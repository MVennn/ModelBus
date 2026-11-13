# evidence/ —— 证据快照与结论卡

> **一句话**：本目录只留两类东西 —— 值得入库的**结论卡**与**代表性快照**；一次性 agent 调研报告的正文不再堆积，结论一行登记在下面的台账里。

## 现役文件

| 文件 | 类型 | 说明 |
|---|---|---|
| `topic-routing-runtime.md` | 结论卡 | 执行链、端点面、控制台、运行态快照、499 / 排序 / 加密思考等未吸收项 |
| `topic-capability-fields.md` | 结论卡 | `contextWindow` / `maxOutputTokens` / `optionSpecs` / `reasoningEffort` 的来源与缺口 |
| `topic-debrand-scope.md` | 结论卡 | 去 ZCode 化的契约层边界、可动面、普查数字 |
| `topic-gemini-channels.md` | 结论卡 | GM 直连与本地 CLIProxyAPI 两条路的实测边界 |
| `topic-sync-ops.md` | 结论卡 | 自动收录链、三次探活验收、仓库级盘点数字 |
| `go-model-sync-20261113-120007.md` | 快照 | 最新一份自动收录决策报告（历史各版按 `docs/MAINTENANCE.md` §3 只留最近一版） |
| `PROGRESS.workbuddy.md` | 台账 | WorkBuddy 接入线历史台账，[docs/DOC-RULES.md](../docs/DOC-RULES.md) §2 定为**只读** |
| `wb_panel_models.json` | 数据 | 网关模型目录快照，`docs/MAINTENANCE.md` §3 定为随仓库分发 |
| `opencode-models-doc-snapshot.html` | 数据 | OpenCode 官方模型文档页面快照（第三方页面原件） |
| `gemini-prod-probe.json` | 数据 | Gemini 生产探测返回样例（357 B） |

> 命名口径：`topic-*.md` 是本仓 evidence 内的结论正本；再往里写新内容前先确认它是「结论」而不是「过程」。

## 整理记录（2026-11-13）

