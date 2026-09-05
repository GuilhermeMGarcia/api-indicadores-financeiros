import asyncio
from fastapi import APIRouter, HTTPException
from api.utils import (
    parse_int, parse_percent, get_fundamentus_html, get_quantbrasil_html, extract_beta_vs_ibov
)

router = APIRouter()


@router.get("/stock/{ticker}")
async def get_stock_data(ticker: str):
    """
    Retorna os dados brutos contábeis de 12 meses + CAGR de Receita (Fundamentus) e o Beta (QuantBrasil) em paralelo.
    """
    # 🎯 Dispara as duas buscas em paralelo
    soup_fundamentus, soup_qb = await asyncio.gather(
        get_fundamentus_html(ticker),
        get_quantbrasil_html(ticker),
        return_exceptions=True
    )

    if isinstance(soup_fundamentus, Exception) or not soup_fundamentus:
        raise HTTPException(status_code=404, detail="Ticker de ação não encontrado ou erro de conexão")

    labels = soup_fundamentus.find_all("td", class_="label")
    datas = soup_fundamentus.find_all("td", class_="data")

    if not labels:
        raise HTTPException(status_code=404, detail="Ticker de ação não encontrado")

    res = {}

    # Mapeamento ajustado sem métricas deriváveis e com o CAGR 5a
    mapeamento_bruto = {
        "Últ balanço processado": ("ult_balanco_processado", lambda x: x),
        "Nro. Ações": ("qtd_acao", parse_int),
        "Cres. Rec (5a)": ("cagr_receita_5a", parse_percent),

        # Balanço Patrimonial
        "Ativo": ("ativo", parse_int),
        "Disponibilidades": ("disponibilidades", parse_int),
        "Dív. Bruta": ("divida_bruta", parse_int),
        "Patrim. Líq": ("patrimonio_liquido", parse_int),
    }

    # Mapeamento da DRE (Apenas a primeira ocorrência = 12 meses)
    mapeamento_dre_12m = {
        "Receita Líquida": "receita_liquida_12m",
        "EBIT": "ebit_12m",
        "Lucro Líquido": "lucro_liquido_12m",
    }

    for lbl_td, data_td in zip(labels, datas):
        lbl = lbl_td.get_text(strip=True).replace("?", "")
        val = data_td.get_text(strip=True)

        try:
            if lbl in mapeamento_bruto:
                key, func = mapeamento_bruto[lbl]
                res[key] = func(val)

            # Captura DRE apenas se ainda NÃO foi adicionado ao dicionário (pega o de 12M e descarta o de 3M)
            elif lbl in mapeamento_dre_12m:
                key = mapeamento_dre_12m[lbl]
                if key not in res:
                    res[key] = parse_int(val)

        except Exception:
            continue

    if not res:
        raise HTTPException(status_code=404, detail="Nenhum dado bruto encontrado para este ticker")

    # Extrai o Beta do QuantBrasil em paralelo
    if isinstance(soup_qb, Exception) or not soup_qb:
        res["beta_ibov_3a"] = None
    else:
        try:
            res["beta_ibov_3a"] = extract_beta_vs_ibov(soup_qb, periodo="3 anos")
        except Exception:
            res["beta_ibov_3a"] = None

    return res