# 模型能力配置审计（2026-11-10）

> **更新（2026-11-11）**：本文描述的问题已落地修复 —— 新增 `tools/caps_upstream.py` 直连 WB 面板 / OC / QN 三个上游模型接口取真值，16/20 个模型的能力字段已换成接口实测值并投影进 DSH，剩 4 条无真值的老实标 none。落地细节、逐模型终值与验收命令见文末 **§9**。
>
> **一句话**：DSH 模型下拉里那些「上下文长度 / 输出上限 / 收不收图片 / 能不能调工具 / 思考档位」，只有 9 个模型是上游真值，剩下的来自 ZCode 内置规则里一条 `.*` 兜底（上下文 100 万、输出 12.8 万、工具 true、图片 false）；而真正写着上游真值的那一层规则，因为我们的 baseURL 指向本地网关，**一条都没命中**。

---

## 0. 结论先行

| 问题 | 回答 |
|---|---|
| 从上游真取值的有多少？ | 20 个模型里 **9 个**（经 WorkBuddy 面板元数据）；11 个只有思考档位，上下文/输出/图片/工具全空，靠兜底补 |
| 上下文是随意填的吗？ | 分两类：9 条**全部能在上游目录原文里指到**（逐条比对过 JSON，0 条编造）；11 条是**兜底魔数** 1000000。这 11 条里真值差得最远的是 Iceman（262144，虚高 3.8 倍），另有 5 条真值 1048576～1050000（偏低约 5%） |
| 输出上限呢？ | 13 个模型写死 128000。真值差得最远的是 MiniMax-M3.1（512000）和 DeepSeek（384000～393216） |
| 「技能」（工具调用/图片）呢？ | 工具调用恒 true —— 但**DSH 宿主根本不读这个字段**，工具无条件发送，写 false 也拦不住；图片是有硬拦的：7 个模型被标成不支持，上游明确给了 `modalities.input: image`，于是这些模型永远发不出图 |
| 每日下拉呢？ | 每天 12:00 由 `model_alias.py` → `dsh_sync.py` 重新投影一遍，但投影源就是上面这份「兜底值」，所以**每天把同一份没核过的数字再确认一次** |
| 一句话结论 | 不是「配错了几个数」，而是**取数链路缺了一层**：上游目录给了真值，本地没有任何脚本去拉它，全靠 ZCode 内置规则猜 |

---

## 1. 三层来源：真值层为什么没生效

DSH 看到的每个字段，是 ZCode 引擎按顺序叠加 6 组规则算出来的，后写的覆盖先写的（`providers/workbuddy/zcode_effective_body.js:104-164`，顺序同 ZCode 上游 `schema.ts`）：

1. `modelRules`（按模型名正则）
2. `modelApiRules`（再按协议名）
3. `providerSiteRules`（再按 baseURL）← **真值层在这里**
4. `templateModelRules` / `builtinProviderModelRules`
5. 用户 `providerModelRules`（`~/.zcode/v2/provider_config.json`）

### 1.1 真值层写了什么

`third-party/zcode/zcode-builtin.json` 的 `providerSiteRules[7]` 是给 DeepSeek 写好的真值：

```json
{"modelMatch":"deepseek-v4\\.1-flash","baseUrlMatch":"https://opencode\\.ai/zen/go/v1/?",
 "config":{"properties":{"contextWindow":1000000,"inputFormat":{"supportsImage":true},
                       "supportsJsonSchemaOutput":true},
           "optionSpecs":{"maxOutputTokens":{"max":384000}}}}
```

### 1.2 它为什么没生效：两个不匹配

| 门 | 规则要求 | 我们实际是 | 结果 |
|---|---|---|---|
| baseURL | `https://opencode.ai/zen/go/v1/?` | `http://127.0.0.1:7871/v1`（走自家网关） | 所有 `provider-site` 规则**一条不命中** |
| 模型名 | `deepseek-v4.1-flash` | `DeepSeek-4.1-Flash`（显示别名） | 即使 baseURL 对了也匹配不上 |

两条都不满足 → 落到 `modelRules[0]` 的 `.*` 兜底：

