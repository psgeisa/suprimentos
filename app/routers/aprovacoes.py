import math
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.estabelecimento import Estabelecimento
from app.models.item_eliminado_log import ItemEliminadoLog
from app.models.suprimento import Suprimento

router = APIRouter(prefix="/api/aprovacoes", tags=["aprovacoes"])


@router.get("/filtros")
def listar_filtros(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Opções dos filtros de aprovação derivadas somente de solicitações pendentes."""
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
def listar_itens_aprovacao(
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
    q = db.query(Suprimento).filter(Suprimento.status == "pendente")

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

    _prio = case(
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
        "prioridade": _prio,
    }
    if sort_by in sortable:
        sort_column = sortable[sort_by]
        ordering = sort_column.desc() if sort_dir == "desc" else sort_column.asc()
        order_by = [ordering, Suprimento.id.asc()]
    else:
        order_by = [
            Suprimento.emergencia.desc(),
            func.lower(func.coalesce(Estabelecimento.tipo, "")).asc(),
            _prio,
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
        if i.teto_gasto is not None:
            teto_gasto = i.teto_gasto
        else:
            teto_gasto = (i.valor_estimado or 0) * 1.2
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
                "valor_compra": i.valor_compra,
                "teto_gasto": teto_gasto,
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


class AprovacaoMarcarRequest(BaseModel):
    aprovado: bool


@router.post("/{suprimento_id}/marcar")
def marcar_aprovado(
    suprimento_id: int,
    data: AprovacaoMarcarRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    item = db.query(Suprimento).filter(Suprimento.id == suprimento_id).first()
    if not item:
        raise HTTPException(404, "Suprimento não encontrado")
    if data.aprovado and item.status != "pendente":
        raise HTTPException(409, "Somente solicitações pendentes podem ser aprovadas")
    if not data.aprovado and item.status != "aprovado":
        raise HTTPException(409, "Somente itens aprovados podem voltar para pendente")
    item.status = "aprovado" if data.aprovado else "pendente"
    item.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "status": item.status}


class TetoGastoRequest(BaseModel):
    teto_gasto: Optional[float] = Field(default=None, gt=0)


@router.put("/{suprimento_id}/teto")
def salvar_teto_gasto(
    suprimento_id: int,
    data: TetoGastoRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    item = db.query(Suprimento).filter(Suprimento.id == suprimento_id).first()
    if not item:
        raise HTTPException(404, "Suprimento não encontrado")
    if item.status != "pendente":
        raise HTTPException(409, "O teto de gasto só pode ser editado em itens pendentes")
    item.teto_gasto = data.teto_gasto
    item.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "teto_gasto": item.teto_gasto}


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


class FinalizarAprovacaoItem(BaseModel):
    id: int
    teto_gasto: Optional[float] = Field(default=None, gt=0)


class FinalizarAprovacaoRequest(BaseModel):
    aprovados: List[FinalizarAprovacaoItem]


@router.post("/finalizar")
def finalizar_aprovacao(
    data: FinalizarAprovacaoRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not data.aprovados:
        return {"ok": True, "total_aprovados": 0}

    ids = [item.id for item in data.aprovados]
    teto_map = {item.id: item.teto_gasto for item in data.aprovados}
    rows = (
        db.query(Suprimento)
        .filter(
            Suprimento.id.in_(ids),
            Suprimento.status == "pendente",
        )
        .all()
    )
    now = datetime.utcnow()
    for row in rows:
        row.status = "aprovado"
        if teto_map.get(row.id) is not None:
            row.teto_gasto = teto_map[row.id]
        elif row.teto_gasto is None:
            row.teto_gasto = (row.valor_estimado or 0) * 1.2
        row.updated_at = now
    db.commit()

    return {"ok": True, "total_aprovados": len(rows)}
