import os
import httpx
from fastapi import APIRouter, Query, HTTPException

router = APIRouter(prefix="/api/lugares", tags=["lugares"])

FOURSQUARE_KEY = os.getenv("FOURSQUARE_KEY", "")
FSQ_URL = "https://api.foursquare.com/v3/places/search"


@router.get("")
async def buscar_lugares(q: str = Query(..., min_length=3)):
    if not FOURSQUARE_KEY:
        raise HTTPException(status_code=503, detail="FOURSQUARE_KEY não configurada.")

    headers = {
        "Authorization": FOURSQUARE_KEY,
        "Accept": "application/json",
    }
    params = {
        "query": q,
        "near": "Brasil",
        "limit": 6,
        "fields": "name,location,tel,categories",
    }

    async with httpx.AsyncClient(timeout=8) as client:
        res = await client.get(FSQ_URL, headers=headers, params=params)

    if res.status_code != 200:
        raise HTTPException(status_code=502, detail="Erro ao consultar Foursquare.")

    results = res.json().get("results", [])
    lugares = []
    for r in results:
        loc = r.get("location", {})
        address_parts = [
            loc.get("address"),
            loc.get("neighborhood"),
            loc.get("locality"),
            loc.get("region"),
        ]
        address = ", ".join(p for p in address_parts if p)
        lugares.append({
            "nome": r.get("name", ""),
            "endereco": address,
            "categoria": r.get("categories", [{}])[0].get("name", "") if r.get("categories") else "",
            "telefone": r.get("tel", ""),
        })

    return lugares
