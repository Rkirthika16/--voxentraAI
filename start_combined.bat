@echo off
echo ===================================================
echo   VoxentraAI -- Combined Full-Stack Launcher
echo ===================================================
cd /d "%~dp0"
if exist backend\venv\Scripts\python.exe (
    backend\venv\Scripts\python.exe run_combined.py
) else (
    python run_combined.py
)
pause
