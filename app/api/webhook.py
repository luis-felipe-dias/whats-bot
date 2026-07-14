# app/api/webhook.py - CORREÇÃO PARA IDENTIFICAR QUEM ENVIOU
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
        status = body.get("status")
        reference_message_id = body.get("referenceMessageId")
        is_status_reply = body.get("isStatusReply", False)
        is_group = body.get("isGroup", False)
        instance_id = body.get("instanceId", "3F43467A7F5BF175DDAF66DA177DAE5D")
        
        # ============================================
        # DETERMINAR QUEM ENVIOU A MENSAGEM
        # ============================================
        # Se from_me = true, a mensagem foi enviada PELO SISTEMA (atendente ou bot)
        # Se from_me = false, a mensagem foi enviada PELO CLIENTE
        
        # MAS importante: se for uma mídia (imagem, documento, etc) e from_me = true,
        # é o atendente que enviou, não o cliente!
        
        is_system_message = from_me  # True = enviado pelo sistema (atendente)
        is_client_message = not from_me  # False = enviado pelo cliente
        
        sender = "cliente"
        direcao = "recebida"
        
        if is_system_message:
            sender = "atendente"
            direcao = "enviada"
            logger.info(f"📤 Mensagem enviada PELO ATENDENTE (from_me=true)")
        else:
            sender = "cliente"
            direcao = "recebida"
            logger.info(f"📥 Mensagem recebida DO CLIENTE (from_me=false)")
        
        logger.info(f"📨 Webhook - chat_id: {chat_id}, from_me: {from_me}, sender: {sender}")
        
        # ============================================
        # EXTRAIR MENSAGEM (TEXTO OU MÍDIA)
        # ============================================
        mensagem = None
        tipo_mensagem = "texto"
        file_url = None
        file_name = None
        mime_type = None
        caption = None
        is_media = False
        
        # Texto
        if "text" in body:
            if isinstance(body["text"], dict):
                mensagem = body["text"].get("message")
            elif isinstance(body["text"], str):
                mensagem = body["text"]
            logger.info(f"📝 TEXTO: {mensagem}")
        
        # Imagem
        if "image" in body:
            image_data = body["image"]
            file_url = image_data.get("imageUrl")
            caption = image_data.get("caption", "")
            mime_type = image_data.get("mimeType", "image/jpeg")
            file_name = f"imagem_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            tipo_mensagem = "imagem"
            mensagem = caption if caption else "📷 Imagem recebida"
            is_media = True
            logger.info(f"📷 IMAGEM - sender: {sender}")
        
        # Documento
        elif "document" in body:
            doc_data = body["document"]
            file_url = doc_data.get("documentUrl")
            file_name = doc_data.get("filename", f"documento_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
            mime_type = doc_data.get("mimeType", "application/pdf")
            caption = doc_data.get("caption", "")
            tipo_mensagem = "documento"
            mensagem = caption or f"📎 Documento recebido: {file_name}"
            is_media = True
            logger.info(f"📎 DOCUMENTO - sender: {sender}")
        
        # Áudio
        elif "audio" in body:
            audio_data = body["audio"]
            file_url = audio_data.get("audioUrl")
            file_name = f"audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.ogg"
            mime_type = audio_data.get("mimeType", "audio/ogg")
            tipo_mensagem = "audio"
            mensagem = "🎤 Áudio recebido"
            is_media = True
            logger.info(f"🎤 ÁUDIO - sender: {sender}")
        
        # Vídeo
        elif "video" in body:
            video_data = body["video"]
            file_url = video_data.get("videoUrl")
            file_name = f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            mime_type = video_data.get("mimeType", "video/mp4")
            tipo_mensagem = "video"
            mensagem = "📹 Vídeo recebido"
            is_media = True
            logger.info(f"📹 VÍDEO - sender: {sender}")
        
        # Localização
        elif "location" in body:
            loc_data = body["location"]
            latitude = loc_data.get("latitude")
            longitude = loc_data.get("longitude")
            tipo_mensagem = "localizacao"
            mensagem = f"📍 Localização: {latitude}, {longitude}"
            file_url = f"https://maps.google.com/?q={latitude},{longitude}"
            logger.info(f"📍 LOCALIZAÇÃO - sender: {sender}")
        
        # Contato
        elif "contact" in body:
            contact_data = body["contact"]
            nome = contact_data.get("name")
            numero = contact_data.get("phone")
            tipo_mensagem = "contato"
            mensagem = f"📇 Contato: {nome} - {numero}"
            logger.info(f"📇 CONTATO - sender: {sender}")
        
        # Botões
        elif "buttonsResponseMessage" in body:
            btn_data = body["buttonsResponseMessage"]
            mensagem = btn_data.get("message")
            tipo_mensagem = "botao"
            logger.info(f"🔘 BOTÃO: {mensagem}")
        
        # Lista de opções
        elif "listResponseMessage" in body:
            list_data = body["listResponseMessage"]
            mensagem = list_data.get("title")
            tipo_mensagem = "lista"
            logger.info(f"📋 LISTA: {mensagem}")
        
        # Reply
        elif "buttonReply" in body:
            btn_data = body["buttonReply"]
            mensagem = btn_data.get("message") or btn_data.get("label")
            tipo_mensagem = "reply"
            logger.info(f"🔘 REPLY: {mensagem}")
        
        if not mensagem and not file_url and not is_media:
            logger.warning(f"⚠️ Mensagem vazia, ignorando")
            return JSONResponse(status_code=200, content={"status": "ignored"})
        
        # ============================================
        # VERIFICAR SE É GRUPO
        # ============================================
        is_group = False
        group_id = None
        
        if telefone and telefone.endswith("-group"):
            is_group = True
            group_id = telefone
            logger.info(f"📢 GRUPO DETECTADO: {group_id}")
        
        # Verificar se é resposta
        is_reply = False
        if reference_message_id:
            is_reply = True
            logger.info(f"💬 Mensagem é uma RESPOSTA ao ID: {reference_message_id}")
        
        if is_status_reply:
            logger.info(f"📌 Mensagem é um STATUS REPLY")
        
        # ============================================
        # PROCESSAR MENSAGEM
        # ============================================
        if is_group:
            background_tasks.add_task(
                process_group_message_only,
                group_id,
                mensagem,
                str(datetime.now().timestamp()),
                chat_name,
                message_id_zapi,
                reference_message_id,
                is_reply,
                is_status_reply,
                from_me,
                chat_id,
                status,
                sender,
                direcao,
                file_url,
                file_name,
                mime_type,
                caption,
                tipo_mensagem,
                instance_id,
                is_media
            )
        else:
            # USAR CHAT_ID COMO IDENTIFICADOR PRINCIPAL
            if not chat_id:
                chat_id = telefone
            
            logger.info(f"📱 Chat ID: {chat_id} -> [{tipo_mensagem}] {mensagem[:50] if mensagem else 'arquivo'} - sender: {sender}")
            
            background_tasks.add_task(
                process_all_messages,
                chat_id,
                mensagem,
                str(datetime.now().timestamp()),
                tipo_mensagem,
                file_url,
                file_name,
                mime_type,
                caption,
                chat_name,
                message_id_zapi,
                reference_message_id,
                is_reply,
                is_status_reply,
                from_me,
                chat_id,
                status,
                sender,
                direcao,
                telefone,
                instance_id,
                is_media
            )
        
        return JSONResponse(status_code=200, content={"status": "received"})
        
    except Exception as e:
        logger.error(f"❌ Erro webhook: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(status_code=200, content={"status": "error"})

async def process_group_message_only(group_id: str, mensagem: str, message_id: str, group_name: str = None, message_id_zapi: str = None, reference_message_id: str = None, is_reply: bool = False, is_status_reply: bool = False, from_me: bool = False, chat_id: str = None, status: str = None, sender: str = "cliente", direcao: str = "recebida", file_url: str = None, file_name: str = None, mime_type: str = None, caption: str = None, tipo: str = "texto", instance_id: str = None, is_media: bool = False):
    """Processa mensagens de grupo"""
    try:
        logger.info(f"📝 Salvando mensagem de grupo: {group_id} - sender: {sender}")
        
        # Buscar ou criar contato do grupo
        contato = await db.db.contatos.find_one({"telefone": group_id})
        if not contato:
            contato_data = {
                "telefone": group_id,
                "nome": group_name or f"Grupo {group_id}",
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
                "instance_id": instance_id
            }
            result = await db.db.sessoes.insert_one(sessao_data)
            sessao = sessao_data
            sessao["_id"] = result.inserted_id
            logger.info(f"✨ Nova sessão de grupo criada: {group_id}")
        
        # Salvar mensagem
        mensagem_service = MensagemService()
        
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
                is_reply=is_reply,
                is_status_reply=is_status_reply,
                from_me=from_me,
                chat_id=chat_id,
                status=status,
                sender=sender,
                direcao=direcao
            )
        
        await db.db.sessoes.update_one(
            {"_id": sessao["_id"]},
            {"$set": {"ultima_interacao": datetime.now()}}
        )
        
        logger.info(f"✅ Mensagem de grupo salva: {group_id} - sender: {sender}")
        
    except Exception as e:
        logger.error(f"❌ Erro process_group_message_only: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

async def process_all_messages(chat_key: str, mensagem: str, message_id: str, tipo: str = "texto", file_url: str = None, file_name: str = None, mime_type: str = None, caption: str = None, chat_name: str = None, message_id_zapi: str = None, reference_message_id: str = None, is_reply: bool = False, is_status_reply: bool = False, from_me: bool = False, chat_id: str = None, status: str = None, sender: str = "cliente", direcao: str = "recebida", telefone: str = None, instance_id: str = None, is_media: bool = False):
    """Processa todas as mensagens - SALVA COM O SENDER CORRETO"""
    try:
        logger.info(f"📝 Processando mensagem para chat: {chat_key} - sender: {sender}")
        
        # 1. BUSCAR OU CRIAR SESSÃO
        sessao = await db.db.sessoes.find_one({"chat_id": chat_key})
        
        if not sessao and telefone:
            sessao = await db.db.sessoes.find_one({"telefone": telefone})
        
        # 2. CRIAR OU BUSCAR CONTATO
        contato_service = ContatoService()
        
        # Para mensagens do atendente (from_me=true), não criar novo contato
        if not from_me and telefone:
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
        
        # 4. SALVAR MENSAGEM COM O SENDER CORRETO
        mensagem_service = MensagemService()
        
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
                is_reply=is_reply,
                is_status_reply=is_status_reply,
                from_me=from_me,
                chat_id=chat_key,
                status=status,
                sender=sender,
                direcao=direcao
            )
        
        # 5. PROCESSAR SE FOR DO CLIENTE (from_me=false)
        if not from_me:
            logger.info(f"🤖 Processando mensagem do cliente com o bot")
            
            sessao_service = SessaoService()
            
            if mensagem and (mensagem.upper() == "CANCELAR" or mensagem == "❌ CANCELAR"):
                await sessao_service.cancelar_atendimento_humano(str(sessao["_id"]))
                await mensagem_service.enfileirar_resposta(
                    contato_id=contato["id"],
                    sessao_id=str(sessao["_id"]),
                    mensagem="✅ Atendimento cancelado! Volte ao menu principal. 💙",
                    botoes=["🛍️ PROMOÇÕES", "🖨️ SERVIÇOS", "🤝 ATENDIMENTO", "📍 INFORMAÇÕES", "💼 TRABALHE CONOSCO"]
                )
                return
            
            if sessao.get("status") == "humano":
                await sessao_service.cliente_enviou_mensagem(str(sessao["_id"]))
                return
            
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
                    botoes=resposta.get("botoes", [])
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
            logger.info(f"📤 Mensagem enviada pelo atendente - salva no histórico")
            sessao_service = SessaoService()
            await sessao_service.atualizar_sessao(str(sessao["_id"]), {
                "ultima_interacao": datetime.now()
            })
        
        logger.info(f"✅ Mensagem processada - chat: {chat_key} - sender: {sender}")
        
    except Exception as e:
        logger.error(f"❌ Erro process_all_messages: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
