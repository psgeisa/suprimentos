from sqlalchemy import Column, Integer, String, DateTime, Text, Float
from datetime import datetime
from app.database import Base


class Suprimento(Base):
    __tablename__ = "suprimentos"

    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String(200), nullable=False)
    descricao = Column(Text, nullable=True)
    categoria = Column(String(200), nullable=False)
    quantidade = Column(Float, nullable=False)
    unidade = Column(String(50), nullable=False, default="un")
    valor_estimado = Column(Float, nullable=True)
    item_id = Column(Integer, nullable=True)
    item_nome = Column(String(200), nullable=True)
    fornecedor_sugerido = Column(String(200), nullable=True)
    estabelecimento_id = Column(Integer, nullable=True)
    solicitante = Column(String(150), nullable=False)
    departamento = Column(String(500), nullable=False)
    prioridade = Column(String(20), nullable=False, default="media")
    emergencia = Column(Integer, default=0)
    prazo_emergencia = Column(String(30), nullable=True)
    status = Column(String(30), nullable=False, default="pendente")
    observacoes = Column(Text, nullable=True)
    data_necessidade = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
