# zgate 对外只读接口与可观测性缺口（只读调查报告）

> **一句话**：`/v1/models` 与 `/health` 都由手写 dispatch 直接产出，没有 mux、没有 struct、没有 metrics 计数；「提前交卷」完全不可观测——日志里一条痕迹都没有。

调查范围：`F:/Project/ModelBus/gateways/zgate`，分支 main，只读。行号以当前工作树为准。
实测佐证：`GET http://127.0.0.1:7871/health`、`GET http://127.0.0.1:7871/v1/models`（listen = `127.0.0.1:7871`，zgate.json）。

---

## 1. /v1/models：处理器、字段来源、平铺混列

### 1.1 路由怎么落到处理器

| 位置 | 内容 |
|---|---|
| `gateways/zgate/internal/router/router.go:546` | `func (s *Server) Handler() http.Handler { return http.HandlerFunc(s.serveHTTP) }` |
| `gateways/zgate/internal/router/router.go:1782-1799` | `normalizePath`，其中 `:1784-1786` 把 `/v1` 前缀剥掉：`if strings.HasPrefix(path, "/v1") && (len(path) == 3 \|\| path[3] == '/') { path = path[3:] }` |
| `gateways/zgate/internal/router/router.go:566-569` | `if path == "/models" { s.models(w); return }` —— `/v1/models` 与 `/models` 同一处理器 |
| `gateways/zgate/internal/router/router.go:1353-1359` | 处理器本体：`writeJSON(w, 200, map[string]any{"object":"list","owned_by":"zgate","data": s.aliases.Catalog()})` |

### 1.2 字段从哪来（CatalogEntry）

`gateways/zgate/internal/alias/alias.go:142-149`：

```go
type CatalogEntry struct {
	ID          string `json:"id"`
	Object      string `json:"object"`
	OwnedBy     string `json:"owned_by"`
	CanonicalID string `json:"canonical_id"`
	Group       string `json:"group"`
	ChainHops   int    `json:"chain_hops"`
}
```

生成逻辑全在 `gateways/zgate/internal/alias/alias.go:155-202`：

- **canonical 别名行**：`alias.go:179-185`，`for _, name := range names`，`ID: name, CanonicalID: name`
  → 显示名自己就是 canonical id（`alias.go:141` 注释 "a display name is its own canonical id"）。
- **legacy 行**：`alias.go:194-201`，`for _, id := range legacy`，`CanonicalID: canonical` 取自 `m.data.Legacy[id]`（`:195`）；`:187-190` 有 `if _, isName := m.data.Models[id]; isName { continue }` 的去重兜底。
- **group / chain_hops**：闭包 `group()` `alias.go:162-172`
  ```go
  hops := len(t.Chain)
  if hops == 0 { hops = 1 } // a direct single-upstream target is one hop
  return t.Group, hops
  ```
  即 `group` = alias map 里 `models[name].group`，`chain_hops` = 链长（无链记 1）。
- **顺序确定**：`alias.go:177` 排 canonical、`:193` 排 legacy。
- 数据源：`~/.zcode/v2/model-alias-map.json`（默认值 `gateways/zgate/internal/config/config.go:213`，解析 `:397`；由 `tools/model_alias.py` 生成 legacy 映射）。

### 1.3 20 别名与 73 旧名确实混在同一个平铺列表

- 同一个 `data` 数组先追加 canonical（`alias.go:178-185`，容量 `len(models)+len(legacy)`），再追加 legacy（`:194-201`），**没有任何分组/包装**。
- 实测 `GET /v1/models`：`count: 93`，其中 `canonical rows: 20`、`legacy rows: 73`（判据 `id !== canonical_id`）。
- alias map 实况：`models: 20`、`legacy: 73`、`overlap: 0`（`C:\\Users\\SansK\\.zcode\\v2\\model-alias-map.json`，27511 B，generated_at `2026-11-10 20:25:37`）。因为 overlap 为 0，`:187-190` 的去重分支当前永不命中，73 条 legacy 每条都是 `id != canonical_id` 的独立行。
- 实测样例（同一数组相邻元素）：
  `{"id":"Beam",...,"canonical_id":"Beam","group":"免费","chain_hops":2}` 与
  `{"id":"DeepSeek-4.1-Fs",...,"canonical_id":"DeepSeek-4.1-Flash","group":"主力","chain_hops":4}`
