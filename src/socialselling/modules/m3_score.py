"""M3 — Score: de inferências para scores de prospect (camada 3).

Módulo PURO e determinístico (sem rede). Fórmula linear documentada do PoC:

    P = (w_fit * Fit + w_intent * Intent) * (Confianca ^ confidence_exponent)

- Fit    = w_fit_tech * tech_match + w_fit_industry * industry_match  (∈ [0,1])
- Intent = soma dos `prior` das hipóteses que DISPARAM, ou seja, cujas `surface_signals`
           intersectam os `intent_signals` detectados na inferência (limitado a 1.0).
           Ausência de sinal de timing ⇒ Intent = 0 (Open-World: não inventa momentum).
- Hard filter (zera o lead): tecnologia proibida pelo ICP OU qualquer `disqualifier`
           detectado (founder solo, negócio imaturo, retração, sem decisora, fora de setor).
"""

from __future__ import annotations

from socialselling.contracts import (
    HypothesisCatalog,
    ICPCriteria,
    Inference,
    ProspectScore,
)


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


def _intent_from_hypotheses(inference: Inference, catalog: HypothesisCatalog) -> float:
    """Soma dos priors das hipóteses cujas surface_signals batem com os intent_signals."""
    detected = _norm_set(inference.intent_signals)
    if not detected:
        return 0.0
    total = 0.0
    for hypothesis in catalog.hypotheses:
        if _norm_set(hypothesis.surface_signals) & detected:
            total += hypothesis.prior
    return min(1.0, total)


def _persona_fit(inference: Inference, persona_weights: dict[str, float]) -> float:
    """Multiplicador de aderência da persona (homem→0, empresa↓, fundadora cheio)."""
    persona = inference.persona or "indefinido"
    default = persona_weights.get("indefinido", 0.5)
    return persona_weights.get(persona, default)


def _score_one(
    inference: Inference,
    icp: ICPCriteria,
    catalog: HypothesisCatalog,
    persona_weights: dict[str, float],
    *,
    w_fit: float,
    w_intent: float,
    confidence_exponent: float,
    w_fit_tech: float,
    w_fit_industry: float,
) -> ProspectScore:
    hard_ok = not _has_excluded_tech(inference, icp) and not inference.disqualifiers
    fit = w_fit_tech * _tech_match(inference, icp) + w_fit_industry * _industry_match(
        inference, icp
    )
    intent = _intent_from_hypotheses(inference, catalog)
    confidence = inference.confidence
    persona_fit = _persona_fit(inference, persona_weights)
    if hard_ok:
        base = (w_fit * fit + w_intent * intent) * (confidence**confidence_exponent)
        p_score = base * persona_fit
    else:
        p_score = 0.0
    return ProspectScore(
        company_id=inference.company.company_id,
        fit=round(fit, 9),
        intent=round(intent, 9),
        confidence=round(confidence, 9),
        persona_fit=round(persona_fit, 9),
        p_score=round(p_score, 9),
        hard_filter_passed=hard_ok,
    )


def run_m3(
    inferences: list[Inference],
    icp: ICPCriteria,
    catalog: HypothesisCatalog,
    *,
    w_fit: float,
    w_intent: float,
    confidence_exponent: float,
    w_fit_tech: float,
    w_fit_industry: float,
    persona_weights: dict[str, float],
) -> list[ProspectScore]:
    """Calcula o ProspectScore de cada inferência (ordem de entrada preservada)."""
    return [
        _score_one(
            inf,
            icp,
            catalog,
            persona_weights,
            w_fit=w_fit,
            w_intent=w_intent,
            confidence_exponent=confidence_exponent,
            w_fit_tech=w_fit_tech,
            w_fit_industry=w_fit_industry,
        )
        for inf in inferences
    ]