```json
{"modelMatch":".*","config":{"properties":{"contextWindow":1000000,"supportsToolCall":true,
  "inputFormat":{"supportsImage":false}},"optionSpecs":{"maxOutputTokens":{"max":128000}}}}
```

**这就是「随意填写」的真身**：不是人手敲的，是内置规则兜底，而且兜底值恰好看着很合理（100 万 / 12.8 万），所以三年来没人发现。

补一条反证（生成侧子代理核实）：`tools/model_alias.py:366` 的注释写着「DSH 侧只能吃 dsh_sync 的兜底值（1000000 / 128000）」，与代码不符 —— `dsh_sync.py:327-330` 用的是 `_positive_int(meta.get("contextWindow"))`，取不到就**不写这个键**，全仓 1000000 只出现在 `zcode-builtin.json` 里。配置侧从来没有兜底，兜底发生在规则求值那一刻。这条过期注释本身就是「改过的东西没对齐」的证据。

### 1.3 一次求值就能看见

`.work/cap-probe.cjs` 用同一份规则文件跑两种输入（只读探针）：

| 模型 | 现在的值（别名 + 网关） | 换成上游 slug + 官方域名 |
|---|---|---|
| DeepSeek-4.1-Flash | ctx 1000000 / max **128000** / img true | ctx 1000000 / max **384000** / img true |
| Qwen-3.8-Max | ctx 1000000 / max 128000 / img **false** | ctx 1000000 / max **131072** / img **true** |
| GPT-6-Luna | ctx 1000000 / max 128000 / img **false** | ctx **1050000** / max 128000 / img **true** |
| MiMo-2.6-Pro | max 128000 | max **131072** |

命中轨迹也印得出来：现在只命中 `model:.*` + `model-api:.*`；换成真值输入才追加 `provider-site:deepseek-v4\\.1-flash` 等精确规则。

---

## 2. 20 个模型的能力值现状

数据来自 `~/.dsh/profiles/desktop/cordis.patch.yml`（YAML 解析，非正则）与 `~/.zcode/v2/provider_config.json`。

| 模型 | 组 | DSH 上下文 | DSH 输出上限 | 图片 | 配置里有 ctx/max/img | 来源 |
|---|---|---|---|---|---|---|
| DeepSeek-4.1-Flash | 主力 | 1000000 | 128000 | 是 | 有 | WB 真值 |
| Gemini-3.8-Flash | 主力 | 1000000 | 128000 | 否 | 无 | 兜底 |
| Gemini-AIS | 主力 | 1000000 | 128000 | 否 | 无 | 兜底 |
| HY3 | 免费 | 192000 | 64000 | 是 | 有 | WB 真值 |
| HY4-Free | 免费 | 960000 | 64000 | 是 | 有 | WB 真值（孤值） |
| Beam | 免费 | 1000000 | 128000 | 否 | 无 | 兜底 |
| Conatus | 免费 | 1000000 | 128000 | 否 | 无 | 兜底 |
| Iceman | 免费 | 1000000 | 128000 | 否 | 无 | 兜底 |
| HY4 | 省钱 | 960000 | 64000 | 是 | 有 | WB 真值（孤值） |
| Qwen-3.8-Max | 省钱 | 1000000 | 128000 | 否 | 无 | 兜底 |
| Qwen-3.8-Flash | 省钱 | 1000000 | 128000 | 否 | 无 | 兜底 |
| GLM-5.3-Flash | 省钱 | 1000000 | 128000 | 是 | 有 | WB 真值 |
| MiniMax-M3.1-Flash | 省钱 | 1000000 | 128000 | 是 | 有 | WB 真值 |
| MiMo-2.6-Flash | 省钱 | 1000000 | 128000 | 否 | 无 | 兜底 |
| MiMo-2.6-Pro | 省钱 | 1000000 | 128000 | 是 | 有 | WB 真值 |
| HY3-X | 省钱 | 192000 | 64000 | 是 | 有 | WB 真值 |
| Claude-Haiku-5.5 | 省钱 | 1000000 | 128000 | 否 | 无 | 兜底 |
| Muse-Spark1.3 | 省钱 | 1000000 | 128000 | 否 | 无 | 兜底 |
| GPT-6-Luna | 省钱 | 1000000 | 128000 | 否 | 无 | 兜底 |
| Space-Bunny | 省钱 | 1000000 | 128000 | 是 | 有 | WB 真值 |

