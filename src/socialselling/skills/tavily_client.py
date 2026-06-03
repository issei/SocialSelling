"""Skill de busca: cliente HTTP da Tavily (sensor exclusivo do M1).

Esta é a única fronteira de rede do M1. Nos testes é substituída por um
fake que devolve fixtures gravadas (determinismo).
"""

from __future__ import annotations

from typing import Any, Protocol

import httpx

_DEFAULT_BASE_URL = "https://api.tavily.com"


class RateLimitError(Exception):
    """HTTP 429 da Tavily."""


class TavilyError(Exception):
    """Falha de rede ou 5xx da Tavily."""


class SearchClient(Protocol):
    """Contrato mínimo de um cliente de busca (real ou fake)."""

    def search(self, query: str, max_results: int, search_depth: str) -> dict[str, Any]:
        ...


class TavilyClient:
    """Cliente real da Tavily. Lê a chave de API por injeção (não toca env aqui)."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float = 20.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def search(self, query: str, max_results: int, search_depth: str) -> dict[str, Any]:
        payload = {
            "api_key": self._api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
        }
        try:
            resp = httpx.post(
                f"{self._base_url}/search", json=payload, timeout=self._timeout
            )
        except httpx.HTTPError as exc:  # timeout, conexão, etc.
            raise TavilyError(str(exc)) from exc
        if resp.status_code == 429:
            raise RateLimitError("tavily rate-limited (429)")
        if resp.status_code >= 500:
            raise TavilyError(f"tavily server error ({resp.status_code})")
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data
