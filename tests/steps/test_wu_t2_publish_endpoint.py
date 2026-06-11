"""Steps BDD para WU-T2 — POST /api/publish."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, scenario, then, when

from socialselling.portal.app import create_portal_app
from socialselling.portal.dao_memory import InMemoryDAO

FEATURE = "../features/wu_t2_publish_endpoint.feature"

_TOKEN = "test-publish-token-abc"

_VALID_SNAPSHOT = {
    "schema_version": 1,
    "profile_id": "talita",
    "run_id": "run_abc",
    "generated_at": "2026-06-10T00:00:00Z",
    "leads": [
        {
            "entity_id": "empresa.com.br",
            "rank_position": 1,
            "company": "Empresa",
        }
    ],
}


@scenario(FEATURE, "Publicação feliz retorna 201 e persiste o snapshot")
def test_publish_201() -> None:
    pass


@scenario(FEATURE, "Republicação do mesmo (profile_id, run_id) retorna 409 sem duplicar")
def test_publish_409() -> None:
    pass


@scenario(FEATURE, "Token ausente retorna 401 sem persistir nada")
def test_publish_401_sem_token() -> None:
    pass


@scenario(FEATURE, "Token errado retorna 401")
def test_publish_401_token_errado() -> None:
    pass


@scenario(FEATURE, 'Snapshot com campo extra "score" é rejeitado com 422')
def test_publish_422_extra() -> None:
    pass


@scenario(FEATURE, "Snapshot com ranks não-estritos é rejeitado com 422")
def test_publish_422_ranks() -> None:
    pass


@pytest.fixture
def ctx() -> dict:  # type: ignore[type-arg]
    return {}


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given("um portal com InMemoryDAO e PUBLISH_TOKEN configurado", target_fixture="ctx")
def given_portal(monkeypatch: pytest.MonkeyPatch) -> dict:  # type: ignore[type-arg]
    monkeypatch.setenv("PUBLISH_TOKEN", _TOKEN)
    dao = InMemoryDAO()
    app = create_portal_app(dao)
    client = TestClient(app, raise_server_exceptions=True)
    return {"client": client, "dao": dao}


@given("o snapshot (talita, run_abc) já está publicado")
def given_snapshot_publicado(ctx: dict) -> None:  # type: ignore[type-arg]
    ctx["client"].post(
        "/api/publish",
        json=_VALID_SNAPSHOT,
        headers={"Authorization": f"Bearer {_TOKEN}"},
    )


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when("faço POST /api/publish com um snapshot válido para (talita, run_abc)")
def when_publish_valido(ctx: dict) -> None:  # type: ignore[type-arg]
    ctx["response"] = ctx["client"].post(
        "/api/publish",
        json=_VALID_SNAPSHOT,
        headers={"Authorization": f"Bearer {_TOKEN}"},
    )


@when("faço POST /api/publish com o mesmo snapshot (talita, run_abc)")
def when_publish_duplicado(ctx: dict) -> None:  # type: ignore[type-arg]
    ctx["response"] = ctx["client"].post(
        "/api/publish",
        json=_VALID_SNAPSHOT,
        headers={"Authorization": f"Bearer {_TOKEN}"},
    )


@when("faço POST /api/publish sem header Authorization")
def when_publish_sem_token(ctx: dict) -> None:  # type: ignore[type-arg]
    ctx["response"] = ctx["client"].post("/api/publish", json=_VALID_SNAPSHOT)


@when("faço POST /api/publish com token errado")
def when_publish_token_errado(ctx: dict) -> None:  # type: ignore[type-arg]
    ctx["response"] = ctx["client"].post(
        "/api/publish",
        json=_VALID_SNAPSHOT,
        headers={"Authorization": "Bearer token-errado"},
    )


@when('faço POST /api/publish com um body que contém o campo extra "score"')
def when_publish_extra_score(ctx: dict) -> None:  # type: ignore[type-arg]
    body = {**_VALID_SNAPSHOT, "score": 0.99}
    ctx["response"] = ctx["client"].post(
        "/api/publish",
        json=body,
        headers={"Authorization": f"Bearer {_TOKEN}"},
    )


@when("faço POST /api/publish com leads em ranks 1 e 3")
def when_publish_ranks_invalidos(ctx: dict) -> None:  # type: ignore[type-arg]
    body = {
        **_VALID_SNAPSHOT,
        "leads": [
            {"entity_id": "a.com.br", "rank_position": 1, "company": "A"},
            {"entity_id": "c.com.br", "rank_position": 3, "company": "C"},
        ],
    }
    ctx["response"] = ctx["client"].post(
        "/api/publish",
        json=body,
        headers={"Authorization": f"Bearer {_TOKEN}"},
    )


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then("a resposta tem status 201")
def then_201(ctx: dict) -> None:  # type: ignore[type-arg]
    assert ctx["response"].status_code == 201, (
        f"Status {ctx['response'].status_code}: {ctx['response'].text}"
    )


@then("o body contém run_id=run_abc")
def then_run_id(ctx: dict) -> None:  # type: ignore[type-arg]
    data = ctx["response"].json()
    assert data.get("run_id") == "run_abc", f"Body: {data}"


@then('o DAO contém 1 snapshot para o perfil "talita"')
def then_1_snapshot(ctx: dict) -> None:  # type: ignore[type-arg]
    snaps = ctx["dao"].list_snapshots("talita")
    assert len(snaps) == 1, f"Esperado 1, obtido {len(snaps)}"


@then("a resposta tem status 409")
def then_409(ctx: dict) -> None:  # type: ignore[type-arg]
    assert ctx["response"].status_code == 409, (
        f"Status {ctx['response'].status_code}: {ctx['response'].text}"
    )


@then('o DAO ainda contém exatamente 1 snapshot para o perfil "talita"')
def then_ainda_1_snapshot(ctx: dict) -> None:  # type: ignore[type-arg]
    snaps = ctx["dao"].list_snapshots("talita")
    assert len(snaps) == 1, f"Esperado 1 (sem duplicar), obtido {len(snaps)}"


@then("a resposta tem status 401")
def then_401(ctx: dict) -> None:  # type: ignore[type-arg]
    assert ctx["response"].status_code == 401, (
        f"Status {ctx['response'].status_code}: {ctx['response'].text}"
    )


@then('o DAO contém 0 snapshots para o perfil "talita"')
def then_0_snapshots(ctx: dict) -> None:  # type: ignore[type-arg]
    snaps = ctx["dao"].list_snapshots("talita")
    assert len(snaps) == 0, f"Esperado 0, obtido {len(snaps)}"


@then("a resposta tem status 422")
def then_422(ctx: dict) -> None:  # type: ignore[type-arg]
    assert ctx["response"].status_code == 422, (
        f"Status {ctx['response'].status_code}: {ctx['response'].text}"
    )
