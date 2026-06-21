from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class AnexoOut(BaseModel):
    id: int
    suprimento_id: int
    nome_arquivo: str
    tipo_mime: Optional[str] = None
    tamanho_bytes: Optional[int] = None
    url_storage: str
    bucket: str
    criado_por: Optional[str] = None
    criado_em: datetime

    class Config:
        from_attributes = True
