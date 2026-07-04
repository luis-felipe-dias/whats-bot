# app/services/mensagem_service.py
from app.core.database import db
from app.core.whatsapp_api import WhatsAppAPI
from datetime import datetime, timezone
import logging
from bson import ObjectId

logger = logging.getLogger(__name__)

class MensagemService:
    
    def __init__(self):
        self.whatsapp_api = WhatsAppAPI()
    
    def _now_utc(self):
        return datetime.now(timezone.utc)
    
    async def salvar_mensagem_recebida(self, sessao_id: str, contato_id: str, conteudo: str, conteudo_original: str, tipo: str = "texto"):
        try:
            mensagem = {
                "sessao_id": sessao_id,
                "contato_id": contato_id,
                "direcao": "recebida",
                "tipo": tipo,
                "conteudo": conteudo,
                "conteudo_original": conteudo_original,
                "data_hora": self._now_utc(),
                "respondida": False
            }
            result = await db.db.mensagens.insert_one(mensagem)
            logger.info(f"📝 Mensagem salva: {result.inserted_id}")
            return result.inserted_id
        except Exception as e:
            logger.error(f"Erro salvar mensagem: {str(e)}")
            raise
    
    async def salvar_mensagem_com_midia(self, sessao_id: str, contato_id: str, conteudo: str, conteudo_original: str, tipo: str, file_url: str = None, file_name: str = None, mime_type: str = None, caption: str = None):
        try:
            mensagem = {
                "sessao_id": sessao_id,
                "contato_id": contato_id,
                "direcao": "recebida",
                "tipo": tipo,
                "conteudo": conteudo,
                "conteudo_original": conteudo_original,
                "data_hora": self._now_utc(),
                "file_name": file_name,
                "mime_type": mime_type,
                "caption": caption or "",
                "respondida": False
            }
            
            if file_url:
                mensagem["file_url"] = file_url
            else:
                mensagem["file_url"] = None
                mensagem["status"] = "url_pendente"
            
            result = await db.db.mensagens.insert_one(mensagem)
            logger.info(f"📎 Mídia salva: {tipo} - {file_name}")
            return result.inserted_id
        except Exception as e:
            logger.error(f"Erro salvar mídia: {str(e)}")
            raise
    
    async def enfileirar_resposta(self, contato_id: str, sessao_id: str, mensagem: str, botoes: list = None):
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
                mensagem_enviada = {
                    "sessao_id": sessao_id,
                    "contato_id": contato_id,
                    "direcao": "enviada",
                    "sender": "pepper",
                    "tipo": "texto",
                    "conteudo": mensagem,
                    "data_hora": self._now_utc(),
                    "respondida": True
                }
                await db.db.mensagens.insert_one(mensagem_enviada)
                logger.info(f"✅ Resposta enviada com sucesso")
                return True
            else:
                logger.error(f"❌ Falha ao enviar mensagem")
                return False
                
        except Exception as e:
            logger.error(f"Erro enfileirar: {str(e)}")
            raise
