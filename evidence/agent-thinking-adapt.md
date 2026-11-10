# 路 C｜thinking / reasoning 适配机制与新 gemini provider 能力判定（只读分片）

> **一句话**：新 `gemini` provider 是 DSH 直连的裸条目，当前**未声明任何思考能力**；静态证据只能判「未声明」，判「能不能思考」必须 1 次极小真实请求；确认支持就只在 `cordis.patch.yml` 手写 `reasoningEfforts`，不支持就保持裸条目（写了档位反而会让上游 400）。

---

## 0. 路径前缀与范围

| 前缀 | 展开 | 说明 |
|---|---|---|
| `MB/` | `F:\Project\ModelBus` | 真实项目根（`F:\Project\_merged\DeepseekHarness` 只是 junction 合并视图，视图根禁建产物） |
| `DSH/` | `~/.dsh` | DSH 宿主 profile / 凭据 / 补丁脚本树 |
| `ZC/` | `~/.zcode/v2` | ZCode 运行时配置树 |

本分片**只读**，未改任何配置 / `docs/` / `tests/` / `PROGRESS.md`，未重启任何长驻网关，未发任何真实 API 请求，未 `git add` / `commit` / `push`。凭据只以变量名 `GEMINI_API_KEY` / `ZCODE_GATEWAY_KEY` 出现，值从未读取、从未打印、从未写入任何文件。

---

## 1. 结论先行

| # | 结论 | 可复查证据 |
|---|---|---|
| C1 | **新 provider 是 DSH 直连，不是 ZCode 路由**：`gemini` 独立 provider、模型 `ais-gemini-3.8-flash`、base `https://catiecli.sukaka.top/v1`、协议 `openai-completions`，整条只有 8 行且无任何思考字段 | `DSH/profiles/desktop/cordis.patch.yml:253-260`（L261 空行、L262 转到 `- insert:`）；`MB/` 全仓 grep `ais-gemini-3\.8-flash\|catiecli\|sukaka` = 0 hits |
| C2 | **它不进 ZCode 配置树、不进别名表**：`provider_config.json` / `model-alias-map.json` 里 `[Gg]emini\|cp:\|ais-` 均 0 hits；`model-alias-map.json` 全文也没有 `reasoning` / `thinking` / `optionSpecs` 字段，它是纯路由表 | `ZC/provider_config.json:1-10`（schemaVersion / providerOrder / providerConfigRules）、`ZC/model-alias-map.json:1-5`（version / generated_at / slot / models）、`ZC/model-alias-map.json:6-67`（DeepSeek 一条完整路由的形状：channel/upstream/base/protocol/price/group/fallbacks/chain/legacy_ids，无任何思考字段） |
| C3 | **「支持思考」要写 3 层，本项目新 provider 只需动第 3 层**：协议层字段由上游决定、ZCode 适配层是 `optionSpecs.reasoningLevel.{values,map}`、DSH 宿主 UI 层是 `reasoningEfforts` + `compat.thinkingFormat` | `MB/docs/UPSTREAM.md:89-94`、`MB/docs/MODEL-PROVIDERS.md:77`、`DSH/profiles/desktop/cordis.patch.yml:66-72`（详见 §3） |
| C4 | `optionSpecs.reasoningLevel.map` **只存在于 `provider_config.json`**；`model-alias-map.json` 里没有，`cordis.patch.yml` 里也没有（后者是投影后的 `reasoningEfforts`） | `ZC/provider_config.json:197,209,351,363,375` 全文 `"map"\s*:` 恰好 5 hits 且全是 `"{}"`；`MB/tools/dsh_sync.py:243-257` 是 map → reasoningEfforts 的唯一投影函数 |
| C5 | **手写字段不会被每日同步冲掉**，因为 `dsh_sync.py` 只重建 `zcode-*`、原样保留其它 provider；但若父代理把模型挪进 `zcode-main`，下一次 `--apply` 会重建该 route 并冲掉手写字段 | `MB/tools/dsh_sync.py:344-362`（L349-353 `preserved = {… if not str(key).startswith("zcode-")}`、L354 `merged_providers = {**routes, **preserved}`）；`MB/tools/dsh_sync.py:12-15` 文档串同口径 |
| C6 | **额度风险（最重要）**：保持独立 `gemini` provider 时不会被每日探针烧额度；一旦挪进 `zcode-*`，立刻进入 `--changed` 的新增指纹必打清单，且 `--deep` 还会额外再打一次，默认 `max_tokens=768` | `MB/tools/model_stream_check.py:126-155`（L133-137 只认 `id=llm-pi-ai` 且 `pid.startswith("zcode-")`）、`:72-74`（LEVEL_ORDER / PROMPT / MAX_TOKENS=768）、`:396-403`（deep_explore 额外打 `force_effort="high"`）、`:477-479`、`:494`；`MB/docs/MODEL-STREAM.md:27-29,40-41,49-57,59-62` |
| C7 | **历史所有 CP/Gemini 结论一律已过期**，不能当新 provider 的能力证据 | `MB/CHANGELOG.md:20-28`（L22 反代下线、L23 主力收敛、L24 三配置删 4 型号、L26 删 `docs/MODEL-PROVIDERS.md` §4.11、L27 五篇 Document 归档、L28 验收 exit 0）；详见 §5 |
| C8 | **本分片不替父代理发探测**：只给 1 次 `max_tokens=16` 的确切请求体与判据表，实际请求由父代理决定 | §6 档 3；历史极小请求模板 `MB/evidence/agent-gemini-runtime.md:11-12,123-141` |

