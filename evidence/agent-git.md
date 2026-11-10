# 2026-11-10 ModelBus 改动取证（git 只读分析）

> **一句话**：今天（2026-11-10 00:00–22:40）共 **17 个 commit**、涉及 **70 个去重文件**（122 个文件条目，+14391 / −2612 行），
> 主体是「**Gemini 两条链（catiecli 的 AIS 七跳链 + 哈基米 gemai.cc 福利档）接入后的四轮稳定性收敛**」：
> 先加首块对冲与响应头看门狗，再把判死权交回上游（关本地看门狗），最后补「等头空窗期提前交卷 200 + SSE 心跳」；
> 另有一条并行的「推理档位（reasoningEfforts）继承与漂移守门」以及一串 CI/文档门禁修复。工作区当时还有 5 个已改未提交文件 + 2 个未跟踪测试。

---

## 一、总览

```
今日 commit 数        17   （git log --since="2026-11-10 00:00"）
去重文件数            70   （含 evidence/ 20 篇归档分片、docs/ 14 篇）
文件条目累计         122
累计增删             +14391 / −2612
最早 / 最晚          14:01（96e274d） / 22:08（bfd6b9e）
工作区未提交          5 改 + 2 未跟踪（截至 22:39，可能仍在被其他会话写入）
git stash            空
```

| hash | 时间 | 一句话 | 文件数 | 类型 |
|---|---|---|---|---|
| 96e274d | 14:01 | Gemini-3.8-Flash 经 GM（catiecli）渠道并入主力组 | 17 | 新增能力：渠道接入 |
| 9adde7f | 14:09 | /health 段表改由 keys.Channels 驱动，pre-commit 补 Go/Python 测试 | 5 | 修 bug：CI 本地绿远端红 |
| a81e55c | 14:12 | MODEL-STREAM 正本入库，check-docs 拦「存在但没进仓库」的链接 | 4 | 修 bug：文档门禁 |
| da9a029 | 14:13 | 补同步报告索引，钩子提示未暂存文档改动 | 2 | 补漏：索引 + 钩子 |
| e032924 | 14:18 | 网关侧思考守卫 + 流式准入探针，移除 CLIProxyAPI 镜像 | 24 | 新增能力 + 删第三方 |
| f52450e | 16:27 | Gemini-AIS 七跳降级链与首字对冲（race.go 新建） | 10 | 新增能力：并发对冲 |
| 38b4509 | 16:27 | 流探针四修，补测预算 2048→8192 词元 | 3 | 修 bug：探针工具 |
| 486a955 | 16:29 | 回填第十七轮验收结论与待办 | 1 | 只改文案（PROGRESS） |
| 6771431 | 20:37 | 新增只读控制台设计稿 docs/CONSOLE.md | 2 | 新增文档 |
| 1c42f03 | 20:37 | 接入 HJ 哈基米渠道 + 响应头看门狗 + 静默冷却 | 9 | 新增能力：渠道接入 |
| 58b7ce8 | 20:37 | 哈基米福利 3.8 从 AIS 链拆成独立模型 Gemini-3.8-Flash | 2 | 结构调整：模型分族 |
| ff48352 | 20:37 | 同步 Gemini 两族口径与排障结论（8 篇文档） | 8 | 只改文档 |
| b73f0a2 | 20:37 | 记第二十三轮拆分与两次看门狗修复 | 2 | 只改文案（PROGRESS/CHANGELOG） |
| 4cb0962 | 20:37 | 归档本轮 17 篇子代理取证分片 | 17 | 归档（纯新增文件） |
| 8c9825c | 21:45 | 判死权归上游，HJ/GM 关掉本地看门狗 | 8 | 策略回退：兼容适配 |
| cbac930 | 21:52 | 去掉 MODEL-PROVIDERS 4.11.3 残留旧表头 | 1 | 只改文案 |
| bfd6b9e | 22:08 | 流式请求提前交卷：等响应头期间回 200 + SSE 心跳 | 7 | 新增能力：earlySSE |

---

## 二、按功能面分组

### 2.1 网关路由（`gateways/zgate/internal/router` + `config` + `keys`）—— 今天的主战场

