import asyncio
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter
from fastapi.responses import JSONResponse
import httpx

router = APIRouter()

# 🚀 Mudamos para HTTP puro conforme o código de sucesso do Git!
FNET_DATA_URL = "http://fnet.bmfbovespa.com.br/fnet/publico/pesquisarGerenciadorDocumentosDados"


@router.get("/proxy_fnet/{cnpj}", tags=["Ferramentas de Diagnóstico (Proxy)"])
async def debug_fnet_raw(cnpj: str):
    cnpj_limpo = cnpj.replace(".", "").replace("-", "").replace("/", "").strip()

    # 🕒 Fuso Horário de Brasília (UTC-3) seguro e nativo do Python
    fuso_br = timezone(timedelta(hours=-3))
    now = datetime.now(fuso_br)

    # Define o período do mês corrente (MM/AAAA) para usar como filtro nativo se necessário
    mes_ano_atual = now.strftime("%m/%Y")

    # Parâmetros simplificados e robustos baseados na URL do Git
    params = {
        "d": "22",
        "s": "0",
        "l": "30",
        "tipoFundo": "1",  # FII
        "situacao": "A",  # Ativo
        "cnpj": cnpj_limpo,  # Usando 'cnpj' em vez de 'cnpjFundo' conforme o Git de sucesso
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
    }

    TIPOS_PERMITIDOS = ["relatorio gerencial", "relatório gerencial", "informe mensal", "informe mensal estruturado"]
    max_tentativas = 2

    async with httpx.AsyncClient(follow_redirects=True) as client:
        for tentativa in range(1, max_tentativas + 1):
            try:
                # Faz a chamada HTTP direta para a API de dados (sem necessidade de handshake prévio no HTTP do FNET!)
                response = await client.get(FNET_DATA_URL, params=params, headers=headers, timeout=12.0)

                if response.status_code == 200:
                    raw_data = response.json()
                    raw_docs = raw_data.get("data", []) or []

                    filtered_docs = []
                    for doc in raw_docs:
                        categoria = (doc.get("categoriaDocumento") or "").strip()
                        tipo = (doc.get("tipoDocumento") or "").strip()
                        especie = (doc.get("especieDocumento") or "").strip()
                        assunto = (doc.get("assunto") or "").strip()
                        descricao_modalidade = (doc.get("descricaoModalidade") or "").strip()

                        # Cria bloco de busca de texto
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
                    raise httpx.HTTPStatusError(f"HTTP {response.status_code}", request=response.request,
                                                response=response)

            except Exception as e:
                if tentativa == max_tentativas:
                    return JSONResponse(
                        status_code=502,
                        content={
                            "erro": f"Falha ao conectar na API da B3 via HTTP após {max_tentativas} tentativas.",
                            "detalhe": str(e)
                        }
                    )
                await asyncio.sleep(0.5)