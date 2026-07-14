# app/api/webhook.py - CORREÇÃO PARA EXTRAIR MÍDIAS EM MENSAGENS DIRETAS
from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from app.services.mensagem_service import MensagemService
from app.services.sessao_service import SessaoService
from app.services.contato_service import ContatoService
from app.core.database import db
from datetime import datetime
import logging
import json
import re

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/webhook")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        body = await request.json()
        
        # ============================================
        # EXTRAIR DADOS PRINCIPAIS
        # ============================================
        telefone = body.get("phone")
        chat_name = body.get("chatName") or body.get("senderName")
        message_id_zapi = body.get("messageId")
        chat_id = body.get("chatLid")
        from_me = body.get("fromMe", False)
        from_api = body.get("fromApi", False)
        status = body.get("status")
        reference_message_id = body.get("referenceMessageId")
        is_status_reply = body.get("isStatusReply", False)
        instance_id = body.get("instanceId", "3F43467A7F5BF175DDAF66DA177DAE5D")
        
        # ============================================
        # IDENTIFICAR SE É GRUPO
        # ============================================
        is_group = False
        group_id = None
        
        if telefone and telefone.endswith("-group"):
            is_group = True
            group_id = telefone
            logger.info(f"📢 GRUPO DETECTADO: {group_id}")
        
        # ============================================
        # REGRA 1: IGNORAR CONFIRMAÇÕES DA API (fromApi=true)
        # ============================================
        if from_api:
            logger.info(f"⏭️ IGNORANDO: Confirmação da API - ID: {message_id_zapi}")
            return JSONResponse(status_code=200, content={"status": "ignored", "reason": "from_api"})
        
        # ============================================
        # EXTRAIR MENSAGEM E MÍDIAS
        # ============================================
        mensagem = None
        tipo = "texto"
        file_url = None
        file_name = None
        mime_type = None
        caption = None
        is_media = False
        
        # TEXTO
        if "text" in body:
            if isinstance(body["text"], dict):
                mensagem = body["text"].get("message")
            elif isinstance(body["text"], str):
                mensagem = body["text"]
            if mensagem:
                logger.info(f"📝 TEXTO: {mensagem[:50] if mensagem else 'vazio'}")
        
        # IMAGEM
        if "image" in body:
            image_data = body["image"]
            file_url = image_data.get("imageUrl")
            caption = image_data.get("caption", "")
            mime_type = image_data.get("mimeType", "image/jpeg")
            file_name = f"imagem_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            tipo = "imagem"
            mensagem = caption if caption else "📷 Imagem recebida"
            is_media = True
            logger.info(f"📷 IMAGEM - URL: {file_url}")
        
        # DOCUMENTO
        elif "document" in body:
            doc_data = body["document"]
            file_url = doc_data.get("documentUrl")
            file_name = doc_data.get("filename", f"documento_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
            mime_type = doc_data.get("mimeType", "application/pdf")
            caption = doc_data.get("caption", "")
            tipo = "documento"
            mensagem = caption or f"📎 Documento recebido: {file_name}"
            is_media = True
            logger.info(f"📎 DOCUMENTO - URL: {file_url}")
        
        # ÁUDIO
        elif "audio" in body:
            audio_data = body["audio"]
            file_url = audio_data.get("audioUrl")
            file_name = f"audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.ogg"
            mime_type = audio_data.get("mimeType", "audio/ogg")
            tipo = "audio"
            mensagem = "🎤 Áudio recebido"
            is_media = True
            logger.info(f"🎤 ÁUDIO - URL: {file_url}")
        
        # VÍDEO
        elif "video" in body:
            video_data = body["video"]
            file_url = video_data.get("videoUrl")
            file_name = f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            mime_type = video_data.get("mimeType", "video/mp4")
            tipo = "video"
            mensagem = "📹 Vídeo recebido"
            is_media = True
            logger.info(f"📹 VÍDEO - URL: {file_url}")
        
        # BOTÕES
        elif "buttonsResponseMessage" in body:
            btn_data = body["buttonsResponseMessage"]
            mensagem = btn_data.get("message")
            tipo = "botao"
            logger.info(f"🔘 BOTÃO: {mensagem}")
        
        # LISTA
        elif "listResponseMessage" in body:
            list_data = body["listResponseMessage"]
            mensagem = list_data.get("title")
            tipo = "lista"
            logger.info(f"📋 LISTA: {mensagem}")
        
        # REPLY
        elif "buttonReply" in body:
            btn_data = body["buttonReply"]
            mensagem = btn_data.get("message") or btn_data.get("label")
            tipo = "reply"
            logger.info(f"🔘 REPLY: {mensagem}")
        
        if not mensagem and not file_url and not is_media:
            logger.warning(f"⚠️ Mensagem vazia, ignorando")
            return JSONResponse(status_code=200, content={"status": "ignored"})
        
        if not chat_id:
            chat_id = telefone
        
        # ============================================
        # REGRA 2: MENSAGEM DO ATENDENTE (from_me=true, fromApi=false)
        # ============================================
        if from_me:
            logger.info(f"📤 Mensagem enviada DIRETAMENTE pelo WhatsApp (atendente)")
            logger.info(f"📱 Chat ID: {chat_id} -> [{tipo}] {mensagem[:50] if mensagem else 'arquivo'}")
            
            if is_group:
                background_tasks.add_task(
                    process_group_message,
                    group_id,
                    mensagem,
                    str(datetime.now().timestamp()),
                    chat_name,
                    message_id_zapi,
                    chat_id,
                    telefone,
                    instance_id,
                    "atendente",
                    tipo,
                    file_url,
                    file_name,
                    mime_type,
                    caption,
                    is_media,
                    reference_message_id,
                    is_status_reply
                )
            else:
                background_tasks.add_task(
                    process_individual_message,
                    chat_id,
                    mensagem,
                    str(datetime.now().timestamp()),
                    chat_name,
                    message_id_zapi,
                    chat_id,
                    telefone,
                    instance_id,
                    "atendente",
                    tipo,
                    file_url,
                    file_name,
                    mime_type,
                    caption,
                    is_media,
                    reference_message_id,
                    is_status_reply
                )
            
            return JSONResponse(status_code=200, content={"status": "received"})
        
        # ============================================
        # REGRA 3: MENSAGEM DO CLIENTE (from_me=false)
        # ============================================
        logger.info(f"📥 Mensagem recebida DO CLIENTE")
        logger.info(f"📱 Chat ID: {chat_id} -> [{tipo}] {mensagem[:50] if mensagem else 'arquivo'}")
        
        if is_group:
            # GRUPO: NÃO PROCESSAR COM O BOT
            background_tasks.add_task(
                process_group_message,
                group_id,
                mensagem,
                str(datetime.now().timestamp()),
                chat_name,
                message_id_zapi,
                chat_id,
                telefone,
                instance_id,
                "cliente",
                tipo,
                file_url,
                file_name,
                mime_type,
                caption,
                is_media,
                reference_message_id,
                is_status_reply
            )
        else:
            # INDIVIDUAL: PROCESSAR COM O BOT
            background_tasks.add_task(
                process_individual_message,
                chat_id,
                mensagem,
                str(datetime.now().timestamp()),
                chat_name,
                message_id_zapi,
                chat_id,
                telefone,
                instance_id,
                "cliente",
                tipo,
                file_url,
                file_name,
                mime_type,
                caption,
                is_media,
                reference_message_id,
                is_status_reply
            )
        
        return JSONResponse(status_code=200, content={"status": "received"})
        
    except Exception as e:
        logger.error(f"❌ Erro webhook: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(status_code=200, content={"status": "error"})

# ============================================
# PROCESSAR MENSAGEM DE GRUPO
# ============================================
async def process_group_message(group_id: str, mensagem: str, message_id: str, chat_name: str, message_id_zapi: str, chat_id: str, telefone: str, instance_id: str, sender: str, tipo: str = "texto", file_url: str = None, file_name: str = None, mime_type: str = None, caption: str = None, is_media: bool = False, reference_message_id: str = None, is_status_reply: bool = False):
    """Processa mensagens de grupo - APENAS SALVA"""
    try:
        logger.info(f"📝 SALVANDO MENSAGEM DE GRUPO: {group_id} - sender: {sender} - tipo: {tipo}")
        
        # Buscar ou criar contato do grupo
        contato = await db.db.contatos.find_one({"telefone": group_id})
        if not contato:
            contato_data = {
                "telefone": group_id,
                "nome": chat_name or f"Grupo {group_id}",
                "nome_personalizado": True,
                "data_criacao": datetime.now(),
                "data_atualizacao": datetime.now(),
                "ultima_interacao": datetime.now(),
                "tags": ["grupo"],
                "observacoes": f"Grupo WhatsApp - ID: {group_id}",
                "is_group": True
            }
            result = await db.db.contatos.insert_one(contato_data)
            contato = contato_data
            contato["_id"] = result.inserted_id
            logger.info(f"✨ Novo contato de grupo criado: {group_id}")
        
        contato["id"] = str(contato["_id"])
        
        # Buscar ou criar sessão do grupo
        sessao = await db.db.sessoes.find_one({"group_id": group_id, "is_group": True})
        if not sessao:
            sessao_data = {
                "contato_id": contato["id"],
                "group_id": group_id,
                "is_group": True,
                "status": "humano",
                "estado_atual": "grupo",
                "dados_contexto": {},
                "data_inicio": datetime.now(),
                "ultima_interacao": datetime.now(),
                "arquivo_pendente": False,
                "human_response_sent": False,
                "last_menu": None,
                "menu_anterior": None,
                "setor_responsavel": "grupo",
                "aguardando_atendente": False,
                "cliente_nome": contato["nome"],
                "chat_id": chat_id,
                "instance_id": instance_id,
                "telefone": group_id
            }
            result = await db.db.sessoes.insert_one(sessao_data)
            sessao = sessao_data
            sessao["_id"] = result.inserted_id
            logger.info(f"✨ Nova sessão de grupo criada: {group_id}")
        else:
            await db.db.sessoes.update_one(
                {"_id": sessao["_id"]},
                {"$set": {"ultima_interacao": datetime.now()}}
            )
        
        # Salvar mensagem
        mensagem_service = MensagemService()
        direcao = "enviada" if sender == "atendente" else "recebida"
        
        if is_media and file_url:
            await mensagem_service.salvar_mensagem_com_midia(
                sessao_id=str(sessao["_id"]),
                contato_id=contato["id"],
                conteudo=mensagem,
                conteudo_original=message_id,
                tipo=tipo,
                file_url=file_url,
                file_name=file_name,
                mime_type=mime_type,
                caption=caption,
                message_id_zapi=message_id_zapi,
                sender=sender,
                direcao=direcao
            )
        else:
            await mensagem_service.salvar_mensagem_recebida(
                sessao_id=str(sessao["_id"]),
                contato_id=contato["id"],
                conteudo=mensagem,
                conteudo_original=message_id,
                tipo=tipo,
                file_url=file_url,
                file_name=file_name,
                mime_type=mime_type,
                caption=caption,
                message_id_zapi=message_id_zapi,
                reference_message_id=reference_message_id,
                is_status_reply=is_status_reply,
                chat_id=chat_id,
                sender=sender,
                direcao=direcao
            )
        
        await db.db.sessoes.update_one(
            {"_id": sessao["_id"]},
            {"$set": {"ultima_interacao": datetime.now()}}
        )
        
        logger.info(f"✅ Mensagem de grupo salva: {group_id} - sender: {sender} - tipo: {tipo}")
        
    except Exception as e:
        logger.error(f"❌ Erro process_group_message: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

# ============================================
# PROCESSAR MENSAGEM INDIVIDUAL
# ============================================
async def process_individual_message(chat_key: str, mensagem: str, message_id: str, chat_name: str, message_id_zapi: str, chat_id: str, telefone: str, instance_id: str, sender: str, tipo: str = "texto", file_url: str = None, file_name: str = None, mime_type: str = None, caption: str = None, is_media: bool = False, reference_message_id: str = None, is_status_reply: bool = False):
    """Processa mensagem individual"""
    try:
        logger.info(f"📝 Processando mensagem individual: {chat_key} - sender: {sender} - tipo: {tipo}")
        
        # 1. BUSCAR OU CRIAR SESSÃO
        sessao = await db.db.sessoes.find_one({"chat_id": chat_key})
        if not sessao and telefone:
            sessao = await db.db.sessoes.find_one({"telefone": telefone})
        
        # 2. CRIAR OU BUSCAR CONTATO
        contato_service = ContatoService()
        
        if sender == "cliente" and telefone:
            contato = await contato_service.get_or_create_contato(telefone, chat_name)
            if chat_name:
                await contato_service.atualizar_nome(contato["id"], chat_name)
        else:
            if telefone:
                contato = await db.db.contatos.find_one({"telefone": telefone})
            else:
                contato = None
            
            if not contato and sessao and sessao.get("contato_id"):
                contato = await db.db.contatos.find_one({"_id": sessao["contato_id"]})
            
            if not contato:
                contato = await contato_service.get_or_create_contato(chat_key, chat_name or "Sistema")
        
        contato["id"] = str(contato["_id"])
        
        # 3. CRIAR SESSÃO SE NÃO EXISTIR
        if not sessao:
            sessao_data = {
                "contato_id": contato["id"],
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
                "aguardando_atendente": False,
                "cliente_nome": contato["nome"],
                "chat_id": chat_key,
                "instance_id": instance_id,
                "telefone": telefone
            }
            result = await db.db.sessoes.insert_one(sessao_data)
            sessao = sessao_data
            sessao["_id"] = result.inserted_id
            logger.info(f"✨ Nova sessão criada - chat_id: {chat_key}")
        else:
            sessao_service = SessaoService()
            update_data = {"ultima_interacao": datetime.now()}
            if telefone and not sessao.get("telefone"):
                update_data["telefone"] = telefone
            if chat_name and not sessao.get("cliente_nome"):
                update_data["cliente_nome"] = chat_name
            
            await sessao_service.atualizar_sessao(str(sessao["_id"]), update_data)
            logger.info(f"📌 Sessão existente: {sessao['_id']}")
        
        # 4. SALVAR MENSAGEM
        mensagem_service = MensagemService()
        direcao = "enviada" if sender == "atendente" else "recebida"
        
        if is_media and file_url:
            await mensagem_service.salvar_mensagem_com_midia(
                sessao_id=str(sessao["_id"]),
                contato_id=contato["id"],
                conteudo=mensagem,
                conteudo_original=message_id,
                tipo=tipo,
                file_url=file_url,
                file_name=file_name,
                mime_type=mime_type,
                caption=caption,
                message_id_zapi=message_id_zapi,
                sender=sender,
                direcao=direcao
            )
        else:
            await mensagem_service.salvar_mensagem_recebida(
                sessao_id=str(sessao["_id"]),
                contato_id=contato["id"],
                conteudo=mensagem,
                conteudo_original=message_id,
                tipo=tipo,
                file_url=file_url,
                file_name=file_name,
                mime_type=mime_type,
                caption=caption,
                message_id_zapi=message_id_zapi,
                reference_message_id=reference_message_id,
                is_status_reply=is_status_reply,
                chat_id=chat_key,
                sender=sender,
                direcao=direcao
            )
        
        # 5. PROCESSAR COM O BOT (APENAS SE FOR CLIENTE)
        if sender == "cliente":
            logger.info(f"🤖 Processando mensagem do cliente com o bot")
            
            sessao_service = SessaoService()
            
            # CANCELAR
            if mensagem and (mensagem.upper() == "CANCELAR" or mensagem == "❌ CANCELAR"):
                await sessao_service.cancelar_atendimento_humano(str(sessao["_id"]))
                await mensagem_service.enfileirar_resposta(
                    contato_id=contato["id"],
                    sessao_id=str(sessao["_id"]),
                    mensagem="✅ Atendimento cancelado! Volte ao menu principal. 💙",
                    botoes=["🛍️ PROMOÇÕES", "🖨️ SERVIÇOS", "🤝 ATENDIMENTO", "📍 INFORMAÇÕES", "💼 TRABALHE CONOSCO"],
                    sender="pepper"
                )
                return
            
            # Se está em atendimento humano
            if sessao.get("status") == "humano":
                await sessao_service.cliente_enviou_mensagem(str(sessao["_id"]))
                return
            
            # Processar com state machine
            from app.core.state_machine import StateMachine
            sm = StateMachine()
            novo_estado, resposta = await sm.process_message(sessao, mensagem)
            
            menu_anterior = sessao.get("estado_atual", "menu_principal")
            
            await sessao_service.atualizar_sessao(str(sessao["_id"]), {
                "estado_atual": novo_estado,
                "ultima_interacao": datetime.now(),
                "menu_anterior": menu_anterior
            })
            
            if resposta.get("status_humano"):
                setor_definido = resposta.get("setor")
                menu_anterior_definido = resposta.get("menu_anterior")
                
                await sessao_service.atualizar_sessao(str(sessao["_id"]), {
                    "setor_responsavel": setor_definido,
                    "menu_anterior": menu_anterior_definido,
                    "status": "humano",
                    "human_response_sent": False,
                    "aguardando_atendente": True
                })
                
                logger.info(f"👤 Atendimento humano ativado - Setor: {setor_definido}")
            
            if resposta.get("texto"):
                await mensagem_service.enfileirar_resposta(
                    contato_id=contato["id"],
                    sessao_id=str(sessao["_id"]),
                    mensagem=resposta["texto"],
                    botoes=resposta.get("botoes", []),
                    sender="pepper"
                )
            
            if resposta.get("criar_fila_humana"):
                from app.services.fila_humana_service import FilaHumanaService
                fila_service = FilaHumanaService()
                await fila_service.criar_ticket(
                    sessao_id=str(sessao["_id"]),
                    contato_id=contato["id"],
                    tipo=resposta.get("tipo_fila", "atendimento")
                )
        else:
            logger.info(f"📤 Mensagem do atendente salva - chat: {chat_key}")
            sessao_service = SessaoService()
            await sessao_service.atualizar_sessao(str(sessao["_id"]), {
                "ultima_interacao": datetime.now()
            })
        
        logger.info(f"✅ Mensagem processada - chat: {chat_key} - sender: {sender} - tipo: {tipo}")
        
    except Exception as e:
        logger.error(f"❌ Erro process_individual_message: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
