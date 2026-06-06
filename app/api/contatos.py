# app/api/contatos.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/contatos")
async def listar_contatos():
    return {"message": "Lista de contatos - em desenvolvimento"}