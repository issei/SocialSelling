"""Contratos de dados do pipeline M1..M5 (Pydantic v2).

REGRA: este modulo contem APENAS modelos de dados (contratos de I/O entre modulos).
NAO implemente logica de negocio aqui. Ver ADR-000 e CLAUDE.md (guardrails).

Mapa das camadas semanticas isoladas (regra inviolavel):
  - Camada 1 Observed Evidence -> ObservedEvidence        (saida de M1)
  - Camada 2 Generated Inferences -> Inference            (saida de M2)
  - Camada 3 Evaluated Hypotheses -> ProspectScore/XAIPayload (M3/M5)
Uma inferencia jamais e tratada como evidencia observada.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DataQualityFlag(StrEnum):
    """Flag de qualidade de dados por sensor (SDD v1.0 secao 1.4)."""

    OK = "OK"
    DEGRADED = "DEGRADED"


class OperatingMode(StrEnum):
    """Modo operacional do ciclo sob falha de sensores."""

    NORMAL = "NORMAL"
    DEGRADED_TAVILY = "DEGRADED_TAVILY"
    DEGRADED_GEMINI = "DEGRADED_GEMINI"
    CACHE_ONLY = "CACHE_ONLY"


# --------------------------------------------------------------------------- #
# Entrada do pipeline                                                         #
# --------------------------------------------------------------------------- #
class EmployeeRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min: int = Field(ge=0)
    max: int = Field(ge=0)

    @model_validator(mode="after")
    def _check_bounds(self) -> EmployeeRange:
        if self.min > self.max:
            raise ValueError("employee_range.min nao pode exceder max")
        return self


class Geographies(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country: str
    regions: list[str] = Field(default_factory=list)


class Firmographics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    industries: list[str]
    employee_range: EmployeeRange
    geographies: Geographies
    business_models: list[str]


class Technographics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mandatory: list[str] = Field(default_factory=list)
    preferred: list[str] = Field(default_factory=list)
    excluded: list[str] = Field(default_factory=list)


class PersonaMatrix(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_roles: list[str]
    min_seniority: str


class ICPCriteria(BaseModel):
    """Contrato universal de entrada — quem e o cliente ideal."""

    model_config = ConfigDict(extra="forbid")

    icp_id: str
    firmographics: Firmographics
    technographics: Technographics
    persona_matrix: PersonaMatrix
    intent_triggers: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Catalogo de hipoteses (config/hypotheses_catalog.json)                      #
# --------------------------------------------------------------------------- #
class Hypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypothesis_id: str
    description: str
    prior: float = Field(ge=0.0, le=1.0)
    surface_signals: list[str]
    sources: list[str]


class HypothesisCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypotheses: list[Hypothesis]


# --------------------------------------------------------------------------- #
# Camada 1 — Observed Evidence (saida de M1 Busca/Tavily)                      #
# --------------------------------------------------------------------------- #
class ObservedEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    query: str
    source_url: str
    title: str
    snippet: str
    captured_at: str  # ISO-8601
    source_trust: float = Field(ge=0.0, le=1.0, default=0.5)
    missing_evidence: bool = False


# --------------------------------------------------------------------------- #
# Camada 2 — Generated Inferences (saida de M2 Extracao/Gemini)               #
# --------------------------------------------------------------------------- #
class CompanyEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str
    normalized_name: str
    domain: str | None = None
    employee_count: int | None = None
    industry: str | None = None
    technologies: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class PersonEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    person_id: str
    normalized_name: str
    role_title: str | None = None
    seniority: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class Inference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: CompanyEntity
    people: list[PersonEntity] = Field(default_factory=list)
    derived_from: list[str]  # evidence_ids — rastreabilidade Evidence -> Inference
    confidence: float = Field(ge=0.0, le=1.0)
    # Sinais de intencao/timing detectados (vocabulario das hipoteses) e
    # desqualificadores detectados (vocabulario fixo). Usados pelo M3 (intent + hard filter).
    intent_signals: list[str] = Field(default_factory=list)
    disqualifiers: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Camada 3 — Evaluated Hypotheses (M3 Score / M4 Ranking / M5 XAI)            #
# --------------------------------------------------------------------------- #
class ProspectScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str
    fit: float = Field(ge=0.0, le=1.0)
    intent: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    p_score: float = Field(ge=0.0)
    hard_filter_passed: bool = True


class Driver(BaseModel):
    model_config = ConfigDict(extra="forbid")

    driver: str
    impact: str
    text: str


class XAIPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str
    final_p_score: float
    positive_signals: list[Driver] = Field(default_factory=list)
    negative_signals: list[Driver] = Field(default_factory=list)
    missing_signals: list[str] = Field(default_factory=list)
    degraded_mode: bool = False


class RankedProspect(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rank: int = Field(ge=1)
    score: ProspectScore
    explanation: XAIPayload
