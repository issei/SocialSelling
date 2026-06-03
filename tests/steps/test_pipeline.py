"""Smoke E2E do orquestrador (pytest-bdd). Sem rede: clientes fake sobre fixtures."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from socialselling.config import load_runtime
from socialselling.contracts import HypothesisCatalog, ICPCriteria, LeadCard
from socialselling.core.cache import query_hash
from socialselling.orchestrator import run_pipeline
from socialselling.skills.gemini_client import RateLimitError as GeminiRateLimit
from socialselling.skills.tavily_client import RateLimitError as TavilyRateLimit

_ROOT = Path(__file__).resolve().parents[2]
_TAVILY = _ROOT / "tests" / "fixtures" / "tavily"
_GEMINI = _ROOT / "tests" / "fixtures" / "gemini"
_NOW = datetime(2026, 1, 1, tzinfo=UTC)

scenarios("../features/pipeline_smoke.feature")


class _FakeTavily:
    def search(
        self,
        query: str,
        max_results: int,
        search_depth: str,
        include_domains: list[str] | None = None,
    ) -> dict[str, Any]:
        path = _TAVILY / f"{query_hash(query)}.json"
        if not path.exists():
            raise TavilyRateLimit("sem fixture")
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return data


class _FakeGemini:
    def generate_json(self, prompt: str) -> dict[str, Any]:
        path = _GEMINI / f"{query_hash(prompt)}.json"
        if not path.exists():
            raise GeminiRateLimit("sem fixture")
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return data


@pytest.fixture
def ctx() -> dict[str, Any]:
    return {}


def _icp() -> ICPCriteria:
    raw = json.loads((_ROOT / "config" / "icp_criteria.talita.json").read_text("utf-8"))
    return ICPCriteria.model_validate(raw)


def _catalog() -> HypothesisCatalog:
    raw = json.loads((_ROOT / "config" / "hypotheses_catalog.json").read_text("utf-8"))
    return HypothesisCatalog.model_validate(raw)


def _run(cache_root: Path) -> list[LeadCard]:
    cfg = load_runtime(_ROOT / "config" / "runtime.toml")
    return run_pipeline(
        _icp(),
        tavily=_FakeTavily(),
        gemini=_FakeGemini(),
        hypotheses=_catalog(),
        cache_root=cache_root,
        now=_NOW,
        cfg=cfg,
    )


@given("um ICP de exemplo e fixtures gravadas")
def _given(ctx: dict[str, Any]) -> None:
    ctx["ready"] = True


@when("eu executo o orquestrador M1 ate M5 duas vezes")
def _when(ctx: dict[str, Any], tmp_path: Path) -> None:
    ctx["run1"] = _run(tmp_path / "c1")
    ctx["run2"] = _run(tmp_path / "c2")


@then("sao produzidos prospects ranqueados")
def _then_produced(ctx: dict[str, Any]) -> None:
    assert len(ctx["run1"]) > 0


@then("cada prospect tem rank crescente, score e explicacao")
def _then_shape(ctx: dict[str, Any]) -> None:
    run1: list[LeadCard] = ctx["run1"]
    for i, card in enumerate(run1, start=1):
        assert card.rank == i
        assert card.display_name
        assert 0.0 <= card.score.p_score <= 1.0
    p_scores = [c.score.p_score for c in run1]
    assert p_scores == sorted(p_scores, reverse=True)
    # ao menos um lead traz link de Instagram (publico Talita)
    assert any(c.links.instagram for c in run1)


@then("a segunda execucao e byte-identica a primeira")
def _then_identical(ctx: dict[str, Any]) -> None:
    dump1 = json.dumps([p.model_dump() for p in ctx["run1"]], sort_keys=True)
    dump2 = json.dumps([p.model_dump() for p in ctx["run2"]], sort_keys=True)
    assert dump1 == dump2
