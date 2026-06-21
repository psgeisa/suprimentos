from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.suprimento import Suprimento
from app.schemas.suprimento import SuprimentoOut
from app.auth import get_current_user

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _=Depends(get_current_user)):
    total = db.query(func.count(Suprimento.id)).scalar()
    por_status = dict(
        db.query(Suprimento.status, func.count(Suprimento.id))
        .group_by(Suprimento.status)
        .all()
    )
    por_prioridade = dict(
        db.query(Suprimento.prioridade, func.count(Suprimento.id))
        .group_by(Suprimento.prioridade)
        .all()
    )
    valor_total = db.query(func.sum(Suprimento.valor_estimado)).scalar() or 0
    recentes = (
        db.query(Suprimento).order_by(Suprimento.created_at.desc()).limit(5).all()
    )
    return {
        "total": total,
        "por_status": por_status,
        "por_prioridade": por_prioridade,
        "valor_total_estimado": round(valor_total, 2),
        "recentes": [SuprimentoOut.model_validate(r) for r in recentes],
    }


@router.get("/categorias")
def categorias(db: Session = Depends(get_db), _=Depends(get_current_user)):
    rows = db.query(Suprimento.categoria).distinct().all()
    return [r[0] for r in rows]
