"""InMemoryDAO — adapter de gate (contract tests e e2e offline).

Usado pelo TestClient e pelo cenário e2e offline (WU-E5). Nunca em produção.
"""

from __future__ import annotations

from socialselling.portal.contracts import (
    FeedbackEvent,
    FeedbackKind,
    Operator,
    PublishedSnapshot,
    Reaction,
)
from socialselling.portal.dao import BasePortalDAO


class InMemoryDAO(BasePortalDAO):
    """Storage em memória — apenas para testes e e2e offline."""

    def __init__(self) -> None:
        # (profile_id, run_id) → (snapshot, published_at)
        self._snapshots: dict[tuple[str, str], tuple[PublishedSnapshot, str]] = {}
        self._events: list[FeedbackEvent] = []
        self._operators: dict[str, Operator] = {}  # code_hash → Operator
        self._next_event_id: int = 1

    def ensure_schema(self) -> None:
        pass  # no-op em memória

    # ------------------------------- snapshots ------------------------------

    def put_snapshot(self, snapshot: PublishedSnapshot, *, now: str) -> bool:
        key = (snapshot.profile_id, snapshot.run_id)
        if key in self._snapshots:
            return False
        self._snapshots[key] = (snapshot, now)
        return True

    def list_snapshots(self, profile_id: str) -> list[PublishedSnapshot]:
        """published_at DESC, tie-break run_id DESC."""
        pairs = [
            (snap, published_at)
            for (pid, _), (snap, published_at) in self._snapshots.items()
            if pid == profile_id
        ]
        pairs.sort(key=lambda t: (t[1], t[0].run_id), reverse=True)
        return [snap for snap, _ in pairs]

    # -------------------------------- feedback ------------------------------

    def append_event(
        self,
        *,
        operator_id: str,
        profile_id: str,
        entity_id: str,
        run_id: str,
        kind: FeedbackKind,
        status_id: str | None,
        reaction: Reaction | None,
        note: str,
        now: str,
    ) -> int:
        event_id = self._next_event_id
        self._next_event_id += 1
        event = FeedbackEvent(
            event_id=event_id,
            operator_id=operator_id,
            profile_id=profile_id,
            entity_id=entity_id,
            run_id=run_id,
            kind=kind,
            status_id=status_id,
            reaction=reaction,
            note=note,
            created_at=now,
        )
        self._events.append(event)
        return event_id

    def events_since(self, since: int, *, limit: int = 500) -> list[FeedbackEvent]:
        result = [e for e in self._events if e.event_id > since]
        result.sort(key=lambda e: e.event_id)
        return result[:limit]

    def latest_status_by_entity(self, profile_id: str) -> dict[str, str]:
        """Último status_id por entity_id (kind=status, maior event_id vence).

        _events é append-only e ordenado por event_id crescente, logo iterar
        sequencialmente e sobrescrever garante que o valor final é o do maior
        event_id — sem necessidade de comparação explícita.
        """
        result: dict[str, str] = {}
        for event in self._events:
            if (
                event.kind is FeedbackKind.STATUS
                and event.profile_id == profile_id
                and event.status_id is not None
            ):
                result[event.entity_id] = event.status_id
        return result

    # ------------------------------- operadoras -----------------------------

    def find_operator_by_code_hash(self, code_hash: str) -> Operator | None:
        return self._operators.get(code_hash)

    def seed_operator(self, operator: Operator) -> None:
        """Método auxiliar de teste — não é parte da porta."""
        self._operators[operator.code_hash] = operator
