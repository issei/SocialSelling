@M1
Feature: M1 Busca — coleta de evidencias observadas via Tavily
  O M1 transforma um ICP em queries, consulta a Tavily (com cache T-24h)
  e produz evidencias observadas de forma deterministica.

  Scenario: Busca feliz gera evidencias deterministicas e byte-identicas
    Given um ICP de exemplo
    And fixtures Tavily gravadas
    When eu executo o M1 duas vezes com relogio fixo
    Then sao geradas evidencias observadas
    And a segunda execucao e byte-identica a primeira

  Scenario: Rate limit sem cache marca missing evidence (Open-World)
    Given um ICP de exemplo
    And o cliente Tavily retorna 429
    When eu executo o M1 uma vez com relogio fixo
    Then ha ao menos uma evidencia com missing_evidence verdadeiro
    And o resultado esta em modo degradado
