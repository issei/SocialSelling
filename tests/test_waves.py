"""Testes do WaveStore (ADR-006): onda por ICP, persistência atômica entre instâncias."""

from __future__ import annotations

from pathlib import Path

from socialselling.corpus.waves import WaveStore


def test_onda_inicial_e_zero(tmp_path: Path) -> None:
    store = WaveStore(tmp_path / "waves.json")
    assert store.current("icp_criteria.talita.json") == 0


def test_advance_incrementa_e_persiste(tmp_path: Path) -> None:
    path = tmp_path / "waves.json"
    store = WaveStore(path)
    assert store.advance("a") == 1
    assert store.advance("a") == 2
    # Nova instância no mesmo path enxerga a onda acumulada.
    assert WaveStore(path).current("a") == 2


def test_ondas_isoladas_por_icp(tmp_path: Path) -> None:
    store = WaveStore(tmp_path / "waves.json")
    store.advance("a")
    assert store.current("a") == 1
    assert store.current("b") == 0  # ICP diferente, onda própria
