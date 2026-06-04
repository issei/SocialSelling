"""Testes do cliente Apollo (WU-A3): mapeamento de status HTTP -> erros tipados.

Sem rede: usa httpx.MockTransport injetado. Cada status vira a degradação esperada
(Open-World): auth/credit/rate-limit/server nunca viram dado fabricado.
"""

from __future__ import annotations

import httpx
import pytest

from socialselling.skills.apollo_client import (
    ApolloAuthError,
    ApolloClient,
    ApolloCreditError,
    ApolloError,
    ApolloRateLimitError,
)


def _client_returning(status: int, json_body: dict[str, object] | None = None) -> ApolloClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=json_body or {})

    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport)
    return ApolloClient("fake-key", client=http)


def test_people_search_ok_returns_payload() -> None:
    client = _client_returning(200, {"people": [{"id": "p1"}]})
    out = client.people_search({"person_titles": ["founder"]})
    assert out == {"people": [{"id": "p1"}]}


def test_403_raises_auth_error() -> None:
    # Sem acesso à API no tier => provedor ausente, degrada para Tavily.
    client = _client_returning(403)
    with pytest.raises(ApolloAuthError):
        client.people_search({})


def test_402_raises_credit_error() -> None:
    client = _client_returning(402)
    with pytest.raises(ApolloCreditError):
        client.org_enrich(domain="acme.com")


def test_429_raises_rate_limit() -> None:
    client = _client_returning(429)
    with pytest.raises(ApolloRateLimitError):
        client.people_match({"id": "p1"})


def test_500_raises_apollo_error() -> None:
    client = _client_returning(500)
    with pytest.raises(ApolloError):
        client.people_search({})


def test_network_error_raises_apollo_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = ApolloClient("fake-key", client=http)
    with pytest.raises(ApolloError):
        client.people_search({})


def test_headers_carry_api_key() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(dict(request.headers))
        return httpx.Response(200, json={})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    ApolloClient("secret-123", client=http).people_search({})
    assert captured.get("x-api-key") == "secret-123"


def test_people_match_reveal_flags_in_body() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured.update(json.loads(request.content))
        return httpx.Response(200, json={})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    ApolloClient("k", client=http).people_match(
        {"id": "p1"}, reveal_personal_emails=True, reveal_phone_number=False
    )
    assert captured["reveal_personal_emails"] is True
    assert captured["reveal_phone_number"] is False
