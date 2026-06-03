Aqui está um modelo de prompt (meta-prompt) estruturado para gerar um novo ficheiro `hypotheses_catalog.json`. Este prompt foi desenhado para respeitar estritamente as regras de validação Pydantic definidas no ficheiro `src/socialselling/contracts.py`, que proíbe campos adicionais (`extra="forbid"`), e segue a mesma filosofia de automação do gerador de ICP presente em `docs/prompts/gerar-icp.md`.

### Ficheiro de Prompt — Gerar `hypotheses_catalog.json`

Cole o bloco de texto abaixo num LLM (como Claude ou Gemini), preencha a secção **CONTEXTO DAS HIPÓTESES DO MERCADO** e guarde o JSON resultante no caminho `config/hypotheses_catalog.json`.

Para validar o ficheiro gerado contra o contrato de dados do projeto, utilize o seguinte comando no seu terminal local:

```bash
py -c "import json; from socialselling.contracts import HypothesisCatalog; HypothesisCatalog.model_validate(json.load(open('config/hypotheses_catalog.json', encoding='utf-8'))); print('Catálogo válido')"

```

---

```text
Você é um Engenheiro de Dados e Especialista em GTM B2B de elite. O seu objetivo é gerar um ficheiro "hypotheses_catalog.json" VÁLIDO para o sistema de inteligência de prospecção SocialSelling a partir do contexto fornecido abaixo. Este catálogo define as hipóteses de dor latente que o motor Bayesiano irá avaliar com base nas evidências web colhidas.

## CONTEXTO DAS HIPÓTESES DO MERCADO (Preencha com as dores/estados do seu público-alvo)
- Setor e Perfil Alvo: 
- Hipótese 1 (Descrição da dor/situação latente): 
  * Sinais de superfície esperados (Ex: termos em vagas, comportamento em posts): 
  * Probabilidade a priori (Prior estimado entre 0.0 e 1.0): 
- Hipótese 2 (Descrição da dor/situação latente): 
  * Sinais de superfície esperados: 
  * Probabilidade a priori (Prior estimado entre 0.0 e 1.0): 
- Hipótese 3 (Descrição da dor/situação latente): 
  * Sinais de superfície esperados: 
  * Probabilidade a priori (Prior estimado entre 0.0 e 1.0): 

## SCHEMA OBRIGATÓRIO (Não adicione, altere ou remova campos — validação extra="forbid")
{
  "hypotheses": [
    {
      "hypothesis_id": "string identificadora curta (Ex: H_01, H_02)",
      "description": "descrição concisa da dor teórica ou estado do lead (string)",
      "prior": "float entre 0.0 e 1.0 representando a probabilidade inicial",
      "surface_signals": ["lista de strings com os identificadores de sinais esperados"],
      "sources": ["lista de strings com as fontes de dados ex: job_boards, web_search, social_media"]
    }
  ]
}

## DIRETRIZES DE CONFIGURAÇÃO E NEGÓCIO
1. prior: Deve ser um número de ponto flutuante estritamente entre 0.0 e 1.0. Nota: a soma dos priors do catálogo NÃO precisa ser igual a 1.0, visto que cada hipótese descreve um estado latente independente.
2. surface_signals: Devem ser escritos em snake_case ou como termos textuais limpos que possam ser correlacionados com os censores de busca.
3. Mantenha o catálogo enxuto para o escopo do PoC, idealmente focado em 3 a 5 hipóteses primárias de forte aderência comercial.

## SAÍDA ESPERADA
Responda APENAS com o JSON válido — sem formatação markdown (sem ```json), sem comentários inline no código e sem qualquer texto explicativo antes ou depois da estrutura.

## EXEMPLO DE REFERÊNCIA (ESTRUTURA E ESTILO)
{
  "hypotheses": [
    {
      "hypothesis_id": "H_01",
      "description": "Estresse de crescimento de infraestrutura cloud.",
      "prior": 0.25,
      "surface_signals": ["contratacao_sre", "aumento_vagas_tecnicas", "uso_aws"],
      "sources": ["job_boards", "web_search"]
    }
  ]
}

```