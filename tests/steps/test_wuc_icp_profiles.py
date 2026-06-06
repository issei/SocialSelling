"""Step defs — WU-C ICP Profile CRUD (pytest-bdd). Sem rede; FS isolado em tmp_path."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, scenarios, then, when

from socialselling.web.app import create_app

scenarios("../features/wuc_icp_profiles.feature")

_ROOT = Path(__file__).resolve().parents[2]
_REAL_CONFIG = _ROOT / "config"

_VALID_ICP_CRITERIA: dict[str, Any] = {
    "icp_id": "icp_founders_servicos_brasil",
    "firmographics": {
        "industries": ["software", "saas"],
        "employee_range": {"min": 5, "max": 50},
        "geographies": {"country": "BR", "regions": []},
        "business_models": ["B2B"],
    },
    "technographics": {"mandatory": [], "preferred": [], "excluded": []},
    "persona_matrix": {"target_roles": ["FOUNDER", "CEO"], "min_seniority": "FOUNDER_OWNER"},
    "intent_triggers": [],
}


@pytest.fixture
def ctx() -> dict[str, Any]:
    return {}


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given("um ambiente de teste com config isolada e catálogo base carregado", target_fixture="ctx")
def _given_env_with_catalog(tmp_path: Path) -> dict[str, Any]:
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    for name in ("hypotheses_catalog.json", "runtime.toml"):
        shutil.copy(_REAL_CONFIG / name, cfg_dir / name)
    client = TestClient(create_app(config_dir=cfg_dir, runtime_path=cfg_dir / "runtime.toml"))
    return {"client": client, "config_dir": cfg_dir}


@given("um ambiente de teste com config isolada sem perfis salvos", target_fixture="ctx")
def _given_env_empty_profiles(tmp_path: Path) -> dict[str, Any]:
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    for name in ("hypotheses_catalog.json", "runtime.toml"):
        shutil.copy(_REAL_CONFIG / name, cfg_dir / name)
    client = TestClient(create_app(config_dir=cfg_dir, runtime_path=cfg_dir / "runtime.toml"))
    return {"client": client, "config_dir": cfg_dir}


@given('um payload de perfil válido com name "SaaS Latam" e H_01 habilitado')
def _given_valid_payload(ctx: dict[str, Any]) -> None:
    ctx["payload"] = {
        "name": "SaaS Latam",
        "description": "Perfil de teste.",
        "icp_criteria": _VALID_ICP_CRITERIA,
        "hypotheses_config": {"H_01": {"enabled": True, "base_weight": 0.8}},
    }


@given('um payload de perfil com hypotheses_config contendo "H_INVALIDO"')
def _given_invalid_payload(ctx: dict[str, Any]) -> None:
    ctx["payload"] = {
        "name": "Perfil Inválido",
        "description": "",
        "icp_criteria": _VALID_ICP_CRITERIA,
        "hypotheses_config": {"H_INVALIDO": {"enabled": True, "base_weight": 0.5}},
    }


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when("POST /api/v1/profiles é chamado com o payload válido")
def _when_post_valid(ctx: dict[str, Any]) -> None:
    ctx["response"] = ctx["client"].post("/api/v1/profiles", json=ctx["payload"])


@when("POST /api/v1/profiles é chamado com o payload inválido")
def _when_post_invalid(ctx: dict[str, Any]) -> None:
    ctx["response"] = ctx["client"].post("/api/v1/profiles", json=ctx["payload"])


@when("GET /api/v1/profiles é chamado")
def _when_get_profiles(ctx: dict[str, Any]) -> None:
    ctx["response"] = ctx["client"].get("/api/v1/profiles")


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then("a resposta tem status 201")
def _then_201(ctx: dict[str, Any]) -> None:
    assert ctx["response"].status_code == 201, ctx["response"].text


@then("a resposta tem status 422")
def _then_422(ctx: dict[str, Any]) -> None:
    assert ctx["response"].status_code == 422, ctx["response"].text


@then("a resposta tem status 200")
def _then_200(ctx: dict[str, Any]) -> None:
    assert ctx["response"].status_code == 200, ctx["response"].text


@then("o campo profile_id está presente no JSON de resposta")
def _then_profile_id_present(ctx: dict[str, Any]) -> None:
    data = ctx["response"].json()
    assert "profile_id" in data
    assert data["profile_id"]  # non-empty


@then("GET /api/v1/profiles retorna uma lista com o perfil criado")
def _then_list_has_profile(ctx: dict[str, Any]) -> None:
    created_id = ctx["response"].json()["profile_id"]
    resp = ctx["client"].get("/api/v1/profiles")
    assert resp.status_code == 200
    profiles = resp.json()
    assert any(p["profile_id"] == created_id for p in profiles)


@then("o JSON de resposta é uma lista vazia")
def _then_empty_list(ctx: dict[str, Any]) -> None:
    assert ctx["response"].json() == []
