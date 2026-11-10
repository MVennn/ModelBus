# 更新日志

> **一句话**：本仓每次改动记在这里 —— 改了什么、为什么、怎么回退；
> 首个版本段落记录本仓从原工作目录拆分建仓的全过程。

版本命名遵循三段式进位：**有功能更新进次版本（+0.1.0），没有就进补丁版本（+0.0.1）**；
破坏性变更同样走次版本，并在版本段落里显式标注。进位规则正本见
[docs/VERSIONING.md](docs/VERSIONING.md) §1 与 §2。

- 「功能更新」= 新增了脚本 / 新增了 provider 分组 / 现有脚本的行为变了。
- 只修 bug、改文档、调参数 → **+0.0.1**。
- 本仓库**没有编译产物**，版本号以本文件的段落标题为准
  （与 `docs/release-notes/<versionName>.md` 的文件名必须一致；文件名**不带 `v` 前缀**，
  发版 tag 才带 —— 口径见 [docs/VERSIONING.md](docs/VERSIONING.md) §3）。

---

## [未发布]

### 判死权归上游：HJ / GM 关掉本地看门狗，全局兜底 12s → 45s（2026-11-10 21:30）

> 当晚 GM 被判死 125 次（沉默 79 + 首块 46），上游真说过 `503 high demand` 的只有 7 次（5.3%）；HJ 判死 32 次，一大半与 502 同秒返回，而同一时段上游一直在正常吐 token。502 是本地造的 —— DSH 的 `retryPolicy` 把 `SERVER` 当可重试，判死一次就换来「一次 502 + 一次客户端重试 + 一次上游重跑」，用户看到的就是「后台在跑 token、本地断开又跑一遍」。

- **改（配置，热加载即可）**：`channelPolicy.HJ` 收敛为 `{"headerTimeoutSec": -1}`；`channelPolicy.GM` 的 `headerTimeoutSec` → `-1`、`firstBlockMs` → `0`、`silenceCooldownSeconds` → `0`、`hedgeAfterMs` → `18000`、`softCooldownSeconds` → `60`；`upstreamHeaderTimeoutSec` → `45`。
- **口径**：本地只做两件事 —— 「并排多问一家」（`hedgeAfterMs` 对冲只多开一路、不取消前一路）与「按上游回话冷却」（429 / 5xx / 403）。**上游没说我死了，就不替他下死亡通知**。
- **为什么不是继续调窗口**：慢是这条链的常态（catiecli 3.8 常态 9-14s 才出正文，哈基米首头从 2.5s 漂到 10s），阈值给多少都在赌，赌错一次就是一次重试 + 一次上游重跑。
- **源码注释同步**：`internal/router/router.go`（`upstreamHeaderTimeout` 上方追加第四次收敛段）、`internal/config/config.go`（`HeaderTimeoutSec` 字段注释改写）。仅注释，无行为变化，二进制可继续用。
- **文档**：[docs/MODEL-PROVIDERS.md](docs/MODEL-PROVIDERS.md) §4.11.3 参数表按渠道重写 + 「第四次收敛」段、§4.11.5 渠道策略行；[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) 新增 §18.4（含判据表与处置表），§18.1 / §18.2 旧处置标注已推翻。
- **验收**：`/admin/reload` → 200 `{"ok":true,"applied":["workbuddy","qoder"]}`；`go build ./...` / `go vet ./...` exit 0；`tools/check-docs.py` / `tools/check-project.py` exit 0。
- **回退**：`cp gateways/zgate/zgate.json.bak-nokill-20261110-2132 gateways/zgate/zgate.json` 后 `POST http://127.0.0.1:7871/admin/reload`。

### 哈基米福利 3.8 拆成独立模型 `Gemini-3.8-Flash`：主力组内压在 Gemini-AIS 之前（2026-11-10 22:27）

> 兜底塞在链里只能吃链首的规则：对冲参数与响应头窗口都取 `Chain[0]`（GM），而链首 `ais-gemini-3.8-flash` 常态「等到 60 秒才回 503 high demand」，每轮先白等一个窗口才轮到哈基米；AIS 一家整片 error 时更是纯浪费。用户 20:20 拍板：拆出来、改名、放主力、压在 AIS 前面。

- **拆链**：`ABBR` 里 `[福利]gemini-3.8-flash` 从 `Gemini-AIS` 改成 `Gemini-3.8-Flash`，`HOP_PRIORITY` 删掉 HJ 项、ais 重编为 0-6 → `Gemini-AIS` 回到 **7 跳全 GM**（3.8 → 3.7 → 3.6 → 3.5 → 3.5-lite → 3.1-lite → 3-preview，价格同 0.11）。
- **新模型**：`Gemini-3.8-Flash` 单跳 `HJ`（上游 `hjm:[福利]gemini-3.8-flash`，价 0.05），`MAIN_ORDER` 里排在整套 `chat:gem:*` 之前 —— 主力组内位置就在 `Gemini-AIS` 上方。
- **legacy 收口**：`NAME_RENAMES` 原先把 `Gemini-3.8-Flash` 记成 `Gemini-AIS` 的旧名，新模型正好复用这个 id，留着同名映射会把老会话解析到 AIS，故清空。拆族后 AIS 的 `legacy_ids` 还挂着 `hjm:[福利]gemini-3.8-flash`，新增 `_consistent_legacy_ids()`（带前缀的 legacy 必须 `_bare()` 命中本模型某跳）并在写盘后清理「与 live 模型同名」与「前缀对不上跳表」的条目 —— `/v1/models` 里同一个上游 id 只对应一个 canonical。
- **验收**：`python -m unittest discover -s tests` 62 项 ok（改写 6 个 Gemini 用例，含磁盘守卫：AIS 7 跳全 GM、3.8-Flash 单跳 HJ、同组、主序在前）；`model_alias.py --apply` 后 `model-alias-map.json` 20 个模型、AIS 7 跳全 GM、3.8-Flash 单跳 0.05；`dsh_sync.py --apply` 生成 patch（70 行 `Gemini-3.8-Flash`、73 行 `Gemini-AIS`，patch 第 8 行默认模型未改）；`/admin/reload` 后实打 `model=Gemini-3.8-Flash` → 200、响应头 4395ms、SSE 出字；`/v1/models` 显示 `Gemini-3.8-Flash` hops=1 主力、`Gemini-AIS` hops=7 主力、旧 id `hjm:[福利]gemini-3.8-flash` canonical 指向新模型。
- **生效条件**：DSH 侧要重启客户端才看得到新模型（patch 已生成）；`provider_config.json` 与 alias map 已落盘，网关已 reload。
- **回退**：`cp provider_config.json.bak-alias-20261110-202537-597800 provider_config.json`，`git checkout tools/model_alias.py tests/test_model_alias_hop_order.py`，再跑 `python tools/model_alias.py --apply`、`python tools/dsh_sync.py --apply`。

### Gemini-AIS 沉默跳也进短冷却：不再每个请求都重撞一遍死跳（2026-11-10 20:20）

> 看门狗已经能「12 秒拿不到响应头就换跳」，但换跳之后**没把这一跳埋起来**：`errUpstreamSilent` 分支只调 `retry()` 回落下一跳，`silence` 表一次都没写。结果是第二个请求又从第一跳起手，把已经证明死掉的跳重新等一遍 —— 用户连发两句，两分钟里大半时间花在撞已知死跳上。

- **改**：`doForwardWith` 命中 `errUpstreamSilent` 后按渠道 `silenceCooldownSeconds` 打 `markSilence`（GM/HJ 各 20 秒），并打一行 `沉默，静默冷却 20s 后再试这一跳`；`doForwardWith` 因此多收一个 `hop *alias.Hop`（桥接与 forward 直转传 `nil`，行为不变）。`cooling()` 本来就同时读 `cool` 与 `silence`，所以串行链与竞速链都会立刻跳过它。
- **不新增失败面**：全链都在短冷却时 `raceChain` 仍然走 `clearSilence` 清掉软冷却重试一次（真冷却 429 / 5xx / 额度一律不动），不会因为埋得太狠把自己饿成 502。
- **口径**：静默冷却保持短（20 秒），它是「这次先说别人」，不是「这跳死了」；死跳 / 限流 / 额度过期仍走 45 秒 - 24 小时那一档。
- **验收**：`gofmt -l .` 空、`go build ./...` / `go vet ./...` exit 0、`go test ./...` 全 ok（新增 `TestSilentHopGetsShortCooldown`：沉默后 `retry` 必须被调用一次且 `cooling(hop)` 为 true）；`tools/check-docs.py` / `tools/check-project.py` exit 0。
- **生效条件**：仍需换二进制（`tools/zgate-lifecycle/deploy-zgate.ps1`），`silenceCooldownSeconds` 是配置但埋点代码是编译期代码。手册见 [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) §18.3 与 [docs/PITFALLS.md](docs/PITFALLS.md) §42 末条。

### Gemini-AIS 换上兜底后仍要 4 分半：响应头容忍 45s → 12s、再按渠道分（GM 12s / HJ 25s）（2026-11-10 深夜）

> 上一版加了「45 秒拿不到响应头就换跳」，结果是**每跳都等满 45 秒**：实测同一跳 `ais-gemini-3.8-flash` 每次都要等到 60.241 秒才回 503 high demand，而哈基米 `[福利]gemini-3.8-flash` 直连 2.5-3.1 秒就出首块。8 跳按 `maxParallel=2` 轮转 = 4 轮 × 45 秒，用户实测 4 分 31 秒；期间客户端等不到首字节会自动重试，反代后台就出现两条「请求中」。

- **默认容忍降到 12s**：`router.go` 的 `const upstreamHeaderTimeout = 12 * time.Second`（原 45s）。12 秒对正常首头（2.5-3.1 秒）有 4 倍余量；全灭时最坏 4 轮 × 12 秒 ≈ 48 秒就给结论，而不是 4 分钟。
- **变成可调配置**：新增 `upstreamHeaderTimeoutSec`（`internal/config/config.go` 的 `Config` + `applyDefaults` 缺省 12；`zgate.json` 已写入 `12`）。`Server.headerTimeout()` 每次现读，优先级 `headerWait` 显式值 > 配置 > 常量；**负数 = 关掉看门狗**（回到无限等）。`/admin/reload` 即可改，不必重编译。
- **沉默告警带模型名**：`[router] https://api.gemai.cc/v1（model=[福利]gemini-3.8-flash）上游 12s 内没给响应头，判这一跳沉默并换跳`。同一个 base 下不同模型能差一个量级，只打 base 分不清是谁被晾着。
- **口径**：这个超时按「正常首头最慢分位 × 3-4」定，不按「上游多久才认输」定 —— 前者保体验，后者只是把超时串成糖葫芦。
- **验收**：`gofmt -l .` 空、`go build ./...` / `go vet ./...` exit 0、`go test ./...` 全 ok（新增 `TestHeaderTimeoutFollowsConfig`：配置 3s 生效 / 缺省回落常量 / 负数返回 0 / `headerWait` 最优先；`config_test.go` 补缺省 12 与 `-1` 两断言）；`zgate.json` JSON 解析通过；`tools/check-docs.py` 40 篇 / `tools/check-project.py` 8 项 exit 0；`TestHeaderTimeoutPerChannel` 覆盖渠道覆盖、渠道负数、渠道缺省回落与显式字段优先。
- **再按渠道分窗口（20:05 实测后补）**：换成 12s 后当晚 20:03 出现「8 跳全灭、50 秒干净失败」，日志里连哈基米那跳也是 `12s 内没给响应头`；同一时刻直连哈基米是 7.5-10.2 秒出首头 —— 12 秒正好卡在它抖动边缘，兜底那家被自己的门槛切掉了。于是 `channelPolicy` 新增 `headerTimeoutSec`（0 = 继承全局，负数 = 该渠道不设看门狗），`Server.headerTimeout(channel)` 优先级改为「显式测试字段 > 渠道 > 全局 > 常量」，`zgate.json` 里 **GM 12s / HJ 25s**。两路并发时 GM 先到点、链继续往下走，HJ 还在等它的 10 秒，谁先出首块谁赢。
- **告警也带上了渠道**：`[router] https://api.gemai.cc/v1（channel=HJ model=[福利]gemini-3.8-flash）上游 25s 内没给响应头…` —— 同一渠道不同模型、同一模型不同时间都能差一个量级，缺渠道名就分不清是「这家慢」还是「这个模型慢」。
- **生效条件**：仍需换二进制（`tools/zgate-lifecycle/deploy-zgate.ps1`）—— 常量与 `headerTimeout()` 是编译期代码；换完再看日志，「45s 内没给响应头」应变成「12s」。手册见 [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) §18.1 与 [docs/PITFALLS.md](docs/PITFALLS.md) §42 末条。
### Gemini-AIS 一分钟零输出：补流式响应头看门狗 + 串行退化告警（2026-11-10 夜）

> 症状是「点了发送，一分钟一个字都没有，客户端只能手动停」，同时上游反代后台**一条记录都没有**。不是网络不通，也不是模型挂了：降级链加了新渠道 `HJ`，而运行中的 `zgate.exe` 是加 HJ 之前构建的 —— 内存里的 `channelPolicy` 只有 `GM`，`racePolicyFor` 因「链上有渠道没配对冲」让整条链退回串行，而串行路径没有首块看门狗，首跳把连接挂住就成了静默。

- **新增流式响应头看门狗**：`router.go` 的 `doForward` 对流式请求最多等 `upstreamHeaderTimeout`（45s）拿响应头，超时判这一跳沉默（`errUpstreamSilent`）直接换下一跳；非流式不受影响（上游常常整段生成完才回头）。`Body` 用 `cancelOnClose` 包一层，成功时取消 ctx 既不泄漏也不掐断正常流；命中沉默**不走 `txRetry`**，避免再白等一个窗口。
- **新增串行退化告警**：`routeChain` 落到 `attemptChain` 之前调 `noteSerialFallback` —— 链上任何渠道没在 `channelPolicy` 里就打一条 `[race] 链上有渠道不在 channelPolicy 里（…），整条链退回串行、取消首块对冲` 的 WARN（按渠道组合 10 分钟去重）。这条 WARN 是「换了渠道忘了换二进制」的唯一可见信号。
- **验收**：`go test ./...` 全 ok（新增 `TestStreamingHeaderWatchdogGivesUp` / `TestStreamingHeaderWatchdogPassesThrough`）、`gofmt -l` 空、`go build` / `go vet` exit 0；`python gateways/zgate/build.py --candidate` 产出 `zgate.candidate.exe`（内容检索 `upstream silent` 命中）。
- **生效条件**：长驻网关，重启由用户执行（`tools/zgate-lifecycle/deploy-zgate.ps1`）；起来后 `/health` 的 `segments` 应多出 `hajimi`。排查手册见 [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) §18 与 [docs/PITFALLS.md](docs/PITFALLS.md) §42。
### Gemini-AIS：3.8 失败先兜哈基米同代福利档，再降代（2026-11-10 夜）

> 原来的链一失败就**降代**（3.8 → 3.7 → 3.6 …），能力掉一档；而 3.8 挂掉多半是那家中转站的问题，不是模型不行。所以在 3.8 与 3.7 之间插一跳**另一家的同一个 3.8**：先换站，再谈降代。

- **新渠道 `HJ`（哈基米，https://api.gemai.cc/v1）**：只承载一跳 `[福利]gemini-3.8-flash`（上游原样 id 带方括号中文前缀，不改写）。它没有自己的模型目录条目 —— 显示名仍是 `Gemini-AIS`，并进同一条链，用户看到的还是那一个模型。
- **链序**：`ais-gemini-3.8-flash`(0) → `[福利]gemini-3.8-flash`(1) → `ais-gemini-3.7-flash`(2) → … → `ais-gemini-3-flash-preview`(7)，链由 7 跳变 8 跳。`HOP_PRIORITY` 整体重排，`CHANNEL_RANK["HJ"]` 与 GM 同为 1（跨渠道顺序完全由 `HOP_PRIORITY` 决定）。
- **价格不能写 0**：`HJ_PRICES` 登记 `0.05`。写 `0.0` 会让 `family_entries()` 把「同族 0 价 + 有价」拆成 `Gemini-AIS` 与 `Gemini-AIS-Free` 两条，链当场断成两条（这也是为什么不给它做免费档）。
- **网关层四登记点**：`internal/keys/keys.go`（`Set` 加 `HJ`、`Channels` 加 `"HJ"`、`reHJBase` 匹配 `gemai.cc`、`Load` 增第 7 参 `hajimiEnvFile`、`For` 加 `case "HJ"`）；`internal/config/config.go`（`HajimiEnvFile` + `upstreams["HJ"]` 默认 + `resolvePaths`）；`internal/router/router.go`（`applyHeaders` 名单补 `HJ`、`healthSegments` 加 `"HJ": "hajimi"`、`reloadKeys` 补参）；`main.go` 的 `keys.Load` 补参。`zgate.json` 加 `hajimiEnvFile` / `upstreams.HJ` / `channelPolicy.HJ`（与 GM 同参数：90 / 20 / -1 / 4000 / 500 / 2 / 24）。渠道总数 6 → 7。
- **凭据**：`providers/hajimi/.env.local`（`HJM_API_KEY`，已 gitignore），由 DSH credentials 搬运，未回显。
- **门禁加固**：`tools/check-project.py` 新增「渠道集合一致性」静态闸 —— 比对 `zgate.json` 的 `upstreams` 与 `keys.go` 的 `Channels`（漏一处即红），并检查 `channelPolicy` 不指向未登记渠道；Bearer needle 与「六段」旧口径同步改成 7 个 upstreams / 七段。
- **验收**：`gofmt -l` 空输出、`go build ./...` / `go vet ./...` exit 0、`go test ./...` 全 ok；`python -m unittest discover -s tests -q` 全绿（新增「哈基米兜底夹在 3.8 与 3.7 之间」与 8 跳顺序两条断言）；`tools/model_alias.py` dry run 确认 `Gemini-AIS` 仍只有一条、链 8 跳。
- **额度纪律**：哈基米与 GM 一样按调用次数计费，未做真实调用验证；链路正确性由 `family_entries` 的离线断言保证。
- **回退**：删 `HOP_PRIORITY` 里 `[福利]gemini-3.8-flash` 那一行 + `ABBR` 对应行 + `MAIN_ORDER` 里 `chat:hjm:…` 一条即回到 7 跳；其余 `HJ` 登记点在链里没有该跳时不会被访问（`keys.Channels` 多一段无害），要彻底删再按上面四处逐一摘除。

### Gemini-AIS：七跳降级 + 首字对冲 + 渠道级快速失败（2026-11-10 傍晚）

> 上游这条中转「难调用」是真事：3.8 / 3.7 常态 503，3.6 / 3.5 常回 200 却十几秒不出字，key 池为空时还要 30 秒才回 403 —— 单跳串行等于把最坏的等待全摊给用户。

