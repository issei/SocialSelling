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

from socialselling.apollo.enrich import enrich_organizations
from socialselling.apollo.reveal import reveal_contacts
from socialselling.config import RuntimeConfig, load_env, load_runtime
from socialselling.contracts import (
    HypothesisCatalog,
    ICPCriteria,
    Inference,
    LeadCard,
    LeadContact,
    LeadLinks,
    ProspectScore,
    XAIPayload,
)
from socialselling.core.cache import JsonCache
from socialselling.core.credit_ledger import CreditBudget
from socialselling.core.request_ledger import RequestBudget
from socialselling.corpus.integration import accumulate_and_rank
from socialselling.corpus.store import CorpusStore  # noqa: F401 (re-exported for callers)
from socialselling.modules.m1_busca import is_degraded, run_m1
from socialselling.modules.m2_extracao import run_m2
from socialselling.modules.m3_score import run_m3
from socialselling.modules.m4_ranking import run_m4
from socialselling.modules.m5_xai import run_m5
from socialselling.signals import DISQUALIFIER_VOCAB, intent_vocab
from socialselling.skills.apollo_client import ApolloClient, ApolloSearchClient
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
    apollo: ApolloSearchClient | None = None,
    wave: int = 0,
    corpus_store: CorpusStore | None = None,
) -> list[LeadCard]:
    """Executa M1→M5 e monta a lista ranqueada de Lead Cards acionaveis.

    `apollo` (opt-in, ADR-004): quando fornecido, o M1 agrega a descoberta firmográfica
    do Apollo (degrau 1, 0 crédito). Sem ele, comportamento byte-idêntico ao atual.
    `wave` (default 0): varia as queries do M1 na busca incremental (ADR-006); 0 = paridade.
    """
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
        persona_term=cfg.tavily.persona_term,
        include_domains=cfg.tavily.include_domains,
        apollo_client=apollo,
        wave=wave,
    )
    # Orçamento de requisições Gemini/dia (RPD, ADR-005). Opt-in; desligado => sem gating.
    request_budget: RequestBudget | None = None
    if cfg.gemini.rpd_enabled:
        request_budget = RequestBudget(
            _ROOT / cfg.gemini.rpd_ledger_path, now, rpd_cap=cfg.gemini.rpd_cap
        )
    inferences = run_m2(
        evidences,
        client=gemini,
        cache=JsonCache(cache_root / "gemini"),
        now=now,
        cache_ttl_hours=cfg.cache.ttl_hours,
        intent_vocab=i_vocab,
        disqualifier_vocab=DISQUALIFIER_VOCAB,
        batch_size=cfg.gemini.batch_size,
        request_budget=request_budget,
        corpus_store=corpus_store,
    )

    # Degrau 2 (ADR-004): org-enrich CONDICIONAL (só firmografia faltante), sob crédito.
    # Só com Apollo presente e havendo inferências; senão inalterado (paridade).
    if apollo is not None and inferences:
        inferences = enrich_organizations(
            inferences,
            apollo_client=apollo,
            budget=CreditBudget(
                _ROOT / cfg.apollo.ledger_path,
                now,
                data_cap=cfg.apollo.caps.data_credits_cap,
                email_cap=cfg.apollo.caps.email_credits_cap,
                mobile_cap=cfg.apollo.caps.mobile_credits_cap,
            ),
            cache=JsonCache(cache_root / "apollo_org"),
            now=now,
            ttl_hours=cfg.apollo.org_enrich_ttl_hours,
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
        persona_weights=cfg.persona.model_dump(),
    )
    ranked_scores = run_m4(scores)
    by_company = {inf.company.company_id: inf for inf in inferences}
    ev_url = {ev.evidence_id: ev.source_url for ev in evidences if ev.source_url}
    degraded = is_degraded(evidences)

    cards: list[LeadCard] = []
    rank = 1
    for score in ranked_scores:
        inference = by_company.get(score.company_id)
        if inference is None:
            continue
        explanation = run_m5(score, inference, icp, degraded_mode=degraded)
        cards.append(_to_lead_card(rank, score, inference, explanation, ev_url))
        rank += 1
    cards = cards[: cfg.runtime.max_leads_per_cycle]

    # Degrau 3 (ADR-004): reveal de contato do top-N, sob orçamento de crédito.
    # Só com Apollo presente (opt-in) e havendo cards; sem isso, inalterado (paridade).
    if apollo is not None and cards:
        budget = CreditBudget(
            _ROOT / cfg.apollo.ledger_path,
            now,
            data_cap=cfg.apollo.caps.data_credits_cap,
            email_cap=cfg.apollo.caps.email_credits_cap,
            mobile_cap=cfg.apollo.caps.mobile_credits_cap,
        )
        cards = reveal_contacts(
            cards,
            apollo_client=apollo,
            budget=budget,
            cache=JsonCache(cache_root / "apollo_reveal"),
            now=now,
            reveal_ttl_hours=cfg.apollo.reveal_ttl_hours,
            top_n_cap=cfg.apollo.reveal_top_n,
        )
    return cards


