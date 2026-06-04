"""Testes da API de feedback (ADR-007). FS e runtime isolados em tmp; sem rede."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from socialselling.learning.feedback_store import FeedbackStore
from socialselling.web.app import create_app

_ROOT = Path(__file__).resolve().parents[2]
_REAL_CONFIG = _ROOT / "config"


@pytest.fixture
def env(tmp_path: Path) -> tuple[TestClient, Path, FeedbackStore]:
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    for name in ("icp_criteria.talita.json", "hypotheses_catalog.json", "runtime.toml"):
        shutil.copy(_REAL_CONFIG / name, cfg_dir / name)
    runtime = cfg_dir / "runtime.toml"
    store = FeedbackStore(tmp_path / "feedback.json")
    client = TestClient(
        create_app(config_dir=cfg_dir, runtime_path=runtime, feedback_store=store)
    )
    return client, runtime, store


def _payload(company_id: str, label: str, fit: float, intent: float) -> dict[str, Any]:
    return {
        "company_id": company_id,
        "label": label,
        "features": {"fit": fit, "intent": intent, "confidence": 0.9, "persona_fit": 1.0},
    }


def test_voto_abaixo_do_gate_nao_aplica(env: tuple[TestClient, Path, FeedbackStore]) -> None:
    client, runtime, store = env
    resp = client.post("/api/feedback", json=_payload("co-1", "like", 0.9, 0.1))
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["learned"]["applied"] is False  # 1 like, 0 dislike
    assert store.get("co-1") is not None  # mas o voto foi registrado
    assert "w_fit = 0.6" in runtime.read_text("utf-8")  # pesos intactos


def test_amostra_suficiente_reajusta_pesos(env: tuple[TestClient, Path, FeedbackStore]) -> None:
    client, runtime, _ = env
    for i in range(3):
        client.post("/api/feedback", json=_payload(f"like-{i}", "like", 0.9, 0.1))
    last = None
    for i in range(3):
        last = client.post("/api/feedback", json=_payload(f"dis-{i}", "dislike", 0.1, 0.9))
    assert last is not None
    body = last.json()
    assert body["learned"]["applied"] is True
    assert body["learned"]["w_fit"] > 0.6  # priorização migrou para fit
    assert body["scoring"]["w_fit"] == body["learned"]["w_fit"]
    # persistido no runtime.toml (não mais o default 0.6)
    assert "w_fit = 0.6\n" not in runtime.read_text("utf-8")


def test_get_labels(env: tuple[TestClient, Path, FeedbackStore]) -> None:
    client, _, _ = env
    client.post("/api/feedback", json=_payload("co-1", "like", 0.9, 0.1))
    client.post("/api/feedback", json=_payload("co-2", "dislike", 0.2, 0.8))
    labels = client.get("/api/feedback").json()
    assert labels == {"co-1": "like", "co-2": "dislike"}


def test_none_desmarca(env: tuple[TestClient, Path, FeedbackStore]) -> None:
    client, _, store = env
    client.post("/api/feedback", json=_payload("co-1", "like", 0.9, 0.1))
    assert store.get("co-1") is not None
    client.post("/api/feedback", json=_payload("co-1", "none", 0.9, 0.1))
    assert store.get("co-1") is None


def test_request_invalido_422(env: tuple[TestClient, Path, FeedbackStore]) -> None:
    client, _, _ = env
    resp = client.post("/api/feedback", json={"company_id": "x", "label": "talvez"})
    assert resp.status_code == 422
