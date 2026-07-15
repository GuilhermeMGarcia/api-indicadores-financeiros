from fastapi import APIRouter
from fastapi.responses import JSONResponse
import httpx

router = APIRouter()

FNET_API_URL = "https://fnet.bmfbovespa.com.br/fnet/publico/pesquisarGerenciadorDocumentosDados"


@router.get("/proxy_fnet/{cnpj}", tags=["Ferramentas de Diagnóstico (Proxy)"])
async def debug_fnet_raw(cnpj: str):
    """
    Retorna o JSON bruto de documentos enviado diretamente pela B3 (FNET).
    Excelente para verificar bloqueios de rede ou dados de teste em tempo real no navegador.
    """
    # Remove formatações como pontos, traços e barras do CNPJ recebido
    cnpj_limpo = cnpj.replace(".", "").replace("-", "").replace("/", "").strip()

    params = {
        "d_draw": "1",
        "d_start": "0",
        "d_length": "10",  # Pega os últimos 10 comunicados
        "cnpjFundo": cnpj_limpo,
        "tipoFundo": "1"  # 1 = FII
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "X-Requested-With": "XMLHttpRequest"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(FNET_API_URL, params=params, headers=headers, timeout=12.0)

            # Retorna uma análise limpa do status da B3
            return {
                "status_code_fnet": response.status_code,
                "cnpj_pesquisado": cnpj_limpo,
                "url_consultada": str(response.url),
                "dados_brutos_fnet": response.json() if response.status_code == 200 else response.text
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"erro": f"Falha de conexão com a B3: {str(e)}"}
            )