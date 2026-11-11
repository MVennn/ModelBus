# docs-review 分片报告：文档与命名一致性审查（ZCode 中心 → DSH + 各类 agent）

> **一句话**：分片启动基线里第一方文档仍以 ZCode 为中心（docs/**/*.md 命中 zcod 463 行、DSH 118 行；根 README.md 17/0），主代理已把门面改写成「DSH 主宿主 + 各类 agent」（README.md 8/12）并把 18 个 blob/main 绝对链接改相对链接，但 docs 正本主语与旧脚本名尚未同步；改写必须按「契约层一个字不动 / 实现层去 ZCode / 新层用 agent 词汇」三层口径分层做，禁止全局字面替换。

---

## 0. 取证口径与时点

- 真实项目路径：`F:\Project\ModelBus`；会话工作区 `F:\Project\_merged\DeepseekHarness` 是 junction 合并视图，本分片全部读写穿透真实路径，未在视图根新建目录、未对 junction 做递归删除。
- 本分片**只读分析**，唯一写入产物是本报告 `evidence/agent-docs-review.md`；未改 `PROGRESS.md` / `docs/` / `tests/` / `provider_config.json` / 任何配置 / 历史记录 / 第三方署名；未 git add/commit/push；未重启 zgate；报告不含任何 key/token 真值。
- 两个取证时点，避免行号误导：
  - **T0 = HEAD 基线 / 分片启动采样**（主代理改写前）：「仍以 ZCode 为中心」逐处台账用此 file:line，与 git diff 的 - 侧一致。
  - **T1 = 当前工作树快照**（取样 2026-11-11 15:44 左右，主代理与代码改名分片并行落地）：按主代理 m00085 要求，「当前态」数字以取样时刻为准，验收以改后磁盘复核。
- 可独立复现的计数命令（PowerShell 7+，workdir=`F:\Project\ModelBus`）：

```powershell
$root='F:\Project\ModelBus'
$docFiles=Get-ChildItem -LiteralPath (Join-Path $root 'docs') -Recurse -File -Filter '*.md' -Force | ForEach-Object { $_.FullName }
$rootFiles=@('README.md','AGENTS.md','CONTRIBUTING.md','SECURITY.md','.gitignore','.gitattributes','.editorconfig') | ForEach-Object { Join-Path $root $_ }
$all=$docFiles+$rootFiles
$rows=foreach($f in $all){
  $z=@(Select-String -LiteralPath $f -Pattern '(?i)zcod' -ErrorAction SilentlyContinue).Count
  $d=@(Select-String -LiteralPath $f -Pattern 'DSH|dsh' -CaseSensitive -ErrorAction SilentlyContinue).Count
  [PSCustomObject]@{File=$f.Substring($root.Length+1);Zcod=$z;DSH=$d}
}
$rows | Sort-Object File | Format-Table -AutoSize
'docs_zcod_total=' + (($rows | Where-Object { $_.File -like 'docs*' } | Measure-Object -Property Zcod -Sum).Sum)
'root_zcod_total=' + (($rows | Where-Object { $_.File -notlike 'docs*' } | Measure-Object -Property Zcod -Sum).Sum)
'docs_dsh_total=' + (($rows | Where-Object { $_.File -like 'docs*' } | Measure-Object -Property DSH -Sum).Sum)
'root_dsh_total=' + (($rows | Where-Object { $_.File -notlike 'docs*' } | Measure-Object -Property DSH -Sum).Sum)
```

  实测 `exitCode=0`、stderr 空；同时用 `tools.grep({pattern:'(?i)zcod', path:'F:\Project\ModelBus\docs', include:'*.md'})` 与逐行 Node 统计双通道复核，逐文件数字一致。

| 指标（按行计） | T0 基线 | T1 快照 | 说明 |
|---|---|---|---|
| docs/**/*.md 命中 `zcod` | 463 | 459 | 主代理改 `docs/DSH-FIRST.md`、`docs/README.md` 后减少 4 |
| docs/**/*.md 命中 `DSH\|dsh` | 118 | 122 | 方向正本与门面新增 DSH 主语 |
| 根 7 文件命中 `zcod` | 31 | 18 | 根 README 17→8、CONTRIBUTING 7→4、SECURITY 2→0 |
| 根 7 文件命中 `DSH\|dsh` | 2 | 17 | 根 README 0→12 |
| 全仓命中 `zcod`（仅口径） | 1943 | 未重跑 | 按顶层 docs 463、evidence 651、PROGRESS.md 158、providers 147、tools 128、third-party 99、CHANGELOG.md 91、memories 75、NOTICE 45、tests 30、gateways 24；本分片只管第一方文档 |
| 41 个 docs .md | 是 | 是 | `tools.glob({pattern:'docs/**/*.md'})` |

- 工作树状态（T1，`git -C F:\Project\ModelBus status --short -- README.md docs tools`）：` M README.md`、` M docs/CAPABILITY-AUDIT.md`、` M docs/DSH-FIRST.md`、` M docs/MODEL-PROVIDERS.md`、` M docs/PITFALLS.md`、` M docs/ROUTING-POLICY.md`、` M docs/TROUBLESHOOTING.md`、` M tools/model_alias.py`；`git diff --stat` = `8 files changed, 128 insertions(+), 183 deletions(-)`。stderr 只有 CRLF 提示（`warning: in the working copy of 'README.md', CRLF will be replaced by LF the next time Git touches it`），非错误。
- CodeGraph：`codegraph_status({})` 报 `Project: F:\Project\_merged\DeepseekHarness / [!] Not initialized`，按任务书不 init、不 sync，检索全用 grep / glob / read / pwsh。

---

## 1. 文档清单与各自一行定位

> 行数取 T1 直读值；docs/ 下 41 篇 .md。`docs/README.md` 是唯一索引（`docs/README.md:68-69`、`docs/DOC-RULES.md:159-162`）。

### 1.1 根文件（7 个，本分片范围）

| 文件 | 行数 | 定位 |
|---|---|---|
| `README.md` | 130 | 仓库门面：是什么、环境要求、使用、反馈、免责声明、开源鸣谢、许可证（T1 已改成 DSH 主宿主） |
| `AGENTS.md` | 109 | 仓库机器协议：PROGRESS 分家、凭据环境变量、CodeGraph、目录两轴、zgate 换版；T1 新增当前架构段 `AGENTS.md:6` |
| `CONTRIBUTING.md` | 76 | 参与贡献：跑起来、加新供应商四步、硬规矩、文档门禁、提交前自检 |
| `SECURITY.md` | 41 | 安全策略：收修版本、报告渠道、安全边界、凭据口径 |
| `.gitignore` | 113 | 忽略规则（含 3 处 zcode 注释）；忽略项本身不动 |
| `.gitattributes` | 23 | 换行/属性规则；0 处 zcod / DSH 命中 |
| `.editorconfig` | 22 | 编辑器规则；0 处 zcod / DSH 命中 |

### 1.2 docs 正本与规范（现役，可改主语）

| 文件 | 行数 | 定位 |
|---|---|---|
| `docs/README.md` | 70 | docs/ 唯一索引，改文档必须同步（T1 已改 :14/:28） |
| `docs/DOC-RULES.md` | 167 | 文档规则正本：命名、一句话块、链接、正本唯一、归档只读 |
| `docs/DSH-FIRST.md` | 143 | **DSH 主导方向正本**：三层命名口径、catalog 真源 + 多宿主投影、批 1–批 4、验收（T1 已改） |
| `docs/ARCHITECTURE.md` | 475 | 运行架构整合方案（含已退役守护脚本的过期口径） |
| `docs/MODEL-PROVIDERS.md` | 894 | provider 与模型参数矩阵正本：四步方法、配置落点、7 个 upstreams |
| `docs/MODEL-ALIAS.md` | 608 | 统一模型命名与分组、alias map 生成口径 |
| `docs/MODEL-STREAM.md` | 198 | 流式/思考/输出/TPS 自动准入 |
| `docs/ROUTING-POLICY.md` | 278 | 路由策略正本：逐跳参数、链预算、单跳豁免 |
| `docs/TOOLS.md` | 110 | 工具清单与产物落点 |
| `docs/MAINTENANCE.md` | 447 | 维护流程：刷价、探测、备份回退、热重载、计划任务、zgate 生命周期 |
| `docs/SECRETS.md` | 348 | 凭据与环境变量索引（只写变量名） |
| `docs/CONSOLE.md` | 361 | ModelBus 控制台设计稿：页面清单、数据源映射、验收 |
| `docs/PITFALLS.md` | 920 | 踩坑总汇（机制解释） |
| `docs/TROUBLESHOOTING.md` | 707 | 排错手册（现象 → 步骤 → 解法） |
| `docs/CAPABILITY-AUDIT.md` | 380 | 模型能力配置审计（2026-11-10 起，含 2026-11-11 落地更新） |
| `docs/ZGATE-LIFECYCLE.md` | 311 | zgate 生命周期正本：部署、计划任务、换版、日志 |
| `docs/BENCHMARKS.md` | 462 | 外部跑分与榜单扩充口径 |
| `docs/UPSTREAM.md` | 430 | 14 个同类开源项目调研 + vendored 来源凭证（事实引用，不宜改主语） |
| `docs/QODER.md` | 205 | Qoder（qoder2api-hub）接入实例 |
| `docs/QWEN.md` | 355 | 千问 AI 平台接入实例 |
| `docs/QINIU.md` | - | 七牛云 AI 网关接入实例（0 处 zcod / DSH 命中） |
| `docs/VERSIONING.md` | 108 | 版本命名规范 |

