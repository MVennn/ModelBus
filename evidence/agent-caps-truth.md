# ZCode 20 个模型能力字段真值取证

> **一句话**：11 条缺 `properties` 的模型里只有 3 条能从仓里的 `providerSiteRules`/`modelRules` 拿到实测真值，其余 8 条在全仓无任何专属规则，只能标 `none`；9 条已有 `properties` 的模型里 6 条与 site rule 有出入，其中 DeepSeek-4.1-Flash 的 `max` 现网 128000、真值 384000。

---

## 1. 结论摘要

| 项 | 数 | 说明 |
| --- | --- | --- |
| 现网 `providerModelRules` | 20 | opencode-go-chat 3 / -free 5 / -fast 12 |
| 有 `properties`（已取证过） | 9 | 本次做交叉核对 |
| 缺 `properties`（被通配兜住） | 11 | 本次逐条取证 |
| `source=site-rule`（置信 high） | 3 | DeepSeek-4.1-Flash、Qwen-3.8-Flash、GLM-5.3-Flash |
| `source=builtin-family`（medium） | 4 | Qwen-3.8-Max、MiniMax-M3.1-Flash、MiMo-2.6-Flash、MiMo-2.6-Pro |
| `source=current`（low） | 5 | HY3、HY4-Free、HY4、HY3-X、Space-Bunny |
| `source=none`（无法取证） | 8 | Gemini×2、Beam、Conatus、Iceman、Claude-Haiku-5.5、Muse-Spark1.3、GPT-6-Luna |
| `--check` 差异 | 15 | exit 1 |

11 条缺 `properties` 的模型里，取证成功 **3 条**（Qwen-3.8-Flash high、Qwen-3.8-Max medium、MiMo-2.6-Flash medium），其余 8 条 `none`。

---

## 2. 取证口径（为什么过去一直没命中）

匹配三要素来自 `third-party/zcode/model-config.ts`：

- `matchesRule`（`model-config.ts:544-546`）：`new RegExp("^(?:" + pattern + ")$", ignoreCase ? "i" : undefined).test(value)` —— **整串全匹配**；
- `modelMatch` 走 `matchesRule(..., true)`（`model-config.ts:408`，忽略大小写），`apiTypeMatch` / `baseUrlMatch` 大小写敏感（`:413`、`:417`）；
- `normalizeBaseURLForRuleMatch`（`model-config.ts:548-559`）去尾部斜杠，base 解析失败则不参与 site 匹配。

过去拿**显示别名**（`DeepSeek-4.1-Flash`）和**本地 base**（`http://127.0.0.1:7863/v1`）去比，而 `providerSiteRules` 要的是上游 id（`deepseek-v4\.1-flash`）与上游地址（`https://opencode\.ai/zen/go/v1/?`），三条规则里能命中的几乎只有 index 0-24 那 25 条上游规则 —— 所以 11 条一直落到 `modelRules[0]` 的通配 `.*`（ctx 1000000 / max 128000 / tool true / img false）。

本次解析链路：`~/.zcode/v2/model-alias-map.json` 取 `base_model` + `chain[]`，每跳 `protocol` → apiType（chat→openai-chat-completions / messages→anthropic-messages / responses→openai-responses），再拿三元组打 `providerSiteRules`。多跳按主 channel 优先、其余按 chain 顺序，冲突记 `conflicts`。

来源优先级：`site-rule(high)` > `builtin-family / builtin-exact(medium/low)` > `current(low)` > `none`。**只命中通配 `.*` 不算证据**（否则 20 条全被 1000000/128000 污染，正是这次要修的病）。

---

## 3. 11 条缺 `properties` 的模型逐条结论

### 3.1 取证成功（3 条）

#### Qwen-3.8-Flash — `source=site-rule` / confidence=high

