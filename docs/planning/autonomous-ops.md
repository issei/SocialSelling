# Operação Autônoma — Estratégia para o Plano Pro

Como progredir o desenvolvimento de forma **autônoma na maior parte do tempo**, aproveitando janelas de madrugada, dentro das limitações de uso do Claude Code Pro — sem nunca comprometer a integridade do repositório.

## 1. Realidade do plano Pro (restrições de design)
- Uso é limitado por **janelas (sessão de ~5h rolantes) + teto semanal**. Loops autônomos consomem essa cota.
- Implicações de design:
  1. **Trabalho fatiado em WUs curtas** que sempre terminam num checkpoint seguro (nunca deixar a árvore num estado quebrado ao fim da janela).
  2. **Pacing de orçamento:** poucas WUs por noite; parar limpo antes de esgotar a janela. Tratar a cota como *error budget* (SRE) — gastar com parcimônia.
  3. **Resumível por design:** o estado vive no git + `PROGRESS.md`, não na memória da sessão. Qualquer run novo reconstrói o contexto lendo esses dois.
  4. **Madrugada > horário comercial:** sem contenção com uso interativo do dono; janela inteira disponível para o agente.

## 2. Âncora de resume: `.ai/state/PROGRESS.md`
Fonte da verdade do "onde paramos". O agente **lê no início** e **atualiza no fim** de todo run. Contrato de campos:
- `marco_atual` / `ultima_tag_verde` — ex.: `WU-2 / v0.2.0`.
- `wu_em_andamento` + `passo_atual` (S1..S6) + `branch`.
- `proxima_acao` — instrução literal do próximo passo.
- `bloqueios` — `NENHUM` ou `BLOCKED: <motivo + o que preciso do dono>`.
- `historico` — linha por run (data, o que fez, tag/checkpoint gerado).

## 3. Protocolo de um run autônomo
```
1. Ler .ai/state/PROGRESS.md e a WU atual em docs/planning/execution-plan.md
2. Se bloqueios != NENHUM → parar e reportar (não adivinhar)
3. git checkout/garantir branch da WU (a partir da última tag verde se nova)
4. Executar O PRÓXIMO PASSO (apenas 1–2 passos por run, conforme pacing)
5. Rodar ./scripts/gate.* :
     - verde  → commit (wip: ou estável) na feature branch ; se a WU fechou:
                `gh pr create --base main --fill` + `gh pr merge --squash --auto --delete-branch`
                (auto-merge só funde com CI verde); após o merge, tag vX.Y.0 na main
     - vermelho após N=2 tentativas → reverter ao último checkpoint verde, marcar BLOCKED
6. Atualizar PROGRESS.md (passo, próxima ação, histórico) — commitado na feature branch
7. Push da feature branch. Parar num checkpoint seguro. NUNCA push direto na main.
```

## 4. Guardrails de autonomia (inegociáveis)
- **Nunca** commit/push direto na `main`; integração só via **PR com CI verde** (auto-merge).
- **Nunca** `--force`; rollback público só via `revert` (em PR).
- **Nunca inventar especificação.** Ambiguidade ou decisão de fronteira → escrever `BLOCKED:` no PROGRESS.md e parar (deixar para o dono).
- **Sem fixtures gravadas, não implementar** módulos que tocam rede (M1/M2): gravar fixtures é etapa supervisionada (ver §6).
- Respeitar guardrails anti-overengineering (CLAUDE.md §5) e regras invioláveis (CLAUDE.md §3).
- Parar sempre num checkpoint; nunca terminar a janela no meio de um passo destrutivo.

## 5. Prompt permanente do agente agendado
Texto a usar na rotina (skill `schedule`/cron). É autocontido — não depende de contexto de conversa:
```
Você é o engenheiro autônomo do PoC SocialSelling. Leia CLAUDE.md,
docs/planning/execution-plan.md, docs/planning/versioning-strategy.md e
.ai/state/PROGRESS.md. Execute o protocolo de docs/planning/autonomous-ops.md §3:
avance 1–2 passos da WU atual, rode ./scripts/gate.ps1, versione (checkpoint na
feature branch; merge+tag na main só se a WU fechou e o gate estiver verde),
atualize PROGRESS.md e pare num checkpoint seguro. Respeite TODOS os guardrails
da §4 — em caso de bloqueio/ambiguidade, escreva BLOCKED no PROGRESS.md e pare
sem adivinhar. Nunca faça push vermelho na main nem --force.
```

## 6. Cadência recomendada
| Item | Recomendação |
|---|---|
| Janela | Madrugada BRT (ex.: 02:00) — sem contenção com uso interativo |
| Frequência | 1 run/noite no início; ajustar pelo consumo semanal |
| Escopo/run | 1–2 passos de uma WU (cabe na janela; termina em checkpoint) |
| Supervisão | WU-1/WU-2 (rede): gravar fixtures com o dono presente antes de liberar autonomia; WU-3/WU-4 (puros) são os mais seguros para rodar sozinhos |
| Revisão humana | Dono revisa os merges/tags da noite pela manhã; CI dá rede de segurança |

## 7. Como ativar o agendamento (a confirmar com o dono)
- Usar a skill **`schedule`** (rotina cron) com o prompt da §5, timezone `America/Sao_Paulo`, ex.: `0 2 * * *`.
- Alternativa interativa: skill **`/loop`** (auto-pace) numa sessão supervisionada.
- **Pré-requisitos honestos:** rotina consome a cota Pro; depende do agente conseguir rodar no horário (rotina em nuvem ou máquina ligada). A ativação fica para o "go" do dono.

## 8. Recuperação de falha noturna
- Gate falhou e não recuperou → estado fica no último checkpoint verde + `BLOCKED` no PROGRESS.md; nada quebrado entra na main.
- Pela manhã: ler `historico` e `bloqueios` no PROGRESS.md; decidir (corrigir, refazer a partir da tag, ou ajustar spec).
