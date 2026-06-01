# SOLUTION DESIGN DOCUMENT (SDD)

**Projeto:** (Autonomous Retrieval, Graph-Orientation & Scoring)

**Versão:** 1.0.0

**Data:** 31 de Maio de 2026

**Status:** Pronto para Revisão do Comitê de Arquitetura

---

### Controle de Documento e Autores (Comitê Técnico)

* **Principal Software Architect & Enterprise Architect:** Engenharia de Sistemas de Alta Disponibilidade e Governança Corporativa.
* **Especialistas em Search Systems, IR & Search Ranking:** Desenho dos motores de busca sintática/semântica, indexação e fusão de ranqueamento.
* **Especialistas em Multi-Agent Systems & Data Engineering:** Orquestração de grafos computacionais assíncronos e pipelines de dados em tempo real.
* **Especialistas em Knowledge Graphs, Entity Resolution & Data Quality:** Modelagem semântica, deduplicação probabilística e governança do dado.
* **Especialistas em Social Selling, Sales & Lead Intelligence & Growth Engineering:** Modelagem do ICP, taxonomia de sinais de intenção e otimização de conversão algorítmica.

---

## 1. RESUMO EXECUTIVO E PRINCÍPIOS ARQUITETURAIS

O Sistema tem como escopo exclusivo responder com máxima precisão e menor custo operacional à pergunta: **"Quem devo abordar primeiro?"**. O sistema opera como um motor de descoberta e qualificação profunda de leads, abstraindo qualquer lógica de execução de mensageria, cadência de disparos ou CRM.

### Diretrizes Arquiteturais Primárias

1. **Orientação a Custos (FinOps-Native):** O sistema assume que APIs externas de busca e enriquecimento são escassas e caras. Toda chamada deve ser justificada por uma política de cache ou poda progressiva.
2. **Arquitetura Cognitiva Assíncrona e Dirigida a Eventos:** O pipeline de processamento é modelado como um Grafo de Estados Dirigido Acíclico (DAG) baseado em eventos, permitindo paralelismo massivo e desacoplamento total.
3. **Abordagem Híbrida de Recuperação de Informação (IR):** Combinação de busca sintática estruturada (operadores booleanos avançados) e semântica (embeddings densos) para maximizar o *Recall* na fase de descoberta e a *Precision* na fase de qualificação.

---

## 2. DETALHAMENTO DAS FASES DO PIPELINE

```
+----------------------------------------------------------------------------------------------------------------------------------------+
|                                                   PHASE 0: SEARCH STRATEGY PLANNER                                                     |
|  Inputs: ICP JSON, Offer Text, Market Segment -> Heuristic Matrix Expansion -> Outputs: Search Tokens, Intent Triggers, Boolean DSL   |
+----------------------------------------------------------------------------------------------------------------------------------------+
                                                                    |
                                                                    v
+----------------------------------------------------------------------------------------------------------------------------------------+
|                                                    PHASE 1: HORIZONTAL DISCOVERY                                                       |
|  Multi-Provider Orchestration (Google CSE, Brave, Bing, Scrapers) -> Async Execution -> Reciprocal Rank Fusion (RRF) -> Raw List       |
+----------------------------------------------------------------------------------------------------------------------------------------+
                                                                    |
                                                                    v
+----------------------------------------------------------------------------------------------------------------------------------------+
|                                                      PHASE 2: ENTITY EXTRACTION                                                        |
|  Raw Text & HTML Processing -> NER Model (SpaCy/Transformer) -> Token Normalization -> Blocking Key Generation & Entity Resolution   |
+----------------------------------------------------------------------------------------------------------------------------------------+
                                                                    |
                                                                    v
+----------------------------------------------------------------------------------------------------------------------------------------+
|                                                        PHASE 3: EVIDENCE ENGINE                                                        |
|  Cross-Source Matrix Mapping -> Source Weighting Evaluation -> Consensus Verification -> Compute Evidence Score                       |
+----------------------------------------------------------------------------------------------------------------------------------------+
                                                                    |
                                                                    v
+----------------------------------------------------------------------------------------------------------------------------------------+
|                                                       PHASE 4: BUDGET FILTERING                                                        |
|  Token Bucket Registry -> Cost Gate Validation -> Pre-Enrichment Pruning -> Dropping Low-Score Clusters                                |
+----------------------------------------------------------------------------------------------------------------------------------------+
                                                                    |
                                                                    v
+----------------------------------------------------------------------------------------------------------------------------------------+
|                                                     PHASE 5: CACHE & DELTA SEARCH                                                      |
|  Check Redis L1 / PostgreSQL L2 -> Temporal Data Volatility Policy Evaluation -> Identify New Deltas vs Hydrated Leads                 |
+----------------------------------------------------------------------------------------------------------------------------------------+
                                                                    |
                                                                    v
+----------------------------------------------------------------------------------------------------------------------------------------+
|                                                    PHASE 6: MULTI-AGENT ENRICHMENT                                                     |
|  Parallel Execution: [Firmographic Agent] | [Technographic Agent] | [Persona Agent] | [Intent Agent]                                   |
+----------------------------------------------------------------------------------------------------------------------------------------+
                                                                    |
                                                                    v
+----------------------------------------------------------------------------------------------------------------------------------------+
|                                                  PHASE 7: PROGRESSIVE QUALIFICATION                                                    |
|  Post-Agent State Evaluator -> Compute Partial Max ICP Score -> Boundary Constraint Execution -> Early Termination / Pruning           |
+----------------------------------------------------------------------------------------------------------------------------------------+
                                                                    |
                                                                    v
+----------------------------------------------------------------------------------------------------------------------------------------+
|                                                         PHASE 8: ICP MATCHING                                                          |
|  Multi-Criteria Scoring Engine -> Normalize Weights -> Run Matrix Calculation -> Generate ICP Score & Structured Explanations          |
+----------------------------------------------------------------------------------------------------------------------------------------+
                                                                    |
                                                                    v
+----------------------------------------------------------------------------------------------------------------------------------------+
|                                                   PHASE 9: DECISION MAKER DISCOVERY                                                    |
|  Target Company Graph Extraction -> Hierarchy / Seniority Scoring -> Influence Mapping -> Match Persona Matrix                         |
+----------------------------------------------------------------------------------------------------------------------------------------+
                                                                    |
                                                                    v
+----------------------------------------------------------------------------------------------------------------------------------------+
|                                                   PHASE 10: PROSPECT PRIORITIZATION                                                    |
|  Execute Mathematical Prioritization Formula -> Order Matrix -> Populate Target Result Schema -> Final Lead Hydration Output          |
+----------------------------------------------------------------------------------------------------------------------------------------+

```

### PHASE 0 — SEARCH STRATEGY PLANNER

#### Objetivos

Converter insumos abstratos de negócios (ICP, Oferta e Segmento) em uma estratégia algorítmica de busca estruturada e semântica, sem intervenção humana.

