# ModelBus 控制台（Console）

> **一句话**：把散在 40 个文件、7 个渠道、3 个端点里的运行数据，聚合成一个只跑在 `127.0.0.1:7872` 的单页后台 —— **Tabler 1.7.4 高星后台外壳 + Microsoft Fluent 2 主题令牌**，网关零改动、前端零 CDN、零构建、零 npm、零第三方 Python 包。

状态：**已落地 v3（2026-11-12）**。v1 是 MD3 / Beer CSS 设计稿，v2 把设计规则改为 **Microsoft Fluent 2 语义令牌**（全手写组件 CSS），v3 按用户「去 GitHub 找高星后台 UI 仓库然后套用」改为 **Tabler 1.7.4 官方竖向骨架与组件类 + Fluent 2 令牌桥接**：外壳用成熟库，设计规则仍是 Fluent 2。实现见 `tools/console/`，本文是正本与验收口径。

---

## 0. 结论速览

| 项 | 决定 |
|---|---|
| 形态 | 独立 Python 进程 `tools/console/server.py`，**不塞进 zgate** |
| 地址 | `http://127.0.0.1:7872`（7871 / 7863 / 8790 已占用，7872 实测空闲） |
| 设计规则 | **Microsoft Fluent 2**：语义色令牌、4px 间距刻度、4/6/8px 圆角、上方光阴影、状态色 + 文字双编码；通过 `--tblr-* → --mb-*` 变量桥接注入 Tabler 外壳 |
| 前端 | 4 个手写静态文件 **41,816 B** + 本地 vendor `tabler.min.css` **686,736 B**（MIT）+ `LICENSE-tabler.txt` 1,247 B；零 npm / 零 CDN / 零构建链 / 零加载型外链，vendor 单文件 **25 个** `url()` 全是内联 `data:image/svg+xml` |
| UI 库 | **Tabler 1.7.4**（`tabler/tabler` 42,052★ / MIT / pushed 2026-11-10 / `@tabler/core@1.7.4`）；官方竖向骨架 + 组件类，`app.css` 只做令牌桥接与少量专有类 |
| 页面 | 8 个：总览 / 模型 / 价格 / 健康 / 流量 / 账号 / 日志 / 运维 |
| 数据 | 13 个只读 `/api/*` + `/healthz` + SSE 日志流；写操作只有 `reload` |
| 网关改动 | **零改动**；P3 的 302 桥未实施 |
| 依赖 | Python 3.12 标准库（`http.server` / `json` / `pathlib` / `urllib` / `re` / `shutil`） |

启动与自检：

```cmd
python tools\console\server.py --port 7872
python tools\console\server.py --check
```

隐藏窗口拉起：`powershell -File tools\console\start-console.ps1 -Detach`（日志落 `.work/console.stdout.log` / `.work/console.stderr.log`）。

---

## 1. 现在缺什么

三个实测事实决定了这个后台该长什么样：

1. **`/health` 只出 JSON**，2026-11-12 实测 **2738 B**（v1 稿记的 1166 B 已过期），7 个渠道段 + 子进程 + 冷却 + 竞速 + guard 挤在一层里。信息全，但没有层级，人眼扫不出「哪一段现在是坏的」。
2. **可可视化资产 38 项、页面候选 12 类**，散在 `~/.zcode/v2/`、`providers/*/cache/`、`gateways/upstream/*/data/`、`%LOCALAPPDATA%/` 四个根下，跨 5 种格式（json / jsonl / 按天分文件的 jsonl / 文本日志 / markdown 报告）。
3. **网关只有三个非代理端点**：`GET /health`、`GET /models`、`POST /admin/reload`（`/v1/models` 剥前缀后落同一 handler）。没有 `/metrics`、没有模板引擎、没有 CORS，也没有任何计数聚合 —— `/health` 是唯一指标出口。

所以它的价值不是「给 `/health` 加个页面」，而是**把 40 个文件读成 8 张能一眼判断的表**，并且让 `/health` 那份 JSON 变成其中一页。

---

## 2. 数据面（2026-11-12 复测）

### 2.1 端点

| 端点 | 方法 | 说明 | 注意 |
|---|---|---|---|
| `127.0.0.1:7871/health` | GET | 网关健康快照 | **每次请求都会 `aliases.Reload()` 重读 alias map 文件**，后台用 5s 服务端缓存合并，轮询间隔 ≥ 5s |
| `127.0.0.1:7871/models`、`/v1/models` | GET | 模型目录简表（同源，实测字节相同，Content-Length 2193） | 只有 `id` / `owned_by`，**没有价格、链路、legacy** |
| `127.0.0.1:7871/admin/reload` | POST | 热加载 alias / 配置 | 无鉴权，只靠绑定 127.0.0.1；返回 `{ok, applied, stale, added, note}`；`GET` 为 405 |
| `127.0.0.1:7863/panel/api/*` | GET | WorkBuddy 面板 | 需自身鉴权 —— **后台不代理它**，只读本地 `data/*.json` |
| `127.0.0.1:8790/ping` | GET | Qoder 存活 | 只判活 |

网关路由字面量在 `gateways/zgate/internal/router/router.go:583/587/591`，`/v1` 前缀剥离在 `:2001-2005`；`health` 实现在 `:1425-1474`（首行 `s.aliases.Reload()`，`upstreamView` 只出 `hasKey` 布尔不出值）。

### 2.2 文件与日志

