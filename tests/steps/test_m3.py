"""Step defs do M3 (pytest-bdd). Modulo puro — inferencias sinteticas, sem rede."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from socialselling.contracts import (
    CompanyEntity,
    HypothesisCatalog,
    ICPCriteria,
    Inference,
    ProspectScore,
)
from socialselling.modules.m3_score import run_m3

_ROOT = Path(__file__).resolve().parents[2]

scenarios("../features/m3_score.feature")

_PARAMS: dict[str, Any] = {
    "w_fit": 0.60,
    "w_intent": 0.40,
    "confidence_exponent": 0.5,
    "w_fit_tech": 0.60,
    "w_fit_industry": 0.40,
}


def _icp() -> ICPCriteria:
    raw = json.loads((_ROOT / "config" / "icp_criteria.example.json").read_text("utf-8"))
    return ICPCriteria.model_validate(raw)


def _catalog() -> HypothesisCatalog:
    raw = json.loads((_ROOT / "config" / "hypotheses_catalog.json").read_text("utf-8"))
    return HypothesisCatalog.model_validate(raw)


def _inference(
    *,
    cid: str,
    technologies: list[str],
    industry: str | None,
    confidence: float,
    intent_signals: list[str] | None = None,
    disqualifiers: list[str] | None = None,
) -> Inference:
    return Inference(
        company=CompanyEntity(
            company_id=cid,
            normalized_name=cid,
            industry=industry,
            technologies=technologies,
            confidence=confidence,
        ),
        people=[],
        derived_from=["ev1"],
        confidence=confidence,
        intent_signals=intent_signals or [],
        disqualifiers=disqualifiers or [],
    )


@pytest.fixture
def ctx() -> dict[str, Any]:
    return {}


def _run(inferences: list[Inference]) -> list[ProspectScore]:
    return run_m3(inferences, _icp(), _catalog(), **_PARAMS)


@given("um ICP e inferencias sinteticas")
def _given_synthetic(ctx: dict[str, Any]) -> None:
    ctx["inferences"] = [
        _inference(
            cid="c1",
            technologies=["aws", "kubernetes"],
            industry="saas",
            confidence=0.9,
            intent_signals=["intencao_ia"],
        ),
        _inference(cid="c2", technologies=["aws"], industry="varejo", confidence=0.5),
    ]


@given("uma inferencia com tecnologia proibida pelo ICP")
def _given_excluded(ctx: dict[str, Any]) -> None:
    ctx["inferences"] = [
        _inference(cid="bad", technologies=["aws", "wordpress"], industry="saas", confidence=0.9)
    ]


@given("uma inferencia com desqualificador detectado")
def _given_disqualified(ctx: dict[str, Any]) -> None:
    ctx["inferences"] = [
        _inference(
            cid="dq",
            technologies=["aws", "kubernetes"],
            industry="saas",
            confidence=0.9,
            intent_signals=["intencao_ia"],
            disqualifiers=["solo_sem_equipe"],
        )
    ]


@given("duas inferencias identicas exceto o sinal de intencao")
def _given_intent_pair(ctx: dict[str, Any]) -> None:
    ctx["inferences"] = [
        _inference(
            cid="com_sinal",
            technologies=["aws", "kubernetes"],
            industry="saas",
            confidence=0.8,
            intent_signals=["depende_de_mim"],
        ),
        _inference(
            cid="sem_sinal",
            technologies=["aws", "kubernetes"],
            industry="saas",
            confidence=0.8,
        ),
    ]


@given("duas inferencias identicas exceto a confianca")
def _given_conf(ctx: dict[str, Any]) -> None:
    ctx["inferences"] = [
        _inference(
            cid="hi",
            technologies=["aws", "kubernetes"],
            industry="saas",
            confidence=0.9,
            intent_signals=["intencao_ia"],
        ),
        _inference(
            cid="lo",
            technologies=["aws", "kubernetes"],
            industry="saas",
            confidence=0.4,
            intent_signals=["intencao_ia"],
        ),
    ]


@when("eu calculo o score duas vezes")
def _when_twice(ctx: dict[str, Any]) -> None:
    ctx["run1"] = _run(ctx["inferences"])
    ctx["run2"] = _run(ctx["inferences"])


@when("eu calculo o score uma vez")
def _when_once(ctx: dict[str, Any]) -> None:
    ctx["run1"] = _run(ctx["inferences"])


@then("cada p_score esta entre 0 e 1")
def _then_range(ctx: dict[str, Any]) -> None:
    for score in ctx["run1"]:
        assert 0.0 <= score.p_score <= 1.0


@then("as duas execucoes sao identicas com tolerancia 1e-9")
def _then_deterministic(ctx: dict[str, Any]) -> None:
    run1: list[ProspectScore] = ctx["run1"]
    run2: list[ProspectScore] = ctx["run2"]
    assert len(run1) == len(run2)
    for a, b in zip(run1, run2, strict=True):
        assert abs(a.p_score - b.p_score) <= 1e-9
        assert abs(a.fit - b.fit) <= 1e-9
        assert abs(a.intent - b.intent) <= 1e-9


@then("o lead tem hard_filter_passed falso e p_score zero")
def _then_hard_filter(ctx: dict[str, Any]) -> None:
    score = ctx["run1"][0]
    assert score.hard_filter_passed is False
    assert score.p_score == 0.0


@then("o prospect com sinal de intencao tem p_score estritamente maior")
def _then_intent_higher(ctx: dict[str, Any]) -> None:
    com_sinal, sem_sinal = ctx["run1"][0], ctx["run1"][1]
    assert com_sinal.intent > sem_sinal.intent
    assert com_sinal.p_score > sem_sinal.p_score


@then("o prospect de maior confianca tem p_score maior ou igual")
def _then_conf_order(ctx: dict[str, Any]) -> None:
    hi, lo = ctx["run1"][0], ctx["run1"][1]
    assert hi.p_score >= lo.p_score
