Você é um comitê de engenharia de elite composto por: Principal Enterprise Architect, Arquiteto de Sistemas Cognitivos, Especialista em Information Retrieval (IR), Principal DevSecOps Cloud Engineer (AWS & Terraform), Staff QA Architect (BDD) e Principal Product/UX Designer. 

Sua missão é gerar um Solution Design Document (SDD) corporativo completo, exaustivo, hiper-detalhado e sem qualquer tipo de simplificação ou placeholders para a versão avançada do projeto "SocialSelling".

O sistema NÃO é um CRM, não gerencia sequências de e-mails ou cadências de contato. O escopo exclusivo do sistema é coletar evidências na web (Instagram/LinkedIn/CNPJ) e responder com precisão cirúrgica e eficiência de custos às seguintes perguntas estratégicas: "Qual empresa devo abordar primeiro?", "Quem dentro dela é o verdadeiro agente de mudança (Buying Motion Owner)?" e "Qual é o contexto comportamental individual e a hipótese de dor exata para iniciar uma abordagem personalizada?".

Gere as especificações divididas estritamente nos 12 arquivos documentais descritos abaixo. Forneça o conteúdo técnico exaustivo e rigoroso para cada arquivo Markdown, utilizando delimitadores claros de código para separá-los:

---

### ARQUIVO 1: `sdd_01_product_vision_and_core_dag.md` (Visão Geral e Fluxo Cognitivo)
1. MATRIZ DE EVOLUÇÃO ARQUITETURAL: Contraste detalhado provando como o modelo State-Driven baseado em grafos de estados em memória volátil (LangGraph Engine) elimina estruturalmente os gargalos de concorrência, latência, travas de leitura/escrita e race conditions inerentes a pipelines lineares e síncronos (como n8n acoplado de forma ingênua ao Google Sheets).
2. PIPELINE DE DATA FLOW (FASE 0 À FASE 10): Detalhe exaustivo do fluxo computacional assíncrono passo a passo, descrevendo o papel analítico de cada fase, desde o Search Strategy Planner (Fase 0) até a Prospect Prioritization (Fase 10).
3. TAXONOMIA LINGUÍSTICA DOS SETORES-CHAVE: Especificação formal do dicionário terminológico e interpretativo para os quatro setores prioritários do negócio (Escritórios de Advocacia Corporativa, Consultorias Empresariais/Financeiras, Software Houses/SaaS, e Empresas de Engenharia), mapeando como termos técnicos e operacionais são traduzidos em proxies de dor (ex: "estamos estruturando" = caos interno; "envolvida nos projetos" = incapacidade de delegar).
4. ARQUITETURA EVOLUTIVA: Mapeamento explícito da matriz de separação de capacidades entre o MVP (foco no Grafo de Estados em memória e Tavily API), V1 (introdução de meta-learning loops via crm_outcome_log, re-ranqueamento por Gradient Descent e buscas multi-hop em banco de dados), V2 (mutação 100% autônoma do contrato ICP global) e a Arquitetura Alvo idealizada.

### ARQUIVO 2: `sdd_02_mathematical_core_scoring.md` (Motores de Cálculo e Álgebra de Priorização)
Forneça os modelos conceituais, equações explícitas de cálculo, tabelas de comportamento operacional e propriedades formais para:
1. PROSPECT PRIORITY SCORE (P_score): Definição exaustiva da MatrixRankFunction:
   P_score = O_score × (1 - α × e^(-β × C_score))
   Fixe as amplitudes paramétricas regulatórias padrão (α = 0.60 e β = 4.0). Determine a tabela exata de comportamento com os 4 quadrantes operacionais resultantes: Alto-O/Baixo-C (Quadrante de Investigação Urgente, com thresholds de emissão de eventos de telemetria), Baixo-O/Alto-C (Poda/Delta Search imediata), Alto-O/Alto-C (Prioridade Máxima) e Baixo-O/Baixo-C. Defina a regra de desempate determinístico em 5 níveis estritos utilizando UUID ASC na última camada de quebra.
