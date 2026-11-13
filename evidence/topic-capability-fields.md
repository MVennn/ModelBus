# 能力字段与档位真值（结论卡）

> **一句话**：DSH 模型表里 `contextWindow` / `maxOutputTokens` / `optionSpecs` 这些能力字段从哪来、哪些是兜底默认值、哪些档位漏了；正本结论见 [docs/CAPABILITY-AUDIT.md](../docs/CAPABILITY-AUDIT.md) 与 [docs/MODEL-STREAM.md](../docs/MODEL-STREAM.md)。

## 1. 字段来源链

| 事实 | 原证据 |
|---|---|
| DSH 宿主**不读** `provider_config.json` 的 `properties` / `optionSpecs`（全仓 0 命中）；它只被 `tools/dsh_sync.py` 投影成 `cordis.patch.yml` 的 `llm-pi-ai.providers.*.models[]` | agent-cap-dsh.md |
| 投影缺字段时的默认值：`contextWindow=1000000`、`maxTokens=128000`、`input=["text"]` | agent-cap-dsh.md |
| 20 条规则只有 WB 渠道的 9 条带**真实** `properties`；其余 11 条的 `contextWindow=1000000` / `supportsToolCall=true` 是 ZCode builtin 的 `.*` 兜底规则在运行期补的，不是真值 | agent-cap-gen.md |
| 上游给不给能力字段按渠道分：OC / WB / QN 给，GM / HJ / QW / QD 不给 | agent-cap-upstream.md |
| 11 条缺 `properties` 里只有 3 条能从 `providerSiteRules` / `modelRules` 取到实测真值，另外 8 条只能标 `none` | agent-caps-truth.md |
| 9 条已有 `properties` 中 6 条与 site rule 有出入；`DeepSeek-4.1-Flash` 现网 `max=128000`、上游真值 `384000` | agent-caps-truth.md |
| 8 条上游有值却留空、5 条 `reasoningLevel` 无来源、4 条与上游不一致 | agent-cap-upstream.md |

## 2. 档位（reasoningEffort）

| 事实 | 原证据 |
|---|---|
| 19 个模型只有 9 个把上游档位搬进 DSH 模型表；10 个缺档 = 5 个生成器回退分支丢失（可重跑补）/ 5 个源头只有开关二态 | agent-effort-audit.md |
| 逐模型默认档**一个都没落地**，只有全局 `reasoningEffort: high`；缺口 8 项 | agent-effort-audit.md |
| HY3-X 的「档位错误」已被平反，不是缺陷 | agent-effort-audit.md |
| 新建 gemini provider 时是裸条目，未声明思考能力 → 上游按默认行为处理 | agent-thinking-adapt.md |
| GM 的能力真值只有 `GET /v1beta/models` 一处：`contextWindow=1000000`、`maxOutputTokens=65536`；HJ 无接口，只能靠厂商文档 | agent-gemini-truth.md |

## 3. 尚未落地

- 上游有值却留空的 8 条、与上游不一致的 4–6 条、无来源的 5 条 `reasoningLevel`：docs 侧只收口了「默认值不可信」这条结论，**逐条真值表没有正本**。要补先跑 `tools/model_caps.py --check`（2026-11-11 基线已有 10 条差异）。
