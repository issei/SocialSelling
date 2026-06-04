"""Reajuste de pesos a partir do feedback acumulado (ADR-007).

Liga o `FeedbackStore` ao modelo treinado e PROJETA os coeficientes aprendidos
sobre os pesos `w_fit`/`w_intent` da fórmula do score, com travas de estabilidade:

1. Gate de amostra mínima (não treina sem sinal dos dois lados).
2. Projeção: coeficientes (fit, intent) → pesos normalizados (somam o total atual).
3. Shrinkage rumo aos pesos atuais (mais votos ⇒ mais confiança no aprendido).
4. Clamp/normalização final.

Determinístico (regra §3.2): mesmo log de feedback ⇒ mesmos pesos.
"""

from __future__ import annotations

from socialselling.config import LearningCfg
from socialselling.learning.feedback_store import FeedbackStore
from socialselling.learning.model import train_logistic
from socialselling.learning.schemas import FeedbackLabel, LearnedWeights

_ROUND = 6


def retrain(
    store: FeedbackStore,
    current: dict[str, float],
    cfg: LearningCfg,
) -> LearnedWeights:
    """Calcula os novos `w_fit`/`w_intent` a partir do feedback (ou mantém os atuais).

    `current` deve conter `w_fit` e `w_intent` (pesos vigentes do score).
    """
    likes, dislikes = store.counts()
    w_fit_cur = current["w_fit"]
    w_intent_cur = current["w_intent"]

    if likes < cfg.min_likes or dislikes < cfg.min_dislikes:
        falta = max(cfg.min_likes - likes, 0) + max(cfg.min_dislikes - dislikes, 0)
        return LearnedWeights(
            w_fit=w_fit_cur,
            w_intent=w_intent_cur,
            n_likes=likes,
            n_dislikes=dislikes,
            applied=False,
            reason=f"amostra insuficiente (faltam {falta} voto(s))",
        )

    records = store.all_records()
    feats = [[r.features.fit, r.features.intent] for r in records]
    ys = [1 if r.label is FeedbackLabel.LIKE else 0 for r in records]
    weights, _bias = train_logistic(feats, ys, epochs=cfg.epochs, lr=cfg.lr, l2=cfg.l2)

    # Só a contribuição POSITIVA de cada feature vira peso (pesos do score são >= 0).
    beta_fit = max(weights[0], 0.0)
    beta_intent = max(weights[1], 0.0)
    total_beta = beta_fit + beta_intent
    if total_beta <= 0.0:
        return LearnedWeights(
            w_fit=w_fit_cur,
            w_intent=w_intent_cur,
            n_likes=likes,
            n_dislikes=dislikes,
            applied=False,
            reason="sem sinal discriminante positivo",
        )

    scale = w_fit_cur + w_intent_cur  # preserva a escala atual (convenção: soma = 1.0)
    learned_fit = beta_fit / total_beta * scale
    learned_intent = beta_intent / total_beta * scale

    n_total = likes + dislikes
    alpha = min(cfg.shrinkage_max, n_total / cfg.shrinkage_ref)
    new_fit = (1.0 - alpha) * w_fit_cur + alpha * learned_fit
    new_intent = (1.0 - alpha) * w_intent_cur + alpha * learned_intent

    # Renormaliza para a escala atual e arredonda (determinismo byte-idêntico).
    norm = new_fit + new_intent
    if norm > 0.0:
        new_fit = new_fit / norm * scale
        new_intent = new_intent / norm * scale

    return LearnedWeights(
        w_fit=round(new_fit, _ROUND),
        w_intent=round(new_intent, _ROUND),
        n_likes=likes,
        n_dislikes=dislikes,
        applied=True,
        reason=f"reajustado a partir de {n_total} voto(s)",
    )