| 分组 | 路径 | 关键内容 | 后台 TTL |
|---|---|---|---|
| 模型真值 | `~/.zcode/v2/model-alias-map.json` | 18 个模型 + legacy 映射（实测 23,928 B） | 30s |
| Provider 配置 | `~/.zcode/v2/provider_config.json` | 三组 provider + 模型映射 | 60s，**只露存在性与键名** |
| 探针 | `~/.zcode/v2/model_probe.json` | 每模型 `status/http/ms/detail/provider/ever_ok`（49,389 B） | 30s |
| 评分 | `~/.zcode/v2/model-scores.json` | `basis` + `models`（1,767 B） | 60s |
| 额度 | `~/.zcode/v2/quota-windows.json` | `windows[3]`（621 B） | 60s |
| 竞技榜 | `~/.zcode/v2/arena-leaderboard.json` | `rows[231]` + `totals`（117,012 B） | 300s |
| 价格 | `providers/workbuddy/cache/wb_pricing.json`（39 项，14,201 B）、`providers/qoder/cache/qd_prices.json`（13 项，2,744 B） | WB 折扣价、Qoder 峰谷价 | 60s |
| 请求明细 | `gateways/upstream/workbuddy/data/request-logs/requests-YYYY-MM-DD.jsonl` | 单日 2.95–6.73 MB，字段含 tokens / ttfb / attempts / credit | 15s，**流式 tail 800 行，不全量入内存** |
| 网关日志 | `%LOCALAPPDATA%/ZCodeGateway/zgate.log`（4,408,304 B） | `时间 LEVEL msg` | 不缓存，尾读 1 MiB |
| 生命周期日志 | 同目录 `{zgate-daemon,zgate-launch,deploy-zgate,watchdog}.log` | 启停与换版 | 不缓存 |
| 子网关日志 | 同目录 `workbuddy.stdout.log`（18.4 MB）/ `.stderr.log` / `qoder.stderr.log` | 子进程原始输出，只报体积不读全文 | 不缓存 |
| 账号 | `gateways/upstream/workbuddy/auths/*.json`（实测 8 个，每个 ~3,400 B） | 含凭据字段 | 60s，**只出条数与掩码** |
| 配置 | `gateways/zgate/zgate.json` | 上游 base、子进程、channelPolicy、reasoningGuard | 60s |

### 2.3 不能破坏的契约

`/health` 现在有 **6 个消费方**，全部按 JSON 解析：

- `gateways/zgate/main.go:322-343` 的 `probeHealth` 用 `json.Unmarshal`（否则启动判定失败）
- `internal/router/router_test.go:186-203` `TestHealthExposesNoKeys` 断言 `json.Valid`
- `internal/router/router_test.go:733-758` `TestHealthHasEveryChannelSegmentWithState` 断言 7 段齐全
- `tools/zgate-lifecycle/deploy-zgate.ps1:72-77` 与 `tools/rename-to-modelbus.ps1:218` 只判 `StatusCode == 200`
- `tools/check-project.py:120-133` 做静态源码断言
- `tools/console/sources.py:150-175` `_get()` 发 `Accept: application/json`、2.5s 超时、`json.loads`，非 JSON 抛 `UPSTREAM_DOWN`

**结论**：`/health` 的默认响应永远是 `application/json; charset=utf-8`。任何 HTML 视图只能挂在「显式 `Accept: text/html`」或独立端口上 —— 这是后台独立成进程的硬理由之一（Go 的 `http.Get` 不发 `Accept`，脚本侧天然不受影响）。实测 `GET/POST/HEAD /health` 均 200 且回同一 2738 B JSON（`serveHTTP` 只判 path 不判 method），所以后台换成独立端口后网关一行都不用动。

---

## 3. 架构：为什么是独立进程

| 方案 | 做法 | 优点 | 致命点 |
|---|---|---|---|
| A 独立后台服务（**采用**） | `tools/console/server.py` 读文件 + 读 `/health`，自己出页面 | 加页面不用换二进制、console 挂了不影响代理、可用 Python 标准库随手改 | 多一个进程要拉起 |
| B 塞进 zgate | `go:embed` 静态文件 + `serveHTTP` 加分支 | 单进程、端口省一个 | 40 个路径的读取逻辑进关键路径；每次改页面都要 `build.py` + 换版重启，而重启会断正在跑的会话流量 |
| C 纯静态页 | 一个 html 直读 `file://` | 零进程 | 浏览器禁止 `file://` 跨源读本地 json，等于没有数据面 |

选 A 的三条理由：

1. **数据面 90% 是文件，不是网关内存**。zgate 内存里只有 alias 和冷却态，其余全在磁盘和子进程产物里；把这些读取搬进网关，只会把「看板故障」升级成「代理故障」。
2. **仓库纪律是「只用标准库」**（[TOOLS.md](TOOLS.md) §0）。Go 侧要出模板就得 `html/template` + `go:embed` + 手写静态路由，收益却只是省一个端口。
3. **失败隔离**。console 崩了，7871 照常转发；这比「看板拖垮网关」重要得多。

P3 保留一个桥（**未实施**）：zgate 在 `Accept` 含 `text/html` 时对 `/health` 回 `302 → http://127.0.0.1:7872/#/health`。改动约 10 行、只在浏览器触发，脚本与测试完全不受影响。本轮按「网关零改动」不做。

---

## 4. 设计规则：Fluent 2 令牌 + Tabler 1.7.4 外壳（2026-11-12 查证）

约束先摆出来：**不许 CDN、不许 npm、不许构建链、不许第三方 Python 包**（[TOOLS.md](TOOLS.md)、[UPSTREAM.md](UPSTREAM.md) §「只用标准库」）。v1 稿选的 Beer CSS 5.0.3 是 **MD3** 语义（`primary/tertiary-container/error-container`），与用户指定的 Microsoft Fluent 2 不是一套体系；`@fluentui/react-components` 又必须走 React + 打包链。v2 因此把 Fluent 2 官方令牌落成一层 CSS 自定义属性、全手写组件；v3 按用户要求「去 GitHub 找高星后台 UI 仓库然后套用」，改为 **Tabler 1.7.4 的官方竖向骨架与组件类 + Fluent 2 令牌桥接**：Tabler 单 CSS 文件本地 vendor（686,736 B，MIT，零外链、零 `@import`、零 CDN），`app.css` 只保留 `--mb-*` 语义令牌并把 `--tblr-*` 变量一次性映射到 `--mb-*`，组件基础样式（`.btn` / `.card` / `.table` / `.badge` / `.empty` / `.alert` / `.modal` / `.nav-link`）全部交给 Tabler，手写 CSS 从 266 行降到 194 行。light/dark 仍只换 `:root[data-theme="dark"]` 的令牌值，并经 `var()` 运行时自动传导给 Tabler；主题切换同时写 `data-theme` 与 `data-bs-theme`。

### 4.1 外部事实卡

