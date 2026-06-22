import httpx
from fastapi import APIRouter, Query, HTTPException

router = APIRouter(prefix="/api/lugares", tags=["lugares"])

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


@router.get("")
async def buscar_lugares(q: str = Query(..., min_length=3)):
    """
    Busca estabelecimentos usando OpenStreetMap/Nominatim.
    Retorna nome, endereço e categoria dos locais encontrados.
    """
    params = {
        "q": q,
        "format": "json",
        "limit": 6,
        "countrycodes": "br",
        "viewbox": "-73.99,-33.75,-34.79,-1.04",  # BB do Brasil
    }

    headers = {
        "User-Agent": "GestaoSuprimentos/1.0",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(NOMINATIM_URL, params=params, headers=headers)

        if res.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"Erro ao buscar locais: {res.status_code}"
            )

        results = res.json()
        if not isinstance(results, list):
            results = []

        lugares = []
        for r in results:
            # Nominatim retorna campos: display_name, address, lat, lon, type, class
            nome = r.get("name", r.get("display_name", ""))
            endereco = r.get("display_name", "")

            # Se o nome e endereço são iguais, simplesmente mostrar nome
            if nome and endereco.startswith(nome):
                endereco = endereco[len(nome):].lstrip(",").strip()

            lugares.append({
                "nome": nome,
                "endereco": endereco,
                "categoria": r.get("class", ""),
                "telefone": "",
            })

        return lugares

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Tempo limite excedido ao buscar locais"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao buscar locais: {str(e)}"
        )