2. OPPORTUNITY SCORE (O_score): Equação expandida combinando as dimensões de Fit estrutural, Intent momentum, e Reachability_Hybrid, modulada pelo Freshness Decay exponencial (E_fresh). Justifique formalmente a remoção matemática do fator 'S_committee_Completeness' do O_score e sua transferência para o C_score.
3. FIT SCORE VECTORIAL: Formalização do cálculo de Similaridade Cosseno Ponderada entre o ICP Feature Vector (centroide do contrato universal) e o Company Feature Vector computado. Defina as restrições de cálculo quando dimensões do vetor ultrapassam a incerteza crítica (u > 0.50) e liste os atributos mínimos obrigatórios do MVP.
4. CONFIDENCE SCORE (C_score): Função puramente multiplicativa combinando o Resolution Confidence Score (RCS), o Data Confidence Score (C_s), o fator de Incerteza do Comitê (Uncertainty_Committee, incorporando o peso residual de S_committee_Completeness) e o produto dos scores de confiabilidade histórica das fontes (∏ SRS_k). Prove o efeito colapso quando uma fonte possui confiabilidade próxima a zero.
5. DATA CONFIDENCE SCORE (C_s) VIA ENTROPIA DE SHANNON: Equação formal calculando a dispersão de opiniões concorrentes de múltiplos provedores. Detalhe o cálculo das probabilidades p_i a partir do Source Quality Score (SQS) e trate formalmente o caso de borda limite de provedor único (m=1).
6. RESOLUTION CONFIDENCE SCORE (RCS): Lógica do algoritmo Jaro-Winkler normalizado e acoplado a multiplicadores penais discretos espaciais (λ_spatial) e cadastrais (λ_CNAE). Defina a matriz rígida de thresholds para Auto-merge, Merge candidato e Entidades distintas.
7. FRESHNESS DECAY TEMPORAL: Definição da função de atenuação exponencial e tabela exaustiva contendo a meia-vida padrão (t₁/₂) em dias para cada tipo de evidência (Instagram comment, LinkedIn job, CNPJ cadastral, etc.), incluindo o comportamento de aceleração de decaimento sob modo de operação degradada.

### ARQUIVO 3: `sdd_03_subjective_logic_and_bayesian_hypotheses.md` (Espaço Latente de Estados e Lógica Subjetiva)
1. FRAMEWORK DE PROPAGAÇÃO DE CONFIANÇA (SUBJECTIVE LOGIC): Especificação formal da Opinião Subjetiva como uma tripla ω = (b, d, u) onde b + d + u = 1. Defina matematicamente as operadores estritas de Desconto (Agent Discounting) baseadas no SRS da fonte e a Fusão de Opiniões pelo Operador de Consenso (Consensus Operator). Especifique obrigatoriamente a regra de guarda de proteção arquitetural contra o bug de divisão por zero (ZeroDivisionError) em runtime quando duas fontes possuem certeza absoluta divergente (u_A = u_B = 0). Desenhe a cadeia causal de propagação de confiança através de todas as camadas do grafo.
2. CATÁLOGO FORMAL DE HIPÓTESES (H1 A H15): Mapeamento exaustivo das 15 hipóteses de negócio suportadas (H1: Expansão Operacional, H2: Centralização Excessiva, H3: Gargalo de Liderança Intermediária, H4: Necessidade de Automação, H5: Busca por Eficiência, H6: Pré-Contratação Transformacional, H7: Crise de Retenção, H8: Pressão de Vendas, H9: Transição de Modelo, H10: Sobrecarga do Fundador, H11: Dor de Qualidade de Entrega, H12: Expansão Geográfica, H13: Pressão Regulatória, H14: Sócio Novo/Reestruturação, H15: Dor de Visibilidade/Marca). Para CADA UMA das 15 hipóteses, forneça obrigatoriamente:
   - Descrição Teórica da Dor.
   - Sinais de Superfície / Evidências de Suporte (Supporting Evidence).
   - Sinais de Contradição (Contradicting Evidence).
   - Evidências Omitidas / Ausentes (Missing Evidence) e seu impacto na Entropia.
   - Probabilidade Prior Inicial (P₀).
   - Impacto quantitativo exato no cálculo final de O_score e C_score.
