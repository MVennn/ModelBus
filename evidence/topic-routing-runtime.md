# 网关执行链与运行态（结论卡）

> **一句话**：zgate 的执行链形状、端点面、控制台与几次本机运行态快照；docs 正本已覆盖的只留指针，docs 没覆盖的结论留在这里。

> 2026-11-13 由 16 篇一次性调研报告归并；原件正文见 git 历史或 `%TEMP%\doc-audit\S2-removed\`。

## 1. 执行链与路由（正本 [docs/ROUTING-POLICY.md](../docs/ROUTING-POLICY.md)）

| 结论 | 原证据 |
|---|---|
| 执行链 `routeChain → racePolicyFor → raceChain → attemptChain → doForwardWith → doForward` | agent-map-race.md |
| 冷却按**物理跳**维护两张表；对冲与首块参数只取**链首**渠道的参数 | agent-map-race.md |
| 45s / 700ms 是 Go 常量（不是配置项），改超时要改代码换版 | agent-zgate.md |
| 渠道优先级来自 alias map 的 chain 顺序，不是 `zgate.json` 里的数组顺序 | agent-zgate.md |
| workbuddy 的 `soft_rate=600s` 对 6004（上游限流）不生效 —— 6004 走冷却表，不走软限流 | agent-zgate.md |
| 主力组由 `tools/model_alias.py` 的 `MAIN_ORDER` 单源定义，投影到三处配置 | agent-mainline-merge.md（正本 [docs/MODEL-ALIAS.md](../docs/MODEL-ALIAS.md)） |
| 新 `ais-gemini-3.8-flash` 是独立直连 provider，与旧 `cp:gemini` 无继承关系 | agent-mainline-merge.md |
| retryPolicy：三条 llm-pi-ai route 可写 `retryPolicy`；`RATE_LIMIT` 应移出可重试集合、`maxRetries` 由 5 降到 0/1；429 自动切模型**没有配置开关**（写在 `tools/dsh_sync.py` 的生成逻辑里） | agent-dsh-retry.md（正本 [docs/TROUBLESHOOTING.md](../docs/TROUBLESHOOTING.md)） |

## 2. 端点面与控制台（正本 [docs/CONSOLE.md](../docs/CONSOLE.md)）

| 结论 | 原证据 |
|---|---|
| 7871 的非代理端点恰好三个：`GET /health`、`GET /v1/models`、`POST /admin/reload`；`/health` 恒返回 JSON，改成 HTML 会同时打断所有消费方 | agent-endpoints.md |
| `/v1/models` 与 `/health` 是手写 dispatch：无 mux、无 route struct、无 metrics、无 access log → 「提前交卷」这类行为在网关侧不可观测 | agent-map-api.md |
| 7872 控制台 = 独立 loopback 只读服务 + 唯一一个 reload 转发；静态审查 13 个文件发现 3 处缺陷；它的自检门禁在网关不可达时会**假绿** | agent-console-impl.md |
| 控制台进度与磁盘漂移：`PROGRESS.md` 写 v2 完成（36 项 PASS / 41649 B），磁盘已是 v3（Tabler 外壳）；2026-11-09 19:11 实测 7872 `pid=31472`、`/healthz` 200 | agent-console-progress.md |
| 控制台验收：3 个 `.py` 编译 rc=0、零 CDN 外链、`check-project.py` exit 0（8 项）；`check-docs.py` 当时 exit 1（1 条未跟踪链接目标） | agent-console-verify.md |

## 3. 运行态快照（时点数据，读前先核对现网）

- 2026-11-09 22:2x：7871 跑 HEAD `bfd6b9e`，二进制 22:24:36 编译、进程 22:25:37 启动；Gemini-AIS 七跳在跑；alias 目录 93 条；**7872 控制台未起**（agent-runtime.md）。
- 2026-11-05 22:29：DSH 模型下拉生效顺序只读盘点（agent-dsh-order.md）。
- `.codegraph/` 存在但 `codegraph_status` 报 `unable to open database file`，当轮退回 grep（agent-dsh-sync-hardening.md）。

## 4. 未吸收 / 待补（docs 里没有正本）

- **499 / CLIENT_DISCONNECTED 未定因**：`gateways/zgate/*.go` 无 499 命中（2026-11-13 复核），本地只证明流式断开时静默 `return`、不产出 499；缺生成点、缺 5.4s 计时来源、缺请求 ID 关联（agent-code499.md、agent-doc499.md）。
- **匿名置底规则不生效**：`tools/model_alias.py` 已改成 `(HY 前缀优先, price, new_id)` 排序，初判该规则对最终列表不起作用；docs 侧「置底」0 命中、只有「匿名」2 处（agent-sort-rule.md）。
- **加密思考不可控**：Iceman 上游会随机分流到加密后端，同一模型时好时坏；L4 展示层修好后被 profile 偏好改回 `compact/completion/final`（agent-iceman-stream.md，偏好规则见 AGENTS.md §16）。
- **channelPolicy 缺省不校验**：不填 `channelPolicy` 时 `ValidatePolicies` 不报错；`model_alias.py` 的 `--check` 与 `--apply` 共用同一继承函数，改继承逻辑会同时影响两者（agent-map-config.md）。
- **已推翻的旧结论（不要再引用）**：agent-map-config.md 称「`ValidatePolicies` 已实现但无调用点」，与 `gateways/zgate/main.go:155` 的 `for _, note := range router.ValidatePolicies(cfg, am)` 不符 —— 现在有调用。
