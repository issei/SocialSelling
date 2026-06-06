# SocialSelling — PoC local

Busca de clientes mais eficiente e automática usando Inteligência Artificial. Responde à pergunta central: **"Quem devo abordar primeiro?"** gerando um ranking explicável de prospects.

Este é um PoC local, **database-less**, com custo de infraestrutura gerenciada zero (consumo exclusivo de tokens de APIs externas).

Para uma documentação aprofundada voltada para desenvolvedores e agentes de IA, consulte o [llm.txt](https://github.com/issei/SocialSelling/tree/main/llm.txt).

---

## 🛠️ Requisitos e Stack do PoC

*   **Python:** 3.11+
*   **Persistência:** File-Based JSON (fria) + In-Memory (quente). Toda escrita é feita de forma atômica (`write-temp + os.replace`).
*   **Sensores de Busca:** [Tavily API](https://tavily.com) (pesquisas na web) e [Apollo REST API](https://www.apollo.io) (enriquecimento estruturado e descoberta).
*   **Cognição:** [Gemini API](https://ai.google.dev) (`gemini-2.5-flash` ou `gemini-2.5-flash-lite`).

---

## 🚀 Como Iniciar

### Setup Rápido (Recomendado para Windows)
Dê **duplo-clique no arquivo `start.bat`**. Na primeira execução, ele irá:
1. Criar o ambiente virtual (`.venv`).
2. Instalar todas as dependências (desenvolvimento e web).
3. Gerar o arquivo `.env` para você configurar suas chaves de API.
4. Iniciar a interface gráfica local no seu navegador padrão.

*(Para usuários Linux/WSL/macOS, execute o script `./start.sh`)*

### Setup Manual
```bash
# Criar e ativar o ambiente virtual
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1 | Linux/WSL: source .venv/bin/activate

# Instalar dependências (modo editável)
pip install -e ".[dev]"

# Configurar variáveis de ambiente
cp .env.example .env
# Abra o arquivo .env e preencha as chaves: TAVILY_API_KEY, GEMINI_API_KEY e APOLLO_API_KEY
```

---

## 🖥️ Como Executar

### 1. Interface Web Cockpit (Amigável)
Permite visualizar e editar parâmetros de scoring, criar critérios de ICP com auxílio do Gemini, rodar a prospecção e visualizar os **Lead Cards** com canais de contato acionáveis (Instagram-first).
```bash
# Instalar dependências web (se já não estiverem instaladas pelo pip install -e ".[dev]")
pip install -e ".[web]"

# Iniciar o servidor FastAPI local
py -m socialselling.web
# Acesse em http://127.0.0.1:8000
```

### 2. Linha de Comando (CLI)
Para execuções rápidas em terminal de forma síncrona:
```bash
py -m socialselling.orchestrator --icp config/icp_criteria.example.json
# A saída será salva em: data/prospects_ranked.json e data/prospects_ranked.md
```

---

## ⚙️ Arquitetura do Pipeline

O pipeline é composto por 5 módulos síncronos e determinísticos:

```
M1 (Busca/Tavily/Apollo) ──► M2 (Extração/Gemini) ──► M3 (Scoring Linear) ──► M4 (Ranking) ──► M5 (XAI)
```

1.  **M1 (Busca):** Coleta evidências cruas com base nos critérios do ICP ([ICPCriteria](https://github.com/issei/SocialSelling/tree/main/src/socialselling/contracts.py#L83)).
2.  **M2 (Extração):** Extrai entidades de empresas ([CompanyEntity](https://github.com/issei/SocialSelling/tree/main/src/socialselling/contracts.py#L133)) e pessoas ([PersonEntity](https://github.com/issei/SocialSelling/tree/main/src/socialselling/contracts.py#L152)) usando o Gemini em lote.
3.  **M3 (Scoring):** Avalia a aderência do lead combinando pesos de **Fit**, **Intent** (Intenção), **Confidence** (Confiança) e **Persona Fit** sob a fórmula linear do projeto, aplicando filtros estáticos desqualificadores.
4.  **M4 (Ranking):** Ordena os leads gerados com base em algoritmo de tie-break estável e determinístico.
5.  **M5 (Explicação/XAI):** Produz justificativas transparentes ([XAIPayload](https://github.com/issei/SocialSelling/tree/main/src/socialselling/contracts.py#L200)) listando motivadores positivos, negativos e evidências ausentes.

---

## 🧠 Padrões e Combinados de Desenvolvimento

*   **Isolamento Estrito:** Nunca compartilhar referências mutáveis entre as camadas de **Evidência Observada** (M1), **Inferência Gerada** (M2) e **Hipótese Avaliada** (M3/M5).
*   **Mundo Aberto (Open-World Assumption):** A falta de informações sobre um critério não invalida o lead; ela aumenta a incerteza (`Missing Evidence`), reduzindo a confiança final do score de forma gradativa.
*   **Determinismo nos Testes (Sem Rede):** As chamadas de rede externas (Tavily/Gemini/Apollo) são simuladas com payloads JSON reais mockados localizados em `tests/fixtures/`.
*   **Quality Gate Obrigatório:** Antes de cada commit/PR, execute o script de validação local:
    *   No Windows PowerShell: `.\scripts\gate.ps1`
    *   No Linux/WSL: `./scripts/gate.sh`
*   **Treinamento por Feedback:** Através da UI local, a operadora pode marcar 👍/👎 nos leads. O sistema utiliza um modelo de Regressão Logística em Python puro (sem bibliotecas pesadas) que se auto-treina deterministicamente e ajusta os pesos `w_fit` e `w_intent` gradualmente seguindo travas rígidas de segurança (L2, Shrinkage e Clamp).

---

## 📂 Organização de Pastas

| Diretório | Descrição |
|---|---|
| [`config/`](https://github.com/issei/SocialSelling/tree/main/config/) | Parâmetros dinâmicos (`runtime.toml`), catálogo de hipóteses e ICPs de exemplo. |
| [`src/socialselling/`](https://github.com/issei/SocialSelling/tree/main/src/socialselling/) | Código-fonte do produto ([contracts.py](https://github.com/issei/SocialSelling/tree/main/src/socialselling/contracts.py), modules M1–M5, core, skills, web, corpus e learning). |
| [`tests/`](https://github.com/issei/SocialSelling/tree/main/tests/) | Cenários BDD Gherkin (`tests/features/`), fixtures JSON de APIs e testes de contrato. |
| [`docs/`](https://github.com/issei/SocialSelling/tree/main/docs/) | ADRs (decisões arquiteturais), governança (DoR/DoD, modo operacional) e roadmap de planejamento. |
| [`data/`](https://github.com/issei/SocialSelling/tree/main/data/) | *(Ignorado no Git)* Bases locais NDJSON, corpus de leads, feedbacks e histórico de execução. |

---

## 📈 Roadmap & Status Atual

*   **Status do MVP:** Módulos M1 a M5 finalizados e integrados. Interface web local funcional para operação. Suporta busca acumulativa por ondas ([ADR-006](https://github.com/issei/SocialSelling/tree/main/docs/decisions/ADR-006-corpus-acumulativo.md)) e loop de reajuste de pesos por feedback ([ADR-007](https://github.com/issei/SocialSelling/tree/main/docs/decisions/ADR-007-aprendizado-feedback.md)).
*   **Última tag estável:** `v0.17.0` (Busca incremental + Feedback por UI local).
*   **Próxima ação/Bloqueio:** Gravação de fixtures reais do Apollo bloqueadas temporariamente por limitação de entitlement do plano Free (erro 403 API_INACCESSIBLE em People Search). Runtime degrada graciosamente para Tavily.
*   **Visão de Roadmap:** Consulte o plano detalhado de execuções em [docs/planning/execution-plan.md](https://github.com/issei/SocialSelling/tree/main/docs/planning/execution-plan.md).
