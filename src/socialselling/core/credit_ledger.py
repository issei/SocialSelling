"""Ledger de crédito Apollo mensal com persistência atômica (ADR-004).

O orçamento PERSISTE entre runs e RESETA mensalmente via período "YYYY-MM".
O relógio é SEMPRE injetado (`now: datetime`) — nunca `datetime.now()` interno.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from socialselling.core.atomic import atomic_write_text


class CreditLedger(BaseModel):
    """Estado persistido do orçamento de crédito Apollo para um período mensal."""

    model_config = ConfigDict(extra="forbid")

    period: str  # formato "YYYY-MM"
    data_credits_used: int = Field(ge=0, default=0)
    email_credits_used: int = Field(ge=0, default=0)
    mobile_credits_used: int = Field(ge=0, default=0)
    data_credits_cap: int = Field(ge=0, default=100)
    email_credits_cap: int = Field(ge=0, default=100)
    mobile_credits_cap: int = Field(ge=0, default=5)


def _load_ledger(path: Path) -> CreditLedger | None:
    """Lê o ledger do disco; retorna None se o arquivo não existir."""
    if not path.exists():
        return None
    return CreditLedger.model_validate_json(path.read_text(encoding="utf-8"))


class CreditBudget:
    """Gerencia o orçamento de crédito Apollo com persistência atômica mensal."""

    def __init__(
        self,
        path: Path,
        now: datetime,
        *,
        data_cap: int = 100,
        email_cap: int = 100,
        mobile_cap: int = 5,
    ) -> None:
        """Carrega ou inicializa o ledger; reseta se o período mudou."""
        self._path = path
        period = now.strftime("%Y-%m")
        existing = _load_ledger(path)
        if existing is None or existing.period != period:
            self._ledger = CreditLedger(
                period=period,
                data_credits_cap=data_cap,
                email_credits_cap=email_cap,
                mobile_credits_cap=mobile_cap,
            )
            self._persist()
        else:
            self._ledger = existing

    # ------------------------------------------------------------------
    # Propriedade de inspeção (usada nos testes)
    # ------------------------------------------------------------------

    @property
    def ledger(self) -> CreditLedger:
        """Retorna o ledger atual (somente leitura lógica)."""
        return self._ledger

    # ------------------------------------------------------------------
    # Créditos disponíveis
    # ------------------------------------------------------------------

    def remaining_data_credits(self) -> int:
        """Créditos de dados restantes (nunca negativo)."""
        return max(0, self._ledger.data_credits_cap - self._ledger.data_credits_used)

    def remaining_email_credits(self) -> int:
        """Créditos de e-mail restantes (nunca negativo)."""
        return max(0, self._ledger.email_credits_cap - self._ledger.email_credits_used)

    def remaining_mobile_credits(self) -> int:
        """Créditos de celular restantes (nunca negativo)."""
        return max(0, self._ledger.mobile_credits_cap - self._ledger.mobile_credits_used)

    # ------------------------------------------------------------------
    # Operações de débito / crédito
    # ------------------------------------------------------------------

    def try_spend(
        self,
        *,
        data: int = 0,
        email: int = 0,
        mobile: int = 0,
    ) -> bool:
        """Tenta debitar créditos; retorna False (sem alterar nada) se algum cap estourar."""
        new_data = self._ledger.data_credits_used + data
        new_email = self._ledger.email_credits_used + email
        new_mobile = self._ledger.mobile_credits_used + mobile

        if (
            new_data > self._ledger.data_credits_cap
            or new_email > self._ledger.email_credits_cap
            or new_mobile > self._ledger.mobile_credits_cap
        ):
            return False

        self._ledger = self._ledger.model_copy(
            update={
                "data_credits_used": new_data,
                "email_credits_used": new_email,
                "mobile_credits_used": new_mobile,
            }
        )
        self._persist()
        return True

    def refund(
        self,
        *,
        data: int = 0,
        email: int = 0,
        mobile: int = 0,
    ) -> None:
        """Devolve créditos previamente debitados (nunca deixa used abaixo de zero)."""
        self._ledger = self._ledger.model_copy(
            update={
                "data_credits_used": max(0, self._ledger.data_credits_used - data),
                "email_credits_used": max(0, self._ledger.email_credits_used - email),
                "mobile_credits_used": max(0, self._ledger.mobile_credits_used - mobile),
            }
        )
        self._persist()

    def reconcile_exhausted(
        self,
        *,
        data: bool = False,
        email: bool = False,
        mobile: bool = False,
    ) -> None:
        """Marca used == cap para as categorias indicadas (verdade do provedor vence)."""
        updates: dict[str, int] = {}
        if data:
            updates["data_credits_used"] = self._ledger.data_credits_cap
        if email:
            updates["email_credits_used"] = self._ledger.email_credits_cap
        if mobile:
            updates["mobile_credits_used"] = self._ledger.mobile_credits_cap
        if updates:
            self._ledger = self._ledger.model_copy(update=updates)
            self._persist()

    # ------------------------------------------------------------------
    # Persistência interna
    # ------------------------------------------------------------------

    def _persist(self) -> None:
        """Grava o ledger atual atomicamente em disco."""
        atomic_write_text(self._path, self._ledger.model_dump_json())
