# PROGRESS — Âncora de Estado (resume autônomo)

> Fonte da verdade do "onde paramos". Todo run autônomo LÊ no início e ATUALIZA no fim.
> Contrato de campos em docs/planning/autonomous-ops.md §2.

## Estado atual
- **marco_atual:** WU-2 (M2 Extração) implementado e verde no gate; merge/tag `v0.3.0` em andamento
- **ultima_tag_verde:** `v0.2.0` (→ `v0.3.0` após merge do M2)
- **wu_em_andamento:** WU-2 concluindo (PR aberto)
- **passo_atual:** WU-2 / S6 (PR → auto-merge → tag)
- **branch:** `feat/m2-extracao`
- **proxima_acao:** Iniciar WU-3 (M3 Score). Módulo PURO (sem rede) — fórmula linear de `runtime.toml` sobre `Inference` → `ProspectScore`. Fixtures = JSON sintético (sem API). Bom candidato a janela autônoma curta.
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
