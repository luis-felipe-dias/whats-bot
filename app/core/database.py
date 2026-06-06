# app/core/database.py
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class Database:
    client: Optional[AsyncIOMotorClient] = None
    db = None

db = Database()

async def connect_to_mongo():
    """Conecta ao MongoDB Atlas"""
    try:
        db.client = AsyncIOMotorClient(settings.mongodb_url)
        await db.client.admin.command('ping')
        logger.info("✅ Conectado ao MongoDB Atlas com sucesso!")
        db.db = db.client[settings.mongodb_db_name]
        await create_indexes()
    except Exception as e:
        logger.error(f"❌ Erro ao conectar ao MongoDB Atlas: {str(e)}")
        raise

async def create_indexes():
    """Cria índices no MongoDB"""
    try:
        # Índices para contatos
        await db.db.contatos.create_index("telefone", unique=True)
        await db.db.contatos.create_index("data_criacao")
        
        # Índices para sessões
        await db.db.sessoes.create_index("contato_id")
        await db.db.sessoes.create_index("status")
        await db.db.sessoes.create_index([("contato_id", 1), ("status", 1)])
        
        # Índices para mensagens
        await db.db.mensagens.create_index("sessao_id")
        await db.db.mensagens.create_index("data_hora")
        
        # Índices para filas
        await db.db.fila_envio.create_index("status")
        await db.db.fila_humana.create_index("status")
        
        # Índices para eventos
        await db.db.eventos.create_index("data_hora")
        await db.db.eventos.create_index([("contato_id", 1), ("data_hora", -1)])
        
        logger.info("✅ Índices do MongoDB criados com sucesso!")
    except Exception as e:
        logger.error(f"❌ Erro ao criar índices: {str(e)}")

async def close_mongo_connection():
    """Fecha conexão com MongoDB Atlas"""
    if db.client:
        db.client.close()
        logger.info("🔌 Conexão com MongoDB Atlas fechada")