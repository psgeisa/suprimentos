from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class EstabelecimentoCreate(BaseModel):
    tipo: str
    segmentos: Optional[str] = None


class EstabelecimentoUpdate(BaseModel):
    tipo: Optional[str] = None
    segmentos: Optional[str] = None
    ativo: Optional[bool] = None


class EstabelecimentoOut(BaseModel):
    id: int
    nome: str
    tipo: str
    segmentos: Optional[str]
    ativo: bool
    criado_em: datetime

    class Config:
        from_attributes = True
