# ============================================================
# bitDance one-click launcher (Windows PowerShell 5.1)
# Starts:
#   1) bitDance_Object backend  (FastAPI, port 8080)
#   2) trader service           (FastAPI + vn.py, port 8000)
#   3) frontend Vite            (port 5173)
# Usage:  powershell -ExecutionPolicy Bypass -File .\start-all.ps1
# ============================================================

$ErrorActionPreference = "Continue"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$BackendDir = Join-Path $RepoRoot "bitDance_Object\backend"
$FrontendDir = Join-Path $RepoRoot "bitDance_Object"
$TraderDir = Join-Path $RepoRoot "trader"
$BackendPy = Join-Path $BackendDir ".venv\Scripts\python.exe"

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  bitDance one-click launcher" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan

# ---------- 0. port conflict check ----------
foreach ($port in 8000, 8080, 5173) {
    $p = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($p) {
        Write-Host ("[!] port {0} in use (PID {1}), skipping that service" -f $port, $p.OwningProcess) -ForegroundColor Yellow
    }
}

# ---------- 1. frontend deps ----------
Write-Host "[1/3] check frontend deps (node_modules) ..." -ForegroundColor Green
if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    Write-Host "      not installed, running npm install ..."
    Push-Location $FrontendDir
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "npm install failed" -ForegroundColor Red
        Pop-Location
        exit 1
    }
    Pop-Location
} else {
    Write-Host "      deps present, skipping."
}

# ---------- 2. backend (8080) ----------
Write-Host "[2/3] starting backend on 8080 ..." -ForegroundColor Green
if (-not (Test-Path $BackendPy)) {
    Write-Host ("[!] missing {0}; run: python -m venv .venv ; pip install -r requirements.txt" -f $BackendPy) -ForegroundColor Red
    exit 1
}
$be = Start-Process -FilePath $BackendPy -ArgumentList "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080" -WorkingDirectory $BackendDir -PassThru -WindowStyle Hidden
Write-Host ("      backend PID: {0}" -f $be.Id)

# ---------- 3. trader (8000) ----------
Write-Host "[3/3] starting trader on 8000 ..." -ForegroundColor Green
$tr = Start-Process -FilePath "python" -ArgumentList "main.py" -WorkingDirectory $TraderDir -PassThru -WindowStyle Hidden
Write-Host ("      trader PID: {0}" -f $tr.Id)

# ---------- 4. frontend (5173) ----------
Write-Host "      starting frontend Vite (5173) ..." -ForegroundColor Green
$fe = Start-Process -FilePath "npm.cmd" -ArgumentList "run", "dev" -WorkingDirectory $FrontendDir -PassThru -WindowStyle Hidden
Write-Host ("      frontend PID: {0}" -f $fe.Id)

# ---------- 5. health check ----------
Write-Host ""
Write-Host "waiting for services ..." -ForegroundColor Cyan
Start-Sleep -Seconds 5

$ok = 0
$beUrl = "http://localhost:8080/api/health"
$trUrl = "http://localhost:8000/"
foreach ($item in @(@{ n = "backend 8080"; u = $beUrl }, @{ n = "trader 8000"; u = $trUrl })) {
    try {
        $r = Invoke-WebRequest -Uri $item.u -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
        Write-Host ("  [OK] {0}  (HTTP {1})" -f $item.n, $r.StatusCode) -ForegroundColor Green
        $ok = $ok + 1
    } catch {
        Write-Host ("  [--] {0} not ready" -f $item.n) -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  frontend: http://localhost:5173" -ForegroundColor White
Write-Host "  backend:  http://localhost:8080/docs" -ForegroundColor White
Write-Host "  trader:   http://localhost:8000" -ForegroundColor White
Write-Host ("  ready: {0}/2" -f $ok) -ForegroundColor Cyan
Write-Host ("  stop all: Stop-Process -Id {0},{1},{2} -Force" -f $be.Id, $tr.Id, $fe.Id) -ForegroundColor Yellow
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""
