# app/api/curadoria.py
"""
Rotas da esteira de curadoria — é por aqui que a Peper aprende.

O trabalho de quem cura tem que caber em dois minutos por dia. Por isso a
fila devolve pergunta e resposta e mais nada: sem telefone, sem nome, sem
contexto para ler. Aprovar, corrigir ou descartar.

Registrar em main.py:
    from app.api import curadoria
    app.include_router(curadoria.router, prefix="/curadoria", tags=["Curadoria"])
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core import conhecimento
from app.core.database import db
from app.utils.helpers import format_iso_brasilia

router = APIRouter()
logger = logging.getLogger(__name__)


class DecisaoRequest(BaseModel):
    por: str = "Atendente"
    resposta_final: Optional[str] = None
    motivo: Optional[str] = None


@router.get("/fila")
async def listar_fila(
    status: str = Query(default="pendente", description="pendente | bloqueado_preco | aprovada | descartada"),
    limite: int = Query(default=30, ge=1, le=100),
):
    """Os candidatos mais antigos primeiro — fila, não pilha."""
    itens = await db.db.curadoria.find({"status": status}) \
        .sort("criado_em", 1).to_list(length=limite)

    return {
        "sucesso": True,
        "status": status,
        "total": await db.db.curadoria.count_documents({"status": status}),
        "itens": [{
            "id": str(i["_id"]),
            "pergunta": i.get("pergunta"),
            "resposta": i.get("resposta_dada"),
            "origem": i.get("origem"),
            "motivo_bloqueio": i.get("motivo_bloqueio"),
            "criado_em": format_iso_brasilia(i.get("criado_em")),
        } for i in itens],
    }


@router.post("/{candidato_id}/aprovar")
async def aprovar(candidato_id: str, req: DecisaoRequest):
    """
    Aprova como está, ou com `resposta_final` corrigida — que é o caso mais
    comum e o mais valioso: a correção é o ensino de verdade.
    """
    resultado = await conhecimento.aprovar(
        candidato_id, aprovado_por=req.por, resposta_final=req.resposta_final
    )
    if not resultado.get("ok"):
        # Preço é 422, não 500: não é falha do sistema, é regra do negócio.
        if resultado.get("erro") == "contem_preco":
            raise HTTPException(status_code=422, detail=resultado["mensagem"])
        raise HTTPException(status_code=400, detail=resultado.get("erro"))
    return {"sucesso": True}


@router.post("/{candidato_id}/descartar")
async def descartar(candidato_id: str, req: DecisaoRequest):
    await conhecimento.descartar(candidato_id, por=req.por, motivo=req.motivo or "")
    return {"sucesso": True}


@router.get("/base")
async def listar_base(
    ativo: bool = Query(default=True),
    limite: int = Query(default=100, ge=1, le=500),
):
    """O que a Peper está usando hoje. Serve para auditar o que ela sabe."""
    itens = await db.db.conhecimento.find(
        {"ativo": ativo},
        {"pergunta": 1, "resposta": 1, "aprovado_por": 1, "aprovado_em": 1,
         "usos": 1, "revalidar_em": 1, "corrigido": 1},
    ).sort("aprovado_em", -1).to_list(length=limite)

    return {
        "sucesso": True,
        "total": await db.db.conhecimento.count_documents({"ativo": ativo}),
        "itens": [{
            "id": str(i["_id"]),
            "pergunta": i.get("pergunta"),
            "resposta": i.get("resposta"),
            "aprovado_por": i.get("aprovado_por"),
            "aprovado_em": format_iso_brasilia(i.get("aprovado_em")),
            "revalidar_em": format_iso_brasilia(i.get("revalidar_em")),
            "usos": i.get("usos", 0),
            "corrigido": i.get("corrigido", False),
        } for i in itens],
    }


@router.post("/base/{conhecimento_id}/desativar")
async def desativar(conhecimento_id: str, req: DecisaoRequest):
    """Tira de circulação na hora. É o desfazer do sistema."""
    await conhecimento.desativar(conhecimento_id, por=req.por)
    return {"sucesso": True}


@router.post("/revalidar")
async def revalidar():
    """
    Tira de uso o que passou de 90 dias sem revisão.

    Existe porque base de conhecimento envelhece em silêncio: a loja muda o
    processo, a resposta aprovada continua valendo, e ninguém desconfia
    justamente por ela ter sido aprovada.
    """
    quantidade = await conhecimento.vencidos()
    return {"sucesso": True, "desativados": quantidade}


@router.get("/resumo")
async def resumo():
    """Números para o painel, sem varrer mensagem."""
    return {
        "sucesso": True,
        "fila_pendente": await db.db.curadoria.count_documents({"status": "pendente"}),
        "bloqueados_por_preco": await db.db.curadoria.count_documents({"status": "bloqueado_preco"}),
        "aprovados": await db.db.curadoria.count_documents({"status": "aprovada"}),
        "base_ativa": await db.db.conhecimento.count_documents({"ativo": True}),
    }
