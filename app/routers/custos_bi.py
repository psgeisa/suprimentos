from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, case, extract
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.estabelecimento import Estabelecimento
from app.models.suprimento import Suprimento
from app.models.user import User

router = APIRouter(prefix="/api/custos-bi", tags=["custos_bi"])

STATUSES_CUSTO = ["aprovado", "em_andamento", "entregue", "concluido"]
STATUSES_PROJECAO = ["pendente", "aprovado"]

_DIAS = ["Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"]


def _custo():
    return func.coalesce(Suprimento.valor_compra, Suprimento.valor_estimado, 0.0)


def _apply_filters(q, busca, data_inicio, data_fim, segmento, estabelecimento, time_val, db):
    if busca:
        t = f"%{busca}%"
        q = q.filter(
            Suprimento.titulo.ilike(t)
            | Suprimento.item_nome.ilike(t)
            | Suprimento.categoria.ilike(t)
            | Suprimento.solicitante.ilike(t)
            | Suprimento.solicitante_responsavel.ilike(t)
        )
    if data_inicio:
        q = q.filter(Suprimento.created_at >= data_inicio)
    if data_fim:
        q = q.filter(Suprimento.created_at <= f"{data_fim}T23:59:59")
    if segmento:
        segs = [s for s in segmento.split(",") if s.strip()]
        if segs:
            q = q.filter(Suprimento.categoria.in_(segs))
    if estabelecimento:
        est_ids = [int(e) for e in estabelecimento.split(",") if e.strip().isdigit()]
        if est_ids:
            q = q.filter(Suprimento.estabelecimento_id.in_(est_ids))
    if time_val:
        times = [t.strip() for t in time_val.split(",") if t.strip()]
        if times:
            nomes = db.query(User.nome).filter(User.time.in_(times)).subquery()
            q = q.filter(Suprimento.solicitante.in_(nomes))
    return q


