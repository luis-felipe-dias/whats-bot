# app/api/sessoes.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/sessoes")
async def listar_sessoes():
    return {"message": "Lista de sessões - em desenvolvimento"}

@router.get("/sessoes/{id}")
async def buscar_sessao(id: str):
    return {"message": f"Detalhes da sessão {id} - em desenvolvimento"}

@router.get("/sessoes/{id}/mensagens")
async def listar_mensagens(id: str):
    return {"message": f"Mensagens da sessão {id} - em desenvolvimento"}

@router.post("/sessoes/{id}/enviar")
async def enviar_mensagem(id: str):
    return {"message": f"Enviar mensagem para sessão {id} - em desenvolvimento"}

@router.post("/sessoes/{id}/finalizar")
async def finalizar_sessao(id: str):
    return {"message": f"Finalizar sessão {id} - em desenvolvimento"}

@router.post("/sessoes/{id}/cancelar")
async def cancelar_atendimento(id: str):
    return {"message": f"Cancelar atendimento da sessão {id} - em desenvolvimento"}