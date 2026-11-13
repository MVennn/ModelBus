# 去 ZCode 化的范围与边界（结论卡）

> **一句话**：把 ZCode 口径从实现层拿掉时，哪些字能改、哪些契约一个字不能动、实际可动的面有多大；三层口径正本见 [docs/DSH-FIRST.md](../docs/DSH-FIRST.md)。

> 2026-11-11 七路普查后归并；一次性的逐文件清单已压成数字，原件见 git 历史。

## 1. 契约层：一个字不动

`~/.zcode/v2/provider_config.json`、`ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` / `ZCODE_BUILTIN`、`third-party/zcode*` 原件、schema 键、`%LOCALAPPDATA%\ZCodeGateway\`、NOTICE 商标段 —— 改名就断外部使用者。

| 普查数字 | 原证据 |
|---|---|
| 全仓 ZCode 命中 10425 处 / 293 文件（2026-11-11 15:59:35 取样），其中 7148 处是上游署名、日志与历史记录，本来就不该改 | agent-zcode-census.md |
| 第一方源码审查：契约层 113 行**勿动** + 实现层净命中 129 行 = 96 必须改 / 24 历史勿动 / 9 可保留 | agent-code-review.md |
| 文档侧：38 篇 docs 里 29 篇带 ZCode 口径共 487 行，但**真正会改坏东西的只有 6 类外部契约** | agent-dshfirst-docs.md |

## 2. 实际可动的面（很小）

| 结论 | 原证据 |
|---|---|
| 可改的只有 6 个自有脚本名、1 个自造环境变量、DSH 侧 3 个 route id、36 篇文档措辞 | agent-dshfirst-naming.md |
| 执行结果：6 脚本改名后旧名 0 残留，9 个 `.py` `py_compile` EXIT=0，1 个 `.js` `node --check` EXIT=0 | agent-rename-code.md |
| 文档同步已完成：docs 顶层 22 篇改成 DSH 主宿主口径、6 个改名脚本同步、三道门禁两轮全绿 | agent-docs-sync.md |
| docs 侧当时仍以 ZCode 为中心（zcod 463 行 / DSH 118 行，根 README 17 / 0），改法是三层：契约层不动 / 实现层去 ZCode / 新层用 agent 词汇 | agent-docs-review.md |

## 3. 架构判断（为什么这么改）

- DSH 里 agent / preset / session / goal / subagent 都是一等公民，模型面只剩 `ctx.llm` 适配器与 `llm/stream` 钩子 → ModelBus 在 DSH 侧的正确形态是**一个 provider 插件 + 一个本地控制端点**，而不是搬一整套 agent 框架（agent-dshfirst-dsh.md）。
- 现役链路仍是 `provider_config.json` 为写入真源 → `dsh_sync.py` 投影 `cordis.patch.yml`；实现层 123 行 ZCode 命中拆 37 契约 / 86 待迁移（agent-functional-review.md）。
- 迁移方案：契约层零改动 + 实现层中性化（保留行为，只换命名）（agent-replacement-plan.md）。

## 4. 未完成

- Go 侧 `X-Agent-Id` 分桶**零实现**：docs/DSH-FIRST.md 只写了契约，代码里没有按 agent 分桶的逻辑（agent-functional-review.md）。
