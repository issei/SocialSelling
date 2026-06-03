# PROGRESS — Âncora de Estado (resume autônomo)

> Fonte da verdade do "onde paramos". Todo run autônomo LÊ no início e ATUALIZA no fim.
> Contrato de campos em docs/planning/autonomous-ops.md §2.

## Estado atual
- **marco_atual:** 🎯 Motor de intenção COMPLETO (público Talita) — ICP+hipóteses; M2 extrai sinais; M3 intent das hipóteses + hard filter; M5 explica; BDD de objetivo. `v0.8.0`
- **ultima_tag_verde:** `v0.8.0`
- **wu_em_andamento:** — (motor de intenção entregue em 4 fatias: PRs #12,#13,#14,#15)
- **passo_atual:** — (`main` verde em e0f0109, 21 testes)
- **branch:** `main`
- **proxima_acao:** Backlog (NÃO iniciar sem o dono). PRIORIDADE = aderência da BUSCA ao público Talita:
  1. **Sondagem empírica** (recomendado): rodar M1/M2 ao vivo com `icp_criteria.talita.json` e ver o que o Tavily acha de founders de serviços — decidir antes de codar (ver ADR-001 / L-024).
  2. Adaptar `generate_queries` (M1) para PT-BR orientado a founder/dor (hoje é tech/inglês).
  3. Calibrar priors das hipóteses e pesos do score com dados reais.
  4. Resolução de entidades: filtrar fornecedores (legado do ICP cloud).
- **bloqueios:** NENHUM (motor honra timing/desqualificadores; busca ainda afinada p/ tech — evolução, não correção)

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
| 2026-06-03 | Motor de intenção (público Talita) | ICP+hipóteses (#12); M2 extrai sinais (#13); M3 intent das hipóteses + hard filter (#14); M5 XAI + BDD de objetivo (#15) | `v0.7.1`→`v0.8.0` |
