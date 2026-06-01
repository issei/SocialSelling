# DOCUMENTO DE DESIGN DE SOLUÇÃO (SDD) — VERSÃO 1.2.0

**Projeto:** SocialSelling

**Status:** Especificação Arquitetural Homologada para Implementação Técnica

---

## 1. INTRODUÇÃO E DIRETRIZES DO PROJETO SocialSelling

O sistema **SocialSelling** foi concebido com o objetivo exclusivo de responder, com alto grau de acurácia e o menor custo operacional possível, à pergunta estratégica: **"Quem devo abordar primeiro?"**.

O escopo desta arquitetura delimita-se estritamente à descoberta, enriquecimento, validação e ordenação de prospects (empresas e seus respectivos decisores). Estão explicitamente fora do escopo deste documento quaisquer componentes de execução de mensageria, automação de *outreach*, gestão de oportunidades (CRM) ou análise de fechamento de negócios.

### Princípios Norteadores da Arquitetura

1. **Independência de Tecnologia:** Toda a especificação é agnóstica em relação a fornecedores de software, linguagens de programação ou bancos de dados específicos. O design baseia-se em conceitos matemáticos de Recuperação de Informação (IR), modelos relacionais estruturados prontos para grafos (*Graph-Ready*) e barramentos de mensageria assíncrona.
2. **Previsibilidade Financeira (FinOps-Native):** O sistema assume que a coleta de dados externos consome cotas limitadas e caras. Toda chamada de rede deve ser precedida por uma validação de cache, análise de redundância ou cálculo de relevância probabilística.
3. **Explicabilidade Estruturada:** O sistema não pode se comportar como uma caixa-preta. Toda nota gerada deve ser acompanhada por um rastro lógico de causalidade.

---

## 2. MACRODOMÍNIO 1: ICP MODELING & ADVANCED SEARCH PLANNING (SDD-002)

Este domínio é o cérebro estratégico do projeto **SocialSelling**. Sua função é transformar critérios abstratos de Perfil de Cliente Ideal (ICP) em uma malha matemática de busca adaptativa, governada por hipóteses comerciais.

```
+-----------------------------------------------------------------------------------+
|                           MACRODOMÍNIO 1: ICP MODELING                            |
|                                                                                   |
|  [ICP Humano] ──► (Contrato Universal JSON) ──► [Search Hypothesis Layer]         |
|                                                          │                        |
|                                                          ▼                        |
|  [Query DSL Compilada] ◄── (Exploração vs Explotação) ◄── [Query Budgeting Matrix] |
+-----------------------------------------------------------------------------------+

```

### 2.1. O Contrato Universal de Dados (`ICP_Criteria`)

O ponto de partida do sistema é a conversão do conhecimento de negócios em um contrato de dados rígido e computável, que serve como a única fonte de verdade para os componentes subsequentes.

```json
{
  "$schema": "https://socialselling.io/schemas/icp-criteria.v1.json",
  "icp_id": "icp_enterprise_cloud_brazil",
  "firmographics": {
    "industries": ["saas", "fintech", "e_commerce"],
    "employee_range": {"min": 100, "max": 1000},
    "geographies": {"country": "BR", "regions": ["SE", "S"]},
    "business_models": ["B2B"]
  },
  "technographics": {
    "mandatory": ["aws", "kubernetes"],
    "preferred": ["terraform", "datadog"],
    "excluded": ["cpanel", "wordpress"]
  },
  "persona_matrix": {
    "target_roles": ["CTO", "VP_INFRASTRUCTURE", "HEAD_DEVOPS"],
    "min_seniority": "MANAGEMENT_LEVEL"
  },
  "intent_triggers": ["JOB_OPENING_TECH", "FUNDING_ROUND", "EXECUTIVE_TURNOVER"]
}

```

### 2.2. A Camada de Hipóteses de Busca (*Search Hypothesis Layer*)

O sistema não realiza buscas brutas baseadas em palavras-chave isoladas. O planejador de busca mapeia o ICP contra um conjunto de **Hipóteses de Comportamento de Mercado**. Uma hipótese é uma suposição lógica de que uma empresa possui uma dor comercial solucionável com base em um conjunto de pegadas digitais.

#### Matriz de Mapeamento de Hipóteses

