# Runs the backend test suite inside the backend container.
# Usage: .\scripts\test-backend.ps1 [pytest args...]   e.g. .\scripts\test-backend.ps1 tests/api -x
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    $running = docker compose ps --status running --services 2>$null
    if ($running -notcontains "backend") {
        Write-Host "Starting backend..." -ForegroundColor Yellow
        docker compose up -d backend | Out-Null
        $port = 8000
        $m = Select-String -Path (Join-Path $root ".env") -Pattern '^BACKEND_PORT=(\d+)' -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($m) { $port = [int]$m.Matches[0].Groups[1].Value }
        for ($i = 0; $i -lt 30; $i++) { try { $h = Invoke-RestMethod "http://localhost:$port/health" -TimeoutSec 4; if ($h.checks) { break } } catch {}; Start-Sleep -Seconds 4 }
    }
    # Drop stale connections to the test database (a previous aborted run can leave locks behind)
    $sql = "select pg_terminate_backend(pid) from pg_stat_activity where datname='legalos_test' and pid <> pg_backend_pid();"
    docker compose exec -T db psql -U legalos -d postgres -c $sql 2>&1 | Out-Null
    $pyargs = if ($args.Count -gt 0) { $args } else { @() }
    docker compose exec -T backend timeout 560 python -m pytest -q --no-header -p no:cacheprovider @pyargs
}
finally { Pop-Location }