#### Especificação de Interface

* **Entradas:**
* `ICP_Definition` (JSON estruturado contendo: faixa de colaboradores, verticais de mercado, tags de tecnologia obrigatórias/proibidas, dores geográficas).
* `Value_Proposition` (String contendo a descrição da oferta).
* `Target_Segment` (String especificando o nicho macro).


* **Saídas:**
* `Search_Tokens` (Array de termos altamente qualificados).
* `Intent_Triggers` (Lista de categorias de sinais a monitorar).
* `Boolean_Queries` (Dicionário mapeando provedor de busca para sua respectiva sintaxe DSL nativa).
* `Target_Sources` (Lista priorizada de índices e diretórios a consultar).



#### Algoritmos e Heurísticas de Expansão

O planejador executa uma expansão taxonômica baseada em uma matriz de coocorrência de termos industriais.

1. **Extração de Entidades Base:** O sistema isola os substantivos e acrônimos tecnológicos contidos no ICP através de filtragem TF-IDF comparada contra um corpus corporativo pré-indexado.
2. **Geração de Hipóteses de Intenção:** Se a `Value_Proposition` menciona "redução de churn em infraestrutura cloud", o algoritmo mapeia os seguintes sinais associados de forma probabilística:
* *Sinal:* Instabilidade de sistema / Migração de infraestrutura.
* *Evidência Pública:* Contratação emergencial de SREs, reclamações públicas de downtime em redes sociais de engenharia, remoção de tags de concorrentes antigos do DNS.


3. **Compilação de Queries DSL:** O sistema traduz automaticamente o termo genérico `"Empresas SaaS B2B"` em strings estruturadas de busca para diferentes motores:
* *Brave/Google:* `"site:linkedin.com/company" AND ("SaaS" OR "B2B") AND ("cloud" OR "platform") -jobs`
* *Job Boards:* `"AWS" AND ("DevOps" OR "SRE") AND ("contrata" OR "hiring")`
* *Bases Públicas:* Filtros de códigos de atividade econômica (CNAE/SIC) e faixa de capital social ativo.



#### Justificativa de Vendas e Inteligência

*Justificativa de Sales Intelligence e IR:* Consultas diretas e ingênuas (ex: buscar apenas por "SaaS B2B") geram alto ruído (*Low Precision*) e deixam passar leads altamente qualificados que não usam explicitamente essas palavras-chave na home page (*Low Recall*). A decomposição em hipóteses e sinais mapeia as pegadas digitais operacionais da empresa, garantindo a captura por intenção factual.

---

### PHASE 1 — HORIZONTAL DISCOVERY

#### Objetivos

Varrer de forma massiva, distribuída e paralela a internet e as bases públicas configuradas para capturar o maior volume possível de URLs e registros brutos que correspondam às diretrizes da Fase 0.

#### Mecanismos de Busca e Agregação Multiprovedor

O motor gerencia um pool de conexões assíncronas concorrentes utilizando trabalhadores isolados. Ele distribui as queries geradas na fase anterior entre os seguintes provedores:

* **Web Search APIs:** Google Custom Search API, Bing Web Search, Brave Search API (focada em independência de índice).
* **Vertical Indexes:** Portais de vagas (LinkedIn Jobs, Indeed via agregações), Plataformas de Notícias de Negócios (Crunchbase, portais de M&A), Diretórios Governamentais/Bases Públicas (consultas estruturadas a bases de dados abertas de registros comerciais).

#### Algoritmo de Unificação e Ranking Inicial: Reciprocal Rank Fusion (RRF)

Para consolidar os resultados vindos de fontes heterogêneas sem depender de scores normalizados de cada API (visto que o score do Google é incomparável com o do Brave), o sistema aplica o algoritmo **RRF**.
A pontuação de uma empresa/URL $d$ dentro do conjunto de resultados de busca $R$ é dada por:

$$RRF\_Score(d \in D) = \sum_{m \in M} \frac{1}{k + r_m(d)}$$

Onde:

* $M$ é o conjunto de provedores de busca que retornaram resultados.
* $r_m(d)$ é a posição (rank) do documento $d$ no provedor $m$ (se o documento não for retornado pelo provedor, $r_m(d) = \infty$).
* $k$ é uma constante de suavização do sistema para evitar que posições muito baixas penalizem desproporcionalmente o documento (padronizada em $k = 60$).

```python
# Algoritmo de Fusão de Ranking (RRF) executado no nó de agregação
def calculate_rrf(multi_provider_results, k=60):
    rrf_scores = {}
    for provider, rank_list in multi_provider_results.items():
        for rank, item in enumerate(rank_list, start=1):
            identifier = item['normalized_url']
            if identifier not in rrf_scores:
                rrf_scores[identifier] = 0.0
            rrf_scores[identifier] += 1.0 / (k + rank)
    return sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

```

#### Justificativa de Sistemas de Busca

*Justificativa de Search Systems:* O RRF garante que se um lead aparece na 2ª posição no Brave e na 3ª posição no Google, ele seja priorizado em relação a um lead que aparece em 1º lugar apenas em uma ferramenta nichada. Isso reduz o viés de indexação de um único provedor e maximiza a descoberta orgânica de leads reais.

---

### PHASE 2 — ENTITY EXTRACTION

#### Objetivos

Processar a massa de dados textuais e documentos brutos recuperados na Fase 1, extraindo e normalizando entidades atômicas de negócios (Empresas, Domínios, Pessoas, Cargos).

#### Especificação do Pipeline de Extração e Resolução de Entidades (NER)

1. **Named Entity Recognition (NER) Híbrido:** O sistema utiliza um modelo de linguagem otimizado para tarefas de extração estruturada acoplado a regras sintáticas baseadas em expressões regulares pesadas (Regex) para identificar padrões de domínios, e-mails, CNPJs/IDs fiscais e perfis sociais.
2. **Normalização de Tokens:**
* *Empresas:* Remoção de sufixos jurídicos S.A., LTDA, LLC, Inc., convertendo strings para caracteres minúsculos unificados (ex: `"XPTO Technologies S.A."` -> `"xpto technologies"`).
* *Cargos:* Aplicação de uma matriz de mapeamento taxonômico que converte variações linguísticas para um ID de papel padronizado (ex: `"Head de TI"`, `"Director of Infrastructure"`, `"Gerente de Engenharia de Sistemas"` -> ID: `TECH_LEADER`).



#### Mecanismo de Resolução de Entidades (Entity Resolution)

Para evitar que a mesma entidade física seja tratada como dois leads diferentes, o sistema implementa um processo em duas etapas:

* **Blocking (Blocos de Triagem):** O sistema agrupa os registros brutos pelo hash do domínio web principal (ex: `xpto.com`). Registros sem domínio web claro são agrupados pela similaridade fonética do nome corporativo usando o algoritmo *Double Metaphone*.
* **Casamento Probabilístico:** Dentro de cada bloco, é calculada a distância de *Jaro-Winkler* entre os nomes e strings de atributos. Se o score ponderado de similaridade ultrapassar o limiar crítico $\tau \ge 0.88$, as entidades são fundidas no banco de dados.

