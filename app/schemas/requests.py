# app/schemas/requests.py
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class EnviarMensagemRequest(BaseModel):
    """Request para enviar mensagem"""
    telefone: str
    mensagem: str
    sessao_id: Optional[str] = None

class FinalizarSessaoRequest(BaseModel):
    """Request para finalizar sessão"""
    sessao_id: str
    motivo: Optional[str] = None

class CancelarAtendimentoRequest(BaseModel):
    """Request para cancelar atendimento humano"""
    sessao_id: str
    motivo: Optional[str] = None

class AvaliarAtendimentoRequest(BaseModel):
    """Request para avaliar atendimento"""
    sessao_id: str
    nota: int  # 1 a 5
    comentario: Optional[str] = None