- base_model：`Qwen3.8-Flash`
- 主跳：`QD http://127.0.0.1:8790/v1`，protocol `chat`
- 次跳：`OC https://opencode.ai/zen/go/v1`，protocol `messages` → apiType `anthropic-messages`
- 命中规则 `providerSiteRules[19]`：`modelMatch=qwen3\.8-flash`，`apiTypeMatch=anthropic-messages`，`baseUrlMatch=https://opencode\.ai/zen/go/v1/?`
- 真值：ctx **1000000**、max **131072**、img **true**、reasoning `[low, medium, xhigh]`
- 为什么不命中：主跳是本地 QD（`127.0.0.1:8790`），本地 base 永远打不中上游规则；必须沿 chain 走到第 1 跳 OC 并用 `messages` 协议才命中。
- 建议值：照抄 site rule；`supportsToolCall` site 不给，保留现网 `true`。

#### Qwen-3.8-Max — `source=builtin-family` / confidence=medium

- base_model：`Qwen3.8-Max`
- 主跳（唯一跳）：`QD http://127.0.0.1:8790/v1`，protocol `chat`
- 命中 `modelRules[63]`：`.*qwen3\.8-(?:max|flash).*` → max **131072**、img **true**、reasoning `[low, medium, xhigh]`
- **ctx 没有证据**：`modelRules[0]` 通配给的 1000000 已剔除，输出 `null`
- 为什么不命中：alias-map 里该模型只有 QD 一跳，没有 OC 跳可走，所以拿不到 `providerSiteRules[18]`（`qwen3\.8-max` + anthropic @ opencode → ctx 1000000 / max 131072 / img true）。
- 建议值：max 131072 / img true 按族级规则写入（medium）；ctx 建议 1000000（依据 `templateRules[opencode-go-messages]` 收录口径 + site rule 18，但那是**推断**，不写进 catalog，只进 notes）。

#### MiMo-2.6-Flash — `source=builtin-family` / confidence=medium

- base_model：`mimo-v2.6-flash`
- 主跳：`OC https://opencode.ai/zen/go/v1`，protocol `chat` → apiType `openai-chat-completions`
- 命中 `modelRules[77]`：`.*mimo-v2\.6-(?:pro|flash).*` → ctx **1000000**、max **131072**、img **true**、reasoning `[disabled, enabled]`
- 为什么不命中：base / apiType 都对，但 54 条 site 规则里只有 `mimo-v2\.5`（index 11），没有 `mimo-v2.6`；族级规则是唯一证据。
- 建议值：照抄族级规则（medium）；`supportsToolCall` 无证据 → `null`。

### 3.2 无法取证（8 条，输出 `null`，不给编造数字）

| display | base_model | 主跳 base / protocol | site 无命中的直接原因 | 建议 |
| --- | --- | --- | --- | --- |
| Gemini-3.8-Flash | `[福利]gemini-3.8-flash` | `https://api.gemai.cc/v1` / chat | 54 条 site 规则没有任何 gemini 条目，也没有 `api.gemai.cc` 这个 base；且 `[福利]` 是本地前缀 | 保留现值 / 打问号 / 人工补 |
| Gemini-AIS | `ais-gemini-3-flash-preview` | `https://catiecli.sukaka.top/v1` / chat（7 跳同 base，7 个不同 base_model） | 同上，无 gemini 规则、base 不在规则表 | 保留现值 / 打问号 / 人工补 |
| Beam | `beam-free` | `https://opencode.ai/zen/go/v1` / messages | base 与 apiType 都对，但没有 `beam` 的 modelMatch（25 条族规则只覆盖 glm-/deepseek-/kimi-k2/qwen/mimo-） | 保留现值 / 打问号 / 人工补 |
| Conatus | `qiniu/conatus-free` | `https://api.qnaigc.com/v1` / messages | 规则表里没有 `api.qnaigc.com` 这个 base | 保留现值 / 打问号 / 人工补 |
| Iceman | `iceman-contributor-free` | `https://opencode.ai/zen/go/v1` / chat | base/apiType 都对，但没有 `iceman` 的 modelMatch | 保留现值 / 打问号 / 人工补 |
| Claude-Haiku-5.5 | `claude-haiku-5-5` | `https://opencode.ai/zen/go/v1` / messages | site 只有 `.*claude-.*` @ `api.anthropic.com`（base 不符）；`modelRules` 只有 `claude-haiku-4[.-]5`，5.5 不匹配 | 保留现值 / 打问号 / 人工补 |
| Muse-Spark1.3 | `muse-spark-1.3-contributor` | `https://opencode.ai/zen/go/v1` / messages | 全仓无 muse 规则 | 保留现值 / 打问号 / 人工补 |
| GPT-6-Luna | `gpt-6-luna` | `https://opencode.ai/zen/go/v1` / messages | site 有 `gpt-5\.6-luna`（responses），model 名不同；`modelRules[26]` 是 `gpt-5\.6`、`[28]` 是 `gpt-6-astra`，都不匹配 `gpt-6-luna` | 保留现值 / 打问号 / 人工补 |

