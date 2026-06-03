"""Grava a fixture REAL do Gemini para os testes determinísticos do M2.

Uso (com venv e .env preenchido):
    .venv/Scripts/python.exe scripts/record_gemini_fixtures.py

Roda o M1 sobre as fixtures Tavily gravadas (sem rede), monta o prompt do M2,
chama o Gemini de verdade e salva a resposta em
tests/fixtures/gemini/<sha256(prompt)>.json.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from socialselling.contracts import HypothesisCatalog, ICPCriteria  # noqa: E402
from socialselling.core.cache import JsonCache, query_hash  # noqa: E402
from socialselling.modules.m1_busca import run_m1  # noqa: E402
from socialselling.modules.m2_extracao import build_prompt  # noqa: E402
from socialselling.signals import DISQUALIFIER_VOCAB, intent_vocab  # noqa: E402
from socialselling.skills.gemini_client import GeminiClient  # noqa: E402

TAVILY_FIXTURES = ROOT / "tests" / "fixtures" / "tavily"
GEMINI_FIXTURES = ROOT / "tests" / "fixtures" / "gemini"
NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _FixtureTavily:
    """Cliente Tavily de fixture (sem rede) para reconstruir as evidências do M1."""

    def search(self, query: str, max_results: int, search_depth: str) -> dict[str, Any]:
        path = TAVILY_FIXTURES / f"{query_hash(query)}.json"
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return data


def _load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env[key] = value
    return env


def main() -> int:
    key = _load_env().get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        print("GEMINI_API_KEY ausente no .env", file=sys.stderr)
        return 1
    icp = ICPCriteria.model_validate(
        json.loads((ROOT / "config" / "icp_criteria.example.json").read_text("utf-8"))
    )
    evidences = run_m1(
        icp,
        client=_FixtureTavily(),
        cache=JsonCache(ROOT / "data" / "cache" / "_record_tmp"),
        now=NOW,
        max_queries=3,
        max_results=10,
        search_depth="basic",
        cache_ttl_hours=24,
    )
    catalog = HypothesisCatalog.model_validate(
        json.loads((ROOT / "config" / "hypotheses_catalog.json").read_text("utf-8"))
    )
    prompt = build_prompt(
        [ev for ev in evidences if not ev.missing_evidence],
        intent_vocab(catalog),
        DISQUALIFIER_VOCAB,
    )
    payload = GeminiClient(key).generate_json(prompt)
    GEMINI_FIXTURES.mkdir(parents=True, exist_ok=True)
    out = GEMINI_FIXTURES / f"{query_hash(prompt)}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), "utf-8")
    n = len(payload.get("inferences", []))
    print(f"gravado: {out.name} ({n} inferences) a partir de {len(evidences)} evidencias")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
