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
        limit: int = 40  # Amostragem alta para garantir que o mês atual completo seja capturado
) -> List[dict]:
    cnpj_limpo = cnpj.replace(".", "").replace("-", "").replace("/", "").strip()

    # Parâmetros otimizados para a B3
    params = {
        "d": "1",
        "s": "0",
        "l": str(limit),
        "cnpjFundo": cnpj_limpo,
        "tipoFundo": "1"
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": f"{FNET_SESSION_URL}?cnpjFundo={cnpj_limpo}",
        "X-Requested-With": "XMLHttpRequest"
    }

    # Termos-chave de interesse para a nossa planilha
    TIPOS_PERMITIDOS = [
        "relatorio gerencial",
        "relatório gerencial",
        "informe mensal estruturado",
        "informe mensal",
        "rendimentos e amortizacoes",
        "rendimentos e amortizações"
    ]

    max_tentativas = 3
    events = []

    for tentativa in range(1, max_tentativas + 1):
        try:
            # Passo 1: Inicialização de sessão com cookies na B3
            session_headers = {"User-Agent": headers["User-Agent"]}
            session_params = {"cnpjFundo": cnpj_limpo}
            session_resp = await client.get(
                FNET_SESSION_URL,
                params=session_params,
                headers=session_headers,
                timeout=8.0
            )

            if session_resp.status_code != 200:
                raise httpx.HTTPStatusError("Falha no handshake", request=session_resp.request, response=session_resp)

            # Passo 2: Consome a API de dados
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
                    # Capturamos todos os campos descritivos possíveis retornados no JSON da B3
                    categoria = (doc.get("categoriaDocumento") or "").strip()
                    tipo = (doc.get("tipoDocumento") or "").strip()
                    especie = (doc.get("especieDocumento") or "").strip()
                    descricao_modalidade = (doc.get("descricaoModalidade") or "").strip()
                    assunto = (doc.get("assunto") or "").strip()

                    # Criamos um bloco de texto unificado para busca de palavras-chave
                    texto_busca = f"{categoria} {tipo} {especie} {descricao_modalidade} {assunto}".lower()

                    # 🔍 FILTRO ROBUSTO: Se o bloco de informações não contiver nenhuma das nossas palavras-chave, ignora.
                    if not any(termo in texto_busca for termo in TIPOS_PERMITIDOS):
                        continue

                    # Captura e tratamento seguro de data de publicação/entrega
                    data_envio_str = doc.get("dataEntrega") or doc.get("dataEnvio") or ""
                    if not data_envio_str:
                        continue

                    try:
                        dt_envio = datetime.strptime(data_envio_str, "%d/%m/%Y %H:%M")
                    except ValueError:
                        continue

                    # Filtro de mês corrente (Se ativo na chamada do Sheets)
                    if current_month_only:
                        if dt_envio.month != mes_atual or dt_envio.year != ano_atual:
                            continue

                    # Montagem da nomenclatura final limpa do tipo de documento para a planilha
                    if tipo:
                        tipo_doc_final = f"{categoria} - {tipo}" if categoria and categoria != tipo else tipo
                    else:
                        tipo_doc_final = categoria or assunto or "Documento Geral"

                    doc_id = doc.get("id")
                    pdf_link = f"https://fnet.bmfbovespa.com.br/fnet/publico/exibirDocumento?id={doc_id}" if doc_id else ""

                    events.append({
                        "ticker": ticker,
                        "cnpj": cnpj_limpo,
                        "data_envio": data_envio_str,
                        "tipo_documento": tipo_doc_final,
                        "assunto": assunto or "N/A",
                        "link": pdf_link
                    })

                return events
            else:
                raise httpx.HTTPStatusError("Erro de resposta dos dados", request=response.request, response=response)

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