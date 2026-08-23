import httpx
from fastapi import APIRouter
from fastapi.responses import Response, JSONResponse
from api.utils import HEADERS  # Importa os headers padronizados
from api.Cache import TTLCache

router = APIRouter()

# Cache do HTML bruto por ticker, por 30 minutos — mesma janela usada
# em utils.py, para manter a mesma política de proteção contra bloqueio
# do Fundamentus em toda a API.
PROXY_CACHE_TTL_SECONDS = 30 * 60  # 30 minutos
proxy_cache = TTLCache(ttl_seconds=PROXY_CACHE_TTL_SECONDS)


@router.get("/proxy/{ticker}")
async def proxy_request(ticker: str):
    """
    Rota de diagnóstico: Retorna o HTML bruto do Fundamentus para inspeção.
    Útil para verificar se o site mudou a estrutura das tabelas.
    """
    ticker = ticker.upper()

    cached_content = proxy_cache.get(ticker)
    if cached_content is not None:
        return Response(
            content=cached_content,
            media_type="text/html",
            headers={"X-Proxy-Source": "Fundamentus-Scraper", "X-Cache": "HIT"}
        )

    url = f"https://www.fundamentus.com.br/detalhes.php?papel={ticker}"

    try:
        # Usamos o AsyncClient para não travar a API enquanto espera o site externo
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            resp = await client.get(url, headers=HEADERS)

            # Se o status não for 200, levantamos o erro explicitamente
            resp.raise_for_status()

            # Retorna o conteúdo respeitando a codificação original do Fundamentus (ISO-8859-1)
            # Isso garante que você veja os acentos corretamente no navegador
            content = resp.content.decode("ISO-8859-1")

            proxy_cache.set(ticker, content)

            return Response(
                content=content,
                media_type="text/html",
                headers={"X-Proxy-Source": "Fundamentus-Scraper", "X-Cache": "MISS"}
            )

    except httpx.HTTPStatusError as e:
        return JSONResponse(
            status_code=e.response.status_code,
            content={"error": f"Erro HTTP no Fundamentus: {e.response.status_code}", "ticker": ticker}
        )
    except httpx.RequestError as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Erro de conexão/rede: {str(e)}", "ticker": ticker}
        )