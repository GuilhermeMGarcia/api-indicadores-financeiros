import httpx
from fastapi import APIRouter
from fastapi.responses import Response, JSONResponse
from api.utils import HEADERS  # Importa os headers padronizados

router = APIRouter()


@router.get("/proxy/{ticker}")
async def proxy_request(ticker: str):
    """
    Rota de diagnóstico: Retorna o HTML bruto do Fundamentus para inspeção.
    Útil para verificar se o site mudou a estrutura das tabelas.
    """
    url = f"https://www.fundamentus.com.br/detalhes.php?papel={ticker.upper()}"

    try:
        # Usamos o AsyncClient para não travar a API enquanto espera o site externo
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            resp = await client.get(url, headers=HEADERS)

            # Se o status não for 200, levantamos o erro explicitamente
            resp.raise_for_status()

            # Retorna o conteúdo respeitando a codificação original do Fundamentus (ISO-8859-1)
            # Isso garante que você veja os acentos corretamente no navegador
            content = resp.content.decode("ISO-8859-1")

            return Response(
                content=content,
                media_type="text/html",
                headers={"X-Proxy-Source": "Fundamentus-Scraper"}
            )

    except httpx.HTTPStatusError as e:
        return JSONResponse(
            status_code=e.response.status_code,
            content={"error": f"Erro HTTP no Fundamentus: {e.response.status_code}", "ticker": ticker}
        )
    except httpx.RequestError as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Erro de conexão/rede: {str(e)}", "ticker": ticker}
        )