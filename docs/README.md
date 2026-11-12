# docs/ 索引

> **一句话**：这里只有索引与定位，不放正文 —— 每篇文档一句话说明「它管什么」，
> 规则本身按 [DOC-RULES.md](DOC-RULES.md) 的单一正本原则只在对应文档里定义。

文档分四类。每篇开头都有一个「一句话」引言块，先看它再决定要不要往下读。

---

## 一、模型与 Provider

| 文档 | 一句话定位 |
|---|---|
| [MODEL-PROVIDERS.md](MODEL-PROVIDERS.md) | **provider 与模型参数正本**：接供应商的四步方法、兼容投影配置落点、7 个 upstreams（OC / WB / QD / QW / QN / GM / HJ）的分组 / 协议 / 工具调用 / 关思考参数 |
| [MODEL-ALIAS.md](MODEL-ALIAS.md) | **统一命名与分组正本**：纯型号名（真重名才加后缀）、跨渠道合并链路（WB 固定链首、其余按价格稳定排序）、同类模型的判定（看上游回包 model / quota / credit，不看名字）、主力/免费/省钱三组、组内顺序由 `MAIN_ORDER`/`LOW_ORDER` 决定、alias map 与流式协议桥接 |
| [QODER.md](QODER.md) | **Qoder 接入正本**：qoder2api-hub 的 8790 进程、OAuth/签到、`qoder` provider 的模型与同步/探测命令、边界与故障处理 |
| [QWEN.md](QWEN.md) | **千问（qianwenai）接入正本**：只提供 Anthropic Messages 的直连上游、`QW` 渠道与协议桥、506 条免费额度四道漏斗筛到 14 个（2026-10 快照）、用完即停与 Go 协议桥流式双路径的边界 |
| [QINIU.md](QINIU.md) | **七牛云 AI 网关接入正本**：`QN` 渠道、只认 Anthropic Messages、`qiniu/conatus-free` 限免到 2026-11-30、同网关其它免费模型的实测结论 |
| [MODEL-QUICK-REF.md](MODEL-QUICK-REF.md) | 早期速查（2026-10-20）：价格、额度与实测首字。**结论已并入 MODEL-PROVIDERS.md**，本篇保留作历史快照 |
| [archive/OPENCODE-GO-ANALYSIS.md](archive/OPENCODE-GO-ANALYSIS.md) | 2026-10-19 的阶段性分析（归档只读）：协议归属实测、价格带筛选、出口方案 |

## 二、流程与规范

| 文档 | 一句话定位 |
|---|---|
| [DOC-RULES.md](DOC-RULES.md) | **文档规则正本**：文件命名（全大写连字符）、分类定位、单一正本映射表、链接纪律、变更触发矩阵、体量预算 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | **运行架构整合方案（已落地 2026-10-23）**：2 个 child（7863 / 8790）与 7 个 upstreams 的实测拆解、`zgate` 单入口 + 按需子进程方案、`gateways/` 与 `providers/` 两轴目录重构、分阶段验收与回退 |
| [DSH-FIRST.md](DSH-FIRST.md) | **DSH 主导的方向正本**：当前架构（DSH 主宿主 + 各类 agent，ZCode 降为兼容投影）、三层命名口径（契约层不动 / 实现层已去 ZCode / 新层用 agent 词汇）、catalog 真源 + 多宿主投影、批 1–批 4 状态与验收口径、DSH 侧可用接缝与多 agent 适配 |
| [MAINTENANCE.md](MAINTENANCE.md) | 日常维护：刷价格表、探测限速、快照保留、`--apply` 备份与回退、热重载注意事项 |
| [ZGATE-LIFECYCLE.md](ZGATE-LIFECYCLE.md) | **zgate 生命周期正本**：计划任务单任务自启、CMD/DSH 会话树与 Job Object 问题、`build.py --candidate` + `tools/zgate-lifecycle/` 换版流程、失败回滚与常见故障 |
| [ROUTING-POLICY.md](ROUTING-POLICY.md) | **路由策略正本**：一条请求「先打哪一跳、等多久、失败算谁的、什么时候不许判死」—— 逐跳参数聚合、链预算 `chainBudgetSec`、单跳链冷却豁免、两张冷却表、启动自检 `ValidatePolicies`、`/v1/models?scope=`、`/health` 的 early/chain/guard 段、各渠道当前实际值与回退 |
| [TOOLS.md](TOOLS.md) | **工具清单正本**：运行环境、每个脚本的产物与去留标记、统一模式与 `--separate` 的区别 |
| [CONSOLE.md](CONSOLE.md) | **可视化后台正本（2026-11-12 已落地 v3）**：Tabler 1.7.4 高星后台外壳 + Microsoft Fluent 2 语义令牌桥接与十二条落地规则、8 页信息架构与字段来源、独立 Python 服务而非塞进网关的取舍、统一响应包与静态/vendor 路由、脱敏红线与同源 POST 校验、资源占用只读候选、验收实测 |
| [VERSIONING.md](VERSIONING.md) | **版本晋升正本**：三段式进位、仓库发布号在哪维护、什么时候不动版本号。发版规则并入本篇 |
| [SECRETS.md](SECRETS.md) | **凭据位置正本**：一律走环境变量，**只写位置不写值**；上传公开仓库前必读 |
| [release-notes/README.md](release-notes/README.md) | **Release 说明格式正本**：形状、动词四选一、覆盖率红线、固定尾巴 |
| [MODEL-STREAM.md](MODEL-STREAM.md) | **流式 / 思考 / 输出 / TPS 准入正本**：模型进表即自动纳入，新增模型免人工逐个测试；含上游加密思考分流 `ENC` 判定口径，§10 记网关守卫 `auto` 模式的同类模型免配置适配 |

