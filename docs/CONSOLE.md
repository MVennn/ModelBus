# ModelBus 控制台（Console）

> **一句话**：把散在 40 个文件、7 个渠道、3 个端点里的运行数据，聚合成一个只跑在 `127.0.0.1:7872` 的 MD3 单页后台 —— 网关零改动、前端零 CDN、零构建、零第三方包。

状态：**设计稿 v1（2026-11-10），尚未落地**。本文只定方案与验收口径，代码在确认后写。

---

## 0. 结论速览

| 项 | 决定 |
|---|---|
| 形态 | 独立 Python 进程 `tools/console/server.py`，**不塞进 zgate** |
| 地址 | `http://127.0.0.1:7872`（7871 / 7863 / 8790 已占用，7872 实测空闲） |
| 前端 | Beer CSS 5（MD3 token，单 CSS 87.9 KB）+ 原生 JS 单文件，无 npm / 无 CDN / 无构建链 |
| 页面 | 8 个：总览 / 模型 / 价格 / 健康 / 流量 / 账号 / 日志 / 运维 |
| 数据 | 以只读聚合为主（文件 + `/health` + 子进程产物）；写操作只有 `reload`，P2 再加长任务触发 |
| 网关改动 | P0–P2 **零改动**；P3 可选加一个 302，让浏览器打开 `7871/health` 直接落到后台 |
| 依赖 | Python 3.12 标准库 + 一个 CSS 文件 |

---

## 1. 现在缺什么

三个事实决定了这个后台该长什么样：

1. **`/health` 只出 JSON**，1166 字节，7 个渠道段 + 子进程 + 冷却 + 竞速挤在一层里。信息全，但没有层级，人眼扫不出「哪一段现在是坏的」。
2. **可可视化资产 38 项、页面候选 12 类**，散在 `~/.zcode/v2/`、`providers/*/cache/`、`gateways/upstream/*/data/`、`%LOCALAPPDATA%/` 四个根下，跨 5 种格式（json / jsonl / 按天分文件的 jsonl / 文本日志 / markdown 报告）。
3. **网关只有三个非代理端点**：`GET /health`、`GET /models`、`POST /admin/reload`。没有 `/metrics`、没有模板引擎、没有 CORS，也没有任何计数聚合 —— `/health` 是唯一指标出口。

所以它的价值不是「给 `/health` 加个页面」，而是**把 40 个文件读成 8 张能一眼判断的表**，并且让 `/health` 那份 JSON 变成其中一页。

---

## 2. 数据面（已实测，2026-11-10）

### 2.1 端点

| 端点 | 方法 | 说明 | 注意 |
|---|---|---|---|
| `127.0.0.1:7871/health` | GET | 网关健康快照 | **每次请求都会 `aliases.Reload()` 重读 alias map 文件**，轮询间隔必须 ≥ 5s |
| `127.0.0.1:7871/models` | GET | 模型目录简表（`/v1/models` 同源） | 只有 `id` / `owned_by`，**没有价格、链路、legacy** |
| `127.0.0.1:7871/admin/reload` | POST | 热加载 alias / 配置 | 无鉴权，只靠绑定 127.0.0.1；返回 `{ok, applied, stale, added, note}` |
| `127.0.0.1:7863/panel/api/*` | GET | WorkBuddy 面板 | 需自身鉴权，跨端口直连会被拦 —— **后台不代理它**，只读本地 `data/*.json` |
| `127.0.0.1:8790/ping` | GET | Qoder 存活 | 只判活 |

### 2.2 文件与日志

