from app.database import Base
from sqlalchemy import Column, Integer, String, Boolean


class Item(Base):
    __tablename__ = "itens"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(200), nullable=False, unique=True, index=True)
    segmento = Column(String(100), nullable=False, index=True)
    ativo = Column(Boolean, nullable=False, default=True)
