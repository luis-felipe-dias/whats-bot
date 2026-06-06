# app/core/whatsapp_api.py
import httpx
from app.core.config import settings
import logging
import json
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class WhatsAppAPI:
    def __init__(self):
        self.instance_id = settings.zapi_instance_id
        self.instance_token = settings.zapi_token  # Token da instância (URL)
        self.client_token = settings.zapi_client_token  # Client-Token (Header)
        self.base_url = settings.zapi_url
        self.timeout = 30.0
        
    async def send_text(self, telefone: str, texto: str) -> bool:
        """
        Envia mensagem de texto via Z-API usando Client-Token no header
        """
        try:
            telefone_clean = self._clean_phone_number(telefone)
            
            # URL com Token da Instância
            url = f"{self.base_url}/instances/{self.instance_id}/token/{self.instance_token}/send-text"
            
            # Payload
            payload = {
                "phone": telefone_clean,
                "message": texto,
                "delayMessage": 15
            }
            
            # Headers com Client-Token (diferente do token da instância)
            headers = {
                'Client-Token': self.client_token,
                'Content-Type': 'application/json'
            }
            
            logger.info(f"Enviando para URL: {url}")
            logger.info(f"Usando Client-Token: {self.client_token[:10]}...")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers
                )
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"✅ Mensagem enviada para {telefone_clean}")
                    logger.info(f"Resposta Z-API: {result}")
                    return True
                else:
                    logger.error(f"❌ Erro Z-API: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Exceção ao enviar mensagem: {str(e)}")
            return False
    
    async def send_buttons(self, telefone: str, texto: str, buttons: list) -> bool:
        """Envia mensagem com botões"""
        try:
            telefone_clean = self._clean_phone_number(telefone)
            
            url = f"{self.base_url}/instances/{self.instance_id}/token/{self.instance_token}/send-buttons"
            
            payload = {
                "phone": telefone_clean,
                "message": texto,
                "buttons": buttons,
                "delayMessage": 15
            }
            
            headers = {
                'Client-Token': self.client_token,
                'Content-Type': 'application/json'
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                
                if response.status_code == 200:
                    logger.info(f"✅ Botões enviados para {telefone_clean}")
                    return True
                else:
                    logger.error(f"❌ Erro ao enviar botões: {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Exceção ao enviar botões: {str(e)}")
            return False
    
    async def get_contact_info(self, telefone: str) -> Dict[str, Any]:
        """Busca informações do contato"""
        try:
            telefone_clean = self._clean_phone_number(telefone)
            
            url = f"{self.base_url}/instances/{self.instance_id}/token/{self.instance_token}/check-number"
            
            headers = {
                'Client-Token': self.client_token,
                'Content-Type': 'application/json'
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    params={"phone": telefone_clean},
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "name": data.get("name", ""),
                        "profile_pic_url": data.get("profilePicUrl", ""),
                        "exists": data.get("exists", False)
                    }
                return {}
                
        except Exception as e:
            logger.error(f"❌ Erro ao buscar contato: {str(e)}")
            return {}
    
    async def save_contact(self, telefone: str, nome: str) -> bool:
        """Salva contato no WhatsApp"""
        try:
            telefone_clean = self._clean_phone_number(telefone)
            
            url = f"{self.base_url}/instances/{self.instance_id}/token/{self.instance_token}/create-contact"
            
            payload = {
                "phone": telefone_clean,
                "name": nome
            }
            
            headers = {
                'Client-Token': self.client_token,
                'Content-Type': 'application/json'
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                
                if response.status_code == 200:
                    logger.info(f"✅ Contato {nome} salvo no WhatsApp")
                    return True
                else:
                    logger.warning(f"⚠️ Não foi possível salvar contato: {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Erro ao salvar contato: {str(e)}")
            return False
    
    def _clean_phone_number(self, telefone: str) -> str:
        """Limpa o número de telefone"""
        cleaned = ''.join(filter(str.isdigit, telefone))
        
        if cleaned.startswith('55') and len(cleaned) > 10:
            cleaned = cleaned[2:]
        
        if not cleaned.startswith('55') and len(cleaned) >= 10:
            cleaned = '55' + cleaned
        
        return cleaned