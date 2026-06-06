# setup_github_project.ps1 - cria o GitHub Project "SocialSelling - SDD Roadmap"
# e popula os cards a partir do historico de .ai/state/PROGRESS.md.
#
# Pre-requisito (uma vez): token com escopo de Projects.
#   gh auth refresh -s project,read:project
#
# Uso:  pwsh scripts/setup_github_project.ps1
# Idempotente-ish: se um project com o mesmo titulo ja existir, reaproveita.

$ErrorActionPreference = "Stop"
$owner = "issei"
$title = "SocialSelling - SDD Roadmap"

function Fail($m) { Write-Error $m; exit 1 }

# 0. Checa escopo
$scopes = (gh auth status 2>&1 | Select-String "Token scopes")
if ($scopes -notmatch "project") {
  Fail "Token sem escopo 'project'. Rode: gh auth refresh -s project,read:project"
}

# 1. Reaproveita ou cria o project
$existing = gh project list --owner $owner --format json | ConvertFrom-Json
$proj = $existing.projects | Where-Object { $_.title -eq $title } | Select-Object -First 1
if ($null -eq $proj) {
  Write-Host "Criando project '$title'..."
  $proj = gh project create --owner $owner --title $title --format json | ConvertFrom-Json
} else {
  Write-Host "Project ja existe (#$($proj.number)); reaproveitando."
}
$number = $proj.number
$projectId = $proj.id
Write-Host "Project #$number  $($proj.url)"

# 2. Descobre o campo Status e os IDs das opcoes (Todo / In Progress / Done)
$fields = gh project field-list $number --owner $owner --format json | ConvertFrom-Json
$status = $fields.fields | Where-Object { $_.name -eq "Status" } | Select-Object -First 1
if ($null -eq $status) { Fail "Campo 'Status' nao encontrado no project." }
$statusFieldId = $status.id

