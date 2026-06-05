"""Testes do run incremental na UI: a onda só avança em ciclo produtivo (ADR-006).

Regressão do bug "Gemini 429 → 0 leads, mas a onda avançou e queimou a wave cacheada".
run_pipeline é stub (sem rede); _ROOT e clientes redirecionados p/ tmp.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import socialselling.web.services as services
from socialselling.contracts import LeadCard, LeadContact, LeadLinks, ProspectScore
from socialselling.corpus.waves import WaveStore

_REAL_CONFIG = Path(__file__).resolve().parents[2] / "config"


def _card(cid: str = "c1") -> LeadCard:
    return LeadCard(
        rank=1,
        display_name="X",
        links=LeadLinks(),
        contact=LeadContact(),
        score=ProspectScore(company_id=cid, fit=0.5, intent=0.5, confidence=0.8, p_score=0.7),
    )


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
    monkeypatch.setattr(services, "GeminiClient", lambda *a, **k: object())
    return cfg_dir, cfg_dir / "runtime.toml", env, tmp_path


def _wave(root: Path) -> int:
    return WaveStore(root / "data" / "corpus" / "waves.json").current("icp_criteria.talita.json")


def test_onda_nao_avanca_em_run_vazio(
    isolated: tuple[Path, Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg_dir, runtime, env, root = isolated
    monkeypatch.setattr(services, "run_pipeline", lambda *a, **k: [])
    cards = services.run_for_icp(cfg_dir, runtime, env, "icp_criteria.talita.json")
    assert cards == []
    assert _wave(root) == 0  # run improdutivo NÃO queima a onda


def test_onda_avanca_em_run_produtivo(
    isolated: tuple[Path, Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg_dir, runtime, env, root = isolated
    monkeypatch.setattr(services, "run_pipeline", lambda *a, **k: [_card("c1")])
    cards = services.run_for_icp(cfg_dir, runtime, env, "icp_criteria.talita.json")
    assert len(cards) == 1
    assert _wave(root) == 1  # ciclo com leads avança p/ buscar novos na próxima


def test_run_vazio_nao_cria_corpus(
    isolated: tuple[Path, Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg_dir, runtime, env, root = isolated
    monkeypatch.setattr(services, "run_pipeline", lambda *a, **k: [])
    services.run_for_icp(cfg_dir, runtime, env, "icp_criteria.talita.json")
    assert not (root / "data" / "corpus" / "leads_corpus.json").exists()
