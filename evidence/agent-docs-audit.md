# 槽5 文档审计核对表 — ModelBus docs/ 与 AGENTS.md

> **一句话**：审计 ModelBus 仓库 docs/（59 篇）与 AGENTS.md 里会误导人的记忆型断言；机器核对后确认 1 处陈旧断言并就地修正，其余高风险断言均属带日期历史快照或已与代码/配置一致，不改。证据以路径:行号为准，全部实读/实测后记录。

生成时间：2026-11-21　审计人：docs-audit（槽5 分片）　写域：仅 docs/ 与 AGENTS.md 确认错误项 + 本 evidence 文件。

## 判据与范围

- 判废五类 / 四条红线：~/.dsh/skills/on-demand/memory-hygiene.md §8.4。
- L3 正本判据：~/.dsh/skills/on-demand/DOCUMENTS-ROUTING.md §1。
- 本仓文档规则：docs/DOC-RULES.md（带日期标注的样例可容忍过时，见 :149）。
- 取证方式：先 grep 绝对措辞（从未/一律/只/必/禁止/已删/不存在/版本数字/端口，命中 2198 行，绝大多数为带日期历史快照），再对当前态断言逐条读代码 / 解析配置 / 查 git / 查计划任务。未开浏览器。

## 审计项表

| 项 | 文件:行号 | 判定 | 原断言 | 实况证据 | 处置 |
|---|---|---|---|---|---|
| 1 链序三维排序 | docs/MODEL-ALIAS.md:564 + :573 | 已修 | "链序是三维排序：渠道 rank → 跳级优先级 → 折算价升序"；"第二维 HOP_PRIORITY 是 0…6 显式数字表、表外取 99" | git log -S HOP_PRIORITY -- tools/model_alias.py 显示提交 c8dbbd8（2026-11-17）删除 HOP_PRIORITY 与 HOP_PRIORITY_DEFAULT；现行 tools/model_alias.py:2019-2034 family_entries() 排序键为 QW_FIRST 特例→CHANNEL_RANK→price→GB/CN 前缀→渠道→upstream，无"跳级优先级"维；全仓 grep 仅 CHANGELOG/PROGRESS 历史记录与该文档命中 | 改为现行排序键清单 + 把 HOP_PRIORITY 段标"历史已退役，勿按现值读"，保住历史记忆价值 |
| 2 TAIL_HOPS 已退役 | docs/MODEL-ALIAS.md:577 | OK | "TAIL_HOPS 常量已从 model_alias.py 删除，被 CHANNEL_RANK 取代" | tools/model_alias.py 中 TAIL_HOPS 仅 3 处命中（:312/:316/:2016）且全是"取代原 TAIL_HOPS"注释，无常量定义 | 保留不动，断言成立 |
| 3 QW_FIRST_MODELS 四事实正本 | docs/MODEL-ALIAS.md:575 / docs/QWEN.md:224-228 | OK | QW 抢链首 / QD 三窗口 / 2.6s 回包 / 200 空正文四事实（lead 追加核对点） | MODEL-ALIAS.md:575 与 QWEN.md:225 覆盖链首；MODEL-ALIAS.md:575 覆盖三窗口 08:58-09:15/20:58-21:15/21:58-22:15；QWEN.md:228 与 MODEL-ALIAS.md:575 覆盖 2.6s；MODEL-ALIAS.md:575 与 QWEN.md:224 覆盖 200 空正文 | 正本全覆盖，已回报 lead 可压热条目；docs 不改 |
| 4 文件存在性断言（约 17 条） | docs/ARCHITECTURE.md:12/82/195 等多篇 | OK | unified-router.js/protocol_bridge.js 已退役；zgate.exe / zgate.json / router.go / bridge.go / reqid.go / model_alias.py / model_visibility.py / model_stream_check.py / dsh_sync.py / check-project.py / model_probe.py / zcode-builtin.json / qoder 目录 / race.go / early_sse.go 存在 | node fs.existsSync 逐条实测 17 条全部命中预期（退役的不存在、其余存在），无一条不符 | 保留不动 |
| 5 zgate.json 结构 | docs/MODEL-PROVIDERS.md:128 / docs/ZGATE-LIFECYCLE.md:267 | OK | 监听 127.0.0.1:7871；upstreams 6 / children 2 | 解析 gateways/zgate/zgate.json：7871 监听、upstreams 6 个、children 2 个，与文档一致 | 保留不动 |
| 6 watchdog 计划任务唯一 | docs/ZGATE-LIFECYCLE.md:56 | OK | "唯一 zgate 自启任务 ModelBus-zgate-watchdog"，LogonTrigger + 每分钟 PT1M、StartBoundary 2026-11-06T22:14、wscript 动作 | Get-ScheduledTask 实测：watchdog StartBoundary/LogonTrigger/PT1M/wscript 全对；另两个 ModelBus 任务一个每日模型同步、一个已 Disabled，无第二个 zgate 自启任务 | 保留不动 |
| 7 PROGRESS 唯一 | AGENTS.md:12-13 | OK（措辞限定于版本库） | "全仓只有一个进度文件：仓库根 PROGRESS.md" | 实测 2 个 PROGRESS.md：根 PROGRESS.md + .work/dsh-first-20261111/PROGRESS.md（283 KB，2026-11-11，git check-ignore 命中 .gitignore:102 /.work/，未被 git 跟踪）。"全仓"措辞对 .work 工作副本不严谨，但 .work 属 gitignore 排除的本地工作区，规则语义指版本库内唯一，不构成误导 | 保留不动 |
| 8 模型条数 19/72 | docs/MODEL-ALIAS.md:585-590 | OK（带日期与漂移声明） | alias 聚合 19 条 / legacy 72 条 / 面板 56 | ~/.zcode/v2/model-alias-map.json 实测 models=10/legacy=48（已变化），但文档 :590 明确标注"四数实测 2026-11-13…会随上游目录漂"，且该文件是运行时状态不进库；属带日期历史口径，符合 DOC-RULES:149 可容忍过时 | 保留不动 |
| 9 CAPABILITY-AUDIT 9 真值 10 兜底 | docs/CAPABILITY-AUDIT.md:7/15-16 | OK（带日期标注） | 9 个上游真值 / 10 个兜底魔数 / 现网 19 模型 | 文首 :3-5 已标"历史快照 2026-11-11，19 模型口径…现网 canonical 24 条，终值见 §9"，:15 也写明历史快照与现值并列 | 保留不动 |
| 10 ZCode chat provider 数 | docs/MODEL-PROVIDERS.md:132-133 | 待lead | "现行 ZCode 只有 3 个 chat provider" | provider_config.json 是 lead 独占写域，本分片不读不改，无法核实当前 provider 数 | 记录交 lead；本分片不动 |
| 11 本机机器名残留 | docs/ZGATE-LIFECYCLE.md:60 | 待lead | 触发器表写"当前用户 MVENN-PC\SansK" | 文件实含真实机器名/用户名（其余 7 处绝对路径均为 <名字>/<用户名> 占位），违反 SECRETS 脱敏惯例；但它是当前触发器事实、非陈旧记忆，改动会削弱可核对性 | 记录交 lead 决定是否脱敏；本分片不动 |
| 12 相对死链 | docs/DOC-RULES.md:105 | OK（误报） | 脚本扫描报 1 处死链 文档名.md | 实读该行是文档规则的行内代码示例（"如 文档名.md"），非真实链接，不含 markdown 链接语法目标 | 保留不动 |
| 13 check-docs 门禁 | 全仓 docs/ | OK（验证） | — | python tools/check-docs.py → [OK] 59 篇文档全部通过（链接 / 锚点 / 引言块 / 孤儿），GATE_EXIT=0 | 作为改动后复核证据 |

