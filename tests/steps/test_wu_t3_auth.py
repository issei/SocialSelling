"""Steps BDD para WU-T3 — autenticação da operadora por código de acesso."""

from __future__ import annotations

import hashlib

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, scenario, then, when

from socialselling.portal.app import create_portal_app
from socialselling.portal.contracts import Operator
from socialselling.portal.dao_memory import InMemoryDAO

FEATURE = "../features/wu_t3_auth.feature"


@scenario(
    FEATURE,
    "Feliz — login com código correto cria sessão e redireciona para /carteira",
)
def test_login_feliz() -> None:
    pass


@scenario(
    FEATURE,
    "Degradado — login com código errado retorna 401 genérico sem criar sessão",
)
def test_login_errado() -> None:
    pass


@scenario(
    FEATURE,
    "Open-World — sem sessão acessa /carteira e é redirecionado para /login",
)
def test_sem_sessao_redirect() -> None:
    pass


@scenario(
    FEATURE,
    "Logout invalida a sessão",
)
def test_logout_invalida_sessao() -> None:
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


def _seed_operator(dao: InMemoryDAO, code: str) -> Operator:
    code_hash = hashlib.sha256(code.encode()).hexdigest()
    operator = Operator(
        operator_id="talita",
        nome="Talita",
        code_hash=code_hash,
        profile_id="talita_profile",
    )
    dao.seed_operator(operator)
    return operator


def _make_client(dao: InMemoryDAO) -> TestClient:
    app = create_portal_app(dao, https_only=True)
    # base_url https:// garante que cookies Secure sejam incluídos pelo httpx
    return TestClient(app, base_url="https://testserver", raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given(
    'um portal com InMemoryDAO e operadora "talita" registrada com código "codigo-correto"',
    target_fixture="ctx",
)
def given_portal_com_operadora() -> dict:  # type: ignore[type-arg]
    dao = InMemoryDAO()
    _seed_operator(dao, "codigo-correto")
    client = _make_client(dao)
    return {"client": client, "dao": dao}


@given(
    'a operadora está autenticada com código "codigo-correto"',
    target_fixture="ctx",
)
def given_operadora_autenticada(ctx: dict) -> dict:  # type: ignore[type-arg]
    resp = ctx["client"].post(
        "/login",
        data={"code": "codigo-correto"},
        follow_redirects=False,
    )
    assert resp.status_code == 303, f"Login falhou: {resp.status_code} {resp.text}"
    return ctx


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when('a operadora envia POST /login com o código "codigo-correto"')
def when_login_correto(ctx: dict) -> None:  # type: ignore[type-arg]
    ctx["response"] = ctx["client"].post(
        "/login",
        data={"code": "codigo-correto"},
        follow_redirects=False,
    )


@when('a operadora envia POST /login com o código "codigo-errado"')
def when_login_errado(ctx: dict) -> None:  # type: ignore[type-arg]
    ctx["response"] = ctx["client"].post(
        "/login",
        data={"code": "codigo-errado"},
        follow_redirects=False,
    )


@when("um cliente sem sessão acessa GET /carteira")
def when_sem_sessao_carteira(ctx: dict) -> None:  # type: ignore[type-arg]
    ctx["response"] = ctx["client"].get("/carteira", follow_redirects=False)


@when("a operadora envia POST /logout")
def when_logout(ctx: dict) -> None:  # type: ignore[type-arg]
    ctx["logout_response"] = ctx["client"].post("/logout", follow_redirects=False)


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then("a resposta de login tem status 303")
def then_login_303(ctx: dict) -> None:  # type: ignore[type-arg]
    resp = ctx["response"]
    assert resp.status_code == 303, f"Esperado 303, obtido {resp.status_code}: {resp.text}"


@then("o header Location da resposta de login aponta para /carteira")
def then_login_location_carteira(ctx: dict) -> None:  # type: ignore[type-arg]
    location = ctx["response"].headers.get("location", "")
    assert location.endswith("/carteira"), f"Location inesperado: {location!r}"


@then("o cookie de sessão tem os atributos HttpOnly, SameSite=lax e Secure")
def then_cookie_atributos(ctx: dict) -> None:  # type: ignore[type-arg]
    set_cookie = ctx["response"].headers.get("set-cookie", "").lower()
    assert set_cookie, "Nenhum cookie Set-Cookie encontrado"
    assert "httponly" in set_cookie, f"HttpOnly ausente em: {set_cookie!r}"
    assert "samesite=lax" in set_cookie, f"SameSite=lax ausente em: {set_cookie!r}"
    assert "secure" in set_cookie, f"Secure ausente em: {set_cookie!r}"


@then("a resposta de login tem status 401")
def then_login_401(ctx: dict) -> None:  # type: ignore[type-arg]
    resp = ctx["response"]
    assert resp.status_code == 401, f"Esperado 401, obtido {resp.status_code}"


@then('o corpo da resposta contém "inválido"')
def then_corpo_invalido(ctx: dict) -> None:  # type: ignore[type-arg]
    body = ctx["response"].text
    assert "inválido" in body.lower() or "invalido" in body.lower(), (
        f"Mensagem 'inválido' não encontrada em: {body!r}"
    )


@then("nenhum cookie de sessão é criado na resposta")
def then_sem_cookie_sessao(ctx: dict) -> None:  # type: ignore[type-arg]
    set_cookie = ctx["response"].headers.get("set-cookie", "")
    # Com 401, não deve haver session cookie com dados
    # (pode haver cookie vazio/expirado, mas não com session data)
    if "session" in set_cookie.lower():
        # Verifica que não há session data preenchida — cookie de sessão vazio é ok
        assert "operator_id" not in set_cookie, (
            f"Cookie de sessão com dados encontrado após 401: {set_cookie!r}"
        )


@then("a resposta tem status 303")
def then_resposta_303(ctx: dict) -> None:  # type: ignore[type-arg]
    resp = ctx["response"]
    assert resp.status_code == 303, f"Esperado 303, obtido {resp.status_code}: {resp.text}"


@then("o header Location aponta para /login")
def then_location_login(ctx: dict) -> None:  # type: ignore[type-arg]
    location = ctx["response"].headers.get("location", "")
    assert location.endswith("/login"), f"Location inesperado: {location!r}"


@then("a resposta de logout tem status 303")
def then_logout_303(ctx: dict) -> None:  # type: ignore[type-arg]
    resp = ctx["logout_response"]
    assert resp.status_code == 303, f"Esperado 303, obtido {resp.status_code}: {resp.text}"


@then("o header Location da resposta de logout aponta para /login")
def then_logout_location_login(ctx: dict) -> None:  # type: ignore[type-arg]
    location = ctx["logout_response"].headers.get("location", "")
    assert location.endswith("/login"), f"Location inesperado: {location!r}"


@then("ao acessar GET /carteira após logout a resposta tem status 303")
def then_carteira_apos_logout_303(ctx: dict) -> None:  # type: ignore[type-arg]
    resp = ctx["client"].get("/carteira", follow_redirects=False)
    assert resp.status_code == 303, (
        f"Esperado 303 após logout, obtido {resp.status_code}: {resp.text}"
    )
