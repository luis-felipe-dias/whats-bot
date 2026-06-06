# app/workers/envio_worker.py
import asyncio
import random
from datetime import datetime
from typing import Optional
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
        logger.info("✅ Envio worker iniciado")
        
    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Envio worker parado")
        
    async def _worker_loop(self):
        ultimo_envio_por_contato = {}
        
        while self.running:
            try:
                # Buscar próximas mensagens na fila
                mensagens = await self._get_pending_messages()
                
                for mensagem in mensagens:
                    # Verificar rate limit por contato
                    contato_id = str(mensagem["contato_id"])
                    now = datetime.now()
                    
                    if contato_id in ultimo_envio_por_contato:
                        diff = (now - ultimo_envio_por_contato[contato_id]).total_seconds()
                        if diff < 2:  # 2 segundos mínimo por contato
                            continue
                    
                    # Delay aleatório para evitar bloqueio
                    delay = random.uniform(1, 3)
                    await asyncio.sleep(delay)
                    
                    # Tentar enviar
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
                # Buscar contato
                contato = await db.db.contatos.find_one({"_id": mensagem["contato_id"]})
                
                if not contato:
                    logger.error(f"Contato não encontrado: {mensagem['contato_id']}")
                    return False
                
                # Enviar via Z-API
                sucesso = await self.whatsapp_api.send_text(
                    telefone=contato["telefone"],
                    texto=mensagem["conteudo"]
                )
                
                if sucesso:
                    return True
                    
            except Exception as e:
                logger.error(f"Erro no envio (tentativa {tentativa + 1}): {str(e)}")
                
            await asyncio.sleep(2 ** tentativa)  # Exponential backoff
            
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

# Singleton instance
_envio_worker = EnvioWorker()

async def start_envio_worker():
    """Inicia o worker de envio"""
    await _envio_worker.start()
    return _envio_worker.task

async def stop_envio_worker():
    """Para o worker de envio"""
    await _envio_worker.stop()