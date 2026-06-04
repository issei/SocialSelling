"""Testes da regressão logística pura (ADR-007): determinismo e separabilidade."""

from __future__ import annotations

from socialselling.learning.model import sigmoid, train_logistic


def test_sigmoid_estavel_nos_extremos() -> None:
    assert abs(sigmoid(0.0) - 0.5) <= 1e-12
    assert sigmoid(1000.0) <= 1.0
    assert sigmoid(-1000.0) >= 0.0  # sem OverflowError


def test_treino_deterministico_byte_identico() -> None:
    feats = [[0.9, 0.1], [0.8, 0.2], [0.1, 0.9], [0.2, 0.8]]
    ys = [1, 1, 0, 0]
    w1, b1 = train_logistic(feats, ys, epochs=300, lr=0.5, l2=0.1)
    w2, b2 = train_logistic(feats, ys, epochs=300, lr=0.5, l2=0.1)
    assert w1 == w2 and b1 == b2  # mesma entrada => mesmos coeficientes, bit a bit


def test_separa_fit_de_intent() -> None:
    # Likes = alto fit / baixo intent; dislikes = baixo fit / alto intent.
    feats = [[0.9, 0.1], [0.85, 0.15], [0.1, 0.9], [0.15, 0.85]]
    ys = [1, 1, 0, 0]
    (w_fit, w_intent), _ = train_logistic(feats, ys, epochs=800, lr=0.5, l2=0.05)
    # O modelo deve associar fit ao like (coef positivo) e intent ao dislike.
    assert w_fit > 0.0 > w_intent


def test_lista_vazia_retorna_vazio() -> None:
    weights, bias = train_logistic([], [], epochs=10, lr=0.5, l2=0.1)
    assert weights == [] and bias == 0.0
