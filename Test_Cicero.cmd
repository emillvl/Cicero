@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run Install_Cicero.cmd first.
    pause
    exit /b 1
)
echo Installing test dependencies. The tests themselves use no network or API keys.
".venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
if errorlevel 1 (
    echo Test dependencies could not be installed.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m pytest -q --cov=interactive_translator --cov-branch --cov-report=term-missing
if errorlevel 1 (
    echo Tests failed. See the results above.
    pause
    exit /b 1
)
pause
