"""Skill Apollo: cliente HTTP REST do 2o sensor firmografico (ADR-004).

Fronteira de rede do Apollo. Nos testes e substituida por um fake/transport mockado
(determinismo, zero rede). Mapeia status HTTP para erros tipados que o pipeline trata
como degradacao Open-World (nunca dado fabricado):
  401/403 -> ApolloAuthError  (chave sem acesso a API no tier; provedor fica ausente)
  402     -> ApolloCreditError (credito esgotado; reconcilia ledger)
  429     -> ApolloRateLimitError (backoff)
  5xx/rede-> ApolloError

So People Search (mixed_people/search) e gratuito. Org Enrich e People Match CONSOMEM
credito — nunca chamar sem orcamento reservado no ledger (ver ADR-004 §3).
"""

from __future__ import annotations

from typing import Any, Protocol

import httpx

_DEFAULT_BASE_URL = "https://api.apollo.io/api/v1"


class ApolloAuthError(Exception):
    """401/403 — chave invalida ou sem acesso a API neste tier."""


class ApolloCreditError(Exception):
    """402 — credito/limite do plano atingido (verdade do provedor)."""


class ApolloRateLimitError(Exception):
    """429 — rate limit da Apollo."""


class ApolloError(Exception):
    """Falha de rede ou 5xx da Apollo."""


class ApolloSearchClient(Protocol):
    """Contrato minimo do cliente Apollo (real ou fake)."""

    def people_search(
        self, filters: dict[str, Any], *, page: int = 1, per_page: int = 25
    ) -> dict[str, Any]: ...

    def org_enrich(
        self, *, domain: str | None = None, organization_name: str | None = None
    ) -> dict[str, Any]: ...

    def people_match(
        self,
        params: dict[str, Any],
        *,
        reveal_personal_emails: bool = False,
        reveal_phone_number: bool = False,
    ) -> dict[str, Any]: ...


class ApolloClient:
    """Cliente real da Apollo. Chave por injecao (nao toca env aqui).

    `client` (httpx.Client) e injetavel para testes com MockTransport (sem rede).
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = client

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------

    def people_search(
        self, filters: dict[str, Any], *, page: int = 1, per_page: int = 25
    ) -> dict[str, Any]:
        """Degrau 1 (0 credito): descoberta firmografica. Contato vem mascarado."""
        body: dict[str, Any] = {**filters, "page": page, "per_page": per_page}
        return self._post("/mixed_people/search", body)

    def org_enrich(
        self, *, domain: str | None = None, organization_name: str | None = None
    ) -> dict[str, Any]:
        """Degrau 2 (1 credito): firmografia precisa. So com orcamento reservado."""
        body: dict[str, Any] = {}
        if domain:
            body["domain"] = domain
        if organization_name:
            body["organization_name"] = organization_name
        return self._post("/organizations/enrich", body)

    def people_match(
        self,
        params: dict[str, Any],
        *,
        reveal_personal_emails: bool = False,
        reveal_phone_number: bool = False,
    ) -> dict[str, Any]:
        """Degrau 3 (1 credito + email/mobile): reveal de contato. So no top-N."""
        body: dict[str, Any] = {
            **params,
            "reveal_personal_emails": reveal_personal_emails,
            "reveal_phone_number": reveal_phone_number,
        }
        return self._post("/people/match", body)

    # ------------------------------------------------------------------
    # Transporte
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "accept": "application/json",
            "x-api-key": self._api_key,
        }

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        try:
            if self._client is not None:
                resp = self._client.post(url, json=body, headers=self._headers())
            else:
                resp = httpx.post(url, json=body, headers=self._headers(), timeout=self._timeout)
        except httpx.HTTPError as exc:  # timeout, conexao, etc.
            raise ApolloError(str(exc)) from exc
        return self._parse_status(resp)

    @staticmethod
    def _parse_status(resp: httpx.Response) -> dict[str, Any]:
        code = resp.status_code
        if code in (401, 403):
            raise ApolloAuthError(f"apollo auth/access denied ({code})")
        if code == 402:
            raise ApolloCreditError("apollo credit/plan limit reached (402)")
        if code == 429:
            raise ApolloRateLimitError("apollo rate-limited (429)")
        if code >= 500:
            raise ApolloError(f"apollo server error ({code})")
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data