---

## 2. 新 provider 现状（静态事实，逐行）

`DSH/profiles/desktop/cordis.patch.yml:253-260` 原文：

```yaml
      gemini:                                  # L253
        displayName: Gemini                   # L254
        apiKeyEnv: GEMINI_API_KEY             # L255
        api: openai-completions               # L256
        baseURL: https://catiecli.sukaka.top/v1   # L257
        models:                               # L258
          - id: ais-gemini-3.8-flash          # L259
            name: ais-gemini-3.8-flash        # L260
```

- **无** `contextWindow` / `maxTokens` / `input` / `reasoningEfforts` / `compat` / `reasoningLevel`（`DSH/profiles/desktop/cordis.patch.yml:259-262`，L261 空行、L262 已是下一个 patch 条目 `- insert:`）。
- 该条目挂在 `- id: llm-pi-ai` → `config.providers` 下（`DSH/profiles/desktop/cordis.patch.yml:39-41`）；同级的 `zcode-main` 头在 `:42-58`（L56 `api: openai-completions`、L57 `baseURL: http://127.0.0.1:7871/v1`、L58 `apiKeyEnv: ZCODE_GATEWAY_KEY`）。**两者不同源**：新 provider 是外部 HTTPS 直连，zgate 那套「无 Authorization 头、key 由网关托管」不适用（`DSH/profiles/desktop/cordis.patch.yml:57-58` vs `:255-257`；`MB/tools/model_stream_check.py:234-238` 无 Authorization 头）。
- `DSH/` 全树 `*.yml` grep `[Gg]emini` 仅 4 hits，就是 L253/254/259/260 → 没有任何第二处声明。
- 凭据名 `GEMINI_API_KEY` 在 `DSH/.credentials.yaml:22` 出现 1 次；本分片只记录 key 名与行号，值未读。

---

## 3. 三层字段：改哪一层才算「声明支持思考」

### 3.1 协议层（wire，上游认什么就发什么）

| 目标协议 | 写入请求体的字段 | 证据 |
|---|---|---|
| `anthropic-messages` | `thinking: {type:'adaptive'}` + `output_config: {effort}` | `MB/docs/UPSTREAM.md:91` |
| `openai-responses` | `reasoning: {effort}` | `MB/docs/UPSTREAM.md:92` |
| `openai-chat-completions` | `reasoning_effort` | `MB/docs/UPSTREAM.md:93`；新 provider 的 `api: openai-completions` 落这一档（`DSH/profiles/desktop/cordis.patch.yml:256`） |
| 关掉 | anthropic → `thinking:{type:'disabled'}`；OpenAI → `none` | `MB/docs/UPSTREAM.md:94` |

- ZCode 内置通用规则会**无条件**给所有 chat 协议模型注入四字段 `{"thinking":{"type":"enabled"},"enable_thinking":true,"reasoning_effort":"high","reasoning":{"effort":"high"}}`，不检查模型是否支持，上游不认其中任一个就 400（`MB/docs/PITFALLS.md:49-62`；`MB/third-party/zcodium/zcode-builtin-reasoning-rules.json:30-36` 的 L34 是四字段 map 原文）。
- 协议→字段的判定工具与最小正确写法：`MB/docs/UPSTREAM.md:318-347`（L328-340 四条 `node third-party/zcodium/reasoning-rules.js map …` 命令及输出，L343-345 `PROTOCOL_FIELDS` 三协议映射）；`MB/third-party/zcodium/reasoning-rules.js:17,53,64,68,134,141,170`。
- **响应侧**（判「能不能思考」看这些字段）：`reasoning_content` / `reasoning` / `thinking` / `reasoningContent` / `thinking_content` / `reasoning_details`（`MB/tools/model_stream_check.py:198-207` 的 L203 键集合；`MB/tools/model_stream_check.py:210-215` 加密思考分流）；桥的转换在 `MB/gateways/zgate/internal/bridge/bridge.go:447-449`（`thinking_delta` → `reasoning_content`）、`:989-991`（anthropic `thinking` 块）、`:1077-1085`（responses `reasoning.summary`）；`MB/gateways/zgate/internal/router/router.go:1181-1186` 的字段白名单同口径。

### 3.2 本项目 / ZCode 适配层（`optionSpecs.reasoningLevel`）

