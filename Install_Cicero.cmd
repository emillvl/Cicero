@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -m venv .venv
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Install Python 3.11 or later, then run this installer again.
        pause
        exit /b 1
    )
    python -m venv .venv
)
if errorlevel 1 (
    echo Could not create the local Python environment.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Installation did not finish. Check your internet connection and try again.
) else (
    echo Installation complete. Run Start_Cicero.cmd.
)
pause
