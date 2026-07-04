# app/utils/helpers.py
from datetime import datetime
from app.core.config import TIMEZONE

def now() -> datetime:
    """Retorna a data/hora atual no fuso horário do Brasil"""
    return datetime.now(TIMEZONE)

def format_datetime(dt: datetime) -> str:
    """Formata uma data/hora para string no formato brasileiro"""
    if dt.tzinfo is None:
        dt = TIMEZONE.localize(dt)
    return dt.strftime("%d/%m/%Y %H:%M:%S")

def to_brasilia(dt: datetime) -> datetime:
    """Converte uma data/hora para o fuso horário do Brasil"""
    if dt.tzinfo is None:
        dt = TIMEZONE.localize(dt)
    return dt.astimezone(TIMEZONE)
