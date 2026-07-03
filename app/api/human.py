# app/api/human.py - APIs de Atendimento Humano
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.services.sessao_service import SessaoService
from app.core.database import db
from app.core.whatsapp_api import WhatsAppAPI
from bson import ObjectId
from datetime import datetime
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class MensagemRequest(BaseModel):
    mensagem: str
    atendente_nome: Optional[str] = "Atendente"

class MensagemMidiaRequest(BaseModel):
    tipo_midia: str  # imagem, documento, audio, video
    midia_url: str
    legenda: Optional[str] = None
    nome_arquivo: Optional[str] = None
    atendente_nome: Optional[str] = "Atendente"

# ============================================
# LISTAR TODAS AS SESSÕES
# ============================================
@router.get("/sessoes")
async def listar_todas_sessoes():
    """Lista todas as sessões com seus status"""
    try:
        sessoes = await db.db.sessoes.find().sort("data_inicio", -1).to_list(length=100)
        resultado = []
        for sessao in sessoes:
            contato = await db.db.contatos.find_one({"_id": ObjectId(sessao["contato_id"])})
            resultado.append({
                "sessao_id": str(sessao["_id"]),
                "cliente": sessao.get("cliente_nome") or (contato.get("nome") if contato else "Desconhecido"),
                "telefone": contato.get("telefone") if contato else "Desconhecido",
                "status": sessao.get("status"),
                "estado_atual": sessao.get("estado_atual"),
                "setor_responsavel": sessao.get("setor_responsavel"),
                "aguardando_atendente": sessao.get("aguardando_atendente", True),
                "data_inicio": sessao.get("data_inicio").isoformat() if sessao.get("data_inicio") else None,
                "ultima_interacao": sessao.get("ultima_interacao").isoformat() if sessao.get("ultima_interacao") else None
            })
        return {"sucesso": True, "sessoes": resultado}
    except Exception as e:
        logger.error(f"Erro ao listar sessões: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# LISTAR SESSÕES ABERTAS (AGUARDANDO ATENDENTE)
# ============================================
@router.get("/sessoes/abertas")
async def get_sessoes_abertas():
    """Retorna todas as sessões humanas em aberto"""
    try:
        sessao_service = SessaoService()
        sessions = await sessao_service.listar_sessoes_abertas()
        return {"sucesso": True, "sessoes": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# BUSCAR UMA SESSÃO ESPECÍFICA
# ============================================
@router.get("/sessoes/{session_id}")
async def buscar_sessao(session_id: str):
    """Busca uma sessão específica pelo ID"""
    try:
        sessao = await db.db.sessoes.find_one({"_id": ObjectId(session_id)})
        if not sessao:
            raise HTTPException(status_code=404, detail="Sessão não encontrada")
        
        contato = await db.db.contatos.find_one({"_id": ObjectId(sessao["contato_id"])})
        
        return {
            "sucesso": True,
            "sessao": {
                "sessao_id": str(sessao["_id"]),
                "cliente": sessao.get("cliente_nome") or (contato.get("nome") if contato else "Desconhecido"),
                "telefone": contato.get("telefone") if contato else "Desconhecido",
                "status": sessao.get("status"),
                "estado_atual": sessao.get("estado_atual"),
                "setor_responsavel": sessao.get("setor_responsavel"),
                "aguardando_atendente": sessao.get("aguardando_atendente", True),
                "data_inicio": sessao.get("data_inicio").isoformat() if sessao.get("data_inicio") else None,
                "ultima_interacao": sessao.get("ultima_interacao").isoformat() if sessao.get("ultima_interacao") else None,
                "menu_anterior": sessao.get("menu_anterior"),
                "last_menu": sessao.get("last_menu"),
                "human_response_sent": sessao.get("human_response_sent", False)
            }
        }
    except Exception as e:
        logger.error(f"Erro ao buscar sessão: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# HISTÓRICO DE MENSAGENS DA SESSÃO
# ============================================
@router.get("/sessoes/{session_id}/mensagens")
async def get_sessao_mensagens(session_id: str):
    """Retorna o histórico de mensagens da sessão"""
    try:
        sessao_service = SessaoService()
        messages = await sessao_service.get_historico_sessao(session_id)
        return {"sucesso": True, "mensagens": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# ENVIAR MENSAGEM DE TEXTO
# ============================================
@router.post("/sessoes/{session_id}/enviar")
async def enviar_mensagem_humana(session_id: str, request: MensagemRequest):
    """Envia uma mensagem de texto do atendente para o cliente"""
    try:
        sessao_service = SessaoService()
        result = await sessao_service.enviar_mensagem_humana(
            session_id, 
            request.mensagem, 
            request.atendente_nome
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# ENVIAR MÍDIA (IMAGEM, DOCUMENTO, ÁUDIO, VÍDEO)
# ============================================
@router.post("/sessoes/{session_id}/enviar-midia")
async def enviar_midia_humana(session_id: str, request: MensagemMidiaRequest):
    """Envia uma mídia (imagem, documento, áudio, vídeo) do atendente para o cliente"""
    try:
        sessao_service = SessaoService()
        
        # Validar sessão
        sessao = await db.db.sessoes.find_one({"_id": ObjectId(session_id)})
        if not sessao:
            raise HTTPException(status_code=404, detail="Sessão não encontrada")
        
        contato = await db.db.contatos.find_one({"_id": ObjectId(sessao["contato_id"])})
        if not contato:
            raise HTTPException(status_code=404, detail="Contato não encontrado")
        
        # Validar tipo de mídia
        tipos_validos = ["imagem", "documento", "audio", "video"]
        if request.tipo_midia not in tipos_validos:
            raise HTTPException(status_code=400, detail=f"Tipo de mídia inválido. Use: {', '.join(tipos_validos)}")
        
        # Enviar mídia via Z-API
        whatsapp = WhatsAppAPI()
        telefone = contato["telefone"]
        
        sucesso = False
        if request.tipo_midia == "imagem":
            sucesso = await whatsapp.send_image(telefone, request.midia_url, request.legenda or "")
        elif request.tipo_midia == "documento":
            sucesso = await whatsapp.send_document(telefone, request.midia_url, request.nome_arquivo or "documento.pdf", request.legenda or "")
        elif request.tipo_midia == "audio":
            sucesso = await whatsapp.send_audio(telefone, request.midia_url)
        elif request.tipo_midia == "video":
            sucesso = await whatsapp.send_video(telefone, request.midia_url, request.legenda or "")
        
        if not sucesso:
            return {"success": False, "message": "Falha ao enviar mídia"}
        
        # Salvar mensagem no histórico
        mensagem_data = {
            "sessao_id": session_id,
            "contato_id": sessao["contato_id"],
            "direcao": "enviada",
            "sender": "human",
            "tipo": request.tipo_midia,
            "conteudo": request.legenda or f"Mídia enviada: {request.tipo_midia}",
            "data_hora": datetime.now(),
            "respondida": True,
            "atendente": request.atendente_nome,
            "file_url": request.midia_url,
            "file_name": request.nome_arquivo
        }
        await db.db.mensagens.insert_one(mensagem_data)
        
        # Atualizar sessão
        await sessao_service.registrar_resposta_atendente(session_id)
        
        return {"success": True, "message": "Mídia enviada com sucesso"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao enviar mídia: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# FINALIZAR SESSÃO
# ============================================
@router.post("/sessoes/{session_id}/finalizar")
async def finalizar_sessao(session_id: str):
    """Finaliza uma sessão manualmente"""
    try:
        sessao_service = SessaoService()
        await sessao_service.finalizar_sessao(session_id)
        return {"sucesso": True, "message": "Sessão finalizada com sucesso"}
    except Exception as e:
        logger.error(f"Erro ao finalizar sessão: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# CANCELAR ATENDIMENTO
# ============================================
@router.post("/sessoes/{session_id}/cancelar")
async def cancelar_atendimento(session_id: str):
    """Cancela o atendimento humano de uma sessão"""
    try:
        sessao_service = SessaoService()
        await sessao_service.atualizar_sessao(session_id, {
            "status": "ativa",
            "estado_atual": "menu_principal",
            "human_response_sent": False,
            "aguardando_atendente": True
        })
        return {"sucesso": True, "message": "Atendimento cancelado com sucesso"}
    except Exception as e:
        logger.error(f"Erro ao cancelar atendimento: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
