"""BDD de objetivo (pytest-bdd): o ranking reflete a estrategia da Talita.

Modulo puro (M3+M4) sobre arquetipos sinteticos com o ICP/catalogo da Talita.
"""

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
from socialselling.modules.m4_ranking import run_m4

_ROOT = Path(__file__).resolve().parents[2]

scenarios("../features/objetivo_ranking.feature")

_PARAMS: dict[str, Any] = {
    "w_fit": 0.60,
    "w_intent": 0.40,
    "confidence_exponent": 0.5,
    "w_fit_tech": 0.60,
    "w_fit_industry": 0.40,
}


def _talita_icp() -> ICPCriteria:
    raw = json.loads((_ROOT / "config" / "icp_criteria.talita.json").read_text("utf-8"))
    return ICPCriteria.model_validate(raw)


def _catalog() -> HypothesisCatalog:
    raw = json.loads((_ROOT / "config" / "hypotheses_catalog.json").read_text("utf-8"))
    return HypothesisCatalog.model_validate(raw)


def _arquetipo(
    cid: str,
    *,
    industry: str,
    intent_signals: list[str],
    disqualifiers: list[str],
) -> Inference:
    return Inference(
        company=CompanyEntity(
            company_id=cid,
            normalized_name=cid,
            industry=industry,
            technologies=[],
            confidence=0.8,
        ),
        people=[],
        derived_from=["ev1"],
        confidence=0.8,
        intent_signals=intent_signals,
        disqualifiers=disqualifiers,
    )


@pytest.fixture
def ctx() -> dict[str, Any]:
    return {}


def _by_id(scores: list[ProspectScore], cid: str) -> ProspectScore:
    return next(s for s in scores if s.company_id == cid)


@given("os arquetipos de prospect da Talita")
def _given_arquetipos(ctx: dict[str, Any]) -> None:
    ctx["inferences"] = [
        _arquetipo(
            "mayara",
            industry="advocacia",
            intent_signals=["depende_de_mim", "contratacao_senior"],
            disqualifiers=[],
        ),
        _arquetipo("fit_puro", industry="consultoria", intent_signals=[], disqualifiers=[]),
        _arquetipo(
            "solo",
            industry="consultoria",
            intent_signals=["depende_de_mim"],
            disqualifiers=["solo_sem_equipe"],
        ),
        _arquetipo("fora_setor", industry="varejo", intent_signals=["expansao"], disqualifiers=[]),
    ]


@when("eu pontuo com o ICP e as hipoteses da Talita e ranqueio")
def _when_rank(ctx: dict[str, Any]) -> None:
    scores = run_m3(ctx["inferences"], _talita_icp(), _catalog(), **_PARAMS)
    ctx["scores"] = scores
    ctx["ranked"] = run_m4(scores)


@then("a Mayara (founder com timing) aparece em primeiro")
def _then_mayara_first(ctx: dict[str, Any]) -> None:
    assert ctx["ranked"][0].company_id == "mayara"


@then("o lead solo desqualificado tem p_score zero e hard filter reprovado")
def _then_solo_zero(ctx: dict[str, Any]) -> None:
    solo = _by_id(ctx["scores"], "solo")
    assert solo.p_score == 0.0
    assert solo.hard_filter_passed is False
    assert ctx["ranked"][-1].company_id == "solo"


@then("o lead com sinal de intencao supera o de fit puro")
def _then_intent_beats_fit(ctx: dict[str, Any]) -> None:
    mayara = _by_id(ctx["scores"], "mayara")
    fit_puro = _by_id(ctx["scores"], "fit_puro")
    assert mayara.p_score > fit_puro.p_score


@then("o lead fora de setor fica abaixo da Mayara")
def _then_fora_setor_below(ctx: dict[str, Any]) -> None:
    order = [s.company_id for s in ctx["ranked"]]
    assert order.index("fora_setor") > order.index("mayara")
