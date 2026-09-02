import cloudscraper
from bs4 import BeautifulSoup
from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from api.Cache import TTLCache

router = APIRouter()

# Cache de 2 minutos para não sobrecarregar
proxy_tesouro_cache = TTLCache(ttl_seconds=120)

URL_PAGINA_TESOURO = "https://www.tesourodireto.com.br/produtos/dados-sobre-titulos/historico-de-precos-e-taxas"

@router.get("/proxy_tesouro/status")
async def verificar_status_tesouro():
    """
    Inspeciona o HTML real da página do Tesouro Direto buscando o botão
    de status '.open-modal-status-mercado' capturado no DevTools.
    """
    cached = proxy_tesouro_cache.get("status_mercado")
    if cached is not None:
        return cached

    try:
        scraper = cloudscraper.create_scraper()
        resp = scraper.get(URL_PAGINA_TESOURO, timeout=15)

        if resp.status_code != 200:
            return JSONResponse(
                status_code=resp.status_code,
                content={"mercado_aberto": False, "status_texto": f"HTTP {resp.status_code} no Tesouro"}
            )

        html_content = resp.text
        soup = BeautifulSoup(html_content, "html.parser")

        # 1. Busca direta pelo botão capturado na sua foto
        botao_status = soup.find("button", class_="open-modal-status-mercado")
        texto_botao = botao_status.get_text(strip=True).lower() if botao_status else ""

        # 2. Busca fallback no texto completo do HTML
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
        return JSONResponse(
            status_code=500,
            content={"mercado_aberto": False, "status_texto": f"Erro de verificação: {str(e)}"}
        )


@router.get("/proxy_tesouro/raw")
async def proxy_tesouro_raw():
    """
    Retorna o HTML da página do Tesouro para verificação visual.
    """
    try:
        scraper = cloudscraper.create_scraper()
        resp = scraper.get(URL_PAGINA_TESOURO, timeout=15)
        return Response(content=resp.text, media_type="text/html")
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})