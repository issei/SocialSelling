@T4
Feature: WU-T4 — APIs de feedback do portal

  Scenario: Feliz — POST feedback grava evento com dados da sessão e run_id do snapshot mais recente
    Given um portal com snapshot "run_2" contendo "cliniq.com.br" para perfil "talita_profile"
    And a operadora "talita" está autenticada no portal
    When ela envia POST /lead/cliniq.com.br/feedback com kind=status e status_id=abordado
    Then a resposta tem status 200
    And o evento gravado tem operator_id=talita profile_id=talita_profile run_id=run_2

  Scenario: Degradado — status_id fora do catálogo retorna 422
    Given um portal com snapshot "run_2" contendo "cliniq.com.br" para perfil "talita_profile"
    And a operadora "talita" está autenticada no portal
    When ela envia POST /lead/cliniq.com.br/feedback com kind=status e status_id=quase_cliente
    Then a resposta tem status 422

  Scenario: Degradado — lead fora da carteira retorna 404
    Given um portal com snapshot "run_2" contendo "cliniq.com.br" para perfil "talita_profile"
    And a operadora "talita" está autenticada no portal
    When ela envia POST /lead/outro.com.br/feedback com kind=status e status_id=abordado
    Then a resposta tem status 404

  Scenario: Open-World — cursor além do fim retorna lista vazia e next_since=since
    Given um portal com 2 eventos de feedback para "talita_profile"
    When o motor solicita GET /api/feedback com since=99
    Then a resposta tem status 200
    And a lista de eventos está vazia
    And o next_since é 99

  Scenario: Degradado — GET /api/feedback sem Bearer retorna 401
    Given um portal sem eventos de feedback
    When um cliente sem Bearer solicita GET /api/feedback
    Then a resposta tem status 401