| 来源 URL | 确切值 | 适用版本 | 查证时间 | 用于哪步 |
|---|---|---|---|---|
| https://github.com/microsoft/fluentui/blob/master/packages/tokens/src/global/spacings.ts | `spacingHorizontalXS=4px / S=8px / SNudge=6px / MNudge=10px / M=12px / L=16px / XL=20px / XXL=24px / XXXL=32px` | Fluent UI v9 tokens（master，2026-11-12） | 2026-11-12 16:37 | 定 `--mb-sp-1..8` 间距刻度 |
| https://github.com/microsoft/fluentui/blob/master/packages/tokens/src/global/borderRadius.ts | `borderRadiusMedium=4px / Large=6px / XLarge=8px / 2XLarge=12px` | 同上 | 同上 | 定 `--mb-radius-s/m/l` |
| https://github.com/microsoft/fluentui/blob/master/packages/tokens/src/alias/lightColor.ts | `colorNeutralForeground1=grey[14] #242424`、`colorNeutralBackground1=white`、`colorBrandBackground=brand[80]` | 同上 | 同上 | 定 light 中性/品牌令牌 |
| https://github.com/microsoft/fluentui/blob/master/packages/tokens/src/alias/darkColor.ts | `colorNeutralForeground1=white`、`colorNeutralBackground1=grey[16] #292929`、`colorBrandBackground=brand[70] #106EBE` | 同上 | 同上 | 定 dark 中性/品牌令牌 |
| https://github.com/veronicaward/skills/blob/main/skills/fluent2-design/references/color-tokens.md | `#0F6CBD / #115EA3 / #0E4775 / #B4D6FA`；中性 `#FFFFFF / #F5F5F5 / #F0F0F0 / #E0E0E0`、描边 `#D1D1D1 / #E0E0E0`、文字 `#242424 / #424242 / #616161 / #707070` | Fluent 2 Web（社区汇编，与官方别名互证） | 同上 | 定 light 主题实值 |
| https://open-design.ai/design-system/microsoft-fluent | 同上 spacing / radius 表 + 官方 `colorNeutralForeground1=grey[14]`、`colorNeutralBackground1=white/grey[16]` | Fluent 2 汇编页 | 同上 | 交叉核对，避免单源抄错 |
| `gh api repos/microsoft/fluentui/releases/latest`（C 路 `evidence/agent-audit.md` §8 一手实取） | `@fluentui/web-components@3.2.1` / MIT；latest release = `@fluentui/react-provider_v9.22.23`（2026-10-29T01:05:26Z），**不是** Web Components 版本，别拿它当组件库版本 | Fluent UI v9 / Web Components 3.2.1 | 2026-11-12 16:37 | 锁版本锚点；Fluent 2 只作设计规则，不引组件包 |
| `gh api repos/tabler/tabler` + `gh api repos/tabler/tabler/releases/latest`（一手实取） | `tabler/tabler` **42,052★**、MIT、`pushed_at=2026-11-10T22:13:59Z`、`archived=false`、默认分支 `dev`；latest release = `@tabler/core@1.7.4` | Tabler 1.7.4 | 2026-11-12 | 选库、锁版本、许可证 |
| `https://preview.tabler.io/layout-vertical.html`（官方骨架） | `.page` > `aside.navbar.navbar-vertical.navbar-expand-*` + `.page-wrapper`；`navbar-brand-autodark` / `navbar-toggler` / `collapse.navbar-collapse` / `nav-link-icon` / `nav-link-title` / `page-header` / `page-body` / `footer` | Tabler 1.7.4 | 2026-11-12 | 定 `index.html` 竖向骨架 |
| `gh api repos/ColorlibHQ/AdminLTE`（对照） | stars 更高，但 v4 的 npm 版本与 release tag 不同步，且依赖 FontAwesome CDN | AdminLTE v4 | 2026-11-12 | 排除：违反零 CDN、版本锚点不稳 |
| `tools/console/static/vendor/tabler.min.css`（本地实取） | **25 个** `url()` 全是内联 `data:image/svg+xml`；`@import` / `fonts.googleapis` / `cdn.jsdelivr` / `unpkg.com` / `url(http` 命中数均为 **0**；仅 `/*!` 注释头保留 `https://tabler.io` 与 MIT LICENSE 链接两个字面量（不产生任何请求）；25 处 `http://www.w3.org/2000/svg` 是内联 SVG 的 namespace | Tabler 1.7.4 | 2026-11-12 | 证明单 CSS 可完全离线本地 vendor |

### 4.2 与 v1 选库表的对照

| 库 | stars | 许可 | 需构建 | 结论 |
|---|---|---|---|---|
| `@fluentui/react-components` | — | MIT | **要**（React + 打包链） | 排除：违反零构建链 |
| `@material/web` 2.5.0 | 11,419 | Apache-2.0 | 要（ESM + Lit） | 排除：MD3 体系，且要打包 |
| Beer CSS 5.0.3 | 2,639 | MIT | 否（单 CSS 87.9 KB） | 排除：MD3 语义色，不是 Fluent 2 |
| MDUI 2.1.5 | 4,539 | MIT | 否 | 排除：MD3 Web Components、shadow DOM |
| AdminLTE v4 | 更高 | MIT | 否 | 排除：npm 版本与 release tag 不同步 + FontAwesome CDN，违反零 CDN |
| **Tabler 1.7.4（v3 采用）** | **42,052** | **MIT** | **否**（单 CSS 本地 vendor） | 官方竖向骨架 + 全套后台组件类；686,736 B 全部内联 data URI，零 CDN / 零 `@import` |
| 内联 Fluent 2 语义令牌（v2 采用，v3 保留为桥接层） | — | 项目自有 | 否 | `--mb-*` 令牌继续定义设计规则；`app.css` 只做 `--tblr-* → --mb-*` 映射 + 少量项目专有类 |

### 4.3 十二条落地规则

