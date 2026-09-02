import time
import asyncio
from bs4 import BeautifulSoup
from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from curl_cffi import requests
from api.Cache import TTLCache

router = APIRouter()

proxy_tesouro_cache = TTLCache(ttl_seconds=120)

URL_PAGINA_TESOURO = "https://www.tesourodireto.com.br/produtos/dados-sobre-titulos/historico-de-precos-e-taxas"
URL_JSON_TESOURO = "https://www.tesourodireto.com.br/json/treport/tesourodireto.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}


def _fetch_com_retry(url: str, retries: int = 3, backoff_factor: float = 0.5):
    """
    Realiza requisições com sistema de retry automático para contornar
    instabilidades momentâneas de WAF/Cloudflare na Vercel.
    """
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(
                url,
                headers=HEADERS,
                impersonate="chrome120",
                timeout=6
            )
            # Se retornou 200, entrega a resposta imediatamente
            if resp.status_code == 200:
                return resp

            # Se for status de erro (ex: 403, 500, 503), aguarda antes da próxima tentativa
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
    Inspeciona o HTML ou JSON do Tesouro Direto utilizando sistema de Retry.
    """
    cached = proxy_tesouro_cache.get("status_mercado")
    if cached is not None:
        return cached

    try:
        # 1. Primeira tentativa: HTML via Retry
        resp = await asyncio.to_thread(_fetch_com_retry, URL_PAGINA_TESOURO)

        # 2. Se mesmo com retry o HTML falhar, aciona Fallback do JSON também com Retry
        if resp.status_code != 200:
            resp_json = await asyncio.to_thread(_fetch_com_retry, URL_JSON_TESOURO)

            if resp_json.status_code != 200:
                return {
                    "mercado_aberto": True,
                    "status_texto": "Mercado Aberto (Bypass)",
                    "detalhe": f"Bloqueio WAF persistente (HTTP {resp.status_code}).",
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

        # 3. Processamento do HTML quando retornado com sucesso (200 OK)
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

        proxy_tesouro_cache.set("status_mercado", status_resultado)
        return status_resultado

    except Exception as e:
        return {
            "mercado_aberto": True,
            "status_texto": "Mercado Aberto",
            "detalhe": f"Erro de rede persistente: {str(e)}",
            "erro_conexao": True
        }


@router.get("/proxy_tesouro/raw")
async def proxy_tesouro_raw():
    """
    Retorna o HTML bruto utilizando a função de Retry.
    """
    try:
        resp = await asyncio.to_thread(_fetch_com_retry, URL_PAGINA_TESOURO)
        if resp.status_code == 200:
            return Response(content=resp.text, media_type="text/html")

        resp_json = await asyncio.to_thread(_fetch_com_retry, URL_JSON_TESOURO)
        return Response(content=resp_json.text, media_type="application/json")
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})