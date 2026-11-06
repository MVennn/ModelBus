#Requires -Version 5.1
<#
.SYNOPSIS
    ModelBus 每日模型同步（Windows 计划任务入口）

.DESCRIPTION
    迁移自 DeepSeekRuntime 的定时任务（原 schedule-4467b892-8205-44ec-8e03-fd0f018c1ab4）。
    移到这里的原因：DSH 的 cron 只在 DSH 运行时才触发，关着就跳过；
                而且有待命定时任务时，DSH 每次退出都要弹确认框。

    五段流水线：
      一、Go 套餐
      二、WorkBuddy2API（倍率上限 0.30）
      三、Qoder（含入口健康检查与直连回退）
      四、统一命名与分组
      五、同步报告与推送

.PARAMETER NoPush
    只写报告，不做 git push。

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File sync-models.ps1
    powershell -NoProfile -ExecutionPolicy Bypass -File sync-models.ps1 -NoPush
#>
[CmdletBinding()]
param(
    [switch]$NoPush
)

$ErrorActionPreference = "Continue"

# ---- 环境 ----------------------------------------------------------------
$ROOT       = "F:\Project\ModelBus"
$GIT_DIR    = "C:\Program Files\Git\cmd"
$REPORT_DIR = Join-Path $ROOT "docs\reports"

# 运行日志不能落在仓库里：日志会回显 provider_config.json 等本机绝对路径，
# 一旦被 sync_report.py 的 `git add docs/reports` 带进提交，
# CI 的 tools/check-secrets.py（[本机用户目录] 规则）就会失败。
# 放到 LOCALAPPDATA 下，仓库里只留 MODEL-SYNC-*.md 这类不含路径的报告。
$STATE_DIR = Join-Path $env:LOCALAPPDATA "ModelBus"
$LOG_DIR   = Join-Path $STATE_DIR "logs"
$STAMP     = Get-Date -Format "yyyyMMdd-HHmmss"
$LOG       = Join-Path $LOG_DIR "sync-$STAMP.log"
$SUMMARY   = Join-Path $STATE_DIR "_last-sync.txt"

# Python 位置不能写死成 C:\Users\<用户名>\...，那同样会触发敏感信息扫描。
# 优先用 LOCALAPPDATA（环境变量展开，源码里看不到用户名），再退回 PATH。
function Resolve-Python {
    foreach ($v in @("Python313", "Python312", "Python311", "Python310")) {
        $c = Join-Path $env:LOCALAPPDATA "Programs\Python\$v\python.exe"
        if (Test-Path $c) { return $c }
    }
    foreach ($n in @("python", "python3", "py")) {
        $cmd = Get-Command $n -ErrorAction SilentlyContinue
        if ($cmd -and $cmd.Source) { return $cmd.Source }
    }
    return ""
}
$PY = Resolve-Python

# 计划任务的 PATH 很干净，git / python 都得自己补
if (Test-Path $GIT_DIR) { $env:PATH = "$GIT_DIR;" + $env:PATH }
# Python 输出中文到管道时，默认 GBK 会炸，强制 UTF-8
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8       = "1"

# ★ 关键：PowerShell 默认按控制台代码页（GBK/936）解码子进程的 stdout，
#   而 Python 输出的是 UTF-8 字节 → 解成乱码字符 → 再以 UTF-8 写入日志，
#   结果就是双重编码。只有把 OutputEncoding 设成 UTF-8，读到的才是正确字符串。
#   之前日志里的「ģ��ͬ����ʼ」就是这么来的。
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding           = $utf8NoBom
try { chcp 65001 | Out-Null } catch { }

if (-not $PY -or -not (Test-Path $PY)) {
    Write-Error "找不到 Python：LOCALAPPDATA\Programs\Python 与 PATH 都没命中"
    exit 2
}
if (-not (Test-Path $ROOT)) {
    Write-Error "找不到仓库: $ROOT"
    exit 2
}

New-Item -ItemType Directory -Path $REPORT_DIR -Force | Out-Null
New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null
Set-Location $ROOT

$script:Fail       = 0
$script:LastCode   = 0
$script:LastOutput = @()
$script:MainN      = -1
$script:FreeN      = -1
$script:SaveN      = -1

# ---- 辅助函数 ------------------------------------------------------------
function Say {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $Message
    Write-Host $line
    Add-Content -LiteralPath $LOG -Value $line -Encoding UTF8
}

