"""Client for a local Ollama instance.

Kept deliberately small: one method that takes a system prompt and a user prompt
and returns the text plus timing, so the agent can report how long the GPU took.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests


class LLMError(RuntimeError):
    """Raised when the model endpoint is unreachable or returns an error."""


@dataclass
class Completion:
    text: str
    tokens: int
    seconds: float

    @property
    def tokens_per_second(self) -> float:
        return self.tokens / self.seconds if self.seconds > 0 else 0.0


class OllamaClient:
    def __init__(self, base_url: str, model: str, timeout: int = 300) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def available(self) -> bool:
        try:
            requests.get(f"{self.base_url}/api/version", timeout=5).raise_for_status()
            return True
        except requests.RequestException:
            return False

    def complete(self, system: str, prompt: str, temperature: float = 0.2) -> Completion:
        body = {
            "model": self.model,
            "system": system,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        try:
            response = requests.post(
                f"{self.base_url}/api/generate", json=body, timeout=self.timeout
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise LLMError(f"{self.base_url} unreachable: {exc}") from exc

        payload = response.json()
        # Ollama reports durations in nanoseconds.
        eval_ns = payload.get("eval_duration", 0) or 0
        return Completion(
            text=payload.get("response", "").strip(),
            tokens=payload.get("eval_count", 0) or 0,
            seconds=eval_ns / 1e9,
        )