# 2b. Garante a coluna "Backlog" (1a posicao). Recria as opcoes via GraphQL preservando ids.
if (-not ($status.options | Where-Object { $_.name -eq "Backlog" })) {
  Write-Host "Criando coluna 'Backlog'..."
  $q = 'query($org:String!,$num:Int!){ user(login:$org){ projectV2(number:$num){ field(name:"Status"){ ... on ProjectV2SingleSelectField{ options{ id name color description } } } } } }'
  $cur = (gh api graphql -f query=$q -F org=$owner -F num=$number | ConvertFrom-Json).data.user.projectV2.field.options
  $opts = '{ name: "Backlog", color: GRAY, description: "Especificacoes/tarefas ainda nao aprovadas para desenvolvimento" }'
  foreach ($o in $cur) {
    $desc = ($o.description -replace '"','\"')
    $opts += "`n      { id: `"$($o.id)`", name: `"$($o.name)`", color: $($o.color), description: `"$desc`" }"
  }
  $m = "mutation { updateProjectV2Field(input: { fieldId: `"$statusFieldId`", singleSelectOptions: [ $opts ] }) { projectV2Field { ... on ProjectV2SingleSelectField { id } } } }"
  gh api graphql -f query=$m | Out-Null
  # Recarrega as opcoes (agora com Backlog) para o OptId enxergar.
  $fields = gh project field-list $number --owner $owner --format json | ConvertFrom-Json
  $status = $fields.fields | Where-Object { $_.name -eq "Status" } | Select-Object -First 1
}

function OptId($name) {
  $o = $status.options | Where-Object { $_.name -eq $name } | Select-Object -First 1
  if ($null -eq $o) { $o = $status.options | Where-Object { $_.name -like "*$name*" } | Select-Object -First 1 }
  return $o.id
}
$optTodo = OptId "Todo"
$optDone = OptId "Done"
$optBacklog = OptId "Backlog"   # coluna de tarefas ainda nao aprovadas p/ dev

# 3. Cards derivados de PROGRESS.md (Done = entregue/mergeado; Todo = diferido/opcional)
$cards = @(
  @{ t = "Fase 0 - fundacao (toolchain + contratos Pydantic + planejamento)"; s = "Done"; b = "Tag v0.1.0. Toolchain, contratos, plano-mestre." }
  @{ t = "Planejamento + fluxo PR + CI + branch protection"; s = "Done"; b = "Tags v0.1.1. PR #1/#2; CI verde; main protegida (check gate)." }
  @{ t = "WU-1 - M1 Busca/Tavily"; s = "Done"; b = "Tag v0.2.0. Cliente Tavily + cache atomico + degradacao; BDD; fixtures reais." }
  @{ t = "WU-2 - M2 Extracao/Gemini"; s = "Done"; b = "Tag v0.3.0. Cliente Gemini + cache + degradacao; isolamento de camadas; BDD." }
  @{ t = "WU-3 - M3 Score"; s = "Done"; b = "Tag v0.4.0. Modulo puro; Fit/Intent/Confianca; hard filter; determinismo 1e-9." }
  @{ t = "WU-4 - M4 Ranking"; s = "Done"; b = "Tag v0.5.0. Ordenacao p_score desc + tie-break estavel; byte-identico." }
  @{ t = "WU-5 - M5 XAI"; s = "Done"; b = "Tag v0.6.0. Drivers +/- + sinais ausentes + degraded_mode." }
  @{ t = "WU-6 - Orquestrador + Smoke E2E"; s = "Done"; b = "Tag v0.7.0. Pipeline M1->M5 + CLI + persistencia atomica; smoke byte-identico." }
  @{ t = "Motor de intencao (ICP + hipoteses)"; s = "Done"; b = "Tags v0.7.1->v0.8.0. PR #12/#13/#14/#15." }
  @{ t = "Aderencia da busca PT-BR/Instagram + Lead Card"; s = "Done"; b = "Tags v0.8.1->v0.9.0. PR #17; contato no M2; LeadCard acionavel." }
  @{ t = "UI de operador local (FastAPI, ADR-002)"; s = "Done"; b = "Tags v0.10.0->v0.11.x. PR #20..#24; params, assistente Gemini, executar, front-end." }
  @{ t = "Precisao de persona"; s = "Done"; b = "Tag v0.12.0. M2 classifica persona; M3 persona_fit; XAI explica." }
  @{ t = "Launcher + SDD LangGraph (ADR-003)"; s = "Done"; b = "Tag v0.12.1. start.bat/sh (#27); SDD orquestracao paralela+FinOps (#28)." }
  @{ t = "Specs de volume + ADR-004/005/006"; s = "Done"; b = "Docs. SDD+ADR-004 Apollo (#31); roadmap escala + ADR-005/006 (#32)." }
  @{ t = "WU-A1 - Apollo schemas + config"; s = "Done"; b = "Tag v0.13.0. apollo/schemas.py + ApolloCfg + [apollo] runtime (#33)." }
  @{ t = "Fundacao ledgers + corpus"; s = "Done"; b = "Tag v0.14.0. credit_ledger/request_ledger/corpus (#35). L-039/40/41." }
  @{ t = "Descoberta Apollo fim-a-fim (A3/A4/A4b/A4c)"; s = "Done"; b = "Tags v0.14.1->v0.14.4. PR #37/#38/#39/#40. Opt-in, mockado, paridade." }
  @{ t = "Escada Apollo completa (specs de volume)"; s = "Done"; b = "Tags v0.15.0->v0.15.3. corpus no orquestrador (#42); batch+RPD (#43); reveal (#44); org-enrich (#45); fixtures (#46)." }
  @{ t = "Overview + UI redesenhada (tabela + drawer)"; s = "Done"; b = "Tags v0.15.4/v0.16.0. PR #48/#49. L-046/47/48." }
  @{ t = "Feedback (ADR-007) + busca incremental (ADR-006)"; s = "Done"; b = "Tag v0.17.0. like/dislike -> regressao logistica (#54); corpus acumulativo + ondas (#55/#56/#57). L-052..055." }
  @{ t = "Gravar fixtures Apollo reais (supervisionado) + run real calibrado"; s = "Backlog"; b = "OPCIONAL. scripts/record_apollo_fixtures.py (so People Search e gratis); ligar [apollo]/[corpus]/[gemini].rpd_enabled e calibrar mapeamento ICP->filtros (L-024)." }
  @{ t = "ADR-005 - deterministico-primeiro"; s = "Backlog"; b = "Diferido V1+. Roteamento deterministico antes da cognicao." }
  @{ t = "ADR-006 - process-only-new"; s = "Backlog"; b = "Diferido V1+. Processar so leads novos no corpus." }
  @{ t = "ADR-003 - motor LangGraph async (opcional)"; s = "Backlog"; b = "Diferido. Pipeline sincrono e o default/oraculo." }
  @{ t = "Calibracao de pesos [persona]/priors com conversao real"; s = "Backlog"; b = "Backlog (docs/analysis/sondagem-talita.md). Nao bloqueia." }
)

# 4. Cria os itens e seta o Status
$i = 0
foreach ($c in $cards) {
  $i++
  Write-Host "[$i/$($cards.Count)] $($c.t)"
  $item = gh project item-create $number --owner $owner --title $c.t --body $c.b --format json | ConvertFrom-Json
  $optId = switch ($c.s) { "Done" { $optDone } "Backlog" { $optBacklog } default { $optTodo } }
  gh project item-edit --id $item.id --project-id $projectId --field-id $statusFieldId --single-select-option-id $optId | Out-Null
}

Write-Host ""
Write-Host "Pronto. $($cards.Count) cards no board: $($proj.url)"
