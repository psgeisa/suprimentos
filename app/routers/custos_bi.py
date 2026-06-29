import traceback
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_viewer
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
    _=Depends(get_viewer),
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


def _calcular_dados(busca, data_inicio, data_fim, segmento, estabelecimento, time_val, db):
    base_q = db.query(Suprimento).filter(Suprimento.status.in_(STATUSES_CUSTO))
    base_q = _apply_filters(base_q, busca, data_inicio, data_fim, segmento, estabelecimento, time_val, db)
    items = base_q.all()

    def custo_item(i):
        return (i.valor_compra or 0) if i.valor_compra is not None else (i.valor_estimado or 0)

    # por_mes
    por_mes = {}
    for i in items:
        if not i.created_at:
            continue
        mes = i.created_at.strftime("%Y-%m")
        por_mes[mes] = por_mes.get(mes, 0) + custo_item(i)
    por_mes_list = [{"mes": m, "custo": round(v, 2)} for m, v in sorted(por_mes.items())]

    # por_dia_semana
    dia_soma = {}
    dia_count = {}
    for i in items:
        if not i.created_at:
            continue
        dia = i.created_at.isoweekday() % 7
        dia_soma[dia] = dia_soma.get(dia, 0) + custo_item(i)
        dia_count[dia] = dia_count.get(dia, 0) + 1
    por_dia = [
        {"dia": d, "label": _DIAS[d], "media": round(dia_soma.get(d, 0) / max(dia_count.get(d, 1), 1), 2)}
        for d in range(7)
    ]

    # por_segmento_mes
    seg_mes = {}
    for i in items:
        if not i.created_at or not i.categoria:
            continue
        key = (i.created_at.strftime("%Y-%m"), i.categoria)
        seg_mes[key] = seg_mes.get(key, 0) + custo_item(i)
    por_segmento_mes = [
        {"mes": k[0], "segmento": k[1], "custo": round(v, 2)}
        for k, v in sorted(seg_mes.items())
    ]

    # por_estabelecimento_mes
    est_ids_found = {i.estabelecimento_id for i in items if i.estabelecimento_id}
    est_map = {}
    if est_ids_found:
        ests = db.query(Estabelecimento).filter(Estabelecimento.id.in_(est_ids_found)).all()
        est_map = {e.id: e.tipo for e in ests}
    est_mes = {}
    for i in items:
        if not i.created_at or not i.estabelecimento_id:
            continue
        label = est_map.get(i.estabelecimento_id, "#{0}".format(i.estabelecimento_id))
        key = (i.created_at.strftime("%Y-%m"), label)
        est_mes[key] = est_mes.get(key, 0) + custo_item(i)
    por_estabelecimento_mes = [
        {"mes": k[0], "estabelecimento": k[1], "custo": round(v, 2)}
        for k, v in sorted(est_mes.items())
    ]

    # por_time
    user_time_map = {
        u.nome: (u.time or "Sem time")
        for u in db.query(User).all()
    }
    time_tot = {}
    for i in items:
        t = user_time_map.get(i.solicitante or "", "Sem time")
        time_tot[t] = time_tot.get(t, 0) + custo_item(i)
    por_time = [{"time": k, "custo": round(v, 2)} for k, v in sorted(time_tot.items())]

    # por_responsavel
    resp_tot = {}
    for i in items:
        r = (i.solicitante_responsavel or "Não informado").strip() or "Não informado"
        resp_tot[r] = resp_tot.get(r, 0) + custo_item(i)
    por_responsavel = [{"responsavel": k, "custo": round(v, 2)} for k, v in sorted(resp_tot.items())]

    # por_solicitante
    sol_tot = {}
    for i in items:
        s = (i.solicitante or "Não informado").strip() or "Não informado"
        sol_tot[s] = sol_tot.get(s, 0) + custo_item(i)
    por_solicitante = [{"solicitante": k, "custo": round(v, 2)} for k, v in sorted(sol_tot.items())]

    # comparativo_mes
    comp_mes = {}
    for i in items:
        if not i.created_at:
            continue
        mes = i.created_at.strftime("%Y-%m")
        entry = comp_mes.setdefault(mes, {"estimado": 0, "teto": 0, "real": 0})
        entry["estimado"] += i.valor_estimado or 0
        teto = i.teto_gasto if i.teto_gasto is not None else (i.valor_estimado or 0) * 1.2
        entry["teto"] += teto
        entry["real"] += i.valor_compra or 0
    comparativo = [
        {
            "mes": m,
            "estimado": round(v["estimado"], 2),
            "teto": round(v["teto"], 2),
            "real": round(v["real"], 2),
        }
        for m, v in sorted(comp_mes.items())
    ]

    # projecao_futuro
    proj_q = db.query(Suprimento).filter(Suprimento.status.in_(STATUSES_PROJECAO))
    proj_q = _apply_filters(proj_q, busca, data_inicio, data_fim, segmento, estabelecimento, time_val, db)
    proj_items = proj_q.all()
    proj_est_ids = {i.estabelecimento_id for i in proj_items if i.estabelecimento_id}
    extra_ids = proj_est_ids - est_ids_found
    if extra_ids:
        extra = db.query(Estabelecimento).filter(Estabelecimento.id.in_(extra_ids)).all()
        est_map.update({e.id: e.tipo for e in extra})
    proj_acc = {}
    for i in proj_items:
        label = est_map.get(i.estabelecimento_id or 0, "Não definido")
        entry = proj_acc.setdefault(label, {"estimado": 0, "teto": 0})
        entry["estimado"] += i.valor_estimado or 0
        teto = i.teto_gasto if i.teto_gasto is not None else (i.valor_estimado or 0) * 1.2
        entry["teto"] += teto
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


