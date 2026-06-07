"""Testes da variação de queries por onda (ADR-006): paridade na onda 0, novos na onda>0."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from socialselling.contracts import ICPCriteria
from socialselling.core.cache import JsonCache
from socialselling.modules.m1_busca import generate_queries, run_m1

_NOW = datetime(2026, 1, 1, tzinfo=UTC)

# ICP fixo para os testes — independente do config/icp_criteria.talita.json em runtime.
# Deve corresponder ao ICP usado ao gravar as fixtures Tavily/Gemini.
_TEST_ICP: dict[str, Any] = {
    "icp_id": "icp_founders_servicos_brasil",
    "firmographics": {
        "industries": ["consultoria", "advocacia", "engenharia", "software", "saas"],
        "employee_range": {"min": 5, "max": 30},
        "geographies": {"country": "BR", "regions": ["SE", "S"]},
        "business_models": ["B2B"],
    },
    "technographics": {
        "mandatory": [],
        "preferred": ["clickup", "notion", "trello", "asana", "monday", "pipedrive"],
        "excluded": [],
    },
    "persona_matrix": {
        "target_roles": ["FOUNDER", "CEO", "MANAGING_PARTNER", "SOCIA_GESTORA"],
        "min_seniority": "FOUNDER_OWNER",
    },
    "intent_triggers": [
        "FUNDADORA_PRESA_NA_OPERACAO",
        "CONTRATACAO_SENIOR",
        "EXPANSAO_OU_NOVA_UNIDADE",
        "INTENCAO_ADOCAO_IA",
        "CONCLUSAO_CURSO_GESTAO",
    ],
}


def _talita() -> ICPCriteria:
    return ICPCriteria.model_validate(_TEST_ICP)


def test_onda_zero_e_paridade() -> None:
    icp = _talita()  # industries: consultoria, advocacia, engenharia, ...; country BR
    q0 = generate_queries(icp, max_queries=3, persona_term="fundadora", wave=0)
    assert q0 == [
        "consultoria fundadora Brasil",
        "advocacia fundadora Brasil",
        "engenharia fundadora Brasil",
    ]
    # default wave (omitido) == wave=0
    assert generate_queries(icp, 3, "fundadora") == q0


def test_onda_um_difere_e_e_deterministica() -> None:
    icp = _talita()
    q0 = generate_queries(icp, 3, "fundadora", wave=0)
    q1 = generate_queries(icp, 3, "fundadora", wave=1)
    assert len(q1) == 3
    assert q1 != q0  # busca leads NOVOS
    assert q1 == generate_queries(icp, 3, "fundadora", wave=1)  # determinístico
    # usa as regiões do ICP (SE/S), ausentes na onda 0
    assert any("SE" in q or " S" in (" " + q) for q in q1)


def test_ondas_consecutivas_variam() -> None:
    icp = _talita()
    janelas = [tuple(generate_queries(icp, 3, "fundadora", wave=w)) for w in range(1, 5)]
    assert len(set(janelas)) > 1  # ondas diferentes não colapsam todas na mesma janela


class _RecordingClient:
    """SearchClient falso que registra as queries e devolve resultado vazio."""

    def __init__(self) -> None:
        self.queries: list[str] = []

    def search(
        self,
        query: str,
        max_results: int,
        search_depth: str,
        include_domains: list[str] | None = None,
    ) -> dict[str, Any]:
        self.queries.append(query)
        return {"results": []}


def _run_wave(client: _RecordingClient, cache_dir: Path, wave: int) -> None:
    run_m1(
        _talita(),
        client=client,
        cache=JsonCache(cache_dir),
        now=_NOW,
        max_queries=3,
        max_results=10,
        search_depth="basic",
        cache_ttl_hours=24,
        persona_term="fundadora",
        wave=wave,
    )


def test_run_m1_repassa_wave(tmp_path: Path) -> None:
    c0, c1 = _RecordingClient(), _RecordingClient()
    _run_wave(c0, tmp_path / "c0", wave=0)
    _run_wave(c1, tmp_path / "c1", wave=1)
    assert c0.queries != c1.queries  # a onda chega até o M1
