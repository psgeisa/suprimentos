"""
Seed Supabase — popula o banco com dados realistas de Jan/2026 a Jul/2026.
Uso: python seed_supabase.py
"""
import os, random, json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# ── Conexão ──────────────────────────────────────────────────────────────────
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

# ── Importa modelos (cria tabelas se não existirem) ──────────────────────────
from app.models import __init__ as _  # noqa — registra todos os modelos
from app.database import Base
from app.models.user import User
from app.models.estabelecimento import Estabelecimento
from app.models.item import Item
from app.models.unidade import Unidade
from app.models.suprimento import Suprimento
from app.models.compra_log import CompraLog
from passlib.context import CryptContext

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

Base.metadata.create_all(engine)
print("✅ Tabelas criadas/verificadas.")

rng = random.Random(42)

# ── Helpers ──────────────────────────────────────────────────────────────────

def rand_dt(start: datetime, end: datetime) -> datetime:
    delta = int((end - start).total_seconds())
    return start + timedelta(seconds=rng.randint(0, delta))


START = datetime(2026, 1, 1)
END   = datetime(2026, 7, 1, 23, 59, 59)

# ── Dados mestres ─────────────────────────────────────────────────────────────

USUARIOS = [
    {"nome": "Admin ONG",        "email": "admin@ong.org",        "role": "admin",        "time": "Gestão"},
    {"nome": "Carlos Mendes",    "email": "carlos@ong.org",        "role": "comprador",    "time": "Compras"},
    {"nome": "Fernanda Lima",    "email": "fernanda@ong.org",      "role": "comprador",    "time": "Compras"},
    {"nome": "Rafael Souza",     "email": "rafael@ong.org",        "role": "aprovador",    "time": "Diretoria"},
    {"nome": "Juliana Costa",    "email": "juliana@ong.org",       "role": "aprovador",    "time": "Diretoria"},
    {"nome": "Marcos Oliveira",  "email": "marcos@ong.org",        "role": "solicitante",  "time": "Projetos"},
    {"nome": "Ana Paula Silva",  "email": "ana@ong.org",           "role": "solicitante",  "time": "Projetos"},
    {"nome": "Thiago Rocha",     "email": "thiago@ong.org",        "role": "solicitante",  "time": "Educação"},
    {"nome": "Patricia Gomes",   "email": "patricia@ong.org",      "role": "solicitante",  "time": "Saúde"},
    {"nome": "Eduardo Ferreira", "email": "eduardo@ong.org",       "role": "solicitante",  "time": "Infraestrutura"},
]

ESTABELECIMENTOS = [
    {"nome": "Sede Central",         "tipo": "Sede Central"},
    {"nome": "Unidade Norte",        "tipo": "Unidade Norte"},
    {"nome": "Unidade Sul",          "tipo": "Unidade Sul"},
    {"nome": "Centro Comunitário A", "tipo": "Centro Comunitário A"},
    {"nome": "Centro Comunitário B", "tipo": "Centro Comunitário B"},
    {"nome": "Escola Parceira",      "tipo": "Escola Parceira"},
]

ITENS = [
    # Limpeza
    ("Detergente líquido 500ml",   "Limpeza"), ("Desinfetante 1L",         "Limpeza"),
    ("Papel toalha rolo",          "Limpeza"), ("Sabão em pó 1kg",         "Limpeza"),
    ("Luva descartável (cx50)",    "Limpeza"), ("Álcool gel 500ml",        "Limpeza"),
    # Escritório
    ("Resma de papel A4",          "Escritório"), ("Caneta esferográfica (cx)", "Escritório"),
    ("Pasta arquivo",              "Escritório"), ("Grampeador",             "Escritório"),
    ("Toner impressora HP",        "Escritório"), ("Caderno 100fls",         "Escritório"),
    # Alimentação
    ("Arroz 5kg",                  "Alimentação"), ("Feijão 1kg",           "Alimentação"),
    ("Óleo de soja 900ml",         "Alimentação"), ("Açúcar 1kg",           "Alimentação"),
    ("Macarrão 500g",              "Alimentação"), ("Sal 1kg",               "Alimentação"),
    ("Leite UHT 1L",               "Alimentação"), ("Biscoito integral (cx)", "Alimentação"),
    # Manutenção
    ("Lâmpada LED 9W",             "Manutenção"), ("Fita isolante",         "Manutenção"),
    ("Parafuso kit",               "Manutenção"), ("Tinta látex 18L",       "Manutenção"),
    ("Extensão elétrica 5m",       "Manutenção"), ("Filtro de ar condic.",  "Manutenção"),
    # Saúde
    ("Máscara cirúrgica (cx50)",   "Saúde"),      ("Termômetro digital",    "Saúde"),
    ("Kit primeiros socorros",     "Saúde"),       ("Álcool 70% 1L",         "Saúde"),
    # Educação
    ("Livro didático Matemática",  "Educação"),   ("Kit tinta guache",      "Educação"),
    ("Giz de cera (cx24)",         "Educação"),   ("EVA colorido (pkg10)",  "Educação"),
    # Tecnologia
    ("Mouse USB",                  "Tecnologia"), ("Teclado ABNT2",         "Tecnologia"),
    ("Cabo HDMI 1.8m",             "Tecnologia"), ("Pen drive 32GB",        "Tecnologia"),
]

