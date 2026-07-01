"""
Seed tabelas de plataforma: ia_sugestao_log e access_logs
Periodo: Jan/2026 - Jul/2026
Uso: python seed_plataforma.py
"""
import os, random, uuid
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models.ia_sugestao_log import IaSugestaoLog
from app.models.access_log import AccessLog
from app.models.user import User

engine = create_engine(os.environ["DATABASE_URL"])
Session = sessionmaker(bind=engine)
Base.metadata.create_all(engine)

rng = random.Random(99)

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END   = datetime(2026, 7, 1, 23, 59, 59, tzinfo=timezone.utc)


def rand_dt(start, end):
    delta = int((end - start).total_seconds())
    return start + timedelta(seconds=rng.randint(0, delta))


# ── Dados para IaSugestaoLog ──────────────────────────────────────────────────

TIPOS = ["segmento", "item", "categoria", "fornecedor", "unidade"]
TIPO_WEIGHTS = [30, 35, 20, 10, 5]

# (termo digitado pelo usuário, sugestão da IA)
CORRECOES = {
    "segmento": [
        ("limpeza geral",   "Limpeza"),
        ("escritório",      "Escritório"),
        ("alimentaçao",     "Alimentação"),
        ("manutençao",      "Manutenção"),
        ("saúde",           "Saúde"),
        ("educação",        "Educação"),
        ("tecnologia",      "Tecnologia"),
        ("Limpeza",         "Limpeza"),
        ("Escritorio",      "Escritório"),
        ("Alimentacao",     "Alimentação"),
    ],
    "item": [
        ("resma papel",          "Resma de papel A4"),
        ("detergente",           "Detergente líquido 500ml"),
        ("café 500g",            "Café em pó 500g"),
        ("arroz",                "Arroz 5kg"),
        ("feijão",               "Feijão 1kg"),
        ("caneta",               "Caneta esferográfica (cx)"),
        ("toner hp",             "Toner impressora HP"),
        ("lampada led",          "Lâmpada LED 9W"),
        ("alcool gel",           "Álcool gel 500ml"),
        ("mascara cirurgica",    "Máscara cirúrgica (cx50)"),
        ("kit primeiros scorros","Kit primeiros socorros"),
        ("mouse",                "Mouse USB"),
    ],
    "categoria": [
        ("Limpeza e Higiene", "Limpeza"),
        ("Papelaria",         "Escritório"),
        ("Comida",            "Alimentação"),
        ("Reparo",            "Manutenção"),
    ],
    "fornecedor": [
        ("atacadao",           "Atacadão Suprimentos"),
        ("distribuidora norte", "Distribuidora Norte"),
        ("mercado",            "Mercado Atacado"),
    ],
    "unidade": [
        ("unidade", "un"),
        ("caixa",   "cx"),
        ("litro",   "L"),
    ],
}

# ── Dados para AccessLog ──────────────────────────────────────────────────────

PATHS = [
    ("/api/suprimentos",          40),
    ("/api/suprimentos/{id}",     20),
    ("/api/compras",              15),
    ("/api/aprovacoes",           12),
    ("/api/dashboard",            18),
    ("/api/itens",                10),
    ("/api/kpis-negocio",         8),
    ("/api/kpis-plataforma",      5),
    ("/api/entregas",             9),
    ("/api/auth/login",           6),
    ("/api/usuarios",             4),
    ("/api/custos-bi",            7),
    ("/api/agenda-financeira",    6),
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Firefox/121.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Mobile Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13) Chrome/120.0 Mobile",
]

CIDADES = [
    ("São Paulo", "SP", "Brasil"),
    ("Rio de Janeiro", "RJ", "Brasil"),
    ("Belo Horizonte", "MG", "Brasil"),
    ("Curitiba", "PR", "Brasil"),
    ("Porto Alegre", "RS", "Brasil"),
    ("Salvador", "BA", "Brasil"),
    ("Fortaleza", "CE", "Brasil"),
]

IPS = [f"177.{rng.randint(1,254)}.{rng.randint(1,254)}.{rng.randint(1,254)}" for _ in range(50)]