| ID Hipótese | Descrição Teórica da Dor | Sinais de Superfície Esperados | Fontes de Dados Primárias |
| --- | --- | --- | --- |
| **H_01** | Estresse de crescimento de infraestrutura cloud. | Contratação ativa de SREs + Aumento de vagas técnicas + Uso de AWS. | Portais de emprego, barramentos de busca web. |
| **H_02** | Substituição de legado ou migração tecnológica. | Remoção de tags antigas de servidores + Vagas mencionando termos de modernização. | Scanners de DNS, históricos de código e cabeçalhos. |
| **H_03** | Injeção de capital com foco em expansão técnica. | Notícia de aporte financeiro recente + Alteração no volume de headcount corporativo. | Portais de notícias financeiras, diários e registros públicos. |

### 2.3. Expansão Semântica, Taxonomia e Geração de Queries Booleanas

A partir das hipóteses validadas, o componente executa uma **Expansão Semântica** utilizando tabelas de equivalência taxonômica.

1. **Normalização de Termos:** O sistema expande as indústrias e tecnologias do ICP para cobrir sinônimos do mercado (ex: `saas` expande para ` "software as a service" OR "plataforma b2b" OR "cloud software"`).
2. **Compilação de Queries DSL:** O planejador traduz a combinação de atributos firmográficos, tecnológicos e de hipóteses em expressões booleanas estruturadas nativas para cada provedor de busca:
* *Sintaxe de Busca Web Geral:* `"site:linkedin.com/company" AND ("saas" OR "fintech") AND ("aws" AND "kubernetes") -jobs`
* *Sintaxe de Busca de Sinais:* `"hiring" AND ("devops" OR "sre") AND ("cloud migration" OR "microservices")`



### 2.4. Estratégia de Gerenciamento de Queries: Exploração vs. Explotação

Para garantir que o sistema descubra leads que competidores não encontram (*High Recall*) sem esgotar o orçamento de APIs em consultas redundantes (*High Precision*), o planejador divide suas rotinas de busca utilizando uma taxa adaptativa $\epsilon$ (Beta-Exploration Parameter):

* **Explotação ($1 - \epsilon$):** 80% do orçamento de consultas é alocado nas strings booleanas de maior conversão histórica (clusters de busca comprovadamente alinhados ao ICP).
* **Exploração ($\epsilon$):** 20% do orçamento é alocado em queries periféricas geradas por mutação aleatória de sinônimos de mercado e cruzamento de sinais fracos, caçando anomalias positivas de mercado.

### 2.5. Alocação de Orçamento de Busca (*Query Budgeting*) e Eficiência

Cada query gerada recebe um custo estimado de execução com base no histórico do provedor. O sistema calcula o índice de **Eficiência de Query** ($Q_e$) após cada ciclo:

$$Q_e = \frac{\text{Leads Válidos Extraídos (Passaram na Fase 2)}}{\text{Custo Monetário Total da Execução da Query}}$$

Queries cujo $Q_e$ caia abaixo de um limiar estatístico aceitável são arquivadas pelo planejador, forçando a reconfiguração automática das strings booleanas no próximo ciclo de planejamento.

---

## 3. MACRODOMÍNIO 2: DISCOVERY & EXTRACTION PIPELINE

Este macrodomínio é responsável por executar a varredura física dos ambientes digitais, consolidar os dados brutos e extrair entidades limpas, livres de duplicidade.

### 3.1. Phase 1 — Horizontal Discovery (Agregação Multiprovedor)

O motor executa de forma paralela e assíncrona as queries estruturadas na Fase 0 contra múltiplos provedores de dados independentes (motores de busca web, diretórios públicos de registro corporativo e agregadores de vagas).

#### Integração via Reciprocal Rank Fusion (RRF)

Como as respostas vêm em formatos de ranqueamento heterogêneos e incomparáveis entre si, o sistema consolida a relevância inicial das URLs corporativas identificadas aplicando a fusão de posições ordinais:

$$RRF\_Score(d \in D) = \sum_{m \in M} \frac{1}{k + r_m(d)}$$

Onde $k = 60$ e $r_m(d)$ é a posição do lead $d$ no ranking do provedor $m$. Se uma URL corporativa aparece no topo de múltiplos motores de busca independentes, seu score RRF é maximizado, definindo sua prioridade na fila de extração de entidades.

### 3.2. Phase 2 — Entity Extraction & Resolution

```
[HTML/JSON Bruto] ──► (NER Engine) ──► [Blocking Key Hash] ──► (Jaro-Winkler) ──► [Entidade Normalizada]

```