def _to_lead_card(
    rank: int,
    score: ProspectScore,
    inference: Inference,
    explanation: XAIPayload,
    ev_url: dict[str, str],
) -> LeadCard:
    """Monta o cartao acionavel a partir do score + inferencia + explicacao."""
    company = inference.company
    person = inference.people[0] if inference.people else None
    display_name = person.normalized_name if person else company.normalized_name
    sources: list[str] = []
    for eid in inference.derived_from:
        url = ev_url.get(eid)
        if url and url not in sources:
            sources.append(url)
    return LeadCard(
        rank=rank,
        display_name=display_name,
        company=company.normalized_name,
        role=person.role_title if person else None,
        sector=company.industry,
        location=company.location,
        links=LeadLinks(
            instagram=company.instagram_url,
            linkedin=company.linkedin_url,
            website=company.website,
        ),
        contact=LeadContact(email=company.email, phone=company.phone),
        score=score,
        why_now=[d.text for d in explanation.positive_signals],
        gaps=explanation.missing_signals,
        sources=sources[:5],
    )


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


def persist_json(cards: list[LeadCard], path: Path) -> None:
    payload = [c.model_dump() for c in cards]
    _atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def render_report(cards: list[LeadCard]) -> str:
    """Relatório de Lead Cards acionáveis (Instagram em primeiro)."""
    lines = ["# Quem abordar primeiro\n"]
    if not cards:
        lines.append("_Nenhum lead qualificado neste ciclo._")
        return "\n".join(lines)
    for card in cards:
        header = f"## #{card.rank} · {card.display_name}"
        if card.role and card.company:
            header += f" — {card.role} @ {card.company}"
        elif card.company and card.company != card.display_name:
            header += f" — {card.company}"
        lines.append(header)
        meta = " · ".join(p for p in [card.sector, card.location] if p)
        s = card.score
        lines.append(
            f"   {meta + ' · ' if meta else ''}P={s.p_score:.3f} "
            f"(fit {s.fit:.2f} · intent {s.intent:.2f} · conf {s.confidence:.2f} "
            f"· persona {s.persona_fit:.2f})"
        )
        if card.links.instagram:
            lines.append(f"   📸 Instagram: {card.links.instagram}")
        lines.append(
            f"   🔗 LinkedIn: {card.links.linkedin or '—'}    🌐 Site: {card.links.website or '—'}"
        )
        contact_bits = [b for b in [card.contact.email, card.contact.phone] if b]
        if contact_bits:
            lines.append(f"   ✉️ Contato: {' · '.join(contact_bits)}")
        if card.why_now:
            lines.append(f"   Por que agora: {' · '.join(card.why_now)}")
        if card.gaps:
            lines.append(f"   Lacunas: {' · '.join(card.gaps)}")
        lines.append(f"   Fontes: {len(card.sources)} evidência(s)")
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

    # Sensor Apollo opt-in (ADR-004): só ativa com [apollo].enabled + chave presente.
    apollo: ApolloSearchClient | None = None
    if cfg.apollo.enabled:
        apollo_key = env.get("APOLLO_API_KEY") or os.environ.get("APOLLO_API_KEY", "")
        if apollo_key:
            apollo = ApolloClient(apollo_key, base_url=cfg.apollo.base_url)
        else:
            print(
                "AVISO: [apollo].enabled mas APOLLO_API_KEY ausente; descoberta Apollo off",
                file=sys.stderr,
            )

    now = datetime.now(UTC)
    # Corpus acumulativo (ADR-006): inicializado antes de run_pipeline para ativar
    # process-only-new (skip de re-extração Gemini para entidades já no corpus).
    corpus_store: CorpusStore | None = None
    if cfg.corpus.enabled:
        corpus_store = CorpusStore(_ROOT / cfg.corpus.path)

    cards = run_pipeline(
        icp,
        tavily=TavilyClient(tavily_key),
        gemini=GeminiClient(gemini_key, model=cfg.gemini.model),
        hypotheses=hypotheses,
        cache_root=_ROOT / "data" / "cache",
        now=now,
        cfg=cfg,
        apollo=apollo,
        corpus_store=corpus_store,
    )

    if corpus_store is not None:
        cards = accumulate_and_rank(
            corpus_store, cards, now, max_display=cfg.runtime.max_leads_per_cycle
        )
        print(f"corpus: {len(corpus_store)} leads conhecidos (acumulado)", file=sys.stderr)

    out_path = Path(args.out)
    persist_json(cards, out_path)
    _atomic_write(out_path.with_suffix(".md"), render_report(cards))
    print(f"OK: {len(cards)} leads -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
