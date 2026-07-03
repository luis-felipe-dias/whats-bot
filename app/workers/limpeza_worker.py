# app/workers/limpeza_worker.py
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from app.core.database import db
from bson import ObjectId
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
                await self._limpar_sessoes_inativas()
                await asyncio.sleep(1800)  # 30 minutos
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erro no loop de limpeza: {str(e)}")
                await asyncio.sleep(60)
    
    async def _limpar_sessoes_inativas(self):
        try:
            # Sessões inativas por mais de 4 horas (240 minutos)
            limite_inativo = datetime.now() - timedelta(hours=4)
            
            # Buscar sessões inativas (não finalizadas)
            sessoes_inativas = await db.db.sessoes.find({
                "status": {"$in": ["ativa", "humano", "fila_humana"]},
                "ultima_interacao": {"$lt": limite_inativo}
            }).to_list(length=None)
            
            logger.info(f"🔍 Encontradas {len(sessoes_inativas)} sessões inativas para limpeza")
            
            for sessao in sessoes_inativas:
                sessao_id = str(sessao["_id"])
                contato_id = sessao.get("contato_id")
                
                logger.info(f"🗑️ Removendo sessão inativa: {sessao_id} - Última interação: {sessao.get('ultima_interacao')}")
                
                # Remover mensagens da sessão
                await db.db.mensagens.delete_many({"sessao_id": sessao_id})
                
                # Remover da fila de envio
                await db.db.fila_envio.delete_many({"sessao_id": sessao_id})
                
                # Remover da fila humana
                await db.db.fila_humana.delete_many({"sessao_id": sessao_id})
                
                # Atualizar contato (resetar contagem)
                if contato_id:
                    await db.db.contatos.update_one(
                        {"_id": ObjectId(contato_id)},
                        {"$set": {"ultima_interacao": datetime.now()}}
                    )
                
                # Remover a sessão
                await db.db.sessoes.delete_one({"_id": sessao["_id"]})
                
                logger.info(f"✅ Sessão {sessao_id} removida pela limpeza automática")
            
            # Também remover sessões finalizadas há mais de 24 horas
            limite_finalizado = datetime.now() - timedelta(hours=24)
            sessoes_finalizadas = await db.db.sessoes.find({
                "status": "finalizada",
                "data_fim": {"$lt": limite_finalizado}
            }).to_list(length=None)
            
            for sessao in sessoes_finalizadas:
                sessao_id = str(sessao["_id"])
                await db.db.mensagens.delete_many({"sessao_id": sessao_id})
                await db.db.fila_envio.delete_many({"sessao_id": sessao_id})
                await db.db.fila_humana.delete_many({"sessao_id": sessao_id})
                await db.db.sessoes.delete_one({"_id": sessao["_id"]})
                logger.info(f"🗑️ Sessão finalizada removida: {sessao_id}")
                
        except Exception as e:
            logger.error(f"Erro na limpeza: {str(e)}")

# Singleton instance
_limpeza_worker = LimpezaWorker()

async def start_limpeza_worker():
    await _limpeza_worker.start()
    return _limpeza_worker.task

async def stop_limpeza_worker():
    await _limpeza_worker.stop()
