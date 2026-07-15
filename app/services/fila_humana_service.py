# app/services/fila_humana_service.py
from app.core.database import db
from datetime import datetime
from app.utils.helpers import now_utc
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)

class FilaHumanaService:
    
    async def criar_ticket(self, sessao_id: str, contato_id: str, tipo: str):
        """Cria um ticket na fila humana"""
        try:
            ticket = {
                "sessao_id": sessao_id,
                "contato_id": contato_id,
                "tipo": tipo,  # impressao, troca, reclamacao, curriculo, atendimento
                "status": "pendente",
                "dados": {},
                "prioridade": 0,
                "data_criacao": now_utc()
            }
            
            result = await db.db.fila_humana.insert_one(ticket)
            
            # Registrar evento
            await db.db.eventos.insert_one({
                "tipo": "atendimento_humano",
                "contato_id": contato_id,
                "sessao_id": sessao_id,
                "dados": {"tipo": tipo},
                "data_hora": now_utc()
            })
            
            logger.info(f"Ticket criado na fila humana: {result.inserted_id} - Tipo: {tipo}")
            return result.inserted_id
            
        except Exception as e:
            logger.error(f"Erro ao criar ticket: {str(e)}")
            raise
    
    async def cancelar_ticket(self, ticket_id: str):
        """Cancela um ticket da fila humana"""
        try:
            await db.db.fila_humana.update_one(
                {"_id": ObjectId(ticket_id)},
                {"$set": {
                    "status": "cancelado",
                    "data_fim": now_utc()
                }}
            )
            
            logger.info(f"Ticket cancelado: {ticket_id}")
            
        except Exception as e:
            logger.error(f"Erro ao cancelar ticket: {str(e)}")
            raise