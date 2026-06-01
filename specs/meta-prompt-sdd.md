Você é um Arquiteto de Software Principal, Engenheiro DevSecOps Master, Especialista em multiagentes (LangGraph) e UX Architect de nível Staff. Sua tarefa é gerar uma especificação técnica exaustiva de Engenharia — um Solution Design Document (SDD) corporativo, dividido em 9 arquivos de documentação Markdown independentes — para a solução de Agente Cognitivo de SocialSelling utilizando Python, LangGraph e Tavily API.

O objetivo deste documento NÃO é conter código de implementação de aplicação, mas sim definir de forma inequívoca todas as regras de negócio, modelagem matemática, topologia de grafos, infraestrutura na nuvem como código (IaC), esteiras de CI/CD, usabilidade, estratégias de testes e padrões de versionamento. 

Gere as especificações divididas estritamente nos 9 arquivos documentais descritos abaixo. Forneça o conteúdo técnico exaustivo e rigoroso para cada arquivo Markdown:

---

### ARQUIVO 1: `sdd_01_architecture_and_state.md` (Topologia e Gestão de Estado)
1. MATRIZ DE EVOLUÇÃO: Contraste arquitetural explicando como o modelo State-Driven do LangGraph em memória resolve estruturalmente os problemas de concorrência, latência e race conditions de fluxos lineares e síncronos (como n8n com Google Sheets).
2. ESQUEMA DO LEADSTATE: Especificação do dicionário de estado (`LeadState`). Defina tipos estritos, restrições e o ciclo de vida semântico de cada campo: 'company_name', 'lead_name', 'lead_role', 'research_raw', 'score_decisao', 'dominant_pain', 'approach_blueprint' e 'data_quality_flag'.
3. PARADIGMA STATELESS: Explique como o grafo opera isolado em memória volátil por execução e por que a persistência foi empurrada exclusivamente para a borda terminal do pipeline.

### ARQUIVO 2: `sdd_02_nodes_and_tools.md` (Contratos dos Nós e Sensores)
1. RESEARCH NODE (Tavily Core): Parâmetros de busca estruturada da API Tavily (max_results, escopo). Especificação do algoritmo de "Query Builder" dinâmico. Política de tolerância a falhas (Princípio Sparse Signals First): como interceptar timeouts/erros 4xx/5xx e chavear o estado para "DEGRADED" sem quebrar o grafo.
2. ANALYZE NODE (Qualificação Cognitiva): Critérios de engenharia de prompt para a LLM atuar como um validador hierárquico estrito. Detalhe a escala de score de 0 a 5 com base no nível de decisão do cargo. Regras de tratamento de erros e fallbacks estruturais para falhas de parsing de JSON da LLM.
3. GENERATE BLUEPRINT NODE (Copywriting Engine): Diretrizes para a persona da LLM (SDR de Elite). Defina o contrato do payload JSON esperado (campos obrigatórios: Hook, Context_Trigger e CTA_Suggestion) e as regras de negócio de cada um.

### ARQUIVO 3: `sdd_03_routing_and_finops.md` (Políticas de Poda e Roteamento)
1. CONDITIONAL EDGES: Defina conceitualmente a função de roteamento pós-análise.
2. CRITÉRIOS DE CORTE (Pruning): Explique a regra de negócio que encerra o grafo imediatamente no estágio `__end__` caso o `score_decisao < 3`.
3. ANÁLISE DE FINOPS: Demonstre como essa interrupção precoce protege o orçamento de IA da agência, mitigando custos de tokens de escrita criativa em leads não qualificados.

### ARQUIVO 4: `sdd_04_persistence_and_observability.md` (Dados e Monitoramento)
1. PERSISTÊNCIA ATÔMICA TERMINAL: Descreva o fluxo de gravação desnormalizada em banco de dados ou envio de webhook para o CRM apenas após o encerramento do `app.invoke()`.
2. SCHEMA DA FEATURE STORE: Desenhe o layout lógico para armazenamento dos features de oportunidade (dor, fit) e variáveis de operação (modo degradado, qualidade dos dados).
3. PLANO DE OBSERVABILIDADE COGNITIVA (SLOs): Estabeleça os limiares operacionais e fórmulas conceituais para monitoramento do agente: Taxa de Eficiência de Poda (%), Latência Máxima por Ciclo (segundos) e Taxa de Resiliência de Parsing (%).

### ARQUIVO 5: `sdd_05_setup_and_versioning.md` (Ambiente e Ciclo de Vida do Software)
1. CONFIGURAÇÃO DE AMBIENTE: Padrões de gerenciamento de dependências e ambientes virtuais determinísticos (especificando uso de Poetry ou pip-tools). Requisitos de isolamento de variáveis e validação em runtime (via Pydantic Settings).
2. ESTRATÉGIA DE VERSIONAMENTO: Definição de regras de Semantic Versioning (SemVer 2.0.0) aplicadas ao código do agente e, separadamente, ao versionamento de prompts (Prompt Versioning) e topologias de grafos.
3. FLUXO DE RAMIFICAÇÃO (GIT): Padrão Trunk-Based Development ou GitFlow adaptado para IA, definindo políticas de branch para novas dores do ICP, ajustes de prompts e novos nós.