| 提交 | 功能面内做了什么 |
|---|---|
| 96e274d | 新渠道 GM（catiecli 中转）：`upstreams.GM` 默认 base、`geminiEnvFile` 三级取 key、Bearer 覆盖名单补 GM、`/health` 扩段 |
| f52450e | 新建 `race.go`（537 行）：首块对冲编排、抢写端闸门、两张冷却表（真冷却 / 静默分开）、渠道级 `poolDown`/`authFatal` 快速失败、`rankedChain` 按实测首字发车；`config` 新增 `ChannelPolicy`（零值=关=老行为） |
| 1c42f03 | 新渠道 HJ（哈基米 gemai.cc）：Keys/Config/Router 全链路；新增**响应头看门狗**（`errUpstreamSilent`）与**静默冷却**；看门狗窗口支持全局 + 按渠道覆盖 |
| 8c9825c | 方向反转：GM/HJ 的 `headerTimeoutSec` 置 `-1`（不设本地看门狗），GM 只保留 `hedgeAfterMs 18s` 对冲；全局兜底 12s→45s |
| bfd6b9e | 新建 `early_sse.go`（293 行）：等上游响应头的空窗期先回 200 + `text/event-stream`，每 10s 补 `: zgate keepalive`；上游最终失败改写成流内 error 事件，不再回「客户端早已放弃的 502」 |

### 2.2 模型链与 provider 配置（`tools/model_alias.py` + `zgate.json` + `check-project.py`）

- **f52450e**：7 个 `ais-gemini-*` id 合并成一条显示名 `Gemini-AIS` 的七跳链，新增 `HOP_PRIORITY` 压跳序；`ChannelPolicy` 只对 GM 开（soft 90 / silence 20 / backoff −1 / firstBlock 4000 / hedge 500 / parallel 2 / authFail 24）。
- **96e274d**：新增 `GM_BASE`/`GM_PRICES`/`CHANNEL_RANK["GM"]=1`，`MAIN_ORDER` 加 `chat:gem:ais-gemini-3.8-flash`，补 `gem:` 前缀。
- **58b7ce8**：哈基米福利档**摘出 AIS 链**，独立成单跳模型 `Gemini-3.8-Flash`（ABBR 新增、MAIN_ORDER 位置压到 `chat:gem:*` 之前、`HOP_PRIORITY` 删 HJ 项、`NAME_RENAMES` 清空避同名 legacy 脏映射）。
- **1c42f03**：`channelPolicy.HJ` 进入 `zgate.json`；`check-project.py` 增「渠道四登记点一致性」闸（`upstreams` / `channelPolicy` / `keys.Channels` / Set 字段）。
- **8c9825c**：`zgate.json` 的 GM 收敛为 `{headerTimeoutSec:-1, firstBlockMs:0, silenceCooldownSeconds:0, hedgeAfterMs:18000, softCooldownSeconds:60}`，HJ 收敛为只剩 `{headerTimeoutSec:-1}`。

### 2.3 健康检查与看门狗

- **9adde7f**：`/health` 的六段硬编码改为遍历 `keys.Channels` + `healthSegmentName()`，测试改名成 `TestHealthHasEveryChannelSegmentWithState` 并遍历同一份清单（根因：CI 断言过时的 `cliproxyapi` 段，本地改过的测试没进提交）。
- **1c42f03**：新增「响应头看门狗」`doForward` + `errUpstreamSilent`，命中沉默按渠道打静默冷却；`/health` 的 `race` 段暴露每跳首块耗时与判定。
- **8c9825c**：看门狗在 GM/HJ 上整体关掉（判死权归上游），并用统计证明：GM 当晚判死 125 次（沉默 79 + 首块 46），上游真说过 503 的仅 7 次（5.3%）；HJ 判死 32 次，一大半与 502 同秒。
- **bfd6b9e**：`earlyCommitMs`（缺省 8000ms）+ `earlyKeepaliveSec`（缺省 10s），把「本地不判死但客户端会判死」的洞补上。

### 2.4 推理档位 / 思考守卫

