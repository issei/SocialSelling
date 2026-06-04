@M3
Feature: M3 Score — scores deterministicos guiados por fit, intencao e desqualificadores
  O M3 aplica a formula linear do PoC sobre inferencias, de forma pura e deterministica.
  Intencao vem das hipoteses que disparam; desqualificador zera o lead.

  Scenario: Score deterministico e dentro de [0,1]
    Given um ICP e inferencias sinteticas
    When eu calculo o score duas vezes
    Then cada p_score esta entre 0 e 1
    And as duas execucoes sao identicas com tolerancia 1e-9

  Scenario: Tecnologia proibida zera o lead
    Given uma inferencia com tecnologia proibida pelo ICP
    When eu calculo o score uma vez
    Then o lead tem hard_filter_passed falso e p_score zero

  Scenario: Desqualificador detectado zera o lead
    Given uma inferencia com desqualificador detectado
    When eu calculo o score uma vez
    Then o lead tem hard_filter_passed falso e p_score zero

  Scenario: Sinal de intencao aumenta o p_score
    Given duas inferencias identicas exceto o sinal de intencao
    When eu calculo o score uma vez
    Then o prospect com sinal de intencao tem p_score estritamente maior

  Scenario: Homem (persona fundador) e zerado
    Given uma inferencia de persona fundador
    When eu calculo o score uma vez
    Then o lead tem persona_fit zero e p_score zero

  Scenario: Conta de empresa e penalizada ante a fundadora
    Given uma fundadora e uma conta de empresa identicas no resto
    When eu calculo o score uma vez
    Then a fundadora tem p_score maior que a conta de empresa

  Scenario: Maior confianca nao reduz o p_score
    Given duas inferencias identicas exceto a confianca
    When eu calculo o score uma vez
    Then o prospect de maior confianca tem p_score maior ou igual