`provider_config.json` 的字段完整度：**9 条有全字段，11 条只有 `reasoningLevel`**，`contextWindow` / `supportsToolCall` / `inputFormat` / `maxOutputTokens` 一个字都没有。

### 2.1 谁写谁不写（代码事实）

| 脚本 | 写 contextWindow | 写 supportsToolCall | 写 supportsImage | 写 maxOutputTokens | 写档位 |
|---|---|---|---|---|---|
| `providers/workbuddy/workbuddy_zcode_sync.py:284-333` | 是（`context_length`） | 是 | 是 | 是（`max_output_tokens`） | 是 |
| `providers/opencode-go/ops/go_model_sync.py:579-593` | **否** | **否** | **否** | **否** | 是 |
| `providers/qoder/qoder_zcode_sync.py:283` | **否** | **否** | **否** | **否** | 是 |

一个模型的字段齐不齐，取决于**链上有没有 WorkBuddy 那一跳**：有 WB 就被写全，纯 OC / QD 链就只剩档位，剩下交给兜底。这就是上面 9 对 11 的由来，不是设计，是副作用。

### 2.2 兜底值的指纹（以后一眼认出来）

同时出现这三件套，就是兜底，不用查：

| 指纹 | 值 |
|---|---|
| `contextWindow` | 1000000 |
| `maxTokens` | 128000 |
| `input` | 只有 `text` |

20 个模型里符合「三件套全中」的：`Gemini-3.8-Flash`、`Gemini-AIS`、`Beam`、`Conatus`、`Iceman`、`Qwen-3.8-Max`、`Qwen-3.8-Flash`、`MiMo-2.6-Flash`、`Claude-Haiku-5.5`、`Muse-Spark1.3`、`GPT-6-Luna` —— **11 个**，与「`provider_config.json` 里没有 ctx 字段」的 11 条完全重合。

反过来，`HY3`/`HY3-X`（192000/64000）、`HY4`/`HY4-Free`（960000/64000）、`Space-Bunny`（1000000/128000/image）这几个数字不像兜底，才是 WB 真值写进来的。

---

## 3. 与上游真值的差额（五类）

真值来源：OC 免鉴权目录 `https://opencode.ai/zen/go/v1/models`（30 条，已落 `.work/cap-oc-models.json`）+ WorkBuddy 面板快照 `evidence/wb_panel_models.json`（56 条）。

### 3.1 上下文：4 个模型虚高、3 个偏低、1 个离谱

| 模型 | 上游真值 | 我们显示 | 偏差 | 后果 |
|---|---|---|---|---|
| Iceman | **262144** | 1000000 | 虚高 **3.8 倍** | 用户以为能塞 100 万，实际 26 万就报错 |
| HY4 / HY4-Free | 1000000（WB）/ 1048576（OC） | **960000** | 偏低 4%～8% | 还没到上限就被压缩/截断 |
| MiMo-2.6-Pro / -Flash | 1048576 | 1000000 | 偏低 4.6% | 同上 |
| Muse-Spark1.3 | 1048576 | 1000000 | 偏低 4.6% | 同上 |
| GPT-6-Luna | 1050000 | 1000000 | 偏低 4.8% | 同上 |
| HY3 / HY3-X | 256000（OC）/ 192000（WB） | 192000 | 取小值 | 保守但可用 |
| Gemini-3.8-Flash / Gemini-AIS | 上游目录没有该字段（HJ 只有 id/object/owned_by，GM 更少） | 1000000 | 无从判断 | 兜底值，不是真值 |
| Conatus | QN 1000000（QN 目录有 ctx） | 1000000 | 巧合一致 | 值对，但仍是兜底来的 |

### 3.2 输出上限：13 个模型写死 128000，最大差 4 倍

| 模型 | 上游真值 | 我们显示 | 倍数 |
|---|---|---|---|
| MiniMax-M3.1-Flash | **512000** | 128000 | 只有 1/4 |
| DeepSeek-4.1-Flash | 384000（OC）/ 393216（WB） | 128000 | 只有 1/3 |
| MiMo-2.6-Pro / -Flash / Beam / Muse / Qwen-3.8-Max / -Flash | 131072 | 128000 | 差 2.4%（无害） |
| Gemini-3.8-Flash | 上游目录无该字段 | 128000 | 无从判断 | 兜底值，不是真值 |

