# app/services/ia_handler.py
"""
Faixa IA da Peper — MVP.

Como se encaixa no bot: é uma FAIXA PARALELA, não uma reescrita. O
webhook.py decide, por telefone, se a mensagem vai para a máquina de
estados (8882, produção, intocada) ou para cá (número de teste).

    mensagem -> webhook -> ia_deve_atender(telefone)?
                             sim -> ia_responder()        <- aqui
                             não -> StateMachine          <- como sempre

Escopo do MVP, de propósito curto:
- contexto = só as mensagens de HOJE (meia-noite de São Paulo em diante)
- 3 ferramentas: buscar produto, confirmar preço/estoque, chamar humano
- áudio é transcrito; foto cai em regra fixa, não em decisão de IA
- a IA NUNCA fala um preço que não veio de ferramenta (trava no código,
  não só no prompt)
"""

import json
import logging
from datetime import datetime, timedelta, timezone as _tz
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import TIMEZONE, settings
from app.core.database import db
from app.core.openai_client import openai_client
from app.services import ia_catalogo
from app.utils.helpers import now_utc

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------- #
# Chaveamento
# ---------------------------------------------------------------------- #

def _so_digitos(valor: str) -> str:
    return "".join(filter(str.isdigit, valor or ""))


def ia_deve_atender(telefone: str) -> bool:
    """
    Liga a IA só para os números da lista branca. Sem isso, um erro de
    configuração joga a loja inteira na IA no meio do expediente.

    IA_NUMEROS vazio com IA_ENABLED=true NÃO libera para todos — libera
    para ninguém. Falhar fechado é a única opção aceitável aqui.
    """
    if not settings.ia_enabled or not openai_client.configurado:
        return False
    permitidos = {_so_digitos(n) for n in settings.ia_numeros.split(",") if n.strip()}
    return _so_digitos(telefone) in permitidos if permitidos else False


# ---------------------------------------------------------------------- #
# Contexto: só o dia de hoje
# ---------------------------------------------------------------------- #

def _inicio_do_dia_utc() -> datetime:
    """
    Meia-noite de HOJE em America/Sao_Paulo, convertida para UTC naive
    (que é como o Mongo deste projeto guarda data_hora).

    Por que não usar UTC direto: em UTC o corte do dia cai às 21h de
    Brasília — exatamente o horário de pico de papelaria. A conversa
    partiria no meio.
    """
    agora_sp = datetime.now(TIMEZONE)
    meia_noite_sp = agora_sp.replace(hour=0, minute=0, second=0, microsecond=0)
    return meia_noite_sp.astimezone(_tz.utc).replace(tzinfo=None)


async def _historico_de_hoje(sessao_id: str, limite: int = 30) -> List[Dict[str, str]]:
    """
    Mensagens da sessão a partir da meia-noite de São Paulo, em ordem.

    `limite` existe como trava de custo: uma conversa com 200 mensagens
    num dia (acontece) viraria um prompt caríssimo. Pega as últimas 30.
    """
    cursor = (
        db.db.mensagens.find(
            {"sessao_id": sessao_id, "data_hora": {"$gte": _inicio_do_dia_utc()}},
            {"conteudo": 1, "direcao": 1, "sender": 1, "tipo": 1},
        )
        .sort("data_hora", -1)
        .limit(limite)
    )
    registros = await cursor.to_list(length=limite)
    registros.reverse()

    historico: List[Dict[str, str]] = []
    for m in registros:
        conteudo = (m.get("conteudo") or "").strip()
        if not conteudo:
            continue
        papel = "assistant" if m.get("direcao") == "enviada" else "user"
        # Mensagem de atendente humano entra como assistant mesmo: para a
        # IA, é "o que a loja já respondeu". Misturar os dois papéis é o
        # que faz o bot repetir o que a atendente acabou de dizer.
        historico.append({"role": papel, "content": conteudo})
    return historico


