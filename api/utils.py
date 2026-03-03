import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException

# Cabeçalhos globais para simular um navegador real
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.fundamentus.com.br/"
}

def is_empty(value: str | None) -> bool:
    """Verifica se o valor retornado pelo site é nulo ou vazio."""
    if value is None:
        return True
    cleaned = value.strip().replace(",", ".")
    # Retorna True apenas para vazios e termos de erro do site
    return cleaned in ["", "-", "N/A"]

def parse_percent(value: str):
    """Converte '10,50%' em 10.50 (float)"""
    if is_empty(value): return None
    return float(value.replace("%", "").replace(".", "").replace(",", ".").strip())

def parse_float(value: str):
    """Converte '1.234,56' em 1234.56 (float)"""
    if is_empty(value): return None
    return float(value.replace(".", "").replace(",", ".").strip())

def parse_int(value: str):
    """Converte '1.234' em 1234 (int)"""
    if is_empty(value): return None
    return int(value.replace(".", "").replace(",", "").strip())

async def get_fundamentus_html(ticker: str) -> BeautifulSoup:
    """Busca o HTML diretamente do Fundamentus de forma assíncrona."""
    url = f"https://www.fundamentus.com.br/detalhes.php?papel={ticker.upper()}"
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            resp = await client.get(url, headers=HEADERS)
            resp.raise_for_status()
            # Fundamentus usa codificação ISO-8859-1 para acentos
            content = resp.content.decode("ISO-8859-1")
            return BeautifulSoup(content, "html.parser")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao acessar Fundamentus: {str(e)}")