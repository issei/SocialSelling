"""Testes do tuner (ADR-007): gate, projeção, shrinkage, determinismo."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from socialselling.config import LearningCfg
from socialselling.learning.feedback_store import FeedbackStore
from socialselling.learning.schemas import FeedbackFeatures, FeedbackLabel
from socialselling.learning.tuner import retrain

_NOW = datetime(2026, 6, 4, 10, 0, 0)
_CURRENT = {"w_fit": 0.6, "w_intent": 0.4}
_CFG = LearningCfg(enabled=True, min_likes=3, min_dislikes=3)


def _seed(store: FeedbackStore, likes_fit: float, dislikes_fit: float, n: int = 4) -> None:
    """n likes com alto fit/baixo intent e n dislikes com baixo fit/alto intent."""
    for i in range(n):
        store.upsert(
            f"like-{i}",
            FeedbackLabel.LIKE,
            FeedbackFeatures(fit=likes_fit, intent=1 - likes_fit, confidence=0.9, persona_fit=1.0),
            _NOW,
        )
        store.upsert(
            f"dis-{i}",
            FeedbackLabel.DISLIKE,
            FeedbackFeatures(
                fit=dislikes_fit, intent=1 - dislikes_fit, confidence=0.9, persona_fit=1.0
            ),
            _NOW,
        )


def test_gate_amostra_insuficiente_nao_aplica(tmp_path: Path) -> None:
    store = FeedbackStore(tmp_path / "fb.json")
    feat = FeedbackFeatures(fit=0.9, intent=0.1, confidence=0.9, persona_fit=1.0)
    store.upsert("a", FeedbackLabel.LIKE, feat, _NOW)
    learned = retrain(store, _CURRENT, _CFG)
    assert learned.applied is False
    assert learned.w_fit == 0.6 and learned.w_intent == 0.4  # mantém atuais
    assert "insuficiente" in learned.reason


def test_curtir_alto_fit_eleva_w_fit(tmp_path: Path) -> None:
    store = FeedbackStore(tmp_path / "fb.json")
    _seed(store, likes_fit=0.9, dislikes_fit=0.1)
    learned = retrain(store, _CURRENT, _CFG)
    assert learned.applied is True
    assert learned.w_fit > 0.6  # priorização migra para fit
    assert learned.w_intent < 0.4
    # escala preservada (soma ~ soma atual)
    assert abs((learned.w_fit + learned.w_intent) - 1.0) <= 1e-6


def test_deterministico(tmp_path: Path) -> None:
    store = FeedbackStore(tmp_path / "fb.json")
    _seed(store, likes_fit=0.9, dislikes_fit=0.1)
    a = retrain(store, _CURRENT, _CFG)
    b = retrain(store, _CURRENT, _CFG)
    assert a == b  # mesmo log => mesmos pesos


def test_shrinkage_limita_o_deslocamento(tmp_path: Path) -> None:
    # Mesmo com sinal forte, alpha<=shrinkage_max impede salto total para (1.0, 0.0).
    store = FeedbackStore(tmp_path / "fb.json")
    _seed(store, likes_fit=0.95, dislikes_fit=0.05, n=4)
    cfg = LearningCfg(enabled=True, shrinkage_max=0.5, shrinkage_ref=20)
    learned = retrain(store, _CURRENT, cfg)
    assert learned.applied is True
    assert learned.w_fit < 1.0  # não saltou tudo de uma vez
