# app/api/fila.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/fila")
async def ver_fila_envio():
    return {"message": "Fila de envio - em desenvolvimento"}

@router.get("/fila-humana")
async def ver_fila_humana():
    return {"message": "Fila humana - em desenvolvimento"}