- **为什么必须原生化降级**：`ais-` 前缀下 7 个 id 首字实测差异巨大（3.8 / 3.7 多为 503；3.6 TTFB 9.63–24.38 s，另有一次 14.24 s 零 content；3.5 TTFB 10.04 s，另两次 31 s 读超时与 47.14 s；3.5-lite 6.71 / 3.74 s；3.1-lite 多 503；3-flash-preview 稳定 1.50 s）。串行链每跳各自等满超时才回落，最坏叠加到 30 秒以上；并发对冲 + 首块闸门才能把「首字」压到实测最快的那一跳上。
- **命名**：`tools/model_alias.py` 的 `ABBR` 把 7 个上游 id 全映射到显示名 **`Gemini-AIS`**，`family_entries()` 合并成**一条 7 跳的链**（3.8 → 3.7 → 3.6 → 3.5 → 3.5-lite → 3.1-lite → 3-preview）。同价 0.11 时原排序键按 upstream 字符串会把 3.5 排到 3.8 前面，故新增 `HOP_PRIORITY`（3.8=0 … 3-preview=6，其它渠道的跳取 99）压住跳序；`MAIN_ORDER` 改从 `chat:gem:ais-gemini-3.8-flash` 起。旧显示名 `Gemini-3.8-Flash` 由 `NAME_RENAMES` 记成 legacy → `Gemini-AIS`，否则老会话选中的旧 id 会因 legacy 自指条目被当死链丢弃（`model_alias.py:2161-2175`）。
- **`channelPolicy`（新配置段，零值=关=老行为）**：`internal/config/config.go` 新增 `ChannelPolicy`（`softCooldownSeconds` / `silenceCooldownSeconds` / `rateLimitBackoffMs`（负数=不做就地 429 退避）/ `firstBlockMs` / `hedgeAfterMs` / `maxParallel` / `authFailCooldownHours`），`zgate.json` 只对 `GM` 开：90 / 20 / -1 / 4000 / 500 / 2 / 24。
- **首字对冲与抢写**：新增 `internal/router/race.go`。`raceGate` 让 N 跳同时发车、谁先写出响应头谁赢，其余路立刻 `cancelAll` —— 输家的 body 一律丢弃，客户端只看到一份响应。`peekFirstContent` 给每跳加首块闸门：`firstBlockMs` 内没出现真正的 delta（`hasContentDelta` 认 `choices[].delta.content`、`delta.reasoning_content`、`candidates[].content.parts[].text`，role-only 与 `[DONE]` 不算）就撤掉这一路、换个跳再上 —— 「200 但空流」因此不再能把首字拖到十几秒。
- **两张冷却表**：`cool`（429 / 5xx / 额度 / 超时）与 `silence`（首块超时）分开，静默只冷却 20 s 且允许在链首轮空时被 `clearSilence` 清掉重排一次，429 与额度冷却一律清不掉（早先把两者混在一起，「清冷却 → 再撞 429 → 再清」的死循环把整条链打成连片 502）。`cooling()` 两表都认。
- **渠道级快速失败**：`poolDown()` 认「没有可用的 Gemini API Key」等四种措辞，命中即 `markChannelOffFor(GM, 90s)` 并把上游原话回给客户端；`authFatal()` 认 401/403 + 鉴权类 marker，命中即按 `authFailCooldownHours` 停用该渠道 24 h（未配 `channelPolicy` 的渠道行为不变）。渠道停用后 `raceChain` 立即 `cancelAll` 并回状态码，不再等其他在飞跳超时 —— 池空实测从 **31.47 s 回 403** 降到 **1.31 s 回 403**，后续请求 **0.0015 s 回 503 `channel_paused`**。
- **发车顺序按实测证据**：`rankedChain()` 把有 `ok` 观测的跳按 `firstBlockMs` 升序排前，从未观测的保持声明顺序（`HOP_PRIORITY` 的「3.8 优先」只在没有实测数据时成立），有失败记录的垫底。`/health` 的 `race` 段暴露每跳的 `firstBlockMs / verdict / at` 与渠道停用到期时间，调参不再靠猜。
- **验收**：`gofmt -l` 空输出、`go vet ./...` exit 0、`go test -count=1 ./internal/router ./internal/config` 双绿（新增 `race_test.go` 六项：抢写唯一、输家不污染、首块超时、静默冷却可清 / 真冷却不可清、`rankedChain` 排序）；`check-project.py` 8 项、`check-docs.py` 39 篇、`check-secrets.py` 192 文件、`python -m unittest discover -s tests -q` 59 项全部 exit 0。首字 12 轮验收（`hedge 1500 / maxParallel 3`）ok=12/12、p50 4.44 s、p90 24.08 s、max 37.76 s —— 难看的原因已定位（能出字的 lite 排在第 5 跳、离群是多个空流跳各等满 8 s），据此把 `firstBlockMs` 收到 4000、`hedgeAfterMs` 收到 500、`maxParallel` 定在 2（6 路扇出会把上游每 key 并发打爆，实测 20 轮全 502）。**上游 key 池当前为空，真调用复测待恢复**；池子恢复后按 `.work/gemini-ais-accept.mjs` 跑 3 轮即可回填。
- **额度纪律**：该上游按**调用次数**计费（一次请求扣一个额度，不论流式与否、是否 403），故链路行为一律用夹具 7999 验；`.work/gemini-ais-accept.mjs` 默认 3 轮、硬上限 10 轮，台账在 `.work/gemini-quota-usage.md`。
- **回退**：删 `zgate.json` 的 `channelPolicy` 段即回到「纯串行、每跳等满超时」的老行为（`raceChain` 只在策略开启且链 ≥2 跳时进入，`race.go` 可以留着）；显示名回退删 `NAME_RENAMES` 与 `ABBR` 的七行、恢复 `MAIN_ORDER`；二进制回退用 `gateways/zgate/zgate.exe.bak-deploy-*`。

> 上一条 2026-11-10 下午「推理档位补齐」里出现的 `Gemini-3.8-Flash` 就是本条的 `Gemini-AIS`（同一条链，只改了显示名）。

### 推理档位补齐 + 探针误判修复 + Iceman 展示层复位（2026-11-10 下午）

- **档位投影**：`python tools/dsh_sync.py --apply` 给 5 个缺口模型补上 `{off: disabled, high: high}`（Gemini-3.8-Flash / Iceman / Qwen-3.8-Flash / MiMo-2.6-Flash / MiMo-2.6-Pro），其余 14 个档位零变化，复跑 `--check` 报「模型表: 无变化」。根因是 `tools/dsh_sync.py:161-191` 的 WARN 回落分支 + `:206-218` 只读模型自身 `optionSpecs`，缺声明时 `_reasoning()` 返回 `{}`。上游仍有 5 个模型（Beam / Conatus / Claude-Haiku-5.5 / GPT-6-Luna / Muse-Spark1.3）因 `providers/opencode-go/ops/go_model_sync.py:577-581` 在 `needs_no_thinking` 时整段跳过 values 而拿不到档位，属源头待修；实测 Beam 无档位却回 818 字思考，门禁把它当 `no_reasoning` 属口径缺口。
- **展示层复位**：`cordis.patch.yml:20-26` 被 14:25 的「自动采集」回退成 `compact / completion / final`（回退源 `cordis.patch.yml.bak-autocapture-20261110142500`），已改回 `verbose / next-input / all`；`reasoningDisplay: continuous` 不动。`dsh_sync.py` 只重写 `llm-pi-ai` 段，14:52 的 `--apply` 未吃回该段。
- **探针四修**（`tools/model_stream_check.py`）：① `RECOVER_TOKENS` 2048→8192，实测 Iceman `high-2048` 思考 1899 字正文 0、`high-4096` 仍 0、`high-8192` 出 549 块 / 2322 字思考 / 100 字正文 / `fin=stop`；② `--changed` 的基准由 `prev.contract` 改 `prev.models` 的 fingerprint，否则契约里新进、results 里没结果的模型永远选不中，`latest.json` 恒少于 `contractCount`，门禁判「结构损坏」；③ 识别网关包成 `HTTP 200 + {"error":{...}}` 的上游排队帧（10605 / RESOURCE_LIMIT），归 `SKIP` 而不是「空 completion」；④ 增量模式给未轮到实测的契约模型补 `SKIP` 占位行（不带 fingerprint），保证 `models` 条数恒等于 `contractCount`。
- **守卫作用域**：`zgate.json` 的 `reasoningGuard.mode` 为 `models`（Iceman / iceman-contributor-free）。上一条里「`zgate.json` 已切 auto」是 12:59 换版当时的状态，此后已收回 `models` —— `auto` 会把 `cn:deepseek-v4.1-flash` 一并纳入探针并打进 600 秒跳过表（`zgate.log` 实见 358 条「跳过期内直接放行」），现状以 `models` 为准。
- **验收**：`check-project.py` 8 项 exit 0；`latest.json` 19 条全量视图 PASS 14 / SKIP 3 / EXEMPT 1 / RECOVERED 1、FAIL 0；Qwen-3.8-Flash 带与不带 `reasoning_effort` 均回 10605 排队（各 184 s），确认非档位适配问题。
- **未做**：探测期心跳 —— `router.go:879-951` 的 `streamIdleHeartbeatSec` 只在上游流已开始后生效，守卫重抽期间客户端零字节（`probeSeconds` 15 × `maxRetries` 1 ≈ 30 s）；Iceman 已降为备用不押注。

### Gemini 3.8 Flash 并入主力组：新增 `GM` 渠道与 `gem:` 前缀（2026-11-10）

- **为什么必须改 Go**：`zgate.json` 的 `keyEnv` 是死字段（`internal/config/config.go` 只赋值、无读取方），上游 key 只能来自 `internal/keys` 的 `Set.For(channel)`，而它硬编码 OC/WB/QD/QW/QN。不新增渠道，`key` 恒为空，`router.attemptChain` 会在 `router.go` 直接跳过该跳，表现为单跳 502。
- **网关层**：`internal/keys/keys.go` 的 `Set` 加 `GM`、新增 `reGMBase`（匹配 `catiecli.sukaka.top`）、`Load` 增 `geminiEnvFile` 参数并支持 env → env 文件 → provider_config 正则回退三级取 key、`For` 加 `case "GM"`；`internal/config/config.go` 加 `GeminiEnvFile` 与 `upstreams["GM"]` 默认；`main.go` / `internal/router/router.go` 两处 `keys.Load` 补参、`/health` 负载加 `gemini` 段；**`applyHeaders` 的 Authorization 覆盖名单补 `GM`** —— 漏掉这一步会把客户端空 Bearer 透传上去，上游回 401 `未提供API Key`（实测踩到）。`zgate.json` 同步加 `geminiEnvFile` 与 `upstreams.GM`。
- **命名与分组**：`tools/model_alias.py` 新增 `GM_BASE` / `GM_PRICES`、`MAIN_ORDER` 追加 `chat:gem:ais-gemini-3.8-flash`、`CHANNEL_RANK["GM"]=1`、`ABBR` 映射 `Gemini-3.8-Flash`、`VENDOR_PREFIXES` 加 Gemini、`price_of` 的 GM 分支、`gem:` 前缀（`PREFIXES` / `CHANNEL_PREFIX` / `whitelist_items`）、`classify` 的 `gem:` 分支、`CHANNEL_BASE["GM"]`。中转无公开价目，价格在 `GM_PRICES` 显式登记，未登记的 id 返 `None` 会被当死链丢弃。
- **凭据**：`providers/gemini/.env.local`（`GEMINI_API_KEY`，已 gitignore），由 DSH credentials 搬运，未回显。
- **DSH 侧入口唯一化**：删除 `cordis.patch.yml` 里手工直连的 `gemini` provider 与 `quickProviders` 的 `- gemini`，provider 由 4 个降为 3 个（zcode-main / zcode-free / zcode-saver），Gemini 改由 `zcode-main` 经 7871 提供。备份 `cordis.patch.yml.bak-gemini-merge-20261110-1352`。
- **门禁与测试**：`tools/check-project.py` 三处随代码更新（Bearer needle 去尾冒号、`/health` 段循环加 `gemini`、提示文案改「六段」）；`tests/test_model_alias_naming.py` 与 `tests/test_model_alias_price.py` 修掉 11-10 主力收敛后遗留的漂移断言（原期望 `Qwen3.8-Max` 在主力的两条，现按 DeepSeek 三跳 + Gemini 单跳重写）；`evidence/agent-thinking-adapt.md` 的本机绝对路径脱敏为 `~`。
- **验收**：`go build ./...` exit 0；`go test ./...` alias/bridge/config/router ok（`internal/supervisor` 的 `TestOnDemandStartAndIdleStop` 挂在 Windows TempDir 文件占用，与本次改动无关）；`python -m unittest discover -s tests` 56 项 OK；`check-project.py` / `check-docs.py` / `check-secrets.py` 全 exit 0；隔离实例 `/health` 200、`/v1/models` 89 条含 `Gemini-3.8-Flash`；生产 `--apply` 后 alias map 主力 2 条、`personalModelIds` 含 `Gemini-3.8-Flash`。
- **未定论项**：上游四次探测（含经 zgate 生产链路）全部返回 503 `This model is currently experiencing high demand`，SSE 零事件、零 token 消耗，**思考能力待复测**，因此 `optionSpecs.reasoningLevel` 暂不配；上游恢复后发一次 `stream:true, reasoning_effort:"high"`，看 delta 里有无 `reasoning_content` 即可定论。
- **回退**：删 `keys.go` / `config.go` / `router.go` / `main.go` / `zgate.json` 里的 GM 段，删 `model_alias.py` 的 GM 与 `gem:` 相关行，还原 `cordis.patch.yml.bak-gemini-merge-20261110-1352` 与 `provider_config.json.bak-alias-20261110-134823-055600`；二进制回退用 `zgate.exe.bak-deploy-*`。

### Iceman 看不到思考 / 输出一节一节：加密分流透明重抽 + 展示层展开（2026-11-10）

- **展示层**：`~/.dsh/profiles/desktop/cordis.patch.yml` 的 `ui-chat` 由 `standard / completion / final` 改成 `verbose / next-input / all`（verbose 的 `foldCompletedTurns:false` 让轮次结束后思考与过程行不再整轮折叠），`ui-skin-claude-style` 加 `reasoningDisplay: continuous`（取消两行步进）；`tools/dsh_sync.py` 只重写 `llm-pi-ai` 段，改动不会被每日同步覆盖；**刷新 GUI 即生效**。
- **网关层**：`gateways/zgate/internal/config/config.go` 新增零值禁用的 `ReasoningGuard`（enabled / models / maxRetries / maxProbeBytes），`zgate.json` 只圈 `Iceman` 与 `iceman-contributor-free`；`internal/router/router.go` 在 `doForwardWith` 写响应头前探测首包，命中「期待思考却先给正文且零明文 thinking delta」直接关流重抽同一跳（上限 3 次，沿用原 headers 保鉴权与 `X-Opencode-Session`），A 格式用 `io.MultiReader` 原字节续上。**改 Go 必须换 `zgate.exe`**：`/admin/reload` 只热加载配置，换版流程见 [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) §16.2；本会话未重启长驻网关。
- **探针与门禁**：`tools/model_stream_check.py` 新增 `_encrypted_reasoning()` / `encryptedReasoning` / `ENC` 列，`judge()` 把零明文思考 + `ENC>0` 明确标成「上游加密思考分流」；顺带修 `_effort_map()`，YAML 1.1 把裸 `off` 读成 `False` 会让 `load_contract()` 抛 `TypeError: sequence item 3: expected str instance, bool found`。`tools/check-project.py` 静态接线由六处扩到七处，并复核报告里的加密分流标注没丢。
- **文档**：[docs/MODEL-STREAM.md](docs/MODEL-STREAM.md) §1/§3/§4/§6/§9 补探针口径，[docs/PITFALLS.md](docs/PITFALLS.md) §41 记现象 → 根因 → 怎么避，[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) §17 记排查顺序，[docs/TOOLS.md](docs/TOOLS.md) 与 [docs/README.md](docs/README.md) 工具表 / 索引同步。
- **验收**：`go vet ./...` / `go test ./...` exit 0；新增 `internal/router/reasoning_guard_test.go` 7 项 PASS（首包判定四形态、白名单 / off / 禁用、重抽保鉴权、上限放行）；`py_compile` / `check-project.py` / `--stream-contract` / `check-docs.py` / `check-secrets.py` 全 exit 0；探针实跑 Iceman 307 块 / 1404 思考 / ENC=1，离线构造 B 格式 `judge()` 正确标注。`build.py --candidate` 编出含守卫的 `zgate.candidate.exe`（PE Subsystem 2 / GUI），隔离端口 17871 + 假上游端到端 PASS：B 首包即时判定重抽（上游 2 次调用、0.00s，不等 B 后端拖尾）、A 格式 `io.MultiReader` 原字节续上不丢块。**线上 7871 的 `zgate.exe` 仍是旧二进制（PID 17852 未动、不含守卫代码）**，网关层要按 §16.2 换版才生效，会话内未重启长驻网关。回退：删 `zgate.json` 的 `reasoningGuard`（零值=禁用）、还原 `cordis.patch.yml` 两个 config 段。


### 守卫二次修复：换连接+换会话重抽、auto 适配、SSE 心跳与 Content-Length（2026-11-10 下午）

> 上一条修的是「有没有守卫」，这一条修的是「守卫为什么没救回思考」——前两版上线后界面依旧看不到思考。

- **重抽为什么白抽**：首版重抽故意沿用原 headers「保 `X-Opencode-Session`」且复用 keep-alive 连接，而上游是按会话/连接粘后端的，3 次重抽全落回同一路加密后端（`zgate.log` 里 3 条「透明重抽同一跳 1/3..3/3」后紧跟 WARN「达上限放行最后一次」）。现改为每次重抽 `req.Close = true` + 会话头追加 `#r<N>-<随机>`，默认上限 5 次。
- **200 却 0 字节**：上游 SSE 自带 `Content-Length` 时，守卫丢弃首段 / 插提示 / 掺心跳都会改长度，写端报 `http: wrote more than the declared Content-Length` 并断流。现对事件流一律 `w.Header().Del("Content-Length")`，交给 `net/http` 按 chunked 重新分帧（`router.go` `copyHeaders` 之后）。
- **思考期静默**：新增 `streamIdleHeartbeatSec`（缺省 15，负数关），空闲超阈值补 `: zgate keepalive` SSE 注释行；非事件流一律不掺。
- **同类模型免配置**：`reasoningGuard.mode` 新增 `"auto"`（`zgate.json` 已切 auto）—— 不再依赖 `models` 白名单，凡声明要思考的流式请求都探针；配按模型学习表（`giveUpAfter` / `giveUpForSeconds`，连续几轮全程加密就短暂停手、到期复探）与达上限提示注入（`injectNotice`，流首插一条 `reasoning_content` 说明）。适配口径见 [docs/MODEL-STREAM.md](docs/MODEL-STREAM.md) §10。
- **日志可定性**：守卫两条命中日志补上游模型名（`模型 %q`），并发多模型时不必再靠时间戳猜是哪个模型被判成加密分流。
- **验收**：`gofmt` / `go build ./...` / `go vet ./...` exit 0；`internal/router` 12 项、`internal/config` 2 项 PASS（新增 auto 覆盖陌生模型、换会话换连接、提示注入、学习跳过、心跳、非流式不掺心跳、带 `Content-Length` 的上游形态）；隔离实例 17881 + 带 CL 的假上游实测两条路径：首跳加密 → 客户端拿到明文思考且加密首跳未泄漏，始终加密 → 200 + 597 字节（提示 + 正文）。**线上已换版**（2026-11-10 12:59 由用户执行 `tools/zgate-lifecycle/restart-zgate.cmd`，`zgate.exe` 与候选同 sha、PID 27360；换版后实跑命中「换连接+换会话重抽 1/5」）。回退：`mode` 改回 `models` 或删 `reasoningGuard` 段；二进制回退用 `zgate.exe.bak-deploy-*`。

### 守卫第三次修复：客户端不发思考档位时由网关补（2026-11-10 下午）

> 前两条都在修「守卫怎么重抽」，换版后仍看不到思考 —— 因为守卫根本没被触发过。

- **真因**：DSH 模型选择器没有逐模型默认档位（catalog 的 `reasoning.defaultEffort` 为空 → 选的是 "Default" 伪档位），真实请求体只有 `{"model":"Iceman","max_tokens":128000}`，**不带 `reasoning_effort`**；而 `guardApplies` 首行 `!reasoningExpectsThinking(body)` 直接返回 false —— `zgate.log` 13:10 那两条请求全程没有任何守卫行，就是这个原因。思考为空不是守卫失效，是守卫没上场。
- **修法（网关侧补档，不动前端 minified）**：`ReasoningGuard` 新增 `forceEffort` / `forceEffortModels`；`doForwardWith` 在发上游前调用 `injectThinkingEffort`，命中「模型在白名单 + 客户端没带 `reasoning_effort`/`thinking`」时补 `reasoning_effort: "high"`，日志写一行 `客户端未声明思考档位，按配置补 reasoning_effort="high"`。客户端显式 `off` 一律原样保留（不能只看 `reasoningExpectsThinking`，它把 off 判成「不期待思考」，照它改会把用户关掉的思考偷偷打开）。
- **为什么不在前端补**：`~/.dsh/profiles/desktop/node_modules/dsh-claude-style/lib/client.js` 在 2026-11-10 12:35 被重建，11-09 打进去的 effort 补丁随之丢失（`patch-claude-style-effort.mjs --check` 报 `NEEDS_REVIEW`，六条锚点全归零）；profile 每次重建都会重演，网关配置不会。
- **验收**：`gofmt` / `go build ./...` / `go vet ./...` exit 0；`internal/router` 14 项、`internal/config` 2 项 PASS（新增 `TestInjectThinkingEffort` 七条边界 + `TestReasoningGuardForcesEffortThenRedraws` 全链路：不带档位的请求 → 补 high → 首跳加密自动重抽 → 客户端只拿到明文思考）。隔离实例 17871 + 真上游实跑（请求体与 DSH 完全同形、无 `reasoning_effort`）：日志两行补档记录，流式 226 / 202 个 `reasoning_content` 块、801 / 714 字明文思考、最大间隔 2.9s。**线上 7871 仍是旧二进制**，需执行 `tools/zgate-lifecycle/restart-zgate.cmd`（会话内不重启长驻网关）。回退：删 `forceEffort` 两行即恢复「客户端不说就不补」。

### 守卫第四次修复：探针设时限 + 窗口期直通（2026-11-10 傍晚）

> 上一条修完触发条件后守卫确实上场了，但用户每次都要等 85 秒再手动点停止 —— 探针在等一整段加密思考，等来的结论却是「重抽也没用」。

