"""Escada de enriquecimento incremental: ICP->filtros + seleção por degrau (ADR-004).

Funções PURAS e determinísticas (sem rede, sem I/O). São o "cérebro" da escada §1 do
SDD: o degrau N só roda para quem o degrau N-1 aprovou, e o gasto de crédito é função
do ranking determinístico (M4) + do ledger. Reexecução byte-idêntica.

NOTA de calibração (como L-024 do Tavily): o mapeamento ICP->filtros Apollo é heurístico
e deve ser afinado empiricamente com a chave real antes de confiar no recall.
"""

from __future__ import annotations

from typing import TypeVar

from socialselling.contracts import ICPCriteria

_COUNTRY_NAMES = {"BR": "Brazil"}

T = TypeVar("T")


def icp_to_people_filters(icp: ICPCriteria, *, persona_term: str = "") -> dict[str, object]:
    """Mapeia o ICP para filtros de People Search (degrau 1, 0 crédito).

    Determinístico: listas preservam a ordem do ICP. Heurístico (a calibrar).
    """
    fg = icp.firmographics
    country = fg.geographies.country
    country_name = _COUNTRY_NAMES.get(country.upper(), country)

    # Apollo espera faixas "min,max" para nº de funcionários.
    employee_ranges = [f"{fg.employee_range.min},{fg.employee_range.max}"]

    titles = list(icp.persona_matrix.target_roles)
    persona = persona_term.strip()

    filters: dict[str, object] = {
        "person_titles": titles,
        "organization_num_employees_ranges": employee_ranges,
        "person_locations": [country_name],
        # Indústrias entram como keywords (sem lookup de tag ids no PoC).
        "q_organization_keyword_tags": list(fg.industries),
    }
    if persona:
        filters["q_keywords"] = persona
    return filters


def needs_org_enrich(*, employee_count: int | None, industry: str | None) -> bool:
    """Degrau 2 só roda se faltar firmografia relevante para o score (evita 1 crédito à toa)."""
    return employee_count is None or industry is None


def reveal_count(*, total: int, remaining_data: int, remaining_email: int, top_n_cap: int) -> int:
    """Quantos leads revelar no degrau 3: limitado pelo MENOR entre ranking, créditos e teto."""
    return max(0, min(total, remaining_data, remaining_email, top_n_cap))


def select_for_reveal(
    ranked: list[T], *, remaining_data: int, remaining_email: int, top_n_cap: int
) -> list[T]:
    """TOP-N do ranking (determinístico) para revelar contato, dentro do orçamento."""
    n = reveal_count(
        total=len(ranked),
        remaining_data=remaining_data,
        remaining_email=remaining_email,
        top_n_cap=top_n_cap,
    )
    return ranked[:n]
