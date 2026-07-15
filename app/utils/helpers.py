# app/utils/helpers.py
from datetime import datetime, timezone
from app.core.config import TIMEZONE

def now_utc() -> datetime:
    """Retorna datetime atual em UTC (padrão para salvamento)"""
    return datetime.now(timezone.utc)

def now_brasilia() -> datetime:
    """Retorna datetime atual no fuso de Brasília (para exibição)"""
    return datetime.now(TIMEZONE)

def to_brasilia(dt: datetime) -> datetime:
    """Converte um datetime para o fuso de Brasília"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TIMEZONE)

def format_iso_brasilia(dt: datetime) -> str:
    """Formata datetime para ISO string no fuso de Brasília"""
    if dt is None:
        return None
    br_dt = to_brasilia(dt)
    return br_dt.isoformat()
