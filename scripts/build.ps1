# build.ps1 - Finance dashboard (Dokhodnost i zagruzka): Google Sheets -> data/dashboard_data.js
# Run: powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1 [-Offline]
#
# Since 2026-11-02 the work is done by build_finance.py:
#   - tabs are discovered automatically (a new "2027" tab is picked up without code changes),
#   - columns are mapped by HEADER names, not by position (inserted columns no longer shift data),
#   - a status block (last data date, empty placeholder rows, bad cells) feeds check_health.py.
# This file stays as the entry point used by download.ps1 / auto_update.ps1 / update.bat.

param([switch]$Offline)

$PYTHON = 'C:\Users\CloudUser\AppData\Local\Programs\Python\Python312\python.exe'
$script = Join-Path $PSScriptRoot "build_finance.py"
if ($Offline) { & $PYTHON $script --offline } else { & $PYTHON $script }
exit $LASTEXITCODE
