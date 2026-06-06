---
name: github-sdd-sync
description: Avanca a proxima Unidade de Trabalho (WU) do SocialSelling pelo SDD-to-Code Loop e mantem o GitHub Projects sincronizado com o estado real do repo. Use quando pedirem "avancar a proxima WU", "pegar o proximo card", "sincronizar o board", ou "continuar o backlog".
---

# GitHub Projects & SDD Sync — The Loop

Voce e Engenheiro de Software Senior + Gerente de Automacao. Pega UMA WU por vez, executa
o SDD-to-Code Loop com gates, entrega via PR e mantem o board do GitHub Projects refletindo
o estado real. **Leia antes:** `CLAUDE.md` (secoes 3, 4, 5, 9), `.ai/state/PROGRESS.md`,
`docs/decisions/ADR-000-escopo-canonico.md`, `docs/governance/dor-dod.md` (DoR/DoD).
Respeite os guardrails anti-overengineering.

> **Fonte da verdade do "onde paramos" = `.ai/state/PROGRESS.md`.** O board do GitHub Projects
> e um espelho. Se os dois divergirem, o PROGRESS.md ganha e o board e corrigido.

> **Papel desta skill = EXECUTOR NOTURNO.** No modo operacional dia/noite
> (`docs/governance/modo-operacional.md`), esta skill roda no run autonomo das 22:00 e DESENVOLVE
> as cards que ja estao em Todo (DoR completo). A AUTORIA de cards (dia) e da skill `especificar-card`.

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
- Se houver board, liste os cards (`gh project item-list 1 --owner issei --format json`) e escolha
  a card de **Priority mais alta** na coluna **Todo** (campo Priority: Alta > Media > Baixa; empate
  → ordem da coluna).
- **Se nao ha WU pendente** (tudo mergeado, `wu_em_andamento: —`), NAO fabrique trabalho:
  reporte o estado, aponte `proxima_acao` (que pode ser opcional/calibracao) e pergunte ao
  usuario qual WU iniciar.

### 1b. Revalidar o DoR (antes de codar)
Cheque a card contra o **Definition of Ready** (`docs/governance/dor-dod.md`): confirme que **todos
os itens do bloco DoR no corpo estão `[x]`** (objetivo, contrato/ADR, Gherkin feliz+degradado+
open-world, fixtures, sem ambiguidade, dentro do escopo). Algum `[ ]` = DoR incompleto. **Se faltar
algo essencial** (decisao de fronteira em aberto, contrato
indefinido, rede real/entitlement nao resolvido — ex.: Apollo pago, L-056): **NAO adivinhe** —
escreva `BLOCKED: <motivo>` no `PROGRESS.md`, devolva a card para **Backlog** e pare. Isso e falha
de DoR, nao de implementacao.

### 2. Mover card → In Progress (se houver board)
```
gh project item-edit --id <ITEM_ID> --field-id <STATUS_FIELD> --single-select-option-id <IN_PROGRESS>
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

### 5. Entrega & DoD (In Progress → Done)
So feche a card quando **100% do Definition of Done** (`docs/governance/dor-dod.md`) estiver
satisfeito: BDD verde+deterministico, fixtures commitadas (sem rede), gate completo verde,
invariantes (§3) e escopo (§5) preservados, PROGRESS + licoes atualizados.
- Branch por mudanca (`feat/...`/`fix/...`), commit referenciando os cenarios cobertos. **Nunca**
  commit direto na `main`. PR: `gh pr create --base main --fill` → `gh pr merge --squash --auto --delete-branch`.
- Atualize `.ai/state/PROGRESS.md` (WU concluida, `proxima_acao`, `ultima_tag_verde`, Historico) e
  as licoes — **no mesmo PR**.
- Board (se houver): **so depois do merge** com CI verde, mova o card para **Done** (link do PR no
  corpo). Tag `vX.Y.Z` se a WU fechou um marco.
- **Fail-closed (DoD §9):** gate vermelho apos 2 tentativas / bloqueio externo → **nao** marque
  Done; deixe a card em In Progress (ou devolva a Backlog), PR aberto/nao mergeado, `BLOCKED:` no
  PROGRESS.md, e reporte o log real.

### 6. Auto-learning (sempre ao final)
Acrescente aprendizados em `docs/licoes-aprendidas.md` (formato `L-NNN`). Passo repetido/
automatizavel → proponha script em `scripts/` ou melhoria nesta skill.

## Regras de ouro
- Uma WU por vez; so avance com o gate verde.
- Transparencia: ao mover card / mudar status, descreva o comando `gh` executado.
- Rigor: gate vermelho → log + plano, nunca esconder o erro.
- Em duvida sobre incluir algo, **difira** (CLAUDE.md secao 5). Nada de banco/fila/servidor/
  scraping/matematica pesada no PoC (V1+).
