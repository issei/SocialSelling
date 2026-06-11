# language: pt
@WU-T2
Funcionalidade: POST /api/publish — publicação de snapshot (WU-T2)

  Cenário: Publicação feliz retorna 201 e persiste o snapshot
    Dado um portal com InMemoryDAO e PUBLISH_TOKEN configurado
    Quando faço POST /api/publish com um snapshot válido para (talita, run_abc)
    Então a resposta tem status 201
    E o body contém run_id=run_abc
    E o DAO contém 1 snapshot para o perfil "talita"

  Cenário: Republicação do mesmo (profile_id, run_id) retorna 409 sem duplicar
    Dado um portal com InMemoryDAO e PUBLISH_TOKEN configurado
    E o snapshot (talita, run_abc) já está publicado
    Quando faço POST /api/publish com o mesmo snapshot (talita, run_abc)
    Então a resposta tem status 409
    E o DAO ainda contém exatamente 1 snapshot para o perfil "talita"

  Cenário: Token ausente retorna 401 sem persistir nada
    Dado um portal com InMemoryDAO e PUBLISH_TOKEN configurado
    Quando faço POST /api/publish sem header Authorization
    Então a resposta tem status 401
    E o DAO contém 0 snapshots para o perfil "talita"

  Cenário: Token errado retorna 401
    Dado um portal com InMemoryDAO e PUBLISH_TOKEN configurado
    Quando faço POST /api/publish com token errado
    Então a resposta tem status 401

  Cenário: Snapshot com campo extra "score" é rejeitado com 422
    Dado um portal com InMemoryDAO e PUBLISH_TOKEN configurado
    Quando faço POST /api/publish com um body que contém o campo extra "score"
    Então a resposta tem status 422
    E o DAO contém 0 snapshots para o perfil "talita"

  Cenário: Snapshot com ranks não-estritos é rejeitado com 422
    Dado um portal com InMemoryDAO e PUBLISH_TOKEN configurado
    Quando faço POST /api/publish com leads em ranks 1 e 3
    Então a resposta tem status 422