这 8 条的 `reasoning_values` 仍输出现网值（档位不是数字，不算编造），`field_sources` 标 `current`；4 个能力字段一律 `null`。

---

## 4. 9 条已有 `properties` 的交叉核对

| display | base_model | 主/末跳 base | 现网 ctx / max / img / tool | site/族规则真值 | 结论 |
| --- | --- | --- | --- | --- | --- |
| DeepSeek-4.1-Flash | `deepseek-v4.1-flash` | 第 1 跳 `https://opencode.ai/zen/go/v1` chat | 1000000 / **128000** / true / true | `providerSiteRules[7]`：1000000 / **384000** / true，rl `[low,high,max]` | **max 不一致**（差异 256000）；**reasoning 多一档 `disabled`**；ctx/img 一致 |
| HY3 | `hy3` | `http://127.0.0.1:7863/v1`（3 跳全 WB） | 192000 / 64000 / true / true | 无命中；参考 `providerSiteRules[14]`（hy3 @ OC）：256000 / 128000 / **false** | 现网走 WB 本地，site 14 不适用；若切 OC 通道需改成 256000/128000/img false |
| HY4-Free | `hy4free` | `http://127.0.0.1:7863/v1` | 960000 / 64000 / true / true | `providerSiteRules[13]` 是 `hy4-preview`：1024000 / 64000 / **false** | base_model 不是 `hy4-preview`，不命中；ctx/img 有出入，标参考 |
| HY4 | `hy4std` | `http://127.0.0.1:7863/v1` | 960000 / 64000 / true / true | 同上（`hy4-preview`） | 同上 |
| GLM-5.3-Flash | `glm-5.3-flash` | 第 2 跳 `https://opencode.ai/zen/go/v1` chat | 1000000 / 131072 / true / true | `providerSiteRules[0]`：1000000 / 131072 / true，rl `[low,high,max]` | **完全一致**（唯一一条四项全对的） |
| MiniMax-M3.1-Flash | `minimax-m3.1-flash` | 主跳 WB，末跳 OC chat | 1000000 / **128000** / true / true | `modelRules[51]` `.*MiniMax-M3.*`：max **32000**、img true（无 ctx）；`providerSiteRules[15]` 是 `minimax-m3`：1000000 / 131072，但 `minimax-m3` 整串不匹配 `minimax-m3.1-flash` | **max 不一致**（128000 → 32000，builtin-family）；ctx 1000000 与 site 15 数值一致但不算命中 |
| MiMo-2.6-Pro | `mimo-v2.6-pro` | 主跳 WB，第 1 跳 OC chat | 1000000 / **128000** / true / true | `modelRules[77]`：1000000 / **131072** / true，rl `[disabled,enabled]` | **max 差 3072**；**reasoning 7 档 → 2 档**（不一致） |
| HY3-X | `hy3-x` | `http://127.0.0.1:7863/v1` | 192000 / 64000 / true / true | 无命中 | 保留现网值（low） |
| Space-Bunny | `space-bunny` | `http://127.0.0.1:7863/v1` | 1000000 / 128000 / true / true | 无命中 | 保留现网值（low）；注意它的 1000000/128000 恰好等于通配值，无法区分是人工填的还是被通配污染的 |

