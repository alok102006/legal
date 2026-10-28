# Backs up LegalOS data: Postgres (pg_dump, custom format) + Qdrant (one snapshot per collection) + optional uploads.
# Usage:  .\scripts\backup.ps1 [-OutDir D:\backups] [-KeepDays 14] [-IncludeUploads] [-QdrantPort 6335]
# Each run writes a time-stamped folder:  <OutDir>\<yyyyMMdd-HHmmss>\{legalos.dump, qdrant\*.snapshot, uploads.zip}
# Restore steps are in README.md ("Backups"). Needs Docker running (the stack from docker-compose.yml).
param(
    [string]$OutDir = (Join-Path (Split-Path -Parent $PSScriptRoot) "backups"),
    [int]$KeepDays = 14,
    [switch]$IncludeUploads,
    [int]$QdrantPort = 6335
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dest = Join-Path $OutDir $stamp
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Push-Location $root
$failed = $false
try {
    # ---- Postgres: dump inside the container (binary-safe), verify it is readable, copy it out
    Write-Host "Postgres: dumping..." -ForegroundColor Cyan
    docker compose exec -T db sh -c "pg_dump -U legalos -d legalos -Fc -f /tmp/legalos.dump && pg_restore -l /tmp/legalos.dump > /dev/null"
    if ($LASTEXITCODE -ne 0) { throw "pg_dump failed (is the db container running?)" }
    docker compose cp db:/tmp/legalos.dump (Join-Path $dest "legalos.dump")
    if ($LASTEXITCODE -ne 0) { throw "could not copy the dump out of the container" }
    docker compose exec -T db rm -f /tmp/legalos.dump | Out-Null
    $size = [math]::Round((Get-Item (Join-Path $dest "legalos.dump")).Length / 1MB, 2)
    Write-Host "  legalos.dump  $size MB" -ForegroundColor Green

    # ---- Qdrant: snapshot every collection through its REST API, download it, delete the server-side copy
    Write-Host "Qdrant: snapshotting..." -ForegroundColor Cyan
    $base = "http://localhost:$QdrantPort"
    $headers = @{}
    if ($env:QDRANT_API_KEY) { $headers["api-key"] = $env:QDRANT_API_KEY }
    $qdir = Join-Path $dest "qdrant"
    New-Item -ItemType Directory -Force -Path $qdir | Out-Null
    $collections = (Invoke-RestMethod -Uri "$base/collections" -Headers $headers -TimeoutSec 30).result.collections
    foreach ($c in $collections) {
        $name = $c.name
        $snap = (Invoke-RestMethod -Method Post -Uri "$base/collections/$name/snapshots" -Headers $headers -TimeoutSec 600).result.name
        $file = Join-Path $qdir "$name.snapshot"
        Invoke-WebRequest -Uri "$base/collections/$name/snapshots/$snap" -Headers $headers -OutFile $file -TimeoutSec 600
        Invoke-RestMethod -Method Delete -Uri "$base/collections/$name/snapshots/$snap" -Headers $headers -TimeoutSec 60 | Out-Null
        $mb = [math]::Round((Get-Item $file).Length / 1MB, 2)
        Write-Host "  $name.snapshot  $mb MB" -ForegroundColor Green
    }

    # ---- Uploaded files (optional: they can be large)
    if ($IncludeUploads) {
        $uploads = Join-Path $root "backend\uploads"
        if (Test-Path $uploads) {
            Write-Host "Uploads: compressing..." -ForegroundColor Cyan
            Compress-Archive -Path (Join-Path $uploads "*") -DestinationPath (Join-Path $dest "uploads.zip") -Force
        }
    }

    # ---- Retention: remove backup folders older than KeepDays
    Get-ChildItem -Path $OutDir -Directory | Where-Object { $_.Name -match '^\d{8}-\d{6}$' -and $_.LastWriteTime -lt (Get-Date).AddDays(-$KeepDays) } |
        ForEach-Object { Write-Host "Removing old backup $($_.Name)" -ForegroundColor DarkGray; Remove-Item -Recurse -Force $_.FullName }

    Write-Host "Backup finished: $dest" -ForegroundColor Green
}
catch {
    $failed = $true
    Write-Host "BACKUP FAILED: $($_.Exception.Message)" -ForegroundColor Red
}
finally { Pop-Location }
if ($failed) { exit 1 }