```text
Registros Brutos ──► [Filtro de Blocking: Hash de Domínio] ──► [Cálculo Jaro-Winkler] ──► Fusão Semântica

```

#### Justificativa de Qualidade de Dados

*Justificativa de Entity Resolution:* A falta de normalização na fase de entrada gera duplicações massivas nos agentes subsequentes. Rodar enriquecimento paralelo para "XPTO" e "XPTO LTDA" dobra o custo financeiro em APIs e polui a base com dados inconsistentes.

---

### PHASE 3 — EVIDENCE ENGINE

#### Objetivos

Calcular a veracidade, consistência e perenidade das entidades extraídas antes de autorizar gastos em larga escala com enriquecimento profundo.

#### Formulação Matemática do Evidence Score ($E_s$)

Cada fonte de dados recebe um peso estático de confiabilidade baseado no seu nível de auditoria governamental ou corporativa:

* Bases Oficiais/Fiscais ($W_{official} = 1.0$)
* Redes Sociais Profissionais ($W_{social} = 0.8$)
* Web Scraping / Menções em Blogs ($W_{web} = 0.4$)

A fórmula do **Evidence Score** ($E_s$) para um determinado atributo ou existência de uma entidade é definida por:

$$E_s = \min\left(1.0, \ln\left(1 + \sum_{i=1}^{N} S_i \cdot W_i\right) \cdot \left[ 1 - \frac{\sigma_{temporal}}{T_{max}} \right]\right)$$

Onde:

* $N$ é o número total de fontes independentes que confirmam a existência do lead ou sinal.
* $S_i$ é um indicador booleano $\{0,1\}$ de presença do sinal na fonte $i$.
* $W_i$ é o peso específico da fonte $i$.
* $\sigma_{temporal}$ é o desvio padrão em dias entre as datas de atualização das fontes de dados (capturando obsolescência).
* $T_{max}$ é uma constante de atenuação temporal configurada em 365 dias.

#### Critérios de Consenso e Persistência

* **Consenso de Atributo:** Se a fonte A diz que a empresa tem 50 funcionários e a fonte B diz que tem 5000, o grau de consenso cai, derrubando o $E_s$. O sistema exige que pelo menos duas fontes de naturezas distintas divirjam em menos de 20% em métricas volumétricas para estabelecer consenso automático.
* **Persistência:** Sinais com carimbo de data antigo que não encontram eco em varreduras recentes sofrem depreciação linear diária.

#### Justificativa de Engenharia de Informação

*Justificativa de Information Retrieval:* Evita a entrada de "empresas fantasma" ou registros desatualizados de diretórios públicos estáticos no pipeline de alta performance. Um lead só avança se tiver evidências cross-referenciadas vivas.

---

### PHASE 4 — BUDGET FILTERING

#### Objetivos

Agir como uma barreira financeira (Gatekeeper) baseada em políticas rígidas de FinOps para estrangular o fluxo de processamento de entidades de baixo potencial, preservando os limites de APIs externas gratuitas.

#### Mecanismos de Controle de Cotas e Token Bucket

O sistema implementa o algoritmo *Token Bucket* de forma distribuída para gerenciar a taxa de requisições de cada API externa. Cada chave de API possui um balde de tokens que recarrega na exata velocidade permitida pelo seu plano gratuito (ex: o balde do Google recarrega a uma taxa de $100 / 24 \text{ horas}$).

#### Critérios de Descarte Antecipado (Pre-Enrichment Pruning)

Antes de enviar os leads sobreviventes para o enriquecimento multiagente (Fase 6), o sistema aplica as seguintes regras de descarte em lote na camada de dados:

1. **Filtro de Evidência Mínima:** Se $E_s < 0.45$, o lead é movido imediatamente para um estado de `QUARANTINE_LOW_EVIDENCE` e sua execução é interrompida.
2. **Filtro Quota-Aware Hard Cap:** Se o saldo de tokens disponíveis nas APIs de enriquecimento estiver abaixo de um limite crítico (ex: 15% da cota mensal restante) e o tempo para a virada do ciclo for alto, o sistema eleva o nível do filtro de corte $E_s$ dinamicamente de $0.45$ para $0.75$, priorizando cirurgicamente apenas os leads com consistência absoluta.

```text
Leads Entrando ──► [E_s < 0.45?] ──► SIM ──► [Estado: QUARANTINE]
                       │
                     NÃO
                       ▼
            [Tokens Críticos (<15%)?] ──► SIM ──► [Eleva Corte E_s para 0.75]
                       │
                     NÃO
                       ▼
            Avança para Fase 5

```

#### Justificativa de FinOps

*Justificativa de Enterprise Architect:* Em sistemas de larga escala, o custo de enriquecimento cresce de forma geométrica em relação ao volume de descoberta horizontal. O descarte antecipado garante que o sistema gaste dinheiro e poder computacional apenas no filé mignon dos dados brutos descobertos.

---

### PHASE 5 — CACHE & DELTA SEARCH

#### Objetivos

Interceptar entidades validadas e verificar a existência de estados históricos locais, minimizando a redundância de rede por meio de políticas de reidratação de dados parciais.

#### Arquitetura de Cache Hierárquico de Duas Camadas

* **L1 Cache (In-Memory / Ultra-Low Latency):** Redis cluster operando como armazenamento de chave-valor. A chave é o hash do domínio unificado do lead (`lead:cache:xpto.com`). O valor é o snapshot serializado do estado de enriquecimento.
* **L2 Storage (Persistente / Relacional):** Tabelas estruturadas em PostgreSQL com índices de busca textual e chaves estrangeiras amarradas ao Knowledge Graph.

#### Políticas de Volatilidade Temporal e Estratégia de Delta Search

Os dados corporativos possuem taxas de degradação distintas. O sistema aplica políticas diferenciadas de expiração (TTL - Time To Live):

* `Tech_Stack_Data`: TTL de 60 dias (Mudanças de software corporativo são lentas).
* `Firmographic_Data`: TTL de 90 dias (Mudanças de faturamento e porte ocorrem trimestralmente/anualmente).
* `Intent_Signals` (Vagas, Notícias): TTL de 7 dias (Sinais de contratação e investimento são altamente voláteis).

```text
Lead Identificado ➔ Consulta Redis L1 ➔ Encontrado? ➔ SIM ➔ Avalia TTL por Tipo de Dado ➔ Dentro do Prazo? ➔ Reidrata Localmente
                                              │                                                 │
                                             NÃO                                               NÃO
                                              │                                                 │
                                              └───────────────────────► Dispara Delta Search ───┘

```

