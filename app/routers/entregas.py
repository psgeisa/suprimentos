import math
import os
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.anexo import Anexo
from app.models.estabelecimento import Estabelecimento
from app.models.suprimento import Suprimento
from app.routers.anexos import MAX_SIZE, _get_supabase

router = APIRouter(prefix="/api/entregas", tags=["entregas"])

STATUS_ENTREGA = "em_andamento"
ENTREGA_BUCKET = "entrega"


def _group_orders(items):
    grouped = {}
    for item in items:
        order_code = item.ordem_compra or f"SOL{item.id:04d}"
        if order_code not in grouped:
            grouped[order_code] = {"title": item.titulo or "", "total": 0}
        grouped[order_code]["total"] += 1
    return [
        {
            "value": order_code,
            "label": (
                f"{order_code} — {group['title'][:50]} "
                f"({group['total']} {'item' if group['total'] == 1 else 'itens'})"
            ),
        }
        for order_code, group in grouped.items()
    ]


@router.get("/filtros")
def listar_filtros(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    items = (
        db.query(Suprimento)
        .filter(Suprimento.status == STATUS_ENTREGA)
        .order_by(Suprimento.id.desc())
        .limit(5000)
        .all()
    )
    establishment_ids = {item.estabelecimento_id for item in items if item.estabelecimento_id}
    establishment_map = {}
    if establishment_ids:
        rows = (
            db.query(Estabelecimento)
            .filter(Estabelecimento.id.in_(establishment_ids))
            .all()
        )
        establishment_map = {item.id: item.tipo for item in rows}

    priority_labels = {
        "baixa": "Baixa",
        "media": "Média",
        "alta": "Alta",
        "urgente": "Urgente",
    }
    present_priorities = {item.prioridade for item in items if item.prioridade}
    return {
        "ordens": _group_orders(items),
        "segmentos": sorted({item.categoria for item in items if item.categoria}),
        "prioridades": [
            {"value": value, "label": label}
            for value, label in priority_labels.items()
            if value in present_priorities
        ],
        "estabelecimentos": [
            {"value": str(establishment_id), "label": establishment_map[establishment_id]}
            for establishment_id in sorted(
                establishment_ids,
                key=lambda value: establishment_map.get(value, "").lower(),
            )
            if establishment_id in establishment_map
        ],
    }


@router.get("/itens")
def listar_itens(
    ordens: Optional[str] = Query(None),
    busca: Optional[str] = Query(None),
    segmento: Optional[str] = Query(None),
    prioridade: Optional[str] = Query(None),
    estabelecimento: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(Suprimento).filter(Suprimento.status == STATUS_ENTREGA)

    if ordens:
        order_list = [value.strip() for value in ordens.split(",") if value.strip()]
        fallback_ids = [
            int(value[3:])
            for value in order_list
            if value.startswith("SOL") and value[3:].isdigit()
        ]
        query = query.filter(
            Suprimento.ordem_compra.in_(order_list)
            | Suprimento.id.in_(fallback_ids)
        )
    if busca:
        term = f"%{busca}%"
        query = query.filter(
            Suprimento.titulo.ilike(term)
            | Suprimento.item_nome.ilike(term)
            | Suprimento.categoria.ilike(term)
            | Suprimento.solicitante.ilike(term)
            | Suprimento.ordem_compra.ilike(term)
            | Suprimento.responsavel_entrega.ilike(term)
        )
    if segmento:
        query = query.filter(
            Suprimento.categoria.in_([value for value in segmento.split(",") if value])
        )
    if prioridade:
        query = query.filter(
            Suprimento.prioridade.in_([value for value in prioridade.split(",") if value])
        )
    if estabelecimento:
        establishment_ids = [
            int(value)
            for value in estabelecimento.split(",")
            if value.strip().isdigit()
        ]
        if establishment_ids:
            query = query.filter(Suprimento.estabelecimento_id.in_(establishment_ids))

    priority_order = case(
        (Suprimento.prioridade == "urgente", 0),
        (Suprimento.prioridade == "alta", 1),
        (Suprimento.prioridade == "media", 2),
        else_=3,
    )
    query = query.outerjoin(
        Estabelecimento,
        Suprimento.estabelecimento_id == Estabelecimento.id,
    )
    sortable = {
        "ordem": Suprimento.ordem_compra,
        "estabelecimento": func.lower(func.coalesce(Estabelecimento.tipo, "")),
        "item": func.lower(func.coalesce(Suprimento.item_nome, Suprimento.titulo, "")),
        "segmento": func.lower(func.coalesce(Suprimento.categoria, "")),
        "prioridade": priority_order,
    }
    if sort_by in sortable:
        column = sortable[sort_by]
        ordering = column.desc() if sort_dir == "desc" else column.asc()
        order_by = [ordering, Suprimento.id.asc()]
    else:
        order_by = [
            Suprimento.emergencia.desc(),
            func.lower(func.coalesce(Estabelecimento.tipo, "")).asc(),
            priority_order,
            Suprimento.created_at.asc(),
        ]

    total = query.count()
    pages = max(1, math.ceil(total / limit))
    items = (
        query.order_by(*order_by)
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    establishment_ids = {item.estabelecimento_id for item in items if item.estabelecimento_id}
    establishment_map = {}
    if establishment_ids:
        rows = (
            db.query(Estabelecimento)
            .filter(Estabelecimento.id.in_(establishment_ids))
            .all()
        )
        establishment_map = {item.id: item.tipo for item in rows}

    item_ids = [item.id for item in items]
    photo_map = {}
    if item_ids:
        photos = (
            db.query(Anexo)
            .filter(
                Anexo.suprimento_id.in_(item_ids),
                Anexo.bucket == ENTREGA_BUCKET,
            )
            .order_by(Anexo.criado_em.desc())
            .all()
        )
        for photo in photos:
            photo_map.setdefault(photo.suprimento_id, photo)

    result = []
    for item in items:
        photo = photo_map.get(item.id)
        result.append(
            {
                "id": item.id,
                "ordem_compra": item.ordem_compra or f"SOL{item.id:04d}",
                "titulo": item.titulo,
                "item_nome": item.item_nome,
                "categoria": item.categoria,
                "quantidade": item.quantidade,
                "unidade": item.unidade,
                "valor_compra": item.valor_compra,
                "prioridade": item.prioridade,
                "emergencia": item.emergencia,
                "solicitante": item.solicitante,
                "estabelecimento_id": item.estabelecimento_id,
                "estabelecimento_tipo": establishment_map.get(item.estabelecimento_id),
                "responsavel_entrega": item.responsavel_entrega,
                "foto_url": photo.url_storage if photo else None,
                "foto_nome": photo.nome_arquivo if photo else None,
            }
        )
    return {"items": result, "total": total, "page": page, "pages": pages}


class ResponsavelEntregaRequest(BaseModel):
    responsavel: Optional[str] = None


@router.put("/{suprimento_id}/responsavel")
def salvar_responsavel(
    suprimento_id: int,
    data: ResponsavelEntregaRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    item = db.query(Suprimento).filter(Suprimento.id == suprimento_id).first()
    if not item:
        raise HTTPException(404, "Suprimento não encontrado")
    if item.status != STATUS_ENTREGA:
        raise HTTPException(409, "Somente itens em andamento podem receber responsável")
    item.responsavel_entrega = (data.responsavel or "").strip() or None
    item.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "responsavel": item.responsavel_entrega}


@router.post("/{suprimento_id}/foto", status_code=201)
async def upload_foto_entrega(
    suprimento_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    item = db.query(Suprimento).filter(Suprimento.id == suprimento_id).first()
    if not item:
        raise HTTPException(404, "Suprimento não encontrado")
    if item.status != STATUS_ENTREGA:
        raise HTTPException(409, "Somente itens em andamento podem receber foto")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(400, "Envie um arquivo de imagem")

    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(413, "Arquivo maior que 10 MB")

    extension = (
        file.filename.rsplit(".", 1)[-1]
        if "." in (file.filename or "")
        else "jpg"
    )
    storage_path = f"{suprimento_id}/{uuid.uuid4().hex}.{extension}"
    storage = _get_supabase()
    storage.storage.from_(ENTREGA_BUCKET).upload(
        storage_path,
        contents,
        {"content-type": file.content_type or "image/jpeg"},
    )
    public_url = storage.storage.from_(ENTREGA_BUCKET).get_public_url(storage_path)

    attachment = Anexo(
        suprimento_id=suprimento_id,
        nome_arquivo=file.filename or storage_path,
        tipo_mime=file.content_type,
        tamanho_bytes=len(contents),
        url_storage=public_url,
        bucket=ENTREGA_BUCKET,
        criado_por=current_user.nome,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return {
        "id": attachment.id,
        "url_storage": attachment.url_storage,
        "bucket": attachment.bucket,
    }


class EntregaFinalizarItem(BaseModel):
    id: int
    responsavel: Optional[str] = None


class EntregaFinalizarRequest(BaseModel):
    entregues: List[EntregaFinalizarItem]


@router.post("/finalizar")
def finalizar_entregas(
    data: EntregaFinalizarRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    delivered = 0
    delivered_at = datetime.utcnow()
    for delivered_item in data.entregues:
        item = (
            db.query(Suprimento)
            .filter(
                Suprimento.id == delivered_item.id,
                Suprimento.status == STATUS_ENTREGA,
            )
            .first()
        )
        if not item:
            continue
        item.status = "concluido"
        item.responsavel_entrega = (
            delivered_item.responsavel or item.responsavel_entrega or ""
        ).strip() or None
        item.entregue_em = delivered_at
        item.updated_at = delivered_at
        delivered += 1
    db.commit()
    return {"ok": True, "total_entregues": delivered}
