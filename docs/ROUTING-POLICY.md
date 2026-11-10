# 路由策略正本：逐跳参数、链预算与单跳豁免

> **一句话**：一条请求进来以后「先打哪一跳、等多久、失败算谁的、什么时候不许判死」全在这里 ——
> 参数按**跳**取（不是按链首）、预算按**链**算、单跳链不吃冷却。本文是这三件事的唯一正本。

> **相关正本**：渠道 / 模型 / 价格见 [MODEL-PROVIDERS.md](MODEL-PROVIDERS.md)，为什么会踩这些坑见 [PITFALLS.md](PITFALLS.md)，
> 现场怎么查见 [TROUBLESHOOTING.md](TROUBLESHOOTING.md)，换二进制见 [ZGATE-LIFECYCLE.md](ZGATE-LIFECYCLE.md)。

---

## 0. 一条请求走完的六步

| 步 | 代码位置 | 做什么 |
|---|---|---|
| 1 | `serveHTTP`（router.go） | 认路径（/health、/models、/admin/reload，其余走别名），把**链预算**塞进 ctx |
| 2 | `routeChain` | 别名命中后拿到 `Chain`（要试的跳列表），按需改写请求体 |
| 3 | `racePlanFor`（race.go） | 从**每一跳**的 `channelPolicy` 聚合出「要不要对冲、并发几路、发车间隔多少」 |
| 4 | `raceChain` / `attemptChain` | 有对冲 → 并排发车抢首块；没有 → 串行回落 |
| 5 | `doForwardWith` → `doForward` | 取 base（`hopBase`）、注头、等响应头（min(本跳窗口, 链剩余)） |
| 6 | `coolHop`（policy.go） | 失败后决定这颗雷要不要落冷却表 |

---

## 1. 参数按跳取，不按链首取（2026-11-10 深夜改）

| 参数 | 取值来源 | 说明 |
|---|---|---|
| `hedgeAfterMs` | 链上各跳**最小正值** | 首跳发出多久没等到响应头就再并一路；某跳配 0 = 该跳不主动催 |
| `maxParallel` | 链上各跳**最大值** | 同时在路上的上限，兜底 2（上游每 key 并发很低，6 路必 429） |
| `firstBlockMs` | 逐跳（只配它时当发车间隔） | 0 = 不判首块；用它兜底间隔 1200ms |
| `headerTimeoutSec` | **被尝试的那一跳** | 0 = 用全局 `upstreamHeaderTimeoutSec`（当前 45）；负数 = 不设看门狗 |
| `silenceCooldownSeconds` | 被尝试的那一跳 | 0 = 沉默不埋冷却 |
| `softCooldownSeconds` | 被尝试的那一跳 | 5xx 冷却秒数 |
| `rateLimitBackoffMs` | 被尝试的那一跳 | -1 = 429 直接换跳；0 / 正数 = 就地等一会儿再重试 |
| `authFailCooldownHours` | 被尝试的那一跳 | key 失效类 403 → 整渠道停多久 |

**为什么改**：原来 `racePolicyFor` 读 `Chain[0]`，一条链上只有链首渠道说了算 —— Gemini-AIS 七跳全 GM，
于是「给 OC / QD / WB 补策略」在当时等于白补（配了也读不到）。改成逐跳聚合之后，任意混合链
（例：GM 慢 + HJ 快）不必再为每个组合手工建模型，链自己就能得到「慢的那跳并排问快的那跳」。

旧五条件（每跳都必须在 `channelPolicy` 里、每跳 proto 都必须是 chat、链首必须有 hedge/firstBlock）也一并取消：
缺配的渠道只是拿不到对冲节奏，不再让整条链退回串行。串行仍然会发生，但只在**真的没人要求对冲**时发生，
并且 `noteSerialChain` 会打一条 Info 说明是哪条链、为什么（按链做 10 分钟去重）。

---

## 2. 链预算 `chainBudgetSec`（缺省 90，负数 = 不限）

| 项 | 语义 |
|---|---|
| 起点 | `serveHTTP` 里进 ctx（`withChainContext`） |
| 用法 | `doForward` 取 min(headerTimeout(渠道), 链剩余) 当这一跳的等头窗口 |
| 预算尽 | 立刻回 **504** `gateway_timeout`，文案 `gateway gave up waiting for the first byte buffer (...)` |
| 冷却 | **不埋**。这是本地的选择，不是上游的错，埋了下次请求会直接跳过热的那一跳 |
| 只管哪一段 | 只管「等响应头」。正文开始流式写出去以后不再计时 —— 长回答本来就不该被杀 |

它解决的是「一条链上每跳各 45s、四跳串起来 = 三分钟」那种无边界的总等待；单跳链的预算就等于它自己那一跳的窗口。

---

## 3. 单跳链三条豁免（2026-11-10 连片 502 的直接产物）

