"""Store acumulativo de leads com upsert idempotente (ADR-006).

Regras:
- Chave estável = entity_id (fornecida por quem chama).
- Upsert last-write-wins por last_seen; first_seen preservado.
- Persistência atômica via atomic_write_text.
- Relógio sempre injetado (parâmetro `now`); sem datetime.now() interno.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from socialselling.core.atomic import atomic_write_text


class CorpusEntry(BaseModel):
    """Entrada do corpus para uma entidade (empresa/lead)."""

    model_config = ConfigDict(extra="forbid")

    entity_id: str
    first_seen: str  # ISO 8601
    last_seen: str  # ISO 8601
    data: dict[str, Any]


class Corpus(BaseModel):
    """Corpus completo; chave = entity_id."""

    model_config = ConfigDict(extra="forbid")

    entries: dict[str, CorpusEntry] = Field(default_factory=dict)


class CorpusStore:
    """Store persistente de leads com upsert idempotente.

    Parâmetros
    ----------
    path:
        Caminho para o arquivo JSON do corpus. Criado automaticamente se ausente.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._corpus = self._load()

    # ------------------------------------------------------------------
    # Consulta
    # ------------------------------------------------------------------

    def is_known(self, entity_id: str) -> bool:
        """Retorna True se entity_id já está no corpus."""
        return entity_id in self._corpus.entries

    def get(self, entity_id: str) -> CorpusEntry | None:
        """Retorna a entrada para entity_id ou None."""
        return self._corpus.entries.get(entity_id)

    def __len__(self) -> int:
        """Número de entradas no corpus."""
        return len(self._corpus.entries)

    def count(self) -> int:
        """Número de entradas no corpus (alias explícito de __len__)."""
        return len(self._corpus.entries)

    def all_entries(self) -> list[CorpusEntry]:
        """Todas as entradas ordenadas por entity_id (determinismo)."""
        return [self._corpus.entries[k] for k in sorted(self._corpus.entries)]

    # ------------------------------------------------------------------
    # Mutação
    # ------------------------------------------------------------------

    def upsert(
        self,
        entity_id: str,
        data: dict[str, Any],
        now: datetime,
    ) -> CorpusEntry:
        """Insere ou atualiza a entrada para entity_id.

        - Se nova: first_seen = last_seen = now.isoformat().
        - Se existente: last_seen = now.isoformat(); data = {**antigo, **novo};
          first_seen preservado.
        - Idempotente: mesmos argumentos → corpus byte-idêntico.
        """
        now_iso = now.isoformat()
        existing = self._corpus.entries.get(entity_id)

        if existing is None:
            entry = CorpusEntry(
                entity_id=entity_id,
                first_seen=now_iso,
                last_seen=now_iso,
                data=dict(data),
            )
        else:
            merged_data: dict[str, Any] = {**existing.data, **data}
            entry = CorpusEntry(
                entity_id=entity_id,
                first_seen=existing.first_seen,
                last_seen=now_iso,
                data=merged_data,
            )

        self._corpus.entries[entity_id] = entry
        self._persist()
        return entry

    # ------------------------------------------------------------------
    # Persistência
    # ------------------------------------------------------------------

    def _load(self) -> Corpus:
        """Carrega corpus do disco; retorna Corpus vazio se arquivo ausente."""
        if not self._path.exists():
            return Corpus()
        raw = self._path.read_text(encoding="utf-8")
        return Corpus.model_validate_json(raw)

    def _persist(self) -> None:
        """Serializa corpus para JSON estável e grava atomicamente."""
        # model_dump_json com sort_keys via json.dumps para determinismo
        raw_dict = self._corpus.model_dump()
        text = json.dumps(raw_dict, ensure_ascii=False, sort_keys=True)
        atomic_write_text(self._path, text)
