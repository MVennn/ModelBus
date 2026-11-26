' sync-models.vbs — 无窗口启动模型同步
'
' 计划任务的动作指向本文件（wscript.exe），而不是 powershell.exe：
'   WScript.Shell.Run 的第二个参数 0 = 隐藏窗口，所以整个 PowerShell
'   进程树都不会闪出 cmd / 控制台窗口。
'
' 日志与结果仍写在脚本同仓的 docs\reports\ 下
Option Explicit

Dim shell, ps1, cmd
Set shell = CreateObject("WScript.Shell")

ps1 = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\")) & "sync-models.ps1"
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & ps1 & """"

' 0 = 隐藏, True = 等待（同步跑完才退出，失败能回传非零退出码给计划任务）
' 原为 False：wscript 立即退出，计划任务 1 秒记 0x0，而 ps1 还在后台跑，
' 失败永远反映不到 LastTaskResult，且 IgnoreNew 因实例已结束而失效。
Dim rc
rc = shell.Run(cmd, 0, True)
WScript.Quit rc