判据只有一个：`singleHopChain(ctx)` = 这条链只有一跳。命中后：

| 场景 | 多跳链 | 单跳链 |
|---|---|---|
| 上游沉默（等头超时） | 进 silence 表 20s | **不落表**，只打 Info「是单跳链，沉默不埋冷却」 |
| 5xx 软冷却 / 超时 5min / 地区受限 / 不可用 | 落 cool 表 | **不落表**，只打 Info |
| 429 限流 / 额度耗尽 | 落表（限流 45s / 额度 24h） | **仍然落表** |

理由：单跳链冷却一跳 = 把这个模型整体关掉。当天的现场就是 Gemini-3.8-Flash 从「偶尔慢」变成「连片 502」——
那唯一一跳被本地判死埋了冷却，下一个请求连上游都没碰。反过来 429 与额度是上游**明确拒绝**，
继续打只会更糟，所以照旧冷却。

### 3.1 `hopBase`：base 只有一个事实来源

请求地址按 `hop.Base` → `cfg.Upstreams[渠道].Base` 顺序取。别名表里的跳一般不写 base，
渠道配置才是单一事实来源，跳级 base 只当覆盖用。（2026-11-10 之前只取 `hop.Base`，
别名里没写 base 的链会拿空地址请求，两跳瞬败报 `all upstreams failed: WB:a -> OC:b`，看着像策略 bug。）

---

## 4. 两张冷却表，别混

| 表 | 装什么 | TTL | 谁能清 |
|---|---|---|---|
| cool | 429 45s、5xx 软冷却（按渠道）、死跳 30min、超时 5min、额度 24h | 见左 | 到期自然过期；`clearCooling` |
| silence | 只有「沉默」一种 | 20s（按渠道） | 到期；**全链沉默兜底会整体清掉** |

必须分开：混成一张会变成「清冷却 → 再撞 429 → 再清」的死循环。键是 `Channel|Upstream|Proxy`，
日志里的键把 proxy 脱敏（`hopKeyForLog`）。

---

## 5. 启动自检 `ValidatePolicies`

在 `serve()` 建完别名表后跑一遍，把「配了但永远读不到」的配置拦在启动期，而不是等排障时猜。

| 判定 | 条件 | 后果 |
|---|---|---|
| **Fatal** | 某渠道**只**服务单跳模型，却配了对冲字段（`hedgeAfterMs` / `maxParallel` / `firstBlockMs` / `rateLimitBackoffMs`） | 拒绝启动，打印渠道 + 受影响的模型（多的压成「等 N 个」） |
| 提示 | 该渠道**同时**服务多跳模型 | 只打 Warn：同一份策略在多跳链上确实有效，不能因此拦下合法配置 |

渠道名写错（`channelPolicy` 里的键在 `upstreams` 里不存在）目前仍是静默 —— 靠这条自检加
`tools/check-project.py` 的渠道集合比对兜住。

---

## 6. 对外模型列表：`/v1/models?scope=`

| scope | 返回 | 用途 |
|---|---|---|
| canonical（缺省） | 统一名（当前 20 条） | 客户端该用的那张表 |
| legacy | 旧 id（当前 73 条） | 历史兼容，`canonical_id` 指回统一名 |
| all | 两边都要 | 排障 / 对账 |

返回体带 `scope`、`total`、`catalog_total` 三个字段，语义分清楚：

| 字段 | 含义 | 例（canonical） |
|---|---|---|
| `total` | **本次返回**的条数，客户端直接拿来数「我有几个模型」 | 20 |
| `catalog_total` | 全部两拨加起来的条数，对账用 | 93 |
| `data` | 本条 scope 的条目 | 20 条 |

两个数混成一个会让 20 条的响应写着 93，看起来像分页没给完 —— 2026-11-10 首版就是这样，当晚拆开。
未知 scope 回 400 `invalid_request_error`，不静默退回默认（拼错才不会被藏住）。
改默认值是一个**对外行为变更**：老客户端如果依赖「一口气拿到 93 条」，需要显式写 `?scope=all`。

---

## 7. 观测面：`/health` 的四段

| 段 | 字段 | 读它干什么 |
|---|---|---|
| early | enabled / window_ms / keepalive_s / wrapped / passed_in_window / committed / keepalives / failed_after_wait | 提前交卷到底救了多少请求；window_ms 是**当前生效值**（0 = 关） |
| chain | budget_s | 链预算实际生效值 |
| guard | enabled / mode / channels / skipping | 思考守卫当前档位、哪些渠道算「会思考」、哪些模型正在被跳过 |
| race | hops / disabled | 每跳的首块观测（`rankedChain` 发车顺序的依据） |

没有这些字段之前，「提前交卷有没有用」「守卫对谁生效」只能靠推理；现在一条 `curl` 就能回答。

### 7.1 思考守卫的三档（`reasoningGuard.mode`）