- **真因（代码级）**：`probeReasoningStream` 只在读到**第一个正文 delta** 时才返回 `streamEncrypted`；加密那一路在思考阶段整段静默（既没有明文 `reasoning_content`，也没有正文），所以判定延迟 = 那一次尝试的整段思考时长。`zgate.log` 实测 13:20:42「重抽 1/5」与 13:21:43「2/5」两次判定之间隔 61 秒；会话 `05:20:31 turn/start → 05:21:56` 用户手动取消，整轮 85 秒 0 字节。而重抽预算花完的「最后一发」又故意用无上限探针，等于把最后一段空等也摊给用户。
- **修法一：探针设时限**（`ReasoningGuard.probeSeconds`，缺省 12）。新增 `probeReasoningStreamDeadline`：goroutine 跑原探针、`select` 到点返回 `timedOut`，调用方关流重抽（缓冲字节丢弃，goroutine 靠 `Close` 解除读阻塞）。日志：`%v 内没有可判定的思考信号（上游静默），换连接+换会话重抽 N/M`。
- **修法二：重抽预算花完就直接放行，不再探测**。守卫块改成三分支 switch —— ① 跳过期：`在「近期拿不到明文思考」跳过期内，直接放行（不再探测）`；② 预算花完：**不探测**，把上游原始流交给客户端（`io.MultiReader(提示, resp.Body)`）；③ 还有预算：按 `probeSeconds` 探测。85 秒空等的直接来源就是「最后一发还探」，删掉即消失。
- **修法三：提示按成因分开写**。探针超时只说「本次思考探测超时（上游思考阶段静默）」；只有真读到 `reasoning.encrypted` 才说「上游本次只下发加密思考」；跳过期说「该模型近期思考拿不到明文（上游加密或思考阶段静默）」。混写会让「重抽之后其实拿到了明文」的界面与日志自相矛盾。
- **修法四：跳过期不滑动续期**。`guardInSkip` 到期先清 `skipUntil` 与 `encryptedOnly` 再返回 false，否则命中一次续一次，窗口期过后永远探不回来；进跳过表的条件也从「从未见过明文」改成「自上一条明文以来连续 N 轮失败」（旧条件在真机永远进不去）。
- **配置**（`zgate.json`）：`maxRetries: 1`（窗口期内重抽几乎必然落回同一后端，实测 12:01 连续 3/3、13:20 连续 2/2）、`probeSeconds: 15`（明文流实测 ttfb 最高 13.5 秒，取 15 才不会把慢而正常的流误判成静默）、`giveUpAfter: 1`（跳过只关掉「重抽」，明文照常流，误跳代价低），`maxProbeBytes: 32768` / `giveUpForSeconds: 600` / `forceEffort` 不变。
- **验收**：`gofmt -l` 空、`go vet` / `go test -count=1 ./...` exit 0（`internal/router` 19 项；新增 `TestProbeReasoningStreamDeadlineTimesOut`、`TestProbeReasoningStreamDeadlinePassesThrough`、`TestReasoningGuardSilentStreamProbesWithDeadline`、`TestReasoningGuardSkipWindowPassesThroughFast`、`TestReasoningGuardSkipWindowExpiresAndReprobes`）；`build.py --candidate` 出 `zgate.candidate.exe`（PE Subsystem 2 / GUI，10,570,752 字节）。隔离实例 `%TEMP%\zgate-iso-probe`（假上游第 1 发先 flush 再静默 3 秒吐加密、第 ≥2 发立即吐明文）：首轮 1,263 ms 拿到明文思考（1 秒探针超时 → 重抽 1 次 → 明文，`attempts.log` 两次调用），第二轮 2 ms 直通并带跳过提示。**线上 7871 仍是旧二进制**，需执行 `tools/zgate-lifecycle/restart-zgate.cmd`（会话内不重启长驻网关）。回退：`probeSeconds` 设负数并把 `maxRetries` 调回 5 即恢复「探满再重抽」，或整段删 `reasoningGuard`。

### 移除 Gemini 反代与主力内 Gemini 模型（2026-11-10）

- **反代下线**：`zgate.json` 删 `CP` upstream 与 `cliproxyapi` child（8317），现役为 5 个 upstream（OC / WB / QD / QW / QN）+ 2 个按需 child（workbuddy :7863 / qoder :8790）；`third-party/cliproxyapi/`（含 exe 与真值配置）整体移到 `.work/cliproxyapi-removed-20261110/` 可逆保留，未删真值、未重启长驻网关。
- **主力收敛**：`tools/model_alias.py` 的 `MAIN_ORDER` 去掉 4 条 `chat:cp:gemini-*`，`MAIN_UPSTREAM_HINTS = ("deepseek",)`；`CHANNEL_RANK` / `CHANNEL_BASE` / `CHANNEL_PREFIX` 去 CP，`MODEL_META` 清空，`price_of` 删 CP 零价分支，`entry_group` 删 CP 白名单闸。
- **运行时配置**：`~/.zcode/v2/provider_config.json` / `model-alias-map.json` / `~/.dsh/profiles/desktop/cordis.patch.yml` 删 4 个 Gemini 型号与 `cp:` legacy 键，各留 `.bak-20261110-gemini-removal` 备份；`arena-leaderboard.json` 属外部榜单快照，保留。
- **Go 侧**：`main.go` / `config.go` / `keys.go` / `router.go` / `router_test.go` 去 CP 凭据、`/health` 第六段与测试段名，`go build` / `go test` / `go vet` / `gofmt` 全绿（本机分片 evidence/agent-gemini-go-cleanup.md，按仓库策略不入库）。
- **门面与文档**：README / AGENTS / docs 11 篇统一改 5 upstream / 2 child，删 `docs/MODEL-PROVIDERS.md` §4.11 Gemini 反代整节与 `docs/ARCHITECTURE.md` 的 CP 架构图行；`tools/check-project.py` 加 5 条防回退 STALE 正则、把 `8317` 反向断言翻成残留检测。历史条目（CHANGELOG / PROGRESS / archive / BENCHMARKS）、tests 夹具与 `tools/check-secrets.py` 的 Gemini key 闸门按「历史与示例」口径保留。
- **记忆**：5 篇 CP/Gemini 专述 Document 归档、2 篇现行句改写，`index.json` 44 条逐条 hash / sizeBytes 复核，`check-memory-hygiene.mjs` exit 0（本机分片 evidence/agent-gemini-memory-cleanup.md，按仓库策略不入库）。
- **验收**：`py_compile` / `check-project.py` / `check-docs.py` / `check-secrets.py` / Go 四件套 / 记忆门禁全 exit 0；未 `git add` / `commit` / `push`（用户未要求）。回退：三份 `.bak-20261110-gemini-removal` 与 `.work/cliproxyapi-removed-20261110/` 原位可逆。


### 检测性价比 / 收录价格口径正规化（2026-11-09）

- **零新增推理请求**（用户 m01007「按你的想法去做，但是要考虑最性价比的打法」）：不新增「每次跑一遍好不好用」探测；每日同步里的 WorkBuddy 价格表骤降逐个探活（`probe_alive` 打 `/v1/chat/completions`）改为默认跳过、保留旧价，实测 19 次探活对最终 39 条 `wb_pricing.json` 零影响；`docs/PITFALLS.md` §35 补「现行口径」注记（`go_model_sync.py` 体检不再发探测请求，去留只看上游清单）。
- **默认不 push**：`sync-models.ps1` 的 `[switch]$NoPush` 翻成 `[switch]$Push`，`if ($Push) { --write --push } else { --write }`；`sync-models.vbs` 计划任务入口不带 `-Push`，每天 12:00 只写报告、不自动 `git commit/push`。推送改手动显式 `powershell … -File sync-models.ps1 -Push`。`tools/check-project.py` 新增 `check_sync_policy(results)` 守这条口径（含 6 类反证）。
- **门面口径**：[docs/MAINTENANCE.md](docs/MAINTENANCE.md) §6 每日任务行按 `sync-models.ps1` 实况重写（五段命令、计划任务名、默认不 push、无峰谷任务）；[docs/TOOLS.md](docs/TOOLS.md) / [docs/SECRETS.md](docs/SECRETS.md) / [docs/MODEL-ALIAS.md](docs/MODEL-ALIAS.md) 同步标注 `--push` 仅手动。
- **收录判断与积分换算正规化**（用户 m01046/m01047「还是按照之前的逻辑，只是正规化一点」）：维持「DeepSeek 为基准、各家价格统一折算成 WorkBuddy 积分」原逻辑与全部数值，只把散落口径收成显式常量 / 单一真值源 / 自解释命名 / 注释；行为等价以 `model_alias.py --check --arena` 改前改后逐字一致为准。
- **hy4free 担心核实**（本机 `usage.json` 按 `cr` 字段重算，零请求）：`hy4free` 1871 次 `cr=0.00`、58/58 桶全零 = 真免费；标 free 却扣 6601 积分的是同族 `cn:hy4-preview-f`（HY4-Pre），已按 `CHANGELOG.md:83-84/92-93` 修为同族挂牌价 0.29 且不再进免费组。

### zgate 生命周期换版自动化 + 门面对齐 3 children / 6 upstreams（2026-11-09）

- **换版机制**：新增 `tools/zgate-lifecycle/`，正本含 `restart-zgate.cmd`（CMD 入口）→ `deploy-zgate.ps1`（`gateways/zgate/build.py --candidate` 编到 `zgate.candidate.exe` 不覆盖运行中 exe → 暂停 watchdog → `Stop-Process zgate` → 备份 → 原子替换 → `schtasks /run /tn \ModelBus-zgate-hidden` → `/health` 轮询 → 恢复 watchdog → 失败回滚）、`install-lifecycle.ps1`（把安全脚本部署到 `%LOCALAPPDATA%\ZCodeGateway` 并校正两个计划任务动作）。`swap-zgate.ps1` / `start-zgate.bat` 改为兼容薄包装，不再 `Start-Process`。
- **自启收敛**：现役为两个计划任务 `\ModelBus-zgate-hidden`（AtLogOn, Interactive/Limited，`wscript //B //Nologo launch-zgate.vbs` → `start-zgate-nw.ps1` 起普通 `serve`）与 `\ModelBus-zgate-watchdog`（PT1M，`ensure-zgate.vbs` → `ensure-zgate.ps1`）；旧 `\ModelBus-zgate` 任务、HKCU Run daemon、Startup 快捷方式均已移除。
- **父链实测**（`PROGRESS.md:2586/2588-2589`）：`DETACHED_PROCESS` / `zgate serve -tray` 不保证调用方整棵进程树被回收时存活（`cmd /c`、`Start-Process` 结束后 2s 内子进程消失）；只有计划任务父链能脱离 CMD/DSH 会话树（跨 run_code 仍 `/health` 200）。
- **架构对齐**：`gateways/zgate/zgate.json` 监听 `127.0.0.1:7871`，6 个 upstreams（OC / WB / QD / QW / QN / CP，CP=CLIProxyAPI `http://127.0.0.1:8317/v1`，`keyEnv=CLIPROXY_API_KEY`）、3 个 children（workbuddy 7863 `/panel/`、qoder 8790 `/ping`、cliproxyapi 8317 `/v1/models`）。环境变量只写变量名：`QWEN_API_KEY` / `QWEN_BASE` / `QD_API_KEY` / `CLIPROXY_API_KEY` / `QINIU_API_KEY`，值一律从环境变量读。
- **热加载边界**：`POST /admin/reload` 热加载 `zgate.json` 的策略 / 空闲 / 窗口 / 上游 base / 凭据，并按 `keys.Load` 六通道 + `ApplyConfig(children)` + `setRuntime` + `aliases.Reload()` 更新运行时（`gateways/zgate/internal/router/router.go:963-986`）；监听地址、新增子进程、alias map 路径与 Go 代码变更仍需 `tools/zgate-lifecycle/restart-zgate.cmd` 受控换版。
- **P1/P2 修复**：门面 / 规则 / 记忆文档逐条精确对齐真实架构，新增 [docs/ZGATE-LIFECYCLE.md](docs/ZGATE-LIFECYCLE.md) 并同步 `docs/README.md` 索引；`AGENTS.md` 增「改完 Go 代码自动跑 `restart-zgate.cmd`、严禁会话内 `Start-Process` / `cmd /c` 拉起」硬规则。
- **验证**：`python tools/check-docs.py` exit 0（链接 / 锚点 / 引言块 / 孤儿全通过）；本轮不重启 / 不停止网关，部署由 lead 执行。回退：`git revert` 本提交；二进制回滚点由 `deploy-zgate.ps1` 的备份保留。

### 选型：显示名去尾缀、漏模型的三种机制（2026-11-06）

- **显示名不再造后缀**（用户口径：只有真不同的模型或无法合并时才加尾缀）。
  `abbreviate()` 兜底不再把 `flash` / `preview` 缩成 `-Fs` / `-Pre`；
  `hy4std` → `HY4`（回包 `model` 本就是 `hy4`，`-Std` 是 WorkBuddy 档位）；
  `hy4-preview` / `-f` / `-ctrl` / `-exp1..3` / `-x` 统一 `HY4-Preview`；
  `kimi-k2.8-preview` → `Kimi-K2.8-Preview`、`step-5-preview` → `Step-5-Preview`、
  `deepseek-v3-2-volc` → `DeepSeek-3.2`。
- **漏模型的三个真机制**（其余「上游 39 个只用 11 个」是白名单设计的必然，不是 bug）：
  ① 裸名去重吞掉同型号的其他渠道（已修，`explicit_channel`）；
  ② 名单点名的跳查不到价 → 静默剔除（2026-11-06 `chat:Qwen3.8-Max` 整条兜底消失、
     日志无提示）→ 新增 `_UNPRICED_HOPS` 汇总「具体跳」；
  ③ 显式渠道条目的跳命中不了名单（`_picked` / `_pick_rank` 只比裸 `<协议>:<上游>`，
     主力判定与名单名次双失效）→ 新增 `hop_specs()`，两处共用。
- 补 `classify()` 的 `oc:` 前缀分支：原来只有 `cn:` / `global:` / `qoder:` / `qwen:` /
  `qn:`，写 `chat:oc:qwen3.8-max` 会落兜底、upstream 带着 `oc:` 当型号名去查价。
- `MAIN_ORDER` 的贵备份拆成 `chat:qoder:Qwen3.8-Max` + `chat:oc:qwen3.8-max`：前者是
  真主链（QD 单跳），后者补 OC 兜底意识（当前 OC_PRICES 缺 `qwen3.8-max` 价，只在
  stderr 留 `WARN: 因缺价未收录 … 具体跳：OC:qwen3.8-max`，补价后自动成兜底跳）。
- **Qoder 免费窗口关闭**：`/v1/models` 从 `price 0.0 / valley 0.0` 变
  `price 0.04 / peak 0.1 / valley 0.04`（`is_free` 仍 true，字段自相矛盾），实测
  `usage.billable` `false` → `true`（`credits` 0.1638）。Qwen-3.8-Flash 因此从免费组
  落到省钱组（0.03），链首仍是 QD（0.03 < OC 0.09）。回归断言不再写死 0.0。
- 回归：新增 `tests/test_model_alias_naming.py`（尾缀规则 4 条 + `oc:` 前缀 3 条）；
  `tests/test_model_alias_price.py` 的主力用例改用 OC 跳构造。共 56 passed。
- 回退：`git revert` 本提交后跑 `python tools/model_alias.py --slot auto --apply --arena --scores`；
  只想恢复旧显示名就把 `ABBR` 的 `hy4std` / `hy4-preview*` 键改回 `HY4-Std` / `HY4-Pre`。

### 选型：Qoder 免费 Qwen3.8-Flash 进链（2026-11-06）

- 事实：Qoder 官方目录里 `Qwen3.8-Flash`（key `qfmodel`）`price_factor 0.0 / is_free true`，
  `/v1/models` 回 `price 0.0 / peak 0.1 / valley 0.0`；经 8790 实测 `usage.billable=false`，
  账号额度 `remain 1400 / used 0` 不变。白天按 peak 0.1 计（×0.86 ≈ 0.086），仍低于 OC 的 0.09。
- 修 `tools/model_alias.py` 两处：`whitelist_items()` 给条目打 `explicit_channel`
  （spec 显式写了 `qoder:` / `cn:` / `global:` 等），main 里显式渠道按 `(渠道, 裸名)`
  去重 —— 原来只按裸名，`Qwen3.8-Flash` 已被 OC messages 条目占位，QD 免费跳被静默吞掉。
- `MERGE_ACROSS_PROTOCOL` 与 `MERGE_FREE_GB` 加 `qwen3.8-flash`（QD chat + OC messages
  并成一条链，避免 `Qwen-3.8-Flash-Msg` 分身）。
- 结果：`Qwen-3.8-Flash` = `QD:Qwen3.8-Flash@0.00 -> OC:qwen3.8-flash@0.09 -> OC@机场`，
  免费组 6 条、省钱组 7 条；`--check` 无漂移，经 7871 实测日志 `model=Qwen-3.8-Flash -> QD:Qwen3.8-Flash (1/3)`。
- 回归：`tests/test_model_alias_qd_free.py`（5 条）。回退：删 `LOW_ORDER` 的
  `chat:qoder:Qwen3.8-Flash` 与两个 `MERGE_*` 里的 `qwen3.8-flash`，重跑 `--apply`。

### 选型修三处硬伤：HY4 归位、探活真正生效、渠道排序表（2026-11-06）

- 起因（三个实锤，共同点是「看起来在自动选型，实际是死代码」）：
  1. 竞技榜上我们手里最强的模型是 `hy4`（建模 #8、静态网页 #10、0.29 积分），却被
     「省钱档 ≤0.11」的价格闸裁掉，配置里留下的是同族第 58 名的 `hy4-preview`。
     只把 `chat:cn:hy4std` 写进名单也不生任何条目 —— 条目只从 `provider_config`
     与池子文件来，白名单只管排序，不管建档。
  2. `model_alias.py --probe-file` 从写出来那天起就没被传过：`sync-models.ps1` 里
     连 `model_probe` 都 grep 不到。于是 2026-10-27 就下架的
     `moonshotai/kimi-k3-free` 一直占着免费组位置，每次调用 502。
  3. `cn:hy4-preview-f` 的 `credits` 是空字符串、`list_rate` 是 0，被判成免费；
     历史 2420 次请求实际扣了 6601 积分。
- 改动：
  1. `tools/model_alias.py`
     - `MAIN_ORDER` 首位加 `chat:cn:hy4std`；新增 `whitelist_items()`：白名单点名但
       配置里没有的型号直接从价格源建条目，按**裸名**比对（否则 `chat:Qwen3.8-Max`
       这种不带渠道前缀的写法会被猜成 OC，与已有的 QD 条目重名）。
     - 新增 `CHANNEL_RANK = {WB:0, OC:1, QD:1, QW:2, QN:3}`，取代原来「WB 布尔 +
       TAIL_HOPS 布尔」两维排序键；同 rank 内保留 QD 先于 OC 的旧顺序以保证等价。
     - `wb_prices()` 重写为两遍：`credits` 权威，缺则用 `list_rate`，两者都缺时用
       同族挂牌价回填并 WARN —— `hy4-preview-f` 由 0.00 变 0.29。
     - 新增 `write_quota_windows()`：三条额度窗口（QN 限免 2026-11-30 / QW 每模型
       试用池 2026-12-15 / QW ¥300 预付 2027-10-28）写到
       `~/.zcode/v2/quota-windows.json`，剩余 ≤30 天在 stderr 告警。
  2. `tools/model_probe.py`：每条结果补 `resp_model` / `quota_model` / `credit`
     三个身份字段，并写 `checked_at`。此前只写 `ok_at`，非 ok 的记录没有任何时间戳，
     `_fresh_probe` 会把整份结果判成过期按「未知」处理 —— 等于死型号永远删不掉。
  3. `tools/sync_report.py`：报告新增「性价比漂移」（读 `model-scores.json`，只列
     intel<85 或 value<1.0）与「额度窗口」（读 `quota-windows.json`，≤30 天 ⚠️、
     过期 ❌）两段，文件缺失时整段不出现。
  4. `sync-models.ps1`：第四步第一轮 apply **之后**接探活，`--probe-file` 才第一次
     真正被传（顺序不能颠倒：本轮新补进配置的型号要先有探测记录，否则会被当成
     `not probed` 直接跳过）；探活可用率低于一半时不据此摘模型，避免网关整体故障
     时把清单删光。漂移检查改用与 apply 同一组参数（`--arena --scores --probe-file`），
     不再天天报「MiMo-2.6-Flash 主力 → 省钱」这种参数不对称造成的假漂移。
- 结果：18 个模型（主力 5 / 免费 5 / 省钱 8）。HY4（当时显示名还是 HY4-Std）进主力第一位，经 7871 实测
  200（0.92s）；Kimi-K3 被探活摘除，调用从 502 变成 400 未知模型。
- 回退：`python tools/model_alias.py --no-scores --no-arena`；要关掉探活就删
  `sync-models.ps1` 里「模型探活」那一段。

### 选型接上性能：竞技榜分数进每日同步 + 每厂商配额（2026-11-06）

- 起因：`docs/BENCHMARKS.md` §5.4 定义了三档换算，但 `model_alias.py` 零引用 ——
  选型只看人工白名单 + 价格阈值。同时每日同步从不传 `--arena`，`arena-main.json`
  停在 2026-10-23 的 5 个候选，文档写「主力 7 个」而实际只有 2 个。
  另一个实锤：`sync_report.py` 的概览把组名写死成「主力/免费/低耗/高耗」，真实组名是
  「主力/免费/省钱」，于是 10 条省钱组模型从概览里凭空消失、合计 9≠19。
