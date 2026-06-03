# Estratégia de Versionamento & Rollback

Objetivo: que qualquer quebra de fluxo seja recuperável de forma **segura, consistente e auditável**. Git é o mecanismo de rollback; este doc define as regras.

## 1. Modelo de branches (trunk-based via Pull Request)
- **`main`** — trunk sempre verde e **protegida**: **nunca** recebe commit/push direto. Toda mudança entra por **Pull Request** com CI verde.
- **`feat/m<n>-<nome>`** — branch curta por módulo/WU. Vive horas/dias, não semanas.
- **`fix/<descricao>`** / **`docs/<descricao>`** / **`chore/<descricao>`** — demais tipos de branch.
- Branches partem sempre da **última tag verde** ou da `main` atualizada (ponto de restauração conhecido).

### Fluxo padrão (obrigatório a partir de agora)
```
git checkout -b <tipo>/<nome> [<tag-verde>]   # nova branch
# ... trabalho + checkpoints ...
./scripts/gate.ps1                            # gate local verde
git push -u origin <tipo>/<nome>
gh pr create --base main --fill               # PR automatico
gh pr merge --squash --auto --delete-branch   # auto-merge quando o CI passar
# apos merge na main, se a WU fechou:
git checkout main && git pull
git tag -a vX.Y.0 -m "..." && git push origin vX.Y.0
```
- **Merge:** `--squash` (1 commit limpo por WU na main) + `--auto` (só funde com CI verde) + `--delete-branch`.
- **Sem CI verde, não funde.** A branch fica aberta até o gate passar.

## 2. Convenção de commits (Conventional Commits)
`<tipo>(<escopo>): <descrição>` — tipos: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `ci`.
- **Checkpoint (resume):** `wip(m1): cliente tavily parcial — passos S3 incompletos`. Permitido vermelho. Só em feature branch.
- **Estável (merge):** `feat(m1): busca tavily com cache e degradacao`. Sempre verde.
- Rodapé obrigatório: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## 3. Versionamento semântico (tags)
Mapa de marcos em [execution-plan §1](execution-plan.md). Regras:
- **Minor** (`0.x.0`) = um módulo concluído e verde na main.
- **Patch** (`0.x.y`) = correção sobre um marco já tag-eado.
- **`v1.0.0`** reservado para o PoC promovido a MVP estável (pós-smoke endurecido).
- Tags **anotadas** (`git tag -a`), com mensagem do que entrega e o que valida. Toda tag é testada (gate verde) antes de criada.

## 4. Distinção crítica: checkpoint vs. ponto de restauração
| | Checkpoint | Ponto de restauração (tag) |
|---|---|---|
| Onde | feature branch | main |
| Estado | pode ser vermelho/WIP | sempre verde |
| Propósito | resume de autonomia | rollback seguro |
| Comando | `git commit -m "wip:..."` | `git tag -a vX` |

## 5. Playbook de rollback (cenários e comandos exatos)

**A) Commit ruim na feature branch (ainda não na main, não pushado)**
```
git reset --hard HEAD~1        # descarta o último commit local
# ou voltar a um checkpoint específico:
git reset --hard <sha_checkpoint>
```

**B) Merge ruim já na main (já pushado) — NUNCA reescrever história pública**
```
git revert -m 1 <sha_do_merge> # cria commit que desfaz, preserva histórico
git push origin main
```

**C) Inspecionar/validar uma versão antiga sem mexer na atual**
```
git worktree add ../ss-v0.2.0 v0.2.0   # checa a tag em pasta isolada
# ... inspeciona ... depois:
git worktree remove ../ss-v0.2.0
```

**D) Refazer um módulo do zero a partir do último marco verde**
```
git checkout -b feat/m2-extracao-v2 v0.2.0   # parte do ponto seguro
```

**E) Hotfix sobre um marco**
```
git checkout -b fix/m1-cache v0.2.0
# ... corrige + gate verde ...
git checkout main && git merge --no-ff fix/m1-cache
git tag -a v0.2.1 -m "fix: cache tavily"
```

## 6. Regras invioláveis de versionamento
1. `main` só muda via **PR com CI verde** — nunca commit/push direto, nunca push vermelho.
2. Nunca `git push --force` em `main` nem em tags.
3. Toda tag corresponde a um estado com gate verde reproduzível.
4. Rollback de algo público = `revert` (via PR), nunca `reset`.
5. Em dúvida, **não destrua**: crie branch/worktree a partir da tag e investigue.

## 7. Backup / durabilidade
- `origin` (GitHub) é a cópia durável; push de main e tags após cada marco.
- Tags replicadas no remoto = pontos de restauração sobrevivem a perda da máquina local.
