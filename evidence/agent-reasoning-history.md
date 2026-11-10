# ModelBus 推理等级 / 思考 / 流式：历史改动闭环审计

> **一句话**：网关侧（守卫四次修复 + forceEffort）与「流式」两条线已真落地并用线上二进制 + 线上日志 + 活体探针闭环；「推理等级」闭环但有 4 个模型空档位与 1 个已知副作用未处置；**展示层（ui-chat）改动是悬空的 —— 改过又被 profile 侧重写回退，当前不生效**；且审计期间（14:33:55）有并行会话把 `reasoningGuard.mode` 由 `auto` 改回 `models` 并已热加载，守卫现行作用域缩到 2 个模型，与 CHANGELOG 口径不一致。

审计口径：只读，唯一写物为本分片。所有结论带 `文件:行号` 或真实命令输出。

---

## 0. 方法与环境（可复现）

- 本会话 `ops_bash` 不可用（`EXECUTOR_UNAVAILABLE: Niubash preparation failed ... link awk.exe ... dsh-ops 0.5.1 并发 bug`），全部命令改用 `run_code` 内 `node:child_process.spawnSync(shell:true)` 执行，等价于 git-bash 命令行。
- 该 shell 是 **cmd.exe**，不是 bash：`ls / grep / sed` 不存在，文件读取一律走 `node:fs`。
- Go 不在默认 PATH：必须显式 `PATH=F:\Program Files\Go\bin;...` + `GOCACHE=~/AppData/Local/Temp/gocache-audit`，否则报 `build cache is required, but could not be located`。
- 中文输出需 `chcp 65001` + `PYTHONIOENCODING=utf-8`。

---

## 1. 时间线（三条线合并、按时间正序）

