from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.openapi.docs import get_redoc_html
from api.proxy import router as proxy_router
from api.fii import router as fii_router
from api.stock import router as stock_router
from api.calendar import router as calendar_router       # Importa o Calendário
from api.proxy_fnet import router as proxy_fnet_router   # Importa o novo Proxy FNET
from api.proxy_quantbrasil import router as proxy_quantbrasil_router  # Proxy de diagnóstico QuantBrasil

# Configuração global da API
app = FastAPI(
    title="🚀 Indicador API - Sistema de Inteligência Financeira",
    description="""
    API de captura e processamento de indicadores financeiros (Ações e FIIs).
    Utiliza Web Scraping assíncrono para extração de dados do Fundamentus e FNET.
    """,
    version="1.2.0",
    docs_url="/docs",
    redoc_url=None  # Desativa o /redoc automático — servido manualmente abaixo com CDN fixo
)

# --- INCLUSÃO DAS ROTAS (Módulos) ---

# Rotas de Proxy (Diagnósticos)
app.include_router(proxy_router, prefix="/api", tags=["Ferramentas de Diagnóstico (Proxy)"])
app.include_router(proxy_fnet_router, prefix="/api", tags=["Ferramentas de Diagnóstico (Proxy)"]) # Registra o Proxy FNET
app.include_router(proxy_quantbrasil_router, prefix="/api", tags=["Ferramentas de Diagnóstico (Proxy)"]) # Registra o Proxy QuantBrasil

# Rotas de Dados
app.include_router(fii_router, prefix="/api", tags=["Fundos Imobiliários (FIIs)"])
app.include_router(stock_router, prefix="/api", tags=["Ações (Stocks)"])
app.include_router(calendar_router, prefix="/api", tags=["Calendário de Eventos (FNET)"])       # Registra o Calendário


@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    """
    ReDoc servido manualmente, com uma versão fixa do CDN (em vez de @next,
    que muda sem aviso e pode quebrar o carregamento, deixando a página em branco).
    """
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Documentação",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2.1.3/bundles/redoc.standalone.js",
    )


