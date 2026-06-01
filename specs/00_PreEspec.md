Atue como um comitê de engenharia de elite composto por: Principal Enterprise Architect, Arquiteto de Sistemas Cognitivos, Especialista em Information Retrieval (IR) & Search Rankings, Especialista em Recommender Systems, Graph Theorist, Especialista em Bayesian Inference, Engenheiro de FinOps e Especialista em Explainable AI (XAI).

Sua missão é produzir um SDD (Solution Design Document) corporativo completo, exaustivo e sem simplificações para a versão avançada do projeto "SocialSelling".

CONTEXTO E ESCOPO RÍGIDO
O sistema NÃO é um CRM, não é uma ferramenta de automação de mensagens (outreach), não gerencia sequências de e-mails, cadências de contato ou previsão de funil de vendas. O escopo exclusivo do sistema é coletar evidências na web e responder com precisão cirúrgica e eficiência de custos às seguintes perguntas:
1. "Qual empresa devo abordar primeiro?"
2. "Quem dentro dela é o verdadeiro agente de mudança (Buying Motion Owner) e quem compõe o comitê?"
3. "Qual é o contexto comportamental individual e a hipótese de dor exata para iniciar uma abordagem personalizada?"

PRINCÍPIOS NORTEADORES MANDATÓRIOS
1. Independência de Tecnologia: Toda a especificação deve ser agnóstica em relação a fornecedores de nuvem, linguagens ou bancos de dados específicos. Foque em conceitos de IR, álgebra linear, teoria dos grafos e modelos relacionais estruturados.
2. FinOps-Native: Toda chamada de rede para sensores externos (APIs ou scraping) possui um custo marginal. O sistema deve tratar cada consulta como um investimento de risco que precisa se pagar através do ganho de informação esperado. Se uma evidência não alterar o ranking final, sua coleta deve ser abortada preventivamente (Stopping Rules).
3. Explicabilidade em Primeiro Lugar: O sistema não pode agir como uma caixa-preta. Toda nota, ranking ou descarte preventivo deve vir acompanhado por um rastro lógico de causalidade auditável.
4. Interface de Negócio com Motor Cognitivo Oculto: A interface com o usuário final deve expressar os resultados na linguagem natural de vendas (Fit, Intent, Reachability e Prospect Score), enquanto as camadas internas operam ocultas através de inferência probabilística avançada.

MODELO MATEMÁTICO CENTRAL
O sistema trata cada oportunidade como uma hipótese probabilística dentro de um espaço de estados latentes. Projete uma nova fórmula para o Prospect Score (P_score) que determine a utilidade comercial esperada por unidade de custo marginal, combinando a prontidão do comitê de compras com a intensidade da dor corporativa inferida. O P_score deve ser modulado pelo Resolution Confidence Score (RCS) da entidade e pelo Data Confidence Score (Cs) global, derivado do inverso da Entropia de Shannon (medindo a convergência ou o conflito de dados entre as fontes).

ESTRUTURA DETALHADA DOS 17 DOMÍNIOS FUNCIONAIS
Desenvolva em profundidade cada um dos seguintes domínios:

• DOMÍNIO 0: Adaptive ICP Intelligence Engine (Meta-Learning Layer)
Responsável por analisar os históricos de conversão real (CLOSED_WON), calcular o Feature Lift Attribution (L_f) de variáveis ocultas e gerar automaticamente um "ICP Implícito/Evolutivo", mutando de forma autônoma o contrato universal do ICP e recalibrando os pesos macro das dimensões do sistema.

• DOMÍNIO 1: Cognitive Search Strategy Engine
Responsável pelo algoritmo de planejamento de busca sintática e semântica. Deve conter a lógica de compilação de Queries DSL avançadas, o equilíbrio estocástico entre Exploração e Explotação (Epsilon-Greedy) e o cálculo do Search Coverage Score (SCS) via modelo estatístico de Capture-Recapture (Lincoln-Petersen) para modular o tráfego de busca e ativar o modo Delta Search (busca incremental).

