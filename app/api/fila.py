# app/api/fila.py - Endpoints para gerenciamento de filas
from fastapi import APIRouter, HTTPException
from app.core.database import db
from bson import ObjectId
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/fila/envio")
async def ver_fila_envio():
    """Verifica o status da fila de envio de mensagens"""
    try:
        pendentes = await db.db.fila_envio.count_documents({"status": "pendente"})
        enviados = await db.db.fila_envio.count_documents({"status": "enviado"})
        erros = await db.db.fila_envio.count_documents({"status": "erro"})
        
        # Buscar últimos 10 itens pendentes
        ultimos = await db.db.fila_envio.find({"status": "pendente"}).sort("data_criacao", -1).limit(10).to_list(length=10)
        
        return {
            "sucesso": True,
            "fila": {
                "pendentes": pendentes,
                "enviados": enviados,
                "erros": erros,
                "ultimos_pendentes": [
                    {
                        "id": str(item["_id"]),
                        "conteudo": item.get("conteudo", "")[:50],
                        "data_criacao": item.get("data_criacao").isoformat() if item.get("data_criacao") else None
                    }
                    for item in ultimos
                ]
            }
        }
    except Exception as e:
        logger.error(f"Erro ao verificar fila: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/fila/humana")
async def ver_fila_humana():
    """Verifica a fila de atendimento humano"""
    try:
        # Buscar tickets pendentes
        tickets = await db.db.fila_humana.find({"status": "pendente"}).sort("prioridade", -1).sort("data_criacao", 1).to_list(length=50)
        
        resultado = []
        for ticket in tickets:
            contato = await db.db.contatos.find_one({"_id": ObjectId(ticket["contato_id"])})
            sessao = await db.db.sessoes.find_one({"_id": ObjectId(ticket["sessao_id"])})
            
            resultado.append({
                "id": str(ticket["_id"]),
                "tipo": ticket.get("tipo", "atendimento"),
                "cliente": sessao.get("cliente_nome") if sessao else (contato.get("nome") if contato else "Desconhecido"),
                "telefone": contato.get("telefone") if contato else "Desconhecido",
                "prioridade": ticket.get("prioridade", 0),
                "data_criacao": ticket.get("data_criacao").isoformat() if ticket.get("data_criacao") else None,
                "sessao_id": str(ticket["sessao_id"]),
                "status": ticket.get("status")
            })
        
        total = await db.db.fila_humana.count_documents({"status": "pendente"})
        
        return {
            "sucesso": True,
            "fila_humana": {
                "total": total,
                "tickets": resultado
            }
        }
    except Exception as e:
        logger.error(f"Erro ao verificar fila humana: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
