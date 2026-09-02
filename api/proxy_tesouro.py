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
    Inspeciona o HTML ou JSON do Tesouro Direto.
    Diferencia bloqueio HTTP (403/500) de manutenção real do mercado.
    """
    cached = proxy_tesouro_cache.get("status_mercado")
    if cached is not None:
        return cached

    try:
        # 1. Tenta requisição síncrona em thread isolada (Vercel-safe)
        resp = await asyncio.to_thread(_fetch_tesouro_sync)

        # Se for bloqueado pelo Cloudflare (403, 503, etc), ativa o Fallback do JSON
        if resp.status_code != 200:
            resp_json = await asyncio.to_thread(_fetch_tesouro_json_sync)

            # Se até o JSON falhar/bloquear, NÃO assuma Manutenção! Retorne erro de conexao/bypass.
            if resp_json.status_code != 200:
                return {
                    "mercado_aberto": True,  # Permite tentar baixar taxas/CSVs
                    "status_texto": "Mercado Aberto (Bypass)",
                    "detalhe": f"Bloqueio WAF (HTTP {resp.status_code}). Checagem ignorada.",
                    "erro_conexao": True
                }

            # Se o JSON respondeu OK (200)
            status_resultado = {
                "mercado_aberto": True,
                "status_texto": "Mercado Aberto",
                "detalhe": "Verificado via JSON Fallback",
                "erro_conexao": False
            }
            proxy_tesouro_cache.set("status_mercado", status_resultado)
            return status_resultado

        # 2. Se a página HTML respondeu 200, faz o parsing exato
        html_content = resp.text
        soup = BeautifulSoup(html_content, "html.parser")

        botao_status = soup.find("button", class_="open-modal-status-mercado")
        texto_botao = botao_status.get_text(strip=True).lower() if botao_status else ""
        texto_html_completo = soup.get_text().lower()

        # Só é MANUTENÇÃO se o texto no HTML afirmar explicitamente isso!
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
        # Em caso de timeout/crash de rede, assume aberto para não travar a dashboard
        return {
            "mercado_aberto": True,
            "status_texto": "Mercado Aberto",
            "detalhe": f"Erro de rede no proxy: {str(e)}",
            "erro_conexao": True
        }


@router.get("/proxy_tesouro/raw")
@router.get("/proxy_tesouro/raw")
async def proxy_tesouro_raw():
    """
    Retorna a resposta bruta do Tesouro (HTML ou JSON fallback) para verificação.
    """
    try:
        resp = await asyncio.to_thread(_fetch_tesouro_sync)
        if resp.status_code == 200:
            return Response(content=resp.text, media_type="text/html")

        # Se o HTML der erro/bloqueio, retorna o JSON oficial do Tesouro
        resp_json = await asyncio.to_thread(_fetch_tesouro_json_sync)
        return Response(content=resp_json.text, media_type="application/json")
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})