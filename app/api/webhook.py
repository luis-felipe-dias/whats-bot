# app/api/webhook.py - OTIMIZADO PARA ALTA PERFORMANCE
from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from app.services.mensagem_service import MensagemService
from app.services.sessao_service import SessaoService
from app.services.contato_service import ContatoService
from app.core.database import db
from app.utils.helpers import now_utc
from datetime import datetime, timedelta
import logging
import json
import asyncio

router = APIRouter()
logger = logging.getLogger(__name__)

# SEMÁFORO PARA CONTROLAR PROCESSAMENTO PARALELO
# Permite até 50 processamentos simultâneos
_semaphore = asyncio.Semaphore(50)

@router.post("/webhook")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        body = await request.json()
        
        # Extrair dados básicos rapidamente
        from_me = body.get("fromMe", False)
        message_id = body.get("messageId")
        is_group = body.get("isGroup", False)
        chat_name = body.get("chatName") or body.get("senderName")
        chat_lid = body.get("chatLid")
        phone = body.get("phone")
        
        # Determinar identificador
        if is_group:
            if phone and phone.endswith("-group"):
                identificador = phone
                telefone = phone
                chat_lid = None
            elif phone:
                identificador = phone
                telefone = phone
                chat_lid = None
            else:
                identificador = f"grupo_{chat_name or message_id}"
                telefone = identificador
                chat_lid = None
        else:
            if chat_lid:
                identificador = chat_lid
            else:
                identificador = phone
            
            if phone and not phone.endswith("-group"):
                telefone = ''.join(filter(str.isdigit, phone))
                if len(telefone) >= 10 and not telefone.startswith('55'):
                    telefone = '55' + telefone
            else:
                telefone = identificador
        
        # Extrair mensagem (apenas texto para validação rápida)
        mensagem = None
        tipo_mensagem = "texto"
        file_url = None
        file_name = None
        mime_type = None
        caption = None
        
        # Detectar tipo de conteúdo rapidamente
        if "image" in body:
            img = body["image"]
            file_url = img.get("imageUrl")
            caption = img.get("caption", "")
            mime_type = img.get("mimeType", "image/jpeg")
            file_name = f"imagem_{now_utc().strftime('%Y%m%d_%H%M%S')}.jpg"
            tipo_mensagem = "imagem"
            mensagem = caption or "📷 Imagem recebida"
        
        elif "document" in body:
            doc = body["document"]
            file_url = doc.get("documentUrl")
            file_name = doc.get("filename", f"documento_{now_utc().strftime('%Y%m%d_%H%M%S')}.pdf")
            mime_type = doc.get("mimeType", "application/pdf")
            caption = doc.get("caption", "")
            tipo_mensagem = "documento"
            mensagem = caption or f"📎 Documento: {file_name}"
        
        elif "audio" in body:
            audio = body["audio"]
            file_url = audio.get("audioUrl")
            file_name = f"audio_{now_utc().strftime('%Y%m%d_%H%M%S')}.ogg"
            mime_type = audio.get("mimeType", "audio/ogg")
            tipo_mensagem = "audio"
            mensagem = "🎤 Áudio recebido"
        
        elif "video" in body:
            video = body["video"]
            file_url = video.get("videoUrl")
            file_name = f"video_{now_utc().strftime('%Y%m%d_%H%M%S')}.mp4"
            mime_type = video.get("mimeType", "video/mp4")
            tipo_mensagem = "video"
            mensagem = "📹 Vídeo recebido"
        
        elif "location" in body:
            loc = body["location"]
            lat = loc.get("latitude")
            lng = loc.get("longitude")
            tipo_mensagem = "localizacao"
            mensagem = f"📍 Localização: {lat}, {lng}"
            file_url = f"https://maps.google.com/?q={lat},{lng}"
        
        elif "contact" in body:
            contact = body["contact"]
            nome = contact.get("name")
            numero = contact.get("phone")
            tipo_mensagem = "contato"
            mensagem = f"📇 Contato: {nome} - {numero}"
        
        elif "buttonsResponseMessage" in body:
            mensagem = body["buttonsResponseMessage"].get("message")
            tipo_mensagem = "botao"
        
        elif "listResponseMessage" in body:
            mensagem = body["listResponseMessage"].get("title")
            tipo_mensagem = "lista"
        
        elif "text" in body:
            if isinstance(body["text"], dict):
                mensagem = body["text"].get("message")
            elif isinstance(body["text"], str):
                mensagem = body["text"]
            tipo_mensagem = "texto"
        
        elif "buttonReply" in body:
            mensagem = body["buttonReply"].get("message") or body["buttonReply"].get("label")
            tipo_mensagem = "reply"
        
        if not mensagem and not file_url:
            return JSONResponse(status_code=200, content={"status": "ignored"})
        
        # Verificação rápida de duplicata (apenas para mensagens com ID)
        if message_id:
            existing = await db.db.mensagens.find_one({"message_id": message_id})
            if existing:
                return JSONResponse(status_code=200, content={"status": "ignored", "reason": "duplicate"})
        
        sender = "cliente" if not from_me else "atendente"
        
        # ADICIONAR À FILA DE PROCESSAMENTO (NÃO BLOQUEAR)
        background_tasks.add_task(
            process_webhook_message_with_semaphore,
            chat_lid,
            telefone,
            identificador,
            mensagem,
            message_id,
            tipo_mensagem,
            from_me,
            sender,
            is_group,
            chat_name,
            file_url,
            file_name,
            mime_type,
            caption
        )
        
        return JSONResponse(status_code=200, content={"status": "received"})
        
    except Exception as e:
        logger.error(f"❌ Erro webhook: {str(e)}")
        return JSONResponse(status_code=200, content={"status": "error"})