`--check` 差异 15 条（exit 1），全部集中在：DeepSeek-4.1-Flash（2）、Qwen-3.8-Max（2）、Qwen-3.8-Flash（4）、MiniMax-M3.1-Flash（1）、MiMo-2.6-Flash（4）、MiMo-2.6-Pro（2）。HY3/HY4/HY3-X/Space-Bunny 零差异（因为来源就是 current 本身）。

---

## 5. 实测命令与原始输出

工具：`tools/model_caps.py`（解析器 + CLI）。所有命令在仓根 `F:/Project/ModelBus` 执行。

### 5.1 主表（默认输出）

```
$ python -B tools/model_caps.py
display             base_model                  apiType                  ctx      max     img  tool  reasoningCount  source          confidence
------------------  --------------------------  -----------------------  -------  ------  ---  ----  --------------  --------------  ----------
DeepSeek-4.1-Flash  deepseek-v4.1-flash         openai-chat-completions  1000000  384000  yes  yes   3               site-rule       high
Gemini-3.8-Flash    [福利]gemini-3.8-flash        openai-chat-completions  -        -       -    -     4               none            none
Gemini-AIS          ais-gemini-3-flash-preview  openai-chat-completions  -        -       -    -     4               none            none
HY3                 hy3                         openai-chat-completions  192000   64000   yes  yes   2               current         low
HY4-Free            hy4free                     openai-chat-completions  960000   64000   yes  yes   1               current         low
Beam                beam-free                   anthropic-messages       -        -       -    -     5               none            none
Conatus             qiniu/conatus-free          anthropic-messages       -        -       -    -     2               none            none
Iceman              iceman-contributor-free     openai-chat-completions  -        -       -    -     4               none            none
HY4                 hy4std                      openai-chat-completions  960000   64000   yes  yes   1               current         low
Qwen-3.8-Max        Qwen3.8-Max                 openai-chat-completions  -        131072  yes  -     3               builtin-family  medium
Qwen-3.8-Flash      Qwen3.8-Flash               anthropic-messages       1000000  131072  yes  -     3               site-rule       high
GLM-5.3-Flash       glm-5.3-flash               openai-chat-completions  1000000  131072  yes  yes   3               site-rule       high
MiniMax-M3.1-Flash  minimax-m3.1-flash          openai-chat-completions  1000000  32000   yes  yes   5               builtin-family  medium
MiMo-2.6-Flash      mimo-v2.6-flash             openai-chat-completions  1000000  131072  yes  -     2               builtin-family  medium
MiMo-2.6-Pro        mimo-v2.6-pro               openai-chat-completions  1000000  131072  yes  yes   2               builtin-family  medium
HY3-X               hy3-x                       openai-chat-completions  192000   64000   yes  yes   2               current         low
Claude-Haiku-5.5    claude-haiku-5-5            anthropic-messages       -        -       -    -     6               none            none
Muse-Spark1.3       muse-spark-1.3-contributor  anthropic-messages       -        -       -    -     5               none            none
GPT-6-Luna          gpt-6-luna                  anthropic-messages       -        -       -    -     6               none            none
Space-Bunny         space-bunny                 openai-chat-completions  1000000  128000  yes  yes   5               current         low
EXIT=0
```

表格后紧跟「无法取证（8 条）」与「仅有现网现值（5 条）」两段，每条给出 base_model / channel / 原因 / 建议（保留现值 / 打问号 / 人工补）。

### 5.2 `--check` 对比现网

