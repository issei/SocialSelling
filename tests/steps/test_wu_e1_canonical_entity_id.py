"""Steps BDD para WU-E1 — canonical_entity_id."""

from __future__ import annotations

import re

import pytest
from pytest_bdd import given, parsers, scenario, then, when

from socialselling.core.identity import canonical_entity_id

FEATURE = "../features/wu_e1_canonical_entity_id.feature"


@scenario(FEATURE, "Site com esquema e subdomínio www retorna domínio limpo")
def test_site_com_www() -> None:
    pass


@scenario(FEATURE, "Site sem esquema é tratado como HTTPS")
def test_site_sem_esquema() -> None:
    pass


@scenario(FEATURE, "Mesmo lead com variações de URL gera mesmo entity_id")
def test_variacoes_url() -> None:
    pass


@scenario(FEATURE, "Site com porta explícita — a porta é ignorada")
def test_porta_ignorada() -> None:
    pass


@scenario(FEATURE, "Fallback por nome+cidade quando não há website")
def test_fallback_sem_website() -> None:
    pass


@scenario(FEATURE, "Fallback é estável com variações de acentos e caixa")
def test_fallback_acentos() -> None:
    pass


@scenario(FEATURE, "Fallback com cidade ausente usa string vazia")
def test_fallback_cidade_ausente() -> None:
    pass


@scenario(FEATURE, "Leads distintos geram entity_ids distintos")
def test_leads_distintos() -> None:
    pass


@scenario(FEATURE, "Lead com site vazio cai no fallback")
def test_site_vazio() -> None:
    pass


# ---------------------------------------------------------------------------
# Fixtures de contexto (estado compartilhado dentro de cada cenário)
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx() -> dict:  # type: ignore[type-arg]
    return {}


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given(parsers.parse('o website "{website}"'), target_fixture="ctx")
def given_website(website: str) -> dict:  # type: ignore[type-arg]
    return {"website": website}


@given("que não há website", target_fixture="ctx")
def given_sem_website() -> dict:  # type: ignore[type-arg]
    return {"website": None}


@given("o website vazio", target_fixture="ctx")
def given_website_vazio() -> dict:  # type: ignore[type-arg]
    return {"website": ""}


@given(parsers.parse('outro lead com website "{website2}"'))
def given_outro_website(ctx: dict, website2: str) -> None:  # type: ignore[type-arg]
    ctx["website2"] = website2


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when(parsers.parse('calculo o entity_id com nome "{name}" e cidade "{city}"'))
def when_calculo_entity_id(ctx: dict, name: str, city: str) -> None:  # type: ignore[type-arg]
    ctx["result"] = canonical_entity_id(ctx.get("website"), name, city)


@when(parsers.parse('calculo o entity_id com nome "{name}" e cidade ausente'))
def when_calculo_sem_cidade(ctx: dict, name: str) -> None:  # type: ignore[type-arg]
    ctx["result"] = canonical_entity_id(ctx.get("website"), name, None)


@when("calculo ambos os entity_ids")
def when_calculo_ambos(ctx: dict) -> None:  # type: ignore[type-arg]
    ctx["result"] = canonical_entity_id(ctx["website"], "Lead A", "CidadeA")
    ctx["result2"] = canonical_entity_id(ctx["website2"], "Lead B", "CidadeB")


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then(parsers.parse('o entity_id é "{expected}"'))
def then_entity_id_igual(ctx: dict, expected: str) -> None:  # type: ignore[type-arg]
    assert ctx["result"] == expected, f"Esperado '{expected}', obtido '{ctx['result']}'"


@then(parsers.parse('é idêntico ao entity_id calculado para website "{alt_website}"'))
def then_identico_ao_alternativo(ctx: dict, alt_website: str) -> None:  # type: ignore[type-arg]
    alt = canonical_entity_id(alt_website, "Cliniq", "São Paulo")
    assert ctx["result"] == alt, f"Resultado '{ctx['result']}' ≠ alternativo '{alt}'"


@then('o entity_id começa com "sha256:"')
def then_comeca_sha256(ctx: dict) -> None:  # type: ignore[type-arg]
    res = ctx["result"]
    assert res.startswith("sha256:"), f"Esperado prefixo sha256:, obtido '{res}'"


@then("tem 64 caracteres hexadecimais após o prefixo")
def then_64_hex(ctx: dict) -> None:  # type: ignore[type-arg]
    suffix = ctx["result"][len("sha256:"):]
    assert re.fullmatch(r"[0-9a-f]{64}", suffix), f"Sufixo inválido: '{suffix}'"


@then(parsers.parse('o entity_id é igual ao de nome "{name2}" e cidade "{city2}"'))
def then_igual_ao_outro(ctx: dict, name2: str, city2: str) -> None:  # type: ignore[type-arg]
    other = canonical_entity_id(None, name2, city2)
    assert ctx["result"] == other, f"'{ctx['result']}' ≠ '{other}'"


@then("os dois entity_ids são diferentes")
def then_distintos(ctx: dict) -> None:  # type: ignore[type-arg]
    assert ctx["result"] != ctx["result2"], (
        f"Esperado ids distintos, mas ambos são '{ctx['result']}'"
    )
