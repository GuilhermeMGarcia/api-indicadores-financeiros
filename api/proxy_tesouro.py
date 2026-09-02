import time
import asyncio
from bs4 import BeautifulSoup
from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from curl_cffi import requests
from api.Cache import TTLCache

router = APIRouter()

# Cache reduzido para 60s
proxy_tesouro_cache = TTLCache(ttl_seconds=60)

URL_PAGINA_TESOURO = "https://www.tesourodireto.com.br/produtos/dados-sobre-titulos/historico-de-precos-e-taxas"
URL_JSON_TESOURO = "https://www.tesourodireto.com.br/json/treport/tesourodireto.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


def _fetch_com_retry(url: str, retries: int = 3, backoff_factor: float = 0.3):
    """
    Mantém uma sessão ativa (Session) entre as tentativas para
    acumular os cookies do Cloudflare e ignorar o desafio de robô na 1ª chamada.
    """
    session = requests.Session()

    for attempt in range(1, retries + 1):
        try:
            resp = session.get(
                url,
                headers=HEADERS,
                impersonate="chrome120",
                timeout=8
            )

            # Se a resposta contiver scripts de validação de robô/bot no HTML,
            # força o loop a tentar novamente usando os cookies que a Session acabou de salvar
            html_baixo = resp.text.lower()
            eh_desafio_bot = "robot" in html_baixo or "bot" in html_baixo or "just a moment" in html_baixo

            if resp.status_code == 200 and not eh_desafio_bot:
                return resp

            # Se caiu no desafio de robô ou tomou status != 200, aguarda a sessão maturar
            if attempt < retries:
                time.sleep(backoff_factor * attempt)

        except Exception:
            if attempt < retries:
                time.sleep(backoff_factor * attempt)
            else:
                raise

    return resp


@router.get("/proxy_tesouro/status")
async def verificar_status_tesouro():
    """
    Verifica o status do Tesouro sem armazenar erros temporários no cache.
    """
    cached = proxy_tesouro_cache.get("status_mercado")
    if cached is not None:
        return cached

    try:
        # 1. Tenta obter o HTML do Tesouro
        resp = await asyncio.to_thread(_fetch_com_retry, URL_PAGINA_TESOURO)

        # 2. Se o HTML falhar, tenta o endpoint JSON oficial
        if resp.status_code != 200:
            resp_json = await asyncio.to_thread(_fetch_com_retry, URL_JSON_TESOURO)

            if resp_json.status_code != 200:
                # ❌ ATENÇÃO: NÃO SALVA NO CACHE em caso de bloqueio WAF!
                return {
                    "mercado_aberto": True,
                    "status_texto": "Mercado Aberto (Bypass)",
                    "detalhe": f"Bloqueio WAF (HTTP {resp.status_code}).",
                    "erro_conexao": True
                }

            status_resultado = {
                "mercado_aberto": True,
                "status_texto": "Mercado Aberto",
                "detalhe": "Verificado via JSON Fallback",
                "erro_conexao": False
            }
            # ✔️ Salva no cache apenas se obteve resposta VÁLIDA
            proxy_tesouro_cache.set("status_mercado", status_resultado)
            return status_resultado

        # 3. Faz o parse do HTML se respondeu 200 OK
        html_content = resp.text
        soup = BeautifulSoup(html_content, "html.parser")

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

        # ✔️ Salva no cache apenas se obteve resposta VÁLIDA
        proxy_tesouro_cache.set("status_mercado", status_resultado)
        return status_resultado

    except Exception as e:
        # ❌ NÃO SALVA NO CACHE em caso de exceção de rede
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
        if resp.status_code == 200:
            return Response(content=resp.text, media_type="text/html")

        resp_json = await asyncio.to_thread(_fetch_com_retry, URL_JSON_TESOURO)
        return Response(content=resp_json.text, media_type="application/json")
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})