3. MOTOR DE ATUALIZAÇÃO RECURSIVA: Formulação matemática da atualização bayesiana sequencial das probabilidades posteriores das hipóteses à medida que novas tuplas de evidências entram no grafo.

### ARQUIVO 4: `sdd_04_sensory_search_and_finops_stopping.md` (Descoberta Ativa e Mecanismo Investigativo)
1. PIPELINE DE DESCOBERTA HORIZONTAL: Mecanismos assíncronos multiprovedor e especificação do algoritmo Reciprocal Rank Fusion (RRF) com constante de suavização k=60 para unificação de rankings ordinais de fontes concorrentes.
2. GERENCIAMENTO DE QUERIES (EXPLORAÇÃO VS. EXPLOTAÇÃO): Mecanismo de alocação de cota de busca orientada a orçamento através do parâmetro adaptativo beta-exploration (ε-Greedy substituído por DSS dinâmico).
3. ADAPTIVE INVESTIGATION ENGINE (THE COGNITIVE STOPPING CORE): Aplicação da Divergência de Kullback-Leibler (KL Divergence) para calcular o Ganho de Informação Esperado (EIG) de cada sensor. Confrontação matemática contra o Custo Marginal de Investigação (MIC) configurado no contrato. Definição matemática e lógica da Regra de Parada Rígida (FinOps Stopping Rule) baseada no threshold τ_FinOps.
4. DELTA SEARCH MODE: Estratégia de funcionamento passivo e reativação incremental. Defina a equação do Discovery Saturation Score (DSS) em janela deslizante W=50 e os critérios rígidos de transição de estado por saturação de novidade.
5. FRAMEWORK DE QUALIDADE DE FONTES (SOURCE QUALITY MODEL): Formalização matemática do vetor SQV_k composto pelas sub-métricas de Credibility Score (CRED_k), Freshness Score (FRESH_k), Coverage Score (COV_k) e Historical Accuracy Score (HACC_k). Defina as fórmulas e os triggers de atualização das dimensões a partir de webhooks operacionais do CRM.

### ARQUIVO 5: `sdd_05_buying_committee_and_motion.md` (Mapeamento do Comitê e Detecção de Liderança Dinâmica)
1. PERSONA SCORING VECTOR (S_persona): Modelo matemático tridimensional ponderado combinando Seniority Level (escala discreta de cargo), Role Alignment Score (similaridade de cosseno de embedding semântico de cargo contra o ICP) e Engagement Frequency.
2. MÉTRICAS ESTATÍSTICAS DO COMITÊ: Equações formais para Committee Completeness (completude vacante), Committee Confidence (confiança epistemológica inversa da incerteza) e Committee Uncertainty Score (ū_committee), detalhando como esses componentes penalizam o C_score sem viciar o O_score.
3. MOTOR DE DIFERENCIAÇÃO COGNITIVA ENTRE SC E BMO: Definição de critérios comportamentais rigorosos e temporais para distinguir o Structural Champion (SC) estático do Buying Motion Owner (BMO) dinâmico (o verdadeiro agente interno de mudança que consome conteúdos de dor e interage com ferramentas). Especifique as janelas e pesos para os 4 tipos de Trigger Events comportamentais.

### ARQUIVO 6: `sdd_06_database_schema_and_graph_ready_ddl.md` (Modelo Físico de Dados Graph-Ready)
1. SEPARAÇÃO SEMÂNTICA DE TRÊS CAMADAS: Diretrizes físicas obrigatórias isolando Fatos Observados (Camada 1 - imutáveis, append-only), Inferências Geradas (Camada 2 - mutáveis, com versionamento temporal) e Hipóteses/Decisões (Camada 3 - probabilísticas, indexadas por ciclo de execução).
2. DDL ANSI SQL COMPLETO (POSTGRESQL 16+): Código SQL puro, executável e tipado para toda a solução de persistência. O DDL deve gerar obrigatoriamente as tabelas estruturadas do paradigma Graph-Ready (Nós e Arestas Atributadas):
   - `icp_contract` (com restrições de validação de soma de pesos = 1.000)
   - `hypothesis_catalog`
   - `source_reliability`
   - `entity_nodes` (com campos de tripla de opinião b, d, u e flags de qualidade de dados)
   - `entity_edges` (arestas relacionais amarrando pessoas, empresas, tecnologias e eventos com atributos de opinião subjetiva, pesos e freshness)
   - `observed_evidence` (tabela imutável de fatos brutos com chave estrangeira restrita por COLLATION idêntica para evitar falhas no planner, e campo de hash SHA-256 único)
   - `generated_inferences`
   - `evaluated_hypotheses`
   - `committee_members`
   - `behavioral_momentum_log`
   - `analytical_feature_store` (Feature Store totalmente desnormalizado separando fisicamente variáveis de Oportunidade e variáveis de Confiança, preparado com campos nulos para pgvector/embeddings na V1)
   - `search_logs`
   - `conflict_resolution_log`
   - `pruned_reason_log`
   - `crm_outcome_log` (Mesa de calibração para o loop fechado de feedback do CRM)
