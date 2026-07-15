import asyncio
from fastapi import APIRouter
from fastapi.responses import JSONResponse
import httpx

router = APIRouter()

FNET_SESSION_URL = "https://fnet.bmfbovespa.com.br/fnet/publico/abrirGerenciadorDocumentosCVM"
FNET_DATA_URL = "https://fnet.bmfbovespa.com.br/fnet/publico/pesquisarGerenciadorDocumentosDados"

@router.get("/proxy_fnet/{cnpj}", tags=["Ferramentas de Diagnóstico (Proxy)"])
async def debug_fnet_raw(cnpj: str):
    cnpj_limpo = cnpj.replace(".", "").replace("-", "").replace("/", "").strip()

    params = {
        "d": "1",
        "s": "0",
        "l": "30",  # Puxa os últimos 30 documentos para análise ampla de testes
        "cnpjFundo": cnpj_limpo,
        "tipoFundo": "1",
        "order[0][column]": "4",
        "order[0][dir]": "asc"
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": f"{FNET_SESSION_URL}?cnpjFundo={cnpj_limpo}",
        "X-Requested-With": "XMLHttpRequest"
    }

    max_tentativas = 3
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for tentativa in range(1, max_tentativas + 1):
            try:
                session_headers = {"User-Agent": headers["User-Agent"]}
                session_params = {"cnpjFundo": cnpj_limpo}
                await client.get(FNET_SESSION_URL, params=session_params, headers=session_headers, timeout=8.0)

                response = await client.get(FNET_DATA_URL, params=params, headers=headers, timeout=10.0)

                if response.status_code == 200:
                    return {
                        "status_code_fnet": response.status_code,
                        "cnpj_pesquisado": cnpj_limpo,
                        "tentativa": tentativa,
                        "url_consultada": str(response.url),
                        "dados_brutos_fnet": response.json()
                    }
                else:
                    raise httpx.HTTPStatusError(
                        f"Erro de dados (HTTP {response.status_code})",
                        request=response.request,
                        response=response
                    )
            except Exception as e:
                await asyncio.sleep(0.5 * tentativa)

        return JSONResponse(status_code=502, content={"erro": "Todas as tentativas falharam."})