- **e032924**：`injectThinkingEffort` 按白名单补档位、reasoning guard 对加密思考流探测→重绘→降级通知（maxRetries / skip window / 结论缓存）；新增四组测试；同时删除 `third-party/cliproxyapi/`（6 文件 2191 行）并从 `tools/model_probe.py` 去掉 CP 分支；`supervisor.stopChild` 修 Windows 日志句柄占用。
- **38b4509 / 未提交**：`tools/model_stream_check.py` 四修 + 未提交的 `EFFORT_CHANNELS`/`drifted_efforts()` 档位继承与漂移守门。

### 2.5 脚本与门禁

| 提交 | 脚本侧改动 |
|---|---|
| 9adde7f | `.githooks/pre-commit` 补 `go build/test`（暂存含 .go）与 `python unittest`；gofmt/go 定位 PATH → `$GOROOT/bin`，找不到 WARN 不静默跳过 |
| a81e55c | `tools/check-docs.py` 新增 `tracked_paths()`：链接目标存在但未跟踪 / 被 exclude 直接 FAIL |
| da9a029 | `docs/reports/README.md` 补索引；pre-commit 提示未暂存文档改动 |
| 1c42f03 / 96e274d | `tools/check-project.py`：Bearer needle、health 段循环、渠道四登记点一致性、`7 个 upstreams` 新口径（旧「6 个」判死） |
| 38b4509 | `tools/model_stream_check.py`：`RECOVER_TOKENS` 2048→8192、`--changed` 基准改 fingerprint、识别「200 + error 帧」的排队（10605 / RESOURCE_LIMIT）、增量模式补 SKIP 占位行 |

### 2.6 文档

14 篇 `docs/*` 改动 + `README.md` + `CHANGELOG.md`：MODEL-PROVIDERS（§4.11 Gemini 接入正本、§4.11.3 参数表按渠道重写）、TROUBLESHOOTING（§18.4 判死权归上游）、PITFALLS（§42 第五轮）、MODEL-STREAM（新建正本）、CONSOLE（新建只读控制台设计稿）、ARCHITECTURE/MAINTENANCE/TOOLS/ZGATE-LIFECYCLE 的渠道数与流程口径。

### 2.7 测试

新增/改写：`race_test.go`（六项对冲）、`router_test.go`（health 段遍历、静默冷却、headerTimeout 按渠道）、`early_sse_test.go`（writer 三条 + 网关级三条）、`reasoning_*_test.go`（三组）、`config_test.go`（ReasoningGuard / ChannelPolicy）、`tests/test_model_alias_hop_order.py`（跳序与七跳链）。工作区另有 2 个未跟踪测试（见第五节）。

---

## 三、Commit 明细

### 96e274d 14:01 — Gemini-3.8-Flash 经 GM 渠道并入主力组（17 文件，+1478/−217）
- **功能面**：网关路由 + 模型链 + 文档 + 测试。
- **本质**：新增渠道能力。`keys.Set` 加 `GM` 与 `catiecli.sukaka.top` 正则、`Load` 支持 `geminiEnvFile` 三级取 key；`config` 加 `GeminiEnvFile` 与 `upstreams.GM`；`/health` 扩到六段；`applyHeaders` 的 Authorization 覆盖名单补 GM（漏掉会把空 Bearer 透传被回 401）。
- **验收**：go build exit 0、go test 除 supervisor Windows TempDir 既有用例全过、unittest 56 项 OK、三个 check 脚本 exit 0；生产 `--apply` 后主力 2 条。**未定论**：上游四次探测全 503，`optionSpecs.reasoningLevel` 暂不配。

### 9adde7f 14:09 — /health 段表改由 keys.Channels 驱动（5 文件，+212/−17）
- **本质**：修 bug（CI 红）。根因：`TestHealthHasSixUpstreamsWithState` 断言已删除的 `cliproxyapi` 段，而本地改过的测试没进提交 → 本地绿、远端红，连续两次推送失败邮件。
- `keys.go` 新增 `var Channels` 作为唯一登记点；`router.go` health 遍历它；`check-project.py` 门禁从段名字面量改为「渠道链路在位」。

### a81e55c 14:12 — MODEL-STREAM 正本入库（4 文件，+285/−2）
- **本质**：修 bug（第二处「本地绿、远端红」）。96e274d 写了 8 处指向 `docs/MODEL-STREAM.md` 的链接，文件本身没进版本库；CHANGELOG 另有两处链到被 exclude 的 `evidence/agent-gemini-*.md`。
- `check-docs.py` 加 `tracked_paths()`，把「存在但不会进仓库」挡在提交前。