UNIDADES = [
    ("un", "Unidade"), ("cx", "Caixa"), ("kg", "Quilograma"),
    ("L",  "Litro"),   ("rolo", "Rolo"), ("pkg", "Pacote"),
    ("m",  "Metro"),   ("par", "Par"),
]

CATEGORIAS_PRECO = {
    "Limpeza":     (8,  120),
    "Escritório":  (15, 350),
    "Alimentação": (5,  80),
    "Manutenção":  (20, 600),
    "Saúde":       (30, 500),
    "Educação":    (10, 200),
    "Tecnologia":  (40, 800),
}

FORNECEDORES = [
    "Distribuidora Norte", "Atacadão Suprimentos", "Papelaria Central",
    "Fornecedora Geral Ltda", "Mercado Atacado", "Tech Supplies BR",
    "Farmácia Popular", "Construleste", "Livraria Educação",
]

PRIORIDADES = ["baixa", "media", "alta", "urgente"]
PRIORIDADE_WEIGHTS = [15, 50, 25, 10]

DEPARTAMENTOS = [
    "Administração", "Projetos Sociais", "Educação", "Saúde",
    "Infraestrutura", "Comunicação", "Captação de Recursos",
]

STATUS_FLOW = {
    # status_final: probabilidade
    "concluido":    0.45,
    "entregue":     0.12,
    "em_andamento": 0.18,
    "aprovado":     0.10,
    "pendente":     0.10,
    "cancelado":    0.05,
}

# ── Inserção ─────────────────────────────────────────────────────────────────

