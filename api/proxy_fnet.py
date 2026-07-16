import time
import httpx
import asyncio
from datetime import datetime
from fastapi import APIRouter

router = APIRouter()

FNET_SESSION_URL = "https://fnet.bmfbovespa.com.br/fnet/publico/abrirGerenciadorDocumentosCVM"
FNET_DATA_URL = "https://fnet.bmfbovespa.com.br/fnet/publico/pesquisarGerenciadorDocumentosDados"


async def buscar_dados_com_retry(client, cnpj_limpo, headers, params, max_tentativas=3):
    """Executa a chamada ao FNET com re-tentativa automática."""
    for tentativa in range(max_tentativas):
        try:
            # Renovação da sessão
            await client.get(FNET_SESSION_URL, params={"cnpjFundo": cnpj_limpo}, headers=headers, timeout=5.0)
            # Requisição dos dados
            response = await client.get(FNET_DATA_URL, params=params, headers=headers, timeout=8.0)

            if response.status_code == 200:
                return response.json()
        except Exception:
            if tentativa == max_tentativas - 1: raise
            await asyncio.sleep(1)
    return None


@router.get("/proxy_fnet/{cnpj}")
async def debug_fnet_raw(cnpj: str):
    cnpj_limpo = cnpj.replace(".", "").replace("-", "").replace("/", "").strip()

    params = {
        "d": "1", "s": "0", "l": "30",
        "cnpjFundo": cnpj_limpo,
        "o[0][dataReferencia]": "desc",
        "isSession": "true",
        "_": str(int(time.time() * 1000)),
    }
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    async with httpx.AsyncClient(verify=False, follow_redirects=True) as client:
        raw_data = await buscar_dados_com_retry(client, cnpj_limpo, headers, params)

    if not raw_data:
        return {"status": "error", "mensagem": "Falha na conexão com a B3"}

    # Processamento e Filtro Robusto
    hoje = datetime.now()
    documentos_filtrados = []

    for doc in raw_data.get("data", []):
        data_str = doc.get("dataEntrega", "")

        # Tenta formatar a data de forma inteligente
        dt_envio = None
        for fmt in ["%d/%m/%Y %H:%M", "%d/%m/%Y"]:
            try:
                dt_envio = datetime.strptime(data_str, fmt)
                break
            except ValueError:
                continue

        if not dt_envio: continue

        # Filtra pelo mês/ano e tipos de documentos
        eh_mes_atual = (dt_envio.month == hoje.month and dt_envio.year == hoje.year)
        tipo = doc.get("tipoDocumento", "")

        # 1. Limpa o nome do tipo removendo espaços extras
        tipo_limpo = tipo.strip()

        # 2. Define a lista de documentos que você QUER capturar
        # Adicionei Informe Trimestral e outros que apareceram no seu log
        tipos_desejados = [
            "Relatório Gerencial",
            "Informe Mensal Estruturado",
            "Informe Mensal",
            "Informe Trimestral Estruturado"
        ]

        # 3. Validação simplificada:
        # Verifica se o tipo limpo está na lista permitida
        eh_valido = tipo_limpo in tipos_desejados

        # Adicione isso no seu loop para ver no log da Vercel (Logs > Deployments)
        # print(f"DEBUG: {doc.get('ticker', 'N/A')} | Tipo: {tipo} | ArqEstruturado: '{doc.get('arquivoEstruturado')}'")

        if eh_mes_atual and eh_valido:
            documentos_filtrados.append(doc)

    return {
        "status": "success",
        "total_filtrado": len(documentos_filtrados),
        "documentos": documentos_filtrados
    }