• DOMÍNIO 2: Distributed Discovery & Entity Resolution
Responsável pela ingestão horizontal usando Reciprocal Rank Fusion (RRF) para mesclar rankings multiprovedor. Deve detalhar o cálculo do Resolution Confidence Score (RCS) baseado na combinação de identificadores determinísticos e similaridade de Jaro-Winkler para impedir fusões errôneas de homonímias comerciais.

• DOMÍNIO 3: Evidence Graph Architecture (Graph-Ready Model)
Responsável por modelar o repositório lógico de persistência sob a forma de vértices e arestas atributadas interconectando: Company, Person, Role, Technology, Event, Source e Clue. O modelo deve permitir saltos relacionais rápidos (Multi-hop) via chaves estrangeiras estruturadas.
O modelo deve separar explicitamente:

1. Evidências observadas
2. Inferências geradas
3. Hipóteses avaliadas

Fatos observados nunca podem ser armazenados no mesmo nível semântico das inferências produzidas pelo sistema.

O documento deve definir os mecanismos de rastreabilidade entre:

Evidence → Inference → Hypothesis → Decision

• DOMÍNIO 4: Bayesian Opportunity Engine (Companhias)
Responsável por atualizar recursivamente a probabilidade posterior de que a organização se alinha ao ICP (Fit Score) à medida que novas tuplas de evidência imutáveis são inseridas no grafo, aplicando o Teorema de Bayes e calculando a entropia de dados.
O documento deve definir explicitamente:

- Inicialização dos priors
- Atualização dos likelihoods
- Estratégias de calibração
- Tratamento de evidências conflitantes
- Evolução dos parâmetros ao longo do aprendizado

Não apenas as fórmulas.

• DOMÍNIO 5: Adaptive Investigation Engine (The Cognitive Stopping Core)
Responsável pelo cálculo do Ganho de Informação Esperado (EIG) via Divergência de Kullback-Leibler (KL Divergence) confrontado contra o Custo Marginal de Investigação (MIC) de cada sensor. Deve definir as regras de parada rígidas (Stopping Rules) por saturação de certeza ou ineficiência econômica de FinOps.
O mecanismo de investigação não deve apenas decidir se coleta mais dados.

Deve decidir qual evidência possui maior valor informacional esperado para reduzir a incerteza atual.

O documento deve definir:

- Question Selection Strategy
- Evidence Acquisition Priority
- Information Gap Ranking

inspirados em Active Learning e Information Theory.

• DOMÍNIO 6: Information Retrieval Ranking Engine
Responsável pelo re-ranqueamento em dois estágios e pela aplicação do algoritmo Maximal Marginal Relevance (MMR) para garantir o controle de diversidade e evitar a monopolização do topo do ranking por micro-nichos idênticos.

• DOMÍNIO 7: Closed-Loop Feedback Learning Mechanism
Responsável por capturar webhooks operacionais de vendas (CONTACTED, RESPONDED, MEETING_BOOKED, CLOSED_WON, CLOSED_LOST) e executar a calibração continuada das verossimilhanças (Likelihoods) do motor bayesiano por descida de gradiente suavizada.

• DOMÍNIO 8: Cognitive Explainable AI Matrix (XAI)
Responsável por traduzir a matemática interna em payloads estruturados contendo os drivers positivos, drivers negativos, sinais ausentes e análise de custos de FinOps de cada lead processado ou podado.

• DOMÍNIO 9: Persona Intelligence Engine
Responsável por modelar individualmente os profissionais mapeados na organização, aplicando o vetor de Seniority e Role Alignment para computar o Persona Scoring Vector (S_persona).

• DOMÍNIO 10: Relationship Intelligence Engine (Social Relationship Graph)
Responsável por ir além da proximidade topológica elementar e construir o Social Relationship Graph, onde cada aresta atributada entre pessoas calcula o Relationship Strength baseado em contagem de interações, recência e conexões mútuas, traçando rotas de menor resistência social (Warm Path Discovery).
O sistema não deve assumir conhecimento perfeito da estrutura de decisão.

