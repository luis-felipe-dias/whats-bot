# app/api/webhook.py
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
        
        telefone = body.get("phone") or body.get("from")
        chat_name = body.get("chatName") or body.get("senderName")
        
        # VERIFICAR SE É GRUPO (número termina com -group)
        is_group = False
        group_id = None
        
        if telefone and telefone.endswith("-group"):
            is_group = True
            group_id = telefone
            logger.info(f"📢 GRUPO DETECTADO: {group_id}")
        
        # Se for grupo, processar separadamente
        if is_group:
            # Extrair mensagem do grupo
            mensagem = None
            if "text" in body:
                if isinstance(body["text"], dict):
                    mensagem = body["text"].get("message")
                elif isinstance(body["text"], str):
                    mensagem = body["text"]
            elif "message" in body:
                mensagem = body["message"]
            
            if not mensagem:
                return JSONResponse(status_code=200, content={"status": "ignored"})
            
            logger.info(f"📢 MENSAGEM DE GRUPO - Grupo: {group_id} - Mensagem: {mensagem[:50]}")
            
            # Processar mensagem de grupo (apenas salvar, sem resposta do bot)
            background_tasks.add_task(
                process_group_message,
                group_id,
                mensagem,
                str(datetime.now().timestamp()),
                chat_name
            )
            
            return JSONResponse(status_code=200, content={"status": "ignored", "reason": "group_message"})
        
        # ============================================
        # MENSAGEM INDIVIDUAL (NORMAL)
        # ============================================
        mensagem = None
        tipo_mensagem = "texto"
        file_url = None
        file_name = None
        mime_type = None
        caption = None
        
        # Imagem
        if "image" in body:
            image_data = body["image"]
            file_url = image_data.get("imageUrl")
            caption = image_data.get("caption", "")
            mime_type = image_data.get("mimeType", "image/jpeg")
            file_name = f"imagem_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            tipo_mensagem = "imagem"
            mensagem = caption if caption else "📷 Imagem recebida"
            logger.info(f"📷 IMAGEM - URL: {file_url}")
        
        # Documento
        elif "document" in body:
            doc_data = body["document"]
            file_url = doc_data.get("documentUrl")
            file_name = doc_data.get("filename", f"documento_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
            mime_type = doc_data.get("mimeType", "application/pdf")
            caption = doc_data.get("caption", "")
            tipo_mensagem = "documento"
            mensagem = caption or f"📎 Documento recebido: {file_name}"
            logger.info(f"📎 DOCUMENTO - URL: {file_url}")
        
        # Áudio
        elif "audio" in body:
            audio_data = body["audio"]
            file_url = audio_data.get("audioUrl")
            file_name = f"audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.ogg"
            mime_type = audio_data.get("mimeType", "audio/ogg")
            tipo_mensagem = "audio"
            mensagem = "🎤 Áudio recebido"
            logger.info(f"🎤 ÁUDIO - URL: {file_url}")
        
        # Vídeo
        elif "video" in body:
            video_data = body["video"]
            file_url = video_data.get("videoUrl")
            file_name = f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            mime_type = video_data.get("mimeType", "video/mp4")
            tipo_mensagem = "video"
            mensagem = "📹 Vídeo recebido"
            logger.info(f"📹 VÍDEO - URL: {file_url}")
        
        # Localização
        elif "location" in body:
            loc_data = body["location"]
            latitude = loc_data.get("latitude")
            longitude = loc_data.get("longitude")
            tipo_mensagem = "localizacao"
            mensagem = f"📍 Localização: {latitude}, {longitude}"
            file_url = f"https://maps.google.com/?q={latitude},{longitude}"
            logger.info(f"📍 LOCALIZAÇÃO: {latitude}, {longitude}")
        
        # Contato
        elif "contact" in body:
            contact_data = body["contact"]
            nome = contact_data.get("name")
            numero = contact_data.get("phone")
            tipo_mensagem = "contato"
            mensagem = f"📇 Contato: {nome} - {numero}"
            logger.info(f"📇 CONTATO: {nome} - {numero}")
        
        # Botões
        elif "buttonsResponseMessage" in body:
            mensagem = body["buttonsResponseMessage"].get("message")
            tipo_mensagem = "botao"
            logger.info(f"🔘 BOTÃO: {mensagem}")
        
        # Lista de opções
        elif "listResponseMessage" in body:
            mensagem = body["listResponseMessage"].get("title")
            tipo_mensagem = "lista"
            logger.info(f"📋 LISTA: {mensagem}")
        
        # Texto
        elif "text" in body:
            if isinstance(body["text"], dict):
                mensagem = body["text"].get("message")
            elif isinstance(body["text"], str):
                mensagem = body["text"]
            tipo_mensagem = "texto"
            logger.info(f"📝 TEXTO: {mensagem}")
        
        # Reply
        elif "buttonReply" in body:
            mensagem = body["buttonReply"].get("message") or body["buttonReply"].get("label")
            tipo_mensagem = "reply"
            logger.info(f"🔘 REPLY: {mensagem}")
        
        if not mensagem and not file_url:
            return JSONResponse(status_code=200, content={"status": "ignored"})
        
        if not telefone:
            return JSONResponse(status_code=200, content={"status": "ignored"})
        
        telefone_clean = ''.join(filter(str.isdigit, telefone))
        if len(telefone_clean) >= 10 and not telefone_clean.startswith('55'):
            telefone_clean = '55' + telefone_clean
        
        logger.info(f"📱 {telefone_clean} -> [{tipo_mensagem}] {mensagem[:50] if mensagem else 'arquivo'}")
        
        background_tasks.add_task(
            process_message,
            telefone_clean,
            mensagem,
            str(datetime.now().timestamp()),
            tipo_mensagem,
            file_url,
            file_name,
            mime_type,
            caption,
            chat_name
        )
        
        return JSONResponse(status_code=200, content={"status": "received"})
        
    except Exception as e:
        logger.error(f"❌ Erro webhook: {str(e)}")
        return JSONResponse(status_code=200, content={"status": "error"})

async def process_group_message(group_id: str, mensagem: str, message_id: str, chat_name: str = None):
    """Processa mensagens de grupo - apenas salva no banco, sem interação do bot"""
    try:
        if not mensagem:
            return
        
        logger.info(f"📝 Processando mensagem de grupo: {group_id}")
        
        # Buscar ou criar sessão para o grupo
        sessao_service = SessaoService()
        
        # Buscar sessão do grupo
        sessao = await db.db.sessoes.find_one({
            "group_id": group_id, "contato_id": group_id,
            "is_group": True
        })
        
        if not sessao:
            # Criar sessão para o grupo
            from datetime import datetime, timezone
            agora = datetime.now(timezone.utc)
            sessao_data = {
                "contato_id": group_id,
                "group_id": group_id, "contato_id": group_id,
                "is_group": True,
                "status": "humano",  # Grupo sempre em atendimento humano
                "estado_atual": "grupo",
                "dados_contexto": {},
                "data_inicio": agora,
                "ultima_interacao": agora,
                "arquivo_pendente": False,
                "human_response_sent": False,
                "last_menu": None,
                "menu_anterior": None,
                "setor_responsavel": "grupo",
                "aguardando_atendente": False,
                "cliente_nome": chat_name or f"Grupo: {group_id}"
            }
            result = await db.db.sessoes.insert_one(sessao_data)
            sessao = sessao_data
            sessao["_id"] = result.inserted_id
            logger.info(f"✨ Nova sessão de grupo criada: {group_id}")
        else:
            logger.info(f"📌 Sessão de grupo existente: {group_id}")
        
        # Salvar mensagem do grupo
        mensagem_service = MensagemService()
        await mensagem_service.salvar_mensagem_recebida(
            sessao_id=str(sessao["_id"]),
            contato_id=group_id,
            conteudo=mensagem,
            conteudo_original=message_id,
            tipo="texto"
        )
        
        # Atualizar última interação
        from datetime import datetime, timezone
        await sessao_service.atualizar_sessao(str(sessao["_id"]), {
            "ultima_interacao": datetime.now(timezone.utc),
            "human_response_sent": False,
            "aguardando_atendente": True
        })
        
        logger.info(f"✅ Mensagem de grupo salva: {group_id}")
        
    except Exception as e:
        logger.error(f"❌ Erro process_group_message: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

async def process_message(telefone: str, mensagem: str, message_id: str, tipo: str = "texto", file_url: str = None, file_name: str = None, mime_type: str = None, caption: str = None, chat_name: str = None):
    try:
        contato_service = ContatoService()
        contato = await contato_service.get_or_create_contato(telefone, chat_name)
        
        if chat_name:
            await contato_service.atualizar_nome(contato["id"], chat_name)
        
        sessao_service = SessaoService()
        sessao = await sessao_service.get_or_create_sessao(contato["id"])
        
        if chat_name:
            await sessao_service.atualizar_sessao(sessao["id"], {"cliente_nome": chat_name})
        
        mensagem_service = MensagemService()
        
        # Salvar mensagem
        if tipo in ["imagem", "documento", "audio", "video", "localizacao", "contato"]:
            await mensagem_service.salvar_mensagem_com_midia(
                sessao_id=sessao["id"],
                contato_id=contato["id"],
                conteudo=mensagem,
                conteudo_original=message_id,
                tipo=tipo,
                file_url=file_url,
                file_name=file_name,
                mime_type=mime_type,
                caption=caption
            )
        else:
            await mensagem_service.salvar_mensagem_recebida(
                sessao_id=sessao["id"],
                contato_id=contato["id"],
                conteudo=mensagem,
                conteudo_original=message_id,
                tipo=tipo
            )
        
        # CANCELAR
        if mensagem and (mensagem.upper() == "CANCELAR" or mensagem == "❌ CANCELAR"):
            await sessao_service.cancelar_atendimento_humano(sessao["id"])
            await mensagem_service.enfileirar_resposta(
                contato_id=contato["id"],
                sessao_id=sessao["id"],
                mensagem="✅ Atendimento cancelado! Volte ao menu principal. 💙",
                botoes=["🛍️ PROMOÇÕES", "🖨️ SERVIÇOS", "🤝 ATENDIMENTO", "📍 INFORMAÇÕES", "💼 TRABALHE CONOSCO"]
            )
            return
        
        # Se está em atendimento humano
        if sessao.get("status") == "humano":
            await sessao_service.cliente_enviou_mensagem(sessao["id"])
            return
        
        # Processar resposta
        from app.core.state_machine import StateMachine
        sm = StateMachine()
        novo_estado, resposta = await sm.process_message(sessao, mensagem)
        
        menu_anterior = sessao.get("estado_atual", "menu_principal")
        
        await sessao_service.atualizar_sessao(sessao["id"], {
            "estado_atual": novo_estado,
            "ultima_interacao": datetime.now(),
            "menu_anterior": menu_anterior
        })
        
        # ATENDIMENTO HUMANO
        if resposta.get("status_humano"):
            setor_definido = resposta.get("setor")
            menu_anterior_definido = resposta.get("menu_anterior")
            
            await sessao_service.atualizar_sessao(sessao["id"], {
                "setor_responsavel": setor_definido,
                "menu_anterior": menu_anterior_definido,
                "status": "humano",
                "human_response_sent": False,
                "aguardando_atendente": True
            })
            
            logger.info(f"👤 Atendimento humano ativado - Setor: {setor_definido} - Menu anterior: {menu_anterior_definido}")
        
        # Enviar resposta
        if resposta.get("texto"):
            await mensagem_service.enfileirar_resposta(
                contato_id=contato["id"],
                sessao_id=sessao["id"],
                mensagem=resposta["texto"],
                botoes=resposta.get("botoes", [])
            )
        
        # Criar fila humana
        if resposta.get("criar_fila_humana"):
            from app.services.fila_humana_service import FilaHumanaService
            fila_service = FilaHumanaService()
            await fila_service.criar_ticket(
                sessao_id=sessao["id"],
                contato_id=contato["id"],
                tipo=resposta.get("tipo_fila", "atendimento")
            )
        
        logger.info(f"✅ Processado: {telefone}")
        
    except Exception as e:
        logger.error(f"❌ Erro processamento: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
