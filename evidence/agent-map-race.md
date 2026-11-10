# zgate 跳/竞速/冷却/超时 执行链路地图

> **一句话**：真实执行链是 `routeChain → racePolicyFor → raceChain(并发编排) → attemptChain(单跳) → doForwardWith(看门狗/首块) → doForward(响应头超时)`，冷却/静默是「按物理跳（含出口）」两张表，而对冲与首块参数**只取链首渠道的策略**。

调查基线：`F:/Project/ModelBus` 分支 main，只读；本文件为本次唯一写入产物。

---

## 1. race.go 函数清单与 raceChain 编排

### 1.1 符号清单（`gateways/zgate/internal/router/race.go`）

| 行号 | 符号 | 职责 |
|---|---|---|
| 30-37 | `raceGate` | 赢家闸门：`mu / claimed / winner / cancels / lastErr` |
| 39-42 | `gateCancel` | 一路尝试的 `{id, cancel}` |
| 46-54 | `(*raceGate).register` | 登记取消函数；**登记时已有赢家则立刻 cancel 这一路**（后补路不烧额度） |
| 58-78 | `(*raceGate).claim` | 抢写端：首个调用者胜，其余 `cancel()`；同 id 重复调用幂等 |
| 80-84 | `(*raceGate).isClaimed` | 是否已有赢家 |
| 87-94 | `(*raceGate).winnerID` | 赢家下标，无则 -1 |
| 101-110 | `(*raceGate).noteErr` | 记链上出现过的最小失败码（只记 >=300） |
| 113-117 | `(*raceGate).errorStatus` | 读该最小失败码（0 = 无），决定回 4xx 还是 502 |
| 119-126 | `raceWriter` | 每路私有写端：`dst/gate/id/hdr/lost/claimed` |
| 128-130 | `newRaceWriter` | 构造，私有 `http.Header{}` |
| 132 | `(*raceWriter).Header` | 返回私有 header（防输家污染赢家响应头） |
| 134-151 | `(*raceWriter).WriteHeader` | **<300 才抢闸门**；>=300 只 `noteErr`+`lost`，不写任何字节 |
| 153-158 | `(*raceWriter).Write` | 输家/未抢到 → 吞掉并返回 `len(b)` |
| 161-168 | `(*raceWriter).Flush` | 满足 `http.Flusher`，输家不 flush |
| 176-222 | `hasContentDelta` | 只认 `choices[].delta.content/reasoning_content` 或 Gemini `candidates[].content.parts[].text` 非空 |
| 228-281 | `peekFirstContent` | 读到首个真实内容块或超时；返回已消费字节（调用方 MultiReader 拼回） |
| 284-292 | `attemptCtl` | 竞速模式控制块：`gate/id/policy/hopTag/hop`（**定义在 race.go，不在 router.go**） |
| 295-301 | `(*Server).channelPolicy` | 按渠道取 `ChannelPolicy`，未配置返回零值 |
| 306-334 | `(*Server).racePolicyFor` | 判定整链是否走对冲，并**返回链首渠道的策略** |
| 343-371 | `(*Server).noteSerialFallback` | 「本该对冲却退回串行」的现场告警，同签名 10 分钟一条 |
| 374-385 | `uniqueStrings` | 保序去重（只用于告警文案） |
| 399-431 | `(*Server).rankedChain` | 发车顺序：ok 按首块毫秒升序 → 无观测/过期按声明序 → 失败排最后 |
| 434-441 | `sameChannel` | 整链是否同一渠道 |
| 445-459 | `(*Server).firstLiveHop` | 首个「未禁渠道 + 不在冷却 + 有 key」的跳 |
| 463-592 | `(*Server).raceChain` | 竞速编排器 |

`hopStatSnap / stale / raceFailTTL / raceOKTTL / noteRaceHop / raceSnapshot` **不在 race.go**，在 `router.go`：
`router.go:251-258`（结构体）、`router.go:264-267`（TTL 常量）、`router.go:271-280`（stale）、`router.go:283-296`（noteRaceHop）、`router.go:315-323`（raceSnapshot）。

### 1.2 raceChain 并发 / 赢家 / 回落

发车闸门与并发上限：

```go
// race.go:464-467
maxParallel := pol.MaxParallel
if maxParallel <= 0 {
    maxParallel = 2
}
```

每路一个 goroutine，统一走 `attemptChain`，只带 `idx` 与 `attemptCtl`：