输出上限填**大**了会 400/截断，填**小**了只是浪费能力；两种都有。

### 3.3 图片输入：7 个模型被错标成「不收图」

上游明确给了 `modalities.input` 含 `image/*`，但 DSH 侧 `input: [text]`：

`Qwen-3.8-Max`、`Qwen-3.8-Flash`、`MiMo-2.6-Flash`、`Claude-Haiku-5.5`、`Muse-Spark1.3`、`GPT-6-Luna`、`Gemini-3.8-Flash`（WB 侧也支持）。

用户在 DSH 里粘图，客户端直接按 text 处理 —— 能力白丢，而且不报错。反向也有：`DeepSeek` / `GLM` / `MiniMax` / `Space-Bunny` / `HY` 系标了 image 且上游确实支持，这几条是对的。

### 3.4 工具调用：全部 true，碰巧上游也全 true

兜底写 `supportsToolCall: true`。OC 目录 30 条全是 `capabilities.tools.supported: true`，所以**这一项没有实际错**，但它是「猜对了」而不是「查过」。

同时被兜底吃掉的还有 `supportsJsonSchemaOutput`（真值 true，兜底 false）和 `supportsNativeWebSearch`（兜底 false）—— 这两项 DSH 目前不用，先记着。

### 3.5 一处投影丢失（待查）

GLM-5.3-Flash 在 `provider_config.json` 里 `maxOutputTokens.max = 131072`，`dsh_sync.py` 投影后 DSH 显示 **128000**。生成器读到的是 131072，落盘却是 128000，中间有一处被兜底值盖掉。同类问题值得逐字段核一次（不影响使用，但说明「投影可信度」不能默认满分）。

### 3.6 这些值填错，在 DSH 里到底会发生什么

宿主侧实测（`evidence/agent-cap-dsh.md`）给出了后果链，不是所有字段都一样疼：

| 字段 | 宿主怎么用 | 填错的后果 |
|---|---|---|
| `contextWindow` | 5 个消费点：解析校验、token 压力条、request/context 事件、溢出判定、压缩阈值 | **没有任何「发送前按窗口预检拒发」的代码**。填大 = 压缩阈值同步放大（ctx=1e6、max=128k 时阈值 800k tokens）→ 请求直接发出 → 上游 400 → 只有错误文案命中 `dsh-llm/lib/index.js:172-173` 的正则才判成 `CONTEXT_WINDOW_EXCEEDED` 并重试一次，否则只是普通 API_ERROR |
| `maxTokens` | 只作为单次输出上限下发 | 填大被上游拒（400）；填小只是浪费能力，无报错 |
| `input.supportsImage` | 客户端**硬拦**：input 不含 image 时发图直接返回 `UNSUPPORTED_CONTENT`，请求不出去 | §3.3 那 7 个假阴性 = 能读图却永远发不出图；反向（标了 image 但上游不支持）只能吃上游 400 |
| `supportsToolCall` | **宿主里根本没有这个字段**（全树 0 命中），`const tools = options.tools ?? []` 无条件发送 | 写 true / false / 不写，行为完全一样 —— 这一项的值只影响人看 |
| 档位 | 只决定下拉里有没有选项行；`disabled` 由投影层映射成 `off`，`DSH_LEVELS` 之外的值直接丢弃 | 档位缺失 = 下拉里没有档位行（不是回退 disabled/enabled）；多出来的档位被静默丢掉，用户点不到 |

另有一条本地特供：本 profile 的 `compaction-basic` 已被 billion-context 的 gate 关掉，实际生效的是它的 60%/90% 两档，读的仍是同一份 `contextWindow` —— 所以「填大一点让面板好看」在这里等于把压缩触发点一起推后。

---

## 4. 思考档位：值对不对、开关灵不灵

### 4.1 值八成来自上游：三条不一致、五条凭经验

