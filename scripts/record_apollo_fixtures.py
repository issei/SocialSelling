"""Grava fixtures REAIS do Apollo (People Search) para os testes determinísticos.

Uso (SUPERVISIONADO — com venv e .env com APOLLO_API_KEY):
    .venv/Scripts/python.exe scripts/record_apollo_fixtures.py

IMPORTANTE (FinOps / ADR-004 §0):
- People Search (`mixed_people/search`) é **0 crédito**, MAS o endpoint da API exige
  **plano Apollo PAGO** — no tier gratuito retorna HTTP 403 `API_INACCESSIBLE`. O
  "0 crédito" vale só na interface web; a master API é bloqueada por completo no Free.
  Logo, este script só funciona com plano pago. Ver L-056.
- Grava SOMENTE People Search. NÃO chama org-enrich nem people/match (esses CONSOMEM
  crédito) — para evitar gastar a cota mensal sem intenção.
- É ferramenta de teste, fora do runtime do produto.

Lê o ICP de exemplo, monta os filtros do degrau 1 e salva a resposta crua em
tests/fixtures/apollo/people_search/<sha256(filtros)>.json.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from socialselling.apollo.ladder import icp_to_people_filters  # noqa: E402
from socialselling.config import load_runtime  # noqa: E402
from socialselling.contracts import ICPCriteria  # noqa: E402
from socialselling.core.cache import query_hash  # noqa: E402
from socialselling.skills.apollo_client import ApolloClient  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "apollo" / "people_search"
ICP_PATH = ROOT / "config" / "icp_criteria.talita.json"


def _load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env[key] = value
    return env


def main() -> int:
    key = _load_env().get("APOLLO_API_KEY") or os.environ.get("APOLLO_API_KEY", "")
    if not key:
        print("APOLLO_API_KEY ausente no .env", file=sys.stderr)
        return 1
    icp = ICPCriteria.model_validate(json.loads(ICP_PATH.read_text("utf-8")))
    cfg = load_runtime(ROOT / "config" / "runtime.toml")
    client = ApolloClient(key, base_url=cfg.apollo.base_url)
    filters = icp_to_people_filters(icp, persona_term=cfg.tavily.persona_term)

    print("Gravando SOMENTE People Search (0 credito). Org-enrich/people-match NAO sao chamados.")
    payload = client.people_search(filters, per_page=25)

    FIXTURES.mkdir(parents=True, exist_ok=True)
    key_hash = query_hash(json.dumps(filters, sort_keys=True))[:16]
    out = FIXTURES / f"{key_hash}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), "utf-8")
    n = len(payload.get("people", []) or [])
    print(f"gravado: filtros={filters} -> {out.name} ({n} pessoas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
