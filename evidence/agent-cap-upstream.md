# 上游能力字段盘点（分片）

> **一句话**：OC/WB/QN 三家目录真给能力字段，GM/HJ/QW/QD 不给；现填 9 组 `contextWindow`/`maxOutputTokens` **全部有上游原文，无一条凭空写**；真问题是 8 条规则上游有值却留空，以及 5 条 `reasoningLevel` 无来源、4 条与上游不一致。

## 1. 数据源实测（2026-11-10 23:2x，本机）

| 源 | 端点 | 结果 |
|---|---|---|
| OC | https://opencode.ai/zen/go/v1/models（无鉴权） | 200，30 条，35661 B → .work/cap-oc-models.json |
| WB 面板 | http://127.0.0.1:7863/panel/api/models（Bearer） | 无 key 401；带 key 200，20 条 → .work/cap-wb-panel-models.json |
| WB 模型面 | http://127.0.0.1:7863/v1/models | 200，20 条，字段最全 → .work/cap-wb-v1-models.json |
| QD | http://127.0.0.1:8790/v1/models | 连接被拒（stopped，未启动） |
| QW | https://maas.qianwenaiapi.com/api/models | **404 空响应** |
| QW | https://maas.qianwenaiapi.com/apps/anthropic/v1/models | **404** `{"code":"InvalidParameter","message":"Not support"}` |
| QN | https://api.qnaigc.com/v1/models | 200，89 条 → .work/cap-qn-models.json |
| GM | https://catiecli.sukaka.top/v1/models | 200，7 条（仅 id/object/owned_by） |
| HJ | https://api.gemai.cc/v1/models | 200，258 条（仅 id/object/created/owned_by/supported_endpoint_types） |

凭据：WB key 取自 `gateways/upstream/workbuddy/config.json` 的 `api_key`（48 字符 → REDACTED）；其余取自 `providers/*/.env.local`。GM/HJ **只发 `GET /v1/models`，零 generateContent/chat**。`ops_bash` 全程正常，取证统一走 `run_code` 内 `node fetch`。

## 2. 字段能力矩阵

| 字段 | OC | WB | QN | GM | HJ | QW | QD |
|---|---|---|---|---|---|---|---|
| ctx | limit.context | context_length/limit.context/max_allowed_size | context_length | 无 | 无 | 拿不到 | 拿不到 |
| maxOut | limit.output | max_output_tokens | max_tokens | 无 | 无 | 拿不到 | 拿不到 |
| 模态 | modalities.input | modalities.input | 无 | 无 | 无 | 拿不到 | 拿不到 |
| 工具 | capabilities.tools.supported | tool_call/supports_tool_call | 无 | 无 | 无 | 拿不到 | 拿不到 |
| 档位 | capabilities.reasoning.effort | reasoning_options/supported_efforts/reasoning_supported_efforts | 无 | 无 | 无 | 拿不到 | 拿不到 |
| 价格 | cost.text.*.price | credits | 无 | 无 | 无 | pools.json 空 | cache/qd_prices.json |

字段并集原文：OC = `…modalities,capabilities,limit,cost,api`；WB = `…limit,max_output_tokens,modalities,reasoning_options,reasoning_supported_efforts,supports_images,supports_tool_call`；QN = `id,object,created,owned_by,context_length,max_tokens,service_status`。

## 3. 结论：谁在写这些字段

- 全仓唯一写 `contextWindow/supportsToolCall/inputFormat/maxOutputTokens` 的代码：`providers/workbuddy/workbuddy_zcode_sync.py:284-333`（`:286` `ctx = int(model.get("context_length") or model.get("max_allowed_size") or 0)`、`:287` `out = int(model.get("max_output_tokens") or 0)`、`:293-296` 写 tool/img）。
- OC 侧 `providers/opencode-go/ops/go_model_sync.py:553-601` 只写 `reasoningLevel.values`（`:574` `values = list(efforts or [])`），不写 ctx/out/tool/img。QD 侧 `providers/qoder/qoder_zcode_sync.py:272-284` 同样只写档位。
- 现 20 条规则全挂 `opencode-go-chat{,-free,-fast}`（`providerOrder` 仅这三项），WB 的 `workbuddy-*` 一条不在 → 这批值是**按 WB 目录人工搬进聚合 provider 的**，脚本不是来源（排除"凭空"但不等于自动同步）。

## 4. 逐字段三态判定（A=有真值且一致；B=有真值但不一致，含漏填；C=上游无此字段）

