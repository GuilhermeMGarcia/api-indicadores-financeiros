import time
import asyncio
from bs4 import BeautifulSoup
from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from curl_cffi import requests
from api.Cache import TTLCache

router = APIRouter()

proxy_tesouro_cache = TTLCache(ttl_seconds=60)

URL_PAGINA_TESOURO = "https://www.tesourodireto.com.br/produtos/dados-sobre-titulos/historico-de-precos-e-taxas"
URL_JSON_TESOURO = "https://www.tesourodireto.com.br/json/treport/tesourodireto.json"

# Lista de navegadores para alternar caso um tome o desafio "Just a moment..."
IMPERSONATES = ["chrome120", "chrome119", "safari15_5"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}


def _fetch_com_retry(url: str, retries: int = 3, backoff_factor: float = 0.5):
    """
    Usa Session e rotaciona o impersonate do curl-cffi para furar o "Just a moment..." do Cloudflare.
    """
    session = requests.Session()

    for attempt in range(retries):
        # Rotaciona entre chrome e safari em cada tentativa
        browser = IMPERSONATES[attempt % len(IMPERSONATES)]
        try:
            resp = session.get(
                url,
                headers=HEADERS,
                impersonate=browser,
                timeout=8
            )

            html_content = resp.text.lower()

            # Detecta se caiu na tela de bloqueio do Cloudflare
            eh_desafio_cloudflare = (
                    "just a moment..." in html_content or
                    "enable javascript" in html_content or
                    'name="robots"' in html_content
            )

            # Se deu 200 OK E NÃO é a tela do Cloudflare, sucesso!
            if resp.status_code == 200 and not eh_desafio_cloudflare:
                return resp

            # Se caiu no desafio, aguarda um pouco antes de trocar o fingerprint
            if attempt < retries - 1:
                time.sleep(backoff_factor * (attempt + 1))

        except Exception:
            if attempt < retries - 1:
                time.sleep(backoff_factor * (attempt + 1))
            else:
                raise

    return resp


@router.get("/proxy_tesouro/status")
async def verificar_status_tesouro():
    cached = proxy_tesouro_cache.get("status_mercado")
    if cached is not None:
        return cached

    try:
        # 1. Tenta baixar a página principal HTML
        resp = await asyncio.to_thread(_fetch_com_retry, URL_PAGINA_TESOURO)

        # Se mesmo com rotação de fingerprint o HTML vier com bloqueio/desafio, chama a API JSON
        html_lower = resp.text.lower() if resp else ""
        if resp.status_code != 200 or "just a moment..." in html_lower:
            resp_json = await asyncio.to_thread(_fetch_com_retry, URL_JSON_TESOURO)

            if resp_json.status_code != 200:
                # Retorna bypass sem salvar no cache para não travar a aplicação
                return {
                    "mercado_aberto": True,
                    "status_texto": "Mercado Aberto (Bypass)",
                    "detalhe": "Cloudflare WAF ativo. Status presumido aberto.",
                    "erro_conexao": True
                }

            status_resultado = {
                "mercado_aberto": True,
                "status_texto": "Mercado Aberto",
                "detalhe": "Verificado via JSON Fallback",
                "erro_conexao": False
            }
            proxy_tesouro_cache.set("status_mercado", status_resultado)
            return status_resultado

        # 2. Faz o parse do HTML legítimo do Tesouro
        soup = BeautifulSoup(resp.text, "html.parser")

        botao_status = soup.find("button", class_="open-modal-status-mercado")
        texto_botao = botao_status.get_text(strip=True).lower() if botao_status else ""
        texto_html_completo = soup.get_text().lower()

        em_manutencao = (
                "mercado em manutenção" in texto_botao or
                "mercado em manutenção" in texto_html_completo or
                "mercado fechado" in texto_botao
        )

        status_resultado = {
            "mercado_aberto": not em_manutencao,
            "status_texto": "Mercado em Manutenção" if em_manutencao else "Mercado Aberto",
            "detalhe": texto_botao if texto_botao else ("Em manutenção" if em_manutencao else "Operacional"),
            "erro_conexao": False
        }

        proxy_tesouro_cache.set("status_mercado", status_resultado)
        return status_resultado

    except Exception as e:
        return {
            "mercado_aberto": True,
            "status_texto": "Mercado Aberto",
            "detalhe": f"Erro de rede: {str(e)}",
            "erro_conexao": True
        }


@router.get("/proxy_tesouro/raw")
async def proxy_tesouro_raw():
    try:
        resp = await asyncio.to_thread(_fetch_com_retry, URL_PAGINA_TESOURO)
        return Response(content=resp.text, media_type="text/html")
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})