import httpx
from fastapi import APIRouter
from fastapi.responses import Response, JSONResponse
from api.utils import HEADERS  # Reaproveita os mesmos headers de navegador
from api.Cache import TTLCache

router = APIRouter()

# Cache do HTML bruto por ticker, por 30 minutos — mesma janela usada
# no proxy.py, para manter a mesma política de proteção contra bloqueio
# em toda a API.
PROXY_QUANTBRASIL_CACHE_TTL_SECONDS = 30 * 60  # 30 minutos
proxy_quantbrasil_cache = TTLCache(ttl_seconds=PROXY_QUANTBRASIL_CACHE_TTL_SECONDS)


@router.get("/proxy_quantbrasil/{ticker}")
async def proxy_quantbrasil_request(ticker: str):
    """
    Rota de diagnóstico: Retorna o HTML bruto da página do ativo no QuantBrasil.
    Use isso primeiro para confirmar que o site responde e para inspecionar
    a estrutura antes de mexer no parsing do stock.py.
    """
    ticker = ticker.upper()

    cached_content = proxy_quantbrasil_cache.get(ticker)
    if cached_content is not None:
        return Response(
            content=cached_content,
            media_type="text/html",
            headers={"X-Proxy-Source": "QuantBrasil-Scraper", "X-Cache": "HIT"}
        )

    url = f"https://quantbrasil.com.br/ativos/{ticker}/"

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            resp = await client.get(url, headers=HEADERS)
            resp.raise_for_status()

            # QuantBrasil serve UTF-8 (diferente do Fundamentus, que é ISO-8859-1)
            content = resp.text

            proxy_quantbrasil_cache.set(ticker, content)

            return Response(
                content=content,
                media_type="text/html",
                headers={"X-Proxy-Source": "QuantBrasil-Scraper", "X-Cache": "MISS"}
            )

    except httpx.HTTPStatusError as e:
        return JSONResponse(
            status_code=e.response.status_code,
            content={"error": f"Erro HTTP no QuantBrasil: {e.response.status_code}", "ticker": ticker}
        )
    except httpx.RequestError as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Erro de conexão/rede: {str(e)}", "ticker": ticker}
        )