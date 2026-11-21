# 槽4 · 经验卡深度校对（proc-audit）

> 结论：61 卡全绿（门禁 P0=0 / P1=0）。逐卡深度校对发现 **4 处失效引用/命令，集中在 3 张卡**（2 张 purge 卡的验证脚本已退役 + 1 处 demote 留档路径写错）；**0 真重复、0 漏登记**；1 条 inbox 待裁定（判定留 inbox）；2 张退役候选（只列不删）。失效项与退役候选存在依赖：若 lead 采纳退役，purge 两卡的失效命令随之消失；若不退役则必须修验证行。

---

## 门禁输出原文摘要

命令：`node ~/.dsh/tools/procedures-audit.mjs --dir ~/.dsh/procedures`（带 `--dir`，exit 0）。原文：

```
卡库体检 · 61 张 / 143.5 KB · ~/.dsh/procedures

P0 必须修（断链 / 缺必需段）：0

P1 建议处理：0

全部通过。
本脚本只读 —— 不写、不删、不改任何卡。处置（补 / 并 / 退役）由使用者审阅后决定。
```

门禁只查格式与卡间断链，不查卡内路径引用是否随系统变更失效——以下四类问题正是门禁覆盖不到的部分。

---

## 四类问题清单

### 1. 死链（卡内引用的路径/脚本已不存在）

逐卡抽取 74 条路径引用，Test-Path 验证：63 存在、11 不存在；逐条核上下文后 **4 条是真失效**，其余 7 条是合法占位符或已删除的历史误建路径（见文末排除说明）。

| # | 卡名 | 行号 | 证据（卡内原文 / 实测） | 判定 |
| --- | --- | --- | --- | --- |
| D1 | 工具-dsh-purge-Agent预设三条重复子任务.md | 5 | 验证行 `node ~/.dsh/tools/purge-preset-alias-fix.mjs --check`；实测该脚本已退役至 `~/.dsh/tools/_retired/purge-preset-alias-fix.mjs`，原路径 MISSING | 失效·真 |
| D2 | 工具-dsh-purge-rc2预设加载失败.md | 5 | 验证行 `node ~/.dsh/tools/purge-preset-list-agents-fix.mjs --check`；脚本已退役至 `_retired/`，原路径 MISSING | 失效·真 |
| D3 | 工具-dsh-purge-rc2预设加载失败.md | 9 | 首选第 1 步 `跑 ~/.dsh/tools/purge-preset-list-agents-fix.mjs`；同 D2 原路径 MISSING | 失效·真 |
| D4 | DeepseekHarness-工具-上游429切模型与重试.md | 21 | 留档写 `~/.dsh/backups/demote-throttled-hop.mjs.disabled-20261105`，实测该 backup MISSING；脚本真身仍在 `~/.dsh/tools/demote-throttled-hop.mjs`（EXISTS），从未进 backups | 失效·真（留档路径写错） |

排除的 7 条（合法，非问题）：`cordis.patch.yml.bak-<ts>`（`<ts>` 占位，backups 实有 4 份 cordis bak）、`ui-chat-guard.out`（运行时日志，logs 目录存在）、`official-runtime-<ver>`/`task-<名>-<stamp>.xml`/`runtime-memories.json.bak-<时间>`（模板占位，backups 实有 task-* 文件）、inbox 两条 `--preview-only` 路径（卡内明确记载已 Remove-Item 删除的历史误建路径，描述历史事件，非让读者去访问）。

### 2. 重复（标题/锚点/触发 Jaccard）

对 61 张卡按 `title×0.5 + anchor×0.35 + trigger×0.15` 算 Jaccard，≥0.3 出 23 对候选；逐对读正文核实后 **0 组真重复**。高分全部来自同项目命名前缀（MuMu-框架-、工具-Windows-、zgate-），锚点 Jaccard 普遍 <0.15。

| 候选组 | 最高分指标 | 内核对 | 判定 |
| --- | --- | --- | --- |
| dsh-宿主-升级前后补丁体检清单.md ↔ dsh-插件-本地手改补丁识别与处置.md | 锚点 J=0.47（全场最高） | 前卡讲「升级后逐条判 CHANGED/重打」；后卡讲「识别哪些包被手改 + 宿主换包三样判据」，两卡互相 `见卡` 交叉引用，是分工不是重复 | 非重复·互补 |
| 工具-dsh-purge-Agent预设三条重复子任务.md ↔ 工具-dsh-purge-rc2预设加载失败.md | 标题 J=0.6 | 共享根因 `preset-compat.js`，但一是「三条同名子任务 withLegacyChildIds」、一是「红队模式 never started / ERR_PACKAGE_PATH_NOT_EXPORTED」，锚点几乎不重叠 | 非重复·不同现象 |
| 工具-Windows-Low标签导致子进程降级.md ↔ 工具-Windows-Low进程自我提权失败.md | 标题 J=0.5 | 两卡正文互写「那张讲映像标签，这张讲令牌，不是同一现象」 | 非重复·已明示 |
| MuMu-框架-LSPosed注入失败.md ↔ MuMu-框架-ZygiskNext与Magisk冲突.md | 标题 J=0.5 | 一为注入断在 system_server、一为双 Zygisk bootloop，锚点 J=0 | 非重复 |
| 其余 19 对（含 zgate-* ×3、工具-DSH宿主重启/插件市场 ×3 等） | ≤0.33 | 同为项目前缀命中，锚点无实质重叠 | 非重复 |

### 3. 漏登记（卡名交叉引用 / INDEX 消歧）

