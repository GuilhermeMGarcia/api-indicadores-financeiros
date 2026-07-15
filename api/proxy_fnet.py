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

    # 1. PEGA A DATA DE HOJE E DEFINE O PRIMEIRO DIA DO MÊS CORRENTE (FUSO SÃO PAULO)
    try:
        fuso_br = zoneinfo.ZoneInfo("America/Sao_Paulo")
        now = datetime.now(fuso_br)
    except Exception:
        now = datetime.now()

    # Formata as datas no padrão que a B3 (FNET) exige: DD/MM/AAAA
    data_inicial = f"01/{now.strftime('%m/%Y')}"   # Ex: 01/07/2026
    data_final = now.strftime("%d/%m/%Y")          # Ex: 15/07/2026

    # Parâmetros oficiais com o novo filtro por data
    params = {
        "d": "1",
        "s": "0",
        "l": "30",  # Limite máximo de amostragem no teste
        "cnpjFundo": cnpj_limpo,
        "tipoFundo": "1",
        "dataInicial": data_inicial,  # Filtro nativo do FNET
        "dataFinal": data_final,      # Filtro nativo do FNET
        "order[0][column]": "4",
        "order[0][dir]": "desc"
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": f"{FNET_SESSION_URL}?cnpjFundo={cnpj_limpo}",
        "X-Requested-With": "XMLHttpRequest"
    }

    TIPOS_PERMITIDOS = ["relatorio gerencial", "informe mensal estruturado", "informe mensal"]
    max_tentativas = 3

    async with httpx.AsyncClient(follow_redirects=True) as client:
        for tentativa in range(1, max_tentativas + 1):
            try:
                # Passo 1: Handshake
                session_headers = {"User-Agent": headers["User-Agent"]}
                session_params = {"cnpjFundo": cnpj_limpo}
                await client.get(FNET_SESSION_URL, params=session_params, headers=session_headers, timeout=8.0)

                # Passo 2: Busca os dados já filtrados por data pela B3
                response = await client.get(FNET_DATA_URL, params=params, headers=headers, timeout=10.0)

                if response.status_code == 200:
                    raw_data = response.json()
                    raw_docs = raw_data.get("data", []) or []

                    # Filtramos o retorno no proxy para ver apenas os tipos de interesse
                    filtered_docs = []
                    for doc in raw_docs:
                        tipo = (doc.get("tipoDocumento") or "").strip()
                        if any(t in tipo.lower() for t in TIPOS_PERMITIDOS):
                            filtered_docs.append({
                                "dataEntrega": doc.get("dataEntrega"),
                                "categoria": doc.get("categoriaDocumento"),
                                "tipo": tipo,
                                "assunto": doc.get("assunto"),
                                "id": doc.get("id")
                            })

                    return {
                        "status_code_fnet": response.status_code,
                        "cnpj_pesquisado": cnpj_limpo,
                        "intervalo_pesquisado": f"{data_inicial} ate {data_final}",
                        "total_documentos_encontrados_b3": len(raw_docs),
                        "documentos_filtrados_por_tipo": filtered_docs
                    }
                else:
                    raise httpx.HTTPStatusError(f"HTTP {response.status_code}", request=response.request, response=response)
            except Exception as e:
                await asyncio.sleep(0.5 * tentativa)

        return JSONResponse(status_code=502, content={"erro": "Todas as tentativas falharam."})