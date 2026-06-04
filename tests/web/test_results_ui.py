"""Testes da UI de resultados (WU-UX1): tabela de leads + drawer de detalhes.

Front-end estático + render client-side; aqui validamos a PRESENÇA da estrutura e a
preservação dos contratos (FastAPI TestClient, sem rede). Ver SDD lead-results-table-ux.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from socialselling.web.app import create_app


def _body() -> str:
    text: str = TestClient(create_app()).get("/").text
    return text


def test_resultados_tem_tabela_e_drawer() -> None:
    body = _body()
    # Tabela de leads + corpo + estado-vazio.
    assert 'id="leadsTable"' in body
    assert 'id="leadsBody"' in body
    assert 'id="leadsEmpty"' in body
    # Drawer de detalhes (slide-over).
    assert 'id="leadDrawer"' in body
    assert 'role="dialog"' in body


def test_tabela_tem_colunas_e_ordenacao() -> None:
    body = _body()
    # Cabeçalhos ordenáveis declarados via data-sort.
    assert 'data-sort="display_name"' in body
    assert 'data-sort="p_score"' in body
    # Coluna de canais (links) e função de render presentes.
    assert "renderTable" in body
    assert "openDrawer" in body


def test_secoes_preservadas_nao_regride() -> None:
    # Invariante de não-regressão: as seções originais continuam (test_pages depende disso).
    body = _body()
    assert 'id="parametros"' in body
    assert 'id="assistente"' in body
    assert 'id="resultados"' in body
