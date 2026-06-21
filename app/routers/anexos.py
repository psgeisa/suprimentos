import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.anexo import Anexo
from app.models.suprimento import Suprimento
from app.schemas.anexo import AnexoOut
from app.auth import get_current_user

router = APIRouter(tags=["anexos"])

BUCKET = "suprimentos-docs"
MAX_SIZE = 10 * 1024 * 1024  # 10 MB


def _get_supabase():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise HTTPException(
            503,
            "Supabase Storage não configurado. Defina SUPABASE_URL e SUPABASE_KEY no .env",
        )
    from supabase import create_client
    return create_client(url, key)


@router.get("/api/suprimentos/{sup_id}/anexos", response_model=List[AnexoOut])
def listar_anexos(sup_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    if not db.query(Suprimento).filter(Suprimento.id == sup_id).first():
        raise HTTPException(404, "Suprimento não encontrado")
    return (
        db.query(Anexo)
        .filter(Anexo.suprimento_id == sup_id)
        .order_by(Anexo.criado_em.desc())
        .all()
    )


@router.post("/api/suprimentos/{sup_id}/anexos", response_model=AnexoOut, status_code=201)
async def upload_anexo(
    sup_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not db.query(Suprimento).filter(Suprimento.id == sup_id).first():
        raise HTTPException(404, "Suprimento não encontrado")

    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(413, "Arquivo maior que 10 MB")

    sb = _get_supabase()
    ext = file.filename.rsplit(".", 1)[-1] if "." in (file.filename or "") else "bin"
    storage_path = f"{sup_id}/{uuid.uuid4().hex}.{ext}"

    sb.storage.from_(BUCKET).upload(
        storage_path,
        contents,
        {"content-type": file.content_type or "application/octet-stream"},
    )
    public_url = sb.storage.from_(BUCKET).get_public_url(storage_path)

    anexo = Anexo(
        suprimento_id=sup_id,
        nome_arquivo=file.filename or storage_path,
        tipo_mime=file.content_type,
        tamanho_bytes=len(contents),
        url_storage=public_url,
        bucket=BUCKET,
        criado_por=current_user.nome,
    )
    db.add(anexo)
    db.commit()
    db.refresh(anexo)
    return anexo


@router.delete("/api/anexos/{anexo_id}", status_code=204)
def deletar_anexo(
    anexo_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    anexo = db.query(Anexo).filter(Anexo.id == anexo_id).first()
    if not anexo:
        raise HTTPException(404, "Anexo não encontrado")

    try:
        sb = _get_supabase()
        marker = f"/object/public/{BUCKET}/"
        url = anexo.url_storage
        if marker in url:
            path = url.split(marker, 1)[1]
            sb.storage.from_(BUCKET).remove([path])
    except Exception:
        pass  # Removemos do DB mesmo se o storage falhar

    db.delete(anexo)
    db.commit()
