import asyncio
from fastapi import APIRouter, HTTPException
from api.utils import (
    parse_percent, parse_float, parse_int,
    get_fundamentus_html, get_quantbrasil_html, extract_beta_vs_ibov
)

router = APIRouter()

@router.get("/stock/{ticker}")
async def get_stock_data(ticker: str):
    """
    Retorna os indicadores de uma ação executando requisições paralelas para Fundamentus e QuantBrasil.
    """
    # 🎯 Executa a busca do HTML de ambas as fontes simultaneamente para maior velocidade
    soup_fundamentus, soup_qb = await asyncio.gather(
        get_fundamentus_html(ticker),
        get_quantbrasil_html(ticker),
        return_exceptions=True
    )

    # Verifica se a requisição principal do Fundamentus falhou
    if isinstance(soup_fundamentus, Exception) or not soup_fundamentus:
        raise HTTPException(status_code=404, detail="Ticker de ação não encontrado ou erro de conexão")

    labels = soup_fundamentus.find_all("td", class_="label")
    datas = soup_fundamentus.find_all("td", class_="data")

    if not labels:
        raise HTTPException(status_code=404, detail="Ticker de ação não encontrado")

    res = {}
    lucro_count = 0

    mapeamento = {
        "ROE": ("roe", parse_percent),
        "ROIC": ("roic", parse_percent),
        "Marg. Líquida": ("margem_liquida", parse_percent),
        "Div Br/ Patrim": ("divida_patrimonio", parse_float),
        "Cres. Rec (5a)": ("cagr_lucro_5a", parse_percent),
        "Patrim. Líq": ("patrimonio_liquido", parse_int),
        "Nro. Ações": ("qtd_acao", parse_int),
        "P/L": ("p_l", parse_float),
        "P/VP": ("p_vp", parse_float),
        "P/EBIT": ("p_ebit", parse_float),
        "EV / EBITDA": ("ev_ebitda", parse_float),
        "EV / EBIT": ("ev_ebit", parse_float),
        "Marg. EBIT": ("margem_ebit", parse_percent),
        "Ativo": ("ativo", parse_int),
        "Dív. Líquida": ("divida_liquida", parse_int),
        "Dív. Bruta": ("divida_bruta", parse_int),
        "Div. Yield": ("div_yield", parse_percent),
    }

    for lbl_td, data_td in zip(labels, datas):
        lbl = lbl_td.get_text(strip=True).replace("?", "")
        val = data_td.get_text(strip=True)

        try:
            if lbl in mapeamento:
                key, func = mapeamento[lbl]
                res[key] = func(val)
            elif lbl == "Lucro Líquido":
                key = "lucro_liquido_12m" if lucro_count == 0 else "lucro_liquido_3m"
                res[key] = parse_int(val)
                lucro_count += 1
        except Exception:
            continue

    if not res:
        raise HTTPException(status_code=404, detail="Nenhum dado válido encontrado para esta ação")

    # Extrai o Beta do QuantBrasil caso a requisição tenha obtido sucesso
    if isinstance(soup_qb, Exception) or not soup_qb:
        res["beta_ibov_3a"] = None
    else:
        try:
            res["beta_ibov_3a"] = extract_beta_vs_ibov(soup_qb, periodo="3 anos")
        except Exception:
            res["beta_ibov_3a"] = None

    return res