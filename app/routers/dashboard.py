from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.database import get_db
from app.models.suprimento import Suprimento
from app.models.estabelecimento import Estabelecimento
from app.models.segmento import Segmento
from app.models.unidade import Unidade
from app.auth import get_viewer, require_admin

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _=Depends(get_viewer)):
    now_local = datetime.now(ZoneInfo("America/Sao_Paulo"))
    month_start_local = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if month_start_local.month == 12:
        next_month_local = month_start_local.replace(
            year=month_start_local.year + 1,
            month=1,
        )
    else:
        next_month_local = month_start_local.replace(month=month_start_local.month + 1)
    month_start = month_start_local.astimezone(timezone.utc).replace(tzinfo=None)
    next_month = next_month_local.astimezone(timezone.utc).replace(tzinfo=None)
    month_filter = (
        Suprimento.created_at >= month_start,
        Suprimento.created_at < next_month,
    )

    total = db.query(func.count(Suprimento.id)).filter(*month_filter).scalar()
    por_status = dict(
        db.query(Suprimento.status, func.count(Suprimento.id))
        .filter(*month_filter)
        .group_by(Suprimento.status)
        .all()
    )
    por_prioridade = dict(
        db.query(Suprimento.prioridade, func.count(Suprimento.id))
        .filter(*month_filter)
        .group_by(Suprimento.prioridade)
        .all()
    )
    valor_total = (
        db.query(func.sum(Suprimento.valor_estimado))
        .filter(*month_filter)
        .scalar()
        or 0
    )

    importantes = (
        db.query(Suprimento)
        .filter(*month_filter)
        .filter(Suprimento.status == "pendente")
        .filter(
            or_(
                Suprimento.emergencia == 1,
                Suprimento.prioridade == "urgente",
            )
        )
        .order_by(Suprimento.created_at.desc())
        .limit(5)
        .all()
    )

    month_items = (
        db.query(Suprimento)
        .filter(*month_filter)
        .order_by(Suprimento.created_at.desc())
        .limit(1000)
        .all()
    )
    establishment_ids = {
        item.estabelecimento_id
        for item in (importantes + month_items)
        if item.estabelecimento_id
    }
    establishment_map = {}
    if establishment_ids:
        establishments = (
            db.query(Estabelecimento)
            .filter(Estabelecimento.id.in_(establishment_ids))
            .all()
        )
        establishment_map = {item.id: item.tipo for item in establishments}

    if importantes:
        preview_type = "emergencias"
        preview = [
            {
                "id": item.id,
                "item": item.item_nome or item.titulo,
                "estabelecimento": establishment_map.get(item.estabelecimento_id) or "—",
                "solicitante": item.solicitante,
                "data_solicitacao": item.created_at.isoformat() if item.created_at else None,
                "data_conclusao_necessaria": item.prazo_emergencia or item.data_necessidade,
            }
            for item in importantes
        ]
    else:
        preview_type = "ordens_recentes"
        grouped_orders = {}
        for item in month_items:
            order_code = item.ordem_compra or f"SOL{item.id:04d}"
            if order_code not in grouped_orders:
                if len(grouped_orders) >= 5:
                    continue
                grouped_orders[order_code] = {
                    "id": item.id,
                    "ordem": order_code,
                    "estabelecimentos": [],
                    "solicitantes": [],
                    "data_solicitacao": item.created_at.isoformat() if item.created_at else None,
                }
            group = grouped_orders.get(order_code)
            if not group:
                continue
            establishment = establishment_map.get(item.estabelecimento_id)
            if establishment and establishment not in group["estabelecimentos"]:
                group["estabelecimentos"].append(establishment)
            if item.solicitante and item.solicitante not in group["solicitantes"]:
                group["solicitantes"].append(item.solicitante)
        preview = list(grouped_orders.values())

    return {
        "total": total,
        "por_status": por_status,
        "por_prioridade": por_prioridade,
        "valor_total_estimado": round(valor_total, 2),
        "mes_referencia": month_start_local.strftime("%Y-%m"),
        "preview_tipo": preview_type,
        "preview": preview,
    }


@router.get("/segmentos")
def segmentos(db: Session = Depends(get_db), _=Depends(get_viewer)):
    from_suprimentos = {r[0] for r in db.query(Suprimento.categoria).distinct().all() if r[0]}
    from_segmentos = {r[0] for r in db.query(Segmento.nome).filter(Segmento.ativo == True).all()}
    return sorted(from_suprimentos | from_segmentos)


class SegmentoCreate(BaseModel):
    nome: str


@router.get("/segmentos/list")
def listar_segmentos(db: Session = Depends(get_db), _=Depends(get_viewer)):
    rows = db.query(Segmento).filter(Segmento.ativo == True).order_by(Segmento.nome).all()
    return [{"id": r.id, "nome": r.nome} for r in rows]


@router.post("/segmentos", status_code=201)
def criar_segmento(data: SegmentoCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    nome = data.nome.strip()
    if not nome:
        raise HTTPException(400, "Informe o nome do segmento")
    if db.query(Segmento).filter(Segmento.nome.ilike(nome), Segmento.ativo == True).first():
        raise HTTPException(400, "Segmento já cadastrado")
    seg = Segmento(nome=nome)
    db.add(seg)
    db.commit()
    db.refresh(seg)
    return {"id": seg.id, "nome": seg.nome}


@router.delete("/segmentos/{id}", status_code=204)
def remover_segmento(id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    seg = db.query(Segmento).filter(Segmento.id == id).first()
    if not seg:
        raise HTTPException(404, "Segmento não encontrado")
    seg.ativo = False
    db.commit()


class UnidadeCreate(BaseModel):
    sigla: str
    nome: str


@router.get("/unidades/list")
def listar_unidades(db: Session = Depends(get_db), _=Depends(get_viewer)):
    rows = db.query(Unidade).filter(Unidade.ativo == True).order_by(Unidade.nome).all()
    return [{"id": r.id, "sigla": r.sigla, "nome": r.nome} for r in rows]


@router.post("/unidades", status_code=201)
def criar_unidade(data: UnidadeCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    sigla = data.sigla.strip()
    nome = data.nome.strip()
    if not sigla or not nome:
        raise HTTPException(400, "Informe sigla e nome")
    if db.query(Unidade).filter(Unidade.sigla == sigla, Unidade.ativo == True).first():
        raise HTTPException(400, "Sigla já cadastrada")
    u = Unidade(sigla=sigla, nome=nome)
    db.add(u)
    db.commit()
    db.refresh(u)
    return {"id": u.id, "sigla": u.sigla, "nome": u.nome}


@router.delete("/unidades/{id}", status_code=204)
def remover_unidade(id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    u = db.query(Unidade).filter(Unidade.id == id).first()
    if not u:
        raise HTTPException(404, "Unidade não encontrada")
    u.ativo = False
    db.commit()