- `chain_hops` 分布：`{1:19, 2:17, 3:16, 4:33, 7:8}`；`group` 只有三档：`免费/省钱/主力`。

> 消费方无法从字段上区分「这是别名还是旧名」，只能靠 `id != canonical_id` 自己推断。

---

## 2. /health：没有结构体，段表由 keys.Channels 驱动

### 2.1 定义位置

**没有响应结构体。** 整个响应是临时 `map[string]any`：

- 处理器：`gateways/zgate/internal/router/router.go:1295-1348`
- payload 构造：`router.go:1328-1347`
- 唯一带 json tag 的结构是与 /health 无关的 `hopStatSnap`（`:251-258`）。

字段清单（`router.go:1328-1347`）：

| 字段 | 来源 |
|---|---|
| `ok` | 常量 `true`（`:1329`） |
| `alias.path` / `alias.models` | `s.aliases.Path()` / `s.aliases.Count()`（`:1330-1333`） |
| `children` | `s.sup.States()`（`:1297`，supervisor.go:513 "States is the /health view of every child"） |
| `cooling` | `s.coolingCount()`（`:1335`，实现在 `:497-510`） |
| `uptime_s` | `int(time.Since(s.started).Seconds())`（`:1336`） |
| 每渠道一段 `opencode/workbuddy/qoder/qwen/qiniu/gemini/hajimi` | 循环 `:1339-1341` |
| `race.hops` / `race.disabled` | `:1345` |

### 2.2 段表确实由 keys.Channels 驱动

- `gateways/zgate/internal/keys/keys.go:32`：`var Channels = []string{"OC", "WB", "QD", "QW", "QN", "GM", "HJ"}`（`:27` 注释自称"新增渠道的唯一登记点"）。
- 驱动循环：`router.go:1338-1341`
  ```go
  // 段名与渠道的对应关系只由 keys.Channels 驱动：加渠道不用再回来改这里。
  for _, channel := range keys.Channels {
  	payload[healthSegmentName(channel)] = upstreamView(channel)
  }
  ```
- 段名映射：`healthSegments` `router.go:1277-1285`（`OC→opencode` … `HJ→hajimi`），回退逻辑 `healthSegmentName` `:1288-1293`（未登记则 `strings.ToLower(channel)`）。
- 段内容：闭包 `upstreamView` `:1298-1327`，字段 `base/key/child/state/last_error`，本地 child 额外 `pid`（`:1321-1323`）；无 key → `state=no_key`（`:1308-1310`）。
- 实测 7 段齐全（`gemini/hajimi/opencode/qiniu/qoder/qwen/workbuddy`）。

### 2.3 race 段 hops：字段与写入点

- 结构 `router.go:250-258`：
  ```go
  type hopStatSnap struct {
  	FirstBlockMs int64  `json:"firstBlockMs"`
  	Verdict      string `json:"verdict"`
  	At           string `json:"at"`
  	Seen time.Time `json:"-"`
  }
  ```
- 写入函数：`noteRaceHop` `router.go:283-296`（`At` = `now.Format("15:04:05")`）。
- 全部写入点（4 处）：
  | 行号 | verdict | 触发 |
  |---|---|---|
  | `router.go:1139` | `no-first-block` | 首块看门狗到点仍无真实内容 delta |
  | `router.go:1154` | `ok` | 流式拿到真实内容首块（`peekFirstContent` 成功） |
  | `router.go:1170` | `ok` | 非 SSE / 未开首块看门狗时，`WriteHeader` 即判赢 |
  | `router.go:1551` | 失败原因字符串 | `doForwardWith` 的 fallback 回调（如 `"Service Unavailable "`） |
