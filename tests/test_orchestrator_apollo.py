"""Testes do wiring Apollo no orquestrador (WU-A4c): encaminhamento + paridade.

Sem rede: usa um spy em run_m1 (monkeypatch) para verificar que o `apollo` chega ao M1
como `apollo_client`. Determinístico.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from socialselling.config import load_runtime
from socialselling.contracts import HypothesisCatalog, ICPCriteria
from socialselling.orchestrator import run_pipeline

_ROOT = Path(__file__).resolve().parents[1]
_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _icp() -> ICPCriteria:
    raw = json.loads((_ROOT / "config" / "icp_criteria.talita.json").read_text("utf-8"))
    return ICPCriteria.model_validate(raw)


def _catalog() -> HypothesisCatalog:
    raw = json.loads((_ROOT / "config" / "hypotheses_catalog.json").read_text("utf-8"))
    return HypothesisCatalog.model_validate(raw)


class _NeverCalledGemini:
    def generate_json(self, prompt: str) -> dict[str, Any]:  # pragma: no cover
        raise AssertionError("Gemini não deve ser chamado com evidências vazias")


class _UnusedTavily:
    def search(
        self,
        query: str,
        max_results: int,
        search_depth: str,
        include_domains: list[str] | None = None,
    ) -> dict[str, Any]:  # pragma: no cover - run_m1 é stubado
        return {"results": []}


def _run_with_spy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, apollo: object | None
) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def fake_run_m1(icp: ICPCriteria, **kwargs: Any) -> list[Any]:
        captured["apollo_client"] = kwargs.get("apollo_client")
        return []

    monkeypatch.setattr("socialselling.orchestrator.run_m1", fake_run_m1)
    cfg = load_runtime(_ROOT / "config" / "runtime.toml")
    cards = run_pipeline(
        _icp(),
        tavily=_UnusedTavily(),
        gemini=_NeverCalledGemini(),
        hypotheses=_catalog(),
        cache_root=tmp_path,
        now=_NOW,
        cfg=cfg,
        apollo=apollo,  # type: ignore[arg-type]
    )
    captured["cards"] = cards
    return captured


def test_run_pipeline_encaminha_apollo_ao_m1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sentinel = object()
    captured = _run_with_spy(monkeypatch, tmp_path, sentinel)
    assert captured["apollo_client"] is sentinel
    assert captured["cards"] == []  # evidências vazias => 0 cards, sem chamar Gemini


def test_run_pipeline_apollo_none_por_padrao(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured = _run_with_spy(monkeypatch, tmp_path, None)
    assert captured["apollo_client"] is None  # paridade: sem Apollo por padrão
