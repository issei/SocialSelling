# language: pt
@WU-E3
Funcionalidade: CLI publish — motor publica top-20 sem score (ADR-010, SDD §6.2)

  Cenário: Publicação feliz do top-20 sem score
    Dado uma visão ranqueada do perfil "talita" com 32 leads
    Quando executo publish para "talita" com o portal respondendo 201
    Então o snapshot enviado tem 20 leads com rank_position 1..20
    E nenhum campo numérico de score aparece no payload publicado
    E o registro local de "talita" guarda os scores por entity_id
    E a CLI termina com sucesso

  Cenário: Republicação do mesmo ranking é idempotente
    Dado uma visão ranqueada do perfil "talita" com 32 leads
    Quando computo o run_id duas vezes para o mesmo ranking
    Então os dois run_id são idênticos
    Quando executo publish para "talita" com o portal respondendo 409
    Então a CLI termina com sucesso

  Cenário: Portal fora do ar não quebra o motor (degradado)
    Dado uma visão ranqueada do perfil "talita" com 32 leads
    Quando executo publish para "talita" com o portal recusando conexão
    Então o registro local de "talita" guarda os scores por entity_id
    E a CLI termina com falha e mensagem acionável

  Cenário: Snapshot preserva missing_evidence (Open-World)
    Dado uma visão ranqueada com um lead cujo gaps lista "sem sinal de contratação"
    Quando o snapshot é montado para "talita"
    Então o missing_evidence do lead lista "sem sinal de contratação"
    E o lead permanece publicado