| 日期 | 改动 | 声称效果 | 是否已验证（证据） | 当前状态 |
|---|---|---|---|---|
| 2026-10-29 | 桥接全链路流式：桥接器按 `stream:true` 请求上游、边收边转（`CHANGELOG.md:465-476`） | Conatus 首块从 12.06s 降到近原生；新增 3 条桥接流式用例 | 有：`gateways/zgate/internal/router/stream_test.go` 现存且本次实跑 `TestBridgeStreamsOnNonTailHop / TestBridgeRegionBlockedFallsBackWithStream / TestBridgeNoFallbackAfterStreamStarted` 全 PASS | **闭环** |
| 2026-11-03 | 推理等级补齐：`build_model_rule()` 按上游 `supported_efforts` 写 `optionSpecs.reasoningLevel.values`；`qoder_zcode_sync.py` / `go_model_sync.py` 同口径；`pickLevel()` 改默认档 = `values.at(-1)`（`PROGRESS.md:1984-2045`；`providers/workbuddy/zcode_effective_body.js:248-270`） | ListModels 从 8/18 → 10/18 有真档位；`cn:hy3` low/high 均 200 | 有：本机 `~/.zcode/v2/provider_config.json` 现存 **14 处** `reasoningLevel`；`HY3.values=["low","high"]`；实测 `node providers/workbuddy/zcode_effective_body.js HY3 HY3-X` exit 0，输出 `level:"high"`、`reasoning_effort:"high"`（与 `PROGRESS.md:2026-2029` 一致） | **闭环**（含 1 项未处置副作用，见 §3-C） |
| 2026-11-06 | 桥接流式不再限制在链尾跳 + `DefaultIdleNonStream`（`CHANGELOG.md:245-262`） | Claude-Haiku-5.5 从「ttfb=total、4 条 data 行」变成真流式 | 有：本次实跑 `go test ./internal/router/ -run "Stream|Bridge"` exit 0，`TestBridgeStreamsOnNonTailHop` PASS；**活体**直连 7871 打 Claude-Haiku-5.5 → `{"status":200,"ttfb":1668,"total":2099,"blocks":17}`（历史是 4 块、ttfb≈total） | **闭环** |
| 2026-11-09 | 前端去掉 `Default` 伪档位：给 `dsh-claude-style/lib/client.js` 打六条规则补丁（`PROGRESS.md:2783-2790`） | 选模型自动带 `reasoningEffort`；25/25 夹具，活体 Iceman 89 chunks | 有反证：`node ~/.dsh/tools/patch-claude-style-effort.mjs desktop --check` → **exit 2**，六条锚点 `old=0 new=0`，`RESULT: NEEDS_REVIEW (no write) - unexpected hit pattern` | **悬空（已被 11-10 网关补档替代）** |
| 2026-11-10 上午 | 守卫首版：探首包、加密分流透明重抽（`CHANGELOG.md:32-38`；`PROGRESS.md:2835-2841`） | 重抽同一跳，上限 3 次 | 有：`reasoning_guard_test.go` 7 项；但同条自述「线上 7871 仍是旧二进制」→ 首版上过线后被证白抽（沿用原 headers + keep-alive 落回同一加密后端，`CHANGELOG.md:45`） | **已被二次修复取代** |
| 2026-11-10 13:2x | 二次修复：`req.Close=true` + 会话头 `#r<N>-<rand>`、`mode:auto`、`streamIdleHeartbeatSec=15`、事件流 `Del("Content-Length")`、`giveUpAfter/giveUpForSeconds` 学习表、日志补模型名（`CHANGELOG.md:41-50`；`PROGRESS.md:2845-2861`） | 12 项 router 测试；12:59 换版 PID 27360；真机 13:05:28 命中 | 有：二进制备份链 `zgate.exe.bak-deploy-20261110-132003`（10,548,736 B）已含 `换连接+换会话重抽` 串；线上日志现存 `换连接+换会话重抽` **36 条**、`达上限放行最后一次` 6 条 | **闭环**（机制仍在现行二进制）；但 `mode` 已于 14:33:55 被改回 `models`，见 §7 |
| 2026-11-10 13:5x | 三次修复：`forceEffort` / `forceEffortModels`，客户端没带档位时网关补 `reasoning_effort:"high"`（`CHANGELOG.md:52-59`；`PROGRESS.md:2866-2874`） | 隔离 17871 两发补档日志 + 226/202 块思考 | 有（活体，本次重做）：不带 `reasoning_effort` 打 `iceman-contributor-free` → `{"status":200,"blocks":198,"thinkChars":931,"firstThinkAt":4729}`；日志同一时刻 `2026-11-10 14:36:18 INFO [router] 客户端未声明思考档位，按配置补 reasoning_effort="high"` | **闭环** |
| 2026-11-10 14:00 | 四次修复：`probeSeconds=15` 探针时限、预算花完直通不探、提示按成因分写、跳过期不滑动续期（`CHANGELOG.md:61-70`；`PROGRESS.md:2911-2935`） | 消除 85 秒空等；隔离实例 1,263ms 拿到明文 | 有：`zgate.exe` mtime **2026-11-10 14:07:45**、10,570,752 B、`sha256 c2755613…c76e9c10`、PID **3264**（14:07:49 起）；二进制含四条新文案（`内没有可判定的思考信号` / `跳过期内，直接放行` / `次探测超时` / `近期思考拿不到明文`），而 13:20 的备份**不含**；线上日志 `跳过期内，直接放行` **358 条**、`换连接+换会话重抽 …1/1`（14:33:52 命中 maxRetries=1 配置） | **闭环**（`PROGRESS.md:2939`「线上仍是旧二进制」已过时） |
| 2026-11-10 上午 | 展示层：`ui-chat` 由 `standard/completion/final` 改 `verbose/next-input/all`，`ui-skin-claude-style` 加 `reasoningDisplay: continuous`（`CHANGELOG.md:34`；`PROGRESS.md:2837`） | 「刷新 GUI 即生效」、思考与过程行不再整轮折叠 | **有反证**：`~/.dsh/profiles/desktop/cordis.patch.yml:20-26` 现为 `transcriptView: compact / collapseTiming: completion / foldedReplies: final`；备份链 `cordis.patch.yml.bak-gemini-devrole-20261110131037:22-26` 曾是 `verbose / next-input`，而 `bak-dshsync-20261110-134823` 起已回到 `compact / completion / final` | **悬空（改动被回退）**；`reasoningDisplay: continuous` 仍生效（`:330`） |
| 2026-11-10 | Gemini 3.8 Flash 并入主力：`optionSpecs.reasoningLevel` 暂不配（`CHANGELOG.md:29`） | 上游 503，思考能力待复测 | 无复测证据；`provider_config.json` 14 条 `reasoningLevel` 里**没有** `Gemini-3.8-Flash` | **悬空（等上游恢复）** |

---

## 2. 门禁真实输出与退出码

