# app/core/palavras_proibidas.py
"""
Palavras e assuntos que a Peper não usa — e o filtro que confere.

POR QUE EXISTE, ALÉM DO PROMPT
O prompt pede. O filtro garante. Modelo de linguagem erra, e o custo de
errar aqui não é parecer bobo: é prometer desconto que não existe, citar
concorrente, falar de margem, ou responder com um termo que a marca não
usa. A instrução no prompt resolve 95% dos casos; os outros 5% chegam ao
cliente. Este arquivo é a rede embaixo.

DUAS CAMADAS, DE PROPÓSITO
1. `para_prompt()` injeta a lista no prompt — evita o erro antes dele
   acontecer, que é mais barato que corrigir depois.
2. `verificar()` roda na resposta pronta, antes de enviar. O que passar
   pela primeira camada morre na segunda.

A LISTA É DO PABLO, NÃO MINHA
Começa com o que os manuais da Yup já proíbem (sigilo, preço enganoso,
sarcasmo) e com termos que nenhuma loja deveria mandar por WhatsApp. O
resto se preenche pelo painel, sem mexer em código — por isso ela vive no
Mongo e não aqui dentro.

CADA REGRA TEM UMA AÇÃO:
  bloquear  -> a resposta não vai. Chama a equipe.
  avisar    -> a resposta vai, mas fica registrada para revisão.
  trocar    -> a palavra é substituída pela preferida da marca.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from app.core.database import db

logger = logging.getLogger(__name__)

COLECAO = "palavras_proibidas"

_cache: Optional[List[Dict[str, Any]]] = None


# As que já vêm dos manuais da Yup. Servem de ponto de partida e podem ser
# desativadas pelo painel como qualquer outra.
PADRAO: List[Dict[str, Any]] = [
    # ── Sigilo (Manual de Cultura: nunca expor custo, margem, estratégia) ──
    {"termo": "margem", "acao": "bloquear", "motivo": "dado interno"},
    {"termo": "preço de custo", "acao": "bloquear", "motivo": "dado interno"},
    {"termo": "nosso fornecedor", "acao": "bloquear", "motivo": "dado interno"},
    {"termo": "lucro", "acao": "bloquear", "motivo": "dado interno"},

    # ── Integridade: urgência inventada e desconto não autorizado ──
    # A Peper não tem alçada para dar desconto. Prometer um é criar uma
    # obrigação que a loja vai ter que honrar no caixa ou desdizer na cara
    # do cliente — e as duas saídas são ruins.
    {"termo": "desconto especial", "acao": "bloquear", "motivo": "a Peper não tem alçada para desconto"},
    {"termo": "último dia", "acao": "bloquear", "motivo": "urgência inventada"},
    {"termo": "últimas unidades", "acao": "bloquear", "motivo": "urgência inventada"},
    {"termo": "promoção relâmpago", "acao": "bloquear", "motivo": "urgência inventada"},

    # ── Nunca afirmar falta sem consultar (ver prompt, bloco 5) ──
    {"termo": "não trabalhamos com", "acao": "bloquear",
     "motivo": "só pode afirmar falta com saldo zero confirmado"},
    {"termo": "não temos esse produto", "acao": "bloquear",
     "motivo": "só pode afirmar falta com saldo zero confirmado"},

    # ── Tom (a Yup não é fria nem burocrática) ──
    {"termo": "prezado cliente", "acao": "trocar", "troca_por": "oi", "motivo": "tom frio"},
    {"termo": "estou à disposição", "acao": "trocar", "troca_por": "qualquer coisa me chama",
     "motivo": "tom burocrático"},
    {"termo": "informamos que", "acao": "trocar", "troca_por": "", "motivo": "tom burocrático"},
    {"termo": "venho por meio desta", "acao": "trocar", "troca_por": "", "motivo": "tom burocrático"},

    # ── Pagamento fora do canal oficial (Manual de Cultura) ──
    {"termo": "pix de conta pessoal", "acao": "bloquear", "motivo": "só canal oficial"},
    {"termo": "minha conta", "acao": "avisar", "motivo": "pode ser pagamento fora do canal oficial"},
]


async def carregar(forcar: bool = False) -> List[Dict[str, Any]]:
    global _cache
    if _cache is not None and not forcar:
        return _cache

    regras = list(PADRAO)
    try:
        async for doc in db.db[COLECAO].find({"ativo": {"$ne": False}}):
            doc.pop("_id", None)
            regras = [r for r in regras if r["termo"].lower() != str(doc.get("termo", "")).lower()]
            regras.append(doc)
    except Exception as e:  # noqa: BLE001
        logger.warning("Não consegui ler as palavras proibidas no Mongo: %s", e)

    _cache = regras
    return regras


def invalidar_cache() -> None:
    """Chamar depois de editar a lista pelo painel."""
    global _cache
    _cache = None


def _padrao(termo: str) -> re.Pattern:
    # \b nas pontas para "lucro" não casar dentro de "lucrosa"; a lista é
    # de termos que a marca não usa, não de pedaços de palavra.
    return re.compile(r"\b" + re.escape(termo.strip()) + r"\b", re.IGNORECASE)


async def para_prompt() -> str:
    """O bloco que entra no prompt. Vazio se não houver nada a dizer."""
    regras = await carregar()
    bloqueia = [r["termo"] for r in regras if r.get("acao") == "bloquear"]
    troca = [(r["termo"], r.get("troca_por", "")) for r in regras if r.get("acao") == "trocar"]
    if not bloqueia and not troca:
        return ""

    linhas = ["", "PALAVRAS QUE A YUP NÃO USA"]
    if bloqueia:
        linhas.append("- Nunca escreva: " + "; ".join(sorted(bloqueia)) + ".")
    for termo, por in troca:
        if por:
            linhas.append(f'- Em vez de "{termo}", diga "{por}".')
        else:
            linhas.append(f'- Não use "{termo}".')
    return "\n".join(linhas)


async def verificar(texto: str) -> Dict[str, Any]:
    """
    Confere a resposta PRONTA, antes de enviar.

    Devolve `texto` já com as trocas aplicadas e `bloquear=True` quando a
    resposta não pode sair. Quem chama decide o que fazer — normalmente
    chamar a equipe, nunca mandar um texto remendado às pressas.
    """
    regras = await carregar()
    achados: List[Dict[str, str]] = []
    bloquear = False
    saida = texto or ""

    for r in regras:
        termo = str(r.get("termo") or "").strip()
        if not termo:
            continue
        padrao = _padrao(termo)
        if not padrao.search(saida):
            continue

        acao = r.get("acao", "avisar")
        achados.append({"termo": termo, "acao": acao, "motivo": r.get("motivo", "")})

        if acao == "bloquear":
            bloquear = True
        elif acao == "trocar":
            saida = padrao.sub(r.get("troca_por", ""), saida)
            # a troca por vazio deixa espaço duplo e vírgula órfã
            saida = re.sub(r"\s{2,}", " ", saida).replace(" ,", ",").strip()

    if achados:
        logger.warning("Filtro de palavras: %s", achados)

    return {"texto": saida, "bloquear": bloquear, "achados": achados}
