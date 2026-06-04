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

    if score.intent > 0 and inference.intent_signals:
        positive.append(
            Driver(
                driver="INTENT_TIMING",
                impact=f"+{score.intent:.2f}",
                text=f"Sinais de timing detectados: {', '.join(sorted(inference.intent_signals))}.",
            )
        )
    elif not inference.intent_signals:
        missing.append("nenhum sinal de timing/intenção detectado")

    if not company.industry:
        missing.append("indústria não identificada")
    if not inference.people:
        missing.append("nenhuma pessoa-chave identificada")

    for disqualifier in sorted(inference.disqualifiers):
        negative.append(
            Driver(
                driver="DISQUALIFIER",
                impact="-",
                text=f"Desqualificador detectado: {disqualifier} — lead descartado.",
            )
        )
    if not score.hard_filter_passed and not inference.disqualifiers:
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

    persona = inference.persona or "indefinido"
    if persona == "fundadora":
        positive.append(Driver(driver="PERSONA", impact="x1.00", text="Persona alvo: fundadora."))
    elif score.persona_fit <= 0.0:
        negative.append(
            Driver(
                driver="PERSONA",
                impact="x0",
                text=f"Persona fora do alvo ({persona}) — fora do público de fundadoras.",
            )
        )
    else:
        missing.append(
            f"persona '{persona}' fora do ideal (fundadora) — peso {score.persona_fit:.2f}"
        )

    return XAIPayload(
        company_id=score.company_id,
        final_p_score=score.p_score,
        positive_signals=positive,
        negative_signals=negative,
        missing_signals=missing,
        degraded_mode=degraded_mode,
    )