# ---------------------------------------------------------------------- #
# Persona
# ---------------------------------------------------------------------- #

async def _prompt_sistema(nome_cliente: Optional[str]) -> str:
    tratamento = (
        f"O cliente se chama {nome_cliente.split()[0]}. Use o primeiro nome dele naturalmente, "
        "uma vez ou duas na conversa — não em toda frase."
        if nome_cliente else
        "Você ainda não sabe o nome do cliente. Pode perguntar, de forma leve, se a conversa permitir."
    )
    from app.core.ficha_loja import para_prompt
    ficha = await para_prompt()

    return f"""Você é a Peper, atendente da YUP! — papelaria e brinquedos em Manhuaçu, Minas Gerais.

{ficha}


Você NÃO é um robô de menu. Você conversa como uma atendente boa de balcão: simpática, direta, sem formalidade excessiva e sem enrolação. Português do Brasil, tom mineiro leve.

{tratamento}

COMO VOCÊ ESCREVE
- Mensagem de WhatsApp: curta. Duas ou três linhas resolvem quase tudo.
- Sem "prezado cliente", sem "estou à disposição", sem bloco de texto.
- Emoji com parcimônia: no máximo um, e só quando couber.
- Nunca diga que você é uma IA ou um sistema. Você é a Peper, da YUP!.

CADA MENSAGEM SUA CUSTA DINHEIRO
Desde outubro de 2026 a Meta cobra por mensagem entregue, inclusive as
suas respostas. Então:
- Quando precisar de mais de uma informação, PEÇA TUDO NUMA MENSAGEM SÓ.
  Certo: "Quantas páginas, colorido ou preto e branco, e frente e verso?"
  Errado: três mensagens seguidas com uma pergunta cada.
- Nunca mande "ok", "entendi", "um momento" sozinhos. Junte com o conteúdo.
- Não repita o que o cliente acabou de dizer para confirmar.

REGRA QUE NÃO SE QUEBRA — PREÇO E ESTOQUE
- Você NUNCA inventa, estima ou "lembra" preço nem quantidade.
- Para falar de produto: chame `buscar_produto` para achar o item.
- Para falar VALOR ou dizer que TEM em estoque: chame `confirmar_preco_estoque` com o código.
- Se a ferramenta devolver fonte "espelho" em vez de "tempo_real", diga o valor e avise que confirma na hora — ex.: "tá R$ 12,90 aqui, só vou confirmar certinho e te falo".
- Se a ferramenta falhar, NÃO adivinhe: chame `chamar_humano`.
- Se a busca achar muitos itens, peça para o cliente especificar (marca, tamanho, cor) em vez de listar tudo.

NUNCA AFIRME QUE A LOJA NÃO TEM
O cadastro usa o nome do fornecedor, não o nome que o cliente usa. O cliente
diz "marcador de texto"; no sistema está "MARCA TEXTO BOSS 70/23 CORES | STABILO".
A busca já tenta variações sozinha, mas ela pode falhar mesmo assim.

- Busca vazia NÃO quer dizer que a loja não tem. Quer dizer que você não achou.
- Nunca diga "não temos", "não trabalhamos com" ou "está em falta" com base
  numa busca vazia. Dizer isso manda embora um cliente de um produto que
  está na prateleira.
- Em vez disso: pergunte a marca, o modelo ou para que vai usar, e busque de
  novo com o que ele responder.
- Se depois de duas buscas você ainda não achou, chame a equipe. Alguém
  olhando a prateleira resolve em dez segundos.
- Só afirme que acabou quando `confirmar_preco_estoque` devolver saldo zero
  de um produto que você ENCONTROU. Aí sim é falta de estoque de verdade.

PRODUTO x SERVIÇO — o saldo significa coisas diferentes
- PRODUTO (caderno, cola, brinquedo): saldo 0 quer dizer que acabou. Diga que
  está em falta e ofereça encomendar ou avisar quando chegar.
- SERVIÇO (impressão, cópia, encadernação, plastificação): saldo 0 é o normal,
  porque não é item de prateleira. NUNCA diga que um serviço está em falta.
  O preço vale do mesmo jeito.

QUANDO CHAMAR HUMANO (`chamar_humano`)
- Reclamação, troca, defeito, cobrança, nota fiscal.
- Pedido grande, orçamento para escola ou empresa.
- Qualquer coisa que você não resolveu em duas tentativas.
- O cliente pedir para falar com uma pessoa.
Ao chamar humano, avise o cliente em uma linha que já está passando para a equipe.

O QUE VOCÊ ATENDE
- Dúvida de produto, preço, disponibilidade e as informações da ficha acima.
- Serviço de impressão: pergunte quantas páginas, colorido ou preto e branco,
  e se é frente e verso — tudo numa mensagem só — antes de passar valor.
"""


