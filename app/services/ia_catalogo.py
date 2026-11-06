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
# Vocabulário: o cliente e o cadastro falam línguas diferentes
# ---------------------------------------------------------------------- #

# O cadastro da loja nomeia por padrão de fornecedor, não por como o
# cliente pede. "marcador de texto" não existe em lugar nenhum; o que
# existe é "MARCA TEXTO BOSS 70/23 CORES ... | STABILO".
SINONIMOS = {
    "marcador": "marca texto",
    "marcadores": "marca texto",
    "marcatexto": "marca texto",
    "grifador": "marca texto",
    "grifa": "marca texto",
    "canetinha": "caneta hidrografica",
    "canetinhas": "caneta hidrografica",
    "hidrocor": "caneta hidrografica",
    "giz de cera": "giz cera",
    "lapis de cor": "lapis cor",
    "apontador": "apontador",
    "xerox": "copia",
    "fotocopia": "copia",
}

# Palavras que o cliente usa para pedir, mas que não descrevem produto.
RUIDO = {
    "de", "da", "do", "das", "dos", "para", "pra", "com", "sem", "um", "uma",
    "uns", "umas", "o", "a", "os", "as", "e", "em", "no", "na", "nos", "nas",
    "tem", "teria", "tenho", "quero", "queria", "gostaria", "preciso",
    "procuro", "voces", "vcs", "ai", "aqui", "por", "favor", "se", "qual",
    "quais", "quanto", "quanta", "custa", "preco", "valor", "me", "ver",
}


def _normalizar(texto: str) -> str:
    import unicodedata
    return "".join(
        c for c in unicodedata.normalize("NFD", texto or "")
        if unicodedata.category(c) != "Mn"
    ).lower().strip()


def _variacoes(termo: str) -> List[str]:
    """
    Gera tentativas, da mais específica para a mais ampla.

    Por que em cascata: a busca do backend exige que TODOS os tokens
    apareçam. "marcador de texto stabilo" não acha nada; "texto stabilo"
    acha dezenas. Em vez de a Peper concluir "não temos" — que foi o que
    aconteceu com o catálogo cheio de Stabilo em estoque —, ela tenta
    formas progressivamente mais largas antes de desistir.
    """
    bruto = _normalizar(termo)
    if not bruto:
        return []

    tentativas: List[str] = [bruto]

    # 1. aplica sinônimos conhecidos da loja
    traduzido = bruto
    for de, para in SINONIMOS.items():
        if de in traduzido:
            traduzido = traduzido.replace(de, para)
    if traduzido != bruto:
        tentativas.append(traduzido)

    # 2. tira as palavras de pedido, fica só o que descreve produto
    #    (sem repetir token, que a tradução de sinônimo às vezes duplica)
    uteis: List[str] = []
    for t in traduzido.split():
        if t not in RUIDO and len(t) > 1 and t not in uteis:
            uteis.append(t)
    if uteis and " ".join(uteis) not in tentativas:
        tentativas.append(" ".join(uteis))

    # 3. últimas cartadas: as PRIMEIRAS palavras, não as mais longas.
    #    Em português o cliente diz o produto antes da marca — "caderno
    #    tilibra", "marca texto stabilo". Escolher pela maior palavra
    #    descartava justamente a marca ("tilibra" perdia para "materias").
    if len(uteis) > 2 and " ".join(uteis[:2]) not in tentativas:
        tentativas.append(" ".join(uteis[:2]))
    if len(uteis) > 1 and uteis[0] not in tentativas:
        tentativas.append(uteis[0])

    return tentativas


# ---------------------------------------------------------------------- #
# Ferramenta 1 — buscar (espelho, 0 chamadas ao Olist)
# ---------------------------------------------------------------------- #

async def buscar_produto(termo: str, limite: int = 5) -> Dict[str, Any]:
    """
    SEM filtro de estoque, de propósito.

    A primeira versão mandava filtro_estoque="com_estoque" e isso
    escondia TODO serviço do catálogo: impressão, cópia, encadernação e
    plastificação têm saldo zero por natureza, porque não são itens de
    prateleira. O cliente perguntava "impressão" e a Peper não achava
    nada, concluía que não sabia o preço e passava para a equipe.

    Agora vem tudo e o saldo vai junto no resultado. Quem decide o que
    dizer é a IA, orientada pelo prompt: saldo zero em produto é "acabou",
    saldo zero em serviço não quer dizer nada.
    """
    for tentativa, termo_usado in enumerate(_variacoes(termo), start=1):
        dados = await _get(
            "/estoque/produtos/buscar",
            {"termo": termo_usado, "limite": limite},
        )
        if dados is None:
            return {"ok": False, "motivo": "catalogo_indisponivel", "produtos": []}

        produtos: List[Dict[str, Any]] = [
            _resumir(codigo, p) for codigo, p in (dados.get("produtos") or {}).items()
        ]
        if produtos:
            return {
                "ok": True,
                "termo_usado": termo_usado,
                "tentativa": tentativa,
                "total_encontrados": dados.get("total_encontrados", len(produtos)),
                # Mostrados = os primeiros `limite`. Se achou 300, a IA tem
                # que pedir para o cliente refinar, não despejar lista.
                "produtos": produtos[:limite],
            }

    return {"ok": True, "total_encontrados": 0, "produtos": [],
            "observacao": "Nada encontrado nem com variações do termo. "
                          "Pergunte a marca ou o tipo exato antes de afirmar que não tem."}


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

    # ATENÇÃO AO FORMATO: /estoque/produtos/{codigo} devolve o produto
    # DIRETO, sem envelope {"sucesso": ...}. A primeira versão checava
    # `sucesso` e por isso NUNCA confirmava preço — a Peper dizia "não
    # consegui confirmar o preço agora" para todo produto que existia.
    espelho = await _get(f"/estoque/produtos/{codigo}")
    if espelho:
        p = espelho.get("produto") if "produto" in espelho else espelho
        if p and (p.get("descricao") or p.get("codigo")):
            return {"ok": True, "fonte": "espelho", **_resumir(codigo, p)}

    return {"ok": False, "motivo": "nao_consegui_confirmar", "codigo": codigo}
