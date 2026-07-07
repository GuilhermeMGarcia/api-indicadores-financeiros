from fastapi import APIRouter, HTTPException
from api.utils import parse_percent, parse_float, parse_int, get_fundamentus_html

router = APIRouter()


@router.get("/fii/{ticker}")
async def get_fii_data(ticker: str):
    soup = await get_fundamentus_html(ticker)

    labels = soup.find_all("td", class_="label")
    datas = soup.find_all("td", class_="data")

    if not labels:
        raise HTTPException(status_code=404, detail="Ticker não encontrado")

    res = {}
    rend_count = 0

    # 1. MAPEAMENTO DE DADOS CLÁSSICOS (Mantido e limpo)
    for lbl_td, data_td in zip(labels, datas):
        lbl = lbl_td.get_text(strip=True).replace("?", "")
        val = data_td.get_text(strip=True)

        mapeamento = {
            "VP/Cota": ("vp_cota", parse_float),
            "Ativos": ("patrimonio", parse_int),
            "Patrim Líquido": ("patrimonio_liq", parse_int),
            "Receita": ("receita_3m", parse_int),
            "Venda de ativos": ("venda_de_ativos_3m", parse_int),
            "FFO": ("ffo_3m", parse_int),
            "Cap Rate": ("cap_rate", parse_percent),
            "Vacância Média": ("vacância_média", parse_percent),
            "Qtd imóveis": ("qtd_imóveis", parse_int),
            "Qtd Unidades": ("qtd_unidades", parse_int),
            "Nro. Cotas": ("qtd_cotas", parse_int),
            "FFO Yield": ("ffo_yield", parse_percent),
            "Div. Yield": ("div_yield", parse_percent),
        }

        if lbl in mapeamento:
            key, func = mapeamento[lbl]
            res[key] = func(val)

        elif lbl == "Rend. Distribuído":
            key = "rend_distribuído_12m" if rend_count == 0 else "rend_distribuído_3m"
            res[key] = parse_int(val)
            rend_count += 1

    # 2. EXTRAÇÃO DINÂMICA DO LINK "Pesquisar Documentos"
    # Buscamos a tag <a> que possui o texto correspondente ao link de pesquisa
    doc_link_tag = soup.find("a", string=lambda text: text and "Pesquisar Documentos" in text)

    if doc_link_tag and doc_link_tag.get("href"):
        href = doc_link_tag.get("href")

        # O Fundamentus às vezes usa links relativos (ex: "documentos.php?papel=HGLG11")
        # Se for relativo, nós concatenamos o domínio base para garantir que o link funcione direto na sua planilha!
        if href.startswith("http"):
            res["doc"] = href
        else:
            # Garante que a URL gerada seja absoluta e válida
            res["doc"] = f"https://www.fundamentus.com.br/{href.lstrip('/')}"
    else:
        res["doc"] = ""  # Fallback caso o link não seja encontrado

    return res