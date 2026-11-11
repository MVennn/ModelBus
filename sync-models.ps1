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
      五、同步报告（默认不 push，显式 -Push 才推）

.PARAMETER Push
    显式要求时才 git add/commit/push；默认只写报告、不推送。
    计划任务（sync-models.vbs）不带此开关，即每天 12:00 只写报告。

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File sync-models.ps1
    powershell -NoProfile -ExecutionPolicy Bypass -File sync-models.ps1 -Push
#>
[CmdletBinding()]
param(
    [switch]$Push
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

# 先刷新 ArenaGalleri 实时榜，再让生成器带 --arena 读候选。
# 2026-11-06 之前这两步都没有：arena-main.json 停在 2026-10-23，
# 文档写「主力 7 个」而实际只有 2 个，整个榜单单机摆设。
# 刷新失败只降级为「不加分」，不阻断同步（-Soft）。
# 必须带 --write：不带时只是 dry run 打印，候选文件永远停在旧日期。
Invoke-Py "竞技榜刷新" @("tools\arena_leaderboard.py", "--refresh", "--force", "--write") -Soft
if ($script:LastCode -ne 0) {
    Say "竞技榜刷新失败，本次沿用旧候选文件"
}

# 竞技榜分数：先让 model_score.py 把 arena-main.json 折算成智力/价格/性价比，
# 再让生成器带 --scores 用它裁掉明显落后的白名单条目（只降不升）。
Invoke-Py "竞技榜分数" @("tools\model_score.py", "--write", "--quiet") -Soft
if ($script:LastCode -ne 0) {
    Say "分数换算失败，本次不带分数选型"
}
$scoresOn = ($script:LastCode -eq 0)
$scoreArgs = @("tools\model_alias.py", "--slot", "auto", "--apply", "--arena")
if ($scoresOn) { $scoreArgs += "--scores" }
Invoke-Py "统一命名写入" $scoreArgs
$applyCode = $script:LastCode

# 探活：把上游已下架或持续不可用的型号从清单里摘掉。
# moonshotai/kimi-k3-free 在 2026-10-27 就 retired 了，却一直占着免费组的位置 ——
# 因为 --probe-file 从来没被传过、探测结果文件根本不存在，剔除逻辑一直是死代码。
# 必须放在第一轮 apply 之后：本轮新补进配置的型号（如 cn:hy4std）此时才有探测记录，
# 否则会被当成 "not probed" 直接跳过。
# --max-tokens 必须给足：默认 32 在 Gemini/Doubao 这类「先思考再出字」的模型上会被
# 思考预算吃光，回 400 "max output tokens were exhausted"，探活把它记成 error，
# 于是「能用的模型」被判死摘掉 —— 2026-11-11 11:02 那次 Gemini-AIS 突然消失就是
# 同一条路径（timeout 且无 ever_ok → 直接摘）。256 是实测能稳定拿到正文的最小值。
Invoke-Py "模型探活" @("tools\model_probe.py", "--timeout", "90", "--sleep", "0.5", "--max-tokens", "256") -Soft
$probeArgs = @()
$probeOut = Join-Path $env:USERPROFILE ".zcode\v2\model_probe.json"
$probeAll = 0
$probeOk = 0
if (Test-Path $probeOut) {
    try {
        $probeJson = Get-Content -Raw -Encoding UTF8 $probeOut | ConvertFrom-Json
        $probeAll = @($probeJson.PSObject.Properties).Count
        $probeOk = @($probeJson.PSObject.Properties | Where-Object { $_.Value.status -eq 'ok' }).Count
    } catch {
        Say "探测结果解析失败：$($_.Exception.Message)"
    }
}
# 过半才算可信：大面积失败更可能是网关或某个渠道整体挂了，这时按探活摘模型
# 会把好型号一起删掉，宁可这一轮不动。
if ($probeAll -gt 0 -and ($probeOk * 2 -ge $probeAll)) {
    $probeArgs = @("--probe-file", $probeOut)
    Say ("探活 $probeOk/$probeAll 可用，本轮按探测结果摘除死型号")
} else {
    Say ("探活 $probeOk/$probeAll 可用，成功率过低，本轮不据此摘模型")
}
$scoreArgs2 = $scoreArgs + $probeArgs

# --check 必须和 --apply 用同一组参数（--arena/--scores/--probe-file）。
# 只用 --check 的话，arena 把 MiMo-2.6-Flash、Space-Bunny 提到主力这件事
# 会被当成漂移，每天都要二轮重写、复查看起来仍「有漂移」，实际是参数不对称。
$checkArgs = @("tools\model_alias.py", "--check", "--arena")
if ($scoresOn) { $checkArgs += "--scores" }
$checkArgs += $probeArgs

# --check 在「有漂移」时返回 1，这是本脚本要处理的正常分支，不算失败
Invoke-Py "漂移检查" $checkArgs -Soft
if ($script:LastCode -ne 0) {
    Say "检测到漂移，收缩名单要两轮才收敛，再写一次"
    Invoke-Py "统一命名二轮" $scoreArgs2
    Invoke-Py "漂移复查" $checkArgs
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

# ---- 流式准入探针（模型进表即自动纳入，无需人工逐个测试） ------------------
# --changed 只测新增 / 档位变更 / 上次非 PASS 待复查；--soft 不阻断流水线。
# 活体探针只在本机每日同步链尾跑，CI / pre-commit 走离线守卫 check-project.py。
Invoke-Py "流式准入探针" @("tools/model_stream_check.py", "--changed", "--soft") -Soft

# ---- 五、同步报告 --------------------------------------------------------
Say "----- 五、同步报告 -----"
if ($Push) {
    Invoke-Py "写报告并推送" @("tools\sync_report.py", "--write", "--push")
} else {
    Invoke-Py "写报告" @("tools\sync_report.py", "--write")
}

# 单一真值视图：报告是生成时刻的快照，current-models.json 才是「当前生效清单」。
# 只读 alias map / zgate.json，不写配置、不探活、不 push、不重启网关。
$currentScript = Join-Path $ROOT "tools\zgate-lifecycle\current-models.ps1"
if (Test-Path $currentScript) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File $currentScript
    if ($LASTEXITCODE -ne 0) { Say "真值视图刷新失败（exit=$LASTEXITCODE）" }
} else {
    Say "真值视图脚本缺失，跳过"
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