### da9a029 14:13 — 补同步报告索引（2 文件，+10）
- 小补漏：`docs/reports/README.md` 一条索引 + pre-commit 提示未暂存文档。

### e032924 14:18 — 思考守卫 + 流式准入探针，移除 CLIProxyAPI（24 文件，+1826/−2191）
- **功能面**：网关路由（reasoning guard）+ 脚本 + 文档；**本质**：新增能力 + 删第三方镜像。
- 新增 `tools/model_stream_check.py`（587 行，增量探针）、`model_stream_exemptions.json`；删 `third-party/cliproxyapi/` 全量（6 文件 2191 行）；`supervisor.stopChild` 同步关闭子进程日志句柄（修 Windows 文件占用导致的随机失败）。

### f52450e 16:27 — Gemini-AIS 七跳降级链与首字对冲（10 文件，+1457/−35）
- **本质**：新增能力（并发对冲）。实测依据：3.8/3.7 常态 503；3.6 TTFB 9.63–24.38s；3.5 有 31s 读超时与 47.14s；3-flash-preview 稳定 1.50s；key 池空时 403 要 30s —— 池空实测 403 从 **31.47s 降到 1.31s**。
- 新增 `race.go` + `race_test.go` 六项；`ChannelPolicy` 七字段全部「零值=关」。

### 38b4509 16:27 — 流探针四修（3 文件，+43/−8）
- `RECOVER_TOKENS` 2048→8192（Iceman high-2048/4096 把预算全花在思考上，8192 才拿到 100 字正文）；`--changed` 基准改 `prev.models` 的 fingerprint；「200 + error 帧」的排队归 SKIP；增量模式补 SKIP 占位行。

### 486a955 16:29 — 回填第十七轮验收（1 文件，PROGRESS +9/−8）
- 只改文案。

### 6771431 20:37 — 只读控制台设计稿（2 文件，+363）
- 新增 `docs/CONSOLE.md`（360 行）+ 登记 `docs/README.md` 索引。纯设计，不动网关响应。

### 1c42f03 20:37 — 接入 HJ 哈基米渠道 + 看门狗 + 静默冷却（9 文件，+495/−39）
- **本质**：新增渠道能力 + 新增稳定性机制。看门狗全局从 45s 降到 12s，并支持按渠道（当时 GM 12s / HJ 25s）。
- `check-project.py` 增「渠道四登记点一致性」闸（加渠道漏改任一处 → FAIL）。

### 58b7ce8 20:37 — 哈基米福利 3.8 拆成独立模型（2 文件，+156/−23）
- **本质**：结构调整（用户口径变更）。以前福利档是 AIS 链里的一跳兜底；用户改成「ais 全档不可用时直接点它」，于是摘出成单跳族，AIS 回到 7 跳全 GM。
- `NAME_RENAMES` 清空（`Gemini-3.8-Flash` 现在是 live 名，同名 legacy 映射会误导排查），新增 `_consistent_legacy_ids` 清存量脏 legacy。

### ff48352 20:37 — 同步 Gemini 两族口径（8 文件，+188/−30）
- 只改文档：MODEL-PROVIDERS 拓写、TROUBLESHOOTING（§17 客户端偏好、§18 排障）、PITFALLS、ARCHITECTURE/MAINTENANCE/TOOLS/ZGATE-LIFECYCLE 的渠道口径。

### b73f0a2 20:37 — 第二十三轮记录（2 文件，+302/−1）
- PROGRESS +248 行、CHANGELOG +55 行，纯记录。

### 4cb0962 20:37 — 归档子代理取证分片（17 文件，+6857）
- 纯新增归档，无代码行为变化（`evidence/agent-*.md` + 4 篇 go-model-sync 报告）。

