# Modo operacional — dia (autoria) vs noite (execução)

> **Princípio:** separar a **autoria de especificação** (interativa, de dia, barata em tokens) da
> **execução de implementação** (autônoma, de noite). Otimiza a cota do Claude Code Pro — o dono usa
> o dia para pensar/evoluir o sistema; o desenvolvimento roda no run agendado das 22:00.
>
> **Para quem:** qualquer LLM/sessão que receba uma instrução para **editar ou evoluir o sistema**.

## Regra padrão

- **De dia (sessão interativa):** a sessão **especifica e gera cards** — **não desenvolve o
  produto**. Enforça o DoR (`docs/governance/dor-dod.md`) **interrogando e cobrando** o dono pelo
  que falta, e só move o card para **Todo** quando o DoR está **100%**.
- **De noite (run autônomo `socialselling-daily-autodev`):** consome a coluna **Todo** e implementa
  via skill `github-sdd-sync` (SDD-to-Code Loop + gate + auto-merge), aplicando o DoD.

## Fronteira: o que vira card (noite) vs o que faço no dia (interativo)

| Vira **card** (noite) | Faço no **dia** (interativo) |
|---|---|
| **Código de produto:** implementação em `src/socialselling/`, `tests/`, fixtures — tudo que muda o comportamento do produto | Specs, ADRs, contratos (autoria), documentação, **tooling** (scripts, CI, skills), governança/processo, e a **curadoria do board** (criar/editar cards, mover Backlog↔Todo) |

## Exceções (posso desenvolver no dia)

1. **Pedido explícito** do dono ("faça agora", "implemente isto"). O override sempre vence.
2. **Hotfix:** `main` quebrada ou bug crítico — corrijo na hora (via PR, gate verde), e registro
   depois.

Fora desses dois casos, implementação de produto = **card/noite**.

## Fluxo de uma sessão de autoria (dia)

1. **Entender** o que o dono quer evoluir (e o porquê).
2. **Rascunhar** a(s) card(s) usando o **template** de `docs/governance/dor-dod.md`.
3. **Cobrar o DoR:** para cada item faltante (objetivo observável? contrato/ADR? Gherkin
   feliz+degradado+open-world? fixtures? ambiguidade de fronteira? dentro do escopo?), **perguntar
   ao dono** até completar. **Nunca** empurrar card incompleta para Todo.
4. Card com **DoR 100%** → criar no board e mover para **Todo** (anunciando o comando `gh`).
5. Se a evolução for grande, **quebrar em várias cards pequenas** (1 WU cada; cabe numa janela).
   **WIP de especificação (just-in-time):** detalhar DoR só das **~5 primeiras** (limite do Todo);
   o resto entra no Backlog como **título de 1 linha** e só ganha DoR quando for puxado
   (ver `dor-dod.md` §Mapa). Não especificar roadmaps inteiros de uma vez.
6. **Auto-learning + melhoria de processo:** registrar lições e, quando houver oportunidade de
   deixar o processo mais inteligente (template, DoR, automação, board), **propor/perguntar** ao
   dono.

## Auto-learning evolutivo (sempre)

Ao fim de cada sessão, registrar aprendizados em `docs/licoes-aprendidas.md` (formato `L-NNN`).
Sempre que enxergar uma oportunidade de tornar este processo mais inteligente, **perguntar ou
confirmar** com o dono em vez de assumir.

## Relação com outros documentos

- **DoR/DoD e template de card:** `docs/governance/dor-dod.md`.
- **Protocolo do run noturno:** `docs/planning/autonomous-ops.md` §3/§4; skill `github-sdd-sync`.
- **Skill de autoria (dia):** `especificar-card`.
- **Board (IDs) e schedule:** `scripts/setup_github_project.ps1`; rotina `socialselling-daily-autodev`.
- **Escopo/guardrails:** CLAUDE.md §3 e §5; ADR-000.
