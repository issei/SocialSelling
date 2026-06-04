"""Testes do FeedbackStore (ADR-007): upsert/remove, contagem, persistência atômica.

Determinístico, sem rede, relógio injetado e `tmp_path` do pytest.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from socialselling.learning.feedback_store import FeedbackStore
from socialselling.learning.schemas import FeedbackFeatures, FeedbackLabel, FeedbackRecord

_NOW = datetime(2026, 6, 4, 10, 0, 0)
_LATER = datetime(2026, 6, 5, 12, 30, 0)


def _feat(fit: float = 0.8, intent: float = 0.2) -> FeedbackFeatures:
    return FeedbackFeatures(fit=fit, intent=intent, confidence=0.9, persona_fit=1.0)


def test_upsert_novo_voto(tmp_path: Path) -> None:
    store = FeedbackStore(tmp_path / "feedback.json")
    rec = store.upsert("co-1", FeedbackLabel.LIKE, _feat(), _NOW)
    assert rec.recorded_at == _NOW.isoformat()
    assert store.get("co-1") is not None
    assert store.counts() == (1, 0)


def test_upsert_troca_rotulo_last_write_wins(tmp_path: Path) -> None:
    store = FeedbackStore(tmp_path / "feedback.json")
    store.upsert("co-1", FeedbackLabel.LIKE, _feat(), _NOW)
    store.upsert("co-1", FeedbackLabel.DISLIKE, _feat(), _LATER)
    assert len(store) == 1  # não duplica
    rec = store.get("co-1")
    assert rec is not None and rec.label is FeedbackLabel.DISLIKE
    assert store.counts() == (0, 1)


def test_remove_desmarca(tmp_path: Path) -> None:
    store = FeedbackStore(tmp_path / "feedback.json")
    store.upsert("co-1", FeedbackLabel.LIKE, _feat(), _NOW)
    assert store.remove("co-1") is True
    assert store.get("co-1") is None
    assert store.remove("co-1") is False  # já não existe


def test_upsert_idempotente_byte_identico(tmp_path: Path) -> None:
    path = tmp_path / "feedback.json"
    store = FeedbackStore(path)
    store.upsert("co-1", FeedbackLabel.LIKE, _feat(), _NOW)
    snap1 = path.read_text(encoding="utf-8")
    store.upsert("co-1", FeedbackLabel.LIKE, _feat(), _NOW)
    snap2 = path.read_text(encoding="utf-8")
    assert snap1 == snap2


def test_acumula_entre_instancias(tmp_path: Path) -> None:
    path = tmp_path / "feedback.json"
    FeedbackStore(path).upsert("co-A", FeedbackLabel.LIKE, _feat(), _NOW)
    store2 = FeedbackStore(path)
    assert store2.get("co-A") is not None
    store2.upsert("co-B", FeedbackLabel.DISLIKE, _feat(), _LATER)
    assert len(store2) == 2


def test_all_records_ordenado_por_company_id(tmp_path: Path) -> None:
    store = FeedbackStore(tmp_path / "feedback.json")
    store.upsert("co-c", FeedbackLabel.LIKE, _feat(), _NOW)
    store.upsert("co-a", FeedbackLabel.LIKE, _feat(), _NOW)
    store.upsert("co-b", FeedbackLabel.DISLIKE, _feat(), _NOW)
    ids = [r.company_id for r in store.all_records()]
    assert ids == ["co-a", "co-b", "co-c"]


def test_labels_mapa_para_ui(tmp_path: Path) -> None:
    store = FeedbackStore(tmp_path / "feedback.json")
    store.upsert("co-1", FeedbackLabel.LIKE, _feat(), _NOW)
    store.upsert("co-2", FeedbackLabel.DISLIKE, _feat(), _NOW)
    assert store.labels() == {"co-1": "like", "co-2": "dislike"}


def test_record_rejeita_campo_extra() -> None:
    with pytest.raises(ValidationError):
        FeedbackRecord.model_validate(
            {
                "company_id": "x",
                "label": "like",
                "features": {"fit": 0.5, "intent": 0.5, "confidence": 0.5, "persona_fit": 1.0},
                "recorded_at": "2026-06-04T10:00:00",
                "campo_extra": "boom",
            }
        )
