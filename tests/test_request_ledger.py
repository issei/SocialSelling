"""Testes determinísticos do RequestBudget / RequestLedger (ADR-005).

Relógio sempre injetado; sem rede; persistência em tmp_path.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from socialselling.core.request_ledger import RequestBudget, RequestLedger

_NOW_DAY1 = datetime(2026, 6, 4, 12, 0, 0)
_NOW_DAY2 = datetime(2026, 6, 5, 0, 0, 1)


# ---------------------------------------------------------------------------
# try_consume dentro do cap
# ---------------------------------------------------------------------------


def test_try_consume_dentro_do_cap(tmp_path: Path) -> None:
    """Consumo bem-sucedido soma ao ledger e persiste."""
    path = tmp_path / "ledger.json"
    budget = RequestBudget(path, _NOW_DAY1, rpd_cap=10)

    assert budget.try_consume(3) is True
    assert budget.ledger.requests_used == 3
    assert budget.remaining() == 7

    # Confirma que foi persistido: nova instância lê o mesmo valor
    budget2 = RequestBudget(path, _NOW_DAY1, rpd_cap=10)
    assert budget2.ledger.requests_used == 3


# ---------------------------------------------------------------------------
# try_consume que excede o cap
# ---------------------------------------------------------------------------


def test_try_consume_excede_cap_nao_altera(tmp_path: Path) -> None:
    """Consumo que ultrapassa o cap retorna False e não altera o ledger."""
    path = tmp_path / "ledger.json"
    budget = RequestBudget(path, _NOW_DAY1, rpd_cap=5)
    budget.try_consume(5)  # esgota

    assert budget.try_consume(1) is False
    assert budget.ledger.requests_used == 5
    assert budget.remaining() == 0

    # Persistência inalterada
    budget2 = RequestBudget(path, _NOW_DAY1, rpd_cap=5)
    assert budget2.ledger.requests_used == 5


# ---------------------------------------------------------------------------
# can_spend
# ---------------------------------------------------------------------------


def test_can_spend_reflete_limite(tmp_path: Path) -> None:
    """can_spend retorna True ou False conforme o orçamento restante."""
    path = tmp_path / "ledger.json"
    budget = RequestBudget(path, _NOW_DAY1, rpd_cap=4)
    budget.try_consume(3)

    assert budget.can_spend(1) is True
    assert budget.can_spend(2) is False  # 3+2 > 4


# ---------------------------------------------------------------------------
# Reset diário
# ---------------------------------------------------------------------------


def test_reset_diario_zera_ledger(tmp_path: Path) -> None:
    """Novo dia cria ledger zerado mesmo que o arquivo exista com consumo."""
    path = tmp_path / "ledger.json"
    budget_dia1 = RequestBudget(path, _NOW_DAY1, rpd_cap=10)
    budget_dia1.try_consume(7)
    assert budget_dia1.ledger.requests_used == 7

    # Novo run no dia seguinte
    budget_dia2 = RequestBudget(path, _NOW_DAY2, rpd_cap=10)
    assert budget_dia2.ledger.requests_used == 0
    assert budget_dia2.ledger.period == "2026-06-05"
    assert budget_dia2.remaining() == 10


# ---------------------------------------------------------------------------
# Acúmulo no mesmo dia entre instâncias
# ---------------------------------------------------------------------------


def test_acumulo_mesmo_dia_entre_instancias(tmp_path: Path) -> None:
    """Consumo de uma instância é visível em instâncias subsequentes do mesmo dia."""
    path = tmp_path / "ledger.json"

    b1 = RequestBudget(path, _NOW_DAY1, rpd_cap=20)
    b1.try_consume(5)

    b2 = RequestBudget(path, _NOW_DAY1, rpd_cap=20)
    assert b2.ledger.requests_used == 5
    b2.try_consume(8)

    b3 = RequestBudget(path, _NOW_DAY1, rpd_cap=20)
    assert b3.ledger.requests_used == 13
    assert b3.remaining() == 7


# ---------------------------------------------------------------------------
# extra="forbid"
# ---------------------------------------------------------------------------


def test_extra_forbid_levanta_validation_error() -> None:
    """RequestLedger rejeita campos desconhecidos (extra='forbid')."""
    with pytest.raises(ValidationError):
        RequestLedger.model_validate(
            {"period": "2026-06-04", "requests_used": 0, "rpd_cap": 100, "campo_extra": True}
        )