3. ÍNDICES DE ALTA PERFORMANCE: Criação de índices parciais, compostos B-Tree de cobertura multi-hop para aceleração de travessia relacional e índices de busca textual trigrama (`pg_trgm`) para otimização de busca de Jaro-Winkler.
4. VIEW DE OBSERVABILIDADE COGNITIVA: DDL de criação da view `v_cognitive_observability` consolidando métricas operacionais agregadas por dia.

### ARQUIVO 7: `sdd_07_event_storming_and_saga_orchestration.md` (Malha Operacional de Eventos e Padrões de Saga)
1. EVENT STORMING OPERATIONAL GRID: Matriz exaustiva contendo exatamente as 18 principais transações do sistema. A tabela deve mapear de forma rigorosa as colunas: `# ID`, `Comando (Action)`, `Evento de Domínio (Result)`, `Política de Negócio Aplicada (Business Rule)` e `Impacto Físico de Mutação DML no Banco de Dados`. Cubra todas as etapas, desde a inicialização do ciclo de busca até o recebimento do feedback do CRM e ativação do Delta Search.
2. PIPELINE DE ORQUESTRAÇÃO DE SAGA (`LeadHydrationSaga`): Desenho do fluxo de vida longa de processamento assíncrono baseado em eventos. Especifique de forma detalhada o Success Path (Caminho Feliz) e as Compensating Actions (Ações de Compensação/Rollback Logístico) quando sensores externos falham ou quando os limites rígidos de FinOps são estancados.

### ARQUIVO 8: `sdd_08_multi_agent_framework_and_cockpit_ux.md` (Orquestração de Atores e Design de Consumo)
1. TOPOLOGIA DE COORDENAÇÃO MULTIAGENTE: Especificação do padrão de Quadro Negro (Blackboard Architecture) implementado sobre o LangGraph. Forneça o contrato operacional detalhado de metas, ferramentas utilizadas, inputs, outputs, barramentos de memória e critérios de sucesso para os agentes especialistas: Scout Agent, Triage Agent e Copywriter Agent (atuando como SDR de Elite).
2. DESIGN DE INTERFACE DE API (DX ERGONOMICS): Princípios de desenho de payloads limpos e autoexplicativos. Justifique a estrutura de nesting do JSON e a tipagem das saídas para fácil consumo por front-ends ou webhooks de terceiros.
3. UX DO OPERATOR COCKPIT: Especificação funcional e de usabilidade da interface gráfica do vendedor final. Desenho da hierarquia visual focada em mitigar a fadiga cognitiva, respondendo instantaneamente às três perguntas cardinais do negócio (Onde focar, Com quem falar, O que falar) através dos blocos de Fit, Intent e Reachability.
4. GESTÃO DE FALHAS E INCERTEZA NA UX: Princípios ergonômicos para exibição visual de leads gerados sob modos degradados de operação ou com Confidence Scores baixos, definindo como o sistema deve alertar o operador (alertas visuais, tooltips explicativas e desativação de ganchos inseguros) para evitar a tomada de decisões comerciais baseadas em dados inconsistentes ou alucinações.

