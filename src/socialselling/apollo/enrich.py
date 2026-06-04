"""Degrau 2 da escada: org enrichment CONDICIONAL (ADR-004).

Roda APÓS o M2 e ANTES do score, só para inferências cuja firmografia está faltando
(`needs_org_enrich`) e que têm um domínio — evita gastar 1 crédito à toa. Cache 30d.
Open-World: sem crédito / sem domínio / falha => inferência segue inalterada (incerteza),
nunca dado fabricado.
"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse

from socialselling.apollo.ladder import needs_org_enrich
from socialselling.apollo.normalize import parse_org_enrich
from socialselling.contracts import Inference
from socialselling.core.cache import JsonCache, query_hash
from socialselling.core.credit_ledger import CreditBudget
from socialselling.skills.apollo_client import (
    ApolloAuthError,
    ApolloCreditError,
    ApolloError,
    ApolloRateLimitError,
    ApolloSearchClient,
)

_ENRICH_ERRORS = (ApolloAuthError, ApolloCreditError, ApolloRateLimitError, ApolloError)


def _domain_of(inf: Inference) -> str | None:
    comp = inf.company
    if comp.domain:
        return comp.domain
    if comp.website:
        host = urlparse(comp.website).netloc or urlparse(f"https://{comp.website}").netloc
        return host.removeprefix("www.") or None
    return None


def enrich_organizations(
    inferences: list[Inference],
    *,
    apollo_client: ApolloSearchClient,
    budget: CreditBudget,
    cache: JsonCache,
    now: datetime,
    ttl_hours: int,
) -> list[Inference]:
    """Preenche firmografia faltante (employee_count/industry) via Apollo, sob orçamento."""
    out: list[Inference] = []
    for inf in inferences:
        comp = inf.company
        if not needs_org_enrich(employee_count=comp.employee_count, industry=comp.industry):
            out.append(inf)
            continue
        domain = _domain_of(inf)
        if domain is None:
            out.append(inf)  # sem chave de enrich => segue (Open-World)
            continue
        key = "apollo:org:" + query_hash(domain)[:16]
        payload = cache.get(key, now, ttl_hours)
        if payload is None:
            if not budget.try_spend(data=1):
                out.append(inf)  # crédito esgotado => segue sem enrich
                continue
            try:
                payload = apollo_client.org_enrich(domain=domain)
                cache.put(key, payload, now)
            except _ENRICH_ERRORS:
                budget.refund(data=1)
                out.append(inf)
                continue
        org = parse_org_enrich(payload)
        out.append(
            inf.model_copy(
                update={
                    "company": comp.model_copy(
                        update={
                            "employee_count": comp.employee_count or org.employee_count,
                            "industry": comp.industry or org.industry,
                        }
                    )
                }
            )
        )
    return out