function Invoke-Py {
    param([string]$Label, [string[]]$Argv, [switch]$Soft)
    Say ">>> $Label"
    $script:LastOutput = @()
    & $PY @Argv 2>&1 | ForEach-Object {
        $script:LastOutput += [string]$_
        Write-Host $_
        Add-Content -LiteralPath $LOG -Value $_ -Encoding UTF8
    }
    $script:LastCode = $LASTEXITCODE
    Say "<<< $Label  exit=$($script:LastCode)"
    # -Soft：非 0 退出属于预期分支（例如漂移检查探测到漂移），不计入失败段数
    if ($script:LastCode -ne 0 -and -not $Soft) { $script:Fail++ }
}

function Show-SyncToast {
    param(
        [int]$Main = -1,
        [int]$Free = -1,
        [int]$Saving = -1,
        [string]$ReportPath = "",
        [string]$LogPath = ""
    )
    $ok = ($script:Fail -eq 0)
    if ($ok) {
        $title = "模型同步完成"
    } else {
        $title = "模型同步有 $($script:Fail) 段失败"
    }

    $parts = @()
    if ($Main -ge 0)   { $parts += "主力 $Main" }
    if ($Free -ge 0)   { $parts += "免费 $Free" }
    if ($Saving -ge 0) { $parts += "省钱 $Saving" }
    $body = if ($parts.Count -gt 0) { $parts -join " / " } else { "见日志" }

    $detail = if ($ReportPath) { Split-Path $ReportPath -Leaf } else { Split-Path $LogPath -Leaf }

    # 结构化摘要落盘，方便事后查
    $summaryFile = $SUMMARY
    @(
        "时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
        "结果: $(if ($ok) { '成功' } else { "失败 $($script:Fail) 段" })",
        "分组: $body",
        "报告: $ReportPath",
        "日志: $LogPath"
    ) | Set-Content -LiteralPath $summaryFile -Encoding UTF8

    $safe = { param($s) [System.Security.SecurityElement]::Escape([string]$s) }
    $xml = @"
<toast>
  <visual>
    <binding template="ToastGeneric">
      <text>$(& $safe $title)</text>
      <text>$(& $safe $body)</text>
      <text>$(& $safe $detail)</text>
    </binding>
  </visual>
</toast>
"@
    try {
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
        $doc = New-Object Windows.Data.Xml.Dom.XmlDocument
        # LoadXml 只接受 UTF-8 字符串；PowerShell 的字符串本身是 UTF-16，需先转字节再回填
        $doc.LoadXml($xml)
        $toast = [Windows.UI.Notifications.ToastNotification]::new($doc)
        $aumid = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
        $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($aumid)
        $notifier.Show($toast)
        Say "已弹出通知"
    } catch {
        Say ("通知失败（不影响同步）: " + $_.Exception.Message)
    }
}

function Test-Port {
    param([string]$TargetHost = "127.0.0.1", [int]$Port, [int]$TimeoutMs = 1500)
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $task = $client.ConnectAsync($TargetHost, $Port)
        if ($task.Wait($TimeoutMs)) { $client.Close(); return $true }
        $client.Close()
        return $false
    } catch {
        return $false
    }
}

function Wait-Port {
    param([string]$TargetHost = "127.0.0.1", [int]$Port, [int]$Seconds = 60)
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Port $TargetHost $Port) { return $true }
        Start-Sleep -Seconds 2
    }
    return (Test-Port $TargetHost $Port)
}

# ---- 开场 ----------------------------------------------------------------
Say "===== 模型同步开始 ====="
Say "仓库: $ROOT"
Say "日志: $LOG"

# ---- 一、Go 套餐 ---------------------------------------------------------
Say "----- 一、Go 套餐 -----"
Invoke-Py "Go 套餐同步" @("providers\opencode-go\ops\go_model_sync.py", "--apply")

# ---- 二、WorkBuddy2API ---------------------------------------------------
Say "----- 二、WorkBuddy2API -----"
$keyCode = @'
import json, pathlib
print(json.loads(pathlib.Path("gateways/upstream/workbuddy/config.json").read_text(encoding="utf-8")).get("api_key", ""))
'@
$env:WB_GATEWAY_KEY = ($keyCode | & $PY -).Trim()
if ([string]::IsNullOrEmpty($env:WB_GATEWAY_KEY)) {
    Say "警告：WorkBuddy api_key 为空，拉清单与写配置大概率会失败"
} else {
    Say ("WB_GATEWAY_KEY 已载入（" + $env:WB_GATEWAY_KEY.Length + " 字符）")
}

Invoke-Py "WorkBuddy 价格表"   @("providers\workbuddy\workbuddy_fetch_pricing.py")
Invoke-Py "WorkBuddy 写配置"   @("providers\workbuddy\workbuddy_zcode_sync.py", "--max-rate", "0.3", "--apply")

# ---- 三、Qoder -----------------------------------------------------------
Say "----- 三、Qoder -----"

