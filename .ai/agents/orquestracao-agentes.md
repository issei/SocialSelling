# Orquestração Multiagente — Desenvolvimento com Claude Code

> **Distinção fundamental (não confundir):**
> - **Módulos de runtime (M1–M5):** funções determinísticas do pipeline. **NÃO** são agentes autônomos. Ver CLAUDE.md §3.
> - **Agentes de desenvolvimento:** subagents do Claude Code que *constroem* o sistema. É deste documento que tratamos.

## Princípio
Orquestração **enxuta**. Para um PoC, a maior parte do trabalho é uma sessão única rodando o SDD-to-Code Loop módulo a módulo. Subagents entram para **fan-out paralelizável** (revisão independente, módulos sem dependência) — não para inflar um "enxame".

## Papéis (charters enxutos)

| Agente | Responsabilidade | Ferramentas típicas | Modo |
|---|---|---|---|
| **Architect** | Guarda do SDD e dos contratos; escreve/atualiza ADRs; valida fronteiras de módulo. Read-mostly. | Read, Grep, Glob | Consultivo, antes de cada fase |
| **Spec/QA** | Escreve `.feature` Gherkin + grava fixtures **antes** da implementação (spec-first). | Write (tests/), Read | Início de cada módulo |
| **Backend** | Implementa o mínimo para passar o BDD do módulo. | Edit, Write (src/), Bash | Núcleo do ciclo |
| **Reviewer** | Roda `/code-review`; checa contra SDD e guardrails; busca simplificação. | Read, Bash, /code-review | Antes do commit |

## Padrão de execução por módulo (pipeline, não big-bang)
```
[Architect: confirma contrato]
   → [Spec/QA: .feature + fixtures gravadas]
      → [Backend: implementa até BDD verde]
         → [gate: pytest-bdd + ruff + mypy --strict]
            → [Reviewer: /code-review + checklist CLAUDE.md §9]
               → commit em branch do módulo
```

## Quando usar subagents vs. sessão única
- **Sessão única (default):** um módulo por vez, ciclo completo. Menor custo, contexto coeso.
- **Subagent paralelo:** apenas para trabalho independente — ex.: Reviewer auditando M1 enquanto Backend implementa M4 (M4 não depende de M1 em runtime, só de scores). Use `Agent` com charter explícito.
- **Não** paralelizar módulos com dependência de dados (M2 depende de M1, M3 de M2).

## Gates de qualidade (inegociáveis)
1. BDD 100% verde e **determinístico** (flakiness = falha).
2. `ruff` + `mypy --strict` limpos.
3. Checklist de revisão (CLAUDE.md §9) cumprido.
4. Nenhum guardrail anti-overengineering (CLAUDE.md §5) violado.

## Governança de commits
- Branch por módulo (`feat/m1-busca`, `feat/m2-extracao`, …).
- Commit só após gate verde. Mensagem referencia o módulo e os cenários BDD cobertos.
- ADRs para qualquer decisão que mude a fronteira arquitetural definida na ADR-000.
