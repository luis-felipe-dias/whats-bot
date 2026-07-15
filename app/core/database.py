# app/core/database.py - OTIMIZADO PARA ALTA PERFORMANCE
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
    """Conecta ao MongoDB com pool otimizado"""
    try:
        # Configurações otimizadas para alta concorrência
        db.client = AsyncIOMotorClient(
            settings.mongodb_url,
            maxPoolSize=100,  # Aumentado para suportar mais conexões
            minPoolSize=20,
            maxIdleTimeMS=30000,
            waitQueueTimeoutMS=5000,
            connectTimeoutMS=10000,
            socketTimeoutMS=30000,
            serverSelectionTimeoutMS=10000,
            retryWrites=True,
            retryReads=True,
            compressors=['snappy', 'zlib']  # Compressão para reduzir tráfego
        )
        
        await db.client.admin.command('ping')
        logger.info("✅ Conectado ao MongoDB Atlas com pool otimizado (max: 100)")
        
        db.db = db.client[settings.mongodb_db_name]
        await create_indexes()
        
    except Exception as e:
        logger.error(f"❌ Erro ao conectar ao MongoDB: {str(e)}")
        raise

async def create_indexes():
    """Cria índices otimizados para alta performance"""
    try:
        # Índices para contatos
        await db.db.contatos.create_index("telefone", unique=True)
        await db.db.contatos.create_index("chat_lid")
        
        # Índices compostos para sessões (mais eficientes)
        await db.db.sessoes.create_index([("contato_id", 1), ("status", 1)])
        await db.db.sessoes.create_index("ultima_interacao")
        
        # Índices para mensagens
        await db.db.mensagens.create_index([("sessao_id", 1), ("data_hora", -1)])
        await db.db.mensagens.create_index("message_id", unique=True, sparse=True)
        
        # Índices para filas
        await db.db.fila_envio.create_index([("status", 1), ("data_criacao", 1)])
        await db.db.fila_humana.create_index([("status", 1), ("prioridade", -1)])
        
        logger.info("✅ Índices do MongoDB criados com sucesso!")
        
    except Exception as e:
        logger.error(f"❌ Erro ao criar índices: {str(e)}")
        raise

async def close_mongo_connection():
    if db.client:
        db.client.close()
        logger.info("🔌 Conexão com MongoDB fechada")
