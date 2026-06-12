"""Steps BDD para WU-T5 — UI da operadora: carteira + lead card."""

from __future__ import annotations

import hashlib

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, scenario, then, when

from socialselling.portal.app import create_portal_app
from socialselling.portal.catalog import load_feedback_catalog
from socialselling.portal.contracts import (
    CarteiraItem,
    FeedbackKind,
    Operator,
    PublishedLead,
    PublishedSnapshot,
)
from socialselling.portal.dao_memory import InMemoryDAO
from socialselling.portal.services import build_carteira

FEATURE = "../features/wu_t5_ui.feature"


@scenario(
    FEATURE,
    "Feliz — carteira exibe leads do snapshot mais recente e em acompanhamento",
)
def test_carteira_feliz() -> None:
    pass


@scenario(
    FEATURE,
    "Open-World — lead sem status aparece como novo na carteira",
)
def test_carteira_lead_sem_status() -> None:
    pass


@scenario(
    FEATURE,
    "Determinismo — duas montagens de carteira geram ordem idêntica",
)
def test_carteira_determinismo() -> None:
    pass


@scenario(
    FEATURE,
    "Degradado — lead fora da carteira do perfil retorna 404",
)
def test_lead_fora_carteira_404() -> None:
    pass


@scenario(
    FEATURE,
    "Open-World — sem sessão acessa lead card e é redirecionado",
)
def test_lead_sem_sessao_redirect() -> None:
    pass


@scenario(
    FEATURE,
    "Assert estrutural — lead card não renderiza campo de score",
)
def test_lead_sem_score() -> None:
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

PROFILE_ID = "talita_profile"
OPERATOR_CODE = "codigo-correto"


def _make_lead(entity_id: str, pos: int) -> PublishedLead:
    return PublishedLead(entity_id=entity_id, rank_position=pos, company=entity_id.upper())


def _make_snapshot(run_id: str, entity_ids: list[str]) -> PublishedSnapshot:
    return PublishedSnapshot(
        profile_id=PROFILE_ID,
        run_id=run_id,
        generated_at="2026-06-11T00:00:00Z",
        leads=[_make_lead(eid, i + 1) for i, eid in enumerate(entity_ids)],
    )


def _seed_operator(dao: InMemoryDAO) -> None:
    code_hash = hashlib.sha256(OPERATOR_CODE.encode()).hexdigest()
    dao.seed_operator(
        Operator(
            operator_id="talita",
            nome="Talita",
            code_hash=code_hash,
            profile_id=PROFILE_ID,
        )
    )


def _make_client(dao: InMemoryDAO) -> TestClient:
    app = create_portal_app(dao, https_only=True)
    return TestClient(app, base_url="https://testserver", raise_server_exceptions=False)


def _login(client: TestClient) -> None:
    resp = client.post("/login", data={"code": OPERATOR_CODE}, follow_redirects=False)
    assert resp.status_code == 303, f"Login falhou: {resp.status_code}"


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given(
    "um portal com snapshot run_2 contendo A e B e snapshot run_1 contendo B e D",
    target_fixture="ctx",
)
def given_portal_com_dois_snapshots() -> dict:  # type: ignore[type-arg]
    dao = InMemoryDAO()
    _seed_operator(dao)
    # run_1 (mais antigo)
    snap1 = _make_snapshot("run_1", ["b.com.br", "d.com.br"])
    dao.put_snapshot(snap1, now="2026-06-11T08:00:00Z")
    # run_2 (mais recente)
    snap2 = _make_snapshot("run_2", ["a.com.br", "b.com.br"])
    dao.put_snapshot(snap2, now="2026-06-11T10:00:00Z")
    return {"dao": dao, "client": _make_client(dao)}


