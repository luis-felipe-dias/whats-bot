# app/api/contatos.py - Endpoints para gerenciamento de contatos
from fastapi import APIRouter, HTTPException
from app.core.database import db
from bson import ObjectId
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/contatos")
async def listar_contatos():
    """Lista todos os contatos"""
    try:
        contatos = await db.db.contatos.find().sort("data_criacao", -1).to_list(length=100)
        resultado = []
        for contato in contatos:
            resultado.append({
                "id": str(contato["_id"]),
                "nome": contato.get("nome", "Desconhecido"),
                "telefone": contato.get("telefone"),
                "nome_personalizado": contato.get("nome_personalizado", False),
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