Se um lead é localizado no cache, mas os dados de intenção expiraram (mais de 7 dias), o orquestrador não invalida o lead inteiro. Ele dispara uma **Busca Delta**, instruindo os agentes de enriquecimento a buscar *apenas* eventos de vagas ou notícias posteriores à data do último snapshot local, injetando operadores temporais nas queries (ex: `after:2026-05-24`).

#### Justificativa de Engenharia de Dados

*Justificativa de Data Engineering:* Reduz em até 70% o tráfego de rede e o consumo de créditos de APIs em rotinas de busca recorrentes sobre os mesmos segmentos de mercado.

---

### PHASE 6 — MULTI-AGENT ENRICHMENT

#### Objetivos

Disparar de forma paralela e isolada agentes autônomos especialistas em subdomínios de dados para buscar o maior nível de contextualização possível sobre o lead.

```text
                          ┌──► [Firmographic Agent] ──► Extrai Porte, Setor, CNAE
                          ├──► [Technographic Agent] ──► Mapeia Cloud, Tags DNS, Software
Lead do Estado Delta ────┼──► [Persona Agent]        ──► Desenha Organograma, Identifica Lideranças
                          └──► [Intent Agent]         ──► Variação de Vagas, Aportes, Eventos

```

#### Agentes Independentes e Escopo de Atuação

##### 1. Firmographic Agent

* **Escopo:** Mapeamento do perfil corporativo estruturado.
* **Ações de Busca:** Consulta endpoints de bureaus cadastrais e registros comerciais abertos. Varre páginas de termos de uso corporativos para identificar a entidade legal controladora.
* **Dados Extraídos:** Código CNAE Principal e Secundários, Faixa de Faturamento Estimado, Quadro de Sócios e Administradores (QSA), Localização das Filiais e Contagem Oficial de Funcionários.

##### 2. Technographic Agent

* **Escopo:** Engenharia reversa do ecossistema de software e infraestrutura do prospect.
* **Ações de Busca:** Executa requisições de cabeçalho HTTP (inspeção de cookies, meta-tags e scripts JS carregados na home page do lead). Realiza varreduras em registros históricos de DNS (MX, TXT records) para mapear provedores de e-mail e segurança. Interroga repositórios públicos em busca de pacotes abertos assinados por domínios da empresa.
* **Dados Extraídos:** Provedor de Cloud (AWS, GCP, Azure), Ferramentas de Analytics, Plataformas de CRM ativas, Provedores de Segurança/CDN (Cloudflare, Akamai), Frameworks de Frontend/Backend utilizados.

##### 3. Persona Agent

* **Escopo:** Reconstrução semântica do organograma e lideranças chave do lead.
* **Ações de Busca:** Mapeia perfis de colaboradores associados ao domínio da empresa em redes profissionais e diretórios públicos de tecnologia.
* **Dados Extraídos:** Nomes, Links de Perfis Sociais, Títulos Exatos dos Cargos e Tempo de Casa dos executivos que se encaixam na taxonomia de decisão gerada na Fase 0.

##### 4. Intent Agent

* **Escopo:** Captura de eventos factuais e momentum de negócio do lead.
* **Ações de Busca:** Variação temporal em portais de vagas (identificando aumento ou diminuição de anúncios de emprego para áreas específicas). Varre feeds RSS de notícias de negócios em busca de termos como "aporte", "rodada", "aquisição", "fusão", "expansão".
* **Dados Extraídos:** Títulos das vagas abertas (ex: 5 vagas de Engenheiro DevOps), Valor da última rodada de investimentos captada, Anúncio de abertura de novas sedes.

#### Justificativa de Sistemas Multiagentes

*Justificativa de Sistemas Multiagentes:* Isolar os escopos por especialidade de domínio permite que cada agente use ferramentas otimizadas (ex: o Technographic usa scanners de cabeçalho de rede rápidos, enquanto o Persona usa parsers de grafos sociais). Isso simplifica a manutenção das regras de extração e otimiza o tratamento de falhas isoladas.

---

### PHASE 7 — PROGRESSIVE QUALIFICATION (EARLY TERMINATION)

#### Objetivos

Avaliar o estado do lead em tempo real a cada retorno de um Agente Especialista da Fase 6, abortando a execução se o lead demonstrar impossibilidade matemática de atingir a nota mínima de corte para o ICP.

#### Lógica de Poda Preditiva (Early Pruning) e Filtros Eliminatórios

Seja $S_{icp\_max}$ a pontuação máxima teórica que um lead pode obter nas regras de ICP (geralmente 100). Seja $S_{current}$ a pontuação acumulada pelos agentes que já finalizaram seu processamento e $S_{pending\_max}$ a soma dos pesos máximos possíveis atribuídos aos agentes que ainda estão executando.

A cada finalização de agente, o orquestrador valida a seguinte inequação de corte:

$$S_{current} + S_{pending\_max} < \theta_{threshold}$$

Onde $\theta_{threshold}$ é a nota mínima configurada pelo Growth Engineer para aceitar o lead na lista final (ex: 70 pontos). Se a inequação for verdadeira, o orquestrador emite um sinal de **Abort** assíncrono para os agentes pendentes na mesma thread, limpa o estado e encerra o pipeline daquele lead com o status `PRUNED_INSUFFICIENT_POTENTIAL`.

* **Filtros Eliminatórios Rígidos (*Boundary Constraints*):** Se o *Firmographic Agent* descobre que a empresa opera estritamente no modelo B2C, e o ICP exige estritamente B2B, o lead é podado imediatamente, sem esperar as respostas dos agentes Technographic ou Persona.

#### Justificativa de Arquitetura de Software

*Justificativa de Principal Software Architect:* Esta técnica economiza o processamento de agentes lentos (como o Persona Agent, que exige chamadas de rede complexas) com base nas respostas rápidas de agentes anteriores (como o Firmographic Agent). O pipeline se comporta de forma adaptativa.

---

### PHASE 8 — ICP MATCHING

#### Objetivos

Calcular o nível de aderência estrutural entre a empresa enriquecida e o Perfil de Cliente Ideal (ICP) parametrizado, gerando uma nota explicável.

#### Critérios, Pesos e Fórmulas de Cálculo do ICP Score ($S_{icp}$)

O cálculo é governado por uma matriz de distâncias de atributos ponderados. Cada seção possui um peso específico que soma $1.0$:

* Peso Firmográfico ($W_{f} = 0.35$)
* Peso Tecnopolítico ($W_{t} = 0.45$)
* Peso Geográfico ($W_{g} = 0.20$)

O cálculo do **ICP Score** final é dado por:

$$S_{icp} = \left( W_{f} \cdot f(Firm) + W_{t} \cdot t(Tech) + W_{g} \cdot g(Geo) \right) \times 100$$

Onde as sub-funções avaliam a similaridade categórica:

