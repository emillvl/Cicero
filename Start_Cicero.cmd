@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run Install_Cicero.cmd once before starting Cicero.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" interactive_translator.py
pause
