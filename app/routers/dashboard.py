import difflib
import json as _json
import os
import re
import unicodedata
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.database import get_db
from app.models.suprimento import Suprimento
from app.models.estabelecimento import Estabelecimento
from app.models.segmento import Segmento
from app.models.unidade import Unidade
from app.models.ia_sugestao_log import IaSugestaoLog
from app.auth import get_viewer, require_admin

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _=Depends(get_viewer)):
    now_local = datetime.now(ZoneInfo("America/Sao_Paulo"))
    month_start_local = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if month_start_local.month == 12:
        next_month_local = month_start_local.replace(
            year=month_start_local.year + 1,
            month=1,
        )
    else:
        next_month_local = month_start_local.replace(month=month_start_local.month + 1)
    month_start = month_start_local.astimezone(timezone.utc).replace(tzinfo=None)
    next_month = next_month_local.astimezone(timezone.utc).replace(tzinfo=None)
    month_filter = (
        Suprimento.created_at >= month_start,
        Suprimento.created_at < next_month,
    )

    total = db.query(func.count(Suprimento.id)).filter(*month_filter).scalar()
    por_status = dict(
        db.query(Suprimento.status, func.count(Suprimento.id))
        .filter(*month_filter)
        .group_by(Suprimento.status)
        .all()
    )
    # Uma entrega também conclui o fluxo, mas preservamos "entregue" para que
    # os dois indicadores do dashboard continuem representando seus conceitos.
    por_status["concluido"] = (
        por_status.get("concluido", 0) + por_status.get("entregue", 0)
    )
    por_prioridade = dict(
        db.query(Suprimento.prioridade, func.count(Suprimento.id))
        .filter(*month_filter)
        .group_by(Suprimento.prioridade)
        .all()
    )
    valor_total = (
        db.query(func.sum(Suprimento.valor_estimado))
        .filter(*month_filter)
        .scalar()
        or 0
    )

    importantes = (
        db.query(Suprimento)
        .filter(*month_filter)
        .filter(Suprimento.status == "pendente")
        .filter(
            or_(
                Suprimento.emergencia == 1,
                Suprimento.prioridade == "urgente",
            )
        )
        .order_by(Suprimento.created_at.desc())
        .limit(5)
        .all()
    )

    month_items = (
        db.query(Suprimento)
        .filter(*month_filter)
        .order_by(Suprimento.created_at.desc())
        .limit(1000)
        .all()
    )
    establishment_ids = {
        item.estabelecimento_id
        for item in (importantes + month_items)
        if item.estabelecimento_id
    }
    establishment_map = {}
    if establishment_ids:
        establishments = (
            db.query(Estabelecimento)
            .filter(Estabelecimento.id.in_(establishment_ids))
            .all()
        )
        establishment_map = {item.id: item.tipo for item in establishments}

    if importantes:
        preview_type = "emergencias"
        preview = [
            {
                "id": item.id,
                "item": item.item_nome or item.titulo,
                "estabelecimento": establishment_map.get(item.estabelecimento_id) or "—",
                "solicitante": item.solicitante,
                "data_solicitacao": item.created_at.isoformat() if item.created_at else None,
                "data_conclusao_necessaria": item.prazo_emergencia or item.data_necessidade,
            }
            for item in importantes
        ]
    else:
        preview_type = "ordens_recentes"
        grouped_orders = {}
        for item in month_items:
            order_code = item.ordem_compra or f"SOL{item.id:04d}"
            if order_code not in grouped_orders:
                if len(grouped_orders) >= 5:
                    continue
                grouped_orders[order_code] = {
                    "id": item.id,
                    "ordem": order_code,
                    "estabelecimentos": [],
                    "solicitantes": [],
                    "data_solicitacao": item.created_at.isoformat() if item.created_at else None,
                }
            group = grouped_orders.get(order_code)
            if not group:
                continue
            establishment = establishment_map.get(item.estabelecimento_id)
            if establishment and establishment not in group["estabelecimentos"]:
                group["estabelecimentos"].append(establishment)
            if item.solicitante and item.solicitante not in group["solicitantes"]:
                group["solicitantes"].append(item.solicitante)
        preview = list(grouped_orders.values())

    return {
        "total": total,
        "por_status": por_status,
        "por_prioridade": por_prioridade,
        "valor_total_estimado": round(valor_total, 2),
        "mes_referencia": month_start_local.strftime("%Y-%m"),
        "preview_tipo": preview_type,
        "preview": preview,
    }


