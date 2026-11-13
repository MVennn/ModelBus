# 同步链、自动收录与仓库运维（结论卡）

> **一句话**：每日 12:00 自动收录链的形状、三次探活/收录验收的结论，以及几份仓库级盘点数字；正本见 [docs/MAINTENANCE.md](../docs/MAINTENANCE.md) 与 [docs/MODEL-ALIAS.md](../docs/MODEL-ALIAS.md)。

## 1. 自动收录链

| 环节 | 结论 | 原证据 |
|---|---|---|
| 定时 | 计划任务每日 12:00 触发 `sync-models.ps1` → `providers/opencode-go/ops/go_model_sync.py`（旧文里的 `scripts/go_model_sync.py` 已不存在） | agent-sync-scheduler.md |
| 报告落点 | 收录报告写本仓 `evidence/go-model-sync-YYYYMMDD-HHMMSS.md`（保留最近一版）；alias 快照报告另写 `docs/reports/MODEL-SYNC-*.md` 并在 `docs/reports/README.md` 登记 | CHANGELOG:833 / 1335 |
| 失败形态 | 2026-11-05 12:00 未到点、零产物 —— 任务没跑，不是链坏了 | agent-sync-scheduler.md、agent-sync-logs.md |
| 报障形态 | DSH 报 `pi-ai provider "zcode-main" has no configured model "Gemini-AIS"` = 模型名在 `provider_config.json` 有、投影后的 `cordis.patch.yml` 里没有 | agent-sync-audit-20261111.md |
| 429 硬化 | 429 优化已固化进生成器，不再靠手工改生成结果 | agent-model-alias-hardening.md |

## 2. 三次探活 / 收录验收

| 结论 | 原证据 |
|---|---|
| 省掉零收益的「骤降探活」（m01007）：模型健康时不额外打探测请求 | agent-detect-cost.md |
| 零请求时复用上次探测信号，不再空跑（agent-detect-quality.md） | agent-detect-quality.md |
| 收录价格口径正规化（m01046 / m01047）：缺价不再静默按 0 计 | agent-admission-price.md |

## 3. 仓库级盘点数字（时点，别当现网）

| 结论 | 原证据 |
|---|---|
| 全仓文本文件 1153 个 / 45,225,871 B | agent-audit.md |
| 热点：`zgate.exe.bak-*` 6 份共 64,514,048 B；请求日志 7 天 27,688,206 B / 40,351 行且**无 retention**；`provider_config.json.bak-*` 49 份共 849,378 B | agent-audit.md |
| 可证明行为等价的最小优化只有 2 个（PowerShell 参数数组去重、Python 校验改 `with`）；优先级 P0=0 / P1=6 / P2=8 | agent-audit.md |
| 2026-11-10 单日 17 个 commit / 70 个去重文件 / +14391 −2612 | agent-git.md |
| 本仓真实项目根是 `F:\Project\ModelBus`，`_merged` junction 不是项目身份（适配性 / 聚合性评估的共同前提） | agent-adaptation.md、agent-aggregation.md |
| 自动性边界：到哪一步由脚本自动、哪一步必须人拍板 | agent-automation.md |
| reasoning 展示：网关侧与流式两条线已闭环；档位仍 4 空档 + 1 副作用；展示层悬空；`reasoningGuard.mode` 曾被并行会话由 `auto` 改回 `models` | agent-reasoning-history.md |

## 4. 未落地

- 请求日志无 retention（7 天 27 MB 且持续增长），只在盘点里记录，没有清理脚本（agent-audit.md）。
- 展示层（L4）悬空：修好后会被 profile 偏好覆盖回 `compact/completion/final`，见 AGENTS.md §16（agent-reasoning-history.md）。
