import httpx
from typing import Optional, Dict, Any


async def fetch_maisretorno_stats(ticker: str, api_key: Optional[str]) -> Dict[str, Any]:
    """
    Busca e mapeia as estatísticas de um ativo via API oficial do Mais Retorno.
    Mapeamento original mantido (Total = begin).
    """
    ticker_clean = ticker.strip().lower()
    identifier = f"{ticker_clean}:b3"

    if not api_key or not api_key.strip():
        return {
            "maisretorno_status": "erro_sem_key",
            "rentabilidade_total": None,
            "sharpe_total": None,
            "rentabilidade_12m": None,
            "sharpe_12m": None
        }

    url = f"https://data.maisretorno.com/mr-data/v4/api/stats/{identifier}"
    headers = {
        "X-Api-Key": api_key,
        "Accept": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)

            if resp.status_code in (401, 403):
                return {
                    "maisretorno_status": "erro_key_invalida",
                    "rentabilidade_total": None,
                    "sharpe_total": None,
                    "rentabilidade_12m": None,
                    "sharpe_12m": None
                }

            resp.raise_for_status()
            data = resp.json()

            stats_root = data.get("stats", {}) or {}
            timeframes = stats_root.get("timeframe", {}) or {}

            # Total busca exclusivamente da janela 'begin'
            tf_begin = timeframes.get("begin", {}) or {}
            rent_total = tf_begin.get("profitability")
            sharpe_total = tf_begin.get("sharpe_ratio")

            return {
                "maisretorno_status": "sucesso",
                "rentabilidade_total": round(rent_total, 2) if isinstance(rent_total, (int, float)) else None,
                "sharpe_total": round(sharpe_total, 2) if isinstance(sharpe_total, (int, float)) else None,
            }

    except Exception as e:
        return {
            "maisretorno_status": "erro_execucao",
            "detalhe": str(e),
            "rentabilidade_total": None,
            "sharpe_total": None,
        }