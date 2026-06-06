"""Step defs — WU-B M5 propagação de proveniência (pytest-bdd). Módulo puro."""

from __future__ import annotations

from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from socialselling.contracts import (
    CompanyEntity,
    ICPCriteria,
    Inference,
    ObservedEvidence,
    ProspectScore,
)
from socialselling.modules.m5_xai import run_m5

scenarios("../features/wub_m5_provenance.feature")


@pytest.fixture
def ctx() -> dict[str, Any]:
    return {}


def _make_icp() -> ICPCriteria:
    return ICPCriteria.model_validate(
        {
            "icp_id": "test",
            "firmographics": {
                "industries": ["tech"],
                "employee_range": {"min": 1, "max": 500},
                "geographies": {"country": "BR"},
                "business_models": ["b2b"],
            },
            "technographics": {"mandatory": [], "preferred": [], "excluded": []},
            "persona_matrix": {"target_roles": ["CEO"], "min_seniority": "senior"},
            "intent_triggers": [],
        }
    )


def _make_score(company_id: str = "c1", intent: float = 0.6) -> ProspectScore:
    return ProspectScore(
        company_id=company_id,
        fit=0.5,
        intent=intent,
        confidence=0.8,
        persona_fit=1.0,
        p_score=0.6,
    )


def _make_inference(derived_from: str, intent_signals: list[str]) -> Inference:
    return Inference(
        company=CompanyEntity(
            company_id="c1",
            normalized_name="Empresa Teste",
            confidence=0.8,
        ),
        derived_from=[derived_from],
        confidence=0.8,
        intent_signals=intent_signals,
    )


def _make_evidence(evidence_id: str, source_url: str) -> ObservedEvidence:
    return ObservedEvidence(
        evidence_id=evidence_id,
        query="expansão brasil",
        source_url=source_url,
        title="Empresa anuncia expansão",
        snippet="Empresa anuncia expansão para novo mercado",
        captured_at="2026-06-06T00:00:00Z",
        source_trust=0.7,
    )


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given('uma inferência com derived_from "ev_001" e intent_signals ["expansão"]')
def _given_inference_ev001(ctx: dict[str, Any]) -> None:
    ctx["inference"] = _make_inference("ev_001", ["expansão"])


@given('uma inferência com derived_from "ev_999" e intent_signals ["expansão"]')
def _given_inference_ev999(ctx: dict[str, Any]) -> None:
    ctx["inference"] = _make_inference("ev_999", ["expansão"])


@given('um evidence_index com "ev_001" apontando para "https://ex.com/noticia"')
def _given_index_ev001_ex(ctx: dict[str, Any]) -> None:
    ctx["evidence_index"] = {"ev_001": _make_evidence("ev_001", "https://ex.com/noticia")}


@given('um evidence_index com "ev_001" apontando para "https://outro.com"')
def _given_index_ev001_outro(ctx: dict[str, Any]) -> None:
    ctx["evidence_index"] = {"ev_001": _make_evidence("ev_001", "https://outro.com")}


@given("um evidence_index vazio")
def _given_empty_index(ctx: dict[str, Any]) -> None:
    ctx["evidence_index"] = {}


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when("run_m5 é chamado com score.intent positivo")
def _when_run_m5(ctx: dict[str, Any]) -> None:
    ctx["payload"] = run_m5(
        _make_score(),
        ctx["inference"],
        _make_icp(),
        evidence_index=ctx["evidence_index"],
    )


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


def _intent_driver(ctx: dict[str, Any]) -> Any:
    payload = ctx["payload"]
    drivers = [d for d in payload.positive_signals if d.driver == "INTENT_TIMING"]
    assert drivers, "INTENT_TIMING driver não encontrado em positive_signals"
    return drivers[0]


@then('o Driver INTENT_TIMING tem references[0].url igual a "https://ex.com/noticia"')
def _then_ref_url(ctx: dict[str, Any]) -> None:
    driver = _intent_driver(ctx)
    assert driver.references, "references está vazio"
    assert driver.references[0].url == "https://ex.com/noticia"


@then("o texto do Driver contém \"Fontes:\"")
def _then_text_fontes(ctx: dict[str, Any]) -> None:
    driver = _intent_driver(ctx)
    assert "Fontes:" in driver.text


@then("o Driver INTENT_TIMING tem references vazio")
def _then_refs_empty(ctx: dict[str, Any]) -> None:
    driver = _intent_driver(ctx)
    assert driver.references == []


@then("o texto do Driver contém \"Análise Semântica Interna\"")
def _then_text_semantica(ctx: dict[str, Any]) -> None:
    driver = _intent_driver(ctx)
    assert "Análise Semântica Interna" in driver.text