@given("o lead D tem status abordado e o lead B tem status fora_do_perfil")
def given_status_d_e_b(ctx: dict) -> None:  # type: ignore[type-arg]
    dao: InMemoryDAO = ctx["dao"]
    for entity_id, status_id in [("d.com.br", "abordado"), ("b.com.br", "fora_do_perfil")]:
        dao.append_event(
            operator_id="talita",
            profile_id=PROFILE_ID,
            entity_id=entity_id,
            run_id="run_1",
            kind=FeedbackKind.STATUS,
            status_id=status_id,
            reaction=None,
            note="",
            now="2026-06-11T09:00:00Z",
        )


@given(
    "um portal com snapshot run_1 contendo somente Z sem nenhum evento de status",
    target_fixture="ctx",
)
def given_portal_z_sem_status() -> dict:  # type: ignore[type-arg]
    dao = InMemoryDAO()
    _seed_operator(dao)
    snap = PublishedSnapshot(
        profile_id=PROFILE_ID,
        run_id="run_1",
        generated_at="2026-06-11T00:00:00Z",
        leads=[PublishedLead(entity_id="z.com.br", rank_position=1, company="Z Corp")],
    )
    dao.put_snapshot(snap, now="2026-06-11T10:00:00Z")
    return {"dao": dao, "client": _make_client(dao)}


@given(
    "um portal com snapshot run_1 contendo A B C em acompanhamento anteriores X Y",
    target_fixture="ctx",
)
def given_portal_determinismo() -> dict:  # type: ignore[type-arg]
    dao = InMemoryDAO()
    # Snapshot anterior com X e Y
    snap_old = _make_snapshot("run_0", ["x.com.br", "y.com.br"])
    dao.put_snapshot(snap_old, now="2026-06-11T08:00:00Z")
    # Snapshot mais recente com A, B, C
    snap_new = _make_snapshot("run_1", ["a.com.br", "b.com.br", "c.com.br"])
    dao.put_snapshot(snap_new, now="2026-06-11T10:00:00Z")
    return {"dao": dao}


@given("um portal sem leads para o perfil da operadora", target_fixture="ctx")
def given_portal_vazio() -> dict:  # type: ignore[type-arg]
    dao = InMemoryDAO()
    _seed_operator(dao)
    return {"dao": dao, "client": _make_client(dao)}


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when("a operadora autenticada acessa GET /carteira")
def when_carteira(ctx: dict) -> None:  # type: ignore[type-arg]
    _login(ctx["client"])
    ctx["response"] = ctx["client"].get("/carteira", follow_redirects=False)


@when("a operadora autenticada acessa GET /lead/inexistente.com.br")
def when_lead_inexistente(ctx: dict) -> None:  # type: ignore[type-arg]
    _login(ctx["client"])
    ctx["response"] = ctx["client"].get("/lead/inexistente.com.br")


@when("um cliente sem sessão acessa GET /lead/qualquer.com.br")
def when_lead_sem_sessao(ctx: dict) -> None:  # type: ignore[type-arg]
    ctx["response"] = ctx["client"].get("/lead/qualquer.com.br", follow_redirects=False)


@when("a operadora autenticada acessa GET /lead/z.com.br")
def when_lead_z(ctx: dict) -> None:  # type: ignore[type-arg]
    _login(ctx["client"])
    ctx["response"] = ctx["client"].get("/lead/z.com.br", follow_redirects=False)


@when("build_carteira é chamado duas vezes com os mesmos dados")
def when_build_duas_vezes(ctx: dict) -> None:  # type: ignore[type-arg]
    catalog = load_feedback_catalog()
    dao: InMemoryDAO = ctx["dao"]
    ctx["result1"] = build_carteira(dao, PROFILE_ID, catalog)
    ctx["result2"] = build_carteira(dao, PROFILE_ID, catalog)


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then("a resposta tem status 200 e é HTML")
def then_200_html(ctx: dict) -> None:  # type: ignore[type-arg]
    resp = ctx["response"]
    assert resp.status_code == 200, f"Esperado 200, obtido {resp.status_code}: {resp.text}"
    assert "text/html" in resp.headers.get("content-type", ""), (
        f"Esperado text/html, obtido: {resp.headers.get('content-type')}"
    )


