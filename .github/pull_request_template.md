## Descrição
<!-- Descreva brevemente as mudanças introduzidas por este PR -->

## Checklist do Autor
- [ ] O Quality Gate local passou 100% (`ruff` + `mypy --strict` + `pytest-bdd`)?
- [ ] Todas as chamadas externas estão mockadas usando fixtures em `tests/fixtures/`?
- [ ] O isolamento de camadas semânticas foi respeitado?
- [ ] O arquivo `.ai/state/PROGRESS.md` foi atualizado?
- [ ] As lições aprendidas foram descritas em `docs/licoes-aprendidas.md` (se houver aprendizado)?

## Checklist do Revisor
- [ ] O código segue o padrão SDD-to-Code Loop?
- [ ] A cobertura de testes BDD é adequada para os novos cenários?
- [ ] Não há vazamento de segredos ou chaves de API?