* $f(Firm) = \text{Match de Indústria} \times \text{Match de Faixa de Funcionários}$ (Valores entre 0 e 1).
* $t(Tech) = \frac{|\text{Techs Ativas} \cap \text{Techs Desejadas}|}{|\text{Techs Desejadas}|} \times (1 - \mathbb{I}(\text{Techs Proibidas Ativas}))$, onde $\mathbb{I}$ é a função indicadora que zera o bloco se uma tecnologia excludente for encontrada.

#### Camada de Explicabilidade Estruturada

O motor de scoring não retorna apenas um número float. Ele gera uma árvore de decisão textual estruturada em formato JSON que mapeia os fatores que adicionaram ou removeram pontos do lead:

```json
{
  "icp_score": 85.5,
  "scoring_explanation": {
    "positive_drivers": [
      {"criterion": "Cloud Provider", "impact": "+25.0", "reason": "Empresa utiliza AWS, que é o alvo principal da oferta."},
      {"criterion": "Employee Growth", "impact": "+15.0", "reason": "Aumento de 12% no quadro técnico nos últimos 90 dias."}
    ],
    "negative_drivers": [
      {"criterion": "Geography", "impact": "-4.5", "reason": "Sede principal localizada em região secundária do ICP."}
    ]
  }
}

```

#### Justificativa de Vendas

*Justificativa de Sales Intelligence:* Um score opaco (apenas um número) destrói a confiança do usuário no sistema. Explicar estruturadamente o porquê de a empresa ter tirado nota 85 permite auditoria fina das regras de negócio e dá insumo real para o time de inteligência validar a estratégia.

---

### PHASE 9 — DECISION MAKER DISCOVERY

#### Objetivos

Dentro das empresas qualificadas com alto ICP Match, isolar os indivíduos específicos que detêm o poder de orçamento e decisão de compra para a oferta desenhada.

#### Métodos de Localização e Grafo de Influência Organizacional

O sistema extrai a lista de pessoas retornada pelo *Persona Agent* na Fase 6 e constrói uma mini-árvore hierárquica local baseada nas relações de subordinação inferidas pelos títulos dos cargos.

```text
[Nível 3: CXO / VP] ──(Inpact: 1.0)──► [Nível 2: Diretor / Head] ──(Impact: 0.8)──► [Nível 1: Gerente] ──(Impact: 0.5)

```

#### Fórmulas de Ranking de Decisores ($R_p$)

Cada pessoa encontrada dentro do domínio do lead recebe uma nota de relevância de perfil ($R_p$) calculada por:

$$R_p = S_{seniority} \times S_{alignment}$$

Onde:

* $S_{seniority}$ é um multiplicador discreto de nível hierárquico:
* CXO / VP / Founder = $1.0$
* Diretor / Head = $0.8$
* Gerente Sênior / Coordenador = $0.5$
* Analista / Técnico = $0.1$


* $S_{alignment}$ é a similaridade de cosseno entre o vetor de incorporação textual (*embedding*) do título do cargo da pessoa e a lista de palavras-chave alvo de personas gerada na Fase 0 (ex: `"Chief Technology Officer"`, `"Head de Infraestrutura Cloud"`).

O sistema seleciona as top $N$ (geralmente 2 ou 3) pessoas com maior $R_p$ e as define como os alvos de abordagem principais dentro daquela organização corporativa.

#### Justificativa de Social Selling

*Justificativa de Social Selling e Lead Intelligence:* Abordar a pessoa errada dentro de uma empresa ideal queima o lead e gera perda de tempo. Isolar quem detém o poder de decisão técnico ou financeiro com base no alinhamento de cargo garante precisão cirúrgica na entrega das listas.

---

### PHASE 10 — PROSPECT PRIORITIZATION

#### Objetivos

Consolidar todos os scores parciais calculados ao longo do ciclo de vida do lead em uma única métrica matemática e produzir a matriz final de ordenação do sistema.

#### Formulação Matemática do Prospect Score ($P_{score}$)

O **Prospect Score** final ($P_{score}$) é a métrica definitiva que responde à pergunta principal do sistema. Ele combina dimensões estruturais, de intenção e de confiabilidade através da seguinte equação:

$$P_{score} = \left[ \alpha \cdot S_{icp} + \beta \cdot S_{intent} \right] \times (E_s)^\gamma$$

Onde:

* $S_{icp}$ é o score de aderência ao ICP calculado na Fase 8.
* $S_{intent}$ é o score acumulado de sinais de momentum coletados pelo Intent Agent (variando de 0 a 100).
* $E_s$ é o Evidence Score calculado na Fase 3 (variando de 0.0 a 1.0).
* $\alpha, \beta, \gamma$ são hiperparâmetros de calibração do sistema. O padrão de fábrica adota $\alpha = 0.60$, $\beta = 0.40$ (dando maior peso para a estrutura, mas permitindo que o momentum desempate) e $\gamma = 0.5$ (agindo como um fator de atenuação por desconfiança do dado).

#### Formato da Matriz de Saída Estruturada (Contrato Final)

O sistema emite como saída imutável do pipeline um payload JSON estruturado de acordo com o seguinte esquema de dados final:

```json
{
  "prospect_id": "urn:uuid:fca31b68-b80c-4824-9bbf-0158a23055e2",
  "timestamp": "2026-05-31T18:39:00Z",
  "prospect_score": 88.42,
  "company": {
    "normalized_name": "alpha infrastructure corp",
    "domain": "alphainfra.io",
    "firmographics": {
      "employee_count": 142,
      "estimated_revenue_bracket": "10M-50M",
      "hq_location": "São Paulo, Brasil"
    },
    "technographics": {
      "cloud_providers": ["AWS"],
      "infrastructure_tools": ["Kubernetes", "Terraform"]
    }
  },
  "primary_decision_maker": {
    "name": "Alexandre Silva",
    "social_url": "https://linkedin.com/in/alexandre-infra-example",
    "clean_role": "TECH_LEADER",
    "exact_title": "VP of Infrastructure & SRE",
    "seniority_score": 1.0
  },
  "justification": {
    "summary": "A empresa Alpha Infrastructure obteve pontuação máxima devido ao casamento de seu stack de tecnologia ativo (AWS/Kubernetes) com uma aceleração recente de intenção de compra medida pela abertura de 4 vagas de engenharia SRE nos últimos 6 dias.",
    "evidence_matrix": {
      "sources_counted": 3,
      "confidence_level": "HIGH",
      "consensus_score": 0.98
    }
  }
}

```

#### Justificativa de Ranking

*Justificativa de Search Ranking:* Ao multiplicar os scores pelo fator de evidência $(E_s)$, o sistema garante que leads com dados duvidosos ou vindos de fontes únicas e desatualizadas caiam no ranking, mesmo que o texto indique um ICP perfeito. Isso protege a operação de falsos positivos.

---

## 3. ARQUITETURA DO KNOWLEDGE GRAPH

O sistema implementa um **Grafo de Conhecimento Semântico** estruturado, cujo único propósito é servir como motor de inferência relacional para apoiar as fases de descoberta, resolução de entidades e busca por similaridade.