1. **层次优先**：字号/字重/颜色一起建立层级，不靠单一维度；KPI 28px 600，节标题 14px 600，正文 13–14px 400。
2. **每个值来自系统**：颜色、间距、圆角、阴影一律走 `--mb-*`；Tabler 组件通过 `--tblr-*: var(--mb-*)` 取值，手写 CSS 不写死十六进制。
3. **间距刻度**：`--mb-sp-1=4 / 2=8 / 3=12 / 4=16 / 5=20 / 6=24 / 8=32px`；组间间距 > 组内间距（`.section` 24px vs `.card` 16px）。
4. **圆角**：`4 / 6 / 8px` + pill，卡片用 8px，按钮/输入用 4px；桥接为 `--tblr-border-radius-sm/m/lg/pill`，Tabler `.card` / `.btn` 自动继承。
5. **可读列宽**：表格单元 `.cell-clip` 裁到 360px，歌词式长文本用 220 字符截断 + `title` 全文。
6. **对比度**：正文 `#242424` on `#FFFFFF` 满足 4.5:1；状态 `.badge.bg-*-lt` 用 10% 品牌/状态色淡底 + 文字，满足非文本对比。
7. **颜色不是唯一信号**：`.badge` 恒带文字（正常/异常/冷却/已配 key），并由 `.view .badge::before` 补 6px 圆点。
8. **单一主操作**：每屏只有 `.btn.btn-primary`（重载网关），其余是 `.btn.btn-outline-secondary`。
9. **光从上方**：`shadow2/8/16` 用 `0 1px 2px` / `0 4px 8px` / `0 8px 16px`，暗色只提透明度不换方向。
10. **数字对齐**：`font-variant-numeric: tabular-nums`，数值列右对齐。
11. **状态色只用在需要决策处**：纯信息数字一律 `--mb-fg-1`，避免满屏彩色。
12. **响应式与可达性**：按 Tabler `navbar-expand-md` 的 768px 断点折窄屏，`#nav-toggle` 纯原生切换 `.collapse.show`（不引 Bootstrap JS）；`:focus-visible` 2px 焦点环；模态 `Escape` 可关；日志 SSE 断开给文字提示。

体积实测（v3，2026-11-12）：手写资产 `index.html` 4,328 B + `app.css` 10,717 B + `app.js` 26,524 B + `favicon.svg` 247 B = **41,816 B**（预算 200 KB，占用 20.4%）；本地 vendor `vendor/tabler.min.css` **686,736 B** + `vendor/LICENSE-tabler.txt` 1,247 B **单独计**，不占手写预算。`--check` 分别打印 `handwritten static bytes` 与 `vendor static bytes`。

---

## 5. 信息架构：8 页

| # | 页面 | 一句话 | 主要数据源 | 刷新 |
|---|---|---|---|---|
| 1 | 总览 | 网关坏没坏、跳数与探测、采样成功率、可复核占用 | `/api/overview`、`/api/ops` | 10s |
| 2 | 模型 | 18 个别名 + 探测 / 评分 / 配额 / 榜单前 20 行 | `/api/models`、`probe`、`scores`、`quota`、`arena` | 手动 / TTL |
| 3 | 价格 | WB 39 项与 Qoder 13 项价目快照 | `/api/prices` | 60s |
| 4 | 健康 | `/health` 原样字段展开 + 原始 JSON（脱敏） | `/api/gateway` | 5s |
| 5 | 流量 | 请求量、成功率、耗时、token、按模型/状态/小时分布 | `/api/traffic` | 15s |
| 6 | 账号 | 8 个 WB 账号掩码 + 凭据红线 | `/api/accounts` | 60s |
| 7 | 日志 | `zgate.log` 尾部 + SSE 实时流 + 日志文件体积 | `/api/logs`、`/api/logs/stream` | 2s 推帧 |
| 8 | 运维 | 占用候选、环境变量/配置文件、动作记录 | `/api/ops`、`config`、`actions/jobs` | 30s |

路由用 hash（`#/overview` …），刷新与直链都能回到同一页，不需要后端 rewrite。前端 `all(paths)=Promise.allSettled`，单个数据源挂掉只让该块显示错误码，不拖垮整页。

---

## 6. 每页字段（与已落地实现对照）

| 页 | 已落地字段 |
|---|---|
| 总览 | 8 个 KPI（网关状态 / 别名模型 / 渠道段 / 跳数可用 / 探测通过 / 请求采样 / 采样成功率 / 可复核占用）；7 段渠道表（状态、凭据、base、child）；运行细节（uptime、冷却、guard、health 体积、平均耗时、token）；占用候选前 5 行 |
| 模型 | 别名表（模型名 + 映射规格脱敏截断）；探测表（状态/HTTP/ms/provider/详情/曾通）；评分表与配额窗口并排；榜单前 20 行（共 231 行，不全推） |
| 价格 | WB 表（id/credits/eff_rate/list_rate/促销/ctx/out/工具/默认 effort）；Qoder 表（price/peak/valley/off_peak） |
| 健康 | 网关契约卡（网关地址、`/health` ok 与 Content-Type、响应体积、`/v1/models` 条数、轮询下限）；字段原样表；原始 JSON 代码块 |
| 流量 | 5 个 KPI；按模型 / 按状态 / 按小时三张分布表；日志文件体积表 |
| 账号 | 凭据红线卡；WB 8 行（掩码 ID/昵称/掩码 UID/凭据存在性/过期/体积）；Qoder 账号文件表 |
| 日志 | SSE 实时框（每 2s 推尾部 20 行，上限 60s 后页面重连）；静态尾部 ≤160 行；日志文件体积表 |
| 运维 | 磁盘总量/可用/可复核占用；占用候选 5 类；环境变量与配置文件状态；动作记录（时间/动作/结果/HTTP/响应） |

v1 稿里「chain 竖向卡片」「alias 与 /models 差集高亮」「TTFB p50/p95」「按天迷你柱」「门禁缓存」属于 P2/P3 增补，本版未做，不写进验收口径。

---

## 7. API 契约

统一响应包，前端只认这一个形状：

```json
{ "ok": true, "generated_at": "2026-11-12T16:44:01+08:00", "ttl_ms": 5000, "data": { } }
```

失败：`{"ok": false, "error": {"code": "UPSTREAM_DOWN", "message": "..."}}`，HTTP 状态码同步（400 / 403 / 404 / 409 / 500 / 502）。

