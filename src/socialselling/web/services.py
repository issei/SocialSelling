"""Ponte fina entre a UI web e o núcleo (lê/grava os mesmos artefatos de config).

NÃO contém lógica de pipeline — apenas orquestra leitura/escrita de configuração
e delega ao núcleo. Mantém o núcleo (M1–M5) intocado (ADR-002).
"""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from socialselling.config import load_env, load_runtime
from socialselling.contracts import HypothesisCatalog, ICPCriteria, LeadCard
from socialselling.core.atomic import atomic_write_text
from socialselling.orchestrator import run_pipeline
from socialselling.skills.gemini_client import CognitionClient, GeminiClient
from socialselling.skills.tavily_client import TavilyClient

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_DIR = _ROOT / "config"
DEFAULT_RUNTIME = _ROOT / "config" / "runtime.toml"

_ICP_NAME_RE = re.compile(r"^icp_criteria[\w.\-]*\.json$")
_SCORING_KEYS = (
    "w_fit",
    "w_intent",
    "confidence_exponent",
    "w_fit_tech",
    "w_fit_industry",
)


class InvalidName(ValueError):
    """Nome de arquivo de ICP fora do padrão permitido."""


class MissingKeys(RuntimeError):
    """Chaves de API ausentes no .env para executar o pipeline."""


def _safe_icp_path(config_dir: Path, name: str) -> Path:
    if not _ICP_NAME_RE.match(name):
        raise InvalidName(name)
    return config_dir / name


def load_config(
    config_dir: Path = DEFAULT_CONFIG_DIR,
    runtime_path: Path = DEFAULT_RUNTIME,
) -> dict[str, Any]:
    """Snapshot legível da configuração atual para a UI."""
    cfg = load_runtime(runtime_path)
    icp_files = sorted(p.name for p in config_dir.glob("icp_criteria*.json"))
    catalog_path = config_dir / "hypotheses_catalog.json"
    hypotheses: list[dict[str, Any]] = []
    if catalog_path.exists():
        catalog = HypothesisCatalog.model_validate(
            json.loads(catalog_path.read_text(encoding="utf-8"))
        )
        hypotheses = [
            {"id": h.hypothesis_id, "prior": h.prior, "description": h.description}
            for h in catalog.hypotheses
        ]
    return {
        "icp_files": icp_files,
        "scoring": cfg.scoring.model_dump(),
        "tavily": {
            "persona_term": cfg.tavily.persona_term,
            "include_domains": cfg.tavily.include_domains,
            "max_queries": cfg.tavily.max_queries,
        },
        "hypotheses": hypotheses,
    }


def read_icp(config_dir: Path, name: str) -> dict[str, Any]:
    """Lê o JSON cru de um ICP (para edição na UI). Valida o nome do arquivo."""
    path = _safe_icp_path(config_dir, name)
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def read_hypotheses(config_dir: Path) -> dict[str, Any]:
    """Lê o catálogo de hipóteses cru (para edição na UI)."""
    data: dict[str, Any] = json.loads(
        (config_dir / "hypotheses_catalog.json").read_text(encoding="utf-8")
    )
    return data


def save_icp(config_dir: Path, name: str, icp: ICPCriteria) -> None:
    """Grava o ICP (já validado) atomicamente."""
    path = _safe_icp_path(config_dir, name)
    atomic_write_text(path, json.dumps(icp.model_dump(), ensure_ascii=False, indent=2) + "\n")


def save_hypotheses(config_dir: Path, catalog: HypothesisCatalog) -> None:
    """Grava o catálogo de hipóteses (já validado) atomicamente."""
    path = config_dir / "hypotheses_catalog.json"
    atomic_write_text(path, json.dumps(catalog.model_dump(), ensure_ascii=False, indent=2) + "\n")


_ICP_ASSIST_PROMPT = (
    "Voce e especialista em ICP B2B. A partir da DESCRICAO do negocio, gere um "
    "icp_criteria valido. Responda SOMENTE com JSON (sem markdown) neste formato exato "
    "(nao adicione nem renomeie campos):\n"
    '{"icp_id":str_snake_case,"firmographics":{"industries":[str_minusculo],'
    '"employee_range":{"min":int>=0,"max":int>=min},"geographies":{"country":str_ISO2,'
    '"regions":[str]},"business_models":[str]},"technographics":{"mandatory":[str],'
    '"preferred":[str],"excluded":[str]},"persona_matrix":{"target_roles":[STR_MAIUSC],'
    '"min_seniority":str},"intent_triggers":[STR_MAIUSC]}\n'
    "Regras: industries/technographics em minusculas (busca em PT-BR); country ISO-2; "
    "min<=max; sem campos extras. Para servicos cujo decisor e a fundadora, "
    "technographics.mandatory pode ser [] (ferramenta de gestao nao e detectavel).\n\n"
    "DESCRICAO DO NEGOCIO:\n"
)


def assist_icp(description: str, client: CognitionClient) -> ICPCriteria:
    """Gera um rascunho de ICP a partir da descrição do negócio (Gemini) e valida."""
    payload = client.generate_json(_ICP_ASSIST_PROMPT + description.strip())
    return ICPCriteria.model_validate(payload)


def run_for_icp(
    config_dir: Path,
    runtime_path: Path,
    env_path: Path,
    icp_name: str,
) -> list[LeadCard]:
    """Executa o pipeline real (Tavily+Gemini) para o ICP selecionado → Lead Cards."""
    env = load_env(env_path)
    tkey = env.get("TAVILY_API_KEY") or os.environ.get("TAVILY_API_KEY", "")
    gkey = env.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
    if not tkey or not gkey:
        raise MissingKeys("TAVILY_API_KEY/GEMINI_API_KEY ausentes no .env")
    cfg = load_runtime(runtime_path)
    icp = ICPCriteria.model_validate(read_icp(config_dir, icp_name))
    catalog = HypothesisCatalog.model_validate(
        json.loads((config_dir / "hypotheses_catalog.json").read_text(encoding="utf-8"))
    )
    return run_pipeline(
        icp,
        tavily=TavilyClient(tkey),
        gemini=GeminiClient(gkey, model=cfg.gemini.model),
        hypotheses=catalog,
        cache_root=_ROOT / "data" / "cache",
        now=datetime.now(UTC),
        cfg=cfg,
    )


def save_scoring(runtime_path: Path, scoring: dict[str, float]) -> None:
    """Atualiza os pesos de [scoring] no runtime.toml, preservando comentários."""
    text = runtime_path.read_text(encoding="utf-8")
    for key in _SCORING_KEYS:
        if key in scoring:
            text = re.sub(
                rf"(?m)^{key}\s*=\s*.*$",
                f"{key} = {scoring[key]}",
                text,
            )
    atomic_write_text(runtime_path, text)
