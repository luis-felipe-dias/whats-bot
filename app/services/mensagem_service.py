# app/services/mensagem_service.py
from app.core.database import db
from datetime import datetime
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)

class MensagemService:
    
    async def salvar_mensagem_recebida(self, sessao_id: str, contato_id: str, conteudo: str, conteudo_original: str, tipo: str = "texto"):
        """Salva mensagem recebida no banco"""
        try:
            mensagem = {
                "sessao_id": sessao_id,
                "contato_id": contato_id,
                "direcao": "recebida",
                "tipo": tipo,
                "conteudo": conteudo,
                "conteudo_original": conteudo_original,
                "data_hora": datetime.now(),
                "metadata": {}
            }
            
            result = await db.db.mensagens.insert_one(mensagem)
            
            # Registrar evento
            await db.db.eventos.insert_one({
                "tipo": "mensagem_recebida",
                "contato_id": contato_id,
                "sessao_id": sessao_id,
                "dados": {"mensagem_id": str(result.inserted_id)},
                "data_hora": datetime.now()
            })
            
            logger.info(f"Mensagem recebida salva: {result.inserted_id}")
            return result.inserted_id
            
        except Exception as e:
            logger.error(f"Erro ao salvar mensagem recebida: {str(e)}")
            raise
    
    async def enfileirar_resposta(self, contato_id: str, sessao_id: str, mensagem: str):
        """Enfileira mensagem para envio"""
        try:
            fila_item = {
                "contato_id": contato_id,
                "sessao_id": sessao_id,
                "conteudo": mensagem,
                "status": "pendente",
                "data_criacao": datetime.now(),
                "tentativas": 0
            }
            
            result = await db.db.fila_envio.insert_one(fila_item)
            logger.info(f"Mensagem enfileirada: {result.inserted_id}")
            return result.inserted_id
            
        except Exception as e:
            logger.error(f"Erro ao enfileirar resposta: {str(e)}")
            raise
    
    async def salvar_avaliacao(self, sessao_id: str, contato_id: str, nota: int):
        """Salva avaliação do atendimento"""
        try:
            avaliacao = {
                "sessao_id": sessao_id,
                "contato_id": contato_id,
                "nota": nota,
                "data_hora": datetime.now()
            }
            
            result = await db.db.avaliacoes.insert_one(avaliacao)
            
            # Registrar evento
            await db.db.eventos.insert_one({
                "tipo": "avaliacao_recebida",
                "contato_id": contato_id,
                "sessao_id": sessao_id,
                "dados": {"nota": nota},
                "data_hora": datetime.now()
            })
            
            logger.info(f"Avaliação salva: {nota} estrelas")
            return result.inserted_id
            
        except Exception as e:
            logger.error(f"Erro ao salvar avaliação: {str(e)}")
            raise