| mode | 判据 | 新增模型要不要改配置 |
|---|---|---|
| `models` | 只看 `models` 白名单 | 要（漏加就不守） |
| `channels` | 先看渠道能力位 `upstreams.<渠道>.guardReasoning`；`models` 非空时再叠一层白名单（**交集**） | 渠道级的不用；白名单非空仍要 |
| `auto`（缺省） | 不看任何表，凡是客户端声明要思考的流式请求都探 | 不用 |

现网是 `channels` + 白名单 `["Iceman","iceman-contributor-free"]` + 仅 `OC` 带能力位：
对 Iceman（链 `OC->OC`）与旧口径等价，往后 OC 上的模型只需把名字加白名单（或清空白名单全量接管）。
`/health.guard` 的 `channels` 就是能力位为真的渠道名，改完 `POST /admin/reload` 立刻能看见。

---

## 8. 当前各渠道实际值（2026-11-10 深夜，`zgate.json`）

| 渠道 | soft | silence | rate | firstBlock | hedge | maxParallel | headerTimeout | 依据 |
|---|---|---|---|---|---|---|---|---|
| WB | 0 | 0 | 0 | 0 | 18000 | 2 | 0 | 有 4 个单跳模型 → 软冷却必须 0；18s 只造福多跳链 |
| OC | 60 | 20 | -1 | 0 | 0 | 2 | 0 | 唯一从不单跳的渠道（11 条多跳），可以放心冷却 |
| QD | 0 | 20 | -1 | 0 | 0 | 2 | 0 | 有 Qwen-3.8-Max 单跳 → 软冷却必须 0 |
| GM | 60 | 0 | -1 | 0 | 18000 | 2 | -1 | 判死权归上游（见 MODEL-PROVIDERS §4.11.3 第四次收敛） |
| HJ | — | — | — | — | — | — | -1 | 单跳直连，只关看门狗 |
| QW / QN | 未配 | 未配 | 未配 | 未配 | 未配 | 未配 | 未配 | QW 只当链尾且协议不同 → 永不走竞速；QN 只有 Conatus 单跳 |

全局：`upstreamHeaderTimeoutSec` 45、`chainBudgetSec` 90、`earlyCommitMs` 未写（生效 8000ms / 10s）。

**零值语义**（配之前先看清，不然会以为「填了 0 就是关掉冷却」，其实是什么都没配）：
softCooldownSeconds / silenceCooldownSeconds = 0 → 冷却函数直接返回 0（等于关）；
rateLimitBackoffMs = 0 → 保留老行为（就地重试）；headerTimeoutSec = 0 → 用全局 45；
authFailCooldownHours = 0 → 不做渠道级禁用。

---

## 9. 验收与回退

1. 代码层：`go build ./...`、`go vet ./...`、`go test ./...` 全 0；
   策略用例在 `internal/router/policy_test.go`（逐跳聚合、单跳不冷却、预算回 504、自检两档、守卫档位）。
2. 配置层：改 `zgate.json` 后 `POST /admin/reload` 即可，不必重启进程。
3. 实机：`curl -s 127.0.0.1:7871/health` 看 early / chain / guard 三段
   （`early.wrapped` 随流式请求增长 = 观测接上了；`guard.mode` 应等于 `zgate.json` 里的档位）；
   `curl -s "127.0.0.1:7871/v1/models?scope=canonical"` 应 `total=20 / catalog_total=93`、`?scope=legacy` 应 `total=73`、`?scope=bad` 应 400。
4. 二进制层：换版只走 `tools/zgate-lifecycle/restart-zgate.cmd`（编译候选 → 停旧 → 原子替换 → 健康检查 → 失败回滚）。
5. 回退：配置问题改 `zgate.json` 加 reload；代码问题 `git revert` 后跑同一条换版脚本。

---

## 10. 代码坐标

| 文件 | 职责 |
|---|---|
| `internal/router/policy.go` | 链预算 ctx、单跳判定、`hopBase`、`coolHop` / `coolWhyOf`、`ValidatePolicies` |
| `internal/router/race.go` | `racePlanFor` / `hopProtocol` / `raceChain` / `rankedChain` / `noteSerialChain` |
| `internal/router/router.go` | `routeChain` / `attemptChain` / `doForward` / 冷却表 / `/health` / `/models` |
| `internal/router/early_sse.go` | 提前交卷 writer + `earlyStats` |
| `internal/config/config.go` | `ChannelPolicy` 字段、`ChainBudgetSec`、`GuardReasoning`、`applyDefaults` |
| `internal/alias/alias.go` | `ChainView` / `Chains()`（给启动自检用） |

*本文只写「参数怎么生效、什么时候不该判死」。具体渠道的价格与模型清单不在这里重复，见 [MODEL-PROVIDERS.md](MODEL-PROVIDERS.md)。*
