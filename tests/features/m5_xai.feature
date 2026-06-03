@M5
Feature: M5 Explicacao (XAI) — payload auditavel por prospect
  O M5 traduz score + inferencia em drivers positivos/negativos e sinais ausentes.

  Scenario: Gera payload com drivers e sinais ausentes
    Given um score aprovado e uma inferencia com dados parciais
    When eu gero a explicacao
    Then o payload tem company_id e final_p_score
    And ha ao menos um driver positivo
    And os sinais ausentes sao listados

  Scenario: Hard filter aparece como driver negativo
    Given um score reprovado no hard filter
    When eu gero a explicacao
    Then ha um driver negativo de tecnologia proibida

  Scenario: Modo degradado e carimbado
    Given um score aprovado e uma inferencia com dados parciais
    When eu gero a explicacao em modo degradado
    Then o payload marca degraded_mode verdadeiro