| 检查面 | 证据 | 判定 |
| --- | --- | --- |
| 卡内「见卡「X」」引用目标是否存在 | 扫全部 64 文件，提取卡名引用，逐一对照 61 张正式卡名：**0 处指向不存在的卡** | 无漏登记 |
| INDEX.md 消歧表 | INDEX.md:22-26 只登记 3 对「卡名分不出来」的消歧，符合 INDEX.md:28-30 自述纪律「只有两张卡现象词太像、光看卡名分不出才加；其余一律不加，逐卡登记会变成两份真相」 | 无漏登记 |
| 验证行引用的 `~/.dsh/tools/*.mjs` 是否存在 | 除两张 purge 卡外全部存在；缺失项已记入死链 D1-D3 | 无额外漏登记 |

### 4. 命令不可复制（整行复制 PowerShell 能否跑）

| 检查面 | 证据 | 判定 |
| --- | --- | --- |
| 两张 purge 卡验证/首选命令 | 见 D1-D3：命令指向的脚本原路径已不存在，整行复制必报「找不到路径」 | **不可复制·真**（3 处） |
| 全卡命令块占位符/全角字符扫描 | 32 处命中：20 处 `<占位>`（`<路径>`、`<ver>`、`<pkg>` 等参数模板）+ 12 处中文注释里的全角标点。均为卡库惯例的参数占位与注释，不属于「命令正文不可复制」 | 其余合规 |
| `~` 家目录写法 | 验证行用 `~/.dsh/tools/...`，PowerShell 原生支持 `~` 展开，整行可复制 | 合规 |

---

## 够格补卡 / inbox 记录

| 来源 | 现象 | 覆盖检查 | 判定 |
| --- | --- | --- | --- |
| _inbox.md:15（2026-11-19，唯一未收口行） | `- [工具] PowerShell Copy-Item -Recurse -Force 源目录到已存在目标目录会嵌一层（大纲\第一卷\大纲\大纲）；目录级还原改为逐文件 Copy-Item。2026-11-19 EmeraldEden 外貌校正踩到。` | 全卡库搜 Copy-Item：仅 `工具-zgate-启动自检拒绝启动与错误不可见.md:30` 命中，但那是「BOM/GBK 编码→改 tools 后 Copy-Item 覆盖」场景，与「目录级 -Recurse 嵌套」无关；未被任何正式卡覆盖 | **留 inbox，不新建卡**。判据：单次踩坑、未复发、解法一句话（逐文件 Copy-Item）、无「代价≥30min/改坏东西」的强证据，未达建卡门槛。若后续复发再补卡。交 lead 复核 |

（_inbox.md 顶部注明 11-12 的 36 条与 11-18 的 18 条均已收口；本轮确认仅 11-19 这一条是未收口行。）

---

## 退役候选（只列不删，移交 lead）

| 卡名 | 退役依据 | 建议 |
| --- | --- | --- |
| 工具-dsh-purge-Agent预设三条重复子任务.md | 卡内 L9 自述「上游已修，补丁可撤（1.6.87 自带后缀、1.6.93 改 return）」；脚本 2026-11-16 已退役至 `_retired/`；现 profile postinstall 仅剩 `purge-hide-revert.mjs` + `verify-patches.mjs`，该补丁段已摘除 | 列退役候选；lead 确认后由 lead 执行退役（本分片不删卡） |
| 工具-dsh-purge-rc2预设加载失败.md | 卡内 L9 自述「上游已修，补丁可撤」；`purge-preset-list-agents-fix.mjs` 同批退役；postinstall 已摘除第 3 段 | 列退役候选；同上 |

依赖提示：这两张卡正是死链 D1-D3 的载体。**若 lead 采纳退役，D1-D3 自动消解（无需修验证行）；若保留，则须把验证/首选命令里的脚本路径改指 `_retired/` 或标注「脚本已退役，仅留档」**。D4（demote 留档路径）与退役无关，独立修：把 L21 `~/.dsh/backups/demote-throttled-hop.mjs.disabled-20261105` 改为 `~/.dsh/tools/demote-throttled-hop.mjs`（现跑 exit 1、只留档别跑的语义不变）。

---

## 核对表（项 / 判定 / 证据）

| 项 | 判定 | 证据（路径:行号 / 实测） |
| --- | --- | --- |
| 门禁 61 卡全绿 | 通过 | 门禁原文 P0=0 / P1=0 / 全部通过，exit 0 |
| 死链 | 4 处真失效（3 卡） | 工具-dsh-purge-Agent预设三条重复子任务.md:5；工具-dsh-purge-rc2预设加载失败.md:5,9；DeepseekHarness-工具-上游429切模型与重试.md:21 |
| 重复 | 0 真重复（23 候选已排除） | Jaccard 对 + 逐卡正文；dsh-宿主-升级前后补丁体检清单.md ↔ dsh-插件-本地手改补丁识别与处置.md 互引互补 |
| 漏登记 | 0 | 卡名交叉引用 0 死链；INDEX.md:22-30 消歧纪律符合 |
| 命令不可复制 | 3 处（与死链 D1-D3 重合） | 同 D1-D3，脚本已退役原路径 MISSING |
| 够格补卡 | 0 张新建 | 唯一未收口 inbox 行 _inbox.md:15 判留 inbox |
| inbox 记录 | 1 条留 inbox | _inbox.md:15，未被正式卡覆盖但未达建卡门槛 |
| 退役候选 | 2 张（只列不删） | 两张 purge 卡，卡内自述已修可撤 + 脚本已退役 + postinstall 已摘段 |

自查：写域仅 procedures（本轮实际未改任何卡）+ 本 evidence 文件；未碰 PROGRESS.md / provider_config.json / docs / tests / ~/.mnemon/* / 技能；未删任何卡；全程未开浏览器。