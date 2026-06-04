"""Testes determinísticos do CreditBudget / CreditLedger (ADR-004, WU-A2).

Relógio sempre injetado; sem rede; sem estado global.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from socialselling.core.credit_ledger import CreditBudget, CreditLedger

# ---------------------------------------------------------------------------
# Fixtures de data fixas
# ---------------------------------------------------------------------------

NOW_JUN = datetime(2026, 6, 4, 12, 0, 0)
NOW_JUL = datetime(2026, 7, 1, 0, 0, 0)


# ---------------------------------------------------------------------------
# try_spend dentro do cap
# ---------------------------------------------------------------------------


def test_try_spend_dentro_do_cap_debita_e_persiste(tmp_path: Path) -> None:
    """Gasto válido debita os contadores e persiste no disco."""
    ledger_path = tmp_path / "ledger.json"
    budget = CreditBudget(ledger_path, NOW_JUN)

    result = budget.try_spend(data=10, email=5, mobile=2)

    assert result is True
    assert budget.ledger.data_credits_used == 10
    assert budget.ledger.email_credits_used == 5
    assert budget.ledger.mobile_credits_used == 2

    # Verificar que o arquivo existe e foi persistido
    assert ledger_path.exists()


def test_try_spend_dentro_do_cap_remaining_cai(tmp_path: Path) -> None:
    """remaining_* reflete o débito corretamente."""
    budget = CreditBudget(tmp_path / "ledger.json", NOW_JUN)
    budget.try_spend(data=30, email=20, mobile=3)

    assert budget.remaining_data_credits() == 70
    assert budget.remaining_email_credits() == 80
    assert budget.remaining_mobile_credits() == 2


# ---------------------------------------------------------------------------
# try_spend que excede o cap
# ---------------------------------------------------------------------------


def test_try_spend_excede_data_cap_retorna_false_sem_debito(tmp_path: Path) -> None:
    """Estourar data cap retorna False e não altera nenhuma categoria."""
    budget = CreditBudget(tmp_path / "ledger.json", NOW_JUN)
    budget.try_spend(data=90)  # usado: 90

    result = budget.try_spend(data=11, email=1, mobile=1)  # 90+11=101 > 100

    assert result is False
    assert budget.ledger.data_credits_used == 90
    assert budget.ledger.email_credits_used == 0
    assert budget.ledger.mobile_credits_used == 0


def test_try_spend_excede_mobile_cap_retorna_false_sem_debito(tmp_path: Path) -> None:
    """Estourar mobile cap retorna False e deixa ledger inalterado."""
    budget = CreditBudget(tmp_path / "ledger.json", NOW_JUN)

    result = budget.try_spend(data=5, email=5, mobile=6)  # 6 > 5

    assert result is False
    assert budget.ledger.data_credits_used == 0
    assert budget.ledger.email_credits_used == 0
    assert budget.ledger.mobile_credits_used == 0


# ---------------------------------------------------------------------------
# Reset mensal
# ---------------------------------------------------------------------------


def test_reset_mensal_zera_contadores(tmp_path: Path) -> None:
    """Novo período no mesmo path cria ledger zerado."""
    ledger_path = tmp_path / "ledger.json"

    budget_jun = CreditBudget(ledger_path, NOW_JUN)
    budget_jun.try_spend(data=50, email=40, mobile=3)

    # Novo budget em julho no mesmo caminho — deve resetar
    budget_jul = CreditBudget(ledger_path, NOW_JUL)

    assert budget_jul.ledger.period == "2026-07"
    assert budget_jul.ledger.data_credits_used == 0
    assert budget_jul.ledger.email_credits_used == 0
    assert budget_jul.ledger.mobile_credits_used == 0


# ---------------------------------------------------------------------------
# Persistência entre instâncias no mesmo mês
# ---------------------------------------------------------------------------


def test_mesmo_mes_acumula_entre_instancias(tmp_path: Path) -> None:
    """Duas instâncias no mesmo mês/path acumulam os débitos."""
    ledger_path = tmp_path / "ledger.json"

    budget1 = CreditBudget(ledger_path, NOW_JUN)
    budget1.try_spend(data=20, email=10, mobile=1)

    # Segunda instância no mesmo mês lê o estado persistido
    budget2 = CreditBudget(ledger_path, NOW_JUN)
    assert budget2.ledger.data_credits_used == 20
    assert budget2.ledger.email_credits_used == 10
    assert budget2.ledger.mobile_credits_used == 1

    budget2.try_spend(data=15, email=5, mobile=2)

    assert budget2.ledger.data_credits_used == 35
    assert budget2.ledger.email_credits_used == 15
    assert budget2.ledger.mobile_credits_used == 3


# ---------------------------------------------------------------------------
# refund
# ---------------------------------------------------------------------------


def test_refund_simetrico(tmp_path: Path) -> None:
    """Gastar N e refund N retorna used ao estado anterior."""
    budget = CreditBudget(tmp_path / "ledger.json", NOW_JUN)
    budget.try_spend(data=30, email=20, mobile=3)

    budget.refund(data=30, email=20, mobile=3)

    assert budget.ledger.data_credits_used == 0
    assert budget.ledger.email_credits_used == 0
    assert budget.ledger.mobile_credits_used == 0


def test_refund_nao_vai_abaixo_de_zero(tmp_path: Path) -> None:
    """refund nunca deixa used negativo."""
    budget = CreditBudget(tmp_path / "ledger.json", NOW_JUN)
    # Sem nenhum gasto, refund de valores altos não deve negativar
    budget.refund(data=999, email=999, mobile=999)

    assert budget.ledger.data_credits_used == 0
    assert budget.ledger.email_credits_used == 0
    assert budget.ledger.mobile_credits_used == 0


# ---------------------------------------------------------------------------
# reconcile_exhausted
# ---------------------------------------------------------------------------


def test_reconcile_exhausted_marca_used_igual_cap(tmp_path: Path) -> None:
    """reconcile_exhausted seta used == cap para as categorias indicadas."""
    budget = CreditBudget(
        tmp_path / "ledger.json", NOW_JUN, data_cap=100, email_cap=100, mobile_cap=5
    )
    budget.try_spend(data=10)

    budget.reconcile_exhausted(data=True, mobile=True)

    assert budget.ledger.data_credits_used == 100
    assert budget.ledger.email_credits_used == 0  # não afetada
    assert budget.ledger.mobile_credits_used == 5


def test_reconcile_exhausted_persiste(tmp_path: Path) -> None:
    """Estado após reconcile é lido corretamente por nova instância."""
    ledger_path = tmp_path / "ledger.json"
    budget = CreditBudget(ledger_path, NOW_JUN)
    budget.reconcile_exhausted(email=True)

    budget2 = CreditBudget(ledger_path, NOW_JUN)
    assert budget2.ledger.email_credits_used == 100


# ---------------------------------------------------------------------------
# extra="forbid"
# ---------------------------------------------------------------------------


def test_credit_ledger_forbid_campo_extra() -> None:
    """CreditLedger rejeita campos desconhecidos via ValidationError."""
    with pytest.raises(ValidationError):
        CreditLedger.model_validate(
            {
                "period": "2026-06",
                "campo_inexistente": 42,
            }
        )
