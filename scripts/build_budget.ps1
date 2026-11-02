# build_budget.ps1 - Parse BDR (tab1) and BDDS (tab2) into budget_data.js
# Zagorodny klub Utrau | OOO Best Glamp
# Run: powershell -ExecutionPolicy Bypass -File .\scripts\build_budget.ps1
# NOTE: keep this file pure ASCII (PowerShell 5.1 reads BOM-less files in the ANSI codepage).
#
# 2026-11-02: real CSV parser (a note with a line break inside a cell no longer splits a row and
# drops its numbers), month columns are detected from the header row (inserted columns no longer
# shift months silently), output is valid JSON + status block for check_health.py.

Add-Type -AssemblyName Microsoft.VisualBasic

$DATA_DIR = Join-Path $PSScriptRoot "..\data"
$RAW_DIR  = Join-Path $DATA_DIR "budget_raw"
$OUT_FILE = Join-Path $DATA_DIR "budget_data.js"

# Fallback month start columns (verified 2026-11-02). Normally detected from the header row.
$MONTHS_BDR  = @(7,11,18,25,29,33,37,41,45,49,53,57)   # tab1 (has cumulative "2/3 months" cols)
$MONTHS_BDDS = @(7,11,15,19,23,27,31,35,39,43,47,51)   # tab2 (no cumulative cols)
$YEAR_COL = 3   # f25 at col3, p26 col4, f26 col5
$warnings = New-Object System.Collections.ArrayList

function Read-CsvRows([string]$path) {
    $p = New-Object Microsoft.VisualBasic.FileIO.TextFieldParser($path, [System.Text.Encoding]::UTF8)
    $p.TextFieldType = [Microsoft.VisualBasic.FileIO.FieldType]::Delimited
    $p.SetDelimiters(",")
    $p.HasFieldsEnclosedInQuotes = $true
    $p.TrimWhiteSpace = $false
    $rows = New-Object System.Collections.ArrayList
    while (-not $p.EndOfData) {
        try { [void]$rows.Add($p.ReadFields()) }
        catch [Microsoft.VisualBasic.FileIO.MalformedLineException] {
            [void]$warnings.Add(("{0}: malformed CSV line {1}" -f (Split-Path $path -Leaf), $p.ErrorLineNumber))
        }
    }
    $p.Close()
    return ,$rows
}

function Cell([object]$cols, [int]$i) {
    if ($i -lt $cols.Count) { return ([string]$cols[$i]).Trim() }
    return ""
}

# Month start columns from the header row: each month block starts with "FAKT <prev year>",
# followed by "PLAN <year>" and "FAKT <year>". Cumulative blocks ("2 months") have no prev year.
function Detect-MonthCols($rows, [int[]]$fallback, [string]$tab) {
    for ($i = 0; $i -lt [Math]::Min(15, $rows.Count); $i++) {
        $r = $rows[$i]
        $years = @()
        foreach ($c in $r) { foreach ($m in [regex]::Matches([string]$c, '20\d\d')) { $years += [int]$m.Value } }
        if ($years.Count -lt 24) { continue }
        $prev = ($years | Measure-Object -Minimum).Minimum
        $cur  = $prev + 1
        $starts = @()
        for ($j = 0; $j -lt $r.Count; $j++) {
            $t = [string]$r[$j]
            if ($t -match "$prev" -and $t -notmatch "$cur" -and $j -ne $YEAR_COL) { $starts += $j }
        }
        $ok = ($starts.Count -eq 12)
        foreach ($s in $starts) {
            if (-not ((Cell $r ($s+1)) -match "$cur" -and (Cell $r ($s+2)) -match "$cur")) { $ok = $false }
        }
        if ($ok) {
            if (($starts -join ',') -ne ($fallback -join ',')) {
                [void]$warnings.Add(("{0}: month columns moved to {1} (were {2}) - read by header" -f $tab, ($starts -join ','), ($fallback -join ',')))
            }
            return @{ cols = $starts; layout = "header"; year = $cur }
        }
        [void]$warnings.Add(("{0}: unexpected month layout in header ({1}) - fallback columns used, CHECK THE SHEET" -f $tab, ($starts -join ',')))
        return @{ cols = $fallback; layout = "fallback"; year = $cur }
    }
    [void]$warnings.Add(("{0}: header row with years not found - fallback columns used, CHECK THE SHEET" -f $tab))
    return @{ cols = $fallback; layout = "fallback" }
}

# Parse a Russian-formatted number. Returns $null if empty/error, else double.
function Parse-Num([string]$s) {
    if ([string]::IsNullOrWhiteSpace($s)) { return $null }
    if ($s -match 'DIV' -or $s -match '#') { return $null }
    # remove spaces (incl non-breaking), ruble sign, percent; comma -> dot
    # .NET \s also matches no-break spaces (U+00A0, U+202F)
    $clean = $s -replace '\s','' -replace [char]0x20BD,'' -replace '%','' -replace '"',''
    $clean = $clean -replace ',','.'
    if ($clean -eq '' -or $clean -eq '-') { return $null }
    $v = 0.0
    if ([double]::TryParse($clean,
            [System.Globalization.NumberStyles]::Any,
            [System.Globalization.CultureInfo]::InvariantCulture, [ref]$v)) {
        return [Math]::Round($v, 2)
    }
    return $null
}

# code level: "1." -> 1, "1.1." -> 2, "2.16.2.1" -> 4 ; non-code -> 0
function Code-Level([string]$code) {
    if ($code -notmatch '^\d') { return 0 }
    $parts = $code.TrimEnd('.').Split('.') | Where-Object { $_ -ne '' }
    return $parts.Count
}

