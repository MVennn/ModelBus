# functional-review 分片报告：端到端功能链路与 DSH 面向适配

> **一句话**：取样时刻的现役链路仍是「ZCode 兼容配置 `~/.zcode/v2/provider_config.json` 为最终写入真源 → `tools/dsh_sync.py` 读它再投影到 DSH `cordis.patch.yml`」，各类 agent 共用 `127.0.0.1:7871` 单一入口；文档层已改写成 DSH 主宿主叙事，实现层仍有 123 行 ZCode 命中（37 行契约层预期保留、86 行路径/叙述待迁移或改写），Go 侧 `X-Agent-Id` 分桶零实现且按主代理口径不纳入本轮验收。

---

## 0. 取样口径、证据纪律与可复现命令

- **真实项目根**：`F:\Project\ModelBus`（`git -C F:\Project\ModelBus rev-parse --show-toplevel` → `F:/Project/ModelBus`）。会话工作区 `F:\Project\_merged\DeepseekHarness` 是 junction 合并视图，全程穿透真实路径只读；视图根零新建。
- **索引**：`codegraph_status` 实测 `[!] Not initialized`（提示 `codegraph init`）。按分片纪律未自行 init，检索一律 `grep / glob / read`。
- **并发改写声明**：本会话内 `AGENTS.md`（107→108 行）、`README.md`（124→129 行）、`CONTRIBUTING.md`（74→75 行）、`docs/DSH-FIRST.md`（143→142 行）被主代理并行改写；`tools/agent_profiles.py` 在 15:50 取样时刚出现。本报告所有「当前态」数字以 **2026-11-11 15:44–15:51 取样时刻**为准，主代理验收时复核改后磁盘。历史 CHANGELOG 未作现状证据。
- **self-report 不作结论**：`AGENTS.md:6` 新增「实现层命名已去 ZCode」、`docs/DSH-FIRST.md:35`「第一方代码里旧名零残留」均按声明处理，结论以 `tools/` 与 `gateways/` 磁盘实测为准。

### 0.1 数字复核：两个独立命令

命令 A（`pwsh`，@(Select-String ...).Count 逐文件命中行数）：

```powershell
$files = @('README.md','AGENTS.md','CONTRIBUTING.md','sync-models.ps1','tools\dsh_sync.py','tools\model_alias.py','tools\model_caps.py','tools\model_probe.py','tools\model_score.py','tools\sync_report.py','tools\arena_leaderboard.py','gateways\zgate\zgate.json','gateways\zgate\internal\config\config.go','gateways\legacy-router\unified-router.js','docs\ARCHITECTURE.md','docs\MODEL-PROVIDERS.md','docs\ROUTING-POLICY.md','docs\DSH-FIRST.md')
foreach ($f in $files) { if (Test-Path $f) { $z = @(Select-String -Path $f -Pattern 'ZCODE_|ZCode|zcode|\.zcode' -AllMatches).Count; $d = @(Select-String -Path $f -Pattern 'DSH_|\.dsh|llm-pi-ai|cordis\.patch|DSH' -AllMatches).Count; Write-Output ('{0} zcode={1} dsh={2}' -f $f,$z,$d) } }
```

A 输出（exit 0，节选）：`tools\dsh_sync.py zcode=45 dsh=67`；`tools\model_alias.py zcode=19 dsh=15`；`tools\model_caps.py zcode=16 dsh=0`；`sync-models.ps1 zcode=3 dsh=6`；`gateways\zgate\zgate.json zcode=3 dsh=0`；`docs\ARCHITECTURE.md zcode=31 dsh=0`；`docs\MODEL-PROVIDERS.md zcode=41 dsh=3`；`docs\DSH-FIRST.md zcode=12 dsh=24`。

命令 B（逐行分列，修正版；**第一次统计曾因 PowerShell 变量名大小写不敏感踩坑**：`$T` 与循环内 `$t` 是同一变量，累加器被每行重置，误得 `SUM total=24`；改用 `$sumT` / `$t` 不同名后修正）：

```powershell
$files = @('README.md','AGENTS.md','CONTRIBUTING.md','sync-models.ps1','tools\dsh_sync.py','tools\model_alias.py','tools\model_caps.py','tools\model_probe.py','tools\model_score.py','tools\sync_report.py','tools\arena_leaderboard.py','tools\caps_upstream.py','gateways\zgate\zgate.json','gateways\zgate\internal\config\config.go','gateways\legacy-router\unified-router.js','docs\ARCHITECTURE.md','docs\MODEL-PROVIDERS.md','docs\ROUTING-POLICY.md','docs\DSH-FIRST.md')
$allRe = 'ZCODE_|ZCode|zcode|\.zcode'
$contractRe = 'provider_config\.json|ZCODE_PERSONAL_PROVIDER_CONFIG_FILE|ZCODE_BUILTIN|ZCODE_GATEWAY_KEY|zcode-main|zcode-free|zcode-saver|zcode-model-ledger|ZCodeGateway|third-party[/\\]zcode|NOTICE'
$pathRe = '~[/\\]\.zcode|\.zcode[/\\]v2|\.zcode\\v2|\.zcode/v2'
$sumT=0; $sumC=0; $sumP=0; $sumN=0; $implT=0; $implC=0; $docT=0; $docC=0
foreach ($f in $files) { if (-not (Test-Path $f)) { continue }; $t=0; $c=0; $p=0; $n=0; Get-Content -LiteralPath $f | ForEach-Object { if ($_ -match $allRe) { $t++; if ($_ -match $contractRe) { $c++ } elseif ($_ -match $pathRe) { $p++ } else { $n++ } } }; $sumT+=$t; $sumC+=$c; $sumP+=$p; $sumN+=$n; if ($f -like 'tools*' -or $f -like 'gateways*' -or $f -like 'sync-models*') { $implT+=$t; $implC+=$c } else { $docT+=$t; $docC+=$c }; Write-Output ('{0} total={1} contract={2} zcode_path={3} narrative={4}' -f $f,$t,$c,$p,$n) }
Write-Output ('SUM total={0} contract={1} zcode_path={2} narrative={3} impl_total={4} impl_contract={5} doc_total={6} doc_contract={7}' -f $sumT,$sumC,$sumP,$sumN,$implT,$implC,$docT,$docC)
```

B 输出（exit 0）：`SUM total=223 contract=52 zcode_path=25 narrative=146 impl_total=123 impl_contract=37 doc_total=100 doc_contract=15`。A 与 B 对 `tools\dsh_sync.py`（45 行）等单文件互相印证。

### 0.2 主代理 (a) 要求的两列口径（契约层排除表对照）