- 改动：
  1. `tools/sync_report.py` —— 组名改为 `GROUP_NAMES = ("主力", "免费", "省钱")`，
     概览补「其他」兜底与合计校验（`合计 N / 清单 M`，对不上显式告警）；
     终端摘要同步改为按 `GROUP_NAMES` 生成。
  2. `sync-models.ps1` —— 第四步新增「竞技榜刷新」
     （`arena_leaderboard.py --refresh --force --write`）与「竞技榜分数」
     （`model_score.py --write --quiet`），生成器改带 `--arena --scores`；
     两步都 `-Soft`，失败只降级不阻断。
  3. 新增 `tools/model_score.py` —— 把 `arena-main.json` 折算成
     `~/.zcode/v2/model-scores.json`（`CHANNEL|upstream` → intel / price_idx / value，
     带 `basis` 写明基准）。同时 `arena_leaderboard.py` 落盘补 `near` 字段，
     让「接近但未入选」也参与折算。
  4. `tools/model_alias.py` —— 新增 `--scores [路径]` / `--no-scores`、`load_scores` /
     `score_of_entry` / `pick_scores_dropped`（**只降不升**，无分数的条目不动）、
     `VENDOR_QUOTA = 2` 与 `pick_quota_dropped`（每厂商省钱组最多 2 个，
     版本高者优先、同版本贵者优先；免费组不占配额）。
  5. `gateways/zgate/internal/router/router.go` —— 新增 `quotaCooldown = 24h` 与
     `quotaExhausted`：额度烧光类的 4xx（`Free quota exhausted` / `AllocationQuota` /
     `insufficient_quota` …）按一天冷却，不再每 30 分钟重撞一次；普通死跳仍是 30 分钟。
- 效果（2026-11-06 22:50 实测）：主力 2 → 4（`MiMo-2.6-Flash` 99.8%、`Space-Bunny` 98.8%
  重新进窗口），省钱 10 → 7（`MiMo-2.6-Pro` 0.13 超价且性价比 0.81 被裁，其余靠价格闸），
  经 7871 探活 `MiMo-2.6-Flash` / `Space-Bunny` / `HY3-X` 全 200。
- 回退：`model_alias.py --slot auto --apply --no-scores --no-arena`，或删
  `~/.zcode/v2/model-scores.json`。口径全文见 `docs/BENCHMARKS.md` §9。

### zgate：地区受限 403 冷却该跳（2026-11-06）

- 起因：请求面板上 Beam 一片「403 Rejected」，与零星 200 交替。实测 alias map 里
  `Beam` 的链是 `[beam-free 直连, beam-free 机场(proxy)]`，直连出口永远
  `403 RegionError: This model is not available in your country`、机场出口 200；
  `zgate.log` 尾部 4000 行里 hop1=367 / hop2=367 / `403 fallback`=359 —— 每个请求都先
  白撞一次直连 403 再回落。原因是 `regionBlocked()` 只让 `chainAccept` 返回 false（回落），
  从不冷却该跳，于是同一跳每次都要重试。
- 改动（`gateways/zgate/internal/router/router.go`）：新增 `regionCooldown = 30m`；
  chat 路径 `accept` 闭包与桥接路径都改为「地区受限 403 **且** 链里存在同 channel + 同
  upstream 的带 proxy 孪生跳（`proxyTwinAfter`）→ 冷却这一跳 30min」。冷却键 `hopKey`
  带 proxy，所以机场孪生跳是另一个键，兜底不会被吃掉；单跳链或无同上游出口跳时**不冷却**，
  否则唯一一跳被冷却会让后续请求连尝试都省掉，把真实 403 变成即时
  `502 all upstreams failed`。
- 同时修 `main.go` 无参数启动（双击 exe）时 `os.Args[2:]` 越界 panic —— 现在正常打 usage
  或报缺配置。
- 测试：`internal/router` 新增 `TestRegionBlocked403CoolsTheDirectHopOnly`（复刻 beam
  实况：直连 403 RegionError → 孪生跳 200，第二个请求必须跳过直连）与
  `TestRegionBlockedDoesNotCoolALoneHop`；`go vet ./...` 与 `go test ./...` 全通过。
- 覆盖面：11 个 OC 型号逐个探过，只有 `beam-free` 是「直连 403 / 机场 200」可修；
  `gpt-6-luna`、`muse-spark-1.3-contributor` 机场同样 400（上游整体不收这个地区），
  其余 8 个两边都 200。因此**不改** `tools/model_alias.py` 的链序 —— 静态清单只认得
  beam，硬排会把两个坏型号的 403 提前；运行期学习更准。
- 生效：候选二进制 `%LOCALAPPDATA%\ZCodeGateway\zgate-0.3.0-cand.exe`，需要用户执行
  `swap-zgate.ps1` 受控重启后生效（长驻网关不由会话重启）。

---

### zgate：桥接流式不再限制在链尾跳（2026-11-06）

- 起因：用户问「输出速度 TPS 还有优化空间吗」。实测经 7871 连打五个模型（stream=true, max_tokens=200）：
  Beam ttfb 0.670s / total 4.280s（88 条 data 行）、GLM-5.3-Flash 1.353s / 5.514s（203 条）、
  MiMo-2.6-Pro 1.788s / 8.354s（61 条）、Iceman 2.594s / 4.787s（199 条），而
  **Claude-Haiku-5.5 ttfb 1.739s / total 1.739s、只有 4 条 data 行** —— 首字节等于总耗时，整段被缓冲。

- 根因：`router.go` 桥接分支把流式门控写成 `wantsStream(body) && index == len(t.Chain)-1`。
  alias map 里所有 OC messages 型号（Claude-Haiku-5.5 / Qwen-3.8-Flash / Muse-Spark1.3 / GPT-6-Luna / Beam）
  都是 2 跳链（直连 + 机场孪生），首跳永远不是链尾 → 走桥接时被强制非流式，要等上游整段生成完才写回。
  chat 协议的跳没有这个问题（`doForwardWith` 一直是边收边发：32KB 读缓冲 + 每次 Read 后 Flush）。

- 改动（`gateways/zgate/internal/router/router.go`）：门控改为 `streaming := wantsStream(body)`。
  安全性不变：非 2xx 在任何字节写出之前就以 `Result` 返回，回落逻辑照旧；200 之后断流本来也回不了落。
- 顺带修（`gateways/zgate/internal/bridge/bridge.go`）：非流式路径的空闲看门狗用的是流式那档 `DefaultIdle = 30s`。
  非流式上游只有整段生成完才吐字节，生成超过 30 秒的正常回答会被误判成 `upstream silent ... 504`；
  新增 `DefaultIdleNonStream = DefaultTimeout`（120s），让总超时当唯一硬闸。
- 测试：新增 `gateways/zgate/internal/router/stream_test.go` —— `TestBridgeStreamsOnNonTailHop`
  （首跳上游先吐 A 再阻塞，客户端必须在上游完成前收到第一个 chunk）、
  `TestBridgeRegionBlockedFallsBackWithStream`（流式上行撞 403 RegionError 仍要回落孪生跳并冷却）。
- 候选二进制 md5 `c96615631f3a52baf5adaa1a17375064`，等用户执行 `swap-zgate.ps1` 生效。
- 回落护栏：`attemptChain` 的回落条件加 `!cw.written &&`。`bridge` 目前在「已写过 chunk」之后
  一律返回 `Status: 200`（`bridge.go` 的 `if !emitted` 之外分支），所以这条分支今天是防御性的；
  留着是为了将来桥接改状态码时不会把第二个响应体写进同一条 SSE 流。
- 测试补第三条：`TestBridgeNoFallbackAfterStreamStarted`（首跳写出一个 delta 后发 RST 断链，
  客户端必须只看到「流内报错 + 收口」、下一跳零命中、状态码仍 200）。
- 现网已于 21:10:28 换上流式修复版 `c9661563…`（`gateways/zgate/zgate.exe`，上一版存为
  `%LOCALAPPDATA%\ZCodeGateway\zgate.exe.bak-20261106-211027`）；同题实测 Claude-Haiku-5.5
  `ttfb 2.227s / total 3.676s`、46 条 data 行（改动前 `1.739s / 1.739s`、4 条）。
- 含回落护栏的新候选是 `f66ef8f97f992caad1eb248ae928cdde`（`%LOCALAPPDATA%\ZCodeGateway\zgate-0.3.0-cand.exe`）。
  护栏分支今日不可达，与现网行为等价，等下次换二进制时一并生效，无需为此单独重启网关。

## [0.6.0] — 2026-11-06

### WB 永远是第一消费来源（2026-11-05）

- 起因：15:44 实测 7871 的 `DeepSeek-4.1-Flash` 全部落到 OC（响应里带
  `opencode.billing_source=go` 与 `X-Opencode-Log-Id`），`GET /health` 显示
  `children.workbuddy.state=stopped`（policy=ondemand + 窗口制，当前不在窗口内），
  7863 无人监听；alias map 的链是 `OC -> OC -> WB -> QW` —— 这是当天 12:00 用一个
  `DEMOTE_HOPS` 集合为躲 6004 模型级限流手工降级的结果，不是 workbuddy 挂了。
- 定调：WB 的额度是**优先消费**对象，链序不允许被任何临时开关改动，也不看价格。
  排序键第一维改成 `WB_FIRST_CHANNELS`（`tools/model_alias.py`），第二维才是
  `TAIL_HOPS`（QW 一年期预付尾跳），其余按价格 / 前缀 / 渠道 / 名称稳定排序。
- 改动：`DEMOTE_HOPS` 常量与排序分支**整段删除**（不是清空），限流改由 zgate
  逐跳回落处理；`~/.zcode/v2/model-alias-map.json` 里 `DeepSeek-4.1-Flash` 的链改回
  `WB -> OC -> OC -> QW`（zgate 按 mtime 每请求热加载别名表，未重启长驻网关）；
  `~/.dsh/tools/demote-throttled-hop.mjs` 已替换为拒绝执行的废弃桩，原实现留档
  `~/.dsh/backups/demote-throttled-hop.mjs.disabled-20261105`。
- 测试：`tests/test_model_alias_demote.py` 换成 `tests/test_model_alias_hop_order.py`，
  钉住四条：WB 等价比价都打头、贵 3 倍仍打头、QW 与机场孪生跳仍在链尾、
  `DEMOTE_HOPS` 属性必须不存在；另加磁盘守卫 —— 读真实 alias map，任何含 WB 跳的
  型号 WB 不在第 0 位即红。全量 44 用例通过。
- 实测：15:45:11 zgate 按需拉起 `wb2api.exe`（pid 40640），请求改走
  `WB:cn:deepseek-v4.1-flash` 并返回 200；生成器 dry-run 的 19 条链里 9 条含 WB，
  9 条全部 `chain: WB:...` 打头。
- 回退：把 `WB_FIRST_CHANNELS` 从排序键里拿掉（等于让 WB 回到按价格排序）；或直接用
  备份 `~/.zcode/v2/model-alias-map.json.bak-wbrestore-*` 覆盖别名表。

### 门禁脚本 GBK 控制台自毁修复（2026-11-04）

- 两个门禁脚本同时补 `if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(errors="replace")` 兜底，与其余仓口径一致（不再单靠 ASCII 约束）。
- `tools/check-docs.py` / `tools/check-secrets.py` 的结论行 `✓` / `✗` 改 ASCII
  `[OK]` / `[FAIL]`：Windows GBK 控制台下 `print("✓")` 抛 `UnicodeEncodeError`，
  两个提交门禁脚本即便检查全过也以退出码 1 结束；`python -I` 会忽略
  `PYTHONIOENCODING` / `PYTHONUTF8`，环境变量救不回来，只能改脚本
- 机制与验证口径见 [docs/PITFALLS.md](docs/PITFALLS.md) §36

### DeepSeekHarness 模型自动同步（2026-11-04）

- 新增 `tools/dsh_sync.py`：读取 ZCode 最终三组，重写 DeepSeekRuntime
  `~/.dsh/profiles/desktop/cordis.patch.yml` 的 `llm-pi-ai` 段；保留其他 patch
  条目与非 `zcode-*` provider，`reasoningLevel.map="{}"` 的模型不写 reasoningEfforts
- 使用默认 ZCode 配置路径时，`tools/model_alias.py --apply` 会在写完后自动调用它；
  DSH 未安装跳过，失败只告警不阻断；`--config` 沙盒不投影，`--no-dsh` 可关闭
- 日常 12:00 自动化、`docs/TOOLS.md`、`docs/MAINTENANCE.md` 同步更新

### WorkBuddy2API 升到 v2026.11.4.1120（2026-11-04）

- 上游 `40d98f9 → e6dd088`（27 个提交），本地保留 `.gitignore` / `main.go` 脱敏两处补丁；
  `go test ./...` 全通过后重编并替换 `wb2api.exe`
- 面板目录回到 20 条：新增 `cn:hy4free`（0 分，显示 `HY4-Free`，进免费组）与
  `cn:hy4std`（0.29，未收录）；旧表 17 个仍可调型号经探活保留
- `tools/model_alias.py` 的显示名表补 `hy4free` / `hy4std`，避免 UI 出现全小写 `hy4free`
- `providers/workbuddy/workbuddy_fetch_pricing.py` 最终 `✓` 改 ASCII `[OK]`，
  避免 GBK 控制台在写盘后抛 `UnicodeEncodeError`

### 依赖口径如实化与门面脚本提示（2026-11-04）

- README / docs/TOOLS.md 标明 `tools/make_social_preview.py` 需 numpy + Pillow
  （此前写「只用标准库」，与脚本硬依赖矛盾）
- 该脚本缺依赖时给出安装提示，不再裸 traceback

### P3 清理（2026-11-04 审查遗留项）

- `tools/sync_report.py` / `tools/check-secrets.py` / `providers/workbuddy/workbuddy_probe_zcode.py`
  的 subprocess 调用补 `encoding="utf-8", errors="replace"`（换机或 UTF-8 模式失效时，
  中文输出不再 UnicodeDecodeError）
- `docs/PITFALLS.md` §71 删掉从未入库的测试文件引用，验证方式改为在线实测
- `docs/TOOLS.md` zgate 行 Qoder 策略 `always` → `ondemand`（与 zgate.json 一致）
- `memories/opencode-go-zcode-models.md` 更新为现行定时任务（12:00 / `automation-3e2f8a53-*`）

## [0.5.0] — 2026-11-01

### 守卫脚本 bug 奇偶同步 + 维护（2026-11-01）

- `tools/check-secrets.py` 对齐 ClientTriage `c3a3952` 已修的漏报 ——
  `re.search` 改 `finditer`（同一行多个命中全查）、`--all` 遵循 `.gitignore`
  （修复前 `--all` 因 .workbuddy 噪音 exit 1）；分叉差异保留，加出处头注释（`079f79d`）
- `tools/check-docs.py` 对齐已修的功能性 bug —— BOM 首锚点、跨盘符 relpath、
  引言只认头部（ZAIM ③ 有意不落地：守卫变体无此误报且按需补算会扫上游
  clone，出处头注释写明）（`9d9ac53`）
- 文档脱敏 —— 运维示例与守卫文档示例改占位（`cf3b403` / `aee3a22`）
- 维护 —— 收尾大扫除（清 __pycache__、过期定价备份与中间版报告，`10a4301`）；
  二进制备份口径收紧为「现役 + 最新回滚点」（`3ff6923`）；
  CI 修 gofmt 连续挂检查（`dbb9b83`）

### zgate 安全微优化：hopKey 脱敏、chat 504 冷却对齐、idleReader 竞态修复（2026-11-01）

落实 09908d8 增量审查 notes 里挂起的小项；不重构状态机，504 冷却为 notes 明示的
「对齐语义」项：

- 修 1（日志脱敏）：`router.go` 新增纯函数 `maskProxy` + `hopKeyForLog` —— 日志与
  错误回显里 `hopKey` 的 proxy 段对 userinfo 做掩码（`http://user:***@host:port`，
  保留用户名）；解析不了的串给固定占位不回显原文。冷却表键**保持原始串**（掩码串
  会让只差口令的两跳共用冷却键），5 处日志点全部切换。当前配置是无凭据 LAN 地址，
  本项为「换成带凭据出口」预埋
- 修 2（504 冷却对齐）：chat 链路径（`attemptChain` 的 accept）收到 504 现在也把
  该跳冷却 5min，与桥接路径的 `coolBridgeFailure` 对齐 —— 静默僵死的 chat 上游
  不再被链上后续每个请求先撞一遍再回落
- 修 3（idleReader 竞态）：看门狗触发改为按「距上一个字节是否空满 idle」判定
  （`last` 时间戳 + 与 `timer.Reset` 共用同一把锁），字节在窗口边缘到达时按剩余
  窗口重排而不是误杀 —— 旧实现两边无锁，这个边界会把还在传输的流误判成 504
  静默，链路白付一次 5min 冷却
- 内存面评估（notes 结论）：流式路径全链路流式（32KB 拷贝缓冲、错误体 8KB 截断），
  无响应体全量驻留；桥接非流式的整段解析属必要驻留；`bufio.Scanner` 初始缓冲
  1MB→64KB（每流式请求省 ~1MB 急切分配，8MB 行上限不变）；`sync.Pool` 类优化
  非热点，不值得做
- 测试：新增 `TestMaskProxyMasksUserinfo`（有凭据 / 仅用户名 / 无凭据 / 畸形）、
  `TestHopKeyForLogMasksCredentials`、`TestChatPath504CoolsTheHop`（504 → 冷却 →
  下一请求直接跳过该跳）、`TestIdleReaderTripsOnSilence` /
  `TestIdleReaderFlowingDataStaysAlive` / `TestIdleReaderBoundaryByteIsNotKilled`
  （边界用例旧实现必挂，6 连跑稳定）
- `go vet ./...` + `go test ./... -count=1` 全绿；`tests/test_model_alias_price.py`
  10/10；`python gateways/zgate/build.py` 重建并过 PE 子系统校验（GUI）。
  **zgate.exe 是构建产物（不入库）：本轮已重建，运行中的网关仍是旧镜像，需人工
  重启后才生效**

### 增量审查修复：退避预算互吃、空出口残留、死代码 attemptBridge（2026-11-01）

对 10-26 后三笔 zgate 网络提交（f8084ec / 502fc16 / 3dcb126）做增量审查发现的
三处明显错误，均为让代码回到其自身文档口径，不改设计：

- 修 1（退避预算互吃）：`doForwardWith` 用循环下标 `attempt == 0` 判「429 是否已
  就地退避过」，而传输层重试的 `continue` 同样会自增下标 —— 先传输失败一次的
  请求再吃 429 时直接进 45s 冷却 + 回落，吃不到 700ms 就地退避，违背
  PITFALLS §34「`txRetry` 与 429 互不吃预算」的口径。改为 `txRetry` / `retry429`
  两个独立计数
- 修 2（空出口残留）：`WithProxy(ctx, "")` 原样返回 context，链上「机场跳后面跟
  直连跳」时直连跳会沿用上一跳的机场出口，违背 `alias.Hop`「空值按直连走」的
  约定。改为无条件覆盖（空值即直连）。当前生成器把机场孪生跳固定在链尾，
  此问题属潜伏契约违背，线上暂未触发
- 修 3（死代码）：`attemptBridge` 自 893c63d（routeChain 改按每跳协议派发）起
  无任何调用方，但 3dcb126 仍在给它打补丁 —— 它是 `attemptChain` 的第二份
  状态机拷贝，继续留着必然再漂移。整体删除，行为零变化
- 测试：新增 `TestTransportFailureDoesNotConsume429Backoff`（EOF → 429 → 退避
  重试 → 200；无就地退避时一跳链直接 502）；`TestProxyOfRoundTrip` 断言改为
  「空出口必须覆盖外层」；更新 `tests/test_model_alias_price.py` 的链长断言
  （502fc16 起链尾带机场孪生跳，该测试 10-30 起本地跑必挂）
- `go test ./... -count=1` 全绿；`python gateways/zgate/build.py` 重建产物并过
  PE 子系统校验（GUI）。**zgate.exe 是构建产物（不入库）：改动需重建 + 重启
  网关进程才生效**

### 传输层瞬时失败重试同一跳（2026-10-31）

- 事故：机场节点到 opencode.ai 的路径对大包短暂黑洞（POST ≥5 KB 挂 5s，GET 正常），
  zgate 把 `client.Do` 的 EOF 直接交给下一跳，一跳链（`Beam`）没有下一跳 → 502
- 修：`doForwardWith` 里传输层错误先重试同一跳一次（300ms，`txRetry` 与 429 的
  `attempt` 分开计数）；桥接路径同样重试，但只在 `!cw.written` 时做，避免重复输出
- 只重试 `EOF / TLS handshake timeout / connection reset / i/o timeout / broken pipe /
  connection refused`；普通 5xx 不重试（上游可能已计费）
- 新增 `TestTransportFailureRetriesSameHop`（hijack 后不写字节即断 = 复刻 EOF）、
  `TestTransportFailedMarkers`；PITFALLS §34