命令：`cd /f/Project/ModelBus && python tools/check-project.py --stream-contract 2>&1 | tail -30`（实际经 `chcp 65001` 包一层）

```
EXIT: 0
[OK] 流式准入报告: 15 条全量视图可解析；PASS 11 / WARN 2 / FAIL 0 / SKIP 1 / EXEMPT 1 / RECOVERED 0（模型健康只记录，不阻断提交）
[OK] 流式准入接线: 同步钩子 / --changed / RECOVER_TOKENS / RETRY_STATES / 加密分流识别 / 契约正本 / 索引 七处全在位
[OK] check-project: 2 项通过（语义 / 换行BOM / PS1 / 流式接线）
```

无参 `python tools/check-project.py` 也是 **exit 0**，末行 `[OK] check-project: 8 项通过`（八项含 zgate.json 真值 children=2 / ports=7863,8790 / upstreams=6、`/v1/models` 聚合 + `/health` 段表、13 个脚本换行 BOM、7 个 PS1 语法）。**门禁本身不覆盖「思考是否真的看得见」，只覆盖接线与契约解析**——这一点是后面所有悬空项的判断基础。

---

## 3. 悬空项清单（只落代码/文档、无实测证据，或实测与声称相反）

| # | 悬空项 | 证据 | 影响 |
|---|---|---|---|
| A | **展示层 ui-chat 三键被回退**：`verbose/next-input/all` 只活在 2026-11-10 13:10 的备份里，13:48 起回到 `compact/completion/final` | `cordis.patch.yml:20-26`（当前）vs `cordis.patch.yml.bak-gemini-devrole-20261110131037:22-26`（曾为 verbose/next-input）；`bak-dshsync-20261110-134823`、`bak-gemini-merge-20261110-1352`、`bak-autocapture-20261110142500` 全部已是 compact | 「轮次结束后思考与过程行仍整轮折叠」这一声称**当前不成立**；回退机制未定位（候选：宿主/profile 侧对 patch 文件的重写，`tools/dsh_sync.py:300-356` 只重写 `llm-pi-ai` 段，不是它） |
| B | **前端 effort 补丁已失效**：六条锚点全归零，脚本判定 `NEEDS_REVIEW` | `node ~/.dsh/tools/patch-claude-style-effort.mjs desktop --check` → exit 2；`client.js` 全文只剩 3 处 `effort` 字样且均为无关片段 | DSH 侧仍无「逐模型默认档」，每次请求都不带 `reasoning_effort`；**只能靠网关 `forceEffort` 兜住白名单模型**（白名单只有 `Iceman` / `iceman-contributor-free`，其他模型仍无档位） |
| C | **`DeepSeek-4.1-Flash` 默认档被顶到 max**（主力模型思考更久、更贵） | `provider_config.json`：`reasoningLevel.values=["disabled","low","high","max"]` + `pickLevel()` 取 `values.at(-1)`（`zcode_effective_body.js:248-251`）；`PROGRESS.md:2044` 自己登记为待解决 | 已登记但**未处置**；用户侧感受是「主力变慢」 |
| D | **4 个模型 `reasoningLevel` 只有空 map、无 values**：`Conatus` / `Claude-Haiku-5.5` / `Muse-Spark1.3` / `GPT-6-Luna` | `provider_config.json` 中这四条为 `{"map":"{}"}`，其余 10 条都有 `values` | UI 只剩开关、档位发不出去 —— 与 2026-11-03 第八轮「按上游声明补齐」的目标不一致，属该轮未覆盖的残项 |
| E | **Gemini-3.8-Flash 思考能力未复测** | `CHANGELOG.md:29`「上游四次探测全 503，`optionSpecs.reasoningLevel` 暂不配」 | 该模型进主力但档位/思考未定义 |
| F | **`PROGRESS.md:2939` 待办过时**：「线上 7871 仍是旧二进制」 | 实际 `zgate.exe` 14:07:45 已换版、PID 3264、含四次修复全部文案 | 文档口径与事实相反，会误导下一次维护 |
| G | **四次修复的超时分支只有隔离实例证据** | 线上日志 `内没有可判定的思考信号` **0 条**、`次探测超时` **0 条**（二进制里都有这两条文案） | 生产从未触发 `probeSeconds` 超时（加密首帧即时判定、不必等满），属**覆盖缺口而非缺陷**；真出静默时只能依赖单测 `TestProbeReasoningStreamDeadlineTimesOut` |

