#requires -Version 5.1
# 由 \ModelBus-zgate-watchdog 经 ensure-zgate.vbs 调用（2026-11-11 起 hidden 任务已合并删除）。
# 起的是普通 serve（不带 -tray）：不设 ZGATE_PARENT_PID，superviseLauncher 直接返回，
# 因此拉起脚本跑完退出后网关不会被自己停掉；父链在 Task Scheduler 而非 CMD/DSH 会话树。
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$pathsFile = Join-Path $here 'zgate-paths.ps1'
if (Test-Path $pathsFile) { . $pathsFile }
if (-not $ZgateHome) {
    $guess = Join-Path $here '..\..\gateways\zgate'
    if (Test-Path (Join-Path $guess 'zgate.json')) { $ZgateHome = (Resolve-Path $guess).Path }
}
if (-not $ZgateHome) { throw '未找到 ZgateHome：先跑 install-lifecycle.ps1 生成 zgate-paths.ps1' }
$exe = Join-Path $ZgateHome 'zgate.exe'
$log = Join-Path $here 'zgate-launch.log'
$port = 7871
function LogLine([string]$m) {
    $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m
    Add-Content -Path $log -Value $line -Encoding UTF8
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
if (-not (Test-Path $exe)) { LogLine ('missing exe: {0}' -f $exe); exit 1 }
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $exe
$psi.Arguments = 'serve'
$psi.WorkingDirectory = $ZgateHome
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
try {
    $p = [System.Diagnostics.Process]::Start($psi)
    LogLine ('started pid={0}' -f $p.Id)
} catch {
    LogLine ('start failed: {0}' -f $_.Exception.Message)
    exit 1
}
for ($i = 0; $i -lt 24; $i++) {
    if (Test-Up) { LogLine 'up=True'; exit 0 }
    Start-Sleep -Milliseconds 500
}
LogLine 'up=False (timed out)'
exit 1
