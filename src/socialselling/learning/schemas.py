"""Contratos de dados do aprendizado por feedback (ADR-007).

REGRA (como em contracts.py): apenas modelos de dados; sem lógica de negócio.
Operam sobre a camada de APRESENTAÇÃO (componentes de `LeadCard.score`).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class FeedbackLabel(StrEnum):
    """Rótulo dado pela operadora a um lead já buscado."""

    LIKE = "like"
    DISLIKE = "dislike"


class FeedbackFeatures(BaseModel):
    """Componentes do score capturados NO MOMENTO do clique (não recomputados).

    Evita acoplar o aprendizado ao recálculo do pipeline e dispensa alterar
    `ProspectScore` — o card já carrega estes valores na UI.
    """

    model_config = ConfigDict(extra="forbid")

    fit: float = Field(ge=0.0, le=1.0)
    intent: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    persona_fit: float = Field(ge=0.0, le=1.0)


class FeedbackRecord(BaseModel):
    """Um voto da operadora sobre um lead (chave = company_id)."""

    model_config = ConfigDict(extra="forbid")

    company_id: str
    label: FeedbackLabel
    features: FeedbackFeatures
    recorded_at: str  # ISO 8601; relógio injetado


class LearnedWeights(BaseModel):
    """Resultado de um reajuste de pesos a partir do feedback acumulado.

    `applied=False` quando o gate de amostra mínima não foi atingido (não treina,
    mantém os pesos atuais) — `reason` explica o porquê.
    """

    model_config = ConfigDict(extra="forbid")

    w_fit: float = Field(ge=0.0)
    w_intent: float = Field(ge=0.0)
    n_likes: int = Field(ge=0)
    n_dislikes: int = Field(ge=0)
    applied: bool
    reason: str = ""