Os documentos textuais capturados na Fase 1 passam por um pipeline de normalização determinística para garantir a integridade da base de dados:

1. **Named Entity Recognition (NER) de Fronteira:** O sistema isola strings correspondentes a nomes corporativos, domínios de internet (`domain`), localizações geográficas e cargos profissionais.
2. **Geração de Chaves de Bloco (*Blocking Keys*):** Para evitar a comparação cruzada de todos os registros contra todos ($O(N^2)$), o sistema limpa o sufixo jurídico das empresas e extrai o núcleo do domínio web corporativo, gerando um hash único estável (ex: "Alpha Software S.A." com site `alpha.com` e "Alpha Tecnologia" com e-mail `contato@alpha.com` são mapeados para a mesma chave de bloco: `hash_md5(alpha.com)`).
3. **Resolução de Entidades Determinística:** Dentro de cada bloco, se os domínios forem idênticos, as entidades são unificadas automaticamente na camada de persistência. Caso haja ausência de domínio, o sistema calcula a distância de *Jaro-Winkler* entre os nomes textuais. Se o coeficiente for superior a $0.94$, os registros são fundidos sob o mesmo ID de empresa, estancando a duplicação antes do enriquecimento.

---

## 4. MACRODOMÍNIO 3: ENRICHMENT FRAMEWORK

Uma vez identificada e unificada a entidade básica da empresa, o sistema dispara os **Enrichment Workers**. Eles operam como componentes especializados, totalmente sem estado (*stateless*), consumindo filas assíncronas dedicadas.

### 4.1. Especialização dos Trabalhadores de Enriquecimento

* **Firmographic Worker:** Especialista em capturar o perfil estrutural da empresa. Acessa bureaus cadastrais estáticos e registros de juntas comerciais para extrair: Contagem de Funcionários, Faixa de Capital Social/Faturamento Estimado, Código de Atividade Econômica Oficial (CNAE/SIC) e Idade da Empresa.
* **Technographic Worker:** Especialista em engenharia reversa do stack tecnológico. Executa varreduras de DNS (registros MX, TXT) e analisa o código-fonte público da home page da empresa buscando assinaturas de scripts e tags de ferramentas.
* **Intent Worker:** Especialista em momentum. Varre portais de emprego e feeds de notícias corporativas para coletar o volume de contratações ativas, rodadas de investimento captadas e anúncios de expansão física de sedes.
* **Persona Worker:** Especialista em organograma corporativo. Mapeia as pessoas que trabalham no domínio alvo e extrai seus respectivos cargos textuais para alimentar o motor de seleção de decisores.

### 4.2. Decision Maker Ranking Engine (O Motor de Seleção de Decisores)

O *Persona Worker* pode localizar centenas de profissionais dentro de uma organização de médio ou grande porte. Para responder à pergunta "Quem abordar?", o sistema implementa o **Decision Maker Ranking Engine**, que avalia e ordena cada indivíduo com base em uma matriz de quatro dimensões ponderadas:

$$R_{dm} = \left( W_{role} \cdot S_{role} + W_{seniority} \cdot S_{seniority} + W_{recency} \cdot S_{recency} + W_{presence} \cdot S_{presence} \right)$$

#### Tabela de Atribuição de Pesos do Motor de Decisores

| Dimensão de Avaliação | Peso | Regra de Cálculo do Score do Atributo |
| --- | --- | --- |
| **Role Alignment ($S_{role}$)** | $0.40$ | Similaridade de cosseno entre o vetor textual do cargo do profissional e a lista `target_roles` do ICP (ex: "Chief Technology Officer" vs "CTO" = $1.00$). |
| **Seniority Level ($S_{seniority}$)** | $0.30$ | Nota discreta baseada na posição hierárquica inferida na Fase 0:<br>

<br>• CXO / Vice-Presidente / Fundador = $1.00$<br>

<br>• Diretor / Head = $0.80$<br>

<br>• Gerente Sênior = $0.50$<br>

<br>• Técnico / Analista = $0.10$ |
| **Time in Role ($S_{recency}$)** | $0.15$ | Tempo de casa no cargo atual. Profissionais que assumiram a cadeira nos últimos 3 meses ganham score $1.00$ (janela de mudança de fornecedores), decaindo linearmente até estabilizar em $0.50$ após 2 anos. |
| **Public Presence ($S_{presence}$)** | $0.15$ | Indicador de atividade pública e completude do perfil social. Perfis com URL validada, foto e descrição preenchida recebem $1.00$, perfis incompletos ou privados recebem $0.20$. |

