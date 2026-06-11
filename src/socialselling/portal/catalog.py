"""Loader/validação do catálogo de feedback (config/feedback_catalog.json)."""

from __future__ import annotations

import json
from pathlib import Path

from socialselling.portal.contracts import FeedbackCatalog

_DEFAULT_PATH = Path(__file__).resolve().parents[3] / "config" / "feedback_catalog.json"


def load_feedback_catalog(path: Path | None = None) -> FeedbackCatalog:
    """Carrega e valida o catálogo de feedback. Levanta ValueError se inválido."""
    resolved = path if path is not None else _DEFAULT_PATH
    raw = json.loads(resolved.read_text(encoding="utf-8"))
    return FeedbackCatalog.model_validate(raw)
