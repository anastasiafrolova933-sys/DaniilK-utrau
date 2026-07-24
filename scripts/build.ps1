# build.ps1 - Parse CSV files and generate dashboard_data.js
# Run: powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1

param()

$DATA_DIR = Join-Path $PSScriptRoot "..\data"
$OUT_FILE = Join-Path $DATA_DIR "dashboard_data.js"

function Parse-Num($s) {
    if ([string]::IsNullOrWhiteSpace($s)) { return 0 }
    $clean = ($s.Trim()) -replace '\s','' -replace ',','.' -replace '%','' -replace '"',''
    $v = 0.0
    [void][double]::TryParse($clean,
        [System.Globalization.NumberStyles]::Any,
        [System.Globalization.CultureInfo]::InvariantCulture, [ref]$v)
    return [Math]::Round($v, 2)
}

function Parse-CsvFile($path, $year) {
    $records = @()
    if (-not (Test-Path $path)) { return ,$records }

    $lines = [System.IO.File]::ReadAllLines($path, [System.Text.Encoding]::UTF8)

    foreach ($line in $lines) {
        $line = $line.Trim()
        if ([string]::IsNullOrEmpty($line)) { continue }

        # Skip lines without any DD.MM.YYYY date
        if ($line -notmatch '\d{2}\.\d{2}\.\d{4}') { continue }

        # Parse quoted CSV manually
        $cols = @()
        $inQ = $false; $cur = ""
        foreach ($ch in $line.ToCharArray()) {
            if ($ch -eq '"') { $inQ = !$inQ }
            elseif ($ch -eq ',' -and !$inQ) { $cols += $cur; $cur = "" }
            else { $cur += $ch }
        }
        $cols += $cur

        # Date is normally in column A. If a row is shifted it lands in column B,
        # while the other columns keep their positions (revenue stays at index 2).
        $raw = $cols[0].Trim()
        if ($raw -notmatch '^(\d{2})\.(\d{2})\.(\d{4})$') {
            if ($cols.Count -gt 1 -and $cols[1].Trim() -match '^(\d{2})\.(\d{2})\.(\d{4})$') {
                $raw = $cols[1].Trim()
            } else { continue }
        }
        [void]($raw -match '^(\d{2})\.(\d{2})\.(\d{4})$')
        $iso = "$($Matches[3])-$($Matches[2])-$($Matches[1])"

        # Skip empty placeholder rows (future dates with no revenue yet)
        if ($cols.Count -le 2 -or [string]::IsNullOrWhiteSpace($cols[2])) { continue }

        function G($i) { if ($cols.Count -gt $i) { return $cols[$i] } else { return "" } }

        $records += [PSCustomObject]@{
            date          = $iso
            year          = [int]$year
            revenue       = Parse-Num (G 2)
            roomNights    = Parse-Num (G 3)
            guestArrivals = Parse-Num (G 5)
            roomArrivals  = Parse-Num (G 6)
            adr           = Parse-Num (G 7)
            revpar        = Parse-Num (G 8)
            als           = Parse-Num (G 9)
            totalRooms    = Parse-Num (G 10)
            underRepair   = Parse-Num (G 11)
            availRooms    = Parse-Num (G 12)
            occupancy     = Parse-Num (G 13)
        }
    }

    Write-Host "[$year] $($records.Count) days parsed" -ForegroundColor Green
    return ,$records
}

# ── Main ────────────────────────────────────────────────────

$all = @()
foreach ($y in @("2024","2025","2026")) {
    $r = Parse-CsvFile (Join-Path $DATA_DIR "raw_$y.csv") $y
    if ($r.Count -gt 0) { $all += $r }
}

if ($all.Count -eq 0) { Write-Host "No data found" -ForegroundColor Red; exit 1 }

$all = $all | Sort-Object date

$now  = (Get-Date).ToString("yyyy-MM-dd HH:mm")
$rows = ($all | ForEach-Object {
    $r = $_
    "{`"date`":`"$($r.date)`",`"year`":$($r.year),`"revenue`":$($r.revenue),`"roomNights`":$($r.roomNights),`"guestArrivals`":$($r.guestArrivals),`"roomArrivals`":$($r.roomArrivals),`"adr`":$($r.adr),`"revpar`":$($r.revpar),`"als`":$($r.als),`"totalRooms`":$($r.totalRooms),`"underRepair`":$($r.underRepair),`"availRooms`":$($r.availRooms),`"occupancy`":$($r.occupancy)}"
}) -join ",`n  "

$js = "// Auto-generated $now - do not edit`nwindow.UTRAU_DATA={generated:`"$now`",daily:[`n  $rows`n]};"
[System.IO.File]::WriteAllText($OUT_FILE, $js, [System.Text.Encoding]::UTF8)

Write-Host "dashboard_data.js -> $($all.Count) records | $OUT_FILE" -ForegroundColor Cyan
