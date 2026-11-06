# app/api/webhook_meta.py
"""
Webhook da API Oficial da Meta (Cloud API).

ESTRATÉGIA: traduzir, não reescrever.

O formato da Meta é completamente diferente do da Z-API. Em vez de duplicar
o bot inteiro, este módulo converte o payload da Meta para o MESMO formato
que o `webhook.py` já entende e entrega para a MESMA função de
processamento. A máquina de estados, os serviços e o painel não mudam uma
linha.

Resultado prático: o 8882 continua na Z-API e o 0424 entra pela Meta ao
mesmo tempo, sem um atrapalhar o outro.
"""

import hashlib
import hmac
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from app.api.webhook import process_webhook_message_with_semaphore
from app.core.config import settings
from app.core.database import db
from app.core.meta_cloud_api import meta_api
from app.utils.helpers import now_utc

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------- #
# 1. Verificação do webhook (GET)
# ---------------------------------------------------------------------- #

@router.get("/webhook-meta")
async def verificar_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """
    A Meta chama este GET uma vez, ao salvar a URL no painel. Tem que
    devolver o challenge em TEXTO PURO — JSON aqui faz a validação falhar
    com "não foi possível validar a URL de retorno".
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.meta_verify_token:
        logger.info("✅ Webhook da Meta verificado.")
        return PlainTextResponse(content=hub_challenge or "", status_code=200)

    logger.warning("❌ Verificação recusada (token não confere).")
    return PlainTextResponse(content="forbidden", status_code=403)


# ---------------------------------------------------------------------- #
# 2. Assinatura
# ---------------------------------------------------------------------- #

def _assinatura_valida(corpo: bytes, cabecalho: Optional[str]) -> bool:
    """
    A Meta assina todo POST com HMAC-SHA256 do app secret.

    Sem isso, qualquer um que descubra a URL injeta mensagem no bot — e o
    backend hoje não tem autenticação nenhuma. `compare_digest` é
    obrigatório: comparar com `==` vaza o segredo por tempo de resposta.
    """
    if not settings.meta_app_secret:
        # Sem segredo configurado, não dá para validar. Avisa alto, porque
        # rodar assim em produção é porta aberta.
        logger.warning("⚠️ META_APP_SECRET não definido — webhook SEM validação de assinatura.")
        return True

    if not cabecalho or not cabecalho.startswith("sha256="):
        return False

    esperado = hmac.new(
        settings.meta_app_secret.encode(), corpo, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(esperado, cabecalho.split("=", 1)[1])


# ---------------------------------------------------------------------- #
# 3. Recebimento (POST)
# ---------------------------------------------------------------------- #

@router.post("/webhook-meta")
async def receber_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Responde 200 SEMPRE e o mais rápido possível. A Meta reenvia o que não
    recebe 200 e, depois de falhas seguidas, desativa a assinatura do
    webhook — então processar antes de responder é o caminho para ficar
    sem webhook nenhum num pico.
    """
    corpo = await request.body()

    if not _assinatura_valida(corpo, request.headers.get("X-Hub-Signature-256")):
        logger.warning("🚫 POST com assinatura inválida.")
        return Response(status_code=403)

    try:
        dados = await request.json()
    except Exception:
        return JSONResponse(status_code=200, content={"status": "ignored"})

    try:
        for entrada in dados.get("entry", []):
            for mudanca in entrada.get("changes", []):
                valor = mudanca.get("value", {})
                campo = mudanca.get("field")

                if campo == "messages":
                    await _tratar_mensagens(valor, background_tasks)
                else:
                    # account_update, template_status_update, etc.
                    logger.info("ℹ️ Webhook '%s' recebido.", campo)
    except Exception as e:
        logger.error("❌ Erro ao processar webhook da Meta: %s", e)

    return JSONResponse(status_code=200, content={"status": "received"})


async def _tratar_mensagens(valor: Dict[str, Any], background_tasks: BackgroundTasks):
    # Recibos de entrega/leitura vêm no mesmo campo. Não são mensagem.
    if valor.get("statuses"):
        return

    mensagens = valor.get("messages") or []
    if not mensagens:
        return

    contatos = {c.get("wa_id"): c for c in valor.get("contacts", [])}

    for msg in mensagens:
        telefone = "".join(filter(str.isdigit, msg.get("from", "")))
        if not telefone:
            continue

        perfil = contatos.get(msg.get("from"), {}).get("profile", {})
        nome = perfil.get("name")
        message_id = msg.get("id")

        # Duplicata: a Meta reenvia quando acha que não entregou.
        if message_id and await db.db.mensagens.find_one({"message_id": message_id}):
            continue

        texto, tipo, url, arquivo, mime, legenda = _traduzir(msg)

        if not texto and not url:
            continue

        # Visto azul antes de processar: o cliente vê que chegou.
        if message_id:
            background_tasks.add_task(meta_api.marcar_como_lida, message_id)

        background_tasks.add_task(
            process_webhook_message_with_semaphore,
            None,          # chat_lid — não existe na Cloud API
            telefone,
            telefone,      # identificador = telefone
            texto,
            message_id,
            tipo,
            False,         # from_me: a Cloud API não ecoa o que a loja envia
            "cliente",
            False,         # is_group: a Cloud API não atende grupo
            nome,
            url,
            arquivo,
            mime,
            legenda,
            # POR NOME, não por posição. Entre `caption` e `canal` existem
            # remetente_nome, remetente_telefone, is_status_reply e
            # reference_message_id — passar "meta" na fila posicional fazia
            # o canal virar is_status_reply e a resposta sair pela Z-API,
            # num canal que não alcança o cliente.
            canal="meta",
        )


