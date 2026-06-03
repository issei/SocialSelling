"""Step defs do M1 (pytest-bdd). Rede mockada por FakeTavilyClient (fixtures gravadas)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from socialselling.config import load_runtime
from socialselling.contracts import ICPCriteria, ObservedEvidence
from socialselling.core.cache import JsonCache, query_hash
from socialselling.modules.m1_busca import is_degraded, run_m1
from socialselling.skills.tavily_client import RateLimitError

_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = _ROOT / "tests" / "fixtures" / "tavily"
_NOW = datetime(2026, 1, 1, tzinfo=UTC)

scenarios("../features/m1_busca.feature")


class FakeTavilyClient:
    """Cliente de busca falso: devolve fixtures gravadas ou simula falha."""

    def __init__(self, fixtures_dir: Path, *, fail: str | None = None) -> None:
        self._dir = fixtures_dir
        self._fail = fail

    def search(
        self,
        query: str,
        max_results: int,
        search_depth: str,
        include_domains: list[str] | None = None,
    ) -> dict[str, Any]:
        if self._fail == "429":
            raise RateLimitError("fake 429")
        path = self._dir / f"{query_hash(query)}.json"
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return data


@pytest.fixture
def ctx() -> dict[str, Any]:
    return {}


def _load_icp() -> ICPCriteria:
    raw = json.loads((_ROOT / "config" / "icp_criteria.talita.json").read_text("utf-8"))
    return ICPCriteria.model_validate(raw)


def _run(client: FakeTavilyClient, cache_root: Path) -> list[ObservedEvidence]:
    cfg = load_runtime(_ROOT / "config" / "runtime.toml")
    return run_m1(
        _load_icp(),
        client=client,
        cache=JsonCache(cache_root),
        now=_NOW,
        max_queries=cfg.tavily.max_queries,
        max_results=cfg.tavily.max_results,
        search_depth=cfg.tavily.search_depth,
        cache_ttl_hours=24,
        persona_term=cfg.tavily.persona_term,
        include_domains=cfg.tavily.include_domains,
    )


@given("um ICP de exemplo")
def _given_icp(ctx: dict[str, Any]) -> None:
    ctx["icp"] = _load_icp()


@given("fixtures Tavily gravadas")
def _given_fixtures(ctx: dict[str, Any]) -> None:
    ctx["client"] = FakeTavilyClient(_FIXTURES)


@given("o cliente Tavily retorna 429")
def _given_429(ctx: dict[str, Any]) -> None:
    ctx["client"] = FakeTavilyClient(_FIXTURES, fail="429")


@when("eu executo o M1 duas vezes com relogio fixo")
def _when_run_twice(ctx: dict[str, Any], tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    ctx["run1"] = _run(ctx["client"], cache_root)
    ctx["run2"] = _run(ctx["client"], cache_root)


@when("eu executo o M1 uma vez com relogio fixo")
def _when_run_once(ctx: dict[str, Any], tmp_path: Path) -> None:
    ctx["run1"] = _run(ctx["client"], tmp_path / "cache")


@then("sao geradas evidencias observadas")
def _then_has_evidences(ctx: dict[str, Any]) -> None:
    run1: list[ObservedEvidence] = ctx["run1"]
    assert len(run1) > 0
    assert all(isinstance(ev, ObservedEvidence) for ev in run1)


@then("a segunda execucao e byte-identica a primeira")
def _then_byte_identical(ctx: dict[str, Any]) -> None:
    dump1 = [ev.model_dump() for ev in ctx["run1"]]
    dump2 = [ev.model_dump() for ev in ctx["run2"]]
    assert dump1 == dump2
    assert json.dumps(dump1, sort_keys=True) == json.dumps(dump2, sort_keys=True)


@then("ha ao menos uma evidencia com missing_evidence verdadeiro")
def _then_missing(ctx: dict[str, Any]) -> None:
    run1: list[ObservedEvidence] = ctx["run1"]
    assert any(ev.missing_evidence for ev in run1)


@then("o resultado esta em modo degradado")
def _then_degraded(ctx: dict[str, Any]) -> None:
    assert is_degraded(ctx["run1"]) is True