```
$ python -B tools/model_caps.py --check
差异 15 条（current = 现网 provider_config，resolved = 解析真值）：
display             provider               field              current                                       resolved            source
------------------  ---------------------  -----------------  --------------------------------------------  ------------------  --------------
DeepSeek-4.1-Flash  opencode-go-chat       max_output_tokens  128000                                        384000              site-rule
DeepSeek-4.1-Flash  opencode-go-chat       reasoning_values   [disabled,low,high,max]                       [low,high,max]      site-rule
Qwen-3.8-Max        opencode-go-chat-fast  max_output_tokens  -                                             131072              builtin-family
Qwen-3.8-Max        opencode-go-chat-fast  supports_image     -                                             yes                 builtin-family
Qwen-3.8-Flash      opencode-go-chat-fast  context_window     -                                             1000000             site-rule
Qwen-3.8-Flash      opencode-go-chat-fast  max_output_tokens  -                                             131072              site-rule
Qwen-3.8-Flash      opencode-go-chat-fast  supports_image     -                                             yes                 site-rule
Qwen-3.8-Flash      opencode-go-chat-fast  reasoning_values   [disabled,low,medium,xhigh]                   [low,medium,xhigh]  site-rule
MiniMax-M3.1-Flash  opencode-go-chat-fast  max_output_tokens  128000                                        32000               builtin-family
MiMo-2.6-Flash      opencode-go-chat-fast  context_window     -                                             1000000             builtin-family
MiMo-2.6-Flash      opencode-go-chat-fast  max_output_tokens  -                                             131072              builtin-family
MiMo-2.6-Flash      opencode-go-chat-fast  supports_image     -                                             yes                 builtin-family
MiMo-2.6-Flash      opencode-go-chat-fast  reasoning_values   [disabled,minimal,low,medium,high,xhigh,max]  [disabled,enabled]  builtin-family
MiMo-2.6-Pro        opencode-go-chat-fast  max_output_tokens  128000                                        131072              builtin-family
MiMo-2.6-Pro        opencode-go-chat-fast  reasoning_values   [disabled,minimal,low,medium,high,xhigh,max]  [disabled,enabled]  builtin-family
EXIT=1
```

### 5.3 `--apply` 只写副本

```
$ cp "$HOME/.zcode/v2/provider_config.json" .work/provider_config.copy.json
$ python -B tools/model_caps.py --apply --target .work/provider_config.copy.json
... 18 处改动，7 个模型 ...
EXIT=0
```

只补写 `properties.contextWindow` / `supportsToolCall` / `inputFormat.supportsImage` 与 `optionSpecs.maxOutputTokens.max` / `reasoningLevel`；空容器不生成（`properties{}` / `inputFormat{}` 零个）；`reasoningLevel.map` 只在现网缺失时补写（内置 map 模板方言是 `{"k": v}`、现网是 `{k: v}`，直接覆盖会改变参数拼装）。指向真身被拒：

```
$ python -B tools/model_caps.py --apply --target ~/.zcode/v2/provider_config.json
拒绝写入 ...provider_config.json：--apply 只允许写副本
EXIT=1
```

### 5.4 单元测试

```
$ python -B tests/test_model_caps.py -q
Ran 21 tests in 0.036s
OK
EXIT=0

$ python -B -m unittest discover -s tests -q
Ran 112 tests in 6.201s
OK
EXIT=0
```

`discover` 会连带跑仓里既有测试（112 条中含本次新增 21 条），末尾那几行 WARN 来自仓内其它脚本（推理档位投影 5 个模型投影后为空、QD 价格源 127.0.0.1:8790 拒绝连接回落快照），与本次产物无关。

---

## 6. 复核要点与未决

1. **`supportsToolCall` 全仓无证据**：54 条 `providerSiteRules` 一律不给该字段，所以 site-rule 命中的三条也沿用现网 `true`（`field_sources` 标 `current`）。要真值只能靠上游 `/v1/models` 实测。
2. **MiniMax-M3.1-Flash 的 max 存疑**：族级 `modelRules[51]` 给 32000，而 site `[15]`（`minimax-m3`）给 131072；两者模型名不同族（3 vs 3.1），按当前口径取族级 32000（medium）。若确认 3.1 与 3 同代，应改判 131072。
3. **Qwen-3.8-Max 的 ctx 缺证据**：族级规则不给 ctx，site 18 走不到（alias 无 OC 跳）。catalog 里 `context_window=null`，notes 里写了推断值 1000000 与依据。
4. **HY3 / HY4 系列**：走 WB 本地 base，site 14/13 都要求上游 base 且 base_model 不同（`hy3` vs `hy4-preview`），只能沿用现值；等 WB 上游确认后再补。
5. **8 条 none**：不建议猜数，保留现值并在 catalog 里留 `null` 更安全 —— DSH 侧压缩阈值会退回通配口径，需要人工按上游文档补。

---