| 分组 | 路径 | 关键内容 | 建议 TTL |
|---|---|---|---|
| 模型真值 | `~/.zcode/v2/model-alias-map.json` | 每个模型的 `group/price/chain[]/fallbacks[]/legacy_ids[]/protocol`（条数随 alias 变，页面不写死） | 30s |
| Provider 配置 | `~/.zcode/v2/provider_config.json` | 三组 provider + 模型映射 | 30s，**只露 `has_key`** |
| 探针 | `~/.zcode/v2/model_probe.json` | 按模型 id：`display/status/http/ms/detail/credit/provider` | 60s |
| 流式准入 | `.work/model-stream/latest.json` | 全量条目：`state/reasons/tps/firstMs/effort/finishReason` | 60s |
| 评分 | `~/.zcode/v2/model-scores.json` | `basis: [model, score, price, source]` + `models` | 60s |
| 额度 | `~/.zcode/v2/quota-windows.json` | `windows[]: {channel, until, days_left, note}` | 60s |
| 竞技榜 | `~/.zcode/v2/arena-main.json`、`arena-leaderboard.json` | 候选与实时榜 | 300s |
| 价格 | `providers/workbuddy/cache/wb_pricing.json`（705 行）、`providers/qoder/cache/qd_prices.json`（96 行） | WB 折扣价、Qoder 峰谷价 | 300s |
| 请求明细 | `gateways/upstream/workbuddy/data/request-logs/requests-YYYY-MM-DD.jsonl` | 今日 4666 行，字段含 tokens / ttfb / attempts / credit | 30s |
| WB 用量 | `gateways/upstream/workbuddy/data/{usage,credit-history,balance_history,state,task-jobs,task-runs,task-logs}.json` | 累计与流水 | 30s |
| WB 账号 | `gateways/upstream/workbuddy/auths/*.json`（实测 8 个） | 账号身份 | 300s，**只给数量与掩码** |
| Qoder 用量 | `gateways/upstream/qoder/usage/usage-summary.json`、`accounts/scheduler/state.json` | `by_model`、`ttft_ms_sum/samples` | 30s |
| 网关日志 | `%LOCALAPPDATA%/ZCodeGateway/zgate.log`（5 MB 轮转） | `时间 LEVEL msg` | 不缓存 |
| 生命周期日志 | 同目录 `{zgate-daemon,zgate-launch,deploy-zgate,watchdog}.log` | 启停与换版 | 不缓存 |
| 子网关日志 | 同目录 `{workbuddy,qoder,cliproxyapi}.{stdout,stderr}.log` | 子进程原始输出 | 不缓存 |
| 同步 | `%LOCALAPPDATA%/ModelBus/logs/sync-<stamp>.log`、`_last-sync.txt`、`current-models.json` | 五段流水线结果 | 30s |
| 报告 | `docs/reports/MODEL-SYNC-<YYYYMMDD-HHMM>.md` | 每次同步的变化清单 | 300s |
| 配置 | `gateways/zgate/zgate.json` | 上游 base、子进程、channelPolicy、reasoningGuard | 30s |
| 计划任务 | `schtasks /query /tn \ModelBus-zgate-hidden` 等两个 | 自启与看门狗 | 60s |

### 2.3 不能破坏的契约

`/health` 现在有 5 个消费方，全部按 JSON 解析：

- `gateways/zgate/main.go:322-343` 的 `probeHealth` 用 `json.Unmarshal`（否则启动判定失败）
- `internal/router/router_test.go:186-203` `TestHealthExposesNoKeys` 断言 `json.Valid`
- `internal/router/router_test.go:733-758` `TestHealthHasEveryChannelSegmentWithState` 断言 7 段齐全
- `tools/zgate-lifecycle/deploy-zgate.ps1:72-77` 与 `tools/rename-to-modelbus.ps1:218` 只判 `StatusCode == 200`
- `tools/check-project.py:120-133` 做静态源码断言（`for _, channel := range keys.Channels`、`func healthSegmentName(` 必须在位）

**结论**：`/health` 的默认响应永远是 JSON。任何 HTML 视图只能挂在「显式 `Accept: text/html`」或独立端口上 —— 这也是后台独立成进程的硬理由之一（Go 的 `http.Get` 不发 `Accept`，脚本侧天然不受影响）。

---

## 3. 架构：为什么是独立进程

