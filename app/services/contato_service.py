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
                    contato = await self._sincronizar_nome(contato, nome)
                    return self._format_contato(contato)

            # 2. BUSCAR POR TELEFONE (SECUNDÁRIO)
            if telefone and not contato:
                contato = await db.db.contatos.find_one({"telefone": telefone})
                if not contato:
                    # Fallback pro caso clássico do celular BR: o mesmo
                    # número às vezes é salvo com e sem o 9º dígito
                    # (55DDD9XXXXXXXX vs 55DDDXXXXXXXX), dependendo de
                    # quando/como o contato entrou. Sem isso, iniciar
                    # conversa pelo painel criava um contato duplicado
                    # pra alguém que já tinha conversado antes.
                    variante = self._variante_telefone_br(telefone)
                    if variante:
                        contato = await db.db.contatos.find_one({"telefone": variante})
                        if contato:
                            logger.info(f"📌 Contato encontrado por variante de telefone: {telefone} ~ {variante}")
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
                    contato = await self._sincronizar_nome(contato, nome)
                    return self._format_contato(contato)
            
            # 3. CRIAR NOVO CONTATO
            if not contato:
                logger.info(f"✨ Criando novo contato: chat_lid={chat_lid}, telefone={telefone}")
                contato_data = {
                    "chat_lid": chat_lid,
                    "telefone": telefone,
                    "nome": nome or telefone or "Cliente",
                    # "personalizado" = alguém do painel corrigiu manualmente.
                    # O nome que chega do próprio WhatsApp (chatName) é
                    # automático, não personalizado - por isso sempre nasce
                    # False, mesmo quando já veio um nome do WhatsApp.
                    "nome_personalizado": False,
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
    
    async def _sincronizar_nome(self, contato: dict, nome: str) -> dict:
        """
        Atualiza o nome automaticamente com o que vier do WhatsApp, mas só
        quando ninguém corrigiu esse nome manualmente pelo painel
        (nome_personalizado=True protege a correção). Sem isso, um contato
        criado sem chatName (ex: primeira mensagem foi uma mídia) ficava
        com o telefone como "nome" para sempre, mesmo depois do WhatsApp
        mandar o nome certo em mensagens seguintes.
        """
        if not nome:
            return contato
        if contato.get("nome_personalizado"):
            return contato
        if contato.get("nome") == nome:
            return contato
        await db.db.contatos.update_one(
            {"_id": contato["_id"]},
            {"$set": {"nome": nome, "data_atualizacao": now_utc()}}
        )
        contato["nome"] = nome
        logger.info(f"🔄 Nome sincronizado automaticamente: {nome}")
        return contato

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
    
    def _variante_telefone_br(self, telefone: str) -> str:
        """
        Gera a variante com/sem o 9º dígito de um celular BR normalizado
        (55DDNNNNNNNNN, 13 dígitos com o 9, ou 55DDNNNNNNNN, 12 sem).
        Retorna "" quando o formato não bate com nenhum dos dois casos.
        """
        if telefone.startswith('55') and len(telefone) == 13 and telefone[4] == '9':
            return telefone[:4] + telefone[5:]  # tira o 9
        if telefone.startswith('55') and len(telefone) == 12:
            return telefone[:4] + '9' + telefone[4:]  # adiciona o 9
        return ""

    def _format_contato(self, contato: dict) -> dict:
        """Formata o contato para retorno"""
        contato["id"] = str(contato["_id"])
        return contato