```go
// race.go:505-511
at := &attemptCtl{gate: gate, id: idx, policy: pol, hopTag: hopKeyForLog(t.Chain[idx]), hop: t.Chain[idx]}
...
go func() {
    s.attemptChain(rw, rr, body, model, t, path, search, idx, at)
    resCh <- idx
}()
```

对冲计时（三级降级：HedgeAfterMs → FirstBlockMs → 1200ms）：

```go
// race.go:514-520
hedge := time.Duration(pol.HedgeAfterMs) * time.Millisecond
if hedge <= 0 { hedge = time.Duration(pol.FirstBlockMs) * time.Millisecond }
if hedge <= 0 { hedge = 1200 * time.Millisecond }
```

- **maxParallel 生效点**：只有两处补充发车判断 —— `race.go:556`（有路结束时 `live < maxParallel && pos < len(order)`）与 `race.go:582`（hedge 定时器到点 `!gate.isClaimed() && live < maxParallel && pos < len(order)`）。默认 2 = 最多叠一层。
- **赢家选中**：不是编排器选，而是写端抢闸门 —— `raceWriter.WriteHeader` 收到 <300 时 `gate.claim(id)`（`race.go:142`），第一个抢到者胜，其余路被 cancel；「先回 200 但空流」不构成赢家（空流由首块看门狗 `peekFirstContent` 判失败）。
- **编排器收口**：`race.go:537-540` 赢家 goroutine 返回即 `return`，请求结束。
- **失败回落**：输的那一路在 `router.go:1401-1407` 的 `fail` 里因 `at != nil` 只记日志、不续链；由 `race.go:556-562` 补发下一跳。全部失败时 `race.go:571-579`：有 4xx 就回原状态码，否则 502。
- **整链被摁停**：`race.go:545-555`（渠道被禁用且整链同渠道 → `cancelAll()` 后立即回 4xx/502），避免还在路上的一路把首字拖到几十秒。
- **全链短冷却兜底**：`race.go:469-483` 只 `clearSilence`（软冷却）；`cool` 表（429/5xx/死跳/额度）一个字都不清。

---

## 2. 「策略取 Chain[0]」出现在哪些行

### 2.1 两处链首取值

```go
// race.go:329（racePolicyFor 取链首渠道策略）
pol := cfg.ChannelPolicy[t.Chain[0].Channel]
if pol.HedgeAfterMs <= 0 && pol.FirstBlockMs <= 0 { return config.ChannelPolicy{}, false }

// race.go:347（noteSerialFallback 同样只看链首）
pol := s.channelPolicy(t.Chain[0].Channel)
```

`raceChain` 收到这一个 `pol` 后，**每一路都复用它**：`race.go:505` 的 `policy: pol`。因此竞速模式下不存在「每跳用自己渠道策略」——只有按渠道名实时查的三项（headerTimeout / silence / soft）是逐跳的。

### 2.2 各参数取值来源

| 参数 | 取值位置 | 粒度 |
|---|---|---|
| 对冲触发条件 | `race.go:307-333`：`len(t.Chain) < 2 || !wantsStream(body)` → false；任一跳非 chat → false；任一跳渠道不在 `cfg.ChannelPolicy` → false；链首 `HedgeAfterMs` 与 `FirstBlockMs` 都 <= 0 → false | **链首 + 全链一致性**（逐跳只校验「是否配置过」，不读值） |
| `HedgeAfterMs` | `race.go:514` | **链首** |
| `FirstBlockMs` | `race.go:505` → `router.go:934-936`（`at.policy.FirstBlockMs`） | **链首** |
| `MaxParallel` | `race.go:464` | **链首** |
| `RateLimitBackoffMs` | `router.go:929`（`at.policy.RateLimitBackoffMs < 0` → 不就地 429 退避） | **链首** |
| `HeaderTimeoutSec` | `router.go:956-957` 传 `hop.Channel` → `doForward` `:867` → `headerTimeout` `router.go:340-359` | **每跳（按渠道）** |
| `SilenceCooldownSeconds` | `router.go:977`（`hop.Channel`）、`router.go:1145`（`at.hop.Channel`）→ `silenceCooldownFor` `router.go:157-163` | **每跳（按渠道）** |
| `SoftCooldownSeconds` | `router.go:1539`（`hop.Channel`）→ `softCooldownFor` `router.go:148-154` | **每跳（按渠道）** |
| `AuthFailCooldownHours` | `router.go:238-247`（`markChannelOff(hop.Channel)`） | 渠道级 |

