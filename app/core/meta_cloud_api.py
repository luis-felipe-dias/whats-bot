# app/core/meta_cloud_api.py
"""
Cliente da API Oficial da Meta (WhatsApp Cloud API).

Espelha a interface de `WhatsAppAPI` (Z-API) de propósito: os mesmos nomes de
método e a mesma assinatura. Assim o resto do bot não precisa saber por qual
canal a mensagem sai — quem decide é o `canal` da sessão.

Diferenças da Z-API que estão tratadas aqui:

1. **Mídia é por ID, não por URL.** A Meta devolve um `media_id`; a URL real
   expira e exige o token no header. Por isso o download fica num endpoint
   nosso (ver webhook_meta.py) e o que circula pelo bot é a URL do nosso
   backend.

2. **Botão tem limite de 3.** A Z-API aceita vários; a Cloud API aceita no
   máximo 3 botões de resposta. Acima disso TEM que ser lista. O
   `send_interactive` troca sozinho — é o conserto definitivo do menu
   ATENDIMENTO, que na Z-API perdia o VOLTAR no `botoes[:5]`.

3. **Janela de 24 horas.** Fora dela só sai template. O erro 131047 é
   devolvido pela Meta e aqui ele é registrado de forma explícita, para não
   virar "falha genérica de envio" no log.
"""

import httpx
import logging
from typing import Optional, List, Dict, Any

from app.core.config import settings

logger = logging.getLogger(__name__)

# Erros da Meta que têm significado de negócio e merecem log próprio.
ERRO_FORA_DA_JANELA = 131047
ERRO_NUMERO_INVALIDO = 131026
ERRO_INCOMPATIVEL = 131060


