import asyncio
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx

router = APIRouter()


class CalendarRequest(BaseModel):
    fundos: List[Dict[str, str]]
    current_month_only: Optional[bool] = True


async def fetch_fundo_events_via_proxy(client: httpx.AsyncClient, ticker: str, cnpj: str) -> List[dict]:
    """
    Agora o calendar.py não briga com a B3!
    Ele apenas consulta o nosso Proxy robusto que criamos.
    """
    # A URL aponta para o seu próprio endpoint que já está blindado
    proxy_url = f"https://api-indicadores-financeiros.vercel.app/api/proxy_fnet/{cnpj}"

    try:
        response = await client.get(proxy_url, timeout=15.0)
        if response.status_code == 200:
            data = response.json()
            # Adiciona o ticker aos resultados que vieram do proxy
            for doc in data.get("documentos", []):
                doc["ticker"] = ticker
            return data.get("documentos", [])
    except Exception as e:
        print(f"Erro ao consultar proxy para {ticker}: {e}")
    return []


@router.post("/calendar", tags=["Calendário de Eventos (FNET)"])
async def get_calendar_events(payload: CalendarRequest):
    if not payload.fundos:
        raise HTTPException(status_code=400, detail="Lista de fundos vazia.")

    # Dispara todas as chamadas em paralelo (super rápido)
    async with httpx.AsyncClient() as client:
        tasks = [
            fetch_fundo_events_via_proxy(client, f["ticker"], f["cnpj"])
            for f in payload.fundos if f.get("cnpj")
        ]
        results = await asyncio.gather(*tasks)

    # Junta tudo
    all_events = [item for sublist in results for item in sublist]

    # Ordena pelo mais recente
    all_events.sort(key=lambda x: x.get("data_envio", ""), reverse=True)

    return all_events