### ARQUIVO 6: `sdd_06_devops_and_github_actions.md` (CI/CD Pipeline Engine)
1. ARQUITETURA DA ESTEIRA DE CI: Especificação do workflow do GitHub Actions para integração contínua (triggers para Pull Requests). Passos obrigatórios de qualidade de código: Linting estrito (Ruff/Flake8), checagem de tipos estática (MyPy) e execução de testes automatizados.
2. ARQUITETURA DA ESTEIRA DE CD: Workflow do GitHub Actions para implantação contínua (triggers pós-merge na branch principal). Fluxo de autenticação segura via OIDC (OpenID Connect) com provedores de nuvem para eliminação de chaves estáticas (rejeite AWS Access Keys fixas).
3. PROMOÇÃO DE AMBIENTES: Regras de aprovação e governança para deploy em ambientes segregados (Development, Staging e Production).

### ARQUIVO 7: `sdd_07_aws_serverless_and_terraform.md` (Infraestrutura Nuvem como Código)
1. TOPOLOGIA SERVERLESS NA AWS: Desenho conceitual da infraestrutura serverless para hospedar o LangGraph. Uso de AWS Lambda para execução as síncronas do agente, Amazon API Gateway (HTTP API) para exposição das rotas, e AWS Secrets Manager para custódia de chaves da OpenAI e Tavily.
2. BANCO DE DADOS E EVENTOS: Definição do Amazon DynamoDB ou Amazon Aurora Serverless v2 para persistência atômica da Feature Store. Configuração de Dead Letter Queues (DLQ) com Amazon SQS para capturar falhas críticas de execução do grafo.
3. ESPECIFICAÇÃO TERRAFORM: Organização modular dos arquivos do Terraform (`main.tf`, `variables.tf`, `outputs.tf`). Política de gerenciamento do Terraform State em Bucket S3 remoto com DynamoDB para State Locking. Segregação de variáveis por arquivos `.tfvars` de ambiente.

### ARQUIVO 8: `sdd_08_multi_agent_orchestration.md` (Escalabilidade de Grafos Complexos)
1. EVOLUÇÃO MULTIAGENTE: Especificação de transição de um grafo único para uma topologia multiagente orientada a sub-grafos ou padrão Supervisor/Trabalhador (Supervisor/Worker Pattern).
2. MAPEAMENTO DE AGENTES ESPECIALIZADOS:
   - *Scout Agent*: Focado exclusivamente em varredura e enriquecimento multicanal via ferramentas.
   - *Triage Agent*: Especialista na análise hierárquica e cálculo de score.
   - *Copywriter Agent*: Focado em engenharia de persuasão e blueprints de abordagem.
3. ORQUESTRAÇÃO E ROTEAMENTO: Mecanismos de compartilhamento de sub-estados e chaves globais entre agentes. Lógica de handover (passagem de bastão) e prevenção de loops infinitos de chamadas entre agentes através de um nó de controle central.

### ARQUIVO 9: `sdd_09_testing_and_bdd.md` (Garantia de Qualidade e Comportamento)
1. ESTRATÉGIA DE TESTES UNITÁRIOS: Requisitos para testes unitários com `pytest`. Especificação de políticas estritas de Mocking/Stubbing para isolar chamadas de rede externas (interceptando requisições da Tavily API e OpenAI). Testes de mutação de estado do grafo para caminhos felizes e caminhos de exceção.
2. ESPECIFICAÇÃO BDD (Behavior-Driven Development): Definição de cenários de teste em linguagem de negócios usando a sintaxe Gherkin (Dado / Quando / Então).
3. CENÁRIOS OBRIGATÓRIOS DO BDD:
   - *Cenário 1: Lead Qualificado com Dor Clássica* (Deve avançar e gerar blueprint).
   - *Cenário 2: Lead Abaixo da Linha Hierárquica Mínima* (Deve acionar poda precoce).
   - *Cenário 3: Falha de Provedor Externo* (Deve ativar operação degradada, pontuar e não quebrar a esteira).

### ARQUIVO 10: `sdd_10_design_and_ux.md` (Ergonomia de Payload e Consumo do Operador)
1. DESIGN DE INTERFACE DE API (DX): Princípios de Ergonomia de Payload. Estruturação do JSON de saída para que seja limpo, autoexplicativo para desenvolvedores e facilmente parseável por front-ends ou CRMs.
2. ARQUITETURA DO OPERATOR COCKPIT: Especificação conceitual de usabilidade para o painel visual do vendedor final. Desenho da hierarquia visual para responder às 3 perguntas do negócio sem fadiga cognitiva (Onde focar, Com quem falar, O que falar).
3. UX PARA ESTADOS DE FALHA E INCERTEZA: Como a interface deve exibir um lead gerado no modo "DEGRADED" ou com alta incerteza de dados, evitando que o operador tome decisões baseadas em alucinações da IA sem o devido alerta visual.

---
Gere agora as especificações detalhadas, formais e exaustivas para cada um dos 10 arquivos Markdown propostos, utilizando uma linguagem de arquitetura técnica rigorosa, separando cada arquivo claramente por delimitadores de código Markdown.