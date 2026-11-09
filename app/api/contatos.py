# app/api/contatos.py - Endpoints para gerenciamento de contatos
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.core.database import db
from app.services.contato_service import ContatoService
from app.utils.helpers import now_utc
from bson import ObjectId
import re
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class AtualizarContatoRequest(BaseModel):
    nome: Optional[str] = None
    tags: Optional[list[str]] = None
    observacoes: Optional[str] = None

@router.get("/contatos")
async def listar_contatos(busca: Optional[str] = None, limit: int = 200, apenas_grupos: bool = False):
    """
    Lista contatos, com busca por nome/telefone e filtro de grupos.
    Antes ignorava completamente busca/limit/apenas_grupos (o painel já
    mandava esses parâmetros há tempos, mas essa rota nunca os lia) e
    nunca devolvia is_group - por isso o filtro "Grupos" do painel nunca
    funcionou e a busca não filtrava nada.
    """
    try:
        query: dict = {}
        if apenas_grupos:
            query["is_group"] = True
        if busca and busca.strip():
            termo = re.escape(busca.strip())
            query["$or"] = [
                {"nome": {"$regex": termo, "$options": "i"}},
                {"telefone": {"$regex": termo, "$options": "i"}}
            ]

        limit = max(1, min(limit or 200, 500))
        contatos = await db.db.contatos.find(query).sort("ultima_interacao", -1).to_list(length=limit)
        resultado = []
        for contato in contatos:
            resultado.append({
                "id": str(contato["_id"]),
                "nome": contato.get("nome", "Desconhecido"),
                "telefone": contato.get("telefone"),
                "nome_personalizado": contato.get("nome_personalizado", False),
                "is_group": contato.get("is_group", False),
                "data_criacao": contato.get("data_criacao").isoformat() if contato.get("data_criacao") else None,
                "ultima_interacao": contato.get("ultima_interacao").isoformat() if contato.get("ultima_interacao") else None,
                "tags": contato.get("tags", [])
            })
        return {"sucesso": True, "contatos": resultado}
    except Exception as e:
        logger.error(f"Erro ao listar contatos: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/contatos/{contato_id}")
async def buscar_contato(contato_id: str):
    """Busca um contato específico pelo ID"""
    try:
        contato = await db.db.contatos.find_one({"_id": ObjectId(contato_id)})
        if not contato:
            raise HTTPException(status_code=404, detail="Contato não encontrado")
        
        return {
            "sucesso": True,
            "contato": {
                "id": str(contato["_id"]),
                "nome": contato.get("nome", "Desconhecido"),
                "telefone": contato.get("telefone"),
                "nome_personalizado": contato.get("nome_personalizado", False),
                "data_criacao": contato.get("data_criacao").isoformat() if contato.get("data_criacao") else None,
                "ultima_interacao": contato.get("ultima_interacao").isoformat() if contato.get("ultima_interacao") else None,
                "tags": contato.get("tags", []),
                "observacoes": contato.get("observacoes", "")
            }
        }
    except Exception as e:
        logger.error(f"Erro ao buscar contato: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/contatos/{contato_id}")
async def atualizar_contato(contato_id: str, request: AtualizarContatoRequest):
    """
    Corrige nome/tags/observações de um contato pelo painel. Sem isso não
    havia como consertar um nome errado (ex: quando o WhatsApp não manda o
    chatName na primeira mensagem e o contato fica salvo com o telefone
    como nome).
    """
    try:
        contato = await db.db.contatos.find_one({"_id": ObjectId(contato_id)})
        if not contato:
            raise HTTPException(status_code=404, detail="Contato não encontrado")

        dados = {}
        if request.nome is not None and request.nome.strip():
            dados["nome"] = request.nome.strip()
            dados["nome_personalizado"] = True
        if request.tags is not None:
            dados["tags"] = request.tags
        if request.observacoes is not None:
            dados["observacoes"] = request.observacoes

        if not dados:
            raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")

        dados["data_atualizacao"] = now_utc()
        await db.db.contatos.update_one({"_id": ObjectId(contato_id)}, {"$set": dados})

        contato_atualizado = await db.db.contatos.find_one({"_id": ObjectId(contato_id)})
        return {
            "sucesso": True,
            "contato": {
                "id": str(contato_atualizado["_id"]),
                "nome": contato_atualizado.get("nome"),
                "telefone": contato_atualizado.get("telefone"),
                "nome_personalizado": contato_atualizado.get("nome_personalizado", False),
                "tags": contato_atualizado.get("tags", []),
                "observacoes": contato_atualizado.get("observacoes", "")
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao atualizar contato: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/grupos")
async def listar_grupos():
    """Lista os contatos marcados como grupo (tag 'grupo')"""
    try:
        grupos = await db.db.contatos.find({"is_group": True}).sort("data_criacao", -1).to_list(length=200)
        resultado = [{
            "id": str(g["_id"]),
            "nome": g.get("nome", "Grupo"),
            "identificador": g.get("telefone"),
            "tags": g.get("tags", []),
            "ultima_interacao": g.get("ultima_interacao").isoformat() if g.get("ultima_interacao") else None
        } for g in grupos]
        return {"sucesso": True, "grupos": resultado}
    except Exception as e:
        logger.error(f"Erro ao listar grupos: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
