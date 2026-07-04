# app/core/whatsapp_api.py - CORREÇÃO PARA GRUPOS
import httpx
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class WhatsAppAPI:
    def __init__(self):
        self.instance_id = settings.zapi_instance_id
        self.instance_token = settings.zapi_token
        self.client_token = settings.zapi_client_token
        self.base_url = "https://api.z-api.io"
        self.timeout = 60.0
        
    async def send_text(self, telefone: str, texto: str) -> bool:
        """Envia mensagem de texto (suporta grupos e individuais)"""
        try:
            # Não limpar o telefone se for grupo (termina com -group)
            if telefone.endswith("-group"):
                telefone_clean = telefone
                logger.info(f"📤 Enviando para GRUPO: {telefone_clean}")
            else:
                telefone_clean = self._clean_phone_number(telefone)
                logger.info(f"📤 Enviando para CONTATO: {telefone_clean}")
            
            url = f"{self.base_url}/instances/{self.instance_id}/token/{self.instance_token}/send-text"
            
            payload = {
                "phone": telefone_clean,
                "message": texto
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
                    logger.error(f"❌ Erro: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Exceção: {str(e)}")
            return False
    
    async def send_image(self, telefone: str, image_url: str, caption: str = "") -> bool:
        try:
            if telefone.endswith("-group"):
                telefone_clean = telefone
            else:
                telefone_clean = self._clean_phone_number(telefone)
            
            url = f"{self.base_url}/instances/{self.instance_id}/token/{self.instance_token}/send-image"
            
            payload = {
                "phone": telefone_clean,
                "image": image_url,
                "caption": caption
            }
            headers = {'Client-Token': self.client_token, 'Content-Type': 'application/json'}
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code == 200:
                    logger.info(f"✅ Imagem enviada para {telefone_clean}")
                    return True
                else:
                    logger.error(f"❌ Erro imagem: {response.status_code}")
                    return False
        except Exception as e:
            logger.error(f"❌ Exceção imagem: {str(e)}")
            return False
    
    async def send_document(self, telefone: str, document_url: str, filename: str = "documento.pdf", caption: str = "") -> bool:
        try:
            if telefone.endswith("-group"):
                telefone_clean = telefone
            else:
                telefone_clean = self._clean_phone_number(telefone)
            
            url = f"{self.base_url}/instances/{self.instance_id}/token/{self.instance_token}/send-document"
            
            payload = {
                "phone": telefone_clean,
                "document": document_url,
                "filename": filename,
                "caption": caption
            }
            headers = {'Client-Token': self.client_token, 'Content-Type': 'application/json'}
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code == 200:
                    logger.info(f"✅ Documento enviado para {telefone_clean}")
                    return True
                else:
                    logger.error(f"❌ Erro documento: {response.status_code}")
                    return False
        except Exception as e:
            logger.error(f"❌ Exceção documento: {str(e)}")
            return False
    
    async def send_audio(self, telefone: str, audio_url: str) -> bool:
        try:
            if telefone.endswith("-group"):
                telefone_clean = telefone
            else:
                telefone_clean = self._clean_phone_number(telefone)
            
            url = f"{self.base_url}/instances/{self.instance_id}/token/{self.instance_token}/send-audio"
            
            payload = {
                "phone": telefone_clean,
                "audio": audio_url
            }
            headers = {'Client-Token': self.client_token, 'Content-Type': 'application/json'}
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code == 200:
                    logger.info(f"✅ Áudio enviado para {telefone_clean}")
                    return True
                else:
                    logger.error(f"❌ Erro áudio: {response.status_code}")
                    return False
        except Exception as e:
            logger.error(f"❌ Exceção áudio: {str(e)}")
            return False
    
    async def send_video(self, telefone: str, video_url: str, caption: str = "") -> bool:
        try:
            if telefone.endswith("-group"):
                telefone_clean = telefone
            else:
                telefone_clean = self._clean_phone_number(telefone)
            
            url = f"{self.base_url}/instances/{self.instance_id}/token/{self.instance_token}/send-video"
            
            payload = {
                "phone": telefone_clean,
                "video": video_url,
                "caption": caption
            }
            headers = {'Client-Token': self.client_token, 'Content-Type': 'application/json'}
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code == 200:
                    logger.info(f"✅ Vídeo enviado para {telefone_clean}")
                    return True
                else:
                    logger.error(f"❌ Erro vídeo: {response.status_code}")
                    return False
        except Exception as e:
            logger.error(f"❌ Exceção vídeo: {str(e)}")
            return False
    
    async def send_interactive(self, telefone: str, texto: str, botoes: list) -> bool:
        try:
            if telefone.endswith("-group"):
                telefone_clean = telefone
            else:
                telefone_clean = self._clean_phone_number(telefone)
            
            url = f"{self.base_url}/instances/{self.instance_id}/token/{self.instance_token}/send-button-list"
            
            buttons = []
            for i, label in enumerate(botoes[:5]):
                buttons.append({"id": str(i + 1), "label": label})
            
            payload = {
                "phone": telefone_clean,
                "message": texto,
                "buttonList": {"buttons": buttons}
            }
            headers = {'Client-Token': self.client_token, 'Content-Type': 'application/json'}
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code == 200:
                    logger.info(f"✅ Botões enviados para {telefone_clean}")
                    return True
                else:
                    logger.error(f"❌ Erro botões: {response.status_code}")
                    return False
        except Exception as e:
            logger.error(f"❌ Exceção botões: {str(e)}")
            return False
    
    def _clean_phone_number(self, telefone: str) -> str:
        cleaned = ''.join(filter(str.isdigit, telefone))
        if len(cleaned) >= 10 and not cleaned.startswith('55'):
            cleaned = '55' + cleaned
        return cleaned