### 每跳自己的出口（`chain[].proxy`）+ 地区受限自动换机场（2026-10-30）

- alias map 的每一跳新增可选 `proxy` 字段：同一 upstream 可以在链里出现两次、只差出口。
  `alias.Hop` 加 `Proxy`，zgate 用 `EgressRouter`（按请求 context 挑 `*http.Transport`）
  实现，`bridge.Forward` / `doForwardWith` 签名都不动
- **地区受限的 403 现在会换跳**：新增 `regionBlocked()`，认
  `unsupported_country_region_territory` / `RegionError` / `not available in your country`；
  `chainAccept` 与两条桥接回落分支都接上 —— 此前 `responses`/`messages` 模型
  （如 `gpt-6-luna`）的 403 会原样返回给客户端，链上的兜底跳永远轮不到
- 冷却键 `hopKey` 带上 proxy：直连跳与机场孪生跳是两个键，直连的 403 不会把兜底跳一起冷却
- `tools/model_alias.py`：新增 `AIRPORT_PROXY`（默认 `http://10.0.0.1:7896`）与
  `with_airport_fallback()`，给每条 OC 直连跳在**链尾**补一条同上游的机场孪生跳；
  重新生成后 18 个条目里 11 条的链变长（DeepSeek 变成 cn → OC → QW → OC@机场）
- 文档：`MODEL-ALIAS.md` §3.0（新字段与排序理由）、`PITFALLS.md` §33（403 不回落）
- 实测：直连 403 → `(2/2)` 机场跳 200；`Claude-Haiku-5.5` / `DeepSeek-4.1-Flash` 全走直连

### 上游僵死 30 秒可判定 + 429 先退避再摘跳（2026-10-29 续）

- **空转看门狗（修 Conatus「两分钟没响应」）**：桥接上游接受连接后一个字节都不发时，
  原来只能干等 `DefaultTimeout`(120s)。新增 `DefaultIdle = 30s`：连续 30 秒无数据
  就断开并返回 `504 upstream_timeout`，流式与非流式两条路径都接上了
- 首块 `role` 改为**延迟到真有数据时才写**，这样超时前没写过任何 SSE，
  路由仍能返回真实错误码或回落，而不是留下一个挂起的空流
- **429 先退避再摘跳**：收到 429 先就地退避 700ms 重试同一跳（限流窗口通常很短），
  仍 429 才把该跳短冷却 45 秒；桥接上游静默超时冷却 5 分钟；死跳仍 30 分钟
- 新增 `TestForwardStreamIdleTimeout`：静默上游必须在空闲上限内返回 504 且零 chunk
- 实测依据：今天 429 来自 WorkBuddy 首跳 182 次、OC 仅 16 次 —— 每次请求都先撞
  WB 再回落，突发时两跳同时 429 就整链失败，用户只能手动重试

### 文档：补「模型自述不可信」口径（2026-10-29）

- 新增 `PITFALLS.md` §31：自述是生成结果不是元数据；集合体/中转模型没有单一作者，
  以 `GET /models` 的 `id` / `owned_by` 与结算账目为事实
- `QINIU.md` §2 改为官方口径 —— Conatus 是**多种模型的集合体**，其「我是
  deepseek-v4.1-flash」的自述不作证据；并记它与频率限制（连问即 429）

### 桥接全链路流式 + 组内排序收归人工名单（2026-10-29）

- **首字慢的根因修复**：`zgate` 协议桥调上游时写死 `stream: false`，整段生成完
  才合成一个 chat SSE chunk —— 实测 Conatus 12.06s 才收到第一个（也是唯一的）
  chunk，而原生 chat 模型 0.98s 就开始逐 token。现在客户端要求流式时，桥接器
  按 `stream: true` 请求上游、边收边转（文本 / `thinking` / `tool_use` /
  Responses `function_call` 增量都各自翻译）
- 只有**链尾跳**走流式：前面某跳失败还要能回落，写出的半截 SSE 收不回来；
  非尾跳仍整段缓冲。上游在任何 chunk 之前报错时，用 JSON 把真实错误码回给
  客户端（`finishBridge` 按 `cw.written` 判定），不再留下挂起的空流
- 新增桥接测试：流式文本、流式工具调用（`finish_reason: tool_calls`）、
  上游报错不吐 chunk 三条用例
- **组内排序改由人工有序名单决定**：`MAIN_ORDER` / `LOW_ORDER` 是唯一权威，
  `MAIN_IDS` / `LOW_PICKS` 由它们派生（原来两份字面量各自维护，易漂移）；
  旧实现按「厂商最低价」排序，把便宜的顶到前面、把 MiMo 挤到列表末尾
- **省钱组收紧**：每厂只留 1–2 个代表作（小米 = MiMo-2.6-Flash + Pro），
  前旗舰 / 上一代（MiMo-2.5、GLM-5.2、Qwen-3.7 等）不再收录；命中 `LOW_PICKS`
  即进组、不再受 `LOW_MAX` 上限约束
- **修 `price_of` 的七牛渠道级 0 价**：原来整个 `QN` 渠道一律返 0，将来播种任何
  付费模型都会被误当免费；现在只对 id 以 `-free` 结尾的模型返 0
- **修 `go_model_sync.py` 误删七牛模型**：`probe_targets` 原来只跳过 WB/QD，
  把 `qn:` 种子当 OpenCode 模型探测 → 400 → 被当死模型删掉（Conatus / Kimi-K3
  曾被整条清掉）。现在跳过任何非 `OC` 渠道的条目
- 删除死代码 `MAIN_FIRST`；修正 `MAIN_ORDER` 里与 `MERGE_ACROSS_PROTOCOL`
  矛盾的注释（messages 版 DeepSeek 实际并入同一条链，不是独立显示名）
- 文档：`MODEL-ALIAS.md` §2/§3/§4/§5/§7 按代码真实口径重写（省钱组原写成
  「每厂商一个、8 条、≤0.11」，与代码的 1–2 个、9 条、白名单豁免不符）；
  `QINIU.md` 改为 2 个模型、显示名不带 `-Free`；`PITFALLS.md` 新增 §27–§30


### 接入七牛云网关，免费组 +1（2026-10-29）

- 新渠道 `QN`：`https://api.qnaigc.com/v1`（只提供 Anthropic Messages），
  经 `zgate` 协议桥接入，`qn:` 前缀裸 id 也能直接落对上游
- `qiniu/conatus-free` → 显示名 **`Conatus`**（后于 2026-10-29 去掉 `-Free` 后缀），进免费组；
  限时免费到 **2026-11-30**（`QN_FREE_UNTIL`），到期后该跳自动剔除
- 把用户在 ZCode 界面手建的独立 `new-provider` 收编：模型改由 `qn:` 种子进
  免费组，指纹 key 迁到 `providers/qiniu/.env.local`（gitignored），
  `providerOrder` 回到三组
- 同网关另测了 3 个免费模型：`kimi-k3-free` 可用（首字约 0.5–1.3s），
  后于 2026-10-29 收录为 **`Kimi-K3`**；`nemotron-3-ultra-free` 502、
  `glm-4.5-air-free` 已退役
- 顺带修 `providers/qoder/qoder_zcode_sync.py`：它还在找已删除的
  `opencode-go-chat-slow`，定时任务第三步会直接退出；现统一落到省钱组
- 新增 [docs/QINIU.md](docs/QINIU.md)


### 千问集合体下线，只留主力链尾跳（2026-10-29）

- **起因**：千问每模型 1M 免费 tokens，实测用量 18.6 亿/天 → 一个模型 30 秒烧完。
  114 个模型全存活也只值约 1.5 小时；实测只剩 30 个存活（约 23 分钟）。
  维持池子需每天探测 114 个上游 + 重建跳序，而池子天天在烂
- **单跳条目是错的设计**：`MiniMax-M2.5` / `GLM-5.3` / `Kimi-K3` / `DeepSeek-4-Pro-Msg`
  都是单跳，额度一烧完就硬 `403 auth failed`，没有下一跳可退。用户点一下就报错
- 处置：`POOL_SPECS` 清空（`Qwen-Pool-Max` / `Qwen-Pool-Fast` 下线），千问单型号种子
  只留 `deepseek-v4.1-flash`；分组因此收缩到 **14 条**（主力 2 / 免费 4 / 省钱 8）
- 保留主力链尾跳：零维护，WB/OC 都挂时才轮到，用来消耗一年期 ¥300
- 顺带修两个真 bug：
  - `expand_hops` 把条目级协议覆盖到每一跳，把千问尾跳的 `messages` 冲成 `chat`
    （路由会按 chat 直转 Messages 上游 → 404）。新增 `CHANNEL_PROTOCOL`，QW 跳一律钉 messages
  - `chatToAnthropic` 不校验 `max_tokens`，ZCode 发 128000 这类值会被上游拒绝
    （`Range of max_tokens should be [1, 65536]`），现夹到 65536
- 新增 `providers/qwen/qwen_pool_probe.py`（手动工具，定时任务不跑）：需要重新启用池子时，
  先探测再 `--write-pools --probe-file` 剔死跳


### 主力合并免费 DeepSeek：一条链混协议 + 千问预付额度（2026-10-28 续）

- `DeepSeek-4.1-Flash` 从两个显示名合并成**一条三跳链**：`WB cn 0.11 → OC 0.11 →
  千问 messages 0.00`。第三跳用 `TAIL_HOPS` 钉在链尾（OC 月度额度先用完，¥300 一年期兜底）
- `gateways/zgate`：链路支持**混协议**——`alias.Hop` 增加 `protocol` 字段，
  `attemptChain` 按每跳自己的协议派发（chat 直转 / messages·responses 过桥）
- `hopFatal` 增加 **403 配额类**判定：实测千问额度用尽返回
  `403 AccessDenied` + `Free quota exhausted`，此前只认 400/402，会硬失败不回落；
  普通 401/403 鉴权错误不受影响（新增 6 个用例的单测）
- `model_alias.py`：`QW_TRIAL_UNTIL` 改为 `QW_CREDIT_UNTIL = 2027-10-28`（¥300 预付额度
  一年有效，边际单价为 0）；新增 `MERGE_ACROSS_PROTOCOL`；千问自家单型号不再播种，
  免费组从 21 条收缩到 11 条

### 分组从四组收缩到三组：主力两条 + 免费 + 省钱（2026-10-28）

- 起因：4 天 74.6 亿 token 的用量统计里 86% 是 `DeepSeek-4.1-Flash` 一个模型
  （5 个历史 id 是同一链路的老名字），高耗组 16 条零使用、主力 6 条里 5 条是榜单自动塞的
- `tools/model_alias.py`：`PROVIDER_*` 改为三组（主力 / 免费 / 省钱），删除
  `opencode-go-chat-slow`；分组改为「人工名单 + 价格兜底」——
  `MAIN_IDS` = DeepSeek 两跳 + 贵备份 `Qwen-3.8-Max`（AA 1122 高于基准 1093），
  `LOW_PICKS` = 每厂商一个（Qwen / 智谱 / MiniMax / 小米 / 腾讯 / Anthropic / OpenAI / Space），
  两者之外的超价模型**直接不收录**；名单键改为 `<协议>:<上游 id>`（防止 chat 与桥接版同名互吸）；
  榜单扩充改为 `--arena` 显式开启
- 结果：52 → 31 条（主力 2 / 免费 21 / 省钱 8），`--check` 零漂移，主力与省钱 8 条实测 200
- 副作用：`opencode-go-chat-slow` provider 消失，选过高耗模型的会话需重选；
  4 个免费条目因同型号付费版被移出而改回不带 `-Free` 的原名
- 踩到的坑：收缩名单要跑两次 `--apply`，第一次落分组、第二次才收敛 `-Free` / `-Msg` 后缀


### 接入千问 AI 平台：`QW` 渠道 + 协议桥 + 免费额度漏斗（2026-10-28）

- 新增 `providers/qwen/` —— `qwen_zcode_sync.py`（把 `qwen:<id>` 播种进免费组，
  支持 `--only` / `--all-chat` / `--probe-file`）、`cache/freetier_20261028.txt`
  （118 个家族的控制台快照）、`.env.local`（`QWEN_API_KEY`，gitignored）
- 新增 `QW` 渠道：`gateways/zgate` 的 `config.go` / `keys.go` / `router.go` /
  `main.go` / `zgate.json` —— 上游只提供 **Anthropic Messages**（`/v1/models` 与
  OpenAI 兼容路径均 404），经既有协议桥转发；`/health` 增 `qwen` 视图
- `tools/model_alias.py` —— 新增 `QW_BASE`、`QW_TRIAL_UNTIL = 2026-12-15`、
  `price_of` 的 QW 分支（窗口内 0、窗口外缺价自动剔除）、`classify` 的 `qwen:`
  分支（**协议钉死 messages**）、`base_of()` 替换原先硬编码三渠道的 base 选择、
  以及「桥接条目让出原型名、`-Msg` 归桥接条目」的命名修正
  （修复前桥接条目会抢走原型名，把聊天条目挤成 `-2`，老会话会静默换渠道）
- 整理方法：控制台 506 条额度 → 294 条 token 计量 → 209 个可对话 → 118 家族
  → 人工收口 18 → 真实体探测 **14 个 200**；控制台列了但 API 不存在的三个
  （`qwen3-max` / `qwen3-coder-plus` / `qwq-plus`）已剔除
- 边界：桥接非真流式（首字≈整段生成）、思考关不掉（桥不转发思考字段）、
  「用完即停」开启后额度耗尽即报错。正本见 `docs/QWEN.md`
- 副作用：手工添加的 `new-provider` 被 `model_alias.py --apply` 整份替换掉（设计如此）
- 集合体（2026-10-28 续）：`providers/qwen/pools.json` + `qwen_zcode_sync.py --write-pools`
  把 117 个对话家族编成长链路 —— `Qwen-Pool-Max`（旗舰 + 代码，23 跳）/
  `Qwen-Pool-Fast`（91 跳）；2026-10-29 三池合两池，池内按「档位 → 版本」降序再用厂商轮转打散；
  `tools/model_alias.py --pools/--no-pools` 负责把池子写成合成条目（`kind: pool`）；
  `gateways/zgate` 新增**死跳判定与 30 分钟冷却**（`Model not exist` / 额度耗尽 / 402
  一律换下一跳，并记住该跳，`/health` 暴露 `cooling`）

### Qoder 排队耗尽不再崩线程：429 + Retry-After（2026-10-28）

- 修复 `gateways/upstream/qoder/qoder_proxy.py` —— `RateLimited` 补上
  `status=429` / `retry_after`。此前排队重试耗尽后，流式请求的 pump 错误处理读
  `exc.status` 抛 `AttributeError`，**整个请求线程崩掉、客户端连错误帧都收不到**
  （2026-10-28 11:47:58 实测）；`/ping` 仍 200，监控看不出异常
- chat / responses / anthropic 三条非流式路径显式捕获 `RateLimited`，走
  `_rate_limited()`（429 + Retry-After），不再落进通用 `except Exception` 的 502
- 流式错误帧附带 `retry_after`，客户端可按上游 `retryAfterSeconds` 退避
- 新增 `tests/_test_issue71_queue_error_paths.py`（7 项：异常契约 + 源码守卫）；
  全量 71 套件 / 1946 项通过
- 实测：`Qwen3.8-Flash` 排队 4 轮共 94.9s 后返回 `HTTP 429`
  （修复前同场景为 502 或 AttributeError 断流）
- 现象 / 根因 / 验证见 `docs/PITFALLS.md` 第 23 条

### 模型价格改为每轮重算，不再继承 alias map（2026-10-28）

- 修复 `tools/model_alias.py` —— `expand_hops()` 不再把 `chain[].price` 原样带回，
  价格一律由 `price_of()` 从当轮价格源重算。此前一次写入即永久冻结，导致
  Step-5-Pre 限免 10-25 到期后仍挂「免费 @0.00」（实测已在扣 x0.33）、
  MiMo-2.6-Pro 停在 0.18（实为 0.13），以及一条 Qoder 源故障时吃静态回退留下的
  0.0 假免费条目。源里查不到价的跳现在直接剔除
- 新增 `--check` —— 重算结果与现有 alias map 比对（新增 / 消失 / 价格 / 分组 / 链路），
  有漂移退出码 1，不写盘；补上 `sync_report.py` 看不见「稳定偏差」的盲区
- 新增 `--probe-max-age-hours`（默认 72h）—— 过期探测结论按「未知」处理，
  避免过期的 `ok` 留住死模型、过期的 `blocked` 删掉活模型
- 价格表超过 48h 未刷新时 stderr 告警
- 命名稳定性：同一 hop 继续沿用上一版名字（只继承 `-Msg` / `-Resp` / `-2` 这类
  去冲突后缀，`-Free` 跟着价格走），避免配置里混入原始 id 时同名模型改名翻转
- 新增 `tests/test_model_alias_price.py`（9 个用例：价格派生、死跳剔除、
  限免到期换组、漂移检测、探测过期），跑法 `python -m unittest discover -s tests -v`
- 现象 / 根因 / 验证见 `docs/PITFALLS.md` 第 22 条；规则正本见
  `docs/MODEL-ALIAS.md` §3.1

### zgate 上游握手超时 15s → 8s（2026-10-27）

- 调整 `gateways/zgate/main.go` —— `http.Transport.TLSHandshakeTimeout` 由 15s 收到 8s。
  透明代理链路握手会抖（实测正常 0.32s、坏窗口 0.6–7.7s、再往上完全不返回），
  15s 会把一次失败拖成 15s 的 502 长尾，叠上备用链就是 20 秒以上的回复
- **不给 `http.Client` 设整体 `Timeout`** —— 流式响应会被整体截断，非流式的长推理
  也会被误杀；只压握手阶段，长回答的传输不受影响
- 现象 / 根因 / 验证见 `docs/PITFALLS.md` 第 21 条

## [0.4.0] — 2026-10-27

### zgate 构建入口收口 + 无窗产物防回退（2026-10-27）

- **新增 `gateways/zgate/build.py` —— zgate 的唯一构建入口**。带 `-H windowsgui`
  编译（GUI 子系统 → 登录自启零窗口），并**强制校验产物的 PE `Subsystem` 必须是 2**，
  不合格直接非零退出。三个用法：
  - `python gateways/zgate/build.py` —— 构建（Windows）+ 校验；
  - `python gateways/zgate/build.py --check` —— 只校验现有产物，不编译；
  - `python gateways/zgate/build.py --cross-check` —— 交叉编译一份 windows/amd64
    到临时目录再校验；`-H windowsgui` 是 windows 链接器 flag，**交叉编译时同样生效**，
    所以这条校验在 Linux CI 上也能真跑起来。
- **核实并订正「裸 `go build` 覆盖产物」的归因**：实测 `go build ./...`（**多包**模式）
  Go 只编译不落盘，**不会**覆盖产物；真正的回退命令是**单包**的 `go build .` ——
  它会把可执行文件原地写到当前目录，产出 `Subsystem = 3`（CONSOLE）的控制台程序，
  静默顶掉无窗版。两者后果相同，但归因要精确到单包命令。
- **补上「为什么会回退」的这一环**：`-H windowsgui` 是**链接期** flag，只在那一次编译里
  生效，事后无法从源码判断，只能读产物的 PE 头 —— 所以光在文档里写对命令不够，
  必须有工具在编译后当场校验。文档记对了、手滑一次就回退（10-26 即如此）。
- **CI 增加一步** `python3 gateways/zgate/build.py --cross-check` —— flag 丢了在 CI 就红，
  不用等下次开机才发现弹窗。
- **文档按单一正本分三处补齐**：
  - `docs/PITFALLS.md` §20（新增）—— 机制：PE `Subsystem` 决定要不要分配控制台、
    快捷方式 `WindowStyle = 7` 对控制台程序**不等于隐藏**、单包 vs 多包 `go build`
    的落盘差异、产物在 `.gitignore` 里所以 `git checkout` 救不回来；
  - `docs/TROUBLESHOOTING.md` §16（新增）—— 排错：现象 → 排查 → 原因/解法；
  - `docs/MAINTENANCE.md` §8.1 —— 构建命令正本改为 `python gateways/zgate/build.py`，
    并写明**别在 `gateways/zgate/` 里裸跑 `go build .`**，检查用 `go vet ./...`；
  - `docs/TOOLS.md` —— 把 `build.py` 登记进工具清单。
- **`.gitignore` 排除 `.workbuddy/`** —— IDE 本地 agent 工作区（可再生）；
  版本化记忆仍在本仓 `memories/`。
- **本机状态核实（不入库）**：`gateways/zgate/zgate.exe` 的 `Subsystem` 已是 2；
  但开工时 **zgate 进程根本没在跑**（7871 / 7863 / 8790 全部无人监听）。
  根因是 **Windows Job Object 随 agent 会话结束回收整棵进程树** ——
  日志里 `11:10:30 已启动` 之后连「已退出」都没有，进程被强杀；
  而 ZCode app-server 新进程建于 `11:10:51`，与死亡时间吻合。
  已用 explorer 拉起启动文件夹快捷方式恢复（父进程 explorer.exe，与登录自启同一条路径，
  能存活；`nohup` / `setsid` / `Start-Process` 起的都会被回收）。
  端到端实测：`/health` `ok:true`、31 个模型、`DeepSeek-4.1-Flash` 经 7871 返回 200、
  `conhost` 无带标题窗口。

