# app/api/admin.py - Endpoints administrativos
from fastapi import APIRouter, HTTPException
from app.core.database import db
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/admin/status")
async def admin_status():
    """Verifica o status geral do sistema"""
    try:
        # Verificar MongoDB
        try:
            await db.db.command('ping')
            mongodb_status = "conectado"
        except:
            mongodb_status = "desconectado"
        
        # Contagens
        contatos = await db.db.contatos.count_documents({})
        sessoes = await db.db.sessoes.count_documents({})
        mensagens = await db.db.mensagens.count_documents({})
        
        return {
            "sucesso": True,
            "status": {
                "mongodb": mongodb_status,
                "contatos": contatos,
                "sessoes": sessoes,
                "mensagens": mensagens,
                "versao_api": "2.0.0"
            }
        }
    except Exception as e:
        logger.error(f"Erro ao verificar status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/health")
async def admin_health():
    """Health check para monitoramento"""
    try:
        await db.db.command('ping')
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}

# ============================================
# ENDPOINTS DE RECUPERAÇÃO DO WORKER
# ============================================
@router.post("/worker/restart")
async def restart_worker():
    """Reinicia o worker de envio"""
    try:
        from app.workers.envio_worker import _envio_worker
        import asyncio
        
        if _envio_worker.running:
            _envio_worker.running = False
            if _envio_worker.task:
                _envio_worker.task.cancel()
                try:
                    await _envio_worker.task
                except:
                    pass
        
        await asyncio.sleep(1)
        
        _envio_worker.running = True
        _envio_worker.task = asyncio.create_task(_envio_worker._worker_loop())
        _envio_worker.consecutive_failures = 0
        
        return {"success": True, "message": "Worker reiniciado"}
    except Exception as e:
        logger.error(f"Erro: {str(e)}")
        return {"success": False, "error": str(e)}

@router.get("/worker/status")
async def get_worker_status():
    """Status do worker"""
    try:
        from app.workers.envio_worker import get_worker_status
        status = await get_worker_status()
        return {"success": True, "status": status}
    except Exception as e:
        return {"success": False, "error": str(e)}
