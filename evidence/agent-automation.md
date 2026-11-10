# 自动性到哪一步 —— 只读取证分片（agent-automation）

> 状态：**初稿已落盘**，继续补证据中（父代理 17:10 指令：先落盘再补证据）。
> 真实项目根：F:\Project\ModelBus；命令真实输出 git rev-parse --show-toplevel → F:/Project/ModelBus，git branch --show-current → main。
> junction 视图 F:\Project\_merged\DeepseekHarness 不是项目身份；codegraph_status 默认指向该视图且报 Not initialized，显式 projectPath=F:\Project\ModelBus 报 [ERR] Failed to get status: unable to open database file（索引不可用），本分片全部结论回源码/配置/运行态核实。
> 取证时间 2026-11-09 17:05–17:10 +08:00。取证工具：powershell.exe -NoProfile -Command (PS 5.1.26100.9818)、read、grep、glob、git。
> 只读合规：本轮未执行任何 --apply、未写 provider_config.json / cordis.patch.yml、未重启/停止网关、未打印任何凭据真值（只出现变量名与长度）、未 git add|commit|push。

## 0. 结论速览（初稿，判据见后）

| # | 硬结论 | 证据锚点 |
|---|---|---|
| C1 | 「发现→建档→探活→评分→收敛→报告」主链是每天 12:00 全自动触发的，不是人工点一次跑一次 | Get-ScheduledTaskInfo 三任务实况 + sync-models.ps1:209-354 |
| C2 | 但「模型可用」的最后一公里不在定时任务里：主力组人工精选、备用组人工指定、白名单人工维护，自动只做「按硬门槛收录 + 裁掉明显更差的」 | go_model_sync.py:34-35、model_alias.py:140-169,469-478 |
| C3 | 探活与探活结果的消费是两轮 apply 串行依赖，且 --check 必须与 --apply 同参数，否则产生「假漂移」每天二轮重写 | sync-models.ps1:279-320、model_alias.py:1717,1897,1932 |
| C4 | 运行期自愈（子进程拉起/逐跳回落/冷却）是代码级全自动；但改 Go 代码后 /admin/reload 只热加载策略/空闲/窗口，换二进制仍需人工触发换版链 | 待补 supervisor.go / alias.go / router.go 精确行（下一步） |
| C5 | 凭据首次注入、新上游接入、候选回滚触发、地区 403 的 proxy 配置均为人工卡点（脚本只消费已有值，不产生凭据） | sync-models.ps1:215-224、go_model_sync.py:26、待补换版脚本 |

## 1. 定时触发：命令真实输出

命令：powershell.exe -NoProfile -Command 'Get-ScheduledTask | Where-Object { $_.TaskName -like "ModelBus*" } | ForEach-Object { ... Get-ScheduledTaskInfo ... }'（输出含 CIM 元数据，下表按字段摘录，值未改；exit=0，stderr 空）。

### ModelBus 模型同步（TaskPath: \ | State: Ready）
```
TRIGGERS_JSON: MSFT_TaskDailyTrigger, Enabled=true, StartBoundary=2026-11-04T12:00:00, DaysInterval=1, Repetition.Interval=null, Repetition.Duration=null, StopAtDurationEnd=false, RandomDelay=null
ACTIONS_JSON : Execute=wscript.exe, Arguments="//nologo F:\Project\ModelBus\sync-models.vbs", WorkingDirectory=null
INFO: LastRunTime=11/09/2026 12:00:01 | LastTaskResult=0 | NextRunTime=11/10/2026 12:00:00 | NumberOfMissedRuns=0
```
判据：Daily / DaysInterval=1 / Repetition.Interval=null → 每天 12:00 一次，无分钟级重复；LastTaskResult=0 表示昨轮成功。

### ModelBus-zgate-hidden（TaskPath: \ | State: Ready）
```
TRIGGERS_JSON: MSFT_TaskLogonTrigger, Enabled=true, UserId=MVENN-PC\<用户名>, StartBoundary=null, Delay=null, Repetition.Interval=null, StopAtDurationEnd=false
ACTIONS_JSON : Execute=wscript.exe, Arguments="//B //Nologo \"C:\Users\<用户名>\AppData\Local\ZCodeGateway\launch-zgate.vbs\"", WorkingDirectory=null
INFO: LastRunTime=11/09/2026 16:33:08 | LastTaskResult=0 | NextRunTime= | NumberOfMissedRuns=0
```
判据：登录时触发一次（非周期），无 Repetition；NextRunTime 空符合 LogonTrigger 语义。

