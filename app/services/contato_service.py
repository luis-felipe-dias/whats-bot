# app/services/contato_service.py
from app.core.database import db
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ContatoService:
    
    async def get_or_create_contato(self, telefone: str):
        """Busca contato existente ou cria novo"""
        try:
            # Buscar contato
            contato = await db.db.contatos.find_one({"telefone": telefone})
            
            if not contato:
                # Criar novo contato
                contato = {
                    "telefone": telefone,
                    "nome": telefone,  # Nome temporário
                    "nome_personalizado": False,
                    "data_criacao": datetime.now(),
                    "data_atualizacao": datetime.now(),
                    "ultima_interacao": datetime.now(),
                    "tags": [],
                    "observacoes": ""
                }
                
                result = await db.db.contatos.insert_one(contato)
                contato["_id"] = result.inserted_id
                
                # Registrar evento
                await db.db.eventos.insert_one({
                    "tipo": "contato_criado",
                    "contato_id": str(result.inserted_id),
                    "dados": {"telefone": telefone},
                    "data_hora": datetime.now()
                })
                
                logger.info(f"Novo contato criado: {telefone}")
            
            # Converter ObjectId para string
            contato["id"] = str(contato["_id"])
            return contato
            
        except Exception as e:
            logger.error(f"Erro ao buscar/criar contato: {str(e)}")
            raise
    
    async def atualizar_contato(self, contato_id: str, dados: dict):
        """Atualiza dados do contato"""
        try:
            dados["data_atualizacao"] = datetime.now()
            
            await db.db.contatos.update_one(
                {"_id": contato_id},
                {"$set": dados}
            )
            
            logger.info(f"Contato atualizado: {contato_id}")
            
        except Exception as e:
            logger.error(f"Erro ao atualizar contato: {str(e)}")
            raise