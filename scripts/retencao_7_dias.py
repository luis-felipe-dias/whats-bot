"""
scripts/retencao_7_dias.py

Cria o índice TTL que apaga mensagens com mais de N dias.

⚠️  LEIA ANTES DE RODAR

O índice TTL é GLOBAL na coleção `mensagens`. Ele não distingue a conversa
de teste da conversa de cliente real do 8882. Rodar isto com 7 dias
significa: toda mensagem da loja passa a ser apagada em 7 dias.

Hoje o limpeza_worker já é agressivo, então 7 dias é uma MELHORA — mas é
uma decisão, não um detalhe. E tem um custo que não aparece agora:
mensagem apagada é material de treino que não existe mais. O pico
(15/12 a 01/03) é a melhor matéria-prima do ano para ensinar a Peper.

Recomendação: 7 dias enquanto for só teste; subir para 90 ANTES de 10/12.

    python scripts/retencao_7_dias.py 7     # teste
    python scripts/retencao_7_dias.py 90    # antes do pico
    python scripts/retencao_7_dias.py --remover
"""

import asyncio
import sys

from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings

NOME_INDICE = "ttl_data_hora"


async def main() -> None:
    cliente = AsyncIOMotorClient(settings.mongodb_url)
    colecao = cliente[settings.mongodb_db_name].mensagens

    if "--remover" in sys.argv:
        await colecao.drop_index(NOME_INDICE)
        print(f"Índice {NOME_INDICE} removido. Mensagens param de expirar.")
        return

    dias = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 7
    segundos = dias * 24 * 60 * 60

    # Trocar o prazo exige recriar: o Mongo não altera expireAfterSeconds
    # de um índice existente por create_index.
    try:
        await colecao.drop_index(NOME_INDICE)
        print(f"Índice anterior removido.")
    except Exception:
        pass

    await colecao.create_index(
        "data_hora", name=NOME_INDICE, expireAfterSeconds=segundos
    )
    print(f"✅ Mensagens passam a expirar em {dias} dias.")
    print("   O Mongo varre a cada ~60s, então a limpeza não é instantânea.")
    cliente.close()


if __name__ == "__main__":
    asyncio.run(main())
