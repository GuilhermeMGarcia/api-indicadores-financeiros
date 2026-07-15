import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx
import zoneinfo

router = APIRouter()

# URLs oficiais de fluxo de dados do FNET da B3
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
        limit: int = 15
) -> List[dict]:
    """
    Busca de forma paralela os documentos de um FII aplicando o fluxo de handshake,
    cookies e mecanismo de re-tentativa idêntico ao proxy validado.
    """
    # Remove formatações do CNPJ
    cnpj_limpo = cnpj.replace(".", "").replace("-", "").replace("/", "").strip()

    # Parâmetros oficiais exigidos pela B3
    params = {
        "d": "0",  # draw
        "s": "0",  # start
        "l": str(limit),  # limit de documentos
        "cnpjFundo": cnpj_limpo,
        "tipoFundo": "1"
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": f"{FNET_SESSION_URL}?cnpjFundo={cnpj_limpo}",
        "X-Requested-With": "XMLHttpRequest"
    }

    max_tentativas = 3
    events = []

    for tentativa in range(1, max_tentativas + 1):
        try:
            # Passo 1: Realiza o Handshake para estabelecer a sessão do IP
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

            # Passo 2: Consome a API de dados utilizando a sessão estabelecida
            response = await client.get(FNET_DATA_URL, params=params, headers=headers, timeout=10.0)

            if response.status_code == 200:
                data = response.json()
                raw_docs = data.get("data", []) or []

                # Definição do fuso horário brasileiro para comparação
                try:
                    fuso_br = zoneinfo.ZoneInfo("America/Sao_Paulo")
                    now = datetime.now(fuso_br)
                except Exception:
                    now = datetime.now()

                mes_atual = now.month
                ano_atual = now.year

                for doc in raw_docs:
                    # No FNET, a data de publicação oficial que o usuário vê é 'dataEntrega'
                    data_envio_str = doc.get("dataEntrega") or doc.get("dataEnvio") or ""

                    if not data_envio_str:
                        continue

                    try:
                        # Faz a conversão para validar o período
                        dt_envio = datetime.strptime(data_envio_str, "%d/%m/%Y %H:%M")
                    except ValueError:
                        continue

                    # Filtra apenas o mês e ano do calendário atualizado
                    if current_month_only:
                        if dt_envio.month != mes_atual or dt_envio.year != ano_atual:
                            continue

                    doc_id = doc.get("id")
                    pdf_link = f"https://fnet.bmfbovespa.com.br/fnet/publico/exibirDocumento?id={doc_id}" if doc_id else ""

                    categoria = doc.get("categoriaDocumento", "").strip()
                    sub_categoria = doc.get("subCategoriaDocumento", "").strip()
                    tipo_doc = f"{categoria} - {sub_categoria}" if sub_categoria else categoria

                    events.append({
                        "ticker": ticker,
                        "cnpj": cnpj_limpo,
                        "data_envio": data_envio_str,
                        "tipo_documento": tipo_doc,
                        "assunto": doc.get("assunto", "").strip() or "N/A",
                        "link": pdf_link
                    })

                # Se completou o processamento com sucesso (mesmo que retorne vazio por conta do mês), interrompe o loop de tentativas
                return events

            else:
                raise httpx.HTTPStatusError(
                    f"Erro de dados (HTTP {response.status_code})",
                    request=response.request,
                    response=response
                )

        except Exception as e:
            # Em caso de falhas de comunicação com a B3, aguarda um tempo progressivo e tenta de novo
            if tentativa == max_tentativas:
                print(f"Erro definitivo ao buscar FNET para {ticker} após {max_tentativas} tentativas: {e}")
            await asyncio.sleep(0.5 * tentativa)

    return events


@router.post("/calendar", tags=["Calendário de Eventos (FNET)"])
async def get_calendar_events(payload: CalendarRequest):
    if not payload.fundos:
        raise HTTPException(status_code=400, detail="A lista de fundos não pode estar vazia.")

    # Gerenciamento dinâmico e paralelo das requisições assíncronas de todos os ativos
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

    # Ordenação dos eventos consolidados de todos os FIIs por data decrescente
    all_events.sort(key=parse_date, reverse=True)

    return all_events