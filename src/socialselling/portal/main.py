"""Entrypoint de produção do portal (ADR-010, SDD §8) — alvo do `render.yaml`.

`uvicorn socialselling.portal.main:app` (start command do Render).

Lê `DATABASE_URL`/`PUBLISH_TOKEN`/`SECRET_KEY` do ambiente (env vars do Render; nunca
commitadas). Monta o `PostgresDAO` com **reconexão por uso** — o Neon free suspende
conexões ociosas, então uma conexão única aberta no boot morreria silenciosamente.

IMPORTANTE: o módulo é importável SEM `DATABASE_URL` (a conexão é preguiçosa — só abre
no primeiro uso / no `ensure_schema` do lifespan). Isso mantém o import barato no CI.
"""

from __future__ import annotations

import os
from typing import Any

from socialselling.portal.app import create_portal_app
from socialselling.portal.dao_postgres import PostgresDAO


class ReconnectingPostgresDAO(PostgresDAO):
    """PostgresDAO que (re)abre a conexão sob demanda — tolerante ao idle do Neon free.

    Cada acesso a `self._conn` verifica se há conexão viva; se ausente ou fechada
    (idle timeout do Neon), abre uma nova. Os métodos herdados de PostgresDAO usam
    `self._conn` normalmente — a reconexão é transparente.
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._live: Any = None

    @property
    def _conn(self) -> Any:
        if self._live is None or getattr(self._live, "closed", True):
            import psycopg

            self._live = psycopg.connect(self._dsn)
        return self._live

    @_conn.setter
    def _conn(self, value: Any) -> None:  # mantém compat com PostgresDAO.__init__
        self._live = value


def _build_dao() -> ReconnectingPostgresDAO:
    dsn = os.environ.get("DATABASE_URL", "")
    # DSN vazio é tolerado no import (CI); a falha só aparece no primeiro uso real.
    return ReconnectingPostgresDAO(dsn)


# Instância exigida pelo start command do Render (uvicorn socialselling.portal.main:app).
app = create_portal_app(_build_dao(), https_only=True)
