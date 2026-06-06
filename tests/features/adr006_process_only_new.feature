@ADR006
Feature: ADR-006 process-only-new — skip de re-extração para entidades do corpus
  Para reduzir o consumo de Gemini entre runs, o M2 deve pular chamadas ao Gemini
  para entidades cujo domínio de company.website já tem extração válida no corpus.
  Entidades pendentes (Gemini falhou antes) são re-tentadas normalmente.

  Scenario: Entidade com extração válida no corpus — Gemini não é chamado
    Given um corpus com extração válida para o domínio "acme.com.br"
    And uma evidência com source_url "https://acme.com.br/sobre"
    When eu executo o M2 com corpus_store
    Then o Gemini não é chamado nenhuma vez
    And a inferência retornada corresponde à do corpus

  Scenario: Entidade pendente no corpus — Gemini é chamado para re-tentativa
    Given um corpus com extração pendente para o domínio "beta.com.br"
    And uma evidência com source_url "https://beta.com.br/home"
    When eu executo o M2 com corpus_store
    Then o Gemini é chamado exatamente 1 vez

  Scenario: Entidade ausente do corpus — Gemini é chamado e resultado armazenado
    Given um corpus vazio
    And uma evidência com source_url "https://gamma.com.br/"
    When eu executo o M2 com corpus_store
    Then o Gemini é chamado exatamente 1 vez
    And a inferência de "gamma.com.br" é armazenada no corpus como válida
