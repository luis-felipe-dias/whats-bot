# app/services/sessao_service.py
from app.core.database import db
from datetime import datetime
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)

class SessaoService:
    
    async def get_or_create_sessao(self, contato_id: str):
        """Busca sessão ativa ou cria nova"""
        try:
            # Buscar sessão ativa
            sessao = await db.db.sessoes.find_one({
                "contato_id": contato_id,
                "status": {"$in": ["ativa", "humano", "fila_humana"]}
            })
            
            if not sessao:
                # Criar nova sessão
                sessao = {
                    "contato_id": contato_id,
                    "status": "ativa",
                    "estado_atual": "menu_principal",
                    "dados_contexto": {},
                    "data_inicio": datetime.now(),
                    "ultima_interacao": datetime.now(),
                    "arquivo_pendente": False
                }
                
                result = await db.db.sessoes.insert_one(sessao)
                sessao["_id"] = result.inserted_id
                
                # Registrar evento
                await db.db.eventos.insert_one({
                    "tipo": "sessao_criada",
                    "contato_id": contato_id,
                    "sessao_id": str(result.inserted_id),
                    "dados": {},
                    "data_hora": datetime.now()
                })
                
                logger.info(f"Nova sessão criada: {result.inserted_id}")
            
            # Converter ObjectId para string
            sessao["id"] = str(sessao["_id"])
            return sessao
            
        except Exception as e:
            logger.error(f"Erro ao buscar/criar sessão: {str(e)}")
            raise
    
    async def atualizar_sessao(self, sessao_id: str, dados: dict):
        """Atualiza dados da sessão"""
        try:
            dados["ultima_interacao"] = datetime.now()
            
            await db.db.sessoes.update_one(
                {"_id": ObjectId(sessao_id)},
                {"$set": dados}
            )
            
            logger.info(f"Sessão atualizada: {sessao_id}")
            
        except Exception as e:
            logger.error(f"Erro ao atualizar sessão: {str(e)}")
            raise
    
    async def finalizar_sessao(self, sessao_id: str):
        """Finaliza uma sessão"""
        try:
            await db.db.sessoes.update_one(
                {"_id": ObjectId(sessao_id)},
                {"$set": {
                    "status": "finalizada",
                    "data_fim": datetime.now()
                }}
            )
            
            # Registrar evento
            await db.db.eventos.insert_one({
                "tipo": "sessao_finalizada",
                "sessao_id": sessao_id,
                "dados": {},
                "data_hora": datetime.now()
            })
            
            logger.info(f"Sessão finalizada: {sessao_id}")
            
        except Exception as e:
            logger.error(f"Erro ao finalizar sessão: {str(e)}")
            raise