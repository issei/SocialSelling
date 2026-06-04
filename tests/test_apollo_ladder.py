"""Testes da escada de enriquecimento (WU-A4, parte pura): ICP->filtros + seleção.

Determinístico, sem rede. Garante: gasto de crédito = função do ranking + orçamento;
degrau N só roda para quem o N-1 aprovou.
"""

from __future__ import annotations

import json
from pathlib import Path

from socialselling.apollo.ladder import (
    icp_to_people_filters,
    needs_org_enrich,
    reveal_count,
    select_for_reveal,
)
from socialselling.contracts import ICPCriteria

_ROOT = Path(__file__).resolve().parents[1]


def _talita_icp() -> ICPCriteria:
    raw = json.loads((_ROOT / "config" / "icp_criteria.talita.json").read_text(encoding="utf-8"))
    return ICPCriteria.model_validate(raw)


def test_icp_to_filters_estrutura_e_determinismo() -> None:
    icp = _talita_icp()
    a = icp_to_people_filters(icp, persona_term="fundadora")
    b = icp_to_people_filters(icp, persona_term="fundadora")
    assert a == b  # determinístico
    assert a["person_titles"] == icp.persona_matrix.target_roles
    assert a["organization_num_employees_ranges"] == ["5,30"]
    assert a["person_locations"] == ["Brazil"]  # BR -> nome
    assert a["q_keywords"] == "fundadora"
    assert a["q_organization_keyword_tags"] == icp.firmographics.industries


def test_needs_org_enrich() -> None:
    assert needs_org_enrich(employee_count=None, industry="consultoria") is True
    assert needs_org_enrich(employee_count=12, industry=None) is True
    assert needs_org_enrich(employee_count=12, industry="consultoria") is False


def test_reveal_count_limitado_pelo_menor() -> None:
    # Limitado pelo MENOR entre total, créditos de dado, créditos de e-mail e teto.
    assert reveal_count(total=100, remaining_data=20, remaining_email=50, top_n_cap=30) == 20
    assert reveal_count(total=100, remaining_data=50, remaining_email=10, top_n_cap=30) == 10
    assert reveal_count(total=5, remaining_data=50, remaining_email=50, top_n_cap=30) == 5
    assert reveal_count(total=100, remaining_data=50, remaining_email=50, top_n_cap=20) == 20


def test_reveal_count_nunca_negativo() -> None:
    assert reveal_count(total=0, remaining_data=0, remaining_email=0, top_n_cap=0) == 0


def test_select_for_reveal_pega_top_n() -> None:
    ranked = ["a", "b", "c", "d", "e"]  # já ordenado (saída do M4)
    out = select_for_reveal(ranked, remaining_data=3, remaining_email=10, top_n_cap=20)
    assert out == ["a", "b", "c"]  # top-3, preserva a ordem do ranking


def test_select_for_reveal_credito_esgotado_revela_nada() -> None:
    ranked = ["a", "b", "c"]
    out = select_for_reveal(ranked, remaining_data=0, remaining_email=10, top_n_cap=20)
    assert out == []  # sem crédito => nenhum reveal (Open-World: gaps, não dado fabricado)
