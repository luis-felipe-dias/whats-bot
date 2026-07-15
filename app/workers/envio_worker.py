# app/workers/envio_worker.py - OTIMIZADO PARA ALTA PERFORMANCE
import asyncio
import random
from datetime import datetime, timezone
from typing import Optional
from app.core.database import db
from app.core.whatsapp_api import WhatsAppAPI
from app.utils.helpers import now_utc
import logging

logger = logging.getLogger(__name__)

class EnvioWorker:
    def __init__(self):
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.whatsapp_api = WhatsAppAPI()
        # Configurar pool de workers
        self.worker_count = 5  # 5 workers paralelos
        self.batch_size = 50  # Mensagens por lote
        
    async def start(self):
        self.running = True
        self.task = asyncio.create_task(self._worker_loop())
        logger.info(f"✅ Envio worker iniciado com {self.worker_count} workers paralelos")
        
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
        while self.running:
            try:
                # Buscar mensagens em lote
                mensagens = await self._get_pending_messages(self.batch_size)
                
                if mensagens:
                    # Processar em paralelo com pool de workers
                    tasks = []
                    for mensagem in mensagens:
                        tasks.append(self._enviar_com_retry(mensagem))
                    
                    # Aguardar todos os envios paralelos
                    resultados = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Atualizar status de cada mensagem
                    for i, (mensagem, resultado) in enumerate(zip(mensagens, resultados)):
                        if isinstance(resultado, Exception):
                            await self._marcar_como_erro(mensagem["_id"])
                            logger.error(f"Erro no envio: {str(resultado)}")
                        elif resultado:
                            await self._marcar_como_enviado(mensagem["_id"])
                        else:
                            await self._marcar_como_erro(mensagem["_id"])
                
                await asyncio.sleep(0.5)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erro no loop do worker: {str(e)}")
                await asyncio.sleep(5)
    
    async def _get_pending_messages(self, limit: int = 50):
        cursor = db.db.fila_envio.find({"status": "pendente"}).limit(limit)
        return await cursor.to_list(length=limit)
    
    async def _enviar_com_retry(self, mensagem: dict, max_retries: int = 3):
        for tentativa in range(max_retries):
            try:
                contato_id = mensagem.get("contato_id")
                
                if contato_id and hasattr(contato_id, 'binary'):
                    contato_id = str(contato_id)
                
                contato = await db.db.contatos.find_one({"_id": contato_id})
                if not contato:
                    continue
                
                texto = mensagem["conteudo"]
                botoes = mensagem.get("botoes", [])
                
                if botoes and len(botoes) > 0:
                    sucesso = await self.whatsapp_api.send_interactive(
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
                    return True
                    
            except Exception as e:
                logger.error(f"Erro envio (tentativa {tentativa + 1}): {str(e)}")
                
            # Backoff exponencial
            await asyncio.sleep(2 ** tentativa)
            
        return False
    
    async def _marcar_como_enviado(self, mensagem_id):
        await db.db.fila_envio.update_one(
            {"_id": mensagem_id},
            {"$set": {"status": "enviado", "data_envio": now_utc()}}
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
