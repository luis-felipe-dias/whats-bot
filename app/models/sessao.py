from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field

StatusSessao = Literal["ativa", "finalizada", "cancelada", "humano", "fila_humana"]
TipoSessao = Literal["promocoes", "impressoes", "atendimento", "informacoes", "trabalhe_conosco"]

class Sessao(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    contato_id: str
    tipo: Optional[TipoSessao] = None
    status: StatusSessao = "ativa"
    estado_atual: str = "menu_principal"
    dados_contexto: dict = {}
    data_inicio: datetime = Field(default_factory=datetime.now)
    data_fim: Optional[datetime] = None
    ultima_interacao: datetime = Field(default_factory=datetime.now)
    atendente_id: Optional[str] = None
    arquivo_pendente: bool = False
    
    class Config:
        populate_by_name = True