"""Steps BDD para WU-E3 — CLI publish (ADR-010, SDD §6.2). HTTP mockado; sem rede."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenario, then, when

from socialselling.contracts import LeadCard, LeadContact, LeadLinks, ProspectScore
from socialselling.sync.publish import build_published_snapshot, publish

FEATURE = "../features/wu_e3_publish_cli.feature"

_GEN_AT = "2026-06-13T00:00:00+00:00"


@scenario(FEATURE, "Publicação feliz do top-20 sem score")
def test_publish_feliz() -> None:
    pass


@scenario(FEATURE, "Republicação do mesmo ranking é idempotente")
def test_publish_idempotente() -> None:
    pass


@scenario(FEATURE, "Portal fora do ar não quebra o motor (degradado)")
def test_publish_degradado() -> None:
    pass


@scenario(FEATURE, "Snapshot preserva missing_evidence (Open-World)")
def test_publish_open_world() -> None:
    pass


def _make_card(rank: int, *, gaps: list[str] | None = None) -> LeadCard:
    """LeadCard determinístico; p_score decresce com o rank (ordem estável)."""
    return LeadCard(
        rank=rank,
        display_name=f"Empresa {rank}",
        company=f"Empresa {rank}",
        sector="Saúde",
        location="São Paulo, SP",
        links=LeadLinks(website=f"https://empresa{rank}.com.br"),
        contact=LeadContact(email=f"contato{rank}@empresa{rank}.com.br"),
        score=ProspectScore(
            company_id=f"empresa{rank}.com.br",
            fit=0.9 - rank * 0.001,
            intent=0.5,
            confidence=0.8,
            persona_fit=1.0,
            p_score=1000.0 - rank,
        ),
        why_now=[f"sinal positivo {rank}"],
        gaps=list(gaps) if gaps is not None else [],
    )


@pytest.fixture
def ctx() -> dict[str, Any]:
    return {}


# --------------------------------------------------------------------------- Given


@given("uma visão ranqueada do perfil \"talita\" com 32 leads", target_fixture="ctx")
def given_ranked_32() -> dict[str, Any]:
    return {"cards": [_make_card(i) for i in range(1, 33)]}


@given(
    'uma visão ranqueada com um lead cujo gaps lista "sem sinal de contratação"',
    target_fixture="ctx",
)
def given_ranked_open_world() -> dict[str, Any]:
    return {"cards": [_make_card(1, gaps=["sem sinal de contratação"])]}


# --------------------------------------------------------------------------- When


@when('executo publish para "talita" com o portal respondendo 201')
def when_publish_201(ctx: dict[str, Any], tmp_path: Path) -> None:
    ctx["root"] = tmp_path
    ctx["exit"] = publish(
        "talita",
        ctx["cards"],
        generated_at=_GEN_AT,
        dry_run=False,
        portal_base_url="http://portal.test",
        token="tok",
        root=tmp_path,
        http_post=lambda url, payload, token: (ctx.setdefault("sent", payload), 201)[1],
    )


@when('executo publish para "talita" com o portal respondendo 409')
def when_publish_409(ctx: dict[str, Any], tmp_path: Path) -> None:
    ctx["root"] = tmp_path
    ctx["exit"] = publish(
        "talita",
        ctx["cards"],
        generated_at=_GEN_AT,
        dry_run=False,
        portal_base_url="http://portal.test",
        token="tok",
        root=tmp_path,
        http_post=lambda url, payload, token: 409,
    )


@when('executo publish para "talita" com o portal recusando conexão')
def when_publish_conn_refused(ctx: dict[str, Any], tmp_path: Path) -> None:
    ctx["root"] = tmp_path

    def _boom(url: str, payload: dict[str, object], token: str) -> int:
        raise ConnectionError("Connection refused")

    ctx["exit"] = publish(
        "talita",
        ctx["cards"],
        generated_at=_GEN_AT,
        dry_run=False,
        portal_base_url="http://portal.test",
        token="tok",
        root=tmp_path,
        http_post=_boom,
    )


@when("computo o run_id duas vezes para o mesmo ranking")
def when_run_id_twice(ctx: dict[str, Any]) -> None:
    # run_id ignora o relógio: generated_at diferente, mesmo conteúdo → mesmo run_id.
    snap_a, _ = build_published_snapshot("talita", ctx["cards"], generated_at=_GEN_AT)
    snap_b, _ = build_published_snapshot(
        "talita", ctx["cards"], generated_at="2099-01-01T00:00:00+00:00"
    )
    ctx["run_id_a"] = snap_a.run_id
    ctx["run_id_b"] = snap_b.run_id


@when('o snapshot é montado para "talita"')
def when_build_snapshot(ctx: dict[str, Any]) -> None:
    snap, _ = build_published_snapshot("talita", ctx["cards"], generated_at=_GEN_AT)
    ctx["snapshot"] = snap


# --------------------------------------------------------------------------- Then


@then("o snapshot enviado tem 20 leads com rank_position 1..20")
def then_top20(ctx: dict[str, Any]) -> None:
    leads = ctx["sent"]["leads"]
    assert len(leads) == 20
    assert [lead["rank_position"] for lead in leads] == list(range(1, 21))


@then("nenhum campo numérico de score aparece no payload publicado")
def then_no_score(ctx: dict[str, Any]) -> None:
    blob = json.dumps(ctx["sent"])
    for forbidden in ("p_score", "fit", "intent", "confidence", "persona_fit", "score"):
        assert forbidden not in blob, f"campo de score vazou: {forbidden}"


@then('o registro local de "talita" guarda os scores por entity_id')
def then_local_scores(ctx: dict[str, Any]) -> None:
    files = list((ctx["root"] / "data" / "published" / "talita").glob("*.json"))
    assert len(files) == 1, f"esperado 1 registro local, obtido {len(files)}"
    record = json.loads(files[0].read_text(encoding="utf-8"))
    assert record["scores"], "scores ausentes no registro local"
    first = next(iter(record["scores"].values()))
    assert set(first) == {"fit", "intent", "confidence", "persona_fit", "p_score"}


@then("a CLI termina com sucesso")
def then_exit_ok(ctx: dict[str, Any]) -> None:
    assert ctx["exit"] == 0, f"exit code {ctx['exit']}"


@then("a CLI termina com falha e mensagem acionável")
def then_exit_fail(ctx: dict[str, Any]) -> None:
    assert ctx["exit"] != 0, "esperava exit code != 0 na degradação"


@then("os dois run_id são idênticos")
def then_run_id_eq(ctx: dict[str, Any]) -> None:
    assert ctx["run_id_a"] == ctx["run_id_b"]


@then('o missing_evidence do lead lista "sem sinal de contratação"')
def then_missing_evidence(ctx: dict[str, Any]) -> None:
    lead = ctx["snapshot"].leads[0]
    assert "sem sinal de contratação" in lead.missing_evidence


@then("o lead permanece publicado")
def then_lead_published(ctx: dict[str, Any]) -> None:
    assert len(ctx["snapshot"].leads) == 1
