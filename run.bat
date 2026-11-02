@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    where py >nul 2>nul
    if %errorlevel%==0 (
        py -3 -m venv .venv
    ) else (
        python -m venv .venv
    )
    if errorlevel 1 goto :error
)

echo Installing dependencies (pygame, matplotlib)...
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
if errorlevel 1 goto :error

echo Starting Maze Runner...
".venv\Scripts\python.exe" -m game.main %*
exit /b %errorlevel%

:error
echo.
echo Setup or launch failed. Check that Python 3 is installed and on PATH.
exit /b 1