function JsNum($v) { if ($null -eq $v) { return 'null' } else { return ($v.ToString([System.Globalization.CultureInfo]::InvariantCulture)) } }
function JsStr([string]$s) { return '"' + (($s -replace '\\','\\' -replace '"','\"') -replace '[\r\n\t]+',' ') + '"' }

function Parse-Tab([string]$path, [int[]]$fallbackCols, [string]$tab) {
    $csv = Read-CsvRows $path
    $det = Detect-MonthCols $csv $fallbackCols $tab
    $monthCols = $det.cols
    $rows = New-Object System.Collections.ArrayList
    $seenFirstCode = $false
    $lastFact = 0

    foreach ($c in $csv) {
        $code = Cell $c 0
        $name = Cell $c 1

        if ($name -eq "") { continue }

        $rawF25 = Cell $c ($YEAR_COL)
        $rawP26 = Cell $c ($YEAR_COL+1)
        $rawF26 = Cell $c ($YEAR_COL+2)
        $f25 = Parse-Num $rawF25
        $p26 = Parse-Num $rawP26
        $f26 = Parse-Num $rawF26
        # ratio/percent row: any year cell contained '%' (e.g. "dolya v vyruchke", "fudkost")
        $isRatio = ($rawF25 -match '%') -or ($rawP26 -match '%') -or ($rawF26 -match '%')

        # skip rows with no values at all (pure labels/spacers), unless it's a code row
        $hasVal = ($f25 -ne $null) -or ($p26 -ne $null) -or ($f26 -ne $null)
        $isCode = $code -match '^\d'
        if (-not $hasVal -and -not $isCode) { continue }

        if ($isCode) { $seenFirstCode = $true }

        $level = Code-Level $code
        # classify kind
        $kind = 'item'
        if ($isCode) { $kind = 'item' }
        elseif (-not $seenFirstCode) { $kind = 'kpi' }     # rows before first code = KPI block
        else { $kind = 'total' }                            # named rows after codes = totals/notes

        # monthly values
        $mf25 = @(); $mp26 = @(); $mf26 = @()
        $mi = 0
        foreach ($mc in $monthCols) {
            $mi++
            $mf25 += JsNum (Parse-Num (Cell $c $mc))
            $mp26 += JsNum (Parse-Num (Cell $c ($mc+1)))
            $vF26 = Parse-Num (Cell $c ($mc+2))
            $mf26 += JsNum $vF26
            # last month with actual revenue (same rule as lastFactMonth() in budget.html)
            if ($code -eq '1.' -and $null -ne $vF26 -and $vF26 -ne 0) { $lastFact = $mi }
        }

        $obj = "{" +
            '"code":' + (JsStr $code) + "," +
            '"name":' + (JsStr $name) + "," +
            '"level":' + $level + "," +
            '"kind":' + (JsStr $kind) + "," +
            '"isRatio":' + $(if ($isRatio) {'true'} else {'false'}) + "," +
            '"year":{"f25":' + (JsNum $f25) + ',"p26":' + (JsNum $p26) + ',"f26":' + (JsNum $f26) + "}," +
            '"mf25":[' + ($mf25 -join ",") + "]," +
            '"mp26":[' + ($mp26 -join ",") + "]," +
            '"mf26":[' + ($mf26 -join ",") + "]" +
        "}"
        [void]$rows.Add($obj)
    }
    return @{ rows = $rows; lastFact = $lastFact; layout = $det.layout; cols = $monthCols; year = $det.year }
}

Write-Host "Parsing BDR (tab1)..."
$bdr  = Parse-Tab (Join-Path $RAW_DIR "tab1.csv") $MONTHS_BDR "BDR"
Write-Host "  $($bdr.rows.Count) rows | month cols by $($bdr.layout) | last fact month: $($bdr.lastFact)"
Write-Host "Parsing BDDS (tab2)..."
$bdds = Parse-Tab (Join-Path $RAW_DIR "tab2.csv") $MONTHS_BDDS "BDDS"
Write-Host "  $($bdds.rows.Count) rows | month cols by $($bdds.layout) | last fact month: $($bdds.lastFact)"
foreach ($w in $warnings) { Write-Host "WARNING: $w" -ForegroundColor Yellow }

$now = (Get-Date).ToString("yyyy-MM-dd HH:mm")
$warnJs = ($warnings | ForEach-Object { JsStr $_ }) -join ","
$budgetYear = $bdr.year; if (-not $budgetYear) { $budgetYear = 'null' }
$status = '{"year":' + $budgetYear + ',"lastFactMonth":{"bdr":' + $bdr.lastFact + ',"bdds":' + $bdds.lastFact + '},' +
          '"layout":{"bdr":"' + $bdr.layout + '","bdds":"' + $bdds.layout + '"},' +
          '"monthCols":{"bdr":[' + ($bdr.cols -join ",") + '],"bdds":[' + ($bdds.cols -join ",") + ']},' +
          '"warnings":[' + $warnJs + ']}'
$js = "// budget_data.js - auto-generated $now`n// Do not edit manually`n" +
      "window.UTRAU_BUDGET={" + '"generated":' + (JsStr $now) + "," + '"status":' + $status + "," +
      '"bdr":[' + "`n  " + ($bdr.rows -join ",`n  ") + "`n]," +
      '"bdds":[' + "`n  " + ($bdds.rows -join ",`n  ") + "`n]};"

[System.IO.File]::WriteAllText($OUT_FILE, $js, (New-Object System.Text.UTF8Encoding($false)))
Write-Host ""
Write-Host "Generated: $OUT_FILE" -ForegroundColor Cyan
