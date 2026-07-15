import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx
import zoneinfo

router = APIRouter()

FNET_SESSION_URL = "https://fnet.bmfbovespa.com.br/fnet/publico/abrirGerenciadorDocumentosCVM"
FNET_DATA_URL = "https://fnet.bmfbovespa.com.br/fnet/publico/pesquisarGerenciadorDocumentosDados"


class CalendarRequest(BaseModel):
    fundos: List[Dict[str, str]]
    current_month_only: Optional[bool] = True


async def fetch_fundo_events(
        client: httpx.AsyncClient,
        ticker: str,
        cnpj: str,
        current_month_only: bool,
        limit: int = 40  # Aumentamos o limite para garantir uma varredura profunda pré-filtro
) -> List[dict]:
    """
    Busca os documentos oficiais do FII no FNET (B3) ordenando do mais novo
    para o mais antigo e filtrando apenas por Relatórios Gerenciais e Informes Mensais.
    """
    cnpj_limpo = cnpj.replace(".", "").replace("-", "").replace("/", "").strip()

    # Parâmetros de ordenação e paginação oficiais da API DataTables do FNET
    params = {
        "d": "1",  # d_draw
        "s": "0",  # d_start
        "l": str(limit),  # d_length
        "cnpjFundo": cnpj_limpo,
        "tipoFundo": "1",  # 1 = FII

        # 🔥 FORÇA A B3 A ORDENAR POR DATA DE ENTREGA (Coluna Índice 4) EM ORDEM DECRESCENTE (DESC)
        "order[0][column]": "4",
        "order[0][dir]": "desc"
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": f"{FNET_SESSION_URL}?cnpjFundo={cnpj_limpo}",
        "X-Requested-With": "XMLHttpRequest"
    }

    max_tentativas = 3
    events = []

    # Lista de tipos de documentos permitidos (Filtro solicitado)
    TIPOS_PERMITIDOS = [
        "relatorio gerencial",
        "informe mensal estruturado",
        "informe mensal"
    ]

    for tentativa in range(1, max_tentativas + 1):
        try:
            # Passo 1: Handshake para abrir sessão na B3
            session_headers = {"User-Agent": headers["User-Agent"]}
            session_params = {"cnpjFundo": cnpj_limpo}
            session_response = await client.get(
                FNET_SESSION_URL,
                params=session_params,
                headers=session_headers,
                timeout=8.0
            )

            if session_response.status_code != 200:
                raise httpx.HTTPStatusError(
                    f"Erro no handshake inicial (HTTP {session_response.status_code})",
                    request=session_response.request,
                    response=session_response
                )

            # Passo 2: Consome os dados ordenados
            response = await client.get(FNET_DATA_URL, params=params, headers=headers, timeout=10.0)

            if response.status_code == 200:
                data = response.json()
                raw_docs = data.get("data", []) or []

                try:
                    fuso_br = zoneinfo.ZoneInfo("America/Sao_Paulo")
                    now = datetime.now(fuso_br)
                except Exception:
                    now = datetime.now()

                mes_atual = now.month
                ano_atual = now.year

                for doc in raw_docs:
                    # Captura o tipo do documento e a categoria de forma segura
                    tipo_doc_raw = doc.get("tipoDocumento", "").strip()
                    categoria_raw = doc.get("categoriaDocumento", "").strip()

                    # Combina para exibição estruturada
                    tipo_doc_formatado = f"{categoria_raw} - {tipo_doc_raw}" if tipo_doc_raw and categoria_raw else (
                                tipo_doc_raw or categoria_raw)

                    # 1. 🔍 FILTRO DE TIPO: Verifica se o documento é um dos que nos interessam
                    tipo_doc_lower = tipo_doc_raw.lower()
                    if not any(t in tipo_doc_lower for t in TIPOS_PERMITIDOS):
                        continue  # Ignora atas, convocações, regulamentos, etc.

                    # Captura a data de entrega oficial
                    data_envio_str = doc.get("dataEntrega") or doc.get("dataEnvio") or ""
                    if not data_envio_str:
                        continue

                    try:
                        dt_envio = datetime.strptime(data_envio_str, "%d/%m/%Y %H:%M")
                    except ValueError:
                        continue

                    # 2. 📅 FILTRO DE DATA (MÊS CORRENTE): Se ativo, verifica mês/ano
                    if current_month_only:
                        if dt_envio.month != mes_atual or dt_envio.year != ano_atual:
                            continue

                    doc_id = doc.get("id")
                    pdf_link = f"https://fnet.bmfbovespa.com.br/fnet/publico/exibirDocumento?id={doc_id}" if doc_id else ""

                    events.append({
                        "ticker": ticker,
                        "cnpj": cnpj_limpo,
                        "data_envio": data_envio_str,
                        "tipo_documento": tipo_doc_formatado,
                        "assunto": doc.get("assunto", "").strip() or "N/A",
                        "link": pdf_link
                    })

                # Se o processamento concluiu, interrompe as tentativas
                return events

            else:
                raise httpx.HTTPStatusError(
                    f"Erro de dados (HTTP {response.status_code})",
                    request=response.request,
                    response=response
                )

        except Exception as e:
            if tentativa == max_tentativas:
                print(f"Erro definitivo ao buscar FNET para {ticker} após {max_tentativas} tentativas: {e}")
            await asyncio.sleep(0.5 * tentativa)

    return events


@router.post("/calendar", tags=["Calendário de Eventos (FNET)"])
async def get_calendar_events(payload: CalendarRequest):
    if not payload.fundos:
        raise HTTPException(status_code=400, detail="A lista de fundos não pode estar vazia.")

    async with httpx.AsyncClient(follow_redirects=True) as client:
        tasks = [
            fetch_fundo_events(client, f["ticker"], f["cnpj"], payload.current_month_only)
            for f in payload.fundos if f.get("cnpj")
        ]
        results = await asyncio.gather(*tasks)

    all_events = []
    for f_events in results:
        all_events.extend(f_events)

    def parse_date(event):
        try:
            return datetime.strptime(event["data_envio"], "%d/%m/%Y %H:%M")
        except ValueError:
            return datetime.min

    all_events.sort(key=parse_date, reverse=True)

    return all_events