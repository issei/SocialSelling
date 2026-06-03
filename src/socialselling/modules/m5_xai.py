"""M5 — Explicação (XAI): traduz score + inferência num payload auditável.

Módulo PURO e determinístico (sem rede) — preferimos regras explícitas a uma
chamada de LLM para garantir reexecução byte-idêntica e custo zero no PoC.
Produz `XAIPayload` com drivers positivos/negativos e sinais ausentes
(Open-World: o que NÃO foi observado também é informação).
"""

from __future__ import annotations

from socialselling.contracts import (
    Driver,
    ICPCriteria,
    Inference,
    ProspectScore,
    XAIPayload,
)


def _norm(values: list[str]) -> set[str]:
    return {v.strip().lower() for v in values if v.strip()}


def run_m5(
    score: ProspectScore,
    inference: Inference,
    icp: ICPCriteria,
    *,
    degraded_mode: bool = False,
) -> XAIPayload:
    """Gera a explicação estruturada de um prospect."""
    company = inference.company
    have = _norm(company.technologies)
    mandatory = _norm(icp.technographics.mandatory)

    positive: list[Driver] = []
    negative: list[Driver] = []
    missing: list[str] = []

    matched = sorted(mandatory & have)
    if matched:
        positive.append(
            Driver(
                driver="TECH_MATCH",
                impact=f"+{score.fit:.2f}",
                text=f"Usa tecnologias exigidas pelo ICP: {', '.join(matched)}.",
            )
        )
    missing_tech = sorted(mandatory - have)
    if missing_tech:
        missing.append(f"tecnologias mandatórias não confirmadas: {', '.join(missing_tech)}")

    if score.intent > 0:
        positive.append(
            Driver(
                driver="INTENT_MOMENTUM",
                impact=f"+{score.intent:.2f}",
                text=f"Convergência de {len(inference.derived_from)} evidências independentes.",
            )
        )

    if not company.industry:
        missing.append("indústria não identificada")
    if not inference.people:
        missing.append("nenhuma pessoa-chave identificada")

    if not score.hard_filter_passed:
        negative.append(
            Driver(
                driver="EXCLUDED_TECH",
                impact="-",
                text="Tecnologia proibida pelo ICP detectada — lead descartado pelo hard filter.",
            )
        )
    if score.confidence < 0.5:
        negative.append(
            Driver(
                driver="LOW_CONFIDENCE",
                impact="-",
                text=f"Confiança baixa nas evidências ({score.confidence:.2f}).",
            )
        )

    return XAIPayload(
        company_id=score.company_id,
        final_p_score=score.p_score,
        positive_signals=positive,
        negative_signals=negative,
        missing_signals=missing,
        degraded_mode=degraded_mode,
    )
