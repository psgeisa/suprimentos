import math
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.models.suprimento import Suprimento
from app.models.estabelecimento import Estabelecimento
from app.schemas.suprimento import SuprimentoCreate, SuprimentoUpdate, SuprimentoOut
from app.auth import get_current_user

router = APIRouter(prefix="/api/suprimentos", tags=["suprimentos"])


@router.get("")
def listar(
    status: Optional[str] = Query(None),
    categoria: Optional[str] = Query(None),
    prioridade: Optional[str] = Query(None),
    estabelecimento: Optional[str] = Query(None),
    busca: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(Suprimento)
    if status:
        q = q.filter(Suprimento.status.in_([v for v in status.split(",") if v]))
    if categoria:
        q = q.filter(Suprimento.categoria.in_([v for v in categoria.split(",") if v]))
    if prioridade:
        q = q.filter(Suprimento.prioridade.in_([v for v in prioridade.split(",") if v]))
    if estabelecimento:
        ids = [int(v) for v in estabelecimento.split(",") if v.isdigit()]
        if ids:
            q = q.filter(Suprimento.estabelecimento_id.in_(ids))
    if busca:
        q = q.filter(
            Suprimento.titulo.ilike(f"%{busca}%")
            | Suprimento.descricao.ilike(f"%{busca}%")
            | Suprimento.categoria.ilike(f"%{busca}%")
            | Suprimento.solicitante.ilike(f"%{busca}%")
            | Suprimento.departamento.ilike(f"%{busca}%")
            | Suprimento.fornecedor_sugerido.ilike(f"%{busca}%")
            | Suprimento.status.ilike(f"%{busca}%")
            | Suprimento.prioridade.ilike(f"%{busca}%")
            | Suprimento.observacoes.ilike(f"%{busca}%")
        )
    total = q.count()
    pages = max(1, math.ceil(total / limit))
    items = q.order_by(Suprimento.created_at.desc()).offset((page - 1) * limit).limit(limit).all()

    est_ids = {i.estabelecimento_id for i in items if i.estabelecimento_id}
    est_map = {}
    if est_ids:
        ests = db.query(Estabelecimento).filter(Estabelecimento.id.in_(est_ids)).all()
        est_map = {e.id: e.tipo for e in ests}

    result = []
    for i in items:
        d = SuprimentoOut.model_validate(i).model_dump()
        d["estabelecimento_tipo"] = est_map.get(i.estabelecimento_id) if i.estabelecimento_id else None
        result.append(d)

    return {"items": result, "total": total, "page": page, "pages": pages}


@router.post("", response_model=SuprimentoOut, status_code=201)
def criar(data: SuprimentoCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    item = Suprimento(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/{id}", response_model=SuprimentoOut)
def obter(id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    item = db.query(Suprimento).filter(Suprimento.id == id).first()
    if not item:
        raise HTTPException(404, "Suprimento não encontrado")
    return item


@router.put("/{id}", response_model=SuprimentoOut)
def atualizar(id: int, data: SuprimentoUpdate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    item = db.query(Suprimento).filter(Suprimento.id == id).first()
    if not item:
        raise HTTPException(404, "Suprimento não encontrado")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(item, field, value)
    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{id}", status_code=204)
def deletar(id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    item = db.query(Suprimento).filter(Suprimento.id == id).first()
    if not item:
        raise HTTPException(404, "Suprimento não encontrado")
    db.delete(item)
    db.commit()
