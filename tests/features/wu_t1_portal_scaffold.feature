# language: pt
@WU-T1
Funcionalidade: Scaffold do portal — porta DAO e /healthz (WU-T1)

  # ---- Contract tests da porta (InMemoryDAO) ----

  Cenário: put_snapshot retorna True na primeira inserção e False na segunda (idempotência)
    Dado um InMemoryDAO limpo
    Quando insiro o snapshot (talita, run_abc) com now="2026-06-10T00:00:00Z"
    Então o resultado é True
    Quando insiro o mesmo snapshot novamente
    Então o resultado é False
    E o DAO contém exatamente 1 snapshot para o perfil "talita"

  Cenário: list_snapshots retorna snapshots em ordem published_at DESC, tie-break run_id DESC
    Dado um InMemoryDAO limpo
    Quando insiro o snapshot (talita, run_a) com now="2026-06-10T01:00:00Z"
    E insiro o snapshot (talita, run_b) com now="2026-06-10T02:00:00Z"
    E insiro o snapshot (talita, run_c) com now="2026-06-10T02:00:00Z"
    Então list_snapshots para "talita" retorna [run_c, run_b, run_a] nessa ordem

  Cenário: events_since retorna eventos com event_id > since em ordem ASC
    Dado um InMemoryDAO limpo com 3 eventos de status
    Quando chamo events_since com since=1
    Então recebo 2 eventos com event_ids [2, 3] em ordem crescente

  Cenário: events_since com since além do fim retorna lista vazia
    Dado um InMemoryDAO limpo com 3 eventos de status
    Quando chamo events_since com since=99
    Então recebo lista vazia

  Cenário: latest_status_by_entity retorna o status do maior event_id
    Dado um InMemoryDAO limpo
    Quando appendo evento kind=status entity_id=cliniq.com.br status_id=interagindo
    E appendo evento kind=status entity_id=cliniq.com.br status_id=abordado
    Então latest_status_by_entity para "talita" retorna cliniq.com.br=abordado

  Cenário: Entidade sem evento de status não aparece no latest_status_by_entity
    Dado um InMemoryDAO limpo com evento kind=reaction para cliniq.com.br
    Quando chamo latest_status_by_entity para "talita"
    Então o dicionário retornado está vazio

  # ---- Teste do app FastAPI ----

  Cenário: GET /healthz retorna 200 e X-Robots-Tag noindex
    Dado um TestClient do portal com InMemoryDAO
    Quando faço GET /healthz
    Então a resposta tem status 200
    E o body JSON contém status=ok
    E o header X-Robots-Tag vale noindex
