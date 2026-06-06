# app/workers/limpeza_worker.py
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from app.core.database import db
import logging

logger = logging.getLogger(__name__)

class LimpezaWorker:
    def __init__(self):
        self.running = False
        self.task: Optional[asyncio.Task] = None
        
    async def start(self):
        self.running = True
        self.task = asyncio.create_task(self._worker_loop())
        logger.info("✅ Limpeza worker iniciado")
        
    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Limpeza worker parado")
        
    async def _worker_loop(self):
        while self.running:
            try:
                # Executar limpeza a cada 30 minutos
                await self._limpar_sessoes_antigas()
                await asyncio.sleep(1800)  # 30 minutos
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erro no loop de limpeza: {str(e)}")
                await asyncio.sleep(60)
    
    async def _limpar_sessoes_antigas(self):
        try:
            # Sessões finalizadas há mais de 3 horas
            limite = datetime.now() - timedelta(hours=3)
            
            # Buscar sessões para limpar
            cursor = db.db.sessoes.find({
                "status": {"$in": ["finalizada", "cancelada"]},
                "data_fim": {"$lt": limite}
            })
            
            sessoes = await cursor.to_list(length=None)
            
            for sessao in sessoes:
                sessao_id = str(sessao["_id"])
                
                # Remover mensagens da sessão
                await db.db.mensagens.delete_many({"sessao_id": sessao_id})
                
                # Remover da fila de envio
                await db.db.fila_envio.delete_many({"sessao_id": sessao_id})
                
                # Remover da fila humana
                await db.db.fila_humana.delete_many({"sessao_id": sessao_id})
                
                # Remover a sessão
                await db.db.sessoes.delete_one({"_id": sessao["_id"]})
                
                logger.info(f"🗑️ Sessão {sessao_id} removida pela limpeza automática")
            
            # Remover mensagens órfãs (sessões que não existem mais)
            sessoes_ativas = await db.db.sessoes.find({}, {"_id": 1}).to_list(length=None)
            sessoes_ids = [str(s["_id"]) for s in sessoes_ativas]
            
            resultado = await db.db.mensagens.delete_many({"sessao_id": {"$nin": sessoes_ids}})
            if resultado.deleted_count > 0:
                logger.info(f"🗑️ {resultado.deleted_count} mensagens órfãs removidas")
                
        except Exception as e:
            logger.error(f"Erro na limpeza: {str(e)}")

# Singleton instance
_limpeza_worker = LimpezaWorker()

async def start_limpeza_worker():
    """Inicia o worker de limpeza"""
    await _limpeza_worker.start()
    return _limpeza_worker.task

async def stop_limpeza_worker():
    """Para o worker de limpeza"""
    await _limpeza_worker.stop()