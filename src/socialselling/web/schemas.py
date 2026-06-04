"""Modelos de request da UI (validação automática pelo FastAPI → 422 se inválido)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from socialselling.contracts import ICPCriteria
from socialselling.learning.schemas import FeedbackFeatures


class SaveIcpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    icp: ICPCriteria


class AssistRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1)


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    icp_name: str = Field(min_length=1)


class FeedbackRequest(BaseModel):
    """Voto da operadora sobre um lead. `label="none"` desmarca (toggle off).

    `features` são os componentes do score capturados do card no clique (ADR-007).
    """

    model_config = ConfigDict(extra="forbid")

    company_id: str = Field(min_length=1)
    label: Literal["like", "dislike", "none"]
    features: FeedbackFeatures


class ScoringUpdate(BaseModel):
    """Pesos editáveis da fórmula de score (subconjunto de runtime.toml [scoring])."""

    model_config = ConfigDict(extra="forbid")

    w_fit: float = Field(ge=0.0)
    w_intent: float = Field(ge=0.0)
    confidence_exponent: float = Field(ge=0.0)
    w_fit_tech: float = Field(ge=0.0)
    w_fit_industry: float = Field(ge=0.0)
