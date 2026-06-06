# Guia de Contribuição - SocialSelling

Obrigado por seu interesse em contribuir com o SocialSelling! Como um projeto proprietário de código disponível (source-available), temos processos rigorosos para garantir a qualidade e a segurança do código.

## Fluxo de Desenvolvimento: SDD-to-Code Loop

Adotamos a metodologia **SDD-to-Code Loop** (Schema Driven Development). O ciclo de vida de qualquer implementação deve seguir estes passos:

1.  **Contrato (Pydantic):** Defina as estruturas de dados e interfaces usando modelos Pydantic em `src/schemas/` (ou local pertinente).
2.  **Cenários BDD:** Escreva cenários Gherkin em arquivos `.feature` dentro de `tests/features/`.
3.  **Fixtures:** Desenvolva as fixtures e mocks necessários em `tests/fixtures/` para garantir isolamento total (100% de mock de rede).
4.  **Implementação Mínima:** Implemente o código necessário para satisfazer os contratos e passar nos testes.
5.  **Quality Gate:** Execute o conjunto de testes e analisadores estáticos locais.

## Portões de Qualidade (Quality Gates)

### DoR (Definition of Ready)
Uma tarefa só pode ser iniciada se:
*   Tiver um objetivo claro e bem documentado.
*   O contrato de entrada/saída estiver fechado.
*   Os cenários Gherkin (Feliz, Degradado e Open-World) estiverem definidos.

### DoD (Definition of Done)
Uma tarefa só é considerada concluída se:
*   Todos os cenários BDD estiverem passando (verde).
*   Houver 100% de mock de chamadas externas (rede).
*   Os analisadores estáticos passarem sem erros: `ruff` e `mypy --strict`.
*   O Quality Gate local passar integralmente.
*   O PR for realizado via branch específica e aprovado.

## Como rodar o Quality Gate localmente

Antes de enviar qualquer contribuição, você **deve** rodar o Quality Gate e garantir que tudo esteja verde.

*   **Windows:**
    ```powershell
    .\scripts\gate.ps1
    ```
*   **Linux/WSL:**
    ```bash
    ./scripts/gate.sh
    ```

## Padrões de Nomenclatura e Commits

### Branches
Use prefixos claros para suas branches:
*   `feat/nome-da-feature`
*   `fix/descricao-do-bug`
*   `docs/melhoria-na-documentacao`
*   `refactor/ajuste-de-codigo`

### Conventional Commits
Seguimos o padrão de [Conventional Commits](https://www.conventionalcommits.org/):
*   `feat:` para novas funcionalidades.
*   `fix:` para correções de bugs.
*   `docs:` para mudanças em documentação.
*   `style:` para mudanças que não afetam o significado do código (espaços, formatação).
*   `refactor:` para mudanças no código que não corrigem bugs nem adicionam funcionalidades.

## Submissão de Pull Requests

Ao abrir um PR, certifique-se de preencher o template de Pull Request fornecido, garantindo que todos os itens do checklist foram cumpridos.
