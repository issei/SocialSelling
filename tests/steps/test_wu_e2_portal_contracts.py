"""Steps BDD para WU-E2 — contratos do portal e catálogo de feedback."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from pytest_bdd import given, scenario, then, when

from socialselling.portal.catalog import load_feedback_catalog
from socialselling.portal.contracts import (
    FeedbackCatalog,
    FeedbackEvent,
    FeedbackKind,
    PublishedLead,
    PublishedSnapshot,
    Reaction,
)

FEATURE = "../features/wu_e2_portal_contracts.feature"


# ---------------------------------------------------------------------------
# Cenários registrados
# ---------------------------------------------------------------------------


@scenario(FEATURE, "Round-trip de PublishedSnapshot (serialização e desserialização)")
def test_snapshot_roundtrip() -> None:
    pass


@scenario(FEATURE, "Ranks não-estritos são rejeitados pelo validador")
def test_ranks_invalidos() -> None:
    pass


@scenario(FEATURE, 'Campo extra "score" é rejeitado (extra=forbid)')
def test_extra_score() -> None:
    pass


@scenario(FEATURE, "FeedbackEvent kind=status com reaction é rejeitado")
def test_status_com_reaction() -> None:
    pass


@scenario(FEATURE, "FeedbackEvent kind=reaction sem reaction é rejeitado")
def test_reaction_sem_reaction() -> None:
    pass


@scenario(FEATURE, "Round-trip de FeedbackEvent válido (kind=status)")
def test_event_roundtrip() -> None:
    pass


@scenario(FEATURE, "Catálogo de feedback padrão carrega e valida sem erros")
def test_catalog_default() -> None:
    pass


@scenario(FEATURE, "Catálogo com status_ids duplicados é rejeitado")
def test_catalog_duplicados() -> None:
    pass


@scenario(FEATURE, 'FeedbackCatalog extra=forbid rejeita campo desconhecido')
def test_catalog_extra() -> None:
    pass


# ---------------------------------------------------------------------------
# Fixture de contexto
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx() -> dict:  # type: ignore[type-arg]
    return {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_lead(rank: int) -> PublishedLead:
    return PublishedLead(
        entity_id=f"empresa{rank}.com.br",
        rank_position=rank,
        company=f"Empresa {rank}",
    )


def _base_event(kind: FeedbackKind, **kwargs: object) -> dict:  # type: ignore[type-arg]
    return {
        "event_id": 1,
        "operator_id": "talita",
        "profile_id": "talita_profile",
        "entity_id": "cliniq.com.br",
        "run_id": "abc123",
        "kind": kind,
        "note": "",
        "created_at": "2026-06-10T00:00:00Z",
        **kwargs,
    }


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given("um PublishedSnapshot válido com 3 leads em ranks 1, 2, 3", target_fixture="ctx")
def given_snapshot_valido() -> dict:  # type: ignore[type-arg]
    snapshot = PublishedSnapshot(
        profile_id="talita",
        run_id="run_abc",
        generated_at="2026-06-10T00:00:00Z",
        leads=[_make_lead(1), _make_lead(2), _make_lead(3)],
    )
    return {"snapshot": snapshot}


@given("um PublishedSnapshot com leads em ranks 1, 3 (pulando o 2)", target_fixture="ctx")
def given_snapshot_ranks_invalidos() -> dict:  # type: ignore[type-arg]
    return {"leads_raw": [_make_lead(1), _make_lead(3)]}


@given('um dicionário de PublishedLead com o campo extra "score"', target_fixture="ctx")
def given_lead_extra_score() -> dict:  # type: ignore[type-arg]
    return {
        "lead_dict": {
            "entity_id": "empresa.com.br",
            "rank_position": 1,
            "company": "Empresa",
            "score": 0.95,  # campo extra proibido
        }
    }


@given("um FeedbackEvent com kind=status e reaction=like", target_fixture="ctx")
def given_event_status_com_reaction() -> dict:  # type: ignore[type-arg]
    return {
        "event_dict": _base_event(
            FeedbackKind.STATUS,
            status_id="abordado",
            reaction=Reaction.LIKE,
        )
    }


@given("um FeedbackEvent com kind=reaction e sem campo reaction", target_fixture="ctx")
def given_event_reaction_sem_reaction() -> dict:  # type: ignore[type-arg]
    return {
        "event_dict": _base_event(FeedbackKind.REACTION)
        # reaction não fornecido
    }


@given("um FeedbackEvent válido com kind=status e status_id=abordado", target_fixture="ctx")
def given_event_valido() -> dict:  # type: ignore[type-arg]
    event = FeedbackEvent(**_base_event(FeedbackKind.STATUS, status_id="abordado"))
    return {"event": event}


@given('um catálogo com dois status tendo status_id="novo"', target_fixture="ctx")
def given_catalog_duplicados() -> dict:  # type: ignore[type-arg]
    return {
        "catalog_dict": {
            "schema_version": 1,
            "statuses": [
                {
                    "status_id": "novo",
                    "label": "Novo",
                    "terminal": False,
                    "rotulo_aprendizado": "neutro",
                    "ordem": 1,
                },
                {
                    "status_id": "novo",
                    "label": "Novo 2",
                    "terminal": False,
                    "rotulo_aprendizado": "neutro",
                    "ordem": 2,
                },
            ],
        }
    }


@given('um dicionário de catálogo com campo extra "versao_interna"', target_fixture="ctx")
def given_catalog_extra() -> dict:  # type: ignore[type-arg]
    return {
        "catalog_dict": {
            "schema_version": 1,
            "versao_interna": "v2",  # campo extra proibido
            "statuses": [],
        }
    }


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when("serializo e desserializo o snapshot")
def when_roundtrip_snapshot(ctx: dict) -> None:  # type: ignore[type-arg]
    snap = ctx["snapshot"]
    raw = snap.model_dump_json()
    ctx["result"] = PublishedSnapshot.model_validate_json(raw)


@when("tento criar o snapshot")
def when_criar_snapshot_invalido(ctx: dict) -> None:  # type: ignore[type-arg]
    try:
        ctx["result"] = PublishedSnapshot(
            profile_id="talita",
            run_id="run_abc",
            generated_at="2026-06-10T00:00:00Z",
            leads=ctx["leads_raw"],
        )
        ctx["error"] = None
    except (ValueError, ValidationError) as exc:
        ctx["error"] = exc


@when("tento criar o PublishedLead")
def when_criar_lead_extra(ctx: dict) -> None:  # type: ignore[type-arg]
    try:
        ctx["result"] = PublishedLead(**ctx["lead_dict"])
        ctx["error"] = None
    except (ValueError, ValidationError) as exc:
        ctx["error"] = exc


@when("tento criar o evento")
def when_criar_event_invalido(ctx: dict) -> None:  # type: ignore[type-arg]
    try:
        ctx["result"] = FeedbackEvent(**ctx["event_dict"])
        ctx["error"] = None
    except (ValueError, ValidationError) as exc:
        ctx["error"] = exc


@when("serializo e desserializo o evento")
def when_roundtrip_event(ctx: dict) -> None:  # type: ignore[type-arg]
    event = ctx["event"]
    raw = event.model_dump_json()
    ctx["result"] = FeedbackEvent.model_validate_json(raw)


@when("carrego o feedback_catalog.json padrão")
def when_carregar_catalog(ctx: dict) -> None:  # type: ignore[type-arg]
    ctx["catalog"] = load_feedback_catalog()


@when("tento validar o catálogo")
def when_validar_catalog_invalido(ctx: dict) -> None:  # type: ignore[type-arg]
    try:
        ctx["result"] = FeedbackCatalog.model_validate(ctx["catalog_dict"])
        ctx["error"] = None
    except (ValueError, ValidationError) as exc:
        ctx["error"] = exc


@when("tento criar o FeedbackCatalog")
def when_criar_catalog_extra(ctx: dict) -> None:  # type: ignore[type-arg]
    try:
        ctx["result"] = FeedbackCatalog.model_validate(ctx["catalog_dict"])
        ctx["error"] = None
    except (ValueError, ValidationError) as exc:
        ctx["error"] = exc


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then("o objeto resultante é idêntico ao original")
def then_identico(ctx: dict) -> None:  # type: ignore[type-arg]
    original = ctx.get("snapshot") or ctx.get("event")
    result = ctx["result"]
    assert original == result, f"Divergência: {original!r} ≠ {result!r}"


@then('recebo ValueError com "rank_position"')
def then_valueerror_rank(ctx: dict) -> None:  # type: ignore[type-arg]
    err = ctx.get("error")
    assert err is not None, "Esperava ValueError, mas nenhum erro ocorreu"
    assert "rank_position" in str(err), f"Erro sem 'rank_position': {err}"


@then("recebo ValidationError")
def then_validation_error(ctx: dict) -> None:  # type: ignore[type-arg]
    err = ctx.get("error")
    assert err is not None, "Esperava ValidationError, mas nenhum erro ocorreu"
    assert isinstance(err, ValidationError), f"Tipo inesperado: {type(err)}"


@then('recebo ValueError com "kind=status"')
def then_valueerror_kind_status(ctx: dict) -> None:  # type: ignore[type-arg]
    err = ctx.get("error")
    assert err is not None, "Esperava erro, mas nenhum ocorreu"
    assert "kind=status" in str(err), f"Erro sem 'kind=status': {err}"


@then('recebo ValueError com "kind=reaction"')
def then_valueerror_kind_reaction(ctx: dict) -> None:  # type: ignore[type-arg]
    err = ctx.get("error")
    assert err is not None, "Esperava erro, mas nenhum ocorreu"
    assert "kind=reaction" in str(err), f"Erro sem 'kind=reaction': {err}"


@then("o catálogo tem 9 status")
def then_9_status(ctx: dict) -> None:  # type: ignore[type-arg]
    catalog = ctx["catalog"]
    assert len(catalog.statuses) == 9, f"Esperado 9 status, obtido {len(catalog.statuses)}"


@then("os status_ids são únicos")
def then_ids_unicos(ctx: dict) -> None:  # type: ignore[type-arg]
    ids = [s.status_id for s in ctx["catalog"].statuses]
    assert len(set(ids)) == len(ids), f"status_ids duplicados: {ids}"


@then("as ordens são únicas e sequenciais de 1 a 9")
def then_ordens_sequenciais(ctx: dict) -> None:  # type: ignore[type-arg]
    ordens = sorted(s.ordem for s in ctx["catalog"].statuses)
    assert ordens == list(range(1, 10)), f"Ordens inválidas: {ordens}"


@then('recebo ValueError com "status_id e ordem devem ser únicos"')
def then_valueerror_duplicados(ctx: dict) -> None:  # type: ignore[type-arg]
    err = ctx.get("error")
    assert err is not None, "Esperava erro, mas nenhum ocorreu"
    assert "status_id e ordem devem ser únicos" in str(err), f"Mensagem inesperada: {err}"
