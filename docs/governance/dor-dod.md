# Definition of Ready (DoR) & Definition of Done (DoD)

> **Para quem:** qualquer LLM/pessoa que **cria especificações e tarefas** (cards) ou que as
> **desenvolve** no SocialSelling. É o contrato de qualidade entre as duas pontas: a LLM que
> versiona specs e o run autônomo que implementa (skill `github-sdd-sync`).
>
> **Fonte da verdade do estado:** `.ai/state/PROGRESS.md`. O **GitHub Project #1** é o espelho.
> **Fonte da verdade arquitetural:** ADR-000 + SDD v1.0. Este doc **não** os substitui — só define
> quando uma card pode mudar de coluna.

## Mapa: colunas do board ↔ portões de qualidade

```
Backlog ──[ DoR ]──► Todo ──(aprovação humana)──► (run pega) In Progress ──[ DoD ]──► Done
```

- **Backlog → Todo:** a card precisa satisfazer **100% do DoR**. Mover para Todo = "aprovo o
  desenvolvimento autônomo disto". **Só humano move Backlog→Todo** (o run nunca se auto-aprova).
- **WIP de especificação — just-in-time (Revisão de Processo #001/P3):** o **Todo mantém no máximo
  ~5 cards** com DoR 100%; o restante fica no **Backlog como título de 1 linha** (sem DoR
  detalhado). O DoR completo só é preenchido quando a card entra na janela de execução (Todo com
  <3 cards → sessão de dia repõe a partir do Backlog — *puxado*, não empurrado). Motivo: DoR
  antecipado é investimento perecível — em 2026-06 um lote de 27+ cards AWS totalmente
  especificados foi suspenso por pivô (ADR-010) dois dias depois.
- **Todo → In Progress:** o run autônomo pega a card de maior prioridade. **Antes de codar**, ele
  **revalida o DoR**; se algo essencial faltar (ambiguidade, contrato indefinido, fixture/rede não
  resolvida), ele **não adivinha** — marca `BLOCKED:` no `PROGRESS.md`, devolve a card para Backlog
  e para. Isso é uma falha de DoR, não de implementação.
- **In Progress → Done:** só com **100% do DoD**. Sem isso, a card permanece em In Progress
  (bloqueada) e o PR não é mergeado (*fail-closed*).

---

## Definition of Ready (DoR) — a card pode ir para Todo?

Uma card só está **Ready** quando **todos** os itens abaixo são verdadeiros. Em caso de dúvida,
ela fica em Backlog (incompleta) — nunca empurrar ambiguidade para o run.

1. **Objetivo observável (1 frase).** O "porquê" + o resultado que se poderá verificar. Deve servir
   à visão do produto ("Quem devo abordar primeiro?"). Nada de objetivo vago.
2. **Fatiada em 1 WU.** Cabe em 1–2 passos / uma janela de execução e termina num *checkpoint
   seguro* (árvore nunca quebrada). Se for grande, **quebrar em várias cards** antes de aprovar.
3. **Contrato definido.** Entrada/saída expressas em termos de `src/socialselling/contracts.py` /
   `docs/contratos/`. Se a card **altera contrato cruzando fronteira de módulo**, precisa de uma
   **ADR vinculada** (criada/aprovada) **antes** de virar Ready.
4. **Critérios de aceitação em Gherkin (esboço).** Pelo menos: **1 caminho feliz** + **1 modo
   degradado** (ex.: 429/timeout) + **1 cenário Open-World** (sinal ausente → incerteza, nunca
   falso). Estes viram os `.feature` em `tests/features/`.
5. **Fixtures identificadas.** Quais respostas de API (Tavily/Gemini/Apollo) precisam estar
   **gravadas** para os testes. Se a card depende de **rede real ainda não gravada** ou de
   **entitlement pago** (ex.: Apollo master API, L-056) → isso é **dependência/bloqueio**: a card
   **não** vira Ready até a fixture existir ou o dono destravar.
6. **Sem decisão de fronteira em aberto.** Nenhuma escolha de design que obrigaria o run a
   "adivinhar". Se existe, resolva na spec (ou abra ADR) antes.
7. **Dentro do escopo canônico.** Respeita ADR-000, os **guardrails anti-overengineering**
   (CLAUDE.md §5) e as **regras invioláveis** (CLAUDE.md §3). Sem infra fora de escopo (banco,
   fila, servidor, scraping, math pesada).
8. **Determinismo viável.** É possível testar sem flakiness (tolerância numérica `1e-9`; APIs
   mockadas). Se a saída é intrinsecamente não-determinística, redesenhar a card.
9. **DoD específico declarado.** A card lista, no corpo, **como se saberá que terminou** (ver
   template). O DoD genérico abaixo se aplica sempre; este é o acréscimo específico da card.

## Definition of Done (DoD) — a card pode ir para Done?

A card só vira **Done** quando **todos** os itens abaixo são verdadeiros. Qualquer falha = **não é
Done** (card fica em In Progress, PR não mergeia).

1. **Cenários BDD verdes e determinísticos.** Os `.feature` do escopo passam 100% e a reexecução é
   **byte-idêntica** (zero tolerância a não-determinismo).
2. **Fixtures gravadas e commitadas; testes não tocam a rede.** Toda chamada externa mockada.
3. **Quality gate completo verde:** `ruff` + `mypy --strict` + `pytest` (rodar via `.venv` —
   `./scripts/gate.ps1`/`.sh`). Asserções numéricas com `abs(a-b) <= 1e-9`.
4. **Invariantes respeitadas.** Camadas semânticas isoladas (Observed ≠ Inferences ≠ Hypotheses);
   toda inferência com `confidence`; persistência atômica (write-temp + `os.replace`) quando houver.
5. **Escopo preservado.** Não viola regras invioláveis (§3) nem guardrails (§5); nenhuma dependência
   de infra fora da ADR-000; implementou **o mínimo** da fatia (sem abstração especulativa).
6. **Integrado via PR com CI verde.** Branch → `gh pr create --base main --fill` →
   `gh pr merge --squash --auto --delete-branch`. **Nunca** commit/push direto na `main`; **nunca**
   `--force`.
7. **Estado atualizado.** `.ai/state/PROGRESS.md` (histórico, próxima ação, tag se aplicável) e
   `docs/licoes-aprendidas.md` (lição `L-NNN`, quando houver aprendizado) atualizados — no mesmo PR.
8. **Card fechada corretamente.** Movida para **Done** com o link do PR no corpo; tag `vX.Y.Z` na
   `main` se a WU fechou um marco.
9. **Fail-closed.** Se não foi possível concluir (gate vermelho após 2 tentativas, bloqueio
   externo, ambiguidade): **não marcar Done** — registrar `BLOCKED:` no `PROGRESS.md`, deixar a card
   em In Progress (ou devolver a Backlog) e o PR **aberto/não mergeado**. Reportar o log real.

---

## Template de card (corpo que a LLM autora deve escrever)

Copie este corpo ao criar a card (`gh project item-create ... --body`). Campos vazios = card
**não Ready**.

```md
## Objetivo
<1 frase: o porquê + resultado observável>

## Contrato (entrada → saída)
<refs a contracts.py / docs/contratos/; ADR vinculada se cruza fronteira de módulo>

## Critérios de aceitação (Gherkin)
- Feliz:      Dado <…> Quando <…> Então <…>
- Degradado:  Dado <429/timeout/…> Quando <…> Então <degrada, não quebra>
- Open-World: Dado <sinal ausente> Quando <…> Então <incerteza ↑, missing evidence explícito>

## Fixtures necessárias
<endpoints/arquivos a gravar em tests/fixtures/ — ou "nenhuma (módulo puro)">

## Fora de escopo
<o que NÃO fazer nesta card>

## Dependências / bloqueios
<ADRs, WUs anteriores, plano pago, fixtures pendentes — ou "nenhum">

## DoD específico
<como saber que ESTA card terminou, além do DoD genérico>

## Tamanho
<1–2 passos? cabe numa janela? se não, quebrar>

## DoR (checklist — marque [x]; só vai para Todo com TODOS [x])
- [ ] Objetivo observável em 1 frase
- [ ] Cabe em 1 WU (1–2 passos / uma janela)
- [ ] Contrato entrada→saída definido (ADR vinculada se cruza fronteira de módulo)
- [ ] Gherkin: feliz + degradado + Open-World
- [ ] Fixtures identificadas (ou "módulo puro"); sem bloqueio de rede-paga/entitlement
- [ ] Sem decisão de fronteira em aberto
- [ ] Dentro do escopo canônico (§3/§5/ADR-000) e determinístico (1e-9, APIs mockadas)
- [ ] DoD específico declarado acima
```

> **Bloco DoR checável:** o corpo de cada card inclui o checklist acima. **Quem move Backlog→Todo
> marca os `[x]`**; o **run noturno revalida** que estão **todos `[x]`** antes de codar — se algum
> estiver `[ ]`, é DoR incompleto → `BLOCKED`, devolve a Backlog (não adivinha). O `scripts/new_card.ps1`
> já gera o card com este bloco.

## Prioridade (campo do board)
O board tem um campo **Priority** (`Alta`/`Media`/`Baixa`). O run noturno pega a card de **Priority
mais alta** em Todo (empate → ordem da coluna). Defina a prioridade ao mover para Todo.

## Checklist rápido (para revisão antes de mover)

**Mover Backlog → Todo (DoR):** objetivo claro ✓ · 1 WU ✓ · contrato/ADR ✓ · Gherkin (feliz+
degradado+open-world) ✓ · fixtures identificadas / sem bloqueio de rede-paga ✓ · sem ambiguidade ✓
· dentro do escopo (§3/§5/ADR-000) ✓ · determinístico ✓ · DoD específico declarado ✓

**Mover In Progress → Done (DoD):** BDD verde+determinístico ✓ · fixtures commitadas, sem rede ✓ ·
`ruff`+`mypy --strict`+`pytest` verdes ✓ · invariantes ✓ · escopo preservado ✓ · PR com CI verde
(auto-merge squash) ✓ · PROGRESS + lições atualizados ✓ · card em Done + tag se marco ✓

## Relação com os outros documentos
- **Modo operacional (dia autoria / noite execução):** `docs/governance/modo-operacional.md` — quem
  cria card (dia) e quem desenvolve (noite); skill de autoria `especificar-card`.
- **Protocolo do run autônomo:** `docs/planning/autonomous-ops.md` §3 (passos S1..S6) e §4
  (guardrails). O DoD é o "verde" que aquele protocolo exige para mergear.
- **SDD-to-Code Loop:** CLAUDE.md §4 (contrato → Gherkin+fixtures → impl mínima → gate → PR).
- **Skill que consome cards:** `.claude/skills/github-sdd-sync/SKILL.md` (revalida DoR ao pegar,
  exige DoD ao fechar).
- **Escopo/guardrails:** CLAUDE.md §3 e §5; ADR-000.
