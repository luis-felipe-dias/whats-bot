# app/api/webhook.py
from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.schemas.webhook import WebhookMessage, WebhookResponse
from app.services.mensagem_service import MensagemService
from app.services.sessao_service import SessaoService
from app.services.contato_service import ContatoService
from app.core.database import db
from datetime import datetime
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/webhook", response_model=WebhookResponse)
async def whatsapp_webhook(message: WebhookMessage, background_tasks: BackgroundTasks):
    try:
        # Extrair dados da mensagem
        telefone = message.from_
        conteudo = message.text or ""
        message_id = message.message_id
        mensagem_tipo = message.type or "text"
        
        # Verificar se é grupo
        if message.is_group:
            logger.info(f"Mensagem ignorada - é grupo: {message.group_id}")
            return WebhookResponse(status="ignored", reason="group_message")
        
        # Verificar duplicata (evitar processar mesma mensagem duas vezes)
        existing_message = await db.db.mensagens.find_one({
            "conteudo_original": message_id
        })
        
        if existing_message:
            logger.info(f"Mensagem duplicada ignorada: {message_id}")
            return WebhookResponse(status="ignored", reason="duplicate")
        
        # Processar mensagem em background
        background_tasks.add_task(process_message, message.dict())
        
        return WebhookResponse(status="received", message="Mensagem recebida com sucesso")
        
    except Exception as e:
        logger.error(f"Erro no webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_message(message_data: dict):
    try:
        from app.services.mensagem_service import MensagemService
        from app.services.sessao_service import SessaoService
        from app.services.contato_service import ContatoService
        from app.core.state_machine import StateMachine
        
        # Extrair dados
        telefone = message_data.get("from_")
        conteudo = message_data.get("text", "")
        message_id = message_data.get("message_id")
        mensagem_tipo = message_data.get("type", "text")
        
        # Buscar ou criar contato
        contato_service = ContatoService()
        contato = await contato_service.get_or_create_contato(telefone)
        
        # Buscar sessão ativa
        sessao_service = SessaoService()
        sessao = await sessao_service.get_or_create_sessao(contato["id"])
        
        # Salvar mensagem recebida
        mensagem_service = MensagemService()
        await mensagem_service.salvar_mensagem_recebida(
            sessao_id=sessao["id"],
            contato_id=contato["id"],
            conteudo=conteudo,
            conteudo_original=message_id,
            tipo=mensagem_tipo
        )
        
        # Processar pelo state machine
        sm = StateMachine()
        novo_estado, resposta = await sm.process_message(sessao, conteudo)
        
        # Atualizar sessão
        await sessao_service.atualizar_sessao(sessao["id"], {
            "estado_atual": novo_estado,
            "ultima_interacao": datetime.now()
        })
        
        # Gerar resposta
        if resposta.get("texto"):
            await mensagem_service.enfileirar_resposta(
                contato_id=contato["id"],
                sessao_id=sessao["id"],
                mensagem=resposta["texto"]
            )
        
        # Criar fila humana se necessário
        if resposta.get("criar_fila_humana"):
            from app.services.fila_humana_service import FilaHumanaService
            fila_service = FilaHumanaService()
            await fila_service.criar_ticket(
                sessao_id=sessao["id"],
                contato_id=contato["id"],
                tipo=resposta.get("tipo_fila", "atendimento")
            )
            
            # Atualizar status da sessão
            await sessao_service.atualizar_sessao(sessao["id"], {
                "status": "fila_humana"
            })
        
        # Salvar avaliação se necessário
        if resposta.get("salvar_avaliacao"):
            await mensagem_service.salvar_avaliacao(
                sessao_id=sessao["id"],
                contato_id=contato["id"],
                nota=resposta["salvar_avaliacao"]
            )
        
        logger.info(f"Mensagem processada com sucesso: {message_id}")
        
    except Exception as e:
        logger.error(f"Erro ao processar mensagem: {str(e)}")