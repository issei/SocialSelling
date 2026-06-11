# language: pt
@WU-E1
Funcionalidade: Regra canônica de entity_id (WU-E1)

  O join do feedback depende da identidade canônica; órfãos corrompem o aprendizado.
  A função canonical_entity_id deve ser estável entre runs e provedores.

  Cenário: Site com esquema e subdomínio www retorna domínio limpo
    Dado o website "https://www.Cliniq.com.br/sobre?x=1"
    Quando calculo o entity_id com nome "Cliniq" e cidade "São Paulo"
    Então o entity_id é "cliniq.com.br"

  Cenário: Site sem esquema é tratado como HTTPS
    Dado o website "cliniq.com.br"
    Quando calculo o entity_id com nome "Cliniq" e cidade "São Paulo"
    Então o entity_id é "cliniq.com.br"

  Cenário: Mesmo lead com variações de URL gera mesmo entity_id
    Dado o website "https://www.cliniq.com.br/sobre"
    Quando calculo o entity_id com nome "Cliniq" e cidade "São Paulo"
    Então o entity_id é "cliniq.com.br"
    E é idêntico ao entity_id calculado para website "cliniq.com.br"

  Cenário: Site com porta explícita — a porta é ignorada
    Dado o website "https://exemplo.com.br:8080/path"
    Quando calculo o entity_id com nome "Exemplo" e cidade "RJ"
    Então o entity_id é "exemplo.com.br"

  Cenário: Fallback por nome+cidade quando não há website
    Dado que não há website
    Quando calculo o entity_id com nome "Loja da Maria" e cidade "São Paulo"
    Então o entity_id começa com "sha256:"
    E tem 64 caracteres hexadecimais após o prefixo

  Cenário: Fallback é estável com variações de acentos e caixa
    Dado que não há website
    Quando calculo o entity_id com nome "LOJA DA MARIA" e cidade "sao paulo"
    Então o entity_id é igual ao de nome "Loja da Maria" e cidade "São Paulo"

  Cenário: Fallback com cidade ausente usa string vazia
    Dado que não há website
    Quando calculo o entity_id com nome "Empresa Alfa" e cidade ausente
    Então o entity_id começa com "sha256:"

  Cenário: Leads distintos geram entity_ids distintos
    Dado o website "https://www.cliniq.com.br"
    E outro lead com website "https://www.outro.com.br"
    Quando calculo ambos os entity_ids
    Então os dois entity_ids são diferentes

  Cenário: Lead com site vazio cai no fallback
    Dado o website vazio
    Quando calculo o entity_id com nome "Empresa Sem Site" e cidade "BH"
    Então o entity_id começa com "sha256:"
