import time
import httpx
from datetime import datetime
from fastapi import APIRouter

router = APIRouter()

FNET_SESSION_URL = "https://fnet.bmfbovespa.com.br/fnet/publico/abrirGerenciadorDocumentosCVM"
FNET_DATA_URL = "https://fnet.bmfbovespa.com.br/fnet/publico/pesquisarGerenciadorDocumentosDados"


@router.get("/proxy_fnet/{cnpj}", tags=["Ferramentas de Diagnóstico (Proxy)"])
async def debug_fnet_raw(cnpj: str):
    cnpj_limpo = cnpj.replace(".", "").replace("-", "").replace("/", "").strip()

    # 1. Parâmetros de consulta à B3 (O segredo é incluir o cnpjFundo aqui!)
    params = {
        "d": "1",
        "s": "0",
        "l": "30",
        "cnpjFundo": cnpj_limpo,  # ESSENCIAL para a B3 saber qual fundo consultar
        "o[0][dataReferencia]": "desc",
        "idCategoriaDocumento": "0",
        "idTipoDocumento": "0",
        "idEspecieDocumento": "0",
        "isSession": "true",
        "_": str(int(time.time() * 1000)),
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }

    async with httpx.AsyncClient(verify=False, follow_redirects=True) as client:
        # A. Handshake (Sessão)
        await client.get(FNET_SESSION_URL, params={"cnpjFundo": cnpj_limpo}, headers=headers)

        # B. Requisição de Dados
        response = await client.get(FNET_DATA_URL, params=params, headers=headers)

        if response.status_code != 200:
            return {"erro": f"Status B3: {response.status_code}"}

        raw_data = response.json()
        hoje = datetime.now()
        documentos_filtrados = []

        # C. Filtro Robusto (A lógica que o GPT sugeriu)
        for doc in raw_data.get("data", []):
            try:
                # Usa dataEntrega para pegar o que foi publicado no mês atual
                data_entrega = datetime.strptime(doc["dataEntrega"], "%d/%m/%Y %H:%M")

                if data_entrega.month != hoje.month or data_entrega.year != hoje.year:
                    continue

                tipo = doc.get("tipoDocumento", "")

                # Lógica de classificação resiliente
                eh_relatorio = tipo == "Relatório Gerencial"
                eh_informe = (
                        tipo == "Informe Mensal Estruturado"
                        or (tipo == "Informe Mensal" and doc.get("arquivoEstruturado") == "S")
                )

                if eh_relatorio or eh_informe:
                    documentos_filtrados.append(doc)
            except:
                continue

        return {
            "status": "success",
            "total_encontrado": len(raw_data.get("data", [])),
            "total_filtrado": len(documentos_filtrados),
            "documentos": documentos_filtrados
        }