O sistema seleciona os dois profissionais com o maior score $R_{dm}$ e os crava como os **Alvos Primários de Abordagem** daquela empresa.

---

## 5. MACRODOMÍNIO 4: QUALIFICATION, SCORING & EXPLAINABILITY

Este domínio reúne todas as variáveis coletadas e calcula as notas finais que governarão o ranking de priorização de Social Selling. O sistema elimina as ambiguidades tradicionais ao separar de forma matemática clara a **Qualidade da Descoberta**, a **Consistência do Perfil**, a **Aderência Estrutural** e o **Momentum de Intenção**.

```
+-----------------------------------------------------------------------------------+
|                        MACRODOMÍNIO 4: SCORING ARCHITECTURE                       |
|                                                                                   |
|  [Fase 3: Discovery Score] ──────┐                                                |
|  [Fase 3: Confidence Score] ─────┼──► [Fase 10: Prioritization Formula (Pscore)]  |
|  [Fase 4: ICP Matching Score] ───┼──► Ordenação da Lista Final "Quem Abordar?"    |
|  [Fase 4: Intent Score] ─────────┘                                                |
+-----------------------------------------------------------------------------------+

```

### 5.1. Discovery Score ($D_s$)

Mede a força bruta da descoberta na internet. O $D_s$ avalia o nível de convergência de fontes independentes que apontam para a existência daquela empresa, ponderado pelo peso estático de confiança de cada canal de origem (*Source Trust Score*, detalhado no Domínio 6).

$$D_s = \min\left(1.0, \ln\left(1 + \sum_{m \in M} ST_s(m)\right) \times \left[ 1 - \frac{\text{Idade\_Dado}_{\text{dias}}}{365} \right]\right)$$

### 5.2. Confidence Score ($C_s$)

Esta é a métrica de governança de dados do sistema. Ao contrário do $D_s$ (que mede volume de fontes), o **Confidence Score** ($C_s$) mede o **conflito e a fricção de dados** entre as fontes de enriquecimento.

Se o *Firmographic Worker* encontra a informação de que a empresa possui 50 funcionários na Fonte A, 500 funcionários na Fonte B e 1200 funcionários na Fonte C, o sistema detecta uma alta variância de dados, indicando inconsistência perfil corporativo.

A fórmula do $C_s$ avalia a dispersão estatística das variáveis numéricas críticas (headcount e faturamento):

$$C_s = D_s \times \left( 1 - \min\left(1.0, \frac{\sigma_{\text{headcount}}}{\mu_{\text{headcount}}}\right) \right) \times \left( 1 - \text{Fator\_Conflito\_Categórico} \right)$$

Onde:

* $\sigma_{\text{headcount}}$ é o desvio padrão da contagem de funcionários medida entre as fontes concorrentes.
* $\mu_{\text{headcount}}$ é a média aritmética do headcount medido.
* $\text{Fator\_Conflito\_Categórico}$ assume valor penalizador de $0.30$ se uma fonte oficial categorizar a indústria como `saas` e outra fonte cadastral categorizar como `consultoria_tradicional`.

Se todas as fontes divergirem drasticamente, o coeficiente de variação aproxima-se de 1, derrubando o $C_s$ do prospect para próximo de zero, alertando o sistema sobre a fragilidade daquele perfil de lead.

### 5.3. Intent Score ($S_{intent}$)

O **Intent Score** deixa de ser uma variável empírica e passa a ser regido por um modelo matemático estruturado que avalia quatro dimensões dos sinais capturados pelo *Intent Worker*: **Recência, Quantidade, Diversidade e Importância**.

Seja $I$ o conjunto de sinais de intenção válidos capturados para a empresa nos últimos 30 dias. O score é calculado por:

$$S_{intent} = \min\left(100.0, \sum_{i \in I} \left( Q_i \times W_i \times \frac{1}{1 + \Delta T_i} \right) \times \left[ \frac{|D_I|}{|I_{\text{total\_possível}}|} \right] \times 100\right)$$

Onde:

