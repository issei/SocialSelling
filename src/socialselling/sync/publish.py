"""CLI `publish` — motor publica o top-20 do ranking no portal (ADR-010, SDD §6.2).

`py -m socialselling.sync.publish --profile <profile_id> [--dry-run]`

- Mapeia a visão ranqueada (LeadCards, ADR-006) para `PublishedSnapshot` SEM score.
- `run_id` determinístico por conteúdo (sem relógio) → republicação idêntica = 409 idempotente.
- Registro local atômico em `data/published/<profile_id>/<run_id>.json` com snapshot + scores
  por entity_id (é onde o join score↔desfecho da calibração acontece; o portal nunca vê score).
- `--dry-run` para no registro local; senão `POST /api/publish` com Bearer.

REGRA: HTTP sempre mockado nos testes (injeção de `http_post`). O motor nunca acessa o banco.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path

from socialselling.contracts import LeadCard
from socialselling.core.atomic import atomic_write_text
from socialselling.core.identity import canonical_entity_id
from socialselling.portal.contracts import (
    MAX_LEADS_PER_SNAPSHOT,
    PublishedDriver,
    PublishedLead,
    PublishedSnapshot,
)

_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# http_post(url, payload, token) -> status_code; lança exceção se a conexão falhar.
HttpPost = Callable[[str, dict[str, object], str], int]


def _split_location(location: str | None) -> tuple[str | None, str | None]:
    """Split best-effort de "Cidade, UF" → (cidade, uf). Sem vírgula → (location, None)."""
    if not location:
        return None, None
    parts = [p.strip() for p in location.split(",")]
    if len(parts) >= 2 and parts[0] and parts[1]:
        return parts[0], parts[1]
    return location.strip() or None, None


def _entity_id_for(card: LeadCard, cidade: str | None) -> str:
    name = card.company or card.display_name
    return canonical_entity_id(card.links.website, name, cidade)


def build_published_snapshot(
    profile_id: str,
    cards: list[LeadCard],
    *,
    generated_at: str,
) -> tuple[PublishedSnapshot, dict[str, dict[str, float]]]:
    """Monta o snapshot (top-20, sem score) + os scores por entity_id (registro local).

    `cards` já vem ranqueado (visão do corpus). Aplica o teto top-20 e reposiciona
    rank_position 1..N. Drivers positivos vêm de `why_now`; `missing_evidence` de `gaps`
    (references de proveniência não são persistidas no corpus → lista vazia, Open-World:
    ausência não é fabricada).
    """
    leads: list[PublishedLead] = []
    scores_by_entity: dict[str, dict[str, float]] = {}

    for position, card in enumerate(cards[:MAX_LEADS_PER_SNAPSHOT], start=1):
        cidade, uf = _split_location(card.location)
        entity_id = _entity_id_for(card, cidade)
        drivers = [
            PublishedDriver(impact="positive", text=text, references=[])
            for text in card.why_now
        ]
        leads.append(
            PublishedLead(
                entity_id=entity_id,
                rank_position=position,
                company=card.company or card.display_name,
                segmento=card.sector,
                cidade=cidade,
                uf=uf,
                instagram=card.links.instagram,
                site=card.links.website,
                email=card.contact.email,
                telefone=card.contact.phone,
                drivers=drivers,
                missing_evidence=list(card.gaps),
            )
        )
        scores_by_entity[entity_id] = {
            "fit": card.score.fit,
            "intent": card.score.intent,
            "confidence": card.score.confidence,
            "persona_fit": card.score.persona_fit,
            "p_score": card.score.p_score,
        }

    run_id = compute_run_id(profile_id, leads)
    snapshot = PublishedSnapshot(
        profile_id=profile_id,
        run_id=run_id,
        generated_at=generated_at,
        leads=leads,
    )
    return snapshot, scores_by_entity


def compute_run_id(profile_id: str, leads: list[PublishedLead]) -> str:
    """run_id determinístico por conteúdo (sem relógio): sha256(...)[:16]."""
    body = ",".join(f"{lead.rank_position}:{lead.entity_id}" for lead in leads)
    raw = f"{profile_id}|{body}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def write_local_record(
    root: Path,
    snapshot: PublishedSnapshot,
    scores_by_entity: dict[str, dict[str, float]],
) -> Path:
    """Grava o registro local atômico data/published/<profile>/<run_id>.json (snapshot+scores)."""
    path = root / "data" / "published" / snapshot.profile_id / f"{snapshot.run_id}.json"
    record = {
        "snapshot": snapshot.model_dump(),
        "scores": scores_by_entity,
    }
    atomic_write_text(path, json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2))
    return path


def _httpx_post(url: str, payload: dict[str, object], token: str) -> int:
    import httpx

    response = httpx.post(
        url, json=payload, headers={"Authorization": f"Bearer {token}"}, timeout=30.0
    )
    return response.status_code


def publish(
    profile_id: str,
    cards: list[LeadCard],
    *,
    generated_at: str,
    dry_run: bool,
    portal_base_url: str = "",
    token: str = "",
    root: Path = _ROOT,
    http_post: HttpPost | None = None,
) -> int:
    """Executa a publicação. Retorna exit code (0=sucesso; !=0=falha degradada).

    Registro local SEMPRE gravado (antes do POST) → degradação deixa snapshot pronto p/ reenvio.
    201 e 409 = sucesso idempotente. Conexão falha → mensagem acionável, exit != 0, dados intactos.
    """
    snapshot, scores_by_entity = build_published_snapshot(
        profile_id, cards, generated_at=generated_at
    )
    local_path = write_local_record(root, snapshot, scores_by_entity)

    if dry_run:
        print(f"[dry-run] snapshot {snapshot.run_id} gravado em {local_path}")
        return 0

    poster = http_post if http_post is not None else _httpx_post
    url = f"{portal_base_url.rstrip('/')}/api/publish"
    try:
        status = poster(url, snapshot.model_dump(), token)
    except Exception as exc:  # noqa: BLE001 — degradação: qualquer falha de rede
        print(
            f"ERRO: portal inacessível ({exc}). Snapshot salvo em {local_path}; "
            f"reenvie quando o portal voltar.",
            file=sys.stderr,
        )
        return 1

    if status in (201, 409):
        print(f"OK: snapshot {snapshot.run_id} publicado (HTTP {status}).")
        return 0

    print(
        f"ERRO: portal respondeu HTTP {status}. Snapshot salvo em {local_path}.",
        file=sys.stderr,
    )
    return 1


def _load_ranked_cards(profile_id: str, root: Path) -> list[LeadCard]:
    """Carrega a visão ranqueada do corpus (ADR-006). Single-corpus no piloto."""
    from socialselling.config import load_runtime
    from socialselling.corpus.integration import ranked_view
    from socialselling.corpus.store import CorpusStore

    cfg = load_runtime(root / "config" / "runtime.toml")
    store = CorpusStore(root / cfg.corpus.path)
    return ranked_view(store, max_display=MAX_LEADS_PER_SNAPSHOT)


def main(argv: list[str] | None = None) -> int:
    from datetime import UTC, datetime

    parser = argparse.ArgumentParser(prog="publish", description="Publica top-20 no portal.")
    parser.add_argument("--profile", required=True, help="profile_id da operadora")
    parser.add_argument("--dry-run", action="store_true", help="só grava o registro local")
    args = parser.parse_args(argv)

    cards = _load_ranked_cards(args.profile, _ROOT)
    if not cards:
        print(f"ERRO: corpus vazio para '{args.profile}'; rode o pipeline antes.", file=sys.stderr)
        return 1

    return publish(
        args.profile,
        cards,
        generated_at=datetime.now(UTC).isoformat(),
        dry_run=args.dry_run,
        portal_base_url=os.environ.get("PORTAL_BASE_URL", ""),
        token=os.environ.get("PORTAL_PUBLISH_TOKEN", ""),
    )


if __name__ == "__main__":
    raise SystemExit(main())
