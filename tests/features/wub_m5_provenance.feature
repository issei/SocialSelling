@WUB
Feature: WU-B — M5 propagação de proveniência (evidence_index → Driver.references)
  O módulo M5 recebe um evidence_index e popula Driver.references do INTENT_TIMING
  com DataProvenance rastreável a cada URL de evidência. Quando o índice está vazio
  ou sem correspondência, o texto cai para "Fonte: Análise Semântica Interna."

  Scenario: INTENT_TIMING com evidência rastreável popula references
    Given uma inferência com derived_from "ev_001" e intent_signals ["expansão"]
    And um evidence_index com "ev_001" apontando para "https://ex.com/noticia"
    When run_m5 é chamado com score.intent positivo
    Then o Driver INTENT_TIMING tem references[0].url igual a "https://ex.com/noticia"
    And o texto do Driver contém "Fontes:"

  Scenario: evidence_index vazio produz references vazio e texto semântico
    Given uma inferência com derived_from "ev_001" e intent_signals ["expansão"]
    And um evidence_index vazio
    When run_m5 é chamado com score.intent positivo
    Then o Driver INTENT_TIMING tem references vazio
    And o texto do Driver contém "Análise Semântica Interna"

  Scenario: derived_from sem correspondência no índice (Open-World)
    Given uma inferência com derived_from "ev_999" e intent_signals ["expansão"]
    And um evidence_index com "ev_001" apontando para "https://outro.com"
    When run_m5 é chamado com score.intent positivo
    Then o Driver INTENT_TIMING tem references vazio
    And o texto do Driver contém "Análise Semântica Interna"
