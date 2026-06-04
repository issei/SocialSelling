"""Normalizacao Apollo: resposta crua -> ApolloPersonHit -> formato canonico (ADR-004).

O formato canonico e o MESMO do Tavily (`{"results":[{title,url,content,score}]}`),
para que `m1_busca._map_result` e o prompt do M2 funcionem SEM alteracao. A firmografia
estruturada vai no `content` (ordem de campos FIXA = determinismo) e e lida tambem pela
triagem barata. Camadas preservadas: o resultado vira ObservedEvidence, nunca inferencia.
"""

from __future__ import annotations

from typing import Any

from socialselling.apollo.schemas import (
    ApolloOrgInfo,
    ApolloPersonHit,
    ApolloRevealResult,
)

# Marcador que a Apollo usa quando o e-mail NAO foi revelado (tier gratuito).
_EMAIL_LOCKED_MARKER = "email_not_unlocked"


def _real_email(value: Any) -> str | None:
    if not isinstance(value, str) or "@" not in value or _EMAIL_LOCKED_MARKER in value:
        return None
    return value


def parse_reveal(payload: dict[str, Any], *, apollo_id: str = "") -> ApolloRevealResult:
    """Resposta de people/match -> ApolloRevealResult (degrau 3).

    `revealed=False` quando a Apollo nao trouxe e-mail/telefone reais — incerteza
    Open-World, NUNCA dado fabricado.
    """
    person = payload.get("person") or {}
    email = _real_email(person.get("email"))
    phone: str | None = None
    phones = person.get("phone_numbers")
    if isinstance(phones, list) and phones and isinstance(phones[0], dict):
        raw = phones[0].get("raw_number") or phones[0].get("sanitized_number")
        phone = str(raw) if raw else None
    return ApolloRevealResult(
        apollo_id=apollo_id or str(person.get("id") or ""),
        email=email,
        phone=phone,
        revealed=bool(email or phone),
    )


def _coalesce_name(person: dict[str, Any]) -> str:
    name = person.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    first = str(person.get("first_name") or "").strip()
    last = str(person.get("last_name") or "").strip()
    return " ".join(p for p in (first, last) if p)


def _is_masked(email: Any, email_status: Any) -> bool:
    if not email or not isinstance(email, str):
        return True
    if _EMAIL_LOCKED_MARKER in email:
        return True
    return email_status not in ("verified", "extrapolated")


def parse_person(person: dict[str, Any]) -> ApolloPersonHit:
    """Mapeia um item bruto de People Search para o contrato tipado (defensivo)."""
    org = person.get("organization") or {}
    employees = org.get("estimated_num_employees")
    return ApolloPersonHit(
        apollo_id=str(person.get("id") or ""),
        name=_coalesce_name(person),
        title=person.get("title"),
        seniority=person.get("seniority"),
        linkedin_url=person.get("linkedin_url"),
        organization_name=org.get("name"),
        organization_domain=org.get("primary_domain") or org.get("website_url"),
        industry=org.get("industry"),
        employee_count=int(employees) if isinstance(employees, int) else None,
        location=person.get("city") or person.get("state") or person.get("country"),
        email_status=person.get("email_status"),
        email_masked=_is_masked(person.get("email"), person.get("email_status")),
    )


def parse_people_search(payload: dict[str, Any]) -> list[ApolloPersonHit]:
    """Extrai a lista de pessoas de uma resposta de People Search (chave `people`)."""
    people = payload.get("people")
    if not isinstance(people, list):
        return []
    return [parse_person(p) for p in people if isinstance(p, dict)]


def person_hit_to_canonical(hit: ApolloPersonHit) -> dict[str, Any]:
    """ApolloPersonHit -> item canonico {title,url,content,score} (formato Tavily).

    `content` carrega a firmografia em ordem FIXA (determinismo). `score` alto (0.9):
    dado de vendor estruturado e mais confiavel que snippet de busca aberta.
    """
    employees = hit.employee_count if hit.employee_count is not None else "—"
    facts = [
        f"empresa: {hit.organization_name or '—'}",
        f"setor: {hit.industry or '—'}",
        f"funcionarios: {employees}",
        f"cargo: {hit.title or '—'}",
        f"local: {hit.location or '—'}",
    ]
    if hit.organization_domain:
        url = f"https://{hit.organization_domain}"
    else:
        url = hit.linkedin_url or ""
    title = f"{hit.name} — {hit.organization_name or ''}".strip(" —")
    return {
        "title": title,
        "url": url,
        "content": " | ".join(facts),
        "score": 0.9,
    }


def to_canonical_results(hits: list[ApolloPersonHit]) -> dict[str, Any]:
    """Lista de hits -> payload canonico Tavily (`{"results": [...]}`) p/ o M1 mapear."""
    return {"results": [person_hit_to_canonical(h) for h in hits]}


def parse_org_enrich(payload: dict[str, Any]) -> ApolloOrgInfo:
    """Resposta de organizations/enrich -> ApolloOrgInfo (degrau 2). Defensivo."""
    org = payload.get("organization") or {}
    employees = org.get("estimated_num_employees")
    return ApolloOrgInfo(
        industry=org.get("industry"),
        employee_count=int(employees) if isinstance(employees, int) else None,
        domain=org.get("primary_domain") or org.get("website_url"),
    )