- 读取点：`raceSnapshot` `:315-323`（`/health` 用，`:1345`）、`rankedChain` `race.go:399-431`（`:400` 决定发车顺序）。
- 整渠道禁用表：`disabledChannels` `:300-313`。
- 实测输出：`"race":{"disabled":{},"hops":{"GM|ais-gemini-3.6-flash|":{"firstBlockMs":8528,"verdict":"ok","at":"22:28:24"},"GM|ais-gemini-3.7-flash|":{"firstBlockMs":0,"verdict":"Service Unavailable ","at":"22:28:20"}, ...}}`
- 注意：`verdict` 是自由文本，失败原因直接拼上游状态文本（`router.go:1038` `retry(fmt.Sprintf("%s %s", http.StatusText(resp.StatusCode), retryHint(head)))`），**不是枚举**。

### 2.4 reasoningGuard 在 /health 里完全没有字段

- 实测 `Object.keys(health)` 过滤 `/guard/i` → `[]`。
- `router.go` 里 guard 只出现在请求路径（`:59`、`:909-913`、`:1043-1126`、`:1829-2150`），**没有任何一处写进 `payload`**。
- 结论：guard 的跳过期内、重抽次数、加密分流命中率，全部不可见（连 `alias` 段那种计数都没有）。

---

## 3. 现有可观测手段盘点

### 3.1 计数/指标：除 /health 外为零

- 全仓 `*.go` 搜 `prometheus|expvar|/metrics|StatsD|opentelemetry` → **0 命中**。
- 也没有 `sync/atomic` 计数（搜 `atomic.Add|atomic.Store|atomic.Int64|sync/atomic` → 0 命中）。
- 唯一"计数"是 `/health` 里的三个派生值：`cooling`（`router.go:497-510` 现算）、`alias.models`（`alias.go:109-116`）、`race.hops` 条数。
- 请求数 / 各模型命中数 / 各跳成功率 / 5xx 数 / 首字分布：**一个都没有持久累计**。`raceStat` 是"每跳最近一次"，不是累计（`router.go:250-258` 注释 "最近观测值"），且有过期丢弃（`raceFailTTL=10m`/`raceOKTTL=1h`，`:264-267`）。
- 进程外也没有补：`main.go:181-184` `http.Server{Handler: router.New(...).Handler()}` 是唯一监听，无 sidecar 指标口。

### 3.2 「提前交卷生效」在日志里没有任何唯一线索

- `gateways/zgate/internal/router/early_sse.go` 全文 **0 个日志调用**（无 `s.log`/`log.`）。
- 实测扫 `%LOCALAPPDATA%\ZCodeGateway\zgate.log`（2,496,772 B / 24,858 行），搜 `early|keepalive|提前|交卷|commit`（忽略大小写）→ **0 命中**。
- 因此：日志**无法**区分「客户端 200 是上游回的」还是「zgate 提前交卷的」，也无法知道这次请求交卷了几次、心跳补了几条、错误被改写成流内事件没有。
- 唯一客观痕迹只在客户端侧字节里：`: zgate keepalive\n\n`（`early_sse.go:31-33`）与流内 error 事件（`:275-292`，`data: {"error":{...,"type":"upstream_error","code":<status>}}` + `data: [DONE]`），但服务端不记这笔账。
- 注意 `StreamIdleHeartbeatSeconds` 的空闲心跳写的是**同一行文本**（`router.go:1248` `io.WriteString(w, ": zgate keepalive\n\n")`），所以客户端看到这行也无法反推是提前交卷还是流中空闲——两条路径的心跳不可区分。

---

## 4. 路由注册位置

**没有 `http.ServeMux`，没有 `mux.Handle` / `mux.HandleFunc`**（全仓 `HandleFunc` 仅出现在 `_test.go` 与 `router.go:546` 的 `http.HandlerFunc(s.serveHTTP)`）。

