"""Orquestrador do pipeline M1→M5 (em memória) + CLI + persistência atômica.

run_pipeline encadeia os módulos de forma determinística (dados clientes, cache,
relógio e config injetados). A CLI conecta os clientes reais (Tavily/Gemini) lendo
chaves do .env. O smoke test injeta clientes fake (fixtures) — sem rede.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from socialselling.config import RuntimeConfig, load_env, load_runtime
from socialselling.contracts import HypothesisCatalog, ICPCriteria, RankedProspect
from socialselling.core.cache import JsonCache
from socialselling.modules.m1_busca import is_degraded, run_m1
from socialselling.modules.m2_extracao import run_m2
from socialselling.modules.m3_score import run_m3
from socialselling.modules.m4_ranking import run_m4
from socialselling.modules.m5_xai import run_m5
from socialselling.signals import DISQUALIFIER_VOCAB, intent_vocab
from socialselling.skills.gemini_client import CognitionClient, GeminiClient
from socialselling.skills.tavily_client import SearchClient, TavilyClient

_ROOT = Path(__file__).resolve().parents[2]


def run_pipeline(
    icp: ICPCriteria,
    *,
    tavily: SearchClient,
    gemini: CognitionClient,
    hypotheses: HypothesisCatalog,
    cache_root: Path,
    now: datetime,
    cfg: RuntimeConfig,
) -> list[RankedProspect]:
    """Executa M1→M5 e monta a lista ranqueada de prospects."""
    i_vocab = intent_vocab(hypotheses)
    evidences = run_m1(
        icp,
        client=tavily,
        cache=JsonCache(cache_root / "tavily"),
        now=now,
        max_queries=cfg.tavily.max_queries,
        max_results=cfg.tavily.max_results,
        search_depth=cfg.tavily.search_depth,
        cache_ttl_hours=cfg.cache.ttl_hours,
    )
    inferences = run_m2(
        evidences,
        client=gemini,
        cache=JsonCache(cache_root / "gemini"),
        now=now,
        cache_ttl_hours=cfg.cache.ttl_hours,
        intent_vocab=i_vocab,
        disqualifier_vocab=DISQUALIFIER_VOCAB,
    )
    scores = run_m3(
        inferences,
        icp,
        hypotheses,
        w_fit=cfg.scoring.w_fit,
        w_intent=cfg.scoring.w_intent,
        confidence_exponent=cfg.scoring.confidence_exponent,
        w_fit_tech=cfg.scoring.w_fit_tech,
        w_fit_industry=cfg.scoring.w_fit_industry,
    )
    ranked_scores = run_m4(scores)
    by_company = {inf.company.company_id: inf for inf in inferences}
    degraded = is_degraded(evidences)

    prospects: list[RankedProspect] = []
    rank = 1
    for score in ranked_scores:
        inference = by_company.get(score.company_id)
        if inference is None:
            continue
        explanation = run_m5(score, inference, icp, degraded_mode=degraded)
        prospects.append(RankedProspect(rank=rank, score=score, explanation=explanation))
        rank += 1
    return prospects[: cfg.runtime.max_leads_per_cycle]


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def persist_json(prospects: list[RankedProspect], path: Path) -> None:
    payload = [p.model_dump() for p in prospects]
    _atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def render_report(prospects: list[RankedProspect]) -> str:
    """Relatório legível: 'aborde X porque…'."""
    lines = ["# Quem abordar primeiro\n"]
    if not prospects:
        lines.append("_Nenhum prospect qualificado neste ciclo._")
        return "\n".join(lines)
    for prospect in prospects:
        company = prospect.score.company_id
        lines.append(f"## #{prospect.rank} — {company} (P={prospect.score.p_score:.3f})")
        for driver in prospect.explanation.positive_signals:
            lines.append(f"- ✅ {driver.text} ({driver.impact})")
        for driver in prospect.explanation.negative_signals:
            lines.append(f"- ⚠️ {driver.text}")
        for gap in prospect.explanation.missing_signals:
            lines.append(f"- ❔ sinal ausente: {gap}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SocialSelling — pipeline M1→M5 (PoC).")
    parser.add_argument("--icp", required=True, help="caminho do icp_criteria.json")
    parser.add_argument("--out", default=str(_ROOT / "data" / "prospects_ranked.json"))
    parser.add_argument("--config", default=str(_ROOT / "config" / "runtime.toml"))
    parser.add_argument("--hypotheses", default=str(_ROOT / "config" / "hypotheses_catalog.json"))
    args = parser.parse_args(argv)

    cfg = load_runtime(Path(args.config))
    env = load_env(_ROOT / ".env")
    tavily_key = env.get("TAVILY_API_KEY") or os.environ.get("TAVILY_API_KEY", "")
    gemini_key = env.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
    if not tavily_key or not gemini_key:
        print("ERRO: TAVILY_API_KEY/GEMINI_API_KEY ausentes no .env", file=sys.stderr)
        return 1

    icp = ICPCriteria.model_validate(json.loads(Path(args.icp).read_text("utf-8")))
    hypotheses = HypothesisCatalog.model_validate(
        json.loads(Path(args.hypotheses).read_text("utf-8"))
    )
    prospects = run_pipeline(
        icp,
        tavily=TavilyClient(tavily_key),
        gemini=GeminiClient(gemini_key, model=cfg.gemini.model),
        hypotheses=hypotheses,
        cache_root=_ROOT / "data" / "cache",
        now=datetime.now(UTC),
        cfg=cfg,
    )
    out_path = Path(args.out)
    persist_json(prospects, out_path)
    _atomic_write(out_path.with_suffix(".md"), render_report(prospects))
    print(f"OK: {len(prospects)} prospects -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
