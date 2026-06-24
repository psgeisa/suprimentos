import secrets
import string
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserOut
from app.auth import hash_password, require_admin

router = APIRouter(prefix="/api/usuarios", tags=["usuarios"])


@router.get("", response_model=List[UserOut])
def listar(db: Session = Depends(get_db), _=Depends(require_admin)):
    return db.query(User).order_by(User.criado_em.desc()).all()


@router.post("", response_model=UserOut, status_code=201)
def criar(data: UserCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(400, "Email já cadastrado")
    if data.role not in ("admin", "solicitante", "compras"):
        raise HTTPException(400, "Role inválido. Use: admin, solicitante ou compras")
    user = User(
        nome=data.nome,
        email=data.email,
        senha_hash=hash_password(data.senha),
        role=data.role,
        time=data.time,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{id}", response_model=UserOut)
def atualizar(id: int, data: UserUpdate, db: Session = Depends(get_db), _=Depends(require_admin)):
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(404, "Usuário não encontrado")
    if data.role and data.role not in ("admin", "solicitante", "compras"):
        raise HTTPException(400, "Role inválido. Use: admin, solicitante ou compras")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{id}", status_code=204)
def desativar(id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(404, "Usuário não encontrado")
    user.ativo = False
    db.commit()


@router.post("/{id}/reset-senha")
def reset_senha(id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(404, "Usuário não encontrado")
    chars = string.ascii_letters + string.digits
    nova_senha = "".join(secrets.choice(chars) for _ in range(12))
    user.senha_hash = hash_password(nova_senha)
    db.commit()
    return {"senha_temporaria": nova_senha}
