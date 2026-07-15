import asyncio
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter
from fastapi.responses import JSONResponse
import httpx

router = APIRouter()

FNET_SESSION_URL = "http://fnet.bmfbovespa.com.br/fnet/publico/abrirGerenciadorDocumentosCVM"
FNET_DATA_URL = "http://fnet.bmfbovespa.com.br/fnet/publico/pesquisarGerenciadorDocumentosDados"

@router.get("/proxy_fnet/{cnpj}", tags=["Ferramentas de Diagnóstico (Proxy)"])
async def debug_fnet_raw(cnpj: str):
    cnpj_limpo = cnpj.replace(".", "").replace("-", "").replace("/", "").strip()

    # 🕒 Fuso Horário de Brasília (UTC-3)
    fuso_br = timezone(timedelta(hours=-3))
    now = datetime.now(fuso_br)

    # Parâmetros estruturados sob o padrão de cookies da sessão
    params = {
        "d": "1",
        "s": "0",
        "l": "50",               # Maior amostragem para garantir a captura
        "tipoFundo": "1",
        "cnpjFundo": cnpj_limpo, # Chave oficial do gerenciador
        "cnpj": cnpj_limpo       # Chave redundante para retrocompatibilidade
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": f"{FNET_SESSION_URL}?cnpjFundo={cnpj_limpo}",
        "X-Requested-With": "XMLHttpRequest"
    }

    TIPOS_PERMITIDOS = ["relatorio gerencial", "relatório gerencial", "informe mensal", "informe mensal estruturado"]
    max_tentativas = 3

    # Instanciação do cliente assíncrono persistindo cookies de forma nativa
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for tentativa in range(1, max_tentativas + 1):
            try:
                # 1. Executa o Handshake para obter e persistir os cookies de sessão no cliente
                session_params = {"cnpjFundo": cnpj_limpo}
                await client.get(FNET_SESSION_URL, params=session_params, headers={"User-Agent": headers["User-Agent"]}, timeout=8.0)

                # 2. Executa a requisição de dados sob a mesma sessão de cookies
                response = await client.get(FNET_DATA_URL, params=params, headers=headers, timeout=12.0)

                if response.status_code == 200:
                    raw_data = response.json()
                    raw_docs = raw_data.get("data", []) or []

                    filtered_docs = []
                    for doc in raw_docs:
                        # Validação de segurança: ignora registros que vazaram de outros CNPJs
                        doc_cnpj = doc.get("cnpjFundo") or ""
                        if doc_cnpj:
                            doc_cnpj_limpo = doc_cnpj.replace(".", "").replace("-", "").replace("/", "").strip()
                            if doc_cnpj_limpo != cnpj_limpo:
                                continue

                        categoria = (doc.get("categoriaDocumento") or "").strip()
                        tipo = (doc.get("tipoDocumento") or "").strip()
                        especie = (doc.get("especieDocumento") or "").strip()
                        assunto = (doc.get("assunto") or "").strip()
                        descricao_modalidade = (doc.get("descricaoModalidade") or "").strip()

                        texto_busca = f"{categoria} {tipo} {especie} {descricao_modalidade} {assunto}".lower()

                        if not any(termo in texto_busca for termo in TIPOS_PERMITIDOS):
                            continue

                        data_envio_str = doc.get("dataEntrega") or doc.get("dataEnvio") or ""
                        if not data_envio_str:
                            continue

                        try:
                            dt_envio = datetime.strptime(data_envio_str, "%d/%m/%Y %H:%M")
                        except ValueError:
                            continue

                        # Filtra apenas registros do mês e ano correntes
                        if dt_envio.month != now.month or dt_envio.year != now.year:
                            continue

                        filtered_docs.append({
                            "id_documento": doc.get("id"),
                            "data_envio": data_envio_str,
                            "cnpj_retornado": doc_cnpj,
                            "nome_fundo": doc.get("descricaoFundo"),
                            "categoria": categoria,
                            "tipo": tipo or "N/A",
                            "assunto": assunto or "N/A"
                        })

                    return {
                        "status_code_fnet": response.status_code,
                        "cnpj_pesquisado": cnpj_limpo,
                        "tentativa": tentativa,
                        "total_recebido_da_b3": len(raw_docs),
                        "total_filtrado_mes_corrente": len(filtered_docs),
                        "documentos": filtered_docs,
                        "dados_originais_b3_primeiro_item": raw_docs[0] if raw_docs else {}
                    }
                else:
                    raise httpx.HTTPStatusError(f"HTTP {response.status_code}", request=response.request, response=response)

            except Exception as e:
                if tentativa == max_tentativas:
                    return JSONResponse(
                        status_code=502,
                        content={
                            "erro": f"Falha na execução após {max_tentativas} tentativas.",
                            "detalhe": str(e)
                        }
                    )
                await asyncio.sleep(0.5 * tentativa)