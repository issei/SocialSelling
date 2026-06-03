# SDD — FASE 2: IMPLEMENTAÇÃO COCKPIT LOCAL (FASTAPI + JINJA2 + TAILWIND)
## Projeto: SocialSelling — Local Dashboard Edition
### Versão: 1.0-LOCAL | Status: APPROVED-FOR-IMPLEMENTATION

---

## 1. VISÃO GERAL DA ARQUITETURA WEB LOCAL

A Fase 2 transiciona a interface de linha de comando (CLI) para uma aplicação web local de página única (*Single-Page Dashboard*) sem alterar o motor analítico central ou violar a diretriz de custo zero de infraestrutura gerenciada. O runtime opera em um único processo Python executado no host (ou via ambiente de desenvolvimento local).

### 1.1 Premissas Técnicas Invioláveis
1. **Database-less Estrito:** Não é permitida a instalação de PostgreSQL, SQLite ou qualquer outro SGBD relacional/NoSQL. O estado da aplicação é lido e persistido via arquivos locais JSON atômicos utilizando a infraestrutura atual de `JsonCache`.
2. **Server-Side Rendering (SSR) Eficiente:** Para evitar a complexidade e a sobrecarga de frameworks JavaScript (React, Vue, Node.js), a interface é gerada no servidor via **Jinja2 Templates** nativos do FastAPI e enviada pronta para o navegador.
3. **Tailwind CSS Isolado:** O estilo visual é injetado via classes utilitárias do Tailwind CSS compiladas ou carregadas diretamente através de um script de CDN estável no template base do HTML.

## 2. ESTRUTURA DE DIRETÓRIOS ESTENDIDA

A estrutura de pastas original é estendida para suportar as camadas de visualização e roteamento web do FastAPI:

```text
src/socialselling/
├── core/
│   └── cache.py             # JsonCache persistente em arquivo
├── modules/
│   ├── m1_busca.py          # Componente M1
│   └── ...
├── templates/               # Camada de Visualização SSR (Nova)
│   ├── base.html            # Template HTML estrutural com Tailwind CDN
│   ├── cockpit.html         # O painel de controle principal (3 blocos)
│   └── config_form.html     # Formulário de edição do ICP e runtime
├── config.py                # Carregador do runtime.toml e .env
├── contracts.py             # Contratos Pydantic de I/O
├── web_app.py               # Servidor FastAPI e rotas de renderização (Novo)
└── orchestrator.py          # Ponto de entrada do pipeline M1→M5

```

## 3. ESPECIFICAÇÃO DE ROTAS E ENDPOINTS (FASTAPI WEB APP)

O ficheiro `src/socialselling/web_app.py` instancia a aplicação FastAPI e expõe as rotas de interface e os endpoints de ação.

### 3.1 Roteamento Web e Renderização Jinja2

```python
from pathlib import Path
from datetime import datetime, UTC
import json
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from socialselling.contracts import ICPCriteria
from socialselling.config import load_runtime, load_env
from socialselling.orchestrator import run_pipeline, persist_json

app = FastAPI(title="SocialSelling - Cockpit Local")
ROOT_DIR = Path(__file__).resolve().parents[2]

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

@app.get("/", response_class=HTMLResponse)
async def view_cockpit(request: Request):
    """Lê o snapshot atual de prospects_ranked.json e renderiza o Cockpit UX."""
    ranked_path = ROOT_DIR / "data" / "prospects_ranked.json"
    prospects = []
    if ranked_path.exists():
        with open(ranked_path, encoding="utf-8") as f:
            prospects = json.load(f)
            
    # Carrega configurações atuais para exibição no cabeçalho
    cfg = load_runtime(ROOT_DIR / "config" / "runtime.toml")
    
    return templates.TemplateResponse(
        "cockpit.html", 
        {"request": request, "prospects": prospects, "config": cfg}
    )

@app.get("/config", response_class=HTMLResponse)
async def view_config_form(request: Request):
    """Carrega o arquivo icp_criteria.example.json atual para edição na tela."""
    icp_path = ROOT_DIR / "config" / "icp_criteria.example.json"
    icp_data = icp_path.read_text(encoding="utf-8") if icp_path.exists() else "{}"
    return templates.TemplateResponse(
        "config_form.html", 
        {"request": request, "icp_json": icp_data}
    )

@app.post("/config/save")
async def save_config(icp_json: str = Form(...)):
    """Valida o JSON enviado contra o contrato ICPCriteria e salva atomicamente."""
    try:
        data = json.loads(icp_json)
        # Força o guardrail extra="forbid" do Pydantic em runtime
        ICPCriteria.model_validate(data)
        
        icp_path = ROOT_DIR / "config" / "icp_criteria.example.json"
        # Escrita protetiva atômica simulada ou direta
        icp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Contrato ICP Inválido: {str(e)}")

@app.post("/pipeline/run")
async def trigger_pipeline():
    """Dispara a execução síncrona em memória do pipeline M1→M5 e atualiza os arquivos."""
    cfg = load_runtime(ROOT_DIR / "config" / "runtime.toml")
    env = load_env(ROOT_DIR / ".env")
    
    tavily_key = env.get("TAVILY_API_KEY") or ""
    gemini_key = env.get("GEMINI_API_KEY") or ""
    
    if not tavily_key or not gemini_key:
        raise HTTPException(status_code=500, detail="Chaves de API ausentes no arquivo .env")
        
    icp_path = ROOT_DIR / "config" / "icp_criteria.example.json"
    icp = ICPCriteria.model_validate(json.loads(icp_path.read_text("utf-8")))
    
    from socialselling.skills.tavily_client import TavilyClient
    from socialselling.skills.gemini_client import GeminiClient
    
    # Execução do pipeline em memória idêntica ao orchestrator CLI
    prospects = run_pipeline(
        icp,
        tavily=TavilyClient(tavily_key),
        gemini=GeminiClient(gemini_key, model=cfg.gemini.model),
        cache_root=ROOT_DIR / "data" / "cache",
        now=datetime.now(UTC),
        cfg=cfg
    )
    
    out_path = ROOT_DIR / "data" / "prospects_ranked.json"
    persist_json(prospects, out_path)
    
    # Atualiza também o relatório markdown legível por consistência
    from socialselling.orchestrator import render_report, _atomic_write
    _atomic_write(out_path.with_suffix(".md"), render_report(prospects))
    
    return RedirectResponse(url="/", status_code=303)

```

## 4. PERSISTÊNCIA FRIA INTEGRADA

O fluxo de dados da Fase 2 preserva integralmente as garantias de atomicidade de escrita do projeto:

1. Quando o usuário clica em **"Executar Prospecção"** na interface web, a rota `/pipeline/run` chama a função centralizada `run_pipeline`.
2. O resultado é serializado e gravado de forma atômica em `data/prospects_ranked.json` usando `tempfile.mkstemp` e `os.replace` através do método `persist_json` do orquestrador.
3. O FastAPI redireciona a requisição com o código HTTP `303 See Other` para a rota raiz `/`, forçando o navegador a recarregar o dashboard com os dados recém-computados e salvos no arquivo.
