# 推理档位（reasoning effort）落地审计

> 一句话结论：**没有按上游完整落地** —— 19 个 ZCode 模型里只有 **9 个**（订正后）把上游声明的档位搬进 DSH 模型表，**10 个缺档**（5 个是生成器回退分支整块丢失、可用重跑修掉；5 个在 ZCode 源头就只剩「开/关」二态或被 `map:{}` 丢弃），另 **1 个**（HY3-X）当时误判为「上游已下架」，2026-11-10 复查为 **判据选错导致的错判，实际档位与上游一致**（panel 目录结构性不含它，原因见 §3 第 8 项）；逐模型默认档**一个都没落地**（只有全局 `reasoningEffort: high`）。缺口合计 **8 项**。

---

## 1. 链路与判定口径

档位真值要经过五跳才见到用户，任何一跳丢字段，后面全是空：

```
workbuddy(7863) /panel/api/models · supported_efforts + default_effort
  └─① providers/workbuddy/workbuddy_zcode_sync.py  →  ~/.zcode/v2/provider_config.json（optionSpecs.reasoningLevel）
  └─② tools/dsh_sync.py（+ zcode_effective_body.js 兜底规则合并） → ~/.dsh/profiles/desktop/cordis.patch.yml
  └─③ DSH 请求体 reasoning_effort
  └─④ gateways/zgate(7871)：不解析、不透出、只在极少数模型补 forceEffort
  └─⑤ wb2api 请求侧 EffortListing / applyEffortPolicy / normalizeReasoningEffort 降级
```

判定标准：**cordis.patch.yml 的 `reasoningEfforts` 是否覆盖上游声明的全部档位**（并在模型可关思考时补 `off: disabled`）。原因：DSH 唯一的档位来源就是这份静态表（见 §4 第 7 项：zgate 的 `/v1/models` 一个 effort 字段都不吐）。

---

## 2. 逐模型表（19 个，2026-11-10 14:36 实测）

上游声明列来源：WB 托管模型取 `GET http://127.0.0.1:7863/panel/api/models`（20 条，含 `supported_efforts`/`default_effort`/`can_disable_thinking`）；OC/QD/QN/GM 托管模型取 ZCode `provider_config.json` 的 `optionSpecs.reasoningLevel` 与 `zcode_effective_body.js` 合并后的 effective values。

