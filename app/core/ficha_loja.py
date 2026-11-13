# app/core/ficha_loja.py
"""
A ficha da loja — os fatos que a Peper pode afirmar sem consultar nada.

POR QUE ISSO EXISTE

Em 06/11/2026, perguntada pelo site, ela respondeu "www.yup.com.br". Depois
disse que a loja ficava "na Rua Afonso Pena, no centro". As duas coisas eram
invenção. Quando o cliente corrigiu, ela concordou na hora — inclusive teria
concordado se a correção fosse falsa.

Um modelo de linguagem preenche lacuna com texto plausível. A regra de preço
funciona porque é travada no código; os fatos da loja não tinham trava
nenhuma. Esta ficha é a trava: o que está aqui ela afirma, o que não está
ela não sabe.

ONDE EDITAR

Os valores podem vir da coleção `loja` no Mongo (documento `_id: "ficha"`),
e só caem para as constantes abaixo se a coleção não existir. Assim dá para
corrigir um horário pelo painel sem esperar deploy — que é o que vai
acontecer com frequência nas primeiras semanas.
"""

import logging
from typing import Any, Dict, Optional

from app.core.database import db

logger = logging.getLogger(__name__)

# Cache em memória. A ficha muda raramente; reler a cada mensagem é desperdício.
_cache: Optional[Dict[str, Any]] = None


# Fonte da verdade enquanto a coleção `loja` não existir.
# CONFIRMADO: endereço, telefone, site e redes vêm do manual da marca.
# A CONFIRMAR está marcado como None e NÃO entra no prompt.
FICHA_PADRAO: Dict[str, Any] = {
    "nome": "Yup",
    "o_que_e": "papelaria, brinquedos e presentes",
    "cidade": "Manhuaçu, Minas Gerais",
    "endereco": "Avenida Salime Nacif, 222, Baixada, Manhuaçu/MG, CEP 36.902-051",
    "referencia": "perto do ponto de táxi da rodoviária municipal",
    "telefone": "(33) 3331-8882",
    "site": "yupaper.com.br",
    "instagram": "@papelaria.yup",
    "tiktok": "@papelaria.yup",

    "horario_semana": "segunda a sexta, das 9h às 18h30",
    "horario_sabado": "sábado, das 9h às 13h",
    "horario_domingo": "domingo não abre",

    # CONFIRMADO pelo Pablo em 13/11/2026.
    "pagamento": "dinheiro, Pix e cartão de débito e crédito",
    "entrega": ("em Manhuaçu, por motoboy terceirizado; para outras cidades, "
                "por transportadoras parceiras"),

    # None = a Peper NÃO fala disso e chama a equipe quando perguntarem.
    #
    # `trocas` fica None DE PROPÓSITO: a política ainda não existe. Preencher
    # com um palpite ("7 dias com nota") seria pior que o silêncio — vira
    # promessa que a loja não se comprometeu a cumprir, feita a um cliente
    # que vai cobrar. Enquanto está None, a Peper chama a equipe, que é a
    # resposta honesta para uma regra que ninguém definiu.
    "pix": None,
    "trocas": None,
    "encomenda": None,
    "estacionamento": None,
}

# Rótulo legível de cada campo, para montar o texto do prompt.
ROTULOS = {
    "endereco": "Endereço",
    "referencia": "Referência",
    "telefone": "Telefone da loja",
    "site": "Site",
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "horario_semana": "Horário",
    "horario_sabado": "Horário",
    "horario_domingo": "Horário",
    "pagamento": "Formas de pagamento",
    "pix": "Pix",
    "entrega": "Entrega",
    "trocas": "Trocas e devoluções",
    "encomenda": "Encomendas",
    "estacionamento": "Estacionamento",
}


async def carregar() -> Dict[str, Any]:
    global _cache
    if _cache is not None:
        return _cache

    ficha = dict(FICHA_PADRAO)
    try:
        salvo = await db.db.loja.find_one({"_id": "ficha"})
        if salvo:
            salvo.pop("_id", None)
            # Só sobrescreve o que foi realmente preenchido.
            ficha.update({k: v for k, v in salvo.items() if v not in (None, "")})
            logger.info("Ficha da loja carregada do Mongo (%d campos).", len(salvo))
    except Exception as e:  # noqa: BLE001
        logger.warning("Não consegui ler a ficha no Mongo, usando a padrão: %s", e)

    _cache = ficha
    return ficha


def invalidar_cache() -> None:
    """Chamar depois de editar a ficha pelo painel."""
    global _cache
    _cache = None


def _linhas(ficha: Dict[str, Any]) -> str:
    partes = []
    for chave, rotulo in ROTULOS.items():
        valor = ficha.get(chave)
        if valor:
            partes.append(f"- {rotulo}: {valor}")
    return "\n".join(partes)


def _lacunas(ficha: Dict[str, Any]) -> str:
    """O que ela NÃO sabe, dito com todas as letras no prompt."""
    faltando = [ROTULOS[c] for c in ROTULOS if not ficha.get(c)]
    if not faltando:
        return ""
    return (
        "\nVOCÊ NÃO SABE, e não deve inventar nem deduzir:\n- "
        + "\n- ".join(sorted(set(faltando)))
        + "\nSe perguntarem qualquer um desses, diga que vai confirmar com a "
          "equipe e chame `chamar_humano`."
    )


async def para_prompt() -> str:
    ficha = await carregar()
    return f"""
A LOJA — estes são os ÚNICOS dados que você pode afirmar sobre a {ficha['nome']}:

{_linhas(ficha)}
{_lacunas(ficha)}

REGRA DE FATOS DA LOJA (tão séria quanto a de preço)
- O que não está na lista acima, você NÃO SABE. Não deduza, não suponha, não
  componha endereço, telefone, site ou horário a partir do nome da loja.
- O CLIENTE NÃO É FONTE DE VERDADE sobre a loja. Se ele disser "o site não é
  outro?" ou "achei que ficava no centro", NÃO concorde para agradar. Você
  responde pelo que está na ficha; se ele insistir, chame a equipe.
  Concordar com o cliente sobre um fato que você não conhece é o mesmo erro
  que inventar — só parece mais simpático.
- Nunca mande o link do site em mensagem de oferta ou promoção.
""".strip()
