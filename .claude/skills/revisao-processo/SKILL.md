---
name: revisao-processo
description: Revisão periódica da condução do processo de desenvolvimento (estrutura, processo, desempenho, custo) com relatório histórico e propostas viradas em cards. Use quando o dono pedir "revisar o processo", "avaliação de desempenho do desenvolvimento", "auditoria do processo", "como está a condução do projeto".
---

# Revisão de processo (agente revisor — dia)

Audita **como** o projeto está sendo desenvolvido (não **o que** foi desenvolvido): estrutura do
repo, processo operacional, desempenho/desperdício e custo de tokens. Produz um **relatório
numerado** na série `docs/analysis/process-reviews/` (histórico comparável entre revisões) e
converte propostas aceitas em **cards** (via skill `especificar-card`).

> Atividade de **dia** (análise/docs/processo — ver `docs/governance/modo-operacional.md`).
> **Não implementa nada**: o produto desta skill é o relatório + cards. Leitura: read-only.

## Passos

### 1. Coletar evidências (sempre as mesmas fontes, para comparabilidade)
- **Revisão anterior:** ler a última `docs/analysis/process-reviews/*.md` — as pendências da §6
  dela viram o primeiro checklist desta revisão (o que foi feito? surtiu efeito?).
- **KPIs:** commits na `main` (`git log --oneline | wc -l`), PRs (`gh pr list --state all`),
  última tag, nº de testes (saída do gate ou CI), tempo do gate, colunas do board
  (`gh project item-list 1 --owner issei`), nº de lições, nº de ADRs.
- **Estado:** `.ai/state/PROGRESS.md`, `git status`/`git branch -v` (lixo? branches gone?
  worktrees órfãs?), `docs/licoes-aprendidas.md` (numeração íntegra? lições aplicadas?).
- **Aderência:** CLAUDE.md vs realidade do código (guardrails ainda valem? contradições com ADRs
  recentes?); skills (`.claude/skills/`) vs prática real dos runs.

### 2. Avaliar em 4 dimensões
1. **Estrutura** — repo organizado conforme CLAUDE.md §6? Lixo acumulado? Docs canônicos íntegros?
2. **Processo** — o que funcionou (com evidência); fluxo PR/gate/board/PROGRESS respeitado?
   Degradação sob falha foi correta?
3. **Desempenho/desperdício** — retrabalho, conflitos evitáveis, trabalho especificado e não
   executado (specs queimadas por pivô), sessões gastas em diagnóstico de tooling.
4. **Custo (tokens/cota)** — cerimônia paga em LLM que poderia ser script? Leitura redundante de
   specs nos runs? Fan-out de agentes valeu? Modo dia/noite respeitado?

### 3. Escrever o relatório (histórico)
- Arquivo: `docs/analysis/process-reviews/AAAA-MM-DD-revisao-NNN.md` (NNN sequencial).
- Estrutura fixa (comparável): **Metadados** (período, gatilho, revisão anterior) → **Snapshot de
  KPIs** (tabela, mesmas métricas sempre) → **Estrutura: achados** → **Processo: o que funciona**
  → **Desempenho: desperdícios** (com evidência concreta: PRs, lições, datas) → **Propostas**
  (numeradas, com prioridade sugerida e encaminhamento) → **Pendências para a próxima revisão**
  (checklist verificável).
- Tom: factual, com números; cada desperdício apontado precisa de evidência (PR, lição, data).

### 4. Encaminhar
- Discutir as propostas com o dono; as aceitas viram **cards** via skill `especificar-card`
  (1 proposta = 1 card pequeno; processo/tooling/docs executam-se de dia, produto vai p/ noite).
- Relatório entra por **PR** (`docs/process-review-NNN` → auto-merge). Nunca commit direto na `main`.
- Atualizar `.ai/state/PROGRESS.md` apenas se a revisão mudar a próxima ação do projeto.
- Registrar lições novas em `docs/licoes-aprendidas.md` se a própria revisão revelou padrão novo.

## Cadência e regras
- **Cadência sugerida:** a cada marco (tag minor) ou ~1×/semana — o dono dispara; a skill não se
  auto-agenda.
- Comparar SEMPRE com a revisão anterior — uma revisão sem "o que mudou desde a última" é só um
  snapshot, não uma série.
- Propor pouco e priorizado (top-3 explícito). Propostas demais = nada executado.
- Não executar as melhorias dentro da revisão (salvo "faça agora" do dono) — especificar.
