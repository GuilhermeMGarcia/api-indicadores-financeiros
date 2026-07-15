import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx

router = APIRouter()

# URL oficial do serviço de consulta de documentos do FNET da B3
FNET_API_URL = "https://fnet.bmfbovespa.com.br/fnet/publico/pesquisarGerenciadorDocumentosDados"


# Modelo de dados que a API espera receber do Google Sheets
class CalendarRequest(BaseModel):
    fundos: List[Dict[str, str]]
    current_month_only: Optional[bool] = True  # Flag para ativar/desativar o filtro do mês atual


# Função auxiliar para buscar documentos e filtrar por data
async def fetch_fundo_events(
        client: httpx.AsyncClient,
        ticker: str,
        cnpj: str,
        current_month_only: bool,
        limit: int = 15  # Aumentamos o limite individual para garantir que pegamos todos do mês
) -> List[dict]:
    params = {
        "d_draw": "1",
        "d_start": "0",
        "d_length": str(limit),
        "cnpjFundo": cnpj,
        "tipoFundo": "1"  # Tipo 1 = FII
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = await client.get(FNET_API_URL, params=params, headers=headers, timeout=10.0)
        if response.status_code != 200:
            return []

        data = response.json()
        raw_docs = data.get("data", [])

        # Obtém o mês e ano corrente baseado na data atual
        now = datetime.now()
        mes_atual = now.month
        ano_atual = now.year

        events = []
        for doc in raw_docs:
            data_envio_str = doc.get("dataEnvio", "")  # Formato: "DD/MM/AAAA HH:MM"

            # Tenta converter a string de data para objeto datetime para podermos filtrar
            try:
                dt_envio = datetime.strptime(data_envio_str, "%d/%m/%Y %H:%M")
            except ValueError:
                continue  # Ignora se a data vier corrompida ou inválida

            # APLICA FILTRAGEM DO MÊS ATUAL se a flag estiver ativa
            if current_month_only:
                if dt_envio.month != mes_atual or dt_envio.year != ano_atual:
                    continue  # Pula este documento se não for do mês e ano correntes

            doc_id = doc.get("id")
            pdf_link = f"https://fnet.bmfbovespa.com.br/fnet/publico/exibirDocumento?id={doc_id}" if doc_id else ""

            categoria = doc.get("categoriaDocumento", "").strip()
            sub_categoria = doc.get("subCategoriaDocumento", "").strip()
            tipo_doc = f"{categoria} - {sub_categoria}" if sub_categoria else categoria

            events.append({
                "ticker": ticker,
                "cnpj": cnpj,
                "data_envio": data_envio_str,
                "tipo_documento": tipo_doc,
                "assunto": doc.get("assunto", "").strip() or "N/A",
                "link": pdf_link
            })
        return events
    except Exception as e:
        print(f"Erro ao buscar FNET para {ticker}: {e}")
        return []


@router.post("/calendar", tags=["Calendário de Eventos (FNET)"])
async def get_calendar_events(payload: CalendarRequest):
    """
    Recebe os FIIs e retorna os comunicados oficiais.
    Por padrão, filtra e traz APENAS os documentos do mês corrente.
    """
    if not payload.fundos:
        raise HTTPException(status_code=400, detail="A lista de fundos não pode estar vazia.")

    # Executa de forma assíncrona e paralela para performance brutal
    async with httpx.AsyncClient() as client:
        tasks = [
            fetch_fundo_events(client, f["ticker"], f["cnpj"], payload.current_month_only)
            for f in payload.fundos if f.get("cnpj")
        ]
        results = await asyncio.gather(*tasks)

    all_events = []
    for f_events in results:
        all_events.extend(f_events)

    # Ordenação decrescente pela data de envio
    def parse_date(event):
        try:
            return datetime.strptime(event["data_envio"], "%d/%m/%Y %H:%M")
        except ValueError:
            return datetime.min

    all_events.sort(key=parse_date, reverse=True)

    return all_events