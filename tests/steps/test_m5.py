"""Step defs do M5 (pytest-bdd). Modulo puro — score/inferencia sinteticos."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from socialselling.contracts import (
    CompanyEntity,
    ICPCriteria,
    Inference,
    ProspectScore,
)
from socialselling.modules.m5_xai import run_m5

_ROOT = Path(__file__).resolve().parents[2]

scenarios("../features/m5_xai.feature")


def _icp() -> ICPCriteria:
    raw = json.loads((_ROOT / "config" / "icp_criteria.example.json").read_text("utf-8"))
    return ICPCriteria.model_validate(raw)


def _inference(technologies: list[str], *, industry: str | None) -> Inference:
    # people=[] de proposito: exercita o sinal ausente "nenhuma pessoa-chave".
    return Inference(
        company=CompanyEntity(
            company_id="c1",
            normalized_name="Acme",
            industry=industry,
            technologies=technologies,
            confidence=0.8,
        ),
        people=[],
        derived_from=["ev1", "ev2"],
        confidence=0.8,
    )


def _score(*, p: float, hard_ok: bool, confidence: float) -> ProspectScore:
    return ProspectScore(
        company_id="c1",
        fit=0.6,
        intent=0.4,
        confidence=confidence,
        p_score=p,
        hard_filter_passed=hard_ok,
    )


@pytest.fixture
def ctx() -> dict[str, Any]:
    return {}


@given("um score aprovado e uma inferencia com dados parciais")
def _given_ok(ctx: dict[str, Any]) -> None:
    ctx["score"] = _score(p=0.55, hard_ok=True, confidence=0.8)
    ctx["inference"] = _inference(["aws", "kubernetes"], industry=None)


@given("um score reprovado no hard filter")
def _given_bad(ctx: dict[str, Any]) -> None:
    ctx["score"] = _score(p=0.0, hard_ok=False, confidence=0.8)
    ctx["inference"] = _inference(["aws", "wordpress"], industry="saas")


@when("eu gero a explicacao")
def _when_run(ctx: dict[str, Any]) -> None:
    ctx["payload"] = run_m5(ctx["score"], ctx["inference"], _icp())


@when("eu gero a explicacao em modo degradado")
def _when_degraded(ctx: dict[str, Any]) -> None:
    ctx["payload"] = run_m5(ctx["score"], ctx["inference"], _icp(), degraded_mode=True)


@then("o payload tem company_id e final_p_score")
def _then_header(ctx: dict[str, Any]) -> None:
    p = ctx["payload"]
    assert p.company_id == "c1"
    assert p.final_p_score == 0.55


@then("ha ao menos um driver positivo")
def _then_positive(ctx: dict[str, Any]) -> None:
    assert len(ctx["payload"].positive_signals) >= 1


@then("os sinais ausentes sao listados")
def _then_missing(ctx: dict[str, Any]) -> None:
    assert len(ctx["payload"].missing_signals) >= 1


@then("ha um driver negativo de tecnologia proibida")
def _then_negative(ctx: dict[str, Any]) -> None:
    drivers = [d.driver for d in ctx["payload"].negative_signals]
    assert "EXCLUDED_TECH" in drivers


@then("o payload marca degraded_mode verdadeiro")
def _then_degraded(ctx: dict[str, Any]) -> None:
    assert ctx["payload"].degraded_mode is True