主代理契约层排除表：`~/.zcode/v2/provider_config.json` 路径、`ZCODE_PERSONAL_PROVIDER_CONFIG_FILE / ZCODE_BUILTIN / ZCODE_GATEWAY_KEY`、`zcode-main|zcode-free|zcode-saver` route id、`zcode-model-ledger.json`、`%LOCALAPPDATA%\ZCodeGateway\`、`third-party/zcode*` 原件、NOTICE 商标署名。

| 分列 | 行数 | 判定 |
|---|---|---|
| **契约层 ZCode（预期保留，不算未清理）** | **77** | `contract=52` + `zcode_path=25`（按 (a) 首句把 `~/.zcode/v2/*` 兼容投影路径归入契约层） |
| **第一方叙述性 ZCode（应改成 DSH / 宿主 / agent 词汇）** | **146** | docstring 主语、注释、WARN/ERROR 文案、函数名、User-Agent 等 |
| 合计 | 223 | 与 B 的 SUM 一致 |

细分（供主代理按更严口径取数）：契约层 77 行里，52 行是排除表明列关键词；25 行是 `~/.zcode/v2/*` 路径，其中 `provider_config.json / model-alias-map.json / zcode-builtin.json` 是 ZCode 真契约，`arena-main.json / model-scores.json / model_probe.json / quota-windows.json / model-sync-state.json / arena-leaderboard.json` 是**本仓自造产物借用该目录**（见 `tools/model_score.py:54-55`、`tools/model_alias.py:33,199,1960`、`tools/sync_report.py:34-35`、`tools/arena_leaderboard.py:54-56`），属实现层待迁，不算外部契约。若按此严口径：契约层 **52**、自造路径 **25**、叙述性 **146**。

按层：实现层（`tools/ + gateways/ + sync-models.ps1`）123 行命中，契约 37 / 路径+叙述 86；文档层 100 行命中，契约 15 / 路径+叙述 85。

---

## 1. 端到端功能链路图（逐跳：实际文件 + 函数/命令）

每日同步链（写侧，触发源 `sync-models.vbs` → `powershell -NoProfile -ExecutionPolicy Bypass -File sync-models.ps1`，`sync-models.ps1:20-24`）：

| 跳 | 位置 | 做什么 | 逐跳证据 |
|---|---|---|---|
| 0 触发 | `sync-models.ps1:26-29,206-208` | `param([switch]$Push)`，开场 Say；`$ROOT="F:\Project\ModelBus"`（:34） | `sync-models.ps1:31,34,42-46,61-89`（Resolve-Python / PYTHONIOENCODING / UTF-8 控制台 / 缺 Python 或仓库 exit 2） |
| 1 上游渠道采集 | providers/* | Go 套餐 `go_model_sync.py --apply`；WB 价格表 + `workbuddy_zcode_sync.py --max-rate 0.3 --apply`；Qoder `start-qoder-proxy.bat` + `qoder_zcode_sync.py --apply`；榜单 `arena_leaderboard.py --refresh --force --write`；分数 `model_score.py --write --quiet` | `sync-models.ps1:212,227-228,235-253,263,270`；三者写兼容投影见 `README.md:35-37`、`CONTRIBUTING.md:44`、`docs/MODEL-PROVIDERS.md:73,88-94,104` |
| 2 provider 表 + alias map | `tools/model_alias.py` | `--slot auto --apply --arena [--scores]` 归一化三组；备份 + 原子替换 `provider_config.json`，写 `model-alias-map.json` 与 `quota-windows.json` | `sync-models.ps1:275-278`；`model_alias.py:75-84`（三组 / PROVIDER_IDS）、`:468-483`（config_path / alias_path）、`:2588-2607`（`shutil.copy2` 备份 + `os.replace` 原子写 3 处）、`:1960-1963`（QUOTA_WINDOWS） |
| 3 探活 + 漂移收敛 | `tools/model_probe.py` / `model_alias.py --check` | `--timeout 90 --sleep 0.5 --max-tokens 256` 写 `model_probe.json`；过半可信才带 `--probe-file`；漂移则二轮 `--apply` + 复查 | `sync-models.ps1:289-333`；`model_probe.py:46-47,209-220,266-267`；`model_alias.py:2064`（apply_probe_filter）、`:2127`（--check） |
| 4 DSH 投影（第一处，best-effort） | `model_alias.py → dsh_sync.py` | `--apply` 末尾在 `not args.no_dsh and args.config is None` 时调 `sync_deepseek_harness(path)`，`subprocess.run([... dsh_sync.py --apply --config ...], timeout=180)`；失败仅 WARN | `model_alias.py:2008-2044`、`:2608-2611`、`:2155`（--no-dsh） |
| 5 DSH 投影（第二处，显式） | `sync-models.ps1:344-350` → `tools/dsh_sync.py` | `--check` 漂移 → `--apply` 重写 `~/.dsh/profiles/<p>/cordis.patch.yml` 的 `llm-pi-ai`、`.credentials.yaml` 引用、`zcode-model-ledger.json` | `dsh_sync.py:562-641`（_main）、`:462-481`（_merge_patch 只换 `zcode-*`）、`:484-510`（.tmp-dshsync + os.replace + .bak-dshsync）、`:517-552`（凭据引用）、`:73,141-149`（账本） |
| 6 流式准入 | `tools/model_stream_check.py --changed --soft` | 读 `cordis.patch.yml` 推导契约，活体探针只测变更项 | `sync-models.ps1:353-356`；`model_stream_check.py:62-65,129-140,506-517` |
| 7 报告 + 真值视图 | `tools/sync_report.py --write [--push]` / `current-models.ps1` | 写 `docs/reports/MODEL-SYNC-*.md` + `model-sync-state.json`；`-Push` 才 git add/commit/push | `sync-models.ps1:358-385`；`sync_report.py:400-407,437-451,361-397`；`:39-42`（阈值 85.0 / 1.0 / 10 / 30） |

运行时链（读侧，与每日同步解耦，常驻 zgate）：

| 跳 | 位置 | 做什么 | 逐跳证据 |
|---|---|---|---|
| 8 启动 | `gateways/zgate/main.go serve()` | `config.Load` → `keys.Load`（7 通道）→ `alias.New` → `ValidatePolicies` → `sup.Start()` → `net.Listen(cfg.Listen)` → `router.New(...).Handler()` | `main.go:139-247`（:131,:135,:150,:155-165,:166,:186-190,:195-197,:209-223） |
| 9 请求路由 | `router.go serveHTTP` | `/health` / `/models` / `POST /admin/reload` 直分；其余读 body.model → `aliases.Reload()` → `Resolve` → `routeAlias` → `routeChain/attemptChain` → `bridge.Forward` → 7 upstream | `router.go:569-644`、`:646-664`、`:1425`、`:1511-1543`、`:1547-1584`、`:1965-1988`；`alias.go:80-106,119,196`；`bridge.go:79,154,205,373,476` |
| 10 DSH / 各类 agent 消费 | `cordis.patch.yml` → `127.0.0.1:7871/v1` | DSH 读 `llm-pi-ai` 目录（`contextWindow / maxTokens / input / reasoningEfforts / compat`），会话 / 子代理 / headless / 服务插件共用单一 baseURL | `dsh_sync.py:349-381`（route 字段）、`:70`（DEFAULT_BASE）、`model_alias.py:85`（ROUTER_BASE）、`zgate.json:2`；`docs/DSH-FIRST.md:95-103` |
| 11 兼容投影 | ZCode 桌面端 | 约 1 秒轮询 `~/.zcode/v2/provider_config.json` | `README.md:44,77`、`docs/MODEL-PROVIDERS.md:84`；`legacy-router/unified-router.js:61-63,192` 回退同源 |

**「改为 DSH + 各类 agent」后哪些环节会断、怎么补：**

1. **真源切换断链（最大）**：`model_alias.py:2588-2592` 与 `dsh_sync.py:152-196` 都以 ZCode 配置为最终真源。若先摘掉 `provider_config.json` 写入而 `catalog/` 真源未落地，跳 1/2/3/11 全断（`catalog/` 实测只有 3 个文件：`model_caps.json / upstream_caps.json / upstream_caps_evidence.json`，是能力证据快照，不是模型目录真源）。补：先落 `catalog/` 真源 + `providers/_sink/` 单写者（`docs/DSH-FIRST.md:58-62`），再让 `dsh_sync.py` 优先读 catalog、ZCode 配置降级为兼容读取别名；**保留 `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` 兼容读取**。
2. **投影字段不等价 → DSH 模型选择器缺项**：`dsh_sync.py:171-182` 已为「型号消失」写 WARN（`provider "zcode-main" has no configured model "Gemini-AIS"`）。补：按 §5 字段表做逐字段行为等价对照后再切真源。
3. **zgate 默认路径改动需换版重启**：`zgate.json:3-4`（aliasMap / providerConfig）与 `config.go:243-415` 默认值若改，`router.go:1986` note 明确「alias map 路径仍需重启 zgate」，而仓规 §6 与本分片禁止会话重启 → 本轮不动这两个路径，只加环境变量优先读取，路径迁移留受控换版窗口。
4. **改名不同批 → 命令 FileNotFoundError**：`sync-models.ps1:228,253` 仍调旧名；`README.md:56-58,72` 与 `CONTRIBUTING.md:32,52` 已写新名，取样时刻磁盘脚本仍是旧名（§4-D1）。补：改名与所有引用点同批改 + 旧名保留 shim/兼容读取一个版本（`CONTRIBUTING.md:32` 的 `WB_PROBE_FILE`（旧名 `WB_ZCODE_PROBE_FILE` 仍兼容）已是正确范式）。
5. **多 agent 分桶断链**：Go 侧 `X-Agent-Id` / `agentId` / `agent_id` 在 `*.go` 中 0 命中（独立命令：`grep -R "X-Agent-Id|agentId|agent_id" gateways/zgate --include=*.go` → 0），改 Go 要换版重启。按主代理 (d)：**Go 侧分桶属后续演进、不纳入本轮验收**；本轮只落 `tools/agent_profiles.py` 只读投影（--list / --check），不改 Go、不重启长驻网关。
6. **双写 DSH 投影**：跳 4（best-effort）与跳 5（显式）重复投影同一 patch。补：二者取一，或显式段只做 `--check` 不计 Fail（见 §4-D2）。

---

## 2. 逐脚本/模块：输入、输出、触发、失败行为、环境变量与配置路径

| 模块 | 输入 | 输出 | 触发方式 | 失败行为 | 依赖 env / 配置路径 |
|---|---|---|---|---|---|
| `sync-models.ps1`（400 行） | Windows 计划任务；`-Push` 开关；本机 Python / git / 7871 / 7863 / 8790 | 5 段流水线产物 + `%LOCALAPPDATA%\ModelBus\logs\sync-*.log` + `_last-sync.txt` + toast | `powershell -NoProfile -ExecutionPolicy Bypass -File sync-models.ps1[-Push]`（:23-24） | `Invoke-Py` 非 0 且非 -Soft 累加 `$script:Fail`（:117-118）；末 `exit 1/0`（:399）；缺 Python/仓库 exit 2（:78-85）；`$ErrorActionPreference="Continue"`（:31）不中断 | `$ROOT=F:\Project\ModelBus`（:34）；`LOCALAPPDATA`（:42）；`PYTHONIOENCODING=utf-8 / PYTHONUTF8=1`（:66-67）；`WB_GATEWAY_KEY`（:220）；`USERPROFILE`（:291） |
| `tools/dsh_sync.py`（649 行） | `ZCODE_CONFIG`（`~/.zcode/v2/provider_config.json`，:61-66）；`DSH_HOME/profiles/<p>/cordis.patch.yml`；`.credentials.yaml`；`EFFECTIVE_SCRIPT`（:60）；`DSH_LEDGER`（:73） | `llm-pi-ai` patch 条目（`zcode-*` routes）、凭据引用、账本；`--check` 漂移 exit 1 | `python tools/dsh_sync.py [--apply|--check]`（:25-27）；`model_alias.py:2023` subprocess；`sync-models.ps1:345,348` | 缺 PyYAML `sys.exit`（:50）；`DshSyncError` → `ERROR: {exc}` exit 2（:644-649）；配置缺结构（:160-161）、无含模型 provider（:195）、找不到凭据文件（:536）、无 gateway apiKey（:545）硬失败；effective script 失败仅 WARN 退化（:205-228）；`PermissionError` 3 次重试（:484-510） | `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE`、`ZCODE_GATEWAY_KEY`（:69）、`DSH_HOME`（:67）、`DSH_PROFILE`（:68）；`shutil.which("node")`（:203） |
| `tools/model_alias.py`（2617 行） | `provider_config.json`（:468-474）、alias map、arena/scores/probe/pools/价目表、`provider_config.json` 三个落点 | 备份 + 原子替换 `provider_config.json`（:2588-2592）、alias map（:2594-2604）、`quota-windows.json`（:2605），末尾 best-effort 投影 DSH | `python tools/model_alias.py --slot auto --apply --arena [--scores] [--probe-file]`；`--check` 漂移 | 找不到 ZCode 配置（:2161）、找不到探测结果（:2320）、缺模板 provider（:2433）、渠道全无价（:2395）硬失败；主力探活不健康「只报不删」（:2343）；缺价 WARN 剔除（:2385）；DSH 投影失败仅 WARN（:2038）；分数/榜单/探测缓存读取失败静默降级（:495,513,581） | `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE`、`UNIFIED_MODEL_MAP`、`ARENA_MAIN_FILE`、`DSH_HOME`、`DSH_PROFILE`、`QD_API_KEY`（:975）；`~/.zcode/v2/*`（:33,199,1960） |
| `tools/sync_report.py`（463 行） | `provider_config.json` + alias map + 上一轮 `model-sync-state.json`（:45-67,406） | `docs/reports/MODEL-SYNC-*.md` + 索引 + 快照（:442-451）；`--push` 时 git add/commit/push（:361-397） | `python tools/sync_report.py --write [--push]`（:402-403），`sync-models.ps1:361-363` | 非 --write 打印 dry run return 0（:437-439）；模型消失打印 WARN（:431）；git_push 内 gate/status 失败 return 1（:371-394） | `ROOT`、`REPORT_DIR=docs/reports`、`REPO_URL`（:27-30）；`~/.zcode/v2/model-scores.json / quota-windows.json / model-sync-state.json`（:34-35,406） |
| `tools/model_caps.py`（1117 行） | alias map、`third-party/zcode/zcode-builtin.json`、现网 `provider_config.json`（:1023-1027） | 20 条能力真值表 / `--json` / `--check` 差异；`--apply --target` 写副本（:1099） | `python tools/model_caps.py [--check|--json|--apply --target PATH]` | `--check` 有差异 exit 1（:1030,1105）；缺 --target exit 2（:1074-1076）；`--apply` 拒绝写 `~/.zcode` 真身（:791「拒绝写入 %s：--apply 只允许写副本，~/.zcode 下的真身不动（进程也不重启）。」） | `ZCODE_BUILTIN`、`catalog/model_caps.json`、`catalog/upstream_caps.json`；`DEFAULT_ALIAS_MAP / DEFAULT_CURRENT = ~/.zcode/v2/*`（:1023-1027） |
| `tools/model_score.py`（187 行） | `~/.zcode/v2/arena-main.json`（:54） | `~/.zcode/v2/model-scores.json`（:55）或 dry-run 排行 | `python tools/model_score.py --write --quiet`（`sync-models.ps1:270` -Soft） | 无可用分数 print + return 1（:160-162）；非 --write dry run return 0（:172-174）；原子写（:177-179） | `--arena-main / --out`（:152-153）；`DEFAULT_BASELINE_PRICE=0.11`（:57） |
| `tools/model_probe.py`（285 行） | `provider_config.json`（:52-58）、alias map（:47,66-70）、旧探测结果（:233） | `~/.zcode/v2/model_probe.json`（:46,266-267） | `python tools/model_probe.py --timeout 90 --sleep 0.5 --max-tokens 256`（`sync-models.ps1:289` -Soft） | 无模型 `raise SystemExit("没有要探测的模型")`（:228-229）；alias 读取失败静默 `return {}`（:68-70）；状态词 ok/fallback/queued/rate_limited/blocked/unavailable/timeout/error（:10-12） | `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE`（:55）；`shutil.which("node")` 调 `zcode_effective_body.js`（:6,93） |
| `tools/arena_leaderboard.py`（390 行） | `https://api.arenaofbias.icu/api/leaderboard`（:7）、本地 cache、alias map、探测文件 | `~/.zcode/v2/arena-main.json`（:55）；`--apply` 时 subprocess 调 model_alias.py（:377-384） | `python tools/arena_leaderboard.py --refresh --force --write`（`sync-models.ps1:263` -Soft） | 拉榜失败用本地 cache（:12,312）；非 write/apply dry run return 0（:366-368）；`subprocess.run(..., check=True)`（:384）硬失败 | `--cache / --out / --probe-file` 默认 `~/.zcode/v2/*`（:54-56,284）；`--timeout=20`（:287）；UA `ZCodeAIModels-arena/1.0`（:111） |
| `tools/model_stream_check.py`（链尾） | `~/.dsh/profiles/<p>/cordis.patch.yml`（:62-65）、`patch-claude-style-effort.mjs`、豁免表 | 流式准入判定 + 可选 patch 修复 | `python tools/model_stream_check.py --changed --soft`（`sync-models.ps1:356` -Soft） | 找不到 patch `raise RuntimeError`（:132）；无 `zcode-*` 模型 `ERROR`（:526）；--soft 不阻断 | `DSH_HOME`、`DSH_PROFILE`（:62-63） |
| `tools/caps_upstream.py`（catalog 真源补充） | WB/OC/QN 上游 /models 接口（:8-12）、alias map、config.json | `catalog/upstream_caps.json` + `upstream_caps_evidence.json`（:36-38） | `python -B tools/caps_upstream.py --fetch`（:19）；无参数读快照；`--check`（:21） | 取不到字段留 null、跨跳冲突记 conflicts 不取舍（:14-16）；--check 差异 exit 1（:395,423-429） | `DEFAULT_ALIAS_MAP / DEFAULT_CURRENT = ~/.zcode/v2/*`（:34,37）；`gateways/upstream/workbuddy/config.json`（:35） |
| `gateways/zgate`（Go） | `zgate.json`（`config.go:209` Load）、7 通道凭据、alias map、HTTP 请求 | `127.0.0.1:7871/v1` 代理；`/health`、`/v1/models?scope=canonical|legacy|all`、`POST /admin/reload` | 计划任务 `\ModelBus-zgate-watchdog`；`zgate serve / status / install / uninstall / replay`（`docs/ARCHITECTURE.md:88-96`） | 配置读失败/非法 JSON（`config.go:209`）；`channelPolicy` Fatal 拒绝启动（`main.go:155-165`）；监听失败（:186-190）；panic → 502/500（`router.go:571-580`）；key 未配 502（:653-655）；链走完 502（:1579-1582）；alias 文件坏保留旧快照（`alias.go:79-106`） | `ZGATE_CONFIG / ZGATE_LISTEN`（`config.go:209,243`）、`UNIFIED_MODEL_MAP`、`ZCODE_PERSONAL_PROVIDER_CONFIG_FILE`、`OPENCODE_SESSION`、7 个 `*_API_KEY / *_KEY`（`keys.go:1-12`）、`ZGATE_PARENT_PID`（`main.go:252`）、`LOCALAPPDATA/ZCodeGateway`（`config.go:243-415`） |
| `gateways/legacy-router`（JS 回退） | 同一份 `provider_config.json` / alias map / 三通道 key | `UNIFIED_ROUTER_PORT=7871` 的旧版分流 | `node gateways/legacy-router/unified-router.js`（:24） | `forwardChain` 逐跳回落（:283）；协议桥 4 个转换器（`protocol_bridge.js:76,140,183,237`） | `UNIFIED_ROUTER_PORT / UNIFIED_ROUTER_HOST / WB_GATEWAY_BASE / QD_GATEWAY_BASE / OPENCODE_SESSION`（:28-31,59）、`ZCODE_PERSONAL_PROVIDER_CONFIG_FILE`（:61-63）、`UNIFIED_MODEL_MAP`（:192） |
| `docs/{ARCHITECTURE,MODEL-PROVIDERS,ROUTING-POLICY}.md`、`docs/DSH-FIRST.md` | 人写文档 | 叙述口径 | 人工维护 | 文档与实现不一致见 §4 | `docs/DSH-FIRST.md:132-140` 验收命令 |

---

## 3. 「ZCode 专项适配 → DSH 面向适配」改造清单

格式：逐项 file:line / 当前字符串 / 目标 DSH 形态 / 改动风险 / 兼容策略（旧环境变量是否保留兼容读取）。契约层按主代理 (a) 明确标「预期保留，不改」。

### 3.1 契约层（预期保留，禁止改名）

| # | file:line | 当前字符串 | 目标 | 风险 | 兼容策略 |
|---|---|---|---|---|---|
| C1 | `dsh_sync.py:61-66`、`model_alias.py:468-474`、`config.go:243`、`zgate.json:4` | `~/.zcode/v2/provider_config.json` / `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` | 原样 | 改则兼容投影端读不到 | 永久保留；新代码只读兼容别名 |
| C2 | `dsh_sync.py:69,517-531`、`AGENTS.md:51-52` | `ZCODE_GATEWAY_KEY` / `ZCODE_BUILTIN` | 原样 | 改则 DSH 凭据引用失效 | 永久保留 |
| C3 | `dsh_sync.py:8-9,76-80,354`、`model_alias.py:2080` | `zcode-main / zcode-free / zcode-saver`、`"zcode-" + slug` | 原样（DSH patch 内既有 route id） | 改则历史会话模型 provider 失效 | 永久保留；新 catalog 真源映射仍产出这三个 id |
| C4 | `dsh_sync.py:73` | `zcode-model-ledger.json` | 原样 | 改则上一轮账本丢失、dropped WARN 失准（:171-182） | 永久保留 |
| C5 | `config.go:243-415`、`zgate.json:73` | `%LOCALAPPDATA%\ZCodeGateway\` / `zgate.log` | 原样 | 改则日志与计划任务路径断 | 永久保留 |
| C6 | `third-party/zcode/LICENSE`、`README.md:109,121-122`、`CONTRIBUTING.md:53-55` | 上游原件与商标署名 | 原样 | 删除破坏署名 | 永久保留，勿动 |

### 3.2 实现层命名（本轮落地项，改中性名 + 旧名兼容 shim）

| # | file:line | 当前字符串 | 目标 DSH 形态 | 改动风险 | 兼容策略 |
|---|---|---|---|---|---|
| R1 | `sync-models.ps1:228` | `providers\workbuddy\workbuddy_zcode_sync.py` | `workbuddy_sync.py` | 不同批改 → FileNotFoundError | 旧名保留转发 shim 一个版本；`docs/DSH-FIRST.md:32,35` 要求同批改 `sync-models.ps1:228,253` |
| R2 | `sync-models.ps1:253` | `providers\qoder\qoder_zcode_sync.py` | `qoder_sync.py` | 同上 | 同上 |
| R3 | `dsh_sync.py:60,205,218,222,227` | `zcode_effective_body.js` | `effective_body.js` | `_effective_metadata`（:199-229）路径失效 → 档位/能力字段退化 | 优先新名，`if not exists` 回落旧名；`docs/DSH-FIRST.md:35` 列为 3 处硬回归面之一 |
| R4 | `model_probe.py:6,93`、`README.md:58` | `zcode_effective_body.js` | `effective_body.js` | 探测按宿主生效请求体失效 | 同上；`docs/DSH-FIRST.md:35` 点名 `model_probe.py:45` |
| R5 | `CONTRIBUTING.md:32` | `WB_ZCODE_PROBE_FILE`（旧名） | `WB_PROBE_FILE` | 旧计划任务/脚本仍设旧 env | **已按正确范式落地**：文档明写「旧名 `WB_ZCODE_PROBE_FILE` 仍兼容」；脚本需 `os.environ.get("WB_PROBE_FILE") or os.environ.get("WB_ZCODE_PROBE_FILE")`，本章其余项照抄 |
| R6 | `docs/DSH-FIRST.md:32`（旧版 :32） | `ZCODE_API_TYPE / ZCODE_BASE_URL / ZCODE_MAX_OUTPUT_TOKENS` | `MB_API_TYPE / MB_BASE_URL / MB_MAX_OUTPUT_TOKENS` | 自造 env 改名 | 旧名保留兼容读取别名，文档主语改「宿主 / 客户端」 |
| R7 | `tools/arena_leaderboard.py:111` | `"User-Agent": "ZCodeAIModels-arena/1.0"` | `ModelBus-arena/1.0` | 上游若按 UA 限流需回归 | 纯标识，无兼容负担；建议同批改 |

### 3.3 自造产物路径（从 `~/.zcode/v2/` 迁出，属实现层）

| # | file:line | 当前字符串 | 目标 DSH 形态 | 风险 | 兼容策略 |
|---|---|---|---|---|---|
| P1 | `model_score.py:54-55`、`arena_leaderboard.py:54-56`、`model_alias.py:33,199` | `~/.zcode/v2/{arena-main,arena-leaderboard,model-scores,model_probe}.json` | `catalog/` 或 `$DSH_HOME/state/` | 改路径则 `sync-models.ps1:291` 与 `model_alias.py --probe-file / --arena-main / --scores` 需同批改 | 新路径优先；旧路径存在时兼容读取（不写回），过渡期双读 |
| P2 | `model_alias.py:1960`、`sync_report.py:34-35,63,406` | `~/.zcode/v2/{quota-windows,model-sync-state}.json` | 同上 | 报告/漂移基线丢失 | 同上 |
| P3 | `sync-models.ps1:291` | `Join-Path $env:USERPROFILE ".zcode\v2\model_probe.json"` | 与 P1 新路径一致 | 探活过半判据（:305）读不到 → 本轮不摘模型（降级，不致命） | 保留旧路径 fallback |

### 3.4 叙述性主语 / docstring（改成 DSH / 宿主 / agent 词汇）

| # | file:line | 当前字符串 | 目标 | 风险 | 兼容策略 |
|---|---|---|---|---|---|
| N1 | `dsh_sync.py:2,4-6,8,11-12,21,29-31,318,563` | `Project ZCode's final model groups...` / `同步 ZCode 最终模型到 DeepSeekRuntime` | 「读 catalog 真源，投影 DSH llm-pi-ai；ZCode 配置为兼容读取别名」 | 仅文字；但切真源后描述会误导 | 与 §5 字段等价改动同批 |
| N2 | `dsh_sync.py:125,127,161,195`、`model_alias.py:2161`、`model_caps.py:791` | `找不到 ZCode 配置` / `ZCode 配置缺少...` / `ZCode 配置不是合法 JSON` | 「找不到模型目录真源（或兼容投影配置）」 | 错误文案误导排障 | 保留旧文案中路径字面量供 grep |
| N3 | `model_alias.py:2,16,2213,2301`、`model_probe.py:2`、`model_caps.py:3,7,18`、`caps_upstream.py:4` | `Rebuild ZCode's model list as four...` / `The three providers` / `unified four-group` | 「三组；宿主无关的模型目录」 | 四组 vs 三组自相矛盾（§4-D6） | 同批修正组数 |
| N4 | `dsh_sync.py:245` | `ZCode 配置是档位的唯一正本；DSH 侧只是投影。` | 「catalog 是档位唯一正本；DSH / ZCode 均为投影」 | 这是真源切换的核心语义 | 必须随 §5 一起改，否则 _efforts_lost 判据失效 |
| N5 | `docs/ARCHITECTURE.md` 31 行、`docs/MODEL-PROVIDERS.md` 41 行命中 | 「对 ZCode 来说…」「ZCode 里现在有哪几个 provider」 | 主语改「宿主 / DSH / 兼容投影」 | 纯文档 | 按 `docs/DSH-FIRST.md:115-128` 8 处过期口径逐行改，勿整篇重写 |
| N6 | `alias.go:1-6`、`router.go:1498-1500` | `Package alias reads ~/.zcode/v2/...` / `ZCode 看到的是 zgate-owned catalog` | 「宿主看到的是 zgate-owned catalog」 | Go 注释改动需换版重启才生效（仓规 §6） | 本轮只记不改，留受控换版窗口 |

### 3.5 架构真源（主代理 (c) 本轮要动的项）

| # | file:line | 当前字符串 | 目标 | 风险 | 兼容策略 |
|---|---|---|---|---|---|
| A1 | `dsh_sync.py:61-66,152-196` | `ZCODE_CONFIG = ...provider_config.json` → `_zcode_providers(cfg)` | `catalog/` 真源优先；`provider_config.json` 降级为兼容读取别名 | **最高**：字段不等价会让 DSH 模型选择器缺项（:171-182 已有 WARN 证据） | 按 §5 逐字段等价对照；保留 `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` 兼容读取 |
| A2 | `model_alias.py:2588-2592,2608-2611` | `os.replace(tmp, path)` 写 ZCode 配置为最终写入器 | `providers/_sink/` 单写者；ZCode 配置降为投影之一（`docs/DSH-FIRST.md:58-62`） | 三套脚本写入段并发覆盖 | 投影器不写真源；一次写入一个落点 |
| A3 | `AGENTS.md:6`、`docs/DSH-FIRST.md:23,25,32,35,85,87,107-111`、`README.md:7-9,25-28` | 「实现层命名已去 ZCode」「第一方代码里旧名零残留」「多 agent 已是当前架构」 | 落地后再改声明；未落地前标「进行中」 | 声明超前于实现 → 验收误判 | 验收以 `tools/` 与 `gateways/` 实现为准（主代理已采纳） |
| A4 | `tools/agent_profiles.py`（15:50 取样时刚出现，未验内容）、Go 侧 0 命中 | 无 `X-Agent-Id` 分桶 | 只读 agent 投影（--list / --check）本轮落地；Go 分桶后续演进 | 改 Go 需换版重启 | 按主代理 (d)：**Go 侧分桶不纳入本轮验收**；不改 Go、不重启长驻网关 |

---

## 4. 功能缺陷与文档/实现不一致清单（附证据）

| # | 现象 | 证据 A | 证据 B | 判定 / 影响 |
|---|---|---|---|---|
| D1 | 文档已写新脚本名，磁盘仍是旧名 | `README.md:56-58,72`（`workbuddy_probe.py / qoder_probe.py / effective_body.js / workbuddy_sync.py / qoder_sync.py`）、`CONTRIBUTING.md:32,52` | `glob("providers/**/*zcode*")` 实测 7 个旧名文件仍在（`workbuddy_zcode_sync.py / qoder_zcode_sync.py / qwen_zcode_sync.py / zcode_effective_body.js / workbuddy_probe_zcode.py / qoder_probe_zcode.py / validate_zcode_models.py`）；`glob("providers/**/*sync*")` 仅 5 项，无新名 | 高：`sync-models.ps1:228,253` 仍调旧名，改名不同批会断流水线；`docs/DSH-FIRST.md:35`「第一方代码里旧名零残留」为超前声明 |
| D2 | DSH patch 双写 | `model_alias.py:2608-2611`（`sync_deepseek_harness(path)` best-effort --apply） | `sync-models.ps1:344-350`（再 `dsh_sync.py --check/--apply`） | 中：同一 patch 一轮两次投影；`model_alias.py:2009-2014` 自承 best-effort，第二段才严格；建议二者取一，或显式段只 --check 不计 Fail |
| D3 | 声明「实现层已去 ZCode」与实测冲突 | `AGENTS.md:6`「实现层命名已去 ZCode，但契约层一个字不动」 | 命令 B：`impl_total=123 impl_contract=37`，即 86 行实现层路径/叙述仍带 ZCode（`dsh_sync.py` 45 行中 27 行叙述） | 高：验收口径风险；主代理已采纳「以 tools/ 与 gateways/ 实现为准」 |
| D4 | 声明「旧名零残留」与实测冲突 | `docs/DSH-FIRST.md:35`「本轮 6 个脚本与这些引用点同批改完，第一方代码里旧名零残留」 | `sync-models.ps1:228,253,291` + `dsh_sync.py:60` + `model_probe.py:6` 旧名/旧路径仍活；`docs/DSH-FIRST.md:35` 自己列的 3 处硬回归面未清 | 高：同 D1 |
| D5 | 「多 agent 已是当前架构」超前 | `docs/DSH-FIRST.md:25,87,107-111`、`README.md:27`「`tools/agent_profiles.py` 给每个 agent 提供只读投影接口」 | Go 侧 `grep "X-Agent-Id|agentId|agent_id" --include=*.go` → 0 命中；`glob("tools/agent_profiles.py")` 15:50 才出现且内容未验 | 中：按主代理 (d) Go 分桶不纳入本轮验收；文档应注明「接口本轮、分桶后续」避免过度声明 |
| D6 | 组数自相矛盾 | `docs/ARCHITECTURE.md:32`「四个 chat 组」、`:251,331`「四组共 36 个模型」、`model_alias.py:2`「four credit-based groups」、`model_probe.py:2`「unified four-group」 | `docs/ARCHITECTURE.md:75-76`「三组」、`model_alias.py:16`「The three providers」、`:84` `GROUPS = ("main","free","low")`、`docs/MODEL-PROVIDERS.md:128-133`「现行 ZCode 只有 3 个 chat provider」 | 中：现役为三组；`docs/DSH-FIRST.md:121` 已列为过期口径 |
| D7 | 目录条数多个数字打架 | `docs/ROUTING-POLICY.md:258`「canonical total=19 / catalog_total=91 / legacy total=72（2026-11-11 实测）」 | `router.go:1504-1505,1508` 注释「canonical 20 条 / legacy 73 条 / 93 条混表」；`docs/ARCHITECTURE.md:331`「36 个模型」 | 中：注释为写代码时快照，实测值随上游目录走；`router.go:1532-1534` 明确 total 是本次返回条数、catalog_total 是全量，勿混。建议注释改「示例值」并指向 :258 |
| D8 | Qoder 生命周期不符 | `docs/MODEL-PROVIDERS.md:266`「Qoder 常驻」 | `gateways/zgate/zgate.json:95-105` `children.qoder policy "ondemand" / idleSeconds 300 / windows [08:58-09:15,20:58-21:15,21:58-22:15]` | 中：现役按需拉起 + 300s 空闲回收，非常驻；`docs/ARCHITECTURE.md:400-402` 已改口径 |
| D9 | 已退役守护器仍写成回退命令 | `docs/ARCHITECTURE.md:316`「P1：zgate uninstall → 重新 `zcode_gateway_watch.ps1 -Install`」 | `docs/ARCHITECTURE.md:212`「zcode_gateway_watch.ps1 / .vbs 退役」；`docs/DSH-FIRST.md:127` 列为过期口径；`AGENTS.md:108` 只走 `\ModelBus-zgate-watchdog` | 中：照抄会拉起已退役进程 |
| D10 | 注释与实现零命中 | `model_alias.py:363-368`「dsh_sync.py 对缺失字段的处理是「不写键」，落宿主自己默认值，不会兜 1000000 / 128000」 | `dsh_sync.py` 内 `1000000 / 128000` 零命中；`docs/DSH-FIRST.md:126` 已列 | 低：注释描述的是正确行为，但引错对象；不影响运行 |
| D11 | catalog/ 真源声明与磁盘不符 | `README.md:9,22,25`「一份 `catalog/` 模型目录真源，投影到 DSH」、`docs/DSH-FIRST.md:22` | `glob("catalog/*")` = 3（`model_caps.json / upstream_caps.json / upstream_caps_evidence.json`），全是能力证据快照；`dsh_sync.py:61-66,152-196` 仍读 `provider_config.json` | 高：真源未落地即先改文档；切真源前需补齐目录文件 + 单写者 |
| D12 | 述职口径与取样时刻 | `README.md:7,25-28,43`、`CONTRIBUTING.md:7,44`「主宿主是 DSH」 | 写侧 `sync-models.ps1:275-278` 仍以 `model_alias.py` 写 ZCode 配置为最终写入器；DSH 只是 :344-350 的下游投影 | 高：叙事 DSH 主宿主，实现 ZCode 中心；这正是主代理 (c) 要动的架构项 |
| D13 | 计划任务用 Start-Process 拉子进程 | `sync-models.ps1:239` `Start-Process -FilePath start-qoder-proxy.bat -WindowStyle Hidden` | `AGENTS.md:108` 禁止 `Start-Process / cmd /c` 直接拉起 **zgate** | 低：对象不同（qoder 代理，非 zgate），不构成违规；但同类模式建议统一到 supervisor（`config.go:35-47` children ondemand） |
| D14 | 第一方 UA / 文案带旧项目名 | `arena_leaderboard.py:111` `"ZCodeAIModels-arena/1.0"`、`model_stream_check.py:140,526` `zcode-*` 过滤 | 契约层 route id `zcode-*` 须保留（C3）；UA 属自造（R7） | 低：区分「契约 id 保留」与「UA 改名」 |