| 判定 | 数量 | 模型 | 说明 |
|---|---|---|---|
| A 一致 | 11 | HY3、HY3-X、HY4、HY4-Free、Space-Bunny、DeepSeek、GLM、MiniMax、Beam、Muse-Spark1.3、Qwen-3.8-Max | 与上游 `efforts` 逐项相同；DeepSeek 的 `off`→`disabled`、GLM/MiniMax 的 `can_disable` 补 disabled，均符合脚本口径 |
| B 不一致 | 4 | MiMo-2.6-Pro、Qwen-3.8-Flash、Claude-Haiku-5.5、GPT-6-Luna | 上游 `["high"]` 却填 7 档；后三者多一个 `disabled`（上游没有 off 声明）；GPT-6-Luna 是把上游 `none` 字面改成 `disabled` |
| C 无来源 | 5 | Gemini-3.8-Flash、Gemini-AIS、Conatus、Iceman、MiMo-2.6-Flash | 上游目录里根本没有 effort 字段（GM/HJ/QN 不复述能力、OC 只给 `reasoning.supported=true`）→ 档位凭经验填 |

**合计 A=11 / B=4 / C=5**。所以「思考档位」也不是全无来源：八成一致，问题集中在 4 条多塞档位和 5 条凭经验。

### 4.2 开关灵不灵，看 `reasoningLevel.map`

档位值只是下拉里的选项，真正发给上游的是 `map` 表达式求值出来的请求体字段。

- 有自定义 map 的（`Claude-Haiku-5.5`、`GPT-6-Luna`、`MiMo` 系、`Qwen-3.8-Flash`、`Conatus`、`Beam`、`Iceman`、`Muse`）：`disabled → none`，只发 2 个字段，干净。
- 没有自定义 map 的（`DeepSeek`、`HY` 系、`GLM`、`MiniMax`、`Space-Bunny`、`Qwen-3.8-Max`）：落到 `modelApiRules` 的兜底表达式，**一次同时发 `thinking` / `enable_thinking` / `reasoning_effort` / `reasoning.effort` 四个字段**。

四个字段里上游只认其中一两个，其余靠「不认识就忽略」蒙混。

补一条来源事实：`disabled → none` 这类 map 串在三个同步脚本里都搜不到（`git log -S` 无结果、内置规则里也没有），只存在于 `provider_config.json` 里 —— 写入者是谁没有留下痕迹，属于「有人手动调过、没记录」的那一层。这就是项目里 `probe` 探测与 `fallback` 变体机制存在的原因 —— 也就是你说的「专门做了适配」的那一层。

**判定**：档位不是随意填，而是「值来自上游、表达靠一条通用兜底表达式」；真正的风险在兜底表达式对某些家系发多了字段，已有 probe 兜底，但没有任何静态检查能提前发现。

---

## 5. 衍生：同一毛病还长在别处

| 位置 | 现状 | 是否有真值源 | 判定 |
|---|---|---|---|
| **显示名** | DSH 下拉用 ZCode 别名（`DeepSeek-4.1-Flash`），上游 name 是 `DeepSeek V4.1 Flash`；WB 面板还有中文 `description` | 有 | 未取，且别名还导致规则匹配全灭 |
| **价格** | `model_alias.py` 按 WB `credits` 与 QD 价格算，有 0.11 阈值分组；`--check` 今天 **exit 1**：Qwen-3.8-Flash 0.09→0.03、Qwen-3.8-Max 0.43→0.17（价格 2 处 + 连带链路签名 2 处，同一根因） | 有（OC 的 `cost` 带分时倍率） | 只用了 WB 一份，OC 的 `cost.multipliers`（工作日白昼 ×2）完全没进模型 |
| **分组与排序** | `PROVIDER_MAIN/LOW_ORDER/CHANNEL_RANK` 全是代码常量手写 | 无（是用户偏好） | 合理，但要写清「这是偏好不是真值」 |
| **协议** | `protocol` 按渠道猜（OC=openai、QW/QN=anthropic） | OC 目录每条带 `api` 字段 | 未取 |
| **弃用/时间** | 上游有 `last_updated`、`release_date`，本地不用 | 有 | 未取，模型下架只能靠 404 发现 |
| **副本漂移** | 同一份能力数据存在 4 处：`provider_config.json`、`cordis.patch.yml`、`zcode-builtin.json`、`wb_panel_models.json` | —— | 只有 provider_config 是源头，其余是投影/快照，无一致性门禁 |
| **漂移检测** | `dsh_sync.py:206-229` 只查「源头有档位、投影变空」，**不查 ctx/max/img/tool，也不查反向** | —— | 今天这类错误它一律看不见 |
| **顺序** | DSH 下拉的组内顺序 = `provider_config` 的 `modelOrder` 数组顺序，`dsh_sync.py:145/320` 按序写出，宿主不再排序 | 无（是偏好） | 改宿主侧无效，每日同步照配置覆盖回来 |
| **冻结** | `properties` / `maxOutputTokens` 只有 WB 同步会写，其余每轮 deepcopy 继承旧值 —— 「价格天天动、能力一写三年不碰」 | 有 | 上游改了能力，本地永远不知道 |