| 行号 | 内容 |
|---|---|
| `router.go:546` | `func (s *Server) Handler() http.Handler { return http.HandlerFunc(s.serveHTTP) }` |
| `router.go:548` | `func (s *Server) serveHTTP(w http.ResponseWriter, r *http.Request)`（表头注释 `:545` "Handler is the whole routing table."） |
| `router.go:561` | `path, search := normalizePath(r)` |
| `router.go:562-565` | `/health` → `s.health(w)` |
| `router.go:566-569` | `/models`（即 `/v1/models`）→ `s.models(w)` |
| `router.go:570-573` | `/admin/reload` → `s.reload(w, r)` |
| `router.go:575-615` | 其余全部走 alias/fallback 路由（`:610` `s.aliases.Reload()`、`:611-614` Resolve→routeAlias、`:615` routeFallback） |
| `main.go:181-184` | `srv := &http.Server{Handler: router.New(cfg, ks, am, sup, client, log).Handler(), ErrorLog: nil}` |
| `router.go:1747-1770` | `reload`：`:1748-1751` 只接受 POST（否则 405）；`:1753` config.Load；`:1758` keys.Load；`:1759` `s.sup.ApplyConfig(next.Children)`；`:1760` setRuntime；`:1761` aliases.Reload |

三个端点在同一个函数里相邻三行，顺序 health → models → reload，都在读 body 之前返回（无中间件、无鉴权、无方法校验——除 reload 内部的 POST 检查）。

---

## 5. 「先回 200 再流式」的实现点，与 EarlyCommitMs 全部读写点

### 5.1 early_sse.go 是唯一的定时提前交卷实现

`gateways/zgate/internal/router/early_sse.go`（293 行，全文无日志）：

| 位置 | 作用 |
|---|---|
| `:41-56` | `earlySSEWriter` 结构（`committed/early/failed/swallow/status/trapped`） |
| `:65-83` `WriteHeader` | 未交卷 → 原样透出；已交卷且 `code>=300` → 转 swallow |
| `:85-105` `Write` | swallow 时扣 body（上限 `sseEarlyMaxTrapped=4096`，`:36`） |
| `:125-146` `commitLocked` | `early` 分支写 SSE 三件套并 `Del("Content-Length"/"Content-Encoding")`（`:136-141`） |
| `:149-180` `start` | 定时器 `commitAfter` 到点调 `commitEarly`，随后 ticker 心跳 |
| `:182-193` `commitEarly` | 未提交则 `commitLocked(200, true)` + Flush |
| `:195-211` `ping` | 写 `sseKeepaliveLine`（`:33`） |
| `:215-223` `finish` | 提前交过卷且 has error → 改写流内 error |
| `:275-292` `writeErrorLocked` | `data: {"error":...}` + `data: [DONE]` |

唯一接线点 `router.go:598-608`：

```go
// 流式请求先交卷：等上游响应头的空窗里就给客户端 200 + text/event-stream 和心跳，
if isChat && wantsStream(body) {
	if window := s.earlyCommitWindow(); window > 0 {
		early = newEarlySSEWriter(w)
		defer early.finish()
		early.start(window, s.earlyKeepalive())
		w = early
	}
}
```

即：只对流式 chat 生效；w 被整体换掉，后续 race/bridge/forward 全部写在这层之上（`routeAlias`/`raceChain`/`newBridgeChunkWriter(w)` 拿到的都是 early writer）。

### 5.2 early_sse.go 之外还有哪些「先 200 再流」

都不是定时提前交卷，只是懒提交/状态透传，但会混淆观测口径：

| 位置 | 性质 |
|---|---|
| `router.go:2265-2281` `bridgeChunkWriter.write` | 首个 chunk 到来才设 SSE 头 + `b.w.WriteHeader(200)`（`:2267-2270`）—— 数据驱动，无定时器 |
| `router.go:2241-2254` `writeResult` | 带 `Content-Length` 写 `r.Status`（上游状态） |
| `router.go:1166` | `w.WriteHeader(resp.StatusCode)` —— 上游状态原样透出（若已提前交卷则被 early writer 吞成 swallow） |
| `router.go:1181-1258` | 转发循环 + 空闲心跳（`:1248` 写 `: zgate keepalive`），与 early 心跳同文本 |
| `race.go:134-151` `raceWriter.WriteHeader` | 只抢闸门再透传状态码，不提前提交 |
| `router.go:1058-1126` | guard 在写字节前先注入可读提示 SSE（`guardSkipNoticeSSE` / `guardNoticeSSE` / `guardTimeoutNoticeSSE`），但那是在 header 之前 prepend 到流首，不是提前 200 |

