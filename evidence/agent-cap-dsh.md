> **一句话**：DSH 宿主根本不读 `provider_config.json` 的 `properties.*` / `optionSpecs.*`（全仓 0 命中），这些字段只被 `tools/dsh_sync.py` 投影成 `cordis.patch.yml` 的 `llm-pi-ai.providers.*.models[]`；真正决定下拉、档位、预算的是后者，缺字段的默认值是 contextWindow=1000000、maxTokens=128000、input=["text"]，而不是 0/隐藏。

# DSH 宿主侧模型能力字段消费链路（实测）

## 0. 五问速查

| # | 问题 | 结论 |
|---|---|---|
| 1 | 下拉模型列表 + 每模型 reasoning 档位由谁生成 | 宿主 `buildModelCatalog` 组装；档位唯一来源是适配器 `reasoningInfo()` 从 `THINKING_LEVELS` 派生的 `efforts`。不认识的值**在投影层就被丢弃**（不照抄、不进下拉）；不认识的值写进 yml **键**则整条 route 配置校验失败 |
| 2 | `contextWindow` 被谁读、写大会怎样 | 5 个消费点（见 §2）。填大 = 压缩阈值跟着放大，**请求照样发出去**，靠上游 400 兜底；没有"超窗预检拦截" |
| 3 | `supportsToolCall`/`supportsImage` 为真但上游不支持 | DSH **没有 tools 能力字段**，工具无条件随请求发送，只能吃上游报错；图片有客户端硬拦（`UNSUPPORTED_CONTENT`） |
| 4 | 匿名代号沉底是配置还是宿主排序 | **配置**。DSH 全链路保序不排序；顺序来自 `provider_config.json` 的 `providerRules[].config.modelOrder` |
| 5 | 缺 contextWindow/tools/image 的默认行为 | contextWindow→1000000，maxTokens→128000，image→仅 text（图片被拦），tools→无字段（照发），reasoning 缺失→整个档位选择器消失 |

## 1. Q1 下拉与档位

**模型列表**：`/dsh/node_modules/@deepseek-ai/dsh-api-session-controller/lib/types/catalog.js:10-61` `buildModelCatalog` —— 对每个 provider 调 `ctx.llm.listModels(provider.id)`，对每个 model 调 `ctx.llm.resolveModelInfo`，只搬运 `{id,name,reasoning,badge}`；`catalog.js:53-54` 把 0 模型的组直接滤掉。

**档位**：`resolveModelInfo` 返回 `context:{contextWindow}` + `...reasoningInfo(model, defaultLevel)`（`dsh-llm-pi-ai/lib/index.js:1955-1965`）。`reasoningInfo` 在 `index.js:1831-1839`：
```js
if (!model.reasoning) return {};
return { reasoning: { efforts: getSupportedThinkingLevels(model).map(level => ({ id, name: 首字母大写 })), ...defaultEffort } };
```
`getSupportedThinkingLevels`（`index.js:772-779`）在 `THINKING_LEVELS=[off,minimal,low,medium,high,xhigh,max]`（`index.js:299-307`）上过滤 `thinkingLevelMap`，其中 `xhigh`/`max` 必须**显式声明**才出现。

**不认识的值**：宿主 schema 是 `reasoningEfforts = z.dict(z.union([z.string(), z.const(null)]), z.union(THINKING_LEVELS))`（`index.js:1034`，注释 1024-1033 明写"键是档位、值是线上拼写"），解析期 `resolveModelReasoning` 用 `THINKING_LEVELS.flatMap` 取键（`index.js:586-608`）——**不在集合里的键在解析阶段根本不被读到**。因此：
- 值（wire 拼写）可以是任意串，如 `'off': disabled`，DSH 原样回传（`cordis.patch.yml:63`、`:75`）；
- 键必须落在 7 个规范档位内，否则在 `resolveProfiles(providers, validation="strict")`（`index.js:1120`）阶段整条 route 报错——**后果不是回退默认，而是这个 provider 整组从下拉消失**：`index.js:1792-1800` 注释原文 "a catalog that fails takes its whole provider out of every picker"，`catalog.js:42-51` 把失败组记进 `failures`、`53-54` 过滤掉空组。
- 只声明 `off` 一个档位 → 直接 invalid（`index.js:598`）；不写 `reasoningEfforts` → `{reasoning: base?.reasoning ?? false}`（`index.js:588`），非内置 catalog 的 route 一律 false → `reasoningInfo` 返回 `{}` → 客户端不显示档位。

**客户端不做二次过滤**：`dsh-client-ui-model-selection/lib/client.js:752-755` 把 `group.models[].reasoning` 原样进 Map；`:947-975` 当前 effort 在列表里找不到时用原始字符串显示（`?? effort`），不会隐藏。
**真正的过滤发生在投影层**：`tools/dsh_sync.py:286` `levels = [v for v in clean if v in DSH_LEVELS and v != "off"]`，`:196-203` `_efforts_outside` 把 `disabled` 与 DSH 表达不了的档位单列，`:287-299` 把 `disabled` 映射成 `off: disabled`。所以 `provider_config.json` 里的 `max/xhigh/minimal/disabled` 全部被消化，其中 `xhigh/minimal` 本就在集合内、`disabled` 变`关`键。

