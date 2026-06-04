"""Testes do corpus acumulativo (ADR-006): upsert idempotente, persistência atômica.

Determinístico, sem rede, relógio injetado e `tmp_path` do pytest.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from socialselling.corpus.store import CorpusEntry, CorpusStore

_NOW = datetime(2026, 6, 4, 10, 0, 0)
_LATER = datetime(2026, 6, 5, 12, 30, 0)


def test_upsert_nova_entidade(tmp_path: Path) -> None:
    store = CorpusStore(tmp_path / "corpus.json")
    entry = store.upsert("ent-1", {"nome": "Acme"}, _NOW)
    assert store.is_known("ent-1")
    assert entry.first_seen == entry.last_seen == _NOW.isoformat()
    assert store.count() == 1


def test_upsert_existente_preserva_first_seen_e_mescla(tmp_path: Path) -> None:
    store = CorpusStore(tmp_path / "corpus.json")
    store.upsert("ent-1", {"nome": "Acme"}, _NOW)
    updated = store.upsert("ent-1", {"setor": "consultoria"}, _LATER)
    # Sem duplicar; first_seen preservado, last_seen atualizado, data mesclado.
    assert store.count() == 1
    assert updated.first_seen == _NOW.isoformat()
    assert updated.last_seen == _LATER.isoformat()
    assert updated.data == {"nome": "Acme", "setor": "consultoria"}


def test_upsert_idempotente_byte_identico(tmp_path: Path) -> None:
    path = tmp_path / "corpus.json"
    store = CorpusStore(path)
    store.upsert("ent-1", {"nome": "Acme"}, _NOW)
    snapshot_1 = path.read_text(encoding="utf-8")
    # Mesmo (entity_id, data, now) => corpus byte-idêntico no disco.
    store.upsert("ent-1", {"nome": "Acme"}, _NOW)
    snapshot_2 = path.read_text(encoding="utf-8")
    assert snapshot_1 == snapshot_2


def test_acumula_entre_instancias(tmp_path: Path) -> None:
    path = tmp_path / "corpus.json"
    CorpusStore(path).upsert("ent-A", {"x": 1}, _NOW)
    # Nova instância no MESMO path enxerga A e adiciona B (acumulação entre runs).
    store2 = CorpusStore(path)
    assert store2.is_known("ent-A")
    store2.upsert("ent-B", {"y": 2}, _LATER)
    assert store2.count() == 2


def test_all_entries_ordenado_por_entity_id(tmp_path: Path) -> None:
    store = CorpusStore(tmp_path / "corpus.json")
    store.upsert("ent-c", {}, _NOW)
    store.upsert("ent-a", {}, _NOW)
    store.upsert("ent-b", {}, _NOW)
    ids = [e.entity_id for e in store.all_entries()]
    assert ids == ["ent-a", "ent-b", "ent-c"]


def test_get_inexistente_retorna_none(tmp_path: Path) -> None:
    store = CorpusStore(tmp_path / "corpus.json")
    assert store.get("nao-existe") is None
    assert store.is_known("nao-existe") is False


def test_corpus_entry_rejeita_campo_extra() -> None:
    # extra="forbid": payload com campo inesperado falha (model_validate p/ não tropeçar no mypy).
    with pytest.raises(ValidationError):
        CorpusEntry.model_validate(
            {
                "entity_id": "x",
                "first_seen": "2026-06-04T10:00:00",
                "last_seen": "2026-06-04T10:00:00",
                "data": {},
                "campo_extra": "boom",
            }
        )