# Qoder 的模型清单从 hub 的 live catalog 拉，需要 8790 的 qoder 代理先起来。
# 代理是 detached 启动的，调用后立即返回，用端口轮询等它起来。
if (-not (Test-Port "127.0.0.1" 8790)) {
    Say "8790 未监听，启动 qoder 代理"
    $bat = Join-Path $ROOT "gateways\upstream\qoder\start-qoder-proxy.bat"
    if (Test-Path $bat) {
        Start-Process -FilePath $bat -WorkingDirectory (Split-Path $bat) -WindowStyle Hidden
        if (Wait-Port "127.0.0.1" 8790 90) {
            Say "8790 已就绪"
        } else {
            Say "8790 启动超时，Qoder 段大概率会失败"
        }
    } else {
        Say "找不到 start-qoder-proxy.bat"
    }
} else {
    Say "8790 已在监听"
}

# 清单从 hub 的 live catalog 拉，不再逐个模型发探测请求。
Invoke-Py "Qoder 写配置" @("providers\qoder\qoder_zcode_sync.py", "--apply")

# ---- 四、统一命名与分组 ---------------------------------------------------
Say "----- 四、统一命名与分组 -----"
Invoke-Py "统一命名写入" @("tools\model_alias.py", "--slot", "auto", "--apply")
$applyCode = $script:LastCode

# --check 在「有漂移」时返回 1，这是本脚本要处理的正常分支，不算失败
Invoke-Py "漂移检查" @("tools\model_alias.py", "--check") -Soft
if ($script:LastCode -ne 0) {
    Say "检测到漂移，收缩名单要两轮才收敛，再写一次"
    Invoke-Py "统一命名二轮" @("tools\model_alias.py", "--slot", "auto", "--apply")
    Invoke-Py "漂移复查" @("tools\model_alias.py", "--check")
    if ($script:LastCode -ne 0) {
        Say "复查仍有漂移，需要人工看"
    } else {
        Say "复查无漂移"
    }
} else {
    Say "无漂移"
}

# 三组数量必须在这里取：LastOutput 每调用一次 Invoke-Py 就被重置，
# 放到报告段之后再解析，拿到的会是 sync_report 的输出（没有 "## 主力 (N)"）。
foreach ($line in $script:LastOutput) {
    if ($line -match "##\s*主力\s*\((\d+)\)") { $script:MainN = [int]$Matches[1] }
    if ($line -match "##\s*免费\s*\((\d+)\)") { $script:FreeN = [int]$Matches[1] }
    if ($line -match "##\s*省钱\s*\((\d+)\)") { $script:SaveN = [int]$Matches[1] }
}
Say "分组计数: 主力 $($script:MainN) / 免费 $($script:FreeN) / 省钱 $($script:SaveN)"

Say "----- DeepSeekHarness 投影 -----"
Invoke-Py "DSH 投影检查" @("tools\dsh_sync.py", "--check")
if ($script:LastCode -ne 0) {
    Say "DSH patch 与仓库不一致，重新投影"
    Invoke-Py "DSH 投影写入" @("tools\dsh_sync.py", "--apply")
} else {
    Say "DSH patch 已是最新"
}

# ---- 五、同步报告 --------------------------------------------------------
Say "----- 五、同步报告 -----"
if ($NoPush) {
    Invoke-Py "写报告" @("tools\sync_report.py", "--write")
} else {
    Invoke-Py "写报告并推送" @("tools\sync_report.py", "--write", "--push")
}

# 从报告输出里取实际落盘路径
$reportPath = ""
foreach ($line in $script:LastOutput) {
    if ($line -match "已写入\s+(.+\.md)\s*$") { $reportPath = $Matches[1].Trim() }
}
if (-not $reportPath) {
    $latest = Get-ChildItem $REPORT_DIR -Filter "MODEL-SYNC-*.md" -ErrorAction SilentlyContinue |
              Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($latest) { $reportPath = $latest.FullName }
}

# 分组数量已在「四、统一命名与分组」段解析进 $script:MainN / FreeN / SaveN
$mainN = $script:MainN; $freeN = $script:FreeN; $saveN = $script:SaveN

# ---- 收尾 ----------------------------------------------------------------
Say "===== 模型同步结束 ====="
Say "失败段数: $($script:Fail)"
Say "本次日志: $LOG"
Say "同步报告: $reportPath"

# 弹通知告诉用户结果（无 cmd 窗口时这是唯一的可见反馈）
Show-SyncToast -Main $mainN -Free $freeN -Saving $saveN -ReportPath $reportPath -LogPath $LOG

if ($script:Fail -gt 0) { exit 1 } else { exit 0 }
