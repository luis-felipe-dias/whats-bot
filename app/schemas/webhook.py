# app/schemas/webhook.py
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class WebhookMessage(BaseModel):
    """Modelo para mensagem recebida do webhook"""
    from_: Optional[str] = None  # Número do remetente
    to: Optional[str] = None  # Número do destinatário
    text: Optional[str] = None  # Texto da mensagem
    message_id: Optional[str] = None  # ID da mensagem
    type: Optional[str] = "text"  # Tipo: text, image, audio, video, document
    is_group: Optional[bool] = False  # Se é mensagem de grupo
    group_id: Optional[str] = None  # ID do grupo se for grupo
    timestamp: Optional[int] = None  # Timestamp da mensagem
    media_url: Optional[str] = None  # URL da mídia se houver
    caption: Optional[str] = None  # Legenda da mídia
    
    class Config:
        populate_by_name = True
        extra = "allow"  # Permite campos extras

class WebhookResponse(BaseModel):
    """Modelo para resposta do webhook"""
    status: str = "received"
    reason: Optional[str] = None
    message: Optional[str] = None
    
    class Config:
        populate_by_name = True

class WhatsAppMedia(BaseModel):
    """Modelo para mídia do WhatsApp"""
    url: str
    mimetype: str
    filename: Optional[str] = None
    size: Optional[int] = None

class WhatsAppContact(BaseModel):
    """Modelo para contato do WhatsApp"""
    name: str
    phone: str
    profile_pic_url: Optional[str] = None