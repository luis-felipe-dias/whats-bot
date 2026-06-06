# app/workers/contato_sync_worker.py
import asyncio
from datetime import datetime
from typing import Optional
from app.core.database import db
from app.core.whatsapp_api import WhatsAppAPI
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class ContatoSyncWorker:
    def __init__(self):
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.whatsapp_api = WhatsAppAPI()
        
    async def start(self):
        if not settings.whatsapp_save_contacts:
            logger.info("Sincronização de contatos desabilitada")
            return
            
        self.running = True
        self.task = asyncio.create_task(self._worker_loop())
        logger.info("✅ Contato sync worker iniciado")
        
    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Contato sync worker parado")
        
    async def _worker_loop(self):
        while self.running:
            try:
                # Buscar contatos sem nome personalizado
                cursor = db.db.contatos.find({
                    "nome_personalizado": False,
                    "foto_url": {"$exists": False}
                }).limit(10)
                
                contatos = await cursor.to_list(length=10)
                
                for contato in contatos:
                    # Buscar dados na Z-API
                    dados = await self.whatsapp_api.get_contact_info(contato["telefone"])
                    
                    if dados and dados.get("exists"):
                        # Atualizar contato
                        await db.db.contatos.update_one(
                            {"_id": contato["_id"]},
                            {"$set": {
                                "nome": dados.get("name", contato["nome"]),
                                "foto_url": dados.get("profile_pic_url"),
                                "data_atualizacao": datetime.now()
                            }}
                        )
                        
                        logger.info(f"Contato sincronizado: {contato['telefone']}")
                    
                    await asyncio.sleep(1)
                
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erro na sincronização: {str(e)}")
                await asyncio.sleep(5)

# Singleton instance
_contato_sync_worker = ContatoSyncWorker()

async def start_contato_sync_worker():
    """Inicia o worker de sincronização de contatos"""
    await _contato_sync_worker.start()
    return _contato_sync_worker.task

async def stop_contato_sync_worker():
    """Para o worker de sincronização de contatos"""
    await _contato_sync_worker.stop()