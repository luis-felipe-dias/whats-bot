# app/schemas/responses.py
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime

class ContatoResponse(BaseModel):
    """Response para contato"""
    id: str
    nome: str
    telefone: str
    foto_url: Optional[str] = None
    data_criacao: datetime
    ultima_interacao: Optional[datetime] = None
    tags: List[str] = []

class SessaoResponse(BaseModel):
    """Response para sessão"""
    id: str
    contato_id: str
    tipo: Optional[str] = None
    status: str
    estado_atual: str
    data_inicio: datetime
    ultima_interacao: datetime

class MensagemResponse(BaseModel):
    """Response para mensagem"""
    id: str
    sessao_id: str
    direcao: str
    conteudo: str
    data_hora: datetime

class FilaHumanaResponse(BaseModel):
    """Response para fila humana"""
    id: str
    sessao_id: str
    contato_id: str
    tipo: str
    status: str
    prioridade: int
    data_criacao: datetime
    data_inicio_atendimento: Optional[datetime] = None

class EstatisticasResponse(BaseModel):
    """Response para estatísticas"""
    total_contatos: int
    sessoes_ativas: int
    fila_humana_pendente: int
    mensagens_enviadas_hoje: int
    avaliacao_media: float
    tempo_medio_resposta: float  # segundos

class ApiResponse(BaseModel):
    """Response padrão da API"""
    success: bool
    message: str
    data: Optional[Any] = None
    error: Optional[str] = None