class MetaCloudAPI:
    """Envio pela API oficial. Mesma interface do cliente Z-API."""

    def __init__(self):
        self.base_url = f"https://graph.facebook.com/{settings.meta_api_version}"
        self.phone_number_id = settings.meta_phone_number_id
        self.token = settings.meta_access_token
        self.timeout = httpx.Timeout(30.0, connect=10.0)

    # ------------------------------------------------------------------ #
    # Infraestrutura
    # ------------------------------------------------------------------ #

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _normalizar(telefone: str) -> str:
        """
        A Meta quer só dígitos, com DDI. O bot guarda telefone já com 55,
        mas pode vir com máscara vinda do painel.
        """
        numero = "".join(filter(str.isdigit, telefone or ""))
        if numero and not numero.startswith("55") and len(numero) >= 10:
            numero = "55" + numero
        return numero

    async def _post(self, payload: Dict[str, Any]) -> Optional[dict]:
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resposta = await client.post(url, json=payload, headers=self._headers)

            if resposta.status_code == 200:
                return resposta.json()

            # A Meta devolve o motivo em JSON. Ler o código evita o
            # "não enviou e não sei por quê" que atrasa o diagnóstico.
            try:
                erro = resposta.json().get("error", {})
            except Exception:
                erro = {"message": resposta.text}

            codigo = erro.get("code")
            detalhe = erro.get("error_data", {}).get("details") or erro.get("message")

            if codigo == ERRO_FORA_DA_JANELA:
                logger.warning(
                    "⏰ Fora da janela de 24h para %s — só template resolve. %s",
                    payload.get("to"), detalhe,
                )
            elif codigo == ERRO_NUMERO_INVALIDO:
                logger.warning("📵 Número sem WhatsApp: %s", payload.get("to"))
            elif codigo == ERRO_INCOMPATIVEL:
                logger.info("↩️ Mensagem incompatível (131060) para %s — normal na primeira troca.", payload.get("to"))
            else:
                logger.error("❌ Meta recusou (%s): %s", codigo, detalhe)

            return None

        except httpx.TimeoutException:
            logger.error("⌛ Timeout no envio para %s", payload.get("to"))
            return None
        except Exception as e:
            logger.error("❌ Falha no envio: %s", e)
            return None

    def _base(self, telefone: str, tipo: str) -> Dict[str, Any]:
        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self._normalizar(telefone),
            "type": tipo,
        }

    # ------------------------------------------------------------------ #
    # Envio
    # ------------------------------------------------------------------ #

    async def send_text(self, telefone: str, mensagem: str, **_) -> Optional[dict]:
        payload = self._base(telefone, "text")
        # preview_url ligado: o cliente vê a miniatura do link do site.
        payload["text"] = {"body": mensagem, "preview_url": True}
        return await self._post(payload)

    async def send_image(self, telefone: str, url: str, caption: str = "", **_) -> Optional[dict]:
        payload = self._base(telefone, "image")
        payload["image"] = {"link": url}
        if caption:
            payload["image"]["caption"] = caption
        return await self._post(payload)

    async def send_document(
        self, telefone: str, url: str, filename: str = "documento.pdf", caption: str = "", **_
    ) -> Optional[dict]:
        payload = self._base(telefone, "document")
        payload["document"] = {"link": url, "filename": filename}
        if caption:
            payload["document"]["caption"] = caption
        return await self._post(payload)

    async def send_audio(self, telefone: str, url: str, **_) -> Optional[dict]:
        payload = self._base(telefone, "audio")
        payload["audio"] = {"link": url}
        return await self._post(payload)

    async def send_video(self, telefone: str, url: str, caption: str = "", **_) -> Optional[dict]:
        payload = self._base(telefone, "video")
        payload["video"] = {"link": url}
        if caption:
            payload["video"]["caption"] = caption
        return await self._post(payload)

    async def send_interactive(
        self,
        telefone: str,
        mensagem: str,
        botoes: List[Any],
        titulo: str = "",
        rodape: str = "",
        **_,
    ) -> Optional[dict]:
        """
        Até 3 opções vira botão; acima disso vira lista.

        É AQUI que o menu de 6 opções deixa de perder o VOLTAR. Na Z-API o
        código cortava em `botoes[:5]` e a última opção sumia sem aviso;
        aqui nada é descartado — o formato é que muda.
        """
        opcoes = [self._opcao(b, i) for i, b in enumerate(botoes or [])]

        if not opcoes:
            return await self.send_text(telefone, mensagem)

        if len(opcoes) <= 3:
            return await self._enviar_botoes(telefone, mensagem, opcoes, rodape)
        return await self._enviar_lista(telefone, mensagem, opcoes, titulo, rodape)

    @staticmethod
    def _opcao(botao: Any, indice: int) -> Dict[str, str]:
        """Aceita string ou dict, como o código antigo fazia."""
        if isinstance(botao, dict):
            rotulo = botao.get("label") or botao.get("texto") or botao.get("title") or ""
            identificador = str(botao.get("id") or botao.get("value") or rotulo or indice)
        else:
            rotulo = str(botao)
            identificador = str(botao)
        # A Meta corta em 20 caracteres no título do botão e 24 na linha da
        # lista. Cortar aqui, de propósito, é melhor que a Meta recusar a
        # mensagem inteira por causa de um rótulo comprido.
        return {"id": identificador[:256], "title": rotulo[:20] or f"Opção {indice + 1}"}

    async def _enviar_botoes(self, telefone, mensagem, opcoes, rodape) -> Optional[dict]:
        payload = self._base(telefone, "interactive")
        interativo: Dict[str, Any] = {
            "type": "button",
            "body": {"text": mensagem[:1024]},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": o["id"], "title": o["title"]}}
                    for o in opcoes
                ]
            },
        }
        if rodape:
            interativo["footer"] = {"text": rodape[:60]}
        payload["interactive"] = interativo
        return await self._post(payload)

    async def _enviar_lista(self, telefone, mensagem, opcoes, titulo, rodape) -> Optional[dict]:
        payload = self._base(telefone, "interactive")
        interativo: Dict[str, Any] = {
            "type": "list",
            "body": {"text": mensagem[:1024]},
            "action": {
                "button": (titulo or "Ver opções")[:20],
                "sections": [
                    {
                        "title": "Opções",
                        # A lista aceita no máximo 10 linhas por seção.
                        "rows": [
                            {"id": o["id"], "title": o["title"][:24]}
                            for o in opcoes[:10]
                        ],
                    }
                ],
            },
        }
        if rodape:
            interativo["footer"] = {"text": rodape[:60]}
        payload["interactive"] = interativo

        if len(opcoes) > 10:
            logger.warning(
                "⚠️ Menu com %d opções; a lista da Meta só aceita 10. Revisar o fluxo.",
                len(opcoes),
            )
        return await self._post(payload)

    async def send_template(
        self, telefone: str, nome_template: str, idioma: str = "pt_BR",
        componentes: Optional[List[dict]] = None, **_
    ) -> Optional[dict]:
        """
        Único jeito de iniciar conversa ou responder fora da janela de 24h.
        O template precisa estar APROVADO no painel da Meta antes.
        """
        payload = self._base(telefone, "template")
        payload["template"] = {
            "name": nome_template,
            "language": {"code": idioma},
        }
        if componentes:
            payload["template"]["components"] = componentes
        return await self._post(payload)

    async def marcar_como_lida(self, message_id: str) -> Optional[dict]:
        """O cliente vê o visto azul — o bot parece atendimento, não robô."""
        return await self._post({
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        })

    # ------------------------------------------------------------------ #
    # Mídia
    # ------------------------------------------------------------------ #

    async def obter_url_midia(self, media_id: str) -> Optional[str]:
        """
        Resolve o media_id para a URL temporária da Meta.
        A URL expira em minutos e exige o token no header — por isso quem
        baixa é o nosso backend, nunca o navegador do atendente direto.
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r = await client.get(f"{self.base_url}/{media_id}", headers=self._headers)
            if r.status_code == 200:
                return r.json().get("url")
            logger.error("❌ Não resolveu media_id %s: %s", media_id, r.text[:200])
        except Exception as e:
            logger.error("❌ Erro ao resolver mídia %s: %s", media_id, e)
        return None

    async def baixar_midia(self, media_url: str) -> Optional[bytes]:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
                r = await client.get(media_url, headers={"Authorization": f"Bearer {self.token}"})
            if r.status_code == 200:
                return r.content
            logger.error("❌ Download de mídia falhou: %s", r.status_code)
        except Exception as e:
            logger.error("❌ Erro no download de mídia: %s", e)
        return None


meta_api = MetaCloudAPI()
