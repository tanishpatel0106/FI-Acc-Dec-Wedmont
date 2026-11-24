param(
    [string]$UvPython = '',
    [switch]$SkipStudies
)
$ErrorActionPreference = 'Stop'
$setupRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$previousUvLinkMode = $env:UV_LINK_MODE
$previousPythonUtf8 = $env:PYTHONUTF8
$previousNumbaThreads = $env:NUMBA_NUM_THREADS
$previousBlasThreads = $env:OPENBLAS_NUM_THREADS
function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed with exit code ${LASTEXITCODE}: $Executable" }
}
function Invoke-Uv {
    param([string[]]$Arguments)
    if ($UvPython) { Invoke-Checked -Executable $UvPython -Arguments (@('-m','uv') + $Arguments) }
    elseif (Get-Command uv -ErrorAction SilentlyContinue) { Invoke-Checked -Executable 'uv' -Arguments $Arguments }
    else { Invoke-Checked -Executable 'python' -Arguments (@('-m','uv') + $Arguments) }
}
Push-Location -LiteralPath $setupRoot
try {
    $nodeVersion = & node --version
    if ($LASTEXITCODE -ne 0 -or [int]($nodeVersion.TrimStart('v').Split('.')[0]) -lt 22) {
        throw 'Install Node.js 22 or newer before running setup.'
    }
    $env:UV_LINK_MODE = 'copy'
    $env:PYTHONUTF8 = '1'
    $env:NUMBA_NUM_THREADS = '4'
    $env:OPENBLAS_NUM_THREADS = '1'
    Invoke-Uv -Arguments @('sync','--project','backend','--frozen','--extra','dev')
    $backendPython = Join-Path $setupRoot 'backend/.venv/Scripts/python.exe'
    Invoke-Checked -Executable $backendPython -Arguments @('-m','lifecycle.cli','ingest','--offline')
    Invoke-Checked -Executable $backendPython -Arguments @('-m','lifecycle.cli','build-panel')
    if (-not $SkipStudies) {
        Invoke-Checked -Executable $backendPython -Arguments @('-m','lifecycle.cli','seed-v2')
        $runSummary = Get-Content -LiteralPath 'research/results/v2_run_ids.json' -Raw | ConvertFrom-Json
        foreach ($entry in $runSummary.PSObject.Properties) {
            if ($entry.Value.status -eq 'done') { continue }
            if ($entry.Name -eq 'permanent' -and $runSummary.permanent_core_duration.status -eq 'done') {
                Write-Warning 'Gold data are unavailable in this public snapshot; the explicit ex-gold Permanent Portfolio variant was computed.'
                continue
            }
            throw "Study did not complete: $($entry.Name). See research/results/v2_run_ids.json."
        }
    }
    Push-Location -LiteralPath (Join-Path $setupRoot 'web')
    try {
        Invoke-Checked -Executable 'npm.cmd' -Arguments @('ci')
        Invoke-Checked -Executable 'npm.cmd' -Arguments @('run','build')
    } finally { Pop-Location }
    Write-Output 'Public-data installation completed. No WRDS account or credentials were used.'
    Write-Output 'Start the API: backend/.venv/Scripts/python.exe -m uvicorn lifecycle.api.main:app --host 127.0.0.1 --port 8000'
    Write-Output 'Start the frontend in another terminal: npm.cmd run start --prefix web'
    Write-Output 'Open http://localhost:3000. See the integrated research handoff for current findings and source boundaries.'
} finally {
    $env:UV_LINK_MODE = $previousUvLinkMode
    $env:PYTHONUTF8 = $previousPythonUtf8
    $env:NUMBA_NUM_THREADS = $previousNumbaThreads
    $env:OPENBLAS_NUM_THREADS = $previousBlasThreads
    Pop-Location
}
