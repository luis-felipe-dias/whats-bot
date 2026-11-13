# app/api/loja.py
"""
Ficha da loja pelo painel — o fim do "me espera que eu dou deploy".

POR QUE ESTA ROTA EXISTE
A ficha (app/core/ficha_loja.py) é a trava que impede a Peper de inventar
endereço, site e horário. Mas até agora ela só podia ser corrigida editando
Python e subindo código. Nas primeiras semanas isso é exatamente o campo que
muda mais: horário de feriado, política de troca que acabou de nascer, Pix.

Então: GET devolve a ficha com rótulo e o que ainda está vazio; PUT grava no
Mongo e invalida o cache. A próxima mensagem do cliente já usa o valor novo.

CAMPO VAZIO NÃO É DEFEITO
Vazio é informação: a Peper diz que vai confirmar com a equipe em vez de
chutar. Por isso o PUT aceita string vazia como "apagar" — devolver um campo
para o estado "não sei" tem que ser tão fácil quanto preencher.

Registrar em main.py:
    from app.api import loja
    app.include_router(loja.router, prefix="/loja", tags=["Loja"])
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core import ficha_loja
from app.core.database import db

router = APIRouter()
logger = logging.getLogger(__name__)

# Os campos que o painel pode editar. Allowlist de propósito: o painel não
# cria campo novo, porque campo que o prompt não lê é campo que o Pablo
# preenche e não vê efeito nenhum.
EDITAVEIS = list(ficha_loja.ROTULOS.keys())

# Ajuda de tela, para quem preenche saber o que a Peper vai dizer.
DICAS: Dict[str, str] = {
    "endereco": "Como você quer que ela dite o endereço para o cliente.",
    "referencia": "Um ponto conhecido perto da loja.",
    "telefone": "Com DDD.",
    "site": "Sem http. Ela nunca manda o site em mensagem de oferta.",
    "instagram": "Com @.",
    "tiktok": "Com @.",
    "horario_semana": "Ex.: segunda a sexta, das 9h às 18h30.",
    "horario_sabado": "Ex.: sábado, das 9h às 13h.",
    "horario_domingo": "Ex.: domingo não abre.",
    "pagamento": "O que a loja aceita hoje.",
    "pix": "Só o necessário para o cliente pagar. Nunca chave de conta pessoal.",
    "entrega": "Como entrega em Manhuaçu e como entrega fora.",
    "trocas": "Prazo e condição. Em branco até a política existir.",
    "encomenda": "Se faz encomenda e em quanto tempo.",
    "estacionamento": "Se tem, onde é.",
}


class FichaRequest(BaseModel):
    campos: Dict[str, Optional[str]]
    por: str = "Atendente"


@router.get("/ficha")
async def ler_ficha():
    """A ficha em vigor — a mesma que vai para o prompt neste momento."""
    ficha = await ficha_loja.carregar()

    campos = []
    for chave in EDITAVEIS:
        valor = ficha.get(chave)
        campos.append({
            "chave": chave,
            "rotulo": ficha_loja.ROTULOS[chave],
            "valor": valor or "",
            "preenchido": bool(valor),
            "dica": DICAS.get(chave, ""),
            "padrao": ficha_loja.FICHA_PADRAO.get(chave) or "",
        })

    faltando = [c["rotulo"] for c in campos if not c["preenchido"]]

    return {
        "sucesso": True,
        "nome": ficha.get("nome"),
        "campos": campos,
        "faltando": sorted(set(faltando)),
        # O texto exato que entra no prompt. Ver é a melhor forma de
        # entender por que um campo vazio muda a resposta dela.
        "prompt": await ficha_loja.para_prompt(),
    }


@router.put("/ficha")
async def salvar_ficha(req: FichaRequest):
    """
    Grava só os campos enviados. String vazia apaga o campo — volta a ser
    "não sei", que é um estado legítimo.
    """
    desconhecidos = [k for k in req.campos if k not in EDITAVEIS]
    if desconhecidos:
        raise HTTPException(400, f"Campo que o prompt não lê: {', '.join(desconhecidos)}")

    atualizar: Dict[str, Any] = {}
    for chave, valor in req.campos.items():
        limpo = (valor or "").strip()
        atualizar[chave] = limpo or None

    if not atualizar:
        raise HTTPException(400, "Nada para salvar.")

    atualizar["atualizado_por"] = req.por

    await db.db.loja.update_one(
        {"_id": "ficha"},
        {"$set": atualizar},
        upsert=True,
    )
    ficha_loja.invalidar_cache()
    logger.info("Ficha da loja atualizada por %s: %s", req.por, list(atualizar.keys()))

    return await ler_ficha()
