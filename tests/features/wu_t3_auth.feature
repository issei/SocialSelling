@T3
Feature: WU-T3 — Autenticação da operadora por código de acesso

  Background:
    Given um portal com InMemoryDAO e operadora "talita" registrada com código "codigo-correto"

  Scenario: Feliz — login com código correto cria sessão e redireciona para /carteira
    When a operadora envia POST /login com o código "codigo-correto"
    Then a resposta de login tem status 303
    And o header Location da resposta de login aponta para /carteira
    And o cookie de sessão tem os atributos HttpOnly, SameSite=lax e Secure

  Scenario: Degradado — login com código errado retorna 401 genérico sem criar sessão
    When a operadora envia POST /login com o código "codigo-errado"
    Then a resposta de login tem status 401
    And o corpo da resposta contém "inválido"
    And nenhum cookie de sessão é criado na resposta

  Scenario: Open-World — sem sessão acessa /carteira e é redirecionado para /login
    When um cliente sem sessão acessa GET /carteira
    Then a resposta tem status 303
    And o header Location aponta para /login

  Scenario: Logout invalida a sessão
    Given a operadora está autenticada com código "codigo-correto"
    When a operadora envia POST /logout
    Then a resposta de logout tem status 303
    And o header Location da resposta de logout aponta para /login
    And ao acessar GET /carteira após logout a resposta tem status 303
