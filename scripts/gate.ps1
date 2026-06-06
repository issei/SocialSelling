# Quality gate do PoC: lint + tipos + testes (CLAUDE.md secao 4).
# Uso:  ./scripts/gate.ps1
# Nota: preferimos o Python do .venv (onde vivem ruff/mypy/pytest); senao caimos
#       em 'py' (no Windows o alias 'python' pode cair no stub da Store). Ver L-036.
$ErrorActionPreference = "Stop"

$venvPy = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
$py = if (Test-Path $venvPy) { $venvPy } else { "py" }
Write-Host "Python: $py" -ForegroundColor DarkGray

Write-Host "== ruff ==" -ForegroundColor Cyan
& $py -m ruff check .
if ($LASTEXITCODE -ne 0) { Write-Host "ruff FALHOU" -ForegroundColor Red; exit 1 }

Write-Host "== mypy --strict ==" -ForegroundColor Cyan
& $py -m mypy
if ($LASTEXITCODE -ne 0) { Write-Host "mypy FALHOU" -ForegroundColor Red; exit 1 }

Write-Host "== pytest ==" -ForegroundColor Cyan
& $py -m pytest -q
if ($LASTEXITCODE -ne 0) { Write-Host "pytest FALHOU" -ForegroundColor Red; exit 1 }

Write-Host "GATE OK" -ForegroundColor Green
