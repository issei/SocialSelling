"""Step defs do M2 (pytest-bdd). Rede mockada por FakeGeminiClient (fixture gravada)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from socialselling.contracts import Inference, ObservedEvidence
from socialselling.core.cache import JsonCache, query_hash
from socialselling.modules.m1_busca import run_m1
from socialselling.modules.m2_extracao import run_m2
from socialselling.skills.gemini_client import RateLimitError

_ROOT = Path(__file__).resolve().parents[2]
_TAVILY = _ROOT / "tests" / "fixtures" / "tavily"
_GEMINI = _ROOT / "tests" / "fixtures" / "gemini"
_NOW = datetime(2026, 1, 1, tzinfo=UTC)

scenarios("../features/m2_extracao.feature")


class _FixtureTavily:
    def search(self, query: str, max_results: int, search_depth: str) -> dict[str, Any]:
        path = _TAVILY / f"{query_hash(query)}.json"
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return data


class FakeGeminiClient:
    def __init__(self, fixtures_dir: Path, *, fail: str | None = None) -> None:
        self._dir = fixtures_dir
        self._fail = fail

    def generate_json(self, prompt: str) -> dict[str, Any]:
        if self._fail == "429":
            raise RateLimitError("fake 429")
        path = self._dir / f"{query_hash(prompt)}.json"
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return data


def _build_evidences() -> list[ObservedEvidence]:
    raw = json.loads((_ROOT / "config" / "icp_criteria.example.json").read_text("utf-8"))
    from socialselling.contracts import ICPCriteria

    icp = ICPCriteria.model_validate(raw)
    return run_m1(
        icp,
        client=_FixtureTavily(),
        cache=JsonCache(_ROOT / "data" / "cache" / "_never_used_in_test"),
        now=_NOW,
        max_queries=3,
        max_results=10,
        search_depth="basic",
        cache_ttl_hours=24,
    )


@pytest.fixture
def ctx() -> dict[str, Any]:
    return {}


def _run_m2(
    client: FakeGeminiClient, cache_root: Path, evidences: list[ObservedEvidence]
) -> list[Inference]:
    return run_m2(
        evidences, client=client, cache=JsonCache(cache_root), now=_NOW, cache_ttl_hours=24
    )


@given("evidencias observadas do M1")
def _given_evidences(ctx: dict[str, Any]) -> None:
    ctx["evidences"] = _build_evidences()


@given("fixtures Gemini gravadas")
def _given_gemini(ctx: dict[str, Any]) -> None:
    ctx["client"] = FakeGeminiClient(_GEMINI)


@given("o cliente Gemini retorna 429")
def _given_429(ctx: dict[str, Any]) -> None:
    ctx["client"] = FakeGeminiClient(_GEMINI, fail="429")


@when("eu executo o M2 duas vezes com relogio fixo")
def _when_twice(ctx: dict[str, Any], tmp_path: Path) -> None:
    root = tmp_path / "cache"
    ctx["run1"] = _run_m2(ctx["client"], root, ctx["evidences"])
    ctx["run2"] = _run_m2(ctx["client"], root, ctx["evidences"])


@when("eu executo o M2 uma vez com relogio fixo")
def _when_once(ctx: dict[str, Any], tmp_path: Path) -> None:
    ctx["run1"] = _run_m2(ctx["client"], tmp_path / "cache", ctx["evidences"])


@then("sao geradas inferencias")
def _then_has(ctx: dict[str, Any]) -> None:
    infs: list[Inference] = ctx["run1"]
    assert len(infs) > 0
    assert all(isinstance(i, Inference) for i in infs)


@then("toda inferencia tem confianca e derived_from rastreavel")
def _then_conf(ctx: dict[str, Any]) -> None:
    infs: list[Inference] = ctx["run1"]
    evidence_ids = {ev.evidence_id for ev in ctx["evidences"]}
    for inf in infs:
        assert 0.0 <= inf.confidence <= 1.0
        assert 0.0 <= inf.company.confidence <= 1.0
        assert all(d in evidence_ids for d in inf.derived_from)
    assert any(len(inf.derived_from) > 0 for inf in infs)


@then("as camadas observed e inference estao isoladas")
def _then_isolated(ctx: dict[str, Any]) -> None:
    assert all(isinstance(ev, ObservedEvidence) for ev in ctx["evidences"])
    assert all(isinstance(inf, Inference) for inf in ctx["run1"])
    assert not any(isinstance(inf, ObservedEvidence) for inf in ctx["run1"])


@then("a segunda execucao e byte-identica a primeira")
def _then_identical(ctx: dict[str, Any]) -> None:
    dump1 = [i.model_dump() for i in ctx["run1"]]
    dump2 = [i.model_dump() for i in ctx["run2"]]
    assert json.dumps(dump1, sort_keys=True) == json.dumps(dump2, sort_keys=True)


@then("nenhuma inferencia e produzida")
def _then_empty(ctx: dict[str, Any]) -> None:
    assert ctx["run1"] == []
