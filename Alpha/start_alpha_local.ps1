# start_alpha_local.ps1 - Project Alpha Sovereign Desktop Launcher (PowerShell)
# Runs Project Alpha 100% locally with zero cloud dependencies or costs.

$Host.UI.RawUI.WindowTitle = "Project Alpha - Sovereign Local AI Executive Operating System"
Write-Host ""
Write-Host "===================================================================" -ForegroundColor Cyan
Write-Host "                     PROJECT ALPHA                                 " -ForegroundColor Cyan -NoNewline
Write-Host ""
Write-Host "       Autonomous Sovereign AI Executive Operating System          " -ForegroundColor White
Write-Host "               [100% Free Local Desktop Mode]                      " -ForegroundColor Green
Write-Host "===================================================================" -ForegroundColor Cyan
Write-Host ""

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# 1. Locate Python
$PythonCmd = "$ScriptDir\..\test_venv\Scripts\python.exe"
if (-not (Test-Path $PythonCmd)) {
    $PythonCmd = "$ScriptDir\venv\Scripts\python.exe"
}
if (-not (Test-Path $PythonCmd)) {
    $PythonCmd = "python"
}

Write-Host "[*] Using Python: $PythonCmd" -ForegroundColor Gray

# 2. Check / Start Ollama
Write-Host "[*] Checking Ollama local service..." -ForegroundColor Gray
$ollamaRunning = $false
try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:11434/" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
    if ($resp.StatusCode -eq 200) { $ollamaRunning = $true }
} catch {}

if (-not $ollamaRunning) {
    Write-Host "[!] Ollama not responding. Starting Ollama daemon in background..." -ForegroundColor Yellow
    $ollamaBin = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
    if (-not (Test-Path $ollamaBin)) {
        $ollamaBin = "C:\Program Files\Ollama\ollama.exe"
    }
    if (Test-Path $ollamaBin) {
        Start-Process -FilePath $ollamaBin -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 3
        Write-Host "[OK] Ollama daemon initiated." -ForegroundColor Green
    } else {
        Write-Host "[WARN] Ollama executable not found. Ensure Ollama is installed from https://ollama.com" -ForegroundColor Yellow
    }
} else {
    Write-Host "[OK] Ollama daemon is active and responsive." -ForegroundColor Green
}

# 3. Set Offline Environment Variables
$env:ALPHA_OFFLINE = "1"
$env:ALPHA_PROVIDER = "ollama"
$env:DEFAULT_MODEL = "llama3.2:1b"
$env:OLLAMA_HOST = "http://127.0.0.1:11434"
$env:ALPHA_EMBEDDINGS = "mock"
$env:ALPHA_PORT = "8765"

# 4. Verify Vault Setup
$vaultDb = "$ScriptDir\Alpha-Vault\sqlite\vault.db"
$rootDb = "$ScriptDir\Alpha-Vault\vault.db"
if ((-not (Test-Path $vaultDb)) -and (-not (Test-Path $rootDb))) {
    Write-Host "[*] Running first-time self-sustaining setup..." -ForegroundColor Cyan
    & $PythonCmd "$ScriptDir\scripts\setup_self_sustaining.py"
}

# 5. Launch Backend
Write-Host ""
Write-Host "===================================================================" -ForegroundColor Cyan
Write-Host "[STARTING] Project Alpha Desktop Backend & FastMCP Server..." -ForegroundColor Yellow
Write-Host "  - Local REST API:    http://127.0.0.1:8765" -ForegroundColor Green
Write-Host "  - WebSocket Stream:  ws://127.0.0.1:8765/ws/events" -ForegroundColor Green
Write-Host "  - FastMCP Server:    http://127.0.0.1:8766 (SSE)" -ForegroundColor Green
Write-Host "  - Executive Engine:  Local Ollama (llama3.2:1b)" -ForegroundColor Cyan
Write-Host "  - Cloud Cost:        `$0.00 / Zero Quota Usage" -ForegroundColor Green
Write-Host "===================================================================" -ForegroundColor Cyan
Write-Host ""

& $PythonCmd "$ScriptDir\alpha.py" start --host 127.0.0.1 --port 8765 --mcp
