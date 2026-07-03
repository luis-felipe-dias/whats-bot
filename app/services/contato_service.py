# app/services/contato_service.py
from app.core.database import db
from datetime import datetime
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)

class ContatoService:
    
    async def get_or_create_contato(self, telefone: str, nome: str = None):
        """Busca contato existente ou cria novo"""
        try:
            if not telefone or telefone == "None":
                telefone = "unknown"
            
            logger.info(f"Buscando/criando contato para telefone: {telefone}")
            
            contato = await db.db.contatos.find_one({"telefone": telefone})
            
            if not contato:
                # Criar novo contato com o nome do chat se disponível
                contato = {
                    "telefone": telefone,
                    "nome": nome if nome else telefone,
                    "nome_personalizado": bool(nome),  # Se veio nome, marca como personalizado
                    "data_criacao": datetime.now(),
                    "data_atualizacao": datetime.now(),
                    "ultima_interacao": datetime.now(),
                    "tags": [],
                    "observacoes": ""
                }
                
                result = await db.db.contatos.insert_one(contato)
                contato["_id"] = result.inserted_id
                logger.info(f"✨ Novo contato criado: {telefone} - Nome: {contato['nome']}")
            else:
                logger.info(f"📌 Contato existente: {telefone} - Nome: {contato.get('nome')}")
                
                # Se o contato não tem nome personalizado e recebemos um nome, atualiza
                if nome and not contato.get("nome_personalizado", False):
                    await self.atualizar_nome(str(contato["_id"]), nome)
                    contato["nome"] = nome
                    contato["nome_personalizado"] = True
                
                # Atualizar última interação
                await db.db.contatos.update_one(
                    {"_id": contato["_id"]},
                    {"$set": {"ultima_interacao": datetime.now()}}
                )
            
            contato["id"] = str(contato["_id"])
            return contato
            
        except Exception as e:
            logger.error(f"Erro ao buscar/criar contato: {str(e)}")
            raise
    
    async def atualizar_nome(self, contato_id: str, nome: str):
        """Atualiza o nome do contato"""
        try:
            if isinstance(contato_id, str):
                contato_id = ObjectId(contato_id)
            
            await db.db.contatos.update_one(
                {"_id": contato_id},
                {"$set": {
                    "nome": nome,
                    "nome_personalizado": True,
                    "data_atualizacao": datetime.now()
                }}
            )
            logger.info(f"✏️ Nome do contato atualizado: {contato_id} -> {nome}")
        except Exception as e:
            logger.error(f"Erro ao atualizar nome: {str(e)}")
            raise
    
    async def atualizar_contato(self, contato_id: str, dados: dict):
        """Atualiza dados do contato"""
        try:
            if isinstance(contato_id, str):
                contato_id = ObjectId(contato_id)
            
            dados["data_atualizacao"] = datetime.now()
            
            await db.db.contatos.update_one(
                {"_id": contato_id},
                {"$set": dados}
            )
            
            logger.info(f"📝 Contato atualizado: {contato_id}")
            
        except Exception as e:
            logger.error(f"Erro ao atualizar contato: {str(e)}")
            raise
