# api-indicadores-financeiros

API própria em Python, hospedada na Vercel, que centraliza indicadores fundamentalistas de ações e FIIs da B3, além de eventos regulatórios (CVM/FNET). Criada para alimentar automaticamente uma planilha de acompanhamento de carteira de investimentos no Google Sheets, eliminando a atualização manual de dados.

🔗 **API em produção:** https://api-indicadores-financeiros.vercel.app

## Por que esse projeto existe

Manter uma carteira de investimentos exige atualizar constantemente indicadores fundamentalistas (P/L, ROE, dívida, DY, Beta, etc.) de dezenas de ativos. Fazer isso manualmente é lento e sujeito a erro. Esta API resolve isso: ela expõe endpoints simples que retornam os indicadores já tratados, prontos para consumo por qualquer cliente HTTP — no meu caso, por scripts em Google Apps Script que atualizam automaticamente uma planilha de carteira em alto desempenho.

## Endpoints

### `GET /api/stock/{ticker}`
Retorna indicadores fundamentalistas de uma ação da B3.

**Exemplo:** `GET /api/stock/PETR4`

**Resposta (campos principais):**
| Campo | Descrição |
|---|---|
| `roe` | Retorno sobre patrimônio líquido |
| `roic` | Retorno sobre capital investido |
| `margem_liquida` | Margem líquida |
| `divida_patrimonio` | Dívida sobre patrimônio |
| `cagr_lucro_5a` | Crescimento anual composto do lucro (5 anos) |
| `p_l`, `p_vp`, `p_ebit` | Múltiplos de valuation |
| `ev_ebitda`, `ev_ebit` | Múltiplos EV |
| `patrimonio_liquido`, `ativo`, `divida_liquida`, `divida_bruta` | Dados de balanço |
| `lucro_liquido_12m`, `lucro_liquido_3m` | Resultado |
| `div_yield` | Dividend yield |
| `beta_ibov_3a` | Volatilidade relativa do ativo vs IBOVESPA (3 anos) |

### `GET /api/fii/{ticker}`
Retorna indicadores de um Fundo de Investimento Imobiliário.

**Exemplo:** `GET /api/fii/KNRI11`

**Resposta (campos principais):**
| Campo | Descrição |
|---|---|
| `vp_cota` | Valor patrimonial por cota |
| `ffo_yield`, `div_yield` | Rentabilidade |
| `patrimonio`, `patrimonio_liq` | Patrimônio do fundo |
| `receita_3m`, `ffo_3m`, `rend_distribuído_3m`, `rend_distribuído_12m` | Resultados recentes |
| `cap_rate` | Taxa de capitalização |
| `vacância_média` | Vacância física média |
| `qtd_imóveis`, `qtd_unidades`, `qtd_cotas` | Dados estruturais do fundo |
| `doc` | Link do gerenciador de documentos na CVM/FNET |

### `POST /api/calendar`
Retorna eventos regulatórios recentes (fatos relevantes, informes, relatórios) para uma lista de fundos, cruzando ticker e CNPJ.

**Corpo da requisição:**
```json
{
  "fundos": [
    { "ticker": "KNRI11", "cnpj": "12345678000199" }
  ]
}
```

**Resposta:** lista de eventos, cada um com `ticker`, `data_envio`, `tipo_documento`, `assunto` e `link` para o documento original.

### `GET /api/proxy_fnet/{cnpj}`

Busca os documentos regulatórios de um fundo diretamente na B3/FNET pelo CNPJ, já filtrados pelo mês corrente e por tipo de documento relevante (Relatório Gerencial, Informe Mensal, Informe Trimestral Estruturado). É o endpoint que `/api/calendar` consome internamente.

**Exemplo:** `GET /api/proxy_fnet/11728688000147`

### `GET /api/proxy/{ticker}`

Rota de diagnóstico: retorna o HTML bruto do Fundamentus para um ticker, sem parsing. Útil para verificar rapidamente se o site mudou a estrutura das tabelas antes de mexer no parser.

**Exemplo:** `GET /api/proxy/PETR4`

## Cache

