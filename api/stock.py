from fastapi import APIRouter, HTTPException
from api.utils import parse_percent, parse_float, parse_int, get_fundamentus_html

router = APIRouter()


@router.get("/stock/{ticker}")
async def get_stock_data(ticker: str):
    """
    Retorna os indicadores de uma ação de forma assíncrona e otimizada.
    """
    # Busca o HTML diretamente usando a nova função no utils.py
    soup = await get_fundamentus_html(ticker)

    labels = soup.find_all("td", class_="label")
    datas = soup.find_all("td", class_="data")

    if not labels:
        raise HTTPException(status_code=404, detail="Ticker de ação não encontrado")

    res = {}
    lucro_count = 0  # Contador para as duas ocorrências de "Lucro Líquido"

    # Mapeamento: Nome no site -> (Chave no JSON, Função de conversão)
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
            # Verifica se o label está no nosso mapa de tradução
            if lbl in mapeamento:
                key, func = mapeamento[lbl]
                res[key] = func(val)

            # Tratamento especial para o Lucro Líquido (aparece 2 vezes)
            elif lbl == "Lucro Líquido":
                key = "lucro_liquido_12m" if lucro_count == 0 else "lucro_liquido_3m"
                res[key] = parse_int(val)
                lucro_count += 1
        except Exception:
            continue  # Ignora erros de parsing em campos específicos

    if not res:
        raise HTTPException(status_code=404, detail="Nenhum dado válido encontrado para esta ação")

    return res