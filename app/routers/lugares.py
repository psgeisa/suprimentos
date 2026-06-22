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
    """Faz requisição ao Nominatim."""
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
    Busca inteligente de estabelecimentos e endereços.
    Estratégia combinada:
    1. Busca por nome de estabelecimento (ex: "Farmacia", "Restaurante")
    2. Se poucos resultados, busca por endereço/rua (ex: "Rua Principal")
    3. Prioriza resultados de Ibiúna, São Paulo
    """
    try:
        vistos = set()
        resultados_finais = []

        # ==================== FASE 1: Busca como ESTABELECIMENTO ====================
        # 1.1 Tenta em Ibiúna como estabelecimento
        query_estabelecimento_ibiuna = f"{q} Ibiúna"
        resultados_estab_ibiuna = await _buscar_nominatim(query_estabelecimento_ibiuna, limit=8)

        for r in resultados_estab_ibiuna:
            display_name = r.get("display_name", "")
            if display_name not in vistos:
                resultados_finais.append(r)
                vistos.add(display_name)

        # Se encontrou bons resultados, retorna aqui
        if len(resultados_finais) >= 3:
            return [_parse_result(r) for r in resultados_finais[:6]]

        # 1.2 Tenta em SP se não encontrou em Ibiúna
        query_estabelecimento_sp = f"{q} São Paulo"
        resultados_estab_sp = await _buscar_nominatim(query_estabelecimento_sp, limit=8)

        for r in resultados_estab_sp:
            display_name = r.get("display_name", "")
            if display_name not in vistos:
                resultados_finais.append(r)
                vistos.add(display_name)

        # ==================== FASE 2: Busca como ENDEREÇO/RUA ====================
        # Se ainda poucos resultados, tenta busca por endereço/rua
        if len(resultados_finais) < 3:
            # Tenta em Ibiúna como rua/endereço
            query_endereco_ibiuna = f"Rua {q}, Ibiúna" if not q.lower().startswith("rua") else f"{q}, Ibiúna"
            resultados_end_ibiuna = await _buscar_nominatim(query_endereco_ibiuna, limit=8)

            for r in resultados_end_ibiuna:
                display_name = r.get("display_name", "")
                if display_name not in vistos:
                    resultados_finais.append(r)
                    vistos.add(display_name)

        # Se ainda poucos, tenta em SP como rua/endereço
        if len(resultados_finais) < 3:
            query_endereco_sp = f"Rua {q}, São Paulo" if not q.lower().startswith("rua") else f"{q}, São Paulo"
            resultados_end_sp = await _buscar_nominatim(query_endereco_sp, limit=8)

            for r in resultados_end_sp:
                display_name = r.get("display_name", "")
                if display_name not in vistos:
                    resultados_finais.append(r)
                    vistos.add(display_name)

        # ==================== FASE 3: Busca GERAL ====================
        # Se ainda vazio, tenta busca geral sem filtros
        if len(resultados_finais) < 3:
            resultados_geral = await _buscar_nominatim(q, limit=8)

            for r in resultados_geral:
                display_name = r.get("display_name", "")
                if display_name not in vistos and len(resultados_finais) < 6:
                    resultados_finais.append(r)
                    vistos.add(display_name)

        return [_parse_result(r) for r in resultados_finais[:6]]

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao buscar locais: {str(e)}"
        )
