"""Steps BDD para WU-T6 — lint do render.yaml + import do entrypoint de produção.

Offline e determinístico. NÃO toca o portal real (o smoke_portal.py é operacional, fora do gate).
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest
import yaml
from pytest_bdd import given, scenario, then, when

_ROOT = Path(__file__).resolve().parent.parent.parent
_RENDER_YAML = _ROOT / "render.yaml"
FEATURE = "../features/wu_t6_render_config.feature"


@scenario(FEATURE, "render.yaml é YAML válido e bate com o contrato da SDD §8")
def test_render_contract() -> None:
    pass


@scenario(FEATURE, "Nenhum segredo está commitado (env vars só referenciadas)")
def test_no_secrets() -> None:
    pass


@scenario(FEATURE, "O entrypoint de produção importa sem DATABASE_URL")
def test_entrypoint_imports() -> None:
    pass


@pytest.fixture
def ctx() -> dict[str, Any]:
    return {}


# --------------------------------------------------------------------------- Given


@given("o arquivo render.yaml na raiz do repositório", target_fixture="ctx")
def given_render_yaml() -> dict[str, Any]:
    return {"text": _RENDER_YAML.read_text(encoding="utf-8")}


@given("que DATABASE_URL não está no ambiente", target_fixture="ctx")
def given_no_db_url(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    return {}


# --------------------------------------------------------------------------- When


@when("faço o parse YAML")
def when_parse_yaml(ctx: dict[str, Any]) -> None:
    ctx["doc"] = yaml.safe_load(ctx["text"])
    ctx["service"] = ctx["doc"]["services"][0]


@when("importo socialselling.portal.main")
def when_import_main(ctx: dict[str, Any]) -> None:
    module = importlib.import_module("socialselling.portal.main")
    importlib.reload(module)
    ctx["module"] = module


# --------------------------------------------------------------------------- Then


@then('há um serviço web "socialselling-portal" na região "virginia" no plano "free"')
def then_service(ctx: dict[str, Any]) -> None:
    svc = ctx["service"]
    assert svc["type"] == "web"
    assert svc["name"] == "socialselling-portal"
    assert svc["region"] == "virginia"
    assert svc["plan"] == "free"


@then('o build é "pip install -e \\".[portal]\\""')
def then_build(ctx: dict[str, Any]) -> None:
    assert ctx["service"]["buildCommand"] == 'pip install -e ".[portal]"'


@then('o start usa "uvicorn socialselling.portal.main:app"')
def then_start(ctx: dict[str, Any]) -> None:
    assert "uvicorn socialselling.portal.main:app" in ctx["service"]["startCommand"]


@then('o health check é "/healthz"')
def then_health(ctx: dict[str, Any]) -> None:
    assert ctx["service"]["healthCheckPath"] == "/healthz"


@then("as env vars DATABASE_URL, PUBLISH_TOKEN e SECRET_KEY existem")
def then_env_vars(ctx: dict[str, Any]) -> None:
    keys = {ev["key"] for ev in ctx["service"]["envVars"]}
    assert {"DATABASE_URL", "PUBLISH_TOKEN", "SECRET_KEY"} <= keys


@then("nenhuma env var tem valor commitado (todas com sync=false)")
def then_no_values(ctx: dict[str, Any]) -> None:
    for ev in ctx["service"]["envVars"]:
        assert "value" not in ev, f"segredo commitado em {ev['key']}"
        assert ev.get("sync") is False, f"{ev['key']} deveria ter sync: false"


@then("o atributo app existe no módulo")
def then_app_exists(ctx: dict[str, Any]) -> None:
    assert hasattr(ctx["module"], "app"), "portal.main:app ausente — start command quebraria"
