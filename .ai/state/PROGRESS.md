# PROGRESS — Âncora de Estado (resume autônomo)

> Fonte da verdade do "onde paramos". Todo run autônomo LÊ no início e ATUALIZA no fim.
> Contrato de campos em docs/planning/autonomous-ops.md §2.

## Estado atual
- **marco_atual:** WU-3 (M3 Score) implementado e verde no gate; merge/tag `v0.4.0` em andamento
- **ultima_tag_verde:** `v0.3.0` (→ `v0.4.0` após merge do M3)
- **wu_em_andamento:** WU-3 concluindo (PR aberto)
- **passo_atual:** WU-3 / S6 (PR → auto-merge → tag)
- **branch:** `feat/m3-score`
- **proxima_acao:** Iniciar WU-4 (M4 Ranking). Módulo PURO — ordenar `list[ProspectScore]` por `p_score` com tie-break estável (ex.: `company_id`). Reexecução byte-idêntica.
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
| 2026-06-03 | WU-1 M1 Busca (autônomo) | cliente Tavily + cache atômico + degradação; BDD determinístico; fixtures reais gravadas | `v0.2.0` |
| 2026-06-03 | WU-2 M2 Extração (autônomo) | cliente Gemini + cache + degradação; 17 inferências reais; isolamento de camadas; BDD determinístico | `v0.3.0` |
| 2026-06-03 | WU-3 M3 Score (autônomo) | módulo puro; fórmula linear Fit/Intent/Confiança; hard filter; determinismo 1e-9 | `v0.4.0` |