另：`PROGRESS.md:2926` 列出的 `guardWanted` / `guardInSkip` 确实存在，只是方法形式（`gateways/zgate/internal/router/router.go:1568` `func (s *Server) guardWanted(...)`、`:1581` `func (s *Server) guardInSkip(model string) bool`）；早期按裸函数名 grep 会 0 命中，属检索口径问题，非缺失。

---

## 4. 单测覆盖情况：**有**（本次实跑，非引用）

命令（`cwd=gateways/zgate`，显式 GOCACHE）：

```
go test ./internal/router/ -run "Stream|Bridge" -v -count=1        → exit 0, ok zgate/internal/router 4.646s
go test ./internal/router/ ./internal/config/ -run "Reasoning|Probe|Heartbeat|Guard|Inject"  → exit 0 (router 10.304s / config 0.027s)
```

| 文件 | 测试函数 |
|---|---|
| `internal/router/reasoning_guard_test.go` | `TestProbeReasoningStreamVerdicts`（:111，含明文思考首块 / 正文先于思考 / 加密 detail 兜底 / 只有 role 无法判定）、`TestReasoningGuardPredicates`（:143）、`TestReasoningGuardRedrawsEncryptedOnlyStream`（:174）、`TestReasoningGuardDisabledPassesThrough`（:220）、`TestReasoningGuardMaxRetriesCapsRedraw`（:233）、`TestReasoningGuardSkipsOffEffort`（:250）、`TestReasoningGuardSkipsNonWhitelistedModel`（:267）、`TestReasoningGuardAutoModeCoversUnknownModel`（:286）、`TestReasoningGuardInjectsNoticeOnGiveUp`（:309）、`TestReasoningGuardGivesUpAfterLearned`（:329）、`TestStreamIdleHeartbeatWritesComment`（:348）、`TestHeartbeatSkipsNonStreamResponse`（:380）、`TestGuardGiveUpWithHeartbeatEnabled`（:409）、`TestGuardGiveUpWithContentLengthBody`（:442） |
| `internal/router/reasoning_force_test.go` | `TestInjectThinkingEffort`（:19，七条边界）、`TestReasoningGuardForcesEffortThenRedraws`（:112） |
| `internal/router/reasoning_probe_timeout_test.go` | `TestProbeReasoningStreamDeadlineTimesOut`（:18）、`TestProbeReasoningStreamDeadlinePassesThrough`（:42）、`TestReasoningGuardSilentStreamProbesWithDeadline`（:91）、`TestReasoningGuardSkipWindowPassesThroughFast`（:140）、`TestReasoningGuardSkipWindowExpiresAndReprobes`（:184） |
| `internal/router/stream_test.go` | `TestBridgeStreamsOnNonTailHop`、`TestBridgeRegionBlockedFallsBackWithStream`、`TestBridgeNoFallbackAfterStreamStarted`、`TestBridgeEndpointUnavailable403FallsBackToAirportTwin`、`TestBridgeClient400IsNotRegionBlocked`（本次全部 PASS） |
| `internal/config/config_test.go` | `TestReasoningGuardJSONWiring`、`TestReasoningGuardDefaults`（本次 PASS） |

**推理等级（`reasoningLevel` / `values` 投影）没有 Go 单测，也没有 Python 单测**：`tests/` 只有 6 个文件（`test_dsh_sync_retry_policy.py`、`test_go_sync_list_only.py`、`test_model_alias_hop_order.py`、`test_model_alias_naming.py`、`test_model_alias_price.py`、`test_model_alias_qd_free.py`），无一涉及档位/effort。它的验收方式一直是「`zcode_effective_body.js` 人工比对 + 经 7863 实测 200」——即**弱覆盖**：脚本可执行、值可读，但没有任何自动断言防回退（这正是 D 类残项能长期存在的原因）。

---

## 5. 活体证据汇总（2026-11-10 14:29–14:36，直连 7871）