### 1.3 历史 / 归档 / 发布说明 / 报告（禁改类，见 §5）

| 文件 | 定位 |
|---|---|
| `docs/MODEL-QUICK-REF.md` | 2026-10-20 速查快照，标题自带「历史快照」；AGENTS.md §5 明令不动 |
| `docs/REVIEW-2026-11-10.md` | 2026-11-10 改动复盘，日期化历史记录 |
| `docs/archive/OPENCODE-GO-ANALYSIS.md` | 2026-10-19 阶段性分析归档；`docs/DOC-RULES.md:152-153` 归档件只读 |
| `docs/release-notes/README.md` | release-notes/ 格式正本（形状、动词、覆盖率红线、固定尾巴） |
| `docs/release-notes/0.1.0.md` … `0.6.0.md` | 6 份已发布版本说明，固定尾巴含旧仓名 Issues 链接 |
| `docs/reports/README.md` | 模型同步报告索引 |
| `docs/reports/MODEL-SYNC-20261106-1200.md` 等 8 份 | 自动化同步报告快照（2026-11-06/09/10/11），0 处 zcod / DSH 命中 |

---

## 2. 仍以 ZCode 为中心的表述逐处台账（file:line / 原句 / 改写建议）

### 2.1 改写总原则：三层口径（不得全局替换）

