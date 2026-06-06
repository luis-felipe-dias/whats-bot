# app/api/estatisticas.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/estatisticas")
async def get_estatisticas():
    return {"message": "Estatísticas - em desenvolvimento"}