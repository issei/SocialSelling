---
name: especificar-card
description: Especifica uma evolução do sistema como card(s) com DoR completo e move para Todo — SEM desenvolver. Use no dia para evoluir/editar o sistema SocialSelling, p.ex. "criar card", "especificar tarefa", "evoluir o sistema", "nova feature/ajuste", "preciso que o sistema faça X".
---

# Especificar & gerar card (modo autoria — dia)

Institucionaliza o **modo operacional dia/noite** (`docs/governance/modo-operacional.md`): de dia a
sessão **especifica e gera cards**, não desenvolve o produto. O desenvolvimento é delegado ao **run
noturno** (skill `github-sdd-sync`). **Leia antes:** `docs/governance/dor-dod.md` (DoR/DoD +
template), `CLAUDE.md` (§3 escopo, §4 loop, §5 guardrails), `.ai/state/PROGRESS.md`.

> **Regra de ouro:** NÃO implemente código de produto (`src/`, `tests/`, fixtures). Seu produto é
> **a card** — objetivo + contrato + Gherkin + fixtures + DoD específico — não o código.
> **Exceções** (aí sim pode codar): pedido explícito do dono ("faça agora") ou hotfix de `main`
> quebrada. Fora disso, especifique.

## Passos

### 1. Entender a evolução
Capte o que o dono quer mudar e o **porquê** (qual resultado observável; como serve a "Quem devo
abordar primeiro?"). Se for grande, planeje **quebrar em várias cards pequenas** (1 WU cada).

### 2. Rascunhar a card pelo template
Use o **template de card** do `dor-dod.md` (Objetivo / Contrato / Critérios Gherkin / Fixtures /
Fora de escopo / Dependências / DoD específico / Tamanho).

### 3. Cobrar o DoR (o coração desta skill)
Percorra os 9 itens do **Definition of Ready** e, **para cada item faltante, PERGUNTE ao dono** até
completar. Não preencha por suposição; não empurre card incompleta. Itens típicos a cobrar:
- Objetivo observável em 1 frase?
- Cabe em 1 WU (1–2 passos / uma janela)? Se não, quebrar.
- Contrato de entrada/saída definido (refs a `contracts.py`/`docs/contratos/`)? Cruza fronteira de
  módulo → **ADR vinculada** antes?
- Gherkin: **caminho feliz + degradado (429/timeout) + Open-World (missing evidence)**?
- Fixtures: quais respostas de API gravar? Depende de **rede real não-gravada** ou **plano pago**
  (ex.: Apollo, L-056)? → é **bloqueio**: não vira Ready até resolver.
- Alguma **decisão de fronteira em aberto**? (se sim, resolver/abrir ADR — não deixar o run adivinhar)
- Dentro do escopo canônico (§3/§5/ADR-000)? Determinismo viável (1e-9, APIs mockadas)?
- **DoD específico** declarado?

### 4. Criar o card e mover para Todo (só com DoR 100%)
Quando — e somente quando — todos os itens do DoR estiverem satisfeitos:
```
gh project item-create 1 --owner issei --title "<tipo>: <resultado>" --body "<corpo do template>"
gh project item-edit --id <ITEM_ID> --project-id PVT_kwHOAAi2gM4BZ3J3 \
  --field-id PVTSSF_lAHOAAi2gM4BZ3J3zhUy5Jg --single-select-option-id f75ad846   # Todo
```
(opções: Backlog=`6cf82daa` Todo=`f75ad846` In Progress=`47fc9ee4` Done=`98236657`.) Anuncie o
comando ao dono (Transparência). **Mover para Todo = aprovação do dono p/ desenvolvimento noturno**
— se o dono ainda não aprovou, deixe em **Backlog**.

### 5. Sincronizar e propor melhorias
- Atualize `.ai/state/PROGRESS.md` se a card representa um marco/próxima ação.
- **Auto-learning evolutivo:** registre lições em `docs/licoes-aprendidas.md` (`L-NNN`) e, sempre
  que houver oportunidade de deixar o processo mais inteligente (template, DoR, automação),
  **pergunte/proponha** ao dono.

## Regras de ouro
- Especifique, não implemente (salvo exceções acima).
- Card incompleta → Backlog + perguntas; nunca Todo.
- Uma card = uma WU pequena; quebre o que for grande.
- Em dúvida sobre escopo, **difira** (CLAUDE.md §5) e pergunte ao dono.
