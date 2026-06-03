@M4
Feature: M4 Ranking — ordenacao deterministica de prospects
  O M4 ordena os scores por p_score desc com tie-break estavel.

  Scenario: Ordena por p_score desc com tie-break estavel e byte-identico
    Given scores de prospect com empate
    When eu ordeno duas vezes
    Then a ordem e por p_score decrescente
    And empates sao resolvidos por company_id ascendente
    And as duas execucoes sao byte-identicas
