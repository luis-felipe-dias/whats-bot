# app/api/palavras.py
"""
Lista de palavras proibidas pelo painel.

A lista nasce incompleta de propósito — o Pablo disse que ainda não definiu
todas. O valor aqui não é a lista inicial, é o ciclo: a Peper escapa com um
termo, ele vê na conversa, cadastra em dez segundos e aquilo não acontece
mais. Sem deploy, sem esperar por mim.

AS TRÊS AÇÕES, E A DIFERENÇA ENTRE ELAS
  bloquear -> a resposta não sai; a conversa vira equipe. Use para o que
              causa prejuízo: desconto que não existe, dado interno,
              urgência inventada.
  trocar   -> a palavra é substituída em silêncio. Use para tom: "prezado
              cliente" virando "oi".
  avisar   -> a resposta sai e fica o registro no log. Use quando você
              suspeita mas não quer travar o atendimento.

Começar tudo em "bloquear" parece seguro e não é: transfere conversa demais
e a equipe para de confiar na Peper. Tom é "trocar"; dinheiro é "bloquear".

Registrar em main.py:
    from app.api import palavras
    app.include_router(palavras.router, prefix="/palavras", tags=["Palavras"])
"""

import logging
from typing import List, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core import palavras_proibidas
from app.core.database import db

router = APIRouter()
logger = logging.getLogger(__name__)

ACOES = ("bloquear", "avisar", "trocar")
COLECAO = palavras_proibidas.COLECAO


class RegraRequest(BaseModel):
    termo: str
    acao: str = "avisar"
    troca_por: Optional[str] = None
    motivo: Optional[str] = None
    ativo: bool = True
    por: str = "Atendente"


def _validar(req: RegraRequest) -> None:
    if not (req.termo or "").strip():
        raise HTTPException(400, "Termo vazio.")
    if req.acao not in ACOES:
        raise HTTPException(400, f"Ação precisa ser uma de: {', '.join(ACOES)}.")
    # "trocar" sem substituto é uma deleção silenciosa de palavra. Às vezes
    # é o que se quer ("informamos que"), então permito — mas só quando o
    # campo vem explicitamente vazio, não quando foi esquecido.
    if req.acao == "trocar" and req.troca_por is None:
        raise HTTPException(400, 'Ação "trocar" precisa de troca_por (pode ser vazio).')


def _oid(valor: str) -> ObjectId:
    try:
        return ObjectId(valor)
    except (InvalidId, TypeError):
        raise HTTPException(400, "Id inválido.")


@router.get("")
async def listar():
    """
    Tudo que o filtro usa agora: as regras de fábrica e as cadastradas.
    As de fábrica não têm id — para desativar uma delas, cadastre o mesmo
    termo, que sobrescreve pelo nome.
    """
    cadastradas = await db.db[COLECAO].find().sort("termo", 1).to_list(length=500)
    nomes = {str(d.get("termo", "")).lower() for d in cadastradas}

    return {
        "sucesso": True,
        "acoes": list(ACOES),
        "padrao": [
            {**r, "id": None, "ativo": True, "sobrescrita": r["termo"].lower() in nomes}
            for r in palavras_proibidas.PADRAO
        ],
        "regras": [{
            "id": str(d["_id"]),
            "termo": d.get("termo"),
            "acao": d.get("acao", "avisar"),
            "troca_por": d.get("troca_por"),
            "motivo": d.get("motivo"),
            "ativo": d.get("ativo", True),
        } for d in cadastradas],
        # O bloco exato que entra no prompt da Peper agora.
        "prompt": await palavras_proibidas.para_prompt(),
    }


@router.post("")
async def criar(req: RegraRequest):
    _validar(req)
    termo = req.termo.strip()

    if await db.db[COLECAO].find_one({"termo": {"$regex": f"^{termo}$", "$options": "i"}}):
        raise HTTPException(409, f'"{termo}" já está na lista.')

    doc = {
        "termo": termo,
        "acao": req.acao,
        "troca_por": req.troca_por,
        "motivo": (req.motivo or "").strip() or None,
        "ativo": req.ativo,
        "criado_por": req.por,
    }
    r = await db.db[COLECAO].insert_one(doc)
    palavras_proibidas.invalidar_cache()
    logger.info('Palavra "%s" (%s) cadastrada por %s.', termo, req.acao, req.por)
    return {"sucesso": True, "id": str(r.inserted_id)}


@router.put("/{regra_id}")
async def atualizar(regra_id: str, req: RegraRequest):
    _validar(req)
    r = await db.db[COLECAO].update_one(
        {"_id": _oid(regra_id)},
        {"$set": {
            "termo": req.termo.strip(),
            "acao": req.acao,
            "troca_por": req.troca_por,
            "motivo": (req.motivo or "").strip() or None,
            "ativo": req.ativo,
            "atualizado_por": req.por,
        }},
    )
    if not r.matched_count:
        raise HTTPException(404, "Regra não encontrada.")
    palavras_proibidas.invalidar_cache()
    return {"sucesso": True}


@router.delete("/{regra_id}")
async def remover(regra_id: str):
    r = await db.db[COLECAO].delete_one({"_id": _oid(regra_id)})
    if not r.deleted_count:
        raise HTTPException(404, "Regra não encontrada.")
    palavras_proibidas.invalidar_cache()
    return {"sucesso": True}


class TesteRequest(BaseModel):
    texto: str


@router.post("/testar")
async def testar(req: TesteRequest):
    """
    Cola um texto e vê o que o filtro faria com ele. Vale mais que a lista:
    é onde se descobre que "\\bmargem\\b" também pega "margem da página".
    """
    return {"sucesso": True, **(await palavras_proibidas.verificar(req.texto))}
