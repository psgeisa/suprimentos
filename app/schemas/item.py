from pydantic import BaseModel
from typing import Optional


class ItemCreate(BaseModel):
    nome: str
    segmento: str
    ativo: bool = True


class ItemUpdate(BaseModel):
    nome: Optional[str] = None
    segmento: Optional[str] = None
    ativo: Optional[bool] = None


class ItemOut(BaseModel):
    id: int
    nome: str
    segmento: str
    ativo: bool

    class Config:
        from_attributes = True
