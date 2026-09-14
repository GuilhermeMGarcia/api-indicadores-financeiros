# api-indicadores-financeiros

API própria em Python, hospedada na Vercel, que centraliza dados contábeis brutos, indicadores de FIIs da B3, preços e taxas do Tesouro Direto, métricas avançadas de fundos/ações (Mais Retorno), além de eventos regulatórios (CVM/FNET). Criada para alimentar automaticamente uma planilha de acompanhamento de carteira de investimentos no Google Sheets, eliminando a atualização manual de dados e otimizando a performance ao delegar o cálculo de múltiplos para a própria planilha.

🔗 **API em produção:** [https://api-indicadores-financeiros.vercel.app](https://api-indicadores-financeiros.vercel.app)

## Por que esse projeto existe

Manter uma carteira de investimentos exige atualizar constantemente dados de balanço, DRE, métricas de risco/retorno e taxas de renda fixa de dezenas de ativos. Fazer isso manualmente é lento e sujeito a erros. Esta API resolve isso: ela expõe endpoints simples e otimizados que retornam os dados já tratados, prontos para consumo por qualquer cliente HTTP — no meu caso, por scripts em Google Apps Script que atualizam automaticamente uma planilha de carteira em alto desempenho.

Na versão **v1.4.0**, o endpoint de Ações foi expandido para fornecer **15 colunas de dados**, combinando **dados contábeis brutos de 12 meses** (Fundamentus), métricas de volatilidade/Beta (QuantBrasil) e indicadores de rentabilidade/Sharpe históricos via integração com a **Mais Retorno**.

## Endpoints

### `GET /api/stock/{ticker}`

Retorna dados brutos contábeis (Fundamentus), CAGR de receita, Beta de 3 anos (QuantBrasil) e métricas consolidadas de rentabilidade e risco da Mais Retorno executados de forma assíncrona.

> **Header Opcional:** `X-MaisRetorno-Key` (para autenticação nas métricas da Mais Retorno).

**Exemplo:** `GET /api/stock/CMIG4`

**Resposta (15 campos mapeados):**

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
| `rentabilidade_total` | Float | Rentabilidade acumulada histórica (%) |
| `sharpe_total` | Float | Índice Sharpe acumulado histórico |
| `rentabilidade_12m` | Float | Rentabilidade nos últimos 12 meses (%) |
| `sharpe_12m` | Float | Índice Sharpe nos últimos 12 meses |

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

### Ferramentas de Diagnóstico (Proxies)

* **`GET /api/proxy_fnet/{cnpj}`:** Busca documentos regulatórios de um fundo diretamente na B3/FNET pelo CNPJ, filtrados pelo mês corrente. Consumido internamente por `/api/calendar`.
* **`GET /api/proxy_maisretorno/{ticker}`:** Rota de diagnóstico para consulta e verificação de payload bruto diretamente na API da Mais Retorno.
* **`GET /api/proxy_quantbrasil/{ticker}`:** Rota de verificação dos dados extraídos do QuantBrasil.
* **`GET /api/proxy_tesouro`:** Diagnóstico do parse do CSV bruto do Tesouro Direto.
* **`GET /api/proxy/{ticker}`:** Retorna o HTML bruto do Fundamentus para validação de estrutura da página.

---

## Cache

Todas as rotas que realizam requisições externas (Fundamentus, QuantBrasil, Mais Retorno, B3/FNET e Tesouro Direto) usam um cache em memória com TTL de **30 minutos**, implementado em `cache.py`. Isso reduz drasticamente o tráfego externo, evita *rate limiting* e garante respostas instantâneas em chamadas repetidas.

> **Observação:** por rodar em ambiente serverless (Vercel), o cache em memória vale enquanto a instância da função permanecer "quente" (*warm start*).

---

## Fontes de dados e créditos

A API opera como uma camada de agregação e estruturação de dados de múltiplas fontes públicas e de mercado:

* **[Fundamentus](https://www.fundamentus.com.br/index.php):** Web scraping de dados contábeis brutos de Ações e indicadores de FIIs.
* **[Mais Retorno](https://maisretorno.com/):** Métricas avançadas de risco e retorno (Índice Sharpe e rentabilidades acumuladas/12m).
* **[QuantBrasil](https://quantbrasil.com.br/):** Extração do Beta histórico (3 anos) vs IBOVESPA.
* **[Tesouro Direto](https://www.tesourodireto.com.br/):** Fonte oficial dos arquivos CSV de preços e taxas dos títulos públicos.
* **[FNET / B3 (CVM)](https://fnet.bmfbovespa.com.br/fnet/publico/abrirGerenciadorDocumentosCVM):** Monitoramento de eventos e informes regulatórios em tempo real.

> Este projeto é de uso pessoal/educacional. Os dados pertencem aos seus respectivos provedores de origem e devem ser utilizados respeitando os termos de uso de cada plataforma.

---

## Stack

* **Linguagem:** Python 3.10+
* **Framework Web:** FastAPI (com `asyncio` para I/O não bloqueante)
* **Template Engine:** Jinja2
* **Parsing / Web Scraping / Networking:** BeautifulSoup4, HTTP Clients (`httpx`, `requests`) e `curl-cffi` (impersonate Chrome para bypass de WAF/TLS)
* **Servidor ASGI (dev):** Uvicorn
* **Deploy:** Vercel (serverless functions)

---

## Onde essa API é usada

Esta API é consumida por uma planilha de controle de carteira de investimentos no Google Sheets, via Google Apps Script, que atualiza automaticamente os dados contábeis de ações e FIIs, o calendário de eventos regulatórios e a precificação de títulos públicos da carteira.

👉 Repositório da planilha: [carteira-investimentos](https://github.com/GuilhermeMGarcia/carteira-investimentos)

---

## Rodando localmente

```bash
git clone [https://github.com/GuilhermeMGarcia/api-indicadores-financeiros.git](https://github.com/GuilhermeMGarcia/api-indicadores-financeiros.git)
cd api-indicadores-financeiros
pip install -r requirements.txt
uvicorn index:app --reload

```

A API sobe em `http://127.0.0.1:8000`. A página inicial (`/`) traz um painel interativo com ticker tape dinâmico e atalhos para os endpoints; a documentação interativa fica em `/docs` (Swagger) e `/redoc` (ReDoc).

---

## Autor

G.Garcia
```

```
