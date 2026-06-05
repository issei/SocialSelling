"""Testes da surface de falha de cognição (Gemini 429/billing) — ADR-002/006.

Garante: run vazio POR falha do Gemini vira CognitionUnavailable (motivo real),
mas com corpus prévio mostra o que há; o endpoint /api/run mapeia p/ 502 com a mensagem.
Sem rede: run_pipeline e clientes são stub/monkeypatch.
"""

from __future__ import annotations

import contextlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import socialselling.web.services as services
from socialselling.contracts import LeadCard, LeadContact, LeadLinks, ProspectScore
from socialselling.corpus.store import CorpusStore
from socialselling.skills.gemini_client import RateLimitError
from socialselling.web.app import create_app
from socialselling.web.services import CognitionUnavailable

_REAL_CONFIG = Path(__file__).resolve().parents[2] / "config"
_MSG = "Your prepayment credits are depleted. Please go to AI Studio..."


def _card(cid: str = "c1") -> LeadCard:
    return LeadCard(
        rank=1,
        display_name="X",
        links=LeadLinks(),
        contact=LeadContact(),
        score=ProspectScore(company_id=cid, fit=0.5, intent=0.5, confidence=0.8, p_score=0.7),
    )


class _BoomGemini:
    """GeminiClient falso que sempre estoura 429 (créditos esgotados)."""

    def __init__(self, *a: Any, **k: Any) -> None:
        pass

    def generate_json(self, prompt: str) -> dict[str, Any]:
        raise RateLimitError(_MSG)


def _pipeline_que_chama_gemini(*a: Any, **k: Any) -> list[LeadCard]:
    """Imita o M2: chama o Gemini (dispara a captura do wrapper) e degrada p/ []."""
    with contextlib.suppress(Exception):
        k["gemini"].generate_json("probe")
    return []


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path, Path]:
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    for name in ("icp_criteria.talita.json", "hypotheses_catalog.json", "runtime.toml"):
        shutil.copy(_REAL_CONFIG / name, cfg_dir / name)
    env = tmp_path / ".env"
    env.write_text("TAVILY_API_KEY=x\nGEMINI_API_KEY=y\n", encoding="utf-8")
    monkeypatch.setattr(services, "_ROOT", tmp_path)
    monkeypatch.setattr(services, "TavilyClient", lambda *a, **k: object())
    monkeypatch.setattr(services, "GeminiClient", _BoomGemini)
    return cfg_dir, cfg_dir / "runtime.toml", env, tmp_path


def test_run_vazio_por_cognicao_levanta_cognition_unavailable(
    isolated: tuple[Path, Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg_dir, runtime, env, _ = isolated
    monkeypatch.setattr(services, "run_pipeline", _pipeline_que_chama_gemini)
    with pytest.raises(CognitionUnavailable) as ei:
        services.run_for_icp(cfg_dir, runtime, env, "icp_criteria.talita.json")
    assert "prepayment credits are depleted" in str(ei.value)  # motivo REAL, não vazio mudo


def test_corpus_previo_mostra_leads_mesmo_com_cognicao_caida(
    isolated: tuple[Path, Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg_dir, runtime, env, root = isolated
    # Semeia o corpus com 1 lead de um ciclo anterior bem-sucedido.
    store = CorpusStore(root / "data" / "corpus" / "leads_corpus.json")
    store.upsert("c1", _card("c1").model_dump(), datetime(2026, 6, 4, 10, 0, 0))
    monkeypatch.setattr(services, "run_pipeline", _pipeline_que_chama_gemini)
    cards = services.run_for_icp(cfg_dir, runtime, env, "icp_criteria.talita.json")
    assert [c.score.company_id for c in cards] == ["c1"]  # mostra o corpus, não levanta erro


def test_run_produtivo_nao_levanta(
    isolated: tuple[Path, Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg_dir, runtime, env, _ = isolated
    monkeypatch.setattr(services, "run_pipeline", lambda *a, **k: [_card("c2")])
    cards = services.run_for_icp(cfg_dir, runtime, env, "icp_criteria.talita.json")
    assert len(cards) == 1  # cognição ok (nunca chamada) → sem erro


def test_endpoint_run_mapeia_502_com_mensagem() -> None:
    def boom(name: str) -> list[LeadCard]:
        raise CognitionUnavailable(_MSG)

    client = TestClient(create_app(pipeline_runner=boom))
    resp = client.post("/api/run", json={"icp_name": "icp_criteria.talita.json"})
    assert resp.status_code == 502
    assert "prepayment credits are depleted" in resp.json()["detail"]
