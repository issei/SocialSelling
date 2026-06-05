"""Testes do GeminiClient: erros expõem a mensagem REAL do Google (sem rede)."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from socialselling.skills.gemini_client import GeminiClient, GeminiError, RateLimitError


def _resp(status: int, payload: dict[str, Any]) -> httpx.Response:
    return httpx.Response(status, json=payload, request=httpx.Request("POST", "http://x"))


def _patch(monkeypatch: pytest.MonkeyPatch, resp: httpx.Response) -> None:
    # gemini_client chama `httpx.post` (lookup no módulo httpx em runtime) → patch global serve.
    monkeypatch.setattr(httpx, "post", lambda *a, **k: resp)


def test_429_surfacia_mensagem_de_billing(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {
        "error": {
            "code": 429,
            "message": "Your prepayment credits are depleted. Please go to AI Studio...",
            "status": "RESOURCE_EXHAUSTED",
        }
    }
    _patch(monkeypatch, _resp(429, body))
    with pytest.raises(RateLimitError) as ei:
        GeminiClient("k").generate_json("p")
    assert "prepayment credits are depleted" in str(ei.value)


def test_429_fallback_quando_corpo_sem_mensagem(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, _resp(429, {}))
    with pytest.raises(RateLimitError) as ei:
        GeminiClient("k").generate_json("p")
    assert "429" in str(ei.value)


def test_4xx_surfacia_mensagem(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, _resp(400, {"error": {"message": "API key not valid"}}))
    with pytest.raises(GeminiError) as ei:
        GeminiClient("k").generate_json("p")
    assert "API key not valid" in str(ei.value)


def test_5xx_vira_gemini_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, _resp(503, {}))
    with pytest.raises(GeminiError):
        GeminiClient("k").generate_json("p")


def test_sucesso_parseia_json(monkeypatch: pytest.MonkeyPatch) -> None:
    ok = {"candidates": [{"content": {"parts": [{"text": '{"inferences":[]}'}]}}]}
    _patch(monkeypatch, _resp(200, ok))
    assert GeminiClient("k").generate_json("p") == {"inferences": []}


def test_rede_vira_gemini_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*a: Any, **k: Any) -> httpx.Response:
        raise httpx.ConnectError("sem rede")

    monkeypatch.setattr(httpx, "post", _boom)
    with pytest.raises(GeminiError):
        GeminiClient("k").generate_json("p")
