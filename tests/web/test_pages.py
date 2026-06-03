"""Testes da fundação web (WU-U1). FastAPI TestClient, sem servidor nem rede."""

from __future__ import annotations

from fastapi.testclient import TestClient

from socialselling.web.app import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_index_responde_200_com_secoes() -> None:
    resp = _client().get("/")
    assert resp.status_code == 200
    body = resp.text
    assert 'id="parametros"' in body
    assert 'id="assistente"' in body
    assert 'id="resultados"' in body


def test_api_config_retorna_snapshot() -> None:
    resp = _client().get("/api/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "icp_files" in data
    assert any("talita" in name for name in data["icp_files"])
    assert "scoring" in data
    assert "w_fit" in data["scoring"]
    assert isinstance(data["hypotheses"], list)