| 方案 | 做法 | 优点 | 致命点 |
|---|---|---|---|
| A 独立后台服务（**采用**） | `tools/console/server.py` 读文件 + 读 `/health`，自己出页面 | 加页面不用换二进制、console 挂了不影响代理、可用 Python 标准库随手改 | 多一个进程要拉起 |
| B 塞进 zgate | `go:embed` 静态文件 + `serveHTTP` 加分支 | 单进程、端口省一个 | 40 个路径的读取逻辑进关键路径；每次改页面都要 `build.py` + 换版重启，而重启会断正在跑的会话流量 |
| C 纯静态页 | 一个 html 直读 `file://` | 零进程 | 浏览器禁止 `file://` 跨源读本地 json，等于没有数据面 |

选 A 的三条理由：

1. **数据面 90% 是文件，不是网关内存**。zgate 内存里只有 alias 和冷却态，其余全在磁盘和子进程产物里；把这些读取搬进网关，只会把「看板故障」升级成「代理故障」。
2. **仓库纪律是「只用标准库」**（`docs/TOOLS.md` §0）。Go 侧要出模板就得 `html/template` + `go:embed` + 手写静态路由，收益却只是省一个端口。
3. **失败隔离**。console 崩了，7871 照常转发；这比「看板拖垮网关」重要得多。

P3 保留一个桥：zgate 在 `Accept` 含 `text/html` 时对 `/health` 回 `302 → http://127.0.0.1:7872/#/health`。改动约 10 行、只在浏览器触发，满足「在浏览器打开 7871/health 就看到页面」，脚本与测试完全不受影响。

---

## 4. 前端选型（2026-11-10 实测）

约束先摆出来：**不许 CDN、不许 npm、不许构建链**（`docs/TOOLS.md`、`docs/UPSTREAM.md` §「只用标准库」）。所以只看「能直接 vendor 的产物」。

| 库 | stars | 许可 | 需构建 | 单文件产物 | 结论 |
|---|---|---|---|---|---|
| `@material/web` 2.5.0 | 11,419 | Apache-2.0 | **要**（2,169 个 ESM 文件，依赖 Lit） | 无 | 排除：要打包链 |
| MDUI 2.1.5 | 4,539 | MIT | 否 | `mdui.css` 22.7 KB + `mdui.global.js` 363 KB | 备选：真 MD3 Web Components、中文文档，但 shadow DOM 定制麻烦、JS 偏大 |
| **Beer CSS 5.0.3** | 2,639 | MIT | 否 | `beer.min.css` **87.9 KB**（`beer.min.js` 18.7 KB 可完全不用） | **采用** |
| Materialize 1.0.0 | 38,772 | MIT | 否 | 316 KB | 排除：MD1/MD2 风格，停更 6 年 |

选 Beer CSS 的理由：单 CSS 覆盖全部元素、**样式不进 shadow DOM**（MD3 token 直接覆盖就能改主题）、零 JS 依赖、MIT、brotli 后仅 14.5 KB。代价是文档纯英文，且它只有 MD3 语义色（primary / secondary / tertiary / error），**没有 green / red**，状态色自己补三行 CSS。

图标不引 Material Symbols 字体（多 200 KB 且要断网可用），全部用内联 SVG，约 16 个，单图标 ≤ 400 B。

体积预算：`index.html` 12 KB + `app.css` 14 KB + `app.js` 30 KB + `beer.min.css` 88 KB ≈ **144 KB**（gzip 后 ≈ 35 KB），首屏一次拉完。

---

## 5. 信息架构：8 页

| # | 页面 | 一句话 | 主要数据源 | 刷新 |
|---|---|---|---|---|
| 1 | 总览 | 现在坏没坏、今天花了多少、哪条链快到期 | `/health`、`request-logs`、`_last-sync.txt`、`quota-windows` | 5s |
| 2 | 模型 | 19 个别名长什么样、链路怎么跳 | `model-alias-map.json` | 30s |
| 3 | 价格 | 谁便宜、谁性价比高、折扣与错峰 | alias `price`、`wb_pricing`、`qd_prices`、`model-scores` | 60s |
| 4 | 健康 | 探针矩阵 + 流式准入 + 冷却倒计时 | `model_probe`、`model-stream/latest`、`/health.race` | 30s |
| 5 | 流量 | 请求量、成功率、TTFB 分位、token 与成本 | `requests-*.jsonl`、`usage-summary` | 30s |
| 6 | 账号 | 8 个 WB 账号余额与信用、Qoder 用量 | `data/*.json`、`auths/`（掩码） | 30s |
| 7 | 日志 | 网关 / 同步 / 生命周期 / 子进程，可搜可跟 | 4 类 `.log` | 手动 + 可选 3s |
| 8 | 运维 | 配置只读、计划任务、门禁、reload 与长任务 | `zgate.json`、`schtasks`、门禁脚本 | 15s |

