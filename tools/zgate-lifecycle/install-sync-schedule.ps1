#Requires -Version 5.1
<#
.SYNOPSIS
    核对每日模型同步计划任务（只读；不注册、不修改、不删除任何任务）。
.DESCRIPTION
    docs/MODEL-ALIAS.md 4.1 节早期承诺 08:00 / 22:00 与工作日四个峰谷边界各跑一次。
    实测 sync-models.ps1 完整流水线带榜单 --write、探活、--push、漂移二轮写入副作用，
    且 model_alias.py 每次 --apply 刷新 generated_at（同参连跑两次 alias map 逐字节不同），
    多时段重跑不幂等。现行口径：只保留一个每日 12:00 主任务。
    本脚本发现主任务缺失只报警并返回 1，由人工决定如何修复。
#>
[CmdletBinding()]
param([string]$TaskName = "ModelBus 模型同步")
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $task) {
    Write-Warning ("未找到计划任务: " + $TaskName + "；按现行口径不自动注册，请人工核对")
    exit 1
}
$taskInfo = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction SilentlyContinue
Write-Host ("任务: " + $task.TaskName + "  State=" + $task.State)
foreach ($t in $task.Triggers) { Write-Host ("  触发器: " + $t.CimClass.CimClassName + " " + $t.StartBoundary) }
foreach ($a in $task.Actions) { Write-Host ("  动作: " + $a.Execute + " " + $a.Arguments) }
if ($taskInfo) { Write-Host ("  上次运行: " + $taskInfo.LastRunTime + "  Result=" + $taskInfo.LastTaskResult) }
if ($task.State -ne "Ready" -and $task.State -ne "Running") {
    Write-Warning "任务状态非 Ready/Running，请人工核对（脚本不做修复）"
    exit 1
}
Write-Host "现行口径核对通过：每日 12:00 一次，无额外峰谷时段任务"
exit 0