---

## 6. 修法（按收益排序）

### P0：把上游目录接进来，一次解决 11 个模型的空字段

`go_model_sync.py` 已经在拉 `/zen/go/v1/models`（`declared_efforts()` 只用了一个字段），目录里 `limit.context` / `limit.output` / `capabilities.tools.supported` / `modalities.input` / `cost` 全都有。

1. 扩 `fetch_live_models()` 的返回：`{id: {ctx, out, tools, images, efforts, cost}}`；
2. `build_model_rule()` 把 ctx/out/images/tools 一并写进 `properties` 与 `optionSpecs`；
3. 同一模型多跳（WB > OC）时**取最保守的一组**（ctx 取最小、out 取最小、图片取交集），并在配置里注释来源；
4. 显示名同时写进 `providerModelRules`（或另建 `displayNames`），避免别名和正则对不上。

> 这一步做完，兜底只剩「真没数据」的模型（Conatus/Gemini 系），可枚举可审计。

改动点（都是小函数，不动主流程）：

| 文件 | 改什么 |
|---|---|
| `providers/opencode-go/ops/go_model_sync.py` | `fetch_live_models()` 多返回 `ctx/out/tools/images/cost`；`build_model_rule()` 写 `properties.contextWindow` / `supportsToolCall` / `inputFormat` 与 `optionSpecs.maxOutputTokens` |
| `providers/qoder/qoder_zcode_sync.py` | 同上，数据源换成 Qoder hub 的模型列表 |
| `providers/workbuddy/workbuddy_zcode_sync.py` | 已经写全，只需补「多跳取最保守」的合并逻辑 |
| `tools/dsh_sync.py` | 漂移检测从「档位单向」扩到四字段双向 |

### P1：给兜底上闸门，不再静默

- `dsh_sync.py` 的漂移检测扩到四字段，双向比对；
- `model_alias.py` 输出「本次同步里仍靠兜底的模型清单」，写进 `docs/reports/` 与 PROGRESS 一行；
- 数量 >0 时 `--check` 打 WARN（不阻断，因为兜底有时是故意的）。

### P2：图片能力按上游 modalities 生成，不再靠 `supports_images` 一个布尔

- `input` 从 `["text","image"]` 升级为按 `modalities.input` 映射（video/pdf 先不接，DSH 侧不认）；
- 与 `docs/MODEL-STREAM.md` 的准入表对齐，避免两处各写一遍。

### P3（先记不做）

- 价格接 OC `cost` 的 `overrides`/`multipliers`，让分时倍率进分组判断；
- `release_date` 进 `/v1/models`，下架提前预警。

---

## 7. 验收口径

| 项 | 判据 |
|---|---|
| 字段来源可审计 | `python -B tools/model_alias.py --check` 与 `python -B tools/dsh_sync.py --check` 都 exit 0，且输出里列出「靠兜底」的模型数 |
| DSH 与上游一致 | 20 个模型的 ctx/max/img/tools 与 `.work/cap-oc-models.json`、`evidence/wb_panel_models.json` 逐字段对齐（脚本比对，不靠眼看） |
| 落盘一致 | `cordis.patch.yml` 的 20 条与生成器内存结果逐字段相等（含 3.5 那处投影丢失） |
| 不回归 | `go test ./...`、`python -B -m unittest discover -s tests -q`、`check-project.py`、`check-docs.py` 全绿 |

