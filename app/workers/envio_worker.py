# app/workers/envio_worker.py - COM RECUPERAÇÃO DE FALHAS
import asyncio
import random
from datetime import datetime, timezone
from typing import Optional
from app.core.database import db
from app.core.whatsapp_api import WhatsAppAPI
from app.utils.helpers import now_utc
import logging
import traceback

logger = logging.getLogger(__name__)

class EnvioWorker:
    def __init__(self):
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.whatsapp_api = WhatsAppAPI()
        self.worker_count = 3
        self.batch_size = 20
        self.consecutive_failures = 0
        self.max_failures = 5
        self.health_check_interval = 30  # segundos
        
    async def start(self):
        self.running = True
        self.task = asyncio.create_task(self._worker_loop())
        logger.info(f"✅ Envio worker iniciado com {self.worker_count} workers")
        
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
                # Health check da Z-API
                if self.consecutive_failures >= self.max_failures:
                    logger.warning(f"⚠️ {self.consecutive_failures} falhas consecutivas. Aguardando recuperação...")
                    await asyncio.sleep(10)
                    self.consecutive_failures = 0
                    continue
                
                # Buscar mensagens em lote
                mensagens = await self._get_pending_messages(self.batch_size)
                
                if mensagens:
                    logger.info(f"📤 Processando {len(mensagens)} mensagens")
                    
                    # Processar em paralelo
                    tasks = []
                    for mensagem in mensagens:
                        tasks.append(self._enviar_com_retry(mensagem))
                    
                    resultados = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Atualizar status
                    sucessos = 0
                    for i, (mensagem, resultado) in enumerate(zip(mensagens, resultados)):
                        if isinstance(resultado, Exception):
                            await self._marcar_como_erro(mensagem["_id"])
                            logger.error(f"❌ Erro: {str(resultado)}")
                            self.consecutive_failures += 1
                        elif resultado:
                            await self._marcar_como_enviado(mensagem["_id"])
                            sucessos += 1
                            self.consecutive_failures = 0
                        else:
                            await self._marcar_como_erro(mensagem["_id"])
                            self.consecutive_failures += 1
                    
                    logger.info(f"✅ {sucessos}/{len(mensagens)} mensagens enviadas")
                else:
                    # Resetar contador de falhas quando não há mensagens
                    self.consecutive_failures = 0
                
                await asyncio.sleep(0.5)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Erro no loop: {str(e)}")
                traceback.print_exc()
                self.consecutive_failures += 1
                await asyncio.sleep(5)
    
    async def _get_pending_messages(self, limit: int = 20):
        try:
            cursor = db.db.fila_envio.find({"status": "pendente"}).limit(limit)
            return await cursor.to_list(length=limit)
        except Exception as e:
            logger.error(f"Erro ao buscar mensagens: {str(e)}")
            return []
    
    async def _enviar_com_retry(self, mensagem: dict, max_retries: int = 3):
        for tentativa in range(max_retries):
            try:
                # Buscar contato
                contato_id = mensagem.get("contato_id")
                if contato_id and hasattr(contato_id, 'binary'):
                    contato_id = str(contato_id)
                
                contato = await db.db.contatos.find_one({"_id": contato_id})
                if not contato:
                    logger.error(f"Contato não encontrado: {contato_id}")
                    return False
                
                texto = mensagem["conteudo"]
                botoes = mensagem.get("botoes", [])
                
                # Enviar com timeout
                try:
                    if botoes and len(botoes) > 0:
                        sucesso = await asyncio.wait_for(
                            self.whatsapp_api.send_interactive(
                                telefone=contato["telefone"],
                                texto=texto,
                                botoes=botoes
                            ),
                            timeout=30.0
                        )
                    else:
                        sucesso = await asyncio.wait_for(
                            self.whatsapp_api.send_text(
                                telefone=contato["telefone"],
                                texto=texto
                            ),
                            timeout=30.0
                        )
                    
                    if sucesso:
                        logger.info(f"✅ Mensagem enviada para {contato['telefone']}")
                        return True
                        
                except asyncio.TimeoutError:
                    logger.warning(f"⏱️ Timeout enviando para {contato['telefone']} (tentativa {tentativa+1})")
                    
            except Exception as e:
                logger.error(f"❌ Erro envio (tentativa {tentativa+1}): {str(e)}")
            
            # Aguardar antes de tentar novamente
            await asyncio.sleep(2 ** tentativa)
            
        return False
    
    async def _marcar_como_enviado(self, mensagem_id):
        try:
            await db.db.fila_envio.update_one(
                {"_id": mensagem_id},
                {"$set": {"status": "enviado", "data_envio": now_utc()}}
            )
        except Exception as e:
            logger.error(f"Erro ao marcar como enviado: {str(e)}")
    
    async def _marcar_como_erro(self, mensagem_id):
        try:
            await db.db.fila_envio.update_one(
                {"_id": mensagem_id},
                {"$set": {"status": "erro"}}
            )
        except Exception as e:
            logger.error(f"Erro ao marcar como erro: {str(e)}")
    
    async def health_check(self):
        """Verifica saúde do worker"""
        try:
            pending = await db.db.fila_envio.count_documents({"status": "pendente"})
            logger.info(f"📊 Fila de envio: {pending} mensagens pendentes")
            return pending
        except Exception as e:
            logger.error(f"Erro no health check: {str(e)}")
            return -1

_envio_worker = EnvioWorker()

async def start_envio_worker():
    await _envio_worker.start()
    return _envio_worker.task

async def stop_envio_worker():
    await _envio_worker.stop()

async def get_worker_status():
    """Retorna status do worker para monitoramento"""
    return {
        "running": _envio_worker.running,
        "pending": await db.db.fila_envio.count_documents({"status": "pendente"}),
        "consecutive_failures": _envio_worker.consecutive_failures
    }
