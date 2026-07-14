# app/services/mensagem_service.py
from app.core.database import db
from app.core.whatsapp_api import WhatsAppAPI
from datetime import datetime
import logging
from bson import ObjectId

logger = logging.getLogger(__name__)

class MensagemService:
    
    def __init__(self):
        self.whatsapp_api = WhatsAppAPI()
    
    async def salvar_mensagem_recebida(self, sessao_id: str, contato_id: str, conteudo: str, conteudo_original: str, tipo: str = "texto", file_url: str = None, file_name: str = None, mime_type: str = None, caption: str = None, message_id_zapi: str = None, reference_message_id: str = None, is_reply: bool = False, is_status_reply: bool = False, from_me: bool = False, chat_id: str = None, status: str = None, sender: str = "cliente", direcao: str = "recebida"):
        """Salva mensagem recebida com todos os dados disponíveis"""
        try:
            mensagem = {
                "sessao_id": sessao_id,
                "contato_id": contato_id,
                "direcao": direcao,
                "sender": sender,
                "tipo": tipo,
                "conteudo": conteudo,
                "conteudo_original": conteudo_original,
                "data_hora": datetime.now(),
                "respondida": False,
                "message_id_zapi": message_id_zapi,
                "reference_message_id": reference_message_id,
                "is_reply": is_reply,
                "is_status_reply": is_status_reply,
                "from_me": from_me,
                "chat_id": chat_id,
                "status": status
            }
            
            if file_url:
                mensagem["file_url"] = file_url
            if file_name:
                mensagem["file_name"] = file_name
            if mime_type:
                mensagem["mime_type"] = mime_type
            if caption:
                mensagem["caption"] = caption
            
            result = await db.db.mensagens.insert_one(mensagem)
            logger.info(f"📝 Mensagem salva: {result.inserted_id} - ZAPI: {message_id_zapi} - sender: {sender}")
            return result.inserted_id
        except Exception as e:
            logger.error(f"Erro salvar mensagem: {str(e)}")
            raise
    
    async def salvar_mensagem_enviada(self, sessao_id: str, contato_id: str, conteudo: str, tipo: str = "texto", sender: str = "pepper", atendente: str = None, message_id_zapi: str = None, status: str = None):
        """Salva mensagem enviada (pelo bot ou atendente)"""
        try:
            mensagem = {
                "sessao_id": sessao_id,
                "contato_id": contato_id,
                "direcao": "enviada",
                "sender": sender,
                "tipo": tipo,
                "conteudo": conteudo,
                "data_hora": datetime.now(),
                "respondida": True,
                "message_id_zapi": message_id_zapi,
                "status": status
            }
            
            if atendente:
                mensagem["atendente"] = atendente
            
            result = await db.db.mensagens.insert_one(mensagem)
            logger.info(f"📤 Mensagem enviada salva: {result.inserted_id} - ZAPI: {message_id_zapi}")
            return result.inserted_id
        except Exception as e:
            logger.error(f"Erro salvar mensagem enviada: {str(e)}")
            raise
    
    async def atualizar_status_mensagem(self, message_id_zapi: str, status: str):
        """Atualiza o status de uma mensagem na Z-API"""
        try:
            await db.db.mensagens.update_one(
                {"message_id_zapi": message_id_zapi},
                {"$set": {"status": status}}
            )
            logger.info(f"🔄 Status da mensagem {message_id_zapi} atualizado para: {status}")
        except Exception as e:
            logger.error(f"Erro ao atualizar status: {str(e)}")
            raise
    
    async def salvar_mensagem_com_midia(self, sessao_id: str, contato_id: str, conteudo: str, conteudo_original: str, tipo: str, file_url: str = None, file_name: str = None, mime_type: str = None, caption: str = None, message_id_zapi: str = None, sender: str = "cliente", direcao: str = "recebida"):
        """Salva mensagem com mídia"""
        try:
            mensagem = {
                "sessao_id": sessao_id,
                "contato_id": contato_id,
                "direcao": direcao,
                "sender": sender,
                "tipo": tipo,
                "conteudo": conteudo,
                "conteudo_original": conteudo_original,
                "data_hora": datetime.now(),
                "file_url": file_url,
                "file_name": file_name,
                "mime_type": mime_type,
                "caption": caption or "",
                "respondida": False,
                "message_id_zapi": message_id_zapi
            }
            result = await db.db.mensagens.insert_one(mensagem)
            logger.info(f"📎 Mídia salva: {tipo} - {file_name} - sender: {sender}")
            return result.inserted_id
        except Exception as e:
            logger.error(f"Erro salvar mídia: {str(e)}")
            raise
    
    async def enfileirar_resposta(self, contato_id: str, sessao_id: str, mensagem: str, botoes: list = None, sender: str = "pepper", atendente: str = None):
        try:
            if isinstance(contato_id, ObjectId):
                contato_id = str(contato_id)
            
            contato = await db.db.contatos.find_one({"_id": ObjectId(contato_id)})
            if not contato:
                logger.error(f"Contato não encontrado: {contato_id}")
                return None
            
            if botoes and len(botoes) > 0:
                sucesso = await self.whatsapp_api.send_interactive(contato["telefone"], mensagem, botoes)
            else:
                sucesso = await self.whatsapp_api.send_text(contato["telefone"], mensagem)
            
            if sucesso:
                await self.salvar_mensagem_enviada(
                    sessao_id=sessao_id,
                    contato_id=contato_id,
                    conteudo=mensagem,
                    tipo="texto",
                    sender=sender
                )
                logger.info(f"✅ Resposta enviada com sucesso")
                return True
            else:
                logger.error(f"❌ Falha ao enviar mensagem")
                return False
                
        except Exception as e:
            logger.error(f"Erro enfileirar: {str(e)}")
            raise