## 三、排错与踩坑

| 文档 | 一句话定位 |
|---|---|
| [PITFALLS.md](PITFALLS.md) | **为什么会出这个坑**：机制解释，每条标 **【通用】/【实例 A】/【实例 B】** |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | **怎么查**：现象 → 排查步骤 → 原因 / 解法，标题即检索词 |

## 四、参考资料

| 位置 | 一句话定位 |
|---|---|
| 仓库根 [README.md](../README.md) | 门面（面向使用者）：DSH 主宿主 + 各类 agent 的定位、环境要求、使用、反馈、免责声明、许可证 |
| 仓库根 [AGENTS.md](../AGENTS.md) | 机器协议（四条硬规矩 + 当前架构声明）：PROGRESS 按逻辑任务分家、凭据走环境变量、有 CodeGraph 先用、改完 Go 代码自动走 `restart-zgate.cmd` 换版 |
| 仓库根 [CHANGELOG.md](../CHANGELOG.md) | 开发者记录：**版本号本身**在它的版本标题里，**进位规则**见 [VERSIONING.md](VERSIONING.md) |
| 仓库根 [PROGRESS.md](../PROGRESS.md) | 本仓唯一进度台账（追加式批次日志） |
| 仓库根 [NOTICE](../NOTICE) | 第三方声明：WorkBuddy2API Panel（MIT）、qoder2api-hub（MIT）、OpenCode Go（商业）、ZCode（Apache-2.0）等 |
| [UPSTREAM.md](UPSTREAM.md) | **上游调研正本**：同类型项目清单、深读结论、借鉴落地、随仓分发的上游文件与来源凭证 |
| [REVIEW-2026-11-10.md](REVIEW-2026-11-10.md) | **2026-11-10 改动复盘**：当日 17 个提交按功能面归并、逐项判定是否真生效与作用半径（哪些只覆盖 1/20 模型）、同一条链改四轮的根因、可整合的四组重复判断与 P0–P2 优化建议 |
| [CAPABILITY-AUDIT.md](CAPABILITY-AUDIT.md) | **模型能力配置审计（2026-11-10，2026-11-11 已按 §9 落地修复）**：DSH 下拉里上下文/输出上限/图片/工具/档位的真实来源 —— 三层规则叠加与 `.*` 兜底魔数、provider-site 真值层因网关 baseURL 全灭、20 个模型逐字段对账、五类差额与 P0–P3 修法 |
| [BENCHMARKS.md](BENCHMARKS.md) | **外部跑分参考**：AI 能力专项测试（2026-09-11 快照）+ ArenaGalleri 实时榜；主力自动扩充的基准、窗口与候选表 |
| 仓库根 [third-party/](../third-party/README.md) | 随仓分发的上游文件：ZCode 规则数据与引擎源码、ZCodium 规则切片，各带来源凭证 |
| 仓库根 [LICENSE](../LICENSE) | 许可证全文（**MIT**），与 [NOTICE](../NOTICE) 配套 |
| [reports/](reports/README.md) | **同步报告索引**：只保留最近一次自动化结束后的模型清单快照与变化（新增 / 移除 / 分组 / 链路）；2026-11-06 之前的历次一次性快照已清理 |
| [release-notes/](release-notes/README.md) | 面向使用者的 Release 说明，文件名 = `versionName`；格式规范在它的 README。最近一份 Release 说明：[0.7.0.md](release-notes/0.7.0.md)。已发布：[0.6.0.md](release-notes/0.6.0.md) / [0.5.0.md](release-notes/0.5.0.md) / [0.4.0.md](release-notes/0.4.0.md) / [0.3.0.md](release-notes/0.3.0.md) / [0.2.0.md](release-notes/0.2.0.md) / [0.1.0.md](release-notes/0.1.0.md) |
| `../evidence/` | 证据快照：网关模型目录、自动收录报告、WorkBuddy 接入线历史台账（只读） |
| [../.githooks/pre-commit](../.githooks/pre-commit) | 提交前敏感信息闸门：启用 `git config core.hooksPath .githooks` |

---

> 新增 / 删除文档后**必须同步更新本索引**（规则见 [DOC-RULES.md](DOC-RULES.md)）；
> 新文档至少要被一处既有文档引用，不允许孤儿。