| 模型 id（cordis） | 上游声明档位 | 落地到 cordis.patch.yml | 判定 | 证据 |
|---|---|---|---|---|
| DeepSeek-4.1-Flash | `[low,high,max]` 默认 high，可关思考 | `{'off': disabled, low, high, max}` + `compat.thinkingFormat: deepseek` | **一致**（off 是 can_disable 的合法扩展） | cordis.patch.yml:57-69 ↔ panel 实测 `cn:deepseek-v4.1-flash` |
| Gemini-3.8-Flash | 无逐档声明，只有兜底二态 `[disabled,enabled]` | 无 reasoningEfforts | **缺档** | cordis.patch.yml:70-72 |
| HY3 | `[low,high]` 默认 high | `{low, high}` | **一致** | cordis.patch.yml:91-99 ↔ panel 实测 `cn:hy3` |
| HY4-Free | `[high]` 默认 high | `{high}` | **一致** | cordis.patch.yml:100-107 ↔ `cn:hy4free` |
| Beam | `[low,medium,high,xhigh,max]`（OC 目录），但 `reasoningLevel.map={}` | 无 | **缺档（源头丢）** | cordis.patch.yml:108-110；go_model_sync.py:581 |
| Conatus | 只有 `map:{}`，effective 兜底 `[disabled,enabled]` | 无 | **缺档（源头二态）** | cordis.patch.yml:111-113 |
| Iceman | effective `[disabled,enabled]`（模型自身无 optionSpecs） | 无（按当前生成器应投影 `{off,high}`） | **缺档（patch 落后）** | cordis.patch.yml:114-116；dsh_sync.py:253-255 |
| HY4 | `[high]` 默认 high | `{high}` | **一致** | cordis.patch.yml:135-142 ↔ `cn:hy4std` |
| Qwen-3.8-Max | `[low,medium,xhigh]` | `{low, medium, xhigh}` | **一致** | cordis.patch.yml:143-149 ↔ provider_config（QD） |
| Qwen-3.8-Flash | 无 optionSpecs，兜底 `[disabled,enabled]` | 无 | **缺档（patch 落后）** | cordis.patch.yml:150-152 |
| GLM-5.3-Flash | `[low,high,max]` 默认 high | `{low, high, max}` | **一致** | cordis.patch.yml:153-162 ↔ `cn:glm-5.3-flash` |
| MiniMax-M3.1-Flash | `[low,medium,high,xhigh,max]` 默认 max | 全 5 档 | **一致** | cordis.patch.yml:163-174 ↔ `cn:minimax-m3.1-flash` |
| MiMo-2.6-Flash | 无 optionSpecs，兜底 `[disabled,enabled]` | 无 | **缺档（patch 落后）** | cordis.patch.yml:175-177 |
| MiMo-2.6-Pro | `supported_efforts=null`、`default_effort=high`、不可关思考 → 网关单档 high | 无（按当前生成器会投影 `{off,high}`） | **缺档 + 投影错档风险** | cordis.patch.yml:178-183；handler.go:640-642；panel 实测 `cn:mimo-v2.6-pro` |
| HY3-X | panel 目录结构性不含（走 opencode-go「省钱」档，不进 WB 的 `agents[cli].models` 菜单）；价目表、网关、上游实测均在 | `{low, high}` | **一致（非下架；判据选错）** | cordis.patch.yml:222-230；client.go:1987-2061 |
| Claude-Haiku-5.5 | OC 目录只有 `map:{}`，档位被生成器丢弃 | 无 | **缺档（源头丢）** | cordis.patch.yml:193-195；go_model_sync.py:577-581 |
| Muse-Spark1.3 | 同上 `map:{}` | 无 | **缺档（源头丢）** | cordis.patch.yml:196-198 |
| GPT-6-Luna | 同上 `map:{}` | 无 | **缺档（源头丢）** | cordis.patch.yml:199-201 |
| Space-Bunny | `[low,medium,high,xhigh,max]` 默认 max | 全 5 档 | **一致** | cordis.patch.yml:202-213 ↔ `cn:space-bunny` |

合计：**一致 9（含复查订正的 HY3-X）/ 缺档 10 / 孤儿 0**。

补充两条确定性：

- `python tools/dsh_sync.py --check` 实测 **exit 1**，输出「模型表: 有变化」→ 当前 patch 已落后于 ZCode 现状，缺档的 5 个（Gemini-3.8-Flash、Iceman、Qwen-3.8-Flash、MiMo-2.6-Flash、MiMo-2.6-Pro）正是"该重跑生成器"的那批。
- 落地档位与实际生效可对上：`cn:deepseek-v4.1-flash` 全量 17133 次请求里 applied=high 11012 次（其中 10053 次带 reasoning_tokens>0）、max 3106 次（2633 次带思维链）、low 177 次，说明声明出来的档位是真被上游执行的，不是装饰。

---

## 3. 三个 realm 的档位来源优先级是否按注释实现

realm 只有 `cn` / `global` 两种，`realmKey` 把空值归一成 `cn`；ZCode 侧没有 realm 概念（provider → DSH 的 `zcode-main/free/saver` 三个 gateway key）。

### 3.1 声明侧（`/v1/models`、面板行）：远端桶 → 静态兜底 → 省略
`internal/upstream/effort_catalog.go:117-133`：

```go
case len(remoteEfforts) > 0:  src = effortCap{efforts: remoteEfforts, defaultEffort: remoteDefault}
default:                      src = staticEffortCap(realm, model)   // :99-105 按 realm 选表
if len(src.efforts) == 0 { return nil, "" }                          // 皆无 → 省略字段
if src.defaultEffort != "" && containsEffort(efforts, src.defaultEffort) { defaultEffort = src.defaultEffort }
```

**与注释(:107-116)一致**：远端非空即权威、不回落到静态；默认档必须落在档位表内才声明（表外默认档被丢弃，正是"defaultEffort 落在表外被丢"的唯一发生点——只在声明侧丢，请求侧不受影响，见 3.3）。调用点：handler.go:639（cn）/ :699（global）、panel.go:957。

