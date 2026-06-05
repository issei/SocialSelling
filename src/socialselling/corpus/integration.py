"""Integração do corpus acumulativo com o pipeline (ADR-006).

Funções determinísticas que ligam os `LeadCard` do run ao `CorpusStore` persistente:
- `accumulate`: upsert idempotente de cada card por `company_id` (entity_id).
- `ranked_view`: projeção do corpus INTEIRO re-ranqueada (-p_score, company_id), com
  `rank` recomputado e teto de EXIBIÇÃO. É aqui que "volume acumula entre runs".

Sem rede. Relógio injetado. Camadas preservadas (opera sobre LeadCard, camada de saída).
"""

from __future__ import annotations

from datetime import datetime

from socialselling.contracts import LeadCard
from socialselling.corpus.store import CorpusStore


def accumulate(store: CorpusStore, cards: list[LeadCard], now: datetime) -> None:
    """Upsert de cada card no corpus (chave = company_id do score). Idempotente."""
    for card in cards:
        store.upsert(card.score.company_id, card.model_dump(), now)


def ranked_view(store: CorpusStore, *, max_display: int) -> list[LeadCard]:
    """Projeta o corpus inteiro como LeadCards ranqueados (determinístico).

    Ordena por -p_score com tie-break estável por company_id (paridade com M4),
    recomputa `rank` (1..N) e aplica o teto de EXIBIÇÃO (`max_display`).
    """
    cards = [LeadCard.model_validate(entry.data) for entry in store.all_entries()]
    cards.sort(key=lambda c: (-c.score.p_score, c.score.company_id))
    ranked: list[LeadCard] = [
        card.model_copy(update={"rank": i}) for i, card in enumerate(cards[:max_display], start=1)
    ]
    return ranked


def accumulate_and_rank(
    store: CorpusStore,
    cards: list[LeadCard],
    now: datetime,
    *,
    max_display: int,
) -> list[LeadCard]:
    """Acumula os cards do run no corpus e devolve o corpus inteiro re-ranqueado.

    É o passo único compartilhado por CLI e UI (ADR-006): "volume acumula entre runs"
    e a saída é sempre a visão ordenada por score, deduplicada por entity_id.
    """
    accumulate(store, cards, now)
    return ranked_view(store, max_display=max_display)