页面 1 就是「`/health` 的可视化」；P3 之后浏览器访问 `7871/health` 会 302 到这里。

---

## 6. 每页字段

### 6.1 总览

- **顶部 4 个 KPI**：网关 uptime（`/health.uptime_s`）、渠道在线（`7/7`，按 7 段 `state` 计数）、今日请求数（`request-logs` 行数）、冷却中渠道数（`/health.cooling`）
- **渠道灯条**：7 个 `OC/WB/QD/QW/QN/GM/HJ` 方块，颜色取 `state`（见 §8.3）；hover 出 `base` 与 `last_error`
- **子进程卡**：`workbuddy`（pid / idle_s / in_window / policy）与 `qoder`（state / port），`stopped` 用灰，`running` 用绿
- **最近同步**：`_last-sync.txt` 的时间 + `model-sync-state.json` 的 `models` 数量，与 alias map 的 `generated_at` 做**偏差提示**（实测曾出现 alias 18:06 而视图 12:05 的过期场景）
- **额度临期**：`quota-windows.json` 里 `days_left ≤ 30` 的条目做成倒计时条
- **错误横幅**：任一渠道 `last_error` 非空时置顶，点击跳到日志页并带上渠道名做过滤词

### 6.2 模型

- 按 `group`（主力 / 免费 / 省钱）分栏，每栏一张表：别名 / 渠道 / 单价 / 跳数 / `protocol`
- 点开一行看到 **chain 竖向卡片**：每跳显示「渠道徽章 + `base` + `protocol` + `price` + `original`」，第一跳标「主」、后续标「F1…Fn」
- `legacy_ids` 默认折叠，显示条数；展开是一列等宽 id
- 与 `/models` 的目录做**差集高亮**：alias 有而目录没有 = 未生效（红），目录有而 alias 没有 = 遗留（黄）

### 6.3 价格

- 主表：`alias price` × 渠道 × 组，支持按价格/评分排序
- 性价比列 = `model-scores.score / price`，按它排序就是「哪个最划算」
- WB 折扣区：`wb_pricing.json` 的 705 行按组折叠，只展开与当前 alias 模型清单相关的行
- Qoder 峰谷区：`qd_prices.json` 的 `off_peak` 字段单独一列
- 每张表右上角必须显示**缓存时间**（`generated_at` 或文件 mtime），避免把旧价当新价

### 6.4 健康

- **探针矩阵**：`model_probe.json` 全量（约 50+ id），列 = 模型 / `status` / `http` / `ms` / `credit` / `provider`，`ms` 用条形长度辅助
- **流式准入**：`model-stream/latest.json` 的 19 条，列 = 模型 / `state` / `tps` / `firstMs` / `effort` / `finishReason`；`reasons` 进 tooltip
- **冷却面板**：`/health.race.hops` 每跳的 `verdict` 与 `firstBlockMs`，`race.disabled` 显示剩余秒并本地倒计时
- 顶部一行汇总：`ok / fail / skip` 三档计数

### 6.5 流量

- 聚合维度三选一：**按小时 / 按模型 / 按账号**（`requests-*.jsonl` 流式逐行累加，不全量入内存）
- 每行：请求数 / 成功数 / 成功率 / `ttfb_ms` 的 p50 与 p95 / 平均 `attempts`（重试率）/ 总 tokens / `cache_hit` 占比 / credit
- 顶部 KPI：今日请求、今日 tokens、今日成本（`credit` 优先，缺失用 `cost_usd`）、最慢 p95 模型
- `days` 参数最多 7（现有 7 个日文件），选多天时按天出迷你柱

### 6.6 账号

