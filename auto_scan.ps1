# ─────────────────────────────────────────────────────────────────
#  Stash – Auto-Scan Script
#  Runs: python stash.py scan --tage 1
#  Logs: C:\Users\timba\stash-mvp\scan_log.txt
# ─────────────────────────────────────────────────────────────────

$ProjectDir = "C:\Users\timba\stash-mvp"
$LogFile    = Join-Path $ProjectDir "scan_log.txt"
$Script     = Join-Path $ProjectDir "stash.py"

# Rotate log file when it exceeds 5 MB
if (Test-Path $LogFile) {
    if ((Get-Item $LogFile).Length -gt 5MB) {
        $archive = Join-Path $ProjectDir "scan_log_old.txt"
        Move-Item -Force $LogFile $archive
    }
}

# Timestamp helper
function Write-Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts  $msg" | Out-File -FilePath $LogFile -Append -Encoding UTF8
}

Write-Log "---- scan start ----"

try {
    $result = & python $Script scan --tage 1 2>&1
    foreach ($line in $result) {
        Write-Log $line
    }
    Write-Log "---- scan done ----"
}
catch {
    Write-Log "ERROR: $_"
    Write-Log "---- scan failed ----"
}
