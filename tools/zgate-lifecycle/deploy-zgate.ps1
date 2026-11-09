#requires -Version 5.1
<#
.SYNOPSIS
  编译候选 zgate.exe → 停旧实例 → 备份/原子替换 → 计划任务拉起 → 健康检查 → 失败回滚。
.DESCRIPTION
  换 Go 代码必须换二进制：/admin/reload 只热加载 zgate.json 的策略/空闲/窗口
  （supervisor.go:473：New children need a restart，可执行与端口布局是启动期固定的）。
  拉起一律走 schtasks /run /tn ModelBus-zgate-hidden：父链在 Task Scheduler 服务下，
  不落进 CMD / DSH 会话的 Job Object，关 CMD、退出 DSH 都不会带走网关。
  脚本跑完即退，不留常驻 powershell。
  用法：
    powershell -NoProfile -ExecutionPolicy Bypass -File deploy-zgate.ps1
    powershell -NoProfile -ExecutionPolicy Bypass -File deploy-zgate.ps1 -SkipBuild
#>
[CmdletBinding()]
param(
    [string]$ZgateDir = '',
    [string]$HiddenTask = 'ModelBus-zgate-hidden',
    [string]$WatchdogTask = 'ModelBus-zgate-watchdog',
    [string]$HealthUrl = 'http://127.0.0.1:7871/health',
    [switch]$SkipBuild,
    [int]$HealthRetries = 40
)
$ErrorActionPreference = 'Stop'
function Resolve-LocalAppData {
    # 三层回退：显式环境变量 -> .NET SpecialFolder -> USERPROFILE 推导。
    # 从 DSH / 计划任务的精简环境里调用时 $env:LOCALAPPDATA 可能为空，
    # 直接 Join-Path $null 会抛 ParameterArgumentValidationErrorNullNotAllowed。
    if ($env:LOCALAPPDATA) { return $env:LOCALAPPDATA }
    $d = [Environment]::GetFolderPath('LocalApplicationData')
    if ($d) { return $d }
    if ($env:USERPROFILE) { return (Join-Path $env:USERPROFILE 'AppData\Local') }
    throw '找不到 LocalAppData：请设置 LOCALAPPDATA / USERPROFILE，或传 -LocalDir'
}
function Resolve-Python {
    # 精简环境（DSH run_code / 计划任务）里 PATH 可能不含 Python，
    # 直接 & python 会抛 CommandNotFoundException；此处按优先级解析绝对路径。
    if ($env:ZGATE_PYTHON) { return $env:ZGATE_PYTHON }
    $c = Get-Command python -ErrorAction SilentlyContinue
    if ($c) {
        if ($c.Path) { return $c.Path }
        if ($c.Source) { return $c.Source }
        if ($c.Definition) { return $c.Definition }
    }
    $c = Get-Command py -ErrorAction SilentlyContinue
    if ($c -and $c.Path) { return $c.Path }
    $guess = Join-Path (Resolve-LocalAppData) 'Programs\Python\Python312\python.exe'
    if (Test-Path $guess) { return $guess }
    throw '找不到 Python：设置 ZGATE_PYTHON，或把 python.exe 放进 PATH'
}
$localDir = Join-Path (Resolve-LocalAppData) 'ZCodeGateway'
if (-not (Test-Path $localDir)) { New-Item -ItemType Directory -Path $localDir -Force | Out-Null }
$logFile = Join-Path $localDir 'deploy-zgate.log'

function Write-Log([string]$msg) {
    $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    Write-Host $line
    Add-Content -Path $logFile -Value $line -Encoding UTF8
}
function Resolve-ZgateDir([string]$given) {
    if ($given) { return (Resolve-Path $given).Path }
    if ($env:ZGATE_DIR) { return (Resolve-Path $env:ZGATE_DIR).Path }
    $pathsFile = Join-Path $PSScriptRoot 'zgate-paths.ps1'
    if (Test-Path $pathsFile) {
        . $pathsFile
        if ($ZgateHome) { return (Resolve-Path $ZgateHome).Path }
    }
    $inRepo = Join-Path $PSScriptRoot '..\..\gateways\zgate'
    if (Test-Path (Join-Path $inRepo 'zgate.json')) { return (Resolve-Path $inRepo).Path }
    throw '找不到 zgate 目录：传 -ZgateDir、设 ZGATE_DIR，或先跑 install-lifecycle.ps1'
}
function Test-Health([string]$url) {
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3
        return ($r.StatusCode -eq 200)
    } catch { return $false }
}
function Invoke-ScheduledStart([string]$task) {
    $o = & schtasks.exe /run /tn $task 2>&1
    $code = $LASTEXITCODE
    Write-Log ('schtasks /run /tn {0} -> exit={1} {2}' -f $task, $code, ($o -join ' '))
    if ($code -ne 0) { throw ('schtasks /run failed (exit={0}): {1}' -f $code, ($o -join ' ')) }
}

$dir = Resolve-ZgateDir $ZgateDir
$exe = Join-Path $dir 'zgate.exe'
$candidate = Join-Path $dir 'zgate.candidate.exe'
$buildPy = Join-Path $dir 'build.py'
$cfg = Join-Path $dir 'zgate.json'
foreach ($f in @($buildPy, $cfg)) {
    if (-not (Test-Path $f)) { throw ('缺少 {0}' -f $f) }
}
Write-Log ('ZgateDir = {0}' -f $dir)
if (-not (Get-ScheduledTask -TaskName $HiddenTask -ErrorAction SilentlyContinue)) {
    throw ('计划任务 {0} 不存在，先跑 install-lifecycle.ps1' -f $HiddenTask)
}