with Session() as db:

    # Users
    existing_emails = {u.email for u in db.query(User.email).all()}
    users_created = []
    for u in USUARIOS:
        if u["email"] not in existing_emails:
            user = User(
                nome=u["nome"], email=u["email"],
                senha_hash=pwd_ctx.hash("admin123"),
                role=u["role"], time=u["time"], ativo=True,
            )
            db.add(user)
            users_created.append(user)
    db.flush()
    all_users = db.query(User).all()
    print(f"✅ Usuários: {len(all_users)} no banco.")

    # Unidades
    existing_siglas = {u.sigla for u in db.query(Unidade.sigla).all()}
    for sigla, nome in UNIDADES:
        if sigla not in existing_siglas:
            db.add(Unidade(sigla=sigla, nome=nome, ativo=True))
    db.flush()

    # Itens
    existing_itens = {i.nome for i in db.query(Item.nome).all()}
    item_objs = []
    for nome, seg in ITENS:
        if nome not in existing_itens:
            obj = Item(nome=nome, segmento=seg, ativo=True)
            db.add(obj)
            item_objs.append(obj)
    db.flush()
    all_items = db.query(Item).all()
    print(f"✅ Itens: {len(all_items)} no banco.")

    # Estabelecimentos
    existing_ests = {e.nome for e in db.query(Estabelecimento.nome).all()}
    est_objs = []
    for e in ESTABELECIMENTOS:
        if e["nome"] not in existing_ests:
            obj = Estabelecimento(nome=e["nome"], tipo=e["tipo"], ativo=True)
            db.add(obj)
            est_objs.append(obj)
    db.flush()
    all_ests = db.query(Estabelecimento).all()
    print(f"✅ Estabelecimentos: {len(all_ests)} no banco.")

    # Suprimentos — 380 registros distribuídos em Jan-Jul 2026
    solicitantes = [u for u in all_users if u.role in ("solicitante", "aprovador", "comprador")]
    responsaveis = [u for u in all_users if u.role in ("aprovador", "comprador", "admin")]
    compradores  = [u for u in all_users if u.role in ("comprador", "admin")]

    existing_count = db.query(Suprimento).count()
    TARGET = 380

    suprimentos_criados = []
    compra_logs = []

    ordem_counter = db.execute(text("SELECT COALESCE(MAX(CAST(REPLACE(ordem_compra,'OC-','') AS INTEGER)),0) FROM suprimentos WHERE ordem_compra LIKE 'OC-%'")).scalar() or 0

    for i in range(TARGET - existing_count if existing_count < TARGET else 0):
        item = rng.choice(all_items)
        cat = item.segmento
        est = rng.choice(all_ests)
        sol_user = rng.choice(solicitantes)
        resp_user = rng.choice(responsaveis)
        forn = rng.choice(FORNECEDORES)
        prio = rng.choices(PRIORIDADES, weights=PRIORIDADE_WEIGHTS, k=1)[0]
        depto = rng.choice(DEPARTAMENTOS)
        emergencia = 1 if prio == "urgente" and rng.random() < 0.4 else 0

        qtd = rng.choice([1, 2, 3, 4, 5, 6, 10, 12, 20, 24, 50, 100])
        p_min, p_max = CATEGORIAS_PRECO[cat]
        val_est = round(rng.uniform(p_min, p_max) * qtd, 2)
        teto    = round(val_est * rng.uniform(1.05, 1.30), 2)

        created = rand_dt(START, END)

        # Determina status e datas derivadas
        status_choices = list(STATUS_FLOW.keys())
        status_weights = list(STATUS_FLOW.values())
        # Registros criados perto do fim têm menor chance de concluir
        days_since = (END - created).days
        if days_since < 15:
            status_weights = [0.10, 0.05, 0.30, 0.25, 0.25, 0.05]
        status = rng.choices(status_choices, weights=status_weights, k=1)[0]

        entregue_em = None
        valor_compra = None
        ordem_compra = None
        updated_at = created + timedelta(hours=rng.randint(1, 72))

        if status in ("concluido", "entregue"):
            dias_ciclo = rng.randint(3, 45)
            entregue_em = created + timedelta(days=dias_ciclo)
            if entregue_em > END:
                entregue_em = END - timedelta(hours=rng.randint(1, 48))
            economia_pct = rng.uniform(-0.05, 0.20)  # pode ser ligeiramente acima
            valor_compra = round(teto * (1 - economia_pct), 2)
            if valor_compra <= 0:
                valor_compra = round(val_est * 0.95, 2)
            ordem_counter += 1
            ordem_compra = f"OC-{ordem_counter:04d}"
            updated_at = entregue_em + timedelta(hours=rng.randint(1, 24))

        elif status == "em_andamento":
            ordem_counter += 1
            ordem_compra = f"OC-{ordem_counter:04d}"
            updated_at = created + timedelta(days=rng.randint(2, 20))

        elif status == "aprovado":
            updated_at = created + timedelta(days=rng.randint(1, 10))

        unidade_sigla = rng.choice(["un", "cx", "kg", "L", "rolo", "pkg"])

        sup = Suprimento(
            titulo=f"{item.nome} — {depto}",
            descricao=f"Solicitação de {qtd} {unidade_sigla} de {item.nome} para uso em {est.tipo}.",
            categoria=cat,
            quantidade=qtd,
            unidade=unidade_sigla,
            valor_estimado=val_est,
            teto_gasto=teto,
            valor_compra=valor_compra,
            item_id=item.id,
            item_nome=item.nome,
            fornecedor_sugerido=forn,
            estabelecimento_id=est.id,
            ordem_compra=ordem_compra,
            solicitante=sol_user.nome,
            solicitante_responsavel=resp_user.nome,
            departamento=depto,
            prioridade=prio,
            emergencia=emergencia,
            prazo_emergencia=(created + timedelta(days=rng.randint(1, 5))).strftime("%Y-%m-%d") if emergencia else None,
            responsavel_entrega=resp_user.nome if status in ("concluido", "entregue", "em_andamento") else None,
            entregue_em=entregue_em,
            status=status,
            observacoes=None,
            data_necessidade=(created + timedelta(days=rng.randint(7, 60))).strftime("%Y-%m-%d"),
            created_at=created,
            updated_at=updated_at,
        )
        db.add(sup)
        suprimentos_criados.append((sup, status, valor_compra, updated_at))

    db.flush()
    print(f"✅ Suprimentos inseridos: {len(suprimentos_criados)} novos.")

    # CompraLog — um log por suprimento concluído/em_andamento
    comp_users = [u for u in all_users if u.role in ("comprador", "admin")]
    existing_logs = db.query(CompraLog).count()

    for sup, status, valor_compra, updated_at in suprimentos_criados:
        if status in ("concluido", "entregue", "em_andamento"):
            comprador = rng.choice(comp_users)
            itens_json = json.dumps([{"id": sup.item_id, "nome": sup.item_nome, "qtd": sup.quantidade}])
            log = CompraLog(
                usuario=comprador.nome,
                usuario_id=comprador.id,
                data_hora=updated_at - timedelta(hours=rng.randint(1, 12)),
                itens_comprados=itens_json,
                itens_nao_comprados=json.dumps([]),
                total_estimado=valor_compra or sup.teto_gasto,
                observacoes=None,
            )
            db.add(log)

    db.flush()

    db.commit()
    print("✅ CompraLogs inseridos.")
    print()
    print("🎉 Seed concluído! Banco Supabase populado com dados de Jan–Jul 2026.")
    total_sups = db.query(Suprimento).count()
    total_logs = db.query(CompraLog).count()
    print(f"   Suprimentos totais : {total_sups}")
    print(f"   CompraLogs totais  : {total_logs}")
    print(f"   Usuários totais    : {db.query(User).count()}")
    print(f"   Itens totais       : {db.query(Item).count()}")
    print(f"   Estabelecimentos   : {db.query(Estabelecimento).count()}")
