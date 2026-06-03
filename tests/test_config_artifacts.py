"""Guarda de configuração: ICPs e catálogo de hipóteses devem validar contra os contratos."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from socialselling.contracts import HypothesisCatalog, ICPCriteria

_ROOT = Path(__file__).resolve().parents[1]
_CONFIG = _ROOT / "config"


@pytest.mark.parametrize(
    "filename",
    ["icp_criteria.example.json", "icp_criteria.talita.json"],
)
def test_icp_valido(filename: str) -> None:
    raw = json.loads((_CONFIG / filename).read_text(encoding="utf-8"))
    icp = ICPCriteria.model_validate(raw)
    assert icp.icp_id
    assert icp.firmographics.industries


def test_hypotheses_catalog_valido() -> None:
    raw = json.loads((_CONFIG / "hypotheses_catalog.json").read_text(encoding="utf-8"))
    catalog = HypothesisCatalog.model_validate(raw)
    assert catalog.hypotheses
    for hypothesis in catalog.hypotheses:
        assert 0.0 <= hypothesis.prior <= 1.0
        assert hypothesis.surface_signals
