"""Testes da reforma cognitiva no M2 (ADR-005): chunking em lotes + orçamento RPD.

Sem rede: fake Gemini conta chamadas e responde por prompt. Determinístico.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from socialselling.contracts import ObservedEvidence
from socialselling.core.cache import JsonCache
from socialselling.core.request_ledger import RequestBudget
from socialselling.modules.m2_extracao import run_m2

_NOW = datetime(2026, 6, 4, 10, 0, 0)
_VOCAB: list[str] = ["expansao"]
_DISQ: list[str] = ["b2c"]


def _evi(n: int) -> list[ObservedEvidence]:
    return [
        ObservedEvidence(
            evidence_id=f"e{i:03d}",
            query="q",
            source_url=f"https://x/{i}",
            title=f"Empresa {i}",
            snippet=f"conteudo {i}",
            captured_at=_NOW.isoformat(),
            source_trust=0.6,
            missing_evidence=False,
        )
        for i in range(n)
    ]


class _CountingGemini:
    """Conta chamadas; devolve 1 inferência nomeada pelo nº de evidências do prompt."""

    def __init__(self) -> None:
        self.calls = 0

    def generate_json(self, prompt: str) -> dict[str, Any]:
        self.calls += 1
        return {
            "inferences": [
                {
                    "company": {"normalized_name": f"Co{self.calls}", "confidence": 0.7},
                    "people": [],
                    "derived_from": [],
                    "intent_signals": [],
                    "disqualifiers": [],
                    "persona": "empresa",
                    "confidence": 0.7,
                }
            ]
        }


def test_um_lote_quando_cabe_no_batch_size(tmp_path: Path) -> None:
    gem = _CountingGemini()
    out = run_m2(
        _evi(10),
        client=gem,
        cache=JsonCache(tmp_path / "g"),
        now=_NOW,
        cache_ttl_hours=24,
        intent_vocab=_VOCAB,
        disqualifier_vocab=_DISQ,
        batch_size=50,
    )
    assert gem.calls == 1  # 10 <= 50 => 1 chamada (paridade com o M2 atual)
    assert len(out) == 1


def test_multiplos_lotes_para_volume(tmp_path: Path) -> None:
    gem = _CountingGemini()
    out = run_m2(
        _evi(25),
        client=gem,
        cache=JsonCache(tmp_path / "g"),
        now=_NOW,
        cache_ttl_hours=24,
        intent_vocab=_VOCAB,
        disqualifier_vocab=_DISQ,
        batch_size=10,
    )
    assert gem.calls == 3  # 25 evidências / lote 10 => 3 chamadas
    assert len(out) == 3  # uma inferência por lote (fake)


def test_rpd_esgotado_pula_lote(tmp_path: Path) -> None:
    gem = _CountingGemini()
    # Orçamento de 2 requisições/dia: o 3º lote é pulado (degrada, sem erro).
    budget = RequestBudget(tmp_path / "rpd.json", _NOW, rpd_cap=2)
    out = run_m2(
        _evi(25),
        client=gem,
        cache=JsonCache(tmp_path / "g"),
        now=_NOW,
        cache_ttl_hours=24,
        intent_vocab=_VOCAB,
        disqualifier_vocab=_DISQ,
        batch_size=10,
        request_budget=budget,
    )
    assert gem.calls == 2  # só 2 lotes couberam no orçamento
    assert len(out) == 2
    assert budget.remaining() == 0


def test_cache_hit_nao_consome_rpd(tmp_path: Path) -> None:
    cache = JsonCache(tmp_path / "g")
    # 1ª passada povoa o cache (sem orçamento).
    run_m2(
        _evi(10),
        client=_CountingGemini(),
        cache=cache,
        now=_NOW,
        cache_ttl_hours=24,
        intent_vocab=_VOCAB,
        disqualifier_vocab=_DISQ,
        batch_size=50,
    )
    # 2ª passada: cache hit => NÃO debita o orçamento RPD.
    budget = RequestBudget(tmp_path / "rpd.json", _NOW, rpd_cap=5)
    run_m2(
        _evi(10),
        client=_CountingGemini(),
        cache=cache,
        now=_NOW,
        cache_ttl_hours=24,
        intent_vocab=_VOCAB,
        disqualifier_vocab=_DISQ,
        batch_size=50,
        request_budget=budget,
    )
    assert budget.remaining() == 5  # nenhuma requisição consumida


def test_determinismo_chunking(tmp_path: Path) -> None:
    a = run_m2(
        _evi(25),
        client=_CountingGemini(),
        cache=JsonCache(tmp_path / "a"),
        now=_NOW,
        cache_ttl_hours=24,
        intent_vocab=_VOCAB,
        disqualifier_vocab=_DISQ,
        batch_size=10,
    )
    b = run_m2(
        _evi(25),
        client=_CountingGemini(),
        cache=JsonCache(tmp_path / "b"),
        now=_NOW,
        cache_ttl_hours=24,
        intent_vocab=_VOCAB,
        disqualifier_vocab=_DISQ,
        batch_size=10,
    )
    assert [i.company.company_id for i in a] == [i.company.company_id for i in b]
