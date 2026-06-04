"""Store persistente de feedback like/dislike (ADR-007).

Espelha o padrão do `CorpusStore`:
- Chave estável = `company_id` (um voto por lead; last-write-wins).
- Persistência atômica via `atomic_write_text`; serialização estável (sort_keys).
- Relógio sempre injetado (`now`); sem datetime.now() interno.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from socialselling.core.atomic import atomic_write_text
from socialselling.learning.schemas import (
    FeedbackFeatures,
    FeedbackLabel,
    FeedbackRecord,
)


class FeedbackLog(BaseModel):
    """Log completo de feedback; chave = company_id."""

    model_config = ConfigDict(extra="forbid")

    records: dict[str, FeedbackRecord] = Field(default_factory=dict)


class FeedbackStore:
    """Store de votos like/dislike por lead.

    Parâmetros
    ----------
    path:
        Caminho para o JSON do log de feedback. Criado automaticamente se ausente.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._log = self._load()

    # ------------------------------------------------------------------
    # Consulta
    # ------------------------------------------------------------------

    def get(self, company_id: str) -> FeedbackRecord | None:
        """Retorna o voto para company_id ou None."""
        return self._log.records.get(company_id)

    def labels(self) -> dict[str, str]:
        """Mapa company_id -> label (para a UI pintar os selos)."""
        return {cid: rec.label.value for cid, rec in self._log.records.items()}

    def all_records(self) -> list[FeedbackRecord]:
        """Todos os votos ordenados por company_id (determinismo do treino)."""
        return [self._log.records[k] for k in sorted(self._log.records)]

    def counts(self) -> tuple[int, int]:
        """(n_likes, n_dislikes) no log."""
        likes = sum(1 for r in self._log.records.values() if r.label is FeedbackLabel.LIKE)
        dislikes = sum(1 for r in self._log.records.values() if r.label is FeedbackLabel.DISLIKE)
        return likes, dislikes

    def __len__(self) -> int:
        return len(self._log.records)

    # ------------------------------------------------------------------
    # Mutação
    # ------------------------------------------------------------------

    def upsert(
        self,
        company_id: str,
        label: FeedbackLabel,
        features: FeedbackFeatures,
        now: datetime,
    ) -> FeedbackRecord:
        """Insere/atualiza o voto de company_id (last-write-wins; idempotente)."""
        record = FeedbackRecord(
            company_id=company_id,
            label=label,
            features=features,
            recorded_at=now.isoformat(),
        )
        self._log.records[company_id] = record
        self._persist()
        return record

    def remove(self, company_id: str) -> bool:
        """Remove o voto de company_id (desmarcar). Retorna True se removeu."""
        if company_id in self._log.records:
            del self._log.records[company_id]
            self._persist()
            return True
        return False

    # ------------------------------------------------------------------
    # Persistência
    # ------------------------------------------------------------------

    def _load(self) -> FeedbackLog:
        if not self._path.exists():
            return FeedbackLog()
        return FeedbackLog.model_validate_json(self._path.read_text(encoding="utf-8"))

    def _persist(self) -> None:
        raw = self._log.model_dump(mode="json")
        text = json.dumps(raw, ensure_ascii=False, sort_keys=True)
        atomic_write_text(self._path, text)
