import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.openapi.docs import get_redoc_html
from fastapi.templating import Jinja2Templates
from fastapi import Request

from api.proxy import router as proxy_router
from api.fii import router as fii_router
from api.stock import router as stock_router
from api.calendar import router as calendar_router
from api.proxy_fnet import router as proxy_fnet_router
from api.proxy_quantbrasil import router as proxy_quantbrasil_router
from api.tesouro import router as tesouro_router
from api.proxy_tesouro import router as proxy_tesouro_router
from api.proxy_maisretorno import router as proxy_maisretorno_router


# Obtém o caminho absoluto da pasta do projeto
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

app = FastAPI(
    title="🚀 Indicador API - Sistema de Inteligência Financeira",
    description="API de captura e processamento de indicadores financeiros.",
    version="1.4.0",
    docs_url="/docs",
    redoc_url=None
)

# Roteadores
app.include_router(proxy_router, prefix="/api", tags=["Ferramentas de Diagnóstico (Proxy)"])
app.include_router(proxy_fnet_router, prefix="/api", tags=["Ferramentas de Diagnóstico (Proxy)"])
app.include_router(proxy_quantbrasil_router, prefix="/api", tags=["Ferramentas de Diagnóstico (Proxy)"])
app.include_router(proxy_tesouro_router, prefix="/api", tags=["Ferramentas de Diagnóstico (Proxy)"])
app.include_router(proxy_maisretorno_router, prefix="/api", tags=["Ferramentas de Diagnóstico (Proxy)"])

app.include_router(fii_router, prefix="/api", tags=["Fundos Imobiliários (FIIs)"])
app.include_router(stock_router, prefix="/api", tags=["Ações (Stocks)"])
app.include_router(calendar_router, prefix="/api", tags=["Calendário de Eventos (FNET)"])
app.include_router(tesouro_router, prefix="/api", tags=["Renda Fixa (Tesouro Direto)"])

@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Documentação",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2.1.3/bundles/redoc.standalone.js",
    )

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})