Todas as rotas que fazem scraping (Fundamentus e B3/FNET) usam um cache em memória com TTL de **30 minutos**, implementado em `cache.py`. Isso reduz o número de requisições às fontes externas — protegendo contra bloqueio por excesso de tráfego — e diminui o tempo de resposta em chamadas repetidas.

* `/api/stock` e `/api/fii` compartilham o cache de HTML do Fundamentus (via `utils.py`)
* `/api/proxy` tem seu próprio cache de HTML, na mesma janela de 30 min
* `/api/proxy_fnet` cacheia o resultado já filtrado por CNPJ; como `/api/calendar` consome esse endpoint internamente, ele é beneficiado pelo mesmo cache sem necessidade de lógica própria

> **Observação:** por rodar em ambiente serverless (Vercel), o cache em memória vale enquanto a mesma instância da função segue "quente" — reduz bastante o tráfego repetido no uso real, mas não garante 100% de acerto em todo cenário (cold starts reiniciam o cache).

## Fontes de dados e créditos

A API opera como uma camada de agregação e estruturação de dados de múltiplas fontes públicas e de mercado:

- **[Fundamentus](https://www.fundamentus.com.br/index.php):** Utilizado via web scraping para a extração dos indicadores fundamentalistas de Ações e FIIs (`/api/stock` e `/api/fii`). Todo crédito pela centralização dos indicadores de balanço e múltiplos originais pertence ao Fundamentus.
- **[FNET / B3 (CVM)](https://fnet.bmfbovespa.com.br/fnet/publico/abrirGerenciadorDocumentosCVM):** Sistema de entrega de documentos da CVM/B3 consumido pelos endpoints `/api/proxy_fnet` e `/api/calendar` para monitorar eventos regulatórios (fatos relevantes, informes mensais e relatórios gerenciais) em tempo real.
- **[QuantBrasil](https://quantbrasil.com.br/):** Plataforma de análise e dados de mercado (*"Não opere no escuro"*), utilizada como referência e suporte complementar para métricas quantitativas e de acompanhamento do mercado financeiro brasileiro.

A função `get_fundamentus_html()` em `utils.py` gerencia a coleta do Fundamentus, enquanto os conectores de rede realizam a ponte com os sistemas da B3 e dados de mercado.

> Este projeto é de uso pessoal/educacional. Os dados pertencem aos seus respectivos provedores de origem e devem ser utilizados respeitando os termos de uso de cada plataforma.

A coleta é feita pela função `get_fundamentus_html()` em `utils.py`, compartilhada pelas rotas `/api/stock` e `/api/fii`. O módulo `proxy.py` expõe uma rota separada só para inspecionar o HTML bruto retornado.

> Este projeto é de uso pessoal/educacional. Os dados pertencem ao Fundamentus e à B3/CVM e devem ser usados respeitando os termos dos sites de origem.

## Stack

* **Linguagem:** Python 3.x
* **Framework Web:** FastAPI
* **Parsing / Web Scraping:** BeautifulSoup4 / HTTP Clients (`requests`, `httpx`)
* **Servidor ASGI (dev):** Uvicorn
* **Deploy:** Vercel (serverless functions)
* **Configuração:** `vercel.json`, `requirements.txt`

## Onde essa API é usada

Esta API é consumida por uma planilha de controle de carteira de investimentos no Google Sheets, via Google Apps Script, que atualiza automaticamente os indicadores de ações e FIIs, o calendário de eventos regulatórios e os dados macroeconômicos da carteira.

👉 Repositório da planilha: [carteira-investimentos](https://github.com/GuilhermeMGarcia/carteira-investimentos)

## Rodando localmente

```bash
git clone [https://github.com/GuilhermeMGarcia/api-indicadores-financeiros.git](https://github.com/GuilhermeMGarcia/api-indicadores-financeiros.git)
cd api-indicadores-financeiros
pip install -r requirements.txt
uvicorn api.index:app --reload

```

A API sobe em `http://127.0.0.1:8000`. A página inicial (`/`) traz um painel com atalhos para todos os endpoints; a documentação interativa fica em `/docs` (Swagger) e `/redoc` (ReDoc).

## Autor

G.Garcia
