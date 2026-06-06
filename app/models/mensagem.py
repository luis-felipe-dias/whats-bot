from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field

DirecaoMensagem = Literal["recebida", "enviada"]
TipoMensagem = Literal["texto", "botao", "arquivo"]

class Mensagem(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    sessao_id: str
    contato_id: str
    direcao: DirecaoMensagem
    tipo: TipoMensagem = "texto"
    conteudo: str
    conteudo_original: Optional[str] = None
    data_hora: datetime = Field(default_factory=datetime.now)
    botao_clicado: Optional[str] = None
    arquivo_url: Optional[str] = None
    metadata: dict = {}
    
    class Config:
        populate_by_name = True