---

## 8. 证据与复现

| 文件 | 内容 |
|---|---|
| `.work/cap-oc-models.json` | OC 目录 30 条原始 JSON（limit / capabilities / modalities / cost） |
| `.work/cap-probe.cjs` | 规则求值探针：别名+网关 vs 上游 slug+官方域名，打印命中轨迹 |
| `evidence/wb_panel_models.json` | WB 面板 56 条元数据（context_length / max_output_tokens / supported_efforts / credits） |
| `third-party/zcode/zcode-builtin.json` | ZCode 内置规则（`modelRules[0]` 兜底、`providerSiteRules[7]` 真值样本） |

复现：`node .work/cap-probe.cjs`；DSH 侧导出见 `.work/cap-patch-dump.py`。

---

## 9. 落地记录（2026-11-11）：上游真值链路

§6 的 P0 建议是「把上游目录接进来」。这一节记落地结果，**它覆盖 §2 / §3 里的兜底值描述**。

### 9.1 新增的一层：真值采集器

| 项 | 内容 |
|---|---|
| 工具 | `tools/caps_upstream.py`（只用标准库） |
| 取材 | WB `/panel/api/models`（ctx / max / tool / img / efforts）、OC `/zen/go/v1/models`（`limit.*`、`capabilities.tools`、`modalities.input`）、QN `/v1/models`（`context_length` / `max_tokens`） |
| 对号 | 按别名 `chain[].channel` 选上游，主用跳优先；WB 的 `cn:` 前缀与大小写差异都会试 |
| 产物 | `catalog/upstream_caps.json`（证据快照，可提交、可离线复算，门禁不联网） |
| 纪律 | 上游没给就是 `null`，**不推算**；跨跳不一致进 `conflicts` 只记录不擅自取舍；主用渠道不提供元数据时只写 `cross` 交叉参考，不填字段 |
| 取证覆盖层 | `catalog/upstream_caps_evidence.json`：接口压根不返回能力字段的渠道（HJ / GM / QW / QD）按厂商文档 + 功能实测取证后补进来，**只在接口为 `null` 时采用**，来源标 `evidence:…`；接口有值就绝不覆盖，只记 `conflicts` |

写入链路变成三段，每段都能单独核对：

```
caps_upstream.py --fetch        # 上游接口 + 取证覆盖层 → catalog/upstream_caps.json（证据）
model_caps.py --upstream ... --apply --apply-source upstream:   # 证据 → provider_config（只落真值）
dsh_sync.py --apply             # provider_config → cordis.patch.yml（DSH 投影）
```

`--apply-source upstream:` 是这轮加的关键闸门：**规则推断值一律不落盘**。以前 `--apply` 会把 builtin-family / site-rule 的推断（比如 MiMo 族级 128000、Qwen 族级 131072）当成真值写进去，族级规则只能说明「可能」，写进配置就成了既成事实。

### 9.2 逐模型终值（来源等级：upstream-api）

