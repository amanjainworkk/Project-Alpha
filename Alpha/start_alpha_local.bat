@echo off
setlocal enabledelayedexpansion

title Project Alpha - Sovereign Local AI Executive Operating System
color 0B

echo ===================================================================
echo                     PROJECT ALPHA
echo       Autonomous Sovereign AI Executive Operating System
echo               [100%% Free Local Desktop Mode]
echo ===================================================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

:: 1. Detect Python Executable
set "PYTHON_CMD="
if exist "%SCRIPT_DIR%..\test_venv\Scripts\python.exe" (
    set "PYTHON_CMD=%SCRIPT_DIR%..\test_venv\Scripts\python.exe"
) else if exist "%SCRIPT_DIR%venv\Scripts\python.exe" (
    set "PYTHON_CMD=%SCRIPT_DIR%venv\Scripts\python.exe"
) else (
    where python >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_CMD=python"
    ) else (
        echo [ERROR] Python not found in virtual environment or PATH!
        echo Please ensure Python 3.10+ is installed.
        pause
        exit /b 1
    )
)

echo [*] Using Python: %PYTHON_CMD%

:: 2. Check Local Ollama Daemon
echo [*] Checking Ollama local service...
curl -s http://127.0.0.1:11434/ >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Ollama is not currently running. Attempting to start in background...
    if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
        start "" /b "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve
    ) else if exist "C:\Program Files\Ollama\ollama.exe" (
        start "" /b "C:\Program Files\Ollama\ollama.exe" serve
    ) else (
        echo [WARN] Ollama executable not found in standard paths.
        echo If Ollama is installed elsewhere, please run 'ollama serve' in another window.
    )
    timeout /t 3 /nobreak >nul
) else (
    echo [OK] Ollama daemon is active and responsive.
)

:: 3. Configure Local Sovereign Environment
set ALPHA_OFFLINE=1
set ALPHA_PROVIDER=ollama
set DEFAULT_MODEL=llama3.2:1b
set OLLAMA_HOST=http://127.0.0.1:11434
set ALPHA_EMBEDDINGS=mock
set ALPHA_PORT=8765

:: 4. Verify / Run Setup if First Time
if not exist "%SCRIPT_DIR%Alpha-Vault\sqlite\vault.db" if not exist "%SCRIPT_DIR%Alpha-Vault\vault.db" (
    echo [*] First time initialization detected. Initializing Alpha's Vault...
    "%PYTHON_CMD%" "%SCRIPT_DIR%scripts\setup_self_sustaining.py"
    if !errorlevel! neq 0 (
        echo [ERROR] Self-sustaining setup encountered an error.
        pause
        exit /b !errorlevel!
    )
)

:: 5. Launch Alpha OS Backend & FastMCP Concurrently
echo.
echo ===================================================================
echo [STARTING] Project Alpha Desktop Backend & FastMCP Server...
echo   - Local REST API:    http://127.0.0.1:8765
echo   - WebSocket Stream:  ws://127.0.0.1:8765/ws/events
echo   - FastMCP Server:    http://127.0.0.1:8766 (SSE)
echo   - Executive Engine:  Local Ollama (llama3.2:1b)
echo   - Cloud Cost:        $0.00 / Zero Quota Usage
echo ===================================================================
echo.

"%PYTHON_CMD%" "%SCRIPT_DIR%alpha.py" start --host 127.0.0.1 --port 8765 --mcp

if %errorlevel% neq 0 (
    echo [ERROR] Alpha backend terminated with code %errorlevel%.
    pause
)
