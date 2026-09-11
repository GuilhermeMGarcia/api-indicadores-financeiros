# api-indicadores-financeiros

API própria em Python, hospedada na Vercel, que centraliza dados contábeis brutos, indicadores de FIIs da B3, preços e taxas do Tesouro Direto, além de eventos regulatórios (CVM/FNET). Criada para alimentar automaticamente uma planilha de acompanhamento de carteira de investimentos no Google Sheets, eliminando a atualização manual de dados e otimizando a performance ao delegar o cálculo de indicadores para a própria planilha.

🔗 **API em produção:** [https://api-indicadores-financeiros.vercel.app](https://api-indicadores-financeiros.vercel.app)

## Por que esse projeto existe

Manter uma carteira de investimentos exige atualizar constantemente dados de balanço, DRE e taxas de renda fixa de dezenas de ativos. Fazer isso manualmente é lento e sujeito a erros. Esta API resolve isso: ela expõe endpoints simples e otimizados que retornam os dados já tratados, prontos para consumo por qualquer cliente HTTP — no meu caso, por scripts em Google Apps Script que atualizam automaticamente uma planilha de carteira em alto desempenho.

Na versão **v1.3.6**, o endpoint de Ações foi refatorado para focar no fornecimento de **dados contábeis brutos de 12 meses**, taxa de crescimento histórico e métricas de mercado (como o Beta), repassando o cálculo de múltiplos e métricas deriváveis (como Valor de Mercado, Dívida Líquida e EV) diretamente para as fórmulas da planilha.

## Endpoints

### `GET /api/stock/{ticker}`

Retorna dados brutos contábeis (Fundamentus) de 12 meses, CAGR de receita e o Beta de 3 anos (QuantBrasil) executados em paralelo.

**Exemplo:** `GET /api/stock/CMIG4`

**Resposta (11 campos principais):**

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `ult_balanco_processado` | String | Data do último balanço processado (ex: `30/06/2026`) |
| `qtd_acao` | Integer | Número total de ações |
| `cagr_receita_5a` | Float | Crescimento anual composto da receita nos últimos 5 anos (%) |
| `ativo` | Integer | Ativo total |
| `disponibilidades` | Integer | Caixa e equivalentes de caixa |
| `divida_bruta` | Integer | Dívida bruta total |
| `patrimonio_liquido` | Integer | Patrimônio líquido |
| `receita_liquida_12m` | Integer | Receita líquida dos últimos 12 meses |
| `ebit_12m` | Integer | EBIT dos últimos 12 meses |
| `lucro_liquido_12m` | Integer | Lucro líquido dos últimos 12 meses |
| `beta_ibov_3a` | Float | Volatilidade relativa do ativo vs IBOVESPA (3 anos) |

---

### `GET /api/fii/{ticker}`

Retorna indicadores de um Fundo de Investimento Imobiliário.

**Exemplo:** `GET /api/fii/KNRI11`

**Resposta (campos principais):**

| Campo | Descrição |
| --- | --- |
| `vp_cota` | Valor patrimonial por cota |
| `ffo_yield`, `div_yield` | Rentabilidade |
| `patrimonio`, `patrimonio_liq` | Patrimônio do fundo |
| `receita_3m`, `ffo_3m`, `rend_distribuído_3m`, `rend_distribuído_12m` | Resultados recentes |
| `cap_rate` | Taxa de capitalização |
| `vacância_média` | Vacância física média |
| `qtd_imóveis`, `qtd_unidades`, `qtd_cotas` | Dados estruturais do fundo |
| `doc` | Link do gerenciador de documentos na CVM/FNET |

---

### `GET /api/tesouro`

Retorna preços e taxas em tempo real de todos os títulos públicos (Selic, IPCA+, Prefixados, Renda+ e Educa+), unificando as tabelas de investimento e resgate.

**Exemplo:** `GET /api/tesouro`

**Resposta (campos principais):**

| Campo | Descrição |
| --- | --- |
| `nome` | Nome oficial do título do Tesouro Direto |
| `taxa_compra` | Rentabilidade anual oferecida para compra/aplicação |
| `preco_compra` | Preço unitário atual para aplicação |
| `investimento_minimo` | Valor mínimo exigido para aplicação |
| `taxa_venda` | Rentabilidade anual oferecida para resgate antecipado |
| `preco_venda` | Preço unitário atual para resgate antecipado |
| `vencimento` | Data de vencimento do título |

---

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

---

### `GET /api/proxy_fnet/{cnpj}`

Busca os documentos regulatórios de um fundo diretamente na B3/FNET pelo CNPJ, já filtrados pelo mês corrente e por tipo de documento relevante (Relatório Gerencial, Informe Mensal, Informe Trimestral Estruturado). É o endpoint que `/api/calendar` consome internamente.

**Exemplo:** `GET /api/proxy_fnet/11728688000147`

---

### `GET /api/proxy/{ticker}`

Rota de diagnóstico: retorna o HTML bruto do Fundamentus para um ticker, sem parsing. Útil para verificar rapidamente se o site mudou a estrutura das tabelas antes de mexer no parser.

**Exemplo:** `GET /api/proxy/PETR4`

---

## Cache

Todas as rotas que realizam requisições externas (Fundamentus, QuantBrasil, B3/FNET e Tesouro Direto) usam um cache em memória com TTL de **30 minutos**, implementado em `cache.py`. Isso reduz o número de requisições às fontes externas — protegendo contra bloqueio por excesso de tráfego — e diminui o tempo de resposta em chamadas repetidas.

* `/api/stock` e `/api/fii` usam caches específicos com TTL de 30 minutos para amenizar requisições repetidas ao Fundamentus e QuantBrasil.
* `/api/tesouro` mantém o cache consolidado dos CSVs de preços e taxas do Tesouro Direto.
* `/api/proxy` tem seu próprio cache de HTML, na mesma janela de 30 min.
* `/api/proxy_fnet` cacheia o resultado já filtrado por CNPJ; como `/api/calendar` consome esse endpoint internamente, ele é beneficiado pelo mesmo cache sem necessidade de lógica própria.

> **Observação:** por rodar em ambiente serverless (Vercel), o cache em memória vale enquanto a mesma instância da função segue "quente" — reduz bastante o tráfego repetido no uso real, mas não garante 100% de acerto em todo cenário (cold starts reiniciam o cache).

---

## Fontes de dados e créditos

A API opera como uma camada de agregação e estruturação de dados de múltiplas fontes públicas e de mercado:

* **[Fundamentus](https://www.fundamentus.com.br/index.php):** Utilizado via web scraping para a extração dos dados contábeis brutos de Ações e indicadores de FIIs (`/api/stock` e `/api/fii`).
* **[QuantBrasil](https://quantbrasil.com.br/):** Plataforma de análise utilizada para extração do Beta histórico (3 anos) vs IBOVESPA no endpoint de ações.
* **[Tesouro Direto](https://www.tesourodireto.com.br/):** Fonte oficial dos arquivos CSV de preços e taxas de investimento e resgate de títulos públicos (`/api/tesouro`).
* **[FNET / B3 (CVM)](https://fnet.bmfbovespa.com.br/fnet/publico/abrirGerenciadorDocumentosCVM):** Sistema de entrega de documentos da CVM/B3 consumido pelos endpoints `/api/proxy_fnet` e `/api/calendar` para monitorar eventos regulatórios em tempo real.

> Este projeto é de uso pessoal/educacional. Os dados pertencem aos seus respectivos provedores de origem e devem ser utilizados respeitando os termos de uso de cada plataforma.

---

## Stack

* **Linguagem:** Python 3.x
* **Framework Web:** FastAPI (com suporte assíncrono `asyncio`)
* **Parsing / Web Scraping / Networking:** BeautifulSoup4, HTTP Clients (`httpx`, `requests`) e `curl-cffi` (impersonate Chrome 120 para conversação TLS e bypass de proteção WAF no Tesouro Direto)
* **Servidor ASGI (dev):** Uvicorn
* **Deploy:** Vercel (serverless functions)
* **Configuração:** `vercel.json`, `requirements.txt`

---

## Onde essa API é usada

Esta API é consumida por uma planilha de controle de carteira de investimentos no Google Sheets, via Google Apps Script, que atualiza automaticamente os dados contábeis de ações e FIIs, o calendário de eventos regulatórios e a precificação de títulos públicos da carteira.

👉 Repositório da planilha: [carteira-investimentos](https://github.com/GuilhermeMGarcia/carteira-investimentos)

---

## Rodando localmente

```bash
git clone https://github.com/GuilhermeMGarcia/api-indicadores-financeiros.git
cd api-indicadores-financeiros
pip install -r requirements.txt
uvicorn api.index:app --reload

```

A API sobe em `[http://127.0.0.1:8000](http://127.0.0.1:8000)`. A página inicial (`/`) traz um painel interativo com ticker tape dinâmico e atalhos para todos os endpoints; a documentação interativa fica em `/docs` (Swagger) e `/redoc` (ReDoc).

---

## Autor

G.Garcia