### 8c9825c 21:45 — 判死权归上游，HJ/GM 关掉本地看门狗（8 文件，+124/−37）
- **本质**：兼容适配 / 策略回退（第四次收敛，方向与 1c42f03 相反）。
- 数据依据：GM 判死 125 次（沉默 79 + 首块 46）中上游真说过 503 仅 7 次（5.3%）；HJ 判死 32 次，一大半与 502 同秒。判死 → 502 → 客户端 retryPolicy 命中 SERVER 必然重打 → 上游同一段 token 算两遍。
- 代码侧只有注释同步（`config.go` ChannelPolicy 注释、`router.go` upstreamHeaderTimeout 注释），**行为变化全在 `zgate.json`**（可 /admin/reload 生效）。

### cbac930 21:52 — 去残留旧表头（1 文件，−2）
- 只改文案（MODEL-PROVIDERS 两行）。

### bfd6b9e 22:08 — 流式请求提前交卷（7 文件，+586）
- **本质**：新增能力。`early_sse.go` 包一层 ResponseWriter：超过 `earlyCommitMs`（8000ms）没人 WriteHeader 就先写 200 + SSE；提前交卷后下游再想写 ≥300 的状态码，body 被扣下（≤4KB 留作提取 message），收尾改写为 `data:` error 事件 + `[DONE]`。
- 只对流式 chat 生效；窗口内上游就回话的走老路径，状态码原样；非流式保真；panic 兜底也走 `early.fail`。
- 窗口给 8 秒的理由：窗口内到达的 429/503 仍能原样透出（客户端该退避就退避），而实测合法首头 2.5–10.2 秒。

---

## 四、专门适配清单（针对某个上游 / 渠道的特殊处理 + 触发条件）

> 行号以 **2026-11-10 22:40 工作区**为准（含未提交改动），标注格式 `文件:行`。

