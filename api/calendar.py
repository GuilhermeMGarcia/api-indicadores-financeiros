import asyncio
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx

router = APIRouter()

class CalendarRequest(BaseModel):
    fundos: List[Dict[str, str]]
    current_month_only: Optional[bool] = True

# Controla no máximo 3 consultas simultâneas na B3 para evitar rate-limit
SEMAFORO_CONCORRENCIA = asyncio.Semaphore(3)

async def fetch_fundo_events_via_proxy(client: httpx.AsyncClient, ticker: str, cnpj: str) -> List[dict]:
    proxy_url = f"https://api-indicadores-financeiros.vercel.app/api/proxy_fnet/{cnpj}"
    eventos_do_fundo = []

    async with SEMAFORO_CONCORRENCIA:
        try:
            response = await client.get(proxy_url, timeout=15.0)
            if response.status_code == 200:
                data = response.json()
                for doc in data.get("documentos", []):
                    evento_formatado = {
                        "ticker": ticker,
                        "data_envio": doc.get("dataEntrega", "N/A"),
                        "tipo_documento": doc.get("tipoDocumento", "N/A"),
                        "assunto": doc.get("informacoesAdicionais") or "N/A",
                        "link": f"https://fnet.bmfbovespa.com.br/fnet/publico/exibirDocumento?id={doc.get('id')}"
                    }
                    eventos_do_fundo.append(evento_formatado)
        except Exception as e:
            print(f"Erro ao consultar proxy para {ticker}: {e}")

        # Pequena pausa entre lotes para manter as sessões ativas no FNET
        await asyncio.sleep(0.1)

    return eventos_do_fundo

@router.post("/calendar", tags=["Calendário de Eventos (FNET)"])
async def get_calendar_events(payload: CalendarRequest):
    if not payload.fundos:
        raise HTTPException(status_code=400, detail="Lista de fundos vazia.")

    async with httpx.AsyncClient() as client:
        tasks = [
            fetch_fundo_events_via_proxy(client, f["ticker"], f["cnpj"])
            for f in payload.fundos if f.get("cnpj")
        ]
        results = await asyncio.gather(*tasks)

    all_events = [item for sublist in results for item in sublist]
    all_events.sort(key=lambda x: x.get("data_envio", ""), reverse=True)

    return all_events