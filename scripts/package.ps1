# TapDeck PyInstaller Packaging Script
$ErrorActionPreference = 'Stop'
$VenvPython = Join-Path $PSScriptRoot '..\.venv\Scripts\python.exe'
$VenvPyInstaller = Join-Path $PSScriptRoot '..\.venv\Scripts\pyinstaller.exe'

if (-not (Test-Path $VenvPython)) {
    Write-Host 'Virtual environment not found. Run: python -m venv .venv' -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $VenvPyInstaller)) {
    Write-Host 'PyInstaller not installed. Installing build dependencies...' -ForegroundColor Yellow
    & $VenvPython -m pip install pyinstaller
}

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $ProjectRoot

Write-Host 'Building TapDeck standalone executable with PyInstaller...' -ForegroundColor Cyan

& $VenvPython -m PyInstaller `
    --name "TapDeck" `
    --windowed `
    --onedir `
    --noconfirm `
    --clean `
    --add-data "config;config" `
    --hidden-import "sounddevice" `
    --hidden-import "scipy.signal" `
    --hidden-import "PySide6" `
    --paths "src" `
    src/tapdeck/main.py

if ($LASTEXITCODE -ne 0) {
    Write-Host 'Packaging failed!' -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host 'Packaging complete! Output executable is in dist\TapDeck\TapDeck.exe' -ForegroundColor Green
