# ADR-011 — O processo de desenvolvimento agêntico é produto de referência

| Campo | Valor |
|---|---|
| Status | **Aprovado** |
| Data | 2026-06-09 |
| Decisores | Dono do produto + Staff Engineer/Arquiteto |
| Complementa | **ADR-010** (pivô motor local + portal da operadora) |
| Formaliza | `docs/planning/autonomous-ops.md`, `docs/governance/modo-operacional.md`, `docs/governance/dor-dod.md` (eleva de prática a decisão arquitetural) |

## Contexto

Este projeto desenvolveu, na prática, um **processo de desenvolvimento autônomo** que já está
validado por evidência, não por promessa:

- **Runs noturnos autônomos** (skill `github-sdd-sync`, rotina das 22:00) entregaram WUs completas
  com gate verde e auto-merge — o histórico do `.ai/state/PROGRESS.md` registra dezenas de entregas
  de `v0.1.0` a `v0.18.3` sem nunca quebrar a `main`.
- **Board como espelho do estado** (GitHub Project #1) com portões DoR/DoD por coluna
  (`docs/governance/dor-dod.md`) e separação dia-autoria/noite-execução
  (`docs/governance/modo-operacional.md`).
- **Quality gate determinístico** (`ruff` + `mypy --strict` + `pytest` 100% offline, tolerância
  `1e-9`) como critério único e inegociável de "verde".
- **Fan-out de subagentes em paralelo** (fundação ledgers+corpus, PR #35, tag `v0.14.0`): 3 agentes
  escreveram módulos independentes em worktrees isoladas; o loop principal colheu, gateou e mergeou.
  As lições L-039/L-040/L-041 documentam o padrão que funcionou ("agentes escrevem, main loop
  valida") e suas armadilhas.

A restrição real que molda tudo: o desenvolvimento roda em **Claude Code com licença Pro**, cujo
uso é limitado por **janelas (~5h rolantes) + teto semanal** (`autonomous-ops.md` §1). A cota é o
recurso escasso do projeto. **Cada token gasto sem agregar ao objetivo é desperdício** — e, com
orçamento limitado, desperdício não é estética: é WU que deixa de ser entregue.

O dono ratificou o desejo de que este projeto seja **referência do novo processo de
desenvolvimento autônomo**: SDD-to-Code + BDD + DevOps + auto-learning, executados por agentes. O
SocialSelling entrega dois produtos: o ranking de prospects **e o próprio processo que o constrói**.

> **Princípio desta ADR:** o processo agêntico é produto de referência. Desperdício operacional
> que não agrega ao objetivo é **defeito** — trata-se com a mesma seriedade de um gate vermelho.

## Decisão

### 1. Política de modelos por classe de tarefa

O run (ou o orquestrador interativo) escolhe o **menor modelo que satisfaz o DoD da tarefa**. Na
dúvida **em tarefa de risco, sobe** de modelo — nunca o contrário. Formaliza a linha "Modelos:" do
plano de orquestração do `PROGRESS.md`.

| Classe de tarefa | Modelo | Exemplos |
|---|---|---|
| Orquestração do run; decisões de arquitetura; WUs de **risco/integração** (cruzam fronteira de módulo, tocam contrato, wiring no orquestrador) | **Topo (Opus/Fable)** | Loop principal do run noturno; autoria de ADR; ledgers; integração motor↔portal |
| Implementação de **módulo isolado com spec fechada** (contrato + Gherkin + fixtures prontos, DoR 100%) | **Sonnet** | Módulo puro do pipeline; DAO com contract tests definidos; endpoint com contrato fixo |
| Tarefas **mecânicas** sem decisão de design | **Haiku** | Sync de board, formatação, scaffolds, renomeações, mover cards |

### 2. Paralelização por subagentes (padrão "harvest")

- WUs **sem dependência entre si no grafo do backlog-plan** podem ser desenvolvidas por
  **subagentes em paralelo**, cada um em **worktree isolada**.
- Os subagentes **escrevem**; o **loop principal colhe, roda o gate e integra** — precedente da
  fundação ledgers+corpus e lições L-039..L-041 (agentes em background travam em prompt de
  permissão; worktree não tem `.venv`; diagnóstico pelo filesystem da worktree).
- **Limite:** paralelizar só quando o ganho supera o custo de coordenação (colheita + gate + merge).
  Para 1–2 WUs pequenas, serial é mais barato.
- **Integração/merge é sempre serializada pelo loop principal** — nunca dois agentes mergeando
  concorrentemente.

### 3. Anti-desperdício (lista verificável)

Cada item abaixo é checável num run; violação recorrente é defeito de processo e vira lição L-NNN:

1. **`PROGRESS.md` enxuto** — é âncora de resume, não diário. Estado atual + próxima ação +
   1 linha de histórico por run; detalhe vive no git/PRs.
2. **Proibido reler specs legadas** (`specs/` herdadas, ~22k linhas). A fonte canônica está em
   `CLAUDE.md`, ADRs e SDDs ativas — reler o legado queima janela sem agregar.
3. **Fail-fast em limite de uso:** ao esbarrar no teto da janela/semana, registrar `BLOCKED` no
   `PROGRESS.md` e **parar** num checkpoint seguro — não insistir nem degradar a qualidade.
4. **Fixtures gravadas + gate offline:** zero custo de API em teste; rede real só em gravação
   supervisionada de fixtures.
5. **Uma WU bem terminada por run > duas pela metade.** Checkpoint seguro sempre; árvore nunca
   quebrada ao fim da janela.
6. **Sem retrabalho cosmético fora do escopo do card** — formatação, renomeação e refactor
   "de passagem" não entram no diff; se valem a pena, viram card.

### 4. Segurança, confiabilidade e integridade em cada passo

Nenhuma economia de cota justifica afrouxar estes pontos:

- **Gate determinístico inegociável** — `ruff` + `mypy --strict` + `pytest` verdes, byte-idêntico,
  antes de qualquer merge.
- **PR-only:** `main` protegida, CI como required check, auto-merge squash. Nunca commit/push
  direto, nunca `--force`.
- **Fail-closed** (DoD §9): não concluiu = não marca Done; `BLOCKED` explícito, PR aberto.
- **Segredos fora do repo:** só em `.env` local e nos painéis dos provedores (Render, Neon,
  GitHub) — nunca commitados, nunca em log.
- **Diffs revisáveis:** squash com mensagem rastreável ao card; o dono revisa os merges da noite
  pela manhã.
- **Menor privilégio nas integrações:** GitHub App do Render restrita ao repo; tokens com escopo
  mínimo necessário.

### 5. Medição (mínimo viável, sem plataforma nova)

- Cada run noturno registra na **linha do histórico do `PROGRESS.md`**: duração aproximada e se
  houve **desperdício notável** (retrabalho, bloqueio tardio, releitura inútil).
- **Lições `L-NNN`** em `docs/licoes-aprendidas.md` continuam sendo o mecanismo de melhoria
  contínua do processo.
- **Revisão mensal** do processo pelo dono (lê histórico + lições e ajusta política de modelos,
  pacing e paralelização).

## Escopo (o que esta ADR não autoriza)

- **Nenhuma plataforma de observabilidade/telemetria paga** — a medição é a linha do PROGRESS +
  lições, ponto.
- **Nenhuma automação que mute infra sem gate** — provisioning e deploy seguem os fluxos gateados
  (e a ADR-009, se a pegada AWS voltar).
- **Não substitui DoR/DoD** — esta ADR governa *como* o trabalho é executado; os portões de
  qualidade das cards continuam em `docs/governance/dor-dod.md`.

## Consequências

**Positivas:** a cota Pro rende mais WUs entregues por semana (modelo certo por tarefa + zero
releitura inútil + paralelismo seletivo); o processo fica auditável (PROGRESS + lições + diffs
rastreáveis) e replicável como referência em outros projetos; segurança e integridade deixam de
depender de disciplina implícita — viram decisão registrada.

**Trade-offs:** escolher modelo por tarefa adiciona um passo de julgamento ao run (mitigado pela
regra "na dúvida em risco, sobe"); fail-fast em limite de uso significa noites que terminam com
menos entregue — aceito, pois meia-WU quebrada custa mais caro que uma noite curta; a medição
minimalista (linha no PROGRESS) não gera métricas finas de custo por WU — suficiente para o
estágio atual, revisitável se a revisão mensal mostrar pontos cegos.
