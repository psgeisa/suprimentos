from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_viewer
from app.database import get_db
from app.models.access_log import AccessLog
from app.models.ia_sugestao_log import IaSugestaoLog
from app.models.suprimento import Suprimento
from app.models.user import User

router = APIRouter(prefix="/api/kpis-plataforma", tags=["kpis_plataforma"])


def _pct(num, den):
    return round(num / den * 100, 1) if den else 0


@router.get("")
def get_kpis_plataforma(db: Session = Depends(get_db), _=Depends(get_viewer)):
    now = datetime.now(timezone.utc)
    now_naive = datetime.utcnow()
    inicio = now - timedelta(days=90)
    inicio_naive = now_naive - timedelta(days=90)

    # ── IA Sugestão Logs ────────────────────────────────────────────────────
    logs = db.query(IaSugestaoLog).filter(IaSugestaoLog.data_hora >= inicio).all()
    total = len(logs)
    aprovados = sum(1 for l in logs if l.aprovacao_stakeholder is True)
    reprovados = sum(1 for l in logs if l.aprovacao_stakeholder is False)
    duplicidades_evitadas = aprovados  # cada aceitação evitou um cadastro duplicado

    taxa_aceitacao = _pct(aprovados, total)

    # Campos mais problemáticos (reprovações por tipo)
    tipo_counter = Counter(l.tipo for l in logs if l.aprovacao_stakeholder is False)
    total_rep = sum(tipo_counter.values()) or 1
    campos_problematicos = [
        {"campo": t, "pct": _pct(c, total_rep)}
        for t, c in tipo_counter.most_common(6)
    ]

    # Termos mais corrigidos (termo_stakeholder → termo_final, quando diferentes)
    correcoes: dict[tuple, int] = {}
    for l in logs:
        if (
            l.aprovacao_stakeholder is True
            and l.sugestao_ia
            and l.termo_stakeholder
            and l.sugestao_ia.strip().lower() != l.termo_stakeholder.strip().lower()
        ):
            key = (l.termo_stakeholder.strip(), l.sugestao_ia.strip())
            correcoes[key] = correcoes.get(key, 0) + 1
    termos_corrigidos = [
        {"de": k[0], "para": k[1], "qtd": v}
        for k, v in sorted(correcoes.items(), key=lambda x: -x[1])[:5]
    ]

    # Usuários que mais recusam (stakeholder_id com mais reprovações)
    rep_por_user: dict[int, int] = {}
    for l in logs:
        if l.aprovacao_stakeholder is False and l.stakeholder_id:
            rep_por_user[l.stakeholder_id] = rep_por_user.get(l.stakeholder_id, 0) + 1
    top_ids = sorted(rep_por_user, key=lambda x: -rep_por_user[x])[:5]
    usuarios_db = {u.id: u.nome for u in db.query(User).filter(User.id.in_(top_ids)).all()} if top_ids else {}
    usuarios_recusam = [
        {"nome": usuarios_db.get(uid, f"Usuário {uid}"), "qtd": rep_por_user[uid]}
        for uid in top_ids
    ]

    # Evolução mensal da taxa de aceitação (6 meses)
    evolucao_ia = []
    for m in range(5, -1, -1):
        d_ini = now - timedelta(days=30 * (m + 1))
        d_fim = now - timedelta(days=30 * m)
        lm = [l for l in db.query(IaSugestaoLog).filter(
            IaSugestaoLog.data_hora >= d_ini,
            IaSugestaoLog.data_hora < d_fim,
        ).all()]
        ap = sum(1 for l in lm if l.aprovacao_stakeholder is True)
        tot = len(lm)
        label = (now - timedelta(days=30 * m)).strftime("%b")
        evolucao_ia.append({"mes": label, "taxa": _pct(ap, tot), "total": tot, "aprovados": ap})

    # ── Segurança ──────────────────────────────────────────────────────────
    total_acessos = db.query(func.count(AccessLog.id)).scalar() or 0
    # Users ativos (distintos, últimos 30 dias)
    usuarios_ativos_mes = (
        db.query(func.count(func.distinct(AccessLog.usuario_id)))
        .filter(AccessLog.data_hora >= now_naive - timedelta(days=30))
        .scalar() or 0
    )
    usuarios_ativos_hoje = (
        db.query(func.count(func.distinct(AccessLog.usuario_id)))
        .filter(AccessLog.data_hora >= now_naive.replace(hour=0, minute=0, second=0))
        .scalar() or 0
    )

    # Acessos por dia da semana (heatmap simplificado)
    acessos_rows = db.query(AccessLog.data_hora).filter(
        AccessLog.data_hora >= inicio_naive
    ).all()
    dow_names = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]
    dow_count = Counter()
    hour_count = Counter()
    for (dt,) in acessos_rows:
        if dt:
            dow_count[dt.weekday()] += 1
            hour_count[dt.hour] += 1
    acessos_por_dia = [{"dia": dow_names[(i + 1) % 7], "qtd": dow_count.get(i, 0)} for i in range(7)]
    acessos_por_hora = [{"hora": f"{h:02d}h", "qtd": hour_count.get(h, 0)} for h in range(24)]

    # Rotas mais acessadas
    rotas_count = (
        db.query(AccessLog.path, func.count(AccessLog.id).label("qtd"))
        .filter(AccessLog.data_hora >= now_naive - timedelta(days=30))
        .group_by(AccessLog.path)
        .order_by(func.count(AccessLog.id).desc())
        .limit(6)
        .all()
    )
    rotas_top = [{"rota": r.path or "/", "qtd": r.qtd} for r in rotas_count]

    # Novos usuários (mês atual vs anterior)
    usuarios_novos_mes = (
        db.query(func.count(User.id))
        .filter(User.criado_em >= now_naive - timedelta(days=30))
        .scalar() or 0
    )

    # ── Utilização da Plataforma ───────────────────────────────────────────
    total_usuarios = db.query(func.count(User.id)).scalar() or 0

    # Funcionalidades mais utilizadas (by path prefix)
    func_map = {
        "/api/suprimentos": "Solicitações",
        "/api/compras": "Compras",
        "/api/dashboard": "Dashboard",
        "/api/itens": "Catálogo",
        "/api/kpis": "KPIs",
        "/api/aprovacoes": "Aprovações",
        "/api/entregas": "Entregas",
    }
    func_count = {v: 0 for v in func_map.values()}
    for r in rotas_top:
        for prefix, nome in func_map.items():
            if r["rota"].startswith(prefix):
                func_count[nome] = func_count.get(nome, 0) + r["qtd"]
    funcionalidades = sorted(
        [{"nome": k, "qtd": v} for k, v in func_count.items() if v > 0],
        key=lambda x: -x["qtd"]
    )

    # ── Fluxo ──────────────────────────────────────────────────────────────
    total_sol = db.query(func.count(Suprimento.id)).scalar() or 0
    com_item = total_sol  # sem relacionamento itens no modelo; assumir todos têm item
    enviados = db.query(func.count(Suprimento.id)).filter(
        Suprimento.status.in_(["aprovado", "em_andamento", "concluido", "entregue"])
    ).scalar() or 0
    aprovados_sol = db.query(func.count(Suprimento.id)).filter(
        Suprimento.status.in_(["em_andamento", "concluido", "entregue"])
    ).scalar() or 0
    concluidos = db.query(func.count(Suprimento.id)).filter(
        Suprimento.status.in_(["concluido", "entregue"])
    ).scalar() or 0
    fluxo = [
        {"etapa": "Criou solicitação", "qtd": total_sol},
        {"etapa": "Preencheu item", "qtd": com_item},
        {"etapa": "Enviou", "qtd": enviados},
        {"etapa": "Aprovado", "qtd": aprovados_sol},
        {"etapa": "Concluído", "qtd": concluidos},
    ]

    return {
        "qualidade_dados": {
            "taxa_aceitacao_ia": taxa_aceitacao,
            "total_interacoes": total,
            "aprovados": aprovados,
            "reprovados": reprovados,
            "duplicidades_evitadas": duplicidades_evitadas,
            "campos_problematicos": campos_problematicos,
            "termos_corrigidos": termos_corrigidos,
            "usuarios_recusam": usuarios_recusam,
            "evolucao_ia": evolucao_ia,
        },
        "seguranca": {
            "total_acessos": total_acessos,
            "rotas_top": rotas_top,
        },
        "utilizacao": {
            "total_usuarios": total_usuarios,
            "usuarios_ativos_hoje": usuarios_ativos_hoje,
            "usuarios_ativos_mes": usuarios_ativos_mes,
            "novos_usuarios_mes": usuarios_novos_mes,
            "acessos_por_dia": acessos_por_dia,
            "acessos_por_hora": acessos_por_hora,
            "funcionalidades": funcionalidades,
        },
        "fluxo": fluxo,
    }
