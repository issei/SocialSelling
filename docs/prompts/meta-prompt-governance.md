# Meta-Prompt: Criação da Governança e Licenciamento do Repositório (GitHub)

Este arquivo contém o meta-prompt projetado para orientar uma LLM ou ferramenta de geração a criar os arquivos de governança, padrões de contribuição, segurança e o licenciamento proprietário do projeto **SocialSelling**.

---

## Como Utilizar este Meta-Prompt
Copie todo o conteúdo dentro do bloco abaixo e envie para a LLM que será encarregada de criar os arquivos no repositório.

```markdown
Você é um Engenheiro de Software Sênior especialista em DevOps, Governança de Código Aberto/Proprietário e Segurança da Informação. Seu objetivo é gerar uma suíte completa de arquivos de governança e licenciamento para o projeto **SocialSelling** no GitHub.

### 1. Contexto do Projeto SocialSelling
O SocialSelling é uma ferramenta local em Python 3.11+ para descoberta e ranking explicável de leads comerciais. O projeto adota uma arquitetura database-less (JSON atômico em disco), sensores externos (Tavily e Apollo) e cognição via Gemini API.
Os combinados operacionais são rigorosos: o fluxo de desenvolvimento baseia-se no SDD-to-Code Loop (Contratos -> BDD Gherkin -> Impl -> Quality Gate local).

### 2. Instruções de Geração por Arquivo

Você deve gerar o conteúdo exato de cada um dos seguintes arquivos, de acordo com as especificações abaixo:

---

#### ARQUIVO A: LICENSE
Gere o conteúdo de uma licença de software proprietária com código disponível (Source-Available). Esta licença deve:
1. Declarar expressamente os direitos de propriedade intelectual exclusivos de Maurício (ou detentor do repositório).
2. Proibir expressamente qualquer reprodução, distribuição, modificação ou cópia do código e documentação sem consentimento prévio por escrito.
3. Proibir de forma absoluta o uso comercial, direto ou indireto, da solução ou de suas partes.
4. Conter uma cláusula indicando que qualquer pessoa física ou jurídica interessada em uso comercial deve entrar em contato exclusivamente pelo e-mail: **mauricio@issei.com.br**.
5. Manter um tom jurídico profissional de proteção de software proprietário de código aberto para leitura (source-available).

---

#### ARQUIVO B: CODE_OF_CONDUCT.md
Gere um Código de Conduta profissional (baseado no Contributor Covenant adaptado para projetos privados/source-available):
1. Defina as regras de convivência respeitosa e ética entre colaboradores e revisores.
2. Defina os canais de reporte de abusos, indicando o e-mail: **mauricio@issei.com.br**.

---

#### ARQUIVO C: CONTRIBUTING.md
Gere o guia de contribuição alinhado aos combinados do SocialSelling:
1. Explique o fluxo de desenvolvimento **SDD-to-Code Loop** (especificar contrato em Pydantic -> escrever cenários BDD `.feature` + fixtures -> implementação mínima -> passar testes e analisadores estáticos).
2. Explique os portões de qualidade:
   - **DoR (Definition of Ready):** A tarefa só inicia se tiver objetivo claro, contrato fechado e cenários Gherkin felizes/degradados/open-world definidos.
   - **DoD (Definition of Done):** A tarefa só fecha com cenários BDD verdes, mock 100% de rede, `ruff` + `mypy --strict` + `pytest` verdes, PR via branch e auto-merge.
3. Forneça instruções para rodar o Quality Gate:
   - No Windows: `.\scripts\gate.ps1`
   - No Linux/WSL: `./scripts/gate.sh`
4. Instrua sobre nomenclatura de branches (ex: `feat/...` ou `docs/...`) e o uso de Conventional Commits.

---

#### ARQUIVO D: SECURITY.md
Gere a política de segurança do projeto:
1. Instrua os usuários e pesquisadores de segurança a NÃO abrirem issues públicas para relatar vulnerabilidades.
2. Defina o e-mail **mauricio@issei.com.br** como o único canal seguro para reporte de vulnerabilidades.
3. Comprometa-se com uma triagem e resposta a reportes de segurança.

---

#### ARQUIVO E: .github/pull_request_template.md
Gere o template de Pull Request para o GitHub, contendo um checklist interativo para o autor e revisor:
- [ ] O Quality Gate local passou 100% (Ruff + Mypy --strict + Pytest-BDD)?
- [ ] Todas as chamadas externas estão mockadas usando fixtures em `tests/fixtures/`?
- [ ] O isolamento de camadas semânticas foi respeitado?
- [ ] O arquivo `.ai/state/PROGRESS.md` foi atualizado?
- [ ] As lições aprendidas foram descritas em `docs/licoes-aprendidas.md` se houver aprendizado?

---

#### ARQUIVO F: .github/ISSUE_TEMPLATE/bug_report.md
Gere um template de Issue para bugs contendo campos para:
1. Descrição do bug e comportamento esperado.
2. Passos para reprodução (comandos executados, parâmetros passados).
3. Ambiente (SO, versão Python).
4. Logs relevantes ou Cognitive Trace.

---

#### ARQUIVO G: .github/ISSUE_TEMPLATE/feature_request.md
Gere um template de Issue para solicitações de novas funcionalidades ou alterações:
1. Objetivo observável (1 frase).
2. Contrato entrada/saída proposto.
3. Critérios de aceitação rascunhados em Gherkin (Feliz, Degradado, Open-World).
4. Fixtures e dependências mapeadas (alinhado com o DoR).

---

Apresente as respostas em blocos de código markdown individuais com o caminho sugerido de criação de cada arquivo no repositório. Use o idioma Português (Brasil) para toda a documentação, exceto a `LICENSE` que deve ser gerada em Inglês Jurídico por padrão internacional de licenciamento de software.
```
