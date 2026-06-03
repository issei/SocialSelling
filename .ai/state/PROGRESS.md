# PROGRESS — Âncora de Estado (resume autônomo)

> Fonte da verdade do "onde paramos". Todo run autônomo LÊ no início e ATUALIZA no fim.
> Contrato de campos em docs/planning/autonomous-ops.md §2.

## Estado atual
- **marco_atual:** Fundação + planejamento concluídos; `main` CI-verde e protegida
- **ultima_tag_verde:** `v0.1.1` (primeiro baseline verificado pelo CI)
- **wu_em_andamento:** — (nenhuma iniciada)
- **passo_atual:** — (próxima WU = WU-1 / S1)
- **branch:** `main`
- **proxima_acao:** Iniciar WU-1 (M1 Busca). S1 = revisar contrato `ObservedEvidence`; depois S2 = escrever `tests/features/m1_busca.feature` + gravar fixtures Tavily. Pré-requisito: rodar `bootstrap` e ter o gate verde no baseline.
- **bloqueios:** NENHUM

## Pré-condições antes de liberar autonomia plena
- [x] `bootstrap` executado (venv + deps) e gate completo verde (ruff+mypy+pytest).
- [x] CI verde no GitHub; `main` protegida (merge exige check `gate`).
- [ ] Fixtures Tavily/Gemini gravadas com supervisão (WU-1/WU-2 tocam rede).
- [ ] Estratégia de agendamento ativada (autonomous-ops §7).

## Histórico
| Data | Run | Resultado | Tag/Checkpoint |
|---|---|---|---|
| 2026-06-02 | Fase 0 (fundação) | toolchain + contratos + planejamento | `v0.1.0` (pré-CI) |
| 2026-06-03 | Planejamento + fluxo PR | PR #1 (docs), PR #2 (fix StrEnum), CI verde, branch protection | `v0.1.1` |