- 精确字段路径：`config.modelConfigRules.providerModelRules[].config.optionSpecs.reasoningLevel.{values,map}`（`MB/docs/MODEL-PROVIDERS.md:72-78`，L77 列全 `modelId / providerId / config.enabled / config.properties / config.optionSpecs`）；`MB/docs/MODEL-PROVIDERS.md:63` 把它列为「换供应商不用改的三件事」之一。
- `values` 决定 UI 下拉，**末位就是默认档**（`MB/docs/MODEL-PROVIDERS.md:557-569`，L559「只由 values 生成，与上游能力无关」、L566-569「`values.at(-1)`；low/high/max → max，low/high → high」）。写错顺序等于改费用与首字延迟。
- `map` 是**一段 JS 表达式**，求值成 JSON 对象再发出去，作用域只有 `reasoningLevel` 与 `maxOutputTokens` 两个自由变量（`MB/docs/MODEL-PROVIDERS.md:518-519`；`MB/providers/workbuddy/zcode_effective_body.js:27-30`、`:168` 用 `new Function('reasoningLevel', 'maxOutputTokens', <map 表达式>)` 求值；`MB/memories/zcode-open-source-upstream.md:28` 同口径）。
- 六种写法（完整表）：`MB/docs/MODEL-PROVIDERS.md:521-528`，逐行是 `"{}"` / `'{"reasoning_effort":reasoningLevel}'` / `'{"thinking":{"type":"disabled"}}'` / `'{"thinking":{"type":"enabled"},"reasoning_effort":reasoningLevel}'` / `'{"thinking":{"type":"enabled"}}'` / 不配（吃默认四字段）。
- 三个同步脚本自动写这些字段：`MB/providers/workbuddy/workbuddy_zcode_sync.py:312-333`（L325-329 三个 `variant_maps`，L332 写 `["map"]`）；`MB/providers/opencode-go/ops/go_model_sync.py:567-598`（L579 `spec["map"] = '{"reasoning_effort":reasoningLevel}'`、L581 `spec["map"] = "{}"`、L586 挂 `optionSpecs`；L573 注释「只能 map="{}"，档位是装饰项，故不写 values」）；`MB/providers/qoder/qoder_zcode_sync.py:273-283`。
- **`model-alias-map.json` 里没有这一层**：它是纯路由表（`ZC/model-alias-map.json:6-67`），`reasoning` / `thinking` / `optionSpecs` 全文 0 hits。

### 3.3 DSH 宿主 UI 层（新 provider 唯一要动的地方）

| 字段 | 作用 | 证据 |
|---|---|---|
| `models[].reasoningEfforts: {<档位>: <wire 值>}` | **声明该模型支持思考 + UI 档位下拉**；宿主把选中档位写进请求的 `reasoning_effort` | `DSH/profiles/desktop/cordis.patch.yml:66-70`（DeepSeek 四档）、`:123-125`（Iceman 两档）、`:247-252`（Space-Bunny 五档）；`MB/tools/dsh_sync.py:243-257` |
| `models[].compat.thinkingFormat: deepseek` | 告诉宿主按 deepseek 那套组思考字段；只在「有 `off: disabled` 且上游认 `thinking`」时配 | `DSH/profiles/desktop/cordis.patch.yml:71-72`、`:126-127`；`MB/tools/dsh_sync.py:249-255` |
| `config.providers[].apiKeyEnv / api / baseURL` | 鉴权与协议（不是思考字段） | `DSH/profiles/desktop/cordis.patch.yml:255-257` |
| `agent-default-model.config.reasoningEffort: high` | **全局**默认档，不是单模型声明 | `DSH/profiles/desktop/cordis.patch.yml:4-9`（L9） |
| `ui-chat.config.{transcriptView,collapseTiming,foldedReplies,performanceUsage}` | 只控制思考过程**怎么显示**，不控制能力 | `DSH/profiles/desktop/cordis.patch.yml:20-29`（L23-29） |
| `reasoningDisplay: continuous` | 思考文字连续出现 vs 步进；合法值 `continuous`/`stepped` | `DSH/profiles/desktop/cordis.patch.yml:370-374`（L373 注释、L374 值）；schema 在 `DSH/profiles/desktop/node_modules/dsh-claude-style/lib/host/settings.js:55-57,252` |
| 宿主模型类型 `reasoning?: { efforts, defaultEffort? }` | provider 声明档位的宿主侧类型 | `DSH/profiles/desktop/node_modules/dsh-better-sidebar/lib/types/sidechat-core.d.ts:228-243`（L235-242） |

- **默认档 = 模型表 efforts 末位**，由 `DSH/tools/patch-claude-style-effort.mjs:20-51` 保证（L28-29 `g=f.efforts[f.efforts.length-1].id`、L33-34 切模型也带上末位档、L42-44 去掉合成的 `Default` 伪档、L48-49 去掉 `Default` 标签）。所以**一旦写了 `reasoningEfforts`，宿主立刻会真的发 `reasoning_effort`** —— 这是「不支持就别写」的硬理由（`MB/docs/MODEL-STREAM.md:14-18`）。
- 档位合法值与宿主 `THINKING_LEVELS` 一致：`["off","minimal","low","medium","high","xhigh","max"]`（`MB/tools/model_stream_check.py:71-72`）；投影时只保留白名单内档位（`MB/tools/dsh_sync.py:71`、`:248`）。

