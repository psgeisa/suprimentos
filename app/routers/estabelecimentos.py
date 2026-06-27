from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user, get_viewer, require_admin
from app.database import get_db
from app.models.estabelecimento import Estabelecimento
from app.schemas.estabelecimento import (
    EstabelecimentoCreate,
    EstabelecimentoOut,
    EstabelecimentoUpdate,
)

router = APIRouter(prefix="/api/estabelecimentos", tags=["estabelecimentos"])

@router.get("", response_model=List[EstabelecimentoOut])
def listar(db: Session = Depends(get_db), _=Depends(get_viewer)):
    return db.query(Estabelecimento).order_by(Estabelecimento.tipo).all()


@router.post("", response_model=EstabelecimentoOut, status_code=201)
def criar(data: EstabelecimentoCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    tipo = data.tipo.strip()
    if not tipo:
        raise HTTPException(400, "Informe o tipo do estabelecimento")
    if db.query(Estabelecimento).filter(Estabelecimento.tipo.ilike(tipo), Estabelecimento.ativo == True).first():
        raise HTTPException(400, "Tipo de estabelecimento já cadastrado")
    item = Estabelecimento(nome=tipo, tipo=tipo, segmentos=data.segmentos)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/{id}", response_model=EstabelecimentoOut)
def atualizar(id: int, data: EstabelecimentoUpdate, db: Session = Depends(get_db), _=Depends(require_admin)):
    item = db.query(Estabelecimento).filter(Estabelecimento.id == id).first()
    if not item:
        raise HTTPException(404, "Estabelecimento não encontrado")
    values = data.model_dump(exclude_none=True)
    if "tipo" in values:
        values["tipo"] = values["tipo"].strip()
        if not values["tipo"]:
            raise HTTPException(400, "Informe o tipo do estabelecimento")
        values["nome"] = values["tipo"]
    for field, value in values.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{id}", status_code=204)
def remover(id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    item = db.query(Estabelecimento).filter(Estabelecimento.id == id).first()
    if not item:
        raise HTTPException(404, "Estabelecimento não encontrado")
    item.ativo = False
    db.commit()
