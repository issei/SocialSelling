"""Testes da API de parâmetros (WU-U2). FS isolado em tmp_path; sem rede."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from socialselling.web.app import create_app

_ROOT = Path(__file__).resolve().parents[2]
_REAL_CONFIG = _ROOT / "config"


@pytest.fixture
def env(tmp_path: Path) -> tuple[TestClient, Path]:
    """App apontado para uma cópia isolada da config (não toca o repo real)."""
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    for name in (
        "icp_criteria.talita.json",
        "icp_criteria.example.json",
        "hypotheses_catalog.json",
        "runtime.toml",
    ):
        shutil.copy(_REAL_CONFIG / name, cfg_dir / name)
    runtime = cfg_dir / "runtime.toml"
    client = TestClient(create_app(config_dir=cfg_dir, runtime_path=runtime))
    return client, cfg_dir


def _valid_icp() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        (_REAL_CONFIG / "icp_criteria.talita.json").read_text("utf-8")
    )
    return data


def test_get_icp_ok(env: tuple[TestClient, Path]) -> None:
    client, _ = env
    resp = client.get("/api/config/icp", params={"name": "icp_criteria.talita.json"})
    assert resp.status_code == 200
    assert resp.json()["icp_id"]


def test_get_icp_nome_invalido_400(env: tuple[TestClient, Path]) -> None:
    client, _ = env
    resp = client.get("/api/config/icp", params={"name": "../secrets.json"})
    assert resp.status_code == 400


def test_get_icp_inexistente_404(env: tuple[TestClient, Path]) -> None:
    client, _ = env
    resp = client.get("/api/config/icp", params={"name": "icp_criteria.nope.json"})
    assert resp.status_code == 404


def test_post_icp_valido_salva(env: tuple[TestClient, Path]) -> None:
    client, cfg_dir = env
    icp = _valid_icp()
    icp["icp_id"] = "icp_editado"
    resp = client.post("/api/config/icp", json={"name": "icp_criteria.novo.json", "icp": icp})
    assert resp.status_code == 200
    saved = json.loads((cfg_dir / "icp_criteria.novo.json").read_text("utf-8"))
    assert saved["icp_id"] == "icp_editado"


def test_post_icp_invalido_422(env: tuple[TestClient, Path]) -> None:
    client, _ = env
    bad = _valid_icp()
    del bad["firmographics"]  # campo obrigatório ausente
    resp = client.post("/api/config/icp", json={"name": "icp_criteria.x.json", "icp": bad})
    assert resp.status_code == 422


def test_post_hypotheses_valido(env: tuple[TestClient, Path]) -> None:
    client, cfg_dir = env
    catalog = json.loads((cfg_dir / "hypotheses_catalog.json").read_text("utf-8"))
    resp = client.post("/api/config/hypotheses", json=catalog)
    assert resp.status_code == 200
    assert resp.json()["count"] == len(catalog["hypotheses"])


def test_post_scoring_atualiza_runtime(env: tuple[TestClient, Path]) -> None:
    client, cfg_dir = env
    resp = client.post(
        "/api/config/scoring",
        json={
            "w_fit": 0.7,
            "w_intent": 0.3,
            "confidence_exponent": 0.5,
            "w_fit_tech": 0.6,
            "w_fit_industry": 0.4,
        },
    )
    assert resp.status_code == 200
    text = (cfg_dir / "runtime.toml").read_text("utf-8")
    assert "w_fit = 0.7" in text
    assert "w_intent = 0.3" in text
