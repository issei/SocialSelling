@WUA
Feature: WU-A — DataProvenance: contrato de proveniência + metadados de hipóteses
  DataProvenance rastreia a fonte documental de cada Driver. Hypothesis ganha campos
  de apresentação (label, description_plain, impact_dimension, guide_tags) com defaults
  que preservam a leitura de JSON antigo sem esses campos.

  Scenario: Driver com DataProvenance rastreia URL da evidência original
    Given um Driver instanciado com uma DataProvenance de URL "https://ex.com"
    When o Driver é serializado via model_dump
    Then references[0].url é "https://ex.com"
    And references[0].source é "Tavily Search"

  Scenario: DataProvenance com url=None é válida (Open-World — ausência não é falso negativo)
    Given uma DataProvenance com url None e source "Análise Semântica Interna"
    When a DataProvenance é instanciada
    Then o objeto é válido com url None

  Scenario: JSON antigo de Hypothesis sem os campos novos carrega com defaults
    Given um dict de Hypothesis sem os campos label e guide_tags
    When HypothesisCatalog.model_validate é chamado com esses dados
    Then a hipótese carrega com label="" e guide_tags=[]