| 端点 | 方法 | 返回 | TTL |
|---|---|---|---|
| `/api/overview` | GET | KPI + 7 段渠道 + 运行细节 + 占用 | 5s |
| `/api/gateway` | GET | `/health` 脱敏原始 JSON + `/v1/models` + 体积与轮询下限 | 5s |
| `/api/models` | GET | 18 条别名 + legacy 计数 + 文件元信息 | 30s |
| `/api/probe` | GET | 探针全量行 + 通过/总数 | 30s |
| `/api/prices` | GET | WB 39 项 + Qoder 13 项 | 60s |
| `/api/scores` | GET | `basis` + `models` 行 | 60s |
| `/api/quota` | GET | `windows[]` | 60s |
| `/api/arena` | GET | 榜单行（前端只展前 20） | 300s |
| `/api/traffic` | GET | 尾部 800 行聚合 | 15s |
| `/api/accounts` | GET | 掩码账号 + 凭据红线 | 60s |
| `/api/logs` | GET | `zgate.log` 尾部 + 日志文件体积 | 5s |
| `/api/config` | GET | 环境变量键名 + 配置文件存在性/体积 | 60s |
| `/api/ops` | GET | 占用候选 + 磁盘用量 | 30s |
| `/api/logs/stream` | GET | `text/event-stream`，30 帧 × 2s | 0 |
| `/api/actions/jobs` | GET | `{running, history, allowed:["reload"]}` | 0 |
| `/api/actions/reload` | POST | 透传 `{ok, applied, stale, added, note}` | — |
| `/healthz` | GET | 后台自身存活 + 网关地址 | 0 |
| `/`、`/index.html`、`/app.css`、`/app.js`、`/favicon.svg`、`/vendor/tabler.min.css` | GET | 静态文件（含本地 vendor 单 CSS） | no-cache |

错误码：`SOURCE_MISSING`（文件不存在）、`PARSE_ERROR`（json / 解析坏）、`UPSTREAM_DOWN`（7871 不通）、`BAD_REQUEST`（未知路由 / Host 或 Origin 不合法）、`JOB_BUSY`（reload 互斥）。

写面只有 `POST /api/actions/reload`：`actions.py` 只发 `POST {GATEWAY}/admin/reload`（`data=b'{}'`），记录 status 与 json 响应，**不重启进程、不写配置、不碰凭据**；服务端校验 `Host` 且**必须带同源 `Origin`**（无 Origin 一律 403，挡住简单跨站 POST）。

---

## 8. 前端实现约束

### 8.1 骨架与路由

- Tabler 官方竖向骨架：`.page` > `aside.navbar.navbar-vertical.navbar-expand-md` + `.page-wrapper`；页头 `.page-header > .container-xl > .row.g-2`，主体 `.page-body > .container-xl > main#view`，页脚 `.footer.footer-transparent`
- 侧栏：`.navbar-brand-autodark` + `ul#nav.navbar-nav`（每页一个 `li.nav-item > a.nav-link`，含 `.nav-link-icon` / `.nav-link-title`）+ 网关状态 `.status-dot`；`navbar-expand-md` 的 **768px** 断点以上常显，以下由 `#nav-toggle` 纯原生切换 `.collapse.show`（**不引 Bootstrap JS**）
- 页头：`.page-pretitle` + `.page-title` + 数据新鲜度 + 明暗开关 + 单一主操作 `.btn.btn-primary`「重载网关」
- 路由用 hash；主题同时写 `data-theme` 与 `data-bs-theme`（Tabler 暗色选择器需要后者），`localStorage["mb-theme"]` 沿用；`app.css` 在 `tabler.min.css` 之后加载，靠 `--tblr-*: var(--mb-*)` 覆盖变量

### 8.2 数字与排版

- 所有数字 `font-variant-numeric: tabular-nums`，数值列右对齐；体积用 `bytes()` 统一 KB/MB/GB
- 全量 `esc()` 转义后才进 `innerHTML`，不拼未信任 HTML

### 8.3 状态色（Fluent 2 语义令牌映射）

| 语义 | Fluent 2 令牌 | Tabler 组件类 | 用于 |
|---|---|---|---|
| 正常 | `--mb-success-fg/bg` → `--tblr-green` | `.badge.bg-green-lt` | `state=ok/running`、探测通过、任务成功、已配 key |
| 注意 | `--mb-warning-fg/bg` → `--tblr-yellow` | `.badge.bg-yellow-lt` | 冷却、idle、pending、partial |
| 故障 | `--mb-danger-fg/bg` → `--tblr-red` | `.badge.bg-red-lt` / `.alert.alert-danger` | 渠道 down、`last_error`、`stale=true`、无 key、数据源错态 |
| 信息 | `--mb-info-fg/bg` → `--tblr-blue` | `.badge.bg-blue-lt` | guard 模式、版本类标签 |
| 停用 | `--mb-neutral-fg/bg` → `--tblr-secondary` | `.badge.bg-secondary-lt` / `.status-secondary` | 未知状态、空值、网关检测中 |

规则：**颜色只用在「需要人做决定」的地方**，纯信息数字一律 `--mb-fg-1`；每个 `.badge` 都带文字，并由 `.view .badge::before` 补 6px 圆点，照顾色弱。网关状态点用 `.status-dot.status-green|red|secondary`，同样是「颜色 + 文字」双编码。

### 8.4 空态、错态、加载

- 空态：Tabler `.empty > .empty-icon / .empty-title / .empty-subtitle`，一句话说明「这个数据源当前没有记录」，不拿占位数据冒充
- 错态：`.alert.alert-danger` + 错误码 + 原始报错首行 + 单源隔离（其他块照常出）
- 加载：`.empty > .empty-icon > .spinner-border.text-primary`；表格统一 `.card > .table-responsive > table.table.table-vcenter.card-table`；总览刷新不清空已有内容（避免闪烁）

### 8.5 暗色与可达性

- 暗色只换 `:root[data-theme="dark"]` 的 `--mb-*` 令牌值；`--tblr-*` 用 `var(--mb-*)` 定义，运行时自动传导，组件样式一行不改；`setTheme()` 同步写 `data-theme` / `data-bs-theme`，侧栏不再带 `data-bs-theme="light"` 硬锁
- 焦点可见、全键盘可达、模态 `Escape` 关闭、`aria-current` + `.nav-link.active` 标当前页、`aria-live` 标视图与 toast；`.navbar-vertical .nav-link-icon` 用 `display:inline-grid !important` 覆盖 Tabler 断点媒体查询里的隐藏规则

---

