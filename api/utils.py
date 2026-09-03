import re
import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException
from api.Cache import TTLCache

# Cabeçalhos globais para simular um navegador real
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.fundamentus.com.br/"
}

# Cache do HTML do Fundamentus por ticker, por 30 minutos.
# Reduz chamadas repetidas ao Fundamentus (evita risco de bloqueio) e
# diminui o tempo de execução da função na Vercel.
FUNDAMENTUS_CACHE_TTL_SECONDS = 30 * 60  # 30 minutos
fundamentus_cache = TTLCache(ttl_seconds=FUNDAMENTUS_CACHE_TTL_SECONDS)

# Cache do HTML do QuantBrasil por ticker, por 30 minutos — mesma política
# de proteção contra bloqueio usada para o Fundamentus.
QUANTBRASIL_CACHE_TTL_SECONDS = 30 * 60  # 30 minutos
quantbrasil_cache = TTLCache(ttl_seconds=QUANTBRASIL_CACHE_TTL_SECONDS)


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
    ticker = ticker.upper()

    cached_content = fundamentus_cache.get(ticker)
    if cached_content is not None:
        return BeautifulSoup(cached_content, "html.parser")

    url = f"https://www.fundamentus.com.br/detalhes.php?papel={ticker}"
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            resp = await client.get(url, headers=HEADERS)
            resp.raise_for_status()
            content = resp.content.decode("ISO-8859-1")
            soup = BeautifulSoup(content, "html.parser")

            # 🛡️ BLINDAGEM DO CACHE:
            # Só grava no cache se o HTML trouxer a tabela de dados esperada
            if soup.find("td", class_="label"):
                fundamentus_cache.set(ticker, content)

            return soup
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao acessar Fundamentus: {str(e)}")


async def get_quantbrasil_html(ticker: str) -> BeautifulSoup:
    ticker = ticker.upper()

    cached_content = quantbrasil_cache.get(ticker)
    if cached_content is not None:
        return BeautifulSoup(cached_content, "html.parser")

    url = f"https://quantbrasil.com.br/ativos/{ticker}/"
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            resp = await client.get(url, headers=HEADERS)
            resp.raise_for_status()
            content = resp.text
            soup = BeautifulSoup(content, "html.parser")

            # 🛡️ BLINDAGEM DO CACHE:
            # Só grava no cache se o Beta realmente estiver presente no HTML lido
            if extract_beta_vs_ibov(soup) is not None:
                quantbrasil_cache.set(ticker, content)

            return soup
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao acessar QuantBrasil: {str(e)}")


def extract_beta_vs_ibov(soup: BeautifulSoup, periodo: str = "3 anos"):
    """
    Extrai o Beta vs IBOV diretamente navegando na estrutura de tags do QuantBrasil.

    Localiza o <span> que contém o texto do período (ex: '3 anos')
    e pega o valor que está no irmão de tag ou no parágrafo <p> seguinte.
    """
    try:
        # 1. Procura o <span> exatamente com o texto do período (ex: "3 anos")
        span_periodo = soup.find(
            lambda tag: tag.name == "span" and periodo in tag.get_text()
        )

        if not span_periodo:
            return None

        # 2. Na árvore HTML, o valor (0,58) está na mesma div pai do <span>
        parent_div = span_periodo.find_parent("div")
        if not parent_div:
            return None

        # 3. Procura o parágrafo <p> que contém a classe "font-mono" ou "font-semibold" (onde fica o 0,58)
        p_valor = parent_div.find("p")
        if p_valor:
            return parse_float(p_valor.get_text(strip=True))

    except Exception:
        pass

    # --- FALLBACK VIA REGEX MELHORADA ---
    # Caso a estrutura de divs mude um pouco, usa a regex resiliente no texto sem dependência de fim de bloco
    texto = soup.get_text(separator="\n")
    periodo_escapado = re.escape(periodo)

    # Busca "3 anos" seguido de quebras de linha e captura o PRIMEIRO número no formato 0,58
    match = re.search(rf"{periodo_escapado}\s*\n+\s*(-?\d+[.,]\d+)", texto)
    if match:
        return parse_float(match.group(1))

    return None