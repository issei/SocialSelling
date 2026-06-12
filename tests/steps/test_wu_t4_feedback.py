"""Steps BDD para WU-T4 — APIs de feedback (POST tabulação + GET cursor)."""

from __future__ import annotations

import hashlib
import os

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, scenario, then, when

from socialselling.portal.app import create_portal_app
from socialselling.portal.contracts import (
    FeedbackKind,
    Operator,
    PublishedLead,
    PublishedSnapshot,
)
from socialselling.portal.dao_memory import InMemoryDAO

FEATURE = "../features/wu_t4_feedback.feature"


@scenario(
    FEATURE,
    "Feliz — POST feedback grava evento com dados da sessão e run_id do snapshot mais recente",
)
def test_post_feedback_feliz() -> None:
    pass


@scenario(
    FEATURE,
    "Degradado — status_id fora do catálogo retorna 422",
)
def test_post_feedback_status_invalido() -> None:
    pass


@scenario(
    FEATURE,
    "Degradado — lead fora da carteira retorna 404",
)
def test_post_feedback_lead_fora_carteira() -> None:
    pass


@scenario(
    FEATURE,
    "Open-World — cursor além do fim retorna lista vazia e next_since=since",
)
def test_get_feedback_cursor_alem_fim() -> None:
    pass


@scenario(
    FEATURE,
    "Degradado — GET /api/feedback sem Bearer retorna 401",
)
def test_get_feedback_sem_bearer() -> None:
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


def _make_snapshot(profile_id: str, run_id: str, entity_ids: list[str]) -> PublishedSnapshot:
    leads = [
        PublishedLead(entity_id=eid, rank_position=i + 1, company=eid)
        for i, eid in enumerate(entity_ids)
    ]
    return PublishedSnapshot(
        profile_id=profile_id,
        run_id=run_id,
        generated_at="2026-06-11T00:00:00Z",
        leads=leads,
    )


def _seed_operator(dao: InMemoryDAO, code: str = "codigo-correto") -> None:
    code_hash = hashlib.sha256(code.encode()).hexdigest()
    dao.seed_operator(
        Operator(
            operator_id="talita",
            nome="Talita",
            code_hash=code_hash,
            profile_id="talita_profile",
        )
    )


def _make_client(dao: InMemoryDAO) -> TestClient:
    app = create_portal_app(dao, https_only=True)
    return TestClient(app, base_url="https://testserver", raise_server_exceptions=False)


def _login(client: TestClient) -> None:
    resp = client.post("/login", data={"code": "codigo-correto"}, follow_redirects=False)
    assert resp.status_code == 303, f"Login falhou: {resp.status_code} {resp.text}"


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given(
    'um portal com snapshot "run_2" contendo "cliniq.com.br" para perfil "talita_profile"',
    target_fixture="ctx",
)
def given_portal_com_snapshot() -> dict:  # type: ignore[type-arg]
    dao = InMemoryDAO()
    _seed_operator(dao)
    snap = _make_snapshot("talita_profile", "run_2", ["cliniq.com.br"])
    dao.put_snapshot(snap, now="2026-06-11T10:00:00Z")
    client = _make_client(dao)
    return {"client": client, "dao": dao}


@given("a operadora \"talita\" está autenticada no portal")
def given_operadora_autenticada(ctx: dict) -> None:  # type: ignore[type-arg]
    _login(ctx["client"])


@given(
    'um portal com 2 eventos de feedback para "talita_profile"',
    target_fixture="ctx",
)
def given_portal_com_2_eventos() -> dict:  # type: ignore[type-arg]
    dao = InMemoryDAO()
    snap = _make_snapshot("talita_profile", "run_x", ["a.com.br", "b.com.br"])
    dao.put_snapshot(snap, now="2026-06-11T10:00:00Z")
    for entity_id in ["a.com.br", "b.com.br"]:
        dao.append_event(
            operator_id="talita",
            profile_id="talita_profile",
            entity_id=entity_id,
            run_id="run_x",
            kind=FeedbackKind.STATUS,
            status_id="novo",
            reaction=None,
            note="",
            now="2026-06-11T10:00:00Z",
        )
    client = _make_client(dao)
    return {"client": client, "dao": dao}


