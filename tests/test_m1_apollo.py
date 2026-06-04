"""Testes do plug Apollo no M1 (WU-A4b): agregação Tavily+Apollo, degradação, paridade.

Sem rede: fakes inline para Tavily e Apollo. Apollo é opt-in e estritamente aditivo.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from socialselling.contracts import ICPCriteria
from socialselling.core.cache import JsonCache
from socialselling.modules.m1_busca import run_m1
from socialselling.skills.apollo_client import ApolloAuthError

_ROOT = Path(__file__).resolve().parents[1]
_NOW = datetime(2026, 6, 4, 10, 0, 0)


def build_people_payload(people: list[dict[str, Any]]) -> dict[str, Any]:
    """Envelopa uma lista de pessoas no formato de resposta do People Search."""
    return {"people": people}


def _icp() -> ICPCriteria:
    raw = json.loads((_ROOT / "config" / "icp_criteria.talita.json").read_text(encoding="utf-8"))
    return ICPCriteria.model_validate(raw)


class _FakeTavily:
    def search(
        self,
        query: str,
        max_results: int,
        search_depth: str,
        include_domains: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "results": [{"title": "T", "url": "https://t.example", "content": "x", "score": 0.5}]
        }


class _FakeApollo:
    def __init__(self, payload: dict[str, Any] | Exception) -> None:
        self._payload = payload

    def people_search(
        self, filters: dict[str, Any], *, page: int = 1, per_page: int = 25
    ) -> dict[str, Any]:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload

    def org_enrich(self, **kw: Any) -> dict[str, Any]:  # pragma: no cover - não usado aqui
        return {}

    def people_match(self, params: dict[str, Any], **kw: Any) -> dict[str, Any]:  # pragma: no cover
        return {}


def test_apollo_ausente_mantem_paridade(tmp_path: Path) -> None:
    cache = JsonCache(tmp_path / "cache")
    evid = run_m1(
        _icp(),
        client=_FakeTavily(),
        cache=cache,
        now=_NOW,
        max_queries=2,
        max_results=5,
        search_depth="basic",
        cache_ttl_hours=24,
    )
    # Sem apollo_client => só evidências do Tavily (uma por query gerada).
    assert all(not e.missing_evidence for e in evid)
    assert all("apollo:people:" not in e.query for e in evid)


def test_apollo_agrega_evidencias(tmp_path: Path) -> None:
    cache = JsonCache(tmp_path / "cache")
    payload = build_people_payload(
        [
            {
                "id": "a1",
                "name": "Talita",
                "organization": {"name": "Acme", "industry": "consultoria"},
            }
        ]
    )
    evid = run_m1(
        _icp(),
        client=_FakeTavily(),
        cache=cache,
        now=_NOW,
        max_queries=1,
        max_results=5,
        search_depth="basic",
        cache_ttl_hours=24,
        apollo_client=_FakeApollo(payload),
    )
    apollo_evid = [e for e in evid if e.query.startswith("apollo:people:")]
    assert len(apollo_evid) == 1
    assert "Acme" in apollo_evid[0].title
    assert "consultoria" in apollo_evid[0].snippet  # firmografia no content canônico


def test_apollo_falha_degrada_sem_quebrar(tmp_path: Path) -> None:
    cache = JsonCache(tmp_path / "cache")
    evid = run_m1(
        _icp(),
        client=_FakeTavily(),
        cache=cache,
        now=_NOW,
        max_queries=1,
        max_results=5,
        search_depth="basic",
        cache_ttl_hours=24,
        apollo_client=_FakeApollo(ApolloAuthError("403")),
    )
    # Apollo 403 (sem API no tier) => provedor ausente; Tavily ainda entrega.
    assert any(e.query.startswith("apollo:people:") for e in evid) is False
    assert any(not e.missing_evidence for e in evid)  # evidência do Tavily presente


def test_apollo_determinismo(tmp_path: Path) -> None:
    payload = build_people_payload([{"id": "a1", "name": "Ana", "organization": {"name": "X"}}])
    a = run_m1(
        _icp(),
        client=_FakeTavily(),
        cache=JsonCache(tmp_path / "c1"),
        now=_NOW,
        max_queries=1,
        max_results=5,
        search_depth="basic",
        cache_ttl_hours=24,
        apollo_client=_FakeApollo(payload),
    )
    b = run_m1(
        _icp(),
        client=_FakeTavily(),
        cache=JsonCache(tmp_path / "c2"),
        now=_NOW,
        max_queries=1,
        max_results=5,
        search_depth="basic",
        cache_ttl_hours=24,
        apollo_client=_FakeApollo(payload),
    )
    assert [e.evidence_id for e in a] == [e.evidence_id for e in b]
