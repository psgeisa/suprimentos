from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.access_log import AccessLog
from app.auth import require_admin

router = APIRouter(prefix="/api/acessos", tags=["acessos"])


@router.get("/stats")
def stats(db: Session = Depends(get_db), _=Depends(require_admin)):
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = today_start.replace(day=1)

    total_acessos = db.query(func.count(AccessLog.id)).scalar() or 0
    visitantes_unicos = db.query(func.count(func.distinct(AccessLog.visitor_id))).scalar() or 0
    acessos_hoje = db.query(func.count(AccessLog.id)).filter(AccessLog.data_hora >= today_start).scalar() or 0
    visitantes_hoje = (
        db.query(func.count(func.distinct(AccessLog.visitor_id)))
        .filter(AccessLog.data_hora >= today_start)
        .scalar()
        or 0
    )
    acessos_mes = db.query(func.count(AccessLog.id)).filter(AccessLog.data_hora >= month_start).scalar() or 0
    visitantes_identificados = (
        db.query(func.count(func.distinct(AccessLog.usuario_id)))
        .filter(AccessLog.usuario_id.isnot(None))
        .scalar()
        or 0
    )

    return {
        "total_acessos": total_acessos,
        "visitantes_unicos": visitantes_unicos,
        "acessos_hoje": acessos_hoje,
        "visitantes_hoje": visitantes_hoje,
        "acessos_mes": acessos_mes,
        "visitantes_identificados": visitantes_identificados,
    }


@router.get("")
def listar(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    query = db.query(AccessLog).order_by(AccessLog.data_hora.desc())
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": r.id,
                "data_hora": (r.data_hora.isoformat() + "Z") if r.data_hora else None,
                "visitor_id": r.visitor_id,
                "ip": r.ip,
                "user_agent": r.user_agent,
                "usuario_id": r.usuario_id,
                "usuario_nome": r.usuario_nome,
            }
            for r in rows
        ],
    }