---

## 5. `tools/dsh_sync.py:152-196` 输入/输出字段逐项（主代理 (c) 等价性对照表）

**函数签名**：`def _zcode_providers(cfg: dict[str, Any]) -> list[dict[str, Any]]:`（:152）。输入是 `_read_json(args.config)`（:121-127、`_main:562-641`），即整份 `provider_config.json`。

### 5.1 输入字段（按读取顺序）

| # | 输入键路径 | 行 | 类型 / 缺省 | 用途 |
|---|---|---|---|---|
| I1 | `cfg["config"]["providerConfigRules"]["providerRules"]` | :154-158 | list[dict]，按 `r["providerId"]` 建成 dict | provider 规则全集 |
| I2 | `cfg["config"]["providerOrder"]` | :159 | list[str]，缺省 `list(rules)` | 决定 DSH 选择器里的 provider 顺序 |
| I3 | `rule["providerName"]` | :188 | str，缺省 `provider_id` | → route.displayName |
| I4 | `rule["config"]["modelOrder"]` 或 `rule["config"]["personalModelIds"]` | :169 | list，缺省 `[]` | → `modelIds`（前者优先） |
| I5 | `rule["config"]["api"]["baseUrl"]` | :190 | str，缺省 `DEFAULT_BASE="http://127.0.0.1:7871/v1"`（:70） | → route.baseURL |
| I6 | `rule["config"]["access"]["apiKey"]` | :191 | str，缺省 `""` | → `_credentials_state` 写 `refs.ZCODE_GATEWAY_KEY`（:534-552） |
| I7 | `cfg["config"]["modelConfigRules"]["providerModelRules"]` | :268-277（`_model_rules`，独立读） | list → {(providerId, modelId): config} | → `_fallback_meta`（:280-292）能力/档位兜底 |
| I8 | `DSH_LEDGER` 上一轮 `providers.<id>.modelIds` | :130-138,176 | `~/.dsh/profiles/<p>/zcode-model-ledger.json` | 算 `dropped` WARN（:176-182） |
| I9 | `EFFECTIVE_SCRIPT` 输出 | :199-229（`_effective_metadata`） | node `zcode_effective_body.js` 的 JSON | → `_metadata_for`（:295-314）优先值；失败退化 I7 |

