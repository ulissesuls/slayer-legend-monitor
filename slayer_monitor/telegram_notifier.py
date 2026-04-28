"""Cliente mínimo do Telegram Bot API para envio de alertas.

Implementa um cooldown por chave (`dedupe_key`) para evitar spam quando
a mesma falha persiste por vários ciclos consecutivos.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import requests


log = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(
        self,
        token: str,
        chat_id: str,
        timeout: int = 15,
        cooldown_seconds: int = 0,
    ) -> None:
        self._url = f"https://api.telegram.org/bot{token}/sendMessage"
        self._chat_id = chat_id
        self._timeout = timeout
        self._cooldown = cooldown_seconds
        self._last_sent: dict[str, float] = {}

    def send(self, text: str, *, dedupe_key: Optional[str] = None) -> bool:
        if dedupe_key and self._cooldown > 0:
            now = time.monotonic()
            last = self._last_sent.get(dedupe_key, 0.0)
            if now - last < self._cooldown:
                log.debug("Telegram alerta '%s' em cooldown — não enviado.", dedupe_key)
                return False
            self._last_sent[dedupe_key] = now

        try:
            response = requests.post(
                self._url,
                data={
                    "chat_id": self._chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": "true",
                },
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            log.error("Falha ao enviar Telegram: %s", exc)
            return False

        if response.status_code != 200:
            log.error(
                "Telegram retornou %s: %s", response.status_code, response.text[:300]
            )
            return False
        return True
