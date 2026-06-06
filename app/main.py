from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from app.core.database import connect_to_mongo, close_mongo_connection
from app.api import webhook, sessoes, contatos, fila, estatisticas, admin
from app.workers.envio_worker import start_envio_worker, stop_envio_worker
from app.workers.limpeza_worker import start_limpeza_worker, stop_limpeza_worker
from app.workers.contato_sync_worker import start_contato_sync_worker, stop_contato_sync_worker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Iniciando YUP Customer Service Platform...")
    await connect_to_mongo()
    await start_envio_worker()
    await start_limpeza_worker()
    await start_contato_sync_worker()
    yield
    await stop_envio_worker()
    await stop_limpeza_worker()
    await stop_contato_sync_worker()
    await close_mongo_connection()

app = FastAPI(title="YUP Customer Service", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(webhook.router, prefix="/bot/yup", tags=["Webhook"])
app.include_router(sessoes.router, prefix="/bot/yup", tags=["Sessões"])
app.include_router(contatos.router, prefix="/bot/yup", tags=["Contatos"])
app.include_router(fila.router, prefix="/bot/yup", tags=["Filas"])
app.include_router(estatisticas.router, prefix="/bot/yup", tags=["Estatísticas"])
app.include_router(admin.router, prefix="/admin/yup", tags=["Admin"])

@app.get("/")
async def root():
    return {"platform": "YUP Customer Service", "assistant": "Peper 💙", "status": "online"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}