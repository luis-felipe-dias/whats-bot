from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field

StatusFila = Literal["pendente", "em_atendimento", "finalizado", "cancelado"]

class FilaHumana(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    sessao_id: str
    contato_id: str
    tipo: str  # impressao, troca, reclamacao, curriculo, atendimento
    status: StatusFila = "pendente"
    dados: dict = {}
    prioridade: int = 0
    data_criacao: datetime = Field(default_factory=datetime.now)
    data_inicio_atendimento: Optional[datetime] = None
    data_fim: Optional[datetime] = None
    atendente_id: Optional[str] = None
    
    class Config:
        populate_by_name = True