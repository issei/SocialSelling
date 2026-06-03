@M3
Feature: M3 Score — scores deterministicos de prospect
  O M3 aplica a formula linear do PoC sobre inferencias, de forma pura e deterministica.

  Scenario: Score deterministico e dentro de [0,1]
    Given um ICP e inferencias sinteticas
    When eu calculo o score duas vezes
    Then cada p_score esta entre 0 e 1
    And as duas execucoes sao identicas com tolerancia 1e-9

  Scenario: Tecnologia proibida zera o lead
    Given uma inferencia com tecnologia proibida pelo ICP
    When eu calculo o score uma vez
    Then o lead tem hard_filter_passed falso e p_score zero

  Scenario: Maior confianca nao reduz o p_score
    Given duas inferencias identicas exceto a confianca
    When eu calculo o score uma vez
    Then o prospect de maior confianca tem p_score maior ou igual