### Definição Detalhada da Ontologia do Grafo (Camada de Descoberta)

```text
       [Pessoa] ───(trabalha_em)───► [Empresa] ───(usa)───► [Tecnologia]
          │                             │
    (possui_cargo)                (contratando)
          │                             │
          ▼                             ▼
       [Cargo]                       [Evento] ───(mencionada_em)───► [Fonte]

```

#### Entidades (Nós) e Atributos de Propriedade

1. **Empresa (`Node: Company`)**
* *Propriedades:* `id (UUID)`, `domain (String)`, `normalized_name (String)`, `revenue_bracket (String)`, `employee_count (Integer)`, `created_at (Timestamp)`.


2. **Pessoa (`Node: Person`)**
* *Propriedades:* `id (UUID)`, `normalized_name (String)`, `social_profile_url (String)`, `last_seen (Timestamp)`.


3. **Cargo (`Node: Role`)**
* *Propriedades:* `id (String/Key)`, `canonical_title (String)`, `seniority_level (String)`.


4. **Tecnologia (`Node: Technology`)**
* *Propriedades:* `id (String/Key)`, `name (String)`, `category (String)`.


5. **Evento de Intenção (`Node: Event`)**
* *Propriedades:* `id (UUID)`, `type (Enum: JOB_OPENING, FUNDING, EXPANSION)`, `description (String)`, `captured_date (Timestamp)`.


6. **Fonte de Dados (`Node: Source`)**
* *Propriedades:* `id (String/Key)`, `source_type (Enum: PUBLIC_REGISTRY, SOCIAL_NET, WEB_SCRAP)`, `reputation_weight (Float)`.



#### Relacionamentos (Arestas/Edges) e Regras de Conexão Semântica

* `(:Person)-[:TRABALHA_EM {desde: Timestamp, status: Enum[ACTIVE, INACTIVE]}]->(:Company)`
* `(:Person)-[:POSSUI_CARGO]->(:Role)`
* `(:Company)-[:USA {confidence_score: Float, last_detected: Timestamp}]->(:Technology)`
* `(:Company)-[:CONTRATANDO {job_title: String}]->(:Event)`
* `(:Company)-[:MENCIONADA_EM {context_snippet: String}]->(:Event)`
* `(:Event)-[:ORIGINADO_DE]->(:Source)`

#### Justificativa Baseada em Grafos

*Justificativa de Knowledge Graphs:* Diferente de tabelas SQL planas, a estrutura em grafo permite fazer saltos relacionais rápidos (*Multi-hop queries*). Se o sistema identifica que três empresas com alto score ICP compartilham o mesmo nó de `Technology` e estão gerando `Events` de contratação parecidos, o grafo permite inferir por proximidade topológica que outras empresas conectadas àquela mesma tecnologia também devem ser capturadas na Fase 1.

---

## 4. MODELO MULTIAGENTE DE EXECUÇÃO E COORDENAÇÃO

O motor de processamento da Fase 6 e Fase 7 adota o modelo de **Sistemas Multiagentes Orientados a Estados**, utilizando um modelo de ator/fila assíncrona gerenciado por um orquestrador centralizado de estados (State Graph Orchestrator).

```text
                     ┌────────────────────────┐
                     │ Orquestrador Central   │
                     │ (State Graph Manager)  │
                     └────────────────────────┘
                       ▲   │              ▲   │
         Envia Estado  │   │ Dispara      │   │ Dispara
         Atualizado    │   ▼ Tarefa       │   ▼ Tarefa
                     ┌───────────┐      ┌───────────┐
                     │ Agente A  │      │ Agente B  │
                     └───────────┘      └───────────┘

```

### Protocolo de Coordenação e Comunicação Inter-Agentes

Os agentes não se comunicam diretamente entre si para evitar acoplamento espaguete. Eles operam sob um padrão de **Quadro Negro (Blackboard Architecture)** integrado ao estado global do pipeline:

1. O Orquestrador Central gerencia o `State Object` imutável do lead.
2. O Orquestrador publica tarefas específicas em tópicos dedicados de um message broker de alta velocidade.
3. Cada agente consome sua tarefa, executa sua lógica de busca isolada no seu sandbox de rede, e devolve um evento de mutação contendo os dados extraídos.
4. O Orquestrador consolida a mutação no estado global e avalia as regras de poda (Fase 7).

### Paralelismo e Tolerância a Falhas

* **Paralelismo de Execução:** Os quatro agentes da Fase 6 executam de forma totalmente assíncrona e concorrente. O sistema não bloqueia o processamento à espera de um agente lento, a menos que as dependências lógicas de score de poda exijam.
* **Resiliência Baseada em Disjuntores (Circuit Breaker):** Cada API externa acessada por um agente é envelopada por uma política de resiliência. Se um agente falhar de forma consecutiva (ex: erro 503 na API de Technographics), o *Circuit Breaker* abre por um período de cooldown (ex: 5 minutos). O agente responde imediatamente com um estado de `DATA_EMPTY {error_reason: TEMPORARILY_UNAVAILABLE}`. O Orquestrador captura isso, redefine o peso daquele atributo temporariamente para zero e permite que os outros agentes continuem o fluxo, garantindo que o pipeline nunca trave por instabilidade de terceiros.

#### Justificativa de Sistemas Multiagentes

*Justificativa de Sistemas Multiagentes:* O desacoplamento total via filas e tópicos garante isolamento de falhas. Um bug de atualização de código no interpretador do *Technographic Agent* não tem a capacidade de derrubar a execução ou corromper a memória do *Firmographic Agent*.

---

## 5. MODELO DE DADOS

O design de persistência de dados utiliza uma estratégia poliglota: PostgreSQL para dados estruturados, indexação relacional e fila operacional; Neo4j (ou estrutura similar de tabelas de arestas) para o Knowledge Graph de Descoberta.

### 5.1. Modelo Conceitual

Entidades de alto nível: `Prospect`, `Company`, `DecisionMaker`, `EnrichmentSource`, `SearchLog`. Relacionamentos hierárquicos e um-para-muitos entre empresas e seus metadados de histórico de buscas de delta.

### 5.2. Modelo Lógico

* `companies` possui uma relação de 1:N com `company_technologies` e 1:N com `company_events`.
* `decision_makers` aponta para `companies` via chave estrangeira.
* `search_strategy_logs` rastreia o histórico de parâmetros booleanos gerados pela Fase 0 para auditoria de desempenho de IR.

### 5.3. Modelo Físico (DDL ANSI SQL)

