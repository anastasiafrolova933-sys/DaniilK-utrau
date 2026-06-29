# ============================================================
# download.ps1 — Загрузка CSV из Google Sheets
# Загородный клуб «Утрау» | ООО Бест Глэмп
# ============================================================
# Запуск: .\scripts\download.ps1
# Требования: Windows PowerShell 5+, доступ к интернету
# ============================================================

$SHEET_ID = "1N9YFy76rV3KcZnN5EwSt8Y-Ji0Y7WpHkwkBrgndChuw"

# GID вкладок — при добавлении новых листов добавить сюда
$TABS = @{
    "2024" = "1688657215"
    "2025" = "881244924"
    "2026" = "253518640"
}

$DATA_DIR = Join-Path $PSScriptRoot "..\data"
New-Item -ItemType Directory -Force -Path $DATA_DIR | Out-Null

$ok = 0
$fail = 0

foreach ($year in $TABS.Keys | Sort-Object) {
    $gid = $TABS[$year]
    if ([string]::IsNullOrEmpty($gid)) {
        Write-Host "[$year] gid не задан — пропуск" -ForegroundColor Yellow
        continue
    }

    $url  = "https://docs.google.com/spreadsheets/d/$SHEET_ID/export?format=csv&gid=$gid"
    $dest = Join-Path $DATA_DIR "raw_$year.csv"

    try {
        Write-Host "[$year] Скачиваю..." -NoNewline
        Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing -ErrorAction Stop
        $rows = (Get-Content $dest).Count
        Write-Host " OK ($rows строк)" -ForegroundColor Green
        $ok++
    } catch {
        Write-Host " ОШИБКА: $_" -ForegroundColor Red
        $fail++
    }
}

Write-Host ""
Write-Host "Загружено: $ok  |  Ошибок: $fail"
if ($fail -eq 0) {
    Write-Host "Запускаю build.ps1..." -ForegroundColor Cyan
    & (Join-Path $PSScriptRoot "build.ps1")
}