---

## 4. 完整配置样例（脱敏）

> 三个样例所在 JSON 段是 `modelConfigRules.providerModelRules[]`，**不含任何凭据**；apiKey 只在 `config.providerConfigRules.providerRules[].config.access.apiKey`（`MB/docs/MODEL-PROVIDERS.md:76`、`MB/AGENTS.md:§2`），本分片未读取。

### 样例 1｜真档位 + deepseek 格式（"支持思考"的完整形状）

ZCode 侧 `ZC/provider_config.json:109-134`：

```json
{
  "modelId": "DeepSeek-4.1-Flash",
  "config": {
    "enabled": true,
    "properties": {
      "contextWindow": 1000000,
      "supportsToolCall": true,
      "inputFormat": { "supportsImage": true }
    },
    "optionSpecs": {
      "maxOutputTokens": { "max": 128000 },
      "reasoningLevel": { "values": ["disabled", "low", "high", "max"] }
    }
  },
  "providerId": "opencode-go-chat"
}
```

→ 投影成 DSH 侧 `DSH/profiles/desktop/cordis.patch.yml:60-72`：

```yaml
- id: DeepSeek-4.1-Flash
  contextWindow: 1000000
  maxTokens: 128000
  input: [text, image]
  reasoningEfforts:
    off: disabled
    low: low
    high: high
    max: max
  compat:
    thinkingFormat: deepseek
```

投影规则原文：`MB/tools/dsh_sync.py:243-257`（L245-246 `map == "{}"` 直接返回空、L249-255 含 `disabled` 时补 `off` 且挂 `compat.thinkingFormat: deepseek`、L256-257 否则逐档自映射）。**注意 `values` 里没有 `map`**，即「不配 map → 吃 ZCode 默认四字段」（`MB/docs/MODEL-PROVIDERS.md:528`）。

### 样例 2｜空 map 退化（"不支持思考参数"的完整形状）

`ZC/provider_config.json:203-211` Conatus（最简）：

```json
{
  "modelId": "Conatus",
  "config": {
    "enabled": true,
    "optionSpecs": { "reasoningLevel": { "map": "{}" } }
  },
  "providerId": "opencode-go-chat-free"
}
```

`ZC/provider_config.json:184-201` Beam（上游声明了档位、但 map 空 → 档位是装饰项）：

```json
{
  "modelId": "Beam",
  "config": {
    "enabled": true,
    "optionSpecs": {
      "reasoningLevel": {
        "values": ["low", "medium", "high", "xhigh", "max"],
        "map": "{}"
      }
    }
  },
  "providerId": "opencode-go-chat-free"
}
```

- 全文 `"map"\s*:` 恰好 5 hits：`ZC/provider_config.json:197,209,351,363,375`，**全是 `"{}"`**，没有第二种表达式形态（其它非 `"{}"` 的 map 写法只存在于脚本模板 `MB/docs/MODEL-PROVIDERS.md:524-527` / `MB/providers/workbuddy/workbuddy_zcode_sync.py:325-329` / `MB/providers/opencode-go/ops/go_model_sync.py:579`，当前运行时一份都没落盘）。
- 空 map 的 DSH 结果是**完全不写** `reasoningEfforts`（`MB/tools/dsh_sync.py:12-14,245-246`；`MB/docs/TOOLS.md:35`；`MB/docs/UPSTREAM.md:320-322`：躲开 400 但退到上游默认档）。当前 5 个空 map 模型见 `MB/docs/MODEL-PROVIDERS.md:530-531`。
- 对照一个「只发 `reasoning_effort`」的 DSH 形状（无 `compat`）：`DSH/profiles/desktop/cordis.patch.yml:241-252` Space-Bunny 五档 `low/medium/high/xhigh/max`。

### 样例 3｜旧 Gemini 历史（**已过期**，仅说明历史口径）

`ZC/provider_config.json.bak-20261110-gemini-removal:143-164`：

```json
{
  "modelId": "Gemini-3.6-Flash",
  "config": {
    "enabled": true,
    "properties": {
      "contextWindow": 262144,
      "supportsToolCall": true,
      "inputFormat": { "supportsImage": false }
    },
    "optionSpecs": {
      "maxOutputTokens": { "max": 16384 },
      "reasoningLevel": { "map": "{}" }
    }
  },
  "providerId": "opencode-go-chat"
}
```

→ `DSH/profiles/desktop/cordis.patch.yml.bak-20261110-gemini-removal:71-75`：

```yaml
- id: Gemini-3.6-Flash
  contextWindow: 262144
  maxTokens: 16384
  input: [text]
```

