import asyncio
from typing import Optional
from fastapi import APIRouter, Header, HTTPException
from api.utils import (
    parse_int, parse_percent,
    get_fundamentus_html, get_quantbrasil_html,
    extract_beta_vs_ibov
)
from api.maisretorno import fetch_maisretorno_stats
from api.proxy_maisretorno import proxy_maisretorno
from api.maisretorno_parser import parse_maisretorno_html

router = APIRouter()


@router.get("/stock/{ticker}")
async def get_stock_data(
    ticker: str,
    x_maisretorno_key: Optional[str] = Header(None, alias="X-MaisRetorno-Key")
):
    # 1. Executa Fundamentus, QuantBrasil e Proxy Scraping em paralelo
    soup_fundamentus, soup_qb, html_mr_resp = await asyncio.gather(
        get_fundamentus_html(ticker),
        get_quantbrasil_html(ticker),
        proxy_maisretorno(ticker),
        return_exceptions=True
    )

    if isinstance(soup_fundamentus, Exception) or not soup_fundamentus:
        raise HTTPException(status_code=404, detail="Ticker de ação não encontrado no Fundamentus")

    labels = soup_fundamentus.find_all("td", class_="label")
    datas = soup_fundamentus.find_all("td", class_="data")

    if not labels:
        raise HTTPException(status_code=404, detail="Ticker de ação não encontrado")

    res = {}

    mapeamento_bruto = {
        "Últ balanço processado": ("ult_balanco_processado", lambda x: x),
        "Nro. Ações": ("qtd_acao", parse_int),
        "Cres. Rec (5a)": ("cagr_receita_5a", parse_percent),
        "Ativo": ("ativo", parse_int),
        "Disponibilidades": ("disponibilidades", parse_int),
        "Dív. Bruta": ("divida_bruta", parse_int),
        "Patrim. Líq": ("patrimonio_liquido", parse_int),
    }

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

            elif lbl in mapeamento_dre_12m:
                key = mapeamento_dre_12m[lbl]
                if key not in res:
                    res[key] = parse_int(val)
        except Exception:
            continue

    # Beta via QuantBrasil
    if isinstance(soup_qb, Exception) or not soup_qb:
        res["beta_ibov_3a"] = None
    else:
        try:
            res["beta_ibov_3a"] = extract_beta_vs_ibov(soup_qb, periodo="3 anos")
        except Exception:
            res["beta_ibov_3a"] = None

    # 2. EXTRAÇÃO VIA SCRAPING PRIMEIRO
    mr_indicadores = {}
    if not isinstance(html_mr_resp, Exception) and hasattr(html_mr_resp, "body"):
        try:
            html_content = html_mr_resp.body.decode("utf-8")
            mr_indicadores = parse_maisretorno_html(html_content)
        except Exception:
            mr_indicadores = {}

    res["rentabilidade_total"] = mr_indicadores.get("rentabilidade_total")
    res["sharpe_total"] = mr_indicadores.get("sharpe_total")
    res["rentabilidade_12m"] = mr_indicadores.get("rentabilidade_12m")
    res["sharpe_12m"] = mr_indicadores.get("sharpe_12m")

    # 3. FALLBACK DA API (Só acionado se o scraping falhar totalmente)
    scraping_falhou = (
        res["rentabilidade_total"] is None and
        res["sharpe_total"] is None
    )

    if scraping_falhou and x_maisretorno_key:
        mr_metrics = await fetch_maisretorno_stats(ticker, x_maisretorno_key)
        if isinstance(mr_metrics, dict):
            res["rentabilidade_total"] = mr_metrics.get("rentabilidade_total")
            res["sharpe_total"] = mr_metrics.get("sharpe_total")
            if res["rentabilidade_12m"] is None:
                res["rentabilidade_12m"] = mr_metrics.get("rentabilidade_total")
            if res["sharpe_12m"] is None:
                res["sharpe_12m"] = mr_metrics.get("sharpe_total")

    return res