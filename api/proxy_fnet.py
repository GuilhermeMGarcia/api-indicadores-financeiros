import time
import httpx
import asyncio
from datetime import datetime
from fastapi import APIRouter
from api.Cache import TTLCache

router = APIRouter()

FNET_SESSION_URL = "https://fnet.bmfbovespa.com.br/fnet/publico/abrirGerenciadorDocumentosCVM"
FNET_DATA_URL = "https://fnet.bmfbovespa.com.br/fnet/publico/pesquisarGerenciadorDocumentosDados"

FNET_CACHE_TTL_SECONDS = 30 * 60  # 30 minutos
fnet_cache = TTLCache(ttl_seconds=FNET_CACHE_TTL_SECONDS)


async def buscar_dados_com_retry(client, cnpj_limpo, headers, params, max_tentativas=3):
    """
    Executa a chamada ao FNET recusando 'Sucessos Falsos' (HTTP 200 com lista vazia por falta de sessão).
    """
    for tentativa in range(1, max_tentativas + 1):
        try:
            # 1. Abre/Aquece a sessão da B3 para o CNPJ
            res_sessao = await client.get(
                FNET_SESSION_URL,
                params={"cnpjFundo": cnpj_limpo},
                headers=headers,
                timeout=6.0
            )

            # Pequena pausa estratégica (150ms) para a B3 propagar os cookies da sessão no backend deles
            await asyncio.sleep(0.15)

            # 2. Requisita os documentos
            response = await client.get(
                FNET_DATA_URL,
                params=params,
                headers=headers,
                timeout=8.0
            )

            if response.status_code == 200:
                json_data = response.json()
                lista_dados = json_data.get("data", [])

                # 🛑 DETECTOR DE FALSO POSITIVO:
                # Se a B3 retornou lista de dados, a sessão funcionou perfeitamente!
                if len(lista_dados) > 0:
                    return json_data

                # Se veio vazio, mas ainda temos tentativas, ignora este '200 fake' e tenta esquentar a sessão de novo
                if tentativa < max_tentativas:
                    await asyncio.sleep(0.4 * tentativa)
                    continue

                # Se foi a última tentativa e continuou vazio, aceita como resposta zerada legítima
                return json_data

        except Exception:
            if tentativa == max_tentativas:
                raise
            await asyncio.sleep(0.5 * tentativa)

    return None


@router.get("/proxy_fnet/{cnpj}")
async def debug_fnet_raw(cnpj: str):
    cnpj_limpo = cnpj.replace(".", "").replace("-", "").replace("/", "").strip()

    cached_result = fnet_cache.get(cnpj_limpo)
    if cached_result is not None:
        return cached_result

    params = {
        "d": "1", "s": "0", "l": "30",
        "cnpjFundo": cnpj_limpo,
        "o[0][dataReferencia]": "desc",
        "isSession": "true",
        "_": str(int(time.time() * 1000)),
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest"
    }

    async with httpx.AsyncClient(verify=False, follow_redirects=True) as client:
        raw_data = await buscar_dados_com_retry(client, cnpj_limpo, headers, params)

    if not raw_data:
        return {"status": "error", "mensagem": "Falha na conexão com a B3"}

    hoje = datetime.now()
    documentos_filtrados = []

    for doc in raw_data.get("data", []):
        data_str = doc.get("dataEntrega", "")

        dt_envio = None
        for fmt in ["%d/%m/%Y %H:%M", "%d/%m/%Y"]:
            try:
                dt_envio = datetime.strptime(data_str, fmt)
                break
            except ValueError:
                continue

        if not dt_envio:
            continue

        eh_mes_atual = (dt_envio.month == hoje.month and dt_envio.year == hoje.year)
        tipo_limpo = doc.get("tipoDocumento", "").strip()

        tipos_desejados = [
            "Relatório Gerencial",
            "Informe Mensal Estruturado",
            "Informe Mensal",
            "Informe Trimestral Estruturado"
        ]

        if eh_mes_atual and tipo_limpo in tipos_desejados:
            documentos_filtrados.append(doc)

    resultado = {
        "status": "success",
        "total_filtrado": len(documentos_filtrados),
        "documentos": documentos_filtrados
    }

    # 🛡️ REGRA DE CACHE RIGOROSA:
    # NUNCA grava no cache se a lista vier zerada.
    # Assim, se em alguma chamada pontual a B3 engasgar, o usuário não fica preso por 1 minuto que seja.
    if len(documentos_filtrados) > 0:
        fnet_cache.set(cnpj_limpo, resultado)

    return resultado