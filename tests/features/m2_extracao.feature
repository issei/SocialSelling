@M2
Feature: M2 Extracao — inferencias a partir das evidencias via Gemini
  O M2 transforma evidencias observadas (camada 1) em inferencias (camada 2),
  com confianca e rastreabilidade, de forma deterministica.

  Scenario: Extracao feliz gera inferencias com confianca e rastreabilidade
    Given evidencias observadas do M1
    And fixtures Gemini gravadas
    When eu executo o M2 duas vezes com relogio fixo
    Then sao geradas inferencias
    And toda inferencia tem confianca e derived_from rastreavel
    And as camadas observed e inference estao isoladas
    And a segunda execucao e byte-identica a primeira

  Scenario: Rate limit sem cache nao produz inferencias (degradado)
    Given evidencias observadas do M1
    And o cliente Gemini retorna 429
    When eu executo o M2 uma vez com relogio fixo
    Then nenhuma inferencia e produzida
