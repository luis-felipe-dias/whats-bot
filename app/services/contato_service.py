# app/services/contato_service.py
from app.core.database import db
from datetime import datetime
from app.utils.helpers import now_utc
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)

class ContatoService:
    
    async def get_or_create_contato(self, chat_lid: str = None, telefone: str = None, nome: str = None, is_group: bool = False) -> dict:
        """
        Busca ou cria um contato seguindo a ordem de prioridade:
        1. chat_lid (prioritário)
        2. telefone
        3. Cria novo se nenhum existir
        """
        try:
            logger.info(f"🔍 Buscando contato: chat_lid={chat_lid}, telefone={telefone}")
            
            contato = None
            
            # 1. BUSCAR POR CHAT_LID (PRIORITÁRIO)
            if chat_lid:
                contato = await db.db.contatos.find_one({"chat_lid": chat_lid})
                if contato:
                    logger.info(f"📌 Contato encontrado por chat_lid: {chat_lid}")
                    # Atualizar telefone se necessário
                    if telefone and contato.get("telefone") != telefone:
                        await db.db.contatos.update_one(
                            {"_id": contato["_id"]},
                            {"$set": {"telefone": telefone, "data_atualizacao": now_utc()}}
                        )
                        contato["telefone"] = telefone
                        logger.info(f"🔄 Telefone atualizado para contato: {telefone}")
                    return self._format_contato(contato)
            
            # 2. BUSCAR POR TELEFONE (SECUNDÁRIO)
            if telefone and not contato:
                contato = await db.db.contatos.find_one({"telefone": telefone})
                if contato:
                    logger.info(f"📌 Contato encontrado por telefone: {telefone}")
                    # Atualizar chat_lid se necessário
                    if chat_lid and contato.get("chat_lid") != chat_lid:
                        await db.db.contatos.update_one(
                            {"_id": contato["_id"]},
                            {"$set": {"chat_lid": chat_lid, "data_atualizacao": now_utc()}}
                        )
                        contato["chat_lid"] = chat_lid
                        logger.info(f"🔄 chat_lid atualizado para contato: {chat_lid}")
                    return self._format_contato(contato)
            
            # 3. CRIAR NOVO CONTATO
            if not contato:
                logger.info(f"✨ Criando novo contato: chat_lid={chat_lid}, telefone={telefone}")
                contato_data = {
                    "chat_lid": chat_lid,
                    "telefone": telefone,
                    "nome": nome or telefone or "Cliente",
                    "nome_personalizado": bool(nome),
                    "is_group": is_group,
                    "data_criacao": now_utc(),
                    "data_atualizacao": now_utc(),
                    "ultima_interacao": now_utc(),
                    "tags": ["grupo"] if is_group else [],
                    "observacoes": f"{'Grupo' if is_group else 'Contato'} - chat_lid: {chat_lid}, telefone: {telefone}"
                }
                result = await db.db.contatos.insert_one(contato_data)
                contato_data["_id"] = result.inserted_id
                contato = contato_data
                logger.info(f"✅ Contato criado com ID: {result.inserted_id}")
            
            return self._format_contato(contato)
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar/criar contato: {str(e)}")
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
                    "data_atualizacao": now_utc()
                }}
            )
            logger.info(f"✏️ Nome atualizado: {contato_id} -> {nome}")
        except Exception as e:
            logger.error(f"Erro ao atualizar nome: {str(e)}")
            raise
    
    def _format_contato(self, contato: dict) -> dict:
        """Formata o contato para retorno"""
        contato["id"] = str(contato["_id"])
        return contato