证据：`docs/DSH-FIRST.md:31`（T0/T1 同义）把 `~/.zcode/v2/provider_config.json`、`ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` / `ZCODE_BUILTIN`、`third-party/zcode/` 与 `third-party/zcodium/` 原件、ZCode schema 键（`providerConfigRules` / `modelConfigRules.providerModelRules` / `modelOrder` / `personalModelIds` / `optionSpecs.reasoningLevel.{values,map}`）、`%LOCALAPPDATA%\ZCodeGateway\`、NOTICE 版权商标段定为「**契约层**（外部世界定的，改了就坏）… **一个字都不动**」；`docs/DSH-FIRST.md:32` 才把脚本名、自造 env、36 篇文档措辞列为「实现层（可改）… 改中性名，旧名保留一个读取别名；文档主语改成『宿主 / 客户端』」；`docs/DSH-FIRST.md:33` 新层用 catalog / capabilities / routing policy / host projection / agent profile。T1 的 `AGENTS.md:6` 与 `docs/DSH-FIRST.md:3` 已把这条定为全仓当前架构。

**结论**：用户说的「对 Zcode 字符等进行替换」只作用于实现层；对契约层、历史归档、发布说明、许可证、第三方署名做字面替换会破坏外部契约与署名，主代理 m00054 已确认这一判定。

### 2.2 门面 / 机器协议 / 贡献 / 安全 / 索引 / 方向正本逐处台账

> 「原句」取 T0 基线（git diff 的 - 侧）；「T1 现状」取 2026-11-11 15:44 直读；建议为主语改写方向。

| file:line（T0） | 原句（T0） | 改写建议 | T1 现状 |
|---|---|---|---|
| `README.md:7` | `**把模型供应商接进 ZCode 客户端的脚本与文档**` | 改为「**DSH 主宿主 + 各类 agent 的模型目录与路由工具仓**」 | 已改（`README.md:7`） |
| `README.md:9` | `不改 ZCode 的代码，只写它的配置文件。` | 改为「一份 `catalog/` 模型目录真源，投影到 DSH 的 `cordis.patch.yml`；各类 agent 共用同一份路由策略。」 | 已改 |
| `README.md:22` | `- **同步** —— …写进 ZCode 的模型列表；` | 写进 `catalog/` 真源，再投影到 DSH 与兼容投影 | 已改（`README.md:22`） |
| `README.md:30` | `**边界**：本仓库**不含 ZCode 客户端**，只读写它的配置文件 provider_config.json` | 增列「不含 DSH 宿主」；配置改称「DSH 侧 `cordis.patch.yml` + 兼容投影 `provider_config.json`」 | 已改（`README.md:35`） |
| `README.md:38` | `\| 客户端 \| ZCode 桌面端（Windows） \|` | 拆成「主宿主 = DSH（DeepSeekRuntime）」+「兼容投影 = ZCode 桌面端（可选）」两行 | 已改（`README.md:43-44`） |
| `README.md:40` | `\| 配置与凭据 \| ZCode 的 provider_config.json（默认在 ~/.zcode/v2/）…` | 主配置改 DSH `cordis.patch.yml`；`~/.zcode/v2/` 保留为契约路径 | 已改（`README.md:46`） |
| `README.md:50` | `…qoder_zcode_sync.py 每次现拉 /v1/models。` | 脚本名按批 2 映射去 ZCode | 已改（`README.md:56` 用 `qoder_sync.py`） |
| `README.md:52` | `必须用 ZCode 的真实请求体：裸 body 能通不代表 ZCode 能通。` | 改「按宿主生效请求体探测（`effective_body.js` 复刻规则合并语义）」 | 已改（`README.md:58`） |
| `README.md:59` | `python tools/model_alias.py --slot auto --probe-file ~/.zcode/v2/model_probe.json --apply` | **保留**：`~/.zcode/v2/model_probe.json` 是契约层活数据路径 | T1 仍保留（`README.md:65`） |
| `README.md:66` | `旧的 go_model_sync.py / workbuddy_zcode_sync.py / qoder_zcode_sync.py 现在只作` | 旧名同步去 ZCode | 已改（`README.md:72`） |
| `README.md:71` | `model_alias.py 会**先备份再原子替换** provider_config.json；ZCode 约 1 秒轮询该文件，` | 主语改「兼容投影端约 1 秒轮询」，补「DSH 侧消费 `cordis.patch.yml`」 | 已改（`README.md:77`） |
| `README.md:87` | `- 涉及的模型与 provider、ZCode 版本` | 改「DSH profile 版本（或兼容宿主版本）」 | 已改（`README.md:93`） |
| `README.md:96` | `- 脚本会修改**你自己的** ZCode 配置文件，写之前会自动备份` | 改「宿主配置（DSH `cordis.patch.yml` / 兼容投影 `provider_config.json`）」 | 已改（`README.md:102`） |
| `README.md:103` | `「ZCode」「OpenCode Zen / Go」等商标、标识的权利均归其权利人所有…` | **保留**：NOTICE 商标段契约层 | T1 仍保留（`README.md:109`） |
| `README.md:115` | `\| [**ZCode**](https://github.com/zai-org/ZCode) \| 目标客户端，本仓改它的配置并复刻它的请求体语义（Apache-2.0） \|` | 用途改「兼容投影宿主…保留其配置落点并复刻其规则合并语义」，署名/链接保留 | 已改（`README.md:121`） |
| `README.md:116` | `\| [**ZCodium**](https://github.com/ZCodium-project/ZCodium) \| ZCode 的 MIT 授权独立审计 fork…` | **保留**：第三方事实与署名 | T1 仍保留（`README.md:122`） |
| `AGENTS.md:49` | `\| ZCode 配置文件路径 \| 环境变量 **ZCODE_PERSONAL_PROVIDER_CONFIG_FILE** \|` | **保留变量名**（契约层）；表格可加注「外部契约名，保持不变」 | T1 表格已移位/扩充；`AGENTS.md:6` 新增当前架构段 |
| `AGENTS.md:50` | `\| ZCode 内置规则文件 \| 环境变量 **ZCODE_BUILTIN** \|` | **保留变量名**（契约层） | 同上；`CONTRIBUTING.md:33` 已注明「兼容投影的内置规则文件路径（外部契约名，保持不变）」 |
| `CONTRIBUTING.md:31` | `\| ZCODE_BUILTIN \| ZCode 内置规则文件路径 \|` | 变量名保留，说明改「兼容投影的内置规则文件路径」 | 已改（`CONTRIBUTING.md:33`） |
| `CONTRIBUTING.md:41` | `3. 用 **ZCode 的真实请求体**探测哪些模型真能用` | 改「用 **宿主生效请求体**探测」 | 已改（`CONTRIBUTING.md:43`） |
| `CONTRIBUTING.md:44` | `**不用改**的是 ZCode 侧的三处落点与 reasoningLevel.map 的覆盖机制。` | 改「兼容投影侧的三处落点」 | 已改（`CONTRIBUTING.md:46`） |
| `CONTRIBUTING.md:51` | `ZCode 已开源（Apache-2.0），vendored 副本在 third-party/zcode/，` | 主语可改「上游已开源…vendored 副本在 `third-party/zcode/`」，目录名保留 | 已改（`CONTRIBUTING.md:52-55`，脚本名改 `effective_body.js`） |
| `SECURITY.md:29` | `- 探测会用 **ZCode 的真实请求体**（含思考参数）。这是本仓能测准的唯一原因，` | 改「**宿主生效请求体**（规则合并语义见 `providers/workbuddy/effective_body.js`）」 | 已改（`SECURITY.md:29,31`） |
| `docs/README.md:14` | `…**provider 与模型参数正本**：接供应商的四步方法、ZCode 配置落点、7 个 upstreams…` | 索引描述改「兼容投影配置落点」 | 已改（`docs/README.md:14`） |
| `docs/README.md:28` | `…三层命名口径（契约层不动 / 实现层去 ZCode / 新层用 agent 词汇）…批 1–批 4 落地顺序` | 改成「当前架构 + 实现层已去 ZCode」，同步索引 | 已改（`docs/README.md:28`） |
| `docs/README.md:54,59` | `NOTICE 第三方声明…ZCode（Apache-2.0）等 / third-party/…ZCode 规则数据与引擎源码、ZCodium 规则切片` | **保留**：第三方署名与来源凭证 | T1 仍保留 |
| `docs/DOC-RULES.md:48` | `\| 脚本改 ZCode 配置的哪几处、两个 --apply 脚本的行为差异 \| [MODEL-PROVIDERS.md] §1、§1.1 \|` | 正本映射表描述改「兼容投影配置的哪几处」；指向 MODEL-PROVIDERS.md 不变 | **T1 未改**，待安排 |
| `docs/DOC-RULES.md:50` | `\| 写配置期间与 ZCode 界面的互斥、热重载注意事项 \| [MAINTENANCE.md] §5…` | 描述改「兼容投影界面的互斥」 | **T1 未改**，待安排 |
| `docs/DSH-FIRST.md:3` | `> 一句话：**这个仓库从「给 ZCode 客户端写配置的脚本集」改成…DSH 是主宿主，ZCode 降为一个投影目标，多 agent 是远期扩展位。**` | 改「现在是…多 agent 已是当前架构；命名按三层口径分层处理，对外契约一个字不动」 | 已改（`docs/DSH-FIRST.md:3`） |
| `docs/DSH-FIRST.md:21,25` | `\| 主宿主 \| ZCode 桌面端读 provider_config.json \| DSH 读 cordis.patch.yml… \| / \| 扩展 \| 单客户端、单用户 \| 多 agent（每 agent 一套路由与预算）。\|` | 对照表「现状」列改已落地口径；多 agent 从「远期」改「当前架构」 | 已改（`docs/DSH-FIRST.md:21,25`） |
| `docs/DSH-FIRST.md:32` | `\| **实现层**（本仓自有命名，可改） \| workbuddy_zcode_sync.py … qwen_zcode_sync.py；自造 env WB_ZCODE_PROBE_FILE…` | 改「（已改）」并列出 6 个新名 + 新 env，旧名保留读取别名 | 已改（`docs/DSH-FIRST.md:32,35,85`） |

### 2.3 docs 正本逐文件台账（代表行 + 命中规模 + 改写建议）

| 文件（T1 命中 zcod/DSH 行数） | 代表行 file:line + 原句（T1 仍为 ZCode 主语） | 改写建议 | 分类 |
|---|---|---|---|
| `docs/MODEL-PROVIDERS.md`（41/3） | `:3` `> **一句话**：ZCode 里现在有哪几个 provider…`；`:69` `## 1. ZCode 侧的关系：配置落点与写入行为`；`:37` `必须用 **ZCode 真实请求体** + 限速` | 一句话与 §1 标题改「兼容投影侧 / 宿主生效请求体」；`:73` 的 `~/.zcode/v2/provider_config.json` 保留 | 主语 + 脚本名 |
| `docs/TROUBLESHOOTING.md`（47/4） | `:23` `## 1. ZCode 里模型列表不刷新 【通用】`；`:25` `**现象**：…但 ZCode 的模型列表里没有新模型；`；`:450` `重跑 qoder_zcode_sync.py --apply` | 现象/标题改「兼容投影里…」；脚本名同步；`ZCODE_BUILTIN` 等 env 保留 | 主语 + 脚本名 |
| `docs/MAINTENANCE.md`（39/4） | `:151` `### 2.3 探测必须用 ZCode 真实 body`；`:224` `## 5. ZCode 配置热重载的注意事项`；`:230` `写配置期间不要在 ZCode 界面里改` | 标题/步骤改「宿主生效 body / 兼容投影热重载 / 兼容投影界面」 | 主语 + 脚本名 |
| `docs/ARCHITECTURE.md`（31/0） | `:27` `\| 生命周期守护 \| workbuddy/zcode_gateway_watch.ps1（PowerShell，常驻） \| … \| ✅ 必须换掉…`；`:316` `- P1：zgate uninstall → 重新 zcode_gateway_watch.ps1 -Install。` | 该脚本已退役（`docs/DSH-FIRST.md:127` 自己列为过期口径），删除回退命令、正文标「已退役」；`%LOCALAPPDATA%\ZCodeGateway\` 保留（契约目录） | 过期口径 + 主语 |
| `docs/PITFALLS.md`（29/22） | `:6` `标 **【通用】** 的坑换任何供应商都成立（ZCode 客户端侧的行为）`；`:45` `## 2. ZCode 内置通用规则无条件发思考字段 → 400`；`:179` `## 8. ZCode 配置会被界面覆盖` | 分类说明改「兼容投影侧行为」；机制解释里的「ZCode 内置规则」属事实引用可保留并补「兼容投影宿主」限定 | 主语 |
| `docs/TOOLS.md`（29/4） | `:8` `tools/model_alias.py 是 ZCode 配置的**唯一最终写入者**`；`:21` `\| 客户端 \| ZCode 桌面端（Windows） \|`；`:35` `dsh_sync.py 读 ZCode 最终 provider_config.json…` | 工具表改「兼容投影最终写入者 / 兼容投影宿主」；6 个脚本名按映射同步；`:57` 归档脚本 `validate_zcode_models.py` 保留（已归档） | 主语 + 脚本名 |
| `docs/SECRETS.md`（24/0） | `:17` `- **ZCode 的 provider_config.json 本身就带 apiKey**`；`:91` `### 3.4 ZCode 配置文件路径`；`:96` `环境变量 **ZCODE_PERSONAL_PROVIDER_CONFIG_FILE**` | 标题/说明改「兼容投影配置文件路径」；**变量名与 `~/.zcode/v2/` 路径全部保留**（契约层 + 凭据口径）；脚本名同步 | 主语 + 脚本名（变量名保留） |
| `docs/QODER.md`（23/0） | `:8` `qoder_probe_zcode.py /` `:9` `qoder_zcode_sync.py 仅作数据采集与兼容。`；`:17` `\| 上游 \| 适配器 \| 端口 \| 在 ZCode 里的形态 \|` | 表头改「在兼容投影里的形态」；脚本名同步 | 主语 + 脚本名 |
| `docs/CAPABILITY-AUDIT.md`（17/29） | `:7` `…剩下的来自 ZCode 内置规则里一条 .* 兜底…`；`:20` `…全靠 ZCode 内置规则猜`；`:356` `改它只为 ZCode 侧一致` | 本文是日期化审计（T1 已被主代理追加 2026-11-11 落地更新），机制叙述属事实引用；仅把「ZCode 侧」改「兼容投影侧」即可，不改结论 | 主语（轻改） |
| `docs/BENCHMARKS.md`（15/5） | `:180` `它在 ZCode 侧走 opencode-go-messages` | 改「兼容投影侧」；`~/.zcode/v2/arena-*.json` 路径保留 | 主语 |
| `docs/DSH-FIRST.md`（12/21） | `:23` `\| 命名 \| 脚本名、函数名、文档主语都是 ZCode \| 内部分层去 ZCode；对外契约原样保留 \|` | 对照表「现状」列是历史描述，保留即可；:50 架构图里的 `zcode_provider_` 建议改中性 sink 名 | 方向正本，已大体改完 |
| `docs/MODEL-ALIAS.md`（11/3） | `:16` `\| ~/.zcode/v2/provider_config.json \| ZCode 看到的三个 provider 与显示名列表 \|`；`:253-254` `DSH 的 zcode-main 型号表由这份配置直接投影` | 说明改「兼容投影看到的三个 provider」；`zcode-main` 是 DSH 侧 provider id（事实/契约），保留 | 主语（轻改） |
| `docs/QWEN.md`（10/0） | `:124` `经 7871 用 ZCode 真实 body 打一遍`；`:275` `走的就是 ZCode 的真实路径。` | 改「宿主生效 body / 兼容投影的路径」；脚本名 `qwen_zcode_sync.py` 同步 | 主语 + 脚本名 |
| `docs/archive/OPENCODE-GO-ANALYSIS.md`（9/0） | 归档分析全文 | **禁改**（`docs/DOC-RULES.md:152-153`），索引里标历史 | 归档 |
| `docs/CONSOLE.md`（8/0） | `:28` `散在 ~/.zcode/v2/、…%LOCALAPPDATA%/ 四个根下`；`:51-53` 数据源表全为 `~/.zcode/v2/*.json` | 数据源路径是契约层（活数据真实位置）**保留**；说明文字可加「兼容投影数据根」限定 | 契约路径保留 |
| `docs/release-notes/0.1.0.md`（7/0）等 6 份 | 固定尾巴「请附上 ZCode 版本」 | **禁改**（已发布版本说明） | 发布说明 |
| `docs/release-notes/README.md`（5/0） | 格式正本里的模板尾巴 | 模板可改；已发布 6 份不动 | 格式正本 |
| `docs/MODEL-QUICK-REF.md`（4/0） | `:8` `> ZCode 里 chat 按成本档拆成 4 组…` | **禁改**（AGENTS.md §5 明令不动；标题自带历史快照） | 历史快照 |
| `docs/README.md`（3/4） | `:54,59` 第三方署名 | 保留；索引已同步 :14/:28 | 索引 |
| `docs/REVIEW-2026-11-10.md`（3/8） | `:22` `**仅 ZCode 客户端可见**`；`:55` `只影响 ZCode 客户端的选择器` | **禁改**（日期化复盘，当时事实） | 历史复盘 |
| `docs/ZGATE-LIFECYCLE.md`（3/6） | `:84,130,299` `%LOCALAPPDATA%\ZCodeGateway` | **保留**：契约目录，改了就找不到日志/脚本 | 契约路径 |
| `docs/DOC-RULES.md`（2/0） | `:48,50` 见 2.2 表 | 正本映射表描述改「兼容投影」 | 主语（轻改） |
| `docs/MODEL-STREAM.md`（1/5） | `:29` `provider 以 zcode- 开头的模型表。tools/dsh_sync.py --apply 从 ZCode 最终` | `zcode-` 前缀与 `zcode-main` 是事实/契约 id 保留；「从 ZCode 最终」改「从兼容投影」 | 主语（轻改） |
| `docs/ROUTING-POLICY.md`（1/0） | `:241` `也不要手改 ~/.zcode/v2/model-alias-map.json` | **保留**：契约活数据路径 | 契约路径 |
| `docs/UPSTREAM.md`（73/0） | `:46` `\| zai-org/ZCode \| 8028 \| Apache-2.0 \| … \| 目标客户端本体 \|`；`:63` `### 3.1 AnyBridge —— 唯一认真实现了 ZCode 配置写入的开源项目`；`:80` `ZCode 的写入路径是 ~/.zcode/v2/config.json…` | **基本保留**：第三方项目名、star 数、license、SHAs、vendored 来源凭证是事实引用；仅可把「目标客户端本体」改「兼容投影宿主本体（调研时）」并补一句时点说明，不改表格数字与 URL | 事实引用 |
| `docs/VERSIONING.md`、`docs/QINIU.md`、`docs/reports/*`（0/0 或 0/1） | 无 ZCode 中心表述 | 无需改写 | 无 |

### 2.4 额外发现（与命名一致性相关）

1. **链接形态违规（T0）**：README.md 29 个 markdown 链接里 24 个是 github.com 绝对链接，其中 18 个指向本仓 `blob/main`，与 `docs/DOC-RULES.md:105-107`「链接到**本仓的文件**一律相对链接」冲突。T1 已由主代理改为 `blobMain=0`、`github=6`（仅 badge / Issues / 4 个第三方项目 URL）、`relativeOrOther=24`，冲突消除。
2. **契约层不得替换**（`docs/DSH-FIRST.md:31`、T1 `AGENTS.md:6`）：`~/.zcode/v2/*`、`ZCODE_PERSONAL_PROVIDER_CONFIG_FILE`、`ZCODE_BUILTIN`、`third-party/zcode*` 原件、`%LOCALAPPDATA%\ZCodeGateway\`、`zcode-main` / `zcode-*` provider id、schema 键、NOTICE 商标段。
3. **索引同步义务**：`docs/README.md:68-69`、`docs/DOC-RULES.md:135` 要求新增/删除/改名文档同步索引并全仓 grep 旧名；`docs/DOC-RULES.md:108-114` 要求双向点验出链入链。若新增「DSH 面向适配」独立文档，必须进 `docs/README.md` 索引，否则 `tools/check-docs.py:168-169` 报孤儿。
4. **根 dotfiles**：`.gitignore:2` `# zcode-ai-models —— 忽略规则`、`.gitignore:33` `# 注意：…wb_zcode_probe.json（账号池探测结果）`、`.gitignore:111` `# 日志现在写到 %LOCALAPPDATA%\ZcodeAIModels\logs\，这里再兜一层。` 属于注释/历史忽略项；注释可改中性名，但**忽略项路径必须与代码实际产物一致**（`wb_zcode_probe.json`、`ZcodeAIModels\logs\` 若随改名同步则一并改，否则保留）。`.gitattributes` / `.editorconfig` 0 命中，无需处理。

---

## 3. 相对链接可打开性抽查

### 3.1 抽查方法（可独立复现，纯只读）

在 `run_code` 内用 `node:fs/promises` + `node:path`：枚举 30 篇第一方文档（根 4 篇 + docs 下 26 篇核心/索引/规范/历史），逐行按正则 `/\[[^\]]*\]\(([^)]+)\)/g` 抽链接（与 `tools/check-docs.py:37` 的 `LINK` 同形）；`http/https/mailto` 跳过；`#锚点` 用 `anchorsOf`（收集 `<a id="...">` 与 `^#{1,6}\s+(.*)$` 经 `slugify`，口径同 `tools/check-docs.py:45-48,98-107`）；`^文档名\.md#` 示例串跳过；其余以当前文件 dirname 做 `path.resolve` 后 `fs.access` 判存在，带 frag 且目标为 .md 时复核目标锚点集合。

### 3.2 抽查清单与结果

| 项 | 数值 / 结果 |
|---|---|
| 抽查文件数 | 30 |
| 抽到 markdown 链接总数 | 484 |
| 跳过 http/https/mailto | 47 |
| 实际校验本地目标 | 436 |
| 目标不存在（死链） | **0** |
| 锚点缺失 | **0** |
| README.md 的 18 个本仓 blob/main 绝对链接映射本地目标 | 18/18 全部存在 |

抽样清单（前 18 条，全 `[OK]`）：

```text
AGENTS.md -> docs/DOC-RULES.md [OK]   (×2，另有 docs/ZGATE-LIFECYCLE.md [OK])
CONTRIBUTING.md -> docs/MODEL-PROVIDERS.md [OK]
CONTRIBUTING.md -> docs/DOC-RULES.md [OK]
SECURITY.md -> docs/SECRETS.md [OK]
docs/README.md -> DOC-RULES.md [OK]
docs/README.md -> MODEL-PROVIDERS.md [OK]
docs/README.md -> MODEL-ALIAS.md [OK]
docs/README.md -> QODER.md [OK]
docs/README.md -> QWEN.md [OK]
docs/README.md -> QINIU.md [OK]
docs/README.md -> MODEL-QUICK-REF.md [OK]
docs/README.md -> archive/OPENCODE-GO-ANALYSIS.md [OK]
docs/README.md -> ARCHITECTURE.md [OK]
docs/README.md -> DSH-FIRST.md [OK]
README.md blob/main -> docs/MODEL-PROVIDERS.md / docs/TOOLS.md / docs/SECRETS.md /
  docs/MAINTENANCE.md / docs/ZGATE-LIFECYCLE.md / docs/BENCHMARKS.md /
  docs/MODEL-ALIAS.md / CONTRIBUTING.md / SECURITY.md / NOTICE / docs/UPSTREAM.md /
  LICENSE —— 全部「本地存在」
```

### 3.3 结论

链接**可打开性**本身没有死链或悬空锚点；问题在**形态**：T0 的 README.md 用绝对 URL 链到本仓文件，违反 `docs/DOC-RULES.md:105-107`，且 `tools/check-docs.py:142-144` 还会用 `git ls-files` 校验相对目标是否被跟踪（绝对 URL 被 `tools/check-docs.py:127-133` 直接跳过，等于这部分链接没被门禁覆盖）。T1 已改相对链接，形态与门禁同时对齐。历史/归档文档里的 `https://github.com/MVennn/ZcodeAIModels/...` 旧仓名链接属发布说明固定尾巴，按 §5 禁改。

---

## 4. 「DSH 面向适配」章节正文草稿（给正文，不落盘）

> 建议：优先**改写** `docs/DSH-FIRST.md` 的 §1/§5（它已是方向正本，避免第二处正本，符合 `docs/DOC-RULES.md:39`「每条规则只在一篇文档里定义」）；若主代理坚持独立成篇，文件名按 `docs/DOC-RULES.md:24-28` 用 `ALL-CAPS-WITH-HYPHENS.md`，并同步 `docs/README.md` 索引。以下正文可直接整段贴入，已带「一句话」引言块。

```markdown
## DSH 面向适配：主宿主、契约边界与多 agent 投影

> **一句话**：ModelBus 以 DSH 为主宿主，会话 / 子代理 / headless / 服务插件等各类 agent 共用 `gateways/zgate` 单一入口与同一份路由策略；`catalog/` 是模型目录真源，DSH 与 ZCode 都是它的投影，其中 ZCode 只作兼容投影，对外契约一个字不动。

### 主宿主与投影关系

- **真源**：`catalog/` 保存模型目录、能力元数据（每条带 `source` + `confidence`）与路由策略；投影器只写真源派生的落点，不写回真源。
- **主宿主 DSH**：`tools/dsh_sync.py` 把目录投到 `~/.dsh/profiles/<profile>/cordis.patch.yml` 的 `llm-pi-ai` 段；DSH 负责 agent 运行时，ModelBus 负责模型供给与路由策略，边界就是 `cordis.patch.yml`（目录）与 `llm/stream`（路由改写点）。
- **各类 agent**：会话、子代理、headless、服务插件共用 `127.0.0.1:7871` 单一入口；`tools/agent_profiles.py` 给每类 agent 提供只读投影接口，per-agent 预算与冷却按 `X-Agent-Id`（或 preset id）分桶。新增 agent 类型不新增一份模型清单。
- **兼容投影 ZCode**：`~/.zcode/v2/provider_config.json` 仍被支持，但不再是中心；探针请求体按该宿主的规则合并语义复算，裸 body 通过不代表按宿主规则合并后能通。

### 三层命名口径（替换动作的唯一边界）

| 层 | 内容 | 处置 |
|---|---|---|
| **契约层** | `~/.zcode/v2/provider_config.json` 及其同目录活数据、`ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` / `ZCODE_BUILTIN`、`third-party/zcode/` 与 `third-party/zcodium/` 原件、ZCode schema 键、`zcode-main` / `zcode-*` provider id、`%LOCALAPPDATA%\ZCodeGateway\`、NOTICE 版权商标段 | **一个字不动**；文档里只改它们的「称呼」，不改字面量 |
| **实现层** | 本仓自有的脚本名 / 缓存名 / 自造 env / 文档主语 | 改中性名，旧名保留一个读取别名；文档主语改成「宿主 / 兼容投影 / 各类 agent」 |
| **新层** | catalog、capabilities、routing policy、host projection、agent profile | 新建即用这套词，不再造 ZCode 词汇 |

### 文档与验收

- 文档主语一律以「DSH 主宿主 + 各类 agent」起手，ZCode 只以「兼容投影」身份出现；第三方项目名、许可证、SHAs、商标段原样保留。
- 链接到本仓文件一律相对链接（`docs/DOC-RULES.md:105-107`）；新增/改名文档同步 `docs/README.md` 索引，孤儿零容忍。
- 改完按 `CONTRIBUTING.md:59-63` 跑 `python3 tools/check-docs.py`，或按方向正本 `docs/DSH-FIRST.md:135-140` 跑 `python -B tools/check-docs.py` 到 exit 0；同组另有 `unittest` / `check-project.py` / `dsh_sync.py --check` / `model_caps.py --check` 四条验收。
```

---

## 5. 历史归档 / 发布说明 / 许可证 / 第三方署名：禁止改写清单

| 路径 | 类型 | 禁改依据 | 实测证据 |
|---|---|---|---|
| `LICENSE` | 许可证 | 法律文本 | 1063 B，head `MIT License / Copyright (c) 2026 M.Venn` |
| `NOTICE` | 第三方署名/许可声明 | `docs/DSH-FIRST.md:31` 把「NOTICE 里的版权与商标段」列进契约层 | 16221 B，head 含 WorkBuddy2API Panel / qoder2api-hub / OpenCode Go / ZCode / Python / Node.js |
| `CHANGELOG.md` | 历史更新日志 | 任务书明令不改历史记录 | 147023 B，head `# 更新日志` |
| `PROGRESS.md` | 进度台账（全仓唯一） | `AGENTS.md §1` + 任务书 | 283492 B，head `# PROGRESS — AI 模型接入 ZCode` |
| `memories/`、`evidence/`（除本分片报告） | 历史/证据快照 | 任务书 + `docs/DOC-RULES.md:152-153`「归档件只读…发现其中有错也不要就地改」 | 目录存在；`tools/check-docs.py:25-31` 的 `SKIP_DIRS` 也跳过 |
| `docs/archive/`（`OPENCODE-GO-ANALYSIS.md`） | 归档分析 | `docs/DOC-RULES.md:152-153`；`tools/check-docs.py:35` `FROZEN_DIRS` 含 `docs/archive/` | 14799 B，head 自述「结论已被…取代大半，故归档」 |
| `docs/MODEL-QUICK-REF.md` | 历史快照 | `AGENTS.md §5` 明令「不要动」 | 7333 B，标题含「历史快照」 |
| `docs/REVIEW-2026-11-10.md` | 日期化改动复盘 | 当时事实，改了等于篡改历史 | 18625 B，head `# 2026-11-10 ModelBus 改动复盘` |
| `docs/release-notes/README.md` | 发布说明格式正本 | 定义已发布说明的形状/固定尾巴 | 8757 B |
| `docs/release-notes/0.1.0.md` … `0.6.0.md` | 6 份已发布 Release 说明 | 已发布内容不改；固定尾巴含旧仓名 `ZcodeAIModels` Issues URL | `0.1.0.md` 3438 B；`0.2.0–0.6.0.md:3` 均含「请附上 ZCode 版本」 |
| `docs/reports/*.md`（8 份 + README.md） | 自动化同步报告快照 | 机器产物/历史快照 | `docs/reports/README.md` 1152 B；8 份 0 处 zcod / DSH 命中 |
| `third-party/zcode*` 原件（含 LICENSE / NOTICE / 规则切片） | vendored 上游 | 任务书「保留上游署名」+ `docs/DSH-FIRST.md:31` 契约层 + `AGENTS.md §5`「不要改 third-party/」 | `docs/UPSTREAM.md:397-400` 逐字抄录与来源凭证 |
| `gateways/upstream/` | 上游 clone（gitignored） | `tools/check-docs.py:33` `SKIP_REL_PREFIXES` | 不属第一方文档 |
| `docs/split/` | 冻结目录（当前不存在） | `tools/check-docs.py:35` `FROZEN_DIRS` | fs.stat 报 MISSING |

> 例外：`docs/release-notes/README.md` 是**格式正本**，主代理可改「未来模板」里的尾巴；已发布的 6 份不动。`docs/UPSTREAM.md` 中的第三方项目名、star 数、license、commit SHA 是事实引用，也不得改写（见 2.3）。

---

## 6. tools/check-docs.py 调用方式与门禁判据（只报告，不执行改动）

脚本共 181 行，已全文读取。

### 6.1 调用方式

```text
python tools/check-docs.py            # 检查全仓（跳过 third-party/、gateways/upstream/ 等不入库目录）   ← tools/check-docs.py:6
python tools/check-docs.py docs/      # 只检查指定子目录                                              ← tools/check-docs.py:7
python -B tools/check-docs.py         # 验收口径写法（不写 .pyc），见 docs/DSH-FIRST.md:137
退出码：0 全部通过 / 1 有问题。                                                                    ← tools/check-docs.py:10
```

`tools/check-docs.py:110-111`：`def main() -> int:` / `targets = sys.argv[1:] or ["."]`；`tools/check-docs.py:24`：`ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))`；`tools/check-docs.py:180-181`：`if __name__ == "__main__": raise SystemExit(main())`。

### 6.2 门禁判据逐条（exit 0 的充要条件）

| # | 判据 | 源码位置 | 失败输出 |
|---|---|---|---|
| 1 | 至少找到一个 .md | `tools/check-docs.py:113-115` | `没有找到 .md 文件` → return 1 |
| 2 | 链接目标存在（相对路径，按 os.path 解析） | `tools/check-docs.py:137-140` | `{rel}: 链接目标不存在 → {link}` |
| 3 | 链接目标被 git 跟踪（`git ls-files -z`，`tools/check-docs.py:73-86`） | `tools/check-docs.py:142-144` | `{rel}: 链接目标不会进仓库（未跟踪或被 .git/info/exclude 挡住）→ {link}` |
| 4 | 文内 `#锚点` 存在 | `tools/check-docs.py:127-133` | `{rel}: 锚点不存在 → {link}` |
| 5 | 跨文件 `xxx.md#frag` 的目标锚点存在（`anchors_of`，`tools/check-docs.py:98-107`） | `tools/check-docs.py:154-157` | `{rel}: 目标锚点不存在 → {link}` |
| 6 | 头 10 行含「一句话」引言块（`ONE_LINER_HEAD = 10`，`tools/check-docs.py:41`；例外：根 README.md、docs/DOC-RULES.md、docs/release-notes/ 开头） | `tools/check-docs.py:159-164` | `{rel}: 开头缺少「一句话」引言块` |
| 7 | docs/ 下无孤儿（被任一文档链接，或已进 `docs/README.md` 索引） | `tools/check-docs.py:168-169` | `{rel}: 孤儿文档 —— 没有被任何文档引用（也未进 docs/README.md 索引）` |
| 8 | 汇总：有 problems → `[FAIL] {len(problems)} 个问题：` + return 1；否则 `[OK] {len(mds)} 篇文档全部通过（链接 / 锚点 / 引言块 / 孤儿）` + return 0 | `tools/check-docs.py:171-177` | - |

配套常量：`tools/check-docs.py:25-31` `SKIP_DIRS = {.git, node_modules, dist, __pycache__, third-party, memories, evidence, .work, .codegraph, .workbuddy, vault}`（**本报告在 evidence/ 下，不进门禁统计**）；`:33` `SKIP_REL_PREFIXES = ("gateways/upstream/",)`；`:35` `FROZEN_DIRS = ("docs/archive/", "docs/split/", "archive/")`；`:37-42` `LINK` / `HAS_ONE_LINER` / `ONE_LINER_HEAD` / `EXAMPLE = re.compile(r"^文档名\.md#")`（规则示例串跳过，`:134-135`）；`:45-48` `slugify(title)`；`:51-70` `collect(dirs)` 按上述集合裁剪。

### 6.3 方向正本列出的完整验收组

`docs/DSH-FIRST.md:135-142`：

```text
python -B -m unittest discover -s tests -q
python -B tools/check-project.py
python -B tools/check-docs.py
python -B tools/dsh_sync.py --check
python -B tools/model_caps.py --check
```

「前四条必须 exit 0；最后一条在批 1 落地后必须 exit 0，非 0 即代表 `catalog` 与现网配置漂移，按输出逐字段修，不许改门禁。」

**本分片按纪律只报告，未执行 `check-docs.py`、未改任何文档/配置/索引**；上述门禁由主代理在改写落地后统一跑。

---

## 7. 追加：docs/ 下 ZCode 脚本名路径引用逐处清单（file:line + 建议新名）

> 主代理 m00054 追加要求。方法：枚举 `docs/**/*.md`，逐行抽 `[A-Za-z0-9_~./%\\:-]*zcod[A-Za-z0-9_~./%\\:-]*` token，归一化后聚合 file:line，筛出「脚本/路径/env」类引用，共 92 个 token；下表按引用次数降序，file:line 为 **T0 基线**（改写前），改写时按文件名 + 上下文定位即可。

### 7.1 实现层改名映射（与 `docs/DSH-FIRST.md:85` T1 批 2 状态对齐）

| 旧名（T0） | 建议新名（= 主代理已落地名） | 类型 |
|---|---|---|
| `workbuddy_zcode_sync.py` | `workbuddy_sync.py` | 脚本 |
| `workbuddy_probe_zcode.py` | `workbuddy_probe.py` | 脚本 |
| `zcode_effective_body.js` | `effective_body.js` | 脚本 |
| `qoder_zcode_sync.py` | `qoder_sync.py` | 脚本 |
| `qoder_probe_zcode.py` | `qoder_probe.py` | 脚本 |
| `qwen_zcode_sync.py` | `qwen_sync.py` | 脚本 |
| `WB_ZCODE_PROBE_FILE` | `WB_PROBE_FILE`（旧名保留读取别名） | 自造 env |
| `ZCODE_API_TYPE` | `MB_API_TYPE` | 自造 env |
| `ZCODE_BASE_URL` | `MB_BASE_URL` | 自造 env |
| `ZCODE_MAX_OUTPUT_TOKENS` | `MB_MAX_OUTPUT_TOKENS` | 自造 env |
| `wb_zcode_probe.json` / `wb_zcode_probe.log` | `wb_probe.json` / `wb_probe.log`（旧名保留读取别名） | 活数据缓存 |
| `providers/_sink/zcode_provider_config.py` | `providers/_sink/compat_provider_config.py`（或保留，属计划 sink） | 未来落点 |
| `zcode_gateway_watch.ps1` | 无新名（**已退役**，删回退命令/标「历史」） | 过期口径 |
| `validate_zcode_models.py` | 保留（`providers/opencode-go/probe/archive/` 已归档一次性脚本） | 归档 |

### 7.2 逐处清单（token | 次数 | file:line | 建议新名 / 处置）

> 同一脚本的「带目录全路径」与「裸文件名」是文档里两种写法，都要同步替换；契约层路径见 7.3，一律不替换。

| token | 次数 | file:line（T0） | 建议新名 / 处置 |
|---|---|---|---|
| `providers/qoder/qoder_zcode_sync.py` | 17 | `docs/CAPABILITY-AUDIT.md:254`; `docs/MAINTENANCE.md:190`; `docs/MODEL-PROVIDERS.md:94,101,494,496`; `docs/QODER.md:80,136,143,149,153`; `docs/release-notes/0.6.0.md:19`; `docs/SECRETS.md:34,119,129`; `docs/TOOLS.md:48`; `docs/TROUBLESHOOTING.md:445` | `qoder_sync.py`（发布说明 `0.6.0.md:19` 属禁改，保留） |
| `workbuddy_zcode_sync.py` | 14 | `docs/DSH-FIRST.md:32`; `docs/MAINTENANCE.md:189,245,271`; `docs/MODEL-ALIAS.md:499`; `docs/MODEL-PROVIDERS.md:130,289,324,784`; `docs/TOOLS.md:60`; `docs/TROUBLESHOOTING.md:182,216`; `docs/UPSTREAM.md:115,415` | `workbuddy_sync.py`（`docs/DSH-FIRST.md:32/85` 作为「旧名映射表」保留原文） |
| `providers/workbuddy/workbuddy_zcode_sync.py` | 10 | `docs/CAPABILITY-AUDIT.md:255`; `docs/MODEL-PROVIDERS.md:93,100,361`; `docs/release-notes/0.6.0.md:19`; `docs/SECRETS.md:75,88,97,113`; `docs/TOOLS.md:43` | 同上；发布说明保留 |
| `providers/workbuddy/zcode_effective_body.js` | 9 | `docs/MODEL-ALIAS.md:567`; `docs/MODEL-PROVIDERS.md:763,773`; `docs/PITFALLS.md:97`; `docs/SECRETS.md:117`; `docs/TOOLS.md:44`; `docs/TROUBLESHOOTING.md:468,705`; `docs/UPSTREAM.md:239` | `effective_body.js` |
| `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` | 7 | `docs/DSH-FIRST.md:31`; `docs/PITFALLS.md:201`; `docs/SECRETS.md:96,102,113`; `docs/TROUBLESHOOTING.md:52,356` | **保留**（契约层 env） |
| `workbuddy_probe_zcode.py` | 7 | `docs/DSH-FIRST.md:32`; `docs/MAINTENANCE.md:153`; `docs/TOOLS.md:58`; `docs/TROUBLESHOOTING.md:293,319,425`; `docs/UPSTREAM.md:84` | `workbuddy_probe.py` |
| `zcode_effective_body.js`（裸名） | 7 | `docs/DSH-FIRST.md:32`; `docs/MAINTENANCE.md:153`; `docs/MODEL-PROVIDERS.md:746`; `docs/TOOLS.md:38,49`; `docs/TROUBLESHOOTING.md:68,319` | `effective_body.js` |
| `qoder_zcode_sync.py`（裸名） | 7 | `docs/DSH-FIRST.md:32`; `docs/MAINTENANCE.md:245,417`; `docs/MODEL-ALIAS.md:499`; `docs/MODEL-PROVIDERS.md:785`; `docs/QODER.md:9`; `docs/TROUBLESHOOTING.md:450` | `qoder_sync.py` |
| `providers/workbuddy/cache/wb_zcode_probe.json` | 7 | `docs/MAINTENANCE.md:165`; `docs/SECRETS.md:41,115`; `docs/TOOLS.md:42,60`; `docs/TROUBLESHOOTING.md:109,140` | `wb_probe.json`（旧名保留读取别名；改名前先确认代码产物名） |
| `providers/qoder/qoder_probe_zcode.py` | 7 | `docs/MODEL-PROVIDERS.md:495`; `docs/QODER.md:135,146,152`; `docs/SECRETS.md:119,129`; `docs/TOOLS.md:49` | `qoder_probe.py` |
| `providers/qwen/qwen_zcode_sync.py` | 7 | `docs/QWEN.md:176,234,260,261`; `docs/SECRETS.md:122,123`; `docs/TOOLS.md:51` | `qwen_sync.py` |
| `qoder_probe_zcode.py`（裸名） | 6 | `docs/DSH-FIRST.md:32`; `docs/MAINTENANCE.md:417`; `docs/QODER.md:8,188`; `docs/SECRETS.md:34`; `docs/TOOLS.md:48` | `qoder_probe.py` |
| `providers/workbuddy/workbuddy_probe_zcode.py` | 6 | `docs/MAINTENANCE.md:129,130`; `docs/PITFALLS.md:71`; `docs/SECRETS.md:75,88`; `docs/TOOLS.md:42` | `workbuddy_probe.py` |
| `ZCODE_BUILTIN` | 5 | `docs/DSH-FIRST.md:31`; `docs/PITFALLS.md:201`; `docs/SECRETS.md:117`; `docs/TROUBLESHOOTING.md:320`; `docs/UPSTREAM.md:364` | **保留**（契约层 env） |
| `config/provider/zcode-builtin.json` | 5 | `docs/UPSTREAM.md:241,274,286,356,368` | **保留**（vendored 上游文件原名） |
| `zcode-main` | 4 | `docs/MODEL-ALIAS.md:253,254`; `docs/PITFALLS.md:759,766` | **保留**（DSH 侧 provider id，事实/契约） |
| `zcode_gateway_watch.ps1` | 3 | `docs/ARCHITECTURE.md:52,316`; `docs/DSH-FIRST.md:127` | 无新名：已退役，删 `ARCHITECTURE.md:316` 的回退命令，正文标历史（`docs/DSH-FIRST.md:127` 自己已列为过期口径） |
| `WB_ZCODE_PROBE_FILE` | 3 | `docs/DSH-FIRST.md:32`; `docs/SECRETS.md:115`; `docs/TROUBLESHOOTING.md:301` | `WB_PROBE_FILE`（旧名保留读取别名） |
| `qwen_zcode_sync.py`（裸名） | 3 | `docs/DSH-FIRST.md:32`; `docs/QWEN.md:169`; `docs/TOOLS.md:52` | `qwen_sync.py` |
| `ZCODE_API_TYPE` | 2 | `docs/DSH-FIRST.md:32`; `docs/SECRETS.md:117` | `MB_API_TYPE` |
| `third-party/zcode/` / `third-party/zcodium/` / `third-party/zcode/zcode-builtin.json` / `third-party/zcodium/reasoning-rules.js` / `zcode-builtin-reasoning-rules.json` | 10+3+2 | `docs/TOOLS.md:68,69`; `docs/CAPABILITY-AUDIT.md:36,294`; `docs/DSH-FIRST.md:31,69`; `docs/UPSTREAM.md:5,315,324,355,397,400` 等 | **保留**（vendored 原件 + 来源凭证） |
| `%LOCALAPPDATA%\ZCodeGateway\`（含 `\zgate.log`、`ensure-zgate.vbs`、`workbuddy.stderr.log`、`qoder.stderr.log`、`zgate.exe`、`autostart-backup-20261109\restore-autostart.ps1`） | 3+3+1+… | `docs/ARCHITECTURE.md:162`; `docs/CONSOLE.md:63`; `docs/MAINTENANCE.md:316,321,326,328,342,378`; `docs/TOOLS.md:29`; `docs/TROUBLESHOOTING.md:339,352,353,380,602,610`; `docs/ZGATE-LIFECYCLE.md:84,130,299` | **保留**（契约目录，改了找不到日志/二进制） |
| `~/.zcode/v2/*`（provider_config.json / model-alias-map.json / model_probe.json / arena-main.json / arena-leaderboard.json / model-scores.json / quota-windows.json / model-sync-state.json / config.json / cli/config.json） | 25+11+8+6+3+3+1+1+… | 见 7.3 与 2.3，覆盖 `docs/MAINTENANCE.md`、`docs/TOOLS.md`、`docs/SECRETS.md`、`docs/CONSOLE.md`、`docs/TROUBLESHOOTING.md`、`docs/BENCHMARKS.md`、`docs/ROUTING-POLICY.md` 等 | **保留**（契约活数据路径） |
| `providers/_sink/zcode_provider_config.py` | 1 | `docs/DSH-FIRST.md:85` | 未来 sink，建议中性名 `compat_provider_config.py`；实测 `glob('providers/_sink/*.py')` 为空，尚不存在 |
| `providers/workbuddy/workbuddy_probe_zcode.py:75` | 1 | `docs/DSH-FIRST.md:35` | 改名硬回归面，随脚本同步 |
| `providers/workbuddy/zcode_effective_body.js:104-164` / `workbuddy_zcode_sync.py:284-333` / `qoder_zcode_sync.py:283` | 各 1 | `docs/CAPABILITY-AUDIT.md:26,110,112` | 行号引用随文件改名同步；审计正文属日期化记录，仅改路径串 |
| `providers/opencode-go/probe/archive/validate_zcode_models.py` | 1 | `docs/TOOLS.md:57` | **保留**（已归档一次性脚本，工具表标注 ❌ 已归档） |
| `probe_zcode.py` / `zcode_sync.py` / `zcode_provider` / `workbuddy/workbuddy_zcode_sync.py` / `qoder/qoder_zcode_sync.py` | 各 1 | `docs/TOOLS.md:44,61,79`; `docs/DSH-FIRST.md:50,62` | 片段/架构图占位，随 7.1 映射改中性名 |
| `ZCODE_BASE_URL` / `ZCODE_MAX_OUTPUT_TOKENS` / `ZCODE_GATEWAY_KEY` | 各 1 | `docs/DSH-FIRST.md:32`; `docs/TOOLS.md:35` | 前两个改 `MB_BASE_URL` / `MB_MAX_OUTPUT_TOKENS`；`ZCODE_GATEWAY_KEY` 属凭据变量名，按契约层保留并只留变量名 |
| `ZcodeAIModels-zgate-daemon` / `https://github.com/MVennn/ZcodeAIModels/issues/new/choose` / `zcode-api` / `zcode2api` / `zcode-token-usage-statusbar` / `ZCode-Agent-Kit` / `zai-org/ZCode` | 1–7 | `docs/MAINTENANCE.md:326`; `docs/release-notes/*`; `docs/UPSTREAM.md:16,46-55,270,273,359,368,389-392` | **保留**：外部项目名 / 旧仓名 / 已发布说明固定尾巴 / 计划任务历史名 |
| `/zcode-model-ledger.json` | 1 | `docs/PITFALLS.md:775` | DSH 侧 ledger 文件名（`~/.dsh/profiles/<profile>/zcode-model-ledger.json`），属本仓自有数据文件，可建议中性名 `model-ledger.json`，但需与 `dsh_sync.py` 实际产物一致 |
| `\.zcode\v2\provider_config.json` / `zcode/v2/provider_config.json` / `/ZCode/resources/config/provider/zcode-builtin.json` / `/path/to/zcode-builtin.json` | 各 1 | `docs/SECRETS.md:95`; `docs/TROUBLESHOOTING.md:320,413`; `docs/UPSTREAM.md:365` | **保留**（Windows 路径写法 / 示例路径 / 上游原文件路径） |

### 7.3 契约层保留项汇总（不得出现在替换 diff 里）

`~/.zcode/v2/provider_config.json`、`~/.zcode/v2/model-alias-map.json`、`~/.zcode/v2/model_probe.json`、`~/.zcode/v2/arena-main.json`、`~/.zcode/v2/arena-leaderboard.json`、`~/.zcode/v2/model-scores.json`、`~/.zcode/v2/quota-windows.json`、`~/.zcode/v2/model-sync-state.json`、`~/.zcode/v2/config.json`、`~/.zcode/cli/config.json`、`~/.zcode/v2/`、`ZCODE_PERSONAL_PROVIDER_CONFIG_FILE`、`ZCODE_BUILTIN`、`third-party/zcode/`、`third-party/zcodium/`、`zcode-builtin.json`、`config/provider/zcode-builtin.json`、`%LOCALAPPDATA%\ZCodeGateway\`（及其下所有文件）、`zcode-main`、`zcode-` 前缀 provider id、ZCode schema 键、NOTICE 商标段、外部项目名与 URL。依据：`docs/DSH-FIRST.md:31`、T1 `AGENTS.md:6`。

### 7.4 复现命令（逐处清单可重算）

```powershell
Select-String -Path (Get-ChildItem -LiteralPath 'F:\Project\ModelBus\docs' -Recurse -File -Filter '*.md').FullName -Pattern '(?i)zcod' |
  ForEach-Object { "$($_.Path):$($_.LineNumber): $($_.Line.Trim())" }
Select-String -Path (Get-ChildItem -LiteralPath 'F:\Project\ModelBus\docs' -Recurse -File -Filter '*.md').FullName -Pattern 'workbuddy_zcode_sync|workbuddy_probe_zcode|zcode_effective_body|qoder_zcode_sync|qoder_probe_zcode|qwen_zcode_sync|WB_ZCODE_PROBE_FILE'
```

实测（T0）：含 zcode 的现存脚本 glob 为 `providers/opencode-go/probe/archive/validate_zcode_models.py`、`providers/qoder/qoder_probe_zcode.py`、`providers/workbuddy/workbuddy_zcode_sync.py`、`providers/workbuddy/workbuddy_probe_zcode.py`、`providers/qoder/qoder_zcode_sync.py`、`providers/qwen/qwen_zcode_sync.py`、`providers/workbuddy/zcode_effective_body.js` 共 7 个；T1 代码改名分片（会话 `a427cdfe-99b1-4407-b18f-1001484a9753`）正在并行落地 6 个 rename，文档路径引用需按 7.2 同步。

---

> 限制：T1「当前态」数字以 2026-11-11 15:44 取样时刻为准；主代理正并行落地 `tools/agent_profiles.py`、docs 路径同步与 `dsh_sync.py` 的 DSH 原生真源开关，验收请以改后磁盘为准（主代理 m00085 口径）。本分片不复核改后磁盘、不代替主代理跑门禁。

---

## 8. 完成判据核对表

> 取样时刻：T0 = HEAD 基线 / 分片启动采样；T1 = 2026-11-11 15:44 左右当前工作树快照。主代理验收请以改后磁盘复核。

| # | 判据（任务书 / 主代理追加） | 结果 | 证据 |
|---|---|---|---|
| 1 | 文档清单与各自定位一行 | 是 | §1：根 7 个 + docs 41 篇，含行数与定位；`tools.glob({pattern:'docs/**/*.md'})`=41 |
| 2 | 仍以 ZCode 为中心的表述逐处台账（file:line / 原句 / 改写建议） | 是 | §2.2 门面/协议/贡献/安全/索引/方向正本 30+ 处逐行；§2.3 docs 正本 30 篇逐文件代表行 + 命中规模 + 建议；区分 T0 基线与 T1 现状 |
| 3 | 相对链接可打开性抽查（抽查清单 + 结果） | 是 | §3：30 篇 / 484 链接 / 436 本地目标 / 0 死链 / 0 锚点缺失；18 条抽样清单；README 18 个绝对链接映射本地目标全部存在；T0 形态冲突 + T1 已修 |
| 4 | 「DSH 面向适配」章节正文草稿（给正文，不落盘） | 是 | §4：可直接贴入的整段正文（含一句话块、主宿主/投影关系、三层命名口径、文档与验收），未写入任何 docs 文件 |
| 5 | 明确历史归档/发布说明/许可证禁改清单 | 是 | §5：13 类，逐条带禁改依据与实测字节/头部；`docs/DOC-RULES.md:152-153`、`AGENTS.md §5`、`tools/check-docs.py:35` |
| 6 | `tools/check-docs.py` 调用方式与门禁判据（只报告，不执行改动） | 是 | §6：调用 3 种写法 + 8 条判据逐条带 file:line + SKIP/FROZEN 常量 + 方向正本验收组；本分片未执行门禁、未改文档 |
| 7 | 追加：docs/ 下 ZCode 脚本名路径引用逐处清单（file:line + 建议新名） | 是 | §7：92 个 token 聚合表；7.1 改名映射与 `docs/DSH-FIRST.md:85` 对齐；7.2 逐处 file:line + 建议；7.3 契约保留项；7.4 复现命令 |
| 8 | 所有结论附 file:line 与可独立复现命令/数字；self-report 不当结论 | 是 | §0 双通道计数命令（grep + Select-String，exit 0）+ T0/T1 数字表；§3 抽查脚本口径；§7.4 重算命令；全文结论均挂 file:line |
| 9 | 只读纪律：不改 PROGRESS.md / docs / tests / 配置 / 历史 / 第三方署名；不 git 操作；不重启网关；凭据不落盘 | 是 | 唯一写入 `evidence/agent-docs-review.md`；`git status --short` 显示的改动均属主代理/代码改名分片，本分片未产生；报告无 key/token 真值 |
| 10 | 报告写到 `F:\Project\ModelBus\evidence\agent-docs-review.md` 并 send_message 回报主代理 | 是 | 本文件已落盘；回报见 send_message |
| 11 | docs/README.md 索引同步提示 | 是 | §2.4(3)、§4 末尾：新增/改名文档必须同步索引，否则 `tools/check-docs.py:168-169` 报孤儿 |

