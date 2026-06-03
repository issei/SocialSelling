"""M2 — Extração (Gemini): de evidências observadas para inferências (camada 2).

Transforma `ObservedEvidence` (camada 1) em `Inference` (camada 2) — isolamento
semântico estrito. Toda inferência carrega `confidence` e `derived_from`
(rastreabilidade Evidence→Inference). Cache de cognição (T-24h) + degradação.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from socialselling.contracts import (
    CompanyEntity,
    Inference,
    ObservedEvidence,
    PersonEntity,
)
from socialselling.core.cache import JsonCache, query_hash
from socialselling.skills.gemini_client import (
    CognitionClient,
    GeminiError,
    RateLimitError,
)

_PROMPT_HEADER = (
    "Voce e um extrator de entidades. A partir dos resultados de busca abaixo, "
    "identifique empresas e pessoas-chave. Responda SOMENTE com JSON valido no formato:\n"
    '{"inferences":[{"company":{"normalized_name":str,"domain":str|null,'
    '"employee_count":int|null,"industry":str|null,"technologies":[str],'
    '"confidence":number},"people":[{"normalized_name":str,"role_title":str|null,'
    '"seniority":str|null,"confidence":number}],"derived_from":[evidence_id],'
    '"confidence":number}]}\n'
    "confidence e um numero entre 0 e 1. derived_from lista os evidence_id usados.\n\n"
)


def build_prompt(evidences: list[ObservedEvidence]) -> str:
    """Prompt determinístico (campos estáveis; ignora captured_at)."""
    ordered = sorted(evidences, key=lambda e: e.evidence_id)
    lines: list[str] = [_PROMPT_HEADER, "Resultados de busca:"]
    for ev in ordered:
        if ev.missing_evidence:
            continue
        snippet = ev.snippet[:800]
        lines.append(
            f"- evidence_id={ev.evidence_id} | titulo={ev.title} | "
            f"url={ev.source_url} | trecho={snippet}"
        )
    return "\n".join(lines)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _as_int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    return None


def _as_str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_inferences(
    raw: dict[str, Any], evidences: list[ObservedEvidence]
) -> list[Inference]:
    valid_ids = {ev.evidence_id for ev in evidences}
    out: list[Inference] = []
    for item in raw.get("inferences", []):
        comp = item.get("company", {}) or {}
        name = str(comp.get("normalized_name", "")).strip()
        if not name:
            continue
        company = CompanyEntity(
            company_id=query_hash(name.lower())[:16],
            normalized_name=name,
            domain=_as_str_or_none(comp.get("domain")),
            employee_count=_as_int_or_none(comp.get("employee_count")),
            industry=_as_str_or_none(comp.get("industry")),
            technologies=[str(t) for t in comp.get("technologies", [])],
            confidence=_clamp01(float(comp.get("confidence", 0.5))),
        )
        people: list[PersonEntity] = []
        for person in item.get("people", []):
            pname = str(person.get("normalized_name", "")).strip()
            if not pname:
                continue
            people.append(
                PersonEntity(
                    person_id=query_hash(f"{name.lower()}|{pname.lower()}")[:16],
                    normalized_name=pname,
                    role_title=_as_str_or_none(person.get("role_title")),
                    seniority=_as_str_or_none(person.get("seniority")),
                    confidence=_clamp01(float(person.get("confidence", 0.5))),
                )
            )
        derived = [eid for eid in item.get("derived_from", []) if eid in valid_ids]
        out.append(
            Inference(
                company=company,
                people=people,
                derived_from=derived,
                confidence=_clamp01(float(item.get("confidence", 0.5))),
            )
        )
    return out


def run_m2(
    evidences: list[ObservedEvidence],
    *,
    client: CognitionClient,
    cache: JsonCache,
    now: datetime,
    cache_ttl_hours: int,
) -> list[Inference]:
    """Executa o M2: monta o prompt, consulta Gemini (com cache T-24h) e mapeia inferências."""
    observed = [ev for ev in evidences if not ev.missing_evidence]
    if not observed:
        return []
    prompt = build_prompt(observed)
    payload = cache.get(prompt, now, cache_ttl_hours)
    if payload is None:
        try:
            payload = client.generate_json(prompt)
            cache.put(prompt, payload, now)
        except (RateLimitError, GeminiError):
            stale = cache.get_any(prompt)
            if stale is None:
                return []
            payload = stale
    return _parse_inferences(payload, observed)
