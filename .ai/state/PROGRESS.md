# PROGRESS — Âncora de Estado (resume autônomo)

> Fonte da verdade do "onde paramos". Todo run autônomo LÊ no início e ATUALIZA no fim.
> Contrato de campos em docs/planning/autonomous-ops.md §2.

## Estado atual
- **marco_atual:** 🎉 PoC COMPLETO — orquestrador M1→M5 + CLI + smoke E2E; merge/tag `v0.7.0` em andamento
- **ultima_tag_verde:** `v0.6.0` (→ `v0.7.0` após merge do orquestrador)
- **wu_em_andamento:** WU-6 concluindo (PR aberto)
- **passo_atual:** WU-6 / S6 (PR → auto-merge → tag)
- **branch:** `feat/m6-orchestrator`
- **proxima_acao:** PoC entregue. Backlog de afinação/V1 (NÃO iniciar sem o dono):
  1. Resolução de entidades: filtrar fornecedores (ex.: "AWS" vazou como prospect #1) — lista de exclusão de vendors.
  2. Intent Worker real (hoje Intent é proxy por convergência de evidências).
  3. Persona/Buying Committee (M2 hoje raramente extrai pessoas das SERPs).
  4. Validar fórmula de score com dados reais; calibrar pesos.
- **bloqueios:** NENHUM (PoC funcional; itens acima são evolução, não correção)

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
| 2026-06-03 | WU-1 M1 Busca (autônomo) | cliente Tavily + cache atômico + degradação; BDD determinístico; fixtures reais gravadas | `v0.2.0` |
| 2026-06-03 | WU-2 M2 Extração (autônomo) | cliente Gemini + cache + degradação; 17 inferências reais; isolamento de camadas; BDD determinístico | `v0.3.0` |
| 2026-06-03 | WU-3 M3 Score (autônomo) | módulo puro; fórmula linear Fit/Intent/Confiança; hard filter; determinismo 1e-9 | `v0.4.0` |
| 2026-06-03 | WU-4 M4 Ranking (autônomo) | módulo puro; ordenação p_score desc + tie-break estável; byte-idêntico | `v0.5.0` |
| 2026-06-03 | WU-5 M5 XAI (autônomo) | módulo puro por regras; drivers +/− + sinais ausentes + degraded_mode | `v0.6.0` |
| 2026-06-03 | WU-6 Orquestrador + Smoke (autônomo) | pipeline M1→M5 + CLI + persistência atômica; smoke E2E byte-idêntico; run real = 17 prospects | `v0.7.0` |
