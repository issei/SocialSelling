"""Porta de storage do portal — BasePortalDAO (ABC).

O app FastAPI conhece SÓ esta interface. Adapters: InMemoryDAO (gate) e
PostgresDAO (prod). Seguindo Ports & Adapters (SDD §5.2).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from socialselling.portal.contracts import (
    FeedbackEvent,
    FeedbackKind,
    Operator,
    PublishedSnapshot,
    Reaction,
)


class BasePortalDAO(ABC):
    """Porta de storage do portal. O app conhece SÓ esta interface."""

    @abstractmethod
    def ensure_schema(self) -> None:
        """CREATE TABLE IF NOT EXISTS idempotente (no-op no InMemory)."""

    # ------------------------------- snapshots ------------------------------

    @abstractmethod
    def put_snapshot(self, snapshot: PublishedSnapshot, *, now: str) -> bool:
        """Insere o snapshot. False se (profile_id, run_id) já existe (→ 409)."""

    @abstractmethod
    def list_snapshots(self, profile_id: str) -> list[PublishedSnapshot]:
        """Snapshots do perfil, mais recente primeiro (published_at DESC,
        tie-break run_id DESC) — base da carteira (§4.1)."""

    # -------------------------------- feedback ------------------------------

    @abstractmethod
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
        """Append-only; retorna o event_id atribuído (serial crescente)."""

    @abstractmethod
    def events_since(self, since: int, *, limit: int = 500) -> list[FeedbackEvent]:
        """Eventos com event_id > since, ordem ASC. Além do fim → lista vazia."""

    @abstractmethod
    def latest_status_by_entity(self, profile_id: str) -> dict[str, str]:
        """Último status_id por entity_id (kind=status, maior event_id vence).
        Entidade ausente do dict = sem evento = 'novo' (Open-World, no chamador)."""

    # ------------------------------- operadoras -----------------------------

    @abstractmethod
    def find_operator_by_code_hash(self, code_hash: str) -> Operator | None:
        """None se não encontrado (login responde 401 genérico)."""