## 9. 安全与脱敏

| 项 | 做法 |
|---|---|
| 绑定 | 只 `127.0.0.1:7872`，不 `0.0.0.0`；`Host` 只接受 `127.0.0.1` / `localhost` / `[::1]`（带或不带 :7872） |
| 跨站 | 不发任何 CORS 头；`POST` 额外校验 `Origin`，**缺省即拒绝**、非同源 403 |
| 响应头 | `Cache-Control: no-store`、`X-Content-Type-Options: nosniff`、`Referrer-Policy: no-referrer` |
| 凭据 | `sources.scrub()` 只按「凭据语境」字段名精确匹配换 `<redacted>`（`accessToken` / `refreshToken` / `cookie` / `api_key` / `authorization` / `secret` / `password` 等），`SECRET_VALUE` 正则脱敏 `sk-` / `Bearer` 值形状；**裸 `token` 不算凭据** —— `total_tokens` / `prompt_tokens` / `completion_tokens` / `cache_hit_tokens` 是业务计量，必须保留（见 [PITFALLS.md](PITFALLS.md) §51）；`provider_config.json` 只出存在性与键名；`auths/*.json` 只出条数、昵称与掩码 ID |
| 掩码 | 账号 ID / UID 前 4 后 2（`work…96`）；日志行裁到 240 字符 |
| 写操作 | 只有 `reload`；前端二次确认弹窗；**绝不自动重启 zgate** |
| 不做 | 不代理 WB `panel/api`、不提供配置编辑、不在前端拼 shell 命令、不读 `credentials.json` 的值 |

---

## 10. 目录与启动

```text
tools/console/
  server.py                # HTTP 服务 + 静态/API 路由 + 统一响应包（stdlib）
  sources.py               # 13 个数据源适配器 + TTL 缓存 + 流式尾读 + scrub
  actions.py               # reload 透传 + 互斥 + 20 条动作历史
  start-console.ps1        # -Port / -Check / -Detach（隐藏窗口）
  static/
    index.html             # Tabler 竖向骨架（4,328 B）
    app.css                # Fluent 2 令牌 + --tblr-* 桥接 + 专有类（10,717 B）
    app.js                 # 8 页 hash 路由 + 拉数 + Tabler 渲染（26,524 B）
    favicon.svg            # 内联 SVG（247 B）
    vendor/
      tabler.min.css       # Tabler 1.7.4 单 CSS，本地离线（686,736 B）
      LICENSE-tabler.txt   # MIT 许可证全文（1,247 B）
```

网关地址可用 `MODELBUS_GATEWAY` 覆盖（默认 `http://127.0.0.1:7871`）；端口用 `--port` 覆盖。`--check` 逐源读一遍 + 分别打印「手写静态资产」（去重、≤200 KB）与「vendor 静态资产」（Tabler，单独计）体积 + 探测网关 `/health`，**不监听端口**，任何源缺失按 `WARN` 不算失败。 `UPSTREAM_DOWN` 只记 `WARN` 是刻意口径：`--check` 验的是静态资产、路由与源适配器可解析，不因上游临时不可达把部署自检判死；运行态上游故障由 `/api/gateway` 返回 502、`app.js` 的 `all()` 单源隔离呈现，二者互不替代，故二次收尾不动这两处。

---

## 11. 分期与当前状态

| 期 | 范围 | 网关改动 | 状态 |
|---|---|---|---|
| **P0** | 总览 / 健康 / 日志 + 骨架与导航 | 无 | **已落地** |
| **P1** | 补齐模型 / 价格 / 流量 / 账号 / 运维（只读） | 无 | **已落地**，8 页全通 |
| **P2** | 写操作 `reload` + 互斥 + 动作历史 | 无 | **已落地**；跑门禁/探针/同步长任务未做 |
| **P3**（可选） | zgate 在 `Accept: text/html` 时 302 到后台；TTFB 分位、差集高亮、门禁缓存 | 约 10 行 + 一次换版 | **未做**（本轮网关零改动） |
| **v3 UI 重构** | 换 Tabler 1.7.4 官方骨架与组件类，Fluent 2 降级为令牌桥接层 | 无 | **已落地**（2026-11-12） |

---

## 12. 验收标准与实测结果