配置现状（`gateways/zgate/zgate.json:14-28`）：`GM` 有 `hedgeAfterMs=18000 / maxParallel=2 / softCooldownSeconds=60 / rateLimitBackoffMs=-1 / silenceCooldownSeconds=0 / headerTimeoutSec=-1`；`HJ` **只有** `headerTimeoutSec=-1`（无对冲、无首块）。按当前配置，GM+HJ 混链因 `race.go:330-332` 链首 GM 有 hedge 仍走竞速，但 HJ 跳吃的是 GM 的 hedge 与 firstBlock。

---

## 3. router.go 的执行函数与冷却读写点

| 位置 | 符号 | 要点 |
|---|---|---|
| `router.go:1363-1382` | `routeChain` | `if pol, ok := s.racePolicyFor(t, body); ok { s.raceChain(...); return }`（1376-1379），否则 `noteSerialFallback` + `attemptChain(..., 0, nil)`（1380-1381） |
| `router.go:1384-1560` | `attemptChain` | 单跳执行器；串行模式 `at=nil` 靠 `index+1` 递归回落（1406 / 1472 / 1494 / 1555），竞速模式 `at!=nil` 只记日志（1401-1407） |
| `router.go:1408-1412` | 冷却判死入口 | `if s.cooling(hop) { log; fail("冷却中") }` |
| `router.go:1434-1499` | 桥接跳分支 | 桥接跳自己写流：`coolBridgeFailure`(1476)、地区受限(1480-1484)、`finishBridge`(1497) |
| `router.go:1507-1547` | `accept` 闭包 | 冷却判定集中地：poolDown→渠道暂停(1511)、authFatal→禁用渠道(1517)、hopFatal/quota(1520-1525)、region(1526-1532)、504(1533-1538)、5xx 软冷却(1539-1545) |
| `router.go:1548-1559` | `doForwardWith` 调用 | `retry` 闭包里 `s.noteRaceHop(at.hopTag, 0, reason)`(1551)；`onThrottled` 记 429 冷却(1558)；末参 `&hop` |
| `router.go:340-359` | `headerTimeout` | 优先级：`s.headerWait`（测试）> 该渠道 `HeaderTimeoutSec`（<0 关看门狗）> 全局 `UpstreamHeaderTimeoutSec`（<0 关）> 常量 12s（`router.go:123`） |
| `router.go:866-903` | `doForward` | 只在 `wantsStream` 且 `wait>0` 时挂响应头看门狗；超时 `return nil, fmt.Errorf("%w within %v", errUpstreamSilent, wait)`（901） |
| `router.go:905-...` | `doForwardWith` | 主循环：`inPlace429`(929)、`firstBlock`(933-936)、`doForward`(957)、沉默路径(966-988，`markSilence` 978)、传输层重试一次(993-1002)、`accept`(1017-1041)、reasoning guard(1043-1127)、首块看门狗(1128-1155)、`w.WriteHeader`(1166)、`noteRaceHop`(1139 / 1154 / 1170) |
| `router.go:166-170` | `markSilence` | 只写 `silence[hopKey(hop)]` |
| `router.go:460-469` | `markCooling` / `markCoolingFor` | `markCooling` 是 30min 包装器，**全仓无调用方**（仅定义）；实际都走 `markCoolingFor`，写 `cool[hopKey(hop)]` |
| `router.go:417-440` | `cooling` | 读两张表并顺手清过期键：先 `cool`(425-431)，再 `silence`(432-438)；渠道 `off` 命中直接 true(418-421) |

`attemptCtl` 字段与唯一写入方：

| 字段 | 含义 | 写入方 |
|---|---|---|
| `gate` | 赢家闸门；nil = 串行 | `race.go:505` |
| `id` | 链上下标 | `race.go:505` |
| `policy` | **链首** `ChannelPolicy` | `race.go:505` |
| `hopTag` | 日志/观测键 `hopKeyForLog` | `race.go:505` |
| `hop` | 本跳实体，判死后上冷却用 | `race.go:505` |

---

## 4. 冷却表：cool 与 silence

键是 `hopKey`，**含出口**，物理跳粒度：

