# app/workers/limpeza_worker.py
import asyncio
from datetime import datetime, timedelta, timezone
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
                await self._limpar_sessoes_antigas()
                await self._remover_dados_orfãos()
                await asyncio.sleep(1800)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erro no loop de limpeza: {str(e)}")
                await asyncio.sleep(60)
    
    async def _limpar_sessoes_antigas(self):
        try:
            agora = datetime.now(timezone.utc)
            limite_3h = agora - timedelta(hours=3)
            
            # NUNCA REMOVER GRUPOS
            # 1. Finalizadas
            sessoes_finalizadas = await db.db.sessoes.find({
                "status": "finalizada",
                "ultima_interacao": {"$lt": limite_3h},
                "is_group": {"$ne": True}
            }).to_list(length=None)
            
            for sessao in sessoes_finalizadas:
                await self._remover_sessao(sessao, "finalizada")
            
            # 2. Ativas inativas
            sessoes_inativas = await db.db.sessoes.find({
                "status": "ativa",
                "setor_responsavel": None,
                "aguardando_atendente": False,
                "ultima_interacao": {"$lt": limite_3h},
                "is_group": {"$ne": True}
            }).to_list(length=None)
            
            for sessao in sessoes_inativas:
                await self._remover_sessao(sessao, "inativa")
            
            # 3. Humanas respondidas
            sessoes_humanas = await db.db.sessoes.find({
                "status": {"$in": ["humano", "aguardando_atendente"]},
                "human_response_sent": True,
                "ultima_interacao": {"$lt": limite_3h},
                "is_group": {"$ne": True}
            }).to_list(length=None)
            
            for sessao in sessoes_humanas:
                await self._remover_sessao(sessao, "humana_respondida")
            
            total = len(sessoes_finalizadas) + len(sessoes_inativas) + len(sessoes_humanas)
            if total > 0:
                logger.info(f"🗑️ Limpeza concluída: {total} sessões removidas")
            
        except Exception as e:
            logger.error(f"Erro na limpeza: {str(e)}")
    
    async def _remover_sessao(self, sessao: dict, motivo: str):
        try:
            sessao_id = str(sessao["_id"])
            
            # NUNCA REMOVER GRUPOS
            if sessao.get("is_group") == True:
                logger.info(f"⏭️ Ignorando grupo: {sessao_id}")
                return
            
            logger.info(f"🗑️ Removendo sessão {sessao_id} - {motivo}")
            
            await db.db.mensagens.delete_many({"sessao_id": sessao_id})
            await db.db.fila_envio.delete_many({"sessao_id": sessao_id})
            await db.db.fila_humana.delete_many({"sessao_id": sessao_id})
            await db.db.eventos.delete_many({"sessao_id": sessao_id})
            await db.db.sessoes.delete_one({"_id": sessao["_id"]})
            
            logger.info(f"✅ Sessão {sessao_id} removida")
            
        except Exception as e:
            logger.error(f"Erro ao remover: {str(e)}")
    
    async def _remover_dados_orfãos(self):
        try:
            sessoes = await db.db.sessoes.find({}, {"_id": 1}).to_list(length=None)
            ids_sessoes = [str(s["_id"]) for s in sessoes]
            
            if not ids_sessoes:
                return
            
            resultado_msg = await db.db.mensagens.delete_many({"sessao_id": {"$nin": ids_sessoes}})
            resultado_fila = await db.db.fila_envio.delete_many({"sessao_id": {"$nin": ids_sessoes}})
            resultado_humana = await db.db.fila_humana.delete_many({"sessao_id": {"$nin": ids_sessoes}})
            resultado_eventos = await db.db.eventos.delete_many({"sessao_id": {"$nin": ids_sessoes}})
            
            total = resultado_msg.deleted_count + resultado_fila.deleted_count + resultado_humana.deleted_count + resultado_eventos.deleted_count
            if total > 0:
                logger.info(f"🗑️ Dados órfãos: Mensagens: {resultado_msg.deleted_count}")
            
        except Exception as e:
            logger.error(f"Erro ao remover órfãos: {str(e)}")

_limpeza_worker = LimpezaWorker()

async def start_limpeza_worker():
    await _limpeza_worker.start()
    return _limpeza_worker.task

async def stop_limpeza_worker():
    await _limpeza_worker.stop()