@router.get("/filtros")
def filtros_custos_bi(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    items = (
        db.query(Suprimento)
        .filter(Suprimento.status.in_(STATUSES_CUSTO + STATUSES_PROJECAO))
        .all()
    )
    est_ids = {i.estabelecimento_id for i in items if i.estabelecimento_id}
    est_map = {}
    if est_ids:
        ests = db.query(Estabelecimento).filter(Estabelecimento.id.in_(est_ids)).all()
        est_map = {e.id: e.tipo for e in ests}

    times = sorted({u.time for u in db.query(User).all() if u.time})
    return {
        "segmentos": sorted({i.categoria for i in items if i.categoria}),
        "estabelecimentos": [
            {"value": str(eid), "label": est_map[eid]}
            for eid in sorted(est_ids, key=lambda x: est_map.get(x, ""))
            if eid in est_map
        ],
        "times": times,
    }


@router.get("/dados")
def dados_custos_bi(
    busca: Optional[str] = Query(None),
    data_inicio: Optional[str] = Query(None),
    data_fim: Optional[str] = Query(None),
    segmento: Optional[str] = Query(None),
    estabelecimento: Optional[str] = Query(None),
    time_val: Optional[str] = Query(None, alias="time"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    base_q = db.query(Suprimento).filter(Suprimento.status.in_(STATUSES_CUSTO))
    base_q = _apply_filters(base_q, busca, data_inicio, data_fim, segmento, estabelecimento, time_val, db)

    # ── 1. Custo total por mês ────────────────────────────────────────────
    por_mes_rows = (
        db.query(
            func.to_char(Suprimento.created_at, "YYYY-MM").label("mes"),
            func.sum(_custo()).label("custo"),
        )
        .filter(Suprimento.status.in_(STATUSES_CUSTO))
        .filter(*(base_q.whereclause,) if base_q.whereclause is not None else ())
        .group_by("mes")
        .order_by("mes")
        .all()
    )

    # ── easier: pull items and aggregate in Python ─────────────────────────
    items = base_q.all()

    # custo efetivo por item
    def custo_item(i):
        return (i.valor_compra or 0) if i.valor_compra is not None else (i.valor_estimado or 0)

    # --- por_mes ---
    por_mes: dict[str, float] = {}
    for i in items:
        if not i.created_at:
            continue
        mes = i.created_at.strftime("%Y-%m")
        por_mes[mes] = por_mes.get(mes, 0) + custo_item(i)
    por_mes_list = [{"mes": m, "custo": round(v, 2)} for m, v in sorted(por_mes.items())]

    # --- por_dia_semana (0=domingo) ---
    dia_soma: dict[int, float] = {}
    dia_count: dict[int, int] = {}
    for i in items:
        if not i.created_at:
            continue
        # Python's weekday(): 0=Monday. isoweekday(): 1=Monday,7=Sunday
        # Convert to 0=Sunday: isoweekday() % 7
        dia = i.created_at.isoweekday() % 7
        dia_soma[dia] = dia_soma.get(dia, 0) + custo_item(i)
        dia_count[dia] = dia_count.get(dia, 0) + 1
    por_dia = [
        {"dia": d, "label": _DIAS[d], "media": round(dia_soma.get(d, 0) / max(dia_count.get(d, 1), 1), 2)}
        for d in range(7)
    ]

    # --- por_segmento_mes ---
    seg_mes: dict[tuple, float] = {}
    for i in items:
        if not i.created_at or not i.categoria:
            continue
        key = (i.created_at.strftime("%Y-%m"), i.categoria)
        seg_mes[key] = seg_mes.get(key, 0) + custo_item(i)
    por_segmento_mes = [
        {"mes": k[0], "segmento": k[1], "custo": round(v, 2)}
        for k, v in sorted(seg_mes.items())
    ]

    # --- por_estabelecimento_mes ---
    est_ids_found = {i.estabelecimento_id for i in items if i.estabelecimento_id}
    est_map: dict[int, str] = {}
    if est_ids_found:
        ests = db.query(Estabelecimento).filter(Estabelecimento.id.in_(est_ids_found)).all()
        est_map = {e.id: e.tipo for e in ests}
    est_mes: dict[tuple, float] = {}
    for i in items:
        if not i.created_at or not i.estabelecimento_id:
            continue
        label = est_map.get(i.estabelecimento_id, f"#{i.estabelecimento_id}")
        key = (i.created_at.strftime("%Y-%m"), label)
        est_mes[key] = est_mes.get(key, 0) + custo_item(i)
    por_estabelecimento_mes = [
        {"mes": k[0], "estabelecimento": k[1], "custo": round(v, 2)}
        for k, v in sorted(est_mes.items())
    ]

    # --- por_time ---
    user_time_map: dict[str, str] = {
        u.nome: (u.time or "Sem time")
        for u in db.query(User).all()
    }
    time_tot: dict[str, float] = {}
    for i in items:
        t = user_time_map.get(i.solicitante or "", "Sem time")
        time_tot[t] = time_tot.get(t, 0) + custo_item(i)
    por_time = [{"time": k, "custo": round(v, 2)} for k, v in sorted(time_tot.items())]

    # --- por_responsavel ---
    resp_tot: dict[str, float] = {}
    for i in items:
        r = (i.solicitante_responsavel or "Não informado").strip() or "Não informado"
        resp_tot[r] = resp_tot.get(r, 0) + custo_item(i)
    por_responsavel = [{"responsavel": k, "custo": round(v, 2)} for k, v in sorted(resp_tot.items())]

    # --- por_solicitante ---
    sol_tot: dict[str, float] = {}
    for i in items:
        s = (i.solicitante or "Não informado").strip() or "Não informado"
        sol_tot[s] = sol_tot.get(s, 0) + custo_item(i)
    por_solicitante = [{"solicitante": k, "custo": round(v, 2)} for k, v in sorted(sol_tot.items())]

    # --- comparativo_mes (estimado x teto x real) ---
    comp_mes: dict[str, dict] = {}
    for i in items:
        if not i.created_at:
            continue
        mes = i.created_at.strftime("%Y-%m")
        e = comp_mes.setdefault(mes, {"estimado": 0, "teto": 0, "real": 0})
        e["estimado"] += i.valor_estimado or 0
        teto = i.teto_gasto if i.teto_gasto is not None else (i.valor_estimado or 0) * 1.2
        e["teto"] += teto
        e["real"] += i.valor_compra or 0
    comparativo = [
        {
            "mes": m,
            "estimado": round(v["estimado"], 2),
            "teto": round(v["teto"], 2),
            "real": round(v["real"], 2),
        }
        for m, v in sorted(comp_mes.items())
    ]

    # --- projecao_futuro (pendente + aprovado, por estabelecimento) ---
    proj_q = db.query(Suprimento).filter(Suprimento.status.in_(STATUSES_PROJECAO))
    proj_q = _apply_filters(proj_q, busca, data_inicio, data_fim, segmento, estabelecimento, time_val, db)
    proj_items = proj_q.all()
    proj_est_ids = {i.estabelecimento_id for i in proj_items if i.estabelecimento_id}
    if proj_est_ids - est_ids_found:
        extra = db.query(Estabelecimento).filter(
            Estabelecimento.id.in_(proj_est_ids - est_ids_found)
        ).all()
        est_map.update({e.id: e.tipo for e in extra})

    proj_acc: dict[str, dict] = {}
    for i in proj_items:
        label = est_map.get(i.estabelecimento_id or 0, "Não definido")
        e = proj_acc.setdefault(label, {"estimado": 0, "teto": 0})
        e["estimado"] += i.valor_estimado or 0
        teto = i.teto_gasto if i.teto_gasto is not None else (i.valor_estimado or 0) * 1.2
        e["teto"] += teto
    projecao = [
        {
            "estabelecimento": k,
            "estimado": round(v["estimado"], 2),
            "teto": round(v["teto"], 2),
        }
        for k, v in sorted(proj_acc.items(), key=lambda x: x[1]["estimado"], reverse=True)
    ]

    return {
        "por_mes": por_mes_list,
        "por_dia_semana": por_dia,
        "por_segmento_mes": por_segmento_mes,
        "por_estabelecimento_mes": por_estabelecimento_mes,
        "por_time": por_time,
        "por_responsavel": por_responsavel,
        "por_solicitante": por_solicitante,
        "comparativo": comparativo,
        "projecao": projecao,
    }
