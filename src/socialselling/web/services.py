"""Ponte fina entre a UI web e o núcleo (lê/grava os mesmos artefatos de config).

NÃO contém lógica de pipeline — apenas orquestra leitura/escrita de configuração
e delega ao núcleo. Mantém o núcleo (M1–M5) intocado (ADR-002).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from socialselling.config import load_runtime
from socialselling.contracts import HypothesisCatalog

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_DIR = _ROOT / "config"
DEFAULT_RUNTIME = _ROOT / "config" / "runtime.toml"


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
