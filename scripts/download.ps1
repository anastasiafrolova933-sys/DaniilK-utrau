# download.ps1 - Download CSV tabs from Google Sheets
# Zagorodny klub Utrau | OOO Best Glamp
# Run: powershell -ExecutionPolicy Bypass -File .\scripts\download.ps1

$SHEET_ID = "1N9YFy76rV3KcZnN5EwSt8Y-Ji0Y7WpHkwkBrgndChuw"

# Tab GIDs - add new years here
$TABS = @{
    "2024" = "1688657215"
    "2025" = "881244924"
    "2026" = "253518640"
}

$DATA_DIR = Join-Path $PSScriptRoot "..\data"
New-Item -ItemType Directory -Force -Path $DATA_DIR | Out-Null

$ok = 0
$fail = 0

foreach ($year in ($TABS.Keys | Sort-Object)) {
    $gid = $TABS[$year]
    if ([string]::IsNullOrEmpty($gid)) {
        Write-Host "[$year] gid not set - skip" -ForegroundColor Yellow
        continue
    }

    $url  = "https://docs.google.com/spreadsheets/d/$SHEET_ID/export?format=csv" + "&gid=$gid"
    $dest = Join-Path $DATA_DIR "raw_$year.csv"

    try {
        Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing -ErrorAction Stop
        $rows = (Get-Content $dest).Count
        Write-Host "[$year] OK ($rows rows)" -ForegroundColor Green
        $ok++
    } catch {
        Write-Host "[$year] ERROR: $_" -ForegroundColor Red
        $fail++
    }
}

Write-Host ""
Write-Host "Downloaded: $ok | Errors: $fail"

if ($fail -eq 0) {
    Write-Host "Running build.ps1..." -ForegroundColor Cyan
    & (Join-Path $PSScriptRoot "build.ps1")
}

# ---- Budget workbook (separate sheet) ----
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
    try {
        Invoke-WebRequest -Uri $url -OutFile (Join-Path $budgetDir "$k.csv") -UseBasicParsing -ErrorAction Stop
        Write-Host "[budget/$k] OK" -ForegroundColor Green
        $bok++
    } catch {
        Write-Host "[budget/$k] ERROR: $_" -ForegroundColor Red
        $bfail++
    }
}
if ($bfail -eq 0 -and $bok -gt 0) {
    Write-Host "Running build_budget.ps1..." -ForegroundColor Cyan
    & (Join-Path $PSScriptRoot "build_budget.ps1")
}

# ---- F&B (Служба питания) — отдельная пара Google-таблиц, парсер на Python ----
$PYTHON = 'C:\Users\CloudUser\AppData\Local\Programs\Python\Python312\python.exe'
$buildFnb = Join-Path $PSScriptRoot "build_fnb.py"
if ((Test-Path $PYTHON) -and (Test-Path $buildFnb)) {
    Write-Host "Running build_fnb.py..." -ForegroundColor Cyan
    & $PYTHON $buildFnb
}

# ---- СПА / Банный комплекс — отдельная Google-таблица (XLSX, все вкладки разом) ----
$buildSpa = Join-Path $PSScriptRoot "build_spa.py"
if ((Test-Path $PYTHON) -and (Test-Path $buildSpa)) {
    Write-Host "Running build_spa.py..." -ForegroundColor Cyan
    & $PYTHON $buildSpa
}