@router.get("/segmentos")
def segmentos(db: Session = Depends(get_db), _=Depends(get_viewer)):
    from_suprimentos = {r[0] for r in db.query(Suprimento.categoria).distinct().all() if r[0]}
    from_segmentos = {r[0] for r in db.query(Segmento.nome).filter(Segmento.ativo == True).all()}
    return sorted(from_suprimentos | from_segmentos)


class SegmentoCreate(BaseModel):
    nome: str


@router.get("/segmentos/list")
def listar_segmentos(db: Session = Depends(get_db), _=Depends(get_viewer)):
    rows = db.query(Segmento).filter(Segmento.ativo == True).order_by(Segmento.nome).all()
    return [{"id": r.id, "nome": r.nome} for r in rows]


_HF_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
_FUZZY_THRESHOLD = 0.70
_AI_THRESHOLD = 0.72


class SimilarityCheckRequest(BaseModel):
    nome: str
    candidates: list[str]


@router.post("/check-similar")
async def check_similar(data: SimilarityCheckRequest):
    nome = data.nome.strip().lower()
    candidates = [c.strip() for c in data.candidates if c.strip()]
    if not nome or not candidates:
        return {"conflict": False, "similar_to": None, "score": None, "method": None}

    # Step 1: fuzzy ratio via difflib (handles prefixes, plurals, derivations)
    for cand in candidates:
        ratio = difflib.SequenceMatcher(None, nome, cand.lower()).ratio()
        if ratio >= _FUZZY_THRESHOLD:
            return {"conflict": True, "similar_to": cand, "score": round(ratio, 3), "method": "fuzzy"}

    # Step 2: semantic similarity via Hugging Face free inference API
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.post(
                f"https://api-inference.huggingface.co/models/{_HF_MODEL}",
                json={"inputs": {"source_sentence": nome, "sentences": [c.lower() for c in candidates]}},
            )
            if resp.status_code == 200:
                scores = resp.json()
                if isinstance(scores, list) and scores:
                    max_score = max(scores)
                    max_idx = scores.index(max_score)
                    if max_score >= _AI_THRESHOLD:
                        return {"conflict": True, "similar_to": candidates[max_idx], "score": round(max_score, 3), "method": "ai"}
    except Exception:
        pass

    return {"conflict": False, "similar_to": None, "score": None, "method": None}


# ── Validação avançada de segmentos (4 casos) ──────────────────────────────

def _normalize_term(text: str) -> str:
    """Remove acentos e converte para minúsculas."""
    return "".join(
        c for c in unicodedata.normalize("NFD", text.lower().strip())
        if unicodedata.category(c) != "Mn"
    )


class SimilarSegmentoRequest(BaseModel):
    nome: str
    candidates: list[str]
    stakeholder_id: int | None = None


