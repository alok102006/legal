# Loads the demo story data (Ramesh Kulkarni's textile business) into the DEMO organisation using the real AI.
# Usage (PowerShell, from the legalos folder):  .\scripts\load-demo.ps1 [-Port 8010]
param([int]$Port = 0)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if ($Port -eq 0) {
    $Port = 8000
    $envFile = Join-Path $root ".env"
    if (Test-Path $envFile) {
        $m = Select-String -Path $envFile -Pattern '^BACKEND_PORT=(\d+)' | Select-Object -First 1
        if ($m) { $Port = [int]$m.Matches[0].Groups[1].Value }
    }
}
$base = "http://localhost:$Port/api/v1"
$hdr = @{ "X-User-Role" = "owner" }
$demo = Join-Path $root "docs\demo"

$health = Invoke-RestMethod "http://localhost:$Port/health"
if (-not $health.checks.llm.ok) { throw "The AI service is not working: $($health.checks.llm.message). Fix the Gemini key first." }
Write-Host "Backend OK on port $Port. Loading demo data..." -ForegroundColor Cyan

function Wait-Until([scriptblock]$Check, [string]$What, [int]$Seconds = 150) {
    $t0 = Get-Date
    while (((Get-Date) - $t0).TotalSeconds -lt $Seconds) {
        $r = & $Check
        if ($r) { return $r }
        Start-Sleep -Seconds 3
    }
    throw "Timed out waiting for $What"
}

# 1. Contract
$c = curl.exe -s -F "file=@$demo\01_yarn_supply_agreement.txt" -F "client_party=Kulkarni Textiles Private Limited" -H "X-User-Role: owner" "$base/contracts/upload" | ConvertFrom-Json
$null = Wait-Until { $d = Invoke-RestMethod -Headers $hdr "$base/contracts/$($c.id)"; if ($d.status -in "analyzed", "failed") { $d } } "contract analysis"
Write-Host "  contract done"

# 2. Supplier (sample registry record for Patel Yarn Traders)
$samples = Invoke-RestMethod -Headers $hdr "$base/vendors/samples"
$patel = $samples | Where-Object { $_.name -eq "Patel Yarn Traders" } | Select-Object -First 1
if ($patel) {
    try { $null = Invoke-RestMethod -Method Post -Headers $hdr -ContentType "application/json" -Uri "$base/vendors" -Body (@{ name = $patel.name; gstin = $patel.gstin } | ConvertTo-Json); Write-Host "  supplier checked" }
    catch { Write-Host "  supplier already exists" }
}

# 3. Notice (received today so the deadline is fresh)
$text = [string](Get-Content "$demo\02_cheque_bounce_notice.txt" -Raw)   # plain string, or ConvertTo-Json would nest an object
$n = Invoke-RestMethod -Method Post -Headers $hdr -ContentType "application/json" -Uri "$base/notices/text" -Body (@{ text = $text; received_date = (Get-Date).ToString("yyyy-MM-dd") } | ConvertTo-Json)
$null = Wait-Until { $d = Invoke-RestMethod -Headers $hdr "$base/notices/$($n.id)"; if ($d.status -in "analyzed", "failed") { $d } } "notice analysis"
Write-Host "  notice done"

# 4. Documents
foreach ($f in @(@("03_employee_handbook.txt", "HR"), @("04_fire_safety_certificate.txt", "Licence or certificate"))) {
    $d = curl.exe -s -F "file=@$demo\$($f[0])" -F "category=$($f[1])" -H "X-User-Role: owner" "$base/knowledge/documents/upload" | ConvertFrom-Json
    $null = Wait-Until { $x = Invoke-RestMethod -Headers $hdr "$base/knowledge/documents/$($d.id)"; if ($x.status -eq "failed" -or ($x.status -eq "ready" -and $x.review_state -ne "pending")) { $x } } "document review"
    Write-Host "  document $($f[0]) done"
}
# 5. Filing history: a new account has none, so past deadlines look "overdue". Mark them as already filed,
#    except the latest GSTR-3B, which stays overdue to show what a missed GST deadline looks like.
$null = Invoke-RestMethod -Method Post -Headers $hdr -ContentType "application/json" -Uri "$base/compliance/sync" -Body "{}"   # make sure the calendar exists first
$tasks = Invoke-RestMethod -Headers $hdr "$base/compliance/tasks"
if ($tasks -isnot [array] -and $tasks.items) { $tasks = $tasks.items }
$overdue = @($tasks | Where-Object { $_.state -eq "overdue" })
$keep = $overdue | Where-Object { $_.rule_id -eq "gst-gstr3b-monthly" } | Sort-Object due_date | Select-Object -Last 1
$ids = @($overdue | Where-Object { -not $keep -or $_.id -ne $keep.id } | ForEach-Object { $_.id })
if ($ids.Count -gt 0) {
    $null = Invoke-RestMethod -Method Post -Headers $hdr -ContentType "application/json" -Uri "$base/compliance/tasks/bulk-complete" -Body (@{ ids = $ids; note = "Filed before joining LegalOS" } | ConvertTo-Json)
    Write-Host "  marked $($ids.Count) earlier filings as already filed"
}
Write-Host "Demo data loaded. Open http://localhost:5173 and click 'Try the demo'." -ForegroundColor Green