FERRAMENTAS = [
    {
        "type": "function",
        "function": {
            "name": "buscar_produto",
            "description": (
                "Busca produtos no catálogo da loja por nome, marca, código ou código de barras. "
                "Use sempre que o cliente mencionar um produto. Não custa nada e é rápido."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "termo": {
                        "type": "string",
                        "description": "O que procurar. Ex.: 'caderno tilibra 10 materias', 'cola bastao', '26705'.",
                    }
                },
                "required": ["termo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "confirmar_preco_estoque",
            "description": (
                "Confirma preço e saldo reais de UM produto, pelo código devolvido por buscar_produto. "
                "OBRIGATÓRIO antes de falar qualquer valor ou afirmar que tem em estoque."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "codigo": {"type": "string", "description": "Código do produto."}
                },
                "required": ["codigo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "chamar_humano",
            "description": (
                "Passa a conversa para um atendente da equipe. Use em reclamação, troca, nota fiscal, "
                "pedido grande, ou quando você não resolveu."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "motivo": {
                        "type": "string",
                        "description": "Resumo de uma linha do que o cliente precisa, para a equipe já chegar sabendo.",
                    }
                },
                "required": ["motivo"],
            },
        },
    },
]


# ---------------------------------------------------------------------- #
# Canal de saída
# ---------------------------------------------------------------------- #

async def _enviar(telefone: str, texto: str, botoes: Optional[List[str]] = None) -> bool:
    """
    Escolhe o canal pelo IA_CANAL. No MVP é "meta" (número de teste), e a
    produção segue na Z-API sem saber que esta faixa existe.
    """
    from app.core.canal import api_por_telefone
    api = await api_por_telefone(telefone)

    if botoes:
        return bool(await api.send_interactive(telefone, texto, botoes))
    return bool(await api.send_text(telefone, texto))


async def _registrar_resposta(sessao_id: str, contato_id: str, texto: str) -> None:
    await db.db.mensagens.insert_one({
        "sessao_id": sessao_id,
        "contato_id": str(contato_id),
        "direcao": "enviada",
        "sender": "pepper",
        "tipo": "texto",
        "conteudo": texto,
        "data_hora": now_utc(),
        "respondida": True,
        "metadata": {"origem": "ia", "modelo": settings.openai_model},
    })


# ---------------------------------------------------------------------- #
# Mídia
# ---------------------------------------------------------------------- #

async def _baixar_audio(file_url: str) -> bytes:
    """
    Na Meta, file_url aponta para o NOSSO proxy (/bot/yup/midia-meta/{id}).
    Chamar o próprio servidor por HTTP de dentro dele funciona, mas é uma
    volta boba e segura um worker: se reconhecer o padrão, baixa direto da
    Meta.
    """
    try:
        if "/midia-meta/" in file_url:
            from app.core.meta_cloud_api import meta_api
            media_id = file_url.rsplit("/", 1)[-1]
            url = await meta_api.obter_url_midia(media_id)
            return await meta_api.baixar_midia(url) if url else b""
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            r = await client.get(file_url)
        return r.content if r.status_code == 200 else b""
    except Exception as e:  # noqa: BLE001
        logger.warning("Falha ao baixar áudio: %s", e)
        return b""


# ---------------------------------------------------------------------- #
# Entrada principal
# ---------------------------------------------------------------------- #

async def ia_responder(
    sessao: Dict[str, Any],
    contato: Dict[str, Any],
    telefone: str,
    mensagem: str,
    tipo: str = "texto",
    file_url: Optional[str] = None,
    mime_type: Optional[str] = None,
) -> None:
    sessao_id = sessao["id"]
    contato_id = contato["id"]
    nome = contato.get("nome") or sessao.get("cliente_nome")

    # ---- Foto e documento: REGRA, não IA.
    # Perguntar "currículo ou impressão?" é decisão de negócio e sempre a
    # mesma. Gastar token e arriscar alucinação nisso não faz sentido.
    if tipo in ("imagem", "documento"):
        texto = "Recebi seu arquivo! 😊 Me diz uma coisa: é currículo ou é pra impressão?"
        if await _enviar(telefone, texto, ["📄 Currículo", "🖨️ Impressão"]):
            await _registrar_resposta(sessao_id, contato_id, texto)
        return

    # ---- Áudio: transcreve e segue na mesma faixa.
    if tipo == "audio" and file_url:
        audio = await _baixar_audio(file_url)
        transcrito = await openai_client.transcrever(audio) if audio else ""
        if not transcrito:
            texto = "Não consegui ouvir seu áudio direito 😅 pode me escrever?"
            if await _enviar(telefone, texto):
                await _registrar_resposta(sessao_id, contato_id, texto)
            return
        mensagem = transcrito
        # Guarda a transcrição na própria mensagem de áudio: o atendente
        # abre o painel e LÊ o que o cliente falou, em vez de dar play.
        await db.db.mensagens.find_one_and_update(
            {"sessao_id": sessao_id, "tipo": "audio", "direcao": "recebida"},
            {"$set": {"metadata.transcricao": transcrito}},
            sort=[("data_hora", -1)],
        )

    if not (mensagem or "").strip():
        return

    historico = await _historico_de_hoje(sessao_id)

    # A ORDEM AQUI É DECISÃO DE CUSTO, não estética.
    # A OpenAI cobra menos pelo trecho INICIAL do prompt quando ele se repete
    # entre chamadas, e ficha + regras são idênticas em toda mensagem. Subir
    # o histórico para o topo "porque é mais importante" quebraria esse
    # reaproveitamento a cada mensagem — e agora cada mensagem é cobrada.
    #
    #   1. ficha + regras      (nunca muda)
    #   2. conhecimento        (muda pouco)
    #   3. histórico de hoje   (muda sempre)
    from app.core.conhecimento import (
        buscar_similares,
        para_prompt as conhecimento_prompt,
    )

    mensagens: List[Dict[str, Any]] = [
        {"role": "system", "content": await _prompt_sistema(nome)}
    ]

    exemplos = await buscar_similares(mensagem)
    if exemplos:
        mensagens.append({"role": "system", "content": conhecimento_prompt(exemplos)})
        logger.info("Conhecimento: %d exemplo(s) aplicado(s), melhor=%.2f",
                    len(exemplos), exemplos[0]["semelhanca"])

    mensagens.extend(historico)
    # Se a transcrição não entrou no histórico (áudio salvo antes), garante
    # que a última fala do cliente está presente.
    if not historico or historico[-1].get("content") != mensagem:
        mensagens.append({"role": "user", "content": mensagem})

    consultas = 0
    usou_ferramenta_de_preco = False
    passar_para_humano: Optional[str] = None

    # Até 4 voltas: buscar -> confirmar -> redigir, com uma de folga.
    for _ in range(4):
        resposta = await openai_client.conversar(mensagens, FERRAMENTAS)
        if not resposta:
            passar_para_humano = "Falha técnica na IA"
            break

        chamadas = resposta.get("tool_calls") or []
        if not chamadas:
            texto = (resposta.get("content") or "").strip()

            # TRAVA DE PREÇO — a parte que protege o caixa.
            # Se a resposta cita valor e nenhuma ferramenta de preço foi
            # usada nesta conversa, o modelo inventou. Não sai.
            if ("R$" in texto or "reais" in texto.lower()) and not usou_ferramenta_de_preco:
                logger.warning("IA tentou falar preço sem consultar o ERP. Resposta bloqueada.")
                mensagens.append({
                    "role": "system",
                    "content": (
                        "Você citou um valor sem chamar confirmar_preco_estoque. "
                        "Chame a ferramenta agora ou responda sem mencionar preço."
                    ),
                })
                continue

            if not texto:
                passar_para_humano = "IA devolveu resposta vazia"
                break

            if await _enviar(telefone, texto):
                await _registrar_resposta(sessao_id, contato_id, texto)
                # Resolveu sem humano: vira candidato a conhecimento.
                # Enfileirar agora é o que torna a curadoria possível depois —
                # sem registro, não há o que revisar amanhã.
                from app.core.conhecimento import registrar_candidato
                await registrar_candidato(
                    sessao_id=sessao_id, pergunta=mensagem, resposta=texto, origem="ia"
                )
            return

        mensagens.append(resposta)

        for chamada in chamadas:
            nome_f = chamada["function"]["name"]
            try:
                args = json.loads(chamada["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}

            if nome_f == "chamar_humano":
                passar_para_humano = args.get("motivo") or "Cliente pediu atendente"
                resultado: Dict[str, Any] = {"ok": True, "transferido": True}

            elif consultas >= settings.ia_max_consultas_erp:
                # Teto por conversa: protege a cota do Olist, que é
                # compartilhada com o sync da reposição.
                logger.info("Teto de consultas ao ERP atingido nesta conversa.")
                resultado = {"ok": False, "motivo": "limite_de_consultas"}

            elif nome_f == "buscar_produto":
                consultas += 1
                resultado = await ia_catalogo.buscar_produto(args.get("termo", ""))

            elif nome_f == "confirmar_preco_estoque":
                consultas += 1
                resultado = await ia_catalogo.confirmar_preco_estoque(args.get("codigo", ""))
                if resultado.get("ok"):
                    usou_ferramenta_de_preco = True

            else:
                resultado = {"ok": False, "motivo": "ferramenta_desconhecida"}

            mensagens.append({
                "role": "tool",
                "tool_call_id": chamada["id"],
                "content": json.dumps(resultado, ensure_ascii=False),
            })

        if passar_para_humano:
            break
    else:
        passar_para_humano = passar_para_humano or "IA não concluiu a resposta"

    # ---- Transferência para a equipe
    if passar_para_humano:
        await _transferir(sessao_id, contato_id, telefone, passar_para_humano)


async def _posicao_na_fila(sessao_id: str) -> int:
    """
    Quantas pessoas estão na frente. Conta tickets ainda pendentes criados
    ANTES do desta sessão. Devolve 0 quando não dá para saber.
    """
    try:
        meu = await db.db.fila_humana.find_one(
            {"sessao_id": sessao_id, "status": "pendente"}, sort=[("data_criacao", -1)]
        )
        if not meu:
            return 0
        return await db.db.fila_humana.count_documents({
            "status": "pendente",
            "data_criacao": {"$lt": meu["data_criacao"]},
        })
    except Exception as e:  # noqa: BLE001
        logger.warning("Não consegui calcular a posição na fila: %s", e)
        return 0


async def _transferir(sessao_id: str, contato_id: str, telefone: str, motivo: str) -> None:
    from app.services.fila_humana_service import FilaHumanaService
    from app.services.sessao_service import SessaoService

    logger.info("IA transferindo sessão %s: %s", sessao_id, motivo)
    try:
        await SessaoService().atualizar_sessao(sessao_id, {
            "status": "humano",
            "setor_responsavel": "atendimento",
            "human_response_sent": False,
            "aguardando_atendente": True,
            "aguardando_desde": now_utc(),
            "dados_contexto.motivo_ia": motivo,
        })
        await FilaHumanaService().criar_ticket(
            sessao_id=sessao_id, contato_id=contato_id, tipo="atendimento"
        )
    except Exception as e:  # noqa: BLE001
        logger.error("Falha ao transferir para humano: %s", e)

    # A posição entra na MESMA mensagem da transferência, nunca numa
    # segunda. Cada mensagem é cobrada, e um "você é o 2º da fila"
    # sozinho custa igual a uma resposta de verdade.
    texto = "Vou te passar pra uma pessoa da equipe aqui, só um instante 💙"
    posicao = await _posicao_na_fila(sessao_id)
    if posicao == 1:
        texto = ("Vou te passar pra uma pessoa da equipe 💙 Tem uma pessoa "
                 "na frente, então pode demorar alguns minutinhos.")
    elif posicao > 1:
        texto = (f"Vou te passar pra uma pessoa da equipe 💙 Tem {posicao} pessoas "
                 "na frente, então pode demorar um pouquinho.")

    if await _enviar(telefone, texto):
        await _registrar_resposta(sessao_id, contato_id, texto)


# ---------------------------------------------------------------------- #
# Volta do atendimento humano para a IA
# ---------------------------------------------------------------------- #

# Palavras que o cliente pode mandar para retomar com a Peper.
PALAVRAS_VOLTAR = {"menu", "bot", "peper", "voltar ao menu", "atendimento automatico"}


def cliente_pediu_bot(mensagem: str) -> bool:
    return (mensagem or "").strip().lower().strip("!.?") in PALAVRAS_VOLTAR


async def devolver_para_ia(sessao_id: str, motivo: str = "atendente devolveu") -> bool:
    """
    Tira a sessão do atendimento humano e devolve para a Peper.

    Usada por três caminhos: o botão no painel, a palavra-chave do cliente
    e a devolução automática por inatividade. Fecha os tickets abertos
    junto — senão a fila do painel enche de ticket fantasma.
    """
    from app.services.fila_humana_service import FilaHumanaService
    from app.services.sessao_service import SessaoService

    try:
        await SessaoService().atualizar_sessao(sessao_id, {
            "status": "ativa",
            "atendente_id": None,
            "aguardando_atendente": False,
            "aguardando_desde": None,
            "human_response_sent": False,
            "bot_suspenso_ate": None,
            "dados_contexto.devolvido_para_ia": motivo,
        })
        await FilaHumanaService().fechar_tickets_da_sessao(sessao_id, motivo="devolvido_ao_bot")
        logger.info("Sessão %s devolvida para a IA (%s)", sessao_id, motivo)
        return True
    except Exception as e:  # noqa: BLE001
        logger.error("Falha ao devolver sessão %s para a IA: %s", sessao_id, e)
        return False


async def devolucao_automatica_elegivel(sessao: Dict[str, Any]) -> bool:
    """
    Verdadeiro quando o cliente foi para a fila, NINGUÉM respondeu, e já
    passou IA_MINUTOS_RETOMADA.

    Só vale enquanto nenhum atendente respondeu: `aguardando_desde` é
    limpo na primeira resposta humana. Se alguém já está no atendimento,
    a IA não atropela — mesmo que demore.
    """
    if not settings.ia_retomar_apos_minutos:
        return False
    if not sessao.get("aguardando_atendente"):
        return False
    desde = sessao.get("aguardando_desde")
    if not desde:
        return False
    if desde.tzinfo is not None:
        desde = desde.replace(tzinfo=None)
    limite = timedelta(minutes=settings.ia_retomar_apos_minutos)
    from app.utils.helpers import now_utc_naive
    return (now_utc_naive() - desde) >= limite