结论：定时器驱动的「先回 200」只有 `earlySSEWriter.start` 一处。

### 5.3 config.EarlyCommitMs 全部读写点

| 行号 | 类型 |
|---|---|
| `gateways/zgate/internal/config/config.go:148-151` | 字段声明 EarlyCommitMs（json 标签 `earlyCommitMs`，注释 `:148-150`：0/缺省 = 8000ms，负数 = 关闭） |
| `config.go:277-279` | applyDefaults 归一化：`if c.EarlyCommitMs == 0 { c.EarlyCommitMs = 8000 }` |
| `config.go:280-282` | 相邻项 `EarlyKeepaliveSec` 归一化 → 10 |
| `router.go:363-371` | 唯一读取点 `earlyCommitWindow()`：`if cfg := s.Config(); cfg != nil && cfg.EarlyCommitMs > 0 { return time.Duration(cfg.EarlyCommitMs) * time.Millisecond }`（`:367-368`） |
| `router.go:69-71` | `earlyCommit time.Duration` / `earlyPing` 测试覆盖字段（"0 = 按配置"） |
| `router.go:602` | 调用方 `if window := s.earlyCommitWindow(); window > 0` |
| `early_sse_test.go:87` | `srv.earlyCommit = window`（测试注入） |

- **当前生效值**：`gateways/zgate/zgate.json` 里**没有** `earlyCommitMs` / `earlyKeepaliveSec` 键 → 走缺省 **8000 ms / 10 s**（同文件 `upstreamHeaderTimeoutSec: 45`，`channelPolicy.GM/HJ.headerTimeoutSec: -1` 即关掉看门狗）。
- 无写入点（除测试），也无 reload 特判——`:335` 注释说明这类值每次现读配置，`/admin/reload` 换值不必重启。

---

## 6. 给「提前交卷」加观测量时的最小改动点（只列函数与行号）

1. `gateways/zgate/internal/router/early_sse.go:41-56` `earlySSEWriter` 结构 —— 加计数字段（early commits / keepalive pings / swallowed errors / trapped bytes）或一个回调指针，避免动 `commitLocked` 签名。
2. `early_sse.go:182-193` `commitEarly` —— 提前交卷的成功/被抢占两分支就在这里，天然的计数点（同时可判 `window` 是否真的烧完）。
3. `early_sse.go:195-211` `ping` —— 心跳成功/客户端已断（`err`）的计数点，也是「连接被中间层干掉」的唯一信号源。
4. `early_sse.go:215-223` `finish` + `:226-251` `fail` —— 统计「提前交卷后最终是成功流 / 被改写成流内 error / panic 兜底」的收口点。
5. `gateways/zgate/internal/router/router.go:601-608` `serveHTTP` —— 唯一接线处，在这里把请求维度（模型、渠道、window、keepalive）挂到 writer 或 server 上。
6. `router.go:283-296` `noteRaceHop` + `:250-258` `hopStatSnap` —— 现成的「最近一次观测」样板，若只要"最近一次交卷"照这个形状加即可。
7. `router.go:1328-1347` `health` 的 payload 构造 —— 新增 `early`/`commit` 段（挂进 `payload`，与 `race` 同级），是暴露给 `/health` 消费方的唯一位置。
8. `router.go:1295-1348` `health` 签名/读取处 —— 若要累计值需要 server 级状态容器，参照 `:73-75` `serialMu/serialAt` 的写法（`New` 在 `:326-331` 初始化）。
9. （可选，日志侧）`router.go:601-608` 内或 `early_sse.go:182-193` —— 现有日志**没有**任何 early 痕迹（实测 24,858 行 0 命中），要能 grep 就得在这里补一行，注意 `s.log` 不在 writer 作用域内，需经 5 的接线点传入。