| # | 适配对象 | 它在适配什么 | 触发条件（代码/配置落点） |
|---|---|---|---|
| A1 | **GM = catiecli 中转**（`catiecli.sukaka.top`） | 上游无本地进程、OpenAI 兼容直连；不配默认 base 就走不通 | `gateways/zgate/internal/config/config.go:334-342`：`upstreams["GM"]` 缺失时补 `Base: https://catiecli.sukaka.top/v1` + `KeyEnv: GEMINI_API_KEY` |
| A2 | GM 的 key 三级取值 | 该站 key 只在 `provider_config.json` 的 base 里能认出来 | `keys.go:119` `reGMBase = (?i)catiecli\.sukaka\.top`；`keys.go:165-172`：env `GEMINI_API_KEY` → `gemini .env.local` → 按正则匹配 providerConfig 规则 |
| A3 | GM/HJ 的 Authorization 强制覆盖 | 漏了任一通道会把客户端原始 Bearer（或空）透传，上游回 401「未提供API Key」 | `router.go:804-809`：`switch channel { case "WB","QD","QW","QN","GM","HJ": h.Set("Authorization","Bearer "+key) }` |
| A4 | GM 的 /health 段名 | 段名要人类可读且不能漏段 | `router.go:1277-1285` `healthSegments`；`router.go:1339-1341` 遍历 `keys.Channels` |
| A5 | GM 的价目与排位 | 中转站无公开价目表，未收录 id 必须丢弃，不能按 0 记账 | `tools/model_alias.py:1060-1062` `if channel == "GM": return GM_PRICES.get(upstream)`；`model_alias.py:109` `GM_PRICES` 统一 0.11 |
| A6 | **HJ = 哈基米 gemai.cc** | 另一家 Gemini 转售站，独立 key（`HJM_API_KEY`），模型 id 必须一字不改带 `[福利]` 前缀（上游只认这个字符串） | `config.go:346-354` 补 `upstreams["HJ"]`（`api.gemai.cc/v1`）；`keys.go:120` `reHJBase = (?i)gemai\.cc`；`keys.go:174-181` 三级取 key；`config.go:141` `hajimiEnvFile` |
| A7 | HJ 的模型分族与跳序 | 福利档以前混在 AIS 链当兜底，现在独立；不能参与 AIS 链内排序 | `model_alias.py:101-108` `HJ_BASE`/`HJ_PRICES`（`[福利]gemini-3.8-flash`: 0.05，不写 0.0——0.0 会被免费档逻辑拆链）；`model_alias.py:241` `CHANNEL_RANK` 加 `"HJ": 1`；`model_alias.py:253` `HOP_PRIORITY` 已删 HJ 项；`model_alias.py:386` `ABBR` → 显示名 `Gemini-3.8-Flash`；`model_alias.py:151` `MAIN_ORDER` 位置压在 `chat:gem:*` 之前 |
| A8 | `hjm:` 显式渠道前缀 | 不写前缀会落到末尾 OC 兜底，把 `[福利]` 当型号名发给 opencode | `model_alias.py:1173` `PREFIXES` 含 `"hjm:"`；`model_alias.py:1318-1330` `classify()` 的 `startswith("hjm:")` 分支 → `channel="HJ"`；`model_alias.py:1493` `CHANNEL_BASE["HJ"]` |
| B1 | **ais-* 七跳链（catiecli 上游 id）** | 同价 0.11 时按 upstream 字符串排序会把 3.5 排到 3.8 前面 | `model_alias.py:253` `HOP_PRIORITY`（3.8=0 … 3-preview=6，其它渠道跳取 99）；`model_alias.py:371` `ABBR` 把 7 个 id 全映射到 `Gemini-AIS` → 合并成一条链 |
| C1 | **首块对冲只对配了 channelPolicy 的渠道生效** | 未配渠道必须逐字节保持串行链老行为 | `race.go:306-334` `racePolicyFor`：`len(Chain)>=2` **且** `wantsStream(body)` **且** 全链 `protocol=="chat"` **且** `cfg.ChannelPolicy[hop.Channel]` 全部存在 **且** 首渠道 `HedgeAfterMs>0 || FirstBlockMs>0`，任一不满足即返回 false → 退回串行 |
| C2 | 对冲退化成串行时的告警 | `racePolicyFor` 静默 false 会让 2026-11-10 那次「链上 HJ 不在内存 channelPolicy 里」的故障无从判断 | `race.go:343-370` `noteSerialFallback`：流式 + 链首配了对冲 + 有渠道不在 `channelPolicy` → `Warnf`，同链条签名 10 分钟一条 |
| D1 | **按渠道覆盖响应头看门狗** | 「60 秒才回 503 的中转」与「抖动到 10 秒才出首块的兜底站」不能共用一个窗口 | `router.go:340-358` `headerTimeout(channel)`：优先级 测试字段 > `channelPolicy[ch].headerTimeoutSec`（**<0 → 返回 0 = 不设看门狗**）> 全局 `upstreamHeaderTimeoutSec`（<0 关）> 常量 12s（`router.go:123`） |
| D2 | 看门狗只挂流式请求 | 非流式上游往往等整段生成完才发头，同一档会误杀长回答 | `router.go:866-870` `doForward`：`wait := s.headerTimeout(channel)`，`wait <= 0 || !wantsStream(body)` 直接 `client.Do`；否则起 goroutine + timer，到点取消并返回 `errUpstreamSilent` |
| D3 | 沉默跳的静默冷却（GM/HJ = 20s，8c9825c 后置 0） | 只换跳不冷却的话下个请求又从死跳起手，每个请求白付一个窗口 | `router.go:966-988`（`errors.Is(err, errUpstreamSilent)` 分支 → `silenceCooldownFor(hop.Channel)` → `markSilence`）；`router.go:1145-1148`（首块超时同款）；`router.go:157-163` 读 `silenceCooldownSeconds` |
| E1 | **GM/HJ 关掉本地看门狗（判死权归上游）** | 本地判死 = 一次 502 + 一次客户端重试 + 一次上游重跑 | `gateways/zgate/zgate.json`：`channelPolicy.GM.headerTimeoutSec=-1`、`channelPolicy.HJ.headerTimeoutSec=-1`；判定点 `router.go:345-348`（`pol.HeaderTimeoutSec < 0 → return 0`）；GM 仅留 `hedgeAfterMs: 18000`，`firstBlockMs: 0`（`race.go:330` 因 `HedgeAfterMs>0` 仍开对冲） |
| F1 | **提前交卷只对流式 chat** | 非流式要确定 JSON + 状态码，提前交卷等于骗人 | `router.go:601-608`：`isChat && wantsStream(body)` 且 `earlyCommitWindow()>0`（缺省 8000ms，`config.go:278`；<0 关）→ 包 `earlySSEWriter` |
| G1 | **思考守卫（reasoning guard）** | 上游只给加密思考流、不给可读内容时透明重绘 | `config.go:58` `ReasoningGuard`（mode=`models` 时按白名单、否则 `auto`；`MaxProbeBytes` 32KB、`MaxRetries` 5、`GiveUpAfter` 2/`GiveUpForSeconds` 600） |
| H1 | **竞速观测保鲜期（未提交）** | 一次 503 不能把 3.8 永久压到最后；实测 21:32–21:47 有 15 分钟一次没碰过 3.8 | 未提交 `router.go` `hopStatSnap.stale()`：失败观测 TTL **10 分钟**（`raceFailTTL`）、成功观测 TTL **1 小时**（`raceOKTTL`）；`race.go` `rankedChain` 的 `case !ok || snap.stale(now)` 分支 |
| H2 | **推理档位继承（未提交）** | 档位格式不能跨渠道搬：WB/QD/OC/QN 认 `reasoning_effort`；`hjm:`/`gem:` 的档位是装饰项，不回写 | 未提交 `model_alias.py` `EFFORT_CHANNELS = ("WB","QD","OC","QN")`；`dsh_sync.py` `_USES_EFFORT_FIELD` 正则命中才写 `compat.thinkingFormat="deepseek"` |