### ARQUIVO 9: `sdd_09_cloud_infrastructure_terraform_aws.md` (Infraestrutura Nuvem como Código Serverless)
1. TOPOLOGIA SERVERLESS NA AWS: Especificação detalhada da arquitetura na nuvem para hospedar a aplicação em modo elástico e resiliente na região `us-east-1`. Mapeie o uso de AWS Lambda para execução isolada e assíncrona do grafo LangGraph, Amazon API Gateway (HTTP API) para exposição segura de endpoints REST, AWS Secrets Manager para custódia encriptada de chaves (OpenAI, Tavily, credenciais do banco) com rotação automática, e AWS IAM configurado sob o Princípio do Menor Privilégio.
2. BANCO DE DADOS E RESILIÊNCIA ASSÍNCRONA: Integração com Amazon Aurora Serverless v2 (PostgreSQL 16) configurado com ACUs dinâmicas para absorver picos de micro-lotes do pipeline. Configuração de Amazon SQS atuando como Dead Letter Queue (DLQ) para capturar payloads de leads que falharam catastroficamente na execução do grafo, integrando alarmes do Amazon CloudWatch baseados em thresholds de erro.
3. ESPECIFICAÇÃO DE MÓDULOS TERRAFORM: Desenho da arquitetura modular do código IaC. Forneça a estrutura conceitual de arquivos (`main.tf`, `variables.tf`, `outputs.tf`), a política de armazenamento seguro do Terraform State em um bucket S3 privado com criptografia SSE-S3 e controle de travas de concorrência (State Locking) usando uma tabela do Amazon DynamoDB. Desenhe o isolamento de variáveis ambientais (Dev, Staging, Production) utilizando arquivos `.tfvars` limpos e segregados.

### ARQUIVO 10: `sdd_10_devops_ci_cd_github_actions.md` (Automação de Esteiras e Governança de Código)
1. ESTEIRA DE INTEGRAÇÃO CONTÍNUA (CI): Especificação do workflow estruturado do GitHub Actions acionado por Pull Requests na branch principal. Defina os passos sequenciais e obrigatórios de checagem de qualidade: Linting estrito e formatação de código com Ruff/Flake8, verificação estática de tipagem estrita com MyPy (configurado em modo `strict: true`) e execução automatizada da suíte de testes com PyTest. O pipeline deve quebrar o build imediatamente se qualquer asserção ou cobertura mínima falhar.
2. ESTEIRA DE IMPLANTAÇÃO CONTÍNUA (CD): Especificação do workflow para deploy automatizado acionado pós-merge na branch principal. Implemente o fluxo de segurança utilizando autenticação via OIDC (OpenID Connect / AssumeRoleWithWebIdentity) da AWS, rejeitando de forma absoluta o armazenamento de chaves estáticas (`AWS_ACCESS_KEY_ID` fixas) nos segredos do repositório.
3. GOVERNANÇA E PROMOÇÃO DE AMBIENTES: Regras estritas para promoção de código entre ambientes segregados (Development, Staging e Production) exigindo aprovações manuais obrigatórias (Environment Protection Rules) dos líderes de engenharia no GitHub e validação automática de testes de integração pós-deploy.

### ARQUIVO 11: `sdd_11_quality_assurance_testing_and_bdd.md` (Estratégia de Testes e Cenários BDD)
1. ESTRATÉGIA DE TESTES UNITÁRIOS COM PYTEST: Requisitos de engenharia para garantia de qualidade do grafo de estados. Defina as políticas estritas de isolamento de rede utilizando Mocking e Stubs (via `pytest-mock` e `responses`) para interceptar e simular payloads das APIs externas da Tavily e OpenAI, garantindo que os testes rodem de forma hermética em ambientes de CI. Especifique os testes de mutação de estado avaliando se os nós alteram o dicionário do `LeadState` conforme os contratos formais em caminhos felizes e em lançamentos de exceções.
2. ESPECIFICAÇÃO BDD (BEHAVIOR-DRIVEN DEVELOPMENT): Estruturação de testes de comportamento escritos na sintaxe canônica Gherkin (Dado / Quando / Então) para validação dos critérios de aceitação de negócios.
3. CENÁRIOS OBRIGATÓRIOS EM GHERKIN: Forneça o código Gherkin completo, inteligível e sem resumos para os seguintes cenários críticos de negócio:
   - *Cenário 1: Lead Qualificado com Dor Clássica de Centralização Excessiva* (Deve validar o score de decisão do cargo, rodar a pesquisa Tavily, casar com o ICP, avançar pela borda condicional e gerar o Conversation Blueprint completo).
   - *Cenário 2: Lead Abaixo da Linha Hierárquica Mínima* (Deve calcular score baixo no nó de análise e acionar de forma determinística a poda precoce na borda condicional, interrompendo a execução e gravando o log de poda para economizar custos de tokens).
   - *Cenário 3: Falha Crítica do Provedor de Dados Externo* (Deve simular um rate-limit ou timeout do scraper de LinkedIn, ativar de forma resiliente a política de operação degradada mudando a flag no estado, recalcular as triplas de opinião aumentando a incerteza residual `u`, processar com dados parciais do Instagram e CNPJ e persistir o lead com a flag `'DEGRADED'` no Feature Store, sem quebrar a esteira de execução).