# Horários de pico: seg-sex 8h-18h concentrado
def rand_work_dt(start, end):
    """Gera datetime com distribuição realista de horário comercial."""
    dt = rand_dt(start, end)
    # 75% chance de cair em horário útil (8-18h, seg-sex)
    if rng.random() < 0.75:
        h = rng.choices(
            list(range(24)),
            weights=[1,1,1,1,1,1,1,2, 8,12,14,12, 10,14,12,10, 8,6,4,3, 2,2,1,1],
            k=1
        )[0]
        dt = dt.replace(hour=h, minute=rng.randint(0, 59))
        # mais acessos em dias úteis
        while dt.weekday() >= 5 and rng.random() < 0.7:
            dt = dt + timedelta(days=rng.choice([-1, 1]))
    return dt


with Session() as db:
    all_users = db.query(User).all()
    user_ids = [u.id for u in all_users]
    stakeholder_ids = [u.id for u in all_users if u.role in ("solicitante", "aprovador")]

    # ── IaSugestaoLog — 1.200 interações ─────────────────────────────────────
    existing = db.query(IaSugestaoLog).count()
    ia_target = 1200

    if existing < ia_target:
        print(f"Inserindo {ia_target - existing} registros em ia_sugestao_log...")
        for _ in range(ia_target - existing):
            tipo = rng.choices(TIPOS, weights=TIPO_WEIGHTS, k=1)[0]
            pares = CORRECOES.get(tipo, [("termo", "Sugestão")])
            termo_user, sugestao = rng.choice(pares)

            # 68% aceita, 32% recusa
            aprovado = rng.random() < 0.68
            termo_final = sugestao if aprovado else termo_user

            dt = rand_dt(START, END)
            uid = rng.choice(stakeholder_ids) if stakeholder_ids else None

            db.add(IaSugestaoLog(
                tipo=tipo,
                stakeholder_id=uid,
                termo_stakeholder=termo_user,
                sugestao_ia=sugestao,
                aprovacao_stakeholder=aprovado,
                termo_final=termo_final,
                data_hora=dt,
            ))

        db.flush()
        print(f"  ✅ ia_sugestao_log: {db.query(IaSugestaoLog).count()} registros totais")
    else:
        print(f"  ✅ ia_sugestao_log já tem {existing} registros, pulando.")

    # ── AccessLog — 8.000 acessos ─────────────────────────────────────────────
    existing_acc = db.query(AccessLog).count()
    acc_target = 8000

    if existing_acc < acc_target:
        print(f"Inserindo {acc_target - existing_acc} registros em access_logs...")
        path_list  = [p for p, _ in PATHS]
        path_wts   = [w for _, w in PATHS]

        for _ in range(acc_target - existing_acc):
            uid = rng.choice(user_ids) if user_ids and rng.random() < 0.85 else None
            user = next((u for u in all_users if u.id == uid), None)
            path_tmpl = rng.choices(path_list, weights=path_wts, k=1)[0]
            # substitui {id} por número real
            path = path_tmpl.replace("{id}", str(rng.randint(1, 2000)))
            cidade, estado, pais = rng.choice(CIDADES)

            dt = rand_work_dt(START, END)
            # access_log usa DateTime sem timezone
            dt_naive = dt.replace(tzinfo=None)

            db.add(AccessLog(
                visitor_id=str(uuid.uuid4()),
                ip=rng.choice(IPS),
                user_agent=rng.choice(USER_AGENTS),
                path=path,
                usuario_id=uid,
                usuario_nome=user.nome if user else None,
                cidade=cidade,
                estado=estado,
                pais=pais,
                data_hora=dt_naive,
            ))

        db.flush()
        print(f"  ✅ access_logs: {db.query(AccessLog).count()} registros totais")
    else:
        print(f"  ✅ access_logs já tem {existing_acc} registros, pulando.")

    db.commit()
    print()
    print("🎉 Seed de plataforma concluído!")
    print(f"   ia_sugestao_log : {db.query(IaSugestaoLog).count()}")
    print(f"   access_logs     : {db.query(AccessLog).count()}")
