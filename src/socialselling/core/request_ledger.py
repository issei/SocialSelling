"""Ledger de requisições Gemini por dia (RPD).

Governa o orçamento de REQUISIÇÕES/DIA do tier gratuito do Gemini entre runs,
persistindo em JSON atômico. Reseta automaticamente quando o dia vira.

Relógio sempre injetado (`now: datetime`) — nunca `datetime.now()` interno.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from socialselling.core.atomic import atomic_write_text

# 1 000 RPD é uma premissa conservadora do tier gratuito do Gemini Flash/Pro.
# Ajuste via parâmetro `rpd_cap` se o projeto migrar para outro tier.
_DEFAULT_RPD_CAP: int = 1000


class RequestLedger(BaseModel):
    """Estado persistido do orçamento de requisições de um único dia."""

    model_config = ConfigDict(extra="forbid")

    period: str
    """Dia de referência no formato 'YYYY-MM-DD'."""

    requests_used: int = Field(ge=0, default=0)
    """Total de requisições consumidas no período."""

    rpd_cap: int = Field(gt=0, default=_DEFAULT_RPD_CAP)
    """Teto de requisições permitidas no período."""


class RequestBudget:
    """Gerencia o orçamento diário de requisições Gemini com persistência atômica."""

    def __init__(
        self,
        path: Path,
        now: datetime,
        *,
        rpd_cap: int = _DEFAULT_RPD_CAP,
    ) -> None:
        """Carrega ou cria o ledger para o dia `now`.

        Se o arquivo estiver ausente ou o período divergir do dia atual,
        um novo ledger zerado é criado e persistido imediatamente (reset diário).
        """
        today = now.strftime("%Y-%m-%d")
        existing = self._load(path)

        if existing is None or existing.period != today:
            self._ledger = RequestLedger(period=today, requests_used=0, rpd_cap=rpd_cap)
            atomic_write_text(path, self._ledger.model_dump_json())
        else:
            self._ledger = existing

        self._path = path

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    @property
    def ledger(self) -> RequestLedger:
        """Acesso de leitura ao estado atual do ledger."""
        return self._ledger

    def remaining(self) -> int:
        """Retorna o número de requisições ainda disponíveis no período."""
        return max(0, self._ledger.rpd_cap - self._ledger.requests_used)

    def can_spend(self, n: int = 1) -> bool:
        """Retorna True se `n` requisições cabem dentro do cap."""
        return self._ledger.requests_used + n <= self._ledger.rpd_cap

    def try_consume(self, n: int = 1) -> bool:
        """Tenta consumir `n` requisições.

        Retorna True e persiste atomicamente se houver orçamento;
        retorna False sem alterar o ledger caso contrário.
        """
        if not self.can_spend(n):
            return False

        self._ledger = RequestLedger(
            period=self._ledger.period,
            requests_used=self._ledger.requests_used + n,
            rpd_cap=self._ledger.rpd_cap,
        )
        atomic_write_text(self._path, self._ledger.model_dump_json())
        return True

    # ------------------------------------------------------------------
    # Helper privado
    # ------------------------------------------------------------------

    @staticmethod
    def _load(path: Path) -> RequestLedger | None:
        """Carrega o ledger do arquivo; retorna None se ausente ou corrompido."""
        if not path.exists():
            return None
        return RequestLedger.model_validate_json(path.read_text(encoding="utf-8"))
