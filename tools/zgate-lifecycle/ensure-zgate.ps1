#requires -Version 5.1
# \ModelBus-zgate-watchdog 每分钟跑一次：7871 不通才调同目录 start-zgate-nw.ps1。
$ErrorActionPreference = 'Continue'
$here = $PSScriptRoot
function Test-Up {
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $c.Connect('127.0.0.1', 7871)
        $c.Close()
        return $true
    } catch { return $false }
}
if (Test-Up) { exit 0 }
& (Join-Path $here 'start-zgate-nw.ps1')
if ($LASTEXITCODE -ne 0) {
    try { Write-EventLog -LogName Application -Source 'zgate-watchdog' -EventId 1 -EntryType Error -Message 'zgate restart failed' } catch {}
    exit 1
}
exit 0
