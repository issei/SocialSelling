"""Testes do degrau 2 Apollo (org-enrich condicional): só firmografia faltante, sob crédito.

Sem rede: fake client + CreditBudget e JsonCache em tmp. Determinístico.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from socialselling.apollo.enrich import enrich_organizations
from socialselling.contracts import CompanyEntity, Inference
from socialselling.core.cache import JsonCache
from socialselling.core.credit_ledger import CreditBudget
from socialselling.skills.apollo_client import ApolloRateLimitError

_NOW = datetime(2026, 6, 4, 10, 0, 0)
_ENRICH = {"organization": {"industry": "consultoria", "estimated_num_employees": 12}}


def _inf(
    company_id: str, *, employee_count: int | None, industry: str | None, domain: str | None
) -> Inference:
    return Inference(
        company=CompanyEntity(
            company_id=company_id,
            normalized_name=company_id,
            domain=domain,
            employee_count=employee_count,
            industry=industry,
            confidence=0.7,
        ),
        people=[],
        derived_from=[],
        confidence=0.7,
    )


class _FakeApollo:
    def __init__(self, payload: dict[str, Any] | Exception) -> None:
        self._payload = payload
        self.enrich_calls = 0

    def people_search(
        self, filters: dict[str, Any], **kw: Any
    ) -> dict[str, Any]:  # pragma: no cover
        return {}

    def people_match(self, params: dict[str, Any], **kw: Any) -> dict[str, Any]:  # pragma: no cover
        return {}

    def org_enrich(
        self, *, domain: str | None = None, organization_name: str | None = None
    ) -> dict[str, Any]:
        self.enrich_calls += 1
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def _budget(tmp_path: Path, data: int) -> CreditBudget:
    return CreditBudget(tmp_path / "ledger.json", _NOW, data_cap=data, email_cap=5, mobile_cap=5)


def _run(
    tmp_path: Path, inferences: list[Inference], apollo: _FakeApollo, data: int = 5
) -> list[Inference]:
    return enrich_organizations(
        inferences,
        apollo_client=apollo,
        budget=_budget(tmp_path, data),
        cache=JsonCache(tmp_path / "org"),
        now=_NOW,
        ttl_hours=720,
    )


def test_enriquece_firmografia_faltante(tmp_path: Path) -> None:
    inf = _inf("c1", employee_count=None, industry=None, domain="acme.com")
    apollo = _FakeApollo(_ENRICH)
    out = _run(tmp_path, [inf], apollo)
    assert apollo.enrich_calls == 1
    assert out[0].company.employee_count == 12
    assert out[0].company.industry == "consultoria"


def test_nao_enriquece_quando_firmografia_completa(tmp_path: Path) -> None:
    inf = _inf("c1", employee_count=20, industry="advocacia", domain="x.com")
    apollo = _FakeApollo(_ENRICH)
    out = _run(tmp_path, [inf], apollo)
    assert apollo.enrich_calls == 0  # já tem firmografia => não gasta crédito
    assert out[0].company.employee_count == 20


def test_sem_dominio_segue_sem_enrich(tmp_path: Path) -> None:
    inf = _inf("c1", employee_count=None, industry=None, domain=None)
    apollo = _FakeApollo(_ENRICH)
    out = _run(tmp_path, [inf], apollo)
    assert apollo.enrich_calls == 0  # sem chave de enrich
    assert out[0].company.employee_count is None


def test_credito_esgotado_segue_sem_enrich(tmp_path: Path) -> None:
    inf = _inf("c1", employee_count=None, industry=None, domain="acme.com")
    apollo = _FakeApollo(_ENRICH)
    out = _run(tmp_path, [inf], apollo, data=0)
    assert apollo.enrich_calls == 0
    assert out[0].company.industry is None


def test_erro_refunda_e_segue(tmp_path: Path) -> None:
    inf = _inf("c1", employee_count=None, industry=None, domain="acme.com")
    budget = _budget(tmp_path, 3)
    out = enrich_organizations(
        [inf],
        apollo_client=_FakeApollo(ApolloRateLimitError("429")),
        budget=budget,
        cache=JsonCache(tmp_path / "org"),
        now=_NOW,
        ttl_hours=720,
    )
    assert budget.remaining_data_credits() == 3  # refund após falha
    assert out[0].company.industry is None