| 探针 | 请求特征 | 结果 |
|---|---|---|
| `Claude-Haiku-5.5` | `stream:true, max_tokens:60` | 200 / ttfb **1668ms** / total 2099ms / **17 块** / 正文 56 字 → 非链尾跳真流式 |
| `iceman-contributor-free` | `stream:true`，**不带** `reasoning_effort` | 200 / 198 块 / **明文思考 931 字** / 首块思考 4729ms / 正文 0（200 max_tokens 全被思考吃掉）→ `forceEffort` 补档 + 明文回传均成立 |
| `cn:deepseek-v4.1-flash`（DSH 自身流量） | 同上 | `14:33:52 重抽 1/1` → `14:33:54 连续 1 轮没拿到明文，600 秒内跳过守卫` → 之后 358 条「跳过期内直接放行」 |

**反思一条**：`maxGap=4729ms` 说明思考阶段仍有近 5 秒静默，靠 `streamIdleHeartbeatSec=15`（`config.go:105`、`zgate.json:11`）兜着；15 秒阈值对「慢思考」偏宽松，日志里尚未见到自己补心跳的实操证据（`zgate keepalive` 在二进制内有、日志中计数 0）——同属 §3-G 的覆盖缺口。

---

## 6. 与文档口径的三处不一致（需订正）

1. `CHANGELOG.md:34` / `PROGRESS.md:2837`：`ui-chat` 已是 `verbose/next-input/all` —— **与当前 `cordis.patch.yml:23-25` 相反**。
2. `PROGRESS.md:2939`：线上仍是旧二进制 —— **已过时**（14:07 换版）。
3. `docs/TROUBLESHOOTING.md:560-580` §17 与 `docs/MAINTENANCE.md:241` §6 的表述与现行配置一致（`probeSeconds 15` / 明文实测最高 13.5s），**无需改**；`docs/TROUBLESHOOTING.md:541-556` §16.2 的「改 Go 必须换 zgate.exe、`/admin/reload` 只热加载」被本次换版过程再次印证（`zgate.exe` 14:07:45 与 PID 3264 同时刻）。

---

## 7. 审计期间发生的状态漂移（并行会话改动，非本片所为）

| 时间 | 事实 | 证据 |
|---|---|---|
| 2026-11-10 14:33:55 | `gateways/zgate/zgate.json` 的 `reasoningGuard.mode` 由 `auto` 改成 `models`（文件 mtime `2026-11-10T06:33:55Z`，`git diff` 为未提交改动：`-"mode": "auto"` / `+"mode": "models"`） | `git diff -U0 -- gateways/zgate/zgate.json` 输出；当前文件 `reasoningGuard={"enabled":true,"mode":"models","models":["Iceman","iceman-contributor-free"],"maxRetries":1,` `"maxProbeBytes":32768,"probeSeconds":15,"injectNotice":true,"giveUpAfter":1,"giveUpForSeconds":600,"forceEffort":"high","forceEffortModels":["Iceman","iceman-contributor-free"]}` |
| 2026-11-10 14:34:27 | 新配置被热加载，运行中的 PID 3264 已按 `models` 生效 | `zgate.log`：`2026-11-10 14:34:27 INFO 配置已热加载: F:\Project\ModelBus\gateways\zgate\zgate.json（生效 [workbuddy qoder]）` |
| 14:34:26 之后 | `cn:deepseek-v4.1-flash` 的守卫日志归于静默（该模型不在白名单里），此前 14:31–14:34 还有 10 余条「跳过期内直接放行」 | `zgate.log` 14:31:07 → 14:34:26 的 skip 记录序列，14:34:26 为最后一条 |

**含义**：`CHANGELOG.md:48`（二次修复）写「`zgate.json` 已切 auto」已不再成立；守卫现行只覆盖 `Iceman` / `iceman-contributor-free`。`cn:deepseek-v4.1-flash`（今日思考日志的主力来源，364 行）从此不再被探针/重抽/跳过判定（`guardWanted` 在 `router.go:1572` 用 `mode=models` + `Models` 白名单直接返回 false）。**补档不受影响**：`injectThinkingEffort`（`router.go:1347-1357`）只看 `ForceEffort` / `ForceEffortModels`（为空才回落 `Models`），与 `Mode` 无关，它自己也从不在 `forceEffortModels` 里 —— 所以该模型的思考能否看到，回到「上游给什么就是什么」。此项不是代码缺陷，是**运行配置与文档/历史声称的漂移**，需要由 lead 决定是订正文档还是把 `mode` 改回 `auto`（本片只读，未改）。

> 复核方式：`git diff -- gateways/zgate/zgate.json` + `Select-String "配置已热加载" ~/AppData/Local/ZCodeGateway/zgate.log | Select-Object -Last 3`。
