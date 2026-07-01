import calendar
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_viewer
from app.database import get_db
from app.models.compra_log import CompraLog
from app.models.estabelecimento import Estabelecimento
from app.models.suprimento import Suprimento

router = APIRouter(prefix="/api/kpis-negocio", tags=["kpis_negocio"])

STATUS_ABERTO = ["pendente", "aprovado", "em_andamento"]
STATUS_CONCLUIDO = ["concluido", "entregue"]


def _delta(current, previous):
    if previous is None or previous == 0:
        return None
    return round((current - previous) / previous * 100, 1)


def _avg_cycle(rows):
    vals = [
        (r.entregue_em - r.created_at).total_seconds() / 86400
        for r in rows
        if r.entregue_em and r.created_at and r.entregue_em >= r.created_at
    ]
    return round(sum(vals) / len(vals), 1) if vals else None


def _economia_sum(rows):
    total = 0.0
    for r in rows:
        base = r.teto_gasto or r.valor_estimado
        if base and r.valor_compra and base > r.valor_compra:
            total += base - r.valor_compra
    return round(total, 2)


@router.get("")
def kpis_negocio(
    dias: int = Query(90, ge=7, le=730),
    db: Session = Depends(get_db),
    _=Depends(get_viewer),
):
    now = datetime.utcnow()
    ini = now - timedelta(days=dias)
    ini_prev = now - timedelta(days=dias * 2)

    # ── KPI Cards ──────────────────────────────────────────────────────

    abertas = db.query(func.count(Suprimento.id)).filter(
        Suprimento.status.in_(STATUS_ABERTO)
    ).scalar() or 0

    em_andamento = db.query(func.count(Suprimento.id)).filter(
        Suprimento.status == "em_andamento"
    ).scalar() or 0

    concluidas = db.query(func.count(Suprimento.id)).filter(
        Suprimento.status.in_(STATUS_CONCLUIDO),
        Suprimento.updated_at >= ini,
    ).scalar() or 0
    concluidas_prev = db.query(func.count(Suprimento.id)).filter(
        Suprimento.status.in_(STATUS_CONCLUIDO),
        Suprimento.updated_at >= ini_prev,
        Suprimento.updated_at < ini,
    ).scalar() or 0

    total_periodo = db.query(func.count(Suprimento.id)).filter(
        Suprimento.created_at >= ini
    ).scalar() or 0
    total_prev = db.query(func.count(Suprimento.id)).filter(
        Suprimento.created_at >= ini_prev,
        Suprimento.created_at < ini,
    ).scalar() or 0

    taxa = round(concluidas / total_periodo * 100, 1) if total_periodo > 0 else 0.0
    taxa_prev = round(concluidas_prev / total_prev * 100, 1) if total_prev > 0 else 0.0

    tempo_rows = db.query(Suprimento).filter(
        Suprimento.status.in_(STATUS_CONCLUIDO),
        Suprimento.entregue_em.isnot(None),
        Suprimento.updated_at >= ini,
    ).all()
    tempo_rows_prev = db.query(Suprimento).filter(
        Suprimento.status.in_(STATUS_CONCLUIDO),
        Suprimento.entregue_em.isnot(None),
        Suprimento.updated_at >= ini_prev,
        Suprimento.updated_at < ini,
    ).all()
    tempo_medio = _avg_cycle(tempo_rows)
    tempo_medio_prev = _avg_cycle(tempo_rows_prev)

    valor_comprado = float(db.query(func.sum(Suprimento.valor_compra)).filter(
        Suprimento.status.in_(STATUS_CONCLUIDO),
        Suprimento.valor_compra.isnot(None),
        Suprimento.updated_at >= ini,
    ).scalar() or 0)
    valor_comprado_prev = float(db.query(func.sum(Suprimento.valor_compra)).filter(
        Suprimento.status.in_(STATUS_CONCLUIDO),
        Suprimento.valor_compra.isnot(None),
        Suprimento.updated_at >= ini_prev,
        Suprimento.updated_at < ini,
    ).scalar() or 0)

    econ_rows = db.query(Suprimento).filter(
        Suprimento.status.in_(STATUS_CONCLUIDO),
        Suprimento.valor_compra.isnot(None),
        Suprimento.updated_at >= ini,
    ).all()
    econ_rows_prev = db.query(Suprimento).filter(
        Suprimento.status.in_(STATUS_CONCLUIDO),
        Suprimento.valor_compra.isnot(None),
        Suprimento.updated_at >= ini_prev,
        Suprimento.updated_at < ini,
    ).all()
    economia = _economia_sum(econ_rows)
    economia_prev = _economia_sum(econ_rows_prev)

    criticas = db.query(func.count(Suprimento.id)).filter(
        Suprimento.status.in_(["pendente", "aprovado"]),
        (Suprimento.prioridade == "urgente") | (Suprimento.emergencia == 1),
    ).scalar() or 0
    criticas_prev = db.query(func.count(Suprimento.id)).filter(
        Suprimento.status.in_(["pendente", "aprovado"]),
        (Suprimento.prioridade == "urgente") | (Suprimento.emergencia == 1),
        Suprimento.created_at >= ini_prev,
        Suprimento.created_at < ini,
    ).scalar() or 0

    # ── Sparklines (últimas 8 semanas) ────────────────────────────────

    spark_abertas, spark_concluidas, spark_valor, spark_tempo = [], [], [], []
    for i in range(7, -1, -1):
        w_end = now - timedelta(weeks=i)
        w_start = now - timedelta(weeks=i + 1)

        spark_abertas.append(
            db.query(func.count(Suprimento.id)).filter(
                Suprimento.created_at >= w_start,
                Suprimento.created_at < w_end,
            ).scalar() or 0
        )
        spark_concluidas.append(
            db.query(func.count(Suprimento.id)).filter(
                Suprimento.status.in_(STATUS_CONCLUIDO),
                Suprimento.updated_at >= w_start,
                Suprimento.updated_at < w_end,
            ).scalar() or 0
        )
        spark_valor.append(
            float(db.query(func.sum(Suprimento.valor_compra)).filter(
                Suprimento.status.in_(STATUS_CONCLUIDO),
                Suprimento.valor_compra.isnot(None),
                Suprimento.updated_at >= w_start,
                Suprimento.updated_at < w_end,
            ).scalar() or 0)
        )
        w_rows = db.query(Suprimento).filter(
            Suprimento.status.in_(STATUS_CONCLUIDO),
            Suprimento.entregue_em.isnot(None),
            Suprimento.updated_at >= w_start,
            Suprimento.updated_at < w_end,
        ).all()
        spark_tempo.append(_avg_cycle(w_rows))

    # ── Funil / Status ─────────────────────────────────────────────────

    status_counts = dict(
        db.query(Suprimento.status, func.count(Suprimento.id))
        .group_by(Suprimento.status)
        .all()
    )
    funil = {
        "solicitacoes": sum(status_counts.get(s, 0) for s in ["pendente", "aprovado", "em_andamento", "entregue", "concluido", "cancelado"]),
        "aprovadas":    sum(status_counts.get(s, 0) for s in ["aprovado", "em_andamento", "entregue", "concluido"]),
        "compradas":    sum(status_counts.get(s, 0) for s in ["em_andamento", "entregue", "concluido"]),
        "recebidas":    sum(status_counts.get(s, 0) for s in ["entregue", "concluido"]),
    }

    # ── Compradores ranking ────────────────────────────────────────────

    comp_rows = (
        db.query(CompraLog.usuario, func.count(CompraLog.id).label("total"))
        .filter(CompraLog.data_hora >= ini)
        .group_by(CompraLog.usuario)
        .order_by(func.count(CompraLog.id).desc())
        .limit(5)
        .all()
    )
    compradores = [{"nome": r.usuario, "compras": r.total} for r in comp_rows]

    # ── Responsáveis mais ativos ───────────────────────────────────────

    resp_rows = (
        db.query(Suprimento.solicitante_responsavel, func.count(Suprimento.id).label("total"))
        .filter(
            Suprimento.created_at >= ini,
            Suprimento.solicitante_responsavel.isnot(None),
            Suprimento.solicitante_responsavel != "",
        )
        .group_by(Suprimento.solicitante_responsavel)
        .order_by(func.count(Suprimento.id).desc())
        .limit(5)
        .all()
    )
    responsaveis = [{"nome": r.solicitante_responsavel, "total": r.total} for r in resp_rows]

    # ── Categorias mais solicitadas ────────────────────────────────────

    cat_rows = (
        db.query(Suprimento.categoria, func.count(Suprimento.id).label("total"))
        .filter(Suprimento.created_at >= ini, Suprimento.categoria.isnot(None))
        .group_by(Suprimento.categoria)
        .order_by(func.count(Suprimento.id).desc())
        .limit(6)
        .all()
    )
    categorias = [{"nome": r.categoria, "total": r.total} for r in cat_rows]

    # ── Estabelecimentos ───────────────────────────────────────────────

    est_rows = (
        db.query(
            Suprimento.estabelecimento_id,
            func.count(Suprimento.id).label("total"),
            func.sum(
                func.coalesce(Suprimento.valor_compra, Suprimento.valor_estimado, 0)
            ).label("valor"),
        )
        .filter(Suprimento.created_at >= ini, Suprimento.estabelecimento_id.isnot(None))
        .group_by(Suprimento.estabelecimento_id)
        .order_by(func.count(Suprimento.id).desc())
        .limit(6)
        .all()
    )
    est_ids = [r.estabelecimento_id for r in est_rows]
    est_map = {}
    if est_ids:
        ests = db.query(Estabelecimento).filter(Estabelecimento.id.in_(est_ids)).all()
        est_map = {e.id: e.tipo for e in ests}

    estabelecimentos = [
        {
            "nome": est_map.get(r.estabelecimento_id, f"Est. {r.estabelecimento_id}"),
            "total": r.total,
            "valor": round(float(r.valor or 0), 2),
        }
        for r in est_rows
    ]

    # ── Solicitado × Comprado (últimos 6 meses) ────────────────────────

    meses = []
    for i in range(5, -1, -1):
        m_month = now.month - i
        m_year = now.year
        while m_month <= 0:
            m_month += 12
            m_year -= 1
        last_day = calendar.monthrange(m_year, m_month)[1]
        m_start = datetime(m_year, m_month, 1)
        m_end = datetime(m_year, m_month, last_day, 23, 59, 59)

        sol = float(
            db.query(
                func.sum(func.coalesce(Suprimento.teto_gasto, Suprimento.valor_estimado, 0))
            ).filter(
                Suprimento.created_at >= m_start,
                Suprimento.created_at <= m_end,
            ).scalar() or 0
        )
        comp = float(
            db.query(func.sum(Suprimento.valor_compra)).filter(
                Suprimento.status.in_(STATUS_CONCLUIDO),
                Suprimento.valor_compra.isnot(None),
                Suprimento.updated_at >= m_start,
                Suprimento.updated_at <= m_end,
            ).scalar() or 0
        )
        meses.append({
            "label": m_start.strftime("%b/%y"),
            "solicitado": round(sol, 2),
            "comprado": round(comp, 2),
        })

    return {
        "periodo_dias": dias,
        "kpis": {
            "abertas":        {"valor": abertas,        "delta": None,                                   "invert": False},
            "em_andamento":   {"valor": em_andamento,   "delta": None,                                   "invert": False},
            "concluidas":     {"valor": concluidas,     "delta": _delta(concluidas, concluidas_prev),    "invert": False},
            "taxa_conclusao": {"valor": taxa,            "delta": _delta(taxa, taxa_prev),               "invert": False},
            "tempo_medio":    {"valor": tempo_medio,     "delta": _delta(tempo_medio, tempo_medio_prev), "invert": True},
            "valor_comprado": {"valor": valor_comprado,  "delta": _delta(valor_comprado, valor_comprado_prev), "invert": False},
            "economia":       {"valor": economia,        "delta": _delta(economia, economia_prev),       "invert": False},
            "criticas":       {"valor": criticas,        "delta": _delta(criticas, criticas_prev),       "invert": True},
        },
        "sparklines": {
            "abertas":    spark_abertas,
            "concluidas": spark_concluidas,
            "valor":      spark_valor,
            "tempo":      spark_tempo,
        },
        "status_counts": status_counts,
        "funil": funil,
        "compradores": compradores,
        "responsaveis": responsaveis,
        "categorias": categorias,
        "estabelecimentos": estabelecimentos,
        "solicitado_comprado": meses,
    }
