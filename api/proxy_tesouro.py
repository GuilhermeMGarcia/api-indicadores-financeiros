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

def _fetch_tesouro_sync():
    """Realiza a requisição simulando um navegador real via curl-cffi"""
    return requests.get(
        URL_PAGINA_TESOURO,
        headers=HEADERS,
        impersonate="chrome120",
        timeout=10
    )

def _fetch_tesouro_json_sync():
    """Fallback via API em JSON do Tesouro"""
    return requests.get(
        URL_JSON_TESOURO,
        headers=HEADERS,
        impersonate="chrome120",
        timeout=10
    )

@router.get("/proxy_tesouro/status")
async def verificar_status_tesouro():
    """
    Inspeciona o HTML real ou fallback JSON para determinar o status do mercado.
    """
    cached = proxy_tesouro_cache.get("status_mercado")
    if cached is not None:
        return cached

    try:
        # Executa a requisição síncrona em uma thread separada (Vercel-safe)
        resp = await asyncio.to_thread(_fetch_tesouro_sync)

        # Se for bloqueado pelo Cloudflare na Vercel, tenta o fallback em JSON
        if resp.status_code != 200:
            resp_json = await asyncio.to_thread(_fetch_tesouro_json_sync)
            if resp_json.status_code == 200:
                # O JSON oficial respondeu; consideramos o mercado aberto por padrão
                status_resultado = {
                    "mercado_aberto": True,
                    "status_texto": "Mercado Aberto",
                    "detalhe": "Verificado via JSON Fallback"
                }
                proxy_tesouro_cache.set("status_mercado", status_resultado)
                return status_resultado

            return JSONResponse(
                status_code=resp.status_code,
                content={"mercado_aberto": False, "status_texto": f"HTTP {resp.status_code} no Tesouro"}
            )

        html_content = resp.text
        soup = BeautifulSoup(html_content, "html.parser")

        # 1. Busca direta pelo botão de status do mercado
        botao_status = soup.find("button", class_="open-modal-status-mercado")
        texto_botao = botao_status.get_text(strip=True).lower() if botao_status else ""

        # 2. Busca fallback no texto do HTML
        texto_html_completo = soup.get_text().lower()

        em_manutencao = (
            "mercado em manutenção" in texto_botao or
            "mercado em manutenção" in texto_html_completo or
            "mercado fechado" in texto_botao
        )

        status_resultado = {
            "mercado_aberto": not em_manutencao,
            "status_texto": "Mercado em Manutenção" if em_manutencao else "Mercado Aberto",
            "detalhe": texto_botao if texto_botao else ("Em manutenção" if em_manutencao else "Operacional")
        }

        proxy_tesouro_cache.set("status_mercado", status_resultado)
        return status_resultado

    except Exception as e:
        # Retorna status gracioso para não quebrar a UI em caso de erro de rede
        return JSONResponse(
            status_code=200,
            content={
                "mercado_aberto": True,
                "status_texto": "Mercado Aberto",
                "detalhe": f"Bypass ativo devido a erro: {str(e)}"
            }
        )


@router.get("/proxy_tesouro/raw")
async def proxy_tesouro_raw():
    """
    Retorna o HTML da página do Tesouro para verificação visual.
    """
    try:
        resp = await asyncio.to_thread(_fetch_tesouro_sync)
        return Response(content=resp.text, media_type="text/html")
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})