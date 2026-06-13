# language: pt
@WU-T6
Funcionalidade: render.yaml + entrypoint de produção (ADR-010, SDD §8)

  Cenário: render.yaml é YAML válido e bate com o contrato da SDD §8
    Dado o arquivo render.yaml na raiz do repositório
    Quando faço o parse YAML
    Então há um serviço web "socialselling-portal" na região "virginia" no plano "free"
    E o build é "pip install -e \".[portal]\""
    E o start usa "uvicorn socialselling.portal.main:app"
    E o health check é "/healthz"

  Cenário: Nenhum segredo está commitado (env vars só referenciadas)
    Dado o arquivo render.yaml na raiz do repositório
    Quando faço o parse YAML
    Então as env vars DATABASE_URL, PUBLISH_TOKEN e SECRET_KEY existem
    E nenhuma env var tem valor commitado (todas com sync=false)

  Cenário: O entrypoint de produção importa sem DATABASE_URL
    Dado que DATABASE_URL não está no ambiente
    Quando importo socialselling.portal.main
    Então o atributo app existe no módulo
