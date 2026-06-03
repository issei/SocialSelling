"""M1 — Busca (Tavily): de ICPCriteria para evidências observadas (camada 1).

Determinístico dado (icp, cliente, cache, now, config). Toda não-determinação
(relógio, rede) é injetada. Degradação segue SDD v1.0 §1.4 (Open-World):
falha de query sem cache vira `ObservedEvidence(missing_evidence=True)`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from socialselling.contracts import ICPCriteria, ObservedEvidence
from socialselling.core.cache import JsonCache, query_hash
from socialselling.skills.tavily_client import (
    RateLimitError,
    SearchClient,
    TavilyError,
)


def generate_queries(icp: ICPCriteria, max_queries: int) -> list[str]:
    """Gera queries determinísticas a partir do ICP (firmográficos + tech obrigatória)."""
    tech = " ".join(icp.technographics.mandatory)
    country = icp.firmographics.geographies.country
    queries: list[str] = []
    for industry in icp.firmographics.industries[:max_queries]:
        query = f"{industry} {tech} company {country}".strip()
        queries.append(query)
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
) -> list[ObservedEvidence]:
    """Executa o M1: gera queries, consulta Tavily (com cache T-24h) e mapeia evidências."""
    evidences: list[ObservedEvidence] = []
    for query in generate_queries(icp, max_queries):
        payload = cache.get(query, now, cache_ttl_hours)
        if payload is None:
            try:
                payload = client.search(query, max_results, search_depth)
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
    return evidences
