"""Testes do assistente Gemini (WU-U3). Gemini mockado; sem rede."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from socialselling.skills.gemini_client import GeminiError
from socialselling.web.app import create_app

_ROOT = Path(__file__).resolve().parents[2]


class _FakeGemini:
    def __init__(
        self, *, payload: dict[str, Any] | None = None, exc: Exception | None = None
    ) -> None:
        self._payload = payload
        self._exc = exc

    def generate_json(self, prompt: str) -> dict[str, Any]:
        if self._exc is not None:
            raise self._exc
        assert self._payload is not None
        return self._payload


def _valid_icp() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        (_ROOT / "config" / "icp_criteria.talita.json").read_text("utf-8")
    )
    return data


def test_assist_icp_valido_200() -> None:
    client = TestClient(create_app(cognition_client=_FakeGemini(payload=_valid_icp())))
    resp = client.post("/api/assist/icp", json={"description": "consultoria para fundadoras"})
    assert resp.status_code == 200
    assert resp.json()["icp_id"]
    assert "firmographics" in resp.json()


def test_assist_icp_lixo_422() -> None:
    client = TestClient(create_app(cognition_client=_FakeGemini(payload={"foo": "bar"})))
    resp = client.post("/api/assist/icp", json={"description": "algo"})
    assert resp.status_code == 422


def test_assist_icp_falha_gemini_502() -> None:
    client = TestClient(create_app(cognition_client=_FakeGemini(exc=GeminiError("boom"))))
    resp = client.post("/api/assist/icp", json={"description": "algo"})
    assert resp.status_code == 502


def test_assist_icp_descricao_vazia_422() -> None:
    client = TestClient(create_app(cognition_client=_FakeGemini(payload=_valid_icp())))
    resp = client.post("/api/assist/icp", json={"description": ""})
    assert resp.status_code == 422
