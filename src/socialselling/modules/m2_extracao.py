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
    "Voce e um extrator de LEADS (empresarias fundadoras de servicos) e dados de "
    "contato. A partir dos resultados de busca abaixo, responda SOMENTE com JSON "
    "valido no formato:\n"
    '{"inferences":[{"company":{"normalized_name":str,"industry":str|null,'
    '"location":str|null,"website":str|null,"instagram_url":str|null,'
    '"linkedin_url":str|null,"email":str|null,"phone":str|null,"confidence":number},'
    '"people":[{"normalized_name":str,"role_title":str|null,"seniority":str|null,'
    '"confidence":number}],"derived_from":[evidence_id],"intent_signals":[token],'
    '"disqualifiers":[token],"persona":str,"confidence":number}]}\n'
    "Regras: confidence entre 0 e 1; derived_from lista os evidence_id usados; "
    "instagram_url SO se for um link de instagram.com; linkedin_url SO se for "
    "linkedin.com; email/phone apenas se EXPLICITOS no texto. Preencha so o que "
    "estiver EVIDENTE, use null quando nao houver — NUNCA invente.\n"
    "intent_signals e disqualifiers: liste APENAS tokens dos vocabularios abaixo que "
    "estiverem EVIDENTES no texto; se nenhum, use lista vazia.\n"
    'persona: classifique o LEAD em exatamente um de: "fundadora" (pessoa, mulher, '
    'fundadora/socia/CEO), "fundador" (pessoa, homem), "empresa" (conta/perfil de '
    'empresa ou marca, sem pessoa fundadora identificavel), "indefinido" (nao da para '
    "inferir). Use o nome e o conteudo para inferir o genero.\n\n"
)

_PERSONA_VALUES = {"fundadora", "fundador", "empresa", "indefinido"}


def build_prompt(
    evidences: list[ObservedEvidence],
    intent_vocab: list[str],
    disqualifier_vocab: list[str],
) -> str:
    """Prompt determinístico (campos estáveis; ignora captured_at)."""
    ordered = sorted(evidences, key=lambda e: e.evidence_id)
    lines: list[str] = [_PROMPT_HEADER]
    lines.append(f"VOCABULARIO intent_signals: {', '.join(intent_vocab)}")
    lines.append(f"VOCABULARIO disqualifiers: {', '.join(disqualifier_vocab)}\n")
    lines.append("Resultados de busca:")
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


def _clean_url(value: Any, *, must_contain: str | None = None) -> str | None:
    """Mantém a URL só se for http(s) e (opcionalmente) contiver um domínio esperado."""
    text = _as_str_or_none(value)
    if text is None or not text.lower().startswith(("http://", "https://")):
        return None
    if must_contain is not None and must_contain not in text.lower():
        return None
    return text


def _clean_email(value: Any) -> str | None:
    text = _as_str_or_none(value)
    if text is None or "@" not in text or "." not in text.split("@")[-1]:
        return None
    return text


def _filter_vocab(values: Any, vocab: list[str]) -> list[str]:
    """Mantém só tokens conhecidos do vocabulário, sem repetição e em ordem estável."""
    allowed = set(vocab)
    out: list[str] = []
    for raw_token in values or []:
        token = str(raw_token).strip().lower()
        if token in allowed and token not in out:
            out.append(token)
    return out


def _parse_inferences(
    raw: dict[str, Any],
    evidences: list[ObservedEvidence],
    intent_vocab: list[str],
    disqualifier_vocab: list[str],
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
            location=_as_str_or_none(comp.get("location")),
            website=_clean_url(comp.get("website")),
            instagram_url=_clean_url(comp.get("instagram_url"), must_contain="instagram.com"),
            linkedin_url=_clean_url(comp.get("linkedin_url"), must_contain="linkedin.com"),
            email=_clean_email(comp.get("email")),
            phone=_as_str_or_none(comp.get("phone")),
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
        persona = str(item.get("persona", "")).strip().lower()
        if persona not in _PERSONA_VALUES:
            persona = "indefinido"
        out.append(
            Inference(
                company=company,
                people=people,
                derived_from=derived,
                confidence=_clamp01(float(item.get("confidence", 0.5))),
                intent_signals=_filter_vocab(item.get("intent_signals"), intent_vocab),
                disqualifiers=_filter_vocab(item.get("disqualifiers"), disqualifier_vocab),
                persona=persona,
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
    intent_vocab: list[str],
    disqualifier_vocab: list[str],
) -> list[Inference]:
    """Executa o M2: monta o prompt, consulta Gemini (com cache T-24h) e mapeia inferências."""
    observed = [ev for ev in evidences if not ev.missing_evidence]
    if not observed:
        return []
    prompt = build_prompt(observed, intent_vocab, disqualifier_vocab)
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
    return _parse_inferences(payload, observed, intent_vocab, disqualifier_vocab)
