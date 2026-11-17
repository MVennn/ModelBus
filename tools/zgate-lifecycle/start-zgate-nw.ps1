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
# 探活失败要分清两种情况：进程已经退出（配置被自检拦下、端口被占、缺 dll），
# 还是进程活着但没监听（卡在初始化）。老版本一律记 'up=False (timed out)'，
# 2026-11-17 那天真正的原因（channelPolicy 自检拒绝启动）只写在子进程 stderr 里，
# 而 stderr 继承自隐藏父进程，等于丢进了 NUL —— 排查时日志只剩三条 WARN。
$alive = $false
try { $alive = -not $p.HasExited } catch { $alive = $false }
if ($alive) {
    LogLine ('up=False (alive but not listening) pid={0}' -f $p.Id)
    exit 1
}
$code = $null
try { $code = $p.ExitCode } catch { }
LogLine ('up=False (process exited) code={0}' -f $code)

# 启动即退出：重跑一次并抓 stderr。只在这条失败路径上 redirect —— 给活着的网关
# 挂管道有副作用（脚本退出后管道断，进程再写 stdout 会 EPIPE）。
$errFile = Join-Path $here 'zgate-launch.err.log'
$outFile = Join-Path $here 'zgate-launch.out.log'
Remove-Item $errFile, $outFile -ErrorAction SilentlyContinue
try {
    $psi2 = New-Object System.Diagnostics.ProcessStartInfo
    $psi2.FileName = $exe
    $psi2.Arguments = 'serve'
    $psi2.WorkingDirectory = $ZgateHome
    $psi2.UseShellExecute = $false
    $psi2.CreateNoWindow = $true
    $psi2.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    $psi2.RedirectStandardError = $true
    $psi2.RedirectStandardOutput = $true
    # zgate 是 Go 程序，stderr 一律 UTF-8；不指定编码时 PS 5.1 会按控制台代码页
    # 解码，中文报错会变成一堆问号（2026-11-17 harness 实测）。
    $psi2.StandardErrorEncoding = [System.Text.Encoding]::UTF8
    $psi2.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $p2 = [System.Diagnostics.Process]::Start($psi2)
    $deadline = (Get-Date).AddSeconds(6)
    while (-not $p2.HasExited -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 200 }
    if (-not $p2.HasExited) { try { $p2.Kill() } catch { } }
    $errText = $p2.StandardError.ReadToEnd()
    $outText = $p2.StandardOutput.ReadToEnd()
    if ($errText) {
        Set-Content -Path $errFile -Value $errText -Encoding UTF8
        foreach ($ln in ($errText -split "`r?`n" | Where-Object { $_.Trim() } | Select-Object -First 8)) {
            LogLine ('stderr: ' + $ln.Trim())
        }
    }
    if ($outText) { Set-Content -Path $outFile -Value $outText -Encoding UTF8 }
} catch {
    LogLine ('stderr probe failed: ' + $_.Exception.Message)
}
exit 1