* $Q_i$: Quantidade de vezes que o sinal específico ocorreu (ex: volume de vagas abertas).
* $W_i$: Peso de importância estático do gatilho (ex: `FUNDING_ROUND` = $1.0$; `JOB_OPENING_TECH` = $0.60$; `BLOG_MENTION` = $0.15$).
* $\Delta T_i$: Recência medida em dias desde a captura do sinal até o momento atual. Um sinal ocorrido hoje ($\Delta T = 0$) tem impacto máximo; um sinal ocorrido há 30 dias sofre decaimento severo.
* $\frac{|D_I|}{|I_{\text{total\_possível}}|}$: Fator de Diversidade. Mede a quantidade de categorias de intenção únicas ativas em relação ao total de categorias monitoradas. Uma empresa que apresenta simultaneamente vagas de DevOps **e** uma nova rodada de investimento recebe uma nota substancialmente maior do que uma empresa que apenas abriu múltiplas vagas do mesmo tipo, caracterizando um momentum real de transformação corporativa.

### 5.4. ICP Matching Score ($S_{icp}$)

Função matricial de adequação estática ao perfil ideal teórico.

$$S_{icp} = \left( 0.40 \cdot \text{Match}_{\text{firm}} + 0.60 \cdot \text{Match}_{\text{tech}} \right) \times \mathbb{I}(\text{Filtros\_Rígidos})$$

* $\mathbb{I}(\text{Filtros\_Rígidos})$: Atua como uma poda lógica instantânea. Se o trabalhador firmográfico validar que o modelo da empresa é exclusivamente B2C, ou se o technographic localizar ferramentas proibidas (`wordpress`, `wix`), a função indicadora assume o valor $0$, zerando o $S_{icp}$.

#### Poda de Lote Progressiva (*Progressive Early Termination*)

Logo após a conclusão de cada trabalhador individual na Fase 6, o orquestrador calcula o **ICP Máximo Possível Residual**. Se o *Firmographic Worker* retornar um dado que derrube a nota estrutural do lead de tal forma que, mesmo que o *Technographic Worker* encontre o cenário perfeito, a nota final projetada não consiga ultrapassar a barreira mínima de corte do sistema (ex: nota 60), o orquestrador emite um sinal de cancelamento imediato para todas as tarefas de enriquecimento pendentes daquele lead na fila assíncrona, estancando o desperdício de créditos de API de forma preditiva.

### 5.5. Fórmula de Priorização Final do Prospect ($P_{score}$)

A ordenação final da lista de entrega para o time de Social Selling é o resultado da fusão de todos os macrodomínios de qualificação do pipeline:

$$P_{score} = \left( 0.60 \cdot S_{icp} + 0.40 \cdot S_{intent} \right) \times (C_s)^{0.5}$$

O alinhamento estrutural ($S_{icp}$) e o momentum comercial ($S_{intent}$) ditam o potencial do lead. Esse potencial é multiplicado pela raiz quadrada do **Confidence Score** ($C_s$). Se o perfil do lead for eivado de conflito de dados entre as fontes, o $C_s$ desaba, arrastando o prospect para as posições mais baixas do ranking de abordagem, protegendo a operação de dados inconsistentes ou falsos positivos.

### 5.6. Motor de Explicabilidade Estruturada (*Explainability Engine*)

O sistema traduz as equações de pontuação em um rastro de justificativa comercial legível por humanos através de uma árvore estruturada de drivers:

```json
{
  "prospect_id": "urn:uuid:7c9e12b4-3c8f-4122-811d-fa8102917aa1",
  "final_p_score": 81.25,
  "metrics_summary": {
    "icp_match_score": 92.00,
    "intent_momentum_score": 75.00,
    "confidence_score": 0.88
  },
  "justification_tree": {
    "positive_signals": [
      {
        "driver": "TECHNOGRAPHIC_MANDATORY",
        "impact": "+35.0",
        "text": "Empresa utiliza a infraestrutura exigida no ICP (AWS e Kubernetes) validada por assinaturas de cabeçalho HTTP."
      },
      {
        "driver": "INTENT_DIVERSITY",
        "impact": "+20.0",
        "text": "Alto momentum detectado: ocorrência combinada de 4 vagas de engenharia Cloud e notícia de rodada de investimento nos últimos 6 dias."
      }
    ],
    "negative_signals": [
      {
        "driver": "DATA_FRICTION_PENALTY",
        "impact": "-6.5",
        "text": "Penalização por divergência de dados: a contagem de funcionários varia entre 120 e 250 colaboradores dependendo da fonte cadastral consultada."
      }
    ]
  }
}

```

---

