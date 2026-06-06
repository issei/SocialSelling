"""Step defs — WU-A DataProvenance + Hypothesis metadata (pytest-bdd). Módulo puro."""

from __future__ import annotations

from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from socialselling.contracts import (
    DataProvenance,
    Driver,
    Hypothesis,
    HypothesisCatalog,
)

scenarios("../features/wua_provenance_contract.feature")


@pytest.fixture
def ctx() -> dict[str, Any]:
    return {}


# ---------------------------------------------------------------------------
# Scenario 1: Driver with DataProvenance
# ---------------------------------------------------------------------------


@given('um Driver instanciado com uma DataProvenance de URL "https://ex.com"')
def _given_driver_with_provenance(ctx: dict[str, Any]) -> None:
    prov = DataProvenance(
        source="Tavily Search",
        url="https://ex.com",
        snippet="Expansão para Brasil",
        extracted_at="2026-06-06T00:00:00Z",
    )
    ctx["driver"] = Driver(
        driver="INTENT_TIMING",
        impact="positivo",
        text="Sinal de expansão detectado.",
        references=[prov],
    )


@when("o Driver é serializado via model_dump")
def _when_driver_dump(ctx: dict[str, Any]) -> None:
    ctx["dump"] = ctx["driver"].model_dump()


@then('references[0].url é "https://ex.com"')
def _then_url(ctx: dict[str, Any]) -> None:
    assert ctx["dump"]["references"][0]["url"] == "https://ex.com"


@then('references[0].source é "Tavily Search"')
def _then_source(ctx: dict[str, Any]) -> None:
    assert ctx["dump"]["references"][0]["source"] == "Tavily Search"


# ---------------------------------------------------------------------------
# Scenario 2: DataProvenance url=None (Open-World)
# ---------------------------------------------------------------------------


@given('uma DataProvenance com url None e source "Análise Semântica Interna"')
def _given_provenance_no_url(ctx: dict[str, Any]) -> None:
    ctx["prov_kwargs"] = {
        "source": "Análise Semântica Interna",
        "url": None,
        "snippet": "",
        "extracted_at": "2026-06-06T00:00:00Z",
    }


@when("a DataProvenance é instanciada")
def _when_prov_instantiated(ctx: dict[str, Any]) -> None:
    ctx["prov"] = DataProvenance(**ctx["prov_kwargs"])


@then("o objeto é válido com url None")
def _then_prov_valid_no_url(ctx: dict[str, Any]) -> None:
    prov: DataProvenance = ctx["prov"]
    assert prov.url is None
    assert prov.source == "Análise Semântica Interna"


# ---------------------------------------------------------------------------
# Scenario 3: Old JSON without new fields → defaults applied
# ---------------------------------------------------------------------------


@given("um dict de Hypothesis sem os campos label e guide_tags")
def _given_old_hypothesis_dict(ctx: dict[str, Any]) -> None:
    ctx["catalog_dict"] = {
        "hypotheses": [
            {
                "hypothesis_id": "H_99",
                "description": "Hipotese legada sem novos campos.",
                "prior": 0.10,
                "surface_signals": ["sinal_x"],
                "sources": ["web_search"],
            }
        ]
    }


@when("HypothesisCatalog.model_validate é chamado com esses dados")
def _when_catalog_validate(ctx: dict[str, Any]) -> None:
    ctx["catalog"] = HypothesisCatalog.model_validate(ctx["catalog_dict"])


@then('a hipótese carrega com label="" e guide_tags=[]')
def _then_defaults_applied(ctx: dict[str, Any]) -> None:
    catalog: HypothesisCatalog = ctx["catalog"]
    hyp: Hypothesis = catalog.hypotheses[0]
    assert hyp.label == ""
    assert hyp.guide_tags == []
    assert hyp.description_plain == ""
    assert hyp.impact_dimension == "intent"
