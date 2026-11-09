from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field

TipoEvento = Literal[
    "mensagem_recebida", "mensagem_enviada",
    "contato_criado", "contato_atualizado", "contato_salvo_whatsapp",
    "sessao_criada", "sessao_finalizada",
    "arquivo_recebido",
    "atendimento_humano", "atendimento_cancelado",
    "avaliacao_recebida",
    "erro_envio", "erro_webhook"
]

class Evento(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    tipo: TipoEvento
    contato_id: Optional[str] = None
    sessao_id: Optional[str] = None
    dados: dict = {}
    data_hora: datetime = Field(default_factory=datetime.now)
    
    class Config:
        populate_by_name = True