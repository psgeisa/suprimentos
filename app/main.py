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
from app.routers import usuarios, anexos

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")


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


def create_app() -> FastAPI:
    app = FastAPI(title="Gestão de Suprimentos", version="2.0.0")

    @app.on_event("startup")
    def startup():
        Base.metadata.create_all(bind=engine)
        seed_admin()

    app.include_router(routers_auth.router)
    app.include_router(usuarios.router)
    app.include_router(suprimentos.router)
    app.include_router(anexos.router)
    app.include_router(dashboard.router)

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
        return FileResponse(os.path.join(FRONTEND_DIR, "static", "index.html"))

    return app


app = create_app()
