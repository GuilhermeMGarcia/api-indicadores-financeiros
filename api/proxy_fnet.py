import asyncio
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
    Simula o handshake inicial do FNET (B3) com mecanismo de re-tentativa (retry)
    caso ocorra oscilação ou erro temporário na comunicação.
    """
    cnpj_limpo = cnpj.replace(".", "").replace("-", "").replace("/", "").strip()

    # Parâmetros oficiais exigidos pela B3
    params = {
        "d": "0",  # draw
        "s": "0",  # start
        "l": "10",  # limit
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
    ultima_excecao = None

    async with httpx.AsyncClient(follow_redirects=True) as client:
        for tentativa in range(1, max_tentativas + 1):
            try:
                # Passo 1: Handshake para criar a sessão na B3
                session_headers = {"User-Agent": headers["User-Agent"]}
                session_params = {"cnpjFundo": cnpj_limpo}
                session_response = await client.get(
                    FNET_SESSION_URL,
                    params=session_params,
                    headers=session_headers,
                    timeout=8.0
                )

                # Se o handshake falhar na B3, joga um erro para ir ao bloco except
                if session_response.status_code != 200:
                    raise httpx.HTTPStatusError(
                        f"Falha no handshake inicial (HTTP {session_response.status_code})",
                        request=session_response.request,
                        response=session_response
                    )

                # Passo 2: Requisição real dos dados usando os cookies gerados no Passo 1
                response = await client.get(FNET_DATA_URL, params=params, headers=headers, timeout=10.0)

                # Se a resposta de dados for 200, deu tudo certo!
                if response.status_code == 200:
                    return {
                        "status_code_fnet": response.status_code,
                        "cnpj_pesquisado": cnpj_limpo,
                        "tentativa": tentativa,
                        "url_consultada": str(response.url),
                        "dados_brutos_fnet": response.json()
                    }
                else:
                    raise httpx.HTTPStatusError(
                        f"Erro de dados (HTTP {response.status_code})",
                        request=response.request,
                        response=response
                    )

            except Exception as e:
                ultima_excecao = e
                # Aguarda um pequeno intervalo antes de tentar de novo (0.5s na segunda, 1s na terceira)
                await asyncio.sleep(0.5 * tentativa)

        # Se todas as tentativas falharem, retorna o último erro capturado
        detalhe_erro = str(ultima_excecao)
        if isinstance(ultima_excecao, httpx.HTTPStatusError):
            try:
                detalhe_erro = ultima_excecao.response.text
            except Exception:
                pass

        return JSONResponse(
            status_code=502,
            content={
                "erro": f"Todas as {max_tentativas} tentativas de conexão com a B3 falharam.",
                "detalhe": detalhe_erro
            }
        )