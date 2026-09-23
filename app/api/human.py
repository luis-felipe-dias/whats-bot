# app/api/human.py - CORREÇÃO PARA USAR O HELPER DE DATAS
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.services.sessao_service import SessaoService
from app.services.mensagem_service import MensagemService
from app.services.contato_service import ContatoService
from app.core.database import db
from app.core.whatsapp_api import WhatsAppAPI
from app.utils.helpers import now_utc, now_utc_naive, format_iso_brasilia
from bson import ObjectId
from datetime import datetime, timedelta
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class MensagemRequest(BaseModel):
    mensagem: str
    atendente_nome: Optional[str] = "Atendente"

class MensagemMidiaRequest(BaseModel):
    tipo_midia: str
    midia_url: str
    legenda: Optional[str] = None
    nome_arquivo: Optional[str] = None
    atendente_nome: Optional[str] = "Atendente"

class IniciarConversaRequest(BaseModel):
    telefone: str
    mensagem: str
    atendente_nome: Optional[str] = "Atendente"

# ============================================
# LISTAR TODAS AS SESSÕES
# ============================================
@router.get("/sessoes")
async def listar_todas_sessoes():
    try:
        sessao_service = SessaoService()
        sessoes = await db.db.sessoes.find().sort("data_inicio", -1).to_list(length=100)
        resultado = []
        for sessao in sessoes:
            contato_id = sessao.get("contato_id")
            contato = None
            
            if not sessao.get("is_group") and contato_id:
                try:
                    contato = await db.db.contatos.find_one({"_id": ObjectId(contato_id)})
                except:
                    contato = None
            
            resultado.append({
                "sessao_id": str(sessao["_id"]),
                "cliente": sessao.get("cliente_nome") or (contato.get("nome") if contato else "Desconhecido"),
                "telefone": sessao.get("identificador") if sessao.get("is_group") else (contato.get("telefone") if contato else "Desconhecido"),
                "status": sessao.get("status"),
                "estado_atual": sessao.get("estado_atual"),
                "setor_responsavel": sessao.get("setor_responsavel"),
                "aguardando_atendente": sessao.get("aguardando_atendente", False),
                "data_inicio": format_iso_brasilia(sessao.get("data_inicio")),
                "ultima_interacao": format_iso_brasilia(sessao.get("ultima_interacao")),
                "is_group": sessao.get("is_group", False)
            })
        return {"sucesso": True, "sessoes": resultado}
    except Exception as e:
        logger.error(f"Erro ao listar sessões: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# ATENDENTE INICIA A CONVERSA (fala primeiro com o cliente)
# ============================================
@router.post("/sessoes/iniciar")
async def iniciar_conversa_atendente(request: IniciarConversaRequest):
    """
    Atendente manda a PRIMEIRA mensagem para um cliente (a Peper nunca
    falou com ele nessa sessão, ou o atendente quer puxar assunto antes).
    Sem isso, assim que o cliente respondesse o bot tomava conta da
    conversa como se fosse uma sessão normal. Aqui a sessão fica com o
    bot suspenso por 30min - mesma janela usada em outras regras do
    painel - e volta sozinha ao normal automático se ninguém mexer.
    """
    try:
        telefone = ''.join(filter(str.isdigit, request.telefone))
        if len(telefone) >= 10 and not telefone.startswith('55'):
            telefone = '55' + telefone
        if len(telefone) < 10:
            raise HTTPException(status_code=400, detail="Telefone inválido")

        if not request.mensagem or not request.mensagem.strip():
            raise HTTPException(status_code=400, detail="Mensagem não pode ser vazia")

        contato_service = ContatoService()
        sessao_service = SessaoService()

        contato = await contato_service.get_or_create_contato(telefone=telefone)
        sessao = await sessao_service.get_or_create_sessao(contato["id"], is_group=False, identificador=telefone)

        whatsapp = WhatsAppAPI()
        sucesso = await whatsapp.send_text(telefone, request.mensagem)
        if not sucesso:
            raise HTTPException(status_code=502, detail="Falha ao enviar mensagem pelo WhatsApp")

        bot_suspenso_ate = now_utc_naive() + timedelta(minutes=30)
        await sessao_service.atualizar_sessao(sessao["id"], {
            "bot_suspenso_ate": bot_suspenso_ate,
            "iniciada_por_atendente": True,
            "human_response_sent": True,
            "aguardando_atendente": False
        })

        mensagem_data = {
            "sessao_id": sessao["id"],
            "contato_id": contato["id"],
            "direcao": "enviada",
            "sender": "human",
            "tipo": "texto",
            "conteudo": request.mensagem,
            "data_hora": now_utc(),
            "respondida": True,
            "atendente": request.atendente_nome
        }
        await db.db.mensagens.insert_one(mensagem_data)

        return {
            "sucesso": True,
            "sessao_id": sessao["id"],
            "contato": {"id": contato["id"], "nome": contato.get("nome"), "telefone": telefone},
            "bot_suspenso_ate": bot_suspenso_ate.isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao iniciar conversa: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# LISTAR SESSÕES ABERTAS
# ============================================
@router.get("/sessoes/abertas")
async def get_sessoes_abertas():
    try:
        sessao_service = SessaoService()
        sessions = await sessao_service.listar_sessoes_abertas()
        return {"sucesso": True, "sessoes": sessions}
    except Exception as e:
        logger.error(f"Erro ao listar sessões abertas: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# BUSCAR UMA SESSÃO ESPECÍFICA
# ============================================
@router.get("/sessoes/{session_id}")
async def buscar_sessao(session_id: str):
    try:
        sessao_service = SessaoService()
        sessao = await sessao_service.get_sessao_por_id(session_id)
        if not sessao:
            raise HTTPException(status_code=404, detail="Sessão não encontrada")
        return {"sucesso": True, "sessao": sessao}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao buscar sessão: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# HISTÓRICO DE MENSAGENS DA SESSÃO
# ============================================
@router.get("/sessoes/{session_id}/mensagens")
async def get_sessao_mensagens(session_id: str):
    try:
        sessao_service = SessaoService()
        messages = await sessao_service.get_historico_sessao(session_id)
        return {"sucesso": True, "mensagens": messages}
    except Exception as e:
        logger.error(f"Erro ao buscar histórico: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# ENVIAR MENSAGEM DE TEXTO
# ============================================
@router.post("/sessoes/{session_id}/enviar")
async def enviar_mensagem_humana(session_id: str, request: MensagemRequest):
    try:
        sessao_service = SessaoService()
        result = await sessao_service.enviar_mensagem_humana(
            session_id,
            request.mensagem,
            request.atendente_nome
        )
        # Antes: sempre retornava 200 mesmo quando o WhatsApp recusou o envio
        # (result["success"] = False), e o painel tratava qualquer resposta
        # como sucesso. Resultado: atendente via a mensagem "enviada" no
        # histórico e o cliente nunca recebia nada, sem nenhum aviso.
        if not result.get("success", False):
            raise HTTPException(status_code=502, detail=result.get("error") or result.get("message") or "Falha ao enviar mensagem pelo WhatsApp")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# ENVIAR MÍDIA
# ============================================
@router.post("/sessoes/{session_id}/enviar-midia")
async def enviar_midia_humana(session_id: str, request: MensagemMidiaRequest):
    try:
        sessao_service = SessaoService()
        
        sessao = await db.db.sessoes.find_one({"_id": ObjectId(session_id)})
        if not sessao:
            raise HTTPException(status_code=404, detail="Sessão não encontrada")
        
        contato_telefone = None
        if sessao.get("is_group"):
            contato_telefone = sessao.get("identificador")
        else:
            contato = await db.db.contatos.find_one({"_id": ObjectId(sessao["contato_id"])})
            if not contato:
                raise HTTPException(status_code=404, detail="Contato não encontrado")
            contato_telefone = contato["telefone"]
        
        tipos_validos = ["imagem", "documento", "audio", "video"]
        if request.tipo_midia not in tipos_validos:
            raise HTTPException(status_code=400, detail=f"Tipo de mídia inválido. Use: {', '.join(tipos_validos)}")
        
        whatsapp = WhatsAppAPI()
        
        sucesso = False
        if request.tipo_midia == "imagem":
            sucesso = await whatsapp.send_image(contato_telefone, request.midia_url, request.legenda or "")
        elif request.tipo_midia == "documento":
            sucesso = await whatsapp.send_document(contato_telefone, request.midia_url, request.nome_arquivo or "documento.pdf", request.legenda or "")
        elif request.tipo_midia == "audio":
            sucesso = await whatsapp.send_audio(contato_telefone, request.midia_url)
        elif request.tipo_midia == "video":
            sucesso = await whatsapp.send_video(contato_telefone, request.midia_url, request.legenda or "")
        
        if not sucesso:
            # Mesmo motivo do /enviar: sem isso, o painel mostrava "encaminhada
            # com sucesso" mesmo quando a Z-API recusou (ex.: link da mídia
            # expirado, formato inválido) e o cliente nunca recebia o arquivo.
            raise HTTPException(status_code=502, detail="Falha ao enviar mídia (link pode ter expirado ou a Z-API recusou o envio)")
        
        mensagem_data = {
            "sessao_id": session_id,
            "contato_id": sessao["contato_id"],
            "direcao": "enviada",
            "sender": "human",
            "tipo": request.tipo_midia,
            "conteudo": request.legenda or f"Mídia enviada: {request.tipo_midia}",
            "data_hora": now_utc(),
            "respondida": True,
            "atendente": request.atendente_nome,
            "file_url": request.midia_url,
            "file_name": request.nome_arquivo
        }
        await db.db.mensagens.insert_one(mensagem_data)
        
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
    try:
        sessao_service = SessaoService()
        mensagem_service = MensagemService()
        
        sessao = await db.db.sessoes.find_one({"_id": ObjectId(session_id)})
        if not sessao:
            raise HTTPException(status_code=404, detail="Sessão não encontrada")
        
        menu_anterior = sessao.get("menu_anterior", "menu_principal")
        
        await sessao_service.cancelar_atendimento_humano(session_id, menu_anterior)
        
        mensagem_confirmacao = "✅ O atendente encerrou o atendimento humano. 💙\n\nVocê está de volta ao atendimento automático com a Peper.\n\nComo posso ajudar você hoje?"
        
        telefone_destino = None
        if sessao.get("is_group"):
            telefone_destino = sessao.get("identificador")
        else:
            contato = await db.db.contatos.find_one({"_id": ObjectId(sessao["contato_id"])})
            if contato:
                telefone_destino = contato["telefone"]
        
        if telefone_destino:
            await mensagem_service.enfileirar_resposta(
                contato_id=sessao["contato_id"],
                sessao_id=session_id,
                mensagem=mensagem_confirmacao,
                botoes=["🛍️ PROMOÇÕES", "🖨️ SERVIÇOS", "🤝 ATENDIMENTO", "📍 INFORMAÇÕES", "💼 TRABALHE CONOSCO"]
            )
        
        return {
            "sucesso": True,
            "message": "Atendimento cancelado com sucesso. Cliente retornou ao menu anterior.",
            "menu_anterior": menu_anterior
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao cancelar atendimento: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
