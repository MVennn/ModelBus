#requires -Version 5.1
# 本地 OpenCode Zen 免费档代理（Bun）。健康检查 8789，不通则无窗拉起。
# 父链在 Task Scheduler，不随 DSH/CMD 会话退出。
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$bun = Join-Path $env:USERPROFILE '.bun/bin/bun.exe'
$server = Join-Path $here 'zen-relay/server.js'
$relayDir = Join-Path $here 'zen-relay'
$port = 8789
$log = Join-Path $here 'zen-relay-launch.log'
function LogLine([string]$m) {
    Add-Content -Path $log -Value ('{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m) -Encoding UTF8
}
function Test-Up {
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $c.Connect('127.0.0.1', $port)
        $c.Close()
        return $true
    } catch { return $false }
}
if (Test-Up) { LogLine 'port already up, skip'; exit 0 }
if (-not (Test-Path $bun)) { LogLine ('missing bun: ' + $bun); exit 1 }
if (-not (Test-Path $server)) { LogLine ('missing server: ' + $server); exit 1 }
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $bun
$psi.Arguments = '"' + $server + '"'
$psi.WorkingDirectory = $relayDir
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
$psi.EnvironmentVariables['PORT'] = '8789'
$psi.EnvironmentVariables['HOST'] = '127.0.0.1'
try {
    $p = [System.Diagnostics.Process]::Start($psi)
    LogLine ('started pid=' + $p.Id)
} catch {
    LogLine ('start failed: ' + $_.Exception.Message)
    exit 1
}
for ($i = 0; $i -lt 20; $i++) {
    if (Test-Up) { LogLine 'up=True'; exit 0 }
    Start-Sleep -Milliseconds 500
}
LogLine 'up=False (timed out)'
exit 1
