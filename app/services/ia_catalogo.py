# app/services/ia_catalogo.py
"""
Acesso a produto/preço/estoque para a Peper IA.

REGRA DE ARQUITETURA (a mais importante deste arquivo):
o bot NÃO fala com o Olist. Ele fala com o backend de estoque
(`meu_projeto`, o MVP de reposição onde a Daiane trabalha).

Motivo: o rate limit da API v3 do Olist é POR CONTA, não por app —
30/min no plano Construa, 60/min no Impulsione. O balcão roda na conta da
FILIAL (54/min configurados), e esse teto já está sendo consumido pelo
sync de reposição. Se o bot abrisse um segundo cliente,
seriam dois limitadores independentes disputando uma cota única, e eles
colidem justamente no dia de movimento. Um dono do token, um limitador.

Dois caminhos, de propósito:

1. BUSCAR (que produto o cliente quer) -> espelho local do backend.
   Custo zero de API, resposta instantânea, e é busca textual, que a API
   do Olist faz mal de qualquer jeito.

2. CONFIRMAR (preço e saldo do item escolhido) -> tempo real.
   Uma chamada, só quando a conversa chegou ao ponto de falar valor.

Com teto por conversa (IA_MAX_CONSULTAS_ERP) para uma conversa não comer
a cota de todas.
"""

import logging
from typing import Any, Dict, List

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Depósitos que valem como "tem na loja" para o cliente do balcão.
# "Fiscal" fica fora de propósito: é saldo fiscal, não prateleira.
DEPOSITOS_VENDAVEIS = ("Controle Geral", "Deposito Loja")


def _url(caminho: str) -> str:
    return f"{settings.backend_estoque_url.rstrip('/')}{caminho}"


def _saldo_vendavel(produto: Dict[str, Any]) -> int:
    estoque = produto.get("estoque") or {}
    return sum(int(estoque.get(d) or 0) for d in DEPOSITOS_VENDAVEIS)


def _resumir(codigo: str, produto: Dict[str, Any]) -> Dict[str, Any]:
    """Só o que a IA precisa para redigir. Menos campo = menos token."""
    return {
        "codigo": produto.get("codigo") or codigo,
        "descricao": produto.get("descricao"),
        "preco": produto.get("preco"),
        "unidade": produto.get("unidade"),
        "saldo": _saldo_vendavel(produto),
    }


async def _get(caminho: str, params: Dict[str, Any] | None = None) -> Dict[str, Any] | None:
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=4.0)) as client:
            r = await client.get(_url(caminho), params=params)
        if r.status_code == 200:
            return r.json()
        logger.warning("Backend de estoque %s -> %s", caminho, r.status_code)
    except httpx.TimeoutException:
        # 8s é o limite do que o cliente aceita esperar. Estourar aqui não
        # é erro fatal: a IA responde "deixa eu confirmar" e chama humano.
        logger.warning("Timeout no backend de estoque em %s", caminho)
    except Exception as e:  # noqa: BLE001
        logger.warning("Falha no backend de estoque em %s: %s", caminho, e)
    return None


# ---------------------------------------------------------------------- #
# Ferramenta 1 — buscar (espelho, 0 chamadas ao Olist)
# ---------------------------------------------------------------------- #

async def buscar_produto(termo: str, limite: int = 5) -> Dict[str, Any]:
    dados = await _get(
        "/estoque/produtos/buscar",
        {"termo": termo, "limite": limite, "filtro_estoque": "com_estoque"},
    )
    if not dados or not dados.get("sucesso"):
        return {"ok": False, "motivo": "catalogo_indisponivel", "produtos": []}

    produtos: List[Dict[str, Any]] = [
        _resumir(codigo, p) for codigo, p in (dados.get("produtos") or {}).items()
    ]
    return {
        "ok": True,
        "total_encontrados": dados.get("total_encontrados", len(produtos)),
        # Mostrados = os primeiros `limite`. Se achou 300, a IA tem que
        # pedir para o cliente refinar, não despejar lista no WhatsApp.
        "produtos": produtos[:limite],
    }


# ---------------------------------------------------------------------- #
# Ferramenta 2 — confirmar (tempo real)
# ---------------------------------------------------------------------- #

async def confirmar_preco_estoque(codigo: str) -> Dict[str, Any]:
    """
    Preço e saldo que PODEM ser falados para o cliente.

    Tenta o endpoint de tempo real primeiro (consulta o Olist na hora).
    Se ele não existir ou falhar, cai no espelho e marca
    `fonte: "espelho"` — a IA é instruída a avisar que vai confirmar
    quando a fonte não for tempo real. Melhor um "confirmo já" do que um
    preço errado dito com convicção.
    """
    tempo_real = await _get(f"/estoque/produtos/{codigo}/tempo-real")
    if tempo_real and tempo_real.get("sucesso"):
        p = tempo_real.get("produto") or {}
        return {"ok": True, "fonte": "tempo_real", **_resumir(codigo, p)}

    espelho = await _get(f"/estoque/produtos/{codigo}")
    if espelho and espelho.get("sucesso"):
        p = espelho.get("produto") or {}
        return {"ok": True, "fonte": "espelho", **_resumir(codigo, p)}

    return {"ok": False, "motivo": "nao_consegui_confirmar", "codigo": codigo}
