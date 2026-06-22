import httpx
from fastapi import APIRouter, Query, HTTPException

router = APIRouter(prefix="/api/lugares", tags=["lugares"])

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


def _parse_result(r: dict) -> dict:
    """Converte resultado do Nominatim para o formato esperado."""
    nome = r.get("name", r.get("display_name", ""))
    endereco = r.get("display_name", "")

    if nome and endereco.startswith(nome):
        endereco = endereco[len(nome):].lstrip(",").strip()

    return {
        "nome": nome,
        "endereco": endereco,
        "categoria": r.get("class", ""),
        "telefone": "",
    }


async def _buscar_nominatim(query: str, limit: int = 8) -> list:
    """Faz requisição ao Nominatim com retry."""
    params = {
        "q": query,
        "format": "json",
        "limit": limit,
        "countrycodes": "br",
    }

    headers = {"User-Agent": "GestaoSuprimentos/1.0"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(NOMINATIM_URL, params=params, headers=headers)

        if res.status_code == 200:
            results = res.json()
            return results if isinstance(results, list) else []

        return []

    except (httpx.TimeoutException, Exception):
        return []


@router.get("")
async def buscar_lugares(q: str = Query(..., min_length=3)):
    """
    Busca estabelecimentos priorizando Ibiúna, SP.
    Estratégia: tenta buscar com termos locais para melhorar relevância.
    """
    try:
        # 1. Busca inicial: termo + Ibiúna
        query_ibiuna = f"{q} Ibiúna"
        resultados_ibiuna = await _buscar_nominatim(query_ibiuna, limit=8)

        # Se encontrou bons resultados em Ibiúna, retorna
        if len(resultados_ibiuna) >= 3:
            return [_parse_result(r) for r in resultados_ibiuna[:6]]

        # 2. Se poucos resultados, tenta com São Paulo
        query_sp = f"{q} São Paulo"
        resultados_sp = await _buscar_nominatim(query_sp, limit=8)

        # 3. Se ainda tiver poucos, tenta busca sem filtro
        if len(resultados_sp) < 3:
            resultados_geral = await _buscar_nominatim(q, limit=8)
        else:
            resultados_geral = []

        # Mescla resultados, priorizando Ibiúna > SP > Geral
        vistos = {r.get("display_name") for r in resultados_ibiuna}
        resultados_mesclados = resultados_ibiuna.copy()

        for r in resultados_sp:
            if r.get("display_name") not in vistos:
                resultados_mesclados.append(r)
                vistos.add(r.get("display_name"))

        for r in resultados_geral:
            if r.get("display_name") not in vistos:
                resultados_mesclados.append(r)
                if len(resultados_mesclados) >= 6:
                    break

        return [_parse_result(r) for r in resultados_mesclados[:6]]

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao buscar locais: {str(e)}"
        )
