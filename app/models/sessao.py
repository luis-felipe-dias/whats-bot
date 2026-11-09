# app/models/sessao.py
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field

StatusSessao = Literal["ativa", "finalizada", "cancelada", "humano", "fila_humana", "aguardando_atendente"]
TipoSessao = Literal["promocoes", "servicos", "atendimento", "informacoes", "trabalhe_conosco"]
SetorResponsavel = Literal["atendimento", "financeiro", "tecnico", "comercial", "rh", "ouvidoria", "qualidade"]

class Sessao(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    contato_id: str
    cliente_nome: Optional[str] = None  # Nome do cliente vindo do chatName
    tipo: Optional[TipoSessao] = None
    status: StatusSessao = "ativa"
    estado_atual: str = "menu_principal"
    dados_contexto: dict = {}
    data_inicio: datetime = Field(default_factory=datetime.now)
    data_fim: Optional[datetime] = None
    ultima_interacao: datetime = Field(default_factory=datetime.now)
    atendente_id: Optional[str] = None
    arquivo_pendente: bool = False
    human_response_sent: bool = False
    last_menu: Optional[str] = None
    menu_anterior: Optional[str] = None
    setor_responsavel: Optional[SetorResponsavel] = None
    aguardando_atendente: bool = True
    
    class Config:
        populate_by_name = True
