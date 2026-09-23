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

    async def fechar_tickets_da_sessao(self, sessao_id: str, motivo: str = "resolvido"):
        """
        Fecha (tira de 'pendente') todos os tickets abertos de uma sessão.
        Sem isso, todo ticket criado ficava 'pendente' pra sempre - mesmo
        depois do cliente cancelar ou do atendente finalizar - poluindo a
        fila humana no painel com tickets fantasma.
        """
        try:
            resultado = await db.db.fila_humana.update_many(
                {"sessao_id": sessao_id, "status": "pendente"},
                {"$set": {"status": motivo, "data_fim": now_utc()}}
            )
            if resultado.modified_count:
                logger.info(f"🗂️ {resultado.modified_count} ticket(s) da sessão {sessao_id} fechado(s) como '{motivo}'")
            return resultado.modified_count
        except Exception as e:
            logger.error(f"Erro ao fechar tickets da sessão: {str(e)}")
            return 0