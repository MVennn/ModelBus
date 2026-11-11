# ModelBus 改名审计：zcode 耦合面盘点与风险分级

> 一句话结论：**能改的只有 6 个自有脚本文件名、1 个自造环境变量、DSH 侧 3 个 route id 和 36 篇文档的措辞；路径、ZCODE_* 变量、third-party 规则数据和 ZCode schema 键一个都不能动。** 改名与「包装」并行才是正解 —— 脚本换中性名，ZCode 语义下沉到 adapter 层。

---

## 0. 统计口径（全仓实测）

| 口径 | 文件数 | 命中次数 |
|---|---|---|
| 全仓扫描（排除 .git / node_modules / .work / .codegraph / 二进制） | 149 | 10211 |
| 其中 `gateways/upstream/workbuddy/data/request-logs/*.jsonl`（运行时日志，不是代码） | 4 | 7844 |
| 扣掉日志 + evidence/ + memories/ + PROGRESS/CHANGELOG + *.bak 后的「代码+文档」口径 | 90 | 1028（891 行） |

目录分布：`gateways` 24 文件/7896（96% 是日志，代码只 17 次）· `evidence` 36/892 · `docs` 28/502 · 仓库根 9/354 · `tools` 13/157 · `providers` 14/156 · `third-party` 9/112 · `memories` 9/106 · `tests` 4/28 · `.github` 2/7 · `assets` 1/1。
按类型（代码口径）：md 36 文件/594 次 · py 26/238 · js 4/77 · NOTICE 39 · json 3/24 · ps1 5/19 · go 8/17 · ts 3/9 · yml 2/7。

### top 20（代码口径，次数 / 命中行数）

| # | 文件 | 次数 | 行数 |
|---|---|---|---|
| 1 | docs/UPSTREAM.md | 75 | 56 |
| 2 | docs/TROUBLESHOOTING.md | 54 | 47 |
| 3 | tools/dsh_sync.py | 48 | 43 |
| 4 | docs/MODEL-PROVIDERS.md | 45 | 42 |
| 5 | docs/TOOLS.md | 45 | 28 |
| 6 | docs/MAINTENANCE.md | 42 | 39 |
| 7 | providers/workbuddy/zcode_effective_body.js | 42 | 38 |
| 8 | NOTICE | 39 | 39 |
| 9 | docs/ARCHITECTURE.md | 37 | 31 |
| 10 | docs/SECRETS.md | 36 | 24 |
| 11 | third-party/zcodium/reasoning-rules.js | 29 | 26 |
| 12 | docs/PITFALLS.md | 27 | 26 |
| 13 | providers/workbuddy/workbuddy_probe_zcode.py | 25 | 24 |
| 14 | docs/QODER.md | 24 | 23 |
| 15 | third-party/zcode/UPSTREAM.md | 24 | 17 |
| 16 | README.md | 22 | 17 |
| 17 | providers/workbuddy/workbuddy_zcode_sync.py | 21 | 18 |
| 18 | docs/CAPABILITY-AUDIT.md | 19 | 14 |
| 19 | providers/qoder/qoder_zcode_sync.py | 19 | 19 |
| 20 | third-party/zcodium/UPSTREAM.md | 18 | 14 |

日志口径另有 `request-logs/requests-2026-11-04.jsonl` 4786 次、`-11-03.jsonl` 2682 次 —— 属于 WorkBuddy 网关请求日志，**不在改名范围**。

---

## 2. 分类判定（逐类给结论）

| 类别 | 代表位置 | 判定 | 风险 |
|---|---|---|---|
| 外部契约：配置路径 | `~/.zcode/v2/provider_config.json`，45 个文件/135 处引用；写入口 `providers/workbuddy/workbuddy_zcode_sync.py:145-146`、`providers/qoder/qoder_zcode_sync.py:116-119`、`providers/qwen/qwen_zcode_sync.py:113-116`、`tools/model_alias.py:478-481`、`tools/dsh_sync.py:61-66`、`gateways/zgate/internal/config/config.go:237` | 不可改 | 高 |
| 外部契约：环境变量 | `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE`（20 文件）、`ZCODE_BUILTIN`（12 文件），`AGENTS.md:49-50` 已写死为契约 | 不可改 | 高 |
| 第三方原件 | `third-party/zcode/`（`.upstream-sha` / LICENSE / `zcode-builtin.json` / `schema.ts:2,36,44,78`）、`third-party/zcodium/` | 不可改、不可改名 | 高 |
| ZCode schema 键 | `providerConfigRules`/`providerRules`（24 处）、`modelConfigRules.providerModelRules`（30 处）、`modelApiRules`（17 处）、`providerOrder`（26 处）、`modelOrder`+`personalModelIds`（32 处）、`optionSpecs.reasoningLevel.{values,map}` | 必须保留（写进 ZCode 配置的键，客户端按键读） | 高 |
| 自有脚本名 | `workbuddy_zcode_sync.py` / `workbuddy_probe_zcode.py` / `zcode_effective_body.js` / `qoder_zcode_sync.py` / `qoder_probe_zcode.py` / `qwen_zcode_sync.py` | 可改（纯本仓自有命名） | 中 |
| 自有环境变量 | `WB_ZCODE_PROBE_FILE`（6 文件）、`ZCODE_API_TYPE` / `ZCODE_BASE_URL` / `ZCODE_MAX_OUTPUT_TOKENS`（仅 `zcode_effective_body.js:43-45,231-237`） | 可改，但保留旧名兼容读取 | 低 |
| DSH 侧 route id | `zcode-main` / `zcode-free` / `zcode-saver`（`tools/dsh_sync.py:74-78,318`；`tests/test_dsh_sync_retry_policy.py:39`；`tools/model_stream_check.py:140,517`） | 可改，但会动用户 `cordis.patch.yml`，建议走 adapter 映射 | 中 |
| 本地自造状态文件 | `~/.zcode/v2/{model-alias-map,arena-main,model-scores,quota-windows,model_probe,model-sync-state}.json`（`tools/model_alias.py:490,1936`、`tools/arena_leaderboard.py:54-56`、`tools/sync_report.py:34-35,66`） | 文件名可改，但 alias-map 被 zgate 热读，改要重启 zgate | 高 |
| 文档与命令入口 | docs 36 篇 594 次；`README.md:7-9,30`；`sync-models.ps1:228,253`；`.github/ISSUE_TEMPLATE/bug_report.yml:39-41,64-65` | 可改措辞，命令路径改则连带改脚本名 | 中 |