```go
// router.go:387
func hopKey(hop alias.Hop) string { return hop.Channel + "|" + hop.Upstream + "|" + hop.Proxy }
// router.go:413-415（日志形态，proxy 经 maskProxy 脱敏；冷却表不用这个）
func hopKeyForLog(hop alias.Hop) string { return hop.Channel + "|" + hop.Upstream + "|" + maskProxy(hop.Proxy) }
```

| 表 | 定义 | 写入 | 读取 / 删除 | TTL 来源 |
|---|---|---|---|---|
| `cool` | `router.go:46`（`map[string]time.Time`，锁 `coolMu` 45） | `router.go:467`（`markCoolingFor`）← 调用点 `router.go:490`(429 桥接)、`493`(504 桥接)、`1469`(hopFatal/quota)、`1483`(桥接 region)、`1522`(hopFatal)、`1531`(region)、`1537`(504)、`1544`(5xx 软冷却)、`1558`(429 退避后仍 429) | `router.go:425-431`（`cooling` 读+过期删除）；`router.go:502-505`（`coolingCount` 顺带清过期） | `hopCooldown`=30m `router.go:79`；`rateLimitCooldown`=45s `router.go:84`；`timeoutCooldown`=5m `router.go:127`；`regionCooldown`=30m `router.go:135`；`quotaCooldown`=24h `router.go:141`；`softCooldownFor` 取策略 `softCooldownSeconds`（148-154） |
| `silence` | `router.go:50`（同锁 `coolMu`） | `router.go:168`（`markSilence`）← 调用点 `router.go:978`（`errUpstreamSilent`，读 `hop.Channel` 的策略）、`router.go:1146`（首块超时，读 `at.hop.Channel`） | `router.go:432-438`（`cooling` 读+清理）；删除 `router.go:181`（`clearSilence`）← 调用点 `race.go:475` | `silenceCooldownFor` 取策略 `silenceCooldownSeconds`（157-163），0 = 不写表 |

另有一张正交的 `off`（整渠道禁用）：`router.go:54` 定义，`router.go:198` / `245` 写入，`router.go:223-235` 读取。

**单跳链（`len(Chain)==1`）是否走同一条 markSilence 路径：是。**
`racePolicyFor` 第一关就是 `len(t.Chain) < 2` → false（`race.go:307`），于是 `routeChain:1381` 调 `attemptChain(..., 0, nil)`，而 `attemptChain:1548` 仍传 `&hop`（非 nil），所以 `doForwardWith` 的沉默分支 `router.go:976-981` 照常 `markSilence(*hop, d)`。
唯一差别：首块看门狗要求 `at != nil && at.policy.FirstBlockMs > 0`（`router.go:933-936`），单跳链 `at==nil`，因此 `router.go:1145` 那条 silence 写入永远不会发生 —— 单跳链只有「连响应头都不给」会进 silence 表。

---

## 5. early_sse.go

字段（`early_sse.go:41-56`）：

| 字段 | 作用 |
|---|---|
| `dst / flusher` | 下游写端与其 Flusher（`:59` 断言） |
| `mu / hdr / committed / early / failed / swallow / status / trapped` | `committed`=已交卷；`early`=不是下游自己写的状态码；`failed`=已写过流内 error；`swallow`=扣下下游错误体；`trapped` 上限 4096（`:36`） |
| `stop / once` | 关心跳的通道与一次性关闭 |

流程：

