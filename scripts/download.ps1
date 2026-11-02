# download.ps1 - Download all Google Sheets sources and rebuild every data/*.js
# Zagorodny klub Utrau | OOO Best Glamp
# Run: powershell -ExecutionPolicy Bypass -File .\scripts\download.ps1
# NOTE: keep this file pure ASCII (PowerShell 5.1 reads BOM-less files in the ANSI codepage).

$PYTHON = 'C:\Users\CloudUser\AppData\Local\Programs\Python\Python312\python.exe'
$DATA_DIR = Join-Path $PSScriptRoot "..\data"
New-Item -ItemType Directory -Force -Path $DATA_DIR | Out-Null
$failed = @()

# ---- 1. Finance (Dokhodnost i zagruzka): build_finance.py downloads all tabs itself ----
Write-Host "Running build.ps1 (finance)..." -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "build.ps1")
if ($LASTEXITCODE -ne 0) { $failed += "finance" }

# ---- 2. Budget workbook (separate sheet) ----
$BUDGET_ID = "1q-5vyXwY0zgB1VtzPh8hn2ZmZ3ieuiMp-u15rIwb1Pg"
$BUDGET_TABS = @{
    "tab1" = "1663630612"   # BDR (P&L)
    "tab2" = "1954215925"   # BDDS (cash flow)
}
$budgetDir = Join-Path $DATA_DIR "budget_raw"
New-Item -ItemType Directory -Force -Path $budgetDir | Out-Null
$bok = 0; $bfail = 0
foreach ($k in ($BUDGET_TABS.Keys | Sort-Object)) {
    $gid = $BUDGET_TABS[$k]
    $url = "https://docs.google.com/spreadsheets/d/$BUDGET_ID/export?format=csv" + "&gid=$gid"
    $tmp = Join-Path $budgetDir "$k.csv.tmp"
    try {
        Invoke-WebRequest -Uri $url -OutFile $tmp -UseBasicParsing -ErrorAction Stop
        # an HTML page instead of CSV = no access; keep the previous good copy then
        $head = [System.IO.File]::ReadAllText($tmp).TrimStart()
        if ($head.StartsWith("<")) { throw "got HTML instead of CSV (no access?)" }
        Move-Item -Force $tmp (Join-Path $budgetDir "$k.csv")
        Write-Host "[budget/$k] OK" -ForegroundColor Green
        $bok++
    } catch {
        Write-Host "[budget/$k] ERROR: $_" -ForegroundColor Red
        Remove-Item -Force $tmp -ErrorAction SilentlyContinue
        $bfail++
    }
}
if ($bfail -eq 0 -and $bok -gt 0) {
    Write-Host "Running build_budget.ps1..." -ForegroundColor Cyan
    & (Join-Path $PSScriptRoot "build_budget.ps1")
} else {
    $failed += "budget"
}

# ---- 3. F&B (restaurant KAEF): registry of monthly files, Python parser ----
$buildFnb = Join-Path $PSScriptRoot "build_fnb.py"
if ((Test-Path $PYTHON) -and (Test-Path $buildFnb)) {
    Write-Host "Running build_fnb.py..." -ForegroundColor Cyan
    & $PYTHON $buildFnb
    if ($LASTEXITCODE -ne 0) { $failed += "fnb" }
}

# ---- 4. SPA / bath complex: one workbook, all monthly tabs (XLSX) ----
$buildSpa = Join-Path $PSScriptRoot "build_spa.py"
if ((Test-Path $PYTHON) -and (Test-Path $buildSpa)) {
    Write-Host "Running build_spa.py..." -ForegroundColor Cyan
    & $PYTHON $buildSpa
    if ($LASTEXITCODE -ne 0) { $failed += "spa" }
}

Write-Host ""
if ($failed.Count -gt 0) {
    Write-Host ("FAILED steps: " + ($failed -join ", ")) -ForegroundColor Red
    exit 1
}
Write-Host "All sources processed."
exit 0
