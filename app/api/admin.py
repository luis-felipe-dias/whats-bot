# app/api/admin.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/dashboard")
async def admin_dashboard():
    return {"message": "Painel administrativo - em desenvolvimento"}