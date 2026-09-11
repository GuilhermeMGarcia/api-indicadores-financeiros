from bs4 import BeautifulSoup


def parse_maisretorno_html(html_content: str) -> dict:
    soup = BeautifulSoup(html_content, "html.parser")

    dados = {
        "rentabilidade_total": None,
        "sharpe_total": None,
        "rentabilidade_12m": None,
        "sharpe_12m": None
    }

    # Busca pelo ID estático 'asset-stats' capturado no inspecionar elemento
    container = soup.find("ul", id="asset-stats")
    if not container:
        return dados

    # Varre as seções dentro da lista
    for card in container.find_all("section"):
        h3 = card.find("h3")
        span = card.find("span")

        if h3 and span:
            titulo = h3.get_text(strip=True).lower()
            valor = span.get_text(strip=True)

            if titulo == "rentabilidade total":
                dados["rentabilidade_total"] = valor
            elif titulo == "sharpe total":
                dados["sharpe_total"] = valor
            elif titulo == "rentabilidade 12m":
                dados["rentabilidade_12m"] = valor
            elif titulo == "sharpe 12m":
                dados["sharpe_12m"] = valor

    return dados