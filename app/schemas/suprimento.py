from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class SuprimentoCreate(BaseModel):
    titulo: str
    descricao: Optional[str] = None
    categoria: str
    quantidade: float
    unidade: str = "un"
    valor_estimado: Optional[float] = None
    fornecedor_sugerido: Optional[str] = None
    solicitante: str
    departamento: str
    prioridade: str = "media"
    emergencia: int = 0
    prazo_emergencia: Optional[str] = None
    status: str = "pendente"
    observacoes: Optional[str] = None
    data_necessidade: Optional[str] = None


class SuprimentoUpdate(BaseModel):
    titulo: Optional[str] = None
    descricao: Optional[str] = None
    categoria: Optional[str] = None
    quantidade: Optional[float] = None
    unidade: Optional[str] = None
    valor_estimado: Optional[float] = None
    fornecedor_sugerido: Optional[str] = None
    solicitante: Optional[str] = None
    departamento: Optional[str] = None
    prioridade: Optional[str] = None
    emergencia: Optional[int] = None
    prazo_emergencia: Optional[str] = None
    status: Optional[str] = None
    observacoes: Optional[str] = None
    data_necessidade: Optional[str] = None


class SuprimentoOut(BaseModel):
    id: int
    titulo: str
    descricao: Optional[str]
    categoria: str
    quantidade: float
    unidade: str
    valor_estimado: Optional[float]
    fornecedor_sugerido: Optional[str]
    solicitante: str
    departamento: str
    prioridade: str
    emergencia: int
    prazo_emergencia: Optional[str]
    status: str
    observacoes: Optional[str]
    data_necessidade: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
