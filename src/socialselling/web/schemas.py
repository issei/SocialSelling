"""Modelos de request da UI (validação automática pelo FastAPI → 422 se inválido)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from socialselling.contracts import ICPCriteria


class SaveIcpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    icp: ICPCriteria


class AssistRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1)


class ScoringUpdate(BaseModel):
    """Pesos editáveis da fórmula de score (subconjunto de runtime.toml [scoring])."""

    model_config = ConfigDict(extra="forbid")

    w_fit: float = Field(ge=0.0)
    w_intent: float = Field(ge=0.0)
    confidence_exponent: float = Field(ge=0.0)
    w_fit_tech: float = Field(ge=0.0)
    w_fit_industry: float = Field(ge=0.0)