**但这层兜底有洞**：CN 静态表 `cnEffortFallback`（effort_catalog.go:32-49，共 16 条）与现网 20 条目录比，**缺 8 个有档位的模型**：`hy4free`、`hy4std`、`space-bunny`、`minimax-m3.1-flash`、`kimi-k3.1-pro`、`kimi-k2.8-preview`、`step-5-preview`、`mimo-v2.6-pro`。远端桶一旦取不到（wb2api 离线/账号失效），这 8 个模型在 `/v1/models` 会直接"无档位可报"，注释承诺的"静态兜底"对它们等于不存在（CN 表仍是 2026-10-21 的 5.8.3 目录口径）。相对而言 global 表（:72-95，23 条）在 2026-10-29 按 5.9.3 目录重抄过、覆盖较完整；但当前**无 global 模型在线**（panel `global_source` 为空），global 分支只做了代码核对、无实测。

### 3.2 请求侧（出站降级表）：静态为基 + 远端覆盖
`effort_catalog.go:152-184`：`cnEffortMap`/`globalEffortMap` → `effortFallbackMap`，先铺静态表，再用远端 `efforts`/`defaults` 的非空项覆盖。**注意这里没有 `defaultEffort ∈ efforts` 校验**（:178-182 直接写入），所以会出现"档位来自静态、默认档来自远端"的跨源组合；`normalizeReasoningEffort`（payload.go:377-403）只在"同距"时用该默认档做 tie-break，默认档不在支持表里时只是永不命中、退回"同距宁高"，不会把非法档写进请求——**降级行为安全，但两处口径（声明有校验、请求侧无校验）不一致，注释 :113-116 只约束了声明侧**。

### 3.3 默认档的真实链路（三层，逐层软化）
1. 上游：多数模型 `default_effort=high`（v4.1-flash、hy3、glm-5.3 系…）；space-bunny / minimax-m3.1-flash 是 max。
2. 网关：`config.json:145-150` `{client_priority:true, default_effort:"max", override_scope:"level", model_defaults:{}}` → 客户端不表态时一律补 **max** 再按 supported 降级；`listing.go:29-46` 还会把 `/v1/models` 的 `reasoning_default_effort` **改写**成网关解析后的档（所以接口上看到的"默认档"= max，不是上游的 high）。
3. DSH：cordis.patch.yml **没有**任何逐模型默认档字段（全文只有 :9 `agent-default-model.reasoningEffort: high`），生成器 `_reasoning`（dsh_sync.py:243-257）也只搬档位列表、不搬默认档。

结果：**用户看到的三方默认档互不相等** —— 上游 high、网关 max、ZCode 侧下拉取数组末位（v4.1-flash 末位 max，实测 ZCode 客户端 1850 次请求全发 max）、DSH 全局 high。

---

## 4. 缺口清单（8 项）

