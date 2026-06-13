"""Steps BDD para o smoke de regressão end-to-end do portal (InMemoryDAO, sem rede).

Cobre a cadeia boot→login→carteira vazia→logout→barreira que foi validada manualmente
em 2026-06-11. Guarda contra regressões em evoluções futuras (WU-E*/T*).
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, scenario, then, when

from socialselling.portal.app import create_portal_app
from socialselling.portal.contracts import Operator
from socialselling.portal.dao_memory import InMemoryDAO

FEATURE = "../features/portal_smoke_regression.feature"
_CODE = "talita-2026"


@scenario(FEATURE, "Saúde — /healthz responde antes de qualquer autenticação")
def test_healthz() -> None:
    pass


@scenario(FEATURE, "Fluxo completo — login, carteira vazia, logout, barreira")
def test_fluxo_completo() -> None:
    pass


@scenario(FEATURE, "Degradado — código inválido não cria sessão e bloqueia /carteira")
def test_degradado() -> None:
    pass


@scenario(FEATURE, "Open-World — carteira sem snapshot não gera erro")
def test_open_world() -> None:
    pass


@pytest.fixture
def ctx() -> dict[str, Any]:
    return {}


# --------------------------------------------------------------------------- Given


@given(
    'um portal com InMemoryDAO e operadora "talita" registrada com código "talita-2026"',
    target_fixture="ctx",
)
def given_portal(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    dao = InMemoryDAO()
    dao.seed_operator(
        Operator(
            operator_id="talita",
            nome="Talita",
            code_hash=hashlib.sha256(_CODE.encode()).hexdigest(),
            profile_id="talita",
        )
    )
    app = create_portal_app(dao, https_only=False)
    client = TestClient(app, follow_redirects=False)
    return {"client": client, "dao": dao}


@given('que a operadora está autenticada com código "talita-2026"')
def given_authenticated(ctx: dict[str, Any]) -> None:
    ctx["client"].post("/login", data={"code": _CODE})


# --------------------------------------------------------------------------- When


@when("um cliente sem sessão acessa GET /healthz")
def when_healthz(ctx: dict[str, Any]) -> None:
    ctx["response"] = ctx["client"].get("/healthz")


@when('a operadora envia POST /login com o código "talita-2026"')
def when_login_ok(ctx: dict[str, Any]) -> None:
    ctx["response"] = ctx["client"].post("/login", data={"code": _CODE})


@when('a operadora envia POST /login com o código "codigo-errado"')
def when_login_bad(ctx: dict[str, Any]) -> None:
    ctx["response"] = ctx["client"].post("/login", data={"code": "codigo-errado"})


@when("a operadora com sessão acessa GET /carteira")
@when("acessa GET /carteira")
def when_carteira(ctx: dict[str, Any]) -> None:
    ctx["response"] = ctx["client"].get("/carteira")


@when("a operadora envia POST /logout")
def when_logout(ctx: dict[str, Any]) -> None:
    ctx["response"] = ctx["client"].post("/logout")


@when("após o logout acessa GET /carteira")
@when("sem sessão acessa GET /carteira")
def when_carteira_no_session(ctx: dict[str, Any]) -> None:
    ctx["response"] = ctx["client"].get("/carteira")


# --------------------------------------------------------------------------- Then


@then("a resposta tem status 200")
def then_200(ctx: dict[str, Any]) -> None:
    assert ctx["response"].status_code == 200, ctx["response"].text


@then("o corpo JSON contém status ok")
def then_status_ok(ctx: dict[str, Any]) -> None:
    assert ctx["response"].json().get("status") == "ok"


@then("a resposta de login tem status 303 e Location /carteira")
def then_login_303(ctx: dict[str, Any]) -> None:
    assert ctx["response"].status_code == 303, ctx["response"].text
    assert ctx["response"].headers["location"] == "/carteira"


@then("a resposta tem status 200 e é HTML")
def then_200_html(ctx: dict[str, Any]) -> None:
    assert ctx["response"].status_code == 200, ctx["response"].text
    assert "text/html" in ctx["response"].headers["content-type"]


@then("o HTML não contém nenhum lead")
def then_no_lead(ctx: dict[str, Any]) -> None:
    assert 'href="/lead/' not in ctx["response"].text


@then("a resposta de logout tem status 303 e Location /login")
@then("a resposta tem status 303 e Location /login")
def then_303_login(ctx: dict[str, Any]) -> None:
    assert ctx["response"].status_code == 303, ctx["response"].text
    assert ctx["response"].headers["location"] == "/login"


@then("a resposta de login tem status 401")
def then_login_401(ctx: dict[str, Any]) -> None:
    assert ctx["response"].status_code == 401, ctx["response"].text


@then("o HTML não contém número de score")
def then_no_score(ctx: dict[str, Any]) -> None:
    blob = ctx["response"].text.lower()
    for forbidden in ("p_score", "fit:", "intent:", '"score"'):
        assert forbidden not in blob, f"score vazou: {forbidden}"
