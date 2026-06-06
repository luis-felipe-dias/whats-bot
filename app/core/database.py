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
    """Conecta ao MongoDB Atlas com configurações otimizadas"""
    try:
        # Configurações para MongoDB Atlas
        db.client = AsyncIOMotorClient(
            settings.mongodb_url,
            maxPoolSize=50,
            minPoolSize=10,
            maxIdleTimeMS=45000,
            waitQueueTimeoutMS=10000,
            connectTimeoutMS=30000,
            socketTimeoutMS=30000,
            serverSelectionTimeoutMS=30000,
            retryWrites=True,
            retryReads=True
        )
        
        # Testar conexão
        await db.client.admin.command('ping')
        logger.info("✅ Conectado ao MongoDB Atlas com sucesso!")
        
        db.db = db.client[settings.mongodb_db_name]
        
        # Criar índices
        await create_indexes()
        
    except Exception as e:
        logger.error(f"❌ Erro ao conectar ao MongoDB Atlas: {str(e)}")
        raise

async def create_indexes():
    """Cria índices otimizados para o MongoDB Atlas"""
    try:
        # Índices para contatos
        await db.db.contatos.create_index("telefone", unique=True)
        await db.db.contatos.create_index("data_criacao")
        await db.db.contatos.create_index("ultima_interacao")
        
        # Índices para sessões
        await db.db.sessoes.create_index("contato_id")
        await db.db.sessoes.create_index("status")
        await db.db.sessoes.create_index([("contato_id", 1), ("status", 1)])
        await db.db.sessoes.create_index("ultima_interacao", expireAfterSeconds=10800)  # 3 horas TTL
        
        # Índices para mensagens
        await db.db.mensagens.create_index("sessao_id")
        await db.db.mensagens.create_index("data_hora")
        await db.db.mensagens.create_index([("sessao_id", 1), ("data_hora", -1)])
        
        # Índices para filas
        await db.db.fila_envio.create_index("status")
        await db.db.fila_envio.create_index([("status", 1), ("data_criacao", 1)])
        
        await db.db.fila_humana.create_index("status")
        await db.db.fila_humana.create_index([("status", 1), ("prioridade", -1), ("data_criacao", 1)])
        
        # Índices para eventos
        await db.db.eventos.create_index("data_hora")
        await db.db.eventos.create_index([("contato_id", 1), ("data_hora", -1)])
        await db.db.eventos.create_index("tipo")
        
        # Índices para estatísticas
        await db.db.estatisticas.create_index("data", unique=True)
        
        logger.info("✅ Índices do MongoDB criados com sucesso!")
        
    except Exception as e:
        logger.error(f"❌ Erro ao criar índices: {str(e)}")
        raise

async def close_mongo_connection():
    """Fecha conexão com MongoDB Atlas"""
    if db.client:
        db.client.close()
        logger.info("🔌 Conexão com MongoDB Atlas fechada")