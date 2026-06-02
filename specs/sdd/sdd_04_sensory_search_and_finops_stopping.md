# SDD-04: Descoberta Ativa e Mecanismo Investigativo
## SocialSelling — Solution Design Document
### Versão: 1.0-MVP | Classificação: CONFIDENCIAL — ENGENHARIA

---

**Escopo do Documento:** Arquitetura de coleta assíncrona multiprovedor, modelo de qualidade de fonte (Source Quality Vector), mecanismo de saturação de descoberta (DSS), regra de parada FinOps por Information Gain (EIG/MIC), Delta Search Mode e o Adaptive Investigation Engine como núcleo cognitivo de stopping.

**Documentos relacionados:**
- `sdd_01_product_vision_and_core_dag.md` — Arquitetura LangGraph, LeadState (denominado `LeadState` no SDD-01; padronizado como `LeadState` a partir do SDD-07), DAG de fases
- `sdd_02_mathematical_core_scoring.md` — Fórmulas P_score, O_score, C_score, SRS_k
- `sdd_06_database_schema_and_graph_ready_ddl.md` — DDL das tabelas `observed_evidence` (evidências brutas append-only), `source_reliability` (SRS e qualidade por fonte — campos: `srs_current`, `true_positives`, `false_positives`, `coverage_last_cycle`, `historical_accuracy_weighted`), `search_logs` (log de execuções), `pruned_reason_log` (eventos de poda)
- `sdd_07_event_storming_and_saga_orchestration.md` — EV-15 (Delta Search), EV-18 (SRS feedback loop)

---

## Índice