| 别名（渠道） | ctx | maxOut | tool/img | rl | 备注 |
|---|---|---|---|---|---|
| DeepSeek-4.1-Flash(WB) | A 1e6 | A 128000 | A T/T | A 4档 | WB `…"off"`+toggle → disabled 合法；OC 口径 maxOut=384000 |
| Gemini-3.8-Flash(HJ) | C | C | C | **C** | HJ 无任何能力字段 |
| Gemini-AIS(GM) | C | C | C | **C** | GM 无任何能力字段 |
| HY3(WB) | A 192000 | A 64000 | A T/T | A [low,high] | OC hy3 另口径 256000/128000 |
| HY4-Free(WB) | A 960000 | A 64000 | A T/T | A [high] | max_allowed_size 才是 1e6 |
| Beam(OC) | **B 漏填** | **B 漏填** | **B 漏填** | A 5档 | OC 1048576/131072，img=false |
| Conatus(QN) | **B 漏填** | **B 漏填** | C | **C** | QN 1e6/128000，无档位字段 |
| Iceman(OC) | **B 漏填** | **B 漏填** | **B 漏填** | **C** | OC 262144/131072，img=false，无 effort |
| HY4(WB) | A 960000 | A 64000 | A T/T | A [high] | |
| Qwen-3.8-Max(QD) | B/C | B/C | C | A(间接) | QD 离线；rl 与 OC 同值 |
| Qwen-3.8-Flash(QD) | **B 漏填** | **B 漏填** | **B 漏填** | **B 多 disabled** | OC 1e6/131072，rl 上游 3 档 |
| GLM-5.3-Flash(WB) | A 1e6 | A 131072 | A T/T | A 3档 | WB/OC 双源一致 |
| MiniMax-M3.1-Flash(WB) | A 1e6 | A 128000 | A T/T | A 5档 | OC maxOut=512000（差 4 倍） |
| MiMo-2.6-Flash(OC) | **B 漏填** | **B 漏填** | **B 漏填** | **C 7档无源** | OC 1048576/131072，无 effort |
| MiMo-2.6-Pro(WB) | A 1e6 | A 128000 | A T/T | **B 7档 vs ["high"]** | OC 1048576/131072 |
| HY3-X(WB) | A 192000 | A 64000 | A T/T | A [low,high] | live 目录无此 id，快照有 |
| Claude-Haiku-5.5(OC) | **B 漏填** | **B 漏填** | **B 漏填** | **B 多 disabled** | OC 1e6/128000 |
| Muse-Spark1.3(OC) | **B 漏填** | **B 漏填** | **B 漏填** | A 5档 | OC 1048576/131072 |
| GPT-6-Luna(OC) | **B 漏填** | **B 漏填** | **B 漏填** | **B none→disabled** | OC 1050000/128000 |
| Space-Bunny(WB) | A 1e6 | A 128000 | A T/T | A 5档 | |

小计：ctx A=9/B=8/C=2；rl **A=11/B=4/C=5**。

## 5. 点名：`contextWindow=1000000` 不是凭空写的

5 条原文（WB `/v1/models` 或 `/panel/api/models`）：

- DeepSeek-4.1-Flash（`provider_config.json:117`）：`{"context_length":1000000,"limit":{"context":1000000,"output":128000},"max_output_tokens":128000,"supports_tool_call":true,"reasoning_supported_efforts":["low","high","max","off"],"reasoning_options":[{"type":"effort","values":["low","high","max"]},{"type":"toggle"}]}`
- GLM-5.3-Flash（`:340`）：`context_length 1000000, max_output_tokens 131072, supported_efforts ["low","high","max"]`
- MiniMax-M3.1-Flash（`:366`）：`context_length 1000000, max_output_tokens 128000`
- MiMo-2.6-Pro（`:415`）：`context_length 1000000, max_output_tokens 128000`
- Space-Bunny（`:530`）：`context_length 1000000, max_output_tokens 128000`

960000/192000 同源：`:205` hy4free `context_length 960000, max_allowed_size 1000000`；`:282` hy4std `960000/64000`；`:180` hy3、`:446` hy3-x `192000/64000`。

HY3-X 的 live 缺席是可见性结构问题（panel 只覆盖 CLI 菜单链路，见 `evidence/agent-effort-audit.md:100`），真值在快照 `providers/workbuddy/cache/wb_pricing.json`：`{"id":"cn:hy3-x","ctx":192000,"out":64000,"tool":true,"img":true,"efforts":["low","high"],"can_disable":false}`，与现填逐项一致。

## 6. 无来源字段（C 类）与不一致（B 类）

- **C 类（上游根本没这字段）**：Gemini-3.8-Flash、Gemini-AIS（GM/HJ 无 reasoning 字段）、Conatus（QN 无 effort）、Iceman（OC 无 effort 数组）、MiMo-2.6-Flash（OC 无 effort）。
- **B 类（上游有值但现填不同）**：MiMo-2.6-Pro（WB `["high"]` vs 现填 7 档，且 panel 为 null、wb_pricing 为 `[]`，三处互相矛盾）、Qwen-3.8-Flash（多 disabled）、Claude-Haiku-5.5（多 disabled）、GPT-6-Luna（`none` 被写成 `disabled`）。
- 硬旁证：`providers/qoder/qoder_zcode_sync.py:278` 明写「目录没有 `can_disable` 字段，故不自行补 `disabled`」，而 Qwen-3.8-Flash 现值恰好补了。
- MiMo 两条档位表完全相同（`[disabled,minimal,low,medium,high,xhigh,max]`），上游均无此声明；ZCode 内置近似表在 `third-party/zcode/zcode-builtin.json:4342` → 疑按兜底表补，非目录取值（**推断，未验证**）。

## 7. 未验证 / 待补

- QW 全渠道零能力证据（端点 404），DeepSeek-4.1-Flash 第 4 跳无法核验。
- QD 8790 stopped 未启动；`providers/qoder/cache/qd_prices.json` 仅价格，Qwen-3.8-Max 只有 OC 旁证。
- WB `cn:hy3-b` / `cn:hy3-c` 已不在 live 目录（快照仍在），可用性未验证。
- 现填值是「人工搬 WB 目录」这一条是**推断**（依据：全仓仅 WB 脚本会写这四个字段 + 规则挂在非 WB provider 上），无写入日志佐证。

## 8. 复现

    curl -s https://opencode.ai/zen/go/v1/models -o .work/cap-oc-models.json
    curl -s -H "Authorization: Bearer %WB_GATEWAY_KEY%" http://127.0.0.1:7863/v1/models
    curl -s -H "Authorization: Bearer %QINIU_API_KEY%" https://api.qnaigc.com/v1/models

逐字段比对产物：`.work/cap-compare.json`（20 别名 × 全链 × 现填）。
