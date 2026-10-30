# TapDeck Diagnostics Runner
$ErrorActionPreference = 'Stop'
$VenvPython = Join-Path $PSScriptRoot '..\.venv\Scripts\python.exe'
if (-not (Test-Path $VenvPython)) {
    Write-Host 'Virtual environment not found. Run: python -m venv .venv' -ForegroundColor Red
    exit 1
}
$env:PYTHONPATH = (Resolve-Path (Join-Path $PSScriptRoot '..\src')).Path
Write-Host 'Starting TapDeck in diagnostics mode...' -ForegroundColor Cyan
& $VenvPython -m tapdeck --diagnostics --log-level DEBUG @args
