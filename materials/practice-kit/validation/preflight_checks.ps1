# Author regression checks with synthetic commands; no Docker/WSL side effects.
$ErrorActionPreference = 'Stop'
$scriptPath = Join-Path $PSScriptRoot '../scripts/preflight.ps1'
$logPath = Join-Path $PSScriptRoot '../work/preflight.txt'
$global:reviewWslExitCode = 0

function wsl {
    $global:LASTEXITCODE = $global:reviewWslExitCode
    Write-Output 'synthetic WSL diagnostic'
}

function docker {
    $global:LASTEXITCODE = 0
    Write-Output 'synthetic Docker diagnostic'
}

$savedSearchPath = $env:PATH
try {
    # An absent executable must fail even after a successful command.
    $env:PATH = ''
    & $scriptPath
    if ($LASTEXITCODE -ne 1) {
        throw 'Missing executable was accepted'
    }
    $log = Get-Content -Raw -Encoding UTF8 -LiteralPath $logPath
    if ($log -notmatch 'FAILED: nvidia-smi' -or $log.Contains([char]0)) {
        throw 'Missing executable or UTF-8 log regression'
    }

    function nvidia-smi {
        $global:LASTEXITCODE = 0
        Write-Output 'synthetic GPU diagnostic'
    }
    $global:reviewWslExitCode = 4
    & $scriptPath
    if ($LASTEXITCODE -ne 1) {
        throw 'Nonzero native exit code was accepted'
    }
    $log = Get-Content -Raw -Encoding UTF8 -LiteralPath $logPath
    if ($log -notmatch 'EXIT CODE: 4') {
        throw 'Native failure was not recorded'
    }

    $global:reviewWslExitCode = 0
    & $scriptPath
    if ($LASTEXITCODE -ne 0) {
        throw 'Successful diagnostics failed'
    }
    Write-Output 'Preflight reference checks: 3 passed (synthetic commands only)'
}
finally {
    $env:PATH = $savedSearchPath
}
