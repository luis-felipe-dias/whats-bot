# app/services/sessao_service.py
from app.core.database import db
from datetime import datetime, timezone
from bson import ObjectId
from app.core.config import TIMEZONE
from app.utils.helpers import now_utc, format_iso_brasilia
import logging

logger = logging.getLogger(__name__)

class SessaoService:
    
    MAPA_SETORES = {
        "atendente": "atendimento",
        "atendimento_humano": "atendimento",
        "humano": "atendimento",
        "meupedido": "financeiro",
        "pedido": "financeiro",
        "trocas": "comercial",
        "devolucoes": "comercial",
        "reclamacao": "ouvidoria",
        "reclamacoes": "ouvidoria",
        "servicos": "tecnico",
        "impressao": "tecnico",
        "encadernacao": "tecnico",
        "plastificacao": "tecnico",
        "curriculo": "rh",
        "trabalhe": "rh",
        "trabalhe_conosco": "rh",
        "promocoes": "comercial",
        "sugestoes": "qualidade",
        "informacoes": "atendimento",
        "default": "atendimento"
    }
    
    
    
    
    def _determinar_setor(self, menu_anterior: str) -> str:
        if not menu_anterior:
            return "atendimento"
        menu_lower = menu_anterior.lower().strip()
        for key, value in self.MAPA_SETORES.items():
            if key in menu_lower or menu_lower in key:
                return value
        return self.MAPA_SETORES["default"]
    
    async def get_or_create_sessao(self, contato_id: str, is_group: bool = False, identificador: str = None) -> dict:
        """
        Busca uma sessão existente ou cria uma nova para o contato.
        UM CONTATO = UMA SESSÃO ATIVA
        """
        try:
            logger.info(f"🔍 Buscando sessão para contato_id: {contato_id}")
            
            sessao = await db.db.sessoes.find_one({
                "contato_id": contato_id,
                "status": {"$in": ["ativa", "humano", "aguardando_atendente"]}
            })
            
            if sessao:
                logger.info(f"📌 Sessão existente: {sessao['_id']}")
                return self._format_sessao(sessao)
            
            logger.info(f"✨ Criando nova sessão para contato: {contato_id}")
            
            if is_group:
                sessao_data = {
                    "contato_id": contato_id,
                    "identificador": identificador,
                    "is_group": True,
                    "status": "humano",
                    "estado_atual": "grupo",
                    "dados_contexto": {},
                    "data_inicio": now_utc(),
                    "ultima_interacao": now_utc(),
                    "arquivo_pendente": False,
                    "human_response_sent": False,
                    "last_menu": None,
                    "menu_anterior": None,
                    "setor_responsavel": "grupo",
                    "aguardando_atendente": False,
                    "cliente_nome": f"Grupo {identificador}"
                }
            else:
                sessao_data = {
                    "contato_id": contato_id,
                    "identificador": identificador,
                    "is_group": False,
                    "status": "ativa",
                    "estado_atual": "menu_principal",
                    "dados_contexto": {},
                    "data_inicio": now_utc(),
                    "ultima_interacao": now_utc(),
                    "arquivo_pendente": False,
                    "human_response_sent": False,
                    "last_menu": None,
                    "menu_anterior": None,
                    "setor_responsavel": None,
                    "aguardando_atendente": False,
                    "cliente_nome": None
                }
            
            result = await db.db.sessoes.insert_one(sessao_data)
            sessao_data["_id"] = result.inserted_id
            logger.info(f"✅ Sessão criada: {result.inserted_id}")
            
            return self._format_sessao(sessao_data)
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar/criar sessão: {str(e)}")
            raise
    
    async def atualizar_sessao(self, sessao_id, dados: dict):
        try:
            if isinstance(sessao_id, str):
                if sessao_id.endswith("-group"):
                    pass
                elif len(sessao_id) == 24:
                    try:
                        sessao_id = ObjectId(sessao_id)
                    except:
                        pass
            
            dados["ultima_interacao"] = now_utc()
            await db.db.sessoes.update_one({"_id": sessao_id}, {"$set": dados})
            logger.info(f"📝 Sessão atualizada: {sessao_id}")
            
        except Exception as e:
            logger.error(f"Erro ao atualizar sessão: {str(e)}")
            raise
    
    async def ativar_atendimento_humano(self, sessao_id: str, novo_estado: str, menu_anterior: str):
        try:
            setor = self._determinar_setor(menu_anterior)
            
            await self.atualizar_sessao(sessao_id, {
                "status": "humano",
                "last_menu": novo_estado,
                "menu_anterior": menu_anterior,
                "setor_responsavel": setor,
                "human_response_sent": False,
                "aguardando_atendente": True
            })
            
            logger.info(f"👤 Atendimento humano ativado - Menu: '{menu_anterior}' -> Setor: {setor}")
            return setor
            
        except Exception as e:
            logger.error(f"Erro ao ativar atendimento humano: {str(e)}")
            raise
    
    async def cancelar_atendimento_humano(self, sessao_id: str, menu_anterior: str = "menu_principal"):
        try:
            await self.atualizar_sessao(sessao_id, {
                "status": "ativa",
                "estado_atual": "menu_principal",
                "setor_responsavel": None,
                "human_response_sent": False,
                "aguardando_atendente": False,
                "last_menu": None,
                "menu_anterior": None
            })
            logger.info(f"❌ Atendimento humano cancelado - Sessão resetada para menu_principal")
        except Exception as e:
            logger.error(f"Erro ao cancelar atendimento humano: {str(e)}")
            raise
    
    async def registrar_resposta_atendente(self, sessao_id: str, atendente_id: str = None):
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
        try:
            logger.info(f"📨 Processando mensagem do cliente para sessão: {sessao_id}")
            
            sessao = None
            try:
                if len(sessao_id) == 24:
                    sessao = await db.db.sessoes.find_one({"_id": ObjectId(sessao_id)})
                else:
                    sessao = await db.db.sessoes.find_one({"_id": sessao_id})
            except:
                sessao = await db.db.sessoes.find_one({"_id": sessao_id})
            
            if not sessao:
                logger.error(f"❌ Sessão não encontrada: {sessao_id}")
                return
            
            status = sessao.get("status")
            human_response_sent = sessao.get("human_response_sent", False)
            
            logger.info(f"📊 Status atual: status={status}, human_response_sent={human_response_sent}")
            
            if status in ["humano", "aguardando_atendente"]:
                if human_response_sent == True:
                    await self.atualizar_sessao(sessao_id, {
                        "aguardando_atendente": True,
                        "human_response_sent": False
                    })
                    logger.info(f"📨 Cliente enviou mensagem após resposta - aguardando_atendente=True")
                else:
                    logger.info(f"⏳ Cliente aguardando atendente - mensagem salva")
            else:
                logger.info(f"📩 Mensagem do cliente salva - sessão ativa (status={status})")
                
        except Exception as e:
            logger.error(f"Erro ao processar mensagem do cliente: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def listar_sessoes_abertas(self):
        try:
            sessoes = await db.db.sessoes.find({
                "status": {"$in": ["humano", "aguardando_atendente"]}
            }).sort("data_inicio", 1).to_list(length=None)
            
            resultado = []
            for sessao in sessoes:
                contato = await db.db.contatos.find_one({"_id": ObjectId(sessao["contato_id"])})
                
                resultado.append({
                    "session_id": str(sessao["_id"]),
                    "phone": sessao.get("identificador") or (contato.get("telefone") if contato else "unknown"),
                    "contact_name": sessao.get("cliente_nome") or (contato.get("nome") if contato else "Cliente"),
                    "menu_anterior": sessao.get("menu_anterior"),
                    "last_menu": sessao.get("last_menu"),
                    "setor_responsavel": sessao.get("setor_responsavel", "atendimento"),
                    "human_response_sent": sessao.get("human_response_sent", False),
                    "aguardando_atendente": sessao.get("aguardando_atendente", True),
                    "created_at": format_iso_brasilia(sessao.get("data_inicio")),
                    "last_interaction": format_iso_brasilia(sessao.get("ultima_interacao")),
                    "is_group": sessao.get("is_group", False),
                    "unread_messages": await db.db.mensagens.count_documents({
                        "sessao_id": str(sessao["_id"]),
                        "direcao": "recebida",
                        "respondida": {"$ne": True}
                    })
                })
            return resultado
        except Exception as e:
            logger.error(f"Erro ao listar sessões abertas: {str(e)}")
            return []
    
    async def get_historico_sessao(self, sessao_id: str):
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
                    "timestamp": format_iso_brasilia(msg.get("data_hora")),
                    "type": msg.get("tipo", "texto"),
                    "respondida": msg.get("respondida", False)
                }
                
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
        try:
            logger.info(f"📤 Enviando mensagem humana para sessão: {sessao_id}")
            
            sessao = None
            try:
                if len(sessao_id) == 24:
                    sessao = await db.db.sessoes.find_one({"_id": ObjectId(sessao_id)})
                else:
                    sessao = await db.db.sessoes.find_one({"_id": sessao_id})
            except:
                sessao = await db.db.sessoes.find_one({"_id": sessao_id})
            
            if not sessao:
                logger.error(f"❌ Sessão não encontrada: {sessao_id}")
                return {"success": False, "error": "Sessão não encontrada"}
            
            logger.info(f"✅ Sessão encontrada: {sessao['_id']} - is_group: {sessao.get('is_group', False)}")
            
            telefone_destino = None
            
            if sessao.get("is_group"):
                telefone_destino = sessao.get("identificador")
                if not telefone_destino:
                    return {"success": False, "error": "Group ID não encontrado"}
                logger.info(f"📤 Enviando mensagem para grupo: {telefone_destino}")
            else:
                contato = await db.db.contatos.find_one({"_id": ObjectId(sessao["contato_id"])})
                if not contato:
                    return {"success": False, "error": "Contato não encontrado"}
                telefone_destino = contato.get("telefone")
                if not telefone_destino:
                    return {"success": False, "error": "Telefone não encontrado"}
                logger.info(f"📤 Enviando mensagem para contato: {telefone_destino}")
            
            mensagem_data = {
                "sessao_id": sessao_id,
                "contato_id": sessao["contato_id"],
                "direcao": "enviada",
                "sender": "human",
                "tipo": "texto",
                "conteudo": mensagem,
                "data_hora": now_utc(),
                "respondida": True,
                "atendente": atendente_nome
            }
            await db.db.mensagens.insert_one(mensagem_data)
            logger.info(f"✅ Mensagem do atendente salva no histórico")
            
            await db.db.mensagens.update_many(
                {"sessao_id": sessao_id, "direcao": "recebida", "respondida": {"$ne": True}},
                {"$set": {"respondida": True}}
            )
            
            await self.registrar_resposta_atendente(sessao_id)
            
            from app.core.whatsapp_api import WhatsAppAPI
            whatsapp = WhatsAppAPI()
            sucesso = await whatsapp.send_text(telefone_destino, mensagem)
            
            if sucesso:
                logger.info(f"✅ Mensagem enviada com sucesso para {telefone_destino}")
            else:
                logger.error(f"❌ Falha ao enviar mensagem para {telefone_destino}")
            
            return {"success": sucesso, "message": "Mensagem enviada" if sucesso else "Falha ao enviar"}
            
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem humana: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {"success": False, "error": str(e)}
    
    async def finalizar_sessao(self, sessao_id: str):
        try:
            await self.atualizar_sessao(sessao_id, {
                "status": "finalizada",
                "data_fim": now_utc()
            })
            logger.info(f"🏁 Sessão finalizada: {sessao_id}")
        except Exception as e:
            logger.error(f"Erro ao finalizar sessão: {str(e)}")
            raise
    
    async def get_sessao_por_id(self, sessao_id: str):
        try:
            sessao = await db.db.sessoes.find_one({"_id": sessao_id})
            if not sessao:
                return None
            
            contato = await db.db.contatos.find_one({"_id": ObjectId(sessao["contato_id"])})
            
            return {
                "sessao_id": str(sessao["_id"]),
                "cliente": sessao.get("cliente_nome") or (contato.get("nome") if contato else "Desconhecido"),
                "telefone": sessao.get("identificador") or (contato.get("telefone") if contato else "Desconhecido"),
                "status": sessao.get("status"),
                "estado_atual": sessao.get("estado_atual"),
                "setor_responsavel": sessao.get("setor_responsavel"),
                "aguardando_atendente": sessao.get("aguardando_atendente", False),
                "data_inicio": format_iso_brasilia(sessao.get("data_inicio")),
                "ultima_interacao": format_iso_brasilia(sessao.get("ultima_interacao")),
                "menu_anterior": sessao.get("menu_anterior"),
                "last_menu": sessao.get("last_menu"),
                "human_response_sent": sessao.get("human_response_sent", False),
                "is_group": sessao.get("is_group", False),
                "identificador": sessao.get("identificador")
            }
        except Exception as e:
            logger.error(f"Erro ao buscar sessão: {str(e)}")
            return None
    
    def _format_sessao(self, sessao: dict) -> dict:
        """Formata a sessão para retorno"""
        sessao["id"] = str(sessao["_id"])
        return sessao
