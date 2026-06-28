from sqlalchemy import Column, Integer, String, DateTime, Text
from datetime import datetime
from app.database import Base


class ItemEliminadoLog(Base):
    __tablename__ = "item_eliminado_logs"

    id = Column(Integer, primary_key=True, index=True)
    suprimento_id = Column(Integer, nullable=False)
    titulo = Column(String(200), nullable=True)
    item_nome = Column(String(200), nullable=True)
    categoria = Column(String(200), nullable=True)
    solicitante = Column(String(150), nullable=True)
    usuario_que_eliminou = Column(String(150), nullable=False)
    usuario_id = Column(Integer, nullable=True)
    data_hora = Column(DateTime, default=datetime.utcnow)
    motivo = Column(Text, nullable=True)
