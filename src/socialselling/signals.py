"""Vocabulários controlados de sinais (intenção/timing e desqualificadores).

O vocabulário de intenção é DERIVADO do catálogo de hipóteses (config-driven).
O vocabulário de desqualificadores é estratégia estável do ICP — falsos positivos
a evitar (founder solo, negócio imaturo, retração, sem decisora, fora de setor).
"""

from __future__ import annotations

from socialselling.contracts import HypothesisCatalog

# Desqualificadores que ZERAM o lead (hard filter no M3). Tokens em snake_case.
DISQUALIFIER_VOCAB: list[str] = [
    "solo_sem_equipe",
    "menos_de_2_anos",
    "retracao_corte_custos",
    "multiplas_socias_sem_decisor",
    "fora_de_setor",
    "perfil_pessoal_sem_empresa",
]


def intent_vocab(catalog: HypothesisCatalog) -> list[str]:
    """União ordenada e sem repetição dos surface_signals de todas as hipóteses."""
    seen: list[str] = []
    for hypothesis in catalog.hypotheses:
        for signal in hypothesis.surface_signals:
            if signal not in seen:
                seen.append(signal)
    return seen
