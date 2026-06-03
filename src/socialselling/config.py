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


class TavilyCfg(BaseModel):
    max_queries: int
    max_results: int
    search_depth: str
    persona_term: str = ""
    include_domains: list[str] = Field(default_factory=list)


class GeminiCfg(BaseModel):
    model: str


class RuntimeBlock(BaseModel):
    max_leads_per_cycle: int


class RuntimeConfig(BaseModel):
    """Espelho tipado de runtime.toml (campos extras são ignorados)."""

    cache: CacheCfg
    scoring: ScoringCfg
    tavily: TavilyCfg
    gemini: GeminiCfg
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