---

## 3. 可改名清单（逐项）

| 现名 | 建议新名 | 外部调用方是否读它 | 回归面 | 风险 |
|---|---|---|---|---|
| `providers/workbuddy/workbuddy_zcode_sync.py` | `providers/workbuddy/write_provider_tiers.py` | 否（ZCode 不读脚本名） | `sync-models.ps1:228`、26 个文件提及、docs/MODEL-PROVIDERS.md:7 处 | 中 |
| `providers/workbuddy/workbuddy_probe_zcode.py` | `.../workbuddy_probe_body.py` | 否 | 18 个文件提及、README.md:51、bug_report.yml:64 | 中 |
| `providers/workbuddy/zcode_effective_body.js` | `.../effective_body.js` | 否，但被 3 处代码按路径引 | `workbuddy_probe_zcode.py:75`、`tools/dsh_sync.py:60`、`tools/model_probe.py:45`、29 个文件提及 | 中 |
| `providers/qoder/qoder_zcode_sync.py` | `qoder_provider_tiers.py` | 否 | `sync-models.ps1:253`、22 个文件 | 中 |
| `providers/qoder/qoder_probe_zcode.py` | `qoder_probe_body.py` | 否 | 11 个文件、docs/QODER.md:5 处 | 中 |
| `providers/qwen/qwen_zcode_sync.py` | `qwen_provider_tiers.py` | 否 | 8 个文件、`qwen_pool_probe.py:140` 提示语 | 中 |
| `WB_ZCODE_PROBE_FILE` | `WB_PROBE_FILE`（旧名 fallback 读一版） | 否 | `workbuddy_probe_zcode.py:67`、`workbuddy_zcode_sync.py:152`、CONTRIBUTING.md、docs/SECRETS.md | 低 |
| `ZCODE_API_TYPE`/`ZCODE_BASE_URL`/`ZCODE_MAX_OUTPUT_TOKENS` | `EFFECTIVE_*`（保留旧名兼容） | 否 | `zcode_effective_body.js:43-45,231-237` + docs/SECRETS.md | 低 |
| `zcode_body()`（`workbuddy_probe_zcode.py:110`） | `effective_body()`（保留别名） | 否 | 24 行内注释、`:265-282` 调用点 | 低 |
| `_zcode_providers()`（`tools/dsh_sync.py:128`） | `_source_providers()` | 否 | 同文件 4 处调用 | 低 |
| DSH route id `zcode-*` | `agent-*`（**先加映射表再切**） | 否（DSH 读 patch，人写 patch 也读） | tests/test_dsh_sync_retry_policy.py:39,204-211；tools/model_stream_check.py:140,517；用户 `cordis.patch.yml` | 高 |
| 文档措辞（"把供应商接进 ZCode 客户端"） | "把模型目录投影给 ZCode 客户端与 DSH agent" | 不涉及 | 36 篇 docs + README + docs/README.md 索引 | 低 |
| `docs/ARCHITECTURE.md:27,52,212,316` 引用的 `workbuddy/zcode_gateway_watch.ps1` | 该文件已不存在（`providers/workbuddy/` 只剩 4 个文件）→ 换成 `zgate install` | 不涉及 | check-docs 不校验代码块路径，所以从未报红 | 低 |

---

## 4. 「包装而非改名」（更该保留 zcode 名字、加 agent 面向抽象的地方）

