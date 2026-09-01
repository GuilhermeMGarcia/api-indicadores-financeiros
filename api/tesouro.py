import io
import csv
import re
import asyncio
from fastapi import APIRouter, HTTPException
from curl_cffi import requests
from api.Cache import TTLCache

router = APIRouter()

URL_HOME_TESOURO = "https://www.tesourodireto.com.br/titulos/precos-e-taxas.htm"
URL_INVESTIR_CSV = "https://www.tesourodireto.com.br/documents/d/guest/rendimento-investir-csv?download=true"
URL_RESGATAR_CSV = "https://www.tesourodireto.com.br/documents/d/guest/rendimento-resgatar-csv?download=true"

TESOURO_CACHE_TTL_SECONDS = 30 * 60  # Cache de 30 minutos
tesouro_cache = TTLCache(ttl_seconds=TESOURO_CACHE_TTL_SECONDS)


def _parse_preco(valor: str):
    """Converte 'R$ 19.729,11' ou 'R$\xa0197,29' em float 19729.11"""
    if not valor:
        return None
    limpo = (
        valor.replace("R$", "")
        .replace("\xa0", "")
        .strip()
        .replace(".", "")
        .replace(",", ".")
    )
    try:
        return float(limpo)
    except ValueError:
        return None


def _extrair_vencimento(nome: str, vencimento_csv: str) -> str:
    """Usa o vencimento do CSV se existir; caso contrário, extrai o ano do nome do título."""
    if vencimento_csv:
        return vencimento_csv

    # Procura um ano de 4 dígitos no nome (ex: "Tesouro IPCA+ 2032" -> "01/01/2032")
    match = re.search(r"\b(20\d{2})\b", nome)
    if match:
        ano = match.group(1)
        return f"01/01/{ano}"

    return ""


def _fetch_tesouro_com_sessao_sync() -> tuple[str, str]:
    """1. Visita Home (Warm-up) -> 2. Baixa CSVs na mesma sessão"""
    with requests.Session(impersonate="chrome120") as session:
        headers_base = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
        }

        res_home = session.get(URL_HOME_TESOURO, headers=headers_base, timeout=10)
        if res_home.status_code != 200:
            raise Exception(f"Falha ao abrir home do Tesouro: Status {res_home.status_code}")

        res_investir = session.get(URL_INVESTIR_CSV, headers=headers_base, timeout=12)
        res_resgatar = session.get(URL_RESGATAR_CSV, headers=headers_base, timeout=12)

        if res_investir.status_code != 200 or res_resgatar.status_code != 200:
            raise Exception(
                f"Erro ao baixar CSVs. Investir: {res_investir.status_code} | Resgatar: {res_resgatar.status_code}"
            )

        return (
            res_investir.content.decode("utf-8-sig"),
            res_resgatar.content.decode("utf-8-sig"),
        )


def _parse_investir_csv(texto: str) -> dict:
    leitor = csv.DictReader(io.StringIO(texto), delimiter=";")
    dados = {}
    for linha in leitor:
        nome = (linha.get("Título") or "").strip()
        if not nome:
            continue
        dados[nome] = {
            "taxa_compra": (linha.get("Rendimento anual do título") or "").strip() or None,
            "preco_compra": _parse_preco(linha.get("Preço unitário de investimento")),
            "investimento_minimo": _parse_preco(linha.get("Investimento mínimo")),
            "vencimento": (linha.get("Vencimento do Título") or "").strip(),
        }
    return dados


def _parse_resgatar_csv(texto: str) -> dict:
    leitor = csv.DictReader(io.StringIO(texto), delimiter=";")
    dados = {}
    for linha in leitor:
        nome = (linha.get("Título") or "").strip()
        if not nome:
            continue
        dados[nome] = {
            "taxa_venda": (linha.get("Rendimento anual do título") or "").strip() or None,
            "preco_venda": _parse_preco(linha.get("Preço unitário de resgate")),
        }
    return dados


@router.get("/tesouro")
async def get_tesouro_bonds():
    """
    Retorna preços e taxas do Tesouro Direto com warm-up de sessão prévia e bypass TLS.
    """
    cached = tesouro_cache.get("titulos")
    if cached is not None:
        return cached

    try:
        loop = asyncio.get_event_loop()
        texto_investir, texto_resgatar = await loop.run_in_executor(
            None, _fetch_tesouro_com_sessao_sync
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro ao acessar Tesouro Direto: {str(e)}"
        )

    dados_compra = _parse_investir_csv(texto_investir)
    dados_venda = _parse_resgatar_csv(texto_resgatar)

    nomes_titulos = sorted(set(dados_compra) | set(dados_venda))

    lista_titulos = []
    for nome in nomes_titulos:
        compra = dados_compra.get(nome, {})
        venda = dados_venda.get(nome, {})

        venc_bruto = compra.get("vencimento", "")
        venc_final = _extrair_vencimento(nome, venc_bruto)

        lista_titulos.append({
            "nome": nome,
            "taxa_compra": compra.get("taxa_compra"),
            "preco_compra": compra.get("preco_compra"),
            "investimento_minimo": compra.get("investimento_minimo"),
            "taxa_venda": venda.get("taxa_venda"),
            "preco_venda": venda.get("preco_venda"),
            "vencimento": venc_final,
        })

    resultado = {
        "status": "OK",
        "total": len(lista_titulos),
        "titulos": lista_titulos,
    }

    if len(lista_titulos) > 0:
        tesouro_cache.set("titulos", resultado)

    return resultado