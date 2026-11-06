' sync-models.vbs — 无窗口启动模型同步
'
' 计划任务的动作指向本文件（wscript.exe），而不是 powershell.exe：
'   WScript.Shell.Run 的第二个参数 0 = 隐藏窗口，所以整个 PowerShell
'   进程树都不会闪出 cmd / 控制台窗口。
'
' 日志与结果仍写在 F:\Project\ModelBus\docs\reports\
Option Explicit

Dim shell, ps1, cmd
Set shell = CreateObject("WScript.Shell")

ps1 = "F:\Project\ModelBus\sync-models.ps1"
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & ps1 & """"

' 0 = 隐藏, False = 不等待（wscript 立即退出，同步在后台跑完）
shell.Run cmd, 0, False