同批 4 条旧 Gemini 规则全部 `map="{}"` 且无 `values`：`:159`(3.6) / `:181`(3) / `:203`(3.5-Lite) / `:225`(3.1-Lite)；DSH 侧 4 条也全是裸条目：`cordis.patch.yml.bak:71-75,76-80,81-84+`。**历史口径 = 刻意不暴露思考档位**，与新 provider 当前的裸条目形状一致 —— 但这是「旧链路的历史选择」，不能推出新 `ais-gemini-3.8-flash` 的能力（`MB/CHANGELOG.md:22-24`）。

---

## 5. 历史结论核对：哪些已过期

| 文件:行号 | 历史结论 | 现状 |
|---|---|---|
| `MB/CHANGELOG.md:20-28` | 2026-11-10 批次：L22 删 CP upstream 与 cliproxyapi child 8317、`third-party/cliproxyapi/` 移到 `.work/cliproxyapi-removed-20261110/`；L23 `MAIN_ORDER` 去 4 条 `chat:cp:gemini-*`、`MAIN_UPSTREAM_HINTS=("deepseek",)`；L24 三配置删 4 型号 + `cp:` legacy 键、各留 `.bak-20261110-gemini-removal`；L26 删 `docs/MODEL-PROVIDERS.md` §4.11；L27 五篇 CP/Gemini Document 归档 | **现行口径**，本分片据此标过期 |
| `MB/evidence/agent-adaptation.md:248` | 旧 CP `Gemini-3.6-Flash` 响应 `{"id":"kJDxas6pBKrv694Phun2-QY","object":"chat.completion","model":"gemini-3.6-flash",…,"reasoning_content"…}` | **已过期**（CP 链路已下线）。但它是「响应侧确实存在 `reasoning_content`」的最强历史证据，可作先验假设，不可作新 provider 判定 |
| `MB/evidence/agent-admission-price.md:11-12` | Gemini 4 Argon 价格 / 主力 = DeepSeek + 4 条 CP Gemini 0.00 | **已过期**（价格与主力表均已删） |
| `MB/evidence/agent-gemini-logs.md:1-3,60,191,203` | CP Gemini hop 的 403/503/429/502、`streamGenerateContent` 403 `Verify your account to continue.` | **已过期**（CP 链路） |
| `MB/evidence/agent-gemini-runtime.md:1-12,123-141` | 走 zgate `127.0.0.1:7871`、1 次 `max_tokens=16` 请求、`ttfb_ms=2014` | **链路已过期，但请求体模板可复用**：L126 `{"model":"<MODEL>","messages":[{"role":"user","content":"hi"}],"stream":true,"max_tokens":16}`；新探测须换 base 与鉴权（§6 档 3） |
| `MB/evidence/agent-gemini-channels-local.md:41-51` | CLIProxyAPI README「Gemini 3.8 Flash 是 Google 面向长周期软件工程与智能体工作流推出的最新 Flash 模型」 | **型号族描述，不是思考能力声明**；且 `third-party/cliproxyapi/` 已被 `CHANGELOG.md:22` 移走 |
| `MB/memories/opencode-go-zcode-models.md:35,54,68` | 空 map 口径 / 探测要带 ZCode 真 body / `gemini-4-argon-contributor` 401 | 前两条**机制仍有效**；`:68` 的 gemini-4-argon 具体型号**已过期**（历史副本，`~/.dsh/AGENTS.md:§8` 要求勿再改勿再读 `~/.zcode/cli/memories/`） |
| `MB/memories/beam-free-thinking-param-fix.md:13-27` | beam-free 400 根因 = 内置通用规则无条件发四字段；解法 `map="{}"` | **机制仍有效**，是「不支持就别写档位」的实测依据（`MB/docs/PITFALLS.md:49-77` 同口径） |
| `MB/docs/MODEL-PROVIDERS.md:211` | `gemini-4-argon-contributor` 需 OpenCode Console Privacy 开关 | **已过期**（该型号不在现役表；全文 18 个 gemini hit 均为泛化提及，无任何现役 Gemini 思考档位声明） |
| `MB/PROGRESS.md:2067` | 「思考档位按 ZCode 有效 reasoningLevel.map 投影：`map="{}"` 的模型不写 `reasoningEfforts`；disabled 档写 `off: disabled` 并配 `thinkingFormat: deepseek`」 | **现行有效**，与 `MB/tools/dsh_sync.py:243-257` 一致 |

---

## 6. 能力判定：三档证据

### 档 1｜静态元数据（已完成，零调用）