### ModelBus-zgate-watchdog（TaskPath: \ | State: Ready）
```
TRIGGERS_JSON: MSFT_TaskTimeTrigger, Enabled=true, StartBoundary=2026-11-06T22:14:00, Repetition.Interval="PT1M", Repetition.Duration=null, StopAtDurationEnd=false, RandomDelay=null
ACTIONS_JSON : Execute=wscript.exe, Arguments="//B //Nologo C:\Users\<用户名>\AppData\Local\ZCodeGateway\ensure-zgate.vbs", WorkingDirectory=null
INFO: LastRunTime=11/09/2026 17:09:01 | LastTaskResult=0 | NextRunTime=11/09/2026 17:10:00 | NumberOfMissedRuns=0
```
判据：Repetition.Interval=PT1M → 每 1 分钟兜底检查一次；17:09:01 刚跑过、17:10:00 下次，运行态活跃。

### 三个 VBS（真实路径 + 行号 + 源码原文）
- F:\Project\ModelBus\sync-models.vbs:14：cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & ps1 & """"；:17：shell.Run cmd, 0, False（0=隐藏、False=不等待）。
- C:\Users\<用户名>\AppData\Local\ZCodeGateway\launch-zgate.vbs:5：ps1 = fso.BuildPath(here, "start-zgate-nw.ps1")；:8：sh.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & ps1 & """", 0, False。
- C:\Users\<用户名>\AppData\Local\ZCodeGateway\ensure-zgate.vbs:5：ps1 = fso.BuildPath(here, "ensure-zgate.ps1")；:8 同上 Run。
- 仓内同源副本存在：tools\zgate-lifecycle\launch-zgate.vbs / ensure-zgate.vbs（glob tools/zgate-lifecycle/** 输出 9 个文件，见 §8）。

## 2. sync-models.ps1 五段流水线（真实路径 F:\Project\ModelBus\sync-models.ps1，共 379 行）

:11-16 自述「五段流水线：一、Go 套餐 / 二、WorkBuddy2API（倍率上限 0.30）/ 三、Qoder（含入口健康检查与直连回退）/ 四、统一命名与分组 / 五、同步报告与推送」。逐段实况（源码原文摘录）：

| 段 | 行号 | 源码原文（节选） | 自动? |
|---|---|---|---|
| 环境 | :33-34 | $ROOT = "F:\Project\ModelBus"；$GIT_DIR = "C:\Program Files\Git\cmd" | 固定值，人工配置 |
| 一 Go | :211 | Invoke-Py "Go 套餐同步" @("providers\opencode-go\ops\go_model_sync.py", "--apply") | 自动（带 --apply 写盘） |
| 二 WB 凭据 | :215-224 | $env:WB_GATEWAY_KEY = ($keyCode | & $PY -).Trim()；:223 Say ("WB_GATEWAY_KEY 已载入（" + $env:WB_GATEWAY_KEY.Length + " 字符）") | 半自动：从 gateways/upstream/workbuddy/config.json 的 api_key 读入环境变量，只报长度不报真值 |
| 二 WB | :226-227 | workbuddy_fetch_pricing.py；workbuddy_zcode_sync.py --max-rate 0.3 --apply | 自动 |
| 三 Qoder 代理 | :234-249 | if (-not (Test-Port "127.0.0.1" 8790)) { ... Start-Process -FilePath $bat -WindowStyle Hidden; Wait-Port "127.0.0.1" 8790 90 } | 自动拉起（detached + 端口轮询） |
| 三 Qoder | :252 | qoder_zcode_sync.py --apply | 自动 |
| 四 榜单 | :262 | tools\arena_leaderboard.py --refresh --force --write -Soft | 自动，失败降级沿用旧候选（:263-265） |
| 四 分数 | :269 | tools\model_score.py --write --quiet -Soft | 自动，失败则不带分数选型（:270-275） |
| 四 首轮 apply | :274-276 | $scoreArgs = @("tools\model_alias.py", "--slot", "auto", "--apply", "--arena")；if ($scoresOn) { $scoreArgs += "--scores" }；Invoke-Py "统一命名写入" $scoreArgs | 自动 |
| 四 探活 | :284 | tools\model_probe.py --timeout 45 --sleep 0.5 -Soft | 自动 |
| 四 探活消费闸 | :286-305 | $probeOut = Join-Path $env:USERPROFILE ".zcode\v2\model_probe.json"；:300 if ($probeAll -gt 0 -and ($probeOk * 2 -ge $probeAll)) { $probeArgs = @("--probe-file", $probeOut) } | 自动，过半才采信 |
| 四 二轮+检查 | :306-328 | $scoreArgs2 = $scoreArgs + $probeArgs；:311-313 $checkArgs = @("tools\model_alias.py", "--check", "--arena") + 同 --scores/--probe-file；:319-320 有漂移则 Invoke-Py "统一命名二轮" $scoreArgs2 + 漂移复查 | 自动，最多收敛两轮 |
| 四 人工卡点 | :322 | Say "复查仍有漂移，需要人工看" | 人工 |
| 四 DSH 投影 | :340-346 | tools\dsh_sync.py --check；不一致则 --apply | 自动 |
| 五 报告 | :350-354 | -NoPush → tools\sync_report.py --write；否则 --write --push | 自动（含 git push 分支；本轮取证未执行） |
| 收尾 | :371-379 | Show-SyncToast（Windows Toast 通知）；if ($script:Fail -gt 0) { exit 1 } else { exit 0 } | 自动 |

:279-283 顺序约束原文：「必须放在第一轮 apply 之后：本轮新补进配置的型号（如 cn:hy4std）此时才有探测记录，否则会被当成 "not probed" 直接跳过。」
:308-310 假漂移原文：「--check 必须和 --apply 用同一组参数（--arena/--scores/--probe-file）。只用 --check 的话，arena 把 MiMo-2.6-Flash、Space-Bunny 提到主力这件事会被当成漂移，每天都要二轮重写、复查看起来仍「有漂移」，实际是参数不对称。」
:116-117：Invoke-Py 里 -Soft 的非 0 退出属预期分支、不计入 $script:Fail。

## 3. 自动发现与建档（已确认部分）

### tools\model_alias.py（共 2134 行）：条目来源三路
- :1041-1042 原文：「条目列表只来自 provider_config 的 personalModelIds（见 inventory）与池子文件，所以某型号一旦因为价格闸被裁出配置，第二天就再也不会被考虑 —— 白名单写了等于没写。」
- :1080：for raw in config.get("personalModelIds") or []:（inventory，:1067-1100）；:1164 同形态（另一处收集函数）。键含 proxy：:1091 key = (hop["channel"], hop["upstream"], hop["protocol"], str(hop.get("proxy") or ""))。
- :1038-1064 whitelist_items(order)：把白名单里点名、但当前配置里已经没有的型号补成候选条目，:1056 item["whitelisted"] = True，:1060-1062 仅显式渠道前缀才去重。:1769 for item in whitelist_items(MAIN_ORDER + LOW_ORDER): 是调用点。
- 池子：:1297「集合体定义：每个池子是一条按顺序试的长链路。文件不存在就跳过。」；:1785-1786 pool_file = Path(args.pools).expanduser() if args.pools else POOLS_FILE / pool_rows = [] if args.no_pools else pool_entries(load_pools(pool_file), args.slot)。
- 白名单本身是人工常量：:146-163 LOW_ORDER = [...]（12 条人工点名），:164 LOW_PICKS = set(LOW_ORDER)；:289-292 MODEL_META 人工补 contextWindow / supportsToolCall 等元数据。
- :2028："personalModelIds": ids, —— 生成器最终把结果写回 personalModelIds（闭环）。

### providers\opencode-go\ops\go_model_sync.py（共 924 行）
- :15-16：「每天跑一次，检测 Go 套餐是否新增模型，对符合收录标准的模型自动写进 ZCode 的 provider_config.json」。
- :18-22 四数据源必须取并集：/zen/go/v1/models、/v2/docs/console/go/、/v2/docs/console/models、provider_config.json 里已配置的模型。
- :24-28 硬门槛：未弃用（410/弃用日期表）、三协议至少一种 200、401 一律不收（workspace 隐私/凭据问题，脚本解决不了）、输出单价 ≤ MAX_OUTPUT_PRICE=1.60（:98）、「价格未知…只报候选，不自动收录」。
- :34-35 人工卡点原文：「主力组是人工精选，不自动进。」「备用组是人工指定（BACKUP_MODEL_IDS），按性价比 < 1 选，不按价格自动进。」:108 BACKUP_MODEL_IDS = {"minimax-m3"}。
- :84-91「去留只看上游清单，不再发探测请求」，历史教训：出口 IP 影响探测（中国 IP 直连 403 / 机场 200），一次探测决定去留会「今天删、明天加」。:82 PRUNE_GUARD_RATIO = 0.34（删超比例只告警不落盘，强删需 --force-prune）。
- :7-10 自述这是 OpenCode-Go 侧接入器，不是通用框架：「接别的供应商时照同样的结构另写一份」→ 新上游接入=人工写新脚本。
- :388 http(CATALOG_API, headers={"Authorization": "Bearer " + key})：控制台目录需要 apiKey，脚本只消费已有凭据（此处仅引用变量名，未取真值）。

### tools\model_score.py（共 186 行）
- :54-55 DEFAULT_ARENA = ~/.zcode/v2/arena-main.json / DEFAULT_OUT = ~/.zcode/v2/model-scores.json；:56-57 BASELINE_MODEL = "deepseek-v4.1-flash" / DEFAULT_BASELINE_PRICE = 0.11。
- :106-113 折算：intel = round(score / base_score * 100, 1)、price_idx = round(price / base_price * 100, 1)、value = round(intel / price_idx, 2)；:112 免费模型 value = None。
- :113 键 f"{channel}|{upstream}"，与 model_alias.py:461 scores.get(f"{hop['channel']}|{hop['upstream']}") 对齐。
- :160-162 无可用分数 return 1（对应 sync-models.ps1:270-272 降级为不带 --scores）；:179-181 原子替换 tmp.replace(path)。

### tools\arena_leaderboard.py
- :56 DEFAULT_PROBE = ~/.zcode/v2/model_probe.json；:284 --probe-file 参数；:378-380 probe = Path(args.probe_file).expanduser() / command += ["--probe-file", str(probe)]（榜单刷新还会把 probe-file 传给下游）。完整刷新链路待补读（下一步）。

## 4. 自动探活（已确认）

### tools\model_probe.py（共 273 行）
- 输入：:46 DEFAULT_OUT = ~/.zcode/v2/model_probe.json；:47 ALIAS = ~/.zcode/v2/model-alias-map.json；:52-58 config_path() 优先 ZCODE_PERSONAL_PROVIDER_CONFIG_FILE 环境变量，否则 ~/.zcode/v2/provider_config.json。
- :48-49 PROVIDERS = ("opencode-go-chat", "opencode-go-chat-free", "opencode-go-chat-fast", "opencode-go-chat-slow") —— 只探这四个 provider id；:85 for model in (rule.get("config") or {}).get("personalModelIds") or []:。
- 请求：:100 --base-url http://127.0.0.1:7871/v1；:129 urllib.request.Request("http://127.0.0.1:7871/v1/chat/completions", ...) —— 经统一路由，依赖 zgate 在线；:93-110 effective_body 调 node providers/workbuddy/zcode_effective_body.js 还原真实 body。
- 输出状态词 :10-16：ok / fallback / queued / rate_limited / blocked / unavailable / timeout / error；:143-161 classify() 逐条映射。
- :237-254 每条记录写 status/http/ms/detail/resp_model/quota_model/credit/provider/body_keys/ever_ok/ok_at/checked_at；:248 ever_ok 跨轮保留；:250-253 注释：「model_alias._fresh_probe 按 checked_at 判新鲜度。之前只写 ok_at，非 ok 的记录没有时间戳 → 整份结果一律被当「未知」，下架的型号永远删不掉」；:256 每探一条就 out_path.write_text(...)（增量落盘）。
- :14-16 自述：「ever_ok is preserved across runs. tools/model_alias.py --probe-file keeps a previously working model through a transient queue/timeout and removes a model that has never answered.」

### tools\model_alias.py 消费侧
- :1717 parser.add_argument("--probe-file", ...)；:1897-1898 if args.probe_file: / probe_path = Path(args.probe_file).expanduser()；:1932 skipped.append(f"{row['new_id']} (probe {status or 'not probed'})")（未探测=跳过，不误删）。
- 顺序约束（sync-models.ps1:279-283）与过半采信闸（:300）见 §2。

## 5. 自动排序/评分（已确认）

- :169 VENDOR_QUOTA = 2；:166-168 注释「每厂商在省钱组最多保留几个代表（用户 2026-11-06 口径：每家公司 1–2 个特色型号）」；:148「同厂商仍受 VENDOR_QUOTA=2 约束」。裁剪实现 :1459 """每厂商最多留 VENDOR_QUOTA 个省钱组代表，返回要裁掉的那批 entry id。、:1486 if len(rows) <= VENDOR_QUOTA:、:1489 for _, _, entry_id in rows[VENDOR_QUOTA:]:、:1491 report.append(f"{vendor} {len(rows)}→{VENDOR_QUOTA}")（精确实现待补读）。
- 只降不升：:469-478 pick_scores_dropped docstring 原文「只降不升：分数只能用来裁，不能把没写进白名单的型号提拔进省钱组 —— 那会绕过人工名单，也会让每日同步在分数抖动时反复改名」；且「只动人工白名单命中的条目，主力/免费/自动补位一律不动」「没有分数的条目保持原状」「低于门槛才裁」。:175-177 SCORE_MIN_INTEL = 85.0 / SCORE_MIN_VALUE = 1.0；:494 weak = intel < SCORE_MIN_INTEL or (value is not None and float(value) < SCORE_MIN_VALUE)。
- 缺价可见性：:529-534 _UNPRICED / _UNPRICED_HOPS 定义，:531-533 注释「逐跳明细：只报渠道计数时，「名单点名的某一跳查不到价」和「价格源整体缺失」长得一模一样…Qwen-3.8-Max 就是这样丢掉 OC 兜底跳的」；:1201-1202 统计写入；:1970-1979 报告输出（:1974 shown = _UNPRICED_HOPS[:12]、:1977 超过 12 条标总数、:1979 整渠道无价判 dead）——精确行待补读。
- :539 _warn_price_once：价格源不可用必须留痕（静默返回空表会把整个渠道的模型从配置里剔除）。

## 6–8. 待补（下一步读取）

- §6 运行自愈：gateways\zgate\internal\supervisor\supervisor.go（always / tick 5s / backoff 1s→60s / healthy / ApplyConfig 边界「新 child 需重启」）；gateways\zgate\internal\router\*.go 逐跳回落与冷却（coolDurationFor / markCoolingFor / quotaCooldown）。grep 已定位 config.go:30 Policy string `json:"policy"` // always | ondemand、config.go:199 策略校验、supervisor.go:90 同校验、router/quota_test.go:32-42 冷却单测。
- §7 热加载边界：gateways\zgate\internal\alias\alias.go:87 same := m.data != nil && stat.ModTime().Equal(m.mtime) && stat.Size() == m.size、:102 m.mtime = stat.ModTime()（每请求比对）；main.go:345-356 reload() → POST /admin/reload；main.go:107「zgate reload 让运行中的实例热加载 zgate.json（策略/空闲/窗口）」；supervisor.go:473 待核。
- §8 自动换版：tools\zgate-lifecycle\ 九脚本（glob 真实输出：restart-zgate.cmd、ensure-zgate.ps1、launch-zgate.vbs、start-zgate-nw.ps1、ensure-zgate.vbs、swap-zgate.ps1、start-zgate.bat、install-lifecycle.ps1、deploy-zgate.ps1）+ gateways\zgate\build.py --candidate + restart-zgate.cmd + deploy-zgate.ps1；AGENTS.md:§6 原文（改完 Go 代码后 agent 自动执行 tools/zgate-lifecycle/restart-zgate.cmd；POST /admin/reload 只热加载 zgate.json 的策略/空闲/窗口，指向 gateways/zgate/internal/supervisor/supervisor.go:473；严禁 Start-Process/cmd /c 直接拉起 zgate）。

## 9. 环节 / 触发方式 / 自动? / 证据 / 卡点（初稿表）

| 环节 | 触发方式 | 自动? | 证据（真实路径:行号 + 实况） | 卡点 |
|---|---|---|---|---|
| 每日同步触发 | Windows 计划任务 Daily 12:00 | 自动 | Get-ScheduledTaskInfo: ModelBus 模型同步 DaysInterval=1 / LastRunTime=11/09/2026 12:00:01 / Result=0 / Next=11/10/2026 12:00:00 | 需 Windows 登录会话/开机；任务本身需人工首次注册 |
| 网关拉起 | LogonTrigger（登录一次） | 自动（一次性） | ModelBus-zgate-hidden MSFT_TaskLogonTrigger UserId 已绑定 / Last=11/09/2026 16:33:08 / Result=0 | 换机/换用户需人工重注册 |
| 网关兜底 | TimeTrigger 每 PT1M | 自动 | ModelBus-zgate-watchdog Repetition.Interval=PT1M / Last=17:09:01 / Next=17:10:00 / Result=0 | 只兜底「进程在不在」，不管配置漂移 |
| Go 套餐发现建档 | 每日流水线第 :211 步 | 半自动 | go_model_sync.py:18-28 四源并集+硬门槛；:34-35 主力/备用组人工 | 401（凭据/workspace）、价格未知只报候选、PRUNE_GUARD_RATIO=0.34 强删需 --force-prune |
| WorkBuddy 同步 | :226-227 | 半自动 | --max-rate 0.3 --apply 自动；:219 从 config.json 读 api_key 入 WB_GATEWAY_KEY | 凭据首次注入人工 |
| Qoder 同步 | :234-252 | 自动 | 端口探测 +Start-Process 拉起 8790 代理 + Wait-Port 90 | 代理脚本缺失则 Say "找不到 start-qoder-proxy.bat"（:245） |
| 榜单刷新 | :262 --refresh --force --write | 自动（可降级） | -Soft；:263-265 失败沿用旧候选 | 上游榜单接口不可用时静默沿用旧数据 |
| 分数折算 | :269 --write --quiet | 自动（可降级） | model_score.py:106-113,179-181 | 无可用分数 return 1 → 本轮不带 --scores |
| 统一命名首轮 apply | :274-276 | 自动 | --slot auto --apply --arena [--scores] | 白名单 LOW_ORDER / MAIN_IDS 人工维护 |
| 分组/配额/评分 | 生成器内部 | 半自动 | VENDOR_QUOTA=2（:169）、pick_scores_dropped 只降不升（:469-478） | 分数只能裁不能提拔；人工名单不变 |
| 探活 | :284 | 自动 | model_probe.py:85,129,237-256；依赖 7871 路由在线 | 网关挂了 → 大面积失败 → :300 过半闸不采信（防误删） |
| 探活结果消费（二轮 apply） | :300-320 | 自动（条件触发） | $probeOk*2 -ge $probeAll 才加 --probe-file | 两轮 apply 串行依赖：首轮 apply 必须先跑才有探测记录 |
| 漂移检查 | :311-320 | 自动 | --check 与 --apply 同参（--arena/--scores/--probe-file） | 参数不对称 → 假漂移；复查仍漂移 :322 需要人工看 |
| DSH 投影 | :340-346 | 自动 | dsh_sync.py --check 不一致则 --apply | — |
| 报告/通知 | :350-377 | 自动 | sync_report.py --write [--push] + Toast | --push 分支会 git push（本轮取证未执行） |
| 运行自愈（子进程） | supervisor tick | 自动（待补精确行） | config.go:30 always|ondemand | 新 child 需重启（ApplyConfig 边界，待补） |
| 逐跳回落/冷却 | 每请求 | 自动（待补精确行） | router/quota_test.go:32-42 quotaCooldown | 地区 403 的 hop.proxy 配置人工（egress.go:10-14 待补） |
| 热加载 | 每请求 ModTime / /admin/reload | 自动（有边界） | alias.go:87、main.go:345-356 | zgate.json 仅策略/空闲/窗口；exe/端口启动期固定（待补 supervisor.go:473） |
| 换版（改 Go 代码后） | restart-zgate.cmd | 半自动（待补） | AGENTS.md §6 + 九脚本（待读） | 候选回滚触发条件、受控重启需人工确认（待补） |

## 10. 仍需人工的卡点（初稿清单）

1. 凭据首次注入：WB_GATEWAY_KEY/api_key、go_model_sync.py:388 的 Bearer key、OPENCODE_GO_KEY 等均由人配置；脚本只消费不产生（sync-models.ps1:215-224、go_model_sync.py:26 401 一律不收）。
2. 人工名单：MAIN_ORDER / LOW_ORDER / BACKUP_MODEL_IDS / MODEL_META 手工维护（model_alias.py:146-163,289-292、go_model_sync.py:34-35,108）。
3. 新上游接入：go_model_sync.py:7-10 明确「接别的供应商时照同样的结构另写一份」= 人工写接入器。
4. 复查仍漂移：sync-models.ps1:322 需要人工看。
5. 强删保护：--force-prune 需人工显式加（go_model_sync.py:80-82）。
6. 换 Go 代码后换二进制：POST /admin/reload 只热加载策略/空闲/窗口（AGENTS.md §6）；换版链与候选回滚触发条件待补读。
7. 地区 403 的 proxy：hop.proxy 来自 alias map / 池子定义，需人工配置出口（egress.go:10-14、model_alias.py:1091 待补精确证据）。

## 11. 未决疑问（待补证据后收敛）

- Q1：supervisor.go 的 tick 是否确为 5s、backoff 是否确为 1s→60s、healthy 判据与 ApplyConfig 对「新 child」的精确边界（supervisor.go:473 原文）。
- Q2：router 逐跳回落顺序、coolDurationFor 的 5min / 一天量级分支、hop.proxy 地区 403 的配置落点。
- Q3：arena_leaderboard.py --refresh --force --write 的完整刷新链路与 --probe-file 传递目的。
- Q4：tools\zgate-lifecycle 九脚本的候选→停→备份→替换→schtasks→health→回滚逐步实况；build.py --candidate 参数；deploy-zgate.ps1 回滚触发条件。
- Q5：文档自述与源码/运行态的冲突点（例如 docs/ 若写「全自动」而 go_model_sync.py:34-35 写「人工精选」），逐条明确指出。
- Q6：sync-models.ps1:353 的 --push 与「本轮禁止 git push」的边界——脚本内有该分支，本轮取证未执行，不算违规。


## lead 验收收口（2026-11-09 17:23，独立复现接管）

### 补齐初稿「待补」6 项
1) supervisor.go：loop(354) ticker 5*time.Second；tick(375) forced = policy==always || inAnyWindow(388)；空闲回收(416)；Ensure 失败 nextTry = backoff(failCount)(423-427)；backoff(437) 1s→2s→4s…capped 60s；healthy(460)；ApplyConfig(475) 注释(473-475) 原文 "New children need a restart (the executable and port layout is boot-time only)."。→ 子进程自愈/启停全自动，新增 child 的 exe 与端口布局启动期固定，必须重启 zgate。
2) 逐跳回落：router.go attemptChain(685-822) 逐跳 cooling(hop) 跳过(694-698)、key 空跳过(699-704)、prepare 失败跳过(705-709)、桥接跳 transportFailed 重试一次(743-751) + retryBridgeOn429(752) + hopFatal 冷却回落(753-761) + regionBlocked&&proxyTwinAfter 冷却 regionCooldown(766-770)、chat 跳 doForwardWith(786-821) 内传输层重试一次(548-557) + 429 退避重试一次(578-587)；冷却常量 45-78：hopCooldown 30min / rateLimitCooldown 45s / timeoutCooldown 5min / regionCooldown 30min / quotaCooldown 24h；hopKey(89)=Channel|Upstream|Proxy 使直连/机场孪生互不干扰。
3) 两个热加载边界分开：alias/alias.go Reload()(79) 用 os.Stat ModTime+Size 判定，serveHTTP(280) 每请求调用 → alias map 写入即自动生效；router.go reload()(963-986) 是 POST /admin/reload 的手动热加载，config.Load + keys.Load + sup.ApplyConfig + setRuntime + aliases.Reload，返回 note「监听地址、新增子进程与 alias map 路径仍需重启 zgate；配置、上游 base 与 key 已热加载」。
4) 改 Go 代码自动换版（本会话新能力）：gateways/zgate/build.py 新增 def build_candidate() -> int 编到 zgate.candidate.exe 不覆盖运行中 exe，main() 分支 --cross-check → --candidate → --check → build_native()；tools/zgate-lifecycle/deploy-zgate.ps1 九步 = build.py --candidate → Disable-ScheduledTask ModelBus-zgate-watchdog → Stop-Process zgate → 备份 .bak-deploy-<stamp> → Move-Item 候选到 zgate.exe → schtasks /run /tn ModelBus-zgate-hidden → /health 轮询 40 次 → 恢复 watchdog；catch 回滚备份并再次 schtasks 拉起。入口 tools/zgate-lifecycle/restart-zgate.cmd；项目 AGENTS.md §6 已写「改完 gateways/zgate/ 下 Go 代码后 agent 自动执行 restart-zgate.cmd，不再要求用户手动重启」。实测换版 16:33 成功：zgate pid=30164 ppid=29892 /health 200、hidden LastRun 16:33:08 Result=0、watchdog LastRun 17:09:01 Result=0。
5) ondemand 三条路径运行态验证：17:17:30 请求 Qwen-3.8-Max 触发 qoder（17:17:33 就绪 pid=5884，3 秒）；17:19:40 请求 Gemini-3.6-Flash 触发 cliproxyapi（就绪 pid=5740，zgate.json 里它 windows=[] 从不时间窗自启、纯 ondemand）；workbuddy pid=30920 常驻。/health 探测后三者 state=running / last_error="" / policy=ondemand，空闲 300s 后 tick(416) 自动回收，可逆。内存实测 zgate 30.8 + wb2api 33.2 = 64.0 MB（拉起前）。
6) 冷却/回落运行态：/health cooling 0→1→2；zgate.log 命中 2915 行，含 17:09-17:10 连续 "[router] OC|beam-free| 冷却中，跳过" 与 17:19:45 "[router] QN|qiniu/conatus-free| 429，退避 700ms 后重试同一跳"。

### 新增硬缺口：峰谷多次自动切换未落地
docs/MODEL-ALIAS.md:375 承诺「自动切换的做法（北京时间）：每天 08:00 / 22:00，外加工作日 09:00 / 12:00 / 14:00 / 18:00（OC 峰谷边界）各跑一次」并给 :379-380 两条命令。Get-ScheduledTask 全量触发器实况（exit=0，25 行，筛 ModelBus|zgate|sync）：ModelBus 模型同步 = MSFT_TaskDailyTrigger StartBoundary 2026-11-04T12:00:00（无 Repetition）；ModelBus-zgate-hidden = MSFT_TaskLogonTrigger；ModelBus-zgate-watchdog = MSFT_TaskTimeTrigger 2026-11-06T22:14:00 Repetition.Interval=PT1M。**没有 08:00 / 22:00 / 09:00 / 14:00 / 18:00 任何一条同步任务** → 峰谷边界的多次重算未落地，只有 12:00 一次会按 --slot auto 顺带判一次当前时段。

### 可见性缺口
12:01 报告说 18 个模型（主力5/免费5/省钱8）且失败段数=0，但当前 alias map=22、provider_config personalModelIds=5/5/12=22；产物 mtime 13:58 晚于报告 12:01，cordis.patch.yml 15:01。→ 报告与现行产物不同步，缺「当前生效清单」单一真值视图；不判同步失败。

### 自动性终判定：分层达标，闭环到「配置级」，未闭环到「供应商级」
全自动：模型清单/价格/榜单/评分/探活/分组/alias map 生成/DSH 投影（Daily 12:00，最近一轮失败段数=0）；网关登录自启 + PT1M watchdog + 崩溃 5s 自愈 + 空闲回收 + 请求触发 ondemand 拉起；alias map 每请求 mtime 热加载；逐跳 429/403/5xx 回落与冷却；改 Go 代码经 restart-zgate.cmd 自动编译候选 + 受控换版。
仍需人工：首次凭据注入（env / .env.local / provider_config）；新上游接入器（go_model_sync.py:7-10 明写「不是通用框架，接别的供应商另写一份」）；主力组人工精选与备用组人工指定（:34-35）；漂移复查仍不一致（sync-models.ps1:322）；/admin/reload 手动 POST；新增 child / 改端口 / 换 alias map 路径必须重启；峰谷多次切换任务未落地；报告与现行产物缺单一真值视图。
