from sqlalchemy import Column, Integer, String, BigInteger, DateTime, ForeignKey
from datetime import datetime

from app.database import Base


class Anexo(Base):
    __tablename__ = "anexos"

    id = Column(Integer, primary_key=True, index=True)
    suprimento_id = Column(Integer, ForeignKey("suprimentos.id", ondelete="CASCADE"), nullable=False)
    nome_arquivo = Column(String(255), nullable=False)
    tipo_mime = Column(String(100), nullable=True)
    tamanho_bytes = Column(BigInteger, nullable=True)
    url_storage = Column(String(500), nullable=False)
    bucket = Column(String(100), nullable=False)
    criado_por = Column(String(150), nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)
