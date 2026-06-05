"""Testes da integração corpus<->pipeline (ADR-006): acumular + projeção ranqueada.

Determinístico, sem rede. Garante: volume acumula entre runs; ranking sobre o corpus
inteiro com tie-break estável; max_display é só EXIBIÇÃO.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from socialselling.contracts import LeadCard, LeadContact, LeadLinks, ProspectScore
from socialselling.corpus.integration import accumulate, accumulate_and_rank, ranked_view
from socialselling.corpus.store import CorpusStore

_NOW = datetime(2026, 6, 4, 10, 0, 0)
_LATER = datetime(2026, 6, 5, 10, 0, 0)


def _card(company_id: str, p_score: float, name: str | None = None) -> LeadCard:
    return LeadCard(
        rank=1,
        display_name=name or company_id,
        company=name or company_id,
        links=LeadLinks(),
        contact=LeadContact(),
        score=ProspectScore(
            company_id=company_id,
            fit=0.5,
            intent=0.5,
            confidence=0.8,
            p_score=p_score,
        ),
    )


def test_accumulate_e_idempotente(tmp_path: Path) -> None:
    store = CorpusStore(tmp_path / "corpus.json")
    accumulate(store, [_card("c1", 0.7)], _NOW)
    accumulate(store, [_card("c1", 0.7)], _NOW)  # mesmo card/now => sem duplicar
    assert len(store) == 1


def test_acumula_entre_runs(tmp_path: Path) -> None:
    path = tmp_path / "corpus.json"
    accumulate(CorpusStore(path), [_card("c1", 0.7)], _NOW)
    # Run 2 (nova instância, mesmo path) traz outra entidade -> corpus cresce.
    accumulate(CorpusStore(path), [_card("c2", 0.9)], _LATER)
    assert len(CorpusStore(path)) == 2


def test_ranked_view_ordena_e_reranqueia(tmp_path: Path) -> None:
    store = CorpusStore(tmp_path / "corpus.json")
    accumulate(store, [_card("c1", 0.40), _card("c2", 0.90), _card("c3", 0.65)], _NOW)
    view = ranked_view(store, max_display=10)
    assert [c.score.company_id for c in view] == ["c2", "c3", "c1"]  # -p_score
    assert [c.rank for c in view] == [1, 2, 3]  # rank recomputado


def test_ranked_view_tie_break_estavel(tmp_path: Path) -> None:
    store = CorpusStore(tmp_path / "corpus.json")
    accumulate(store, [_card("cz", 0.5), _card("ca", 0.5)], _NOW)
    view = ranked_view(store, max_display=10)
    # Empate em p_score => tie-break por company_id (estável).
    assert [c.score.company_id for c in view] == ["ca", "cz"]


def test_max_display_limita_exibicao_nao_volume(tmp_path: Path) -> None:
    store = CorpusStore(tmp_path / "corpus.json")
    accumulate(store, [_card(f"c{i}", i / 10) for i in range(1, 6)], _NOW)
    view = ranked_view(store, max_display=2)
    assert len(view) == 2  # exibição limitada...
    assert len(store) == 5  # ...mas o corpus conhece os 5


def test_accumulate_and_rank_acumula_entre_runs(tmp_path: Path) -> None:
    # Helper único (CLI+UI): dois runs sucessivos crescem o corpus e a saída é a
    # visão ordenada por score, deduplicada por entity_id.
    path = tmp_path / "corpus.json"
    out1 = accumulate_and_rank(CorpusStore(path), [_card("c1", 0.4)], _NOW, max_display=10)
    assert [c.score.company_id for c in out1] == ["c1"]
    out2 = accumulate_and_rank(
        CorpusStore(path), [_card("c2", 0.9), _card("c1", 0.4)], _LATER, max_display=10
    )
    assert [c.score.company_id for c in out2] == ["c2", "c1"]  # cresceu, ordenado por score
    assert [c.rank for c in out2] == [1, 2]
    assert len(CorpusStore(path)) == 2  # c1 não duplicou