Os papéis:

- Champion
- Influencer
- Decision Maker
- Economic Buyer
- Blocker

devem ser modelados como distribuições probabilísticas com níveis explícitos de confiança.

O documento deve definir:

- Committee Confidence Score
- Committee Completeness Score
- Committee Uncertainty Score

• DOMÍNIO 11: Buying Committee Engine
Responsável por agregar a inteligência das personas coletadas e tipificar os profissionais nos papéis de Champion, Influencer, Decision Maker, Economic Buyer e Blocker, gerando o Committee Score (S_committee) ponderado que penaliza comitês incompletos ou com potenciais detratores.

• DOMÍNIO 12: Trigger Intelligence Engine
Responsável pelo Intent Pattern Engine, identificando clusters de correlação temporal de sinais de momentum em uma janela de 14 dias (ex: Cloud Migration Pattern, Corporate Transformation Pattern) e injetando bônus multiplicadores para blindar o score contra decaimentos precoces.

• DOMÍNIO 13: Pain Intelligence Engine (Domain Knowledge)
Responsável por cruzar as evidências do grafo com matrizes de conhecimento industrial para inferir e calcular a probabilidade de dores de negócios ocultas enfrentadas pela empresa (ex: gargalos de escalabilidade, ineficiência de custos em nuvem).

• DOMÍNIO 13A: Hypothesis Intelligence Engine

Responsável por transformar evidências observadas em hipóteses explícitas de negócio.

Exemplos:

- Expansão operacional
- Centralização excessiva
- Gargalo de liderança
- Necessidade de automação
- Busca por eficiência

Cada hipótese deve possuir:

- Prior Probability
- Posterior Probability
- Supporting Evidence
- Contradicting Evidence
- Confidence Score
- Freshness Score

As hipóteses devem ser atualizadas continuamente conforme novas evidências são incorporadas ao grafo.

• DOMÍNIO 14: Persona Behavioral Intelligence Engine (Digital Twin Cognitivo)
Responsável por construir um perfil comportamental probabilístico baseado em evidências públicas observáveis.
O domínio deve operar sob o princípio Sparse Signals First.
O sistema não pode assumir disponibilidade de:
- podcasts
- newsletters
- palestras
- repositórios públicos

Essas fontes devem ser tratadas como enriquecimento opcional.
O documento deve definir estratégias degradadas de funcionamento quando apenas sinais mínimos estiverem disponíveis.

• DOMÍNIO 15: Buying Motion Intelligence Engine (The Agent of Change)
Responsável por identificar o ator interno que está efetivamente impulsionando a mudança dentro da organização corporativa. O motor deve discernir quando um tomador de decisão estático (CXO) está inerte, mas um Champion técnico (Head/Manager) está publicando ativamente sobre a dor, abrindo vagas ou interagindo com o problema de mercado, elegendo essa pessoa como o "Buying Motion Owner" prioritário para a abordagem inicial.

• DOMÍNIO 16: Adaptive Buyer Persona Learning
Camada de meta-aprendizado focada no perfil humano. O sistema deve analisar os históricos de oportunidades convertidas e aprender de forma autônoma quais personas (ex: Head of DevOps e não o CTO) iniciam e tracionam com maior taxa de sucesso o processo real de compras, gerando o "Buyer Persona Evolutivo" e ajustando os pesos de ranking hierárquico.


O Domínio 1 é responsável apenas pela geração e execução de estratégias de descoberta.
O Domínio 5 é o único responsável pela decisão investigativa adaptativa e seleção da próxima evidência.

