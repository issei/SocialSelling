"""Serviços da camada de apresentação do portal (SDD §4.1).

build_carteira: monta a visão determinística da carteira a partir do DAO.
Regras da §4.1: last-event-wins para status, terminais saem, dedupe na mais recente,
ordenação estável por rank_position (recente) → company casefold + entity_id (acompanhamento).
"""

from __future__ import annotations

from socialselling.portal.contracts import (
    CarteiraItem,
    FeedbackCatalog,
)
from socialselling.portal.dao import BasePortalDAO


def build_carteira(
    dao: BasePortalDAO,
    profile_id: str,
    catalog: FeedbackCatalog,
) -> list[CarteiraItem]:
    """Monta a carteira da operadora (determinística — mesma entrada → mesma saída).

    Regras §4.1:
    1. Sem evento de status → "novo" (Open-World default, nunca fabricado).
    2. Status atual = status_id do evento kind=status de maior event_id do par
       (profile_id, entity_id).
    3. Status terminal → lead sai da carteira (em qualquer snapshot).
    4. Lead presente no snapshot mais recente e em anteriores → uma vez, posição
       do snapshot mais recente.
    5. Ordenação: leads do snapshot mais recente por rank_position; depois
       "em acompanhamento" por company casefold, tie-break entity_id.
    """
    snapshots = dao.list_snapshots(profile_id)
    if not snapshots:
        return []

    most_recent = snapshots[0]
    terminal_ids: frozenset[str] = frozenset(
        s.status_id for s in catalog.statuses if s.terminal
    )
    status_map = dao.latest_status_by_entity(profile_id)

    # 1. Leads do snapshot mais recente (mantêm rank_position)
    most_recent_entities: set[str] = set()
    items: list[CarteiraItem] = []
    for lead in most_recent.leads:
        most_recent_entities.add(lead.entity_id)
        current_status = status_map.get(lead.entity_id, "novo")
        if current_status not in terminal_ids:
            items.append(
                CarteiraItem(
                    lead=lead,
                    status_id=current_status,
                    em_acompanhamento=False,
                    run_id=most_recent.run_id,
                )
            )

    # 2. Leads de snapshots anteriores não-terminais (em acompanhamento)
    seen_entities: set[str] = set(most_recent_entities)
    em_acompanhamento: list[CarteiraItem] = []
    for snap in snapshots[1:]:
        for lead in snap.leads:
            if lead.entity_id in seen_entities:
                continue
            seen_entities.add(lead.entity_id)
            current_status = status_map.get(lead.entity_id, "novo")
            if current_status not in terminal_ids:
                em_acompanhamento.append(
                    CarteiraItem(
                        lead=lead,
                        status_id=current_status,
                        em_acompanhamento=True,
                        run_id=snap.run_id,
                    )
                )

    # Ordenação estável: company casefold, tie-break entity_id
    em_acompanhamento.sort(
        key=lambda x: (x.lead.company.casefold(), x.lead.entity_id)
    )

    return items + em_acompanhamento