| # | 标准 | 实测 |
|---|---|---|
| 1 | 零加载型外链：静态资源不得触发任何外部请求 | 手写 4 文件 `https?://` 命中 **0**（`favicon.svg` 的 `http://www.w3.org/2000/svg` 是 SVG namespace）；`vendor/tabler.min.css` 的 25 个 `url()` 全是内联 `data:image/svg+xml`，`@import` / `fonts.googleapis` / `cdn.jsdelivr` / `unpkg.com` / `url(http` 命中 **0**；仅 `/*!` 注释头留 `https://tabler.io` 与 MIT LICENSE 两个不产生请求的字面量。E2E 新增 `VENDOR offline CSS` 断言锁住 |
| 2 | 零依赖：只用标准库 | `server.py` / `sources.py` / `actions.py` 无第三方 import；`py_compile` exit 0 |
| 3 | 手写静态资产 ≤ 200 KB；vendor 单独计 | `--check` 分别打印：手写 **41,816 B**（去重后；v2 为 41,649 B）、vendor **686,736 B**（Tabler 1.7.4，离线单 CSS）。v2 修正过 `/` 与 `/index.html` 别名双计 44,105 B 的老问题；v3 把 vendor 从手写预算里拆出，避免 686 KB 误判 FAIL；缺 vendor 文件直接 FAIL |
| 4 | 路由全通 + 缓存 | 端到端 **39 项 PASS**：21 GET 全 200（新增 `/vendor/tabler.min.css`）、4 HEAD 全 200 且 body=0 B（新增 vendor）、6 项安全断言、7 项脱敏断言、1 项 vendor 离线断言；`--check` 13 个 `/api/*` 全 OK；5s TTL 缓存合并 `/health` 轮询；侧栏浏览器 8 页 hash 逐页渲染 `fail=false`（总览 8 导航 / 10 卡 / 2 表，两张本地样式表全加载、零横向滚动） |
| 5 | 不碰网关：实现里没有 `zgate.exe` 启停调用 | `actions.py` 只发 `POST /admin/reload`；网关 7871 全程在跑且响应未改 |
| 6 | 门禁 | `check-project.py` exit 0；`check-docs.py` 范围模式（5 篇：本正本 / README / PITFALLS / TOOLS / MAINTENANCE）exit 0；`py_compile`、`node --check static/app.js` exit 0；`server.py --check` exit 0（`handwritten static bytes = 41816` / `vendor static bytes = 686736` / `result = PASS (0 failure(s))`）。全仓 `check-docs.py` exit 1 只因用户既有未跟踪 `docs/reports/MODEL-SYNC-20261112-1209.md` 被 `docs/reports/README.md:7` 链接（HEAD 无该链接、`git ls-files` 无目标），与本轮改动无关 |
| 7 | `/health` 契约不变 | 仍 `application/json; charset=utf-8`、约 2.7 KB（`uptime_s` 等动态字段位数增长会使体积浮动，本轮实测 2,741 B）、7 个渠道段齐全、`key` 只露 bool；A 路分片 `evidence/agent-endpoints.md` 复现 18 个顶层键 |
| 8 | 脱敏：strict 口径 + shapes 口径 | `/api/config`、`/api/accounts` 对凭据字段名零命中；`/api/gateway`、`/api/overview`、`/api/traffic`、`/api/probe` 与 `static/app.js` 对凭据值形状（`sk-` / `Bearer`）和凭据字段名双零命中；脱敏单测 13 项 PASS 同时锁「凭据被抹」与「`*_tokens` 计量保留」 |
| 9 | 跨站与写面 | 无 `Origin` POST 403、跨站 `Origin` 403、同源 `Origin` 200、`Host: evil.example` 403、未知路由 404、`GET /api/actions/reload` 404；`HEAD` 不写 body |
| 10 | Tabler 外壳 + Fluent 2 桥接 | `index.html` 用官方竖向骨架与 `.page` / `.navbar-vertical` / `.page-wrapper` / `.page-header` / `.page-body` / `.footer`；`app.css` 194 行只做 `--tblr-*: var(--mb-*)` 映射与专有类；`app.js` 8 个 render 函数主体未动、只换 helper 输出 Tabler 类；`setTheme()` 同步 `data-theme` + `data-bs-theme`；`#nav-toggle` 原生切 `.collapse.show`，零 Bootstrap JS；MIT 全文随 `vendor/LICENSE-tabler.txt` 落盘 |
| 11 | 降级路径结构化（2026-11-12 二次收尾） | 修三处只读后台的降级缺陷：`static/app.js:356` 状态灯改按 `env.ok === true && !env.__err` 判定（健康页 `/api/gateway` 502 显「网关不可达」、总览页成功不再恒显不可达）；`server.py:185-186` `do_POST` 补 `except Exception` 兜底为 `err_envelope("PARSE_ERROR", ...)` 结构化 500，不再返回裸 HTML；`start-console.ps1:27` 启动提示补上 stderr 访问日志路径。两个运行时探针 `.work/probe-gateway-dot.cjs` 5 例行为矩阵全 PASS、`.work/probe-post-json.py` 断言 500 + JSON 全 PASS；修复后 `server.py --check` 0 failure、39 项 E2E 重跑仍全绿；侧栏浏览器真渲染复验总览 `gwText="网关在线"` / `gwDotClass="status-dot status-green"`（旧逻辑恒显「网关不可达」）、8 页 hash 逐页 `err=false`，两张本地样式表全加载、零横向滚动 |

---

## 13. 资源占用审查（只读，不自动清理）

全仓审查（C 路 `evidence/agent-audit.md` 419 行 / 37,908 B / SHA256 `0BF7ED72…878D`，主线按下节命令独立复现）发现 7 类占用候选，全部在 `/api/ops` 与运维页列出**体积与处置建议**，后台不删任何文件：

| 候选 | 实测（2026-11-12 16:27–16:37 采样，长驻网关持续写盘） | 性质 | 建议 |
|---|---|---|---|
| `gateways/zgate/zgate.exe.bak-*` 换版备份 | 6 份 64,514,048 B（单份 10,695,680–10,816,512 B）；`.work/` 另有 2 份候选 exe 18,111,488 B | 受控换版回滚链（`docs/ZGATE-LIFECYCLE.md`） | 保留最近 2 份，其余移出仓或加 `.git/info/exclude`；删前需用户确认，本轮不动 |
| `request-logs/requests-*.jsonl` | 7 files / 27,688,206 B / 40,351 行，oldest 2026-11-05 23:59:55、newest 16:31:17 仍在写；单日最大 `requests-2026-11-10.jsonl` 6,734,059 B / 9,753 行 | 流水，`reqlog.go:356` 1s ticker，**grep 未找到 retention 实现** | 加保留窗口（如 7 天）；后台已改流式 tail 800 行，不再全量入内存；明细行只做聚合不展示 |
| `%LOCALAPPDATA%/ZCodeGateway/` 日志 | 60 files / 27,257,840 B；`zgate.log` 5 MB 轮转（`logx.go:30-34`），子进程 stdout/stderr 无轮转（`supervisor.go:241/245`），`workbuddy.stdout.log` 18,353,059 B 最大 | 活日志 | 子进程日志加轮转上限；后台只读尾 1 MiB |
| `gateways/upstream/workbuddy/data/` | 18 files / 29,240,509 B；`usage.json` 401,887 B + 等量 `.bak`，30s flush 全量重写（`usage.go:37/:129`）写放大约 2× | 活数据 + 双写备份 | 后台只读聚合；改写入策略等价未证，本轮不动 |
| `.work/` | 335 files / 24,133,519 B（复测；初测 333 / 23,963,775 B） | 中间产物 | 按 `AGENTS.md` 只进真实项目 `.work/`；定期微扫 |
| `~/.zcode/v2/provider_config.json.bak-*` | 49 份 / 849,378 B；另有 `model-alias-map.json.bak-*` 4 份 99,994 B、`wb_pricing.json.bak-*` 7 份 99,411 B | 本机真值备份（`copy2` 全量，含 `apiKey` 键），不得入库 | 保持 gitignored，勿 `git add -f` |
| `%SystemDrive%/` 字面量目录 | 5 文件 1,332,016 B | 历史反复由外部 `spawnSync` 把字面量当相对路径创建（`PROGRESS.md:2692/2739/2777` 已记），**仓内代码零引用** | 列入 ops 只读候选；需用户确认后再清，本轮不动 |

