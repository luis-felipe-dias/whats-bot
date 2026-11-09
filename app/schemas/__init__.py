# app/schemas/__init__.py
from .webhook import WebhookMessage, WebhookResponse
from .requests import EnviarMensagemRequest, FinalizarSessaoRequest, CancelarAtendimentoRequest, AvaliarAtendimentoRequest
from .responses import ContatoResponse, SessaoResponse, MensagemResponse, FilaHumanaResponse, EstatisticasResponse, ApiResponse

__all__ = [
    "WebhookMessage",
    "WebhookResponse", 
    "EnviarMensagemRequest",
    "FinalizarSessaoRequest",
    "CancelarAtendimentoRequest",
    "AvaliarAtendimentoRequest",
    "ContatoResponse",
    "SessaoResponse",
    "MensagemResponse", 
    "FilaHumanaResponse",
    "EstatisticasResponse",
    "ApiResponse"
]