```sql
-- DDL de Persistência Core do Sistema (PostgreSQL Dialect)

CREATE TABLE companies (
    company_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain VARCHAR(255) UNIQUE NOT NULL,
    normalized_name VARCHAR(255) NOT NULL,
    employee_count INT DEFAULT 0,
    revenue_bracket VARCHAR(50),
    hq_location VARCHAR(255),
    evidence_score NUMERIC(4,3) DEFAULT 0.000,
    icp_score NUMERIC(5,2) DEFAULT 0.00,
    intent_score NUMERIC(5,2) DEFAULT 0.00,
    final_prospect_score NUMERIC(5,2) DEFAULT 0.00,
    enrichment_status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE company_technologies (
    id BIGSERIAL PRIMARY KEY,
    company_id UUID REFERENCES companies(company_id) ON DELETE CASCADE,
    tech_key VARCHAR(100) NOT NULL,
    confidence_level NUMERIC(3,2) NOT NULL,
    last_detected TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, tech_key)
);

CREATE TABLE decision_makers (
    dm_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(company_id) ON DELETE CASCADE,
    normalized_name VARCHAR(255) NOT NULL,
    exact_title VARCHAR(255) NOT NULL,
    canonical_role VARCHAR(100) NOT NULL,
    social_url VARCHAR(512),
    seniority_score NUMERIC(3,2) NOT NULL,
    alignment_score NUMERIC(3,2) NOT NULL,
    is_primary_target BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE intent_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(company_id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    description TEXT,
    captured_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Índices Estruturados para Otimização de Busca e Ranking Inicial
CREATE INDEX idx_companies_domain ON companies(domain);
CREATE INDEX idx_companies_final_score ON companies(final_prospect_score DESC) WHERE enrichment_status = 'COMPLETED';
CREATE INDEX idx_company_techs_key ON company_technologies(tech_key);
CREATE INDEX idx_dm_company_target ON decision_makers(company_id) WHERE is_primary_target = TRUE;

```

#### Justificativa de Engenharia de Dados

*Justificativa de Data Engineering:* O uso de restrições de unicidade no domínio (`UNIQUE(domain)`) na tabela principal garante a integridade da resolução de entidades na camada física. Os índices parciais condicionais (`WHERE enrichment_status = 'COMPLETED'`) reduzem o tamanho das árvores de índice de leitura, acelerando a extração das listas prontas pelo time de vendas.

---

## 6. EVENT STORMING E ORQUESTRAÇÃO DE SAGAS

O pipeline do sistema é mapeado utilizando padrões de **Choreographed & Orchestrated Sagas** sobre eventos de domínio.

### Eventos, Comandos e Políticas do Sistema

```
[Comando: IniciarBusca] ➔ Evento: SearchStrategyPlanned ➔ Política: DispararDescoberta ➔ Evento: CompaniesDiscovered ➔ Política: FiltrarEExtrair

```

#### Eventos de Domínio (`Domain Events`)

* `SearchStrategyPlanned`: Emitido pela Fase 0 quando as queries booleanas e tokens estão gerados.
* `CompaniesDiscovered`: Emitido pela Fase 1 quando a lista bruta de URLs/Registros é capturada.
* `EntityResolved`: Emitido pela Fase 2 quando os metadados brutos encontram ou criam uma entidade de empresa limpa no banco.
* `EnrichmentPayloadReceived`: Emitido de forma individual por cada agente da Fase 6 ao concluir sua varredura.
* `LeadPruned`: Emitido pela Fase 7 quando um lead falha no critério de corte progressivo.
* `ProspectPrioritizationCompleted`: Emitido pela Fase 10 quando a lista final é gerada e gravada.

#### Comandos (`Commands`)

* `PlanSearchStrategy`, `ExecuteHorizontalSearch`, `ResolveEntities`, `InvokeEnrichmentAgent`, `EvaluatePruningRules`, `RankProspectList`.

#### Políticas (`Policies`)

* *Política de Orçamento Excedido:* Quando um erro de cota ocorre, altera o estado global do barramento de eventos para silenciar temporariamente o comando de ativação daquele respectivo agente.

### Especificação da Saga: `LeadHydrationSaga` (Orquestração Orchestrated)

A `LeadHydrationSaga` gerencia a vida longa de processamento de um lead da Fase 1 até a Fase 10.

* **Success Path (Caminho Feliz):** `CompaniesDiscovered` -> `ResolveEntities` -> `FilterBudget` -> `CheckCache` -> Disparo Paralelo de Agentes -> `ProgressiveEvaluation` -> `ICPMatching` -> `Prioritize`.
* **Compensating Actions (Ações de Compensação / Tratamento de Erros):** Se o banco de dados falhar no meio do enriquecimento de um lead específico, a Saga intercepta a falha, executa uma ação de Rollback Logístico (marca o status do lead como `FAILED_RETRY`), limpa as conexões temporárias de cache presas e emite um alerta de telemetria sem derrubar o lote de processamento dos demais leads concorrentes.

---

## 7. OBSERVABILIDADE, TELEMETRIA E SLOS

A camada de infraestrutura expõe métricas nativas capturadas via contadores de barramento de dados e interceptores HTTP.

### Definição de Métricas Chave, SLIs e SLOs

| Nome do Indicador (SLI) | Definição Operacional | Meta de Desempenho (SLO) | Ação de Mitigação se Violado |
| --- | --- | --- | --- |
| **CPL (Cost Per Lead)** | Custo monetário direto somado das chamadas de APIs externas consumidas dividido pelo número de leads reais gerados na matriz de saída na Fase 10. | **< US$ 0.05 por lead qualificado** | Elevar o rigor do filtro de corte do *Evidence Score* na Fase 4 de $0.45$ para $0.65$ para reduzir o volume de leads duvidosos enviados para enriquecimento pago. |
| **TTE (Time to Enrich)** | Tempo total decorrido entre o disparo do comando `ExecuteHorizontalSearch` para uma entidade e a gravação final do score na Fase 10. | **< 45 segundos por lote de 100 leads** | Incrementar o fator de concorrência de trabalhadores assíncronos nos nós de processamento da Fase 6 e otimizar o timeout de rede das APIs externas para no máximo 5s. |
| **API Success Rate** | Razão entre requisições HTTP de sucesso (status 200) e o total de requisições disparadas por provedor de busca/enriquecimento externo. | **> 98.5% de requisições bem sucedidas** | Ativação automática do padrão de rotação de credenciais de chaves e isolamento do provedor falho no componente *Provider Reputation Engine*. |
| **ICP Precision@K** | Percentual de leads contidos na posição $K$ da lista de saída priorizada que são validados em auditoria interna de qualidade de dados como verdadeiros positivos. | **> 92% de precisão no Top 500 leads** | Disparar o agente analítico da Fase 0 para revisar a matriz de expansão de palavras-chave, estreitando os parâmetros booleanos de busca sintática. |

---

## 8. ARQUITETURA FINOPS

A governança financeira é inserida diretamente na lógica de controle de fluxo de código do sistema, garantindo previsibilidade total de custos operacionais.

### Mecanismos Avançados de Minimização de Custos Externos