### 破坏性变更

无。原有 `go build -C gateways/zgate -ldflags "-H windowsgui" -o zgate.exe .`
仍然可用，`build.py` 只是把它包起来并加上产物校验。

### 回退

删掉 `gateways/zgate/build.py` 与 CI 里那一步即可，其余改动（文档、`.gitignore`）
无行为影响。已发布的 `zgate.exe` 不入库，回退不影响已装好的二进制。

---

## [0.3.0] — 2026-10-26

### 四组制收口与全仓审查修复（2026-10-26）

- **四组制收口**：`备用` / `对话` / `响应` 三个 provider 不再由脚本创建或写入。
  `go_model_sync.py` 的 `CHAT_PROVIDER["备用"]` 与 `BACKUP_PROVIDER` 都指向
  `opencode-go-chat-slow`，messages / responses 模型也按成本进四组，协议差异交给
  zgate 按 alias map 桥接；`workbuddy_zcode_sync.py` 的备用档并入高耗。
  新增协议提示缓存 `providers/opencode-go/cache/go_protocols.json`（不入库），
  `model_alias.py` 用它给裸 OC id 补 `protocol`。
- 修复 `go_model_sync.py` 的免费模型打印崩溃 —— `row` 在价格兜底前就捕获了
  `price`，命中「按名含 free」分支时 `NoneType` 报错；挪到价格解析之后。
- 修复 报告目录漂移 —— 脚本移到 `providers/opencode-go/ops/` 后，`dirname` 三层
  只到 `providers/`，报告落到 `providers/evidence/`；改为四层回到仓库根 `evidence/`。
- 修复 价格源静默失败 —— 缓存读不到时整个渠道的模型会被无声剔除；现在 stderr 告警，
  且整渠道无价时拒绝 `--apply`（`--force-unpriced` 可绕过）。
- 修复 未公布价格被归零 —— 原来统一写 `0.0`，下游按「免费」分档；改为保留 `None`
  （只有 `-f` 模型与纯路由别名补 0）。
- 修复 `legacy-router` 跨渠道回退 —— fallback 链共用单一 base，WB → OC 的回退
  会把 OC 模型名发到 WorkBuddy 网关；改为按 hop 自带的 base/channel 回退并换 key。
- 修复 `protocol_bridge.js` —— 上游 4xx 一律映射成 502，探测脚本无法区分
  「凭证失效 / 参数错误」；改为透传上游状态码。
- 修复 WB 探测门控 —— `rate_limited` / `timeout` 等瞬态状态会直接把模型从配置里剔除，
  而从未探测的模型反而保留；改为瞬态保留并留痕。
- 修复 zgate 查询串转发 —— `RawQuery` 不含 `?`，带 query 的请求路径被拼成
  `.../completionsstream=1`（移植自 JS 的 `url.search`，语义差一个字符）；
  补 `?` 并新增 `TestQueryStringIsForwarded`
- 修复 zgate 其余项 —— 错误体改为限长 `ReadAll`（单次 `Read` 会拿到不完整片段）；
  转发前去掉 `Accept-Encoding`（transport 禁用了透明解压，压缩体让
  `chainAccept` 看不到 `model_unavailable`）；bridge 保留上游状态码并接
  `r.Context()`；`attemptBridge` 只对 5xx/429 回退、末跳透传真实错误；
  `/admin/reload` 同步热加载 key；`startChild` 锁外读 cfg 的竞态；alias 热加载
  同时比较 mtime 与 size；boot 改为后台执行（先起 monitor，`Stop` 加守卫）；
  `stop:""` 不再变成 `[""]`、错误文本按 rune 截断；install 的 PowerShell 单引号转义
- 修复 工具链 —— `providerConfigRules` list 形态写入崩溃；`check-secrets.py`
  片段级豁免 + git 失败报错；`make_social_preview.py` 相对 `m` 参考点与 T/S
  控制点复位；`sync_report.py` 按实际 `--out-dir` 提交；`check-docs.py` 锚点误报；
  榜单缓存超过 24 小时告警；删除死常量 `REMOVE_PROVIDERS`
- 验证 —— `go build ./...` / `go vet ./...` / `go test ./...` 全绿（含新回归测试）；
  相关 Python `py_compile`、JS `node --check` 通过；zgate 重建后 7871 端到端
  （chat / messages / responses）由四组制批次实测 200

### 运行架构整合：三个反代并成一个 Go 入口（破坏性：目录与启动方式变了）

- **新增 `gateways/zgate`（Go）**：一个二进制顶掉原来的 Node 路由（`tools/unified-router.js`）
  与 PowerShell 守护器（`workbuddy/zcode_gateway_watch.ps1`）。监听 `127.0.0.1:7871`，
  做 alias 分流、chat ↔ messages/responses 协议桥、以及两个上游子进程的起停。
- **子进程策略**：WorkBuddy `ondemand`（首个 WB 请求拉起，空闲 900 秒回收）；
  Qoder `always`（签到不能停）。子进程装在 Windows Job Object 里，zgate 挂了不会留下孤儿。
- **内存实测**：改造前 4 个进程 293.4 MB（PowerShell 守护器 124.2 + Node 路由 71.5 +
  Qoder 70.1 + wb2api 27.6）；改造后 3 个进程 **99.3 MB**（zgate 18.5 + Qoder 57.2 + wb2api 23.2）；
  WB 空闲回收后 76.1 MB；只留 zgate 时 18.5 MB。
- **等价性**：新入口在 7971 与旧路由并行跑了 9 个用例（OC/WB/QD chat、messages 桥、
  responses 桥、三种流式、未知模型），状态码/响应形态/SSE 事件序列 9/9 一致，之后才切到 7871。
  `gateways/zgate/smoke_test.py` 保留为常设冒烟（6 项）。
- **目录重构（破坏性）**：`workbuddy/gateway` → `gateways/upstream/workbuddy`；
  `qoder/gateway` → `gateways/upstream/qoder`；三家采集脚本 → `providers/<vendor>/`；
  旧 JS 路由 → `gateways/legacy-router/`（回退用，保留一个版本）。
  `.gitignore`、4 个脚本的硬编码路径、19 篇文档与模板的路径已同步；
  `zcode_gateway_watch.ps1/.vbs` 已删除，`.gitignore` 里两份过期备份也已清理。
- **启动方式（破坏性）**：`zgate install` 写登录自启快捷方式（`schtasks ONLOGON` 在普通权限下
  被拒绝）；`zgate status` 一次看全服务、子进程、端口与凭据有无；配置在
  `gateways/zgate/zgate.json`。
- **偏差说明**：没有实现「跟随 ZCode 主进程」——在 Go 里判主进程要读 PEB 命令行，代价高且脆；
  改成 zgate 常驻（19 MB），顺带可以用 `always` 策略让 WorkBuddy 的定时任务在 ZCode 关闭时也跑。
- **验证**：`go test ./...`（bridge/alias/router/supervisor 共 12 个用例）+ `go vet` + `gofmt`
  全绿；四条通道真实请求 200；WB 冷启动 1.6 秒；CI 增加 Go 格式/构建/测试步骤。
- **回退**：`zgate uninstall` → `node gateways/legacy-router/unified-router.js` 并手动起
  `gateways/upstream/workbuddy/run.bat`；或 `git revert` 本次提交。

### 追加：两个网关全部改按需 + 签到窗口 + 热加载（2026-10-23 晚）

- **不再常驻任何上游**：Qoder 从 `always` 改成 `ondemand`；两个子进程都空闲 300 秒回收。
  ZCode 启动后 7863 / 8790 都是空的，只有请求打到才拉起（WB 冷启动约 1.6 秒）。
- **新增 `children.*.windows`**：本地时间 `HH:MM-HH:MM`，支持跨午夜；窗内按 `always` 处理。
  默认 WB 四档（9 / 10 / 21 / 22 点前后）、Qoder 三档（9 / 21 / 22 点），保住签到与保活。
- **新增 `zgate reload` / `POST /admin/reload`**：策略、空闲阈值、窗口可热加载；
  新增 child、监听地址与上游 base 仍需重启。
- **修复**：协议桥补 120s 超时；`Process.Release` 改 `sync.Once`（double CloseHandle）；
  `external` 接管实例纳入 5 秒健康轮询；重启退避改成 1s→2s→…→60s；日志运行期按 5 MB 轮转；
  `zgate status` 不再打开写句柄；`qoder:` 前缀大小写不敏感；删除 `WaitExit` / `Missing` /
  `Redacted` 等死代码。
- **修复 回退链**：WorkBuddy 把上游 6004 模型限流转成 `400 {"code":"model_unavailable"}`，
  旧逻辑只在 429/502/503/504 上重试，导致 `global:` → `cn:` 的回退从未生效。现在这种 400
  按「池故障」触发回退，普通 400（参数错误）仍然直通不重试。
- **配置解析修正**：`args` 里以 `/` 开头的参数（如 `cmd /c`）不再被当成路径解析。
- **验证**：旁路实例实测「启动不起、窗内起、reload 后回收」；`go test ./...` 24 个用例全绿。

### 显示名 `Flash`/`-Free` + 按消耗排序 + 自动化同步报告（2026-10-23 晚）

- **命名**：`Fs` 改回 `Flash`（`DeepSeek-4.1-Flash`、`GLM-5.3-Flash`、`MiMo-2.6-Flash`）；
  免费重复条目的后缀 `-F` 改为 `-Free`（`HY3-Free`、`HY4-Pre-Free`、`DeepSeek-4-Flash-Free`）。
- **排序**：组内按积分消耗从低到高；**同厂商粘成一块**，整块的位置按该厂商最便宜的那条排，
  块内再按价格升序。名字里仍然不显示积分。
- **自动化**：新增 `tools/sync_report.py` —— 对比上一轮快照
  （`~/.zcode/v2/model-sync-state.json`），生成 `docs/reports/MODEL-SYNC-<时间>.md`
  （新增 / 移除 / 分组变化 / 链路变化 + 当前清单），自动更新 `docs/reports/README.md` 索引；
  `--write --push` 会再 `git add/commit/push`。日常自动化的最后一步加它。
- 结果：28 个模型（主力 6 / 免费 5 / 低耗 8 / 高耗 9），排序与命名已线上生效。

### 显示名只留型号 + 跨渠道合并链路（2026-10-23 晚，破坏性）

- **命名**：显示名去掉渠道与积分，只剩型号 —— `W/0.03/DeepSeek-4.1-Fs` →
  `DeepSeek-4.1-Fs`。版本号保留点号。
- **跨渠道合并**：同型号同协议的所有渠道合成一条 `chain`，按价格升序尝试，
  每一跳自带 `base` / `channel` / `upstream`。例：`DeepSeek-4.1-Fs` =
  WB 免费 → WB sg → WB cn → OC。
- **分组**：免费 = 链路最低价 0；低耗 = 0 < 最低价 ≤ **0.11**（DeepSeek OC 基准价）；
  高耗 = > 0.11；主力仍由 `MAIN_IDS` + 榜单决定并优先于价格。
- **免费重复**：同型号既有免费又有付费时，免费那条单独成条并加 `-F`
  （`HY3-F`、`HY4-Pre-F`、`DeepSeek-4-Fs-F`）；`deepseek-v4.1-flash` 例外，
  免费档并入付费条目并置顶（`MERGE_FREE_GB`）。
- **router**：`alias.Target` 新增 `chain`，`routeChain` / `attemptBridge` 按跳切换
  base、渠道与 key；旧的 `base` + `fallbacks` 仍兼容。
- **生成器**：`family_entries()` 取代旧的按渠道命名 + `merge_inventory`；
  链路写回 alias map 并可从 `chain` 还原，重复运行幂等；`legacy` 支持改名链传递。
- 结果：28 个模型（主力 6 / 免费 5 / 低耗 8 / 高耗 9）。
- 上线：新二进制 + 新配置 + 新 alias map 由一次性计划任务在 21:41 一起替换并重启。

### 显示名恢复版本点号 + 免费 DeepSeek 进主力置顶（2026-10-23 晚）

- **命名**：`model_alias.py` 的 `ABBR` 与兜底规则不再删版本点号 ——
  `DeepSeek-41-Fs` → `DeepSeek-4.1-Fs`、`Qwen-38-Fs` → `Qwen-3.8-Fs`、
  `MiMo-26-Fs` → `MiMo-2.6-Fs`、`GLM-53-Fs` → `GLM-5.3-Fs`、
  `MiniMax-M31-Fs` → `MiniMax-M3.1-Fs`、`Claude-Haiku-55` → `Claude-Haiku-5.5`、
  `Kimi-K28-Pre` → `Kimi-K2.8-Pre`、`GPT-56-Luna` → `GPT-5.6-Luna`、
  `Muse-Spark12/13` → `Muse-Spark1.2/1.3`、`LongCat-20` → `LongCat-2.0`。
  旧名全部进 alias map 的 `legacy`，老会话继续可路由。
- **主力**：`W/0.03/DeepSeek-4.1-Fs` 固定在主力组**第一位**（`MAIN_FIRST`）。
- **免费档并入付费条目**（`MERGE_FREE_GB`）：`deepseek-v4.1-flash` 的免费 GB 档不再单独成条，
  折进 `W/0.03/DeepSeek-4.1-Fs`，条目内链路为
  `global:deepseek-v4.1-flash`（免费）→ `global:deepseek-v4.1-flash-sg`（0.03）→
  `cn:deepseek-v4.1-flash`，**免费优先**；显示价保留 0.03。
- 合并时的价格档位**从 `wb_pricing.json` 重建**，不依赖上一次写进配置的条目，
  因此重复跑 `--apply` 不会再退回 `W/0.00`（已实测两次幂等）。
- 重新生成：35 个模型（主力 7 / 免费 4 / 低耗 13 / 高耗 11），
  备份 `provider_config.json.bak-alias-20261023-212838-434500`。

### 显示名 `Preview` 缩为 `Pre`（2026-10-23）

- `model_alias.py` 的 `ABBR` 与后缀兜底规则把 `Preview` 缩成 `Pre`：
  `Kimi-K28-Pre`、`HY4-Pre`、`Step-5-Pre`、`LongCat-25-Pre`。
- 重新生成四组与 alias map：37 个模型，旧显示名进 `legacy`，老会话仍可路由；
  `W/0.00/HY4-Pre` 经 7871 实测 200。
- 备份：`provider_config.json.bak-alias-20261023-192910-362000`。

### 每日自动化加入 Qoder 模型查询（2026-10-23）

- 定时任务 `automation-3e2f8a53-b408-4bf8-90ff-4a331a721f5c` 从「Go + WorkBuddy」
  扩为四段：Go → WorkBuddy → **Qoder（实时目录 + 真实 body 探测 + 并入）** →
  `model_alias.py` 统一归一化；标题改为「每天 12:00 自动收录 Go 套餐、WorkBuddy 与
  Qoder 新模型」。Qoder 探测全部超时时会检查 7871，必要时改 `--direct` 直连 8790 重探。
- 修 `go_model_sync.py` 的显示名误判：配置被 `model_alias.py` 重写成
  `W/0.03/…`、`O/0.11/…`、`Q/0.09/…` 后，脚本会把这些显示名直接发给 Go 上游探测，
  404 后按「跑不通即清」误删。现在先按 `model-alias-map.json` 还原上游裸 id 再体检，
  WorkBuddy / Qoder 渠道直接跳过。
- 首跑结果：Qoder 探测 8 个模型（`Qwen3.8-Flash` 复通 HTTP 200 并自动收录），
  四组共 37 个模型（主力 7 / 免费 5 / 低耗 14 / 高耗 11），其中 Qoder 8 个；
  `Q/0.09/Qwen-38-Fs` 经 7871 实测 200。

### 显示名压缩为 `W/0.03/DeepSeek-41-Fs`（2026-10-23）

- 模型 ID 从 `渠道 : 型号 : 积分` 改为 `单字母/积分/紧凑型号`：`W` WorkBuddy、
  `O` OpenCode-Go、`Q` Qoder；型号去掉版本里的 `V` 和点、`Flash` 缩写为 `Fs`
  （`DeepSeek-41-Fs`、`Qwen-38-Fs`、`GLM-53-Fs`、`MiniMax-M31-Fs`、`MiMo-26-Fs`、
  `Claude-Haiku-55`）。
- `model_alias.py` 新增 `CHANNEL_LETTER`，`ABBR` 全部换成紧凑名；alias map 的
  `legacy` 保留旧空格 ID，老会话仍可路由。
- 重新生成四组：仍是 36 个模型，主力 7 / 免费 5 / 低耗 13 / 高耗 11；
  新 ID 经 7871 实测 200，旧 ID 也仍 200。
- 文档/记忆中的示例同步为新格式。

### 主力按外部榜单自动扩充（2026-10-23）

- 新增 `tools/arena_leaderboard.py`：拉 ArenaGalleri 实时榜
  （`https://api.arenaofbias.icu/api/leaderboard`，10 分钟刷新），以
  `deepseek-v4.1-flash` 为基准，筛出「分数 ≥95%、积分 ≤0.11、非临时、≥50 局、
  积分 >0」的**已配置模型**，写 `~/.zcode/v2/arena-main.json`。
- `tools/model_alias.py` 新增 `--arena-main` / `--no-arena`：默认读候选文件，
  按 `(channel, upstream)` 扩充主力；alias map 条目增加 `main_reason`
  （`manual` / `arena`）。顺手修复 `--probe-file` 分支里 `transient_kept` 未初始化、
  一旦命中「改名未探测」就 `NameError` 的隐患。
- 2026-10-23 首次扩充：主力 4 → **7**，新增
  `OC : MiMo-V2.6-FS : 0.06`（1112 分，基准 101.1%）、
  `WB : Space-Bunny : 0.08`（1075，97.7%）、
  `OC : Claude-Haiku-5.5 : 0.09`（1064，96.7%）；三个模型经 7871 实测 chat 200。
  免费模型（0 积分）仍留在免费组；榜单掉出窗口会自动退回原组。
- 榜单接口失败时用本地缓存；候选集合或规则没变时不重写配置，分数波动不会引起
  模型 ID 抖动。
- 文档：`BENCHMARKS.md` 新增 §8（接口、口径、候选表、名字映射边界与回退），
  `MODEL-ALIAS.md` §4.2 / §6 / §7、`TOOLS.md`、`MAINTENANCE.md` §2.1、`README.md`
  同步更新。

### 同步脚本：免费 `-f` 模型漏收修复 + 「跑不通即清」策略（2026-10-23）

- 修复 `workbuddy/workbuddy_zcode_sync.py` 的 `rate_of()` —— 原先只重新解析原始
  `credits` / `promo_credits` 字符串，免费 `-f` 模型（网关 `credits` 为空串）被判
  `None`，按「无公布倍率」排除。改为优先信任价格表已归一化的 `eff_rate` / `list_rate`
  （`wb_pricing.json` 本就是分档的唯一价格输入），缺失才回退原始串解析。
  结果：`cn:hy4-preview-f`、`global:hy4-preview-f` 收进免代档（免代 5 → 7，其余档零位移）
- 调整 `opencode-go/ops/go_model_sync.py` 的 `stale_reason()` —— 已配置模型体检从
  「400/402/404 且带 unavailable 标记才移除」收紧为：`error` 类里仅豁免
  **401（凭据/隐私授权）** 与 **429（限频冷却）**，其余 400/402/404/410 与 5xx
  一律判「跑不通」并 `prune_model`；复通后由新模型评估自动加回。
  口径：跑不通即清、复通即加回（WorkBuddy 侧本就按 blocked/unavailable 移除，未改）
- 文档对齐：`MAINTENANCE.md` §7 待办 6/7 标记已修并新增第 8 条；
  `TROUBLESHOOTING.md` §13 对应三行改为「自动处理 / 已修」；`TOOLS.md` 同步两处脚本说明

### 统一模型命名：四组 + alias map + 协议桥（2026-10-23）

- ZCode provider 统一为四组：**主力 / 免费 / 低耗 / 高耗**；`备用` 按积分并入高耗，
  `对话` / `响应` 两个协议组折入四组。
- 模型 ID 改为 `渠道 : 型号 : 积分`（`WB : DeepSeek-V4.1-FS : 0.11`、`OC : DeepSeek-V4.1-FS : 0.11`、
  `QD : GLM-5.3 : 0.69`）；价格写进显示名，调价时靠 alias map 的 legacy 兼容旧会话。
- 显示名改为可读大小写并去掉 `-f` / `-sg` / `-free`（`DeepSeek-V4.1-FS`、`GLM-5.3-FS`、
  `HY4-Preview`），价格后缀不再带 `X`。
- `model_alias.py --slot auto|peak|offpeak`：Qoder 按 `price_factor_peak/valley` 与
  22:00–08:00 窗口取价；WorkBuddy 用时段刷新后的 `eff_rate`。08:00 / 22:00 各重写一次
  即可让倍率随早晚变化；模型 ID 变化由 legacy map 兼容旧会话。
