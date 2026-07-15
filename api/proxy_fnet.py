from fastapi import APIRouter
from fastapi.responses import JSONResponse
import httpx

router = APIRouter()

# URLs oficiais do fluxo do FNET
FNET_SESSION_URL = "https://fnet.bmfbovespa.com.br/fnet/publico/abrirGerenciadorDocumentosCVM"
FNET_DATA_URL = "https://fnet.bmfbovespa.com.br/fnet/publico/pesquisarGerenciadorDocumentosDados"

@router.get("/proxy_fnet/{cnpj}", tags=["Ferramentas de Diagnóstico (Proxy)"])
async def debug_fnet_raw(cnpj: str):
    """
    Simula o handshake inicial do FNET (B3) abrindo o gerenciador
    e consumindo a rota de dados real de documentos.
    """
    cnpj_limpo = cnpj.replace(".", "").replace("-", "").replace("/", "").strip()

    # Parâmetros corretos exigidos internamente pela B3
    params = {
        "d": "0",    # draw
        "s": "0",    # start
        "l": "10",   # limit (últimos 10 comunicados)
        "cnpjFundo": cnpj_limpo,
        "tipoFundo": "1"
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": f"{FNET_SESSION_URL}?cnpjFundo={cnpj_limpo}",
        "X-Requested-With": "XMLHttpRequest"
    }

    # Usando httpx.AsyncClient para gerenciar os cookies automaticamente durante o fluxo
    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            # Passo 1: Abre a página que você sugeriu para criar a sessão na B3
            session_headers = {"User-Agent": headers["User-Agent"]}
            session_params = {"cnpjFundo": cnpj_limpo}
            await client.get(FNET_SESSION_URL, params=session_params, headers=session_headers, timeout=10.0)

            # Passo 2: Executa a requisição dos dados usando os cookies gerados no Passo 1
            response = await client.get(FNET_DATA_URL, params=params, headers=headers, timeout=12.0)

            if response.status_code == 200:
                return {
                    "status_code_fnet": response.status_code,
                    "cnpj_pesquisado": cnpj_limpo,
                    "url_consultada": str(response.url),
                    "dados_brutos_fnet": response.json()
                }
            else:
                return JSONResponse(
                    status_code=response.status_code,
                    content={
                        "erro": f"B3 retornou HTTP {response.status_code}",
                        "detalhe": response.text
                    }
                )

        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"erro": f"Falha de conexão no fluxo da B3: {str(e)}"}
            )