### 5.2 输出字段（每项 5 键，:185-193）

| # | 输出键 | 来源 | 下游消费 |
|---|---|---|---|
| O1 | `providerId` | I1/I2 的 `provider_id` | `KNOWN_PROVIDER_IDS` 映射（:76-80,351-354）→ `zcode-main/free/saver` 或 `"zcode-"+slug` |
| O2 | `providerName` | I3 | route.displayName（:373） |
| O3 | `modelIds` | I4 | 逐条 `_build_route`（:356-371）→ models[] |
| O4 | `baseUrl` | I5 或 :70 缺省 | route.baseURL（:377） |
| O5 | `apiKey` | I6 | `_credentials_state(args.dsh_home/".credentials.yaml", patch_key, args.apply)`（:562-641,534-552） |

### 5.3 逐 model 派生字段（:295-381，等价性必查）

| 字段 | 计算 | 行 |
|---|---|---|
| `id` | O3 的 model_id | :362 |
| `contextWindow` | `_metadata_for` 的 `props.contextWindow`，正整才写（`_positive_int`） | :309,363,365-366 |
| `maxTokens` | `opts.maxOutputTokens.max`，正整才写 | :310,364,367-368 |
| `input` | `["text","image"]` 若 `supportsImage` 否则 `["text"]` | :311,369 |
| `reasoningEfforts` | `_reasoning(values, map)`：`map == "{}"` 返回空；`disabled` → {off:disabled}；只保留 `DSH_LEVELS`（:71）内且 != off | :317-342,370 |
| `compat.thinkingFormat` | 仅 `map` 含 `reasoning_effort` 时写 `deepseek`（:74-75,333-341） | :330-341 |
| route 级 | `displayName / retryPolicy(deepcopy RETRY_POLICY :85-94) / api="openai-completions" / baseURL / apiKeyEnv="ZCODE_GATEWAY_KEY" / models` | :372-380 |

