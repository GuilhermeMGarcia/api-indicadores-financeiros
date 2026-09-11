import time
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from curl_cffi import requests
from api.Cache import TTLCache

router = APIRouter()

# Cache do HTML bruto por ticker, por 30 minutos — mesma política usada
# no proxy_quantbrasil.py e no proxy.py.
PROXY_MAISRETORNO_CACHE_TTL_SECONDS = 30 * 60  # 30 minutos
proxy_maisretorno_cache = TTLCache(ttl_seconds=PROXY_MAISRETORNO_CACHE_TTL_SECONDS)

# Lista de navegadores para alternar caso um tome bloqueio/desafio (Cloudflare/WAF)
IMPERSONATES = ["chrome120", "chrome119", "safari15_5"]

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}


def _fetch_com_retry(url: str, retries: int = 3, backoff_factor: float = 0.5):
    """
    Usa Session e rotaciona o impersonate do curl-cffi para furar bloqueios
    de fingerprint TLS (Cloudflare/WAF) do Mais Retorno.
    """
    session = requests.Session()
    resp = None

    for attempt in range(retries):
        browser = IMPERSONATES[attempt % len(IMPERSONATES)]
        try:
            resp = session.get(
                url,
                headers=HEADERS,
                impersonate=browser,
                timeout=12
            )

            html_lower = resp.text.lower()

            eh_bloqueio = (
                "just a moment..." in html_lower or
                "enable javascript" in html_lower or
                "attention required" in html_lower or
                resp.status_code in (403, 503)
            )

            if resp.status_code == 200 and not eh_bloqueio:
                return resp

            if attempt < retries - 1:
                time.sleep(backoff_factor * (attempt + 1))

        except Exception:
            if attempt < retries - 1:
                time.sleep(backoff_factor * (attempt + 1))
            else:
                raise

    return resp


@router.get("/proxy_maisretorno/{ticker}", response_class=HTMLResponse)
async def proxy_maisretorno(ticker: str):
    """
    Rota de diagnóstico e bypass: faz a requisição direta ao HTML público do Mais Retorno
    (via curl_cffi, imitando fingerprint de navegador real) e devolve o HTML bruto
    para inspeção e testes de extração.
    """
    ticker_clean = ticker.strip().lower()

    cached_content = proxy_maisretorno_cache.get(ticker_clean)
    if cached_content is not None:
        return HTMLResponse(content=cached_content, status_code=200)

    url = f"https://maisretorno.com/acoes/{ticker_clean}"

    try:
        resp = await asyncio.to_thread(_fetch_com_retry, url)

        if resp is None:
            raise HTTPException(status_code=500, detail="Falha na conexão com o Mais Retorno: sem resposta.")

        if resp.status_code in (403, 503):
            raise HTTPException(
                status_code=resp.status_code,
                detail="Requisição bloqueada pelo Cloudflare/WAF do Mais Retorno."
            )

        if resp.status_code != 200:
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"Erro ao acessar página do Mais Retorno: HTTP {resp.status_code}"
            )

        content = resp.text
        proxy_maisretorno_cache.set(ticker_clean, content)

        return HTMLResponse(content=content, status_code=200)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Falha na conexão com o Mais Retorno: {str(e)}"
        )