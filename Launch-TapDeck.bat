@echo off
cd /d "%~dp0"
title TapDeck 2.0 Acoustic HUD
echo ====================================================================
echo                   TapDeck 2.0 Acoustic Radar
echo ====================================================================
echo.
echo Starting acoustic engine and visual radar window...
echo.
echo (Keep this window open or minimize it while using TapDeck)
echo.
"%~dp0.venv\Scripts\python.exe" -m tapdeck
echo.
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo TapDeck encountered an error (exit code: %ERRORLEVEL%).
    pause
)
