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

    for lbl_td, data_td in zip(labels, datas):
        lbl = lbl_td.get_text(strip=True).replace("?", "")
        val = data_td.get_text(strip=True)

        # Usando um dicionário de mapeamento para deixar o código mais limpo que o match/case
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
        }

        if lbl in mapeamento:
            key, func = mapeamento[lbl]
            res[key] = func(val)

        elif lbl == "Rend. Distribuído":
            key = "rend_distribuído_12m" if rend_count == 0 else "rend_distribuído_3m"
            res[key] = parse_int(val)
            rend_count += 1

    return res