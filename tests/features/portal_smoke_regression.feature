# language: pt
@portal-regression
Funcionalidade: Portal da operadora — smoke de regressão end-to-end

  Contexto:
    Dado um portal com InMemoryDAO e operadora "talita" registrada com código "talita-2026"

  Cenário: Saúde — /healthz responde antes de qualquer autenticação
    Quando um cliente sem sessão acessa GET /healthz
    Então a resposta tem status 200
    E o corpo JSON contém status ok

  Cenário: Fluxo completo — login, carteira vazia, logout, barreira
    Quando a operadora envia POST /login com o código "talita-2026"
    Então a resposta de login tem status 303 e Location /carteira
    Quando a operadora com sessão acessa GET /carteira
    Então a resposta tem status 200 e é HTML
    E o HTML não contém nenhum lead
    Quando a operadora envia POST /logout
    Então a resposta de logout tem status 303 e Location /login
    Quando após o logout acessa GET /carteira
    Então a resposta tem status 303 e Location /login

  Cenário: Degradado — código inválido não cria sessão e bloqueia /carteira
    Quando a operadora envia POST /login com o código "codigo-errado"
    Então a resposta de login tem status 401
    Quando sem sessão acessa GET /carteira
    Então a resposta tem status 303 e Location /login

  Cenário: Open-World — carteira sem snapshot não gera erro
    Dado que a operadora está autenticada com código "talita-2026"
    Quando acessa GET /carteira
    Então a resposta tem status 200 e é HTML
    E o HTML não contém número de score
