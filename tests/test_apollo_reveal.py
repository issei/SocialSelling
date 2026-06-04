"""Testes do degrau 3 Apollo (reveal de contato): top-N, orçamento, cache, Open-World.

Sem rede: fake client + CreditBudget e JsonCache em tmp. Determinístico.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from socialselling.apollo.reveal import reveal_contacts
from socialselling.contracts import LeadCard, LeadContact, LeadLinks, ProspectScore
from socialselling.core.cache import JsonCache
from socialselling.core.credit_ledger import CreditBudget
from socialselling.skills.apollo_client import ApolloRateLimitError

_NOW = datetime(2026, 6, 4, 10, 0, 0)


def _card(company_id: str, p_score: float, website: str | None = "https://acme.com") -> LeadCard:
    return LeadCard(
        rank=1,
        display_name=f"Pessoa {company_id}",
        company=f"Co {company_id}",
        links=LeadLinks(website=website),
        contact=LeadContact(),
        score=ProspectScore(
            company_id=company_id, fit=0.5, intent=0.5, confidence=0.8, p_score=p_score
        ),
    )


class _FakeApollo:
    def __init__(self, payload: dict[str, Any] | Exception) -> None:
        self._payload = payload
        self.match_calls = 0

    def people_search(
        self, filters: dict[str, Any], **kw: Any
    ) -> dict[str, Any]:  # pragma: no cover
        return {}

    def org_enrich(self, **kw: Any) -> dict[str, Any]:  # pragma: no cover
        return {}

    def people_match(self, params: dict[str, Any], **kw: Any) -> dict[str, Any]:
        self.match_calls += 1
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


_REVEALED = {"person": {"email": "talita@acme.com", "phone_numbers": [{"raw_number": "+5511999"}]}}
_LOCKED = {"person": {"email": "email_not_unlocked@domain.com"}}


def _budget(tmp_path: Path, *, data: int, email: int) -> CreditBudget:
    return CreditBudget(
        tmp_path / "ledger.json", _NOW, data_cap=data, email_cap=email, mobile_cap=5
    )


def test_reveal_preenche_contato_do_top_n(tmp_path: Path) -> None:
    cards = [_card("c1", 0.9), _card("c2", 0.8), _card("c3", 0.7)]
    apollo = _FakeApollo(_REVEALED)
    out = reveal_contacts(
        cards,
        apollo_client=apollo,
        budget=_budget(tmp_path, data=2, email=2),
        cache=JsonCache(tmp_path / "rev"),
        now=_NOW,
        reveal_ttl_hours=2160,
        top_n_cap=20,
    )
    # Orçamento 2 => só os 2 primeiros revelados; o 3º intacto (sem contato).
    assert out[0].contact.email == "talita@acme.com"
    assert out[1].contact.email == "talita@acme.com"
    assert out[2].contact.email is None
    assert apollo.match_calls == 2


def test_orcamento_esgotado_marca_gap(tmp_path: Path) -> None:
    cards = [_card("c1", 0.9)]
    apollo = _FakeApollo(_REVEALED)
    out = reveal_contacts(
        cards,
        apollo_client=apollo,
        budget=_budget(tmp_path, data=0, email=0),
        cache=JsonCache(tmp_path / "rev"),
        now=_NOW,
        reveal_ttl_hours=2160,
        top_n_cap=20,
    )
    assert apollo.match_calls == 0  # sem crédito => nem chama
    assert out[0].contact.email is None


def test_cache_hit_nao_gasta_credito_duas_vezes(tmp_path: Path) -> None:
    cache = JsonCache(tmp_path / "rev")
    budget = _budget(tmp_path, data=5, email=5)
    cards = [_card("c1", 0.9)]
    reveal_contacts(
        cards,
        apollo_client=_FakeApollo(_REVEALED),
        budget=budget,
        cache=cache,
        now=_NOW,
        reveal_ttl_hours=2160,
        top_n_cap=20,
    )
    used_after_first = budget.remaining_data_credits()
    # 2ª revelação do mesmo card => cache hit => NÃO gasta crédito de novo.
    apollo2 = _FakeApollo(_REVEALED)
    reveal_contacts(
        cards,
        apollo_client=apollo2,
        budget=budget,
        cache=cache,
        now=_NOW,
        reveal_ttl_hours=2160,
        top_n_cap=20,
    )
    assert apollo2.match_calls == 0
    assert budget.remaining_data_credits() == used_after_first


def test_reveal_indisponivel_marca_gap_e_refunda(tmp_path: Path) -> None:
    cards = [_card("c1", 0.9)]
    budget = _budget(tmp_path, data=3, email=3)
    out = reveal_contacts(
        cards,
        apollo_client=_FakeApollo(_LOCKED),
        budget=budget,
        cache=JsonCache(tmp_path / "r"),
        now=_NOW,
        reveal_ttl_hours=2160,
        top_n_cap=20,
    )
    # email mascarado => não revelado => gap, sem fabricar contato.
    assert out[0].contact.email is None
    assert "sem_email_no_apollo" in out[0].gaps


def test_erro_apollo_refunda_credito(tmp_path: Path) -> None:
    cards = [_card("c1", 0.9)]
    budget = _budget(tmp_path, data=3, email=3)
    out = reveal_contacts(
        cards,
        apollo_client=_FakeApollo(ApolloRateLimitError("429")),
        budget=budget,
        cache=JsonCache(tmp_path / "r"),
        now=_NOW,
        reveal_ttl_hours=2160,
        top_n_cap=20,
    )
    # Falha após reserva => refund: crédito volta ao cap.
    assert budget.remaining_data_credits() == 3
    assert "sem_email_no_apollo" in out[0].gaps
