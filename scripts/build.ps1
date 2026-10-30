# TapDeck Build and Test Runner
$ErrorActionPreference = 'Stop'
$VenvPython = Join-Path $PSScriptRoot '..\.venv\Scripts\python.exe'
if (-not (Test-Path $VenvPython)) {
    Write-Host 'Virtual environment not found. Run: python -m venv .venv' -ForegroundColor Red
    exit 1
}

$env:PYTHONPATH = (Resolve-Path (Join-Path $PSScriptRoot '..\src')).Path

Write-Host '=== Step 1: Running Ruff Linter & Formatter Check ===' -ForegroundColor Cyan
& $VenvPython -m ruff check src tests
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Ruff linting failed!' -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host '=== Step 2: Running Pytest Test Suite ===' -ForegroundColor Cyan
& $VenvPython -m pytest tests -m "not hardware" -v
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Pytest execution failed!' -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host '=== Build verification passed successfully! ===' -ForegroundColor Green
