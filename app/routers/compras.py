import json
import math
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.compra_log import CompraLog
from app.models.estabelecimento import Estabelecimento
from app.models.item_eliminado_log import ItemEliminadoLog
from app.models.suprimento import Suprimento

router = APIRouter(prefix="/api/compras", tags=["compras"])

STATUSES_ABERTOS = ["pendente", "aprovado", "em_andamento"]


@router.get("/ordens")
def listar_ordens(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Retorna IDs e títulos de suprimentos em aberto para o multiselect de Ordem de Compra."""
    items = (
        db.query(Suprimento)
        .filter(Suprimento.status.in_(STATUSES_ABERTOS))
        .order_by(Suprimento.id.desc())
        .limit(500)
        .all()
    )
    return [{"id": i.id, "label": f"#{i.id} — {(i.titulo or '')[:50]}"} for i in items]


@router.get("/itens")
def listar_itens_compra(
    ids: Optional[str] = Query(None),
    busca: Optional[str] = Query(None),
    segmento: Optional[str] = Query(None),
    prioridade: Optional[str] = Query(None),
    estabelecimento: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    q = db.query(Suprimento).filter(Suprimento.status.in_(STATUSES_ABERTOS))

    if ids:
        id_list = [int(v) for v in ids.split(",") if v.strip().isdigit()]
        if id_list:
            q = q.filter(Suprimento.id.in_(id_list))

    if busca:
        b = f"%{busca}%"
        q = q.filter(
            Suprimento.titulo.ilike(b)
            | Suprimento.item_nome.ilike(b)
            | Suprimento.categoria.ilike(b)
            | Suprimento.solicitante.ilike(b)
        )

    if segmento:
        q = q.filter(Suprimento.categoria.in_([v for v in segmento.split(",") if v]))

    if prioridade:
        q = q.filter(Suprimento.prioridade.in_([v for v in prioridade.split(",") if v]))

    if estabelecimento:
        est_ids = [int(v) for v in estabelecimento.split(",") if v.strip().isdigit()]
        if est_ids:
            q = q.filter(Suprimento.estabelecimento_id.in_(est_ids))

    total = q.count()
    pages = max(1, math.ceil(total / limit))
    items = (
        q.order_by(Suprimento.prioridade.desc(), Suprimento.created_at.asc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    est_ids_set = {i.estabelecimento_id for i in items if i.estabelecimento_id}
    est_map = {}
    if est_ids_set:
        ests = db.query(Estabelecimento).filter(Estabelecimento.id.in_(est_ids_set)).all()
        est_map = {e.id: e.tipo for e in ests}

    result = []
    for i in items:
        result.append(
            {
                "id": i.id,
                "titulo": i.titulo,
                "item_nome": i.item_nome,
                "categoria": i.categoria,
                "quantidade": i.quantidade,
                "unidade": i.unidade,
                "valor_estimado": i.valor_estimado,
                "prioridade": i.prioridade,
                "emergencia": i.emergencia,
                "status": i.status,
                "solicitante": i.solicitante,
                "departamento": i.departamento,
                "estabelecimento_id": i.estabelecimento_id,
                "estabelecimento_tipo": est_map.get(i.estabelecimento_id) if i.estabelecimento_id else None,
                "created_at": i.created_at.isoformat() if i.created_at else None,
            }
        )

    return {"items": result, "total": total, "page": page, "pages": pages}


class EliminarRequest(BaseModel):
    suprimento_id: int
    motivo: Optional[str] = None


@router.post("/eliminar")
def eliminar_item(
    data: EliminarRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    sup = db.query(Suprimento).filter(Suprimento.id == data.suprimento_id).first()
    if not sup:
        raise HTTPException(404, "Suprimento não encontrado")

    log = ItemEliminadoLog(
        suprimento_id=sup.id,
        titulo=sup.titulo,
        item_nome=sup.item_nome,
        categoria=sup.categoria,
        solicitante=sup.solicitante,
        usuario_que_eliminou=current_user.nome,
        usuario_id=current_user.id,
        motivo=data.motivo,
        data_hora=datetime.utcnow(),
    )
    db.add(log)

    sup.status = "cancelado"
    sup.updated_at = datetime.utcnow()
    db.commit()

    return {"ok": True, "log_id": log.id}


class FinalizarItemSchema(BaseModel):
    id: int
    titulo: Optional[str] = None
    item_nome: Optional[str] = None
    categoria: Optional[str] = None
    quantidade: Optional[float] = None
    unidade: Optional[str] = None
    valor_estimado: Optional[float] = None
    estabelecimento_tipo: Optional[str] = None
    solicitante: Optional[str] = None
    prioridade: Optional[str] = None


class FinalizarRequest(BaseModel):
    comprados: List[FinalizarItemSchema]
    nao_comprados: List[int]
    observacoes: Optional[str] = None


@router.post("/finalizar")
def finalizar_compra(
    data: FinalizarRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    comprados_ids = [i.id for i in data.comprados]

    if comprados_ids:
        db.query(Suprimento).filter(Suprimento.id.in_(comprados_ids)).update(
            {"status": "concluido", "updated_at": datetime.utcnow()},
            synchronize_session=False,
        )

    total_estimado = sum((i.valor_estimado or 0) for i in data.comprados) or None

    log = CompraLog(
        usuario=current_user.nome,
        usuario_id=current_user.id,
        data_hora=datetime.utcnow(),
        itens_comprados=json.dumps(
            [i.model_dump() for i in data.comprados], ensure_ascii=False
        ),
        itens_nao_comprados=json.dumps(data.nao_comprados),
        total_estimado=total_estimado,
        observacoes=data.observacoes,
    )
    db.add(log)
    db.commit()

    return {"ok": True, "log_id": log.id, "total_comprados": len(comprados_ids)}
