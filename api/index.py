from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.openapi.docs import get_redoc_html
from api.proxy import router as proxy_router
from api.fii import router as fii_router
from api.stock import router as stock_router
from api.calendar import router as calendar_router       # Importa o Calendário
from api.proxy_fnet import router as proxy_fnet_router   # Importa o novo Proxy FNET
from api.proxy_quantbrasil import router as proxy_quantbrasil_router  # Proxy de diagnóstico QuantBrasil
from api.tesouro import router as tesouro_router         # Importa o Tesouro Direto

# Configuração global da API
app = FastAPI(
    title="🚀 Indicador API - Sistema de Inteligência Financeira",
    description="""
    API de captura e processamento de indicadores financeiros (Ações, FIIs e Renda Fixa/Tesouro).
    Utiliza Web Scraping e conectores diretos para extração de dados do Fundamentus, FNET e Tesouro Direto.
    """,
    version="1.3.0",
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
app.include_router(tesouro_router, prefix="/api", tags=["Renda Fixa (Tesouro Direto)"])       # Registra o Tesouro Direto


@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    """
    ReDoc servido manualmente, com uma versão fixa do CDN.
    """
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Documentação",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2.1.3/bundles/redoc.standalone.js",
    )


@app.get("/", response_class=HTMLResponse)
@app.get("/", response_class=HTMLResponse)
@app.get("/", response_class=HTMLResponse)
async def home():
    """
    Página inicial estilizada com ticker tape dinâmico e Dashboard de Monitoramento do Tesouro
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
                .wrap { max-width: 900px; margin: 0 auto; padding: 40px 20px; }

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
                    animation: scroll-left 35s linear infinite;
                }
                .ticker-track span { margin-right: 30px; font-size: 13px; color: var(--text-dim); }
                .ticker-track .rate { color: var(--accent); font-weight: 600; }
                @keyframes scroll-left {
                    from { transform: translateX(0); }
                    to { transform: translateX(-50%); }
                }
                @media (prefers-reduced-motion: reduce) {
                    .ticker-track { animation: none; }
                }

                header { margin-top: 20px; margin-bottom: 30px; }
                .eyebrow {
                    font-size: 12px;
                    letter-spacing: 0.12em;
                    color: var(--accent);
                    text-transform: uppercase;
                    margin-bottom: 10px;
                }
                h1 {
                    font-family: 'Space Grotesk', sans-serif;
                    font-size: 28px;
                    line-height: 1.25;
                    margin: 0 0 14px;
                    color: var(--text);
                    font-weight: 600;
                }
                p.lede {
                    color: var(--text-dim);
                    font-size: 13.5px;
                    line-height: 1.6;
                    margin: 0;
                }

                /* GRID HEAD DO DASHBOARD */
                .hero-grid {
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 20px;
                    margin-bottom: 36px;
                }
                @media (max-width: 768px) {
                    .hero-grid { grid-template-columns: 1fr; }
                }

                /* DASHBOARD MONITOR DE TAXAS */
                .monitor-card {
                    background: var(--surface);
                    border: 1px solid var(--border);
                    border-radius: 8px;
                    padding: 20px;
                    display: flex;
                    flex-direction: column;
                    justify-content: space-between;
                }
                .monitor-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 16px;
                }
                .monitor-title {
                    font-family: 'Space Grotesk', sans-serif;
                    font-size: 14px;
                    font-weight: 600;
                    color: var(--text);
                    text-transform: uppercase;
                    letter-spacing: 0.05em;
                }
                .btn-refresh {
                    background: var(--accent);
                    color: #0A0E1A;
                    border: none;
                    padding: 8px 14px;
                    border-radius: 5px;
                    font-family: 'IBM Plex Mono', monospace;
                    font-size: 12px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: opacity 0.2s;
                    display: flex;
                    align-items: center;
                    gap: 6px;
                }
                .btn-refresh:hover { opacity: 0.9; }
                .btn-refresh:disabled { opacity: 0.5; cursor: not-allowed; }

                .titulos-list {
                    display: flex;
                    flex-direction: column;
                    gap: 10px;
                }
                .titulo-item {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    background: var(--bg);
                    padding: 10px 12px;
                    border-radius: 6px;
                    border: 1px solid var(--border);
                    font-size: 12.5px;
                }
                .titulo-nome { color: var(--text-dim); font-size: 12px; }
                .titulo-taxa { color: var(--accent); font-weight: 600; font-size: 13px; }

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
                    padding: 12px 16px;
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
                .path { color: var(--text); font-size: 13px; flex-shrink: 0; }
                .desc { color: var(--text-dim); font-size: 12px; margin-left: auto; text-align: right; }

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
                <div class="ticker-track" id="ticker-content">
                    <span>Carregando taxas do Tesouro...</span>
                </div>
            </div>

            <div class="wrap">
                <div class="hero-grid">
                    <header>
                        <div class="eyebrow">Indicador API · v1.3.0</div>
                        <h1>Dados fundamentalistas da B3, prontos pra consumo.</h1>
                        <p class="lede">
                            Coleta e organiza indicadores de Ações, FIIs, Tesouro Direto e eventos regulatórios da 
                            B3/FNET — via scraping assíncrono, servidos como JSON simples. Construída para alimentar 
                            uma planilha de acompanhamento de carteira via Google Apps Script.
                        </p>
                    </header>

                    <!-- WIDGET DE MONITORAMENTO COM BOTÃO GATILHO -->
                    <div class="monitor-card">
                        <div class="monitor-header">
                            <span class="monitor-title">🎯 Tesouro+ Taxas</span>
                            <button id="btn-atualizar" class="btn-refresh" onclick="dispararGatilhoTesouro()">
                                🔄 Atualizar Taxas
                            </button>
                        </div>
                        <div class="titulos-list" id="monitor-list">
                            <div class="titulo-item"><span>Clique em Atualizar para buscar...</span></div>
                        </div>
                    </div>
                </div>

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
                    <div class="section-title">Ações, FIIs &amp; Renda Fixa</div>
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
                    <a class="row" href="/api/tesouro">
                        <span class="method">GET</span>
                        <span class="path">/api/tesouro</span>
                        <span class="desc">Preços e taxas em tempo real do Tesouro Direto</span>
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
                    <span>Dados: <a href="https://www.fundamentus.com.br/index.php">Fundamentus</a> | <a href="https://www.tesourodireto.com.br/produtos/dados-sobre-titulos/historico-de-precos-e-taxas">Tesouro Direto</a></span>
                </footer>
            </div>

            <script>
                // Cálculo dinâmico baseado no ano atual
                const anoAtual = new Date().getFullYear();

                const titulosAlvo = [
                    `Tesouro Prefixado ${anoAtual + 3}`,
                    `Tesouro IPCA+ ${anoAtual + 3}`,
                    `Tesouro IPCA+ ${anoAtual + 6}`,
                    `Tesouro IPCA+ ${anoAtual + 14}`,
                    "Tesouro Renda+ Aposentadoria Extra 2065"
                ];

                async function dispararGatilhoTesouro() {
                    const btn = document.getElementById('btn-atualizar');
                    const container = document.getElementById('monitor-list');

                    btn.disabled = true;
                    btn.innerText = "⏳ Buscando...";
                    container.innerHTML = '<div class="titulo-item"><span>Consultando Tesouro Direto...</span></div>';

                    try {
                        // Adiciona parâmetro com timestamp para ignorar caches antigos ao clicar no botão
                        const res = await fetch('/api/tesouro?t=' + Date.now());
                        const data = await res.json();

                        if (data.status === 'OK' && data.titulos) {
                            let html = '';
                            titulosAlvo.forEach(nomeAlvo => {
                                const encontrado = data.titulos.find(t => 
                                    t.nome.trim().toLowerCase() === nomeAlvo.trim().toLowerCase()
                                );

                                const taxa = encontrado ? (encontrado.taxa_compra || encontrado.taxa_venda || 'N/A') : 'Não enc.';
                                html += `
                                    <div class="titulo-item">
                                        <span class="titulo-nome">${nomeAlvo}</span>
                                        <span class="titulo-taxa">${taxa}</span>
                                    </div>
                                `;
                            });
                            container.innerHTML = html;
                        } else {
                            container.innerHTML = '<div class="titulo-item"><span style="color:#E8A33D">Falha ao obter dados. Tente novamente.</span></div>';
                        }
                    } catch (e) {
                        container.innerHTML = '<div class="titulo-item"><span style="color:#ff5555">Erro na requisição.</span></div>';
                    } finally {
                        btn.disabled = false;
                        btn.innerText = "🔄 Atualizar Taxas";
                    }
                }

                async function carregarTicker() {
                    const container = document.getElementById('ticker-content');
                    try {
                        const res = await fetch('/api/tesouro');
                        const data = await res.json();

                        if (data.status === 'OK' && data.titulos && data.titulos.length > 0) {
                            const palavrasChave = ['Selic', 'IPCA+', 'Prefixado', 'Renda+', 'Educa+'];
                            const titulosDestaque = [];

                            palavrasChave.forEach(cat => {
                                const filtrados = data.titulos.filter(t => t.nome.includes(cat)).slice(0, 2);
                                titulosDestaque.push(...filtrados);
                            });

                            const itens = titulosDestaque.map(t => {
                                const taxa = t.taxa_compra || t.taxa_venda || 'N/A';
                                return `<span>${t.nome}: <span class="rate">${taxa}</span></span>`;
                            }).join('');

                            container.innerHTML = itens + itens;
                        } else {
                            container.innerHTML = '<span>Tesouro Direto: Taxas indisponíveis no momento</span>';
                        }
                    } catch (e) {
                        container.innerHTML = '<span>Tesouro Direto: Dados de mercado indisponíveis</span>';
                    }
                }

                // Carrega o ticker e dispara a busca inicial da sua lista ao abrir a página
                carregarTicker();
                dispararGatilhoTesouro();
            </script>
        </body>
    </html>
    """