- **证据**：`DSH/profiles/desktop/cordis.patch.yml:253-260` 裸条目；`ZC/provider_config.json` / `ZC/model-alias-map.json` 无该模型（§2）；`DSH/profiles/desktop/cordis.patch.yml:256` 协议 `openai-completions` → 若思考，wire 字段应是 `reasoning_effort`（`MB/docs/UPSTREAM.md:93`）；`MB/evidence/agent-gemini-channels-local.md:41-51` 只能对上型号族名字。
- **能证明**：该模型**当前未被声明**支持思考；不在 ZCode 适配链路；不在每日探针契约内（额度暂时安全）。
- **不能证明**：上游是否真的会吐 `reasoning_content`、是否接受 `reasoning_effort`、默认档是开还是关。**「未声明」≠「不具备」**（`MB/docs/MODEL-PROVIDERS.md:559` 明确说档位下拉与上游能力无关）。

### 档 2｜已有日志 / 历史响应里的 reasoning 字段（已查完，零调用）

- **证据**：
  - 旧 CP Gemini 响应含 `reasoning_content`：`MB/evidence/agent-adaptation.md:248`（HTTP 200 `application/json` `chat.completion`）。
  - 同项目另一个模型的 SSE 实测 `delta.reasoning_content:"Okay"`：`MB/evidence/agent-adaptation.md:243`、`:74`、`:55`。
  - 本项目桥能识别并统一这些字段：`MB/gateways/zgate/internal/bridge/bridge.go:447-449,989-991,1077-1085`；`MB/gateways/zgate/internal/router/router.go:1181-1186`。
  - 探针的「隐藏思考」判据正是「`no_reasoning` 模型强开 `high` 后 `reasoningChars>0`」：`MB/tools/model_stream_check.py:396-403`、`:198-207`。
- **能证明**：本项目有成熟的「响应侧思考字段」识别链路；同型号族在**另一条已下线链路**上吐过思考。
- **不能证明**：新 provider（不同 `baseURL`、不同 model id、不同鉴权、不同上游实现）也吐。`CHANGELOG.md:22` 已下线 CP 且 `third-party/cliproxyapi/` 已移走，**不允许跨链路迁移结论**。

### 档 3｜1 次最小真实请求（本分片只给方案，实际请求留给父代理）

**前置（只回 True/False，不回值）**：

```powershell
[bool](Get-Item Env:GEMINI_API_KEY -ErrorAction SilentlyContinue)
```

若为 False，父代理需自行决定如何从 `DSH/.credentials.yaml:22` 对应的宿主凭据存储注入环境变量；本分片不读取、不打印、不写入该值。

**请求体（1 次，`max_tokens=16`，与 `MB/evidence/agent-gemini-runtime.md:11,126` 的 16 token 口径一致；不带任何思考参数，避免上游不认 `reasoning_effort` 直接 400 白耗一次额度）**：

```json
{"model":"ais-gemini-3.8-flash","messages":[{"role":"user","content":"hi"}],"stream":false,"max_tokens":16}
```

**PowerShell（本机 runtime 为 native Windows PowerShell；只输出字段名与长度，不回显响应正文/凭据）**：

```powershell
$ErrorActionPreference = 'Stop'
if (-not (Test-Path Env:GEMINI_API_KEY)) { throw 'GEMINI_API_KEY 未注入环境变量' }
$body = '{"model":"ais-gemini-3.8-flash","messages":[{"role":"user","content":"hi"}],"stream":false,"max_tokens":16}'
$r = Invoke-WebRequest -UseBasicParsing -Uri 'https://catiecli.sukaka.top/v1/chat/completions' -Method Post -ContentType 'application/json; charset=utf-8' -Headers @{ Authorization = "Bearer $env:GEMINI_API_KEY" } -Body $body
"HTTP=" + $r.StatusCode
$o = $r.Content | ConvertFrom-Json
$m = $o.choices[0].message
[pscustomobject]@{
  model         = $o.model
  finish_reason = $o.choices[0].finish_reason
  message_keys  = @($m.PSObject.Properties.Name)
  content_len   = ([string]$m.content).Length
  usage         = ($o.usage | ConvertTo-Json -Compress)
} | ConvertTo-Json -Depth 4
$lens = @{}; foreach ($p in $m.PSObject.Properties) { if ($p.Name -ne 'content') { $lens[$p.Name] = ([string]$p.Value).Length } }; "field_lens=" + ($lens | ConvertTo-Json -Compress)
```

**bash 变体（二选一，只发一次；产物进真实项目 `.work/`）**：

```bash
mkdir -p .work/agent-thinking-probe
curl -sS -o .work/agent-thinking-probe/resp.json -w 'HTTP=%{http_code}\n' \
  -X POST 'https://catiecli.sukaka.top/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $GEMINI_API_KEY" \
  --data '{"model":"ais-gemini-3.8-flash","messages":[{"role":"user","content":"hi"}],"stream":false,"max_tokens":16}'
python -c "import json;d=json.load(open('.work/agent-thinking-probe/resp.json',encoding='utf-8'));m=d['choices'][0].get('message',{});print('model=',d.get('model'));print('finish_reason=',d['choices'][0].get('finish_reason'));print('message_keys=',list(m));print('field_lens=',{k:len(str(v)) for k,v in m.items() if k!='content'});print('content_len=',len(str(m.get('content') or '')));print('usage=',d.get('usage'))"
```

