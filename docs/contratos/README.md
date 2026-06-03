# Contratos de dados (I/O dos modulos M1..M5)

Definidos em [`src/socialselling/contracts.py`](../../src/socialselling/contracts.py) (Pydantic v2). Sao **apenas modelos de dados** — sem logica de negocio.

## Mapa modulo -> contrato

| Modulo | Entrada | Saida | Camada semantica |
|---|---|---|---|
| **M1 Busca** | `ICPCriteria` | `list[ObservedEvidence]` | 1 — Observed Evidence |
| **M2 Extracao** | `list[ObservedEvidence]` | `list[Inference]` | 2 — Generated Inferences |
| **M3 Score** | `list[Inference]` + catalogo | `list[ProspectScore]` | 3 — Evaluated Hypotheses |
| **M4 Ranking** | `list[ProspectScore]` | `list[RankedProspect]` (parcial) | 3 |
| **M5 XAI** | `ProspectScore` + `Inference` | `XAIPayload` | 3 |

## Regras invioláveis refletidas nos contratos
- **Isolamento de camadas:** `ObservedEvidence`, `Inference` e `ProspectScore`/`XAIPayload` sao tipos distintos; nunca se misturam.
- **Rastreabilidade:** `Inference.derived_from` guarda os `evidence_id` de origem (Evidence -> Inference).
- **Confianca obrigatoria:** nenhuma inferencia existe sem `confidence` (campo obrigatorio em `Inference`, `CompanyEntity`, `PersonEntity`).
- **Open-World:** `ObservedEvidence.missing_evidence` modela ausencia de sinal explicitamente.

## Como evoluir um contrato
Mudanca em contrato que cruze fronteira de modulo exige ADR (ver `docs/decisions/`). `extra="forbid"` garante que campos novos sejam intencionais, nao acidentais.
