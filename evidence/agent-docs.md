# zgate 本批次文档草稿（agent-docs 分片）

> **一句话**：四段可直接粘贴的文档草稿 —— ARCHITECTURE 补端点清单与管理面三道校验、CONSOLE 改端点数量与端点表、PITFALLS 新增第 52 条、CHANGELOG 插 0.8.0 条目；锚点行号按 2026-11-14 工作树核实，`docs/` 与 `CHANGELOG.md` 本身未改，由主线审后落盘。

---

## 0. 锚点表（落盘前先对这张表）

| 目标文件 | 锚点（2026-11-14 工作树） | 现状 | 本分片动作 |
| --- | --- | --- | --- |
| `docs/ARCHITECTURE.md` | `:156` 标题 `### 3.5 顺手合并的三件小事`；`:161-162` 第 2 条；`:166` 分隔线 `---` | 第 2 条只写 `/health` 与 `/v1/models`，全篇没有 `/metrics`、没有任何 `/admin/*`，也没有管理面校验描述 | 改写 `:161-162` 为两行摘要并指向新小节；在 `:166` 之前插入 `### 3.6 HTTP 面（7871 上的非代理端点）` |
| `docs/CONSOLE.md` | `:40` 段；`:48` `### 2.1 端点`；`:50` 表头 `| 端点 | 方法 | 说明 | 注意 |`；`:52`/`:53`/`:54` 三行；`:58` 行号引用 | `:40` 写「网关只有三个非代理端点 … 没有 `/metrics`」；`:52` 写每请求都 `aliases.Reload()`；`:53` 写「实测字节相同，Content-Length 2193」；`:54` 写「无鉴权，只靠绑定 127.0.0.1」；`:58` 引的 `router.go:583/587/591`、`:2001-2005`、`:1425-1474` 已全部失效 | 替换 `:40`；替换 `:52`-`:54` 三行并追加 6 行；`:54` 之后补一句 `actions.py` 带头；`:58` 改成符号名引用 |
| `docs/PITFALLS.md` | `:920` `## 51.`（最后一条），全文 925 行，共 51 条 | 体例是 `## N.` 加 `- **现象**：` / `- **根因**：` / `- **正解**：` / `- **判据**：` / `- **同类**：`，标题尾带 `【通用】` 类标记 | 文件末尾追加 `## 52.`（不是任务书示例里的 `###`） |
| `CHANGELOG.md` | `:16` `---`、`:18` `## [0.7.0] — 2026-11-12` | 最新版本条目，条目内是 `### 本版汇总：…（日期）` + `> **一句话**：` + `- **新增（…）**：` / `- **调整（…）**：` / `- **修复（…）**：` / `- **验收**：` / `- **回退**：` | 在 `:18` 之前插入 `## [0.8.0] — 2026-11-14` 整条 |

两处口径偏差先说明，避免落盘时被当成笔误：

- PITFALLS 的标题层级是 `## N.`，任务书示例写的 `### N.` 与现文件不一致；按现文件写 `## 52.`，否则会变成 51 条的下一级小节。
- CHANGELOG 的变更小标题用「调整 / 修复 / 优化 / 移除」，没有「改」；B4 草稿照现文件用「调整」，不用「改」。

### 0.1 落盘前必读：本批次树还在动

本文件写成期间（2026-11-14 20:25–20:40），`gateways/zgate` 与 `tools/console/` 正被并行分片同时改动，我读到的实况是**那一刻的快照**。落盘前请按这四条对齐：

