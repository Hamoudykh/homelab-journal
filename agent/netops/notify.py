"""Telegram delivery.

Credentials come from the environment. If they are absent the notifier stays
silent rather than failing, so the agent can be run locally without secrets.
"""

from __future__ import annotations

import requests


class TelegramNotifier:
    #  Telegram rejects messages longer than this.
    MAX_LENGTH = 4096

    def __init__(self, token: str | None, chat_id: str | None, timeout: int = 15) -> None:
        self.token = token
        self.chat_id = chat_id
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    def send(self, text: str) -> bool:
        """Send a message. Returns False if disabled or delivery failed."""
        if not self.enabled:
            return False

        if len(text) > self.MAX_LENGTH:
            text = text[: self.MAX_LENGTH - 20] + "\n... (truncated)"

        try:
            response = requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={"chat_id": self.chat_id, "text": text},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return True
        except requests.RequestException as exc:
            print(f"telegram delivery failed: {exc}")
            return False