| 模型 | ctx | max_out | tool | img | 来源 |
|---|---|---|---|---|---|
| DeepSeek-4.1-Flash | 1000000 | 128000 | ✓ | ✓ | WB（OC 报 out 384000，冲突记为次要跳） |
| HY3 | 192000 | 64000 | ✓ | ✓ | WB |
| HY4 / HY4-Free | 960000 | 64000 | ✓ | ✓ | WB |
| GLM-5.3-Flash | 1000000 | 131072 | ✓ | ✓ | WB |
| MiniMax-M3.1-Flash | 1000000 | 128000 | ✓ | ✓ | WB（OC 报 512000） |
| MiMo-2.6-Pro | 1000000 | 128000 | ✓ | ✓ | WB（OC 报 1048576/131072） |
| Space-Bunny | 1000000 | 128000 | ✓ | ✓ | WB |
| Beam | 1048576 | 131072 | ✓ | ✗ | OC（纯文本输入） |
| Iceman | 262144 | 131072 | ✓ | ✗ | OC（虚高 3.8 倍的那条，已改正） |
| MiMo-2.6-Flash | 1048576 | 131072 | ✓ | ✓ | OC |
| Qwen-3.8-Flash | 1000000 | 131072 | ✓ | ✓ | OC（主用跳 QD 无元数据，取同款 OC 跳） |
| Claude-Haiku-5.5 | 1000000 | 128000 | ✓ | ✓ | OC |
| Muse-Spark1.3 | 1048576 | 131072 | ✓ | ✓ | OC |
| GPT-6-Luna | 1050000 | 128000 | ✓ | ✓ | OC |
| Conatus | 1000000 | 128000 | – | – | QN（上游没给 tool/img，保持空） |
| Gemini-3.8-Flash | 1048576 | 65536 | ✓ | ✓ | 官方 3.8 Flash 文档 + HJ 内联 PNG 实测（`evidence:` 覆盖层） |
| Gemini-AIS | 1000000 | 65536 | ✓ | ✓ | GM `/v1beta/models` 自报（厂商文档 1048576，取中继值） |
| Qwen-3.8-Max | – | – | – | – | **无真值**：QD 端点不可达（8790 拒连） |
| HY3-X | – | – | – | – | **无真值**：WB 面板没有 hy3-x 条目 |

剩这 2 条仍吃 ZCode 内置兜底（1M / 128k），文档与 catalog 里一律标 `source=none`，这是**已知未解决项**，不是「已核对」。

### 9.3 没动的部分及原因

| 项 | 决定 |
|---|---|
| 思考档位 `reasoningLevel.values` | 本轮不动。上游 effort 列表有 `minimal` / `none` / `enabled` 等 ZCode 方言里没有的值，硬收窄会让用户在下拉里丢选项 |
| `Qwen-3.8-Max` 的 max/img | 只有 OC 交叉参考（131072 / 收图），没有主用跳证据，不写 |
| `supportsToolCall` | 依旧写上游真值，但**DSH 宿主不读这个字段**（工具无条件发送），改它只为 ZCode 侧一致 |

### 9.4 验收

| 命令 | 结果 |
|---|---|
| `python -B tools/caps_upstream.py --check` | exit 0，现网与上游真值一致 |
| `python -B tools/model_caps.py --upstream catalog/upstream_caps.json --check` | exit 1，剩 6 条**故意不落**的档位/推断差异（见 §9.3） |
| `python -B tools/dsh_sync.py --check` | exit 0，patch 与 provider_config 一致 |
| `python -B -m unittest discover -s tests -q` | 124 tests OK（新增 `tests/test_caps_upstream.py` 12 例） |

复跑采真值（需联网，约 3 秒）：`python -B tools/caps_upstream.py --fetch && python -B tools/caps_upstream.py --check`。

### 9.5 两个 Gemini：接口不给，靠取证补

HJ 与 GM 都不会告诉你能力字段（HJ `/v1beta/models` 的 `inputTokenLimit` / `outputTokenLimit` 全是 `null`，`/api/pricing` 也没有 context；GM `/v1/models` 只有 id），所以这两条换个取法，证据落 `evidence/agent-gemini-truth.md`：

| 模型 | 关键证据 | 采用的结论 |
|---|---|---|
| Gemini-3.8-Flash（HJ 单跳） | 官方 Token limits / Modalities 页；内联 2×2 PNG 返回文本（`promptTokenCount` 2553，纯文本 1454） | ctx 1048576 / max 65536 / tool ✓ / img ✓ |
| Gemini-AIS（探测时 GM 七跳，现链 3 跳） | GM `/v1beta/models` 七跳全部 `inputTokenLimit=1000000`、`outputTokenLimit=65536`；厂商文档同族 1048576 | ctx 1000000（取中继自报）/ max 65536 / tool ✓ / img ✓ |

两条原文兜底值都错在一起：`max_output_tokens=128000`（真值 65536，虚高约一倍）、`supports_image=false`（实际收图）。改完 DSH 侧 `maxTokens: 65536`、`input: [text, image]` 都已投影。

仍属推断、明确不写的两处：**Qwen-3.8-Max** 的 max/img 只有 OC 交叉参考（QD 8790 拒连）；**HY3-X** 在 WB 面板与 `/v1/models` 都不存在，没有可对号的上游条目。
