"""Steps BDD para WU-T1 — scaffold do portal (porta DAO + /healthz)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, scenario, then, when

from socialselling.portal.app import create_portal_app
from socialselling.portal.contracts import (
    FeedbackKind,
    PublishedLead,
    PublishedSnapshot,
    Reaction,
)
from socialselling.portal.dao_memory import InMemoryDAO

FEATURE = "../features/wu_t1_portal_scaffold.feature"


@scenario(
    FEATURE,
    "put_snapshot retorna True na primeira inserção e False na segunda (idempotência)",
)
def test_put_snapshot_idempotente() -> None:
    pass


@scenario(
    FEATURE,
    "list_snapshots retorna snapshots em ordem published_at DESC, tie-break run_id DESC",
)
def test_list_snapshots_ordem() -> None:
    pass


@scenario(FEATURE, "events_since retorna eventos com event_id > since em ordem ASC")
def test_events_since_asc() -> None:
    pass


@scenario(FEATURE, "events_since com since além do fim retorna lista vazia")
def test_events_since_vazio() -> None:
    pass


@scenario(FEATURE, "latest_status_by_entity retorna o status do maior event_id")
def test_latest_status_maior_event_id() -> None:
    pass


@scenario(FEATURE, "Entidade sem evento de status não aparece no latest_status_by_entity")
def test_latest_status_sem_evento() -> None:
    pass


@scenario(FEATURE, "GET /healthz retorna 200 e X-Robots-Tag noindex")
def test_healthz() -> None:
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


def _make_snapshot(profile_id: str, run_id: str) -> PublishedSnapshot:
    return PublishedSnapshot(
        profile_id=profile_id,
        run_id=run_id,
        generated_at="2026-06-10T00:00:00Z",
        leads=[
            PublishedLead(
                entity_id="empresa.com.br",
                rank_position=1,
                company="Empresa",
            )
        ],
    )


def _append_status(
    dao: InMemoryDAO,
    entity_id: str,
    status_id: str,
    profile_id: str = "talita",
) -> int:
    return dao.append_event(
        operator_id="talita",
        profile_id=profile_id,
        entity_id=entity_id,
        run_id="run_x",
        kind=FeedbackKind.STATUS,
        status_id=status_id,
        reaction=None,
        note="",
        now="2026-06-10T00:00:00Z",
    )


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given("um InMemoryDAO limpo", target_fixture="ctx")
def given_dao_limpo() -> dict:  # type: ignore[type-arg]
    return {"dao": InMemoryDAO(), "result": None}


@given("um InMemoryDAO limpo com 3 eventos de status", target_fixture="ctx")
def given_dao_com_3_eventos() -> dict:  # type: ignore[type-arg]
    dao = InMemoryDAO()
    _append_status(dao, "a.com.br", "novo")
    _append_status(dao, "b.com.br", "abordado")
    _append_status(dao, "c.com.br", "interagindo")
    return {"dao": dao}


@given("um InMemoryDAO limpo com evento kind=reaction para cliniq.com.br", target_fixture="ctx")
def given_dao_com_reaction() -> dict:  # type: ignore[type-arg]
    dao = InMemoryDAO()
    dao.append_event(
        operator_id="talita",
        profile_id="talita",
        entity_id="cliniq.com.br",
        run_id="run_x",
        kind=FeedbackKind.REACTION,
        status_id=None,
        reaction=Reaction.LIKE,
        note="",
        now="2026-06-10T00:00:00Z",
    )
    return {"dao": dao}


@given("um TestClient do portal com InMemoryDAO", target_fixture="ctx")
def given_testclient() -> dict:  # type: ignore[type-arg]
    dao = InMemoryDAO()
    app = create_portal_app(dao)
    client = TestClient(app, raise_server_exceptions=True)
    return {"client": client}


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when('insiro o snapshot (talita, run_abc) com now="2026-06-10T00:00:00Z"')
def when_insiro_snapshot(ctx: dict) -> None:  # type: ignore[type-arg]
    snap = _make_snapshot("talita", "run_abc")
    ctx["snapshot"] = snap
    ctx["result"] = ctx["dao"].put_snapshot(snap, now="2026-06-10T00:00:00Z")


@when("insiro o mesmo snapshot novamente")
def when_insiro_novamente(ctx: dict) -> None:  # type: ignore[type-arg]
    ctx["result"] = ctx["dao"].put_snapshot(ctx["snapshot"], now="2026-06-10T00:00:00Z")


@when('insiro o snapshot (talita, run_a) com now="2026-06-10T01:00:00Z"')
def when_insiro_run_a(ctx: dict) -> None:  # type: ignore[type-arg]
    ctx["dao"].put_snapshot(_make_snapshot("talita", "run_a"), now="2026-06-10T01:00:00Z")


@when('insiro o snapshot (talita, run_b) com now="2026-06-10T02:00:00Z"')
def when_insiro_run_b(ctx: dict) -> None:  # type: ignore[type-arg]
    ctx["dao"].put_snapshot(_make_snapshot("talita", "run_b"), now="2026-06-10T02:00:00Z")


@when('insiro o snapshot (talita, run_c) com now="2026-06-10T02:00:00Z"')
def when_insiro_run_c(ctx: dict) -> None:  # type: ignore[type-arg]
    ctx["dao"].put_snapshot(_make_snapshot("talita", "run_c"), now="2026-06-10T02:00:00Z")


@when("chamo events_since com since=1")
def when_events_since_1(ctx: dict) -> None:  # type: ignore[type-arg]
    ctx["events"] = ctx["dao"].events_since(1)


@when("chamo events_since com since=99")
def when_events_since_99(ctx: dict) -> None:  # type: ignore[type-arg]
    ctx["events"] = ctx["dao"].events_since(99)


@when("appendo evento kind=status entity_id=cliniq.com.br status_id=interagindo")
def when_append_interagindo(ctx: dict) -> None:  # type: ignore[type-arg]
    _append_status(ctx["dao"], "cliniq.com.br", "interagindo")


@when("appendo evento kind=status entity_id=cliniq.com.br status_id=abordado")
def when_append_abordado(ctx: dict) -> None:  # type: ignore[type-arg]
    _append_status(ctx["dao"], "cliniq.com.br", "abordado")


@when('chamo latest_status_by_entity para "talita"')
def when_latest_status(ctx: dict) -> None:  # type: ignore[type-arg]
    ctx["status_map"] = ctx["dao"].latest_status_by_entity("talita")


@when("faço GET /healthz")
def when_get_healthz(ctx: dict) -> None:  # type: ignore[type-arg]
    ctx["response"] = ctx["client"].get("/healthz")


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then("o resultado é True")
def then_resultado_true(ctx: dict) -> None:  # type: ignore[type-arg]
    assert ctx["result"] is True, f"Esperado True, obtido {ctx['result']}"


@then("o resultado é False")
def then_resultado_false(ctx: dict) -> None:  # type: ignore[type-arg]
    assert ctx["result"] is False, f"Esperado False, obtido {ctx['result']}"


@then('o DAO contém exatamente 1 snapshot para o perfil "talita"')
def then_1_snapshot(ctx: dict) -> None:  # type: ignore[type-arg]
    snaps = ctx["dao"].list_snapshots("talita")
    assert len(snaps) == 1, f"Esperado 1 snapshot, obtido {len(snaps)}"


@then('list_snapshots para "talita" retorna [run_c, run_b, run_a] nessa ordem')
def then_lista_ordem(ctx: dict) -> None:  # type: ignore[type-arg]
    snaps = ctx["dao"].list_snapshots("talita")
    run_ids = [s.run_id for s in snaps]
    assert run_ids == ["run_c", "run_b", "run_a"], f"Ordem incorreta: {run_ids}"


@then("recebo 2 eventos com event_ids [2, 3] em ordem crescente")
def then_eventos_2_3(ctx: dict) -> None:  # type: ignore[type-arg]
    ids = [e.event_id for e in ctx["events"]]
    assert ids == [2, 3], f"event_ids incorretos: {ids}"


@then("recebo lista vazia")
def then_lista_vazia(ctx: dict) -> None:  # type: ignore[type-arg]
    assert ctx["events"] == [], f"Esperado lista vazia, obtido {ctx['events']}"


@then("latest_status_by_entity para \"talita\" retorna cliniq.com.br=abordado")
def then_latest_abordado(ctx: dict) -> None:  # type: ignore[type-arg]
    status_map = ctx["dao"].latest_status_by_entity("talita")
    assert status_map.get("cliniq.com.br") == "abordado", (
        f"Mapa incorreto: {status_map}"
    )


@then("o dicionário retornado está vazio")
def then_dict_vazio(ctx: dict) -> None:  # type: ignore[type-arg]
    assert ctx["status_map"] == {}, f"Esperado dict vazio, obtido {ctx['status_map']}"


@then("a resposta tem status 200")
def then_status_200(ctx: dict) -> None:  # type: ignore[type-arg]
    assert ctx["response"].status_code == 200, (
        f"Status {ctx['response'].status_code}, body: {ctx['response'].text}"
    )


@then("o body JSON contém status=ok")
def then_body_ok(ctx: dict) -> None:  # type: ignore[type-arg]
    data = ctx["response"].json()
    assert data.get("status") == "ok", f"Body inesperado: {data}"


@then("o header X-Robots-Tag vale noindex")
def then_noindex(ctx: dict) -> None:  # type: ignore[type-arg]
    val = ctx["response"].headers.get("x-robots-tag", "")
    assert val == "noindex", f"Header X-Robots-Tag incorreto: '{val}'"