## 2. Q2 contextWindow 的 5 个消费点与"填大"的真实后果

| 消费点 | 位置 | 作用 |
|---|---|---|
| route 解析与校验 | `dsh-llm-pi-ai/lib/index.js:657-712`（`:694-695` 必须正整数） | `entry.contextWindow ?? base?.contextWindow ?? request.defaultContextWindow`；默认 `DEFAULT_CONTEXT_WINDOW=1e6`（`:960`） |
| 目录归一化 | `dsh-llm/lib/index.js:2124-2146` | 非正整数 → `INVALID_MODEL_CONTEXT`，整个 model 元数据非法 |
| 会话事件 | `dsh-agent-loop/lib/index.js:1066-1075` | 每请求把 `contextWindow` 写进 `request/context` 事件（变了才 append） |
| UI 压力条 | `dsh-token-meter/lib/index.js:454-467`、`:490-494`、`:818-824` | 投影出 `{contextWindow,pressureTokens,projectedTokens}`，客户端百分比读数 |
| 溢出判定 | `dsh-llm-pi-ai/lib/index.js:1487-1496` `mapStopReason` | `isContextOverflow(message, contextWindow)` 或错误文案命中 → `CONTEXT_WINDOW_EXCEEDED` |

压缩阈值（若启用 compaction-basic）：`dsh-compaction-basic/lib/index.js:124-146`
```js
messageBudgetTokens = contextWindow - reservedCompletionTokens;
pressureBudgetTokens = messageBudgetTokens - policy.headroomTokens;   // headroom 默认 65536 (:63)
thresholdTokens = floor(min(contextWindow * 0.8, pressureBudgetTokens));  // DEFAULT_THRESHOLD_RATIO=0.8 (:14)
retainTokens = floor(messageBudgetTokens * 0.16);                     // DEFAULT_RETAIN_RATIO=0.16 (:17)
```
以 `DeepSeek-4.1-Flash`（ctx=1000000、maxTokens=128000）算：threshold=800000 tokens。**没有找到任何"发送前按 contextWindow 预检并拒发"的代码**（`prompt admission` 侧只对图片做拦截，`:2000-2003`）。所以填大的后果链是：
1. 客户端压缩永远不会在真实上限（如 128k）之前触发；
2. 请求直发 → 上游返回超窗错误；
3. 只有错误文本命中 `isContextWindowExceededError` 正则（`dsh-llm/lib/index.js:172-173`：maximum/max context length|window、too large for context、exceeds model context…）才会被判成 `CONTEXT_WINDOW_EXCEEDED`，进而触发自动压缩+重试（`compaction-basic:879-905`，默认 `maxOverflowRetries=1`，`:83`）；
4. 文案不匹配 = 普通 API_ERROR，直接被 retry 策略（`cordis.patch.yml:43-47` 只重试 EMPTY_RESPONSE/SERVER/TIMEOUT/TRANSPORT）放大成一次失败。
**本 profile 的额外事实**：`compaction-basic` 与 `command-compact` 被 billion-context 的 gate 全局置 `disabled:true`（`~/.dsh/profiles/desktop/node_modules/billion-context/dist/agent/dsh-compaction-gate.js:3`，`disableBasicCompaction` 挂在 `internal/config` 全局钩子上），真正跑的是 billion-context 自己的 60%/90% 阈值（`cordis.patch.yml:482-490`）。即：**DSH 原生兜底在本机不生效，阈值全由 billion-context 从同一份 `contextWindow` 换算**。

## 3. Q3 工具与图片

- **工具无能力字段**：整棵 `resources/app/dsh` 里 `supportsToolCall` 出现 **0 次**（同名扫描 `providerModelRules`/`optionSpecs` 也是 0 次）。适配器侧 `dsh-llm-pi-ai/lib/index.js:1988` `const tools = options.tools ?? [];` —— 无条件随请求发送，无按模型过滤。结论：`supportsToolCall=false` 写了也**没有任何宿主代码消费**，工具照发，失败只可能来自上游 4xx。
- **图片有客户端硬拦**：`index.js:2000-2003`
  ```js
  const containsImage = options.messages.some(m => contentHasImage(m.content));
  if (containsImage && !model.input.includes("image")) throw new LlmError(..., "UNSUPPORTED_CONTENT");
  if (containsImage && attachments === void 0) throw new LlmError(..., "UNSUPPORTED_CONTENT");
  ```
  即 `input` 里没 `image` 时请求**发不出去**，报 `UNSUPPORTED_CONTENT`；反向（声明 image 但上游不支持）= 直发吃上游 400，无兜底。
- 声明 image 还需 `resolveAttachments` 服务在位，否则同样 `UNSUPPORTED_CONTENT`（`:2003`）。

