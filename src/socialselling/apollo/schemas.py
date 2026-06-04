"""Contratos de dados (wire) do sensor Apollo (Pydantic v2, `extra="forbid"`).

REGRA (CLAUDE.md §3.1): aqui ficam APENAS os contratos de I/O do Apollo. A
configuracao de runtime (`ApolloCfg`/`ApolloCapsCfg`) vive em `config.py`; a logica
de orquestracao (ladder, ledger) vive em seus proprios modulos. Ver ADR-004 e
`docs/specs/apollo-busca-enriquecimento-incremental-sdd.md` §4.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ApolloEndpoint(StrEnum):
    """Endpoints Apollo usados pela escada de enriquecimento, por custo de credito."""

    PEOPLE_SEARCH = "people_search"  # 0 credito (descoberta)
    ORG_ENRICH = "org_enrich"  # 1 data-credit (firmografia precisa)
    PEOPLE_MATCH = "people_match"  # 1 data + email/mobile (reveal de contato)


class ApolloPersonHit(BaseModel):
    """Normalizacao do item de People Search (subset estavel da resposta Apollo).

    Contato vem MASCARADO no tier gratuito; o reveal so ocorre no degrau 3
    (`people/match`). A empresa aninhada alimenta a triagem barata (poda sem Gemini).
    """

    model_config = ConfigDict(extra="forbid")

    apollo_id: str
    name: str
    title: str | None = None
    seniority: str | None = None
    linkedin_url: str | None = None
    # Empresa aninhada (firmografia que alimenta a triagem barata):
    organization_name: str | None = None
    organization_domain: str | None = None
    industry: str | None = None
    employee_count: int | None = Field(default=None, ge=0)
    location: str | None = None
    # Contato MASCARADO no tier gratuito; reveal so no degrau 3:
    email_status: str | None = None  # "verified" | "locked" | None
    email_masked: bool = True


class ApolloRevealResult(BaseModel):
    """Resultado do degrau 3 (reveal). `revealed=False` => Apollo nao tinha o dado
    (incerteza Open-World, NAO erro; nunca fabricar contato)."""

    model_config = ConfigDict(extra="forbid")

    apollo_id: str
    email: str | None = None
    phone: str | None = None
    revealed: bool = False
