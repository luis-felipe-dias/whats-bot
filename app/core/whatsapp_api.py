# app/core/whatsapp_api.py
import httpx
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class WhatsAppAPI:
    def __init__(self):
        self.instance_id = settings.zapi_instance_id
        self.instance_token = settings.zapi_token
        self.client_token = settings.zapi_client_token
        self.base_url = settings.zapi_url
        self.timeout = 30.0
        
    async def send_text(self, telefone: str, texto: str) -> bool:
        """Envia mensagem de texto via Z-API"""
        try:
            telefone_clean = self._clean_phone_number(telefone)
            
            url = f"{self.base_url}/instances/{self.instance_id}/token/{self.instance_token}/send-text"
            
            payload = {
                "phone": telefone_clean,
                "message": texto,
                "delayMessage": 15
            }
            
            headers = {
                'Client-Token': self.client_token,
                'Content-Type': 'application/json'
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                
                if response.status_code == 200:
                    logger.info(f"✅ Mensagem enviada para {telefone_clean}")
                    return True
                else:
                    logger.error(f"❌ Erro Z-API: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Erro ao enviar mensagem: {str(e)}")
            return False
    
    async def get_contact_info(self, telefone: str) -> dict:
        """Busca informações do contato"""
        return {}  # Implementar depois
    
    async def save_contact(self, telefone: str, nome: str) -> bool:
        """Salva contato no WhatsApp"""
        return True  # Implementar depois
    
    def _clean_phone_number(self, telefone: str) -> str:
        """Limpa o número de telefone"""
        cleaned = ''.join(filter(str.isdigit, telefone))
        if cleaned.startswith('55') and len(cleaned) > 10:
            cleaned = cleaned[2:]
        if not cleaned.startswith('55') and len(cleaned) >= 10:
            cleaned = '55' + cleaned
        return cleaned