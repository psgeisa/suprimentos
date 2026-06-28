import os
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.database import Base, engine, SessionLocal
import app.models  # noqa — garante registro de todos os modelos antes do create_all
from app.routers import suprimentos, dashboard
from app.routers import auth as routers_auth
from app.routers import usuarios, anexos, lugares, estabelecimentos, itens, compras
from sqlalchemy import inspect, text

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


def create_app() -> FastAPI:
    app = FastAPI(title="Gestão de Suprimentos", version="2.0.0")

    @app.on_event("startup")
    def startup():
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
