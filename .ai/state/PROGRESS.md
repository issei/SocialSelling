# PROGRESS — Âncora de Estado (resume autônomo)

> Fonte da verdade do "onde paramos". Todo run autônomo LÊ no início e ATUALIZA no fim.
> Contrato de campos em docs/planning/autonomous-ops.md §2.

## Estado atual
- **marco_atual:** Fundação concluída (Fase 0)
- **ultima_tag_verde:** `v0.1.0`
- **wu_em_andamento:** — (nenhuma iniciada)
- **passo_atual:** — (próxima WU = WU-1 / S1)
- **branch:** `main`
- **proxima_acao:** Iniciar WU-1 (M1 Busca). S1 = revisar contrato `ObservedEvidence`; depois S2 = escrever `tests/features/m1_busca.feature` + gravar fixtures Tavily. Pré-requisito: rodar `bootstrap` e ter o gate verde no baseline.
- **bloqueios:** NENHUM

## Pré-condições antes de liberar autonomia plena
- [ ] `./scripts/bootstrap.ps1` executado (venv + deps) e `./scripts/gate.ps1` verde.
- [ ] CI verde no GitHub.
- [ ] Fixtures Tavily/Gemini gravadas com supervisão (WU-1/WU-2 tocam rede).
- [ ] Estratégia de agendamento ativada (autonomous-ops §7).

## Histórico
| Data | Run | Resultado | Tag/Checkpoint |
|---|---|---|---|
| 2026-06-02 | Fase 0 (fundação) | toolchain + contratos + planejamento | `v0.1.0` |