@given("um portal sem eventos de feedback", target_fixture="ctx")
def given_portal_sem_eventos() -> dict:  # type: ignore[type-arg]
    dao = InMemoryDAO()
    client = _make_client(dao)
    return {"client": client, "dao": dao}


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when("ela envia POST /lead/cliniq.com.br/feedback com kind=status e status_id=abordado")
def when_post_feedback_abordado(ctx: dict) -> None:  # type: ignore[type-arg]
    ctx["response"] = ctx["client"].post(
        "/lead/cliniq.com.br/feedback",
        json={"kind": "status", "status_id": "abordado"},
    )


@when("ela envia POST /lead/cliniq.com.br/feedback com kind=status e status_id=quase_cliente")
def when_post_feedback_invalido(ctx: dict) -> None:  # type: ignore[type-arg]
    ctx["response"] = ctx["client"].post(
        "/lead/cliniq.com.br/feedback",
        json={"kind": "status", "status_id": "quase_cliente"},
    )


@when("ela envia POST /lead/outro.com.br/feedback com kind=status e status_id=abordado")
def when_post_feedback_lead_fora(ctx: dict) -> None:  # type: ignore[type-arg]
    ctx["response"] = ctx["client"].post(
        "/lead/outro.com.br/feedback",
        json={"kind": "status", "status_id": "abordado"},
    )


@when("o motor solicita GET /api/feedback com since=99")
def when_get_feedback_since_99(ctx: dict) -> None:  # type: ignore[type-arg]
    os.environ["PUBLISH_TOKEN"] = "test-token"
    ctx["response"] = ctx["client"].get(
        "/api/feedback",
        params={"since": 99},
        headers={"Authorization": "Bearer test-token"},
    )


@when("um cliente sem Bearer solicita GET /api/feedback")
def when_get_feedback_sem_bearer(ctx: dict) -> None:  # type: ignore[type-arg]
    ctx["response"] = ctx["client"].get("/api/feedback", params={"since": 0})


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then("a resposta tem status 200")
def then_status_200(ctx: dict) -> None:  # type: ignore[type-arg]
    resp = ctx["response"]
    assert resp.status_code == 200, f"Esperado 200, obtido {resp.status_code}: {resp.text}"


@then("o evento gravado tem operator_id=talita profile_id=talita_profile run_id=run_2")
def then_evento_gravado(ctx: dict) -> None:  # type: ignore[type-arg]
    dao: InMemoryDAO = ctx["dao"]
    events = dao.events_since(0)
    assert len(events) == 1, f"Esperado 1 evento, obtido {len(events)}"
    ev = events[0]
    assert ev.operator_id == "talita", f"operator_id errado: {ev.operator_id}"
    assert ev.profile_id == "talita_profile", f"profile_id errado: {ev.profile_id}"
    assert ev.run_id == "run_2", f"run_id errado: {ev.run_id}"


@then("a resposta tem status 422")
def then_status_422(ctx: dict) -> None:  # type: ignore[type-arg]
    resp = ctx["response"]
    assert resp.status_code == 422, f"Esperado 422, obtido {resp.status_code}: {resp.text}"


@then("a resposta tem status 404")
def then_status_404(ctx: dict) -> None:  # type: ignore[type-arg]
    resp = ctx["response"]
    assert resp.status_code == 404, f"Esperado 404, obtido {resp.status_code}: {resp.text}"


@then("a lista de eventos está vazia")
def then_eventos_vazios(ctx: dict) -> None:  # type: ignore[type-arg]
    data = ctx["response"].json()
    assert data["events"] == [], f"Esperado lista vazia, obtido: {data['events']}"


@then("o next_since é 99")
def then_next_since_99(ctx: dict) -> None:  # type: ignore[type-arg]
    data = ctx["response"].json()
    assert data["next_since"] == 99, f"next_since errado: {data['next_since']}"


@then("a resposta tem status 401")
def then_status_401(ctx: dict) -> None:  # type: ignore[type-arg]
    resp = ctx["response"]
    assert resp.status_code == 401, f"Esperado 401, obtido {resp.status_code}: {resp.text}"
