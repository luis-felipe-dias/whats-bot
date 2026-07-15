# app/api/estatisticas.py - Endpoints para estatísticas
from fastapi import APIRouter, HTTPException
from app.core.database import db
from datetime import datetime, timedelta
from app.utils.helpers import now_utc
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/estatisticas")
async def get_estatisticas():
    """Obtém estatísticas gerais do sistema"""
    try:
        # Total de contatos
        total_contatos = await db.db.contatos.count_documents({})
        
        # Sessões ativas
        sessoes_ativas = await db.db.sessoes.count_documents({
            "status": {"$in": ["ativa", "humano", "aguardando_atendente"]}
        })
        
        # Sessões em atendimento humano
        humano_ativas = await db.db.sessoes.count_documents({
            "status": {"$in": ["humano", "aguardando_atendente"]}
        })
        
        # Mensagens hoje
        hoje = now_utc().replace(hour=0, minute=0, second=0, microsecond=0)
        mensagens_hoje = await db.db.mensagens.count_documents({
            "data_hora": {"$gte": hoje}
        })
        
        # Mensagens recebidas hoje
        recebidas_hoje = await db.db.mensagens.count_documents({
            "data_hora": {"$gte": hoje},
            "direcao": "recebida"
        })
        
        # Mensagens enviadas hoje
        enviadas_hoje = await db.db.mensagens.count_documents({
            "data_hora": {"$gte": hoje},
            "direcao": "enviada"
        })
        
        # Fila humana pendente
        fila_pendente = await db.db.fila_humana.count_documents({"status": "pendente"})
        
        # Avaliações (se existir coleção)
        avaliacoes = await db.db.avaliacoes.count_documents({}) if hasattr(db.db, 'avaliacoes') else 0
        
        return {
            "sucesso": True,
            "estatisticas": {
                "total_contatos": total_contatos,
                "sessoes_ativas": sessoes_ativas,
                "atendimento_humano_ativas": humano_ativas,
                "fila_humana_pendente": fila_pendente,
                "mensagens_hoje": mensagens_hoje,
                "mensagens_recebidas_hoje": recebidas_hoje,
                "mensagens_enviadas_hoje": enviadas_hoje,
                "total_avaliacoes": avaliacoes
            }
        }
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/estatisticas/contatos")
async def estatisticas_contatos():
    """Estatísticas detalhadas de contatos"""
    try:
        total = await db.db.contatos.count_documents({})
        personalizados = await db.db.contatos.count_documents({"nome_personalizado": True})
        
        # Contatos com interação nos últimos 7 dias
        semana = now_utc() - timedelta(days=7)
        ativos = await db.db.contatos.count_documents({
            "ultima_interacao": {"$gte": semana}
        })
        
        return {
            "sucesso": True,
            "estatisticas": {
                "total_contatos": total,
                "nomes_personalizados": personalizados,
                "contatos_ativos_7dias": ativos
            }
        }
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas de contatos: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