1. **5 个模型 cordis 缺档（可修）**：Gemini-3.8-Flash、Iceman、Qwen-3.8-Flash、MiMo-2.6-Flash、MiMo-2.6-Pro。根因：这些模型在 `provider_config.json` 里没有自己的 `optionSpecs.reasoningLevel`，档位只存在于 ZCode 的全局兜底规则；上次生成时 `_effective_metadata`（dsh_sync.py:161-191）走了 WARN 回落分支，`_fallback_meta`（:206-218）对模型自身 rule 取不到 values → `_reasoning` 返回 `{}`。`--check` 已报警（exit 1）。
2. **投影本身对 MiMo-2.6-Pro 错档**：上游 `supported_efforts=null` + `can_disable=false`，网关只声明单档 high；生成器按兜底规则会投影 `{'off': disabled, high}`（dsh_sync.py:253-255），凭空多给一个"关闭思考"——而该模型上游不允许关。重跑生成器前需先修这条，否则以修好一个、错一个收场。
3. **5 个模型源头丢档**：Beam（`map:{}` 把 5 档 values 丢掉）、Claude-Haiku-5.5、Muse-Spark1.3、GPT-6-Luna（同样 `map:{}`），Conatus（连 values 都没有）。根因在 `providers/opencode-go/ops/go_model_sync.py:577-581`：`needs_no_thinking` 且非 chat 协议/命中 `EFFORT_UNSUPPORTED` 时只写 `spec["map"]={}`，`optionSpecs.values` 被跳过；ZCode 侧于是拿不到档位，DSH 也就无档可选。这 4 个 OC 模型实测只吃 `reasoning_effort` 就返回 200（同文件 :567-573 注释），档位是可表达的，是上游脚本把它们丢了。
4. **逐模型默认档全线缺失**：cordis 无 `defaultReasoningEffort`/等效字段，DSH 只能按全局 high 发；对 Qwen-3.8-Max `{low,medium,xhigh}`、HY4-Free `{high}`、MiniMax 5 档这类模型，"默认"与上游声明无关。hy4free 实测 679 次 `requested=""` 被网关补成 high，属于网关兜底而非上游默认。
5. **默认档三方不一致（见 §3.3）**：上游 high / 网关 max / ZCode 数组末位 max / DSH high，四个值，没有任何一处对齐。
6. **声明与实际不符（2 例，均有日志）**：
   - `cn:mimo-v2.6-pro` 被 `handler.go:640-642` 退化成单档 high 声明，但实测 42 次 `requested=high` 全部 `applied` 为空（上游 `supported_efforts=null`，出站档位被丢弃）；
   - `cn:hy4-preview-f`（历史模型）1507 次 `requested=high` 也全部 applied 为空，而响应里 reasoning_tokens 高达 21249——档位声明不生效、思考照跑。
7. **zgate 不承接档位声明**：`GET http://127.0.0.1:7871/v1/models` 实测 89 个模型，键只有 `id,object,owned_by,canonical_id,group,chain_hops`，**effort/reasoning 命中 0**（2026-11-10T06:36:45Z）。zgate 内部也没有任何档位目录逻辑（只有 config.go:72-81 的守卫注释与 router.go:1347-1386 给 Iceman 补 `forceEffort`）。→ DSH 无法动态发现档位，只能靠静态 patch，因此上面每一项缺口都必须人手修一遍。
8. **HY3-X 不是下架，是本处判据选错**（2026-11-10 15:5x 初判订正，17:5x 补机制）：原判「上游 20 条目录里已无 hy3-x」只依据 WorkBuddy panel 列表，而该列表**结构上不可能列出它**。机制链（`gateways/upstream/workbuddy/internal/upstream/client.go:1987-2061`）：panel 目录 = `env.Data.Agents` 中 `name=="cli"` 的 `models` 白名单 ∩ `dynMap`（已剔 `nonChatModel`：`nes-`/`completion-`/`codewise-` 前缀、`maxOutputTokens≤256`、tags 含 `text-to-image`）∩ `!Disabled`，再剔 `isAutoModeID`；即**只覆盖 WB 账号 CLI 菜单这一条链路**。HY3-X 挂的是 ZCode 的 `opencode-go-chat-fast`（providerName「省钱」，`config.api.baseUrl=http://127.0.0.1:7871/v1`，`modelOrder` 12 项里第 8 位），走 zgate 直连（`/v1/models` 里 `chain_hops=1`、`group=省钱`），两套可见性没有交集 —— **目录不含是结构性的，不是数据缺了**。三条真值反证照旧：① `providers/workbuddy/cache/wb_pricing.json`（39 条全 cn:）仍含 `cn:hy3-x`，`efforts=[low,high]`、`default_effort=high`、`ctx 192000/out 64000`、`can_disable=false`；② `GET http://127.0.0.1:7871/v1/models` 96 条里 `HY3-X group=省钱`，hy3 系其余（`cn:hy3`/`cn:hy3-b`/`cn:hy3-c`/`HY3`/`HY3-F`/`HY3-Free`）全在「免费」组，只有 `hy3-x` 系属「省钱」；③ 直连 7871 `model=HY3-X` 流式 0.9s 返回正常 SSE，含 `reasoning_content`，回显 `model=hy3-x`。**教训：判「下架」必须用与消费链路同源的目录（zgate `/v1/models` 或 `wb_pricing.json`），拿单一上游的面板菜单做全集就会把「不在这条链上」误读成「没了」。** 档位声明 `{low, high}` 与上游一致，既不构成缺档，也不构成孤儿。