- WB 账号卡：数量 8，每张只显示**掩码 id**（前 4 后 2）、最近活跃时间、`balance_history` 最新余额、`credit-history` 最近 5 笔
- `usage.json` 的 `buckets` 按小时聚合出迷你折线（纯 SVG，不引图表库）
- `state.json` / `task-jobs` / `task-runs`：最近任务成功失败各几条
- Qoder 区：`usage-summary.json` 的 `requests / errors / total_tokens / cost_usd / unpriced`，`by_model` 出一张小表
- **红线**：`auths/*.json` 的任何 token / cookie / 邮箱**永不出现在响应里**，只出条数与掩码

### 6.7 日志

- 四个来源切换：`zgate` / `sync` / `lifecycle`（daemon、launch、deploy、watchdog 合一）/ `child`（workbuddy、qoder 的 stdout 与 stderr）
- `tail` 默认 200 行，可调 100–2000；关键词过滤在服务端做（避免把 5 MB 全推给浏览器）
- 级别按行首 `LEVEL` 上色：`ERROR` / `WARN` / 其它
- 「跟随」开关：开时每 3s 拉新增（服务端记字节偏移，只回增量）

### 6.8 运维

- **配置只读视图**：`zgate.json` 结构化成四块 —— 监听与路径、7 个 upstreams 的 `base`、两个 child 的 `exe/port/health`、`channelPolicy` 与 `reasoningGuard` 的参数表；只读，不提供编辑框（改配置走 `deploy-zgate.ps1` 流程）
- **计划任务**：`\\ModelBus-zgate-hidden`、`\\ModelBus-zgate-watchdog` 的状态与下次运行时间（`schtasks /query /fo LIST` 解析）
- **门禁**：`check-project.py` / `check-docs.py` / `check-secrets.py` 最近一次结果（exit code + 首行摘要），结果缓存在 `.work/console/gates.json`
- **动作区**（都要二次确认）：热加载（`POST 7871/admin/reload`）、跑门禁（P2）、跑探针（P2）、跑同步（P2）
- **同步历史**：`docs/reports/` 文件名列表 + `_last-sync.txt` 内容

---

## 7. API 契约

统一响应包，前端只认这一个形状：

```json
{
  "ok": true,
  "generated_at": "2026-11-10T18:30:00+08:00",
  "ttl_ms": 5000,
  "data": { }
}
```

失败：`{"ok": false, "error": {"code": "UPSTREAM_DOWN", "message": "127.0.0.1:7871 连接失败"}}`，HTTP 状态码同步（200 / 400 / 500 / 503）。

| 端点 | 方法 | 参数 | 返回 | TTL |
|---|---|---|---|---|
| `/api/overview` | GET | — | KPI + 渠道灯 + 子进程 + 同步摘要 + 额度临期 + 横幅 | 5s |
| `/api/gateway` | GET | — | `/health` 原始 JSON + 派生的 `channels[]`（含冷却剩余秒） | 5s |
| `/api/models` | GET | — | 19 条别名 + chain + legacy + 与 `/models` 的差集 | 30s |
| `/api/prices` | GET | — | 统一价表（alias + WB + Qoder + 评分） | 60s |
| `/api/probe` | GET | `mode=probe\|stream` | 探针矩阵 / 准入矩阵 | 60s |
| `/api/traffic` | GET | `days=1..7`、`group=hour\|model\|account` | 聚合行 + KPI | 30s |
| `/api/accounts` | GET | — | WB 掩码账号 + 余额/信用 + Qoder 用量 | 30s |
| `/api/logs` | GET | `name=zgate\|sync\|lifecycle\|child`、`file=`、`tail=200`、`q=` | 行数组 + 是否还有更多 | 0 |
| `/api/logs/stream` | GET | `name=`、`offset=` | 增量行 + 新 offset | 0 |
| `/api/config` | GET | — | 脱敏后的 `zgate.json` 视图 | 30s |
| `/api/ops` | GET | — | 计划任务 + 门禁缓存 + 报告列表 | 15s |
| `/api/actions/reload` | POST | — | 透传 `{ok, applied, stale, added, note}` | — |
| `/api/actions/jobs` | POST | `{job: probe\|sync\|gates}` | `{job_id}` | — |
| `/api/actions/jobs/{id}` | GET | — | 状态 + 尾部输出 | — |
| `/healthz` | GET | — | 后台自身存活与各数据源可达性 | 0 |

