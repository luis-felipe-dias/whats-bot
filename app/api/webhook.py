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
        
        # ============================================
        # EXTRAIR MENSAGEM E MÍDIAS
        # ============================================
        mensagem = None
        tipo_mensagem = "texto"
        file_url = None
        file_name = None
        mime_type = None
        caption = None
        
        # Verificar se é imagem
        if "image" in body:
            image_data = body["image"]
            file_url = image_data.get("imageUrl")
            caption = image_data.get("caption", "")
            mime_type = image_data.get("mimeType", "image/jpeg")
            # Extrair nome do arquivo da URL
            if file_url:
                file_name = file_url.split("/")[-1].split("?")[0] or f"imagem_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            else:
                file_name = f"imagem_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            tipo_mensagem = "imagem"
            mensagem = caption if caption else "📷 Imagem recebida"
            logger.info(f"📷 IMAGEM - URL: {file_url}")
        
        # Verificar se é documento/PDF
        elif "document" in body:
            doc_data = body["document"]
            file_url = doc_data.get("documentUrl")
            file_name = doc_data.get("filename", f"documento_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
            mime_type = doc_data.get("mimeType", "application/pdf")
            caption = doc_data.get("caption", "")
            tipo_mensagem = "documento"
            mensagem = caption or f"📎 Documento recebido: {file_name}"
            logger.info(f"📎 DOCUMENTO - URL: {file_url}")
        
        # Verificar se é áudio
        elif "audio" in body:
            audio_data = body["audio"]
            file_url = audio_data.get("audioUrl")
            file_name = f"audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.ogg"
            mime_type = audio_data.get("mimeType", "audio/ogg")
            tipo_mensagem = "audio"
            mensagem = "🎤 Áudio recebido"
            logger.info(f"🎤 ÁUDIO - URL: {file_url}")
        
        # Verificar se é vídeo
        elif "video" in body:
            video_data = body["video"]
            file_url = video_data.get("videoUrl")
            file_name = f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            mime_type = video_data.get("mimeType", "video/mp4")
            tipo_mensagem = "video"
            mensagem = "📹 Vídeo recebido"
            logger.info(f"📹 VÍDEO - URL: {file_url}")
        
        # Verificar se é localização
        elif "location" in body:
            loc_data = body["location"]
            latitude = loc_data.get("latitude")
            longitude = loc_data.get("longitude")
            tipo_mensagem = "localizacao"
            mensagem = f"📍 Localização: {latitude}, {longitude}"
            file_url = f"https://maps.google.com/?q={latitude},{longitude}"
            logger.info(f"📍 LOCALIZAÇÃO: {latitude}, {longitude}")
        
        # Verificar se é contato
        elif "contact" in body:
            contact_data = body["contact"]
            nome = contact_data.get("name")
            numero = contact_data.get("phone")
            tipo_mensagem = "contato"
            mensagem = f"📇 Contato: {nome} - {numero}"
            logger.info(f"📇 CONTATO: {nome} - {numero}")
        
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
        
        # Texto normal
        elif "text" in body:
            if isinstance(body["text"], dict):
                mensagem = body["text"].get("message")
            elif isinstance(body["text"], str):
                mensagem = body["text"]
            tipo_mensagem = "texto"
            logger.info(f"📝 TEXTO: {mensagem}")
        
        # Botão reply
        elif "buttonReply" in body:
            btn_data = body["buttonReply"]
            mensagem = btn_data.get("message") or btn_data.get("label")
            tipo_mensagem = "reply"
            logger.info(f"🔘 REPLY: {mensagem}")
        
        if not mensagem and not file_url and tipo_mensagem == "desconhecido":
            logger.warning(f"⚠️ Tipo de mensagem não reconhecido")
            return JSONResponse(status_code=200, content={"status": "ignored"})
        
        if not telefone:
            return JSONResponse(status_code=200, content={"status": "ignored"})
        
        telefone_clean = ''.join(filter(str.isdigit, telefone))
        if len(telefone_clean) >= 10 and not telefone_clean.startswith('55'):
            telefone_clean = '55' + telefone_clean
        
        logger.info(f"📱 {telefone_clean} -> [{tipo_mensagem}] {mensagem[:50] if mensagem else 'arquivo'}")
        logger.info(f"👤 Cliente: {chat_name}")
        
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

async def process_message(telefone: str, mensagem: str, message_id: str, tipo: str = "texto", file_url: str = None, file_name: str = None, mime_type: str = None, caption: str = None, chat_name: str = None):
    try:
        contato_service = ContatoService()
        contato = await contato_service.get_or_create_contato(telefone, chat_name)
        
        # Se recebeu nome do chat, atualizar contato
        if chat_name and (contato.get("nome") == telefone or not contato.get("nome_personalizado")):
            await contato_service.atualizar_nome(contato["id"], chat_name)
        
        sessao_service = SessaoService()
        sessao = await sessao_service.get_or_create_sessao(contato["id"])
        
        # Atualizar sessão com nome do cliente
        if chat_name:
            await sessao_service.atualizar_sessao(sessao["id"], {"cliente_nome": chat_name})
        
        # SEMPRE salvar mensagem
        mensagem_service = MensagemService()
        
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
        
        # VERIFICAR CANCELAR PRIMEIRO
        if mensagem and (mensagem.upper() == "CANCELAR" or mensagem == "❌ CANCELAR"):
            logger.info(f"❌ CANCELAR detectado - resetando sessão")
            await sessao_service.atualizar_sessao(sessao["id"], {
                "status": "ativa",
                "estado_atual": "menu_principal",
                "human_response_sent": False,
                "last_menu": None,
                "menu_anterior": None,
                "setor_responsavel": None,
                "aguardando_atendente": True
            })
            await mensagem_service.enfileirar_resposta(
                contato_id=contato["id"],
                sessao_id=sessao["id"],
                mensagem="✅ Atendimento cancelado! Volte ao menu principal. 💙",
                botoes=["🛍️ PROMOÇÕES", "🖨️ SERVIÇOS", "🤝 ATENDIMENTO", "📍 INFORMAÇÕES", "💼 TRABALHE CONOSCO"]
            )
            return
        
        # Se está em atendimento humano, apenas salvar e marcar que cliente enviou
        if sessao.get("status") == "humano":
            logger.info(f"⏸️ Em atendimento humano - cliente enviou mensagem")
            await sessao_service.cliente_enviou_mensagem(sessao["id"])
            return
        
        # Processar resposta
        from app.core.state_machine import StateMachine
        sm = StateMachine()
        novo_estado, resposta = await sm.process_message(sessao, mensagem)
        
        # Salvar menu anterior antes de mudar
        menu_anterior = sessao.get("estado_atual", "menu_principal")
        
        # Atualizar sessão
        await sessao_service.atualizar_sessao(sessao["id"], {
            "estado_atual": novo_estado,
            "ultima_interacao": datetime.now(),
            "menu_anterior": menu_anterior
        })
        
        # Atendimento humano
        if resposta.get("status_humano"):
            setor = await sessao_service.ativar_atendimento_humano(sessao["id"], novo_estado, menu_anterior)
            logger.info(f"👤 Atendimento humano ativado - Origem: {menu_anterior} -> Setor: {setor}")
        
        # Enviar resposta
        if resposta.get("texto"):
            texto_resposta = resposta["texto"].replace("Frete grátis para compras acima de R$100! 💙", "")
            await mensagem_service.enfileirar_resposta(
                contato_id=contato["id"],
                sessao_id=sessao["id"],
                mensagem=texto_resposta,
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