### 5.4 等价性红线（切 `catalog/` 真源时逐项核对）

1. **O1–O5 五键一个不少**，且 `providerOrder` 顺序、`modelOrder` 优先于 `personalModelIds` 的语义保留（:159,169）。
2. **`DEFAULT_BASE` 兜底**（:70,190,377）：catalog 缺 baseUrl 时仍落 `http://127.0.0.1:7871/v1`，否则 DSH 会话直接连不上。
3. **`dropped WARN` 不丢**（:171-182）：账本 `zcode-model-ledger.json` 是 C4 契约层，文件名与路径不变。
4. **档位判据不翻**：`_efforts_lost`（:242-265）docstring 现写「ZCode 配置是档位的唯一正本；DSH 侧只是投影」（:245），切真源后必须同步改成「catalog 是唯一正本」，否则「源头非空、投影为空」的 --check 判失败逻辑（:247,264）会拿错对照源。
5. **`_merge_patch` 的 `zcode-*` 前缀过滤**（:462-481，`if not str(key).startswith("zcode-")`）与非 zcode provider 保留语义不变（:15）。
6. **凭据引用**：I6 的 apiKey 写 `refs.ZCODE_GATEWAY_KEY`（:517-531），catalog 真源里必须带同名字段或明确可从兼容配置读取；缺失会触发 :545「ZCode provider 配置里没有 gateway apiKey，无法写 DSH 凭据引用」硬失败。
7. **effective metadata 退化链**：I9 失败时（node 不存在 / 脚本不存在 / 非 0 / 非 JSON）仅 WARN 并退化 I7（:205-228），catalog 真源须自己带齐这些能力字段，否则 DSH 侧上下文窗口/最大输出悄悄变默认值（`model_alias.py:363-368` 已指出「不写键」行为）。

