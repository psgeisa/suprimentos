from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.database import Base


class IaSugestaoLog(Base):
    __tablename__ = "ia_sugestao_log"

    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String(50), nullable=False)          # 'segmento', 'item', etc.
    stakeholder_id = Column(Integer, nullable=True)
    termo_stakeholder = Column(String(200), nullable=False)
    sugestao_ia = Column(String(200), nullable=True)
    aprovacao_stakeholder = Column(Boolean, nullable=True)  # True=aprovado, False=reprovado
    termo_final = Column(String(200), nullable=True)
    data_hora = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
