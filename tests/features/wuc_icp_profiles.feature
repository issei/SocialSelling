@WUC
Feature: WU-C — ICP Profile CRUD + CLI --profile
  O sistema de perfis permite criar, listar, deletar e ativar configurações de ICP
  nomeadas persistidas como JSON atômico, com 4 endpoints FastAPI e opção --profile no CLI.

  Scenario: Criar perfil válido e listá-lo via GET
    Given um ambiente de teste com config isolada e catálogo base carregado
    And um payload de perfil válido com name "SaaS Latam" e H_01 habilitado
    When POST /api/v1/profiles é chamado com o payload válido
    Then a resposta tem status 201
    And o campo profile_id está presente no JSON de resposta
    And GET /api/v1/profiles retorna uma lista com o perfil criado

  Scenario: Criar perfil com hypothesis_id inválido retorna 422
    Given um ambiente de teste com config isolada e catálogo base carregado
    And um payload de perfil com hypotheses_config contendo "H_INVALIDO"
    When POST /api/v1/profiles é chamado com o payload inválido
    Then a resposta tem status 422

  Scenario: GET /api/v1/profiles com diretório vazio retorna lista vazia
    Given um ambiente de teste com config isolada sem perfis salvos
    When GET /api/v1/profiles é chamado
    Then a resposta tem status 200
    And o JSON de resposta é uma lista vazia
