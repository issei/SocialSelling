# Guia de Engenharia e Setup DevOps Local — Projeto SocialSelling

**Versão:** 1.0.0  
**Arquitetura-alvo:** WSL2 (Ubuntu 22.04 LTS) + Docker Desktop + Poetry + LangGraph  
**Hardware Host:** Intel i7-1165G7 · 16 GB RAM · Windows 11 Home (Build 26200)

---

## ÍNDICE

1. [Seção 1 — Isolamento da Camada de Virtualização (WSL2 & Host Optimization)](#seção-1)
2. [Seção 2 — Orquestração de Banco e Cache Local (Docker Compose Core)](#seção-2)
3. [Seção 3 — Gerenciamento Determinístico de Dependências (Poetry Workspace)](#seção-3)
4. [Seção 4 — Esteira Local de Qualidade de Código (Pre-commit Hooks)](#seção-4)
5. [Seção 5 — Arquitetura de Ambiente de Testes Herméticos (Mocking Layer)](#seção-5)
6. [Seção 6 — Playbook Operacional de Deploy e Executabilidade Local](#seção-6)

---

## SEÇÃO 1 — Isolamento da Camada de Virtualização (WSL2 & Host Optimization) {#seção-1}

### 1.1 Contexto e Estratégia FinOps Local

Com 16 GB de RAM física e o WSL2 como hypervisor de camada 2, a regra de ouro é: **o host Windows deve reter no mínimo 50% da memória para manter o Explorador de Arquivos, o Docker Desktop, o browser do desenvolvedor e o antivírus operando sem swap**. Por isso, o teto do WSL2 é fixado em **8 GB** e os vCPUs em **4**, liberando os outros 4 threads para o sistema operacional hospedeiro.

### 1.2 Arquivo `.wslconfig`

> **Localização obrigatória:** `C:\Users\<SEU_USUARIO>\.wslconfig`  
> Crie ou substitua o arquivo existente com o conteúdo abaixo. Após salvar, execute `wsl --shutdown` no PowerShell e reinicie o terminal WSL2.

```ini
# =============================================================================
# .wslconfig — Configuração de Hipervisor WSL2 para Projeto SocialSelling
# Host: Windows 11 Home · i7-1165G7 · 16 GB RAM
# Política FinOps: 50% RAM / 50% CPU reservados para o host
# =============================================================================

[wsl2]

# ── Recursos de Computação ──────────────────────────────────────────────────
# Limita o WSL2 a 8 GB de RAM (50% do total físico).
# Impede que o Vmmem engula memória do host sob carga de testes/scraping.
memory=8GB

# Limita a 4 vCPUs (50% dos 8 threads lógicos do i7-1165G7).
# Os 4 threads restantes garantem responsividade do Windows e do Docker Desktop.
processors=4

# Tamanho do arquivo de swap interno do WSL2.
# 4 GB de swap evita OOM-killer durante picos de build de imagens Docker.
swap=4GB

# Caminho do arquivo de swap (dentro do perfil do usuário Windows).
# Altere <SEU_USUARIO> pelo nome de usuário real da máquina.
swapFile=C:\\Users\\<SEU_USUARIO>\\AppData\\Local\\Temp\\wsl-swap.vhdx

# ── Rede ─────────────────────────────────────────────────────────────────────
# Modo espelhado: o WSL2 compartilha o stack de rede do host Windows.
# Elimina o problema clássico de "localhost não resolve dentro do WSL2"
# e garante que chamadas a http://localhost:8000 (FastAPI) funcionem
# tanto no browser Windows quanto dentro do próprio WSL2.
networkingMode=mirrored

# Permite que o WSL2 acesse serviços na rede local do host (ex.: RDP, VPN).
hostAddressLoopback=true

# ── Gerenciamento de Memória ─────────────────────────────────────────────────
# Política de reclaim agressivo: o WSL2 devolve páginas de cache de disco
# ao host assim que os processos Linux as liberam.
# "drop_cache" é mais agressivo que "gradual" e recomendado para máquinas
# com memória limitada (≤16 GB) onde testes de carga são executados em bursts.
autoMemoryReclaim=drop_cache

# ── Kernel e Performance ─────────────────────────────────────────────────────
# Desabilita o kernel compactado do Windows para usar o kernel WSL2 stock.
# Necessário para compatibilidade com módulos Docker como OverlayFS.
kernelCommandLine=vsyscall=emulate

# Habilita page reporting: informa ao hipervisor Hyper-V quais páginas
# estão livres, permitindo que o Windows recupere memória física real.
pageReporting=true

# ── Interoperabilidade ───────────────────────────────────────────────────────
# Permite executar binários Windows (.exe) a partir do terminal Linux.
# Útil para abrir o VS Code com `code .` a partir do WSL2.
[interop]
enabled=true
appendWindowsPath=true
```

### 1.3 Passos de Validação Pós-configuração

#### 1.3.1 Validação de Virtualização — PowerShell (Executar como Administrador)

```powershell
# ── Passo 1: Verificar se o Hyper-V está ativo e a virtualização está habilitada
systeminfo | Select-String -Pattern "Hyper-V", "Virtualization"

# Saída esperada (trecho):
# Hyper-V Requirements: VM Monitor Mode Extensions: Yes
#                       Virtualization Enabled In Firmware: Yes
#                       Second Level Address Translation: Yes
#                       Data Execution Prevention Available: Yes

# ── Passo 2: Confirmar versão do WSL e distro padrão
wsl --status
# Saída esperada:
# Default Distribution: Ubuntu-22.04
# Default Version: 2

# ── Passo 3: Listar distros e confirmar que Ubuntu-22.04 roda em WSL2
wsl --list --verbose
# Saída esperada:
#   NAME            STATE           VERSION
# * Ubuntu-22.04    Running         2

# ── Passo 4: Reiniciar o WSL2 para aplicar o .wslconfig
wsl --shutdown
Start-Sleep -Seconds 3
wsl --distribution Ubuntu-22.04 -- echo "WSL2 reiniciado com sucesso"
```

#### 1.3.2 Validação de Alocação de Recursos — Terminal Ubuntu (Bash)

```bash
#!/usr/bin/env bash
# =============================================================================
# validate_wsl_resources.sh
# Execute dentro do terminal Ubuntu-22.04 após aplicar o .wslconfig
# =============================================================================

echo "============================================================"
echo " VALIDAÇÃO DE RECURSOS WSL2 — SocialSelling"
echo "============================================================"

# ── Memória Total Disponível para o WSL2
echo ""
echo "[1/5] Memória disponível para o WSL2:"
free -h
# Esperado: total na linha 'Mem:' próximo de 8.0Gi

# ── CPUs Alocados
echo ""
echo "[2/5] vCPUs alocados:"
nproc
# Esperado: 4

# ── Detalhes dos processadores
echo ""
echo "[3/5] Informações dos CPUs (primeiras 12 linhas):"
lscpu | head -12

# ── Modo de Rede (Mirrored)
echo ""
echo "[4/5] Interfaces de rede (modo espelhado deve mostrar eth0 com IP do host):"
ip addr show eth0 2>/dev/null || ip addr show | grep -A 2 "eth0\|lo"

# ── Versão do Kernel WSL2
echo ""
echo "[5/5] Versão do Kernel WSL2:"
uname -r
# Esperado: algo como 5.15.x.x-microsoft-standard-WSL2

echo ""
echo "============================================================"
echo " Validação concluída. Verifique os valores acima."
echo "============================================================"
```

---

## SEÇÃO 2 — Orquestração de Banco e Cache Local (Docker Compose Core) {#seção-2}

### 2.1 Estrutura de Arquivos

```
socialselling/
├── docker/
│   ├── init.sql          ← Script DDL de inicialização atômica
│   └── redis.conf        ← Configuração customizada do Redis
├── .env                  ← Variáveis de ambiente (nunca comitar)
├── .env.example          ← Template seguro para versionamento
└── docker-compose.yml    ← Manifesto principal de orquestração
```

### 2.2 Arquivo `.env.example`

> Copie para `.env` e preencha com valores reais antes de subir os contêineres.

```dotenv
# =============================================================================
# .env.example — Template de Variáveis de Ambiente do SocialSelling
# NUNCA comite o arquivo .env real. Adicione-o ao .gitignore.
# =============================================================================

# ── PostgreSQL ───────────────────────────────────────────────────────────────
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=socialselling
POSTGRES_USER=ss_admin
POSTGRES_PASSWORD=SocialSelling@2024!Secure

# ── Redis ────────────────────────────────────────────────────────────────────
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=Redis@SocialSelling2024

# ── Aplicação ────────────────────────────────────────────────────────────────
APP_ENV=development
APP_PORT=8000
APP_LOG_LEVEL=debug
SECRET_KEY=gerar-com-openssl-rand-hex-32-aqui

# ── LLM / APIs Externas ──────────────────────────────────────────────────────
OPENAI_API_KEY=sk-proj-SUBSTITUIR_PELA_CHAVE_REAL
TAVILY_API_KEY=tvly-SUBSTITUIR_PELA_CHAVE_REAL

# ── Strings de Conexão (construídas a partir das variáveis acima) ─────────────
DATABASE_URL=postgresql+psycopg2://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}
REDIS_URL=redis://:${REDIS_PASSWORD}@${REDIS_HOST}:${REDIS_PORT}/0
```

### 2.3 Arquivo `docker-compose.yml`

```yaml
# =============================================================================
# docker-compose.yml — Camada de Dados e Cache do SocialSelling
# Compatível com Docker Compose v2 (plugin nativo do Docker Desktop 4.x+)
# Otimizado para WSL2 com 8 GB de RAM limitados
# =============================================================================

version: "3.9"

# ── Rede Interna Isolada ─────────────────────────────────────────────────────
networks:
  socialselling_net:
    driver: bridge
    ipam:
      config:
        - subnet: 172.28.0.0/16

# ── Volumes Persistentes ─────────────────────────────────────────────────────
volumes:
  postgres_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      # Caminho dentro do WSL2. Dados persistem entre restarts dos contêineres.
      device: ${PWD}/volumes/postgres
  redis_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: ${PWD}/volumes/redis

# ── Serviços ─────────────────────────────────────────────────────────────────
services:

  # ────────────────────────────────────────────────────────────────────────────
  # POSTGRESQL 16 — Banco de Dados Relacional Principal
  # ────────────────────────────────────────────────────────────────────────────
  postgres:
    image: postgres:16-alpine
    container_name: ss_postgres
    restart: unless-stopped
    networks:
      socialselling_net:
        ipv4_address: 172.28.0.10

    # Variáveis carregadas do .env
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      # Configurações de performance passadas via POSTGRES_INITDB_ARGS
      # As otimizações principais são injetadas pelo init.sql (veja abaixo)
      PGDATA: /var/lib/postgresql/data/pgdata

    # Parâmetros de tuning do PostgreSQL para ambiente de 8 GB (WSL2)
    # shared_buffers=2GB   → 25% da RAM do WSL2 (regra de ouro do Postgres)
    # work_mem=64MB        → memória por operação de sort/hash por conexão
    # effective_cache_size=4GB → estimativa do cache de SO para o planner
    # maintenance_work_mem=256MB → para VACUUM, CREATE INDEX etc.
    # max_connections=50   → conservador para ambiente de dev (evita OOM)
    command: >
      postgres
        -c shared_buffers=2GB
        -c work_mem=64MB
        -c effective_cache_size=4GB
        -c maintenance_work_mem=256MB
        -c max_connections=50
        -c wal_level=minimal
        -c max_wal_senders=0
        -c checkpoint_completion_target=0.9
        -c random_page_cost=1.1
        -c log_min_duration_statement=500
        -c log_line_prefix='%t [%p] %u@%d '
        -c timezone=America/Sao_Paulo

    ports:
      - "5432:5432"

    volumes:
      # Volume persistente para dados do banco
      - postgres_data:/var/lib/postgresql/data
      # Script de inicialização atômica — executado apenas no primeiro boot
      - ./docker/init.sql:/docker-entrypoint-initdb.d/01_init.sql:ro

    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 15s

    # Limite de memória do contêiner dentro do WSL2
    mem_limit: 3g
    mem_reservation: 2g
    shm_size: 512m   # /dev/shm para operações de sort do Postgres

    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "3"

  # ────────────────────────────────────────────────────────────────────────────
  # REDIS 7 — Cache L1 para Snapshots de Scrapers
  # ────────────────────────────────────────────────────────────────────────────
  redis:
    image: redis:7.2-alpine
    container_name: ss_redis
    restart: unless-stopped
    networks:
      socialselling_net:
        ipv4_address: 172.28.0.11

    # Redis é iniciado com arquivo de configuração customizado
    command: redis-server /usr/local/etc/redis/redis.conf

    ports:
      - "6379:6379"

    volumes:
      # Persistência RDB para sobreviver a restarts
      - redis_data:/data
      # Configuração customizada com senha e limites de memória
      - ./docker/redis.conf:/usr/local/etc/redis/redis.conf:ro

    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5
      start_period: 5s

    mem_limit: 512m
    mem_reservation: 256m

    logging:
      driver: "json-file"
      options:
        max-size: "20m"
        max-file: "2"

    depends_on:
      postgres:
        condition: service_healthy
```

### 2.4 Arquivo `docker/redis.conf`

```conf
# =============================================================================
# redis.conf — Configuração do Redis 7 para SocialSelling
# Política: volatile-lru com limite de 384 MB
# =============================================================================

# ── Segurança ─────────────────────────────────────────────────────────────────
# Requerido para acesso autenticado (substitua pelo valor do .env no runtime)
requirepass Redis@SocialSelling2024

# Desabilita comandos perigosos em ambiente de dev
rename-command FLUSHALL ""
rename-command FLUSHDB  ""
rename-command CONFIG   "CONFIG_ADMIN_ONLY"
rename-command DEBUG    ""

# ── Rede ─────────────────────────────────────────────────────────────────────
bind 0.0.0.0
port 6379
protected-mode yes
tcp-backlog 511
timeout 300
tcp-keepalive 60

# ── Política de Memória ───────────────────────────────────────────────────────
# Limite de 384 MB (75% dos 512 MB alocados ao contêiner)
maxmemory 384mb

# volatile-lru: remove apenas chaves com TTL configurado usando LRU.
# Ideal para cache de snapshots de scrapers (sempre têm TTL definido).
# Chaves sem TTL (configuração persistente) são preservadas.
maxmemory-policy volatile-lru

# Amostras para o algoritmo LRU aproximado (5 é o padrão; 10 é mais preciso)
maxmemory-samples 10

# ── Persistência RDB ──────────────────────────────────────────────────────────
# Salva snapshot se houver pelo menos 1 alteração nos últimos 3600 segundos
save 3600 1
# Ou se houver 100 alterações nos últimos 300 segundos
save 300 100
# Ou se houver 10000 alterações nos últimos 60 segundos
save 60 10000

dbfilename dump.rdb
dir /data
rdbcompression yes
rdbchecksum yes

# ── Performance ───────────────────────────────────────────────────────────────
# Desabilita AOF em desenvolvimento (prioridade é velocidade, não durabilidade)
appendonly no

# Lazy freeing: libera memória de grandes chaves em background
lazyfree-lazy-eviction yes
lazyfree-lazy-expire yes
lazyfree-lazy-server-del yes

# ── Logging ───────────────────────────────────────────────────────────────────
loglevel notice
logfile ""

# ── Databases ─────────────────────────────────────────────────────────────────
# DB 0: cache de snapshots de scrapers
# DB 1: sessões e rate limiting
# DB 2: filas de jobs (reserva)
databases 4
```

### 2.5 Script de Inicialização Atômica `docker/init.sql`

```sql
-- =============================================================================
-- init.sql — DDL de Inicialização Atômica do SocialSelling
-- Executado pelo entrypoint do PostgreSQL 16 no PRIMEIRO boot do contêiner.
-- Garante estrutura de tabelas, índices, extensões e view de observabilidade.
-- =============================================================================

-- ── Extensões ──────────────────────────────────────────────────────────────--
-- pg_trgm: índices trigramas para busca fuzzy de nomes de leads e empresas
CREATE EXTENSION IF NOT EXISTS pg_trgm;
-- uuid-ossp: geração de UUIDs v4 para PKs de leads
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- pg_stat_statements: coleta de métricas de queries para observabilidade
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
-- unaccent: normalização de acentos para buscas transliteradas
CREATE EXTENSION IF NOT EXISTS unaccent;

-- ── Schema Principal ───────────────────────────────────────────────────────--
CREATE SCHEMA IF NOT EXISTS socialselling;
SET search_path TO socialselling, public;

-- ── Tabela: leads ─────────────────────────────────────────────────────────--
-- Armazena os leads identificados pelo agente de prospecção.
CREATE TABLE IF NOT EXISTS leads (
    id                  UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    full_name           VARCHAR(255)    NOT NULL,
    normalized_name     VARCHAR(255)    GENERATED ALWAYS AS (
                            unaccent(lower(trim(full_name)))
                        ) STORED,
    email               VARCHAR(320)    UNIQUE,
    linkedin_url        VARCHAR(512),
    company_name        VARCHAR(255),
    normalized_company  VARCHAR(255)    GENERATED ALWAYS AS (
                            unaccent(lower(trim(company_name)))
                        ) STORED,
    job_title           VARCHAR(255),
    industry            VARCHAR(128),
    city                VARCHAR(128),
    country             VARCHAR(64)     DEFAULT 'BR',
    -- Score de qualidade calculado pelo nó de análise do LangGraph (0.0 a 1.0)
    qualification_score NUMERIC(4,3)    CHECK (qualification_score BETWEEN 0.0 AND 1.0),
    -- Estado do lead no funil do agente
    status              VARCHAR(64)     NOT NULL DEFAULT 'raw'
                            CHECK (status IN (
                                'raw',          -- recém capturado
                                'enriched',     -- dados complementados pela Tavily
                                'analyzed',     -- pontuado pelo nó de análise
                                'approved',     -- aprovado para contato
                                'rejected',     -- descartado pelo filtro de qualidade
                                'contacted',    -- primeiro contato realizado
                                'converted'     -- convertido em oportunidade
                            )),
    -- Payload JSON com contexto de pesquisa retornado pela Tavily
    research_payload    JSONB,
    -- Payload JSON com a saída do nó de análise do LangGraph
    analysis_payload    JSONB,
    -- Metadados de rastreabilidade
    source              VARCHAR(128),   -- ex: 'linkedin_scraper', 'manual', 'tavily'
    scraper_run_id      UUID,           -- vincula ao ciclo de scraping que gerou o lead
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    deleted_at          TIMESTAMPTZ     -- soft delete
);

-- ── Tabela: scraper_runs ──────────────────────────────────────────────────--
-- Rastreia cada ciclo de execução dos scrapers.
CREATE TABLE IF NOT EXISTS scraper_runs (
    id              UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    scraper_name    VARCHAR(128)    NOT NULL,
    started_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    status          VARCHAR(32)     NOT NULL DEFAULT 'running'
                        CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    leads_captured  INTEGER         DEFAULT 0,
    leads_rejected  INTEGER         DEFAULT 0,
    error_message   TEXT,
    config_snapshot JSONB           -- snapshot da configuração usada na execução
);

-- ── Tabela: agent_events ──────────────────────────────────────────────────--
-- Log de eventos dos nós do grafo LangGraph para auditoria e debugging.
CREATE TABLE IF NOT EXISTS agent_events (
    id          BIGSERIAL       PRIMARY KEY,
    lead_id     UUID            REFERENCES leads(id) ON DELETE SET NULL,
    run_id      UUID,           -- ID de execução do grafo
    node_name   VARCHAR(128)    NOT NULL, -- ex: 'research_node', 'analysis_node'
    event_type  VARCHAR(64)     NOT NULL, -- ex: 'node_start', 'node_end', 'error'
    payload     JSONB,
    tokens_used INTEGER,        -- custo em tokens (para billing tracking)
    latency_ms  INTEGER,        -- latência do nó em milissegundos
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- ── Tabela: outreach_campaigns ────────────────────────────────────────────--
-- Campanhas de abordagem geradas pelo agente de mensagens.
CREATE TABLE IF NOT EXISTS outreach_campaigns (
    id              UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    lead_id         UUID            NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    channel         VARCHAR(64)     NOT NULL CHECK (channel IN ('linkedin', 'email', 'whatsapp')),
    message_content TEXT            NOT NULL,
    sent_at         TIMESTAMPTZ,
    status          VARCHAR(32)     DEFAULT 'draft'
                        CHECK (status IN ('draft', 'scheduled', 'sent', 'replied', 'bounced')),
    reply_content   TEXT,
    replied_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- ── ÍNDICES — Pesquisa Multi-hop com Trigramas ────────────────────────────--

-- Índice trigrama no nome normalizado do lead (busca fuzzy por nome)
CREATE INDEX IF NOT EXISTS idx_leads_trgm_name
    ON leads USING GIN (normalized_name gin_trgm_ops);

-- Índice trigrama no nome normalizado da empresa
CREATE INDEX IF NOT EXISTS idx_leads_trgm_company
    ON leads USING GIN (normalized_company gin_trgm_ops);

-- Índice BTREE para filtragens por status (high-cardinality queries)
CREATE INDEX IF NOT EXISTS idx_leads_status
    ON leads (status) WHERE deleted_at IS NULL;

-- Índice composto para queries de funil com filtro de score
CREATE INDEX IF NOT EXISTS idx_leads_status_score
    ON leads (status, qualification_score DESC)
    WHERE deleted_at IS NULL;

-- Índice GIN no payload de pesquisa (Tavily) para queries JSONB
CREATE INDEX IF NOT EXISTS idx_leads_research_payload
    ON leads USING GIN (research_payload jsonb_path_ops);

-- Índice GIN no payload de análise do LangGraph
CREATE INDEX IF NOT EXISTS idx_leads_analysis_payload
    ON leads USING GIN (analysis_payload jsonb_path_ops);

-- Índice no email (já tem UNIQUE, mas explícito para partial index sem nulos)
CREATE INDEX IF NOT EXISTS idx_leads_email
    ON leads (email) WHERE email IS NOT NULL AND deleted_at IS NULL;

-- Índice no LinkedIn URL
CREATE INDEX IF NOT EXISTS idx_leads_linkedin
    ON leads (linkedin_url) WHERE linkedin_url IS NOT NULL;

-- Índice na tabela de eventos para lookup por lead
CREATE INDEX IF NOT EXISTS idx_agent_events_lead_id
    ON agent_events (lead_id, created_at DESC);

-- Índice na tabela de eventos para lookup por run
CREATE INDEX IF NOT EXISTS idx_agent_events_run_id
    ON agent_events (run_id, created_at DESC);

-- ── Trigger: updated_at automático ───────────────────────────────────────--
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_leads_updated_at
    BEFORE UPDATE ON leads
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ── VIEW: observabilidade_cognitiva ──────────────────────────────────────--
-- View de monitoramento do pipeline cognitivo do agente LangGraph.
-- Consolida métricas de qualidade, custo de tokens e latência por nó.
CREATE OR REPLACE VIEW v_observabilidade_cognitiva AS
SELECT
    -- Janela temporal de análise
    date_trunc('hour', ae.created_at)                   AS hora_execucao,
    ae.node_name                                         AS no_grafo,
    ae.event_type                                        AS tipo_evento,

    -- Métricas de volume
    COUNT(*)                                             AS total_execucoes,
    COUNT(DISTINCT ae.lead_id)                           AS leads_processados,

    -- Métricas de custo (tokens OpenAI)
    SUM(ae.tokens_used)                                  AS total_tokens,
    ROUND(AVG(ae.tokens_used), 1)                        AS media_tokens_por_exec,
    MAX(ae.tokens_used)                                  AS pico_tokens,

    -- Métricas de performance
    ROUND(AVG(ae.latency_ms), 0)                         AS latencia_media_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (
        ORDER BY ae.latency_ms
    )                                                    AS p95_latencia_ms,
    MAX(ae.latency_ms)                                   AS latencia_maxima_ms,

    -- Taxa de erro
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE ae.event_type = 'error') / COUNT(*),
        2
    )                                                    AS taxa_erro_pct,

    -- Leads aprovados no período
    COUNT(DISTINCT l.id) FILTER (
        WHERE l.status IN ('approved', 'contacted', 'converted')
    )                                                    AS leads_aprovados,

    -- Score médio de qualificação dos leads processados
    ROUND(AVG(l.qualification_score)::NUMERIC, 3)        AS score_medio_qualificacao

FROM agent_events ae
LEFT JOIN leads l ON l.id = ae.lead_id
GROUP BY 1, 2, 3
ORDER BY 1 DESC, 2, 3;

-- Concede acesso de leitura à view para o usuário da aplicação
GRANT SELECT ON v_observabilidade_cognitiva TO CURRENT_USER;
GRANT SELECT ON v_observabilidade_cognitiva TO PUBLIC;

-- ── Dados de Seed para Testes ─────────────────────────────────────────────--
-- Insere um scraper_run de exemplo para validar a estrutura
INSERT INTO scraper_runs (scraper_name, status, leads_captured)
VALUES ('init_seed', 'completed', 0)
ON CONFLICT DO NOTHING;

-- Mensagem de confirmação nos logs do Docker
DO $$
BEGIN
    RAISE NOTICE '=== SocialSelling DDL: Inicialização atômica concluída com sucesso. ===';
    RAISE NOTICE '    Extensões: pg_trgm, uuid-ossp, pg_stat_statements, unaccent';
    RAISE NOTICE '    Tabelas: leads, scraper_runs, agent_events, outreach_campaigns';
    RAISE NOTICE '    View: v_observabilidade_cognitiva';
    RAISE NOTICE '    Índices: 10 índices (BTREE + GIN trigrama)';
END $$;
```

### 2.6 Comando para Criar os Diretórios de Volume Antes do Primeiro Boot

```bash
# Execute dentro do WSL2, na raiz do projeto
mkdir -p volumes/postgres volumes/redis docker
```

---

## SEÇÃO 3 — Gerenciamento Determinístico de Dependências (Poetry Workspace) {#seção-3}

### 3.1 Instalação e Configuração do Poetry

```bash
# ── Passo 1: Instalar o Poetry via instalador oficial (não via pip global)
curl -sSL https://install.python-poetry.org | python3 -

# ── Passo 2: Adicionar o binário do Poetry ao PATH permanentemente
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# ── Passo 3: Verificar a instalação
poetry --version
# Saída esperada: Poetry (version 1.8.x ou superior)

# ── Passo 4: Configurar o Poetry para criar o .venv DENTRO do projeto
# Isso garante que o VS Code e outras IDEs detectem automaticamente o ambiente
poetry config virtualenvs.in-project true

# Confirmar configuração
poetry config --list | grep virtualenvs.in-project
# Saída esperada: virtualenvs.in-project = true

# ── Passo 5: Garantir Python 3.11 disponível no WSL2
python3 --version
# Se necessário, instale via deadsnakes PPA:
# sudo add-apt-repository ppa:deadsnakes/ppa
# sudo apt-get update
# sudo apt-get install python3.11 python3.11-dev python3.11-venv
```

### 3.2 Arquivo `pyproject.toml` Completo

```toml
# =============================================================================
# pyproject.toml — Contrato de Dependências do SocialSelling
# Gerenciado pelo Poetry — NÃO edite manualmente o poetry.lock
# =============================================================================

[tool.poetry]
name = "socialselling"
version = "0.1.0"
description = "Agente de Social Selling baseado em LangGraph para prospecção B2B inteligente"
authors = ["SocialSelling Team <dev@socialselling.com.br>"]
readme = "README.md"
license = "Proprietary"
packages = [{ include = "socialselling", from = "src" }]

[tool.poetry.dependencies]
# ── Runtime Core ──────────────────────────────────────────────────────────────
python = "^3.11"

# ── Orquestração de Agentes LLM ──────────────────────────────────────────────
# LangGraph: framework de grafo para agentes com estado (nós e arestas)
langgraph = "^0.2.0"

# LangChain com backend OpenAI (GPT-4o, embeddings)
langchain-openai = "^0.1.0"

# Integrações comunitárias: loaders, parsers, utilitários
langchain-community = "^0.2.0"

# ── Pesquisa Web (Nó Tavily do Grafo) ────────────────────────────────────────
# Cliente oficial da Tavily Search API para enriquecimento de leads
tavily-python = "^0.3.0"

# ── API Web ───────────────────────────────────────────────────────────────────
# FastAPI: framework HTTP assíncrono para expor o agente via REST
fastapi = {version = "^0.111.0", extras = ["all"]}

# Uvicorn: servidor ASGI de alta performance
uvicorn = {version = "^0.30.0", extras = ["standard"]}

# ── Configuração e Validação ──────────────────────────────────────────────────
# Pydantic Settings: carrega variáveis de ambiente com tipagem segura
pydantic-settings = "^2.3.0"

# ── Persistência (ORM + Driver) ───────────────────────────────────────────────
# SQLAlchemy: ORM async compatível com asyncpg e psycopg2
sqlalchemy = {version = "^2.0.0", extras = ["asyncio"]}

# psycopg2-binary: driver PostgreSQL para SQLAlchemy síncrono e Alembic
psycopg2-binary = "^2.9.9"

# ── Deduplicação e Fuzzy Matching ─────────────────────────────────────────────
# Jellyfish: algoritmos de similaridade de strings (Jaro-Winkler, Soundex, etc.)
# Usado no nó de deduplicação de leads do grafo
jellyfish = "^1.0.0"

# ── Dependências Transitivas Fixadas ──────────────────────────────────────────
# Fixamos versões para garantir builds reproduzíveis em CI e local
httpx = "^0.27.0"           # cliente HTTP async (usado internamente pelo LangChain)
pydantic = "^2.7.0"         # validação de dados (base do FastAPI e LangChain)
tenacity = "^8.3.0"         # retry automático para chamadas de API externas

[tool.poetry.group.dev.dependencies]
# ── Testes ────────────────────────────────────────────────────────────────────
# Pytest: framework principal de testes
pytest = "^8.2.0"

# pytest-mock: fixtures de mocking baseadas em unittest.mock
pytest-mock = "^3.14.0"

# pytest-asyncio: suporte a testes de funções assíncronas (nós async do grafo)
pytest-asyncio = "^0.23.0"

# responses: intercepta e mocka chamadas HTTP (requests library)
responses = "^0.25.0"

# httpx mock: intercepta chamadas httpx (para mocking da Tavily e OpenAI)
respx = "^0.21.0"

# pytest-cov: relatórios de cobertura de código
pytest-cov = "^5.0.0"

# Faker: geração de dados sintéticos para fixtures de teste
faker = "^25.0.0"

# ── Linting e Formatação ──────────────────────────────────────────────────────
# Ruff: linter e formatter ultra-rápido (substitui Black + Flake8 + isort)
ruff = "^0.4.0"

# ── Checagem de Tipos ─────────────────────────────────────────────────────────
# MyPy: análise estática com suporte a generics e PEP 695
mypy = "^1.10.0"

# Stubs de tipos para bibliotecas sem type hints nativos
types-psycopg2 = "^2.9.21"

# ── Ferramentas de Desenvolvimento ───────────────────────────────────────────
# Pre-commit: gerenciador de hooks de git
pre-commit = "^3.7.0"

# ipython: REPL aprimorado para debugging interativo
ipython = "^8.25.0"

# ── Build System ─────────────────────────────────────────────────────────────
[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

# =============================================================================
# CONFIGURAÇÃO DO RUFF (Linter + Formatter)
# =============================================================================
[tool.ruff]
# Versão mínima do Python alvo
target-version = "py311"

# Comprimento máximo de linha
line-length = 100

# Diretórios excluídos da análise
exclude = [
    ".git",
    ".venv",
    "__pycache__",
    "*.egg-info",
    "dist",
    "build",
    "migrations",
    ".mypy_cache",
    ".pytest_cache",
]

[tool.ruff.lint]
# Conjuntos de regras habilitados:
# E, W: pycodestyle (erros e avisos de estilo)
# F: pyflakes (variáveis não usadas, imports não usados etc.)
# I: isort (ordenação de imports)
# N: pep8-naming (convenções de nomenclatura)
# UP: pyupgrade (modernizações de sintaxe Python)
# B: flake8-bugbear (bugs potenciais)
# ANN: flake8-annotations (anotações de tipo obrigatórias)
# SIM: flake8-simplify (simplificações de código)
# TCH: flake8-type-checking (imports exclusivos de TYPE_CHECKING)
select = ["E", "W", "F", "I", "N", "UP", "B", "ANN", "SIM", "TCH"]

# Regras ignoradas (justificativa inline):
ignore = [
    "ANN101",  # self não precisa de anotação de tipo
    "ANN102",  # cls não precisa de anotação de tipo
    "ANN401",  # permite uso de Any quando necessário (ex: payloads JSONB)
    "B008",    # permite chamadas de função em parâmetros default (FastAPI Depends)
]

# Regras que o Ruff deve tentar corrigir automaticamente
fixable = ["ALL"]
unfixable = []

[tool.ruff.lint.per-file-ignores]
# Nos arquivos de teste, relaxamos algumas regras de anotação
"tests/**/*.py" = ["ANN", "N802"]
# No conftest, permite fixtures sem anotações de retorno
"conftest.py" = ["ANN201", "ANN202"]

[tool.ruff.format]
# Estilo de aspas (double é o padrão do Black, compatível com a maioria das IDEs)
quote-style = "double"
indent-style = "space"
skip-magic-trailing-comma = false
line-ending = "auto"

# =============================================================================
# CONFIGURAÇÃO DO MYPY (Checagem Estática de Tipos)
# =============================================================================
[tool.mypy]
# Versão mínima do Python
python_version = "3.11"

# ── Modo Strict Completo ──────────────────────────────────────────────────────
strict = true

# Exige que TODAS as funções e métodos tenham anotações de tipo
disallow_untyped_defs = true
disallow_incomplete_defs = true

# Proíbe chamadas para funções sem tipo sem anotação explícita
disallow_untyped_calls = true

# Proíbe decoradores sem tipo
disallow_untyped_decorators = true

# Proíbe retornos implícitos de Any
warn_return_any = true

# Alerta sobre tipos redundantes (ex: Optional[Optional[str]])
warn_redundant_casts = true

# Alerta sobre imports não usados
warn_unused_ignores = true

# Proíbe redefinições de variáveis com tipos incompatíveis
allow_redefinition = false

# Não permite que variáveis sejam usadas antes de terem tipo inferido
no_implicit_optional = true

# Exige que todos os módulos de terceiros tenham stubs ou sejam explicitamente ignorados
ignore_missing_imports = false

# ── Overrides por Módulo ──────────────────────────────────────────────────────
# Bibliotecas que não possuem stubs completos: desabilitar checagem de imports
[[tool.mypy.overrides]]
module = [
    "langgraph.*",
    "langchain_community.*",
    "tavily.*",
    "jellyfish.*",
    "faker.*",
    "responses.*",
    "respx.*",
]
ignore_missing_imports = true

# Nos testes, relaxamos a checagem de tipos para permitir fixtures dinâmicas
[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
disallow_incomplete_defs = false

# =============================================================================
# CONFIGURAÇÃO DO PYTEST
# =============================================================================
[tool.pytest.ini_options]
# Diretório raiz dos testes
testpaths = ["tests"]

# Modo asyncio padrão (necessário para pytest-asyncio)
asyncio_mode = "auto"

# Flags padrão:
# -v: verbose (mostra nome de cada teste)
# --tb=short: traceback curto (mais legível)
# --strict-markers: falha se markers não declarados forem usados
addopts = [
    "-v",
    "--tb=short",
    "--strict-markers",
    "--cov=src/socialselling",
    "--cov-report=term-missing",
    "--cov-report=html:htmlcov",
    "--cov-fail-under=80",
]

# Markers customizados (devem ser declarados aqui para evitar warnings)
markers = [
    "unit: testes unitários puros (sem I/O externo)",
    "integration: testes de integração com serviços locais (Docker)",
    "slow: testes que levam mais de 5 segundos",
    "bdd: cenários de BDD",
]

# Filtros de warnings para reduzir ruído nos logs de teste
filterwarnings = [
    "ignore::DeprecationWarning:langchain.*:",
    "ignore::PendingDeprecationWarning",
]

# =============================================================================
# CONFIGURAÇÃO DE COBERTURA DE CÓDIGO
# =============================================================================
[tool.coverage.run]
source = ["src/socialselling"]
omit = [
    "*/migrations/*",
    "*/tests/*",
    "*/__main__.py",
    "*/conftest.py",
]
branch = true

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
    "@abstractmethod",
]
```

---

## SEÇÃO 4 — Esteira Local de Qualidade de Código (Pre-commit Hooks) {#seção-4}

### 4.1 Instalação do Pre-commit

```bash
# Instalar o pre-commit no ambiente virtual do projeto
poetry run pre-commit install

# Instalar também o hook de commit-msg (opcional, para conventional commits)
poetry run pre-commit install --hook-type commit-msg

# Verificar instalação
cat .git/hooks/pre-commit | head -3
# Saída esperada: #!/usr/bin/env python
#                 # File generated by pre-commit
```

### 4.2 Arquivo `.pre-commit-config.yaml` Completo

```yaml
# =============================================================================
# .pre-commit-config.yaml — Esteira de Qualidade Local do SocialSelling
# Garante paridade com o pipeline CI/CD antes de qualquer push.
# =============================================================================

# Versão mínima do pre-commit requerida
minimum_pre_commit_version: "3.7.0"

# Comportamento padrão: falha rápida no primeiro hook que falhar
fail_fast: false

# =============================================================================
# REPOSITÓRIOS E HOOKS
# =============================================================================
repos:

  # ── Hooks Utilitários (pre-commit oficial) ──────────────────────────────────
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      # Remove espaços em branco no final das linhas
      - id: trailing-whitespace
        args: [--markdown-linebreak-ext=md]

      # Garante que todos os arquivos terminam com uma linha em branco
      - id: end-of-file-fixer

      # Valida sintaxe de arquivos YAML
      - id: check-yaml
        args: [--unsafe]  # permite tags YAML customizadas (ex: !secret)

      # Valida sintaxe de arquivos TOML
      - id: check-toml

      # Valida sintaxe de arquivos JSON
      - id: check-json

      # Previne commit de arquivos grandes (>500 KB)
      - id: check-added-large-files
        args: [--maxkb=500]

      # Detecta credenciais hardcoded (senhas, chaves de API)
      - id: detect-private-key

      # Previne merge conflicts não resolvidos
      - id: check-merge-conflict

      # Verifica se há imports circulares básicos
      - id: check-ast

      # Ordena requirements.txt (se existir)
      - id: requirements-txt-fixer

  # ── RUFF — Linter + Formatter Ultra-rápido ───────────────────────────────--
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.4
    hooks:
      # Ruff Linter: detecta e corrige automaticamente problemas de estilo e bugs
      - id: ruff
        name: "Ruff Linter"
        args:
          - --fix              # aplica correções automáticas quando possível
          - --exit-non-zero-on-fix  # falha se houve correção (força review)
        types_or: [python, pyi]
        # Roda em todos os arquivos Python do projeto
        files: ^(src|tests)/

      # Ruff Formatter: formata código (substitui Black)
      - id: ruff-format
        name: "Ruff Formatter"
        types_or: [python, pyi]
        files: ^(src|tests)/

  # ── MYPY — Checagem Estática de Tipos ───────────────────────────────────--
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        name: "MyPy (strict type checking)"
        # Usa o Python e as dependências instaladas no .venv do projeto
        language: system
        entry: poetry run mypy
        # Argumentos de modo strict — sobrescrevem pyproject.toml para CI parity
        args:
          - --strict
          - --ignore-missing-imports
          - --show-error-codes
          - --pretty
        types: [python]
        files: ^src/socialselling/
        # Exclui migrations (gerados automaticamente pelo Alembic)
        exclude: ^src/socialselling/migrations/

  # ── SEGURANÇA — Bandit (SAST para Python) ────────────────────────────────--
  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.8
    hooks:
      - id: bandit
        name: "Bandit (Security SAST)"
        args:
          - -c
          - pyproject.toml   # configuração embutida no pyproject.toml
          - -r               # recursivo
        files: ^src/socialselling/
        # Exclui testes (uso de assert é esperado em testes)
        exclude: ^tests/

  # ── CONVENTIONAL COMMITS ─────────────────────────────────────────────────--
  - repo: https://github.com/compilerla/conventional-pre-commit
    rev: v3.2.0
    hooks:
      - id: conventional-pre-commit
        name: "Conventional Commits Format"
        stages: [commit-msg]
        # Tipos permitidos de commit:
        # feat: nova funcionalidade
        # fix: correção de bug
        # docs: apenas documentação
        # style: formatação (sem mudança de lógica)
        # refactor: refatoração (sem novo feat nem fix)
        # test: adição/modificação de testes
        # chore: tarefas de manutenção (deps, config)
        # ci: mudanças no pipeline de CI/CD
        args:
          - feat
          - fix
          - docs
          - style
          - refactor
          - test
          - chore
          - ci
          - perf

# =============================================================================
# CONFIGURAÇÃO GLOBAL
# =============================================================================

# Tipos de arquivos excluídos de TODOS os hooks
exclude: |
    (?x)^(
        \.git/.*|
        \.venv/.*|
        __pycache__/.*|
        .*\.egg-info/.*|
        dist/.*|
        build/.*|
        htmlcov/.*|
        \.mypy_cache/.*|
        \.pytest_cache/.*|
        volumes/.*|
        docker/.*\.sql
    )$
```

### 4.3 Configuração do Bandit no `pyproject.toml`

Adicione ao `pyproject.toml` (complementa o arquivo da Seção 3):

```toml
# =============================================================================
# CONFIGURAÇÃO DO BANDIT (SAST — Análise de Segurança Estática)
# =============================================================================
[tool.bandit]
# Skips de falsos positivos conhecidos:
# B101: uso de assert (necessário em validações de configuração)
# B311: uso de random (aceitável para IDs não-criptográficos)
skips = ["B101", "B311"]

# Nível mínimo de severidade para reportar (LOW, MEDIUM, HIGH)
severity = "MEDIUM"

# Nível mínimo de confiança para reportar
confidence = "MEDIUM"

# Exclui arquivos de teste da análise de segurança
exclude_dirs = ["tests", "migrations", ".venv"]
```

### 4.4 Execução Manual dos Hooks (Para Validação Inicial)

```bash
# Rodar todos os hooks em todos os arquivos do projeto (primeira execução)
poetry run pre-commit run --all-files

# Rodar apenas o Ruff (linting)
poetry run pre-commit run ruff --all-files

# Rodar apenas o Ruff Formatter
poetry run pre-commit run ruff-format --all-files

# Rodar apenas o MyPy
poetry run pre-commit run mypy --all-files

# Atualizar todos os hooks para a última versão
poetry run pre-commit autoupdate
```

---

## SEÇÃO 5 — Arquitetura de Ambiente de Testes Herméticos (Mocking Layer) {#seção-5}

### 5.1 Princípios de Isolamento — Sandbox de Rede Local

**REGRA ABSOLUTA:** Nenhum teste unitário deve realizar chamadas HTTP reais durante a execução local. Toda comunicação com APIs externas (OpenAI, Tavily) **DEVE** ser interceptada pela camada de mocking antes de chegar à rede.

A estratégia de isolamento opera em duas camadas:

1. **`responses` / `respx`:** Interceptam chamadas HTTP a nível de socket, antes que qualquer pacote saia pela interface de rede. Se um teste esquece de registrar um mock e tenta fazer uma chamada real, a biblioteca lança `ConnectionError` imediatamente.

2. **`pytest-mock` (MagicMock):** Mocka diretamente os clientes Python das APIs (ex: `AsyncOpenAI`, `TavilyClient`), impedindo até a tentativa de conexão TCP.

### 5.2 Estrutura de Diretórios de Testes

```
tests/
├── conftest.py                     ← Fixtures globais (esta seção)
├── fixtures/
│   ├── leads.json                  ← Payloads de leads para testes
│   ├── tavily_responses.json       ← Respostas mockadas da Tavily
│   └── openai_responses.json       ← Respostas mockadas da OpenAI
├── unit/
│   ├── test_research_node.py       ← Testes do nó de pesquisa
│   ├── test_analysis_node.py       ← Testes do nó de análise
│   ├── test_deduplication_node.py  ← Testes do nó de deduplicação
│   └── test_outreach_node.py       ← Testes do nó de geração de mensagem
├── integration/
│   ├── test_graph_flow.py          ← Testes de fluxo completo do grafo
│   └── test_database_repositories.py ← Testes de repositórios com Postgres real
└── bdd/
    ├── features/
    │   └── lead_qualification.feature ← Cenários Gherkin
    └── test_lead_qualification_bdd.py
```

### 5.3 Arquivo `conftest.py` Completo

```python
# =============================================================================
# conftest.py — Fixtures Globais de Teste do SocialSelling
# =============================================================================
# REGRA: Este arquivo não deve importar nenhum módulo que faça I/O real.
# Todas as dependências externas (OpenAI, Tavily, PostgreSQL, Redis)
# DEVEM ser mockadas antes de qualquer asserção.
# =============================================================================

from __future__ import annotations

import json
import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx
import responses as responses_lib
from faker import Faker

# =============================================================================
# CONFIGURAÇÃO GLOBAL DO PYTEST
# =============================================================================

# Configura o Faker para gerar dados em português do Brasil
fake = Faker("pt_BR")

# Marca todos os testes neste arquivo como assíncronos por padrão
pytestmark = pytest.mark.asyncio


# =============================================================================
# FIXTURES DE ISOLAMENTO DE REDE
# =============================================================================

@pytest.fixture(autouse=True)
def block_real_http_calls() -> Generator[None, None, None]:
    """
    Fixture AUTOUSE: Ativada automaticamente em TODOS os testes unitários.

    Configura a biblioteca `responses` para interceptar qualquer chamada HTTP
    real e lançar ConnectionError se não houver um mock registrado.

    Esta é a garantia final de que nenhum teste unitário vaza para a internet.
    """
    with responses_lib.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        # Permite apenas chamadas para localhost (banco, redis em testes de integração)
        # Bloqueia qualquer chamada para domínios externos
        rsps.add_passthrough("http://localhost")
        rsps.add_passthrough("http://127.0.0.1")
        yield


# =============================================================================
# FIXTURES DO ESTADO DO GRAFO LANGGRAPH
# =============================================================================

@pytest.fixture
def lead_state_raw() -> dict[str, Any]:
    """
    Retorna um LeadState no estado 'raw' (entrada do grafo).
    Representa um lead recém-capturado pelo scraper, sem enriquecimento.
    """
    return {
        "lead_id": str(uuid.uuid4()),
        "full_name": fake.name(),
        "email": fake.email(),
        "linkedin_url": f"https://linkedin.com/in/{fake.user_name()}",
        "company_name": fake.company(),
        "job_title": fake.job(),
        "industry": "Tecnologia da Informação",
        "city": "São Paulo",
        "country": "BR",
        "status": "raw",
        "qualification_score": None,
        "research_payload": None,
        "analysis_payload": None,
        "source": "linkedin_scraper",
        "scraper_run_id": str(uuid.uuid4()),
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        # Campos de controle do grafo LangGraph
        "messages": [],
        "current_node": "research_node",
        "error": None,
        "retry_count": 0,
    }


@pytest.fixture
def lead_state_enriched(lead_state_raw: dict[str, Any]) -> dict[str, Any]:
    """
    Retorna um LeadState no estado 'enriched'.
    Representa um lead após execução bem-sucedida do nó de pesquisa (Tavily).
    """
    enriched = lead_state_raw.copy()
    enriched.update({
        "status": "enriched",
        "current_node": "analysis_node",
        "research_payload": {
            "query": f"{enriched['full_name']} {enriched['company_name']}",
            "results": [
                {
                    "title": f"{enriched['full_name']} — CEO at {enriched['company_name']}",
                    "url": f"https://linkedin.com/in/{fake.user_name()}",
                    "content": (
                        f"{enriched['full_name']} é CEO da {enriched['company_name']}, "
                        "empresa de SaaS B2B com 150 funcionários fundada em 2018. "
                        "Especialista em vendas consultivas e expansão de mercado."
                    ),
                    "score": 0.92,
                },
                {
                    "title": f"{enriched['company_name']} raises Series A funding",
                    "url": "https://techcrunch.com/example",
                    "content": (
                        f"{enriched['company_name']} captou R$ 8M em rodada Série A "
                        "para expandir operações no Brasil e Chile."
                    ),
                    "score": 0.87,
                },
            ],
            "answer": (
                f"{enriched['full_name']} é o CEO da {enriched['company_name']}, "
                "uma empresa de SaaS B2B em crescimento acelerado."
            ),
            "follow_up_questions": [
                "Qual o principal produto da empresa?",
                "Quantos clientes a empresa possui atualmente?",
            ],
        },
    })
    return enriched


@pytest.fixture
def lead_state_analyzed(lead_state_enriched: dict[str, Any]) -> dict[str, Any]:
    """
    Retorna um LeadState no estado 'analyzed'.
    Representa um lead após execução bem-sucedida do nó de análise (LLM).
    """
    analyzed = lead_state_enriched.copy()
    analyzed.update({
        "status": "analyzed",
        "qualification_score": 0.847,
        "current_node": "qualification_gate",
        "analysis_payload": {
            "icp_match": True,
            "icp_score": 0.847,
            "signals": {
                "decision_maker": True,
                "company_size_fit": True,   # 50-500 funcionários
                "industry_fit": True,
                "growth_signal": True,      # rodada de investimento recente
                "budget_signal": True,      # empresa captou Série A
                "pain_points": [
                    "Escalabilidade da equipe de vendas",
                    "Necessidade de automação do processo comercial",
                ],
            },
            "rejection_reasons": [],
            "recommended_approach": (
                "Abordagem consultiva focada em ROI. Mencionar a rodada Série A "
                "como contexto de crescimento. Propor uma demo focada em automação "
                "de prospecção."
            ),
            "personalized_hook": (
                f"Vi que a {analyzed['company_name']} captou recentemente uma Série A. "
                "Parabéns! Empresas nessa fase geralmente enfrentam o desafio de "
                "escalar vendas sem perder a qualidade do processo consultivo."
            ),
            "llm_model": "gpt-4o",
            "tokens_used": 1247,
            "latency_ms": 2341,
        },
    })
    return analyzed


# =============================================================================
# FIXTURES DE MOCK DAS APIS EXTERNAS
# =============================================================================

@pytest.fixture
def mock_tavily_response() -> dict[str, Any]:
    """
    Retorna uma resposta JSON válida e realista da Tavily Search API.
    Baseada no contrato real da API (https://docs.tavily.com).
    """
    return {
        "query": "João Silva CEO TechCorp Brasil",
        "follow_up_questions": [
            "Qual o tamanho da equipe da TechCorp?",
            "A TechCorp opera em outros países?",
        ],
        "answer": (
            "João Silva é o CEO e cofundador da TechCorp Brasil, empresa de SaaS B2B "
            "fundada em 2018 com foco em automação comercial para o mercado mid-market."
        ),
        "images": [],
        "results": [
            {
                "title": "João Silva - CEO at TechCorp Brasil | LinkedIn",
                "url": "https://linkedin.com/in/joao-silva-techcorp",
                "content": (
                    "João Silva · CEO na TechCorp Brasil · 12 anos de experiência "
                    "em vendas B2B e tecnologia · MBA pela FGV · São Paulo, Brasil"
                ),
                "score": 0.94,
                "raw_content": None,
            },
            {
                "title": "TechCorp Brasil capta R$8M em rodada Série A — Distrito",
                "url": "https://distrito.me/techcorp-serie-a",
                "content": (
                    "A TechCorp Brasil anunciou uma rodada Série A de R$8 milhões "
                    "liderada pelo fundo SP Ventures. Os recursos serão utilizados "
                    "para expansão da equipe de vendas e desenvolvimento de produto."
                ),
                "score": 0.89,
                "raw_content": None,
            },
        ],
        "response_time": 1.24,
    }


@pytest.fixture
def mock_openai_analysis_response() -> dict[str, Any]:
    """
    Retorna uma resposta JSON válida simulando o output do nó de análise
    que chama a API da OpenAI (GPT-4o) para qualificação de leads.

    A estrutura simula o formato de resposta do LangChain ChatOpenAI.
    """
    return {
        "id": "chatcmpl-test-" + str(uuid.uuid4())[:8],
        "object": "chat.completion",
        "created": int(datetime.now(tz=timezone.utc).timestamp()),
        "model": "gpt-4o-2024-05-13",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps({
                        "icp_match": True,
                        "icp_score": 0.847,
                        "signals": {
                            "decision_maker": True,
                            "company_size_fit": True,
                            "industry_fit": True,
                            "growth_signal": True,
                            "budget_signal": True,
                            "pain_points": [
                                "Escalabilidade da equipe de vendas",
                                "Automação do processo comercial",
                            ],
                        },
                        "rejection_reasons": [],
                        "recommended_approach": (
                            "Abordagem consultiva com foco em ROI. "
                            "Contextualizar a rodada Série A."
                        ),
                        "personalized_hook": (
                            "Vi que vocês captaram recentemente uma Série A. "
                            "Parabéns! Empresas nessa fase geralmente enfrentam o "
                            "desafio de escalar vendas sem perder qualidade."
                        ),
                    }),
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 987,
            "completion_tokens": 260,
            "total_tokens": 1247,
        },
    }


# =============================================================================
# FIXTURES DE MOCKING DOS CLIENTES DE API
# =============================================================================

@pytest.fixture
def mock_tavily_client(
    mock_tavily_response: dict[str, Any],
) -> Generator[MagicMock, None, None]:
    """
    Mocka o TavilyClient para interceptar chamadas ao nó de pesquisa.
    Retorna a fixture mock_tavily_response sem fazer chamadas reais.
    """
    with patch("socialselling.nodes.research_node.TavilyClient") as mock_client_class:
        mock_instance = MagicMock()
        mock_instance.search.return_value = mock_tavily_response
        mock_client_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_openai_client(
    mock_openai_analysis_response: dict[str, Any],
) -> Generator[AsyncMock, None, None]:
    """
    Mocka o AsyncOpenAI (LangChain ChatOpenAI) para interceptar chamadas
    ao nó de análise. Simula a resposta do GPT-4o sem tokens reais.
    """
    with patch("socialselling.nodes.analysis_node.ChatOpenAI") as mock_chat_class:
        mock_instance = AsyncMock()
        # Simula o método ainvoke do LangChain
        mock_response = MagicMock()
        mock_response.content = mock_openai_analysis_response["choices"][0]["message"]["content"]
        mock_response.response_metadata = {
            "token_usage": mock_openai_analysis_response["usage"],
            "model_name": "gpt-4o-2024-05-13",
        }
        mock_instance.ainvoke = AsyncMock(return_value=mock_response)
        mock_chat_class.return_value = mock_instance
        yield mock_instance


# =============================================================================
# FIXTURES DE BANCO DE DADOS (INTEGRAÇÃO)
# =============================================================================

@pytest.fixture(scope="session")
def db_url() -> str:
    """
    URL de conexão com o PostgreSQL local (Docker Compose).
    Usada APENAS em testes de integração (marcados com @pytest.mark.integration).
    """
    return (
        "postgresql+psycopg2://ss_admin:SocialSelling@2024!Secure"
        "@localhost:5432/socialselling"
    )


# =============================================================================
# FIXTURES DE DADOS SINTÉTICOS (BDD / VOLUME)
# =============================================================================

@pytest.fixture
def sample_leads_batch() -> list[dict[str, Any]]:
    """
    Gera um batch de 10 leads sintéticos para testes de volume e BDD.
    Usa o Faker com localização pt_BR para dados realistas.
    """
    leads = []
    for _ in range(10):
        leads.append({
            "lead_id": str(uuid.uuid4()),
            "full_name": fake.name(),
            "email": fake.company_email(),
            "linkedin_url": f"https://linkedin.com/in/{fake.user_name()}",
            "company_name": fake.company(),
            "job_title": fake.job(),
            "industry": fake.random_element([
                "Tecnologia da Informação",
                "Saúde e Biotecnologia",
                "Serviços Financeiros",
                "Varejo e E-commerce",
                "Manufatura",
            ]),
            "city": fake.city(),
            "country": "BR",
            "status": "raw",
            "qualification_score": None,
            "research_payload": None,
            "analysis_payload": None,
            "source": "linkedin_scraper",
            "scraper_run_id": str(uuid.uuid4()),
        })
    return leads
```

### 5.4 Exemplo de Teste Unitário Usando as Fixtures

```python
# tests/unit/test_research_node.py
# =============================================================================
# Exemplo de teste unitário hermético para o nó de pesquisa Tavily
# =============================================================================

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.mark.unit
class TestResearchNode:
    """Testes unitários para o nó de pesquisa (Tavily) do grafo LangGraph."""

    def test_research_node_returns_enriched_state(
        self,
        lead_state_raw: dict[str, Any],
        mock_tavily_client: MagicMock,
        mock_tavily_response: dict[str, Any],
    ) -> None:
        """
        DADO um lead no estado 'raw'
        QUANDO o nó de pesquisa é executado
        ENTÃO o estado deve ser atualizado para 'enriched'
         E o research_payload deve conter os resultados da Tavily
         E nenhuma chamada HTTP real deve ter sido feita
        """
        from socialselling.nodes.research_node import research_node

        result = research_node(lead_state_raw)

        assert result["status"] == "enriched"
        assert result["research_payload"] is not None
        assert len(result["research_payload"]["results"]) > 0
        # Verifica que o mock foi chamado corretamente
        mock_tavily_client.search.assert_called_once()

    def test_research_node_handles_empty_results(
        self,
        lead_state_raw: dict[str, Any],
        mock_tavily_client: MagicMock,
    ) -> None:
        """
        DADO um lead no estado 'raw'
        QUANDO a Tavily retorna 0 resultados
        ENTÃO o estado deve ser 'enriched' (com payload vazio)
         E o lead não deve ser marcado como 'rejected' neste nó
        """
        from socialselling.nodes.research_node import research_node

        mock_tavily_client.search.return_value = {
            "query": "test",
            "results": [],
            "answer": "",
            "follow_up_questions": [],
            "response_time": 0.5,
        }

        result = research_node(lead_state_raw)

        assert result["status"] == "enriched"
        assert result["research_payload"]["results"] == []
```

---

## SEÇÃO 6 — Playbook Operacional de Deploy e Executabilidade Local {#seção-6}

### Visão Geral do Fluxo de Boot

```
Windows Host
    └─► WSL2 (Ubuntu 22.04)
            ├─► Docker Desktop (Backend WSL2)
            │       ├─► ss_postgres (PostgreSQL 16)
            │       └─► ss_redis (Redis 7.2)
            └─► Poetry (.venv local)
                    ├─► Uvicorn (FastAPI + hot-reload)
                    └─► Pytest (suíte de testes herméticos)
```

### Pré-requisitos Obrigatórios

Antes de executar o playbook, confirme que os seguintes itens estão instalados:

| Ferramenta | Versão Mínima | Verificação |
|---|---|---|
| Docker Desktop | 4.30+ (Engine 26+) | `docker --version` |
| Docker Compose | v2 (plugin nativo) | `docker compose version` |
| Python no WSL2 | 3.11+ | `python3 --version` |
| Poetry | 1.8+ | `poetry --version` |
| Git | 2.40+ | `git --version` |

---

### PASSO 1 — Clonagem e Abertura do Ambiente

```bash
#!/usr/bin/env bash
# =============================================================================
# PASSO 1: Clonagem e estrutura inicial do projeto
# Execute dentro do terminal Ubuntu-22.04 (WSL2)
# =============================================================================

# ── 1.1: Clonar o repositório
git clone https://github.com/sua-org/socialselling.git
cd socialselling

# ── 1.2: Criar os diretórios de volume persistente para o Docker
# (devem existir ANTES do primeiro `docker compose up`)
mkdir -p volumes/postgres volumes/redis

# ── 1.3: Criar o arquivo .env a partir do template
cp .env.example .env

# ── 1.4: Editar o .env com as credenciais reais
# OBRIGATÓRIO: preencher OPENAI_API_KEY e TAVILY_API_KEY antes de prosseguir
nano .env
# Ou: code .env  (abre no VS Code via WSL2 Remote Extension)

# ── 1.5: Verificar a estrutura do projeto
ls -la
# Saída esperada (estrutura mínima):
# drwxr-xr-x  docker/
# drwxr-xr-x  src/
# drwxr-xr-x  tests/
# drwxr-xr-x  volumes/
# -rw-r--r--  .env
# -rw-r--r--  .env.example
# -rw-r--r--  .pre-commit-config.yaml
# -rw-r--r--  docker-compose.yml
# -rw-r--r--  pyproject.toml

echo "✅ Passo 1 concluído: Projeto clonado e estrutura validada."
```

---

### PASSO 2 — Ativação do Docker Compose e Checagem de Logs

```bash
# =============================================================================
# PASSO 2: Subir a Camada de Dados (PostgreSQL + Redis)
# =============================================================================

# ── 2.1: Garantir que o Docker Desktop está rodando (com WSL2 Backend ativo)
docker info | grep -E "Server Version|Operating System|Architecture"
# Se retornar erro, abra o Docker Desktop no Windows e aguarde inicializar.

# ── 2.2: Subir os contêineres em modo detached (background)
docker compose up -d

# Saída esperada:
# [+] Running 3/3
#  ✔ Network socialselling_socialselling_net  Created
#  ✔ Container ss_postgres                   Started
#  ✔ Container ss_redis                      Started

# ── 2.3: Aguardar o healthcheck do PostgreSQL passar
echo "Aguardando PostgreSQL ficar saudável..."
until docker compose exec postgres pg_isready -U ss_admin -d socialselling; do
    echo "  PostgreSQL ainda inicializando... aguardando 3s"
    sleep 3
done
echo "✅ PostgreSQL está saudável e pronto para receber conexões."

# ── 2.4: Verificar logs do PostgreSQL (confirmar execução do init.sql)
docker compose logs postgres | grep -E "NOTICE|ERROR|FATAL|LOG"
# Saída esperada (trecho dos logs do init.sql):
# ss_postgres  | NOTICE:  === SocialSelling DDL: Inicialização atômica concluída ===
# ss_postgres  | NOTICE:      Extensões: pg_trgm, uuid-ossp, pg_stat_statements, unaccent
# ss_postgres  | NOTICE:      Tabelas: leads, scraper_runs, agent_events, outreach_campaigns
# ss_postgres  | NOTICE:      View: v_observabilidade_cognitiva
# ss_postgres  | NOTICE:      Índices: 10 índices (BTREE + GIN trigrama)

# ── 2.5: Verificar logs do Redis
docker compose logs redis | tail -10
# Saída esperada:
# ss_redis  | Ready to accept connections

# ── 2.6: Testar conectividade com o Redis
docker compose exec redis redis-cli -a "Redis@SocialSelling2024" ping
# Saída esperada: PONG

# ── 2.7: Verificar as tabelas criadas no PostgreSQL
docker compose exec postgres psql -U ss_admin -d socialselling \
    -c "\dt socialselling.*"
# Saída esperada:
#              List of relations
#  Schema        | Name                | Type  | Owner
# ---------------+---------------------+-------+----------
#  socialselling | agent_events        | table | ss_admin
#  socialselling | leads               | table | ss_admin
#  socialselling | outreach_campaigns  | table | ss_admin
#  socialselling | scraper_runs        | table | ss_admin

# ── 2.8: Verificar status geral dos contêineres
docker compose ps
# Ambos devem mostrar STATUS: healthy

echo "✅ Passo 2 concluído: Camada de dados ativa e validada."
```

---

### PASSO 3 — Instalação das Dependências e Carga do `.env`

```bash
# =============================================================================
# PASSO 3: Instalar dependências com Poetry e carregar variáveis de ambiente
# =============================================================================

# ── 3.1: Confirmar que o Poetry usa Python 3.11
poetry env use python3.11

# ── 3.2: Instalar todas as dependências (incluindo grupo dev)
# O flag --sync garante que nenhuma dependência extra esteja instalada
poetry install --sync

# Saída esperada (trecho):
# Installing dependencies from lock file
# Package operations: XX installs, 0 updates, 0 removals
#   ...
# Installing the current project: socialselling (0.1.0)

# ── 3.3: Verificar que o .venv foi criado DENTRO do projeto
ls -la .venv/
# Saída esperada: diretório .venv/ presente na raiz do projeto

# ── 3.4: Verificar instalação das dependências críticas
poetry run python -c "
import langgraph
import langchain_openai
import fastapi
import sqlalchemy
import jellyfish
print('✅ Todas as dependências críticas importadas com sucesso.')
print(f'   LangGraph: {langgraph.__version__}')
print(f'   FastAPI: {fastapi.__version__}')
print(f'   SQLAlchemy: {sqlalchemy.__version__}')
"

# ── 3.5: Carregar variáveis do .env para a sessão atual do shell
# O python-dotenv (incluído via pydantic-settings) carrega automaticamente,
# mas para uso interativo no shell, exportamos manualmente:
set -a  # export automático de todas as variáveis
source .env
set +a  # desativa o export automático

# ── 3.6: Verificar que as variáveis críticas estão carregadas
echo "POSTGRES_HOST=${POSTGRES_HOST}"
echo "REDIS_HOST=${REDIS_HOST}"
echo "OPENAI_API_KEY=${OPENAI_API_KEY:0:10}...   (truncado por segurança)"
echo "TAVILY_API_KEY=${TAVILY_API_KEY:0:10}...   (truncado por segurança)"

# ── 3.7: Instalar os pre-commit hooks no repositório local
poetry run pre-commit install
poetry run pre-commit install --hook-type commit-msg
echo "✅ Pre-commit hooks instalados."

echo "✅ Passo 3 concluído: Dependências instaladas e ambiente configurado."
```

---

### PASSO 4 — Inicialização do Servidor FastAPI com Hot-reload

```bash
# =============================================================================
# PASSO 4: Iniciar o servidor FastAPI via Uvicorn com hot-reload
# =============================================================================

# ── Comando principal de inicialização do servidor
# Flags explicadas:
# src.socialselling.main:app  → módulo Python + objeto FastAPI (app)
# --host 0.0.0.0              → aceita conexões de qualquer interface
#                               (necessário para acesso via browser no Windows
#                               graças ao networkingMode=mirrored do WSL2)
# --port 8000                 → porta padrão da aplicação
# --reload                    → hot-reload: reinicia o servidor ao detectar
#                               mudanças em qualquer arquivo .py do src/
# --reload-dir src/           → monitora apenas o diretório src/ (não testes)
# --log-level debug           → logs detalhados em ambiente de desenvolvimento
# --workers 1                 → 1 worker em dev (hot-reload só funciona com 1)

poetry run uvicorn src.socialselling.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --reload-dir src/ \
    --log-level debug \
    --workers 1

# =============================================================================
# ALTERNATIVA: Script de inicialização com validação prévia
# Salve como: scripts/start_dev.sh
# =============================================================================

cat > scripts/start_dev.sh << 'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail

echo "🚀 Iniciando SocialSelling Dev Server..."

# Validar que os contêineres estão rodando
if ! docker compose ps | grep -q "healthy"; then
    echo "❌ Docker Compose não está saudável. Execute: docker compose up -d"
    exit 1
fi

# Carregar variáveis de ambiente
set -a
source .env
set +a

# Validar variáveis críticas
: "${OPENAI_API_KEY:?ERRO: OPENAI_API_KEY não definida no .env}"
: "${TAVILY_API_KEY:?ERRO: TAVILY_API_KEY não definida no .env}"
: "${DATABASE_URL:?ERRO: DATABASE_URL não definida no .env}"

echo "✅ Variáveis de ambiente validadas."
echo "🌐 Servidor disponível em: http://localhost:8000"
echo "📚 Documentação Swagger: http://localhost:8000/docs"
echo "📖 Documentação ReDoc:   http://localhost:8000/redoc"
echo ""
echo "⌨️  Pressione CTRL+C para encerrar."
echo ""

# Iniciar o servidor
poetry run uvicorn src.socialselling.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --reload-dir src/ \
    --log-level debug \
    --workers 1
SCRIPT

chmod +x scripts/start_dev.sh

# Saída esperada ao iniciar o servidor:
# INFO:     Will watch for changes in these directories: ['/.../src']
# INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
# INFO:     Started reloader process [XXXX] using WatchFiles
# INFO:     Started server process [XXXX]
# INFO:     Waiting for application startup.
# INFO:     Application startup complete.

# Para acessar do browser Windows:
# http://localhost:8000/docs  ← Swagger UI
# http://localhost:8000/redoc ← ReDoc
```

---

### PASSO 5 — Execução da Suíte de Testes (BDD e Unitários)

```bash
# =============================================================================
# PASSO 5: Executar a suíte completa de validação local
# =============================================================================

# ── 5.1: Rodar APENAS os testes unitários (herméticos, sem Docker necessário)
# Estes devem passar em qualquer ambiente, sem serviços externos rodando.
poetry run pytest tests/unit/ \
    -v \
    --tb=short \
    -m "unit" \
    --no-header

# ── 5.2: Rodar os testes de BDD (cenários Gherkin)
poetry run pytest tests/bdd/ \
    -v \
    --tb=short \
    -m "bdd" \
    --no-header

# ── 5.3: Rodar a suíte COMPLETA (unitários + BDD) com relatório de cobertura
poetry run pytest tests/ \
    -v \
    --tb=short \
    -m "unit or bdd" \
    --cov=src/socialselling \
    --cov-report=term-missing \
    --cov-report=html:htmlcov \
    --cov-fail-under=80 \
    --no-header

# ── 5.4: Rodar APENAS os testes de integração (requer Docker Compose ativo)
poetry run pytest tests/integration/ \
    -v \
    --tb=long \
    -m "integration" \
    --no-header

# ── 5.5: Rodar todos os testes com output XML (para CI/CD)
poetry run pytest tests/ \
    -m "unit or bdd" \
    --junitxml=reports/junit.xml \
    --cov=src/socialselling \
    --cov-report=xml:reports/coverage.xml \
    -q

# ── 5.6: Abrir o relatório de cobertura no browser Windows
# (graças ao networkingMode=mirrored, um servidor HTTP local é acessível)
python3 -m http.server 8080 --directory htmlcov &
echo "📊 Relatório de cobertura disponível em: http://localhost:8080"
# Acesse no browser do Windows: http://localhost:8080

# =============================================================================
# REFERÊNCIA DE COMANDOS RÁPIDOS (CHEATSHEET)
# =============================================================================

# Rodar um teste específico por nome
poetry run pytest tests/ -k "test_research_node_returns_enriched_state" -v

# Rodar com captura de output do print() desabilitada (útil para debug)
poetry run pytest tests/unit/ -v -s

# Rodar com failfast (para no primeiro erro)
poetry run pytest tests/ -m "unit" --failfast

# Listar todos os testes disponíveis sem executar
poetry run pytest tests/ --collect-only -q

# Verificar os markers disponíveis
poetry run pytest --markers
```

---

### PASSO 6 — Comandos de Manutenção e Troubleshooting

```bash
# =============================================================================
# MANUTENÇÃO DO AMBIENTE
# =============================================================================

# ── Parar todos os contêineres (preserva dados nos volumes)
docker compose stop

# ── Parar E remover contêineres (preserva volumes)
docker compose down

# ── RESET COMPLETO: Remove contêineres E volumes (APAGA DADOS DO BANCO)
docker compose down -v
rm -rf volumes/postgres/* volumes/redis/*

# ── Ver logs em tempo real de um serviço específico
docker compose logs -f postgres
docker compose logs -f redis

# ── Acessar o PostgreSQL interativamente
docker compose exec postgres psql -U ss_admin -d socialselling

# Queries úteis no psql:
# \dt socialselling.*          → listar tabelas
# \di socialselling.*          → listar índices
# SELECT * FROM v_observabilidade_cognitiva LIMIT 10;  → view de observabilidade
# \q                           → sair

# ── Acessar o Redis interativamente
docker compose exec redis redis-cli -a "Redis@SocialSelling2024"

# Comandos úteis no redis-cli:
# INFO memory                  → uso de memória
# DBSIZE                       → número de chaves
# KEYS scraper:*               → listar chaves de scrapers
# TTL <chave>                  → ver TTL de uma chave
# MONITOR                      → monitorar comandos em tempo real

# ── Atualizar dependências do Poetry
poetry update                  # atualiza dentro dos constraints do pyproject.toml
poetry show --outdated         # mostra dependências desatualizadas

# ── Limpar cache do Poetry
poetry cache clear --all pypi

# ── Limpar cache do pytest e MyPy
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true

# ── Verificar uso de memória do WSL2 (deve respeitar o limite de 8 GB)
free -h
cat /proc/meminfo | grep -E "MemTotal|MemFree|MemAvailable|Buffers|Cached"

# ── Verificar uso de CPU (deve usar no máximo 4 cores)
nproc
top -bn1 | head -5
```

---

### Diagrama de Dependências de Boot

```
ORDEM OBRIGATÓRIA DE INICIALIZAÇÃO
===================================

[1] Windows Host
    └─► [Verificar] .wslconfig aplicado + WSL2 reiniciado

[2] Docker Desktop (Windows App)
    └─► WSL2 Backend ativo

[3] docker compose up -d
    ├─► ss_postgres (PostgreSQL 16)
    │       └─► init.sql executa automaticamente no 1º boot
    │               ├─► Extensões (pg_trgm, uuid-ossp...)
    │               ├─► Tabelas (leads, agent_events...)
    │               ├─► Índices (BTREE + GIN trigrama)
    │               └─► View (v_observabilidade_cognitiva)
    └─► ss_redis (Redis 7.2)
            └─► redis.conf aplicado (volatile-lru, 384 MB)

[4] poetry install --sync
    └─► .venv/ criado dentro do projeto

[5] source .env
    └─► Variáveis de ambiente carregadas na sessão

[6] pre-commit install
    └─► Hooks instalados em .git/hooks/

[7a] poetry run uvicorn ...   ← Desenvolvimento
[7b] poetry run pytest ...    ← Testes
```

---

*Guia gerado para o Projeto SocialSelling — Versão 1.0.0*  
*Stack: WSL2 + Docker + PostgreSQL 16 + Redis 7 + Poetry + LangGraph + FastAPI*
