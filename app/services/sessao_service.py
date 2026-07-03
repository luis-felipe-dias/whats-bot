# app/services/sessao_service.py
from app.core.database import db
from datetime import datetime, timedelta
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)

class SessaoService:
    
    # Mapeamento de menu_anterior para setor responsável
    MAPA_SETORES = {
        "reclamacao": "ouvidoria",
        "trocas": "comercial",
        "pedido": "financeiro",
        "servicos": "tecnico",
        "impressao": "tecnico",
        "encadernacao": "tecnico",
        "plastificacao": "tecnico",
        "curriculo": "rh",
        "atendimento": "atendimento",
        "informacoes": "atendimento",
        "promocoes": "comercial",
        "trabalhe": "rh",
        "sugestoes": "qualidade"
    }
    
    async def get_or_create_sessao(self, contato_id: str):
        """Busca sessão ativa ou cria nova"""
        try:
            logger.info(f"Buscando sessão para contato_id: {contato_id}")
            
            sessao = await db.db.sessoes.find_one({
                "contato_id": contato_id,
                "status": {"$in": ["ativa", "humano", "fila_humana", "aguardando_atendente"]}
            })
            
            if not sessao:
                sessao = {
                    "contato_id": contato_id,
                    "status": "ativa",
                    "estado_atual": "menu_principal",
                    "dados_contexto": {},
                    "data_inicio": datetime.now(),
                    "ultima_interacao": datetime.now(),
                    "arquivo_pendente": False,
                    "human_response_sent": False,
                    "last_menu": None,
                    "menu_anterior": None,
                    "setor_responsavel": None,
                    "aguardando_atendente": True
                }
                result = await db.db.sessoes.insert_one(sessao)
                sessao["_id"] = result.inserted_id
                logger.info(f"✨ Nova sessão criada: {result.inserted_id}")
            
            sessao["id"] = str(sessao["_id"])
            return sessao
            
        except Exception as e:
            logger.error(f"Erro ao buscar/criar sessão: {str(e)}")
            raise
    
    async def atualizar_sessao(self, sessao_id: str, dados: dict):
        try:
            if isinstance(sessao_id, str):
                sessao_id = ObjectId(sessao_id)
            
            dados["ultima_interacao"] = datetime.now()
            await db.db.sessoes.update_one({"_id": sessao_id}, {"$set": dados})
            logger.info(f"📝 Sessão atualizada: {sessao_id}")
            
        except Exception as e:
            logger.error(f"Erro ao atualizar sessão: {str(e)}")
            raise
    
    async def ativar_atendimento_humano(self, sessao_id: str, novo_estado: str, menu_anterior: str):
        """Ativa atendimento humano e define o setor responsável baseado no menu anterior"""
        try:
            # O setor é definido pelo menu anterior (de onde veio a solicitação)
            setor = self.MAPA_SETORES.get(menu_anterior, "atendimento")
            
            await self.atualizar_sessao(sessao_id, {
                "status": "humano",
                "last_menu": novo_estado,
                "menu_anterior": menu_anterior,
                "setor_responsavel": setor,
                "human_response_sent": False,
                "aguardando_atendente": True
            })
            logger.info(f"👤 Atendimento humano ativado - Origem: {menu_anterior} -> Setor: {setor}")
            return setor
        except Exception as e:
            logger.error(f"Erro ao ativar atendimento humano: {str(e)}")
            raise
    
    async def registrar_resposta_atendente(self, sessao_id: str, atendente_id: str = None):
        """Registra que o atendente respondeu"""
        try:
            await self.atualizar_sessao(sessao_id, {
                "human_response_sent": True,
                "aguardando_atendente": False,
                "atendente_id": atendente_id
            })
            logger.info(f"💬 Atendente respondeu - aguardando_atendente=False")
        except Exception as e:
            logger.error(f"Erro ao registrar resposta: {str(e)}")
            raise
    
    async def cliente_enviou_mensagem(self, sessao_id: str):
        """Cliente enviou mensagem - se atendente já respondeu, volta para aguardando"""
        try:
            sessao = await db.db.sessoes.find_one({"_id": ObjectId(sessao_id)})
            if sessao and sessao.get("status") == "humano":
                if sessao.get("human_response_sent") == True:
                    # Atendente já respondeu, cliente enviou nova mensagem
                    await self.atualizar_sessao(sessao_id, {
                        "aguardando_atendente": True,
                        "human_response_sent": False
                    })
                    logger.info(f"📨 Cliente enviou mensagem após resposta - aguardando_atendente=True")
                else:
                    # Ainda aguardando primeira resposta
                    logger.info(f"⏳ Cliente aguardando atendente - mensagem salva")
        except Exception as e:
            logger.error(f"Erro ao processar mensagem do cliente: {str(e)}")
            raise
    
    async def listar_sessoes_abertas(self):
        """Retorna TODAS as sessões humanas em aberto com informações detalhadas"""
        try:
            sessoes = await db.db.sessoes.find({
                "status": {"$in": ["humano", "aguardando_atendente"]}
            }).sort("data_inicio", 1).to_list(length=None)
            
            resultado = []
            for sessao in sessoes:
                contato = await db.db.contatos.find_one({"_id": ObjectId(sessao["contato_id"])})
                
                # Contar mensagens não respondidas
                mensagens_nao_respondidas = await db.db.mensagens.count_documents({
                    "sessao_id": str(sessao["_id"]),
                    "direcao": "recebida",
                    "respondida": {"$ne": True}
                })
                
                resultado.append({
                    "session_id": str(sessao["_id"]),
                    "phone": contato.get("telefone") if contato else "unknown",
                    "contact_name": contato.get("nome") if contato else "Cliente",
                    "menu_anterior": sessao.get("menu_anterior"),  # O menu que originou o atendimento
                    "last_menu": sessao.get("last_menu"),  # O menu atual
                    "setor_responsavel": sessao.get("setor_responsavel", "atendimento"),
                    "human_response_sent": sessao.get("human_response_sent", False),
                    "aguardando_atendente": sessao.get("aguardando_atendente", True),
                    "created_at": sessao.get("data_inicio").isoformat() if sessao.get("data_inicio") else None,
                    "last_interaction": sessao.get("ultima_interacao").isoformat() if sessao.get("ultima_interacao") else None,
                    "unread_messages": mensagens_nao_respondidas
                })
            return resultado
        except Exception as e:
            logger.error(f"Erro ao listar sessões abertas: {str(e)}")
            return []
    
    async def get_historico_sessao(self, sessao_id: str):
        """Retorna todas as mensagens da sessão com identificação de remetente"""
        try:
            mensagens = await db.db.mensagens.find({
                "sessao_id": sessao_id
            }).sort("data_hora", 1).to_list(length=None)
            
            resultado = []
            for msg in mensagens:
                remetente = "cliente"
                if msg.get("direcao") == "enviada":
                    if msg.get("sender") == "human":
                        remetente = "atendente"
                    else:
                        remetente = "pepper"
                
                item = {
                    "sender": remetente,
                    "message": msg.get("conteudo"),
                    "timestamp": msg.get("data_hora").isoformat() if msg.get("data_hora") else None,
                    "type": msg.get("tipo", "texto"),
                    "respondida": msg.get("respondida", False)
                }
                
                # Adicionar dados de mídia se existir
                if msg.get("file_url"):
                    item["file_url"] = msg.get("file_url")
                    item["file_name"] = msg.get("file_name")
                    item["mime_type"] = msg.get("mime_type")
                
                resultado.append(item)
            return resultado
        except Exception as e:
            logger.error(f"Erro ao buscar histórico: {str(e)}")
            return []
    
    async def enviar_mensagem_humana(self, sessao_id: str, mensagem: str, atendente_nome: str = "Atendente"):
        """Envia mensagem do atendente para o cliente"""
        try:
            sessao = await db.db.sessoes.find_one({"_id": ObjectId(sessao_id)})
            if not sessao:
                raise Exception("Sessão não encontrada")
            
            contato = await db.db.contatos.find_one({"_id": ObjectId(sessao["contato_id"])})
            if not contato:
                raise Exception("Contato não encontrado")
            
            # Salvar mensagem do atendente
            mensagem_data = {
                "sessao_id": sessao_id,
                "contato_id": sessao["contato_id"],
                "direcao": "enviada",
                "sender": "human",
                "tipo": "texto",
                "conteudo": mensagem,
                "data_hora": datetime.now(),
                "respondida": True,
                "atendente": atendente_nome
            }
            await db.db.mensagens.insert_one(mensagem_data)
            
            # Marcar mensagens anteriores como respondidas
            await db.db.mensagens.update_many(
                {"sessao_id": sessao_id, "direcao": "recebida", "respondida": {"$ne": True}},
                {"$set": {"respondida": True}}
            )
            
            # Atualizar sessão
            await self.registrar_resposta_atendente(sessao_id)
            
            # Enviar para WhatsApp
            from app.core.whatsapp_api import WhatsAppAPI
            whatsapp = WhatsAppAPI()
            sucesso = await whatsapp.send_text(contato["telefone"], mensagem)
            
            return {"success": sucesso, "message": "Mensagem enviada" if sucesso else "Falha ao enviar"}
            
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem humana: {str(e)}")
            return {"success": False, "error": str(e)}
