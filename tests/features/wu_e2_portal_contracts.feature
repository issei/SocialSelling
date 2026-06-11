# language: pt
@WU-E2
Funcionalidade: Contratos do portal e catálogo de feedback (WU-E2)

  Cenário: Round-trip de PublishedSnapshot (serialização e desserialização)
    Dado um PublishedSnapshot válido com 3 leads em ranks 1, 2, 3
    Quando serializo e desserializo o snapshot
    Então o objeto resultante é idêntico ao original

  Cenário: Ranks não-estritos são rejeitados pelo validador
    Dado um PublishedSnapshot com leads em ranks 1, 3 (pulando o 2)
    Quando tento criar o snapshot
    Então recebo ValueError com "rank_position"

  Cenário: Campo extra "score" é rejeitado (extra=forbid)
    Dado um dicionário de PublishedLead com o campo extra "score"
    Quando tento criar o PublishedLead
    Então recebo ValidationError

  Cenário: FeedbackEvent kind=status com reaction é rejeitado
    Dado um FeedbackEvent com kind=status e reaction=like
    Quando tento criar o evento
    Então recebo ValueError com "kind=status"

  Cenário: FeedbackEvent kind=reaction sem reaction é rejeitado
    Dado um FeedbackEvent com kind=reaction e sem campo reaction
    Quando tento criar o evento
    Então recebo ValueError com "kind=reaction"

  Cenário: Round-trip de FeedbackEvent válido (kind=status)
    Dado um FeedbackEvent válido com kind=status e status_id=abordado
    Quando serializo e desserializo o evento
    Então o objeto resultante é idêntico ao original

  Cenário: Catálogo de feedback padrão carrega e valida sem erros
    Quando carrego o feedback_catalog.json padrão
    Então o catálogo tem 9 status
    E os status_ids são únicos
    E as ordens são únicas e sequenciais de 1 a 9

  Cenário: Catálogo com status_ids duplicados é rejeitado
    Dado um catálogo com dois status tendo status_id="novo"
    Quando tento validar o catálogo
    Então recebo ValueError com "status_id e ordem devem ser únicos"

  Cenário: FeedbackCatalog extra=forbid rejeita campo desconhecido
    Dado um dicionário de catálogo com campo extra "versao_interna"
    Quando tento criar o FeedbackCatalog
    Então recebo ValidationError