> 主线 17:11 独立复现（只读 `Get-ChildItem -Recurse | Measure-Object -Sum`）：`zgate.exe.bak-*` 6 份 64,514,048 B、`provider_config.json.bak-*` 49 份 849,378 B、`%SystemDrive%/` 5 文件 1,332,016 B 三项与 C 路采样完全一致；`request-logs` 27,805,856 B、`%LOCALAPPDATA%/ZCodeGateway` 28,794,579 B、`.work/` 34,814,010 B 因活服务持续写入与本轮中间产物累加而高于 16:27–16:37 采样值，属正常增长，口径以各采样时刻为准。7871 仍由 zgate pid=17336 Listen、7872 空闲。

功能实现优化（已落地，行为等价）：

1. **服务端 TTL 缓存**合并 `/health` 轮询，避免多标签页把 `aliases.Reload()` 打成热点（C 路实测 `docs/CONSOLE.md` 口径：每次 `/health` 请求都触发 `aliases.Reload()` 重读 alias map，轮询必须 ≥ 5s）。
2. **流式尾读** `_tail_bytes()` / `tail_jsonl()` 只读文件尾部 1 MiB，27 MB 日志目录不再全量入内存。
3. **单源隔离** `Promise.allSettled`，一个数据源坏掉不影响其余 7 页。
4. **静态预算去重 + 分层**：`--check` 用文件名集合统计，`index.html` 两条路由别名不重复计数（v2 修正前 44,105 B → 修正后 41,649 B）；v3 再把手写资产（41,816 B，仍卡 200 KB）与本地 vendor（686,736 B，单独打印校验存在）拆开，避免引入 Tabler 后误判超预算。
5. **写面收紧**：`reload` 改同源 POST + 必带 `Origin`；`HEAD` 复用 `GET` 且不写 body。
6. **占用处置只读化**：`/api/ops` 只汇总体积与建议，不删任何文件；删除属不可逆且配置备份含凭据真值，全部留待用户拍板。
7. **状态灯三态判据收紧**（2026-11-12 二次收尾）：`all()` 对失败源写的是 truthy 的 `{ __err: ... }`，原 `bag["/api/gateway"] ? true : ...` 会把 502 错判「在线」、总览恒判「不可达」；改按响应包 `ok === true` 且无 `__err` 判在线，缺源保持「检测中」。
8. **写面异常结构化**：`do_POST` 只捕 `SourceError` 时，非预期异常会走裸 HTML 500、前端 `api()` 报「响应不是 JSON」；补通用兜底为统一 `err_envelope` JSON 包，`reload_gateway()` 自身已捕的 HTTP/URL/超时异常路径不变。
9. **启动日志提示补全**：`log_message` 写 `sys.stderr`，`-Detach` 提示原先只给 stdout 路径（打开只有一行启动语）；提示同时给出 `access-log stderr` 路径，不改进程模型、不加新参数。

### 13.1 已证行为等价的最小优化候选（登记，本轮不动核心同步链）

C 路给出两条**有行为等价证明**的候选，均落在既有核心同步脚本上。本轮边界是「构建后台 + 只读审查」，按仓规「不做顺手重构」不动 `sync-models.ps1` 与 `go_model_sync.py`，登记为单独批次候选，改时按下列矩阵复验：

| 候选 | 位置 | 等价证明（C 路实测） | 本轮处置 |
|---|---|---|---|
| C1 校验读改用 `with` | `providers/opencode-go/ops/go_model_sync.py:700` `json.load(open(tmp, encoding="utf-8"))` | Python 3.12：`C1_valid_equal=True`；invalid JSON 异常逐字相等（`JSONDecodeError \| Expecting property name enclosed in double quotes: line 1 column 2 (char 1)`）；`-W error::ResourceWarning` 下新写法不触发未关闭句柄告警 | 登记 P2，等价已证，单独批次 |
| C2 公共参数数组去重 | `sync-models.ps1:275-277` / `:316-318` `$scoreArgs` / `$checkArgs` | 数组拼接矩阵 `scoresOn∈{T,F}` × `probeArgs∈{0,2}` 共 4 组 `score_eq=True check_eq=True`；边界：`:321-325` 漂移分支 `$scoreArgs2` 未纳入，一并重构需扩矩阵 | 登记 P2，等价已证（限定范围），单独批次 |

证不出等价、明确**不建议本轮改**（C 路 §4）：删 6 份 `zgate.exe.bak-*`（回滚链不可逆）、给 request-logs 加 retention（会删审计证据）、`egress.go:65` 无上限 cache 加 LRU（改长连接复用时机）、5 处 backup 抽公共 helper（命名 / 时机 / 失败处理不一）、`sync-models.ps1:31` `ErrorActionPreference=Continue` 改 `Stop`（改同步成败与退出码）、删 49 份配置备份（含凭据真值）。

---

## 14. 风险与回退

| 风险 | 触发条件 | 处理 |
|---|---|---|
| 端口冲突 | 7872 被别人占了 | `--port` 参数；起不来时打印占用者 pid |
| `/health` 轮询压力 | 多标签页同时开 | 服务端 5s 缓存合并，前端总览 10s 单定时器 |
| 请求日志过大 | 日文件上万行 | 流式逐行聚合 + 15s 缓存；只读尾部 |
| SSE 长连接 | 日志页久开 | 30 帧 × 2s 上限，断开给文字提示，切页重连 |
| 误触写操作 | 点了重载网关 | 二次确认 + 结果 toast + 动作历史；失败保留原始报错 |
| 后台进程消失 | 关机 / 会话结束 | `start-console.ps1 -Detach`；服务无状态，重启无副作用 |

回退：删 `tools/console/` 一个目录即完全消失，不涉及网关与配置。

---

> 相关：`/health` 字段语义见 [ARCHITECTURE.md](ARCHITECTURE.md)，别名与链路见 [MODEL-ALIAS.md](MODEL-ALIAS.md)，文档规则见 [DOC-RULES.md](DOC-RULES.md)，凭据位置见 [SECRETS.md](SECRETS.md)。
