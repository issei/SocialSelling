"""Sondagem empirica (NAO faz parte do runtime): o que e achavel do publico Talita?

Roda buscas reais no Tavily (generica e filtrada por instagram/linkedin) e uma
extracao orientada a CONTATO no Gemini, para informar (a) a aderencia da busca e
(b) o schema da apresentacao final. Saida so no console.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from socialselling.skills.gemini_client import GeminiClient  # noqa: E402

QUERIES = [
    "consultoria empresarial fundadora instagram",
    "escritorio advocacia socia fundadora sao paulo",
    "software house founder brasil linkedin",
    "consultoria financeira empresaria crescimento equipe",
]


def _env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k] = v
    return env


def tavily(key: str, query: str, *, domains: list[str] | None) -> list[dict[str, Any]]:
    body: dict[str, Any] = {
        "api_key": key,
        "query": query,
        "max_results": 5,
        "search_depth": "basic",
    }
    if domains:
        body["include_domains"] = domains
    r = httpx.post("https://api.tavily.com/search", json=body, timeout=30)
    r.raise_for_status()
    results: list[dict[str, Any]] = r.json().get("results", [])
    return results


def main() -> int:
    env = _env()
    tkey = env["TAVILY_API_KEY"]
    gkey = env["GEMINI_API_KEY"]

    print("=" * 78)
    print("PARTE 1 — BUSCA TAVILY (generica vs filtrada por instagram/linkedin)")
    print("=" * 78)
    harvested: list[dict[str, Any]] = []
    for q in QUERIES:
        print(f"\n### QUERY: {q}")
        gen = tavily(tkey, q, domains=None)
        print("  [generica]")
        for res in gen[:4]:
            print(f"    - {res.get('url', '')}")
            print(f"      {str(res.get('title', ''))[:90]}")
        harvested.extend(gen)
        soc = tavily(tkey, q, domains=["instagram.com", "linkedin.com"])
        print("  [instagram/linkedin]")
        if not soc:
            print("    (nada)")
        for res in soc[:4]:
            print(f"    - {res.get('url', '')}")
            print(f"      {str(res.get('title', ''))[:90]}")

    print("\n" + "=" * 78)
    print("PARTE 2 — EXTRACAO ORIENTADA A CONTATO (Gemini) sobre os resultados")
    print("=" * 78)
    evidence_lines = []
    for res in harvested[:18]:
        evidence_lines.append(
            f"- url={res.get('url', '')} | titulo={res.get('title', '')} | "
            f"trecho={str(res.get('content', ''))[:400]}"
        )
    prompt = (
        "Voce extrai LEADS (empresarias fundadoras de servicos) dos resultados abaixo. "
        'Responda SOMENTE JSON: {"leads":[{"nome":str|null,"empresa":str|null,'
        '"papel":str|null,"setor":str|null,"localizacao":str|null,'
        '"website":str|null,"instagram_url":str|null,"linkedin_url":str|null,'
        '"email":str|null,"telefone":str|null,"fonte_url":str,'
        '"sinais":[str],"confianca":number}]}. '
        "Preencha so o que estiver EVIDENTE; use null quando nao houver. Nao invente.\n\n"
        + "\n".join(evidence_lines)
    )
    payload = GeminiClient(gkey).generate_json(prompt)
    leads = payload.get("leads", [])
    print(f"\nleads extraidos: {len(leads)}")
    for lead in leads[:8]:
        print(json.dumps(lead, ensure_ascii=False, indent=2))
    # cobertura de campos
    fields = ["instagram_url", "linkedin_url", "website", "email", "telefone", "localizacao"]
    print("\nCOBERTURA de campos (quantos leads tem cada um):")
    for f in fields:
        n = sum(1 for x in leads if x.get(f))
        print(f"  {f}: {n}/{len(leads)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