- **start**（`:149-180`）：`commitAfter<=0` 直接返回；keepalive 缺省 10s；goroutine 等 `commitAfter` 或 `stop`，到点 `commitEarly()` 失败（已交卷/已失败）即退出，否则进 ticker 循环 `ping()`。
- **commitEarly**（`:182-193`）：未 committed 且未 failed 时 `commitLocked(200, true)` 并 flush；`commitLocked`（`:125-146`）在 `early=true` 时自己立 SSE 头（`text/event-stream` / `no-cache` / `keep-alive` / `X-Accel-Buffering: no`）并 `Del("Content-Length"/"Content-Encoding")`。
- **ping**（`:195-211`）：写 `": zgate keepalive"` 注释行并 flush；写失败即停。
- **WriteHeader**（`:65-83`）：未交卷 → 原样透出（老行为）；已交卷且 `code>=300` → 只把 `status` 记成最大值并置 `swallow`，不写状态码。
- **Write**（`:85-105`）：`swallow` 时截断进 `trapped` 并返回 `len(b)`；未交卷时隐式 200。
- **finish**（`:215-223`）：`stopPings()` 后，只有 `!failed && committed && early && swallow` 才 `writeErrorLocked(errorMessageLocked(), status)`。
- **errorMessageLocked**（`:255-273`）：从 `trapped` JSON 取 `error.message` 或顶层 `message`，取不到用 `"upstream failed with status N"`。
- **writeErrorLocked**（`:275-293`）：写 `data: {"error":{"message":...,"type":"upstream_error","code":status}}` + `data: [DONE]`，flush，置 `failed`。
- **fail**（`:226-251`）：panic 兜底；未交卷回真 JSON+状态码，已交卷且 `early` 则写流内 error。
- **接入点**：`router.go:601-608`，条件 `isChat && wantsStream(body) && s.earlyCommitWindow() > 0`；`early = newEarlySSEWriter(w)`、`defer early.finish()`、`w = early`。竞速与串行都在这一层之内，所以 raceChain 全灭时的 `writeJSON(w, 502, ...)`（`race.go:493 / 550 / 553 / 575 / 578`）也会被改写成流内 error。

**日志：无。** `early_sse.go` 内没有任何 `s.log` / `log.` 调用（grep 0 命中，imports 亦无 logx）。

---

## 6. go vet 现状

```
# cd gateways/zgate && go vet ./...
Go: /f/Program Files/Go/bin/go.exe   （= /c/Program Files/Go/bin/go.exe）
EXIT=0   无任何输出
```

结论：当前工作树可编译、vet 干净（基线可信，后续改动可对照）。

---

## 7. per-hop 化改造会碰到的最小改动点（只列函数与行号）

| 位置 | 现状 | 为什么要动 |
|---|---|---|
| `race.go:306-334` `racePolicyFor` | 返回单个 `config.ChannelPolicy` + 全链「是否配置过」校验 | 需改成逐跳策略（或返回 `[]config.ChannelPolicy`），并定「混链判定」新口径 |
| `race.go:463` `raceChain` 签名 | 形参 `pol config.ChannelPolicy` | 传参换成逐跳策略集合 |
| `race.go:464-467` | `maxParallel := pol.MaxParallel` | 逐跳上限的聚合口径（取最大 / 取链首） |
| `race.go:505` | `policy: pol` 单值写入 `attemptCtl` | 改为从 `pols[idx]` 取 |
| `race.go:514-520` | 单个 `hedge` 由链首三级降级算出 | 每 hop 一个 hedge，需多 timer |
| `race.go:524-530` | `order := s.rankedChain(...)` + 单 `timer` 首发 | 每跳独立 timer 的初始化 |
| `race.go:533-591` | `select` 只有 `resCh / timer.C / ctx.Done` 三路 | 多 timer 的 select 与重排 |
| `race.go:556`、`race.go:582` | `live < maxParallel` 两处共用同一上限 | 逐跳上限下的发车判据 |
| `race.go:581-587` | `resetTimer(timer, hedge)` 单计时器 | 换 timer 组 |
| `race.go:284-292` `attemptCtl` | `policy` 单字段 | 结构体本身要按跳携带策略/上限 |
| `router.go:929` | `inPlace429 := !(at != nil && at.policy.RateLimitBackoffMs < 0)` | 改成按 `at.hop` 渠道取策略 |
| `router.go:933-936` | `firstBlock` 全取自 `at.policy.FirstBlockMs` | 同上 |
| `router.go:1548-1559` | `doForwardWith(..., hop.Channel, ..., at, &hop)` | 传参面：新增逐跳 policy 参数，或由 `at.hop` 现查 |
| `router.go:343-371` `noteSerialFallback` | 只查链首渠道策略决定是否告警、缺失列表按全链算 | 逐跳后判据要重写，否则会刷「链首没有 policy」的噪声 |
| `config/config.go:95-129` `ChannelPolicy` | 键是 channel（渠道级） | 要做到「同渠道不同跳不同参数」需新增 hop 级配置层级；仅按渠道区分则不动 |
| `race.go:399-431` `rankedChain` | 只依赖 `hopStatSnap` | 不用改（与策略无关，观测键 `hopKeyForLog` 已含 proxy） |
| `router.go:340-359` `headerTimeout`、`router.go:148-163` 两个 cooldown 取值 | 本来就按 `hop.Channel` 现查 | 无需改动，是现成的逐跳样板 |
