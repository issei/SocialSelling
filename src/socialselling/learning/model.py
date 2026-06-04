"""Regressão logística em Python puro — treino DETERMINÍSTICO (ADR-007).

Sem numpy/sklearn (mantém o PoC enxuto). Determinismo (regra §3.2):
- pesos/bias inicializados em 0.0;
- gradiente full-batch (sem amostragem aleatória), nº de épocas fixo;
- ordem das amostras é a fornecida pelo chamador (FeedbackStore.all_records → company_id);
- regularização L2 nos pesos (não no bias) para estabilidade.

Mesmo (X, y, hiperparâmetros) ⇒ mesmos coeficientes, bit a bit.
"""

from __future__ import annotations

import math


def sigmoid(z: float) -> float:
    """Sigmoide numericamente estável (sem overflow para z muito negativo)."""
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    ez = math.exp(z)
    return ez / (1.0 + ez)


def train_logistic(
    features: list[list[float]],
    labels: list[int],
    *,
    epochs: int,
    lr: float,
    l2: float,
) -> tuple[list[float], float]:
    """Treina uma regressão logística binária por gradiente full-batch.

    Parâmetros
    ----------
    features:
        Lista de vetores de features (mesma dimensão `d`).
    labels:
        Rótulos binários (0/1), alinhados a `features`.
    epochs, lr, l2:
        Hiperparâmetros fixos (sem early-stopping/aleatoriedade → determinístico).

    Retorna
    -------
    (weights, bias): pesos por feature e o termo de viés.
    """
    n = len(features)
    if n == 0:
        return [], 0.0
    d = len(features[0])
    weights = [0.0] * d
    bias = 0.0
    for _ in range(epochs):
        grad_w = [0.0] * d
        grad_b = 0.0
        for xi, yi in zip(features, labels, strict=True):
            z = bias + sum(weights[j] * xi[j] for j in range(d))
            err = sigmoid(z) - yi
            for j in range(d):
                grad_w[j] += err * xi[j]
            grad_b += err
        for j in range(d):
            weights[j] -= lr * (grad_w[j] / n + l2 * weights[j])
        bias -= lr * (grad_b / n)
    return weights, bias
