"""Smoke E2E da UI (WU-U6): assistente → salvar → executar. Tudo mockado, sem rede."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from socialselling.contracts import LeadCard, LeadContact, LeadLinks, ProspectScore
from socialselling.web.app import create_app

_ROOT = Path(__file__).resolve().parents[2]
_REAL_CONFIG = _ROOT / "config"


class _FakeGemini:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def generate_json(self, prompt: str) -> dict[str, Any]:
        return self._payload


def _lead() -> LeadCard:
    return LeadCard(
        rank=1,
        display_name="Maria Fundadora",
        company="Acme Consultoria",
        role="Fundadora",
        sector="consultoria",
        location="São Paulo, SP",
        links=LeadLinks(instagram="https://www.instagram.com/maria"),
        contact=LeadContact(),
        score=ProspectScore(company_id="x", fit=1.0, intent=0.5, confidence=0.8, p_score=0.62),
        why_now=["Sinais de timing detectados: expansao."],
        sources=["https://www.instagram.com/maria"],
    )


def test_fluxo_assistente_salvar_executar(tmp_path: Path) -> None:
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    for name in ("icp_criteria.talita.json", "hypotheses_catalog.json", "runtime.toml"):
        shutil.copy(_REAL_CONFIG / name, cfg_dir / name)
    draft = json.loads((_REAL_CONFIG / "icp_criteria.talita.json").read_text("utf-8"))

    app = create_app(
        config_dir=cfg_dir,
        runtime_path=cfg_dir / "runtime.toml",
        cognition_client=_FakeGemini(draft),
        pipeline_runner=lambda name: [_lead()],
    )
    client = TestClient(app)

    # 1) Assistente gera rascunho de ICP
    assisted = client.post("/api/assist/icp", json={"description": "consultoria p/ fundadoras"})
    assert assisted.status_code == 200
    icp = assisted.json()
    assert icp["icp_id"]

    # 2) Salvar o ICP gerado
    saved = client.post(
        "/api/config/icp", json={"name": "icp_criteria.e2e.json", "icp": icp}
    )
    assert saved.status_code == 200
    assert (cfg_dir / "icp_criteria.e2e.json").exists()

    # 3) Executar com o ICP salvo e ver os Lead Cards
    run = client.post("/api/run", json={"icp_name": "icp_criteria.e2e.json"})
    assert run.status_code == 200
    body = run.json()
    assert body["count"] == 1
    lead = body["leads"][0]
    assert lead["display_name"] == "Maria Fundadora"
    assert lead["links"]["instagram"].endswith("/maria")