**判据表**：

| 观察 | 判定 | 下一步 |
|---|---|---|
| HTTP 200 且 `message_keys` 含 `reasoning_content` / `reasoning` / `thinking` 且对应 `field_lens>0` | **具备明文思考**，无需显式开档也会吐 | 走 §7 分支 A；档位 wire 值按 `MB/docs/UPSTREAM.md:93` 用 `reasoning_effort` |
| HTTP 200 且 `content_len=0`、`finish_reason=length`、思考字段长度 >0 | **思考吃光了 16 token 预算**，是「默认就在思考」的强证据 | 同上；注意 `MB/docs/MODEL-STREAM.md:59-62` / `MB/docs/QWEN.md:308-314` 的小预算陷阱 |
| HTTP 200 且只有 `reasoning_details[type=reasoning.encrypted]` | 上游有加密思考，但宿主 pi-ai 当 replay 元数据丢弃，GUI 看不到 | 仍按分支 B 处理（`MB/gateways/zgate/internal/config/config.go:44-49`、`MB/tools/model_stream_check.py:210-215`） |
| HTTP 200 且**无任何**思考字段 | 本次请求未触发思考（可能默认档 off，或需显式 `reasoning_effort`） | **不能据此判「不具备」**；若要继续只能再花 1 次额度带 `"reasoning_effort":"low"` 复测 —— 由父代理决定，本分片不擅自加 |
| HTTP 4xx / 5xx | 鉴权、协议或字段问题，能力未定 | 按分支 B 退化，不暴露档位 |

- **能证明**：这一次请求下，上游是否会吐明文思考字段、是否接受裸 body。
- **不能证明**：其它档位是否可调、`max` 档是否被拒、长期稳定性、不同提示词下的行为。要全判需要多次请求，与「可调用次数很少」冲突，故本分片**只主张 1 次**。

---

## 7. 可执行的最小改动清单

### 分支 A｜确认支持 thinking

| 步 | 文件:行号 | 动作 |
|---|---|---|
| A1 | `DSH/profiles/desktop/cordis.patch.yml:259-260` | 在 `- id/name` 下补 `contextWindow` / `maxTokens` / `input: [text]` 与 `reasoningEfforts`。**推荐先按 `:247-252` Space-Bunny 形状**（`low/medium/high/xhigh/max` 之类自映射，**不加 `compat`**），因为该 provider 是 `openai-completions`（`:256`），按 `MB/docs/UPSTREAM.md:93` 只认 `reasoning_effort`；只有当实测确认上游认 deepseek 那套 `thinking` + 有 `off: disabled` 时，才照 `:66-72` 补 `compat.thinkingFormat: deepseek` |
| A2 | 同上 `:253-260` | **不要加** `optionSpecs` / `reasoningLevel` / `map` —— DSH patch 不认这些字段（§3.2 末、§C4） |
| A3 | `MB/tools/dsh_sync.py:349-354` | 若 `--apply` 会跑：非 `zcode-*` 原样保留，A1 手写字段安全，**无需改 ZCode 配置、无需跑投影** |
| A4 | `DSH/profiles/desktop/cordis.patch.yml:9` / `:20-29` / `:374` | 全局默认档与展示项**不用改**（它们不是单模型能力声明） |
| A5（仅当父代理把模型挪进 `zcode-main`） | `ZC/provider_config.json:106-108` 的 `providerModelRules[]`、`:4-8` 的 `providerOrder`、`:12-30` 的 `personalModelIds/modelOrder` | 补一条模型规则（形状照 `:109-134`）：`optionSpecs.reasoningLevel.values` 按实测档位写、`map` 按实测 wire 字段从 `MB/docs/MODEL-PROVIDERS.md:523-528` 选；把模型 id 加进 `personalModelIds` / `modelOrder`；然后 `python tools/dsh_sync.py --check` → `--apply` 由脚本生成 DSH 侧 `reasoningEfforts`（`:243-257`）。**手写字段会被重建冲掉，别两头都写** |
| A6（A5 的必配配套） | `MB/tools/model_stream_exemptions.json:1-18` 或保持 provider 名非 `zcode-` | 挪进 `zcode-*` 后模型立刻进入每日探针（§C6）；必须先定豁免/隔离方案，否则 `--changed` 新增指纹必打 + `--deep` 额外一打，与「可调用次数很少」直接冲突 |

### 分支 B｜不支持 / 不确认（**默认推荐**，零额度风险）