---

## 五、未提交改动（截至 2026-11-10 22:39，可能仍被其他会话写入）

`git status --porcelain -uall`：7 项（5 改 + 2 未跟踪），`git diff --stat`：+387/−19，`git stash list` 空。

| 文件 | 功能面 | 本质 |
|---|---|---|
| `gateways/zgate/internal/router/router.go` (+31) | 健康检查 / 竞速排序 | `hopStatSnap` 增 `Seen time.Time`（不进 JSON），新增 `raceFailTTL=10m` / `raceOKTTL=1h` 与 `stale()`，`noteRaceHop` 写入时刻 |
| `gateways/zgate/internal/router/race.go` (+6/−1) | 竞速排序 | `rankedChain` 的 B 类从「没有观测」扩成「没有观测或观测过期」，让恢复的上游能被重新试到 |
| `gateways/zgate/internal/router/race_test.go` (+33) | 测试 | `TestRankedChainRetriesStaleObservations`：过期失败回声明顺序、新鲜失败仍压最后、过期成功也回声明顺序 |
| `tools/model_alias.py` (+238/−15) | 模型链与 provider 配置 | 新增推理档位继承链（`EFFORT_CHANNELS`、`pick_rule_config`、`_inherit_efforts`）与漂移守门 `drifted_efforts()`（`--check` 会失败） |
| `tools/dsh_sync.py` (+97/−2) | 脚本 | `_efforts_lost()` 回归守门（源头非空、投影为空即报）、`_keep_efforts()` 保留手写档位、`thinkingFormat` 只在 map 表达式真含 `reasoning_effort` 时才声明 |
| `tests/test_dsh_sync_efforts.py` (未跟踪) | 测试 | 新增档位投影/守门用例 |
| `tests/test_model_alias_efforts.py` (未跟踪) | 测试 | 新增档位继承用例 |

> ⚠️ 这 5 个已改文件在 22:39 仍在变化（同工作区有并行会话）。本文只记录当时快照，**没有跑 go test / 没有换版、没有重启任何长驻进程**。

---

## 六、方法与限制

- 依据：`git log --since="2026-11-10 00:00"`、逐 commit `git show --stat/--numstat`、对 f52450e / 1c42f03 / 8c9825c / bfd6b9e / 58b7ce8 / e032924 / 96e274d 的关键 diff 逐段读；运行时行为以**当前工作区代码**为准（`router.go`、`race.go`、`early_sse.go`、`config.go`、`keys.go`、`model_alias.py`）交叉核对。
- 未做：修改任何源码 / PROGRESS.md / docs / tests / provider_config.json；未 git add/commit/push；未动 stash；未重启 zgate / wb2api / mihomo / ModelBus 网关；未跑 build/test（工作区正在被并行写入，结果会失真）。
- 凭据：全文不含 key / token 明文，仅出现环境变量名（`GEMINI_API_KEY` / `HJM_API_KEY`）。
