# Cerimônia de entrega de WU (Work Unit) — P6 / ADR-011.
# Uso: ./scripts/ship_wu.ps1 -WU "WU-T5" -Branch "feat/wu-t5-ui" [-CardId "PVTI_..."] [-PRTitle "feat(portal): WU-T5 — ..."]
# Pré-condições:
#   - Branch criada e arquivos já editados/staged
#   - GITHUB_TOKEN ou gh autenticado
#   - Variável de ambiente: PROJECT_ID (PVT_...) e STATUS_FIELD_ID (PVTSSF_...)
#     (fallback: valores do projeto SocialSelling)
param(
    [Parameter(Mandatory)][string]$WU,
    [Parameter(Mandatory)][string]$Branch,
    [string]$CardId = "",
    [string]$PRTitle = "",
    [string]$CommitMsg = "",
    [string]$ProjectId   = "PVT_kwHOAAi2gM4BZ3J3",
    [string]$StatusFieldId = "PVTSSF_lAHOAAi2gM4BZ3J3zhUy5Jg",
    [string]$DoneOptionId   = "98236657",
    [switch]$SkipGate,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$venvPy = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
$py = if (Test-Path $venvPy) { $venvPy } else { "py" }

function Log($msg, $color = "Cyan") { Write-Host "[$WU] $msg" -ForegroundColor $color }
function Run($cmd) {
    if ($DryRun) { Write-Host "[DRY-RUN] $cmd" -ForegroundColor DarkGray; return }
    Invoke-Expression $cmd
    if ($LASTEXITCODE -ne 0) { throw "Comando falhou (exit $LASTEXITCODE): $cmd" }
}

# ── 1. Gate ────────────────────────────────────────────────────────────────────
if (-not $SkipGate) {
    Log "Rodando gate (check_licoes + ruff + mypy + pytest)..."
    & $py scripts/check_licoes.py; if ($LASTEXITCODE -ne 0) { throw "check_licoes falhou" }
    & $py -m ruff check .;          if ($LASTEXITCODE -ne 0) { throw "ruff falhou" }
    & $py -m mypy;                  if ($LASTEXITCODE -ne 0) { throw "mypy falhou" }
    & $py -m pytest -q;             if ($LASTEXITCODE -ne 0) { throw "pytest falhou" }
    Log "Gate verde." "Green"
} else {
    Log "Gate ignorado (--SkipGate)." "Yellow"
}

# ── 2. Commit (se há mudanças) ─────────────────────────────────────────────────
$status = git status --porcelain
if ($status) {
    if (-not $CommitMsg) {
        $CommitMsg = "feat(portal): $WU — implementacao completa`n`nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
    }
    Log "Commitando mudanças..."
    $msgFile = [System.IO.Path]::GetTempFileName()
    Set-Content -Path $msgFile -Value $CommitMsg -Encoding UTF8
    Run "git add -A"
    Run "git commit -F `"$msgFile`""
    Remove-Item $msgFile -ErrorAction SilentlyContinue
} else {
    Log "Nenhuma mudança para commitar — branch já commitada." "Yellow"
}

# ── 3. Push ────────────────────────────────────────────────────────────────────
Log "Push de $Branch..."
Run "git push -u origin $Branch"

# ── 4. PR ─────────────────────────────────────────────────────────────────────
if (-not $PRTitle) { $PRTitle = "feat(portal): $WU — entrega automatica" }
Log "Criando PR..."
$prUrl = ""
if (-not $DryRun) {
    $prUrl = gh pr create --base main --title $PRTitle --body "Entrega automatica de $WU via ship_wu.ps1.`n`n:robot: Generated with [Claude Code](https://claude.com/claude-code)"
    Write-Host "PR criado: $prUrl"
}

# ── 5. Auto-merge + aguardar CI ───────────────────────────────────────────────
Log "Ativando auto-merge (squash)..."
$prNum = if ($prUrl -match "/(\d+)$") { $matches[1] } else { "" }
if ($prNum -and -not $DryRun) {
    gh pr merge $prNum --squash --auto --delete-branch
    Log "Aguardando CI..."
    gh pr checks $prNum --watch
    $merged = gh pr view $prNum --json state --jq ".state"
    if ($merged -ne "MERGED") {
        Log "PR ainda não mergeado; aguardando mais 30s..." "Yellow"
        Start-Sleep 30
        $merged = gh pr view $prNum --json state --jq ".state"
    }
    if ($merged -eq "MERGED") {
        Log "PR $prNum mergeado." "Green"
    } else {
        Log "PR $prNum não mergeado automaticamente. Verifique manualmente." "Red"
    }
}

# ── 6. Pull main ──────────────────────────────────────────────────────────────
Log "Pull da main..."
Run "git checkout main"
Run "git pull"

# ── 7. Mover card para Done ────────────────────────────────────────────────────
if ($CardId -and -not $DryRun) {
    Log "Movendo card $CardId para Done..."
    gh project item-edit --project-id $ProjectId --id $CardId --field-id $StatusFieldId --single-select-option-id $DoneOptionId
    Log "Card movido para Done." "Green"
} elseif (-not $CardId) {
    Log "CardId não fornecido — mover o card manualmente." "Yellow"
}

Log "Entrega de $WU concluída." "Green"
