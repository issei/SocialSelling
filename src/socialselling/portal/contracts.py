"""Contratos do portal da operadora (SDD portal-operadora-piloto §2).

Compartilhados entre o motor (CLIs publish/pull-feedback) e o portal (API/UI).
REGRA: apenas modelos de dados; sem lógica de negócio, sem import de FastAPI/psycopg.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from socialselling.contracts import DataProvenance

MAX_LEADS_PER_SNAPSHOT = 20


# --------------------------------------------------------------------------- #
# Publicação (motor → portal)                                                  #
# --------------------------------------------------------------------------- #
class PublishedDriver(BaseModel):
    """Driver XAI em linguagem natural, com proveniência (WU-A/WU-B)."""

    model_config = ConfigDict(extra="forbid")

    impact: str  # "positive" | "negative"
    text: str  # frase em linguagem natural (Driver.text do M5)
    references: list[DataProvenance] = Field(default_factory=list)


class PublishedLead(BaseModel):
    """Lead na camada de apresentação da operadora — SEM score numérico."""

    model_config = ConfigDict(extra="forbid")

    entity_id: str  # identidade canônica (§7.1)
    rank_position: int = Field(ge=1, le=MAX_LEADS_PER_SNAPSHOT)
    company: str
    segmento: str | None = None
    cidade: str | None = None
    uf: str | None = None
    instagram: str | None = None
    site: str | None = None
    email: str | None = None
    telefone: str | None = None
    drivers: list[PublishedDriver] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)  # Open-World explícito


class PublishedSnapshot(BaseModel):
    """Snapshot publicado de um run: top-20 do ranking do perfil."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    profile_id: str  # ICP Profile da operadora (WU-C)
    run_id: str  # hash estável do conteúdo do ranking (§7.2) — idempotência
    generated_at: str  # ISO-8601 UTC, relógio injetado
    leads: list[PublishedLead] = Field(max_length=MAX_LEADS_PER_SNAPSHOT)

    @model_validator(mode="after")
    def _ranks_estritos(self) -> PublishedSnapshot:
        ranks = [lead.rank_position for lead in self.leads]
        if ranks != list(range(1, len(ranks) + 1)):
            raise ValueError("rank_position deve ser 1..N estrito, na ordem da lista")
        return self


# --------------------------------------------------------------------------- #
# Feedback (operadora → portal → motor)                                        #
# --------------------------------------------------------------------------- #
class FeedbackKind(StrEnum):
    STATUS = "status"
    REACTION = "reaction"


class Reaction(StrEnum):
    LIKE = "like"
    DISLIKE = "dislike"


class FeedbackEvent(BaseModel):
    """Evento append-only de feedback. event_id é o cursor do pull."""

    model_config = ConfigDict(extra="forbid")

    event_id: int = Field(ge=1)  # serial atribuído pelo portal
    operator_id: str
    profile_id: str
    entity_id: str
    run_id: str  # run do snapshot em que o lead foi exibido
    kind: FeedbackKind
    status_id: str | None = None  # obrigatório quando kind=status
    reaction: Reaction | None = None  # obrigatório quando kind=reaction
    note: str = ""
    created_at: str  # ISO-8601 UTC

    @model_validator(mode="after")
    def _kind_consistente(self) -> FeedbackEvent:
        if self.kind is FeedbackKind.STATUS and (
            self.status_id is None or self.reaction is not None
        ):
            raise ValueError("kind=status exige status_id e proíbe reaction")
        if self.kind is FeedbackKind.REACTION and (
            self.reaction is None or self.status_id is not None
        ):
            raise ValueError("kind=reaction exige reaction e proíbe status_id")
        return self


class FeedbackEventIn(BaseModel):
    """Corpo do POST /lead/{entity_id}/feedback (sessão da operadora).

    operator_id/profile_id vêm da sessão; entity_id do path; run_id do snapshot
    mais recente em que o lead aparece. NUNCA do corpo (anti-spoofing).
    """

    model_config = ConfigDict(extra="forbid")

    kind: FeedbackKind
    status_id: str | None = None
    reaction: Reaction | None = None
    note: str = ""


class FeedbackPage(BaseModel):
    """Resposta do GET /api/feedback — página de eventos por cursor."""

    model_config = ConfigDict(extra="forbid")

    events: list[FeedbackEvent]  # ordenados por event_id ASC
    next_since: int  # último event_id retornado; igual a `since` se vazio


# --------------------------------------------------------------------------- #
# Catálogo de status do funil (config/feedback_catalog.json)                   #
# --------------------------------------------------------------------------- #
class RotuloAprendizado(StrEnum):
    """Rótulo para a calibração offline (NÃO alimenta a ADR-007 na fase 1)."""

    NEUTRO = "neutro"
    POSITIVO = "positivo"
    POSITIVO_FORTE = "positivo_forte"
    NEGATIVO_FRACO = "negativo_fraco"
    NEGATIVO_FIT = "negativo_fit"
    QUALIDADE_DADO = "qualidade_dado"


class CatalogStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status_id: str  # estável, snake_case (nunca renomear; label é mutável)
    label: str
    terminal: bool  # terminal ⇒ lead sai da carteira
    rotulo_aprendizado: RotuloAprendizado
    ordem: int = Field(ge=1)


class FeedbackCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    statuses: list[CatalogStatus]

    @model_validator(mode="after")
    def _ids_e_ordens_unicos(self) -> FeedbackCatalog:
        ids = [s.status_id for s in self.statuses]
        ordens = [s.ordem for s in self.statuses]
        if len(set(ids)) != len(ids) or len(set(ordens)) != len(ordens):
            raise ValueError("status_id e ordem devem ser únicos no catálogo")
        return self


# --------------------------------------------------------------------------- #
# Operadora (auth do portal)                                                   #
# --------------------------------------------------------------------------- #
class Operator(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operator_id: str
    nome: str
    code_hash: str  # SHA-256 hex do código de acesso (§5.3)
    profile_id: str  # ICP Profile da operadora — escopo de TUDO que ela vê
