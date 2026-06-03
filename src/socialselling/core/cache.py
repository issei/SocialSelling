"""Cache frio em arquivo JSON, com escrita atômica (write-temp + os.replace).

Determinístico: o TTL é avaliado contra um `now` injetado (nunca `datetime.now()`
interno), para permitir reexecução byte-idêntica nos testes.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


def query_hash(text: str) -> str:
    """Hash estável de uma string (sha256 hex)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class JsonCache:
    """Cache chave→payload em `root/<sha256(query)>.json` com TTL por horas."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def _path(self, query: str) -> Path:
        return self._root / f"{query_hash(query)}.json"

    def get(self, query: str, now: datetime, ttl_hours: int) -> dict[str, Any] | None:
        """Retorna o payload se existir e estiver dentro do TTL; senão None."""
        entry = self._read(query)
        if entry is None:
            return None
        stored_at = datetime.fromisoformat(str(entry["stored_at"]))
        age_hours = (now - stored_at).total_seconds() / 3600.0
        if age_hours > ttl_hours:
            return None
        payload: dict[str, Any] = entry["payload"]
        return payload

    def get_any(self, query: str) -> dict[str, Any] | None:
        """Retorna o payload ignorando o TTL (fallback de degradação)."""
        entry = self._read(query)
        if entry is None:
            return None
        payload: dict[str, Any] = entry["payload"]
        return payload

    def put(self, query: str, payload: dict[str, Any], now: datetime) -> None:
        """Grava atomicamente o payload com carimbo `stored_at`."""
        self._root.mkdir(parents=True, exist_ok=True)
        entry = {"query": query, "stored_at": now.isoformat(), "payload": payload}
        path = self._path(query)
        fd, tmp = tempfile.mkstemp(dir=self._root, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(entry, fh, ensure_ascii=False, sort_keys=True)
            os.replace(tmp, path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def _read(self, query: str) -> dict[str, Any] | None:
        path = self._path(query)
        if not path.exists():
            return None
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return data
