# build_budget.ps1 - Parse BDR (tab1) and BDDS (tab2) into budget_data.js
# Zagorodny klub Utrau | OOO Best Glamp
# Run: powershell -ExecutionPolicy Bypass -File .\scripts\build_budget.ps1

$DATA_DIR = Join-Path $PSScriptRoot "..\data"
$RAW_DIR  = Join-Path $DATA_DIR "budget_raw"
$OUT_FILE = Join-Path $DATA_DIR "budget_data.js"

# Month start columns differ per tab (verified from row 2 headers)
$MONTHS_BDR  = @(7,11,18,25,29,33,37,41,45,49,53,57)   # tab1 (has cumulative cols)
$MONTHS_BDDS = @(7,11,15,19,23,27,31,35,39,43,47,51)   # tab2 (no cumulative cols)
$YEAR_COL = 3   # f25 at col3, p26 col4, f26 col5

function Parse-Line([string]$line) {
    $cols = New-Object System.Collections.ArrayList; $inQ=$false; $cur=""
    foreach ($ch in $line.ToCharArray()) {
        if ($ch -eq '"') { $inQ = -not $inQ }
        elseif ($ch -eq ',' -and -not $inQ) { [void]$cols.Add($cur); $cur="" }
        else { $cur += $ch }
    }
    [void]$cols.Add($cur); return ,$cols
}

function Cell([object]$cols, [int]$i) {
    if ($i -lt $cols.Count) { return ([string]$cols[$i]).Trim() }
    return ""
}

# Parse a Russian-formatted number. Returns $null if empty/error, else double.
function Parse-Num([string]$s) {
    if ([string]::IsNullOrWhiteSpace($s)) { return $null }
    if ($s -match 'DIV' -or $s -match '#') { return $null }
    # remove spaces (incl non-breaking), ruble sign, percent; comma -> dot
    $clean = $s -replace '[\s  ]','' -replace [char]0x20BD,'' -replace '%','' -replace '"',''
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
function JsStr([string]$s) { return '"' + ($s -replace '\\','\\' -replace '"','\"') + '"' }

function Parse-Tab([string]$path, [int[]]$monthCols) {
    $lines = [System.IO.File]::ReadAllLines($path, [System.Text.Encoding]::UTF8)
    $rows = New-Object System.Collections.ArrayList
    $seenFirstCode = $false

    for ($i = 0; $i -lt $lines.Count; $i++) {
        $c = Parse-Line $lines[$i]
        $code = Cell $c 0
        $name = Cell $c 1

        if ($name -eq "") { continue }

        $rawF25 = Cell $c ($YEAR_COL)
        $rawP26 = Cell $c ($YEAR_COL+1)
        $rawF26 = Cell $c ($YEAR_COL+2)
        $f25 = Parse-Num $rawF25
        $p26 = Parse-Num $rawP26
        $f26 = Parse-Num $rawF26
        # ratio/percent row: any year cell contained '%' (e.g. "доля в выручке", "фудкост")
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
        foreach ($mc in $monthCols) {
            $mf25 += JsNum (Parse-Num (Cell $c $mc))
            $mp26 += JsNum (Parse-Num (Cell $c ($mc+1)))
            $mf26 += JsNum (Parse-Num (Cell $c ($mc+2)))
        }

        $obj = "{" +
            "code:" + (JsStr $code) + "," +
            "name:" + (JsStr $name) + "," +
            "level:" + $level + "," +
            "kind:" + (JsStr $kind) + "," +
            "isRatio:" + $(if ($isRatio) {'true'} else {'false'}) + "," +
            "year:{f25:" + (JsNum $f25) + ",p26:" + (JsNum $p26) + ",f26:" + (JsNum $f26) + "}," +
            "mf25:[" + ($mf25 -join ",") + "]," +
            "mp26:[" + ($mp26 -join ",") + "]," +
            "mf26:[" + ($mf26 -join ",") + "]" +
        "}"
        [void]$rows.Add($obj)
    }
    return ,$rows
}

Write-Host "Parsing BDR (tab1)..."
$bdr  = Parse-Tab (Join-Path $RAW_DIR "tab1.csv") $MONTHS_BDR
Write-Host "  $($bdr.Count) rows"
Write-Host "Parsing BDDS (tab2)..."
$bdds = Parse-Tab (Join-Path $RAW_DIR "tab2.csv") $MONTHS_BDDS
Write-Host "  $($bdds.Count) rows"

$now = (Get-Date).ToString("yyyy-MM-dd HH:mm")
$js = "// budget_data.js - auto-generated $now`n// Do not edit manually`n" +
      "window.UTRAU_BUDGET={generated:" + (JsStr $now) + "," +
      "bdr:[`n  " + ($bdr -join ",`n  ") + "`n]," +
      "bdds:[`n  " + ($bdds -join ",`n  ") + "`n]};"

[System.IO.File]::WriteAllText($OUT_FILE, $js, [System.Text.Encoding]::UTF8)
Write-Host ""
Write-Host "Generated: $OUT_FILE" -ForegroundColor Cyan
