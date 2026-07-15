import time
import httpx
import asyncio
from datetime import datetime
from fastapi import APIRouter

router = APIRouter()

FNET_SESSION_URL = "https://fnet.bmfbovespa.com.br/fnet/publico/abrirGerenciadorDocumentosCVM"
FNET_DATA_URL = "https://fnet.bmfbovespa.com.br/fnet/publico/pesquisarGerenciadorDocumentosDados"


async def buscar_com_retry(client, cnpj_limpo, headers, params, max_tentativas=3):
    """Executa a chamada com estratégia de retry."""
    for tentativa in range(max_tentativas):
        try:
            # Garante o handshake antes de cada requisição principal para renovar o cookie
            await client.get(FNET_SESSION_URL, params={"cnpjFundo": cnpj_limpo}, headers=headers, timeout=5.0)

            response = await client.get(FNET_DATA_URL, params=params, headers=headers, timeout=8.0)

            if response.status_code == 200:
                return response.json()
        except Exception:
            if tentativa == max_tentativas - 1: raise
            await asyncio.sleep(1 * (tentativa + 1))  # Aumenta o tempo de espera (1s, 2s...)
    return None


@router.get("/proxy_fnet/{cnpj}", tags=["Ferramentas de Diagnóstico (Proxy)"])
async def debug_fnet_raw(cnpj: str):
    cnpj_limpo = cnpj.replace(".", "").replace("-", "").replace("/", "").strip()

    params = {
        "d": "1", "s": "0", "l": "30",
        "cnpjFundo": cnpj_limpo,
        "o[0][dataReferencia]": "desc",
        "isSession": "true",
        "_": str(int(time.time() * 1000)),
    }
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    async with httpx.AsyncClient(verify=False, follow_redirects=True) as client:
        raw_data = await buscar_com_retry(client, cnpj_limpo, headers, params)

    if not raw_data:
        return {"erro": "Falha após múltiplas tentativas"}

    # Filtro lógico mantido
    hoje = datetime.now()
    docs = [d for d in raw_data.get("data", []) if
            datetime.strptime(d.get("dataEntrega", "01/01/2000 00:00"), "%d/%m/%Y %H:%M").month == hoje.month and
            (d.get("tipoDocumento") == "Relatório Gerencial" or d.get(
                "tipoDocumento") == "Informe Mensal Estruturado" or (
                         d.get("tipoDocumento") == "Informe Mensal" and d.get("arquivoEstruturado") == "S"))]

    return {"status": "success", "total_filtrado": len(docs), "documentos": docs}