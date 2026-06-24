from app.database import Base
from sqlalchemy import Column, Integer, String, Boolean


class Unidade(Base):
    __tablename__ = "unidades"

    id = Column(Integer, primary_key=True, index=True)
    sigla = Column(String(20), nullable=False, unique=True, index=True)
    nome = Column(String(100), nullable=False)
    ativo = Column(Boolean, nullable=False, default=True)