## 6. MACRODOMÍNIO 5: INTELLIGENCE FOUNDATION & RELATIONAL DEPLOYMENT

A infraestrutura de suporte garante persistência eficiente, inteligência de fontes e prontidão para evolução futura para grafos sem impor complexidade tecnológica na primeira versão.

### 6.1. Cache Dinâmico & Camada de Busca Incremental (*Delta Search*)

Para mitigar a redundância de chamadas de rede e o re-enriquecimento de entidades já mapeadas, o sistema implementa uma **Camada de Volatilidade Temporal** que gerencia o ciclo de vida dos snapshots de dados locais:

* **Dados Firmográficos:** TTL de 60 dias. Mudanças de porte e CNAE são raras.
* **Dados Tecnológicos:** TTL de 45 dias.
* **Dados de Intenção e Sinais:** TTL de 5 dias. Sinais de contratação e investimento envelhecem rapidamente.

#### Lógica Operacional da Busca Delta

Quando um domínio web corporativo entra no Discovery Pipeline, o sistema checa a presença do snapshot local. Se o lead existe na base relacional e os dados firmográficos e tecnológicos estão dentro do prazo do TTL, as tarefas dos respectivos trabalhadores são suprimidas.

Caso o dado de intenção esteja expirado (coletado há mais de 5 dias), o orquestrador monta uma **Tarefa Delta**: instrui o *Intent Worker* a realizar uma varredura externa injetando modificadores temporais restritos à janela de tempo que compreende a data da última atualização local e o dia corrente (ex: `after:2026-05-26`), capturando exclusivamente os novos sinais emitidos sem re-processar o histórico antigo.

### 6.2. Sistema de Reputação Dinâmica de Fontes (*Source Intelligence*)

Para evitar a dependência exclusiva de pesos estáticos de confiança nas APIs externas, o sistema armazena logs de performance de cada provedor de informação a cada ciclo de execução, mapeando três métricas de controle estrutural na camada de metadados de infraestrutura:

1. **`historical_precision`:** Percentual de dados entregues pela fonte que foram confirmados por outras vias ou que não geraram rejeição lógica nas regras do ICP (mede a taxa de lixo ou dados falsos introduzidos pela fonte).
2. **`historical_recall`:** Capacidade da fonte de trazer os dados cruciais de enriquecimento exigidos pelo sistema sem retornar payloads vazios ou nulos.
3. **`historical_conversion`:** Volume de leads provenientes daquela fonte específica que atingiram posições de topo no ranking final de priorização ($P_{score} \ge 80.00$).

Esses contadores históricos funcionam como uma camada de telemetria de auditoria de dados. No futuro, eles serão utilizados pelo *Search Strategy Planner* para reconfigurar dinamicamente a priorização de roteamento de chamadas, desligando canais de dados que geram fricção e priorizando fontes de alta conversão.

### 6.3. Modelo Relacional Pronto para Grafo (*Graph-Ready Relational Model*)

O sistema adota um design de banco de dados puramente relacional normalizado, mas estruturado sob a semântica estrita de **Tabelas de Entidades (Nós)** e **Tabelas de Associação (Arestas com Atributos)**.

Essa escolha elimina a necessidade de instalar, gerenciar e licenciar bancos de dados de grafos nativos na V1 do projeto, mantendo a simplicidade de consultas SQL estruturadas rápidas, ao mesmo tempo que garante que toda a base de conhecimento possa ser exportada para uma estrutura de grafos no futuro com custo de transformação de dados igual a zero.

#### Esquema de Persistência Conceitual-Lógico (Tabelas de Dados)

```
+-------------------+             +-----------------------------+             +-----------------+
|  node_companies   | 1         N | edge_company_employees      | N         1 |   node_persons  |
|  (Entity/Node)    | <────────── | (Relationship/Edge + Attr)  | ──────────> |  (Entity/Node)  |
+-------------------+             +-----------------------------+             +-----------------+
          │ 1                                   │ N
          │                                     ▼
          │ N                             +------------+
          ├─────────────────────────────> | node_roles |
          │                               +------------+
          │ 1                             +-------------------+
          └─────────────────────────────> | node_technologies |
                                          +-------------------+

```

##### 1. Tabela: `node_companies` (Entidade / Nó Empresa)

Armazena os atributos atômicos firmográficos consolidados após a resolução de entidades.

