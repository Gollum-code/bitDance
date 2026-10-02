param(
    [int]$Port = 8000
)

# Change to script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $scriptDir

Write-Host "[start-dev] project dir: $scriptDir"

# Try to find and kill existing uvicorn/python processes for this app
Write-Host "[start-dev] Searching for existing uvicorn processes (matching 'uvicorn' or listening on port $Port)"
$pids = @()
# Prefer filtering by process command line to avoid killing unrelated python processes
try {
    $uvicornProcs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'uvicorn') }
    if ($uvicornProcs) { $pids += $uvicornProcs | Select-Object -ExpandProperty ProcessId }
} catch {
    # ignore
}

# Also include processes that are listening on the port (fallback)
try {
    $listeners = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess
    if ($listeners) { $pids += $listeners }
} catch {
    $lines = netstat -ano | findstr ":$Port"
    foreach ($l in $lines) {
        $cols = $l -split '\s+'
        $p = $cols[-1]
        if ($p -match '^\d+$') { $pids += [int]$p }
    }
}

$pids = $pids | Sort-Object -Unique
if ($pids -and $pids.Count -gt 0) {
    foreach ($pid in $pids) {
        try {
            Stop-Process -Id $pid -Force -ErrorAction Stop
            Write-Host "[start-dev] Killed process $pid"
        } catch {
            Write-Warning ("[start-dev] Failed to kill process {0}: {1}" -f $pid, $_)
        }
    }
} else {
    Write-Host "[start-dev] No matching uvicorn/python processes found on port $Port"
}

# Activate virtual environment (best-effort)
$activate = Join-Path $scriptDir ".\.venv\Scripts\Activate.ps1"
if (Test-Path $activate) {
    Write-Host "[start-dev] Activating virtualenv..."
    & $activate
} else {
    Write-Warning "[start-dev] Activation script not found at $activate. Continuing without activation."
}

# Ensure python path
$python = Join-Path $scriptDir ".\.venv\Scripts\python.exe"
if (-Not (Test-Path $python)) {
    Write-Warning "[start-dev] Python not found at $python. Please activate venv or adjust path."
}

# Start uvicorn in a detached process so the script returns immediately
Write-Host "[start-dev] Starting uvicorn on 0.0.0.0:$Port ..."
Start-Process -NoNewWindow -FilePath $python -ArgumentList "-m uvicorn main:app --host 0.0.0.0 --port $Port --reload" -WorkingDirectory $scriptDir

Write-Host "[start-dev] uvicorn started. Use 'netstat -ano | findstr $Port' or 'tasklist /FI \"PID eq (Get-NetTCPConnection -LocalPort $Port).OwningProcess\"' to inspect."
