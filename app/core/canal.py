# app/core/canal.py
"""
Decide por qual canal uma mensagem de saída deve ir: Z-API ou API oficial
da Meta.

POR QUE ISSO EXISTE

O bot passou a atender por dois canais ao mesmo tempo — o 8882 na Z-API e
o número de teste na Meta — mas todo o caminho de SAÍDA continuou
instanciando `WhatsAppAPI()` direto, em cinco lugares diferentes.

O efeito prático foi o pior possível: a conversa entrava pela Meta, o
atendente respondia pelo painel, a mensagem ia para a Z-API, o cliente
nunca recebia — e o histórico do painel mostrava a mensagem como enviada.
Atendente falando sozinho sem saber.

A regra: o canal é gravado na sessão e no contato quando a mensagem
CHEGA, e toda saída pergunta aqui por onde responder. Nada de adivinhar
pelo número.
"""

import logging
from typing import Any, Dict, Optional

from bson import ObjectId

from app.core.config import settings
from app.core.database import db

logger = logging.getLogger(__name__)

CANAL_META = "meta"
CANAL_ZAPI = "zapi"


def _cliente(canal: str):
    if canal == CANAL_META and settings.meta_enabled:
        from app.core.meta_cloud_api import meta_api
        return meta_api
    from app.core.whatsapp_api import WhatsAppAPI
    return WhatsAppAPI()


def canal_de(sessao: Optional[Dict[str, Any]] = None,
             contato: Optional[Dict[str, Any]] = None) -> str:
    """Canal gravado na sessão; se não houver, o do contato; senão Z-API."""
    for origem in (sessao, contato):
        if origem:
            canal = origem.get("canal")
            if canal in (CANAL_META, CANAL_ZAPI):
                return canal
    return CANAL_ZAPI


def api_de(sessao: Optional[Dict[str, Any]] = None,
           contato: Optional[Dict[str, Any]] = None):
    """Cliente de envio a partir dos documentos que o chamador já tem em mão."""
    return _cliente(canal_de(sessao, contato))


async def api_por_telefone(telefone: str):
    """
    Quando só existe o telefone (caminho do painel). Uma consulta ao
    contato; na dúvida, Z-API — que é o canal de produção.
    """
    try:
        contato = await db.db.contatos.find_one(
            {"telefone": telefone}, {"canal": 1}
        )
        return _cliente(canal_de(contato=contato))
    except Exception as e:  # noqa: BLE001
        logger.warning("Não consegui descobrir o canal de %s: %s", telefone, e)
        return _cliente(CANAL_ZAPI)


async def api_por_sessao_id(sessao_id: str):
    """Idem, a partir do id da sessão."""
    try:
        consulta = {"_id": ObjectId(sessao_id)} if len(str(sessao_id)) == 24 else {"_id": sessao_id}
        sessao = await db.db.sessoes.find_one(consulta, {"canal": 1, "contato_id": 1})
        if sessao and sessao.get("canal"):
            return _cliente(sessao["canal"])
        if sessao and sessao.get("contato_id"):
            contato = await db.db.contatos.find_one(
                {"_id": ObjectId(sessao["contato_id"])}, {"canal": 1}
            )
            return _cliente(canal_de(contato=contato))
    except Exception as e:  # noqa: BLE001
        logger.warning("Não consegui descobrir o canal da sessão %s: %s", sessao_id, e)
    return _cliente(CANAL_ZAPI)


async def gravar_canal(contato_id: str, sessao_id: str, canal: str) -> None:
    """
    Marca contato e sessão com o canal de entrada. Chamado no recebimento,
    para que a saída não precise adivinhar depois.
    """
    if canal not in (CANAL_META, CANAL_ZAPI):
        return
    try:
        await db.db.contatos.update_one(
            {"_id": ObjectId(contato_id)}, {"$set": {"canal": canal}}
        )
        consulta = {"_id": ObjectId(sessao_id)} if len(str(sessao_id)) == 24 else {"_id": sessao_id}
        await db.db.sessoes.update_one(consulta, {"$set": {"canal": canal}})
    except Exception as e:  # noqa: BLE001
        logger.warning("Falha ao gravar canal '%s': %s", canal, e)
