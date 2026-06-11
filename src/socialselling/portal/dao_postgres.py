"""PostgresDAO — adapter de produção (Neon Postgres free via psycopg v3).

REGRA: psycopg é importado SOMENTE aqui. Cada método = 1 statement SQL puro.
Fora do gate: risco residual aceito, coberto pelo smoke pós-deploy (runbook §9).
"""

from __future__ import annotations

import json
from typing import Any

from socialselling.portal.contracts import (
    FeedbackEvent,
    FeedbackKind,
    Operator,
    PublishedSnapshot,
    Reaction,
)
from socialselling.portal.dao import BasePortalDAO

_DDL = """
CREATE TABLE IF NOT EXISTS snapshots (
    profile_id   TEXT        NOT NULL,
    run_id       TEXT        NOT NULL,
    payload      JSONB       NOT NULL,
    published_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (profile_id, run_id)
);

CREATE TABLE IF NOT EXISTS feedback_events (
    id          BIGSERIAL PRIMARY KEY,
    operator_id TEXT        NOT NULL,
    profile_id  TEXT        NOT NULL,
    entity_id   TEXT        NOT NULL,
    run_id      TEXT        NOT NULL,
    kind        TEXT        NOT NULL CHECK (kind IN ('status', 'reaction')),
    status_id   TEXT,
    reaction    TEXT        CHECK (reaction IN ('like', 'dislike')),
    note        TEXT        NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS operators (
    operator_id TEXT PRIMARY KEY,
    nome        TEXT NOT NULL,
    code_hash   TEXT NOT NULL,
    profile_id  TEXT NOT NULL
);
"""


class PostgresDAO(BasePortalDAO):
    """Adapter de produção — psycopg v3, 1 SQL por método."""

    def __init__(self, conn: Any) -> None:
        self._conn: Any = conn

    def ensure_schema(self) -> None:
        with self._conn.cursor() as cur:
            cur.execute(_DDL)
        self._conn.commit()

    # ------------------------------- snapshots ------------------------------

    def put_snapshot(self, snapshot: PublishedSnapshot, *, now: str) -> bool:
        sql = """
            INSERT INTO snapshots (profile_id, run_id, payload, published_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (profile_id, run_id) DO NOTHING
        """
        with self._conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    snapshot.profile_id,
                    snapshot.run_id,
                    json.dumps(snapshot.model_dump()),
                    now,
                ),
            )
            inserted: bool = bool(cur.rowcount == 1)
        self._conn.commit()
        return inserted

    def list_snapshots(self, profile_id: str) -> list[PublishedSnapshot]:
        sql = """
            SELECT payload FROM snapshots
            WHERE profile_id = %s
            ORDER BY published_at DESC, run_id DESC
        """
        with self._conn.cursor() as cur:
            cur.execute(sql, (profile_id,))
            rows = cur.fetchall()
        return [PublishedSnapshot.model_validate(r[0]) for r in rows]

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
        sql = """
            INSERT INTO feedback_events
                (operator_id, profile_id, entity_id, run_id, kind,
                 status_id, reaction, note, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        with self._conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    operator_id, profile_id, entity_id, run_id, kind.value,
                    status_id,
                    reaction.value if reaction else None,
                    note, now,
                ),
            )
            event_id: int = cur.fetchone()[0]
        self._conn.commit()
        return event_id

    def events_since(self, since: int, *, limit: int = 500) -> list[FeedbackEvent]:
        sql = """
            SELECT id, operator_id, profile_id, entity_id, run_id,
                   kind, status_id, reaction, note, created_at
            FROM feedback_events
            WHERE id > %s
            ORDER BY id ASC
            LIMIT %s
        """
        with self._conn.cursor() as cur:
            cur.execute(sql, (since, limit))
            rows = cur.fetchall()
        return [
            FeedbackEvent(
                event_id=r[0],
                operator_id=r[1],
                profile_id=r[2],
                entity_id=r[3],
                run_id=r[4],
                kind=FeedbackKind(r[5]),
                status_id=r[6],
                reaction=Reaction(r[7]) if r[7] else None,
                note=r[8],
                created_at=str(r[9]),
            )
            for r in rows
        ]

    def latest_status_by_entity(self, profile_id: str) -> dict[str, str]:
        sql = """
            SELECT DISTINCT ON (entity_id) entity_id, status_id
            FROM feedback_events
            WHERE profile_id = %s AND kind = 'status' AND status_id IS NOT NULL
            ORDER BY entity_id, id DESC
        """
        with self._conn.cursor() as cur:
            cur.execute(sql, (profile_id,))
            rows = cur.fetchall()
        return {r[0]: r[1] for r in rows}

    # ------------------------------- operadoras -----------------------------

    def find_operator_by_code_hash(self, code_hash: str) -> Operator | None:
        sql = """
            SELECT operator_id, nome, code_hash, profile_id
            FROM operators WHERE code_hash = %s
        """
        with self._conn.cursor() as cur:
            cur.execute(sql, (code_hash,))
            row = cur.fetchone()
        if row is None:
            return None
        return Operator(
            operator_id=row[0],
            nome=row[1],
            code_hash=row[2],
            profile_id=row[3],
        )
