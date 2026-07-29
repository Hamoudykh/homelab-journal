"""Configuration, read from the environment with sensible lab defaults.

Nothing secret is hardcoded. The Telegram credentials come from the environment
only, so this file is safe to commit.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    prometheus_url: str
    alertmanager_url: str
    ollama_url: str
    ollama_model: str
    telegram_token: str | None
    telegram_chat_id: str | None
    request_timeout: int
    llm_timeout: int

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_token and self.telegram_chat_id)


def load() -> Config:
    return Config(
        prometheus_url=os.getenv("PROMETHEUS_URL", "http://192.168.1.12:9090"),
        alertmanager_url=os.getenv("ALERTMANAGER_URL", "http://192.168.1.12:9093"),
        ollama_url=os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
        telegram_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
        request_timeout=int(os.getenv("REQUEST_TIMEOUT", "10")),
        llm_timeout=int(os.getenv("LLM_TIMEOUT", "300")),
    )
