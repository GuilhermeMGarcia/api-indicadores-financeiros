from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from api.proxy import router as proxy_router
from api.fii import router as fii_router
from api.stock import router as stock_router
from api.calendar import router as calendar_router       # Importa o Calendário
from api.proxy_fnet import router as proxy_fnet_router   # Importa o novo Proxy FNET

# Configuração global da API
app = FastAPI(
    title="🚀 Indicador API - Sistema de Inteligência Financeira",
    description="""
    API de captura e processamento de indicadores financeiros (Ações e FIIs).
    Utiliza Web Scraping assíncrono para extração de dados do Fundamentus e FNET.
    """,
    version="1.2.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# --- INCLUSÃO DAS ROTAS (Módulos) ---

# Rotas de Proxy (Diagnósticos)
app.include_router(proxy_router, prefix="/api", tags=["Ferramentas de Diagnóstico (Proxy)"])
app.include_router(proxy_fnet_router, prefix="/api", tags=["Ferramentas de Diagnóstico (Proxy)"]) # Registra o Proxy FNET

# Rotas de Dados
app.include_router(fii_router, prefix="/api", tags=["Fundos Imobiliários (FIIs)"])
app.include_router(stock_router, prefix="/api", tags=["Ações (Stocks)"])
app.include_router(calendar_router, prefix="/api", tags=["Calendário de Eventos (FNET)"])       # Registra o Calendário


@app.get("/", response_class=HTMLResponse)
async def home():
    """
    Página inicial estilizada com atalhos de teste
    """
    return """
    <html>
        <head>
            <title>Indicador API</title>
            <style>
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; max-width: 800px; margin: 40px auto; padding: 20px; background-color: #f4f7f6; }
                h1 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
                .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 20px; }
                ul { list-style: none; padding: 0; }
                li { margin-bottom: 10px; background: #fff; padding: 10px; border-radius: 4px; border-left: 5px solid #3498db; transition: 0.3s; }
                li:hover { border-left: 5px solid #2ecc71; transform: translateX(5px); }
                a { text-decoration: none; color: #2980b9; font-weight: bold; }
                .tag { font-size: 0.8em; color: #7f8c8d; background: #ecf0f1; padding: 2px 6px; border-radius: 3px; margin-right: 5px; }
            </style>
        </head>
        <body>
            <h1>🚀 Painel de Controle - Indicador API</h1>

            <div class="card">
                <h2>📚 Documentação</h2>
                <ul>
                    <li><a href="/docs">📑 Swagger UI (Interativo)</a></li>
                    <li><a href="/redoc">📘 ReDoc (Leitura Limpa)</a></li>
                </ul>
            </div>

            <div class="card">
                <h2>🧪 Endpoints de Teste</h2>
                <ul>
                    <li><span class="tag">GET</span> <a href="/api/stock/PETR4">📈 Ações: Exemplo PETR4</a></li>
                    <li><span class="tag">GET</span> <a href="/api/fii/HGLG11">🏢 FIIs: Exemplo HGLG11</a></li>
                    <li><span class="tag">GET</span> <a href="/api/proxy/PETR4">🔗 Proxy Fundamentus: Ver HTML bruto de PETR4</a></li>
                    <li><span class="tag">GET</span> <a href="/api/proxy_fnet/11728688000147">📅 Proxy FNET: Ver JSON bruto do HGLG1
                </ul>
            </div>

            <footer style="text-align: center; color: #95a5a6; font-size: 0.9em;">
                Desenvolvido para integração com Google Apps Script
            </footer>
        </body>
    </html>
    """