async def process_webhook_message_with_semaphore(*args, **kwargs):
    """Processa mensagem com controle de concorrência"""
    async with _semaphore:
        await process_webhook_message(*args, **kwargs)

async def process_webhook_message(chat_lid: str, telefone: str, identificador: str, mensagem: str, message_id: str, tipo: str, from_me: bool, sender: str, is_group: bool, chat_name: str, file_url: str = None, file_name: str = None, mime_type: str = None, caption: str = None):
    """Processa mensagem do webhook - OTIMIZADO"""
    try:
        # Buscar ou criar contato (com cache em memória)
        contato_service = ContatoService()
        
        if is_group:
            contato = await contato_service.get_or_create_contato(
                chat_lid=None,
                telefone=identificador,
                nome=chat_name or f"Grupo {identificador}",
                is_group=True
            )
        else:
            contato = await contato_service.get_or_create_contato(
                chat_lid=chat_lid,
                telefone=telefone,
                nome=chat_name,
                is_group=False
            )
        
        # Buscar sessão (com cache)
        sessao_service = SessaoService()
        sessao = await sessao_service.get_or_create_sessao(
            contato_id=contato["id"],
            is_group=is_group,
            identificador=identificador
        )
        
        # Verificar duplicata de atendente (rápido)
        if from_me:
            limite = now_utc() - timedelta(seconds=60)
            duplicata = await db.db.mensagens.find_one({
                "sessao_id": sessao["id"],
                "conteudo": mensagem,
                "data_hora": {"$gte": limite},
                "direcao": "enviada"
            })
            
            if duplicata:
                await sessao_service.atualizar_sessao(sessao["id"], {
                    "ultima_interacao": now_utc()
                })
                if not is_group:
                    await sessao_service.registrar_resposta_atendente(sessao["id"])
                return
        
        # Salvar mensagem (assíncrono)
        mensagem_service = MensagemService()
        
        if tipo in ["imagem", "documento", "audio", "video", "localizacao", "contato"]:
            await mensagem_service.salvar_mensagem_webhook(
                sessao_id=sessao["id"],
                contato_id=contato["id"],
                conteudo=mensagem,
                message_id=message_id,
                tipo=tipo,
                sender=sender,
                from_me=from_me,
                file_url=file_url,
                file_name=file_name,
                mime_type=mime_type,
                caption=caption
            )
        else:
            await mensagem_service.salvar_mensagem_webhook(
                sessao_id=sessao["id"],
                contato_id=contato["id"],
                conteudo=mensagem,
                message_id=message_id,
                tipo=tipo,
                sender=sender,
                from_me=from_me
            )
        
        # Atualizar sessão
        await sessao_service.atualizar_sessao(sessao["id"], {
            "ultima_interacao": now_utc()
        })
        
        # Processar mensagem do cliente (não grupo)
        if not from_me and not is_group:
            # CANCELAR
            if mensagem.upper() == "CANCELAR" or mensagem == "❌ CANCELAR":
                await sessao_service.cancelar_atendimento_humano(sessao["id"])
                await mensagem_service.enfileirar_resposta(
                    contato_id=contato["id"],
                    sessao_id=sessao["id"],
                    mensagem="✅ Atendimento cancelado! Volte ao menu principal. 💙",
                    botoes=["🛍️ PROMOÇÕES", "🖨️ SERVIÇOS", "🤝 ATENDIMENTO", "📍 INFORMAÇÕES", "💼 TRABALHE CONOSCO"]
                )
                return
            
            # ATENDIMENTO HUMANO
            if sessao.get("status") == "humano":
                await sessao_service.cliente_enviou_mensagem(sessao["id"])
                return
            
            # PROCESSAR RESPOSTA DO BOT
            from app.core.state_machine import StateMachine
            sm = StateMachine()
            novo_estado, resposta = await sm.process_message(sessao, mensagem)
            
            menu_anterior = sessao.get("estado_atual", "menu_principal")
            
            await sessao_service.atualizar_sessao(sessao["id"], {
                "estado_atual": novo_estado,
                "ultima_interacao": now_utc(),
                "menu_anterior": menu_anterior
            })
            
            # ATIVAR ATENDIMENTO HUMANO
            if resposta.get("status_humano"):
                setor = resposta.get("setor")
                await sessao_service.atualizar_sessao(sessao["id"], {
                    "setor_responsavel": setor,
                    "menu_anterior": resposta.get("menu_anterior", menu_anterior),
                    "status": "humano",
                    "human_response_sent": False,
                    "aguardando_atendente": True
                })
            
            # ENVIAR RESPOSTA
            if resposta.get("texto"):
                await mensagem_service.enfileirar_resposta(
                    contato_id=contato["id"],
                    sessao_id=sessao["id"],
                    mensagem=resposta["texto"],
                    botoes=resposta.get("botoes", [])
                )
            
            # FILA HUMANA
            if resposta.get("criar_fila_humana"):
                from app.services.fila_humana_service import FilaHumanaService
                fila_service = FilaHumanaService()
                await fila_service.criar_ticket(
                    sessao_id=sessao["id"],
                    contato_id=contato["id"],
                    tipo=resposta.get("tipo_fila", "atendimento")
                )
        
        # MENSAGEM DO ATENDENTE OU GRUPO
        elif from_me or is_group:
            if not is_group:
                await sessao_service.registrar_resposta_atendente(sessao["id"])
        
    except Exception as e:
        logger.error(f"❌ Erro processando: {str(e)}")
