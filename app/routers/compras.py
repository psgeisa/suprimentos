import json
import math
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import case, func
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
        .filter(Suprimento.status == "pendente")
        .order_by(Suprimento.id.desc())
        .limit(2000)
        .all()
    )
    grouped = {}
    for item in items:
        ordem = item.ordem_compra or f"SOL{item.id:04d}"
        if ordem not in grouped:
            grouped[ordem] = {"titulo": item.titulo or "", "total": 0}
        grouped[ordem]["total"] += 1
    return [{
        "ordem_compra": ordem,
        "label": (
            f"{ordem} — {group['titulo'][:50]} "
            f"({group['total']} {'item' if group['total'] == 1 else 'itens'})"
        ),
    } for ordem, group in grouped.items()]


@router.get("/filtros")
def listar_filtros(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Opções dos filtros de compra derivadas somente de solicitações pendentes."""
    items = (
        db.query(Suprimento)
        .filter(Suprimento.status == "pendente")
        .order_by(Suprimento.id.desc())
        .limit(5000)
        .all()
    )

    grouped_orders = {}
    for item in items:
        ordem = item.ordem_compra or f"SOL{item.id:04d}"
        if ordem not in grouped_orders:
            grouped_orders[ordem] = {"titulo": item.titulo or "", "total": 0}
        grouped_orders[ordem]["total"] += 1

    est_ids = {item.estabelecimento_id for item in items if item.estabelecimento_id}
    est_map = {}
    if est_ids:
        estabelecimentos = (
            db.query(Estabelecimento)
            .filter(Estabelecimento.id.in_(est_ids))
            .all()
        )
        est_map = {item.id: item.tipo for item in estabelecimentos}

    priority_labels = {
        "baixa": "Baixa",
        "media": "Média",
        "alta": "Alta",
        "urgente": "Urgente",
    }
    present_priorities = {item.prioridade for item in items if item.prioridade}

    return {
        "ordens": [
            {
                "value": ordem,
                "label": (
                    f"{ordem} — {group['titulo'][:50]} "
                    f"({group['total']} {'item' if group['total'] == 1 else 'itens'})"
                ),
            }
            for ordem, group in grouped_orders.items()
        ],
        "segmentos": sorted({item.categoria for item in items if item.categoria}),
        "prioridades": [
            {"value": value, "label": label}
            for value, label in priority_labels.items()
            if value in present_priorities
        ],
        "estabelecimentos": [
            {"value": str(est_id), "label": est_map[est_id]}
            for est_id in sorted(est_ids, key=lambda value: est_map.get(value, "").lower())
            if est_id in est_map
        ],
    }


@router.get("/itens")
def listar_itens_compra(
    ids: Optional[str] = Query(None),
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
    q = db.query(Suprimento).filter(Suprimento.status.in_(STATUSES_ABERTOS))

    if ids:
        id_list = [int(v) for v in ids.split(",") if v.strip().isdigit()]
        if id_list:
            q = q.filter(Suprimento.id.in_(id_list))

    if ordens:
        ordem_list = [value.strip() for value in ordens.split(",") if value.strip()]
        if ordem_list:
            sol_orders = [value for value in ordem_list if value.startswith("SOL")]
            q = q.filter(
                Suprimento.ordem_compra.in_(ordem_list)
                | Suprimento.id.in_([
                    int(value[3:]) for value in sol_orders
                    if value[3:].isdigit()
                ])
            )

    if busca:
        b = f"%{busca}%"
        q = q.filter(
            Suprimento.titulo.ilike(b)
            | Suprimento.item_nome.ilike(b)
            | Suprimento.categoria.ilike(b)
            | Suprimento.solicitante.ilike(b)
            | Suprimento.ordem_compra.ilike(b)
        )

    if segmento:
        q = q.filter(Suprimento.categoria.in_([v for v in segmento.split(",") if v]))

    if prioridade:
        q = q.filter(Suprimento.prioridade.in_([v for v in prioridade.split(",") if v]))

    if estabelecimento:
        est_ids = [int(v) for v in estabelecimento.split(",") if v.strip().isdigit()]
        if est_ids:
            q = q.filter(Suprimento.estabelecimento_id.in_(est_ids))

    _prio_compras = case(
        (Suprimento.prioridade == 'urgente', 0),
        (Suprimento.prioridade == 'alta', 1),
        (Suprimento.prioridade == 'media', 2),
        else_=3,
    )
    q = q.outerjoin(
        Estabelecimento,
        Suprimento.estabelecimento_id == Estabelecimento.id,
    )
    total = q.count()
    pages = max(1, math.ceil(total / limit))
    sortable = {
        "ordem": Suprimento.ordem_compra,
        "estabelecimento": func.lower(func.coalesce(Estabelecimento.tipo, "")),
        "item": func.lower(func.coalesce(Suprimento.item_nome, Suprimento.titulo, "")),
        "segmento": func.lower(func.coalesce(Suprimento.categoria, "")),
        "prioridade": _prio_compras,
    }
    if sort_by in sortable:
        sort_column = sortable[sort_by]
        ordering = sort_column.desc() if sort_dir == "desc" else sort_column.asc()
        order_by = [ordering, Suprimento.id.asc()]
    else:
        order_by = [
            Suprimento.emergencia.desc(),
            func.lower(func.coalesce(Estabelecimento.tipo, "")).asc(),
            _prio_compras,
            Suprimento.created_at.asc(),
        ]
    items = (
        q.order_by(*order_by)
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
                "ordem_compra": i.ordem_compra or f"SOL{i.id:04d}",
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
    valor_compra: Optional[float] = Field(default=None, gt=0)
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

    total_estimado = sum(
        i.valor_compra if i.valor_compra is not None else (i.valor_estimado or 0)
        for i in data.comprados
    ) or None

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
