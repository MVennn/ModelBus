#Requires -Version 5.1
<#
.SYNOPSIS
    生成「当前生效模型清单」单一真值视图（只读）。
.DESCRIPTION
    读 alias map（统一命名空间真值）与 gateways/zgate/zgate.json（上游/子进程真值），
    写出 %LOCALAPPDATA%/ModelBus/current-models.json。
    不写 provider_config.json、不探活、不 push、不重启网关、不打印凭据。
    只读复用 model_probe.json 已采字段生成 billing_suspect / stale_models / slow_models
    三个零请求质量信号；不新增任何模型推理请求。
    每日 12:00 主同步流水线第五段在报告落盘后调用本脚本。
    注意：PS 5.1 的 ConvertFrom-Json 大小写不敏感，legacy 里的裸名与 models 里的统一名
    仅大小写不同会报 DuplicateKeysInJsonString；故统一用 JavaScriptSerializer 解析。
#>
[CmdletBinding()]
param(
    [string]$AliasMap = "",
    [string]$ZgateJson = "",
    [string]$OutFile = "",
    [string]$ProbeJson = ""
)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Web.Extensions

function Resolve-LocalAppData {
    if ($env:LOCALAPPDATA) { return $env:LOCALAPPDATA }
    try {
        $p = [Environment]::GetFolderPath("LocalApplicationData")
        if ($p) { return $p }
    } catch { }
    if ($env:USERPROFILE) { return (Join-Path $env:USERPROFILE "AppData\Local") }
    throw "无法定位 LOCALAPPDATA"
}

function Resolve-RepoRoot {
    $d = $PSScriptRoot
    $d = Split-Path -Parent $d
    $d = Split-Path -Parent $d
    return $d
}

$root = Resolve-RepoRoot
if (-not $AliasMap) {
    if ($env:UNIFIED_MODEL_MAP) { $AliasMap = $env:UNIFIED_MODEL_MAP }
    else { $AliasMap = Join-Path $env:USERPROFILE ".zcode\v2\model-alias-map.json" }
}
if (-not (Test-Path $AliasMap)) { throw "alias map 不存在: $AliasMap" }
if (-not $ZgateJson) { $ZgateJson = Join-Path $root "gateways\zgate\zgate.json" }
if (-not (Test-Path $ZgateJson)) { throw "zgate.json 不存在: $ZgateJson" }

$stateDir = Join-Path (Resolve-LocalAppData) "ModelBus"
if (-not $OutFile) { $OutFile = Join-Path $stateDir "current-models.json" }
if (-not (Test-Path $stateDir)) { New-Item -ItemType Directory -Path $stateDir -Force | Out-Null }

$jss = New-Object System.Web.Script.Serialization.JavaScriptSerializer
$alias = $jss.DeserializeObject((Get-Content -Raw -Encoding UTF8 $AliasMap))
$zgate = $jss.DeserializeObject((Get-Content -Raw -Encoding UTF8 $ZgateJson))

$upObj = $null
if ($zgate.ContainsKey("upstreams")) { $upObj = $zgate["upstreams"] }
if (-not $upObj -and $zgate.ContainsKey("Upstreams")) { $upObj = $zgate["Upstreams"] }
$chObj = $null
if ($zgate.ContainsKey("children")) { $chObj = $zgate["children"] }
if (-not $chObj -and $zgate.ContainsKey("Children")) { $chObj = $zgate["Children"] }
$upstreamNames = @()
$childNames = @()
if ($upObj) { $upstreamNames = @($upObj.Keys | Sort-Object) }
if ($chObj) { $childNames = @($chObj.Keys | Sort-Object) }

$modelsDict = $alias["models"]
$legacyDict = $null
if ($alias.ContainsKey("legacy")) { $legacyDict = $alias["legacy"] }
$legacyKeys = 0
$legacyByCanonical = @{}
if ($legacyDict) {
    $legacyKeys = @($legacyDict.Keys).Count
    foreach ($k in $legacyDict.Keys) {
        $canon = [string]$legacyDict[$k]
        if (-not $legacyByCanonical.ContainsKey($canon)) { $legacyByCanonical[$canon] = @() }
        $legacyByCanonical[$canon] += [string]$k
    }
}

