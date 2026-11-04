param([string]$Image = 'python:3.12-slim')
$ErrorActionPreference = 'Stop'
$kitRoot = Split-Path $PSScriptRoot -Parent
New-Item -ItemType Directory -Force (Join-Path $kitRoot 'work') | Out-Null
$logFile = Join-Path $kitRoot 'work/preflight.txt'
"Preflight UTC: $([DateTime]::UtcNow.ToString('o'))" | Set-Content -Encoding UTF8 $logFile

function Write-PreflightLine {
    param([Parameter(ValueFromPipeline = $true)]$InputObject)
    process {
        # Tee-Object в Windows PowerShell 5.1 дописывает UTF-16 и портит UTF-8-лог.
        $line = [string]$InputObject
        Add-Content -Encoding UTF8 -LiteralPath $logFile -Value $line
        Write-Output $line
    }
}
# Исполняемый файл и аргументы разделены; здесь нет Invoke-Expression.
$diagnostics = @(
    @{ File = 'wsl'; Arguments = @('--status') },
    @{ File = 'wsl'; Arguments = @('--list', '--verbose') },
    @{ File = 'docker'; Arguments = @('context', 'show') },
    @{ File = 'docker'; Arguments = @('version') },
    @{ File = 'docker'; Arguments = @('compose', 'version') },
    @{ File = 'nvidia-smi'; Arguments = @() },
    @{ File = 'docker'; Arguments = @('run', '--rm', '--gpus', 'all', $Image, 'nvidia-smi') }
)
$failed = $false
foreach ($diagnostic in $diagnostics) {
    $executable = $diagnostic.File
    $commandArguments = $diagnostic.Arguments
    $savedConsoleEncoding = [Console]::OutputEncoding
    "COMMAND: $executable $($commandArguments -join ' ')" | Write-PreflightLine
    try {
        # Отсутствующая программа — отдельная ошибка, а не старый LASTEXITCODE.
        Get-Command $executable -ErrorAction Stop | Out-Null
        if ($executable -eq 'wsl') {
            # wsl.exe выводит перенаправленную диагностику в UTF-16LE.
            [Console]::OutputEncoding = [System.Text.Encoding]::Unicode
        }
        & $executable @commandArguments 2>&1 | Write-PreflightLine
        $commandExitCode = $LASTEXITCODE
        "EXIT CODE: $commandExitCode" | Write-PreflightLine
        if ($commandExitCode -ne 0) {
            $failed = $true
        }
    }
    catch {
        $failed = $true
        "FAILED: $executable ($($_.Exception.GetType().Name))" | Write-PreflightLine
    }
    finally {
        [Console]::OutputEncoding = $savedConsoleEncoding
    }
}
if ($failed) {
    Write-Warning 'Есть ошибки; изучите слой отказа. GPU/inference ещё не подтверждены.'
    exit 1
}
Write-Output 'Диагностика завершена. Следующий шаг: tensor CUDA, модель, API и оценка.'
