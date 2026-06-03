"""Testes da API de execução (WU-U4). Pipeline mockado; sem rede."""

from __future__ import annotations

from fastapi.testclient import TestClient

from socialselling.contracts import (
    LeadCard,
    LeadContact,
    LeadLinks,
    ProspectScore,
)
from socialselling.skills.gemini_client import GeminiError
from socialselling.web.app import create_app


def _card() -> LeadCard:
    return LeadCard(
        rank=1,
        display_name="Maria",
        company="Acme",
        role="Fundadora",
        sector="consultoria",
        location="SP",
        links=LeadLinks(instagram="https://www.instagram.com/maria"),
        contact=LeadContact(),
        score=ProspectScore(company_id="x", fit=0.8, intent=0.5, confidence=0.8, p_score=0.6),
        why_now=["timing: expansao"],
        sources=["https://www.instagram.com/maria"],
    )


def test_run_retorna_leads() -> None:
    client = TestClient(create_app(pipeline_runner=lambda name: [_card()]))
    resp = client.post("/api/run", json={"icp_name": "icp_criteria.talita.json"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "done"
    assert body["count"] == 1
    assert body["leads"][0]["display_name"] == "Maria"
    assert body["leads"][0]["links"]["instagram"].endswith("/maria")
    assert body["run_id"]


def test_run_status_recupera() -> None:
    client = TestClient(create_app(pipeline_runner=lambda name: [_card()]))
    run_id = client.post("/api/run", json={"icp_name": "icp_criteria.talita.json"}).json()["run_id"]
    resp = client.get(f"/api/run/{run_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"


def test_run_status_inexistente_404() -> None:
    client = TestClient(create_app(pipeline_runner=lambda name: [_card()]))
    assert client.get("/api/run/run-999").status_code == 404


def test_run_falha_externa_502() -> None:
    def _boom(name: str) -> list[LeadCard]:
        raise GeminiError("estourou")

    client = TestClient(create_app(pipeline_runner=_boom))
    resp = client.post("/api/run", json={"icp_name": "icp_criteria.talita.json"})
    assert resp.status_code == 502
