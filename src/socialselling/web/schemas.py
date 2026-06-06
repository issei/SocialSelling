"""Modelos de request da UI (validação automática pelo FastAPI → 422 se inválido)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from socialselling.contracts import HypothesisCatalog, ICPCriteria
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


# ---------------------------------------------------------------------------
# WU-C — ICP Profiles
# ---------------------------------------------------------------------------


class HypothesisConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    base_weight: float = Field(ge=0.0, le=1.0)


class ICPProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str
    name: str = Field(min_length=1, max_length=80)
    description: str = ""
    icp_criteria: dict[str, Any]
    hypotheses_config: dict[str, HypothesisConfig] = Field(default_factory=dict)
    created_at: str  # ISO-8601


class ICPProfileCreate(BaseModel):
    """Payload de criação — profile_id e created_at são gerados pelo servidor."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    description: str = ""
    icp_criteria: dict[str, Any]
    hypotheses_config: dict[str, HypothesisConfig] = Field(default_factory=dict)


def apply_profile_to_catalog(
    profile: ICPProfile, base_catalog: HypothesisCatalog
) -> HypothesisCatalog:
    """Filtra e ajusta o catálogo de hipóteses segundo a config do perfil (puro)."""
    if not profile.hypotheses_config:
        return base_catalog
    result = []
    for h in base_catalog.hypotheses:
        cfg = profile.hypotheses_config.get(h.hypothesis_id)
        if cfg is None or not cfg.enabled:
            continue
        result.append(h.model_copy(update={"prior": cfg.base_weight}))
    return HypothesisCatalog(hypotheses=result)