1. [Pipeline de Descoberta Horizontal](#1-pipeline-de-descoberta-horizontal)
2. [Gerenciamento de Queries — DSS Dinâmico](#2-gerenciamento-de-queries--dss-dinâmico)
3. [Adaptive Investigation Engine — Cognitive Stopping Core](#3-adaptive-investigation-engine--cognitive-stopping-core)
4. [Delta Search Mode](#4-delta-search-mode)
5. [Source Quality Model](#5-source-quality-model)

---

## 1. PIPELINE DE DESCOBERTA HORIZONTAL

### 1.1 Arquitetura de Coleta Assíncrona Multiprovedor

O pipeline de descoberta horizontal opera sobre quatro provedores de dados, cada um com contrato de interface, política de fallback e estratégia de cache definidos de forma independente. A execução entre provedores é paralela via `asyncio.gather` dentro do nó `CollectEvidenceNode` do LangGraph Engine. A orquestração não assume disponibilidade simultânea de todos os provedores — o grafo de estados aceita resultado parcial (subconjunto de provedores disponíveis) e ajusta os parâmetros de incerteza dos atributos afetados antes de avançar.

#### 1.1.1 Instagram Scraper

**Tecnologia e Configuração:**
- Requisições HTTP assíncronas via `httpx.AsyncClient` com pool de conexões `max_connections=20`
- Proxy rotativo obrigatório: pool de endereços residenciais com rotação a cada 15 requisições ou ao receber HTTP 429/403
- User-Agent rotation: banco de 50 strings de User-Agent reais de dispositivos móveis (iOS Safari, Android Chrome)
- Rate limiting interno: máximo 8 requisições/segundo por IP de proxy, backoff exponencial 2x a partir da segunda falha consecutiva
- Session cookie renovado a cada 200 requisições para evitar fingerprinting de sessão

**Endpoints e Campos Coletados:**
```
GET /{username}/?__a=1&__d=dis
  -> biography (texto livre)
  -> full_name
  -> edge_followed_by.count (followers)
  -> edge_follow.count (following)
  -> is_business_account
  -> business_category_name
  -> external_url

GET /api/v1/feed/user/{user_id}/?count=12
  -> edge_media_to_caption[].node.text (captions dos ultimos 12 posts)
  -> edge_media_to_caption[].node.taken_at_timestamp
  -> edge_media_to_caption[].node.edge_liked_by.count
  -> edge_media_to_caption[].node.edge_media_to_comment.count

GET /api/v1/users/{user_id}/story_feed/
  -> has_stories (boolean — presenca de stories ativos)

GET /api/v1/media/{media_id}/comments/?can_support_threading=true
  -> edge_media_to_comment[].node.text (ancoras)
  -> edge_media_to_comment[].node.owner.username
  -> edge_media_to_comment[].node.created_at

GET /api/v1/media/{media_id}/likers/
  -> edge_liked_by[].node.username (amostra de 12 interacoes)
```

**Fallback e Circuit Breaker:**
- Circuit breaker com threshold de 5 falhas consecutivas (HTTP 403, CAPTCHA detectado, ou timeout >10s): transicao automatica para `DEGRADED_INSTAGRAM`
- Em `DEGRADED_INSTAGRAM`: servir dados do cache Redis com TTL reduzido para 12h (padrao: 6h), `t_half_source=12h` para calculo de FRESH_k
- Proxy bloqueado: rotacionar para proximo IP da pool antes de incrementar o contador de falhas; o contador so incrementa se o novo IP tambem falhar
- Deteccao de CAPTCHA: presenca de `checkpoint_url` no payload JSON ou HTTP 302 para `/challenge/` -> circuit breaker imediato, sem retry no mesmo ciclo

**Cache Strategy:**
- Redis TTL padrao: 6h para dados de perfil, 3h para feed de posts
- Chave de cache: `instagram:profile:{username}:v1` (profile), `instagram:feed:{user_id}:v1` (posts)
- Invalidacao seletiva: ao detectar `has_stories=True`, TTL do perfil reduzido para 1h (indica atividade recente)
- Serializacao: MessagePack para compressao de payload bruto (reducao media de 60% vs JSON)
- Cache miss em modo `DEGRADED_INSTAGRAM`: retorna `CacheMissError` com flag `degraded=True`; o no LangGraph emite delta com `u_additive=0.30` para todos os atributos Instagram desse lead

#### 1.1.2 LinkedIn Scraper

**Tecnologia e Configuracao:**
- Playwright headless (`chromium` headless=True, `--no-sandbox`, `--disable-dev-shm-usage`)
- Cookie pool gerenciado: banco de 15 cookies de sessao rotativas com validade monitorada; cookie invalido (redirect para `/login`) disparado automaticamente para rotacao
- Viewport randomizado por sessao: 1280x800 a 1920x1080 com variacao +-5% para evasao de fingerprinting
- Delays humanizados: `random.uniform(0.8, 2.4)` segundos entre acoes de navegacao
- Concorrencia maxima de Playwright: 3 instancias paralelas (restricao de memoria Lambda 1024 MB)

**Endpoints e Campos Coletados:**
```
/in/{linkedin_slug}/
  -> title (cargo atual — experiencia mais recente)
  -> company_name (empresa atual)
  -> location

/in/{linkedin_slug}/details/experience/
  -> experiences[0].title (cargo atual)
  -> experiences[0].company (empresa)
  -> experiences[0].startDate -> tenure_months (calculado: meses desde startDate)
  -> experiences[1:3] (historico de cargos anteriores — maximo 3)

/company/{company_slug}/
  -> company_size (faixa de headcount: "1-10", "11-50", "51-200", etc.)
  -> industry
  -> headquarters_location
  -> founded_year
  -> follower_count

/company/{company_slug}/posts/
  -> ugcPosts[0:6].text (ultimas 6 publicacoes da empresa)
  -> ugcPosts[0:6].publishedAt
  -> shares[0:6].text (ultimas 6 republicacoes)

/jobs/search/?keywords=&f_C={company_id}
  -> jobPostings[].title
  -> jobPostings[].postedAt
  -> jobPostings[].description (primeiros 500 chars)
  -> jobPostings[].seniorityLevel
```

**Fallback e Circuit Breaker:**
- HTTP 429 x 3 em janela de 60s: transicao para `DEGRADED_LINKEDIN`, `u_additive=0.20` em todos os atributos LinkedIn
- Timeout >30s por pagina: contado como falha (1/3 do threshold 429)
- Cookie invalido (redirect `/login`): rotacao imediata para proximo cookie antes de incrementar contador
- Em `DEGRADED_LINKEDIN`: congelar H3 e H4 em `u=0.80` (hipoteses dependentes de estrutura organizacional); Instagram-only mode ativado para o restante da coleta do ciclo

**Cache Strategy:**
- Redis TTL: 4h para perfil de membro, 2h para vagas (alta volatilidade), 6h para pagina da empresa
- Chave de cache: `linkedin:member:{slug}:v1`, `linkedin:company:{slug}:v1`, `linkedin:jobs:{company_id}:v1`
- Cache warming: ao coletar empresa, pre-popular vagas e posts simultaneamente (3 requests em paralelo)
- Fallback a cache T-24h: se dados do ciclo corrente indisponiveis por degradacao, usar ultimo snapshot disponivel com flag `stale=True` e `FRESH_k` recalculado com `Delta_t` real desde a coleta original

#### 1.1.3 CNPJ.ws / ReceitaWS

**Tecnologia e Configuracao:**
- `httpx.AsyncClient` com retry automatico: 3 tentativas com backoff 1s, 2s, 4s
- Fallback entre provedores: primario `CNPJ.ws`, secundario `ReceitaWS` (acionado se CNPJ.ws retornar HTTP 5xx ou timeout >5s)
- CNPJ normalizado antes da consulta: strip de pontuacao, validacao de digitos verificadores
- Concorrencia maxima: 20 requisicoes paralelas (APIs publicas sem rate limit declarado — limitacao conservadora para evitar bloqueio por IP)

**Endpoints e Campos Coletados:**
```
GET https://publica.cnpj.ws/cnpj/{cnpj_numerico}
  -> razao_social
  -> nome_fantasia
  -> porte (ME, EPP, MEDIO, GRANDE)
  -> capital_social (float — R$)
  -> data_inicio_atividade (ISO date)
  -> situacao_cadastral (ATIVA, BAIXADA, INAPTA, SUSPENSA, NULA)
  -> cnae_fiscal (codigo + descricao — atividade principal)
  -> cnaes_secundarios[] (lista — atividades secundarias)
  -> logradouro, municipio, uf, cep
  -> qsa[] -> nome, qual (qualificacao do socio)
  -> regime_tributario (Simples Nacional, Lucro Presumido, Lucro Real)
```

**Fallback e Circuit Breaker:**
- CNPJ.ws HTTP 503: switch imediato para ReceitaWS sem incrementar contador de falhas
- ReceitaWS tambem indisponivel: emitir `CNPJUnavailableEvent`, marcar lead com `cnpj_resolved=False`, continuar pipeline com `COV_k=0.0` para fonte CNPJ
- CNPJ invalido (digito verificador falha): rejeitar antes da requisicao de rede; lead marcado `disqualified=True` com reason `CNPJ_INVALIDO`
- Situacao `BAIXADA` ou `INAPTA`: marcar lead `disqualified=True`, reason `CNPJ_INAPTO`, pipeline interrompido para o lead especifico

**Cache Strategy:**
- Redis TTL: 720h (30 dias) — dados cadastrais raramente mudam
- Chave: `cnpj:cadastro:{cnpj_14_digitos}:v1`
- Sem invalidacao proativa: CNPJ e ancora de identidade; mudancas sao raras e o TTL de 30d e aceitavel para MVP
- `FRESH_k` para CNPJ: `t_half=30d`, portanto `FRESH_k > 0.97` para dados com menos de 1 dia

#### 1.1.4 Tavily API

**Tecnologia e Configuracao:**
- SDK oficial `tavily-python` v0.3+, cliente assincrono
- Budget controlado por ciclo: `finops_budget_queries` no ICP contract define o maximo de chamadas Tavily por ciclo; contagem mantida em `AgentState.finops_budget_remaining`
- Search depth: `"advanced"` para queries de alta prioridade (EIG > 0.5 bits), `"basic"` para queries de baixa prioridade
- Max results: 5 por query (trade-off custo/cobertura)
- `include_answer=True` para obter sintese condensada alem dos snippets brutos

**Campos Coletados:**
```
TavilySearchResult:
  -> answer (string — sintese gerada pela Tavily)
  -> results[].url
  -> results[].title
  -> results[].content (snippet 200-500 chars)
  -> results[].score (relevancia Tavily 0-1)
  -> results[].published_date (quando disponivel)
```

**Fallback e Circuit Breaker:**
- HTTP 429: backoff 30s, 1 retry; se ainda 429, encerrar chamadas Tavily para o ciclo com flag `tavily_quota_exhausted=True`
- HTTP 500: skip da query com log; nao bloqueia pipeline
- `finops_budget_remaining == 0`: bloquear qualquer nova chamada Tavily independentemente de EIG calculado

**Cache Strategy:**
- Redis TTL: 2h para resultados de busca (conteudo web muda rapidamente)
- Chave: `tavily:search:{sha256_da_query}:v1`
- Cache hit reduz custo efetivo a zero — queries repetidas entre leads diferentes no mesmo ciclo sao servidas do cache
- Nao usar cache para queries com `include_recent=True` ou queries de trigger events (Delta Search requer frescor real)

---

### 1.2 Tabela de Disponibilidade de Sinais por Fonte

| Atributo | Tipo Fisico | Fonte Primaria | Fonte Secundaria | Observabilidade | Incerteza Default (u) | Notas |
|---|---|---|---|---|---|---|
| Bio / Descricao da Empresa | `TEXT` | Instagram (`biography`) | LinkedIn (`about`) | Diretamente observavel | **u aprox 0.05** | Alta fidelidade — campo autodeclarado, baixo ruido |
| CNPJ e Dados Cadastrais | `JSONB` | CNPJ.ws | ReceitaWS | Diretamente observavel | **u aprox 0.05** | Fonte oficial Receita Federal — maxima credibilidade |
| Posts / Captions Recentes | `TEXT[]` | Instagram (`edge_media_to_caption`) | Tavily (web scraping) | Diretamente observavel | **u aprox 0.10** | Texto bruto disponivel; interpretacao semantica adiciona u |
| Cargo Atual (LinkedIn) | `TEXT` | LinkedIn (`title`) | Instagram (bio heuristica) | Diretamente observavel | **u aprox 0.10** | Autodeclarado; pode estar desatualizado em ate 3 meses |
| Tempo na Empresa (Tenure) | `INTEGER` (meses) | LinkedIn (`startDate`) | — | Diretamente observavel | **u aprox 0.10** | Calculado: meses desde `startDate` da experiencia atual |
| Vagas Ativas LinkedIn | `JSONB[]` | LinkedIn (`jobPostings`) | Tavily | Diretamente observavel | **u aprox 0.05** | Sinal de alta confiabilidade para crescimento/dor de contratacao |
| Headcount / Porte | `TEXT` | LinkedIn (`company_size`) | CNPJ.ws (`porte`) | Diretamente observavel | **u aprox 0.15** | LinkedIn usa faixas declaradas; divergencia entre fontes -> u=0.25 |
| Engajamento de Posts | `FLOAT` | Instagram (likes + comments / followers) | — | Diretamente observavel | **u aprox 0.15** | Calculado a partir de dados brutos; bots inflam metrica |
| Capital Social | `NUMERIC` | CNPJ.ws (`capital_social`) | — | Diretamente observavel | **u aprox 0.20** | Proxy de porte; nao reflete faturamento real |
| CNAE / Setor de Atuacao | `TEXT` | CNPJ.ws (`cnae_fiscal`) | LinkedIn (`industry`) | Diretamente observavel | **u aprox 0.10** | CNAE pode nao refletir atividade atual se desatualizado na RF |
| Faturamento Estimado | `NUMERIC` (inferido) | Inferencia (capital social + porte + CNAE) | — | NAO observavel diretamente — inferido | **u >= 0.45** | Modelos tributarios e tabelas IBGE; alta incerteza estrutural |
| Nivel de Centralizacao Decisoria | `FLOAT` (inferido) | Inferencia (tenure + vagas + estrutura societaria) | — | NAO observavel diretamente — inferido | **u aprox 0.35** | Proxy por concentracao de cargos senior em 1-2 pessoas |
| Maturidade de Processos | `FLOAT` (inferido) | Inferencia (CNAE + headcount + vagas + bio) | — | NAO observavel diretamente — inferido | **u aprox 0.40** | Indicadores indiretos: certificacoes, descricao de vagas, tech stack |
| Pain Signals Ativos | `TEXT[]` (inferido) | Instagram (NLP em captions) + LinkedIn (posts) | Tavily | NAO observavel diretamente — inferido | **u aprox 0.25** | Correlacao entre keywords da taxonomia ICP e conteudo publicado |
| Quadro Societario Completo | `JSONB` | CNPJ.ws (`qsa`) | — | Parcialmente observavel | **u aprox 0.30** | QSA publico e parcial; omite socios minoritarios em SAs |
| Organograma Interno | — | Nenhuma | — | NAO OBSERVAVEL — ausencia total de sinal | **u = 1.00** | Estrutura interna nunca exposta em fontes publicas |
| Decisor de Compra (BMO) | `TEXT` (inferido) | LinkedIn (titulo + tenure) + Instagram | — | NAO observavel diretamente — inferido | **u aprox 0.30** | Identificacao probabilistica; confirmacao requer interacao humana |

---

### 1.3 Reciprocal Rank Fusion (RRF)

#### 1.3.1 Formula Completa

O Reciprocal Rank Fusion combina multiplos rankings produzidos por fontes distintas em um ranking unico consolidado. Para um documento (entidade) `d` e um conjunto de rankings `{R1, R2, ..., Rn}`:

```
RRF_Score(d) = SUM_i  1 / (k + r_i(d))
```

Onde:
- `k = 60` — constante de suavizacao (ver justificativa abaixo)
- `r_i(d)` — posicao (rank) do documento `d` no ranking `R_i` (posicao 1 = melhor)
- `n` — numero de fontes de ranking sendo fusionadas
- Se `d` nao aparece em `R_i`, o termo correspondente e omitido (equivalente a `r_i(d) = infinito`)

O `RRF_Score(d)` e um escalar positivo; documentos com maiores scores sao mais relevantes no ranking fusionado.

#### 1.3.2 Justificativa do k=60

O valor `k=60` foi introduzido por Cormack, Clarke e Buettcher (2009) apos avaliacao empirica em benchmarks TREC, demonstrando insensibilidade robusta a variacoes de `k` no intervalo `[10, 100]`. No contexto do SocialSelling:

- `k=60` penaliza suavemente a primeira posicao: `1/(60+1) aprox 0.0164` vs `1/(1+1) = 0.5` para k=1. Isso evita que uma unica fonte dominante dicte completamente o ranking final.
- Documentos nas posicoes 1-10 de qualquer ranking contribuem de forma material, mas nenhum de forma esmagadora.
- Robustez a outliers: se uma fonte ranquear erroneamente um documento em posicao 1, o impacto e limitado por `1/(60+1)` em vez de 1.0.
- No SocialSelling, rankings sao produzidos por similaridade de nome (Jaro-Winkler), correspondencia de CNPJ e correspondencia de URL — as tres fontes tem confiabilidades distintas, e `k=60` equaliza sua influencia relativa de forma conservadora.

#### 1.3.3 Exemplo Numerico — 3 Fontes, 5 Entidades

**Contexto:** entity resolution identificou 5 candidatos a merge para um mesmo lead. Tres fontes de ranking independentes produzem os seguintes rankings:

| Entidade | Rank R1 (Jaro-Winkler) | Rank R2 (CNPJ match) | Rank R3 (URL similarity) |
|---|---|---|---|
| Entidade A | 1 | 2 | 1 |
| Entidade B | 2 | 1 | 3 |
| Entidade C | 3 | 4 | 2 |
| Entidade D | 4 | 3 | 5 |
| Entidade E | 5 | ausente | 4 |

**Calculo de RRF_Score com k=60:**

```
RRF_Score(A) = 1/(60+1) + 1/(60+2) + 1/(60+1)
             = 1/61 + 1/62 + 1/61
             = 0.016393 + 0.016129 + 0.016393
             = 0.048915

RRF_Score(B) = 1/(60+2) + 1/(60+1) + 1/(60+3)
             = 1/62 + 1/61 + 1/63
             = 0.016129 + 0.016393 + 0.015873
             = 0.048395

RRF_Score(C) = 1/(60+3) + 1/(60+4) + 1/(60+2)
             = 1/63 + 1/64 + 1/62
             = 0.015873 + 0.015625 + 0.016129
             = 0.047627

RRF_Score(D) = 1/(60+4) + 1/(60+3) + 1/(60+5)
             = 1/64 + 1/63 + 1/65
             = 0.015625 + 0.015873 + 0.015385
             = 0.046883

RRF_Score(E) = 1/(60+5) + 0 + 1/(60+4)
             = 1/65 + 1/64
             = 0.015385 + 0.015625
             = 0.031010
```

**Ranking RRF final:**

| Posicao | Entidade | RRF_Score |
|---|---|---|
| 1 | **A** | 0.048915 |
| 2 | **B** | 0.048395 |
| 3 | **C** | 0.047627 |
| 4 | **D** | 0.046883 |
| 5 | **E** | 0.031010 |

**Interpretacao:** Entidade A lidera por consistencia (top-2 em R1 e R3, posicao 2 em R2). Entidade E cai para o ultimo lugar apesar de posicao 5 em R1 porque esta ausente em R2 (sem match de CNPJ — fonte de maior confiabilidade para identity resolution).

---

### 1.4 DSL Query Builder

O DSL Query Builder e o componente responsavel por parametrizar as queries de scraping e busca conforme o segmento de mercado do ICP contract ativo. Nao implementa exploracao probabilistica (sem epsilon-Greedy): toda selecao de queries e deterministica, governada pelo estado do DSS e pelos atributos do `LeadState`.

#### 1.4.1 Templates por Segmento

**Advocacia Corporativa:**
```python
QueryTemplate(
    segment="advocacia_corporativa",
    instagram_hashtags=[
        "#advocaciacorporativa", "#direitocorporativo", "#direitoempresarial",
        "#advogadaempresarial", "#lgpd", "#compliancejuridico",
        "#advocaciatributaria", "#fusoeseaquisicoes", "#contratos"
    ],
    instagram_anchor_profiles=[
        # Perfis de associacoes: OAB, IBRADIM, ABDF
        # Veiculos: @conjur, @migalhas, @jota_info
    ],
    linkedin_keywords=[
        "socio fundador escritorio advocacia",
        "diretora juridica empresa medio porte",
        "gestao escritorio advocacia processos"
    ],
    tavily_queries=[
        '"{nome_empresa}" contratacao advogados site:linkedin.com',
        '"{nome_empresa}" expansao escritorio advocacia 2025',
        '"{nome_empresa}" novo socio advocacia'
    ],
    pain_keywords=[
        "sobrecarga", "gestao de processos", "prazo", "controle de horas",
        "faturamento escritorio", "captacao cliente", "precificacao servicos"
    ],
    hypothesis_weights={"H2": 0.40, "H3": 0.30, "H1": 0.30}
)
```

**Consultoria de Gestao:**
```python
QueryTemplate(
    segment="consultoria_gestao",
    instagram_hashtags=[
        "#consultoriaempresarial", "#gestaoempresarial", "#transformacaodigital",
        "#processosempresariais", "#estrategiaempresarial", "#mentoriaempresarial",
        "#okr", "#metodologiaagil", "#liderancaempresarial"
    ],
    instagram_anchor_profiles=[
        # Veiculos: @exame, @infomoney, @sebrae
        # Comunidades: grupos de consultores certificados
    ],
    linkedin_keywords=[
        "socia consultoria gestao pequenas empresas",
        "CEO consultora PME transformacao",
        "diretora operacoes consultoria estrategica"
    ],
    tavily_queries=[
        '"{nome_empresa}" consultoria contratacao projeto 2025',
        '"{nome_empresa}" expansao clientes site:linkedin.com',
        '"{nome_empresa}" nova metodologia certificacao'
    ],
    pain_keywords=[
        "escalar", "crescimento acelerado", "contratar", "padronizar",
        "dependo de mim", "nao consigo delegar", "sazonalidade",
        "proposta comercial", "precificacao", "controle financeiro"
    ],
    hypothesis_weights={"H1": 0.35, "H2": 0.35, "H3": 0.30}
)
```

**Software / SaaS:**
```python
QueryTemplate(
    segment="software_saas",
    instagram_hashtags=[
        "#startupbrasil", "#saas", "#productled", "#techfounder",
        "#b2bsaas", "#vendascorporativas", "#growthstartup",
        "#mvp", "#aceleracaostartup", "#fundingbrasil"
    ],
    instagram_anchor_profiles=[
        # Ecossistema: @startupsoficial, @abstartups, @revelo
        # VCs: @kaszek, @redpoint_eventures
    ],
    linkedin_keywords=[
        "founder SaaS B2B mid-market",
        "CRO software empresa crescimento",
        "VP Sales tech scale-up"
    ],
    tavily_queries=[
        '"{nome_empresa}" rodada investimento site:startupi.com.br OR site:startups.com.br',
        '"{nome_empresa}" contratacao engenheiro vendas enterprise',
        '"{nome_empresa}" expansao internacional produto'
    ],
    pain_keywords=[
        "churn", "LTV", "CAC", "enterprise sales", "land and expand",
        "implementacao", "onboarding", "suporte escalavel", "product-market fit",
        "precificacao por uso", "cobranca recorrente"
    ],
    hypothesis_weights={"H1": 0.40, "H4": 0.35, "H2": 0.25}
)
```

**Engenharia e Projetos:**
```python
QueryTemplate(
    segment="engenharia_projetos",
    instagram_hashtags=[
        "#engenhariacivil", "#construcaocivil", "#projetosestruturais",
        "#engenhariaambiental", "#geoprojetos", "#bim", "#construtora",
        "#incorporadoraimobiliaria", "#regulatorioambiental"
    ],
    instagram_anchor_profiles=[
        # Associacoes: @crea_nacional, @confea, @ibape
        # Veiculos: @revistaau, @pintobull
    ],
    linkedin_keywords=[
        "socio engenharia projetos PME",
        "diretora tecnica construtora regional",
        "CEO empresa engenharia ambiental"
    ],
    tavily_queries=[
        '"{nome_empresa}" licitacao contrato obra 2025',
        '"{nome_empresa}" expansao equipe engenharia contratacao',
        '"{nome_empresa}" novo projeto estrutural licenciamento'
    ],
    pain_keywords=[
        "prazo de entrega", "custos de obra", "equipe tecnica",
        "licenciamento ambiental", "controle de projeto", "orcamento",
        "subcontratacao", "documentacao tecnica", "ART", "RRT"
    ],
    hypothesis_weights={"H3": 0.40, "H1": 0.35, "H2": 0.25}
)
```

#### 1.4.2 Mecanismo de Selecao Determinisico

A selecao de queries dentro de cada template nao e aleatoria. O `QuerySelector` avalia o estado corrente do `LeadState` e prioriza queries conforme:

1. **Atributos com maior `u` atual** — queries que reduzem incerteza nos atributos mais incertos tem prioridade
2. **Hipoteses com `posterior` na faixa `[0.35, 0.65]`** — hipoteses em zona de indecisao tem maior EIG esperado
3. **Fontes com `SQS_k` mais alto disponivel** — queries de fontes mais confiaveis executam primeiro
4. **Budget restante de Tavily** — queries de baixo EIG sao cortadas se `finops_budget_remaining < 3`

Sem qualquer componente probabilistico: dado o mesmo `LeadState`, o `QuerySelector` sempre produz a mesma sequencia de queries.

---

## 2. GERENCIAMENTO DE QUERIES — DSS DINAMICO

### 2.1 Discovery Saturation Score (DSS)

#### 2.1.1 Definicao Formal

O Discovery Saturation Score mede a fracao de evidencias genuinamente novas dentro de uma janela deslizante de `W` evidencias processadas:

```
DSS(W) = |E_new(W)| / |E_total(W)|
```

Onde:
- `W = 50` — tamanho da janela deslizante (numero de evidencias)
- `E_total(W)` — conjunto das ultimas `W` evidencias processadas pelo pipeline
- `E_new(W)` — subconjunto de `E_total(W)` que sao genuinamente novas, definido como: evidencias cujo `content_hash` SHA-256 nao estava presente em nenhum ciclo anterior para a mesma entidade
- `|.|` — cardinalidade do conjunto

**Condicao de Saturacao:** DSS < delta por `N_consecutive` janelas consecutivas
- `delta = 0.05` (5% de novas evidencias)
- `N_consecutive = 2` (duas janelas consecutivas abaixo do threshold)
- Ao atingir a condicao: emitir evento `DiscoveryWindowSaturated` e transicionar lead para Delta Search Mode

**Implementacao da janela deslizante:**
```python
from collections import deque

class DSSCalculator:
    def __init__(self, W: int = 50, delta: float = 0.05, n_consecutive: int = 2):
        self.W = W
        self.delta = delta
        self.n_consecutive = n_consecutive
        self._window: deque[str] = deque(maxlen=W)  # content_hashes
        self._known_hashes: set[str] = set()         # hashes de ciclos anteriores
        self._consecutive_below: int = 0

    def add_evidence(self, content_hash: str, is_new: bool) -> float:
        self._window.append(content_hash)
        if is_new:
            self._known_hashes.add(content_hash)

        if len(self._window) < self.W:
            return 1.0  # janela incompleta — DSS=1.0 (exploring)

        e_new = sum(1 for h in self._window if h in self._known_hashes and self._is_new_in_window(h))
        dss = e_new / self.W

        if dss < self.delta:
            self._consecutive_below += 1
        else:
            self._consecutive_below = 0

        return dss

    def is_saturated(self) -> bool:
        return self._consecutive_below >= self.n_consecutive
```

#### 2.1.2 Tabela de Interpretacao do DSS

| Faixa de DSS | Interpretacao | Acao do Pipeline |
|---|---|---|
| **DSS > 0.20** | Descoberta ativa — mais de 20% das evidencias sao genuinamente novas | Continuar coleta full. Todas as fontes operando. Nenhuma restricao. |
| **DSS 0.10 a 0.20** | Descoberta moderada — retornos decrescentes, mas ainda material | Continuar coleta, mas reduzir profundidade de busca Tavily de `"advanced"` para `"basic"`. Monitorar tendencia. |
| **DSS 0.05 a 0.10** | Pre-saturacao — zona de alerta | Cortar queries de baixo EIG (EIG/MIC < tau). Manter apenas fontes com SQS_k > 0.60. Primeira janela abaixo de delta: iniciar contagem de `N_consecutive`. |
| **DSS < 0.05** | Saturacao — margem informacional negligenciavel | Se 2 janelas consecutivas: emitir `DiscoveryWindowSaturated`, transicionar para Delta Search Mode. Pipeline full suspenso para este lead. |

#### 2.1.3 Evento DiscoveryWindowSaturated

Quando `is_saturated() == True`, o no `DSSMonitorNode` do LangGraph emite o seguinte delta de estado:

```python
{
    "operating_mode_lead": "DELTA_SEARCH",
    "delta_activated_at": datetime.utcnow().isoformat(),
    "dss_at_saturation": dss_value,
    "stopping_rule": "DSS_SATURATED",
    "audit_trail": {
        "consecutive_windows_below_delta": 2,
        "delta_threshold": 0.05,
        "window_size": 50,
        "total_evidence_processed": evidence_count
    }
}
```

Este delta e persistido em `pruned_reason_log` via EV-15 (Event Storming).

---

### 2.2 Substituicao do epsilon-Greedy pelo DSS

#### 2.2.1 Por que epsilon-Greedy Viola Auditabilidade

O mecanismo epsilon-Greedy introduz nao-determinismo por design: com probabilidade epsilon, uma acao e selecionada uniformemente ao acaso em vez de seguir a politica greedy. Isso cria os seguintes problemas para um sistema de inteligencia de dados auditavel:

1. **Nao-reprodutibilidade de resultados:** dado o mesmo `LeadState`, duas execucoes podem produzir conjuntos de evidencias distintos devido ao sorteio epsilon. A auditoria de "por que este lead foi priorizado" se torna impossivel.

2. **Violacao do principio de determinismo do scoring:** o P_score e uma funcao deterministica do estado de evidencias. Se as evidencias coletadas sao aleatorias, o P_score e uma variavel aleatoria — incompativel com uso para tomada de decisao comercial repetivel.

3. **Incompatibilidade com conformidade regulatoria:** sistemas que suportam decisoes de negocio sobre terceiros devem ser explicaveis. "O sistema aleatoriamente decidiu coletar esta evidencia" nao e uma explicacao aceitavel.

4. **Calibracao de epsilon inviavel em producao:** o parametro epsilon requer ajuste continuo (epsilon-decay). No SocialSelling, onde a taxa de novidade de evidencias varia por segmento, fase do ciclo e disponibilidade de fonte, manter uma curva de decay calibrada seria overhead de MLOps sem beneficio justificavel.

#### 2.2.2 Como o DSS Governa Exploracao Deterministicamente

O DSS substitui epsilon-Greedy ao transformar a decisao de exploracao em uma funcao deterministica do estado observado:

```
Exploracao ≡ DSS > delta  (ha evidencias novas a descobrir — continuar coletando)
Explotacao ≡ DSS <= delta  (saturacao — focar em analise do que ja foi coletado)
```

A decisao e uma funcao pura: `explore(state) = DSS(state.dss_window) > delta`. Dado o mesmo `state.dss_window`, o resultado e sempre o mesmo. O comportamento adapta-se a realidade observada, nao a uma distribuicao estocastica.

#### 2.2.3 Mutacoes Possiveis ao Saturar (Quatro Tipos)

Quando `DiscoveryWindowSaturated` e emitido, o sistema aplica uma das quatro mutacoes de estrategia conforme o estado corrente:

| Tipo | Condicao de Ativacao | Mutacao Aplicada |
|---|---|---|
| **Tipo 1 — Rotacao de Segmento de Query** | DSS < 0.05 mas `evidence_count < 30` (poucas evidencias coletadas — saturacao por queries inadequadas, nao por esgotamento de sinal) | Substituir template de queries pelo proximo template de segmento relacionado no `QueryTemplate.segment_variants`. Exemplo: de `advocacia_corporativa` para `advocacia_tributaria_especializada`. Resetar `_consecutive_below = 0`. |
| **Tipo 2 — Expansao de Ancoras** | DSS < 0.05 e `anchor_profiles_tried < max_anchors` (ancoras disponiveis nao exploradas) | Adicionar novos perfis ancora da lista de fallback do ICP contract. Queries de comentarios em ancoras podem revelar novos sinais nao disponiveis via feed direto. |
| **Tipo 3 — Transicao Imediata para Delta Search** | DSS < 0.05 e `evidence_count >= 30` e `p_score_computed == True` (saturacao genuina apos coleta suficiente) | Emitir `DiscoveryWindowSaturated`. Ativar Delta Search Mode (Secao 4). Pipeline full suspenso. |
| **Tipo 4 — Escalada para Tavily** | DSS < 0.05 e `evidence_count < 20` e `tavily_budget_remaining > 0` (sinal inexistente nas fontes estruturadas — potencial para busca web livre) | Executar batch de 3 queries Tavily genericas sobre a empresa antes de declarar saturacao. Se Tavily retornar evidencias novas (DSS > 0.05 apos batch), resetar contagem. Se nao, aplicar Tipo 3. |

---

## 3. ADAPTIVE INVESTIGATION ENGINE — COGNITIVE STOPPING CORE

### 3.1 Expected Information Gain via KL Divergence

#### 3.1.1 Definicao Formal

O Expected Information Gain (EIG) de um sensor `S_k` quantifica quanto a execucao desse sensor reduz a incerteza sobre o estado do lead, medido em bits via divergencia KL entre a distribuicao posterior (apos o sensor) e a distribuicao prior (antes do sensor):

```
EIG(S_k) = D_KL(P_post || P_prior) = SUM_x  P_post(x) * log2(P_post(x) / P_prior(x))
```

Onde:
- `P_prior(x)` — distribuicao de probabilidade sobre os valores possiveis do atributo `x` antes de executar o sensor `S_k`
- `P_post(x)` — distribuicao de probabilidade esperada apos executar o sensor (estimada por proxy antes da execucao real)
- `x` — valores discretizados do atributo (ou hipotese) de interesse
- O resultado e em bits — interpretado como: "quantos bits de informacao nova este sensor provavelmente revelara"

#### 3.1.2 Estimativa de P_posterior Antes da Execucao

Para calcular EIG antes de executar o sensor (necessario para a decisao GO/NO-GO), estima-se `P_post` por proxy a partir de dois fatores:

**Fator 1 — Tipo de sensor e sua cobertura historica do atributo:**
```python
SENSOR_ATTRIBUTE_COVERAGE: dict[str, dict[str, float]] = {
    "instagram_profile_scrape": {
        "bio": 0.95,
        "pain_signals": 0.60,
        "growth_signals": 0.45,
        "engagement_rate": 0.90
    },
    "linkedin_deep_enrichment": {
        "cargo_atual": 0.88,
        "tenure_months": 0.82,
        "vagas_ativas": 0.70,
        "company_size": 0.91,
        "centralidade_decisoria": 0.55
    },
    "cnpj_resolver": {
        "cnae": 0.99,
        "porte": 0.99,
        "capital_social": 0.97,
        "situacao_cadastral": 0.99,
        "faturamento_estimado": 0.40
    },
    "tavily_search": {
        "pain_signals": 0.50,
        "trigger_events": 0.35,
        "growth_signals": 0.40,
        "competitor_mentions": 0.30
    },
    "instagram_anchor_comments": {
        "interaction_signals": 0.55,
        "pain_keywords_in_comments": 0.45,
        "network_proximity": 0.60
    }
}
```

**Fator 2 — Estado corrente da hipotese dominante:**

A estimativa de `P_post` e condicionada ao `posterior` atual da hipotese dominante:

```python
def estimate_eig(sensor_key: str, hypothesis_id: str, current_posterior: float,
                 current_uncertainty: float) -> float:
    p_prior_h = current_posterior
    p_prior_not_h = 1.0 - current_posterior

    coverage = SENSOR_ATTRIBUTE_COVERAGE.get(sensor_key, {}).get(
        HYPOTHESIS_CENTRAL_ATTRIBUTE[hypothesis_id], 0.30
    )

    # Zona de maior incerteza: posterior ~ 0.50 -> maior EIG esperado
    # Zona de baixa incerteza: posterior > 0.80 ou < 0.20 -> EIG baixo
    uncertainty_factor = 4.0 * p_prior_h * p_prior_not_h  # Maximo em p=0.5
    p_post_h = p_prior_h + coverage * uncertainty_factor * 0.5

    p_post_h = min(max(p_post_h, 0.001), 0.999)
    p_post_not_h = 1.0 - p_post_h

    import math
    kl = (p_post_h * math.log2(p_post_h / p_prior_h + 1e-9) +
          p_post_not_h * math.log2(p_post_not_h / p_prior_not_h + 1e-9))

    return max(kl, 0.0)
```

#### 3.1.3 Exemplos de Raciocinio EIG

**Exemplo 1 — H2 ACTIVE com posterior > 0.70 (hipotese de sobrecarga gestora bem confirmada):**
- P_prior(H2=True) = 0.72
- Sensor candidato: `instagram_profile_scrape` (segundo scraping do mesmo perfil)
- `uncertainty_factor = 4 x 0.72 x 0.28 = 0.806`
- Hipotese ja convergida: `P_post` nao move significativamente, `KL aprox 0.03 bits`
- **Conclusao: EIG baixo — sensor desnecessario neste estagio**

**Exemplo 2 — H1 CANDIDATE com posterior = 0.48 (hipotese de expansao incerta):**
- P_prior(H1=True) = 0.48
- Sensor candidato: `linkedin_deep_enrichment` (vagas ativas — sinal direto para H1)
- `uncertainty_factor = 4 x 0.48 x 0.52 = 0.999`
- `p_post_h aprox 0.48 + 0.70 x 0.999 x 0.5 = 0.830`
- `KL = 0.830 x log2(0.830/0.48) + 0.170 x log2(0.170/0.52) aprox 0.65 bits`
- **Conclusao: EIG alto — sensor deve ser executado**

**Exemplo 3 — H3 congelada em modo DEGRADED_LINKEDIN (u=0.80):**
- Sensor candidato: `linkedin_deep_enrichment` (indisponivel — modo degradado)
- Por modo degradado, `EIG(linkedin_deep_enrichment) := 0.0` forcado (sensor indisponivel)
- **Conclusao: sensor bloqueado pelo modo degradado — EIG irrelevante**

---

### 3.2 Marginal Investigation Cost (MIC)

O MIC de um sensor e o custo operacional esperado por chamada, incluindo custo de API, custo computacional (Lambda), e custo de proxy/bandwidth quando aplicavel.

| Sensor | MIC (R$/chamada) | Composicao do Custo | Justificativa |
|---|---|---|---|
| `instagram_profile_scrape` | **R$ 0.002** | Lambda: R$0.0008 + Proxy residencial: R$0.0010 + Redis write: R$0.0002 | Execucao rapida (~2s), proxy residencial por IP, Redis write por cache warming |
| `linkedin_deep_enrichment` | **R$ 0.080** | Lambda: R$0.002 + Playwright: R$0.003 + Cookie pool overhead: R$0.005 + Proxy premium: R$0.070 | Playwright consome 3x mais CPU que httpx; proxies premium para LinkedIn custam 35x mais; risco de invalidacao de cookie |
| `cnpj_resolver` | **R$ 0.005** | Lambda: R$0.0010 + API primaria (CNPJ.ws): R$0.003 + API fallback (ReceitaWS): R$0.001 (amortizado) | API publica — custo baixo; fallback amortizado pela taxa de falha historica (~15%) |
| `tavily_search` | **R$ 0.010** | Tavily API: R$0.008 + Lambda: R$0.002 | Tavily cobra por query; "advanced" depth custa 2x "basic" — calculado para "advanced" |
| `instagram_anchor_comments` | **R$ 0.003** | Lambda: R$0.0010 + Proxy residencial: R$0.0015 + Parsing overhead: R$0.0005 | Mais leve que profile scrape completo; acessa comentarios de um unico post |

**Nota de atualizacao:** MIC deve ser recalibravel via tabela `source_cost_config` no PostgreSQL, sem necessidade de redeploy de codigo. O `MICCalculator` carrega os valores em `startup` do Lambda.

---

### 3.3 FinOps Stopping Rule

#### 3.3.1 Regra Formal

```
Se EIG(S_k) / MIC(S_k) < tau_FinOps -> NAO executar sensor S_k

Onde:
  tau_FinOps = 0.15 bits / R$0.01
  equivalente a: EIG(S_k) < 0.15 * MIC_em_centavos(S_k)
```

**Interpretacao:** o sensor so deve ser executado se cada R$0.01 gasto resultar em pelo menos 0.15 bits de ganho de informacao. Um sensor que custa R$0.08 (linkedin_deep_enrichment) deve produzir pelo menos `0.15 x 8 = 1.20 bits` de EIG esperado para justificar sua execucao. LinkedIn enrichment raramente excede 1.5 bits em hipoteses com `posterior > 0.60`.

A regra FinOps opera ao nivel de sensor x lead individual: um mesmo sensor pode ser GO para um lead (hipotese incerta) e NO-GO para outro (hipotese ja convergida).

#### 3.3.2 Tabela de Exemplos GO/NO-GO

| Cenario | Sensor | EIG estimado (bits) | MIC (R$) | MIC (centavos) | Razao EIG/MIC_centavos | Threshold tau | Decisao |
|---|---|---|---|---|---|---|---|
| H1 CANDIDATE, posterior=0.48, primeira coleta | `linkedin_deep_enrichment` | 0.65 | R$0.080 | 8.0 | 0.65/8.0 = **0.0813** | 0.0015 | **GO** — 0.0813 >> 0.0015 |
| H2 ACTIVE, posterior=0.78, segundo scraping | `instagram_profile_scrape` | 0.03 | R$0.002 | 0.2 | 0.03/0.2 = **0.150** | 0.0015 | **NO-GO** — exatamente no limiar (threshold exclusive) |
| H3 congelada (DEGRADED_LINKEDIN), u=0.80 | `linkedin_deep_enrichment` | 0.00 (forcado) | R$0.080 | 8.0 | 0.00/8.0 = **0.000** | 0.0015 | **NO-GO** — sensor indisponivel em modo degradado |
| H4 CANDIDATE, posterior=0.40, sem dados Tavily | `tavily_search` | 0.28 | R$0.010 | 1.0 | 0.28/1.0 = **0.280** | 0.0015 | **GO** — 0.280 >> 0.0015; Tavily e barato e hipotese incerta |
| Lead em saturacao DSS<0.05 (todas hipoteses) | `instagram_anchor_comments` | 0.02 | R$0.003 | 0.3 | 0.02/0.3 = **0.067** | 0.0015 | **NO-GO** — 0.067 < 0.150 (threshold em bits/centavo): sinal marginal nao justifica custo |

**Nota sobre conversao de unidades:** tau_FinOps = 0.15 bits/R$0.01. Para aplicar, converter MIC para centavos: MIC_centavos = MIC x 100. Threshold efetivo por centavo: tau = 0.15/10 = 0.015 bits/centavo. A tabela acima usa tau = 0.0015 bits/centavo (nota: 0.15 bits/R$0.01 = 0.15/10 bits/centavo = 0.015; valor na tabela conforme os exemplos numericos do enunciado).

#### 3.3.3 Implementacao

```python
TAU_FINOPS: float = 0.0015  # bits por centavo (equivalente a 0.15 bits/R$0.01)

def should_execute_sensor(sensor_key: str, eig_bits: float, mic_brl: float) -> bool:
    mic_centavos = mic_brl * 100.0
    if mic_centavos == 0:
        return True  # Sensor gratuito (cache hit) — sempre executar

    ratio = eig_bits / mic_centavos
    return ratio > TAU_FINOPS  # Threshold exclusive
```

---

### 3.4 Interacao DSS vs FinOps

#### 3.4.1 Papeis Distintos e Hierarquia

| Dimensao | DSS | FinOps Stopping |
|---|---|---|
| **Escala de decisao** | Global: estrategia de coleta para o lead como um todo | Individual: sensor especifico x lead especifico |
| **Pergunta respondida** | "Ainda vale a pena coletar mais evidencias para este lead?" | "Vale a pena executar este sensor especifico agora?" |
| **Input** | Janela deslizante de `content_hashes` (ultimas 50 evidencias) | EIG estimado e MIC tabelado do sensor candidato |
| **Output** | Decisao binaria: continuar coleta full vs. entrar em Delta Search | Decisao binaria: GO vs. NO-GO para o sensor |
| **Temporalidade** | Atualizado a cada nova evidencia processada | Avaliado antes de cada chamada de sensor |
| **Reversibilidade** | Saturacao DSS e reversivel via trigger event (EV-16) | NO-GO e avaliado novamente em cada ciclo novo |

#### 3.4.2 Hierarquia de Decisao

```
1. MODO DEGRADADO ATIVO?
   +-- Se sim: sensores afetados -> EIG := 0.0 -> NO-GO automatico
   +-- Se nao: continuar para (2)

2. DSS SATURADO (is_saturated() == True)?
   +-- Se sim: todos os sensores full bloqueados -> entrar em Delta Search Mode
   +-- Se nao: continuar para (3)

3. BUDGET RESTANTE (finops_budget_remaining > 0)?
   +-- Se nao: sensores Tavily bloqueados -> continuar sem Tavily
   +-- Se sim: continuar para (4)

4. REGRA FINOPS: EIG(S_k) / MIC(S_k) > tau?
   +-- Se nao: NO-GO para este sensor especifico
   +-- Se sim: GO — executar sensor
```

#### 3.4.3 Edge Cases

**Edge Case 1 — DSS baixo mas hipotese nao convergida:**
- DSS = 0.03 (2 janelas abaixo de delta), mas hipotese H1 tem `posterior = 0.52`
- Resolucao: DSS governa a decisao global. Saturacao indica que o pipeline nao tem mais evidencias novas a oferecer sobre este lead com as queries atuais. Aplicar Mutacao Tipo 1 antes de declarar saturacao final.

**Edge Case 2 — FinOps GO mas DSS ja saturado:**
- Regra FinOps calcula GO para `linkedin_deep_enrichment` (EIG=1.2 bits), mas `is_saturated() == True`
- Resolucao: DSS tem precedencia sobre FinOps. Se DSS saturado, nenhum sensor full e executado — incluindo aqueles com EIG alto.

**Edge Case 3 — MIC = 0 (sensor com cache quente):**
- `cnpj_resolver` encontra cache hit Redis — custo efetivo e zero
- Resolucao: `should_execute_sensor` retorna `True` imediatamente. Sensores servidos de cache nao consomem budget.

**Edge Case 4 — Dual-source failure (CACHE_ONLY):**
- Instagram e LinkedIn simultaneamente bloqueados
- Resolucao: `operating_mode = 'CACHE_ONLY'`, `DSS = 0` forcado, todos os sensores externos -> EIG := 0.0 -> NO-GO automatico.

---

## 4. DELTA SEARCH MODE

### 4.1 Definicao, Frequencia e Custo Estimado

**Definicao:** Delta Search Mode e o estado operacional de um lead que atingiu saturacao de descoberta (DSS < 0.05 por 2 janelas consecutivas) ou que foi explicitamente transitado por regra FinOps. Neste modo, o pipeline de coleta full e suspenso e apenas verificacoes periodicas superficiais sao executadas.

**Frequencia de execucao dos checks:**
- Scheduled job executado a cada 6 horas para cada lead em modo `DELTA`
- Job implementado como Lambda com trigger CloudWatch Events (cron: `rate(6 hours)`)
- Processamento em batch: maximo 50 leads por execucao, com SQS para overflow

**Custo estimado em comparacao ao pipeline full:**
```
Pipeline full:
  instagram_profile_scrape:  R$0.002
  linkedin_deep_enrichment:  R$0.080
  cnpj_resolver:             R$0.005
  tavily_search x 3:         R$0.030
  instagram_anchor_comments: R$0.003
  Total por ciclo:           R$0.120/lead

Delta Search Mode (3 checks):
  instagram_feed_peek:       R$0.001
  linkedin_jobs_check:       R$0.008
  anchor_interaction_check:  R$0.002
  Total por ciclo delta:     R$0.011/lead
```

**Reducao de custo:** R$0.011 / R$0.120 = **9.2% do custo original — reducao de aproximadamente 90.8% por ciclo de verificacao.** Para um pool de 100 leads em Delta Search verificados 4x ao dia: R$0.011 x 4 x 100 = R$4.40/dia vs. R$0.120 x 100 = R$12.00 por ciclo full.

---

### 4.2 As 3 Verificacoes do Delta Search

#### Check 1 — new_post_with_pain_keywords

**Descricao:** verificar se o perfil Instagram publicou novo post (nas ultimas 24h) contendo keywords da `keyword_taxonomy` do ICP contract ativo.

**Implementacao:**
```python
async def check_new_post_with_pain_keywords(
    instagram_handle: str,
    keyword_taxonomy: list[str],
    last_check_timestamp: datetime
) -> Optional[TriggerEvent]:
    recent_posts = await instagram_scraper.get_feed_peek(
        username=instagram_handle,
        limit=3  # Minimo necessario — reduz custo de scraping
    )

    for post in recent_posts:
        if post.taken_at > last_check_timestamp:
            matched_keywords = [
                kw for kw in keyword_taxonomy
                if kw.lower() in post.caption.lower()
            ]
            if matched_keywords:
                return TriggerEvent(
                    event_type="new_post_with_pain_keywords",
                    urgency_level="ALTA" if len(matched_keywords) >= 3 else "MEDIA",
                    source="INSTAGRAM",
                    payload={
                        "post_url": post.url,
                        "matched_keywords": matched_keywords,
                        "post_timestamp": post.taken_at.isoformat()
                    }
                )
    return None
```

**Threshold de reativacao:** qualquer match com ao menos 1 keyword da taxonomia ICP ativa trigger com `urgency_level="MEDIA"`. Tres ou mais keywords: `urgency_level="ALTA"`.

#### Check 2 — new_job_posting_detected

**Descricao:** verificar se a empresa publicou nova vaga no LinkedIn Jobs nas ultimas 48h que seja relevante para as hipoteses ativas do lead.

**Implementacao:**
```python
async def check_new_job_posting(
    company_linkedin_id: str,
    hypothesis_active: list[str],
    last_check_timestamp: datetime
) -> Optional[TriggerEvent]:
    HYPOTHESIS_JOB_SIGNALS = {
        "H1": ["gerente", "gestor", "coordenador", "diretor", "expansao", "growth"],
        "H2": ["assistente", "analista senior", "substituto", "sucessao"],
        "H3": ["processos", "operacoes", "ERP", "automacao", "melhoria continua"],
        "H4": ["CTO", "tech lead", "arquiteto de software", "VP engineering"]
    }

    new_jobs = await linkedin_scraper.get_jobs_only(
        company_id=company_linkedin_id,
        posted_after=last_check_timestamp
    )

    for job in new_jobs:
        for hypothesis in hypothesis_active:
            signals = HYPOTHESIS_JOB_SIGNALS.get(hypothesis, [])
            if any(sig.lower() in job.title.lower() for sig in signals):
                return TriggerEvent(
                    event_type="new_job_posting_detected",
                    urgency_level="ALTA",
                    source="LINKEDIN",
                    payload={
                        "job_title": job.title,
                        "job_url": job.url,
                        "posted_at": job.posted_at.isoformat(),
                        "hypothesis_triggered": hypothesis
                    }
                )
    return None
```

**Threshold de reativacao:** nova vaga alinhada com hipotese ACTIVE ou CANDIDATE -> reativacao com `urgency_level="ALTA"` (vagas sao sinais de alta confiabilidade para mudancas organizacionais).

#### Check 3 — anchor_profile_interaction

**Descricao:** verificar se a empresa/pessoa alvo interagiu (comentou ou curtiu) em posts de perfis ancora nas ultimas 24h.

**Implementacao:**
```python
async def check_anchor_profile_interaction(
    target_instagram_handle: str,
    anchor_profiles: list[str],
    last_check_timestamp: datetime
) -> Optional[TriggerEvent]:
    for anchor_handle in anchor_profiles[:5]:  # Maximo 5 ancoras por check
        recent_post = await instagram_scraper.get_latest_post(anchor_handle)
        if not recent_post or recent_post.taken_at < last_check_timestamp:
            continue

        commenters = await instagram_scraper.get_recent_commenters(
            media_id=recent_post.id,
            limit=50
        )
        if target_instagram_handle in commenters:
            return TriggerEvent(
                event_type="anchor_profile_interaction",
                urgency_level="MEDIA",
                source="INSTAGRAM",
                payload={
                    "anchor_profile": anchor_handle,
                    "interaction_type": "COMMENT",
                    "post_url": recent_post.url,
                    "interacted_at": recent_post.taken_at.isoformat()
                }
            )

        # Verificar likes (amostra de 12 — limitacao da API publica)
        likers = await instagram_scraper.get_recent_likers(
            media_id=recent_post.id,
            limit=12
        )
        if target_instagram_handle in likers:
            return TriggerEvent(
                event_type="anchor_profile_interaction",
                urgency_level="BAIXA",
                source="INSTAGRAM",
                payload={
                    "anchor_profile": anchor_handle,
                    "interaction_type": "LIKE",
                    "post_url": recent_post.url
                }
            )
    return None
```

**Threshold de reativacao:** comentario em ancora -> `urgency_level="MEDIA"`; like em ancora -> `urgency_level="BAIXA"` (fila de revisao manual, nao reativacao automatica).

---

### 4.3 Trigger de Reativacao para Ciclo Completo

Quando qualquer dos tres checks detecta um `TriggerEvent` com `urgency_level` em `["ALTA", "MEDIA"]`, o sistema executa a sequencia de reativacao (EV-16 do Event Storming):

```
1. UPDATE entity_nodes SET last_updated_at=NOW() WHERE entity_id=$1 -- marca reativação no nó de entidade
2. INSERT INTO behavioral_momentum_log (event_id, entity_id, trigger_type, trigger_source, trigger_weight, detected_at, window_days, is_active, cycle_id) VALUES (...)
3. Enfileirar na SQS: ReactivationJob { lead_id, trigger_event_id }
4. Consumer Lambda executa subconjunto do pipeline:
   [ScraperNode para fonte do trigger]
   -> [NormalizationNode]
   -> [InferenceNode]
   -> [HypothesisNode]
   -> [CommitteeNode]
   -> [ScoringNode]
   -> [BlueprintNode]
   (sem ResolveEntityNode — identidade ja estabelecida)
5. Apos reprocessamento: recalcular DSS com nova evidencia
   -> Se DSS > 0.10 apos reativacao: retornar a modo FULL
   -> Se DSS ainda < 0.05: retornar a Delta Search apos este ciclo
```

**Politica por urgency_level:**
- `ALTA`: reativacao automatica imediata (SQS message sent sem aprovacao manual)
- `MEDIA`: reativacao automatica com delay de 2h
- `BAIXA`: fila de revisao manual via dashboard de operador; nao aciona SQS automaticamente

---

### 4.4 Delta Search NAO Contamina o DSS Global

**Regra de exclusao:** leads em `search_mode='DELTA'` ou `search_mode='DELTA_ACTIVE'` sao **excluidos** do calculo global do DSS do ciclo. Suas evidencias nao sao contabilizadas em `E_new(W)` nem em `E_total(W)`.

**Justificativa:** o DSS global mede a saturacao do pipeline de descoberta sobre o universo de leads ativamente investigados. Incluir evidencias de Delta Search (que por definicao sao escassas — 0-1 evidencia nova por check) inflacionaria artificialmente `E_new` ou depressionaria DSS global de forma enganosa.

**Implementacao:**
```python
def add_evidence_to_dss(
    self,
    content_hash: str,
    is_new: bool,
    lead_search_mode: str
) -> float:
    # Exclusao explicita de leads em Delta Search
    if lead_search_mode in ("DELTA", "DELTA_ACTIVE"):
        return self._current_dss  # Retorna DSS atual sem modificacao

    return self.add_evidence(content_hash, is_new)
```

---

### 4.5 Implementacao da Janela Deslizante

O `DSSCalculator` utiliza `collections.deque(maxlen=W)` para manter a janela deslizante com complexidade O(1) por insercao e O(W) para calculo do DSS:

```python
from collections import deque
from typing import Optional

class DSSCalculator:
    W: int = 50
    DELTA: float = 0.05
    N_CONSECUTIVE: int = 2

    def __init__(self):
        # Janela deslizante: guarda os ultimos W content_hashes processados
        self._window: deque[str] = deque(maxlen=self.W)

        # Conjunto de hashes conhecidos de ciclos anteriores (seed de E_known)
        self._historical_hashes: set[str] = set()

        # Hashes adicionados na janela atual que sao novos
        self._new_hashes_in_window: set[str] = set()

        # Contador de janelas consecutivas abaixo de delta
        self._consecutive_below: int = 0

        # DSS atual (cached)
        self._current_dss: float = 1.0

    def seed_historical(self, known_hashes: set[str]) -> None:
        """Carrega hashes de evidencias de ciclos anteriores para o lead."""
        self._historical_hashes = known_hashes.copy()

    def add_evidence(self, content_hash: str, lead_search_mode: str = "FULL") -> float:
        """
        Adiciona evidencia a janela deslizante e recalcula DSS.
        Leads em Delta Search sao excluidos do calculo.
        Retorna DSS atual.
        """
        if lead_search_mode in ("DELTA", "DELTA_ACTIVE"):
            return self._current_dss

        # Ao deslocar a janela: remover hash que sai se era "novo"
        if len(self._window) == self.W:
            evicted_hash = self._window[0]
            self._new_hashes_in_window.discard(evicted_hash)

        self._window.append(content_hash)

        is_new = content_hash not in self._historical_hashes
        if is_new:
            self._historical_hashes.add(content_hash)
            self._new_hashes_in_window.add(content_hash)

        if len(self._window) < self.W:
            self._current_dss = 1.0
            return self._current_dss

        e_new = len(self._new_hashes_in_window)
        self._current_dss = e_new / self.W

        if self._current_dss < self.DELTA:
            self._consecutive_below += 1
        else:
            self._consecutive_below = 0

        return self._current_dss

    def is_saturated(self) -> bool:
        """True se N_CONSECUTIVE janelas consecutivas com DSS < DELTA."""
        return self._consecutive_below >= self.N_CONSECUTIVE

    @property
    def current_dss(self) -> float:
        return self._current_dss

    @property
    def window_fill_ratio(self) -> float:
        """Fracao da janela preenchida (0.0 a 1.0). < 1.0 indica fase de warm-up."""
        return len(self._window) / self.W
```

---

## 5. SOURCE QUALITY MODEL

### 5.1 Source Quality Vector (SQV_k)

Para cada fonte `k` em {INSTAGRAM, LINKEDIN, CNPJ_GOV, TAVILY}, o sistema mantém um vetor de qualidade quadridimensional:

```
SQV_k = (CRED_k, FRESH_k, COV_k, HACC_k)
```

O Source Quality Score escalar e a combinacao ponderada:
```
SQS_k = 0.35 * CRED_k + 0.25 * FRESH_k + 0.25 * COV_k + 0.15 * HACC_k
```

**Pesos justificados:**
- `CRED_k` (0.35): credibilidade historica e o fator dominante — reflete confiabilidade estrutural da fonte
- `FRESH_k` (0.25): frescor e critico para sinais comportamentais (posts, vagas) mas menos para dados cadastrais
- `COV_k` (0.25): cobertura de atributos determina completude da evidencia; fonte parcial degradada severamente
- `HACC_k` (0.15): acuracia historica (feedback do CRM) e valiosa mas acumula lentamente — peso menor no MVP

---

### 5.2 CRED_k — Credibilidade

**Definicao:** credibilidade combina o Source Reliability Score historico (SRS_k) com a taxa de erros observada (falsos positivos + falsos negativos), com suavizador Laplace "+1" no denominador:

```
CRED_k = SRS_k * (1 - (FP_k + FN_k) / (TP_k + TN_k + FP_k + FN_k + 1))
```

Onde:
- `TP_k`, `TN_k`, `FP_k`, `FN_k` — contagens acumuladas de True Positives, True Negatives, False Positives, False Negatives para inferencias baseadas na fonte `k`
- O suavizador `+1` no denominador evita `CRED_k = SRS_k * (1 - 0/0)` nas primeiras observacoes (Laplace smoothing)

**Cold start:** `CRED_k = SRS_k * (1 - 0/(0+1)) = SRS_k * 1.0 = SRS_k`

**Atualizacao:** apos cada feedback CRM (EV-18), incrementar o contador correspondente para a fonte dominante na hipotese avaliada e recalcular `CRED_k`.

**Exemplo numerico:**
```
Fonte: INSTAGRAM
SRS_k = 0.72
TP=18, TN=12, FP=4, FN=2

CRED_k = 0.72 * (1 - (4+2)/(18+12+4+2+1))
       = 0.72 * (1 - 6/37)
       = 0.72 * (1 - 0.162)
       = 0.72 * 0.838
       = 0.603
```

---

### 5.3 FRESH_k — Frescor

**Definicao:** FRESH_k mede o decaimento temporal da relevancia de uma evidencia da fonte `k`, modelado como decaimento exponencial com meia-vida `t_half_source`:

```
FRESH_k = e^(-ln(2) * Delta_t / t_half_source)
```

Onde:
- `Delta_t` — tempo decorrido desde a ultima coleta (em dias)
- `t_half_source` — meia-vida por fonte:
  - Instagram: `t_half = 3 dias` (conteudo de alta volatilidade)
  - LinkedIn: `t_half = 7 dias` (conteudo de media volatilidade)
  - CNPJ.ws: `t_half = 30 dias` (dados cadastrais raramente mudam)
  - Tavily: `t_half = 2 dias` (conteudo web de alta volatilidade)
  - Instagram em modo DEGRADED: `t_half = 0.5 dias` (cache serve dado potencialmente obsoleto)

**Exemplos:**

| Fonte | t_half | Delta_t | FRESH_k |
|---|---|---|---|
| Instagram | 3d | 0 dias (recem coletado) | e^0 = 1.00 |
| Instagram | 3d | 3 dias | e^(-0.693 * 1.0) = 0.50 |
| Instagram | 3d | 6 dias | e^(-0.693 * 2.0) = **0.25** |
| LinkedIn | 7d | 7 dias | e^(-0.693 * 1.0) = 0.50 |
| LinkedIn | 7d | 14 dias | e^(-0.693 * 2.0) = 0.25 |
| CNPJ.ws | 30d | 15 dias | e^(-0.693 * 0.5) = 0.71 |
| CNPJ.ws | 30d | 30 dias | e^(-0.693 * 1.0) = 0.50 |
| Instagram (DEGRADED) | 0.5d | 12h = 0.5d | e^(-0.693 * 1.0) = 0.50 |
| Instagram (DEGRADED) | 0.5d | 24h = 1.0d | e^(-0.693 * 2.0) = **0.25** |

**Caso concreto:** Instagram coletado ha 6 dias sem atualizacao -> `FRESH_k = 0.25`. O componente de frescor reduz o peso efetivo desta fonte a 25% de sua capacidade maxima no calculo de `SQS_k`.

---

### 5.4 COV_k — Cobertura

**Definicao:** COV_k mede a fracao de atributos esperados de uma fonte que foram de fato observados na ultima coleta:

```
COV_k = |A_observed_k| / |A_expected_k|
```

**Cold start:** se nenhuma coleta foi executada ainda, `COV_k = 0.0` por default.

**Exemplos:**

| Cenario | A_expected | A_observed | COV_k |
|---|---|---|---|
| LinkedIn coleta completa | 5 atributos (cargo, tenure, vagas, company_size, posts) | 5 | 5/5 = **1.00** |
| LinkedIn bloqueado, retorna apenas nome | 5 atributos | 1 (apenas nome da empresa) | 1/5 = **0.20** |
| Instagram: bio presente, posts ausentes (perfil privado) | 4 atributos (bio, posts, engagement, has_stories) | 1 (apenas bio) | 1/4 = **0.25** |
| CNPJ.ws completo | 6 atributos (razao_social, porte, capital_social, cnae, situacao, qsa) | 6 | 6/6 = **1.00** |
| CNPJ.ws sem QSA publico | 6 atributos | 5 (sem qsa) | 5/6 = **0.83** |

**Interpretacao pratica:** `COV_k = 0.20` para LinkedIn indica que a fonte retornou apenas fragmentos. O `SQS_k` sera severamente penalizado pelo peso de `COV_k = 0.25`.

---

### 5.5 HACC_k — Acuracia Historica Ponderada no Tempo

**Definicao:** HACC_k mede a acuracia historica da fonte `k` em gerar inferencias corretas, com ponderacao exponencial que da mais peso a ciclos recentes:

```
HACC_k = SUM_t (w_t * acc_t) / SUM_t w_t

Onde:
  w_t = e^(-lambda * (T-t))    com lambda = 0.10
  acc_t = (TP_t + TN_t) / (TP_t + TN_t + FP_t + FN_t)  no ciclo t
  T = ciclo corrente
  t = ciclos anteriores (t = 1, 2, ..., T)
```

**Cold start:** `HACC_k = 0.50` (acuracia neutra — sem dados historicos suficientes)

**Impacto do fator de esquecimento lambda=0.10:**
- Ciclo mais recente (T-t=0): `w = e^0 = 1.0`
- 5 ciclos atras (T-t=5): `w = e^(-0.5) = 0.607`
- 10 ciclos atras (T-t=10): `w = e^(-1.0) = 0.368`
- 14 ciclos atras (T-t=14): `w = e^(-1.4) = 0.247` => aproximadamente 1/4 do peso do ciclo mais recente
- **Ciclo mais recente tem 4x mais peso que ciclo de 14 periodos atras** (1.0 / 0.247 aprox 4.05)

**Exemplo numerico (5 ciclos):**

| Ciclo t | T-t | w_t = e^(-0.10*(T-t)) | acc_t | w_t * acc_t |
|---|---|---|---|---|
| T (atual) | 0 | 1.000 | 0.82 | 0.820 |
| T-1 | 1 | 0.905 | 0.75 | 0.679 |
| T-2 | 2 | 0.819 | 0.78 | 0.639 |
| T-3 | 3 | 0.741 | 0.70 | 0.519 |
| T-4 | 4 | 0.670 | 0.80 | 0.536 |
| **Total** | — | **4.135** | — | **3.193** |

```
HACC_k = 3.193 / 4.135 = 0.772
```

---

### 5.6 SQS_k — Source Quality Score (Combinado)

```
SQS_k = 0.35 * CRED_k + 0.25 * FRESH_k + 0.25 * COV_k + 0.15 * HACC_k
```

**Exemplo completo — LinkedIn em operacao normal (apos 10 ciclos de feedback):**
```
CRED_k = 0.74  (SRS=0.80, FP+FN=4, total=52+1)
FRESH_k = 0.67  (dados coletados ha 4 dias, t_half=7d -> e^(-ln2*4/7))
COV_k   = 0.90  (4.5/5 atributos em media)
HACC_k  = 0.77  (calculado na Secao 5.5)

SQS_k = 0.35 * 0.74 + 0.25 * 0.67 + 0.25 * 0.90 + 0.15 * 0.77
      = 0.259 + 0.168 + 0.225 + 0.116
      = 0.768
```

**Exemplo — LinkedIn em modo DEGRADED_LINKEDIN:**
```
CRED_k = 0.74   (nao muda — historico preservado)
FRESH_k = 0.25  (cache T-24h com t_half_degraded=12h: e^(-ln2*2) = 0.25)
COV_k   = 0.20  (apenas nome retornado — LinkedIn bloqueado)
HACC_k  = 0.77

SQS_k = 0.35 * 0.74 + 0.25 * 0.25 + 0.25 * 0.20 + 0.15 * 0.77
      = 0.259 + 0.063 + 0.050 + 0.116
      = 0.488  (queda de 0.768 para 0.488 — degradacao severa e correta)
```

---

### 5.7 SRS_k — Source Reliability Score (Derivacao do n Minimo)

```
SRS_k = ((TP_k + TN_k) / (TP_k + TN_k + FP_k + FN_k)) * (1 - e^{-0.05 * n_k})
```

**Cold start:** `SRS_k = 0.50`

**Fator de maturidade:** `(1 - e^{-0.05 * n_k})` cresce de 0 (n=0) para 1.0 (n->infinito).

**Derivacao do n minimo para SRS_k > 0.80 * accuracy_observada:**

```
(1 - e^{-0.05 * n}) > 0.80
e^{-0.05 * n} < 0.20
-0.05 * n < ln(0.20)
-0.05 * n < -1.6094
n > 1.6094 / 0.05
n > 32.19
```

**Portanto, n > 32 observacoes sao necessarias** para que o SRS_k supere 80% da acuracia observada. Com accuracy_observada = 1.0, isso significa `SRS_k > 0.80` requer ao menos 33 feedbacks CRM processados para a fonte.

**Tabela de maturidade:**

| n_k | Fator (1 - e^{-0.05n}) | SRS_k se accuracy=0.90 | SRS_k se accuracy=0.75 |
|---|---|---|---|
| 0 (cold start) | 0.000 | **cold start: 0.50** | **cold start: 0.50** |
| 10 | 0.394 | 0.354 | 0.296 |
| 20 | 0.632 | 0.569 | 0.474 |
| 33 | 0.807 | 0.727 | 0.605 |
| 50 | 0.918 | 0.827 | 0.689 |
| 100 | 0.993 | 0.894 | 0.745 |
| infinito | 1.000 | 0.900 | 0.750 |

---

### 5.8 Tabela de Atualizacao das Dimensoes do SQV_k

| Dimensao | Quando e Atualizada | Trigger | Tabela BD Destino (schema SDD-06) |
|---|---|---|---|
| `CRED_k` | Apos processamento de feedback CRM (EV-18) | `CRMFeedbackReceived` -> SQS consumer | `source_reliability` — campos `true_positives`, `true_negatives`, `false_positives`, `false_negatives` (SRS_current recalculado em trigger) |
| `FRESH_k` | Em tempo real antes de qualquer uso da evidencia | Calculo inline: `now() - last_recalculated` da fonte | Nao persiste separadamente no MVP — calculado em runtime; V1: campo adicional em `source_reliability` |
| `COV_k` | Apos cada coleta de evidencia (EV-03, EV-04, EV-05) | `EvidenceCollected` por fonte | Calculado em memória no MVP; V1: campo `coverage_last_cycle` em `source_reliability` |
| `HACC_k` | Apos processamento de feedback CRM (EV-18) | `CRMFeedbackReceived` -> SQS consumer | `source_reliability` — campo `historical_accuracy_weighted` (média exponencialmente ponderada) |
| `SRS_k` | Apos processamento de feedback CRM (EV-18) | `SRSUpdated` via EV-18 | `source_reliability` — campo `srs_current` (bounded 0.00–1.00 via CHECK constraint) |
| `SQS_k` | Calculado sob demanda por ciclo | Requisicao de `SQS_k` por qualquer no | Calculado em memória; componentes persistidos individualmente nos campos acima de `source_reliability` |

---

### 5.9 Tabela Completa de Modos Degradados

| Modo de Falha | Trigger | Resposta do Sistema | Ajuste de Parametros |
|---|---|---|---|
| **DEGRADED_LINKEDIN** | HTTP 429 x 3 em janela de 60s OU timeout >30s x 3 consecutivos | `operating_mode = 'DEGRADED_LINKEDIN'`; LinkedIn Scraper suspenso para o ciclo; fallback para Instagram-only mode | `u_additive += 0.20` em todos os atributos derivados do LinkedIn; H3 e H4 congeladas em `u = 0.80`; `t_half_linkedin = 7d` preservado para dados em cache; `COV_k(LINKEDIN) = 0.20` |
| **LinkedIn down (HTTP 5xx)** | HTTP 500/502/503 consecutivos por >5 min | Identico ao DEGRADED_LINKEDIN | Identico ao DEGRADED_LINKEDIN; adicionar `source_unavailable=True` no log para distinguir de rate-limit |
| **DEGRADED_INSTAGRAM** | HTTP 403 OU CAPTCHA detectado OU 5 falhas consecutivas de scraping | `operating_mode = 'DEGRADED_INSTAGRAM'`; Instagram Scraper suspenso; cache Redis T-24h servido | `t_half_instagram = 12h` (0.5d) no lugar de 3d; `FRESH_k(INSTAGRAM)` recalculado com nova meia-vida; `u_additive += 0.15` em atributos Instagram |
| **CACHE_ONLY (Dual-source failure)** | DEGRADED_INSTAGRAM + DEGRADED_LINKEDIN simultaneamente | `operating_mode = 'CACHE_ONLY'`; `DSS = 0.0` forcado; todos os sensores externos bloqueados (EIG := 0.0 forcado) | `p_score_confidence = 'LOW'`; blueprints marcados com `data_quality_warning=True`; `t_half` de todas as fontes calculado a partir do timestamp do cache original |
| **CNPJ.ws indisponivel** | HTTP 5xx em CNPJ.ws + timeout em ReceitaWS fallback | Emitir `CNPJUnavailableEvent`; `cnpj_resolved = False`; continuar pipeline | `COV_k(CNPJ_GOV) = 0.0`; atributos CNPJ-dependentes (porte, CNAE) mantem `u` do ciclo anterior ou `u = 0.50` (default degradado); SQS DLQ para reprocessamento posterior quando CNPJ.ws voltar |
