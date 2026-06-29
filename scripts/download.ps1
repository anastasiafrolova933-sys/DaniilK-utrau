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
