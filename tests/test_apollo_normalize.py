"""Testes de normalização Apollo (WU-A3): parse cru -> hit -> canônico Tavily.

Determinístico, sem rede. Garante: contato mascarado por padrão, firmografia em ordem
fixa no `content`, e formato canônico compatível com `m1_busca._map_result`.
"""

from __future__ import annotations

from typing import Any

from socialselling.apollo.normalize import (
    parse_people_search,
    parse_person,
    person_hit_to_canonical,
    to_canonical_results,
)

# Amostra de resposta crua de People Search (subset realista, sem rede).
_RAW: dict[str, Any] = {
    "people": [
        {
            "id": "5f1",
            "first_name": "Talita",
            "last_name": "Souza",
            "title": "Founder",
            "seniority": "founder",
            "linkedin_url": "https://linkedin.com/in/talita",
            "email": "email_not_unlocked@domain.com",
            "email_status": "locked",
            "city": "São Paulo",
            "organization": {
                "name": "Acme Consultoria",
                "primary_domain": "acme.com.br",
                "industry": "consultoria",
                "estimated_num_employees": 12,
            },
        }
    ]
}


def test_parse_people_search_extrai_hit() -> None:
    hits = parse_people_search(_RAW)
    assert len(hits) == 1
    hit = hits[0]
    assert hit.apollo_id == "5f1"
    assert hit.name == "Talita Souza"
    assert hit.organization_name == "Acme Consultoria"
    assert hit.organization_domain == "acme.com.br"
    assert hit.employee_count == 12


def test_email_mascarado_por_padrao() -> None:
    # Marcador email_not_unlocked => mascarado (Open-World: contato não revelado).
    hit = parse_people_search(_RAW)[0]
    assert hit.email_masked is True


def test_parse_payload_vazio_retorna_lista_vazia() -> None:
    assert parse_people_search({}) == []
    assert parse_people_search({"people": None}) == []


def test_parse_person_defensivo_sem_organizacao() -> None:
    hit = parse_person({"id": "x", "first_name": "Ana"})
    assert hit.name == "Ana"
    assert hit.organization_name is None
    assert hit.employee_count is None
    assert hit.email_masked is True  # sem e-mail => mascarado


def test_canonico_tem_formato_tavily_e_ordem_fixa() -> None:
    hit = parse_people_search(_RAW)[0]
    canonical = person_hit_to_canonical(hit)
    # Mesmo formato do Tavily para o M1 mapear sem alteração.
    assert set(canonical.keys()) == {"title", "url", "content", "score"}
    assert canonical["score"] == 0.9
    assert canonical["url"] == "https://acme.com.br"
    # Ordem FIXA dos campos no content (determinismo).
    assert canonical["content"] == (
        "empresa: Acme Consultoria | setor: consultoria | "
        "funcionarios: 12 | cargo: Founder | local: São Paulo"
    )


def test_to_canonical_results_envelopa_em_results() -> None:
    hits = parse_people_search(_RAW)
    payload = to_canonical_results(hits)
    assert "results" in payload
    assert len(payload["results"]) == 1
    assert payload["results"][0]["title"].startswith("Talita Souza")


def test_normalizacao_deterministica() -> None:
    # Mesma entrada -> saída byte-idêntica (regra §3.2).
    a = to_canonical_results(parse_people_search(_RAW))
    b = to_canonical_results(parse_people_search(_RAW))
    assert a == b
