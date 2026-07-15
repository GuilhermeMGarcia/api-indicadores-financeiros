import httpx
import time
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

FNET_SESSION_URL = "https://fnet.bmfbovespa.com.br/fnet/publico/abrirGerenciadorDocumentosCVM"
FNET_DATA_URL = "https://fnet.bmfbovespa.com.br/fnet/publico/pesquisarGerenciadorDocumentosDados"

@router.get("/proxy_fnet/{cnpj}", tags=["Ferramentas de Diagnóstico (Proxy)"])
async def debug_fnet_raw(cnpj: str):
    # 1. Limpeza básica do CNPJ
    cnpj_limpo = cnpj.replace(".", "").replace("-", "").replace("/", "").strip()

    # 2. O mínimo de parâmetros que a B3 exige para devolver uma lista
    params = {
        "d": "1",
        "s": "0",
        "l": "10",
        "o[0][dataReferencia]": "desc",
        "idCategoriaDocumento": "0",
        "idTipoDocumento": "0",
        "idEspecieDocumento": "0",
        "isSession": "true",
        "_": str(int(time.time() * 1000)),
    }


    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }

    # 3. Execução bruta
    async with httpx.AsyncClient(verify=False, follow_redirects=True) as client:
        try:
            # Passo A: Bate na porta da B3 e pega o "crachá" (Cookies de Sessão)
            await client.get(
                FNET_SESSION_URL,
                params={"cnpjFundo": cnpj_limpo},
                headers=headers,
                timeout=10.0
            )

            # Passo B: Pede os dados usando o crachá
            response = await client.get(
                FNET_DATA_URL,
                params=params,
                headers=headers,
                timeout=10.0
            )

            # 4. Retorna exatamente o que a B3 enviou, sem alterar uma vírgula
            if response.status_code == 200:
                return response.json()
            else:
                return {"erro": f"A B3 retornou Status {response.status_code}"}

        except Exception as e:
            return {"erro_critico": str(e)}