$modelsOut = @()
foreach ($id in ($modelsDict.Keys | Sort-Object)) {
    $t = $modelsDict[$id]
    $chain = @()
    if ($t.ContainsKey("chain") -and $t["chain"]) { $chain = @($t["chain"]) }
    $primary = ""
    if ($chain.Count -gt 0 -and $chain[0].ContainsKey("channel")) { $primary = [string]$chain[0]["channel"] }
    elseif ($t.ContainsKey("channel")) { $primary = [string]$t["channel"] }
    $hops = $chain.Count
    if ($hops -eq 0) { $hops = 1 }
    $la = @()
    if ($legacyByCanonical.ContainsKey([string]$id)) { $la = @($legacyByCanonical[[string]$id]) }
    $modelsOut += [ordered]@{
        id = [string]$id
        group = [string]$t["group"]
        primary_channel = $primary
        chain_hops = $hops
        legacy_alias_count = $la.Count
    }
}

$groupNames = @("主力", "免费", "省钱")
$groupCounts = [ordered]@{}
foreach ($g in $groupNames) {
    $groupCounts[$g] = @($modelsOut | Where-Object { $_["group"] -eq $g }).Count
}
$other = @($modelsOut | Where-Object { $_["group"] -notin $groupNames }).Count
if ($other -gt 0) { $groupCounts["其他（未登记）"] = $other }

# ── 零请求质量信号：只读复用 model_probe.json 已采字段，不发任何推理请求 ──────────
# billing_suspect：免费组 chain 上游（含 channel 前缀变体）反查到 credit>0，
#   或显示名/上游名带 free 且 credit>0 —— 守「标着 free 却在扣积分」的漂移，只告警。
#   历史：cn:hy4-preview-f 曾被判免费却累计扣 6601 积分，现已按 0.29 计费修复。
# stale_models：有 ok_at 且距今 >7 天 且本轮 status != ok；无 ok_at 归 unknown 不硬判。
# slow_models：ms > 10000。
function Get-Field($rec, $name, $default) {
    if ($null -ne $rec -and $rec.ContainsKey($name) -and $null -ne $rec[$name]) { return $rec[$name] }
    return $default
}
function Get-ProbeRecord($dict, $upstream, $channel) {
    if ($null -eq $dict) { return $null }
    $cl = ([string]$channel).ToLowerInvariant()
    $candidates = @([string]$upstream)
    if ($cl) { $candidates += ($cl + ":" + [string]$upstream) }
    foreach ($c in $candidates) {
        if ($dict.ContainsKey($c)) { return $dict[$c] }
    }
    return $null
}
$probePath = ""
if ($ProbeJson) { $probePath = $ProbeJson }
else { $probePath = Join-Path $env:USERPROFILE ".zcode\v2\model_probe.json" }
$probeDict = $null
$probeAsOf = ""
if (Test-Path $probePath) {
    $probeDict = $jss.DeserializeObject((Get-Content -Raw -Encoding UTF8 $probePath))
    foreach ($pv in $probeDict.Values) {
        if ($pv -isnot [System.Collections.IDictionary]) { continue }
        $ca = [string](Get-Field $pv "checked_at" "")
        if ($ca -gt $probeAsOf) { $probeAsOf = $ca }
    }
}
$billingSuspect = @()
$seenSuspect = @{}
foreach ($id in ($modelsDict.Keys | Sort-Object)) {
    $tt = $modelsDict[$id]
    if ([string]$tt["group"] -ne "免费") { continue }
    $fchain = @()
    if ($tt.ContainsKey("chain") -and $tt["chain"]) { $fchain = @($tt["chain"]) }
    foreach ($h in $fchain) {
        $up = [string]$h["upstream"]
        $chn = [string]$h["channel"]
        $rec = Get-ProbeRecord $probeDict $up $chn
        if ($null -eq $rec) { continue }
        $cr = Get-Field $rec "credit" $null
        if ($cr -is [System.ValueType] -and (([double]$cr) -gt 0)) {
            $key = [string]$id + "|" + $up
            if (-not $seenSuspect.ContainsKey($key)) {
                $seenSuspect[$key] = $true
                $billingSuspect += [ordered]@{
                    id          = [string]$id
                    upstream    = $up
                    display     = [string](Get-Field $rec "display" "")
                    credit      = [double]$cr
                    resp_model  = [string](Get-Field $rec "resp_model" "")
                    quota_model = [string](Get-Field $rec "quota_model" "")
                    reason      = "免费组上游回包 credit>0：标签与实际扣费不一致"
                }
            }
        }
    }
}
if ($probeDict) {
    foreach ($pk in ($probeDict.Keys | Sort-Object)) {
        $pv = $probeDict[$pk]
        if ($pv -isnot [System.Collections.IDictionary]) { continue }
        $disp = [string](Get-Field $pv "display" "")
        $freeLabel = ($disp -match "(?i)free|免费") -or ([string]$pk -match "(?i)free")
        if (-not $freeLabel) { continue }
        $cr = Get-Field $pv "credit" $null
        if ($cr -is [System.ValueType] -and (([double]$cr) -gt 0)) {
            $key2 = [string]$pk
            if (-not $seenSuspect.ContainsKey($key2)) {
                $seenSuspect[$key2] = $true
                $billingSuspect += [ordered]@{
                    id          = $key2
                    upstream    = $key2
                    display     = $disp
                    credit      = [double]$cr
                    resp_model  = [string](Get-Field $pv "resp_model" "")
                    quota_model = [string](Get-Field $pv "quota_model" "")
                    reason      = "显示名/上游带 free 标签但回包 credit>0"
                }
            }
        }
    }
}
$staleModels = @()
$slowModels = @()
$now = Get-Date
if ($probeDict) {
    foreach ($pk in ($probeDict.Keys | Sort-Object)) {
        $pv = $probeDict[$pk]
        if ($pv -isnot [System.Collections.IDictionary]) { continue }
        $ms = Get-Field $pv "ms" $null
        if ($ms -is [System.ValueType] -and (([double]$ms) -gt 10000)) {
            $slowModels += [ordered]@{
                id = [string]$pk; display = [string](Get-Field $pv "display" "")
                ms = [double]$ms; status = [string](Get-Field $pv "status" "")
            }
        }
        $okAtRaw = [string](Get-Field $pv "ok_at" "")
        if (-not $okAtRaw) { continue }
        $okAt = $null
        try {
            $okAt = [datetime]::ParseExact($okAtRaw,
                @("yyyy-MM-dd HH:mm:ss", "yyyy-MM-ddTHH:mm:ss"),
                [System.Globalization.CultureInfo]::InvariantCulture,
                [System.Globalization.DateTimeStyles]::None)
        } catch {
            try { $okAt = [datetime]::Parse($okAtRaw) } catch { $okAt = $null }
        }
        if ($null -eq $okAt) { continue }
        $st = [string](Get-Field $pv "status" "")
        if ($st -eq "ok") { continue }
        $days = ($now - $okAt).TotalDays
        if ($days -gt 7) {
            $staleModels += [ordered]@{
                id = [string]$pk; display = [string](Get-Field $pv "display" "")
                status = $st; ok_at = $okAtRaw; days = [math]::Round($days, 1)
            }
        }
    }
}
# ── 零请求质量信号结束 ──────────────────────────────────────────────────────