@app.get("/", response_class=HTMLResponse)
async def home():
    """
    Página inicial estilizada com atalhos de teste
    """
    return """
    <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Indicador API</title>
            <link rel="preconnect" href="https://fonts.googleapis.com">
            <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
            <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
            <style>
                :root {
                    --bg: #0A0E1A;
                    --surface: #121A2B;
                    --surface-hover: #17203570;
                    --border: #232C44;
                    --text: #EDF1F7;
                    --text-dim: #8B93AC;
                    --accent: #3ECF8E;
                    --accent-dim: #3ECF8E33;
                    --amber: #E8A33D;
                }
                * { box-sizing: border-box; }
                body {
                    font-family: 'IBM Plex Mono', monospace;
                    background: var(--bg);
                    color: var(--text);
                    margin: 0;
                    padding: 0;
                    min-height: 100vh;
                }
                .wrap { max-width: 760px; margin: 0 auto; padding: 56px 24px 40px; }

                /* Ticker tape */
                .ticker-outer {
                    border-top: 1px solid var(--border);
                    border-bottom: 1px solid var(--border);
                    overflow: hidden;
                    background: var(--surface);
                    white-space: nowrap;
                }
                .ticker-track {
                    display: inline-block;
                    padding: 10px 0;
                    animation: scroll-left 28s linear infinite;
                }
                .ticker-track span { margin-right: 40px; font-size: 13px; color: var(--text-dim); }
                .ticker-track .up { color: var(--accent); }
                .ticker-track .down { color: #E8646B; }
                @keyframes scroll-left {
                    from { transform: translateX(0); }
                    to { transform: translateX(-50%); }
                }
                @media (prefers-reduced-motion: reduce) {
                    .ticker-track { animation: none; }
                }

                header { margin-top: 44px; margin-bottom: 40px; }
                .eyebrow {
                    font-size: 12px;
                    letter-spacing: 0.12em;
                    color: var(--accent);
                    text-transform: uppercase;
                    margin-bottom: 14px;
                }
                h1 {
                    font-family: 'Space Grotesk', sans-serif;
                    font-size: 32px;
                    line-height: 1.25;
                    margin: 0 0 14px;
                    color: var(--text);
                    font-weight: 600;
                }
                p.lede {
                    color: var(--text-dim);
                    font-size: 14.5px;
                    line-height: 1.7;
                    max-width: 58ch;
                    margin: 0;
                }

                section { margin-bottom: 36px; }
                .section-title {
                    font-family: 'Space Grotesk', sans-serif;
                    font-size: 13px;
                    letter-spacing: 0.08em;
                    text-transform: uppercase;
                    color: var(--text-dim);
                    margin-bottom: 14px;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }
                .section-title::after {
                    content: "";
                    flex: 1;
                    height: 1px;
                    background: var(--border);
                }

                .row {
                    display: flex;
                    align-items: center;
                    gap: 14px;
                    padding: 13px 16px;
                    border: 1px solid var(--border);
                    border-radius: 6px;
                    background: var(--surface);
                    margin-bottom: 8px;
                    text-decoration: none;
                    transition: border-color 0.15s ease, background 0.15s ease;
                }
                .row:hover { border-color: var(--accent); background: var(--surface-hover); }
                .method {
                    font-size: 11px;
                    font-weight: 600;
                    color: var(--accent);
                    background: var(--accent-dim);
                    padding: 3px 8px;
                    border-radius: 4px;
                    letter-spacing: 0.04em;
                    flex-shrink: 0;
                }
                .method.post { color: var(--amber); background: #E8A33D2b; }
                .path {
                    color: var(--text);
                    font-size: 13.5px;
                    flex-shrink: 0;
                }
                .desc {
                    color: var(--text-dim);
                    font-size: 12.5px;
                    margin-left: auto;
                    text-align: right;
                }

                footer {
                    margin-top: 48px;
                    padding-top: 20px;
                    border-top: 1px solid var(--border);
                    color: var(--text-dim);
                    font-size: 12px;
                    display: flex;
                    justify-content: space-between;
                    flex-wrap: wrap;
                    gap: 8px;
                }
                footer a { color: var(--text-dim); }
                footer a:hover { color: var(--accent); }
            </style>
        </head>
        <body>
            <div class="ticker-outer">
                <div class="ticker-track">
                    <span>PETR4 <span class="up">▲ ROE 24.1%</span></span>
                    <span>KNRI11 <span class="down">▼ VACÂNCIA 3.2%</span></span>
                    <span>ITSA4 <span class="up">▲ DIV. YIELD 6.8%</span></span>
                    <span>HGLG11 <span class="up">▲ P/VP 0.97</span></span>
                    <span>CMIG4 <span class="down">▼ DÍVIDA/PL 1.4</span></span>
                    <span>PETR4 <span class="up">▲ ROE 24.1%</span></span>
                    <span>KNRI11 <span class="down">▼ VACÂNCIA 3.2%</span></span>
                    <span>ITSA4 <span class="up">▲ DIV. YIELD 6.8%</span></span>
                    <span>HGLG11 <span class="up">▲ P/VP 0.97</span></span>
                    <span>CMIG4 <span class="down">▼ DÍVIDA/PL 1.4</span></span>
                </div>
            </div>

            <div class="wrap">
                <header>
                    <div class="eyebrow">Indicador API · v1.2.0</div>
                    <h1>Dados fundamentalistas da B3,<br>prontos pra consumo.</h1>
                    <p class="lede">
                        Coleta e organiza indicadores de Ações e FIIs direto do Fundamentus,
                        além de eventos regulatórios da B3/FNET — via scraping assíncrono,
                        servidos como JSON simples. Construída para alimentar uma planilha
                        de acompanhamento de carteira via Google Apps Script.
                    </p>
                </header>

                <section>
                    <div class="section-title">Documentação</div>
                    <a class="row" href="/docs">
                        <span class="method">GET</span>
                        <span class="path">/docs</span>
                        <span class="desc">Swagger UI — interativo, testa direto no navegador</span>
                    </a>
                    <a class="row" href="/redoc">
                        <span class="method">GET</span>
                        <span class="path">/redoc</span>
                        <span class="desc">ReDoc — leitura limpa, referência completa</span>
                    </a>
                </section>

                <section>
                    <div class="section-title">Ações &amp; FIIs</div>
                    <a class="row" href="/api/stock/PETR4">
                        <span class="method">GET</span>
                        <span class="path">/api/stock/PETR4</span>
                        <span class="desc">Indicadores fundamentalistas de uma ação</span>
                    </a>
                    <a class="row" href="/api/fii/HGLG11">
                        <span class="method">GET</span>
                        <span class="path">/api/fii/HGLG11</span>
                        <span class="desc">Indicadores de um Fundo Imobiliário</span>
                    </a>
                </section>

                <section>
                    <div class="section-title">Eventos regulatórios (B3/FNET)</div>
                    <a class="row" href="/api/proxy_fnet/11728688000147">
                        <span class="method">GET</span>
                        <span class="path">/api/proxy_fnet/{cnpj}</span>
                        <span class="desc">Documentos filtrados de um fundo pelo CNPJ</span>
                    </a>
                    <div class="row" style="cursor:default;">
                        <span class="method post">POST</span>
                        <span class="path">/api/calendar</span>
                        <span class="desc">Calendário de eventos para uma lista de fundos</span>
                    </div>
                </section>

                <section>
                    <div class="section-title">Diagnóstico</div>
                    <a class="row" href="/api/proxy/PETR4">
                        <span class="method">GET</span>
                        <span class="path">/api/proxy/{ticker}</span>
                        <span class="desc">HTML bruto do Fundamentus, pra inspeção</span>
                    </a>
                    <a class="row" href="/api/proxy_quantbrasil/PETR4">
                        <span class="method">GET</span>
                        <span class="path">/api/proxy_quantbrasil/{ticker}</span>
                        <span class="desc">HTML bruto do QuantBrasil, pra inspeção</span>
                    </a>
                </section>

                <footer>
                    <span>Desenvolvido para integração com Google Apps Script</span>
                    <span>Dados: <a href="https://www.fundamentus.com.br/index.php">Fundamentus</a></span>
                </footer>
            </div>
        </body>
    </html>
    """