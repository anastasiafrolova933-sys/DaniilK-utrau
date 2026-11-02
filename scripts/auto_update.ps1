# auto_update.ps1 - Full daily pipeline: download -> build -> health check -> push to GitHub Pages
# Zagorodny klub Utrau | OOO Best Glamp
# Triggered by Windows Task Scheduler (task UtrauDashboardUpdate, see docs/README.md)
# Test run without git/notifications:  powershell -ExecutionPolicy Bypass -File .\scripts\auto_update.ps1 -NoPush
# NOTE: keep this file pure ASCII (PowerShell 5.1 reads BOM-less files in the ANSI codepage).
#
# 2026-11-02: output of every step goes to data/update.log (was discarded with Out-Null, so
# "no access to file" / "empty tab" never surfaced), check_health.py writes data/health.json
# (data freshness for the portal + summary text for push / future Telegram bot).

param([switch]$NoPush)

$ErrorActionPreference = 'Continue'
$repo = Split-Path $PSScriptRoot -Parent
$log  = Join-Path $repo "data\update.log"
$PYTHON = 'C:\Users\CloudUser\AppData\Local\Programs\Python\Python312\python.exe'

# python prints UTF-8; make PowerShell decode it as UTF-8 too (otherwise Cyrillic in the log breaks)
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$env:PYTHONIOENCODING = 'utf-8'

function Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $msg"
    Write-Host $line
    Add-Content -Path $log -Value $line -Encoding UTF8
}

# run a step, copy all its output (incl. Write-Host and python stderr) into the log
function Run-Step($title, [scriptblock]$block) {
    Log "--- $title"
    $code = 0
    try {
        & $block *>&1 | ForEach-Object {
            $t = "$_".TrimEnd()
            if ($t) { Log "    $t" }
        }
        $code = $LASTEXITCODE
    } catch {
        Log "    EXCEPTION: $_"
        $code = 1
    }
    if ($null -eq $code) { $code = 0 }
    return $code
}

Log "=== Auto-update start ==="

# 1. Download + build all four reports (download.ps1 runs every builder)
$dl = Run-Step "download + build (finance, budget, F&B, SPA)" { & (Join-Path $PSScriptRoot "download.ps1") }
if ($dl -ne 0) { Log "Download/build finished WITH ERRORS (exit $dl) - see lines above" } else { Log "Download/build OK" }

# 2. Health check: how fresh is each report, what is broken -> data/health.json
$hc = Run-Step "health check" { & $PYTHON (Join-Path $PSScriptRoot "check_health.py") }
$healthFile = Join-Path $repo "data\health.json"
$overall = "unknown"; $tag = ""
if (Test-Path $healthFile) {
    try {
        $h = [System.IO.File]::ReadAllText($healthFile, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
        $overall = $h.overall
        $parts = @()
        foreach ($k in @('finance', 'budget', 'fnb', 'spa')) {
            $r = $h.reports.$k
            if ($r -and $r.state -ne 'ok') { $parts += ("{0} {1}" -f $k, $r.dataTo) }
        }
        if ($parts.Count -gt 0) { $tag = " (stale: " + ($parts -join ", ") + ")" }
    } catch { Log "health.json unreadable: $_" }
}
Log ("Health: " + $overall + $tag)

if ($NoPush) {
    Log "-NoPush: git and notifications skipped"
    Log "=== Auto-update done ==="
    exit 0
}

# 3. Commit & push if data changed
Push-Location $repo
try {
    git add data/ 2>&1 | Out-Null
    $status = (git status --porcelain -- data/ 2>&1) -join ''
    if (-not $status) {
        Log "No changes - skip git push"
    } else {
        $date = Get-Date -Format 'dd.MM.yyyy HH:mm'
        git commit -m "Data update $date | health: $overall$tag" 2>&1 | Out-Null
        # --autostash: uncommitted edits elsewhere in the repo must not block the data push
        git pull --rebase --autostash origin master 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { git rebase --abort 2>&1 | Out-Null }
        git push origin HEAD:master 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Log "Pushed to GitHub Pages"
        } else {
            Log "Push FAILED (exit $LASTEXITCODE)"
        }
    }
} finally {
    Pop-Location
}

# 4. Notifications: daily digest + stale-data alert (push needs local chat server on :8768)
$notify = Join-Path $repo "backend\notify_push.py"
if (Test-Path $notify) {
    $np = Run-Step "notify_push" { & $PYTHON $notify }
}

Log "=== Auto-update done ==="
