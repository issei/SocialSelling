@objetivo @pipeline
Feature: Objetivo de negocio — quem deve aparecer no topo (publico Talita)
  Valida que o ranking honra a estrategia: founder estruturada com sinal de timing
  no topo; founder solo desqualificada zerada; fora-de-setor abaixo.

  Scenario: Mayara lidera; solo desqualificada e zerada
    Given os arquetipos de prospect da Talita
    When eu pontuo com o ICP e as hipoteses da Talita e ranqueio
    Then a Mayara (founder com timing) aparece em primeiro
    And o lead solo desqualificado tem p_score zero e hard filter reprovado
    And o lead com sinal de intencao supera o de fit puro
    And o lead fora de setor fica abaixo da Mayara
