# app/models/mensagem.py
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field

DirecaoMensagem = Literal["recebida", "enviada"]
TipoMensagem = Literal["texto", "botao", "arquivo", "imagem", "documento", "audio", "video", "localizacao", "contato"]

class Mensagem(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    sessao_id: str
    contato_id: str
    direcao: DirecaoMensagem
    sender: Optional[str] = None  # client, pepper, human
    tipo: TipoMensagem = "texto"
    conteudo: str
    conteudo_original: Optional[str] = None
    data_hora: datetime = Field(default_factory=datetime.now)
    botao_clicado: Optional[str] = None
    arquivo_url: Optional[str] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    caption: Optional[str] = None
    metadata: dict = {}
    # NOVOS CAMPOS
    message_id_zapi: Optional[str] = None  # ID da mensagem na Z-API
    reference_message_id: Optional[str] = None  # ID da mensagem que está sendo respondida
    is_reply: bool = False
    is_status_reply: bool = False
    from_me: bool = False
    chat_id: Optional[str] = None
    status: Optional[str] = None  # RECEIVED, SENT, DELIVERED, READ
    respondida: bool = False
    atendente: Optional[str] = None
    
    class Config:
        populate_by_name = True
