from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.database import Base


class AccessLog(Base):
    __tablename__ = "access_logs"

    id = Column(Integer, primary_key=True, index=True)
    visitor_id = Column(String(36), nullable=True, index=True)
    ip = Column(String(64), nullable=True)
    user_agent = Column(String(500), nullable=True)
    path = Column(String(300), nullable=True)
    usuario_id = Column(Integer, nullable=True)
    usuario_nome = Column(String(150), nullable=True)
    cidade = Column(String(150), nullable=True)
    estado = Column(String(150), nullable=True)
    pais = Column(String(150), nullable=True)
    data_hora = Column(DateTime, default=datetime.utcnow, index=True)
