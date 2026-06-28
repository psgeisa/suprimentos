import json
from sqlalchemy import Column, Integer, String, DateTime, Text, Float
from datetime import datetime
from app.database import Base


class CompraLog(Base):
    __tablename__ = "compra_logs"

    id = Column(Integer, primary_key=True, index=True)
    usuario = Column(String(150), nullable=False)
    usuario_id = Column(Integer, nullable=True)
    data_hora = Column(DateTime, default=datetime.utcnow)
    itens_comprados = Column(Text, nullable=True)   # JSON list
    itens_nao_comprados = Column(Text, nullable=True)  # JSON list of IDs
    total_estimado = Column(Float, nullable=True)
    observacoes = Column(Text, nullable=True)
