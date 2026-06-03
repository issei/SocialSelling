"""M4 — Ranking: ordena scores de prospect de forma determinística.

Módulo PURO. Ordena por `p_score` decrescente com tie-break ESTÁVEL por
`company_id` (ascendente), garantindo reexecução byte-idêntica.

Nota de design: o `RankedProspect` (que inclui o XAIPayload) é montado pelo
orquestrador (M6) após o M5. O M4 apenas estabelece a ordem dos scores.
"""

from __future__ import annotations

from socialselling.contracts import ProspectScore


def run_m4(scores: list[ProspectScore]) -> list[ProspectScore]:
    """Ordena por p_score desc; empates por company_id asc (tie-break estável)."""
    return sorted(scores, key=lambda s: (-s.p_score, s.company_id))
