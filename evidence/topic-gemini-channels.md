# Gemini / CLIProxyAPI 渠道实测（结论卡）

> **一句话**：Gemini 这条线走过的两条路（本地 CLIProxyAPI 中转 vs 远程 GM 直连）与各自的能力边界；现行口径正本是 [docs/MODEL-PROVIDERS.md](../docs/MODEL-PROVIDERS.md) §4.11。

## 1. 现行：远程 GM 直连（正本 §4.11，这里只留「为什么」）

- 网关 `https://catiecli.sukaka.top/v1`，`GET /v1/models` 自取目录（2026-11-10 返回 7 个 `ais-gemini-*` id）。`Gemini-AIS` = `ais-gemini-3.8-flash` 领头的同站降级链，2026-11-11 11:03 起只留 3 跳（3.8 → 3.7 → 3.6），后四跳记 `dropped_hops`、仍留在 `legacy_ids`。
- 渠道 `GM` 远程直连无本地子进程；`Authorization: Bearer` 必须由 zgate `applyHeaders` 覆盖注入，透传空 Bearer 上游回 401 `未提供API Key`。
- 价：无公开价目，`tools/model_alias.py` 的 `GM_PRICES` 显式登记 `0.11`；未登记的 id 返回 `None` → 当死链丢弃，**新增型号必须先补价**。
- 思考参数**未定论**：3.8 / 3.7 常态 503 拿不到稳定样本；3.6 上 `{"thinking":{"type":"disabled"}}` 首字 2.27s（对照 `reasoning_effort:minimal` 12.67s），样本不足，暂不配 `optionSpecs.reasoningLevel`。
- GM 是仅有的两个开 `channelPolicy` 的渠道之一（另一个 HJ 哈基米，2026-11-11 整族下线）—— 竞速、静默冷却、403 暂停只对这两个生效。
- 原证据：agent-gemini-truth.md、agent-gemini-thinking-proof.md、agent-gemini-ais-alias.md、agent-gemini-merge-plan.md。

## 2. 已弃：本地 CLIProxyAPI 中转（CP）

| 结论 | 原证据 |
|---|---|
| 版本 v8.0.61，2026-11-09 11:38–11:50 落地；**只有 5 类 Gemini 渠道**，不存在「复用网页端 cookie」的渠道 —— 靠网页登录态白嫖这条路走不通 | agent-cliproxyapi.md、agent-gemini-channels-local.md、agent-gemini-channels-web.md |
| AI Studio 免费层限额 **20 次/天**；antigravity OAuth 被上游回 `403 VALIDATION_REQUIRED` | agent-gemini-channels-web.md |
| CP 凭据已从 zgate 侧移除（`main.go` / `config.go` / `keys.go` / `router.go` 去 CP 凭据、`/health` 第六段与测试段名；`go build` / `go test` / `go vet` / `gofmt` 全绿） | agent-gemini-go-cleanup.md（CHANGELOG:216） |

## 3. 迁移面（一次性统计）

| 结论 | 原证据 |
|---|---|
| 从 CP 切到 GM 时硬引用 204 行 / 38 文件，但**真正决定 provider 是否存在只有 9 处** | agent-gemini-merge-plan.md |
| 记忆层要动 10 处；5 篇 CP/Gemini 专述 Document 已归档、`index.json` 44 条逐条 hash / sizeBytes 复核 | agent-gemini38-memory.md、agent-gemini-memory-cleanup.md（CHANGELOG:218） |
| docs 侧要改两处：`docs/MODEL-PROVIDERS.md` §4.11 与 `docs/MODEL-ALIAS.md` 的链序段（L326-338 / L348），已改 | agent-gemini-memory-docs.md |
| gemini 3.8 渠道配置项盘点、provider 落点定位、docs 侧表述清理清单均已并入 §4.11 | agent-gemini38-config.md、agent-gemini-provider-locate.md、agent-gemini-docs-cleanup.md、agent-gemini-code.md、agent-gemini-runtime.md、gemini-merge-result.md |

## 4. 未解决

- 3.8 / 3.7 常态 503，思考参数拿不到稳定样本 → `optionSpecs` 保持空；要补必须挑低峰时段重测（agent-gemini-thinking-proof.md）。
- 首字极慢的日志实证已并入 [docs/TROUBLESHOOTING.md](../docs/TROUBLESHOOTING.md) §18 的排障链，未新增独立结论（agent-gemini-logs.md）。
