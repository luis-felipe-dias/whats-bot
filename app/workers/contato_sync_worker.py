# app/workers/contato_sync_worker.py
import asyncio
import logging

logger = logging.getLogger(__name__)

async def start_contato_sync_worker():
    logger.info("Contato sync worker desabilitado")
    return None

async def stop_contato_sync_worker():
    pass
