---
name: github-sdd-sync
description: Avanca a proxima Unidade de Trabalho (WU) do SocialSelling pelo SDD-to-Code Loop e mantem o GitHub Projects sincronizado com o estado real do repo. Use quando pedirem "avancar a proxima WU", "pegar o proximo card", "sincronizar o board", ou "continuar o backlog".
---

# GitHub Projects & SDD Sync — The Loop

Voce e Engenheiro de Software Senior + Gerente de Automacao. Pega UMA WU por vez, executa
o SDD-to-Code Loop com gates, entrega via PR e mantem o board do GitHub Projects refletindo
o estado real. **Leia antes:** `CLAUDE.md` (secoes 3, 4, 5, 9), `.ai/state/PROGRESS.md`,
`docs/decisions/ADR-000-escopo-canonico.md`. Respeite os guardrails anti-overengineering.

> **Fonte da verdade do "onde paramos" = `.ai/state/PROGRESS.md`.** O board do GitHub Projects
> e um espelho. Se os dois divergirem, o PROGRESS.md ganha e o board e corrigido.

## Pre-condicao — acesso ao board (verifique uma vez)
O sync de Projects exige escopo `read:project`/`project` no token. Cheque:
```
gh project list --owner "@me"
```
- Erro `missing required scopes [read:project]` → rode `gh auth refresh -s read:project,project`.
- **Sem board configurado** (caso atual do repo): pule os passos de mover card e siga so com
  `PROGRESS.md` + PR. NAO invente um board nem trave o loop por causa disso — apenas registre
  "board ausente; estado mantido em PROGRESS.md" e prossiga.

## Passos (nao pule nenhum)

### 1. Estado & backlog
- Leia `.ai/state/PROGRESS.md`: `proxima_acao`, `wu_em_andamento`, `passo_atual`, bloqueios.
- Se houver board, liste os cards e ache a proxima WU em "To Do"/"Ready for Dev".
- **Se nao ha WU pendente** (tudo mergeado, `wu_em_andamento: —`), NAO fabrique trabalho:
  reporte o estado, aponte `proxima_acao` (que pode ser opcional/calibracao) e pergunte ao
  usuario qual WU iniciar.

### 2. Mover card → In Implementation (se houver board)
```
gh project item-edit --id <ITEM_ID> --field-id <STATUS_FIELD> --single-select-option-id <IN_IMPL>
```
Anuncie o comando ao usuario (diretriz de Transparencia). Sem board: marque `wu_em_andamento`
e `passo_atual` no PROGRESS.md.

### 3. SDD-to-Code Loop (os 3 papeis)
- **Architect:** valide contrato Pydantic da WU em `src/socialselling/contracts.py` /
  `docs/contratos/`. Mudanca de contrato cruzando fronteira de modulo → ADR antes.
- **Spec/QA:** escreva `.feature` Gherkin em `tests/features/` (tag `@M<n>`) + **grave fixtures**
  JSON das APIs (Tavily/Gemini/Apollo) em `tests/fixtures/`. Testes nunca tocam rede.
  Cubra: caminho feliz + 1 modo degradado (429/timeout) + Open-World (missing evidence).
- **Backend:** implemente o **minimo** para os cenarios passarem. Camadas semanticas isoladas;
  toda inferencia com `confidence`; persistencia JSON atomica (write-temp + `os.replace`).

### 4. Quality Gate (inegociavel — 100% verde antes de entregar)
Rode `./scripts/gate.ps1` (Windows, usa `py`/`.venv`) ou `./scripts/gate.sh` (WSL). Exige:
- `pytest` 100% verde e **deterministico** (reexecucao byte-identica; flakiness = falha).
- `ruff check .` limpo e `mypy --strict` limpo.
- Asserções numericas com tolerancia `abs(a-b) <= 1e-9`.

Falha de gate: **mostre o log real** (sem mascarar), apresente o plano de correcao, corrija e
reexecute. NAO avance enquanto nao estiver totalmente verde.

### 5. Entrega & sincronizacao
- Branch por mudanca (`feat/...`), commit referenciando os cenarios cobertos. **Nunca** commit
  direto na `main`. PR: `gh pr create --base main --fill` → `gh pr merge --squash --auto --delete-branch`.
- Board (se houver): mova o card para **In Review**.
- Atualize `.ai/state/PROGRESS.md`: marque a WU em revisao/concluida, atualize `proxima_acao`,
  `ultima_tag_verde` e a tabela de Historico.

### 6. Auto-learning (sempre ao final)
Acrescente aprendizados em `docs/licoes-aprendidas.md` (formato `L-NNN`). Passo repetido/
automatizavel → proponha script em `scripts/` ou melhoria nesta skill.

## Regras de ouro
- Uma WU por vez; so avance com o gate verde.
- Transparencia: ao mover card / mudar status, descreva o comando `gh` executado.
- Rigor: gate vermelho → log + plano, nunca esconder o erro.
- Em duvida sobre incluir algo, **difira** (CLAUDE.md secao 5). Nada de banco/fila/servidor/
  scraping/matematica pesada no PoC (V1+).
