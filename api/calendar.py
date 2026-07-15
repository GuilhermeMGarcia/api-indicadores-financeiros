import asyncio
from datetime import datetime
from typing import List, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx

router = APIRouter()

# URL oficial do serviço de consulta de documentos do FNET da B3
FNET_API_URL = "https://fnet.bmfbovespa.com.br/fnet/publico/pesquisarGerenciadorDocumentosDados"


# Modelo de dados que a API espera receber do Google Sheets
class CalendarRequest(BaseModel):
    fundos: List[Dict[str, str]]  # Exemplo: [{"ticker": "HGLG11", "cnpj": "26502794000185"}]


# Função auxiliar para buscar documentos de um único fundo de forma assíncrona
async def fetch_fundo_events(client: httpx.AsyncClient, ticker: str, cnpj: str, limit: int = 5) -> List[dict]:
    params = {
        "d_draw": "1",
        "d_start": "0",
        "d_length": str(limit),  # Limita a busca aos últimos 'X' documentos do fundo
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

        events = []
        for doc in raw_docs:
            doc_id = doc.get("id")
            # Montamos o link oficial do PDF direto para o documento
            pdf_link = f"https://fnet.bmfbovespa.com.br/fnet/publico/exibirDocumento?id={doc_id}" if doc_id else ""

            # Formatação limpa do tipo de documento
            categoria = doc.get("categoriaDocumento", "").strip()
            sub_categoria = doc.get("subCategoriaDocumento", "").strip()
            tipo_doc = f"{categoria} - {sub_categoria}" if sub_categoria else categoria

            events.append({
                "ticker": ticker,
                "cnpj": cnpj,
                "data_envio": doc.get("dataEnvio", ""),  # Formato original: "DD/MM/AAAA HH:MM"
                "tipo_documento": tipo_doc,
                "assunto": doc.get("assunto", "").strip() or "N/A",
                "link": pdf_link
            })
        return events
    except Exception as e:
        # Silencia erros individuais para não derrubar a consulta dos outros fundos
        print(f"Erro ao buscar FNET para {ticker}: {e}")
        return []


@router.post("/calendar", tags=["Calendário de Eventos (FNET)"])
async def get_calendar_events(payload: CalendarRequest):
    """
    Recebe uma lista de tickers e CNPJs de FIIs, faz consultas paralelas no FNET (B3)
    e retorna uma lista consolidada dos últimos comunicados ordenada por data de envio.
    """
    if not payload.fundos:
        raise HTTPException(status_code=400, detail="A lista de fundos não pode estar vazia.")

    # Usamos httpx.AsyncClient para disparar requisições concorrentes ultrarrápidas
    async with httpx.AsyncClient() as client:
        tasks = [
            fetch_fundo_events(client, f["ticker"], f["cnpj"])
            for f in payload.fundos if f.get("cnpj")
        ]

        # Executa todas as buscas de forma paralela nos servidores da B3/CVM
        results = await asyncio.gather(*tasks)

    # Agrupa todos os resultados das buscas em uma única lista plana
    all_events = []
    for f_events in results:
        all_events.extend(f_events)

    # Função interna para parsear e ordenar as datas "DD/MM/AAAA HH:MM" de forma decrescente
    def parse_date(event):
        try:
            return datetime.strptime(event["data_envio"], "%d/%m/%Y %H:%M")
        except ValueError:
            return datetime.min

    # Ordena os eventos mundiais do mais novo para o mais antigo
    all_events.sort(key=parse_date, reverse=True)

    return all_events