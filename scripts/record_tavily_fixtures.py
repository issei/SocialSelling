"""Grava fixtures REAIS da Tavily para os testes determinísticos do M1.

Uso (com venv e .env preenchido):
    .venv/Scripts/python.exe scripts/record_tavily_fixtures.py

Lê o ICP de exemplo, gera as queries do M1, chama a Tavily de verdade e
salva cada resposta em tests/fixtures/tavily/<sha256(query)>.json.
NÃO faz parte do runtime do produto — é ferramenta de teste.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from socialselling.contracts import ICPCriteria  # noqa: E402
from socialselling.core.cache import query_hash  # noqa: E402
from socialselling.modules.m1_busca import generate_queries  # noqa: E402
from socialselling.skills.tavily_client import TavilyClient  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "tavily"
MAX_QUERIES = 3
MAX_RESULTS = 10
SEARCH_DEPTH = "basic"


def _load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env[key] = value
    return env


def main() -> int:
    key = _load_env().get("TAVILY_API_KEY") or os.environ.get("TAVILY_API_KEY", "")
    if not key:
        print("TAVILY_API_KEY ausente no .env", file=sys.stderr)
        return 1
    icp = ICPCriteria.model_validate(
        json.loads((ROOT / "config" / "icp_criteria.example.json").read_text("utf-8"))
    )
    client = TavilyClient(key)
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for query in generate_queries(icp, MAX_QUERIES):
        payload = client.search(query, MAX_RESULTS, SEARCH_DEPTH)
        # normaliza para reduzir flutuação entre gravações
        slim = {
            "results": [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", ""),
                    "score": r.get("score", 0.5),
                }
                for r in payload.get("results", [])
            ]
        }
        out = FIXTURES / f"{query_hash(query)}.json"
        out.write_text(json.dumps(slim, ensure_ascii=False, indent=2, sort_keys=True), "utf-8")
        print(f"gravado: {query!r} -> {out.name} ({len(slim['results'])} results)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