@router.post("/check-similar-segmento")
async def check_similar_segmento(data: SimilarSegmentoRequest):
    nome = data.nome.strip()
    nome_norm = _normalize_term(nome)
    pairs = [(c.strip(), _normalize_term(c)) for c in data.candidates if c.strip()]

    if not nome_norm or not pairs:
        return {"conflict_type": None}

    # Caso 1 — correspondência exata (ignorando acentos e capitalização)
    for cand, cand_norm in pairs:
        if nome_norm == cand_norm:
            return {"conflict_type": "exact", "similar_to": cand}

    # Caso 2 — palavra composta: candidato aparece como palavra inteira dentro do novo termo
    for cand, cand_norm in pairs:
        pattern = r"(?<![a-z])" + re.escape(cand_norm) + r"(?![a-z])"
        if re.search(pattern, nome_norm) and nome_norm != cand_norm:
            return {"conflict_type": "composed", "similar_to": cand}

    # Caso 3 — variação morfológica (fuzzy >= 0.72 na forma normalizada)
    best_ratio, best_cand = 0.0, None
    for cand, cand_norm in pairs:
        ratio = difflib.SequenceMatcher(None, nome_norm, cand_norm).ratio()
        if ratio > best_ratio:
            best_ratio, best_cand = ratio, cand
    if best_ratio >= 0.72:
        return {"conflict_type": "variation", "similar_to": best_cand, "score": round(best_ratio, 3)}

    # Caso 4 — verificação semântica via IA (Google Gemini — gratuito)
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if gemini_key:
        cand_list = [c for c, _ in pairs]
        prompt = (
            "Você é especialista em categorização de produtos para um sistema de gestão de suprimentos brasileiro.\n"
            "Dado uma lista de termos já cadastrados e um novo termo digitado pelo usuário, determine se o novo termo "
            "representa o mesmo conceito que algum termo existente.\n\n"
            "Considere: erros ortográficos/digitação, gírias e dialetos de qualquer região do Brasil, termos em outros "
            "idiomas (inglês, espanhol etc.) com mesmo significado, variações de plural/diminutivo/aumentativo, siglas.\n\n"
            f"Termos existentes: {_json.dumps(cand_list, ensure_ascii=False)}\n"
            f'Novo termo: "{nome}"\n\n'
            'Se o novo termo É coberto por algum existente, responda com JSON: '
            '{"match": true, "matched_term": "...", "explanation": "explicação curta em português (max 120 chars)"}\n'
            'Se NÃO for coberto, responda com JSON: {"match": false}\n'
            "Responda SOMENTE com JSON, sem texto adicional."
        )
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}",
                    headers={"content-type": "application/json"},
                    json={"contents": [{"parts": [{"text": prompt}]}]},
                )
                if resp.status_code == 200:
                    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                    # remove blocos de markdown se o modelo os incluir
                    text = re.sub(r"^```[a-z]*\n?", "", text).rstrip("` \n")
                    ai_data = _json.loads(text)
                    if ai_data.get("match"):
                        return {
                            "conflict_type": "ai",
                            "similar_to": ai_data.get("matched_term"),
                            "explanation": ai_data.get("explanation"),
                        }
        except Exception:
            pass

    return {"conflict_type": None}


class IaSugestaoLogCreate(BaseModel):
    tipo: str
    stakeholder_id: int | None = None
    termo_stakeholder: str
    sugestao_ia: str | None = None
    aprovacao_stakeholder: bool | None = None
    termo_final: str | None = None


@router.post("/ia-sugestao-log", status_code=201)
def registrar_ia_sugestao(data: IaSugestaoLogCreate, db: Session = Depends(get_db), _=Depends(get_viewer)):
    log = IaSugestaoLog(
        tipo=data.tipo,
        stakeholder_id=data.stakeholder_id,
        termo_stakeholder=data.termo_stakeholder,
        sugestao_ia=data.sugestao_ia,
        aprovacao_stakeholder=data.aprovacao_stakeholder,
        termo_final=data.termo_final,
        data_hora=datetime.now(timezone.utc),
    )
    db.add(log)
    db.commit()
    return {"ok": True}


@router.post("/segmentos", status_code=201)
def criar_segmento(data: SegmentoCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    nome = data.nome.strip()
    if not nome:
        raise HTTPException(400, "Informe o nome do segmento")
    if db.query(Segmento).filter(Segmento.nome.ilike(nome), Segmento.ativo == True).first():
        raise HTTPException(400, "Segmento já cadastrado")
    seg = Segmento(nome=nome)
    db.add(seg)
    db.commit()
    db.refresh(seg)
    return {"id": seg.id, "nome": seg.nome}


@router.delete("/segmentos/{id}", status_code=204)
def remover_segmento(id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    seg = db.query(Segmento).filter(Segmento.id == id).first()
    if not seg:
        raise HTTPException(404, "Segmento não encontrado")
    seg.ativo = False
    db.commit()


class UnidadeCreate(BaseModel):
    sigla: str
    nome: str


@router.get("/unidades/list")
def listar_unidades(db: Session = Depends(get_db), _=Depends(get_viewer)):
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
