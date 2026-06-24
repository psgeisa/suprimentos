from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, case, asc

from app.database import get_db
from app.models.suprimento import Suprimento
from app.models.categoria import Categoria
from app.models.unidade import Unidade
from app.schemas.suprimento import SuprimentoOut
from app.auth import get_current_user, require_admin

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _=Depends(get_current_user)):
    total = db.query(func.count(Suprimento.id)).scalar()
    por_status = dict(
        db.query(Suprimento.status, func.count(Suprimento.id))
        .group_by(Suprimento.status)
        .all()
    )
    por_prioridade = dict(
        db.query(Suprimento.prioridade, func.count(Suprimento.id))
        .group_by(Suprimento.prioridade)
        .all()
    )
    valor_total = db.query(func.sum(Suprimento.valor_estimado)).scalar() or 0
    _prio_order = case(
        (Suprimento.prioridade == 'urgente', 0),
        (Suprimento.prioridade == 'alta', 1),
        else_=2,
    )
    importantes = (
        db.query(Suprimento)
        .filter(Suprimento.prioridade.in_(['urgente', 'alta']))
        .filter(Suprimento.status.notin_(['concluido', 'cancelado']))
        .order_by(_prio_order, Suprimento.created_at.desc())
        .limit(5)
        .all()
    )
    recentes = importantes
    return {
        "total": total,
        "por_status": por_status,
        "por_prioridade": por_prioridade,
        "valor_total_estimado": round(valor_total, 2),
        "recentes": [SuprimentoOut.model_validate(r) for r in recentes],
    }


@router.get("/categorias")
def categorias(db: Session = Depends(get_db), _=Depends(get_current_user)):
    from_suprimentos = {r[0] for r in db.query(Suprimento.categoria).distinct().all() if r[0]}
    from_categorias = {r[0] for r in db.query(Categoria.nome).filter(Categoria.ativo == True).all()}
    return sorted(from_suprimentos | from_categorias)


class CategoriaCreate(BaseModel):
    nome: str


@router.get("/categorias/list")
def listar_categorias(db: Session = Depends(get_db), _=Depends(get_current_user)):
    rows = db.query(Categoria).filter(Categoria.ativo == True).order_by(Categoria.nome).all()
    return [{"id": r.id, "nome": r.nome} for r in rows]


@router.post("/categorias", status_code=201)
def criar_categoria(data: CategoriaCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    nome = data.nome.strip()
    if not nome:
        raise HTTPException(400, "Informe o nome do segmento")
    if db.query(Categoria).filter(Categoria.nome.ilike(nome), Categoria.ativo == True).first():
        raise HTTPException(400, "Segmento já cadastrado")
    cat = Categoria(nome=nome)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return {"id": cat.id, "nome": cat.nome}


@router.delete("/categorias/{id}", status_code=204)
def remover_categoria(id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    cat = db.query(Categoria).filter(Categoria.id == id).first()
    if not cat:
        raise HTTPException(404, "Segmento não encontrado")
    cat.ativo = False
    db.commit()


class UnidadeCreate(BaseModel):
    sigla: str
    nome: str


@router.get("/unidades/list")
def listar_unidades(db: Session = Depends(get_db), _=Depends(get_current_user)):
    rows = db.query(Unidade).filter(Unidade.ativo == True).order_by(Unidade.nome).all()
    return [{"id": r.id, "sigla": r.sigla, "nome": r.nome} for r in rows]


@router.post("/unidades", status_code=201)
def criar_unidade(data: UnidadeCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    sigla = data.sigla.strip()
    nome = data.nome.strip()
    if not sigla or not nome:
        raise HTTPException(400, "Informe sigla e nome")
    if db.query(Unidade).filter(Unidade.sigla == sigla, Unidade.ativo == True).first():
        raise HTTPException(400, "Sigla já cadastrada")
    u = Unidade(sigla=sigla, nome=nome)
    db.add(u)
    db.commit()
    db.refresh(u)
    return {"id": u.id, "sigla": u.sigla, "nome": u.nome}


@router.delete("/unidades/{id}", status_code=204)
def remover_unidade(id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    u = db.query(Unidade).filter(Unidade.id == id).first()
    if not u:
        raise HTTPException(404, "Unidade não encontrada")
    u.ativo = False
    db.commit()
