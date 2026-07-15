import asyncio
from datetime import datetime
from fastapi import APIRouter
from fastapi.responses import JSONResponse
import httpx
import zoneinfo

router = APIRouter()

FNET_SESSION_URL = "https://fnet.bmfbovespa.com.br/fnet/publico/abrirGerenciadorDocumentosCVM"
FNET_DATA_URL = "https://fnet.bmfbovespa.com.br/fnet/publico/pesquisarGerenciadorDocumentosDados"

@router.get("/proxy_fnet/{cnpj}", tags=["Ferramentas de Diagnóstico (Proxy)"])
async def debug_fnet_raw(cnpj: str):
    cnpj_limpo = cnpj.replace(".", "").replace("-", "").replace("/", "").strip()

    # Parâmetros simples e diretos para não confundir a rota da B3
    params = {
        "d_draw": "1",
        "d_start": "0",
        "d_length": "100",  # Trazemos uma quantidade maior para garantir que o mês atual esteja no meio
        "cnpjFundo": cnpj_limpo,
        "tipoFundo": "1"
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": f"{FNET_SESSION_URL}?cnpjFundo={cnpj_limpo}",
        "X-Requested-With": "XMLHttpRequest"
    }

    TIPOS_PERMITIDOS = ["relatorio gerencial", "informe mensal estruturado", "informe mensal"]
    max_tentativas = 3

    # Define o fuso horário correto do Brasil
    try:
        fuso_br = zoneinfo.ZoneInfo("America/Sao_Paulo")
        now = datetime.now(fuso_br)
    except Exception:
        now = datetime.now()

    mes_atual = now.month
    ano_atual = now.year

    async with httpx.AsyncClient(follow_redirects=True) as client:
        for tentativa in range(1, max_tentativas + 1):
            try:
                # Passo 1: Handshake
                session_headers = {"User-Agent": headers["User-Agent"]}
                session_params = {"cnpjFundo": cnpj_limpo}
                await client.get(FNET_SESSION_URL, params=session_params, headers=session_headers, timeout=8.0)

                # Passo 2: Consome os dados brutos
                response = await client.get(FNET_DATA_URL, params=params, headers=headers, timeout=12.0)

                if response.status_code == 200:
                    raw_data = response.json()
                    raw_docs = raw_data.get("data", []) or []

                    # 1. Filtramos e limpamos os dados no Python
                    filtered_docs = []
                    for doc in raw_docs:
                        tipo = (doc.get("tipoDocumento") or "").strip()
                        categoria = (doc.get("categoriaDocumento") or "").strip()
                        tipo_doc_formatado = f"{categoria} - {tipo}" if tipo and categoria else (tipo or categoria)

                        # Filtro por tipo
                        if not any(t in tipo.lower() for t in TIPOS_PERMITIDOS):
                            continue

                        # Captura e validação da data
                        data_envio_str = doc.get("dataEntrega") or doc.get("dataEnvio") or ""
                        if not data_envio_str:
                            continue

                        try:
                            dt_envio = datetime.strptime(data_envio_str, "%d/%m/%Y %H:%M")
                        except ValueError:
                            continue

                        # Filtro pelo mês atual
                        if dt_envio.month != mes_atual or dt_envio.year != ano_atual:
                            continue

                        filtered_docs.append({
                            "data_envio": data_envio_str,
                            "dt_object": dt_envio, # temporário para ordenação
                            "tipo_documento": tipo_doc_formatado,
                            "assunto": doc.get("assunto", "").strip() or "N/A",
                            "id": doc.get("id")
                        })

                    # 2. Ordena os documentos filtrados do mais novo para o mais antigo
                    filtered_docs.sort(key=lambda x: x["dt_object"], reverse=True)

                    # Remove o objeto datetime temporário antes de responder
                    for doc in filtered_docs:
                        doc.pop("dt_object", None)

                    return {
                        "status_code_fnet": response.status_code,
                        "cnpj_pesquisado": cnpj_limpo,
                        "tentativa": tentativa,
                        "mes_referencia_pesquisado": f"{mes_atual}/{ano_atual}",
                        "total_bruto_recebido_da_b3": len(raw_docs),
                        "total_filtrado": len(filtered_docs),
                        "documentos": filtered_docs
                    }
                else:
                    raise httpx.HTTPStatusError(f"HTTP {response.status_code}", request=response.request, response=response)
            except Exception as e:
                await asyncio.sleep(0.5 * tentativa)

        return JSONResponse(status_code=502, content={"erro": "Todas as tentativas falharam."})