## 改动文件清单（逐行，路径:行号）

- F:\Project\ModelBus\docs\MODEL-ALIAS.md:564 — 把"三维排序（含跳级优先级）"改为现行排序键清单，并说明跳级优先级一维已于 2026-11-17 删除。
- F:\Project\ModelBus\docs\MODEL-ALIAS.md:573 — 把"第二维 HOP_PRIORITY 数字表"整段标为"历史已退役，勿按现值读"，补上删除提交号 c8dbbd8 与现行同价排序落点。

git diff 复核：docs/MODEL-ALIAS.md | 4 ++--（2 插入 2 删除），无其他文件改动。门禁 exit 0。

## 未解决项（交 lead）

1. docs/MODEL-PROVIDERS.md:132-133 "现行 ZCode 只有 3 个 chat provider" —— 需 lead 在 provider_config.json（其独占写域）核对当前 provider 数，若已变则由 lead 决定是否修正该文档。
2. docs/ZGATE-LIFECYCLE.md:60 含真实机器名 MVENN-PC\SansK —— 需 lead 决定是否按 SECRETS 脱敏惯例改为占位；本分片为避免削弱事实可核对性未擅改。
3. AGENTS.md:12-13 "全仓只有一个 PROGRESS.md" 措辞对 .work/ 本地工作副本不严谨（实测 2 个，另一个被 gitignore 排除）——需 lead 判断是否补"版本库内"限定；非记忆型陈旧错误，本分片未改。