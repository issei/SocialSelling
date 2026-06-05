"""Estado da onda de busca incremental por ICP (ADR-006).

Cada "Executar Prospecção" na UI avança a onda do ICP, fazendo o M1 variar as queries
e trazer leads NOVOS (acumulados no corpus). Persistência atômica; sem datetime interno.
"""

from __future__ import annotations

import json
from pathlib import Path

from socialselling.core.atomic import atomic_write_text


class WaveStore:
    """Mapa persistente icp_name -> índice da onda atual (default 0)."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data = self._load()

    def current(self, icp_name: str) -> int:
        """Onda atual do ICP (0 se nunca executado)."""
        return self._data.get(icp_name, 0)

    def advance(self, icp_name: str) -> int:
        """Incrementa e persiste a onda do ICP; retorna o novo valor."""
        nxt = self.current(icp_name) + 1
        self._data[icp_name] = nxt
        self._persist()
        return nxt

    def _load(self) -> dict[str, int]:
        if not self._path.exists():
            return {}
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        return {str(k): int(v) for k, v in raw.items()}

    def _persist(self) -> None:
        text = json.dumps(self._data, ensure_ascii=False, sort_keys=True)
        atomic_write_text(self._path, text)
