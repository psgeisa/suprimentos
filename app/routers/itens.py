from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.item import Item
from app.schemas.item import ItemCreate, ItemUpdate, ItemOut
from app.auth import get_current_user, get_viewer

router = APIRouter(prefix="/api/itens", tags=["itens"])


@router.get("", response_model=list[ItemOut])
def listar(
    segmento: Optional[str] = Query(None),
    busca: Optional[str] = Query(None),
    apenas_ativos: bool = Query(True),
    db: Session = Depends(get_db),
    _=Depends(get_viewer),
):
    q = db.query(Item)
    if apenas_ativos:
        q = q.filter(Item.ativo == True)
    if segmento:
        q = q.filter(Item.segmento == segmento)
    if busca:
        q = q.filter(Item.nome.ilike(f"%{busca}%"))
    return q.order_by(Item.segmento, Item.nome).all()


@router.post("", response_model=ItemOut, status_code=201)
def criar(payload: ItemCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    if db.query(Item).filter(Item.nome == payload.nome).first():
        raise HTTPException(status_code=400, detail="Item já cadastrado.")
    item = Item(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/{item_id}", response_model=ItemOut)
def atualizar(item_id: int, payload: ItemUpdate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
def remover(item_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado.")
    db.delete(item)
    db.commit()
