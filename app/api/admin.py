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
