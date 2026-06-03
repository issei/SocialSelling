@pipeline @smoke
Feature: Pipeline E2E deterministico em memoria
  O orquestrador encadeia M1..M5 e produz um ranking estavel e reproduzivel.

  Scenario: Execucao end-to-end produz ranking estavel e byte-identico
    Given um ICP de exemplo e fixtures gravadas
    When eu executo o orquestrador M1 ate M5 duas vezes
    Then sao produzidos prospects ranqueados
    And cada prospect tem rank crescente, score e explicacao
    And a segunda execucao e byte-identica a primeira