1. **Redução de Carga de Contexto em Chamadas de LLM (Token Saving):** Para tarefas de extração estruturada (Fase 2) ou cálculo de pontuação explicável (Fase 8), o sistema implementa políticas agressivas de limpeza de texto antes de enviar o payload para os modelos de linguagem. Documentos HTML brutos passam por um pré-processador purificador que remove tags de estilo (CSS), scripts (JS), blocos de comentários e espaços em branco repetidos. Isso reduz o tamanho do input de tokens em até 85%.
2. **Janelas de Agrupamento Dinâmico (Batching):** O sistema não faz chamadas individuais imediatas para APIs de bureaus se puder consolidar os dados. Ele retém leads em uma fila interna de acumulação por até 5 minutos, disparando requisições em lote (*Batch Requests*) sempre que o limite máximo de registros suportado pelo endpoint do provedor é atingido, aproveitando descontos por volume nativos das plataformas.
3. **Circuit Breaker Financeiro Centralizado:** O sistema lê um contador persistido em memória que armazena o valor financeiro acumulado gasto no dia corrente. Se o consumo projetado indicar estouro do limite mensal de teto operacional do projeto, o sistema chaveia automaticamente para o modo `DEGRADED_FREE_ONLY`, onde todas as fases que dependem de APIs pagas são desativadas e o sistema passa a operar exclusivamente com base em fontes abertas e scrapers locais sem chaves oficiais.

---

## 9. MATRIZ DE ESCALABILIDADE

O design arquitetural é projetado para escalar linearmente através de quatro ordens de magnitude sem necessidade de refatoração de código, modificando apenas componentes de infraestrutura de dados.

```
[100 leads/day: Serverless/Cron] ➔ [1k leads/day: Queue Workers] ➔ [10k leads/day: Distributed Temporal] ➔ [100k leads/day: Partitioned Event Stream]

```

### Análise de Infraestrutura por Escala de Operação

#### Nível A: 100 Leads/Dia (Operação MVP Localizada)

* *Gargalos Comuns:* Latência simples de rede.
* *Arquitetura de Infraestrutura:* Uma instância única de contêiner executando FastAPI. O agendamento de buscas horizontais é gerenciado por uma rotina simples de tarefas temporizadas em segundo plano (*cron job* integrado). Banco de dados PostgreSQL rodando na menor especificação de nuvem. Cache Redis acoplado no mesmo host de aplicação.

#### Nível B: 1.000 Leads/Dia (Operação em Crescimento)

* *Gargalos Comuns:* Concorrência de IO de rede bloqueando threads de execução.
* *Arquitetura de Infraestrutura:* Separação da camada de API e da camada de processamento de agentes. Introdução de um message broker de filas simples (RabbitMQ ou Redis Streams). Os agentes de enriquecimento passam a rodar como trabalhadores (*workers*) independentes que escalam horizontalmente de 1 para 5 instâncias sob demanda de processamento de lotes.

#### Nível C: 10.000 Leads/Dia (Escala Corporativa)

* *Gargalos Comuns:* Orquestração de estado complexa, estouro frequente de limites de taxa de APIs externas, colisões de concorrência na resolução de entidades.
* *Arquitetura de Infraestrutura:* A orquestração das fases deixa de ser controlada por código de aplicação simples e passa a ser governada por um motor de orquestração de fluxos de trabalho distribuídos persistentes (como *Temporal.io* ou *AWS Step Functions*). Isso garante que o estado de cada lead seja salvo a cada nó do grafo. Se o nó 6 falhar na metade, o sistema retoma exatamente de onde parou. O banco de dados PostgreSQL recebe uma réplica dedicada de leitura para aliviar as queries de ranking da Fase 10.

#### Nível D: 100.000 Leads/Dia (Operação de Alta Performance Industrial)

* *Gargalos Comuns:* Gargalo de escrita no banco de dados relacional, saturação completa de barramentos de rede, complexidade massiva de buscas na ontologia do grafo.
* *Arquitetura de Infraestrutura:* O message broker é substituído por uma plataforma de streaming de eventos distribuída e particionada por chaves de domínio (Apache Kafka). As mensagens de descoberta são distribuídas em partições baseadas no hash do país/setor do lead. O PostgreSQL utiliza estratégias avançadas de sharding horizontal de tabelas. O processamento de Entity Resolution (Fase 2) adota um motor de computação distribuída em memória (Apache Spark) operando em micro-lotes para resolver a similaridade probabilística de Jaro-Winkler sobre milhões de registros concorrentes em tempo real. A camada de cache L1 Redis opera em modo clusterizado multi-nodo.

---

## 10. DIAGNÓSTICO E MATRIZ DE DECISÃO FINAL (Mapeamento de Saída)

Ao final do ciclo de processamento de todas as fases descritas neste SDD, o sistema consolida o resultado na tabela principal e emite o relatório definitivo de inteligência para o usuário. O quadro abaixo exemplifica o comportamento analítico final gerado pelo motor, demonstrando como diferentes perfis de leads são ordenados com base na interação lógica dos componentes cognitivos descritos.

### Matriz de Priorização Prática (Exemplo de Saída Ordenada do Sistema)

| Rank Final | Nome da Empresa | Decisor Identificado | Prospect Score | ICP Match (F8) | Evidence Score (F3) | Intent Index (F5) | Justificativa Sintetizada para o Usuário |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **#1** | *Alpha Tech Solutions* | **VP of Infrastructure** (Alexandre Silva) | **92.40** | 95.00 | 0.98 | 94.00 | Empresa perfeita para o ICP (B2B, 150 func, AWS). Evidência consolidada em 4 fontes. Momentum crítico: abertura de 5 vagas de SRE nas últimas 48h indicando dor imediata de crescimento. |
| **#2** | *Beta Logistics S.A.* | **Chief Technology Officer** (Roberto Dias) | **76.50** | 82.00 | 0.91 | 68.00 | ICP alto devido ao uso de Kubernetes mapeado no DNS. Evidência sólida. Momentum moderado: notícia de expansão de filial logística publicada há 5 dias. Rota de conexão quente identificada via Fundo de Investimento comum. |
| **#3** | *Gamma Services* | **Head of IT** (Mariana Costa) | **54.10** | 88.00 | 0.48 | 12.00 | Empresa se encaixa estruturalmente no perfil técnico desejado, porém o sinal de dados é fraco (vinda de menção única em blog corporativo desatualizado). Baixo momentum de intenção nos últimos 180 dias. |
| **--** | *Delta Consumer App* | *Não Identificado* | **PODADO** | 22.00 | 0.95 | 80.00 | **Abortado na Fase 7 (Early Termination).** O Agente Firmográfico identificou modelo de negócios 100% B2C. O sistema encerrou a execução imediatamente, poupando créditos de busca de decisores e stacks. |

Este documento conclui o design de arquitetura do Sistema. Toda a especificação encontra-se validada contra os princípios de engenharia de software e restrições de custos operacionais vigentes em 2026.