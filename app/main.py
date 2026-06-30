import asyncio
import os
import uuid
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.limiter import limiter

from app.database import Base, engine, SessionLocal
import app.models  # noqa — garante registro de todos os modelos antes do create_all
from app.routers import suprimentos, dashboard
from app.routers import auth as routers_auth
from app.routers import usuarios, anexos, lugares, estabelecimentos, itens, compras, entregas, aprovacoes, custos_bi, acessos
from sqlalchemy import inspect, text

VISITOR_COOKIE = "visitor_id"
VISITOR_COOKIE_MAX_AGE = 60 * 60 * 24 * 730  # ~2 anos


def _save_access_log(visitor_id: str, ip: str | None, user_agent: str | None, path: str):
    """Executa em thread separada para nunca atrasar a resposta ao usuário."""
    from app.models.access_log import AccessLog

    db = SessionLocal()
    try:
        db.add(AccessLog(
            visitor_id=visitor_id,
            ip=ip,
            user_agent=user_agent,
            path=path,
            data_hora=datetime.utcnow(),
        ))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Registra cada carregamento da página inicial (data/hora, IP e visitante).

    O registro roda em segundo plano (thread separada) para não impactar a
    navegação do usuário: a resposta é devolvida imediatamente, sem esperar
    a gravação no banco.
    """

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.method == "GET" and request.url.path == "/":
            visitor_id = request.cookies.get(VISITOR_COOKIE)
            is_new_visitor = not visitor_id
            if is_new_visitor:
                visitor_id = str(uuid.uuid4())
                response.set_cookie(
                    VISITOR_COOKIE, visitor_id,
                    max_age=VISITOR_COOKIE_MAX_AGE, httponly=True, samesite="lax",
                )

            forwarded = request.headers.get("x-forwarded-for")
            ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else None)
            user_agent = request.headers.get("user-agent")

            asyncio.create_task(
                run_in_threadpool(_save_access_log, visitor_id, ip, user_agent, request.url.path)
            )
        return response

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")


_ITENS_SEED = [
    ("Leite", "Alimentação"), ("Arroz", "Alimentação"), ("Feijão", "Alimentação"),
    ("Macarrão", "Alimentação"), ("Açúcar", "Alimentação"), ("Sal", "Alimentação"),
    ("Óleo de Soja", "Alimentação"), ("Farinha de Trigo", "Alimentação"),
    ("Café", "Alimentação"), ("Biscoito", "Alimentação"), ("Pão de Forma", "Alimentação"),
    ("Queijo", "Alimentação"), ("Presunto", "Alimentação"), ("Iogurte", "Alimentação"),
    ("Refrigerante", "Alimentação"), ("Suco", "Alimentação"),
    ("Água Mineral", "Alimentação"), ("Ovos", "Alimentação"),
    ("Margarina", "Alimentação"), ("Molho de Tomate", "Alimentação"),
    ("Detergente", "Limpeza"), ("Sabão em Pó", "Limpeza"), ("Amaciante", "Limpeza"),
    ("Água Sanitária", "Limpeza"), ("Desinfetante", "Limpeza"),
    ("Esponja de Louça", "Limpeza"), ("Pano de Limpeza", "Limpeza"),
    ("Limpador Multiuso", "Limpeza"), ("Saco de Lixo", "Limpeza"),
    ("Papel Toalha", "Limpeza"), ("Detergente Neutro", "Limpeza"),
    ("Saco de Lixo 100L", "Limpeza"),
    ("Papel Higiênico", "Higiene"), ("Sabonete", "Higiene"),
    ("Shampoo", "Higiene"), ("Creme Dental", "Higiene"),
    ("Escova de Dentes", "Higiene"),
    ("Papel Sulfite A4", "Material de Escritório"),
    ("Caneta Esferográfica", "Material de Escritório"),
    ("Pasta Suspensa", "Material de Escritório"),
    ("Toner para Impressora", "Material de Escritório"),
    ("Notebook", "Informática"), ("Monitor 24\"", "Informática"),
    ("Teclado USB", "Informática"), ("Mouse Sem Fio", "Informática"),
    ("Licença Microsoft 365", "Software"),
    ("Licença Adobe Creative Cloud", "Software"),
    ("Licença Power BI Pro", "Software"),
    ("Assinatura GitHub Copilot", "Software"),
    ("SSD 1TB", "Tecnologia"), ("Memória RAM 16GB", "Tecnologia"),
    ("Switch de Rede", "Tecnologia"), ("Access Point Wi-Fi", "Tecnologia"),
    ("Cabo de Rede Cat6", "Telecomunicações"),
    ("Telefone IP", "Telecomunicações"),
    ("Chip de Dados Corporativo", "Telecomunicações"),
    ("Mesa de Escritório", "Mobiliário"), ("Cadeira Ergonômica", "Mobiliário"),
    ("Armário Arquivo", "Mobiliário"),
    ("Lâmpada LED", "Elétrico"), ("Disjuntor", "Elétrico"),
    ("Filtro de Linha", "Elétrico"),
    ("Torneira", "Hidráulico"), ("Registro de Água", "Hidráulico"),
    ("Tubo PVC", "Hidráulico"),
    ("Furadeira", "Ferramentas"), ("Parafusadeira", "Ferramentas"),
    ("Jogo de Chaves Allen", "Ferramentas"),
    ("Capacete de Segurança", "EPI"), ("Luva de Proteção", "EPI"),
    ("Óculos de Segurança", "EPI"),
    ("Camiseta Uniforme", "Uniformes"), ("Jaqueta Corporativa", "Uniformes"),
    ("Café em Pó", "Copa"), ("Açúcar Refinado", "Copa"),
    ("Filtro de Café", "Copa"), ("Copo Descartável", "Copa"),
    ("Banner Institucional", "Gráfica"), ("Cartão de Visita", "Gráfica"),
    ("Adesivo Personalizado", "Gráfica"),
    ("Placa de Sinalização", "Sinalização"),
    ("Placa de Saída de Emergência", "Sinalização"),
    ("Muda de Palmeira", "Jardinagem"), ("Adubo Orgânico", "Jardinagem"),
    ("Ar Condicionado Split", "Climatização"),
    ("Filtro para Ar Condicionado", "Climatização"),
    ("Extintor de Incêndio", "Segurança"),
    ("Câmera de Monitoramento", "Segurança"),
    ("Fechadura Eletrônica", "Segurança"),
    ("Combustível Diesel", "Transporte"), ("Vale Transporte", "Transporte"),
    ("Rastreador Veicular", "Transporte"),
    ("Caixa de Papelão", "Embalagens"), ("Filme Stretch", "Embalagens"),
    ("Etiqueta Adesiva", "Embalagens"),
    ("Exame Admissional", "Saúde Ocupacional"),
    ("Kit de Primeiros Socorros", "Saúde Ocupacional"),
    ("Consultoria Jurídica", "Jurídico"), ("Parecer Jurídico", "Jurídico"),
    ("Serviço de Auditoria", "Auditoria"),
    ("Consultoria Financeira", "Contabilidade"),
    ("Servidor Cloud", "Cloud Computing"), ("Storage 1TB", "Cloud Computing"),
    ("Banco de Dados Gerenciado", "Cloud Computing"),
    ("Sensor IoT", "IoT"), ("Gateway IoT", "IoT"),
    ("Rack 44U", "Data Center"), ("Nobreak", "Data Center"),
]


def seed_itens():
    from app.models.item import Item

    db = SessionLocal()
    try:
        if db.query(Item).count() == 0:
            db.bulk_save_objects([Item(nome=nome, segmento=seg) for nome, seg in _ITENS_SEED])
            db.commit()
            print(f"[seed] {len(_ITENS_SEED)} itens inseridos.")
    finally:
        db.close()


def seed_admin():
    from app.models.user import User
    from app.auth import hash_password

    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            admin = User(
                nome="Administrador",
                email="admin@ong.org",
                senha_hash=hash_password("admin123"),
                role="admin",
            )
            db.add(admin)
            db.commit()
            print("=" * 50)
            print("Usuário admin criado automaticamente:")
            print("  Email : admin@ong.org")
            print("  Senha : admin123")
            print("Altere a senha após o primeiro login!")
            print("=" * 50)
    finally:
        db.close()


def migrate_schema():
    """Aplica migrações pequenas necessárias em bancos já existentes."""
    columns = {column["name"] for column in inspect(engine).get_columns("suprimentos")}
    if "estabelecimento_id" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE suprimentos ADD COLUMN estabelecimento_id INTEGER"))
    estabelecimento_columns = {column["name"] for column in inspect(engine).get_columns("estabelecimentos")}
    if "segmentos" not in estabelecimento_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE estabelecimentos ADD COLUMN segmentos VARCHAR(500)"))
    user_columns = {column["name"] for column in inspect(engine).get_columns("users")}
    if "time" not in user_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE users ADD COLUMN time VARCHAR(150)"))
    sup_columns2 = {column["name"] for column in inspect(engine).get_columns("suprimentos")}
    if "item_id" not in sup_columns2:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE suprimentos ADD COLUMN item_id INTEGER"))
    if "item_nome" not in sup_columns2:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE suprimentos ADD COLUMN item_nome VARCHAR(200)"))
    if "solicitante_responsavel" not in sup_columns2:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE suprimentos ADD COLUMN solicitante_responsavel VARCHAR(150)"))
    sup_columns3 = {column["name"] for column in inspect(engine).get_columns("suprimentos")}
    if "ordem_compra" not in sup_columns3:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE suprimentos ADD COLUMN ordem_compra VARCHAR(20)"))
    if "valor_compra" not in sup_columns3:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE suprimentos ADD COLUMN valor_compra FLOAT"))
    if "teto_gasto" not in sup_columns3:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE suprimentos ADD COLUMN teto_gasto FLOAT"))
            connection.execute(text(
                "UPDATE suprimentos "
                "SET teto_gasto = valor_compra, valor_compra = NULL "
                "WHERE status IN ('pendente', 'aprovado') AND valor_compra IS NOT NULL"
            ))
    if "responsavel_entrega" not in sup_columns3:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE suprimentos ADD COLUMN responsavel_entrega VARCHAR(200)"))
    if "entregue_em" not in sup_columns3:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE suprimentos ADD COLUMN entregue_em TIMESTAMP"))


def migrate_segmento_table():
    """Preserva os registros ao substituir a antiga tabela categorias."""
    existing_tables = set(inspect(engine).get_table_names())
    if "segmento" in existing_tables:
        return
    legacy_table = "categorias" if "categorias" in existing_tables else (
        "segmentos" if "segmentos" in existing_tables else None
    )
    if legacy_table:
        with engine.begin() as connection:
            connection.execute(text(f"ALTER TABLE {legacy_table} RENAME TO segmento"))


def create_app() -> FastAPI:
    app = FastAPI(title="Gestão de Suprimentos", version="2.0.0")
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(AccessLogMiddleware)

    @app.on_event("startup")
    def startup():
        migrate_segmento_table()
        Base.metadata.create_all(bind=engine)
        migrate_schema()
        seed_admin()
        seed_itens()

    app.include_router(routers_auth.router)
    app.include_router(usuarios.router)
    app.include_router(suprimentos.router)
    app.include_router(anexos.router)
    app.include_router(dashboard.router)
    app.include_router(lugares.router)
    app.include_router(estabelecimentos.router)
    app.include_router(itens.router)
    app.include_router(compras.router)
    app.include_router(entregas.router)
    app.include_router(aprovacoes.router)
    app.include_router(custos_bi.router)
    app.include_router(acessos.router)

    app.mount(
        "/static",
        StaticFiles(directory=os.path.join(FRONTEND_DIR, "static")),
        name="static",
    )
    app.mount(
        "/imgs",
        StaticFiles(directory=os.path.join(FRONTEND_DIR, "imgs")),
        name="imgs",
    )

    @app.get("/", response_class=FileResponse)
    def index():
        return FileResponse(
            os.path.join(FRONTEND_DIR, "static", "index.html"),
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )

    return app


app = create_app()
