"""M3 — Score: de inferências para scores de prospect (camada 3).

Módulo PURO e determinístico (sem rede). Fórmula linear documentada do PoC:

    P = (w_fit * Fit + w_intent * Intent) * (Confianca ^ confidence_exponent)

- Fit   = w_fit_tech * tech_match + w_fit_industry * industry_match  (∈ [0,1])
- Intent= proxy do PoC = min(1, |derived_from| / intent_evidence_norm) (placeholder;
          um Intent Worker dedicado entra na V1).
- Hard filter: tecnologia proibida pelo ICP zera o lead (hard_filter_passed=False, P=0).
"""

from __future__ import annotations

from socialselling.contracts import ICPCriteria, Inference, ProspectScore


def _norm_set(values: list[str]) -> set[str]:
    return {v.strip().lower() for v in values if v.strip()}


def _tech_match(inference: Inference, icp: ICPCriteria) -> float:
    mandatory = _norm_set(icp.technographics.mandatory)
    if not mandatory:
        return 1.0
    have = _norm_set(inference.company.technologies)
    return len(mandatory & have) / len(mandatory)


def _industry_match(inference: Inference, icp: ICPCriteria) -> float:
    industry = (inference.company.industry or "").strip().lower()
    if not industry:
        return 0.0
    for wanted in _norm_set(icp.firmographics.industries):
        if wanted in industry or industry in wanted:
            return 1.0
    return 0.0


def _has_excluded_tech(inference: Inference, icp: ICPCriteria) -> bool:
    excluded = _norm_set(icp.technographics.excluded)
    return bool(excluded & _norm_set(inference.company.technologies))


def _score_one(
    inference: Inference,
    icp: ICPCriteria,
    *,
    w_fit: float,
    w_intent: float,
    confidence_exponent: float,
    w_fit_tech: float,
    w_fit_industry: float,
    intent_evidence_norm: int,
) -> ProspectScore:
    hard_ok = not _has_excluded_tech(inference, icp)
    fit = w_fit_tech * _tech_match(inference, icp) + w_fit_industry * _industry_match(
        inference, icp
    )
    norm = max(1, intent_evidence_norm)
    intent = min(1.0, len(inference.derived_from) / norm)
    confidence = inference.confidence
    if hard_ok:
        p_score = (w_fit * fit + w_intent * intent) * (confidence**confidence_exponent)
    else:
        p_score = 0.0
    return ProspectScore(
        company_id=inference.company.company_id,
        fit=round(fit, 9),
        intent=round(intent, 9),
        confidence=round(confidence, 9),
        p_score=round(p_score, 9),
        hard_filter_passed=hard_ok,
    )


def run_m3(
    inferences: list[Inference],
    icp: ICPCriteria,
    *,
    w_fit: float,
    w_intent: float,
    confidence_exponent: float,
    w_fit_tech: float,
    w_fit_industry: float,
    intent_evidence_norm: int,
) -> list[ProspectScore]:
    """Calcula o ProspectScore de cada inferência (ordem de entrada preservada)."""
    return [
        _score_one(
            inf,
            icp,
            w_fit=w_fit,
            w_intent=w_intent,
            confidence_exponent=confidence_exponent,
            w_fit_tech=w_fit_tech,
            w_fit_industry=w_fit_industry,
            intent_evidence_norm=intent_evidence_norm,
        )
        for inf in inferences
    ]
