# app/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging
from app.core.database import connect_to_mongo, close_mongo_connection
from app.api import webhook, sessoes, contatos, fila, estatisticas, admin
from app.workers.envio_worker import start_envio_worker, stop_envio_worker
from app.workers.limpeza_worker import start_limpeza_worker, stop_limpeza_worker
from app.workers.contato_sync_worker import start_contato_sync_worker, stop_contato_sync_worker

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Iniciando YUP Customer Service Platform...")
    
    try:
        # Conectar ao MongoDB Atlas
        await connect_to_mongo()
        logger.info("✅ MongoDB Atlas conectado")
        
        # Iniciar workers
        envio_task = await start_envio_worker()
        limpeza_task = await start_limpeza_worker()
        contato_sync_task = await start_contato_sync_worker()
        logger.info("✅ Workers iniciados")
        
        yield
        
    except Exception as e:
        logger.error(f"❌ Erro na inicialização: {str(e)}")
        raise
    finally:
        # Shutdown
        logger.info("🛑 Desligando YUP Customer Service Platform...")
        await stop_envio_worker()
        await stop_limpeza_worker()
        await stop_contato_sync_worker()
        await close_mongo_connection()
        logger.info("✅ Sistema desligado")

app = FastAPI(
    title="YUP Customer Service Platform",
    description="Plataforma de atendimento Peper 💙",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook.router, prefix="/bot/yup", tags=["Webhook"])
app.include_router(sessoes.router, prefix="/bot/yup", tags=["Sessões"])
app.include_router(contatos.router, prefix="/bot/yup", tags=["Contatos"])
app.include_router(fila.router, prefix="/bot/yup", tags=["Filas"])
app.include_router(estatisticas.router, prefix="/bot/yup", tags=["Estatísticas"])
app.include_router(admin.router, prefix="/admin/yup", tags=["Admin"])

@app.get("/")
async def root():
    return {
        "platform": "YUP Customer Service",
        "assistant": "Peper 💙",
        "status": "online",
        "mongodb": "connected",
        "zapi": "configured"
    }

@app.get("/health")
async def health_check():
    from app.core.database import db
    try:
        await db.db.command('ping')
        mongodb_status = "healthy"
    except:
        mongodb_status = "unhealthy"
    
    return {
        "status": "healthy",
        "mongodb": mongodb_status,
        "workers": "running"
    }