ENTREGAS TÉCNICAS E ARTEFATOS ESPERADOS
No corpo do SDD, você deve obrigatoriamente fornecer:
1. Visão Arquitetural Consolidada do sistema, detalhando o fluxo de dados e os loops de feedback.
2. Fundamentos Matemáticos e Fórmulas Explícitas para todas as funções de scoring citadas (P_score, EIG, Entropia, Comitê, Intenção, RCS, RCS, etc.).
3. Payload JSON de Explicabilidade Unificada (Contrato Final de Saída) contendo a tradução semântica em Fit, Intent, Reachability, as features brutas extraídas, os drivers positivos/negativos, o mapa estruturado do Buying Committee com o indicador de Buying Motion Owner, a matriz de dores inferidas, o Conversation Blueprint (ganchos, hipóteses e propostas) e a auditoria financeira de FinOps com a justificativa de poda ou saturação temporal.
4. Payload JSON de Poda Estruturada (pruned_reason_payload) detalhando a fase e o limite violado que causou o descarte antecipado do lead.
5. Modelo Físico de Dados ANSI SQL (DDL Completo) estruturado para o paradigma Graph-Ready (Nós e Arestas Atributadas), incluindo a Analytical Feature Store desnormalizada para machine learning e a persistência estruturada de experimentos de busca e feedback comercial do CRM.
6. Event Storming Operational Grid mapeando a correlação de Comandos, Eventos de Domínio, Políticas de Negócio e Impacto Físico no Banco de Dados para as principais transações do sistema.
7. Plano de Observabilidade focado em eficiência cognitiva, detalhando as metas de SLO para Custo por Lead Qualificado, Taxa de Falsos Positivos de Fusão e Saturação de Investigação.

RESTRIÇÕES ARQUITETURAIS OBRIGATÓRIAS

1. O documento deve diferenciar explicitamente:

- Arquitetura Alvo (Target Architecture)
- MVP
- V1
- V2

Evite projetar todos os componentes como obrigatórios para a primeira versão.

2. Cada domínio funcional deve possuir:

- Objetivo
- Responsabilidades
- Entradas
- Saídas
- Dependências
- Critérios de ativação
- Critérios de parada
- Evolução prevista

3. Toda capacidade avançada deve indicar:

- Dados mínimos necessários
- Dados opcionais
- Comportamento sob escassez de dados

O sistema deve funcionar mesmo com sinais incompletos.

O sistema deve definir explicitamente:

- Evidence Confidence
- Source Confidence
- Entity Confidence
- Hypothesis Confidence
- Committee Confidence

A confiança deve ser propagada através do grafo.

Nenhuma inferência pode existir sem score explícito de confiança.

Para cada domínio funcional identificar:

- Agente responsável
- Objetivo
- Ferramentas utilizadas
- Entradas
- Saídas
- Memória
- Critérios de sucesso

O documento deve apresentar a topologia de coordenação entre agentes e domínios.

Arquitetura Evolutiva
Separação clara entre:

- MVP
- V1
- V2
- Arquitetura Alvo

Catálogo de Hipóteses
Lista estruturada das hipóteses de negócio suportadas pelo sistema, seus sinais observáveis, regras de atualização e impactos nos scores finais.

REQUISITOS AVANÇADOS OBRIGATÓRIOS

1. Confidence Propagation Framework
2. Temporal Intelligence Framework
3. Sensor Orchestration Framework
4. Causal Evidence Chain Model (Diferenciar explicitamente:Correlated Evidence;Contributing Evidence;Potential Cause;Confirmed Cause)
5. Learning Governance Framework
6. Prospect Decision Engine
7. Bias Prevention Framework
8. Failure Modes & Recovery Strategy

Cada framework deve conter:

- Modelo conceitual
- Modelo matemático
- Contratos
- Fluxos
- Persistência
- Observabilidade
- Evolução MVP → V1 → V2 → Target

Problema: Ausência de sinal também é informação. Exemplo:
empresa crescendo
nenhuma contratação
nenhuma transformação digital

Isso reduz hipóteses. Adicionar:
O sistema deve modelar explicitamente:
Positive Evidence
Negative Evidence
Missing Evidence
e definir impacto matemático de cada uma.

Não resuma. Não pule etapas. Forneça uma especificação robusta de nível de produção técnica.