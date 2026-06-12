@T5
Feature: WU-T5 — UI da operadora: carteira + lead card

  Scenario: Feliz — carteira exibe leads do snapshot mais recente e em acompanhamento
    Given um portal com snapshot run_2 contendo A e B e snapshot run_1 contendo B e D
    And o lead D tem status abordado e o lead B tem status fora_do_perfil
    When a operadora autenticada acessa GET /carteira
    Then a resposta tem status 200 e é HTML
    And A aparece na carteira sem indicação de acompanhamento
    And D aparece na carteira como em acompanhamento
    And B não aparece na carteira por ser terminal
    And a carteira não exibe nenhum número de score

  Scenario: Open-World — lead sem status aparece como novo na carteira
    Given um portal com snapshot run_1 contendo somente Z sem nenhum evento de status
    When a operadora autenticada acessa GET /carteira
    Then a resposta tem status 200 e é HTML
    And o status de Z na carteira é novo

  Scenario: Determinismo — duas montagens de carteira geram ordem idêntica
    Given um portal com snapshot run_1 contendo A B C em acompanhamento anteriores X Y
    When build_carteira é chamado duas vezes com os mesmos dados
    Then as duas listas são idênticas

  Scenario: Degradado — lead fora da carteira do perfil retorna 404
    Given um portal sem leads para o perfil da operadora
    When a operadora autenticada acessa GET /lead/inexistente.com.br
    Then a resposta tem status 404

  Scenario: Open-World — sem sessão acessa lead card e é redirecionado
    Given um portal sem leads para o perfil da operadora
    When um cliente sem sessão acessa GET /lead/qualquer.com.br
    Then a resposta tem status 303

  Scenario: Assert estrutural — lead card não renderiza campo de score
    Given um portal com snapshot run_1 contendo somente Z sem nenhum evento de status
    When a operadora autenticada acessa GET /lead/z.com.br
    Then a resposta tem status 200 e é HTML
    And o HTML do lead card não contém campos de score numérico
