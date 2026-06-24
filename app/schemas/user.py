from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class UserCreate(BaseModel):
    nome: str
    email: str
    senha: str
    role: str = "solicitante"
    time: Optional[str] = None


class UserUpdate(BaseModel):
    nome: Optional[str] = None
    role: Optional[str] = None
    time: Optional[str] = None
    ativo: Optional[bool] = None


class UserOut(BaseModel):
    id: int
    nome: str
    email: str
    role: str
    time: Optional[str] = None
    ativo: bool
    criado_em: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserOut
