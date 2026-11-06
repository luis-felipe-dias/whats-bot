# app/core/openai_client.py
"""
Cliente da OpenAI para a Peper IA (MVP).

Por que httpx e não o SDK oficial: o bot já usa httpx em todo lugar e já
roda em asyncio. Puxar o SDK só para isso adiciona dependência, versão
para travar e um cliente HTTP paralelo. Duas chamadas resolvem.

O que existe aqui:
- conversar()  -> Chat Completions com tool calling (função -> JSON)
- transcrever() -> Whisper, para o cliente que manda áudio

NUNCA logar a chave. NUNCA logar o corpo completo da resposta (vem junto
o texto do cliente).
"""

import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

API_BASE = "https://api.openai.com/v1"


class OpenAIErro(Exception):
    pass


class OpenAIClient:
    def __init__(self) -> None:
        self.chave = settings.openai_api_key
        self.modelo = settings.openai_model
        self.modelo_audio = settings.openai_model_audio
        # 25s: acima disso o cliente no WhatsApp já desistiu de esperar.
        self.timeout = httpx.Timeout(25.0, connect=10.0)

    @property
    def configurado(self) -> bool:
        return bool(self.chave)

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.chave}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------ #
    # Conversa
    # ------------------------------------------------------------------ #

    async def conversar(
        self,
        mensagens: List[Dict[str, Any]],
        ferramentas: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Devolve a mensagem crua do modelo (dict com 'content' e/ou
        'tool_calls'). Quem decide o que fazer com tool_calls é o handler.

        Retorna {} em qualquer falha — o handler trata como "não consegui
        responder" e passa para humano, em vez de deixar o cliente no vácuo.
        """
        if not self.configurado:
            logger.error("OPENAI_API_KEY não definida — faixa IA não responde.")
            return {}

        corpo: Dict[str, Any] = {
            "model": self.modelo,
            "messages": mensagens,
            "temperature": settings.openai_temperature,
            # Teto por resposta. Atendimento de papelaria é curto; sem teto
            # um prompt ruim vira uma resposta de 800 tokens no WhatsApp.
            "max_tokens": settings.openai_max_tokens,
        }
        if ferramentas:
            corpo["tools"] = ferramentas
            corpo["tool_choice"] = "auto"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r = await client.post(
                    f"{API_BASE}/chat/completions", json=corpo, headers=self._headers
                )
            if r.status_code != 200:
                # A OpenAI devolve o motivo em JSON; o código importa
                # (429 = cota/limite, 401 = chave errada).
                try:
                    erro = r.json().get("error", {}).get("message")
                except Exception:
                    erro = r.text[:200]
                logger.error("OpenAI recusou (%s): %s", r.status_code, erro)
                return {}

            dados = r.json()
            uso = dados.get("usage", {})
            logger.info(
                "IA respondeu — entrada=%s saida=%s tokens",
                uso.get("prompt_tokens"), uso.get("completion_tokens"),
            )
            return (dados.get("choices") or [{}])[0].get("message", {}) or {}

        except httpx.TimeoutException:
            logger.error("Timeout na OpenAI.")
            return {}
        except Exception as e:  # noqa: BLE001
            logger.error("Falha na OpenAI: %s", e)
            return {}

    # ------------------------------------------------------------------ #
    # Áudio
    # ------------------------------------------------------------------ #

    async def transcrever(self, audio: bytes, nome: str = "audio.ogg") -> str:
        """
        Áudio é o hábito dominante do cliente de papelaria no WhatsApp.
        O bot antigo respondia "OPÇÃO INVÁLIDA" para áudio — aqui ele ouve.

        Devolve "" se não conseguir; o handler então pede para o cliente
        escrever, em vez de ignorar a mensagem.
        """
        if not self.configurado:
            return ""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
                r = await client.post(
                    f"{API_BASE}/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self.chave}"},
                    files={"file": (nome, audio, "application/octet-stream")},
                    data={"model": self.modelo_audio, "language": "pt"},
                )
            if r.status_code == 200:
                texto = (r.json().get("text") or "").strip()
                logger.info("Áudio transcrito (%d caracteres).", len(texto))
                return texto
            logger.error("Transcrição falhou (%s): %s", r.status_code, r.text[:200])
        except Exception as e:  # noqa: BLE001
            logger.error("Erro na transcrição: %s", e)
        return ""


openai_client = OpenAIClient()