$payload = [ordered]@{
    generated_at = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    alias_generated_at = [string]$alias["generated_at"]
    slot = [string]$alias["slot"]
    source = [ordered]@{ alias_map = $AliasMap; zgate_json = $ZgateJson }
    total = $modelsOut.Count
    groups = $groupCounts
    legacy_keys = $legacyKeys
    upstreams = $upstreamNames
    children = $childNames
    models = $modelsOut
    data_as_of = [string]$alias["generated_at"]
    probe_as_of = $probeAsOf
    probe_source = $probePath
    billing_suspect = @($billingSuspect)
    stale_models = @($staleModels)
    slow_models = @($slowModels)
    note = "本文件是当前生效清单的单一真值；docs/reports/MODEL-SYNC-*.md 是各自生成时刻的快照，手动 --apply 之后以本文件为准。三个零请求信号只复用 model_probe.json 已采字段守「免费标签 vs 实际扣费」漂移（历史事件 cn:hy4-preview-f 曾被判免费却累计扣 6601 积分，已按 0.29 计费修复）；只告警、不删模型、不改价、不发请求。"
}
$json = $payload | ConvertTo-Json -Depth 8
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($OutFile, $json + "`n", $utf8)
Write-Host ("真值视图已写入 " + $OutFile + "  total=" + $modelsOut.Count + "  legacy_keys=" + $legacyKeys + "  billing_suspect=" + @($billingSuspect).Count + "  stale=" + @($staleModels).Count + "  slow=" + @($slowModels).Count)
exit 0
