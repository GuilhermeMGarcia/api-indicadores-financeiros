import asyncio
from fastapi import APIRouter, HTTPException
from api.utils import (
    parse_int, get_fundamentus_html, get_quantbrasil_html, extract_beta_vs_ibov
)

router = APIRouter()


@router.get("/stock/{ticker}")
async def get_stock_data(ticker: str):
    """
    Retorna os dados brutos contábeis (Fundamentus) e o Beta (QuantBrasil) em paralelo.
    """
    # 🎯 Dispara as duas buscas em paralelo para não perder velocidade
    soup_fundamentus, soup_qb = await asyncio.gather(
        get_fundamentus_html(ticker),
        get_quantbrasil_html(ticker),
        return_exceptions=True
    )

    # Valida a requisição principal do Fundamentus
    if isinstance(soup_fundamentus, Exception) or not soup_fundamentus:
        raise HTTPException(status_code=404, detail="Ticker de ação não encontrado ou erro de conexão")

    labels = soup_fundamentus.find_all("td", class_="label")
    datas = soup_fundamentus.find_all("td", class_="data")

    if not labels:
        raise HTTPException(status_code=404, detail="Ticker de ação não encontrado")

    res = {}

    receita_count = 0
    ebit_count = 0
    lucro_count = 0

    # Mapeamento exclusivo para DADOS BRUTOS (Sem os indicadores calculados)
    mapeamento_bruto = {
        "Últ balanço processado": ("ult_balanco_processado", lambda x: x),
        "Nro. Ações": ("qtd_acao", parse_int),
        "Valor de mercado": ("valor_de_mercado", parse_int),
        "Valor da firma": ("valor_da_firma", parse_int),

        # Balanço Patrimonial
        "Ativo": ("ativo", parse_int),
        "Disponibilidades": ("disponibilidades", parse_int),
        "Dív. Bruta": ("divida_bruta", parse_int),
        "Dív. Líquida": ("divida_liquida", parse_int),
        "Patrim. Líq": ("patrimonio_liquido", parse_int),
    }

    for lbl_td, data_td in zip(labels, datas):
        lbl = lbl_td.get_text(strip=True).replace("?", "")
        val = data_td.get_text(strip=True)

        try:
            if lbl in mapeamento_bruto:
                key, func = mapeamento_bruto[lbl]
                res[key] = func(val)

            # Tratamento para duplicidades da DRE
            elif lbl == "Receita Líquida":
                key = "receita_liquida_12m" if receita_count == 0 else "receita_liquida_3m"
                res[key] = parse_int(val)
                receita_count += 1

            elif lbl == "EBIT":
                key = "ebit_12m" if ebit_count == 0 else "ebit_3m"
                res[key] = parse_int(val)
                ebit_count += 1

            elif lbl == "Lucro Líquido":
                key = "lucro_liquido_12m" if lucro_count == 0 else "lucro_liquido_3m"
                res[key] = parse_int(val)
                lucro_count += 1

        except Exception:
            continue

    if not res:
        raise HTTPException(status_code=404, detail="Nenhum dado bruto encontrado para este ticker")

    # 🎯 Extrai o Beta do QuantBrasil em paralelo
    if isinstance(soup_qb, Exception) or not soup_qb:
        res["beta_ibov_3a"] = None
    else:
        try:
            res["beta_ibov_3a"] = extract_beta_vs_ibov(soup_qb, periodo="3 anos")
        except Exception:
            res["beta_ibov_3a"] = None

    return res