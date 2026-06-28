from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class SuprimentoCreate(BaseModel):
    titulo: str
    descricao: Optional[str] = None
    categoria: str
    ordem_compra: Optional[str] = None
    item_id: Optional[int] = None
    item_nome: Optional[str] = None
    quantidade: float
    unidade: str = "un"
    valor_estimado: Optional[float] = None
    valor_compra: Optional[float] = None
    fornecedor_sugerido: Optional[str] = None
    estabelecimento_id: Optional[int] = None
    solicitante: str
    solicitante_responsavel: Optional[str] = None
    departamento: str
    prioridade: str = "media"
    emergencia: int = 0
    prazo_emergencia: Optional[str] = None
    responsavel_entrega: Optional[str] = None
    entregue_em: Optional[datetime] = None
    status: str = "pendente"
    observacoes: Optional[str] = None
    data_necessidade: Optional[str] = None


class SuprimentoUpdate(BaseModel):
    titulo: Optional[str] = None
    descricao: Optional[str] = None
    categoria: Optional[str] = None
    ordem_compra: Optional[str] = None
    item_id: Optional[int] = None
    item_nome: Optional[str] = None
    quantidade: Optional[float] = None
    unidade: Optional[str] = None
    valor_estimado: Optional[float] = None
    valor_compra: Optional[float] = None
    fornecedor_sugerido: Optional[str] = None
    estabelecimento_id: Optional[int] = None
    solicitante: Optional[str] = None
    solicitante_responsavel: Optional[str] = None
    departamento: Optional[str] = None
    prioridade: Optional[str] = None
    emergencia: Optional[int] = None
    prazo_emergencia: Optional[str] = None
    responsavel_entrega: Optional[str] = None
    entregue_em: Optional[datetime] = None
    status: Optional[str] = None
    observacoes: Optional[str] = None
    data_necessidade: Optional[str] = None


class SuprimentoOut(BaseModel):
    id: int
    titulo: str
    descricao: Optional[str]
    categoria: str
    ordem_compra: Optional[str] = None
    item_id: Optional[int] = None
    item_nome: Optional[str] = None
    quantidade: float
    unidade: str
    valor_estimado: Optional[float]
    valor_compra: Optional[float] = None
    fornecedor_sugerido: Optional[str]
    estabelecimento_id: Optional[int]
    estabelecimento_tipo: Optional[str] = None
    solicitante: str
    solicitante_responsavel: Optional[str] = None
    departamento: str
    prioridade: str
    emergencia: int
    prazo_emergencia: Optional[str]
    responsavel_entrega: Optional[str] = None
    entregue_em: Optional[datetime] = None
    status: str
    observacoes: Optional[str]
    data_necessidade: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