- WorkBuddy 的 CN/GB 合并成一个 `WB` 口子：GB 优先、GB 全不可用时路由自动回退 CN；
  同价 CN/GB 对合并，GB 免费/付费价档保留；显示名去掉地区并改成
  `WB : DeepSeek-V4.1-FS : 0.03`（冒号两侧有空格）。
- OpenCode-Go 的 DeepSeek V4.1 Flash / V4 Pro 加入峰谷价：峰时 UTC 周一至周五
  01:00–04:00、06:00–10:00，其余时间谷价；V4.1 Flash 峰 0.22 / 谷 0.11，
  V4 Pro 峰 0.77 / 谷 0.39。
- `Qwen3.8-Flash` 提进主力：榜单 #4 总分 372.95、积分 0.09；DeepSeek V4.1 Flash
  #11 是 342.40 / 0.11，智力与价格都更优。它走 messages 桥接，已实测 chat 200。
- 积分换算：WorkBuddy `eff_rate` 原样；OpenCode-Go 以 `deepseek-v4.1-flash`
  $0.15 入 / $0.60 出 ↔ 0.11（1 积分 = $3.409/M，1:1 混合）；Qoder `price_factor × 0.86`
  （同名模型比值中位数）。
- 新增 `tools/model_alias.py`：生成四组 + `~/.zcode/v2/model-alias-map.json`；
  `--probe-file` 只保留 ok（或曾 ok 的瞬时限流）。
- 新增 `tools/model_probe.py`：用 ZCode 真实 body（含 provider 的 `optionSpecs`
  覆盖）探测四组，经 7871，桥接模型也覆盖。
- 新增 `tools/protocol_bridge.js`：chat ↔ Anthropic Messages / OpenAI Responses，
  非流式上游 + 合成 chat SSE，支持文本、思考与工具调用。
- `tools/unified-router.js` 优先按 alias map 还原上游，旧 `cn:`/`global:`/`qoder:`
  前缀保留为 legacy 回退；`/health` 增加 alias 条数。
- `go_model_sync.py` 把 `WB:`/`OC:`/`QD:` 视作非 Go 模型跳过，避免体检误删。
- 当前 43 个模型 / 4 个 provider；37 个 ok，5 个 WB GB 模型因账号池冷却暂为瞬时限流。
- 旧的三个 sync / 两个 probe 降级为数据采集与兼容；`model_alias.py` 是唯一最终写入者。



- 新增 `qoder/` 适配器：qoder2api-hub（MIT）clone 到 `qoder/gateway/`（整目录
  gitignore），默认 `127.0.0.1:8790`；API key 与面板密码持久化在
  `accounts/settings.json`，脚本从 git-ignored 的 `qoder/.env.local` 读 `QD_API_KEY`
- Qoder CN 账号通过 OAuth 设备授权入库；`_install_umid.py` 装好签到所需的 UMID；
  启动巡检签到 +100 Credits
- 新增 `qoder/qoder_zcode_sync.py`：拉 `/v1/models` → 排除 Auto/Fast 别名 →
  按 `price_factor` 升序 → 写独立 `qoder` provider（默认 `--max-price 0.8`）；
  `--probe-file` 只保留探测 `ok` 的模型
- 新增 `qoder/qoder_probe_zcode.py`：用 ZCode 真实 body 探测，7 个模型 200；
  `Qwen3.8-Flash` 因上游 10605 排队（≈19k，p3）暂不收录，复通后自动加回；
  结果带 `ever_ok`，排队/超时不误杀曾 200 的模型（免费 `DeepSeek-Flash` 排队时 64s 后 200，也可能 90s+ 后 502）
- （`--separate` 旧模式）独立的 `qoder` provider 排在 `opencode-go-chat-free`
  之后；7 个模型未配 `optionSpecs` 覆写（原生四件套全通）
- 默认改为**合并模式**（2026-10-23 同日调整）：模型加 `qoder:` 前缀并入免费
  （price 0）/ 低耗（≤0.2）/ 高耗（>0.2）三个 chat 组；7871 路由剥前缀后转 8790；
  不再创建独立 `qoder` provider，provider 列表仍是 7 个。`--separate` 保留旧模式
- 兼容性：`go_model_sync.py` 把 `qoder:` 视作非 Go 模型跳过体检/清理；
  `workbuddy_zcode_sync.py` 的合并逻辑只清 `cn:`/`global:`，不会动 `qoder:`
- 文档：新增 `docs/QODER.md`，更新 `MODEL-PROVIDERS.md` §4.9/§5.2、`TOOLS.md`、
  `SECRETS.md`、`TROUBLESHOOTING.md` §14、`MAINTENANCE.md` §8.1、`README.md`、`NOTICE`
- 边界：WorkBuddy2API 与 OpenCode-Go 不动；Agent2API 评估后暂不采用

### 追加：登录自启零窗口落地（2026-10-26）

- **zgate 改按 GUI 子系统构建**（`go build -ldflags "-H windowsgui"`，命令正本见
  [docs/MAINTENANCE.md](docs/MAINTENANCE.md) §8.1）。此前发布的二进制实际是控制台程序，
  登录自启会挂一个最小化 cmd 窗口：中文按 GBK 显示成乱码（日志本身是 UTF-8，没坏），
  而且关掉该窗口等于杀掉网关。GUI 子系统下零窗口，日志只落
  `%LOCALAPPDATA%\ZCodeGateway\zgate.log`。
- **修复 `AttachParentConsole` 吞输出**：旧逻辑无条件把 stdout/stderr 重绑到父控制台，
  在管道（mintty / CI / 脚本）与 `> 文件` 重定向下输出被吞进隐藏 conhost。现在先判断
  继承句柄类型，管道/文件保留原样，只在句柄无效或本就是控制台时才接管 ——
  `zgate status` 在 Git Bash、cmd、PowerShell 里都照常打印。
- **顺带修复**：CHANGELOG 0.3.0 段落里四个小节整块重复的历史残留（并发写坏），
  删去重复的 70 行。
- **验证**：`go vet` / `gofmt` / `go test ./...` 全绿；GUI 构建下管道、cmd 重定向、
  分离启动三场景输出正常；运行中进程 `MainWindowHandle=0`、`/health` 200、28 个 alias 模型。

> 未发版，版本号不动（[docs/VERSIONING.md](docs/VERSIONING.md) §5）。

---

## [0.2.0] — 2026-10-23

### 凭据守卫（2026-10-23）

- 修复 `tools/check-secrets.py` —— `PLACEHOLDER` 命中后整行 `continue`：行内只要
  出现 `example.com` / `<...>` / `YOUR-` 就把同一行的真值一起放过。改为只豁免
  匹配片段本身（示例 URL 仍按预期放行，真 token 不再逃检）
- 验证 —— `check-secrets.py` ✓（86 个文件）、`check-docs.py` ✓（20 篇）、
  全部 `.py` `ast.parse` ✓、全部 `.js` `node --check` ✓

### 脱敏：修掉报告回显本机路径的泄漏源，补敏感信息守卫（2026-10-23）

只修脱敏与守卫，不动版本号（规则见 [docs/VERSIONING.md](docs/VERSIONING.md) §5）。

- 修复 `opencode-go/ops/go_model_sync.py` —— 两处「已写入 %s」把 `--config` 的
  绝对路径原样回显到报告里，而报告会作为 evidence 提交，于是本机用户目录
  （`C:\Users\...\provider_config.json`）进了版本库：提交 `92baac2` 的两个 evidence
  文件就是这么漏的。改为只输出 `os.path.basename(args.config)`，报告里从此只有文件名。
  报告落盘路径那行（`log("报告: %s"`）在文件写完之后才执行，不进正文，无需处理
- 新增 `tools/check-secrets.py` —— 本仓原来没有守卫，凭据规则之外多两条：
  「本机用户目录」（`C:\Users\<名字>`，正反斜杠都拦）与「真实邮箱域名」，
  都是上面这个坑的直接产物。已接入 CI 的「敏感信息扫描」步骤
- 脱敏 `evidence/go-model-sync-20261022-234800.md` 与 `evidence/go-model-sync-20261023-000011.md`
  —— 两处 `已写入 <USER>\...\provider_config.json` 改为 `已写入 provider_config.json`。
  历史提交里的旧内容不会因此消失（旧 SHA 仍可访问），要彻底清需重写历史，见 PROGRESS 待解决段

### 同步脚本自动清理失效模型（2026-10-23）

脚本行为变了，按本文件第 10 行的口径「现有脚本的行为变了 = 功能更新」；未发版，
版本号不动（规则见 [docs/VERSIONING.md](docs/VERSIONING.md) §5）。

- 调整 `opencode-go/ops/go_model_sync.py` —— 已配置模型体检从「只报告」改为
  「`--apply` 时直接移除」：上游弃用（410 / 弃用日期表）、端点不可用（402
  `Endpoint is unavailable`）、模型不支持（400 `Unsupported model`）的模型，
  连同 `personalModelIds`、`modelOrder`、`modelConfigRules` 一并删掉，报告写
  「移除」和上游原话。原来只写「建议从配置移除」，删不删全靠人盯
- 调整 `opencode-go/ops/go_model_sync.py` —— 体检跳过 `cn:` / `global:` 开头的
  WorkBuddy 模型（统一路由把它们转给网关，不属于 Go 套餐），不再把它们报成
  Go 探测异常；本轮实测清掉 4 个：`minimax-m3.1-flash-free`（410 弃用）、
  `longcat-2.0` 与 `longcat-2.5-preview-free`（402）、`mimo-v2.5-pro`（400）
- 调整 `workbuddy/workbuddy_zcode_sync.py` —— 统一模式下，不再被选中的
  `cn:` / `global:` 模型从配置删除并列出名字（原来只重排选中的，网关下架的会一直留着）
- 调整 `workbuddy/workbuddy_zcode_sync.py` —— 加残缺列表保护：网关偶尔只返回
  部分模型（本轮实测遇到一次 34/56），这时缺失的模型只报告 `kept`、不删除，
  避免把正常模型误判成已下架
- 调整 `workbuddy/workbuddy_fetch_pricing.py` —— 新列表比旧表少 30% 以上时
  拒绝覆盖旧表（退出码 2），确认是真实下架需加 `--force`，防止残缺响应覆盖价格表

### 文档骨架对齐基准仓（2026-10-22）

不动版本号（只改文档，规则见 [docs/VERSIONING.md](docs/VERSIONING.md) §5）。

- 调整 文档 —— 文件命名统一为**全大写 + 连字符**：`docs/模型速查表.md` → `docs/MODEL-QUICK-REF.md`、
  `docs/archive/OPENCODE-GO-模型与订阅优化分析.md` → `docs/archive/OPENCODE-GO-ANALYSIS.md`；
  三处文件均用 `git mv`，引用方（docs/README.md、docs/DOC-RULES.md、AGENTS.md、PROGRESS.md）
  全部改到新名。命名规则写入 [docs/DOC-RULES.md](docs/DOC-RULES.md) §1
- 调整 文档 —— `docs/release-notes/v0.1.0.md` → `docs/release-notes/0.1.0.md`：
  基准仓口径是「文件名 = `versionName`，无 `v` 前缀」；**git tag 仍是 `v0.1.0`，未动**
- 调整 文档 —— `docs/README.md` 索引重写：开头引言块与结尾提醒对齐基准仓，
  四张表的链接逐条复核，过长的一句话定位（尤其 MODEL-PROVIDERS 那行）压缩到一行读完；
  索引行长度纪律写入 [docs/DOC-RULES.md](docs/DOC-RULES.md) §6
- 调整 文档 —— `docs/VERSIONING.md` 补「§5 不发版的时候：不动版本号」（按本仓情况改写，
  含「改文件名不算发版」这一条）；§2 判断口诀与边界情况表对齐基准仓，补两条本仓边界
- 调整 文档 —— `docs/MODEL-QUICK-REF.md` 补「一句话」引言块 + 降级声明
  （结论已并入 MODEL-PROVIDERS.md，本篇保留作历史快照）
- 验证 —— `python tools/check-docs.py` 通过（20 篇）

### WorkBuddy 价格表（2026-10-22）

- 修复 `workbuddy/workbuddy_fetch_pricing.py` —— `can_disable` 读错字段名：面板实际返回
  `can_disable_thinking`，旧脚本只找 `can_disable`，缺失时默认 `false`，导致 2026-10-22
  快照把全部模型的「可关思考」写成 false，与 `docs/MODEL-PROVIDERS.md` 的 ✅ 和实测矛盾。
  归一化改为 `can_disable_thinking` → `can_disable`；重新抓取后 15 个模型为 true，
  文档表里 4 个 ✅ 模型全部对上。重抓同时看到 `cn:glm-5.2` / `cn:hy4-preview` 的夜间促销
  （0.50x / 0x），文档表仍按标准价 0.79 / 0.29，不改。

### 收尾大扫除（2026-10-22）

- 清理 磁盘 —— 删 `workbuddy/__pycache__/`（40K，`.gitignore` 已排除、可再生成）与
  `workbuddy/cache/wb_pricing.json.bak-20261022-125554`（20K，价格表自动备份，
  保留最新 `wb_pricing.json`）；仓库 53109K → 53053K
- 调整 文档 —— `docs/MODEL-PROVIDERS.md` 对齐实际配置：范围行改为 OpenCode-Go 七个 /
  WorkBuddy2API 四个；WorkBuddy 快照日期改 2026-10-22（复核无倍率 / 分档变化）；
  补 `global:deepseek-v4.1-flash`、`global:deepseek-v4.1-flash-sg` 的 effort 档位；
  `cn:minimax-m3` 输出上限 524K → 512K；§5.2 的 WorkBuddy 模型数 30 → 18
- 调整 文档 —— `docs/release-notes/README.md` 补「反馈入口」规则：加粗总结后单独一行
  绝对地址 `https://github.com/MVennn/ZcodeAIModels/issues/new/choose`，然后才是 `## 本版内容`
- 调整 文档 —— `AGENTS.md` §3 改为「有 `.codegraph/` 就优先用」，与当前工作副本一致
- 清理 文档 —— PROGRESS 与 memories 里的机场出口 IP 脱敏（补记 2026-10-22 的两笔提交）
- 验证 —— `python tools/check-docs.py` 通过（20 篇）；全部 `.py` `py_compile`、
  全部 `.js` `node --check` 通过

### Issue 表单（2026-10-22）

- 新增 `.github/ISSUE_TEMPLATE/` —— 问题反馈（Bug）与功能建议两套表单，外加 `config.yml`：
  Bug 表单要求填 ZCode 版本、provider / 模型、脚本与完整命令、输出原文，
  并确认已备份 `provider_config.json`、贴出的内容不含凭据；功能建议要求先写场景并确认只改接入层

### 自动收录定时任务修复（2026-10-22）

ZCode 的每日自动收录任务报「触发运行失败」。根因是自动化的目标会话被删了
（`target_task_id` 指向 `deleted=1` 的会话 → 派发报 `Session not found`）；
另外 10:00 的两班定时窗口因机器睡眠被跳过，ZCode 不补跑。

- 修复 自动化 —— 重建每日自动收录任务为每天 **12:00**；取网关 key 的来源从
  `provider_config.json` 的 `workbuddy-low` 改成 `workbuddy/gateway/config.json`
  的 `api_key`（统一路由并组后 `workbuddy-*` provider 已不存在，原写法抛
  `StopIteration`）
- 调整 自动化 —— 目标会话置空：ZCode 派发走 `createTask` 分支，**每次运行新建
  独立会话**，上下文不再累积（该字段只读不写回，解绑永久）
- 验证 —— 12:00 那班 `dispatched → succeeded`；Go 建议收录 0 个、配置未改动；
  WorkBuddy 18 个模型并入五个 chat 组，与同步前逐个对账一致
- 调整 文档 —— MAINTENANCE §6 每日任务改 12:00 并补 key 来源、§7 登记两条脚本
  待办；TROUBLESHOOTING 补 §13「每日自动收录的体检刷出一片 400 / 403」
- 新增 数据 —— 两份 Go 同步报告（`evidence/go-model-sync/go-model-sync-20261022-*.md`）

### 守护器生命周期加固（2026-10-21 深夜）

排查「关掉 ZCode 后 wb2api 还在」：停止分支本来就有（当天 23:51 实测停过一次），
真正的问题是主进程只按 PID 判活、ZCode 退出后 2–5 秒又被拉起会**静默**取消停止、
守护器不在场时遗留的网关 / 路由没人清。

- 修复 脚本 —— `workbuddy/zcode_gateway_watch.ps1` 主进程改用**进程句柄**判存活
  （`Process.HasExited`），PID 被系统复用不再把已退出的 ZCode 误判成还在跑；
  连续两次认不出主进程才按退出处理
- 修复 脚本 —— **启动对账**：守护器启动时若没有 ZCode 主进程却还有网关 / 路由在监听，
  按遗留进程清掉（`-KeepOrphans` 可跳过，用于手动常驻网关）
- 修复 脚本 —— 停止时若没接管过 pid，按端口反查网关 / 路由再校验进程名与命令行，
  上次守护器留下的孤儿不会漏杀
- 调整 脚本 —— 宽限期 / 排空期 ZCode 回来都会写日志并取消停止（排空期回来还会把已停的
  统一路由立刻拉回）；排空上限默认 `30` → `5` 秒
- 新增 脚本 —— 每 15 分钟一条心跳日志（`-HeartbeatSeconds`），日志里没有心跳即说明守护器没了；
  `-Status` 增加脚本版本、守护器 pid，并在守护器进程早于脚本修改时间时提示「加载的是旧代码」
- 调整 文档 —— TOOLS / MAINTENANCE §8 / TROUBLESHOOTING §11 同步；补「关窗 ≠ 退出」

### 门面统一批次（2026-10-21）

在「README 收敛批次」之后再收一轮：门面压到与 GSAuxiliary 同款的七节，
开发者内容继续下沉 `docs/`，门面资源（logo / 社交预览）统一由 `assets/icon.svg` 渲染。

- 调整 文档 —— 根 README 收敛为七节（这是什么 / 环境要求 / 使用 / 反馈 / 免责声明 / 开源鸣谢 / 许可证）；
  顶部不写「一句话」引言块，定位由副标题承担（对齐 GSAuxiliary）
- 调整 文档 —— 「接一个新的模型供应商」四步下沉 [docs/MODEL-PROVIDERS.md](docs/MODEL-PROVIDERS.md) §0；
  `provider_config.json` 的三个落点与两个 `--apply` 脚本的写入差异下沉同篇 §1 / §1.1；统一路由下沉 [docs/TOOLS.md](docs/TOOLS.md) §2
- 新增 工具 —— `tools/make_social_preview.py`：自带 SVG 渲染器，从 `assets/icon.svg` 生成
  `assets/logo.png`（512×512）与 `assets/social-preview.png`（1280×640），不依赖 cairosvg 等外部程序
- 调整 资源 —— `assets/logo.png` 改为由 `assets/icon.svg` 渲染，图形不再有两份正本
- 调整 文档 —— `docs/DOC-RULES.md` 正本映射表与 `docs/README.md` 索引同步；
  各仓 docs 里指向根 README 章节的文字引用改指新正本
- 调整 仓库 —— GitHub 仓库描述与话题改成面向使用者的口径（与 README 副标题同调）

---

## [0.1.0] — 2026-10-21

本仓**首次建仓**：从同级的「OpenWrt 工作目录」里把
**AI 模型接入**这一条线整体拆出来，成为独立仓库 `ZcodeAIModels`。

拆分只做两件事：**搬文件** 与 **补文档**。**没有改动任何脚本逻辑**，
**没有改动 ZCode 的 `provider_config.json`**，也没有动原目录里的其它线
（路由器运维、ShellCrash、前端控制台等仍留在 OpenWrt 工作目录）。

### 调整

