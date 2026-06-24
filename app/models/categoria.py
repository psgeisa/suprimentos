from app.database import Base
from sqlalchemy import Column, Integer, String, Boolean


class Categoria(Base):
    __tablename__ = "categorias"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False, unique=True, index=True)
    ativo = Column(Boolean, nullable=False, default=True)