- 75 篇 md → 8 篇：5 张主题卡 + 本台账 + 1 份最新收录快照 + 只读的历史台账。
- 判定口径：结论已被 `docs/` 正本吸收 → 删并留指针；未吸收 → 进对应主题卡；纯过程细节（逐次探测、逐行日志、中间结论）不留。
- 同时删除 1 个被 `.git/info/exclude` 挡住的残留备份 `agent-effort-audit.md.bak-hy3xcause-20261110`。
- 恢复方式：入库文件 `git show HEAD:evidence/<文件名>`；被 `.git/info/exclude` 挡住的本地分片没有 git 历史，从 `%TEMP%\doc-audit\S2-removed\` 拷回。

## 台账（一行一篇，按主题分组）

### 路由与运行态（→ `topic-routing-runtime.md`）

| 原件 | 主题 | 结论一句话 | 去向 |
|---|---|---|---|
| agent-map-race.md | 路由 | 执行链 `routeChain → racePolicyFor → raceChain → attemptChain → doForwardWith → doForward`；冷却按物理跳两张表，对冲与首块参数只取链首渠道 | topic-routing-runtime.md §1 |
| agent-zgate.md | 路由 | 45s / 700ms 是 Go 常量；渠道优先级来自 alias map chain；workbuddy `soft_rate=600s` 对 6004 不生效 | topic-routing-runtime.md §1 |
| agent-mainline-merge.md | 路由 | 主力由 `tools/model_alias.py` 的 `MAIN_ORDER` 单源定义、投影三处；新 ais-gemini-3.8-flash 与旧 cp:gemini 无继承关系 | topic-routing-runtime.md §1 |
| agent-dsh-retry.md | 路由 | 三条 llm-pi-ai route 应写 retryPolicy；RATE_LIMIT 移出可重试集合、maxRetries 5→0/1；429 自动切模型无配置开关 | topic-routing-runtime.md §1 |
| agent-map-api.md | 端点 | `/v1/models` 与 `/health` 手写 dispatch，无 mux / struct / metrics / access log，提前交卷不可观测 | topic-routing-runtime.md §2 |
| agent-endpoints.md | 端点 | 7871 非代理端点恰三个：`GET /health`、`GET /v1/models`、`POST /admin/reload`；`/health` 恒 JSON | topic-routing-runtime.md §2 |
| agent-console-impl.md | 控制台 | tools/console 13 文件静态审查：独立 loopback 只读服务 + 唯一 reload 转发；3 个缺陷；自检门禁在网关不可达时假绿 | topic-routing-runtime.md §2 |
| agent-console-progress.md | 控制台 | PROGRESS 写 v2 完成而磁盘已到 v3（Tabler 外壳）；2026-11-09 19:11 实测 7872 `pid=31472`、`/healthz` 200 | topic-routing-runtime.md §2 |
| agent-console-verify.md | 控制台 | 3 个 `.py` 编译 rc=0、零 CDN 外链；`check-project.py` exit 0（8 项）；`check-docs.py` 当时 exit 1 | topic-routing-runtime.md §2 |
| agent-runtime.md | 运行态 | 2026-11-09：7871 HEAD `bfd6b9e`、22:24:36 编译 / 22:25:37 启动、Gemini-AIS 七跳、93 条目录；7872 未起 | topic-routing-runtime.md §3 |
| agent-gateway-lifecycle.md | 生命周期 | 网关生命周期逐行调研（2026-11-09T07:43，432 KB） | docs/ZGATE-LIFECYCLE.md 已吸收 |
| agent-code499.md | 排障 | 499 / CLIENT_DISCONNECTED 证据不足：无生成点、无 5.4s 计时来源、无请求 ID 关联 | topic-routing-runtime.md §4 |
| agent-doc499.md | 排障 | 2026-11-12 20:26:55 AIS 流式 499 的文档侧取证 | topic-routing-runtime.md §4 |
| agent-sort-rule.md | 排序 | 匿名置底规则在 `model_alias.py` 已改成 `(HY 前缀优先, price, new_id)`，初判对最终列表不生效 | topic-routing-runtime.md §4 |
| agent-iceman-stream.md | 流式 | Iceman 可流式也可看明文思考；不可控项是上游随机分流加密后端；L4 修复被 profile 偏好回退 | topic-routing-runtime.md §4 |
| agent-map-config.md | 配置 | channelPolicy 缺省不校验；`--check`/`--apply` 共用继承函数；其「ValidatePolicies 无调用点」已被 main.go:155 推翻 | topic-routing-runtime.md §4 |

### 能力字段与档位（→ `topic-capability-fields.md`）

| 原件 | 主题 | 结论一句话 | 去向 |
|---|---|---|---|
| agent-cap-dsh.md | 能力字段 | DSH 不读 provider_config.json 的 properties / optionSpecs；只被 `dsh_sync.py` 投影成 `cordis.patch.yml`，缺字段默认 1000000 / 128000 / `["text"]` | topic-capability-fields.md §1 |
| agent-cap-gen.md | 能力字段 | 20 条规则只有 WB 9 条带真实 properties；其余 11 条默认值由 ZCode builtin `.*` 兜底运行期补 | topic-capability-fields.md §1 |
| agent-cap-upstream.md | 能力字段 | OC/WB/QN 给能力字段，GM/HJ/QW/QD 不给；8 条有值留空、5 条 reasoningLevel 无来源、4 条与上游不一致 | topic-capability-fields.md §1 |
| agent-caps-truth.md | 能力字段 | 11 条缺 properties 只有 3 条可取证，8 条只能标 none；9 条已有 properties 中 6 条与 site rule 有出入；DeepSeek-4.1-Flash 现网 128000 / 真值 384000 | topic-capability-fields.md §1 |
| agent-effort-audit.md | 档位 | 19 模型只有 9 个搬了上游档位，10 个缺档；逐模型默认档一个没落地，缺口 8 项；HY3-X 误判已平反 | topic-capability-fields.md §2 |
| agent-thinking-adapt.md | 档位 | 新 gemini provider 是裸条目，未声明思考能力 | topic-capability-fields.md §2 |
| agent-gemini-truth.md | 能力字段 | GM 能力真值只有 `GET /v1beta/models`：contextWindow 1000000 / maxOutputTokens 65536；HJ 只能靠厂商文档 | topic-capability-fields.md §2 |

### 去 ZCode 化的范围（→ `topic-debrand-scope.md`）

| 原件 | 主题 | 结论一句话 | 去向 |
|---|---|---|---|
| agent-zcode-census.md | 去 ZCode | 2026-11-11 15:59:35 取样：命中 10425 处 / 293 文件，7148 处是上游署名 + 日志 + 历史保留 | topic-debrand-scope.md §1 |
| agent-code-review.md | 去 ZCode | 第一方源码 30 项 file:line：契约层 113 行勿动 + 实现层 129 行（96 必改 / 24 历史 / 9 可留） | topic-debrand-scope.md §1 |
| agent-dshfirst-docs.md | 去 ZCode | 38 篇 docs 中 29 篇带 ZCode 口径 487 行，真正会改坏的只有 6 类外部契约 | topic-debrand-scope.md §1 |
| agent-dshfirst-naming.md | 去 ZCode | 可改的只有 6 个脚本名、1 个环境变量、3 个 route id、36 篇文档措辞 | topic-debrand-scope.md §2 |
| agent-rename-code.md | 去 ZCode | 6 脚本改名后旧名 0 残留；9 个 `.py` py_compile EXIT=0；1 个 `.js` node --check EXIT=0 | topic-debrand-scope.md §2 |
| agent-docs-sync.md | 去 ZCode | docs 顶层 22 篇改成 DSH 主宿主口径、6 个改名脚本同步、三道门禁两轮全绿 | topic-debrand-scope.md §2 |
| agent-docs-review.md | 去 ZCode | docs 仍以 ZCode 为中心（463 / 118 行，根 README 17 / 0），三层改法 | topic-debrand-scope.md §2 |
| agent-dshfirst-dsh.md | 架构 | DSH 里 agent/preset/session/goal/subagent 都是一等公民；ModelBus 应做成 provider 插件 + 本地控制端点 | docs/DSH-FIRST.md 已吸收 + topic-debrand-scope.md §3 |
| agent-functional-review.md | 架构 | 现役链路 provider_config.json → dsh_sync.py 投影；实现层 123 行 ZCode（37 契约 / 86 待迁移）；Go 侧 X-Agent-Id 分桶零实现 | topic-debrand-scope.md §3 §4 |
| agent-replacement-plan.md | 架构 | 契约层零改动 + 实现层中性化的迁移方案 | topic-debrand-scope.md §3 |

### Gemini / CLIProxyAPI（→ `topic-gemini-channels.md`）

| 原件 | 主题 | 结论一句话 | 去向 |
|---|---|---|---|
| agent-cliproxyapi.md | Gemini | CLIProxyAPI v8.0.61 本地网关落地记录（2026-11-09 11:38–11:50） | topic-gemini-channels.md §2 |
| agent-gemini-channels-local.md | Gemini | CP 8.0.61 只有 5 类 Gemini 渠道 | topic-gemini-channels.md §2 |
| agent-gemini-channels-web.md | Gemini | 不存在网页端 cookie 复用；AI Studio 免费层 20 次/天；antigravity OAuth 403 VALIDATION_REQUIRED | topic-gemini-channels.md §2 |
| agent-gemini-go-cleanup.md | Gemini | Go 侧去 CP 凭据 + `/health` 第六段，build/test/vet/gofmt 全绿 | CHANGELOG:216 + topic-gemini-channels.md §2 |
| agent-gemini-ais-alias.md | Gemini | GM 7 个 Flash 合成 Gemini-AIS 7 跳链、HOP_PRIORITY 压序、`--check` 退出码 1、单测 59 项全绿 | docs/MODEL-PROVIDERS.md §4.11（后收窄 3 跳） |
| agent-gemini-thinking-proof.md | Gemini | 3.8 Flash 思考能力待补，拿不到稳定样本 | topic-gemini-channels.md §4 |
| agent-gemini-merge-plan.md | Gemini | 硬引用 204 行 / 38 文件，真正决定存在性只有 9 处 | topic-gemini-channels.md §3 |
| agent-gemini-memory-docs.md | Gemini | docs §4.11 与 MODEL-ALIAS 链序段（L326-338 / L348）须改写 | topic-gemini-channels.md §3 |
| agent-gemini38-memory.md | Gemini | 记忆层 10 处要动 | topic-gemini-channels.md §3 |
| agent-gemini-memory-cleanup.md | Gemini | 5 篇 CP/Gemini Document 归档 + index.json 44 条 hash/sizeBytes 复核 | CHANGELOG:218 + topic-gemini-channels.md §3 |
| agent-gemini-logs.md | Gemini | 首字极慢的逐跳日志实证 | docs/TROUBLESHOOTING.md §18 已吸收 |
| agent-gemini-code.md | Gemini | CP 相关代码改动记录 | topic-gemini-channels.md §3 |
| agent-gemini-runtime.md | Gemini | 运行时对照（渠道 / 凭据 / alias） | topic-gemini-channels.md §3 |
| agent-gemini38-config.md | Gemini | gemini 3.8 渠道配置项盘点 | topic-gemini-channels.md §3 |
| agent-gemini-provider-locate.md | Gemini | gemini provider 落点定位 | topic-gemini-channels.md §3 |
| agent-gemini-docs-cleanup.md | Gemini | docs 侧 Gemini 表述清理清单 | topic-gemini-channels.md §3 |
| gemini-merge-result.md | Gemini | 2026-11-10 主代理合并落地记录 | topic-gemini-channels.md §3 |

### 同步链、探活与运维（→ `topic-sync-ops.md`）

| 原件 | 主题 | 结论一句话 | 去向 |
|---|---|---|---|
| agent-sync-scheduler.md | 同步 | 每日 12:00 计划任务；2026-11-05 未到点、零产物（任务没跑≠链坏） | topic-sync-ops.md §1 |
| agent-sync-logs.md | 同步 | 每日同步执行前后的日志取样 | topic-sync-ops.md §1 |
| agent-sync-audit-20261111.md | 同步 | 报障 `pi-ai provider "zcode-main" has no configured model "Gemini-AIS"` = 投影后的 cordis.patch.yml 缺模型 | topic-sync-ops.md §1 |
| agent-model-alias-hardening.md | 同步 | 429 优化固化进生成器，不再手工改生成结果 | topic-sync-ops.md §1 |
| agent-detect-cost.md | 探活 | 省掉零收益的骤降探活验收（m01007） | topic-sync-ops.md §2 |
| agent-detect-quality.md | 探活 | 零请求时复用上次探测信号的验收 | topic-sync-ops.md §2 |
| agent-admission-price.md | 收录 | 收录价格口径正规化验收（m01046 / m01047） | topic-sync-ops.md §2 |
| agent-audit.md | 运维 | 1153 文本文件 / 45,225,871 B；`zgate.exe.bak-*` 64,514,048 B；请求日志 7 天 27,688,206 B / 40,351 行无 retention；`.bak-*` 49 份 849,378 B；P0=0 / P1=6 / P2=8 | topic-sync-ops.md §3 |
| agent-git.md | 运维 | 2026-11-10 17 个 commit / 70 去重文件 / +14391 −2612 | topic-sync-ops.md §3 |
| agent-adaptation.md | 评估 | 反代 / 模型提供商适配性评估终稿（真实项目根 `F:\Project\ModelBus`，junction 不是项目身份） | topic-sync-ops.md §3 |
| agent-aggregation.md | 评估 | 聚合性评估分片终稿 | topic-sync-ops.md §3 |
| agent-automation.md | 评估 | 自动性边界：哪一步脚本自动、哪一步必须人拍板 | topic-sync-ops.md §3 |
| agent-reasoning-history.md | 展示 | 网关与流式两条线已闭环；档位 4 空档 + 1 副作用；展示层悬空；`reasoningGuard.mode` 被并行会话改回 models | topic-sync-ops.md §3 §4 |
| agent-dsh-order.md | 快照 | 2026-11-05 22:29 DSH 模型下拉生效顺序只读盘点 | topic-routing-runtime.md §3 |
| agent-dsh-sync-hardening.md | 快照 | `.codegraph/` 存在但 `codegraph_status` 报 `unable to open database file`，当轮退回 grep | topic-routing-runtime.md §3 |
| DSH-REVIEW-SUMMARY-2026-11-11.md | 汇总 | 7 路审查汇总（过程汇总，结论已进各主题卡） | 各主题卡 |
| go-model-sync-20261106-120006.md<br>go-model-sync-20261106-232822.md<br>go-model-sync-20261109-120007.md<br>go-model-sync-20261110-120007.md<br>go-model-sync-20261111-120008.md<br>go-model-sync-20261111-133607.md<br>go-model-sync-20261112-120012.md | 快照 | 同一脚本的 7 份历史收录决策报告（实时 /models 30、Go 文档 31、定价 32、全量 93、已过弃用 21、控制台 32、已配置 18、待评估 24） | 只留最新 `go-model-sync-20261113-120007.md`（docs/MAINTENANCE.md §3 保留策略：一次性报告只留最近一版） |
