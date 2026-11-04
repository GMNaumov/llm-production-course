param([string]$Image = 'python:3.12-slim')
$ErrorActionPreference = 'Continue'
$kitRoot = Split-Path $PSScriptRoot -Parent
New-Item -ItemType Directory -Force (Join-Path $kitRoot 'work') | Out-Null
$logFile = Join-Path $kitRoot 'work/preflight.txt'
"Preflight UTC: $([DateTime]::UtcNow.ToString('o'))" | Set-Content -Encoding UTF8 $logFile
$diagnostics = @(
    { wsl --status }, { wsl --list --verbose }, { docker context show },
    { docker version }, { docker compose version }, { nvidia-smi },
    { docker run --rm --gpus all $Image nvidia-smi }
)
$failed = $false
foreach ($diagnostic in $diagnostics) {
    "COMMAND: $diagnostic" | Tee-Object -FilePath $logFile -Append
    & $diagnostic 2>&1 | Tee-Object -FilePath $logFile -Append
    if ($LASTEXITCODE -ne 0) { $failed = $true }
}
if ($failed) { Write-Warning 'Есть ошибки; изучите слой отказа. GPU/inference ещё не подтверждены.'; exit 1 }
Write-Output 'Диагностика завершена. Следующий шаг: tensor CUDA, модель, API и оценка.'
