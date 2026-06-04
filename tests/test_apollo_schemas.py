"""Testes de contrato do sensor Apollo (WU-A1): schemas wire + bloco [apollo] do runtime.

Sem rede — apenas validação de contratos Pydantic e do carregamento de config (ADR-004).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from socialselling.apollo.schemas import (
    ApolloEndpoint,
    ApolloPersonHit,
    ApolloRevealResult,
)
from socialselling.config import RuntimeConfig, load_runtime

_ROOT = Path(__file__).resolve().parents[1]
_RUNTIME = _ROOT / "config" / "runtime.toml"


def test_endpoint_values() -> None:
    # StrEnum estável (usado como chave de custo/cache). `.value` evita o
    # comparison-overlap do mypy --strict entre o membro do enum e o literal str.
    assert ApolloEndpoint.PEOPLE_SEARCH.value == "people_search"
    assert ApolloEndpoint.ORG_ENRICH.value == "org_enrich"
    assert ApolloEndpoint.PEOPLE_MATCH.value == "people_match"


def test_person_hit_defaults_open_world() -> None:
    hit = ApolloPersonHit(apollo_id="a1", name="Fulana de Tal")
    # Contato mascarado por padrão no tier gratuito; firmografia opcional (Open-World).
    assert hit.email_masked is True
    assert hit.employee_count is None
    assert hit.organization_domain is None


def test_person_hit_rejects_extra_fields() -> None:
    # extra="forbid": payload do Apollo com campo inesperado falha cedo (schema drift).
    # model_validate(dict) para o campo extra não tropeçar no checagem estática do mypy.
    with pytest.raises(ValidationError):
        ApolloPersonHit.model_validate(
            {"apollo_id": "a1", "name": "X", "unexpected_field": "boom"}
        )


def test_person_hit_rejects_negative_employee_count() -> None:
    with pytest.raises(ValidationError):
        ApolloPersonHit(apollo_id="a1", name="X", employee_count=-3)


def test_reveal_result_defaults_not_revealed() -> None:
    # revealed=False por padrão => ausência de contato é incerteza, não dado fabricado.
    res = ApolloRevealResult(apollo_id="a1")
    assert res.revealed is False
    assert res.email is None
    assert res.phone is None


def test_runtime_loads_apollo_block() -> None:
    cfg: RuntimeConfig = load_runtime(_RUNTIME)
    assert cfg.apollo.enabled is False  # opt-in: desligado por padrão (paridade)
    assert cfg.apollo.base_url.startswith("https://")
    assert cfg.apollo.caps.data_credits_cap == 100
    assert cfg.apollo.caps.mobile_credits_cap == 5


def test_apollo_cfg_defaults_when_absent() -> None:
    # Retrocompatível: runtime sem [apollo] ainda valida (default enabled=False).
    minimal = {
        "cache": {"ttl_hours": 24},
        "scoring": {
            "w_fit": 0.6,
            "w_intent": 0.4,
            "confidence_exponent": 0.5,
            "w_fit_tech": 0.6,
            "w_fit_industry": 0.4,
            "intent_evidence_norm": 5,
        },
        "tavily": {"max_queries": 3, "max_results": 10, "search_depth": "basic"},
        "gemini": {"model": "gemini-2.5-flash-lite"},
        "runtime": {"max_leads_per_cycle": 50},
    }
    cfg = RuntimeConfig.model_validate(minimal)
    assert cfg.apollo.enabled is False
    assert cfg.apollo.reveal_top_n == 20