| 步 | 文件:行号 | 动作 |
|---|---|---|
| B1 | `DSH/profiles/desktop/cordis.patch.yml:259-260` | **保持裸条目**：不写 `reasoningEfforts`、不写 `compat`、不写任何 `reasoningLevel`。理由：写了档位宿主就会真发 `reasoning_effort`（`DSH/tools/patch-claude-style-effort.mjs:28-34,42-49`），上游不认就 400（`MB/docs/PITFALLS.md:62`） |
| B2（仅当走 ZCode 链路） | `ZC/provider_config.json:203-211`（Conatus 形状） | 补 `optionSpecs.reasoningLevel.map = "{}"`，**不写 `values`**（`MB/providers/opencode-go/ops/go_model_sync.py:573-581`「档位是装饰项，故不写 values」）；投影结果仍是 DSH 侧不写 `reasoningEfforts`（`MB/tools/dsh_sync.py:245-246`） |
| B3 | `MB/tools/model_stream_check.py:126-155` / `:494` | 保持 provider 名 `gemini`（非 `zcode-`），不进探针契约表，避免每天白发推理请求 |
| B4 | `MB/tools/model_stream_exemptions.json:1-18` | 若 B3 做不到，按现有两条豁免的形状（`reason` + `recoverWhen`）加豁免；注意 note 明确「探针仍会实测」，豁免**不等于零调用** |

### 无论哪条分支都不改

- `ZC/model-alias-map.json`（纯路由表，无思考字段；`ZC/model-alias-map.json:1-5,6-67`）。
- `MB/docs/`、`MB/tests/`、`MB/PROGRESS.md`、`MB/tools/model_alias.py` 的 `MAIN_ORDER` 等（本分片只读；`MB/AGENTS.md:§1,§5`）。
- 任何长驻网关（zgate / wb2api / mihomo）：`DSH/profiles/desktop/cordis.patch.yml` 是热加载 patch，`MB/tools/dsh_sync.py:29-31` 明写「DSH hot-reloads the profile patch, so no restart is needed after a write」。

---

## 8. 主代理必须亲自复核的点

1. **「合并到主力内」的语义**（最高优先级）：是 (a) 挪进 DSH 的 `zcode-main` route（`DSH/profiles/desktop/cordis.patch.yml:42-58`），还是 (b) 进 `MB/tools/model_alias.py` 的 `MAIN_ORDER` / `model-alias-map.json` 的 zgate 别名表？两条链路完全分离 —— 本分片只覆盖 (a) 的 DSH profile 侧，(b) 是另一路分片的领域。选 (a) 就必须连带处理 A5/A6。
2. **额度冲突**：`MB/tools/model_stream_check.py:72-74` 默认 `max_tokens=768`、`:477-478` `--changed` 对新增指纹必打、`:396-403,479` `--deep` 额外一打、`:88` `RETRIES=2`。挪进 `zcode-*` 等于给一个「可调用次数很少」的模型挂上每日多次真实推理，必须先定方案（`MB/docs/MODEL-STREAM.md:49-57,59-62`）。
3. **鉴权来源**：`DSH/.credentials.yaml:22` 只确认了 key 名 `GEMINI_API_KEY`，值未读；`$env:GEMINI_API_KEY` 是否已在会话注入需要父代理实测。`DSH/profiles/desktop/cordis.patch.yml:255-257` 的 base 是外部 HTTPS，**不能套用** `MB/tools/model_stream_check.py:234-238` 的「无 Authorization 头、网关自管 key」写法。
4. **历史证据不可迁移**：`MB/evidence/agent-adaptation.md:248` 的 `reasoning_content` 属 `MB/CHANGELOG.md:22` 已下线的 CP 链路；`third-party/cliproxyapi/` 已移走。型号名对得上不等于能力对得上。
5. **并发改动**：本会话内 `MB/tools/model_stream_check.py` 从 573 行变成 587 行（新增 `_effort_map` 等），本分片已按复核后的**当前**行号写（`load_contract:126`、`_request:225`、`deep_explore:396`、`main:474`、错误行 `:494`）；父代理落盘前建议再 grep 一次行号。
6. `compat.thinkingFormat: deepseek` 是否该加，取决于档 3 实测的 wire 字段，不能照抄 DeepSeek 样例（`DSH/profiles/desktop/cordis.patch.yml:71-72`）。
7. 本分片**未发任何真实请求、未改任何配置**；所有 A/B 改动都只是清单，实际落地由父代理执行并验收。

---

## 9. 本分片自身约束落实

| 约束 | 落实 |
|---|---|
| 只写自己的分片 | 仅 `MB/evidence/agent-thinking-adapt.md` |
| 凭据 | 只出现变量名 `GEMINI_API_KEY` / `ZCODE_GATEWAY_KEY`；值未读、未打印、未写入 |
| 长驻网关 | 未重启 / 停止 / 重配；未执行 `Start-Process` / `restart-zgate.cmd` / 计划任务操作 |
| git | 未 `add` / `commit` / `push` |
| 禁改范围 | 未改 `PROGRESS.md` / 任何配置 / `docs/` / `tests/` |
| 调用次数 | **0 次真实 API 请求**；档 3 只给方案 |
| 检索方式 | `.codegraph/` 空（Not initialized）→ 全程 `glob` / `grep` / `read`，未跑 `codegraph init` |
| 委派 | delegation depth=1/1，本分片未再派子代理 |
