"""Carregamento de configuração de runtime e de segredos (.env).

`runtime.toml` → `RuntimeConfig` (tipado). Segredos vêm do `.env` (nunca versionado).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, Field


class CacheCfg(BaseModel):
    ttl_hours: int


class ScoringCfg(BaseModel):
    w_fit: float
    w_intent: float
    confidence_exponent: float
    w_fit_tech: float
    w_fit_industry: float
    intent_evidence_norm: int


class PersonaCfg(BaseModel):
    """Multiplicadores de aderência de persona (M3)."""

    fundadora: float = 1.0
    indefinido: float = 0.5
    empresa: float = 0.35
    fundador: float = 0.0


class TavilyCfg(BaseModel):
    max_queries: int
    max_results: int
    search_depth: str
    persona_term: str = ""
    include_domains: list[str] = Field(default_factory=list)


class GeminiCfg(BaseModel):
    """Cognição Gemini. `batch_size`/RPD são a reforma cognitiva (ADR-005).

    Defaults preservam paridade: `batch_size` alto => 1 lote (prompt idêntico ao atual);
    `rpd_enabled=False` => sem orçamento de requisições.
    """

    model: str
    batch_size: int = 50
    rpd_enabled: bool = False
    rpd_cap: int = 1000
    rpd_ledger_path: str = "data/gemini_request_ledger.json"


class ApolloCapsCfg(BaseModel):
    """Orçamento mensal do tier gratuito Apollo (ADR-004). Reconciliável via 402."""

    data_credits_cap: int = 100
    email_credits_cap: int = 100
    mobile_credits_cap: int = 5


class ApolloCfg(BaseModel):
    """Configuração do sensor Apollo (ADR-004). Opt-in: `enabled` + APOLLO_API_KEY.

    Default `enabled=False` mantém o pipeline byte-idêntico ao atual (paridade).
    """

    enabled: bool = False
    base_url: str = "https://api.apollo.io/api/v1"
    ledger_path: str = "data/apollo_credit_ledger.json"
    reveal_top_n: int = 20
    org_enrich_ttl_hours: int = 720
    reveal_ttl_hours: int = 2160
    per_minute_limit: int = 50
    caps: ApolloCapsCfg = ApolloCapsCfg()


class CorpusCfg(BaseModel):
    """Corpus de leads acumulativo (ADR-006). Opt-in: `enabled`.

    Default `enabled=False` => run stateless atual (sobrescreve), paridade preservada.
    """

    enabled: bool = False
    path: str = "data/corpus/leads_corpus.json"


class LearningCfg(BaseModel):
    """Aprendizado por feedback like/dislike (ADR-007). Opt-in: `enabled`.

    Default `enabled=False` => sem reajuste de pesos (paridade). Travas de
    estabilidade do auto-apply: gate de amostra mínima, L2, shrinkage e clamp.
    """

    enabled: bool = False
    feedback_path: str = "data/feedback.json"
    min_likes: int = 3
    min_dislikes: int = 3
    l2: float = 0.1
    epochs: int = 500
    lr: float = 0.5
    # Fração máxima de deslocamento rumo aos pesos aprendidos; `ref` = nº de votos
    # para atingir essa confiança máxima (mais dados => mais peso ao aprendido).
    shrinkage_max: float = 0.5
    shrinkage_ref: int = 20


class RuntimeBlock(BaseModel):
    max_leads_per_cycle: int


class RuntimeConfig(BaseModel):
    """Espelho tipado de runtime.toml (campos extras são ignorados)."""

    cache: CacheCfg
    scoring: ScoringCfg
    persona: PersonaCfg = PersonaCfg()
    tavily: TavilyCfg
    gemini: GeminiCfg
    apollo: ApolloCfg = ApolloCfg()
    corpus: CorpusCfg = CorpusCfg()
    learning: LearningCfg = LearningCfg()
    runtime: RuntimeBlock


def load_runtime(path: Path) -> RuntimeConfig:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return RuntimeConfig.model_validate(data)


def load_env(path: Path) -> dict[str, str]:
    """Lê pares CHAVE=valor de um .env (sem dependência externa)."""
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env[key] = value
    return env
