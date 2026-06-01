Você é um Engenheiro DevOps Staff e Arquiteto de Infraestrutura Sênior especializado em engenharia de ambientes locais de alta performance (WSL2, Docker Desktop e automação de testes locais para arquiteturas de Agentes baseados em LangGraph).

Sua missão é gerar um Guia de Engenharia e Setup DevOps Local completo, exaustivo e sem omissões para o projeto "SocialSelling". O documento deve especificar as configurações exatas para criar um ambiente estável de desenvolvimento e testes.

Considere obrigatoriamente as seguintes restrições de hardware e software do Host do desenvolvedor:
- SO Host: Windows 11 Home Single Language (Build 26200)
- CPU: 11th Gen Intel(R) Core(TM) i7-1165G7 @ 2.80GHz (4 Cores / 8 Threads)
- RAM: 16.0 GB Física
- Virtualização: Ativada na BIOS (AMI Firmware de Out/2024)

Gere a especificação técnica dividida estritamente nas 6 seções descritas abaixo, fornecendo os manifestos e arquivos de configuração completos e prontos para uso local:

---

### SEÇÃO 1: ISOLAMENTO DA CAMADA DE VIRTUALIZAÇÃO (WSL2 & HOST OPTIMIZATION)
Como o Host roda Windows 11 Home, a infraestrutura deve ser governada estritamente via WSL2 (Ubuntu 22.04 LTS) integrado ao Docker Desktop com WSL2 Backend.
1. CONFIGURAÇÃO DO .WSLCONFIG: Forneça o arquivo de configuração `.wslconfig` completo a ser inserido na pasta `%USERPROFILE%` do Windows. Aplique regras rígidas de FinOps local para evitar a inanição de memória do sistema operacional hospedeiro (Host), considerando o limite de 16GB de RAM e 8 threads:
   - Limite estrito de memória para o WSL: 8GB (50% da máquina).
   - Limite de processadores: 4 vCPUs.
   - Ativação do modo de rede espelhado (`networkingMode=mirrored`) para localhost estável.
   - Ativação de auto-reclaim de memória (`autoMemoryReclaim=drop_cache`).
2. PASSOS DE VALIDAÇÃO: Instruções de comandos PowerShell e Bash para verificar o status de virtualização (Nested Virtualization) e checagem de alocação de recursos dentro do terminal Ubuntu.

### SEÇÃO 2: ORQUESTRAÇÃO DE BANCO E CACHE LOCAL (DOCKER COMPOSE CORE)
Gere um arquivo `docker-compose.yml` completo e pronto para produção local, provisionando a Camada de Dados e Cache do SocialSelling.
1. POSTGRESQL 16+: Contêiner parametrizado com a base `socialselling`, usuário e senhas seguros via variáveis. Mapeie volumes persistentes locais para evitar perda de dados de ciclos de testes. Adicione parâmetros de otimização de memória do Postgres (`shared_buffers=2GB`, `work_mem=64MB`) adequados aos 8GB limitados do WSL2.
2. REDIS 7+ (CACHE L1): Contêiner para gerenciamento do ciclo de vida dos snapshots de scrapers com limite de memória estrita configurado via maxmemory política de descarte volatile-lru.
3. INICIALIZAÇÃO ATÔMICA (init.sql): Forneça a automação do script de entrypoint do Docker que monta a estrutura de tabelas, índices multi-hop trigrama e a view de observabilidade cognitiva gerados no DDL do banco imediatamente no primeiro boot do contêiner.

### SEÇÃO 3: GERENCIAMENTO DETERMINÍSTICO DE DEPENDÊNCIAS (POETRY WORKSPACE)
1. CONFIGURAÇÃO DO POETRY: Comandos e configurações para garantir que o Poetry isole o ambiente virtual dentro da pasta do projeto (`poetry config virtualenvs.in-project true`).
2. CONTRATO DE INJEÇÃO (pyproject.toml): Gere o arquivo completo especificando o Python 3.11+ e todas as dependências estritas: `langgraph`, `langchain-openai`, `langchain-community`, `tavily-python`, `fastapi`, `uvicorn`, `pydantic-settings`, `sqlalchemy`, `psycopg2-binary`, `jellyfish`, e as dependências de desenvolvimento: `pytest`, `pytest-mock`, `responses`, `ruff`, `mypy`.

### SEÇÃO 4: ESTEIRA LOCAL DE QUALIDADE DE CÓDIGO (PRE-COMMIT HOOKS)
Especifique as regras de qualidade que rodam localmente antes de qualquer commit para garantir paridade com o CI/CD corporativo.
1. ARQUIVO .PRE-COMMIT-CONFIG.YAML: Manifesto completo configurando hooks para:
   - Ruff (para linting ultra-rápido e formatação de código).
   - MyPy (checagem estática de tipos rodando em modo `--strict`).
2. CONFIGURAÇÃO MYPY: Adicione as diretrizes de configuração do MyPy no `pyproject.toml` desativando checagens implícitas e exigindo tipagem em todas as assinaturas de nós do grafo.

### SEÇÃO 5: ARQUITETURA DE AMBIENTE DE TESTES HERMÉTICOS (MOCKING LAYER)
1. SANDBOX DE REDE LOCAL: Definição de diretrizes para isolamento completo de chamadas externas de API (OpenAI e Tavily) usando `pytest-mock` e `responses`. É terminantemente proibido que a suíte de testes unitários execute chamadas reais à internet na máquina local do desenvolvedor.
2. FIXTURES DO PYTEST: Gere um arquivo `conftest.py` contendo as fixtures padrão que injetam um estado `LeadState` mockado e simulam as respostas em JSON válidos do nó de análise e do nó de pesquisa da Tavily.

### SEÇÃO 6: PLAYBOOK OPERACIONAIS DE DEPLOY E EXECUTABILIDADE LOCAL
Crie o roteiro passo a passo ordenado dos comandos executados de dentro do terminal WSL2 para subir a aplicação do zero:
1. Clonagem e abertura do ambiente.
2. Ativação do Docker Compose e checagem de logs do banco.
3. Execução do Poetry Install e carga de variáveis via arquivo `.env` local.
4. Comando exato de inicialização do servidor local FastAPI via Uvicorn com hot-reload ativo (`--reload`).
5. Comando Pytest para rodar a suíte de validação de BDD local.

---
Gere agora as especificações detalhadas, exaustivas, limpas e com os códigos dos manifestos (YML, TOML, SQL, CONF) prontos para implementação local imediata, sem o uso de resumos ou trechos ocultos.