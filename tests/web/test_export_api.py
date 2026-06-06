"""Testes do endpoint GET /api/run/{run_id}/export.csv (sem scoring).

Cenários:
  Feliz      — run com 2 leads retorna 200, CSV com BOM, header PT-BR, 2 linhas de dados,
               sem colunas de score.
  Edge       — run inexistente retorna 404.
  Open-World — lead com campos opcionais ausentes (None) não quebra a linha.
"""

from __future__ import annotations

import csv
import io

from fastapi.testclient import TestClient

from socialselling.contracts import (
    LeadCard,
    LeadContact,
    LeadLinks,
    ProspectScore,
)
from socialselling.web.app import create_app
from socialselling.web.services import leads_to_csv

_SCORE = ProspectScore(company_id="c1", fit=0.8, intent=0.5, confidence=0.9, p_score=0.7)


def _card(
    rank: int = 1,
    name: str = "Maria Silva",
    company: str = "Acme",
    instagram: str | None = "https://instagram.com/maria",
    email: str | None = "maria@acme.com",
    phone: str | None = "+5511999990000",
    sources: list[str] | None = None,
) -> LeadCard:
    return LeadCard(
        rank=rank,
        display_name=name,
        company=company,
        role="Fundadora",
        sector="consultoria",
        location="São Paulo, SP",
        links=LeadLinks(instagram=instagram, linkedin=None, website="https://acme.com.br"),
        contact=LeadContact(email=email, phone=phone),
        score=_SCORE,
        why_now=["timing: expansão"],
        sources=sources if sources is not None else ["https://instagram.com/maria"],
    )


def _run_with_cards(cards: list[LeadCard]) -> tuple[TestClient, str]:
    """Cria app injetando o runner e executa POST /api/run; retorna (client, run_id)."""
    client = TestClient(create_app(pipeline_runner=lambda _: cards))
    resp = client.post("/api/run", json={"icp_name": "icp_criteria.talita.json"})
    run_id: str = resp.json()["run_id"]
    return client, run_id


# ---------------------------------------------------------------------------
# Feliz: 2 leads → 200, CSV correto, sem score
# ---------------------------------------------------------------------------

def test_export_status_200_com_dois_leads() -> None:
    client, run_id = _run_with_cards([_card(rank=1), _card(rank=2, name="João Sauro")])
    resp = client.get(f"/api/run/{run_id}/export.csv")
    assert resp.status_code == 200


def test_export_content_type_csv() -> None:
    client, run_id = _run_with_cards([_card()])
    resp = client.get(f"/api/run/{run_id}/export.csv")
    assert "text/csv" in resp.headers["content-type"]


def test_export_content_disposition() -> None:
    client, run_id = _run_with_cards([_card()])
    resp = client.get(f"/api/run/{run_id}/export.csv")
    assert "attachment" in resp.headers["content-disposition"]
    assert "leads.csv" in resp.headers["content-disposition"]


def test_export_inicia_com_bom_utf8() -> None:
    client, run_id = _run_with_cards([_card()])
    content = client.get(f"/api/run/{run_id}/export.csv").content
    assert content[:3] == b"\xef\xbb\xbf", "CSV deve iniciar com BOM UTF-8"


def test_export_header_pt_br() -> None:
    client, run_id = _run_with_cards([_card()])
    text = client.get(f"/api/run/{run_id}/export.csv").text
    # Remover BOM antes de parsear
    text = text.lstrip("﻿")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    header = next(reader)
    assert header == [
        "Nome", "Empresa", "Cargo", "Setor", "Localizacao",
        "Instagram", "LinkedIn", "Website", "E-mail", "Telefone", "Fontes",
    ]


def test_export_duas_linhas_de_dados() -> None:
    client, run_id = _run_with_cards([_card(rank=1), _card(rank=2, name="João Sauro")])
    text = client.get(f"/api/run/{run_id}/export.csv").text.lstrip("﻿")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    assert len(rows) == 3, "header + 2 linhas de dados"


def test_export_sem_colunas_de_score() -> None:
    client, run_id = _run_with_cards([_card()])
    text = client.get(f"/api/run/{run_id}/export.csv").text
    for forbidden in ("p_score", "fit", "intent", "confidence", "rank", "company_id"):
        assert forbidden not in text, f"campo proibido no CSV: {forbidden}"


def test_export_dados_corretos() -> None:
    card = _card(
        name="Maria Silva",
        company="Acme",
        instagram="https://instagram.com/maria",
        email="maria@acme.com",
        sources=["src1", "src2"],
    )
    client, run_id = _run_with_cards([card])
    text = client.get(f"/api/run/{run_id}/export.csv").text.lstrip("﻿")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    next(reader)  # skip header
    row = next(reader)
    assert row[0] == "Maria Silva"
    assert row[1] == "Acme"
    assert row[8] == "maria@acme.com"
    assert row[10] == "src1 | src2"


# ---------------------------------------------------------------------------
# Edge: run inexistente → 404
# ---------------------------------------------------------------------------

def test_export_run_inexistente_404() -> None:
    client = TestClient(create_app(pipeline_runner=lambda _: []))
    resp = client.get("/api/run/run-inexistente/export.csv")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Open-World: campos opcionais ausentes → linha íntegra
# ---------------------------------------------------------------------------

def test_export_lead_sem_opcionais_nao_quebra() -> None:
    card = LeadCard(
        rank=1,
        display_name="Minimal Lead",
        company=None,
        role=None,
        sector=None,
        location=None,
        links=LeadLinks(),
        contact=LeadContact(),
        score=_SCORE,
        sources=[],
    )
    client, run_id = _run_with_cards([card])
    resp = client.get(f"/api/run/{run_id}/export.csv")
    assert resp.status_code == 200
    text = resp.text.lstrip("﻿")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    next(reader)  # header
    row = next(reader)
    assert len(row) == 11, "linha deve ter exatamente 11 colunas mesmo com Nones"
    assert row[0] == "Minimal Lead"
    # campos opcionais ficam vazios, não None
    for i in range(1, 11):
        assert row[i] != "None", f"coluna {i} não deve conter a string 'None'"


# ---------------------------------------------------------------------------
# Teste unitário da função pura leads_to_csv
# ---------------------------------------------------------------------------

def test_leads_to_csv_puro_determinístico() -> None:
    cards = [_card(rank=1), _card(rank=2, name="João")]
    result1 = leads_to_csv(cards)
    result2 = leads_to_csv(cards)
    assert result1 == result2, "leads_to_csv deve ser determinístico"
    assert result1.startswith("﻿"), "deve iniciar com BOM"
    lines = result1.lstrip("﻿").splitlines()
    assert len(lines) == 3  # header + 2 data rows
