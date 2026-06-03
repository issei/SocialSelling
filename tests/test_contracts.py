"""Sanity da Fase 0: valida os arquivos de exemplo contra os contratos.

NAO testa logica de negocio. Apenas prova que o toolchain esta executavel-ready
e que os contratos batem com os arquivos de config versionados.
"""

import json
from pathlib import Path

from socialselling.contracts import HypothesisCatalog, ICPCriteria

_CONFIG = Path(__file__).resolve().parents[1] / "config"


def test_icp_example_is_valid() -> None:
    data = json.loads((_CONFIG / "icp_criteria.example.json").read_text(encoding="utf-8"))
    icp = ICPCriteria.model_validate(data)
    assert icp.icp_id == "icp_enterprise_cloud_brazil"
    assert icp.firmographics.employee_range.min <= icp.firmographics.employee_range.max


def test_hypotheses_catalog_is_valid() -> None:
    data = json.loads((_CONFIG / "hypotheses_catalog.json").read_text(encoding="utf-8"))
    catalog = HypothesisCatalog.model_validate(data)
    assert len(catalog.hypotheses) >= 3
    assert all(0.0 <= h.prior <= 1.0 for h in catalog.hypotheses)
