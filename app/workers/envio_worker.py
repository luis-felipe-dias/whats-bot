# app/workers/envio_worker.py
import asyncio
import random
from datetime import datetime
from typing import Optional
from bson import ObjectId
from app.core.database import db
from app.core.whatsapp_api import WhatsAppAPI
import logging

logger = logging.getLogger(__name__)

class EnvioWorker:
    def __init__(self):
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.whatsapp_api = WhatsAppAPI()
        
    async def start(self):
        self.running = True
        self.task = asyncio.create_task(self._worker_loop())
        logger.info("Envio worker iniciado")
        
    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Envio worker parado")
        
    async def _worker_loop(self):
        ultimo_envio_por_contato = {}
        
        while self.running:
            try:
                mensagens = await self._get_pending_messages()
                
                for mensagem in mensagens:
                    contato_id = str(mensagem["contato_id"])
                    now = datetime.now()
                    
                    if contato_id in ultimo_envio_por_contato:
                        diff = (now - ultimo_envio_por_contato[contato_id]).total_seconds()
                        if diff < 2:
                            continue
                    
                    delay = random.uniform(1, 3)
                    await asyncio.sleep(delay)
                    
                    sucesso = await self._enviar_com_retry(mensagem)
                    
                    if sucesso:
                        await self._marcar_como_enviado(mensagem["_id"])
                        ultimo_envio_por_contato[contato_id] = datetime.now()
                    else:
                        await self._marcar_como_erro(mensagem["_id"])
                
                await asyncio.sleep(0.5)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erro no loop do worker: {str(e)}")
                await asyncio.sleep(5)
    
    async def _get_pending_messages(self, limit: int = 10):
        cursor = db.db.fila_envio.find({"status": "pendente"}).limit(limit)
        return await cursor.to_list(length=limit)
    
    async def _enviar_com_retry(self, mensagem: dict, max_retries: int = 3):
        for tentativa in range(max_retries):
            try:
                contato_id = mensagem.get("contato_id")
                
                if contato_id and hasattr(contato_id, 'binary'):
                    contato_id = str(contato_id)
                
                logger.info(f"Buscando contato com ID: {contato_id}")
                
                contato = await db.db.contatos.find_one({"_id": contato_id})
                
                if not contato and contato_id:
                    try:
                        contato = await db.db.contatos.find_one({"_id": ObjectId(contato_id)})
                    except:
                        pass
                
                if not contato:
                    logger.error(f"Contato nao encontrado: {contato_id}")
                    return False
                
                texto = mensagem["conteudo"]
                botoes = mensagem.get("botoes", [])
                
                logger.info(f"Enviando para: {contato['telefone']}")
                logger.info(f"Texto: {texto[:50]}...")
                logger.info(f"Botoes: {botoes}")
                
                # Enviar com botões se houver
                if botoes and len(botoes) > 0:
                    sucesso = await self.whatsapp_api.send_buttons(
                        telefone=contato["telefone"],
                        texto=texto,
                        buttons=botoes
                    )
                else:
                    sucesso = await self.whatsapp_api.send_text(
                        telefone=contato["telefone"],
                        texto=texto
                    )
                
                if sucesso:
                    logger.info(f"Mensagem enviada com sucesso para {contato['telefone']}")
                    return True
                    
            except Exception as e:
                logger.error(f"Erro no envio (tentativa {tentativa + 1}): {str(e)}")
                
            await asyncio.sleep(2 ** tentativa)
            
        return False
    
    async def _marcar_como_enviado(self, mensagem_id):
        await db.db.fila_envio.update_one(
            {"_id": mensagem_id},
            {"$set": {"status": "enviado", "data_envio": datetime.now()}}
        )
    
    async def _marcar_como_erro(self, mensagem_id):
        await db.db.fila_envio.update_one(
            {"_id": mensagem_id},
            {"$set": {"status": "erro"}}
        )

_envio_worker = EnvioWorker()

async def start_envio_worker():
    await _envio_worker.start()
    return _envio_worker.task

async def stop_envio_worker():
    await _envio_worker.stop()
