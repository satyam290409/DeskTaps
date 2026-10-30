# TapDeck 2.0 Launcher
$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $PSScriptRoot
$Pythonw = Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe'
Start-Process -FilePath $Pythonw -ArgumentList "-m tapdeck"
Write-Host "TapDeck 2.0 launched! The Visual Radar is opening on your screen." -ForegroundColor Green