---

## 5. 真实流量证据（落地是否生效）

`gateways/upstream/workbuddy/data/request-logs/*.jsonl` 全量 24407 条（2026-11-03 ~ 11-10），DSH 客户端 19944 条：

| 观察点 | 数据 |
|---|---|
| DSH 请求里带 `reasoning_effort` 的 | 16503 / 19944（82.7%） |
| `deepseek-harness` 无档位请求 | 3441 条，集中在 `cn:hy4-preview-f`(1735)、`cn:deepseek-v4.1-flash`(1549)、`cn:hy4free`(104)、`cn:mimo-v2.6-pro`(53) |
| v4.1-flash 实际生效档分布 | high 11012 / max 3106 / low 177 / 无档 2845 |
| 带思维链的占比（applied=high） | 10053 / 11012 有 `reasoning_tokens>0` |
| ZCode 客户端（ZCode/3.17.2） | v4.1-flash：max 1850、low 176、high 17、无 1277 → 印证"取数组末位当默认档"（workbuddy_zcode_sync.py:302-307 注释） |
| 网关补档（requested 空 → applied 有值） | hy4free 679 次补 high、hy3 15 次补 high；v4.1-flash 1549 次空档则被 `normalizeReasoningEffort` 删空（payload.go:351-355） |

配套：`agent-default-model.reasoningEffort: high`（cordis.patch.yml:9）是 DSH 唯一默认档来源；zgate config.go:73-75 注释称"DSH 请求体根本不带 reasoning_effort"，与 11-10 的日志（`reasoning_effort=high, reasoning_effort_requested=high`）**相矛盾**，该注释是旧版实测、已过时，勿再作为判断依据。

---

## 6. 任务书必读项的核对偏差（避免后来者重复劳动）

- `internal/upstream/conv_fields.go`（90 行）只处理 `conversationRequestId` / `startsNewUserRequest` / `agent=cli`，**与 reasoning/effort/thinking 无关**；相关改写全部在 `payload.go`（:91-165 prepareBodyOpt、:339-413 normalizeReasoningEffort）、`thinking.go`（:182-243 injectThinking/ensureDeepSeekEffort）、`effort_policy.go`（:111-226）。
- `providers/workbuddy/archive/wb_model_status.json`（9648B，2026-10-20）只有 `{status,http,detail,checked_at}`，**没有任何 reasoning/supportedEfforts/defaultEffort 字段**，不能当档位真值；有效真值是 `cache/wb_pricing.json`（39 条，字段 `efforts`/`default_effort`/`can_disable`）与线上 `/panel/api/models`。
- `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` 在本机未设置，实际文件是脚本默认路径 `~/.zcode/v2/provider_config.json`（12083B，mtime 2026-11-10 05:48）。
- 本会话 `ops_bash` 不可用（`EXECUTOR_UNAVAILABLE: Niubash preparation failed`），全部证据用 node:fs/child_process 采集；bundled python 缺 PyYAML，`dsh_sync.py` 用系统 Python 3.12.10 执行。

---

## 7. 复核命令

```bash
# ① 生成器是否落后（预期 exit 1 + "模型表: 有变化"）
python tools/dsh_sync.py --check

# ② 上游声明的档位真值
curl -s -H "Authorization: Bearer $WB_GATEWAY_KEY" http://127.0.0.1:7863/panel/api/models | head -c 2000

# ③ DSH 能不能动态拿到档位（预期只有 6 个键、effort 命中 0）
curl -s http://127.0.0.1:7871/v1/models | python -c "import json,sys;d=json.load(sys.stdin)['data'];print(len(d),sorted(d[0]))"

# ④ 落地档位与实际生效对照
python - <<'PY'
import json,glob,collections
c=collections.defaultdict(collections.Counter)
for f in glob.glob('gateways/upstream/workbuddy/data/request-logs/*.jsonl'):
    for l in open(f,encoding='utf-8'):
        if l.strip():
            r=json.loads(l); c[r['model']][r.get('reasoning_effort','<无>')]+=1
for m in sorted(c): print(m, dict(c[m]))
PY
```