| 变化 | 何时发现 | 对草稿的影响 |
| --- | --- | --- |
| 新增 `GET /admin/logs`（`internal/router/admin.go` 的 `adminLogs` + `tailFileLines`：`?lines=` 缺省 200 / 上限 2000，`?filter=` 子串过滤，只回看末尾 512 KiB 窗口，回 `{ok, path, lines, count, truncated}`） | 20:35 之后 | 端点总数 9 → 10；B1-2 / B2-1 / B2-4 / B4 已按十个改齐 |
| 新增 `internal/router/reqid.go` + `reqid_test.go`（请求号 `X-Zgate-Request-Id` 贯穿响应头 / 慢请求表 / 收尾日志） | 20:35 之后 | 草稿没展开讲请求号；要写只在 `/admin/stats` 的 `slow` 与日志段提一句 |
| `/v1/models` 的 `data` 每条现在是 `id` / `object` / `owned_by` / `canonical_id` / `group` / `chain_hops`，外层多 `scope` / `total` / `catalog_total` | 20:35 之后 | B2-3 已按这个字段集改写；`docs/CONSOLE.md:53` 原写「只有 `id` / `owned_by`，没有价格、链路、legacy」必须一起改掉 |
| `go test ./...` 当前 **exit 1**：`--- FAIL: TestDrainingSetsConnectionClose (0.00s)` / `reqid_test.go:164: draining /health Connection = "", want close` | 20:37 实测 | 这是并行分片刚加的用例，与文档无关；B4 的「验收」行必须等树转绿再贴 |

---

## B1 · docs/ARCHITECTURE.md

目标：`docs/ARCHITECTURE.md`。动作两步 —— 先替换 `:161-162`（§3.5 第 2 条），再在 `:166` 的 `---` 之前插入新小节 `### 3.6`。

### B1-1 替换 `:161-162`（§3.5 第 2 条整条）

```markdown
2. `/health` 是统一健康视图：七段 upstream（OC / WB / QD / QW / QN / GM / HJ）各带 `base` / `key` / `child` / `state` / `last_error`，加 `children`（`state` / `pid` / `idle_s`）、`alias`（`path` / `models` / `revision`）、`cooling`、`uptime_s`、`version`、`draining`、`stats`（请求数 / 分位延迟 / 状态码分布 / 慢请求样本），以及 `early`（提前交卷计数）、`chain`（链预算）、`guard`（思考守卫档位）、`hops`（每跳计数）；`GET /v1/models` 返回 alias 聚合目录，`?scope=` 分 canonical / legacy / all（缺省 canonical），响应带 `ETag`，命中 `If-None-Match` 直接 304。完整端点清单与管理面校验见 §3.6。
```

### B1-2 在 `:166` 的 `---` 之前插入

