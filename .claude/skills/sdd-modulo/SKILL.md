---
name: sdd-modulo
description: Implementa um modulo do pipeline SocialSelling (M1..M5) seguindo o SDD-to-Code Loop com gates de teste. Use quando for desenvolver/avancar um modulo do PoC, p.ex. "implementar M1", "comecar o modulo de extracao", "avancar o pipeline".
---

# SDD-to-Code Loop para um modulo (M1..M5)

Orquestra a implementacao de UM modulo por vez, com validacao constante. Leia antes:
`CLAUDE.md`, `docs/decisions/ADR-000-escopo-canonico.md`, `docs/planning/roadmap-poc.md`,
`docs/contratos/README.md`. Respeite os guardrails anti-overengineering (CLAUDE.md secao 5).

## Passos (nao pule nenhum)

1. **Contexto & contrato (papel: Architect).**
   - Confirme entrada/saida do modulo em `docs/contratos/README.md` e `src/socialselling/contracts.py`.
   - Se o contrato precisar mudar e cruzar fronteira de modulo, abra uma ADR antes.

2. **Spec-first (papel: Spec/QA).**
   - Escreva o(s) `.feature` Gherkin em `tests/features/` com tag `@M<n>`.
   - **Grave as fixtures** das APIs (Tavily/Gemini) em `tests/fixtures/` como JSON. Testes nunca chamam rede real.
   - Cubra: caminho feliz + ao menos um modo degradado (429/timeout) + Open-World (missing evidence).

3. **Implementacao minima (papel: Backend).**
   - Implemente em `src/socialselling/modules/m<n>_*.py` apenas o necessario para passar os cenarios.
   - Use os tipos de `contracts.py`. Camadas semanticas isoladas; toda inferencia com `confidence`.
   - Persistencia (se houver): JSON atomico (write-temp + `os.replace`).

4. **Gate (inegociavel).**
   - Rode `./scripts/gate.ps1` (Windows; usa `py`) ou `./scripts/gate.sh` (WSL).
   - Exigencia: `pytest-bdd` 100% verde e **deterministico** (reexecucao byte-identica), `ruff` e `mypy --strict` limpos.
   - Asserções numericas com tolerancia `abs(a-b) <= 1e-9`. Flakiness = falha.

5. **Review & commit (papel: Reviewer).**
   - Rode `/code-review`. Cheque o checklist de CLAUDE.md secao 9 e os guardrails (secao 5).
   - Commit em branch do modulo (`feat/m<n>-<nome>`), mensagem referenciando os cenarios cobertos.

6. **Auto-learning (sempre ao final).**
   - Acrescente aprendizados em `docs/licoes-aprendidas.md` (formato `L-NNN`).
   - Se um passo se repetiu/automatizavel, proponha script em `scripts/` ou melhoria nesta skill.

## Regras de ouro
- Um modulo por vez; so avance com o gate verde (DAG: M1 -> M2 -> M3 -> M4 -> M5 -> smoke).
- Em duvida sobre incluir algo, **difira** (walking skeleton).
- Nada de banco, fila, servidor, scraping ou matematica pesada no PoC (sao V1+).