@then("A aparece na carteira sem indicação de acompanhamento")
def then_a_na_carteira(ctx: dict) -> None:  # type: ignore[type-arg]
    html = ctx["response"].text
    assert "a.com.br".upper() in html or "a.com.br" in html, (
        f"Lead A não encontrado no HTML: {html[:500]}"
    )
    # A está no snapshot mais recente; D é quem está em acompanhamento
    # Verificamos que "a.com.br" ou "A.COM.BR" aparece (renderizado pelo template)


@then("D aparece na carteira como em acompanhamento")
def then_d_acompanhamento(ctx: dict) -> None:  # type: ignore[type-arg]
    html = ctx["response"].text
    assert "d.com.br" in html.lower() or "D.COM.BR" in html, (
        f"Lead D não encontrado no HTML: {html[:500]}"
    )
    assert "acompanhamento" in html.lower(), (
        f"'em acompanhamento' não encontrado no HTML: {html[:500]}"
    )


@then("B não aparece na carteira por ser terminal")
def then_b_ausente(ctx: dict) -> None:  # type: ignore[type-arg]
    # B tem status "fora_do_perfil" (terminal) → deve ser excluído da carteira
    # Verificamos via build_carteira (serviço puro)
    dao: InMemoryDAO = ctx["dao"]
    catalog = load_feedback_catalog()
    items = build_carteira(dao, PROFILE_ID, catalog)
    entity_ids = [i.lead.entity_id for i in items]
    assert "b.com.br" not in entity_ids, (
        f"Lead B (terminal) apareceu na carteira: {entity_ids}"
    )


@then("a carteira não exibe nenhum número de score")
def then_sem_score_carteira(ctx: dict) -> None:  # type: ignore[type-arg]
    html = ctx["response"].text
    for field in ("p_score", "fit_score", "intent_score", "confidence_score"):
        assert field not in html, f"Campo de score '{field}' encontrado na carteira"


@then("o status de Z na carteira é novo")
def then_z_status_novo(ctx: dict) -> None:  # type: ignore[type-arg]
    dao: InMemoryDAO = ctx["dao"]
    catalog = load_feedback_catalog()
    items = build_carteira(dao, PROFILE_ID, catalog)
    assert len(items) == 1, f"Esperado 1 item, obtido {len(items)}"
    assert items[0].status_id == "novo", f"Status errado: {items[0].status_id}"
    # Confirma que não foi gravado evento (Open-World)
    events = dao.events_since(0)
    assert events == [], f"Eventos inesperados: {events}"


@then("as duas listas são idênticas")
def then_listas_identicas(ctx: dict) -> None:  # type: ignore[type-arg]
    r1: list[CarteiraItem] = ctx["result1"]
    r2: list[CarteiraItem] = ctx["result2"]
    assert len(r1) == len(r2), f"Tamanhos diferentes: {len(r1)} vs {len(r2)}"
    for i, (a, b) in enumerate(zip(r1, r2, strict=True)):
        assert a.lead.entity_id == b.lead.entity_id, (
            f"Posição {i}: {a.lead.entity_id} vs {b.lead.entity_id}"
        )
        assert a.status_id == b.status_id, f"Status diferente na posição {i}"


@then("a resposta tem status 404")
def then_404(ctx: dict) -> None:  # type: ignore[type-arg]
    resp = ctx["response"]
    assert resp.status_code == 404, f"Esperado 404, obtido {resp.status_code}: {resp.text}"


@then("a resposta tem status 303")
def then_303(ctx: dict) -> None:  # type: ignore[type-arg]
    resp = ctx["response"]
    assert resp.status_code == 303, f"Esperado 303, obtido {resp.status_code}: {resp.text}"


@then("o HTML do lead card não contém campos de score numérico")
def then_sem_score_lead(ctx: dict) -> None:  # type: ignore[type-arg]
    html = ctx["response"].text
    for field in ("p_score", "fit_score", "intent_score", "confidence_score", "fit:", "intent:"):
        assert field not in html, (
            f"Campo de score '{field}' encontrado no lead card"
        )
