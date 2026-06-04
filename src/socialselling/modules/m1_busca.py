"""M1 — Busca (Tavily): de ICPCriteria para evidências observadas (camada 1).

Determinístico dado (icp, cliente, cache, now, config). Toda não-determinação
(relógio, rede) é injetada. Degradação segue SDD v1.0 §1.4 (Open-World):
falha de query sem cache vira `ObservedEvidence(missing_evidence=True)`.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from socialselling.apollo.ladder import icp_to_people_filters
from socialselling.apollo.normalize import parse_people_search, to_canonical_results
from socialselling.contracts import ICPCriteria, ObservedEvidence
from socialselling.core.cache import JsonCache, query_hash
from socialselling.skills.apollo_client import (
    ApolloAuthError,
    ApolloCreditError,
    ApolloError,
    ApolloRateLimitError,
    ApolloSearchClient,
)
from socialselling.skills.tavily_client import (
    RateLimitError,
    SearchClient,
    TavilyError,
)

_APOLLO_ERRORS = (ApolloAuthError, ApolloCreditError, ApolloRateLimitError, ApolloError)

_COUNTRY_NAMES = {"BR": "Brasil"}


def generate_queries(icp: ICPCriteria, max_queries: int, persona_term: str = "") -> list[str]:
    """Gera queries determinísticas (PT-BR, orientadas à persona) a partir do ICP.

    Ex.: industries=[consultoria, advocacia], persona='fundadora', country=BR →
    ['consultoria fundadora Brasil', 'advocacia fundadora Brasil']. O viés para
    perfis sociais (Instagram/LinkedIn) é aplicado via `include_domains` no M1.
    """
    country = icp.firmographics.geographies.country
    country_name = _COUNTRY_NAMES.get(country.upper(), country)
    persona = persona_term.strip()
    queries: list[str] = []
    for industry in icp.firmographics.industries[:max_queries]:
        parts = [industry.strip(), persona, country_name]
        queries.append(" ".join(p for p in parts if p))
    return queries


def is_degraded(evidences: list[ObservedEvidence]) -> bool:
    """True se qualquer evidência marca ausência de sinal (modo degradado)."""
    return any(ev.missing_evidence for ev in evidences)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _map_result(query: str, result: dict[str, Any], now: datetime) -> ObservedEvidence:
    url = str(result.get("url", ""))
    score = result.get("score", 0.5)
    return ObservedEvidence(
        evidence_id=query_hash(f"{query}|{url}")[:16],
        query=query,
        source_url=url,
        title=str(result.get("title", "")),
        snippet=str(result.get("content", "")),
        captured_at=now.isoformat(),
        source_trust=_clamp01(float(score)),
        missing_evidence=False,
    )


def _missing(query: str, now: datetime) -> ObservedEvidence:
    return ObservedEvidence(
        evidence_id=query_hash(f"{query}|MISSING")[:16],
        query=query,
        source_url="",
        title="",
        snippet="",
        captured_at=now.isoformat(),
        source_trust=0.0,
        missing_evidence=True,
    )


def _apollo_cache_key(filters: dict[str, Any]) -> str:
    """Chave de cache estável para a descoberta Apollo (hash canônico dos filtros)."""
    return "apollo:people:" + query_hash(json.dumps(filters, sort_keys=True))[:16]


def run_apollo_discovery(
    icp: ICPCriteria,
    *,
    apollo_client: ApolloSearchClient,
    cache: JsonCache,
    now: datetime,
    persona_term: str = "",
    per_page: int = 25,
    cache_ttl_hours: int = 24,
) -> list[ObservedEvidence]:
    """Degrau 1 Apollo (0 crédito): People Search → evidências canônicas.

    Open-World: qualquer falha do Apollo (403 sem-API / 429 / crédito / rede) faz o
    provedor ficar AUSENTE (retorna []), nunca quebra o M1 — o Tavily cobre a descoberta.
    Reusa o cache (T-24h) e o `_map_result` canônico → sem mudança em M2.
    """
    filters = icp_to_people_filters(icp, persona_term=persona_term)
    key = _apollo_cache_key(filters)
    payload = cache.get(key, now, cache_ttl_hours)
    if payload is None:
        try:
            payload = apollo_client.people_search(filters, per_page=per_page)
            cache.put(key, payload, now)
        except _APOLLO_ERRORS:
            stale = cache.get_any(key)
            if stale is None:
                return []  # provedor ausente; degrada para o Tavily, sem fabricar dado
            payload = stale
    hits = parse_people_search(payload)
    canonical = to_canonical_results(hits)
    return [_map_result(key, result, now) for result in canonical.get("results", [])]


def run_m1(
    icp: ICPCriteria,
    *,
    client: SearchClient,
    cache: JsonCache,
    now: datetime,
    max_queries: int,
    max_results: int,
    search_depth: str,
    cache_ttl_hours: int,
    persona_term: str = "",
    include_domains: list[str] | None = None,
    apollo_client: ApolloSearchClient | None = None,
    apollo_per_page: int = 25,
) -> list[ObservedEvidence]:
    """Executa o M1: gera queries, consulta Tavily (cache T-24h) e mapeia evidências.

    Se `apollo_client` for fornecido (opt-in, ADR-004), agrega a descoberta firmográfica
    do Apollo (degrau 1, 0 crédito) às evidências do Tavily. Sem ele, comportamento
    byte-idêntico ao atual.
    """
    evidences: list[ObservedEvidence] = []
    for query in generate_queries(icp, max_queries, persona_term):
        payload = cache.get(query, now, cache_ttl_hours)
        if payload is None:
            try:
                payload = client.search(query, max_results, search_depth, include_domains)
                cache.put(query, payload, now)
            except (RateLimitError, TavilyError):
                stale = cache.get_any(query)
                if stale is None:
                    evidences.append(_missing(query, now))
                    continue
                payload = stale
        results = payload.get("results", [])
        if not results:
            evidences.append(_missing(query, now))
            continue
        for result in results:
            evidences.append(_map_result(query, result, now))
    if apollo_client is not None:
        evidences += run_apollo_discovery(
            icp,
            apollo_client=apollo_client,
            cache=cache,
            now=now,
            persona_term=persona_term,
            per_page=apollo_per_page,
            cache_ttl_hours=cache_ttl_hours,
        )
    return evidences