@router.get("/agenda")
def agenda_financeira(
    busca: Optional[str] = Query(None),
    data_inicio: Optional[str] = Query(None),
    data_fim: Optional[str] = Query(None),
    segmento: Optional[str] = Query(None),
    estabelecimento: Optional[str] = Query(None),
    time_val: Optional[str] = Query(None, alias="time"),
    db: Session = Depends(get_db),
    _=Depends(get_viewer),
):
    try:
        all_statuses = ["pendente", "aprovado", "em_andamento", "entregue", "concluido"]
        q = db.query(Suprimento).filter(Suprimento.status.in_(all_statuses))
        q = _apply_filters(q, busca, data_inicio, data_fim, segmento, estabelecimento, time_val, db)
        items = q.order_by(Suprimento.created_at).all()

        now = datetime.utcnow()
        result = []

        for s in items:
            if not s.created_at:
                continue

            data_ini = s.created_at.strftime("%Y-%m-%d")

            # Data de pagamento/prazo: usa data_necessidade ou fallback +30 dias
            data_pag = s.data_necessidade  # já é string "YYYY-MM-DD" ou None
            if not data_pag:
                data_pag = (s.created_at + timedelta(days=30)).strftime("%Y-%m-%d")

            # Data de entrega real, se existir
            data_ent = (
                s.entregue_em.strftime("%Y-%m-%d") if s.entregue_em else data_pag
            )

            # Mapeamento de status
            if s.status in ("entregue", "concluido"):
                agenda_status = "concluido"
            elif s.status == "em_andamento":
                agenda_status = "em_andamento"
            else:  # pendente, aprovado
                agenda_status = "programado"

            # Detecta atraso: prazo no passado e não concluído
            if agenda_status != "concluido" and s.data_necessidade:
                try:
                    if datetime.strptime(s.data_necessidade, "%Y-%m-%d") < now:
                        agenda_status = "atrasado"
                except Exception:
                    pass

            # Lead time em dias
            try:
                lead = max((datetime.strptime(data_pag, "%Y-%m-%d") - s.created_at).days, 1)
            except Exception:
                lead = 0

            result.append({
                "id": s.id,
                "nome": s.titulo,
                "categoria": s.categoria or "—",
                "fornecedor": s.fornecedor_sugerido or "—",
                "centroCusto": s.departamento or "—",
                "responsavel": (s.solicitante_responsavel or s.solicitante or "—"),
                "status": agenda_status,
                "valorPrevisto": round(s.valor_estimado or 0, 2),
                "valorRealizado": round(s.valor_compra or 0, 2),
                "dataInicio": data_ini,
                "dataPagamento": data_pag,
                "dataEntrega": data_ent,
                "leadTime": lead,
                "obs": s.observacoes or "",
            })

        return result
    except Exception:
        return JSONResponse(status_code=500, content={"detail": traceback.format_exc()})


@router.get("/dados")
def dados_custos_bi(
    busca: Optional[str] = Query(None),
    data_inicio: Optional[str] = Query(None),
    data_fim: Optional[str] = Query(None),
    segmento: Optional[str] = Query(None),
    estabelecimento: Optional[str] = Query(None),
    time_val: Optional[str] = Query(None, alias="time"),
    db: Session = Depends(get_db),
    _=Depends(get_viewer),
):
    try:
        return _calcular_dados(busca, data_inicio, data_fim, segmento, estabelecimento, time_val, db)
    except Exception:
        return JSONResponse(status_code=500, content={"detail": traceback.format_exc()})
