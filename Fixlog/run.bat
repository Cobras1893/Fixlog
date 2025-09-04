@echo off
setlocal enabledelayedexpansion
title FixLog - Run (create venv, install, start)

REM === Go to this script's folder ===
cd /d "%~dp0"

REM === 1) Check Python ===
where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found. Please install Python 3.10+ and add it to PATH.
  pause
  exit /b 1
)

REM === 2) Create venv if missing ===
if not exist ".venv" (
  echo [INFO] Creating virtual environment...
  python -m venv .venv
  if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
  )
)

REM === 3) Activate venv ===
call ".venv\Scripts\activate"
if errorlevel 1 (
  echo [ERROR] Failed to activate virtual environment.
  pause
  exit /b 1
)

REM === 4) Upgrade pip ===
python -m pip install --upgrade pip

REM === 5) Install dependencies ===
if exist "requirements.txt" (
  echo [INFO] Installing from requirements.txt...
  pip install -r requirements.txt
) else (
  echo [WARN] requirements.txt not found. Installing Flask only...
  pip install Flask
)

REM === 6) Default Flask env ===
if "%FLASK_APP%"=="" set "FLASK_APP=app.py"
if "%FLASK_RUN_HOST%"=="" set "FLASK_RUN_HOST=0.0.0.0"
if "%FLASK_RUN_PORT%"=="" set "FLASK_RUN_PORT=5000"

REM === 7) Quick check for login.html tip ===
if not exist "templates\login.html" (
  echo [WARN] templates\login.html not found. Make sure your login template exists.
)

REM === 8) Open browser and start server ===
start "" http://localhost:%FLASK_RUN_PORT%/
flask run --host=%FLASK_RUN_HOST% --port=%FLASK_RUN_PORT%
