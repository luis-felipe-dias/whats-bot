from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class Contato(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    nome: str
    telefone: str
    foto_url: Optional[str] = None
    nome_personalizado: bool = False
    data_criacao: datetime = Field(default_factory=datetime.now)
    data_atualizacao: datetime = Field(default_factory=datetime.now)
    ultima_interacao: Optional[datetime] = None
    tags: list[str] = []
    observacoes: Optional[str] = None
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True