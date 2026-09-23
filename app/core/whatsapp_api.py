# app/core/whatsapp_api.py - CORREÇÃO PARA GRUPOS + RETRY CENTRALIZADO
import httpx
import asyncio
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

    async def _post(self, endpoint: str, payload: dict, descricao: str) -> bool:
        """
        Faz o POST na Z-API com retry (settings.whatsapp_retry_attempts) e
        backoff exponencial curto. Não bloqueia o event loop: cada tentativa
        usa httpx assíncrono e o intervalo entre tentativas é um
        asyncio.sleep. Antes disso, uma falha de rede numa mensagem (ex: a
        Z-API engasgar por 1s) significava mensagem perdida sem nenhuma
        nova tentativa.
        """
        url = f"{self.base_url}/instances/{self.instance_id}/token/{self.instance_token}/{endpoint}"
        headers = {'Client-Token': self.client_token, 'Content-Type': 'application/json'}
        tentativas = max(1, settings.whatsapp_retry_attempts)

        for tentativa in range(1, tentativas + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, json=payload, headers=headers)

                if response.status_code == 200:
                    if tentativa > 1:
                        logger.info(f"✅ {descricao} enviado na tentativa {tentativa}/{tentativas}")
                    else:
                        logger.info(f"✅ {descricao} enviado")
                    return True

                logger.error(f"❌ Erro {descricao} (tentativa {tentativa}/{tentativas}): {response.status_code} - {response.text}")

            except Exception as e:
                logger.error(f"❌ Exceção {descricao} (tentativa {tentativa}/{tentativas}): {str(e)}")

            if tentativa < tentativas:
                await asyncio.sleep(min(2 ** (tentativa - 1), 8))

        logger.error(f"❌ {descricao} falhou após {tentativas} tentativa(s)")
        return False

    def _telefone_para_envio(self, telefone: str) -> str:
        # Grupo (termina com -group) não pode ser "limpo" como número de telefone
        if telefone.endswith("-group"):
            return telefone
        return self._clean_phone_number(telefone)

    async def send_text(self, telefone: str, texto: str) -> bool:
        """Envia mensagem de texto (suporta grupos e individuais)"""
        telefone_clean = self._telefone_para_envio(telefone)
        payload = {"phone": telefone_clean, "message": texto}
        return await self._post("send-text", payload, f"texto para {telefone_clean}")

    async def send_image(self, telefone: str, image_url: str, caption: str = "") -> bool:
        telefone_clean = self._telefone_para_envio(telefone)
        payload = {"phone": telefone_clean, "image": image_url, "caption": caption}
        return await self._post("send-image", payload, f"imagem para {telefone_clean}")

    async def send_document(self, telefone: str, document_url: str, filename: str = "documento.pdf", caption: str = "") -> bool:
        telefone_clean = self._telefone_para_envio(telefone)
        payload = {"phone": telefone_clean, "document": document_url, "filename": filename, "caption": caption}
        return await self._post("send-document", payload, f"documento para {telefone_clean}")

    async def send_audio(self, telefone: str, audio_url: str) -> bool:
        telefone_clean = self._telefone_para_envio(telefone)
        payload = {"phone": telefone_clean, "audio": audio_url}
        return await self._post("send-audio", payload, f"áudio para {telefone_clean}")

    async def send_video(self, telefone: str, video_url: str, caption: str = "") -> bool:
        telefone_clean = self._telefone_para_envio(telefone)
        payload = {"phone": telefone_clean, "video": video_url, "caption": caption}
        return await self._post("send-video", payload, f"vídeo para {telefone_clean}")

    async def send_interactive(self, telefone: str, texto: str, botoes: list) -> bool:
        telefone_clean = self._telefone_para_envio(telefone)
        buttons = [{"id": str(i + 1), "label": label} for i, label in enumerate(botoes[:5])]
        payload = {"phone": telefone_clean, "message": texto, "buttonList": {"buttons": buttons}}
        return await self._post("send-button-list", payload, f"botões para {telefone_clean}")

    def _clean_phone_number(self, telefone: str) -> str:
        cleaned = ''.join(filter(str.isdigit, telefone))
        if len(cleaned) >= 10 and not cleaned.startswith('55'):
            cleaned = '55' + cleaned
        return cleaned