* `company_id`: UUID (Chave Primária)
* `domain`: VARCHAR(255) (Índice Único de Bloqueio)
* `normalized_name`: VARCHAR(255)
* `employee_count`: INT
* `revenue_bracket`: VARCHAR(50)
* `country_code`: CHAR(2)
* `business_model`: VARCHAR(20) (Ex: B2B, B2C)
* `updated_at`: TIMESTAMP

##### 2. Tabela: `node_persons` (Entidade / Nó Pessoa)

Armazena os indivíduos localizados na web de forma isolada.

* `person_id`: UUID (Chave Primária)
* `normalized_name`: VARCHAR(255)
* `social_profile_url`: VARCHAR(512) (Índice Único)

##### 3. Tabela: `node_roles` (Entidade / Nó Cargo)

Tabela de referência taxonômica de papéis corporativos.

* `role_key`: VARCHAR(100) (Chave Primária — Ex: 'CTO', 'HEAD_DEVOPS')
* `canonical_title`: VARCHAR(255)
* `seniority_level`: VARCHAR(50)

##### 4. Tabela: `node_technologies` (Entidade / Nó Tecnologia)

Dicionário de ferramentas de mercado rastreáveis.

* `tech_key`: VARCHAR(100) (Chave Primária — Ex: 'aws', 'kubernetes')
* `tech_name`: VARCHAR(150)
* `category`: VARCHAR(100)

##### 5. Tabela: `node_events` (Entidade / Nó Evento de Intenção)

Instâncias factuais de momentum coletadas no mercado.

* `event_id`: UUID (Chave Primária)
* `event_type`: VARCHAR(50) (Ex: 'JOB_OPENING', 'FUNDING_ROUND')
* `description`: TEXT
* `captured_date`: TIMESTAMP

##### 6. Tabela: `edge_company_employees` (Associação / Aresta Trabalha Em)

Conecta a pessoa à empresa, carregando os atributos específicos do vínculo identificados pelo motor de decisores.

* `company_id`: UUID (Chave Estrangeira referenciando `node_companies`)
* `person_id`: UUID (Chave Estrangeira referenciando `node_persons`)
* `role_key`: VARCHAR(100) (Chave Estrangeira referenciando `node_roles`)
* `is_primary_target`: BOOLEAN (Sinalizador do Alvo Principal de Abordagem)
* `dm_rank_score`: DECIMAL(4,2) (Nota calculada pelo Decision Maker Engine)
* *Chave Primária Composta:* `(company_id, person_id)`

##### 7. Tabela: `edge_company_technologies` (Associação / Aresta Usa)

Mapeia a infraestrutura técnica ativa de cada organização.

* `company_id`: UUID (Chave Estrangeira referenciando `node_companies`)
* `tech_key`: VARCHAR(100) (Chave Estrangeira referenciando `node_technologies`)
* `confidence_score`: DECIMAL(3,2) (Grau de certeza da detecção do Worker)
* *Chave Primária Composta:* `(company_id, tech_key)`

##### 8. Tabela: `edge_company_events` (Associação / Aresta Emitiu Sinal)

Vincula os eventos de momentum recentes às organizações correspondentes.

* `company_id`: UUID (Chave Estrangeira referenciando `node_companies`)
* `event_id`: UUID (Chave Estrangeira referenciando `node_events`)
* *Chave Primária Composta:* `(company_id, event_id)`

##### 9. Tabela: `pipeline_prospect_scores` (Tabela de Consolidação de Ranking)

Camada final de consumo do sistema, onde residem os resultados calculados e ordenados prontos para a extração do usuário.

* `company_id`: UUID (Chave Primária referenciando `node_companies`)
* `discovery_score`: DECIMAL(4,3)
* `confidence_score`: DECIMAL(4,3)
* `icp_score`: DECIMAL(5,2)
* `intent_score`: DECIMAL(5,2)
* `final_prospect_score`: DECIMAL(5,2) (Coluna de Ordenação Principal)
* `explainability_payload`: JSONB (Payload gerado pelo Motor de Explicabilidade)
* `processing_status`: VARCHAR(30) (Ex: 'STAGING', 'COMPLETED', 'PRUNED')

Esta arquitetura encerra a especificação do projeto **SocialSelling** em seu nível MVP de alta maturidade, garantindo o controle total sobre a esteira de dados, o isolamento analítico de pontuações e a prontidão evolutiva de inteligência sem adicionar riscos técnicos ou custos de desenvolvimento prematuros.