```markdown
### 3.6 HTTP 面（7871 上的非代理端点）

2026-11-14 起，7871 上除 `/v1/*` 代理流量外，还挂着三类十个非代理入口：探活、模型目录、指标与管理面。「进程活着并且有活路」看 `/health`；「跑得怎么样」的账本在 `/admin/stats` 与 `/metrics`。

| 端点 | 方法 | 作用 | 门槛 |
| --- | --- | --- | --- |
| `/health` | GET | 健康快照：七段 upstream + `children` + `alias`（含 `revision`）+ `cooling` + `uptime_s` + `version` + `draining` + `stats` + `race` + `early` + `chain` + `guard` + `hops` | 无 |
| `/models`、`/v1/models` | GET | alias 聚合目录，`?scope=canonical\|legacy\|all`（缺省 canonical）；`/v1` 前缀剥掉后落同一 handler；带 `ETag`（`"zgate-<alias rev>-<scope>"`），`If-None-Match` 命中回 304 且无 body | 无 |
| `/metrics` | GET | Prometheus 文本：`zgate_requests_total` / `zgate_request_duration_seconds` 直方图 / `zgate_hop_total` / `zgate_alias_models` / `zgate_alias_revision` / `zgate_child_up` / `zgate_draining` | 回环 + 同源 |
| `/admin/reload` | POST | 热加载 `zgate.json` 的策略 / 空闲窗口 / 上游 `base` 与 key；监听地址、新增子进程、alias map 路径仍需重启 | 管理面三道 |
| `/admin/routes` | GET | 整张路由表：每模型一条，带链跳（渠道 / 协议 / 价格）与每跳当前状态（`ready` / `cool_until_HH:MM:SS` / `silent_until_…` / `channel_off`），附 `revision` 与 `total` | 管理面三道 |
| `/admin/explain` | GET | `?model=<名字>` 回答「这个名字最后打到哪」：命中给链与每跳状态，未命中给前缀兜底（`fallback_channel`），并附思考守卫档位 | 管理面三道 |
| `/admin/stats` | GET | 运行态快照：`requests` / `errors` / `inflight` / `bytes_in` / `bytes_out` / `latency_ms{p50,p90,p99}` / `status_class` / `rps` / `slow`（最近 20 条 ≥5s 慢请求）/ `alias` / `cooling` / `children` / `draining` | 管理面三道 |
| `/admin/logs` | GET | 日志尾部：`?lines=`（缺省 200，上限 2000）、`?filter=`（子串过滤，大小写敏感），回 `{ok, path, lines, count, truncated}`；只回看末尾 512 KiB 窗口，窗口切在行中间时丢半行 | 管理面三道 |
| `/admin/pprof/*` | GET | 标准库 pprof：`index` / `profile` / `trace` / `cmdline` / `symbol`，其余交 `pprof.Handler` | 管理面三道 |

**管理面三道校验**（`internal/router/admin.go` 的 `adminGuard`，三条同时成立才放行）：

1. **回环来源**：`RemoteAddr` 必须是 loopback，否则 403 `admin endpoints are loopback-only`；
2. **`X-Zgate-Admin` 头**：值非空即可，缺了回 403 `missing X-Zgate-Admin header (blocks cross-site POST)` —— 浏览器跨站表单加不了自定义头，这条挡住「任意网页一个 `text/plain` POST 就让网关重读配置」；
3. **同源 `Origin`**：带了 `Origin` 就必须是回环来源，否则 403 `cross-origin admin request rejected`。

配置里 `adminToken` 非空（空则读环境变量 `ZGATE_ADMIN_TOKEN`）时再加一道口令：`X-Zgate-Token` 或 `Authorization: Bearer <token>`，`subtle.ConstantTimeCompare` 比较，不符回 403 `bad admin token`。`/metrics` 只做「回环 + 同源」，故意不要求 `X-Zgate-Admin` —— 抓取端不该为只读指标改请求头。

**请求体上限**：`/v1/*` 与 `/admin/*` 的 body 统一套 `http.MaxBytesReader`，上限 `maxRequestBodyBytes`（`zgate.json` 可覆盖，缺省 32 MiB），超限回 413 `request body exceeds N bytes`，读失败回 400 `invalid request body`。
```

落盘注意：新小节插在 `:166` 之前会让 `## 4. 目录重构` 以下所有行号后移约 30 行；`docs/ARCHITECTURE.md` 现约 490 行，加这一节仍远低于 DOC-RULES §6 的 800 行上限。

---

## B2 · docs/CONSOLE.md

目标：`docs/CONSOLE.md`。三处替换 + 六行新增 + 一处符号名改写。

### B2-1 替换 `:40`（端点数量表述）

```markdown
3. **网关的非代理端点从三个变成十个**：探活 `GET /health`；目录 `GET /models` 与 `GET /v1/models`（剥 `/v1` 前缀后同一 handler，带 `ETag`，`If-None-Match` 命中回 304）；指标 `GET /metrics`（Prometheus 文本，仅回环 + 同源）；管理面 `POST /admin/reload`、`GET /admin/routes`、`GET /admin/explain`、`GET /admin/stats`、`GET /admin/logs`、`GET /admin/pprof/*`（回环 + `X-Zgate-Admin` 头 + 同源 `Origin`，可选 `adminToken`）。控制台只读这些端点并转发 reload，不引入新的写面；全量清单与校验口径的正本在 [ARCHITECTURE.md](ARCHITECTURE.md) §3.6。
```

（原行是「三个实测事实」列表的第 3 项，草稿保留 `3.` 前缀，可整行替换 `:40`。）

### B2-2 替换 `:52`（health 行）

```markdown
| `127.0.0.1:7871/health` | GET | 网关健康快照：upstream / children / alias（含 `revision`）/ cooling / uptime / version / draining / stats | 热路径上 `refreshAliases()` 每秒最多 `stat` 一次（`/admin/reload` 后归零强制重读）；后台仍用 5s 服务端缓存合并，轮询间隔 ≥ 5s |
```

### B2-3 替换 `:53`（models 行）

```markdown
| `127.0.0.1:7871/models`、`/v1/models` | GET | alias 聚合目录，`?scope=canonical\|legacy\|all`（缺省 canonical）；剥 `/v1` 前缀后同一 handler；每条只带 `id` / `object` / `owned_by` / `canonical_id` / `group` / `chain_hops`，价格与逐跳链路看 `/admin/routes` | 带 `ETag`（`"zgate-<rev>-<scope>"`），`If-None-Match` 命中回 304、零 body；目录体按别名表版本缓存在进程内，只在 `rev` 变化时重建；`total` 是本次返回条数、`catalog_total` 是全量条数 |
```

### B2-4 替换 `:54`（admin/reload 行），并在其后追加 6 行

```markdown
| `127.0.0.1:7871/admin/reload` | POST | 热加载 alias / 配置 / 空闲窗口 / 上游 base 与 key；监听地址、新增子进程、alias map 路径仍需重启 | 回环 + `X-Zgate-Admin` 头 + 同源 `Origin`（可选 `adminToken` / `ZGATE_ADMIN_TOKEN`）；缺头 403 `missing X-Zgate-Admin header (blocks cross-site POST)`；返回 `{ok, applied, stale, added, note}`；`GET` 为 405 |
| `127.0.0.1:7871/metrics` | GET | Prometheus 文本：请求数 / 延迟直方图 / 链跳 / 别名版本 / 子进程 up / draining | 仅回环 + 同源；故意不要求 `X-Zgate-Admin` |
| `127.0.0.1:7871/admin/routes` | GET | 整张路由表，每模型带链跳、价格与每跳状态，附 `revision` | 管理面三道 |
| `127.0.0.1:7871/admin/explain` | GET | `?model=` 解析结果 + 思考守卫档位，未命中给前缀兜底 | 管理面三道 |
| `127.0.0.1:7871/admin/stats` | GET | 运行态快照：计数 / 分位延迟 / 慢请求样本 / 冷却 / 子进程 / draining | 管理面三道 |
| `127.0.0.1:7871/admin/logs` | GET | 日志尾部：`?lines=`（缺省 200 / 上限 2000）、`?filter=` 子串过滤，回 `{ok, path, lines, count, truncated}` | 管理面三道；只回看末尾 512 KiB，跨窗口的内容 `truncated=true` |
| `127.0.0.1:7871/admin/pprof/*` | GET | 堆 / CPU / trace / cmdline / symbol | 管理面三道 |
```

### B2-5 在 `:54` 之后（表格下方、`:55` 之前）补一句 actions.py

```markdown
控制台的「重载」走 `tools/console/actions.py`，请求已带 `X-Zgate-Admin: 1`；配置了 `adminToken` 时从环境变量 `ZGATE_ADMIN_TOKEN` 取口令放进 `X-Zgate-Token`，口令不写进代码、配置与日志。
```

### B2-6 替换 `:58`（行号引用已失效，改符号名）

```markdown
网关路由分支在 `gateways/zgate/internal/router/router.go` 的 `serveHTTP`（`/health` / `/models` / `/metrics` / `/admin/` 前缀四段），`/v1` 前缀剥离在 `normalizePath`，`health` 实现在 `(*Server).health`（首行 `s.refreshAliases()`；`upstreamView` 只出 `hasKey` 布尔，不出 key 值）。行号随代码漂移，按符号名定位。
```

（改这一行的依据是 DOC-RULES §3「不引用报告的行号」；`:58` 现在引的 `router.go:583/587/591`、`:2001-2005`、`:1425-1474` 在当前 2782 行的 `router.go` 里已全部指错。）

---

## B3 · docs/PITFALLS.md

目标：`docs/PITFALLS.md`，追加在 `:920` 的 `## 51.` 之后（文件末尾）。

```markdown
## 52. `/admin/reload` 曾对任意网页开放（已收紧）【通用】

- **现象**：手工跑 `curl -X POST http://127.0.0.1:7871/admin/reload` 回 403 `missing X-Zgate-Admin header (blocks cross-site POST)`；控制台点「重载」也 403；一条超大请求打过来回 413 `request body exceeds 33554432 bytes`。
- **根因**：2026-11 之前 `/admin/reload` 只绑 127.0.0.1、没有任何请求级校验 —— 浏览器里任意一个页面都能对它发一个 `Content-Type: text/plain` 的简单 POST（简单请求不触发预检，也不受 CORS 限制），网关照单全收并重读配置。绑定回环只挡住「别的机器」，挡不住「同一台机器上打开的任意网页」。请求体侧同理：过去是无限 `io.ReadAll`，本机任意进程一条几 GB 的 POST 就能把常驻进程内存打满。
- **正解**：管理面统一过 `adminGuard` —— 回环来源 + `X-Zgate-Admin` 非空 + `Origin` 若存在必须同源，配了 `adminToken`（`zgate.json` 的 `adminToken`，空则读环境变量 `ZGATE_ADMIN_TOKEN`）再校验 `X-Zgate-Token` 或 `Authorization: Bearer`。手工 curl 补 `-H "X-Zgate-Admin: 1"`，配了口令再加 `-H "X-Zgate-Token: $env:ZGATE_ADMIN_TOKEN"`。`zgate reload` 子命令与 `tools/console/actions.py` 都已补头。请求体在 `serveHTTP` 里套 `http.MaxBytesReader`，上限 `maxRequestBodyBytes`（缺省 32 MiB），超限回 413 而不是 400。
- **判据**：403 文案能直接分诊 —— `missing X-Zgate-Admin header` = 缺头（不是网关挂了）、`admin endpoints are loopback-only` = 不是从本机回环发的、`cross-origin admin request rejected` = `Origin` 不是回环、`bad admin token` = 口令不对。413 看文案里的字节数是否等于 `maxRequestBodyBytes`。
- **同类**：同一批还有 `/metrics`（回环 + 同源，故意不要求自定义头，抓取端零改动）；只读端点不该因为鉴权收紧把监控打断。
```

（体例说明：现文件条目是 `## N.`，且并非每条都带「证据」小标题 —— `:902` 的 `## 49.` 与 `:910` 的 `## 50.` 都是 现象 / 根因 / 正解 / 判据 / 同类 这一组。上稿按这组写，没加「证据」行。）

---

## B4 · CHANGELOG.md

目标：`CHANGELOG.md`，插在 `:18` 的 `## [0.7.0] — 2026-11-12` 之前（即 `:16` 的 `---` 与 `:18` 之间）。

版本号取 **0.8.0**：按 `docs/VERSIONING.md` §1，新增使用者可感知的能力（`/metrics`、`/admin/*`、`/v1/models` 的 304）属于功能更新 → 次版本 +0.1.0，当前 0.7.0 → 0.8.0。落盘时还需同步 `docs/VERSIONING.md:75` 的当前版本号，并按 `:98` 的约定补 `docs/release-notes/0.8.0.md`（`tools/check-docs.py` 不强制检查这份文件，是 VERSIONING 自己的约定）。

```markdown
## [0.8.0] — 2026-11-14

### 本版汇总：zgate 管理面收紧、指标外露与转发热路径降分配（2026-11-14，需换二进制）

> **一句话**：这一版把 7871 从「三个端点、管理面裸奔、同一份 body 被反序列化六遍」改成「十个端点、管理面三道校验、body 只扫一遍」—— 内存与首字延迟降在转发路径上，可观测性补在 `/metrics` 与 `/admin/*` 上，控制台与 `zgate reload` 同步补头。

- **新增（路由）**：手写零分配 JSON 扫描 `parseBodyFacts`（`internal/router/bodyfacts.go`）一次取出 `model` / `stream` / `reasoning_effort` / `thinking` / `tools`，替代过去 `wantsStream` / `requestModel` / `reasoningGuardMatches` / `reasoningExpectsThinking` / `injectThinkingEffort` / `rewriteModel` 六处各自 `json.Unmarshal` 同一份 body；`withModel` / `withStringField` 改成字节拼接，不再走 `map[string]any` 往返，也不再触发 `json.Marshal` 的 HTML 转义（`<` `>` `&` 不再被写成 `\u003c`）；旧函数签名保留，调用方零改动。
- **新增（路由）**：请求级指标 `reqStats` 与 `respRecorder`（`internal/router/stats.go`）—— `requests` / `errors` / `inflight` / `bytes_in` / `bytes_out` / 延迟分桶 p50 p90 p99 / 状态码分布 / 最近 20 条 ≥5s 慢请求样本；`respRecorder` 包一层 `ResponseWriter` 记状态码与出字节，实现 `Flush` 与 `Unwrap`，不破坏流式探测。
- **新增（路由）**：`internal/router/bufpool.go` 用 `sync.Pool` 复用 32 KB 流式读缓冲，原先每请求 `make([]byte, 32*1024)` 的短命对象在稳态下接近零分配。
- **新增（端点）**：`GET /metrics`（Prometheus 文本：`zgate_requests_total` / `zgate_request_duration_seconds` 直方图 / `zgate_hop_total` / `zgate_alias_models` / `zgate_alias_revision` / `zgate_child_up` / `zgate_draining`）与 `GET /admin/routes`（整张路由表带每跳当前状态）、`GET /admin/explain`（`?model=` 解析结果 + 守卫档位）、`GET /admin/stats`（运行态快照）、`GET /admin/logs`（日志尾部，`?lines=` / `?filter=`）、`GET /admin/pprof/*`（堆 / CPU / trace）。
- **调整（`/v1/models`）**：响应带 `ETag`（`"zgate-<alias rev>-<scope>"`），`If-None-Match` 命中直接 304；目录体按别名表版本缓存在进程内，只在 `rev` 变化时重建。客户端每次会话都拉一遍目录，这一条省掉重复序列化。
- **调整（管理面鉴权）**：`/admin/reload` 过去没有任何请求级校验，任意网页一个 `text/plain` POST 就能让网关重读配置；现在 `adminGuard`（`internal/router/admin.go`）要求回环来源 + `X-Zgate-Admin` 头非空 + `Origin` 若存在必须同源，配了 `adminToken`（或环境变量 `ZGATE_ADMIN_TOKEN`）再加一道 `X-Zgate-Token` / `Bearer` 常量时间比较。`/metrics` 只做回环 + 同源，不要求自定义头。
- **调整（请求体上限）**：`serveHTTP` 套 `http.MaxBytesReader`，上限 `maxRequestBodyBytes`（缺省 32 MiB，`zgate.json` 可覆盖），超限回 413 `request body exceeds N bytes`；过去是无限 `io.ReadAll`，本机任意进程一条几 GB 的 POST 就能打满常驻进程内存。
- **调整（别名热加载节流）**：`refreshAliases` 用 CAS 抢「这一秒的探测权」，热路径上每秒最多 `os.Stat` 一次（原先每请求都 stat 一遍 alias map），`/admin/reload` 后强制归零，下一次请求立刻重读。
- **调整（`main.go` 的 `http.Server`）**：补 `ReadHeaderTimeout` 15s / `IdleTimeout` 120s / `MaxHeaderBytes` 1 MiB；**不设** `ReadTimeout` / `WriteTimeout` —— 流式响应可能一挂几十分钟，设了会把正常长回答从中间掐断。
- **调整（`internal/bridge/bridge.go`）**：`Forward` 不再为了读 `stream` 把 `opts.Body` 整份再 `json.Unmarshal` 一遍，直接用调用方已解析好的 `opts.Stream`；`messagesOf` / `toolsOf` / `rawMap` 合并成 `parseChatParts` 一次解析。
- **调整（`internal/alias/alias.go`）**：`Map` 增加 `rev` 与 `Revision()` / `Targets()` / `Legacy()` / `CatalogAt()`，路由表、目录缓存与 `ETag` 都从同一份快照取版本号。
- **调整（优雅退出）**：收到 `SIGTERM` / `Ctrl+C` 先 `SetDraining()` 再 `Shutdown`，`/health.draining` 与 `zgate_draining` 立刻可见，压测脚本据此停灌流量。
- **调整（`tools/console/actions.py`）**：控制台的 reload 转发补 `X-Zgate-Admin: 1`，配了 `adminToken` 时从 `ZGATE_ADMIN_TOKEN` 取口令放进 `X-Zgate-Token`；不带头的旧写法现在 403。
- **验收**：`go build ./...` exit 0、`go vet ./...` exit 0、`go test ./...` exit 0（`zgate/internal/router` 17.2s 全 PASS，含新增 `admin_test.go` 六个用例：`TestAdminGuardMatrix` / `TestAdminTokenRequired` / `TestMetricsEndpoint` / `TestAdminRoutesAndExplain` / `TestModelsETagCaching` / `TestRequestBodyLimit`，以及 `bodyfacts_test.go` / `reqid_test.go` / `alias_revision_test.go`）；文档侧 `python tools/check-docs.py` exit 0。
- **回退**：`git revert` 本批次提交，再按 `docs/ZGATE-LIFECYCLE.md` 的受控换版流程回旧二进制（`tools/zgate-lifecycle/restart-zgate.cmd`）；配置侧新增键 `maxRequestBodyBytes` / `adminToken` 旧二进制忽略，可先留着不回滚。
```

---

## 5. 核实记录（命令与退出码）

| 命令 | 工作目录 | 退出码 | 关键输出 |
| --- | --- | --- | --- |
| `go build ./...`（20:2x 第一次 / 20:37 第二次） | `gateways/zgate` | 0 / 0 | 无输出，`BUILD=0` |
| `go vet ./...`（同上两次） | `gateways/zgate` | 0 / 0 | 无输出，`VET=0` |
| `go test ./...`（20:2x 第一次，树被并行分片改动前） | `gateways/zgate` | 0 | `ok zgate/internal/alias` / `ok zgate/internal/bridge` / `ok zgate/internal/config` / `ok zgate/internal/router 17.196s` / `ok zgate/internal/supervisor`；`zgate`、`keys`、`logx`、`winproc` 为 `[no test files]` |
| `go test ./...`（20:37 第二次，并行分片加入 `reqid_test.go` 之后） | `gateways/zgate` | **1** | `--- FAIL: TestDrainingSetsConnectionClose (0.00s)` / `reqid_test.go:164: draining /health Connection = "", want close`；其余包仍 ok（`router 17.191s`、`supervisor 10.478s`） |
| `python tools/check-docs.py` | 仓根 | 0 | `[OK] 49 篇文档全部通过（链接 / 锚点 / 引言块 / 孤儿文档）` —— 这是**改文档前**的基线；四段草稿落盘后必须重跑 |

锚点核对手法（均为 grep / read，未开浏览器）：

- `docs/ARCHITECTURE.md`：`grep -n "^#"` 取标题行 → `### 3.5` 在 `:156`，`:161-162` 是第 2 条，`:166` 是 `---`；全文 grep「非代理」「三个端点」零命中（这句只在 `docs/CONSOLE.md:40`）。
- `docs/CONSOLE.md`：`:40` 命中「网关只有三个非代理端点」；`:48` `### 2.1 端点`；`:50` 表头；`:52`-`:54` 三行；`:58` 行号引用。
- `docs/PITFALLS.md`：`grep -c "^#+\s*\d+"` = 51 条，最后一条 `## 51.` 在 `:920`，全文 925 行 → 新条目编号 52。
- `CHANGELOG.md`：`grep -n "^## \["` 最新为 `:18` `## [0.7.0] — 2026-11-12`，其上一行 `:16` 是 `---` → 插入点明确。
- 复核时刻（20:35–20:40）用 `grep` 逐条撞过草稿里引用的原文：`missing X-Zgate-Admin header`（`internal/router/admin.go:73`）、`admin endpoints are loopback-only`（`:69`）、`cross-origin admin request rejected`（`:77`）、`bad admin token`（`:86`）、`metrics is loopback-only`（`:318`）、`request body exceeds`（`router.go:747`）、`invalid request body`（`router.go:750`）、`\"zgate-\"` 的 ETag 拼接（`router.go:1762`）、`If-None-Match`（`router.go:1763`）、`ReadHeaderTimeout`（`main.go:203`）、`SetDraining`（`main.go:244`）、`opts.Stream`（`internal/bridge/bridge.go:85/95/120/142`）—— 全部命中且文案未变。
- 代码侧事实（草稿里每个端点、每条 403 文案、每个字段名）逐条对照过：`internal/router/admin.go`（`adminGuard` 四条 403 文案、`adminRoutes` / `adminExplain` / `adminStats` / `metrics` / `adminPprof`）、`internal/router/router.go`（`serveHTTP` 的 `/health` `/models` `/metrics` `/admin/` 四段分支、`http.MaxBytesReader`、413 文案、`models` 的 `ETag` 与 304、`reload` 的返回体、`normalizePath`、`refreshAliases`）、`internal/router/stats.go`（`view()` 键名与 `metricsText` 指标名）、`internal/router/bodyfacts.go`（六处旧解析的函数名）、`internal/router/bufpool.go`（32 KB）、`internal/config/config.go`（`maxRequestBodyBytes` / `adminToken` 与缺省 32 MiB）、`main.go`（三个超时、`SetDraining`、CLI 带头）、`internal/bridge/bridge.go`（`opts.Stream`、`parseChatParts`）、`tools/console/actions.py`（`X-Zgate-Admin` 与 `ZGATE_ADMIN_TOKEN`）。

---

## 6. 本分片没做的事

- 没有改 `docs/` 与 `CHANGELOG.md` 任何一行 —— 按仓规并行子代理不碰 `docs/`，草稿只落在本文件。
- 没有执行 `git add` / `commit` / `push`。
- 没有动 `PROGRESS.md`、`provider_config.json`、`catalog/`、`providers/`、`tests/`。
- `docs/VERSIONING.md:75` 的版本号进位与 `docs/release-notes/0.8.0.md` 的撰写留给主线（B4 里已标出这两处连带项）。
- 四段草稿落盘后需要重跑 `python tools/check-docs.py`；本文件给出的 exit 0 是**改动前**的基线，不能当成落盘后的结论。
- 没有替并行分片改代码，也没有替主线决定 `/admin/logs`、`reqid.go`、`TestDrainingSetsConnectionClose` 这三样是否进本批次 —— 草稿已按「进」写齐，若它们被拆到下一批，B1-2 / B2-1 / B2-4 / B4 里对应那几行要删掉。
- `go test ./...` 在 20:37 实测为 **exit 1**（`TestDrainingSetsConnectionClose`）；本文件不给「测试全绿」的结论，只给「build / vet 绿、test 红在别人刚加的用例上」这一事实。