def _traduzir(msg: Dict[str, Any]):
    """
    Converte uma mensagem da Meta para a tupla que o bot já consome.

    Mídia: a Meta manda `id`, não URL. O que vai para o bot é a URL do
    NOSSO backend (`/bot/yup/midia-meta/{id}`), porque a URL da Meta expira
    em minutos e exige o token — o navegador do atendente não conseguiria
    abrir sozinho.
    """
    tipo_meta = msg.get("type")
    carimbo = now_utc().strftime("%Y%m%d_%H%M%S")

    def midia(bloco: Dict[str, Any], extensao: str, rotulo: str, tipo_bot: str):
        media_id = bloco.get("id")
        url = f"{settings.backend_public_url}/bot/yup/midia-meta/{media_id}" if media_id else None
        legenda = bloco.get("caption", "")
        nome = bloco.get("filename") or f"{tipo_bot}_{carimbo}.{extensao}"
        return (legenda or rotulo, tipo_bot, url, nome, bloco.get("mime_type"), legenda)

    if tipo_meta == "text":
        return (msg.get("text", {}).get("body"), "texto", None, None, None, None)

    if tipo_meta == "image":
        return midia(msg.get("image", {}), "jpg", "📷 Imagem recebida", "imagem")

    if tipo_meta == "document":
        bloco = msg.get("document", {})
        texto, _, url, nome, mime, legenda = midia(bloco, "pdf", "", "documento")
        return (legenda or f"📎 Documento: {nome}", "documento", url, nome, mime, legenda)

    if tipo_meta == "audio":
        return midia(msg.get("audio", {}), "ogg", "🎤 Áudio recebido", "audio")

    if tipo_meta == "video":
        return midia(msg.get("video", {}), "mp4", "📹 Vídeo recebido", "video")

    if tipo_meta == "sticker":
        # O bot antigo não tratava sticker e a mensagem sumia em silêncio.
        return midia(msg.get("sticker", {}), "webp", "😀 Figurinha recebida", "imagem")

    if tipo_meta == "location":
        loc = msg.get("location", {})
        lat, lng = loc.get("latitude"), loc.get("longitude")
        return (
            f"📍 Localização: {lat}, {lng}",
            "localizacao",
            f"https://maps.google.com/?q={lat},{lng}",
            None, None, None,
        )

    if tipo_meta == "contacts":
        pessoas = msg.get("contacts", [])
        if pessoas:
            p = pessoas[0]
            nome = p.get("name", {}).get("formatted_name", "")
            fones = p.get("phones", [])
            numero = fones[0].get("phone") if fones else ""
            return (f"📇 Contato: {nome} - {numero}", "contato", None, None, None, None)

    if tipo_meta == "interactive":
        inter = msg.get("interactive", {})
        resposta = inter.get("button_reply") or inter.get("list_reply") or {}
        # O TÍTULO é o que a máquina de estados compara, igual à Z-API.
        return (resposta.get("title"), "botao", None, None, None, None)

    if tipo_meta == "button":
        # Resposta a botão de template.
        return (msg.get("button", {}).get("text"), "botao", None, None, None, None)

    if tipo_meta == "reaction":
        emoji = msg.get("reaction", {}).get("emoji", "")
        return (f"Reagiu com {emoji}", "reacao", None, None, None, None)

    logger.info("ℹ️ Tipo de mensagem não tratado: %s", tipo_meta)
    return (None, "texto", None, None, None, None)


# ---------------------------------------------------------------------- #
# 4. Proxy de mídia
# ---------------------------------------------------------------------- #

@router.get("/midia-meta/{media_id}")
async def servir_midia(media_id: str):
    """
    Entrega a mídia da Meta para o painel.

    Existe porque a URL da Meta expira em minutos e exige o token no
    header — guardar essa URL no banco daria link quebrado no dia seguinte.
    Aqui o token nunca sai do servidor.
    """
    url = await meta_api.obter_url_midia(media_id)
    if not url:
        return JSONResponse(status_code=404, content={"erro": "mídia não encontrada ou expirada"})

    conteudo = await meta_api.baixar_midia(url)
    if not conteudo:
        return JSONResponse(status_code=502, content={"erro": "falha ao baixar a mídia"})

    return Response(
        content=conteudo,
        media_type="application/octet-stream",
        headers={"Cache-Control": "private, max-age=3600"},
    )