### ARQUIVO 12: `sdd_12_xai_and_pruning_json_contracts.md` (Contratos JSON de Explicabilidade e Poda)
Forneça os esquemas de validação e payloads JSON reais de exemplo de nível de produção técnica para:
1. JSON DE EXPLICABILIDADE UNIFICADA (CONTRATO FINAL DE SAÍDA DO GRAFO): JSON real e completo mapeando a resposta estruturada para o operador comercial de Social Selling. O payload deve conter obrigatoriamente:
   - Resumo das métricas unificadas (`opportunity_score`, `confidence_score` e `priority_score` detalhando fórmulas e pesos utilizados).
   - Matriz de drivers XAI (`top_positive_signals` e `top_negative_signals` amarrados às suas respectivas evidências imutáveis, fontes e modificadores de freshness, além do bloco de `missing_evidence_impact` calculando a entropia de Shannon em bits e recomendações de mitigação).
   - Dados detalhados da entidade corporativa alvo (incluindo o cálculo do vetor de faturamento inferido por proxy e a tripla de opinião semântica da empresa).
   - Mapa completo do Buying Committee (contendo a completude e incerteza do comitê, listagem de membros com seus respectivos scores individuais `S_persona`, triplas de opinião, e a eleição clara do Buying Motion Owner via `bmo_momentum_score` diferenciado do Structural Champion).
   - O Conversation Blueprint gerado de forma determinística pelo componente formal (contendo o Hook temporal válido, Context Trigger associado, Pain Narrative com âncoras textuais na linguagem do comprador, Credibility Anchor amarrada à biblioteca de cases do segmento do contrato e a CTA Suggestion refinada por canal com contraindicações rígidas de abordagem).
   - Metadados de qualidade dos dados indicando o modo operacional ativo.
2. JSON DE PODA ESTRUTURADA (`pruned_reason_payload`): JSON real e exaustivo emitido quando as Stopping Rules ou restrições de borda de FinOps/Saturação são violadas. O contrato deve mapear o ID do evento de poda, as regras financeiras avaliadas detalhando o ratio EIG/MIC confrontado contra o threshold τ_FinOps, o valor do Discovery Saturation Score (DSS) que causou a interrupção por saturação da fronteira, os scores parciais calculados até o momento do descarte, e a configuração detalhada da transição de modo para Delta Search (intervalo de monitoramento passivo e a lista de triggers moleculares configurados para reativação futura do lead).

---
REQUISITO COMPORTAMENTAL DE GERAÇÃO: 
- Utilize estritamente a linguagem técnica, formal e rigorosa de arquitetura de software e engenharia de sistemas de IA.
- Escreva a documentação integralmente em português, mantendo termos técnicos de mercado consolidados em inglês (como *Pipeline*, *Feature Store*, *Payload*, *Trunk-Based*, etc.).
- Não resuma tabelas, não simplifique o DDL, não use comentários do tipo "// adicione o resto aqui". Gere todo o conteúdo de forma sequencial, limpa e estruturada para servir como especificação executável em nível de produção.
- Injete os dados reais do negócio contidos no contexto fornecido (<CONTEXTO_DO_PROJETO>) para parametrizar todas as variáveis, dores de ICP e blue-prints criados.