- 调整 仓库 —— 从 OpenWrt 工作目录拆出独立仓库 `ZcodeAIModels`，可独立上传 GitHub。
- 调整 目录 —— `opencode-go/ops/`：长期运维脚本（模型自动收录 + 请求头注入代理）。
- 调整 目录 —— `opencode-go/probe/`：一次性探测脚本（连通性 / 协议 / 基准 / 关思考）。
- 调整 目录 —— `opencode-go/probe/archive/`：已被取代的 `validate_zcode_models.py`。
- 调整 目录 —— `opencode-go/probe/results/20261019/`：探测原始结果快照（本地留存，不随仓库分发）。
- 调整 目录 —— `workbuddy/`：WorkBuddy2API 接入脚本 + 活数据缓存 + 日志。
- 调整 目录 —— `workbuddy/archive/`：已被取代的旧探测脚本与旧缓存。
- 调整 目录 —— `evidence/`：网关模型目录快照与自动收录报告。
- 调整 脚本 —— `go_model_sync.py`：从 `scripts/` 迁入 `opencode-go/ops/`。
- 调整 脚本 —— `opencode-header-proxy.js`：从 `scripts/` 迁入 `opencode-go/ops/`。
- 调整 脚本 —— `probe_models.py`：从 `scripts/` 迁入 `opencode-go/probe/`。
- 调整 脚本 —— `probe_protocols.py`：从 `scripts/` 迁入 `opencode-go/probe/`。
- 调整 脚本 —— `bench_models.py`：从 `scripts/` 迁入 `opencode-go/probe/`。
- 调整 脚本 —— `bench_clean.py`：从 `scripts/` 迁入 `opencode-go/probe/`。
- 调整 脚本 —— `thinking-off-probe.js`：从 `scripts/` 迁入 `opencode-go/probe/`。
- 调整 脚本 —— `validate_zcode_models.py`：从 `scripts/` 迁入 `opencode-go/probe/archive/`。
- 调整 脚本 —— `workbuddy_probe_zcode.py`：从 `scripts/` 迁入 `workbuddy/`。
- 调整 脚本 —— `workbuddy_zcode_sync.py`：从 `scripts/` 迁入 `workbuddy/`。
- 调整 脚本 —— `zcode_effective_body.js`：从 `scripts/` 迁入 `workbuddy/`（仍与探测脚本同目录，硬依赖未破）。
- 调整 脚本 —— `workbuddy_probe_models.py`：从 `scripts/` 迁入 `workbuddy/archive/`（已被取代）。
- 调整 数据 —— `wb_pricing.json`：从 `scripts/` 迁入 `workbuddy/cache/`（活数据）。
- 调整 数据 —— `wb_zcode_probe.json`：从 `scripts/` 迁入 `workbuddy/cache/`（活数据）。
- 调整 数据 —— `wb_zcode_probe.log`：从 `scripts/` 迁入 `workbuddy/logs/`。
- 调整 数据 —— `wb_model_status.json`：从 `scripts/` 迁入 `workbuddy/archive/`（已被取代）。
- 调整 数据 —— `wb_probe_rerun.log`：从 `scripts/` 迁入 `workbuddy/archive/`（一次性日志）。
- 清理 数据 —— `wb_probe_rerun.log`：一次性探测日志，结果已由 `wb_model_status.json`
  与 `workbuddy/cache/wb_zcode_probe.json` 覆盖，2026-10-21 删除。
- 调整 数据 —— `probe_results.json` / `bench_results.json` / `bench_clean.json`：从 `scripts/` 迁入 `opencode-go/probe/results/20261019/`。
- 调整 数据 —— `wb_panel_models.json`：从原 `audit/` 迁入 `evidence/`。
- 调整 数据 —— `go-model-sync-*.md`（5 份）：从原 `audit/` 迁入 `evidence/go-model-sync/`。
- 调整 文档 —— 新增根 `README.md`（门面：这是什么 / 适用环境 / 快速开始 / 文件清单 / 已知坑）。
- 调整 文档 —— 新增根 `AGENTS.md`（机器协议：PROGRESS 按逻辑任务分家 / 凭据走环境变量 / CodeGraph）。
- 调整 文档 —— 新增根 `CHANGELOG.md`（本文件）与根 `NOTICE`（第三方声明）。
- 调整 文档 —— 新增根 `.gitignore`（排除凭据、缓存、日志、大体积探测结果与字节码）。
- 调整 文档 —— 新增 `docs/README.md`（docs 唯一索引，四类分区）。
- 调整 文档 —— 新增 `docs/DOC-RULES.md`（文档规则正本）。
- 调整 文档 —— 新增 `docs/MODEL-PROVIDERS.md`（provider 分组 / 协议 / 工具调用 / 关思考参数矩阵的正本）。
- 调整 文档 —— 新增 `docs/PITFALLS.md`（踩坑总汇）。
- 调整 文档 —— 新增 `docs/TROUBLESHOOTING.md`（排错手册，现象 → 排查步骤 → 原因 / 解法）。
- 调整 文档 —— 新增 `docs/MAINTENANCE.md`（价格表刷新 / 探测限速 / 快照保留 / 备份回退 / 热重载注意事项）。
- 调整 文档 —— 新增 `docs/release-notes/README.md`（Release 说明格式正本）与 `docs/release-notes/0.1.0.md`（首版说明；当时文件名带 `v` 前缀，2026-10-22 统一去掉）。
- 调整 进度 —— 根 `PROGRESS.md` 承接本仓唯一进度台账（追加式批次日志）。
- 调整 进度 —— 原 `PROGRESS.workbuddy.md` 归档到 `evidence/`，作为 WorkBuddy 接入线的历史台账。

### 修复

- 修复 凭据外置 —— OpenCode-Go API key 从源码移到**环境变量**：
  `opencode-go/probe/` 下 **5 个探测脚本**（`probe_models.py`、`probe_protocols.py`、
  `bench_models.py`、`bench_clean.py`、`thinking-off-probe.js`）里的明文 `oc_sk_…`
  **全部删除**，改为 `os.environ.get("OPENCODE_GO_KEY")` /
  `process.env.OPENCODE_GO_KEY`；**未设置时明确报错退出**，不再带着空 key 去请求
- 修复 文档 —— [README.md](README.md) 的「适用环境」与「快速开始」补 `OPENCODE_GO_KEY`，
  「已知坑」第 6 条从「仍有明文 API key」改为「已改为环境变量读取，未设置时明确报错」

> 新增的环境变量：**`OPENCODE_GO_KEY`**（必填）。
> 复核结果：本仓已**不再有任何明文 key**（`oc_sk_` 全文检索无命中）。

### 待补

- `LICENSE` —— **已补**：仓库根的 MIT 全文（见 [LICENSE](LICENSE)）。
- `docs/VERSIONING.md` —— **已补**：版本晋升规则的独立正本（见 [docs/VERSIONING.md](docs/VERSIONING.md)）。
- ~~待补 `workbuddy_fetch_pricing.py`~~ —— **已补**：`workbuddy/workbuddy_fetch_pricing.py`
  从网关 `/panel/api/models` 拉价格、归一化后写入 `cache/wb_pricing.json`（写前自动备份），
  并打印倍率变化 / 新增 / 下架的摘要；`--dry-run` 可只看不写。
  归一化后的字段集与既有价格表**完全一致**（合成数据自测通过）。
- ~~待补 路径修正~~ —— **已修**：`go_model_sync.py` 的报告目录改为本仓内 `evidence/`，
  可用 `GO_SYNC_REPORT_DIR` 覆盖；`workbuddy_probe_zcode.py` 与 `workbuddy_zcode_sync.py`
  的价格表 / 探测缓存默认路径改为 `cache/`（拆仓时漏改，本次补上）。

### 新增

- 新增 `workbuddy_fetch_pricing.py` —— WorkBuddy 侧；`python workbuddy_fetch_pricing.py`
  一条命令刷新价格表，取代手工维护（详见 `docs/MAINTENANCE.md` §1.3）。

### 通用化（2026-10-20）

> 这一轮把仓库从「只对某一台机器/某一个人成立」改成「**任何用 ZCode 的人都能照着做**」。
> **规则与做法用通用措辞；WorkBuddy2API 与 OpenCode-Go 这两个具体实例单列。**

- 调整 定位 —— 根 [README.md](README.md) 从「把 OpenCode-Go 与 WorkBuddy2API 接进 ZCode」
  改成「把**任意**模型供应商接进 ZCode（以这两个为例）」，并新增
  「通用方法：接一个新的模型供应商」四步（摸清接口面 → 归一化价格表 → 用 ZCode 真实 body 探测 → 分档写配置）。
- 调整 文档 —— [docs/MODEL-PROVIDERS.md](docs/MODEL-PROVIDERS.md) 新增 §0「接一个新的模型供应商」
  与「通用概念 ↔ 本仓叫法」对照表；§2 / §4 标注为本次实例。
- 调整 文档 —— [docs/MAINTENANCE.md](docs/MAINTENANCE.md) §1 拆成「§1.1 通用做法（换供应商照这个做）」
  + 「§1.2 / §1.3 两个实例」，并给出「取目录 → 归一化 → 写盘 + 变动摘要」的三步通用做法。
- 调整 文档 —— [docs/SECRETS.md](docs/SECRETS.md) 凭据位置表补一行「其它供应商的凭据」，
  明确**任何**供应商的凭据都只走环境变量，并给出加新供应商时的三步清单。
- 调整 文档 —— [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) 与
  [docs/PITFALLS.md](docs/PITFALLS.md) 每条加【通用】/【实例 A】/【实例 B】标记，
  区分「换供应商也成立」与「只有本仓实例才有」。
- 修复 路径 —— 文档与脚本里的**本机绝对路径**（写死的用户名主目录、旧仓库目录）改为
  仓内相对路径 / `~/.zcode/...` / 按脚本位置与当前用户主目录推导。
- 修复 路径 —— `go_model_sync.py` 的 ZCode 配置路径默认值改为按当前用户主目录推导
  （**在本机解析结果不变**），仍可用 `--config` 覆盖。
- 调整 文档 —— `PROGRESS.md`、`evidence/PROGRESS.workbuddy.md` 里的设备型号改为通用措辞
  （历史探测结论与数据一律保留原样，并保留采集时点）。
- 调整 文档 —— `memories/` 下四个文件里的绝对路径改为仓内相对路径。

### README 收敛批次（2026-10-21）

参照系列仓 gsauxiliary 的门面格式，把根 `README.md` 收敛为**面向用户**的说明，
开发者向的内容下沉 `docs/`：

- 调整 文档 —— 根 README 顶部去掉「一句话」引言块，门面定位由副标题承担（对齐 gsauxiliary）；`tools/check-docs.py` 同步豁免根 README 的引言块检查

- 调整 文档 —— 根 README 重写为 logo 头 + 徽章 + 这是什么 / 适用环境 / 快速开始 /
  接一个新的模型供应商（四步概览）/ 与 ZCode 的关系 / 反馈 / 免责声明 / 开源鸣谢 / 许可证；
  删掉「文件清单」「目录结构」「已知坑」「记忆文档」「参与与治理」等开发者向章节
- 调整 文档 —— 新增 [docs/TOOLS.md](docs/TOOLS.md)：工具清单**正本**（产物与去留标记），
  取代原根 README 的「文件清单」；「已知坑」统一看 [docs/PITFALLS.md](docs/PITFALLS.md)
- 调整 文档 —— DOC-RULES / MAINTENANCE / MODEL-PROVIDERS / docs/README 里指向根 README
  「文件清单 / 已知坑」的引用，同步改指新位置
- 修复 CI —— 当时的流水线配置只定义了隐藏模板 `.python`、没有任何可见作业，
  流水线一创建就失败（零作业）；改为语法与文档两组真实作业

### 反代排序批次（2026-10-21）

WorkBuddy2API 三个 provider 的模型顺序改为「主力置顶 → CN 优先 → 按厂商分组」：

- 变更 脚本 —— `workbuddy_zcode_sync.py`：新增 `PINNED_MODEL_IDS` / `VENDOR_ORDER` /
  `model_sort_key()`，`personalModelIds` 与 `modelOrder` 按新规则排序；
  新增 `--reorder-only`（只重排，不改成员与档位）
- 变更 配置 —— 界面顺序改为 低代 → 免代 → 高代；低代首位固定 `cn:deepseek-v4.1-flash`
- 修复 排序 —— 原「全表按倍率升序 + id」把 CN/全球与不同厂商打散，
  主力 `cn:deepseek-v4.1-flash` 落到低代第 8 位
- 调整 文档 —— MODEL-PROVIDERS §4.2–§4.5、TOOLS 同步；记录促销漂移
  （`cn:hy4-preview` 已 `0x`、`cn:glm-5.2` 促销 x0.50，下次完整同步再改档）

### 自动收录扩展批次（2026-10-21）

- 变更 自动化 —— 每天 10:00 的收录任务从「只跑 Go」扩展为「Go + WorkBuddy」：
  执行 `go_model_sync.py --apply`、`workbuddy_fetch_pricing.py`、
  `workbuddy_probe_zcode.py --max-rate 0.3 --sleep 20`、
  `workbuddy_zcode_sync.py --max-rate 0.3 --apply`
- 变更 分档 —— WorkBuddy 收价上限从 0.80 收到 **0.30**（以主力 x0.11 锚定）：
  低代只留 ≤0.16 的主力价位；0.17–0.30 归高代；原高代 x0.50–0.79（4.5–7.2 倍）
  整组移出，自动收录也不再引进
- 修复 自动化 —— 旧任务 `automation-5ad749e3…` 指向已删除的旧目录 `Openwrt/`，
  已停用；新任务 `automation-cfcb5c6d…` 绑定当前仓库
- 调整 文档 —— MAINTENANCE §6 定期动作同步为双线

### 网关随 ZCode 起停批次（2026-10-21）

反代（`wb2api`）不再需要手动开 cmd 拉起，网关寿命跟随 ZCode：

- 新增 脚本 —— `workbuddy/zcode_gateway_watch.ps1`：无窗口守护器。ZCode 启动 →
  静默拉起 `wb2api`（清空 HTTP(S)_PROXY，与 `run.bat` 一致）；ZCode 全部退出 →
  宽限 8 秒后停网关；运行期间每 15 秒探活，网关挂了自动重启（失败退避 60 秒）
- 新增 脚本 —— `workbuddy/zcode_gateway_watch.vbs`：wscript 无窗口启动上述 ps1，
  不出现控制台窗口
- 新增 开关 —— `-Install` 在启动文件夹注册快捷方式（登录自启）并立即启动守护器；
  `-Uninstall` 移除自启并停守护器；`-Status` 一次看 ZCode / 网关 / 守护器；
  `-DryRun` 只记状态迁移，用于验证状态机
- 调整 文档 —— TOOLS、MAINTENANCE §8、TROUBLESHOOTING §11、docs/README、
  README 适用环境、MODEL-PROVIDERS §4
- 注意 —— 网关的定时任务（签到 / 保活 / 夜猫子）只在网关进程活着时执行；
  绑到 ZCode 生命周期后，ZCode 不在的时段不会跑（详见 MAINTENANCE §8）

### 网关目录并入本仓批次（2026-10-21）

反代网关的整个 clone 搬进仓库，不再维护两个目录：

- 变更 目录 —— 旧网关目录 `<旧网关安装目录>` → `workbuddy/gateway/`
  （含上游 `.git`、`config.json`、`auths/`、`data/`、`wb2api.exe`）；旧目录已删除
- 变更 忽略 —— 主仓 `.gitignore` 整目录排除 `workbuddy/gateway/`（账号凭据、密钥、
  运行时状态、二进制都不进公开仓库）；网关仍可用
  `git -C workbuddy/gateway pull --ff-only` 更新
- 变更 脚本 —— `zcode_gateway_watch.ps1` 的默认网关目录改为按脚本位置推导
  `<仓库>/workbuddy/gateway`（`WB_GATEWAY_DIR` 仍可覆盖）
- 变更 工具 —— `tools/check-docs.py` 跳过 `workbuddy/gateway/`（不入库的上游 clone）
- 调整 文档 —— MAINTENANCE §8（更新 / 重建网关目录的步骤）、TOOLS、SECRETS、
  TROUBLESHOOTING §11、NOTICE
- 说明 —— 上游检查：`origin/main` = 本地 `6b31db6`，无新提交，未产生 pull 变更

### 网关 ↔ ZCode 联动优化批次（2026-10-21）

守护器从「按进程名数数」升级为「盯主进程 + 就绪判定 + 排空」：

- 变更 判据 —— 只跟随 ZCode **主进程**（命令行既不含 `--type=` 也不含 `zcode.cjs`）；
  GPU / renderer / crashpad / CLI 宿主晚退不再拖住网关
- 变更 启动 —— 轮询 1000 → 500 ms；就绪判定从「TCP 端口打开」改为 `/panel/` 返回 200；
  网关 stdout / stderr 每次启动前轮转为 `.1`
- 新增 停网关前排空 —— 最多等 `-DrainTimeoutSeconds`（默认 30 秒）让在途连接结束；
  宽限期内 ZCode 重新打开则取消停止
- 新增 联动检查 —— `-Status` 增加 ZCode 主进程 PID、网关就绪状态，并校验
  `workbuddy-*` 三个 provider 的 `baseUrl` / `apiKey`（只报状态，不打印值）；
  ZCode 每次启动时也做同一校验，不匹配写「联动警告」到日志
- 修复 `-Uninstall` —— 排除当前进程，避免把自己的 PowerShell 一起结束
- 调整 文档 —— MAINTENANCE §8、TOOLS、TROUBLESHOOTING §11

### 外部跑分参考收录（2026-10-21）

- 新增 文档 —— `docs/BENCHMARKS.md`：收录第三方公开榜「AI 能力专项测试」
  （7 题 · 4 方向 · 总分 400）的四个榜单入口、评测口径、2026-09-11 总分榜快照、
  四方向 / 逐题前三，以及本仓在配模型在榜上的位置与读法
- 调整 文档 —— `docs/README.md` 参考资料索引、`docs/DOC-RULES.md` §1 / §2、
  `docs/MODEL-PROVIDERS.md` §6 补交叉链接
- 说明 —— 榜单数据非本仓实测，分数会随站点更新变化；本篇只做快照，不替代 `evidence/` 下的本仓探测结果
- 调整 文档 —— 按榜单四方向重排本仓在配模型：`BENCHMARKS.md` §5.1 / §5.2 增方向榜与
  每模型最强方向；`MODEL-PROVIDERS.md` §6.1 增方向首选表；**provider 分档未改**，
  方向只作第二轴（理由见 BENCHMARKS §5.3）
- 调整 文档 —— 以 `deepseek-v4.1-flash`（总分 342.40 / 输出 $1.20/M / 倍率 0.11）
  为 100 基准，新增 `BENCHMARKS.md` §5.4 与 `MODEL-PROVIDERS.md` §6.2：
  按智力指数、价格指数、性价比把在配模型分为主力 / 低耗 / 高耗 / 免费 / 备用；
  未上榜模型保持原组（本轮只做选型层，备用档落地见下一条）

### 备用档落地（2026-10-21）

- 新增 provider —— `opencode-go-chat-backup`（备用）：按 DeepSeek 基准性价比 < 1，
  移入 `minimax-m3`；`opencode-go-chat-slow` 只剩 `longcat-2.0`
- 新增 provider —— `workbuddy-backup`（备用）：移入 `cn:deepseek-v4-flash`、
  `cn:minimax-m3`；同时按实时价把 `cn:hy4-preview` 从免代移到高代（x0.29）
- 变更 脚本 —— `go_model_sync.py` 增 `BACKUP_MODEL_IDS` / `--reclassify-only`；
  `workbuddy_zcode_sync.py` 增第四档 `backup` / `--reclassify-only`
- 变更 配置 —— 本机 `provider_config.json` 已写入；备份
  `.bak-reclassify-20261021-174621`、`.bak-wbproxy-20261021-174621`、
  `.bak-wbproxy-20261021-174649`
- 调整 文档 —— MODEL-PROVIDERS §2.1 / §2.5.1 / §4.2 / §4.3 / §4.5.1 / §6.2、
  TOOLS、MAINTENANCE、TROUBLESHOOTING、BENCHMARKS §5.4
- 调整 文档 —— `BENCHMARKS.md` §5.4 把 OpenCode-Go / WorkBuddy 两张分档表
  合并为一张，按主力 → 低耗 → 高耗 → 免费 → 备用排序；价格列保留原单位，
  横比看已归一的「价格指数」

### 统一路由：WorkBuddy 并入五个 chat 组（2026-10-21）

- 新增 脚本 —— `tools/unified-router.js`：按 model 前缀分流 `cn:` / `global:` →
  WorkBuddy 网关，其余 → OpenCode-Go；监听 `127.0.0.1:7871`，`GET /health` 做健康检查
- 变更 配置 —— 删除 `workbuddy-low/free/high/backup` 四个 provider；18 个 WorkBuddy
  模型并入 `opencode-go-chat/-free/-fast/-slow/-backup`；五个 chat 组 `baseUrl`
  指向路由；`对话` / `响应` 仍直连 OpenCode。备份
  `provider_config.json.bak-unified-*` / `.bak-wbproxy-*`
- 变更 脚本 —— `workbuddy_zcode_sync.py` 默认 unified 模式（`--separate` 保留旧四档）；
  `--reclassify-only` 适配统一模式；`apply_unified` 每次先清掉目标组里的 WorkBuddy
  模型再重放，避免重复
- 变更 守护器 —— `zcode_gateway_watch.ps1` 随 ZCode 启停统一路由；`-Status` 显示
  路由与五个 chat 组；新增 `-RouterPort` / `-RouterScript` / `-NoRouter`；
  日志 `router.stdout.log` / `router.stderr.log`
- 调整 文档 —— MODEL-PROVIDERS §2 / §4 / §6.2、TOOLS、MAINTENANCE §4.4 / §8、
  TROUBLESHOOTING §11 / §12、PITFALLS §12、SECRETS、docs/README
- 说明 —— 统一路由是本地进程；ZCode 不开时由守护器停掉。回退：恢复
  `.bak-unified-*`，或 `workbuddy_zcode_sync.py --separate --apply` 重建四档
