#requires -Version 5.1
<#
.SYNOPSIS
  把 tools/zgate-lifecycle/ 的安全正本部署到 %LOCALAPPDATA%\ZCodeGateway，
  校正计划任务动作（现行只有 ModelBus-zgate-watchdog；ModelBus-zgate-hidden 若存在则一并校正），并清除「会话里 Start-Process 拉起」的旧脚本。
.DESCRIPTION
  只改本机启动链路，不动正在运行的网关；换二进制另跑 deploy-zgate.ps1 / restart-zgate.cmd。
  幂等：重复执行只覆盖脚本、仅当任务动作不符时才 Set-ScheduledTask。
#>
[CmdletBinding()]
param(
    [string]$ZgateDir = '',
    [string]$LocalDir = '',
    [string]$HiddenTask = 'ModelBus-zgate-hidden',
    [string]$WatchdogTask = 'ModelBus-zgate-watchdog'
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
if (-not $LocalDir) { $LocalDir = Join-Path (Resolve-LocalAppData) 'ZCodeGateway' }
$src = $PSScriptRoot
if (-not $ZgateDir) {
    if ($env:ZGATE_DIR) { $ZgateDir = $env:ZGATE_DIR }
    else {
        $guess = Join-Path $src '..\..\gateways\zgate'
        if (Test-Path (Join-Path $guess 'zgate.json')) { $ZgateDir = (Resolve-Path $guess).Path }
    }
}
if (-not $ZgateDir) { throw '找不到 zgate 目录，请传 -ZgateDir <绝对路径>' }
$ZgateDir = (Resolve-Path $ZgateDir).Path
if (-not (Test-Path (Join-Path $ZgateDir 'zgate.json'))) { throw ('{0} 下没有 zgate.json' -f $ZgateDir) }

if (-not (Test-Path $LocalDir)) { New-Item -ItemType Directory -Path $LocalDir -Force | Out-Null }
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$bakDir = Join-Path $LocalDir ('autostart-backup-' + $stamp)
New-Item -ItemType Directory -Path $bakDir -Force | Out-Null

$files = @('deploy-zgate.ps1','restart-zgate.cmd','start-zgate-nw.ps1','ensure-zgate.ps1',
           'launch-zgate.vbs','ensure-zgate.vbs','swap-zgate.ps1','start-zgate.bat')
foreach ($f in $files) {
    $s = Join-Path $src $f
    $d = Join-Path $LocalDir $f
    if (-not (Test-Path $s)) { throw ('仓库正本缺失：{0}' -f $s) }
    if (Test-Path $d) { Copy-Item -LiteralPath $d -Destination (Join-Path $bakDir $f) -Force }
    Copy-Item -LiteralPath $s -Destination $d -Force
    Write-Host ('[OK] 部署 {0}' -f $d)
}

# 本机真值：只写在 AppData（不入版本库），仓库正本零绝对路径
$pathsFile = Join-Path $LocalDir 'zgate-paths.ps1'
$nl = [Environment]::NewLine
$content = '# 由 install-lifecycle.ps1 生成：本机真值，不入版本库' + $nl + '$ZgateHome = ' + "'" + $ZgateDir + "'" + $nl
[System.IO.File]::WriteAllText($pathsFile, $content, (New-Object System.Text.UTF8Encoding($true)))
Write-Host ('[OK] 写入 {0}（ZgateDir={1}）' -f $pathsFile, $ZgateDir)

# 校正计划任务动作（不动 Principal / Trigger / Settings）
$wantHiddenArg = '//B //Nologo "' + (Join-Path $LocalDir 'launch-zgate.vbs') + '"'
$wantWatchArg  = '//B //Nologo ' + (Join-Path $LocalDir 'ensure-zgate.vbs')
function Fix-Task([string]$name, [string]$arg, [string]$kind) {
    $t = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if (-not $t) {
        $a = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument $arg
        $p = New-ScheduledTaskPrincipal -UserId ('{0}\{1}' -f $env:USERDOMAIN, $env:USERNAME) -LogonType Interactive -RunLevel Limited
        if ($kind -eq 'hidden') {
            $tr = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
            $st = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero)
        } else {
            # 2026-11-11 起单任务双触发器：登录即拉起 + 每分钟兜底
            $tr = @()
            $tr += New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 1)
            $tr += New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
            $st = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew
        }
        try {
            Register-ScheduledTask -TaskName $name -Action $a -Trigger $tr -Principal $p -Settings $st | Out-Null
        } catch {
            Write-Host ('[WARN] 注册 {0} 被系统拒绝（{1}）：需管理员权限，或手动 Register-ScheduledTask -Xml 备份文件' -f $name, $_.Exception.Message)
            return
        }
        Write-Host ('[OK] 注册计划任务 {0}' -f $name)
        return
    }
    $cur = $t.Actions[0].Arguments
    if ($cur -ne $arg) {
        $a = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument $arg
        try {
            Set-ScheduledTask -TaskName $name -Action $a | Out-Null
        } catch {
            Write-Host ('[WARN] 校正 {0} 被系统拒绝（{1}）：改计划任务需管理员权限' -f $name, $_.Exception.Message)
            return
        }
        Write-Host ('[OK] 校正 {0} 动作：{1} -> {2}' -f $name, $cur, $arg)
    } else {
        Write-Host ('[OK] {0} 动作已正确，未改动' -f $name)
    }
}
if (Get-ScheduledTask -TaskName $HiddenTask -ErrorAction SilentlyContinue) {
    Fix-Task $HiddenTask $wantHiddenArg 'hidden'
} else {
    Write-Host ('[SKIP] {0} 不存在：2026-11-11 已合并进 {1}，重建需管理员' -f $HiddenTask, $WatchdogTask)
}
Fix-Task $WatchdogTask $wantWatchArg 'watchdog'
Write-Host ''
Write-Host '完成。启动链路全部走计划任务父链，关 CMD / 退出 DSH 不会带走网关。'
Write-Host '换二进制：跑 restart-zgate.cmd（或 deploy-zgate.ps1），一次完成编译+替换+拉起+健康检查。'
