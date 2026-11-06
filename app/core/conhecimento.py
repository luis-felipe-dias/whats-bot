# app/core/conhecimento.py
"""
A base de conhecimento da Peper e a esteira de curadoria que a alimenta.

O PRINCÍPIO

"Aprender", neste projeto, não é treinar modelo. É guardar pares
pergunta→resposta que um humano aprovou e, na hora de responder, trazer de
volta os poucos mais parecidos. Barato, auditável e reversível: desativar
uma resposta ruim é uma linha, não um retreino.

A REGRA QUE NÃO SE QUEBRA — PREÇO NÃO VIRA CONHECIMENTO

O Olist Tiny é a fonte de preço. Um par aprovado dizendo "a impressão custa
R$ 0,50" parece inofensivo no dia em que é salvo e vira mentira dois meses
depois — dita com confiança e com o aval de quem aprovou. É pior que não
ter base, porque ninguém desconfia de resposta aprovada.

Por isso candidato com preço é BLOQUEADO aqui, no código. Não é orientação
para quem cura: é trava.

O CICLO

    conversa resolvida pela IA
        -> candidato em `curadoria` (status: pendente)
            -> humano aprova / corrige / descarta
                -> aprovado vira `conhecimento` com embedding
                    -> 90 dias depois volta para a fila para revalidar
"""

import logging
import math
import re
from datetime import timedelta
from typing import Any, Dict, List, Optional

from bson import ObjectId

from app.core.database import db
from app.core.openai_client import openai_client
from app.utils.helpers import now_utc, now_utc_naive

logger = logging.getLogger(__name__)

# Abaixo disso a "semelhança" é coincidência de palavra comum e só atrapalha.
LIMIAR = 0.78
MAX_EXEMPLOS = 3
VALIDADE_DIAS = 90

# Cache em memória: a base é pequena (centenas de itens) e comparar vetor em
# Python é instantâneo. Evita depender de índice vetorial do Atlas, que não
# existe em todo plano.
_cache: Optional[List[Dict[str, Any]]] = None


# ---------------------------------------------------------------------- #
# A trava de preço
# ---------------------------------------------------------------------- #

_PADROES_PRECO = [
    re.compile(r"r\$\s*\d", re.I),
    re.compile(r"\b\d+[.,]\d{2}\b"),
    re.compile(r"\b\d+\s*(reais|real|conto)\b", re.I),
    re.compile(r"\b(custa|preço|preco|valor)\b.{0,20}\b\d", re.I),
]


def contem_preco(texto: str) -> bool:
    """
    True quando o texto afirma um valor. Deliberadamente sensível: um falso
    positivo custa um par descartado; um falso negativo custa um preço
    errado circulando por meses.
    """
    t = texto or ""
    return any(p.search(t) for p in _PADROES_PRECO)


# ---------------------------------------------------------------------- #
# Similaridade
# ---------------------------------------------------------------------- #