$watchdogExisted = [bool](Get-ScheduledTask -TaskName $WatchdogTask -ErrorAction SilentlyContinue)
$backup = ''
$replaced = $false
$watchdogPaused = $false
$rc = 0

try {
    # 1) 编译候选：绝不原地覆盖正在运行的 zgate.exe（Windows 会锁文件）
    if (-not $SkipBuild) {
        Write-Log '编译候选产物（build.py --candidate）...'
        # 钉死子进程输出编码：build.py 的中文 print 经管道被 PS5.1 按 ANSI 解码会变乱码。
        $env:PYTHONIOENCODING = 'utf-8'
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
        $pythonExe = Resolve-Python
        & $pythonExe $buildPy --candidate
        if ($LASTEXITCODE -ne 0) { throw ('build.py --candidate 退出码 {0}' -f $LASTEXITCODE) }
    }
    if (-not (Test-Path $candidate)) { throw ('候选产物未生成：{0}' -f $candidate) }
    Write-Log ('候选就绪：{0}' -f $candidate)

    # 2) 暂停看门狗，避免它抢在替换窗口用旧脚本拉起
    if ($watchdogExisted) {
        Disable-ScheduledTask -TaskName $WatchdogTask -ErrorAction Stop | Out-Null
        $watchdogPaused = $true
        Write-Log ('已暂停 {0}' -f $WatchdogTask)
    }

    # 3) 停旧实例（winproc 的 Job Object 会一并回收它监管的 children）
    $old = Get-Process -Name zgate -ErrorAction SilentlyContinue
    if ($old) {
        Write-Log ('停旧实例 pid={0}' -f (($old | Select-Object -ExpandProperty Id) -join ','))
        $old | Stop-Process -Force -ErrorAction SilentlyContinue
    } else {
        Write-Log '旧实例未在运行，直接换版'
    }
    for ($i = 0; $i -lt 20; $i++) {
        if (-not (Get-Process -Name zgate -ErrorAction SilentlyContinue)) { break }
        Start-Sleep -Milliseconds 250
    }
    if (Get-Process -Name zgate -ErrorAction SilentlyContinue) { throw '旧实例未能停止，放弃换版' }

    # 4) 备份 + 原子替换
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $backup = $exe + '.bak-deploy-' + $stamp
    if (Test-Path $exe) { Copy-Item -LiteralPath $exe -Destination $backup -Force }
    Move-Item -LiteralPath $candidate -Destination $exe -Force
    $replaced = $true
    Write-Log ('已替换 {0}（备份：{1}）' -f $exe, $backup)

    # 5) 计划任务拉起：父链落在 Task Scheduler，脱离 CMD/DSH 会话树
    Invoke-ScheduledStart $HiddenTask

    # 6) 健康检查
    $ok = $false
    for ($i = 0; $i -lt $HealthRetries; $i++) {
        if (Test-Health $HealthUrl) { $ok = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $ok) { throw ('健康检查 {0} 次未通过：{1}' -f $HealthRetries, $HealthUrl) }
    $proc = Get-Process -Name zgate -ErrorAction SilentlyContinue | Select-Object -First 1
    $parentInfo = ''
    if ($proc) {
        $ci = Get-CimInstance Win32_Process -Filter ('ProcessId={0}' -f $proc.Id) -ErrorAction SilentlyContinue
        if ($ci) { $parentInfo = 'ppid=' + $ci.ParentProcessId }
    }
    Write-Log ('换版完成：/health 200，zgate pid={0} {1}' -f $proc.Id, $parentInfo)
    Write-Log '父链在 Task Scheduler 下；关闭本 CMD / 退出 DSH 均不影响该实例。'
}
catch {
    $rc = 1
    Write-Log ('失败：{0}' -f $_.Exception.Message)
    Write-Log ('堆栈：{0}' -f $_.ScriptStackTrace)
    if ($replaced -and $backup -and (Test-Path $backup)) {
        Copy-Item -LiteralPath $backup -Destination $exe -Force -ErrorAction SilentlyContinue
        Write-Log ('已用备份恢复 {0}' -f $exe)
    }
    # 无论是否换版，网关都必须以某个可用二进制重新起来
    try {
        if (-not (Test-Health $HealthUrl)) {
            Invoke-ScheduledStart $HiddenTask
            for ($i = 0; $i -lt 15; $i++) {
                if (Test-Health $HealthUrl) { break }
                Start-Sleep -Seconds 1
            }
        }
        Write-Log ('回滚后 health = {0}' -f (Test-Health $HealthUrl))
    } catch {
        Write-Log ('回滚拉起失败：{0}' -f $_.Exception.Message)
    }
}
finally {
    if ($watchdogPaused) {
        try {
            Enable-ScheduledTask -TaskName $WatchdogTask -ErrorAction Stop | Out-Null
            Write-Log ('已恢复 {0}' -f $WatchdogTask)
        } catch {
            Write-Log ('恢复看门狗失败：{0}' -f $_.Exception.Message)
        }
    }
}
exit $rc