---

## 6. 完成判据核对表

| # | 任务书判据 | 本报告落点 | 状态 | 证据 |
|---|---|---|---|---|
| 1 | ① 功能链路图：上游渠道探测 → provider 表 → alias map → zgate 桥接 → DSH cordis.patch.yml → 各类 agent 消费，逐跳写实际文件与函数/命令 | §1 两张表共 12 跳 + 6 条断链/补法 | 完成 | 每跳附 file:line；`sync-models.ps1:212-385`、`model_alias.py:2588-2611`、`main.go:139-247`、`router.go:569-644,1547-1584`、`dsh_sync.py:562-641` |
| 2 | ② 每个脚本/模块的输入、输出、触发方式、失败行为、依赖环境变量与配置路径表 | §2，14 行（11 个脚本/模块 + 2 个链尾补充 + 文档组 1 行） | 完成 | 每行附 file:line 与原始报错字符串 |
| 3 | ③ 改造清单：逐项 file:line、当前字符串（含 `~/.zcode/v2/*`、`ZCODE_*`、`zcode-main/free/saver`、`*_zcode_sync.py` 等）、目标 DSH 形态、改动风险、兼容策略（旧环境变量是否保留兼容读取） | §3 五组共 27 项（C1–C6 / R1–R7 / P1–P3 / N1–N6 / A1–A4） | 完成 | 每项 6 列齐全；R5 给出 `os.environ.get("WB_PROBE_FILE") or os.environ.get("WB_ZCODE_PROBE_FILE")` 兼容范式 |
| 4 | ④ 功能缺陷与文档/实现不一致清单（附证据） | §4，D1–D14 共 14 条 | 完成 | 每条双证据 file:line 或可复现命令/数字 |
| 5 | 区分「仍是 ZCode 中心」与「已是 DSH 面向」证据，不把历史 CHANGELOG 当现状证据 | §0 取样口径 + D3/D12 明确「实现 ZCode 中心 / 叙事 DSH 主宿主」 | 完成 | `dsh_sync.py:2,4-6,152-196,245` vs `README.md:25-28` |
| 6 | 主代理 (a)：契约层 vs 第一方叙述性 ZCode 分列数字 | §0.2：契约 77 / 叙述 146，合计 223；严口径 52 / 25 / 146 | 完成 | 命令 B exit 0 输出 `SUM total=223 contract=52 zcode_path=25 narrative=146`；含 PowerShell 变量名踩坑与修正记录 |
| 7 | 主代理 (b)：重读 15:44 改写后的 `docs/DSH-FIRST.md` | §0 + D5 + A3 引用当前 142 行版（:3,19-25,27-35,82-88,107-111） | 完成 | `docs/DSH-FIRST.md:25`「多 agent 已是当前架构」、:87「接口本轮落地；分桶按 §6 演进」 |
| 8 | 主代理 (c)：`dsh_sync.py:152-196` 输入/输出字段逐项列出 | §5：I1–I9 / O1–O5 / 6 个派生字段 / 7 条等价红线 | 完成 | 逐行号；含 :245 档位正本文案须随真源切换 |
| 9 | 主代理 (d)：Go 侧 `X-Agent-Id` 分桶属后续演进、不纳入本轮验收；不改 Go、不重启网关 | §1 断链 5、A4、D5 | 完成 | `grep ... --include=*.go` → 0 命中；`AGENTS.md:107-108`、`router.go:1986` |
| 10 | 纪律：只读分析，唯一可写产物是本分片报告 | 本报告之外零写入 | 完成 | 未改 PROGRESS.md / docs/ / tests/ / provider_config.json / 配置 / CHANGELOG / memories/ / 其它 evidence / 第三方署名；未 git add/commit/push；未重启 zgate；凭据未入文件与汇报 |
| 11 | 所有结论附 file:line 与可独立复现命令/数字；self-report 不当结论 | §0.1 两条命令 + 全文 file:line | 完成 | 命令 A / B 均 exit 0；D3 明确排除 AGENTS.md:6 声明 |
| 12 | 报告写 `F:\Project\ModelBus\evidence\agent-functional-review.md` 并 send_message 回报主代理 | 本文件 + 收尾 send_message | 完成 | 见文件落盘回执与主代理消息回执 |

**遗留限制（非本分片范围）**：(1) 取样期间主代理并行改写 `docs/`、`AGENTS.md`、`README.md`、`CONTRIBUTING.md` 与新增 `tools/agent_profiles.py` / `dsh_sync.py` 真源开关，本报告「当前态」数字定格在 15:44–15:51，验收请复核改后磁盘；(2) `tools/agent_profiles.py` 取样时刻刚出现，未读其内容，其 `--list / --check` 行为未独立验证；(3) 未执行 `dsh_sync.py --check` / `model_caps.py --check` 等活体门禁（本分片只读、不触长驻网关），门禁结果以主代理验收为准；(4) 契约层 25 行 `~/.zcode/v2/*` 路径中 6 个自造产物文件是否外迁，需主代理在 §3.3 P1–P3 拍板。