def _cosseno(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    produto = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return produto / (na * nb) if na and nb else 0.0


async def recarregar() -> int:
    """Relê a base para a memória. Chamar após aprovar ou desativar um item."""
    global _cache
    try:
        itens = await db.db.conhecimento.find(
            {"ativo": True}, {"pergunta": 1, "resposta": 1, "embedding": 1}
        ).to_list(length=5000)
        _cache = [i for i in itens if i.get("embedding")]
        logger.info("Base de conhecimento carregada: %d itens.", len(_cache))
        return len(_cache)
    except Exception as e:  # noqa: BLE001
        logger.warning("Falha ao carregar a base de conhecimento: %s", e)
        _cache = []
        return 0


async def buscar_similares(pergunta: str, limite: int = MAX_EXEMPLOS) -> List[Dict[str, str]]:
    """Os poucos exemplos aprovados mais próximos da pergunta de agora."""
    if _cache is None:
        await recarregar()
    if not _cache:
        return []

    vetor = await openai_client.embedding(pergunta)
    if not vetor:
        return []

    pontuados = [(_cosseno(vetor, i["embedding"]), i) for i in _cache]
    pontuados.sort(key=lambda p: p[0], reverse=True)

    return [
        {"pergunta": i["pergunta"], "resposta": i["resposta"], "semelhanca": round(s, 3)}
        for s, i in pontuados[:limite] if s >= LIMIAR
    ]


def para_prompt(exemplos: List[Dict[str, str]]) -> str:
    """Trecho injetado no prompt. Vazio quando não há nada relevante."""
    if not exemplos:
        return ""
    linhas = "\n\n".join(
        f'Cliente: "{e["pergunta"]}"\nResposta aprovada: "{e["resposta"]}"'
        for e in exemplos
    )
    return (
        "COMO A EQUIPE JÁ RESPONDEU PERGUNTAS PARECIDAS\n"
        "Use como referência de conteúdo e de tom. Não copie palavra por "
        "palavra se a pergunta de agora for diferente, e NUNCA tire preço "
        "daqui — preço só de `confirmar_preco_estoque`.\n\n"
        f"{linhas}"
    )


# ---------------------------------------------------------------------- #
# Esteira de curadoria
# ---------------------------------------------------------------------- #

async def registrar_candidato(
    sessao_id: str,
    pergunta: str,
    resposta: str,
    origem: str = "ia",
    atendente: Optional[str] = None,
) -> None:
    """
    Enfileira um par para revisão humana. Nunca derruba o atendimento: é
    sempre melhor perder um candidato que falhar a resposta ao cliente.

    Guarda só o texto — sem telefone, sem nome. O que vai para a base é a
    pergunta e a resposta, não quem perguntou.
    """
    pergunta = (pergunta or "").strip()
    resposta = (resposta or "").strip()
    if len(pergunta) < 8 or len(resposta) < 8:
        return

    try:
        # Bloqueio de preço: entra na fila marcado, para quem cura entender
        # por que não pode aprovar, em vez de sumir sem explicação.
        tem_preco = contem_preco(pergunta) or contem_preco(resposta)

        await db.db.curadoria.insert_one({
            "sessao_id": sessao_id,
            "pergunta": pergunta,
            "resposta_dada": resposta,
            "origem": origem,
            "atendente": atendente,
            "status": "bloqueado_preco" if tem_preco else "pendente",
            "motivo_bloqueio": (
                "Contém valor. Preço vem do Olist a cada consulta e não pode "
                "ser congelado na base." if tem_preco else None
            ),
            "criado_em": now_utc(),
        })
    except Exception as e:  # noqa: BLE001
        logger.warning("Não consegui enfileirar candidato de curadoria: %s", e)


async def aprovar(candidato_id: str, aprovado_por: str,
                  resposta_final: Optional[str] = None) -> Dict[str, Any]:
    """
    Promove um candidato a conhecimento. `resposta_final` permite corrigir
    antes de aprovar — que é o caso mais comum e o mais valioso.
    """
    candidato = await db.db.curadoria.find_one({"_id": ObjectId(candidato_id)})
    if not candidato:
        return {"ok": False, "erro": "candidato_nao_encontrado"}

    pergunta = candidato["pergunta"]
    resposta = (resposta_final or candidato["resposta_dada"]).strip()

    # A trava vale também na correção: o humano pode, sem querer, digitar um
    # valor na resposta que está consertando.
    if contem_preco(resposta) or contem_preco(pergunta):
        return {
            "ok": False,
            "erro": "contem_preco",
            "mensagem": "Essa resposta tem valor. Preço vem do Olist e não "
                        "pode virar conhecimento fixo.",
        }

    vetor = await openai_client.embedding(pergunta)
    if not vetor:
        return {"ok": False, "erro": "falha_embedding"}

    await db.db.conhecimento.insert_one({
        "pergunta": pergunta,
        "resposta": resposta,
        "embedding": vetor,
        "aprovado_por": aprovado_por,
        "aprovado_em": now_utc(),
        "revalidar_em": now_utc_naive() + timedelta(days=VALIDADE_DIAS),
        "usos": 0,
        "ativo": True,
        "corrigido": bool(resposta_final and resposta_final != candidato["resposta_dada"]),
    })

    await db.db.curadoria.update_one(
        {"_id": ObjectId(candidato_id)},
        {"$set": {"status": "aprovada", "aprovado_por": aprovado_por,
                  "resposta_final": resposta, "decidido_em": now_utc()}},
    )

    await recarregar()
    return {"ok": True}


async def descartar(candidato_id: str, por: str, motivo: str = "") -> Dict[str, Any]:
    await db.db.curadoria.update_one(
        {"_id": ObjectId(candidato_id)},
        {"$set": {"status": "descartada", "decidido_por": por,
                  "motivo": motivo, "decidido_em": now_utc()}},
    )
    return {"ok": True}


async def desativar(conhecimento_id: str, por: str) -> Dict[str, Any]:
    """Tira uma resposta de circulação na hora. O desfazer do sistema."""
    await db.db.conhecimento.update_one(
        {"_id": ObjectId(conhecimento_id)},
        {"$set": {"ativo": False, "desativado_por": por, "desativado_em": now_utc()}},
    )
    await recarregar()
    return {"ok": True}


async def vencidos() -> int:
    """
    Devolve à fila o que passou da validade.

    Sem isso a base envelhece em silêncio: a loja muda o processo, a resposta
    aprovada continua valendo, e ninguém percebe porque "já foi revisada".
    """
    try:
        resultado = await db.db.conhecimento.update_many(
            {"ativo": True, "revalidar_em": {"$lt": now_utc_naive()}},
            {"$set": {"ativo": False, "motivo_inativo": "venceu_validade"}},
        )
        if resultado.modified_count:
            logger.info("%d item(ns) de conhecimento venceram e saíram de uso.",
                        resultado.modified_count)
            await recarregar()
        return resultado.modified_count
    except Exception as e:  # noqa: BLE001
        logger.warning("Falha ao revalidar conhecimento: %s", e)
        return 0