## 4. Q4 顺序：配置写死，宿主保序

```
provider_config.json  providerRules[].config.modelOrder
   ↓ dsh_sync.py:145  ids = pcfg.get("modelOrder") or pcfg.get("personalModelIds")
   ↓ dsh_sync.py:320  for model_id in provider["modelIds"]  → models[] 顺序即数组顺序
cordis.patch.yml llm-pi-ai.providers.*.models[]
   ↓ pi-ai resolveEntry 按数组顺序建 Map（index.js:684-712）
   ↓ listModels 原序 map 出去（index.js:1927-1943）
   ↓ dsh-llm listModels 注释原话 "detached model metadata in adapter-preferred order"（dsh-llm/lib/index.js:2080-2107）
   ↓ buildModelCatalog 原序搬运（catalog.js:12-40）
客户端 orderModelProviders 只排 **组**，注释明写 model order within each group is unchanged（dsh-client-ui-model-selection/lib/client.js:1107-1116）
```
实测 `modelOrder`：主力=[DeepSeek-4.1-Flash, Gemini-3.8-Flash, Gemini-AIS]；免费=[HY3, HY4-Free, Beam, **Conatus, Iceman**]；省钱=[HY4, Qwen-3.8-Max, Qwen-3.8-Flash, GLM-5.3-Flash, MiniMax-M3.1-Flash, MiMo-2.6-Flash, MiMo-2.6-Pro, HY3-X, Claude-Haiku-5.5, Muse-Spark1.3, GPT-6-Luna, Space-Bunny]。
→ **Conatus/Iceman 沉底是因为它们在 modelOrder 末尾**（配置/别名规则写死），不是宿主排序。要调位置就改 modelOrder，改 DSH 侧无效（每日同步会覆盖）。

## 5. Q5 缺字段的真实默认值

投影层（`tools/dsh_sync.py:313-345`）先做了归一：`_positive_int`（`:309-310`）把非正整数变 None → **键直接省略**，因此"缺"在这条链上等价于"不写"。

| 缺的字段 | 宿主默认 | 证据 |
|---|---|---|
| contextWindow | **1000000**（不是 0、不隐藏） | `index.js:1058` `defaultContextWindow: ...default(DEFAULT_CONTEXT_WINDOW)`；`:960` `DEFAULT_CONTEXT_WINDOW = 1e6`；缺省回退链 `:694-695` |
| maxTokens | **128000** | `:962` `DEFAULT_MAX_TOKENS = 128e3`；`:1059`；回退链 `:696-697` |
| input / supportsImage | **["text"]**（图片被客户端拦） | `:973` `DEFAULT_INPUT=["text"]`；`:1060`；`dsh_sync.py:333` `model["input"] = ["text","image"] if supportsImage else ["text"]` |
| supportsToolCall | **无此字段，工具照发** | 全仓 0 命中；`index.js:1988` |
| reasoningLevel.values | **无档位**：`_reasoning` 返回 `{}`（`dsh_sync.py:301-302`）→ 无 `reasoningEfforts` → `reasoning:false`（`index.js:588`）→ `reasoningInfo` 返回 `{}`（`:1832`）→ 选择器里没有档位行 | 同左；另有 `_keep_efforts`（`dsh_sync.py:393-423`）在源头退化时保留旧 yml 档位，避免"档位突然消失" |

缺字段的 11 条 = #2,3,6,7,8,10,11,14,17,18,19（Gemini-3.8-Flash / Gemini-AIS / Beam / Conatus / Iceman / Qwen-3.8-Max / Qwen-3.8-Flash / MiMo-2.6-Flash / Claude-Haiku-5.5 / Muse-Spark1.3 / GPT-6-Luna）。它们当前在 yml 里的实际值来自 `zcode_effective_body.js` 的 resolved 元数据或 `_fallback_meta`（`dsh_sync.py:244-278`），不是 DSH 的默认值——**只有连生成器都没写时，才会落到上表 1e6/128k**。

## 6. 未验证 / 需注意

- 「未知档位键写进 yml 会让整组 provider 从下拉消失」是从 `index.js:1034` 的 key schema + `:1120` strict 校验 + `:1792-1800` 注释推出的**代码路径推断，未做写盘实测**（`~/.dsh` 只读纪律）。
- `provider_config.json → yml` 的顺序是否还会被 `tools/model_alias.py` 二次排序：**未验证**（只确认 `modelOrder` 是顺序来源，且当前 yml 顺序与它完全一致）。
- asar 读取方式：`resources/app.asar` 非标准布局（header 从 offset 16 开始，base=5748140），用外部 `node`（v24.13.1）解析；本次逐字节比对 `resources/app/dsh` 与 asar 内容一致（desktop-runtime.json 4942461 B 相等），故行号引用 asar 内路径、内容读自带镜像。
- 凭据：本报告不含任何 key；`ZCODE_GATEWAY_KEY` 只以环境变量名出现，值一律 `<REDACTED>`。
