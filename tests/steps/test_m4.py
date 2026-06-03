"""Step defs do M4 (pytest-bdd). Modulo puro — scores sinteticos."""

from __future__ import annotations

import json
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from socialselling.contracts import ProspectScore
from socialselling.modules.m4_ranking import run_m4

scenarios("../features/m4_ranking.feature")


def _score(cid: str, p: float) -> ProspectScore:
    return ProspectScore(
        company_id=cid, fit=0.5, intent=0.5, confidence=0.8, p_score=p, hard_filter_passed=True
    )


@pytest.fixture
def ctx() -> dict[str, Any]:
    return {}


@given("scores de prospect com empate")
def _given_scores(ctx: dict[str, Any]) -> None:
    # 'b' e 'a' empatam em 0.5; 'c' tem 0.9; 'd' tem 0.1
    ctx["scores"] = [_score("b", 0.5), _score("c", 0.9), _score("a", 0.5), _score("d", 0.1)]


@when("eu ordeno duas vezes")
def _when_twice(ctx: dict[str, Any]) -> None:
    ctx["run1"] = run_m4(ctx["scores"])
    ctx["run2"] = run_m4(ctx["scores"])


@then("a ordem e por p_score decrescente")
def _then_desc(ctx: dict[str, Any]) -> None:
    ps = [s.p_score for s in ctx["run1"]]
    assert ps == sorted(ps, reverse=True)


@then("empates sao resolvidos por company_id ascendente")
def _then_tiebreak(ctx: dict[str, Any]) -> None:
    order = [s.company_id for s in ctx["run1"]]
    assert order == ["c", "a", "b", "d"]


@then("as duas execucoes sao byte-identicas")
def _then_identical(ctx: dict[str, Any]) -> None:
    dump1 = json.dumps([s.model_dump() for s in ctx["run1"]], sort_keys=True)
    dump2 = json.dumps([s.model_dump() for s in ctx["run2"]], sort_keys=True)
    assert dump1 == dump2