1. **`providers/workbuddy/zcode_effective_body.js`**：它复刻的是**ZCode 客户端的请求体语义**（`:3-14`），改名会掩盖事实。保留文件名，在 Python 侧只暴露中性入口 —— `workbuddy_probe_zcode.py:110` 的 `zcode_body()` 已是唯一调用面，加 `effective_body = zcode_body` 别名即可换口径。
2. **`tools/dsh_sync.py` 的 `KNOWN_PROVIDER_IDS`（:74-78）**：这是整条链唯一的"ZCode provider → DSH route"映射表。把取值搬到 `adapter.route_id()` 函数里（返回值暂仍 `zcode-*`），未来切 `agent-*` 只改一处；测试常量 `tests/test_dsh_sync_retry_policy.py:39` 同步一处。
3. **`tools/dsh_sync.py` 本身就是现成 adapter（:2-18）**：docstring 说得很清楚「Project ZCode's final model groups into DeepSeekRuntime's llm-pi-ai profile」。建议在文档里正式命名为 `zcode → llm-pi-ai adapter`，代码零改动，口径立刻变成 agent 面向。
4. **三个 `*_zcode_sync.py` 的写入段**（`workbuddy_zcode_sync.py:364-371`、`qoder_zcode_sync.py:191-199`、`qwen_zcode_sync.py:345-352`）语义重复：建议抽 `providers/_sink/zcode_provider_config.py`，脚本名保留、写入逻辑单点；将来加 DSH sink 时平级新增而不是复制粘贴。
5. **`gateways/legacy-router/unified-router.js:62-63,193` 与 `gateways/zgate/internal/alias/alias.go:1-4`**：读的是 `~/.zcode/v2/*.json`，属于"网关读客户端配置"的既有事实，保留 zcode 名字 + 在 README 里标注为 "ZCode config reader" 即可。
6. **`workbuddy_fetch_pricing.py:12,17,26` 对 `workbuddy_zcode_sync.py` 的引用**：把注释里的脚本名换成"同步脚本"，不绑定文件名，脚本改名时这里零改动。

---

## 5. 不能碰清单（动了就让 ZCode 客户端或第三方失效）

1. `~/.zcode/v2/provider_config.json` 的**目录与文件名**（客户端按此路径读；覆盖 `tools/model_alias.py`、`tools/dsh_sync.py`、`tools/model_probe.py`、`tools/sync_report.py`、三个 `*_zcode_sync.py`、`gateways/zgate/internal/config/config.go:237`、`gateways/legacy-router/unified-router.js:62-63`）。
2. `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` / `ZCODE_BUILTIN` 两个变量名（`AGENTS.md:49-50` 契约；`third-party/zcodium/reasoning-rules.js` 的漂移检查也读 `ZCODE_BUILTIN`）。
3. `third-party/zcode/` 整目录（7 文件，含 `.upstream-sha` 钉的 commit、LICENSE、`zcode-builtin.json`、3 个 `.ts` 原样源码；`third-party/README.md:12` 明写"原样，未改一个字节"）与 `third-party/zcodium/`（2 文件）。
4. 写进 provider_config.json 的**全部键名**：`providerConfigRules`/`providerRules`、`modelConfigRules.providerModelRules`、`modelConfigRules.modelApiRules`、`personalModelIds`、`modelOrder`、`providerOrder`、`optionSpecs.reasoningLevel.values`/`.map`、`config.access.apiKey`。
5. `~/.zcode/v2/model-alias-map.json`（`gateways/zgate/internal/alias/alias.go:1-4` 按 mtime 热加载；改名要重启 zgate —— 本任务禁止）。
6. `gateways/zgate/zgate.json:3-4,70` 与 `internal/config/config.go:231,237,312` 里的 aliasMap / providerConfig / `%LOCALAPPDATA%\ZCodeGateway` 日志目录（编译进常驻进程）。
7. `NOTICE:5-6`（`zcode-ai-models` copyright 行）、`NOTICE:64-77`、`NOTICE:318` 商标段与 Apache-2.0 归属说明 —— 法务文本，改名会破坏许可链条。
8. `tests/test_dsh_sync_retry_policy.py:109` 的 `ZCODE_GATEWAY_KEY` fixture 与 `tools/dsh_sync.py:69,482-495` 写进用户 profile 的 `refs.ZCODE_GATEWAY_KEY`（改则用户 DSH 凭据引用断，需迁移脚本）。
9. Windows 自启动项 `ZcodeAIModels-zgate-cutover` / `zgate.lnk`（`~/.dsh/AGENTS.md` §10 保留清单）—— 仓外但改名会断自启。

---

## 6. 落地顺序（结论）

**第一步（低风险、立即可做）**：docs 措辞 + `docs/ARCHITECTURE.md` 死链清理 + `WB_ZCODE_PROBE_FILE` 与 3 个 `ZCODE_*` 自造变量的兼容改名。
**第二步（中风险、需一次全仓同步）**：6 个脚本文件名 + 对应 3 处硬编码路径（`dsh_sync.py:60`、`model_probe.py:45`、`workbuddy_probe_zcode.py:75`）+ `sync-models.ps1:228,253` + 26/18/22/11/8 处文档命令，一次性提交并跑 `check-docs`。
**第三步（高风险、需迁移）**：DSH route id 与 `ZCODE_GATEWAY_KEY` —— 先加 adapter 映射与人写 patch 的兼容读，再切默认值，且必须避开 zgate 在线时段（alias-map 相关一律不动）。
**永远不做**：第 5 节清单全部。
