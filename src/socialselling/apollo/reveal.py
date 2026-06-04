"""Degrau 3 da escada: reveal de contato do TOP-N do ranking (ADR-004).

Único passo que gasta os escassos email/mobile-credits. Roda DEPOIS do ranking (M4),
só para o top-N que o orçamento permite, e NUNCA re-paga (cache de 90d). Open-World:
crédito esgotado ou contato indisponível => `gaps`, nunca dado fabricado.
"""

from __future__ import annotations

import json
from datetime import datetime
from urllib.parse import urlparse

from socialselling.apollo.ladder import reveal_count
from socialselling.apollo.normalize import parse_reveal
from socialselling.contracts import LeadCard, LeadContact
from socialselling.core.cache import JsonCache, query_hash
from socialselling.core.credit_ledger import CreditBudget
from socialselling.skills.apollo_client import (
    ApolloAuthError,
    ApolloCreditError,
    ApolloError,
    ApolloRateLimitError,
    ApolloSearchClient,
)

_REVEAL_ERRORS = (ApolloAuthError, ApolloCreditError, ApolloRateLimitError, ApolloError)


def _domain_from(website: str | None) -> str | None:
    if not website:
        return None
    host = urlparse(website).netloc or urlparse(f"https://{website}").netloc
    return host.removeprefix("www.") or None


def _match_params(card: LeadCard) -> dict[str, object]:
    params: dict[str, object] = {"name": card.display_name}
    if card.company:
        params["organization_name"] = card.company
    domain = _domain_from(card.links.website)
    if domain:
        params["domain"] = domain
    return params


def _with_gap(card: LeadCard, reason: str) -> LeadCard:
    if reason in card.gaps:
        return card
    return card.model_copy(update={"gaps": [*card.gaps, reason]})


def reveal_contacts(
    cards: list[LeadCard],
    *,
    apollo_client: ApolloSearchClient,
    budget: CreditBudget,
    cache: JsonCache,
    now: datetime,
    reveal_ttl_hours: int,
    top_n_cap: int,
) -> list[LeadCard]:
    """Revela contato do top-N do ranking dentro do orçamento; demais ficam intactos."""
    n = reveal_count(
        total=len(cards),
        remaining_data=budget.remaining_data_credits(),
        remaining_email=budget.remaining_email_credits(),
        top_n_cap=top_n_cap,
    )
    out: list[LeadCard] = []
    for i, card in enumerate(cards):
        if i >= n:
            out.append(card)
            continue
        out.append(_reveal_one(card, apollo_client, budget, cache, now, reveal_ttl_hours))
    return out


def _reveal_one(
    card: LeadCard,
    apollo_client: ApolloSearchClient,
    budget: CreditBudget,
    cache: JsonCache,
    now: datetime,
    reveal_ttl_hours: int,
) -> LeadCard:
    params = _match_params(card)
    key = "apollo:reveal:" + query_hash(json.dumps(params, sort_keys=True))[:16]
    payload = cache.get(key, now, reveal_ttl_hours)
    if payload is None:
        # Reserva pessimista: 1 data + 1 email credit. Esgotado => não revela.
        if not budget.try_spend(data=1, email=1):
            return _with_gap(card, "contato_nao_revelado_orcamento")
        try:
            payload = apollo_client.people_match(params, reveal_personal_emails=True)
            cache.put(key, payload, now)
        except _REVEAL_ERRORS:
            budget.refund(data=1, email=1)  # falha após reserva => devolve crédito
            return _with_gap(card, "sem_email_no_apollo")
    result = parse_reveal(payload)
    if not result.revealed:
        return _with_gap(card, "sem_email_no_apollo")
    return card.model_copy(
        update={
            "contact": LeadContact(
                email=result.email or card.contact.email,
                phone=result.phone or card.contact.phone,
            )
        }
    )