错误码：`SOURCE_MISSING`（文件不存在，多半是还没跑过）、`PARSE_ERROR`（json 坏了）、`UPSTREAM_DOWN`（7871 不通）、`BAD_REQUEST`、`JOB_BUSY`（同类型任务在跑）。

---

## 8. 前端实现约束

### 8.1 骨架与路由

- 顶栏（app bar）：标题 + 全局刷新 + 数据新鲜度（「刚更新 / 23s 前」）+ 暗色开关
- 侧栏（navigation drawer）：8 个入口；≥1240px 常驻，更窄时收成抽屉
- 路由用 hash（`#/overview`、`#/models`…），刷新与直链都能回到同一页，不需要后端 rewrite

### 8.2 数字与排版

- 所有数字 `font-variant-numeric: tabular-nums`，表格右对齐，单位用小字跟在数字后（`312 ms`、`1.2 M tok`）
- 相对时间用「12s 前 / 3 分钟前」，绝对时间进 `title`

### 8.3 状态色（MD3 token 映射）

| 语义 | token | 用于 |
|---|---|---|
| 正常 | `tertiary-container` / `on-tertiary-container` | `state=ok`、探针 `status` 正常、任务成功 |
| 注意 | 自定义 `--warn-container`（琥珀） | 过期视图、`days_left ≤ 30`、重试率高 |
| 故障 | `error-container` / `on-error-container` | 渠道 down、`last_error` 非空、`stale=true` |
| 冷却 / 停用 | `surface-variant` / `on-surface-variant` | `cooling`、`state=stopped`、`disabled` |

规则：**颜色只用在「需要人做决定」的地方**，纯信息数字一律 `on-surface`，避免满屏彩色反而看不出重点。

### 8.4 空态、错态、加载

- 空态：一句话说明「这个文件还没生成，先跑 `tools/model_probe.py`」，给出可复制的命令
- 错态：错误码 + 原始报错首行 + 「重试」，不要只说「加载失败」
- 加载：首次进入用骨架块，刷新时只在顶栏转小圈，**不清空已有内容**（避免闪烁）

### 8.5 暗色与可达性

- 暗色 = `<html class="dark">` + `localStorage`，默认跟随系统
- 状态不只靠颜色：徽章始终带文字（`OK` / `FAIL` / `冷却`），照顾色弱
- 焦点可见、全键盘可达；`prefers-reduced-motion` 时关掉过渡

---

## 9. 安全与脱敏

| 项 | 做法 |
|---|---|
| 绑定 | 只 `127.0.0.1:7872`，不 `0.0.0.0`；校验 `Host` 头只接受 `127.0.0.1:7872` / `localhost:7872` |
| 跨站 | 不发任何 CORS 头；写操作额外校验 `Origin`（缺省或同源才放行） |
| 凭据 | 一律不出响应。`provider_config.json` 只出 `{provider, models, has_key: bool}`；`.env.local` 只出键名；`auths/*.json` 只出条数与掩码 |
| 掩码 | 账号 id 前 4 后 2；`client_ip` 只留 `127.0.0.1`；`user_agent` 截断 60 字符 |
| 写操作 | 只有 `reload` 与 P2 的三种长任务；全部 POST + 前端二次确认弹窗；**绝不自动重启 zgate**（长驻进程纪律） |
| 不做 | 不代理 WB `panel/api`（会把鉴权 key 带到前端）、不提供配置编辑、不在前端拼接任何 shell 命令 |

---

## 10. 目录与启动

```text
tools/console/
  server.py                # HTTP 服务 + 路由 + 统一响应包（stdlib）
  sources.py               # 数据源适配器：每个源一个函数 + TTL 缓存
  actions.py               # reload 透传与长任务触发（P2）
  static/
    index.html             # 单页骨架
    app.css                # 布局与状态色（MD3 token 覆盖）
    app.js                 # 路由 + 拉数 + 渲染（原生 JS，无框架）
    vendor/beer.min.css    # Beer CSS 5.0.3（87.9 KB，MIT）
    vendor/LICENSE-beercss.txt
  start-console.ps1        # 隐藏窗口拉起（可选计划任务）
```

