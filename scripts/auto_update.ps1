# auto_update.ps1 - Full daily pipeline: download -> build -> push to GitHub Pages
# Zagorodny klub Utrau | OOO Best Glamp
# Triggered by Windows Task Scheduler (see docs/README.md)

$ErrorActionPreference = 'Continue'
$repo = Split-Path $PSScriptRoot -Parent
$log  = Join-Path $repo "data\update.log"

function Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $msg"
    Write-Host $line
    Add-Content -Path $log -Value $line -Encoding UTF8
}

Log "=== Auto-update start ==="

# 1. Download fresh CSV from Google Sheets
try {
    & (Join-Path $PSScriptRoot "download.ps1") | Out-Null
    Log "Download OK"
} catch {
    Log "Download FAILED: $_"
    exit 1
}

# 2. Build dashboard_data.js (download.ps1 already calls build.ps1, but run to be safe)
try {
    & (Join-Path $PSScriptRoot "build.ps1") | Out-Null
    Log "Build OK"
} catch {
    Log "Build FAILED: $_"
    exit 1
}

# 3. Commit & push if data changed
Push-Location $repo
try {
    git add data/ 2>&1 | Out-Null
    $status = (git status --porcelain 2>&1) -join ''
    if (-not $status) {
        Log "No changes - skip push"
        exit 0
    }
    $date = Get-Date -Format 'dd.MM.yyyy HH:mm'
    git commit -m "Data update $date" 2>&1 | Out-Null
    git pull --rebase origin master 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { git rebase --abort 2>&1 | Out-Null }
    git push origin HEAD:master 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Log "Pushed to GitHub Pages"
        Log "  -> https://anastasiafrolova933-sys.github.io/DaniilK-utrau/finance.html"
    } else {
        Log "Push FAILED (exit $LASTEXITCODE)"
    }
} finally {
    Pop-Location
}

Log "=== Auto-update done ==="
