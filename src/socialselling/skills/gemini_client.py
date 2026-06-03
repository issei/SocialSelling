"""Skill de cognição: cliente HTTP do Gemini (motor cognitivo dos módulos M2/M3/M5).

Fronteira de rede da cognição. Nos testes é substituída por um fake que
devolve fixtures JSON gravadas (determinismo).
"""

from __future__ import annotations

import json
from typing import Any, Protocol

import httpx

_DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com"


class RateLimitError(Exception):
    """HTTP 429 do Gemini."""


class GeminiError(Exception):
    """Falha de rede, 5xx ou resposta não-parseável do Gemini."""


class CognitionClient(Protocol):
    """Contrato mínimo de um motor cognitivo (real ou fake)."""

    def generate_json(self, prompt: str) -> dict[str, Any]: ...


class GeminiClient:
    """Cliente real do Gemini. Pede saída JSON estruturada (temperatura 0)."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "gemini-2.5-flash-lite",
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float = 120.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def generate_json(self, prompt: str) -> dict[str, Any]:
        url = f"{self._base_url}/v1beta/models/{self._model}:generateContent?key={self._api_key}"
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
        }
        try:
            resp = httpx.post(url, json=body, timeout=self._timeout)
        except httpx.HTTPError as exc:
            raise GeminiError(str(exc)) from exc
        if resp.status_code == 429:
            raise RateLimitError("gemini rate-limited (429)")
        if resp.status_code >= 500:
            raise GeminiError(f"gemini server error ({resp.status_code})")
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed: dict[str, Any] = json.loads(text)
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise GeminiError(f"resposta Gemini inesperada: {exc}") from exc
        return parsed