启动：

```cmd
python tools\console\server.py --port 7872
```

自检：`python tools\console\server.py --check` —— 逐个读数据源、断言关键字段、打印每个源的字节数与耗时，任何源缺失都不算失败（只标灰）。

---

## 11. 分期

| 期 | 范围 | 网关改动 | 验收 |
|---|---|---|---|
| **P0** | 总览 / 健康 / 日志 三页 + 骨架与导航 | 无 | `curl` 三个 API 全 200；页面能看出「哪个渠道坏、哪条日志报错」 |
| **P1** | 补齐模型 / 价格 / 流量 / 账号 / 运维（只读） | 无 | 八页全部有数据；八页里没有一处 `NaN` / 空白表 |
| **P2** | 写操作：reload、跑门禁、跑探针、跑同步（排队 + 禁并发） | 无 | 连点两次只跑一次（`JOB_BUSY`）；reload 成功后 `stale=false` |
| **P3**（可选） | zgate 在 `Accept: text/html` 时 302 到后台 | 约 10 行 + 一次换版 | `curl -H 'Accept: text/html' 7871/health` 得 302；`curl`（无 Accept）仍是 JSON；两个 router 测试仍绿 |

P0 与 P1 只读，随时可停；P2 起才有副作用，每个动作都留日志。

---

## 12. 验收标准

1. **零外网**：`grep -E 'https?://' tools/console/static/` 只允许出现 `127.0.0.1`；断网可用。
2. **零依赖**：`pip list` 无关；只用标准库（`http.server`、`json`、`pathlib`、`socket`、`subprocess`、`re`）。
3. **体积**：`static/` 总计 ≤ 200 KB，首屏一个 HTML + 一个 CSS + 一个 JS。
4. **响应时间**：本机 `/api/overview` ≤ 120 ms（缓存命中）；`/api/traffic?days=7` ≤ 800 ms。
5. **不碰网关**：实现里没有 `zgate.exe` 的启停调用；`reload` 只发 HTTP。
6. **不影响既有门禁**：`python tools/check-project.py`、`python tools/check-docs.py` 仍 exit 0。
7. **`/health` 契约不变**：`curl 7871/health` 仍是 `Content-Type: application/json`、`json.Valid`、7 段齐全。
8. **脱敏**：对 `/api/config`、`/api/accounts` 的响应做一次 `grep -iE 'apikey|token|cookie|secret|sk-'`，必须零命中。

---

## 13. 风险与回退

| 风险 | 触发条件 | 处理 |
|---|---|---|
| 端口冲突 | 7872 被别人占了 | `--port` 参数；起不来时打印占用者 pid |
| `/health` 轮询压力 | 多标签页同时开 | 服务端 5s 缓存合并，前端只跟一个定时器；标签页 `visibilitychange` 隐藏时停轮询 |
| 请求日志过大 | 日文件上万行 | 流式逐行聚合 + 30s 缓存；只读最近 7 天，不做全历史 |
| 视图过期 | 同步完没刷新 | 顶部与每表都标数据时间，过期（与 `alias.generated_at` 差 > 1h）显式标黄 |
| 误触写操作 | 点了 reload | 二次确认 + 结果 toast；失败保留原始报错 |
| 后台进程消失 | 关机 / 会话结束 | P1 提供 `start-console.ps1` 与可选计划任务；服务本身无状态，重启无副作用 |

回退：删 `tools/console/` 一个目录即完全消失，不涉及网关与配置。

---

> 相关：`/health` 的字段语义见 [ARCHITECTURE.md](ARCHITECTURE.md)，别名与链路见 [MODEL-ALIAS.md](MODEL-ALIAS.md)，
> 生命周期与换版见 [ZGATE-LIFECYCLE.md](ZGATE-LIFECYCLE.md)，脚本产物去留见 [TOOLS.md](TOOLS.md)。
