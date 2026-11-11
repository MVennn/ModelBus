# ZCode 全仓普查 / 分类台账与替换映射（分片 agent-zcode-census）

> **一句话**：主代理拍板 **选 A —— 契约层保持原样、零新增 DSH_* 同名替代**；取样 **2026-11-11 15:59:35 (+08:00)** 纯文本命中 **10425 处 / 293 文件**（pwsh 同批复核 10425 处，闭合）；上游署名 + 上游运行日志 + 历史记录 7148 处原样保留，本轮实际改写域仅「实现层自造 env / 文件名 / 标识符 + 第一方叙述性措辞」。

---

## 0 分片边界、能力选择与证据口径

- 分片 `zcode-census`；父代理 `session-90f67405-5d4e-4707-b280-3eba9af5856a`；真实项目 `F:\Project\ModelBus`（`F:\Project\_merged\DeepseekHarness` 为 junction 视图，一律穿透真实路径，视图根零新建）。
- 本分片只读分析；唯一写入产物即本报告 `evidence/agent-zcode-census.md`。未改 `PROGRESS.md` / `docs/` / `tests/` / `provider_config.json` / 任何配置 / 历史记录 / 第三方署名；未 git add / commit / push；未重启 zgate；凭据值零输出。
- 能力选择：开工前核对会话技能目录并按 `progress-visibility` / `dsh-edit-tool-exact-match` / `windows-spawn-toolchain-invocation` 执行；按主代理 15:50 与 15:54 两次指令，定稿阶段不再自行加载任何 skill / 操作手册。
- `codegraph_status` 实测 `[i] Project: F:\Project\_merged\DeepseekHarness` / `[!] Not initialized` / `[i] Run "codegraph init" to initialize`；按 `AGENTS.md` §5 退回 `grep` / `glob` / `read` + Node 与 pwsh 双通道复核，未自行 `codegraph init`。
- 口径：`occ` = 每行 `/zcode|zcodium/gi` 全局出现次数；`lines` = 含至少一处命中的行数；`files` = 命中文件数。二进制（扩展名白名单 + 首 8192 字节含 NUL）单列，不计入主数。
- **自引用排除**：统计时排除本报告自身，避免报告正文里的 ZCode 字样反向抬高主数；pwsh 复核用同一排除项。
- **取样时刻口径**：本仓在作业期间被并发分片持续改动（主代理正在落地 `tools/agent_profiles.py`、docs 路径同步、`dsh_sync.py` DSH 原生真源开关；第 6 路子代理正在执行 6 脚本 `git mv`）。§1 主数为 2026-11-11 15:59:35 (+08:00) 同批重跑值；主代理验收时按磁盘复核改后值。
- **口径裁决**：主代理 15:54 拍板「选 A」，本报告 §3 已按该裁决重定稿；任务书原 C 类「DSH_* 优先 + ZCODE_* 兜底」方案完整保留于 §5.3，明确标注「按 live 契约层保持原样，本轮未实施，仅作备选」，**不与 §3 主方案并列、不作推荐**。
- `grep` 工具返回**匹配行数**、单次上限 250（`[CAP]` 需分目录重跑），与 Node 的 `occ` 口径不同，并列给出、不相加。
- **分类正交性**：A / A2 / B / D / E / F1 / F4 / F6 / F7 按「文件」归类，九类 occ 合计闭合 10425；C 类按「出现处 / 字符串」归类，是活跃文件内的子集，与 A–F 不相加。归位见 §2.1。

## 1 总量与可复核数字

### 1.1 主数（Node 全量扫描，纯文本，按 §1.10 复核命令重跑于 2026-11-11 15:59:35 (+08:00)）

| 指标 | 值 |
|---|---|
| 递归文件总数（排除本报告） | 1224 |
| 文本 / 二进制 | 1157 / 67 |
| **总命中 occ** | **10425** |
| 命中行数 lines | 6622 |
| 命中文件数 files | 293 |
| 二进制内 ASCII 串命中（单列） | 7826 |

### 1.2 大小写变体分布

| 变体 | 快照 A occ（历史，保留） | 当前 occ（2026-11-11 15:59:35 (+08:00) 重跑） | 当前占比 |
|---|---|---|---|
| `ZCode` | 6505 | 7231 | 69.36% |
| `zcode` | 1892 | 2619 | 25.12% |
| `ZCODE` | 164 | 285 | 2.73% |
| `Zcode` | 117 | 160 | 1.53% |
| `ZCodium` | 72 | 80 | 0.77% |
| `zcodium` | 44 | 50 | 0.48% |
| **合计** | **8794** | **10425** | 100% |

快照 A 变体分布按主代理指令原样保留（合计 8794）；当前列为同批重跑实测（合计 10425）。`ZCode/3.17.2` 与 `ZCodeExecutor` 高频主要来自 `gateways/upstream/workbuddy/data/request-logs/requests-2026-11-04.jsonl` 的 User-Agent，属 A2 上游运行日志，原样保留。

### 1.3 按顶层目录 / 根文件命中

| 顶层 | occ |
|---|---|
| `gateways` | 5222 |
| `.work` | 2261 |
| `evidence` | 1418 |
| `docs` | 581 |
| `tools` | 178 |
| `PROGRESS.md` | 175 |
| `third-party` | 151 |
| `memories` | 109 |
| `providers` | 107 |
| `CHANGELOG.md` | 100 |
| `NOTICE` | 50 |
| `tests` | 33 |
| `README.md` | 13 |
| `AGENTS.md` | 11 |
| `.github` | 7 |
| `CONTRIBUTING.md` | 4 |
| `.gitignore` | 3 |
| `assets` | 1 |
| `sync-models.ps1` | 1 |

### 1.4 文件 Top30（按 occ 降序）

| # | 文件 | occ | 匹配行 |
|---|---|---|---|
| 1 | `gateways/upstream/workbuddy/data/request-logs/requests-2026-11-04.jsonl` | 4786 | 2393 |
| 2 | `.work/code-review-ledger.part.md` | 564 | 300 |
| 3 | `gateways/upstream/workbuddy/data/request-logs/requests-2026-11-06.jsonl` | 314 | 157 |
| 4 | `evidence/agent-gateway-lifecycle.md` | 287 | 236 |
| 5 | `evidence/agent-docs-review.md` | 276 | 125 |
| 6 | `.work/agent-gemini-fullscan.json` | 208 | 187 |
| 7 | `.work/dsh-first-20261111/PROGRESS.md` | 175 | 158 |
| 8 | `PROGRESS.md` | 175 | 158 |
| 9 | `.work/code-review-cimpl-final.md` | 137 | 129 |
| 10 | `.work/code-review-cimpl.md` | 132 | 129 |
| 11 | `docs/UPSTREAM.md` | 109 | 73 |
| 12 | `evidence/agent-dshfirst-docs.md` | 107 | 45 |
| 13 | `.work/dsh-first-20261111/CHANGELOG.md` | 100 | 91 |
| 14 | `CHANGELOG.md` | 100 | 91 |
| 15 | `evidence/agent-dshfirst-naming.md` | 98 | 49 |
| 16 | `.work/memory-audit-20261110.md` | 77 | 50 |
| 17 | `gateways/upstream/workbuddy/data/request-logs/requests-2026-11-09.jsonl` | 62 | 31 |
| 18 | `evidence/agent-gemini-memory-docs.md` | 59 | 40 |
| 19 | `evidence/agent-sync-logs.md` | 58 | 42 |
| 20 | `docs/TROUBLESHOOTING.md` | 54 | 47 |
| 21 | `.work/vf-secrets.txt` | 52 | 35 |
| 22 | `.work/dsh-rename-20261111/tools__dsh_sync.py` | 50 | 45 |
| 23 | `docs/TOOLS.md` | 50 | 29 |
| 24 | `NOTICE` | 50 | 45 |
| 25 | `.work/evidence/agent-onboard-chain.md` | 47 | 36 |
| 26 | `evidence/agent-gemini-logs.md` | 46 | 28 |
| 27 | `evidence/agent-gemini-provider-locate.md` | 46 | 28 |
| 28 | `tools/dsh_sync.py.bak-effort-20261110125432` | 46 | 41 |
| 29 | `docs/MODEL-PROVIDERS.md` | 44 | 41 |
| 30 | `tools/dsh_sync.py` | 44 | 40 |

### 1.5 双通道独立复核与闭合（同批取样）

| 通道 | 口径 | 扫描文本 | 命中文件 | occ | lines |
|---|---|---|---|---|---|
| Node | 扩展名白名单 + 首 8KB 含 NUL 判二进制；逐行 `/zcode|zcodium/gi` | 1157 | 293 | **10425** | 6622 |
| pwsh `Select-String`（§1.10 复核命令） | 同白名单 + Node 判定的内容二进制文件列表内嵌排除 6 项 | 1157 | 293 | **10425** | 6622 |

两通道差值 `0`。完全闭合（同批取样、同排除项、同正则）。

pwsh 内嵌排除的内容二进制文件（Node 按 NUL 判定、扩展名不在白名单内）：

- `gateways/zgate/zgate.exe.bak-before-early-sse`（PE/MZ 头 `4d5a9000…`）
- `gateways/zgate/zgate.exe.bak-deploy-20261110-222534`（PE/MZ 头 `4d5a9000…`）
- `gateways/zgate/zgate.exe.bak-deploy-20261110-230821`（PE/MZ 头 `4d5a9000…`）
- `gateways/zgate/zgate.exe.bak-deploy-20261110-231016`（PE/MZ 头 `4d5a9000…`）
- `gateways/zgate/zgate.exe.bak-deploy-20261111-100600`（PE/MZ 头 `4d5a9000…`）
- `gateways/zgate/zgate.exe.bak-deploy-20261111-115622`（PE/MZ 头 `4d5a9000…`）

### 1.6 作业期间并发漂移（历史取样，单列记录）

| 快照 | 时刻 | 文件数 | 命中文件 | Node occ | 说明 |
|---|---|---|---|---|---|
| **A（起点，历史）** | 15:26–15:33 | 1179 | 264 | **8794** | 双通道：Node 8794 / pwsh 8830；差 36 = 6 个 PE `.exe.bak-*` 各 6 occ（MZ 头 `4d5a9000…`），逐文件闭合 |
| **B（中间，历史）** | 15:46 | 1187 | 271 | **9129** | 并发分片已改 AGENTS.md / docs / tests / tools |
| **C（中间）** | 15:51 | 1202 | 283 | **9969** | 同批双通道闭合（Node 9969 / pwsh 9969） |
| **D（定稿重跑）** | 2026-11-11 15:59:35 (+08:00) | **1224** | **293** | **10425** | **本报告主数；排除报告自身** |

`git status --short` / `git log -1`（2026-11-11 15:59:35 (+08:00) 取样）：

```text
=== GIT STATUS ===
 M AGENTS.md
 M CONTRIBUTING.md
 M README.md
 M SECURITY.md
 M catalog/model_caps.json
 M catalog/upstream_caps.json
 M catalog/upstream_caps_evidence.json
 M docs/CAPABILITY-AUDIT.md
 M docs/DSH-FIRST.md
 M docs/MODEL-PROVIDERS.md
 M docs/PITFALLS.md
 M docs/README.md
 M docs/ROUTING-POLICY.md
 M docs/TROUBLESHOOTING.md
 M gateways/legacy-router/protocol_bridge.js
 M gateways/legacy-router/unified-router.js
 D providers/qoder/qoder_probe_zcode.py
 D providers/qoder/qoder_zcode_sync.py
 M providers/qwen/qwen_pool_probe.py
 D providers/qwen/qwen_zcode_sync.py
 M providers/workbuddy/workbuddy_fetch_pricing.py
 D providers/workbuddy/workbuddy_probe_zcode.py
 D providers/workbuddy/workbuddy_zcode_sync.py
 D providers/workbuddy/zcode_effective_body.js
 M sync-models.ps1
 M tests/test_dsh_sync_efforts.py
 M tests/test_model_alias_efforts.py
 M tests/test_model_alias_hop_order.py
 M tools/arena_leaderboard.py
 M tools/caps_upstream.py
 M tools/dsh_sync.py
 M tools/model_alias.py
 M tools/model_caps.py
 M tools/model_probe.py
 M tools/model_score.py
 M tools/sync_report.py
?? evidence/agent-docs-review.md
?? evidence/agent-gemini38-config.md
?? evidence/agent-gemini38-memory.md
```

`git ls-files` 实测 `TRACKED_TOTAL=232` / `TRACKED_WITH_ZCODE=126` / `TRACKED_OCC=2270`（数值随并发落地持续下降）。

**进行中快照说明**：`docs/DSH-FIRST.md:35` / `:85` 写的是本轮完成态承诺，主代理验收时按磁盘复核（新名存在 / 旧名零残留 / `git status` 出现改名 / `sync-models.ps1:228,253` 与 `tools/dsh_sync.py:60`、`tools/model_probe.py:45` 引用同步），失败由主代理接管并把文档状态改回待落地。本报告的取样编号仅用于标注时点，不代表完成态。

### 1.7 二进制命中（单列，不计入主数）

| 文件 | ASCII 串命中 |
|---|---|
| `.codegraph/codegraph.db` | 7569 occ / 7453 runs（残留索引 DB；与 `codegraph_status` Not initialized 并存，索引重建由人决定） |
| `.work/zgate-early-sse.exe` / `.work/zgate.candidate.exe` / `gateways/zgate/zgate.exe` | 各 6 |
| 9 个 `gateways/zgate/zgate.exe.bak-*` | 各 6 |
| `tools/__pycache__/dsh_sync.cpython-312.pyc` | 45 |
| `tools/__pycache__/model_caps.cpython-312.pyc` | 17 |
| `tests/__pycache__/test_dsh_sync_retry_policy.cpython-312.pyc` | 12 |
| `tools/__pycache__/model_alias.cpython-312.pyc` | 11 |
| 其余 `__pycache__` / `.pyc` | 各 1–5 |

二进制合计 **7826 occ**，全部跳过（`.exe` 重新编译、`.pyc` 由 Python 重建、`.db` 由索引工具重建）。

### 1.8 grep 分模式 / 分目录（作业期间取样，行数口径）

| 模式 | 全仓匹配行 |
|---|---|
| `(?i)zcode` | 1900 [CAP] |
| `ZCODE_` | 91 |
| `zcodium` | 31 |
| `~/.zcode` | 236 |
| `zcode-` | 263 [CAP] |
| `ZCodeGateway` | 92 |
| `ZcodeAIModels` | 78 |

| 目录 | (?i)zcode 匹配行 |
|---|---|
| `tools` | 128 |
| `providers` | 147 |
| `gateways/zgate` | 18 |
| `gateways/legacy-router` | 6 |
| `gateways/upstream` | 0 |
| `docs` | 446 [CAP] |
| `tests` | 30 |
| `.github` | 7 |
| `assets` | 1 |
| `third-party` | 86 |
| `memories` | 73 |
| `evidence` | 646 [CAP] |
| `.work` | 701 [CAP] |

`[CAP]` = 触及工具 250 上限，已按目录重跑；`gateways/upstream` 的 0 系工具默认忽略 `.jsonl` 日志，Node 全量扫描在 3 个 request-logs 里实得 5162 occ。

`glob("**/*[zZ][cC][oO][dD][eE]*")` → 15 个文件（14 个原有 + 本报告自身）；`glob("**/*zcodium*")` → 0（工具目录匹配局限），实际 2 个目录 `third-party/zcode/`、`third-party/zcodium/` 由 `Get-ChildItem` 证实，均属 A 类原样保留。文件名命中清单：

| 文件名 | 归类 |
|---|---|
| `.work/zcode-files.txt` | F1 |
| `memories/opencode-go-zcode-models.md` | B |
| `memories/workbuddy-proxy-zcode.md` | B |
| `memories/zcode-open-source-upstream.md` | B |
| `memories/zcode-ui-ordering-preferences.md` | B |
| `providers/opencode-go/probe/archive/validate_zcode_models.py` | D |
| `providers/qoder/qoder_probe_zcode.py` | D |
| `providers/qoder/qoder_zcode_sync.py` | D |
| `providers/qwen/qwen_zcode_sync.py` | D |
| `providers/workbuddy/workbuddy_probe_zcode.py` | D |
| `providers/workbuddy/workbuddy_zcode_sync.py` | D |
| `providers/workbuddy/zcode_effective_body.js` | D |
| `third-party/zcode/zcode-builtin.json` | A |
| `third-party/zcodium/zcode-builtin-reasoning-rules.json` | A |
| `evidence/agent-zcode-census.md` | 本报告（统计时排除） |

### 1.9 复核证据小结

- 主数 10425 由 Node 与 pwsh 双通道同批闭合，二进制 7826 单列，快照 A/B/C 单列历史。
- 所有数字可按 §1.10 命令独立重跑；主代理验收时按改后磁盘再跑一次并比对各类 occ。

### 1.10 复核命令（可整行复制）

```powershell
$root = 'F:\Project\ModelBus'
$skip = @('.exe','.dll','.pyc','.png','.jpg','.jpeg','.gif','.webp','.ico','.db','.bin','.zip','.7z','.gz','.pdf','.so','.a','.o','.class','.woff','.woff2','.ttf')
$self = 'evidence\agent-zcode-census.md'
$occ = 0; $lines = 0; $mf = 0
$files = Get-ChildItem -LiteralPath $root -Recurse -File | Where-Object { ($_.FullName -notmatch '\\.git\\') -and ($_.FullName.Substring($root.Length+1) -ne $self) -and ($skip -notcontains $_.Extension.ToLowerInvariant()) }
foreach ($f in $files) { $m = Select-String -LiteralPath $f.FullName -Pattern 'zcode|zcodium' -AllMatches; if ($m) { $mf++; foreach ($x in $m) { $occ += $x.Matches.Count; $lines++ } } }
"FILES=$($files.Count) MATCHFILES=$mf OCC=$occ LINES=$lines"
```

注：该简化命令按扩展名白名单扫描，会额外把 6 个 PE `.exe.bak-*` 当文本计入（每个 6 occ，合计 36）；要严格复现 Node 主数 10425，把下列路径加入排除：

- `gateways/zgate/zgate.exe.bak-before-early-sse`
- `gateways/zgate/zgate.exe.bak-deploy-20261110-222534`
- `gateways/zgate/zgate.exe.bak-deploy-20261110-230821`
- `gateways/zgate/zgate.exe.bak-deploy-20261110-231016`
- `gateways/zgate/zgate.exe.bak-deploy-20261111-100600`
- `gateways/zgate/zgate.exe.bak-deploy-20261111-115622`

```powershell
Set-Location 'F:\Project\ModelBus'; $t = git ls-files; $o = 0; $n = 0
foreach ($f in $t) { if (Test-Path -LiteralPath $f) { $m = Select-String -LiteralPath $f -Pattern 'zcode|zcodium' -AllMatches; if ($m) { $n++; foreach ($x in $m) { $o += $x.Matches.Count } } } }
"TRACKED_TOTAL=$($t.Count) TRACKED_WITH_ZCODE=$n TRACKED_OCC=$o"
```

Node 主数复现要点：递归 `readdirSync(...,{withFileTypes:true})` 排除 `.git` 与 `evidence/agent-zcode-census.md`；`BIN_EXT` 白名单 + 首 8192 字节含 NUL 判二进制；`buf.toString('utf8')` 后剥首字符 `0xFEFF`；按 `/\r?\n/` 切行；每行 `line.match(/zcode|zcodium/gi)` 累加。

## 2 分类台账 A–F（完整文件清单）

### 2.1 判定规则

| 父任务类 | 本分片归类 | 判定 | 处置 |
|---|---|---|---|
| A 第三方上游 / 许可证署名 | A | `NOTICE`、`LICENSE*`、`third-party/zcode/**`、`third-party/zcodium/**` | **KEEP**，上游事实与署名 |
| A（补充） | A2 | `gateways/upstream/**` 上游 clone 源码与 `request-logs/*.jsonl` 运行日志 | **KEEP**，上游产物 / 运行史实 |
| B 历史记录 | B | `CHANGELOG.md`、`PROGRESS.md`、`memories/**`、`evidence/agent-*.md`、`docs/release-notes/**`、`docs/archive/**` | **KEEP**，史实保留 |
| C 运行时配置路径与环境变量 | C（按出现处） | `~/.zcode/v2/*`、`ZCODE_*`、`ZCodeGateway`、`%LOCALAPPDATA%\ZCodeGateway\` 等 | **拍板选 A：契约层原样保留，零新增同名替代**；仅 4 个自造 env 改中性名 + 旧名 fallback（见 §3.2 / §3.3） |
| D 活跃代码标识符 / 字符串 / 注释 / 文件名 | D | `tools/**`、`providers/**`、`gateways/zgate/**`、`gateways/legacy-router/**`、`tests/**`、`catalog/**`、`.github/**`、根 `sync-models.ps1` / `.vbs` | **实现层替换 + 叙述性改写**（契约层部分 KEEP） |
| E 当前行为文档 | E | `README.md`、`AGENTS.md`、`CONTRIBUTING.md`、`SECURITY.md`、`docs/**`（非归档） | **叙述性改写**（主语改 DSH 主宿主 + 各类 agent） |
| F 资产 / 杂项 | F1 `.work/**`、F4 `assets/**`、F6 `*.bak-*` / `__pycache__` / `.log`、F7 根配置与 `third-party/README.md` | F1 跳过；F4 逐项判定；F6 跳过且随源文件同步；F7 根配置与索引说明需改写 |

### 2.2 汇总（occ 闭合）

| 类 | 文件数 | occ | 匹配行 | 处置 |
|---|---|---|---|---|
| A | 9 | 182 | 140 | 原样保留 |
| A2 | 7 | 5167 | 2586 | 原样保留 |
| B | 61 | 1799 | 1270 | 原样保留 |
| D | 45 | 303 | 282 | 实现层替换 + 叙述改写 |
| E | 25 | 570 | 441 | 叙述性改写 |
| F1 | 129 | 2261 | 1790 | 跳过（临时产物） |
| F4 | 1 | 1 | 1 | 逐项判定 |
| F6 | 12 | 98 | 85 | 跳过（备份/日志） |
| F7 | 4 | 44 | 27 | 改写 / 同步 |
| **合计** | **293** | **10425** | **6622** | — |

闭合等式：`A:182 + A2:5167 + B:1799 + D:303 + E:570 + F1:2261 + F4:1 + F6:98 + F7:44 = 10425`。

### 2.3 A 类完整清单（9 文件 / 182 occ）

| 文件 | occ | 匹配行 |
|---|---|---|
| `NOTICE` | 50 | 45 |
| `third-party/zcodium/reasoning-rules.js` | 38 | 29 |
| `third-party/zcodium/UPSTREAM.md` | 34 | 21 |
| `third-party/zcode/UPSTREAM.md` | 25 | 18 |
| `third-party/zcode/zcode-builtin.json` | 15 | 11 |
| `third-party/zcodium/zcode-builtin-reasoning-rules.json` | 11 | 7 |
| `third-party/zcode/schema.ts` | 4 | 4 |
| `third-party/zcode/model-config.ts` | 3 | 3 |
| `third-party/zcode/rule-data-schema.ts` | 2 | 2 |

### 2.4 A2 类完整清单（7 文件 / 5167 occ）

| 文件 | occ | 匹配行 |
|---|---|---|
| `gateways/upstream/workbuddy/data/request-logs/requests-2026-11-04.jsonl` | 4786 | 2393 |
| `gateways/upstream/workbuddy/data/request-logs/requests-2026-11-06.jsonl` | 314 | 157 |
| `gateways/upstream/workbuddy/data/request-logs/requests-2026-11-09.jsonl` | 62 | 31 |
| `gateways/upstream/qoder/CHANGELOG.md` | 2 | 2 |
| `gateways/upstream/workbuddy/internal/server/handler.go` | 1 | 1 |
| `gateways/upstream/workbuddy/internal/upstream/context_catalog.go` | 1 | 1 |
| `gateways/upstream/workbuddy/internal/upstream/payload.go` | 1 | 1 |

### 2.5 B 类完整清单（61 文件 / 1799 occ）

| 文件 | occ | 匹配行 |
|---|---|---|
| `evidence/agent-gateway-lifecycle.md` | 287 | 236 |
| `evidence/agent-docs-review.md` | 276 | 125 |
| `PROGRESS.md` | 175 | 158 |
| `evidence/agent-dshfirst-docs.md` | 107 | 45 |
| `CHANGELOG.md` | 100 | 91 |
| `evidence/agent-dshfirst-naming.md` | 98 | 49 |
| `evidence/agent-gemini-memory-docs.md` | 59 | 40 |
| `evidence/agent-sync-logs.md` | 58 | 42 |
| `evidence/agent-gemini-logs.md` | 46 | 28 |
| `evidence/agent-gemini-provider-locate.md` | 46 | 28 |
| `evidence/agent-thinking-adapt.md` | 41 | 27 |
| `evidence/agent-gemini-code.md` | 31 | 26 |
| `evidence/agent-gemini-merge-plan.md` | 30 | 24 |
| `evidence/agent-mainline-merge.md` | 27 | 22 |
| `evidence/agent-sync-scheduler.md` | 27 | 23 |
| `evidence/agent-dsh-order.md` | 24 | 20 |
| `memories/opencode-go-zcode-models.md` | 24 | 16 |
| `evidence/agent-effort-audit.md` | 21 | 13 |
| `evidence/agent-sort-rule.md` | 21 | 17 |
| `evidence/agent-cap-gen.md` | 20 | 17 |
| `memories/zcode-open-source-upstream.md` | 20 | 13 |
| `evidence/agent-gemini38-config.md` | 19 | 17 |
| `memories/beam-free-thinking-param-fix.md` | 19 | 13 |
| `memories/workbuddy-proxy-zcode.md` | 19 | 15 |
| `evidence/agent-aggregation.md` | 16 | 13 |
| `evidence/agent-automation.md` | 16 | 12 |
| `memories/MEMORY.md` | 15 | 6 |
| `evidence/agent-gemini-channels-web.md` | 12 | 7 |
| `evidence/agent-zgate.md` | 12 | 10 |
| `evidence/agent-gemini38-memory.md` | 11 | 11 |
| `docs/archive/OPENCODE-GO-ANALYSIS.md` | 9 | 9 |
| `evidence/agent-dsh-retry.md` | 9 | 7 |
| `docs/release-notes/0.1.0.md` | 7 | 7 |
| `evidence/agent-adaptation.md` | 7 | 7 |
| `evidence/agent-reasoning-history.md` | 7 | 4 |
| `evidence/agent-cap-upstream.md` | 6 | 4 |
| `evidence/agent-map-config.md` | 6 | 6 |
| `evidence/agent-runtime.md` | 6 | 6 |
| `docs/release-notes/0.6.0.md` | 5 | 3 |
| `docs/release-notes/README.md` | 5 | 5 |
| `evidence/agent-caps-truth.md` | 5 | 5 |
| `docs/release-notes/0.3.0.md` | 4 | 3 |
| `evidence/agent-gemini-memory-cleanup.md` | 4 | 2 |
| `memories/zcode-ui-ordering-preferences.md` | 4 | 4 |
| `memories/zgate-windowless-build.md` | 4 | 4 |
| `docs/release-notes/0.2.0.md` | 3 | 2 |
| `docs/release-notes/0.4.0.md` | 3 | 2 |
| `docs/release-notes/0.5.0.md` | 3 | 2 |
| `evidence/agent-map-api.md` | 3 | 3 |
| `evidence/agent-model-alias-hardening.md` | 3 | 3 |
| `evidence/agent-sync-audit-20261111.md` | 3 | 3 |
| `memories/beam-free-daily-quota.md` | 3 | 3 |
| `evidence/agent-cap-dsh.md` | 2 | 2 |
| `evidence/agent-cliproxyapi.md` | 2 | 1 |
| `evidence/agent-detect-quality.md` | 2 | 2 |
| `evidence/agent-iceman-stream.md` | 2 | 2 |
| `evidence/agent-admission-price.md` | 1 | 1 |
| `evidence/agent-dshfirst-dsh.md` | 1 | 1 |
| `evidence/agent-gemini-runtime.md` | 1 | 1 |
| `evidence/agent-gemini-truth.md` | 1 | 1 |
| `memories/answer-first-preference.md` | 1 | 1 |

### 2.6 D 类完整清单（45 文件 / 303 occ）

| 文件 | occ | 匹配行 |
|---|---|---|
| `tools/dsh_sync.py` | 44 | 40 |
| `providers/workbuddy/effective_body.js` | 39 | 35 |
| `providers/workbuddy/workbuddy_probe.py` | 20 | 18 |
| `tools/model_alias.py` | 19 | 19 |
| `tools/model_caps.py` | 14 | 12 |
| `tests/test_dsh_sync_efforts.py` | 13 | 13 |
| `tests/test_dsh_sync_retry_policy.py` | 13 | 10 |
| `providers/qoder/qoder_sync.py` | 11 | 11 |
| `tools/rename-to-modelbus.ps1` | 11 | 10 |
| `tools/sync_report.py` | 9 | 9 |
| `providers/opencode-go/ops/go_model_sync.py` | 7 | 7 |
| `tools/agent_profiles.py` | 7 | 3 |
| `.github/ISSUE_TEMPLATE/bug_report.yml` | 6 | 6 |
| `providers/qwen/qwen_sync.py` | 6 | 6 |
| `providers/workbuddy/workbuddy_sync.py` | 6 | 5 |
| `tools/model_probe.py` | 6 | 6 |
| `tools/model_score.py` | 6 | 6 |
| `tools/arena_leaderboard.py` | 5 | 5 |
| `gateways/legacy-router/unified-router.js` | 4 | 4 |
| `gateways/zgate/internal/config/config.go` | 4 | 4 |
| `providers/opencode-go/probe/archive/validate_zcode_models.py` | 4 | 4 |
| `providers/qoder/qoder_probe.py` | 4 | 4 |
| `gateways/zgate/internal/router/router.go` | 3 | 3 |
| `gateways/zgate/main.go` | 3 | 3 |
| `gateways/zgate/zgate.json` | 3 | 3 |
| `providers/opencode-go/probe/bench_clean.py` | 3 | 3 |
| `providers/opencode-go/probe/bench_models.py` | 3 | 3 |
| `providers/opencode-go/probe/probe_protocols.py` | 3 | 3 |
| `tests/test_model_caps.py` | 3 | 3 |
| `gateways/zgate/internal/alias/alias.go` | 2 | 2 |
| `gateways/zgate/internal/bridge/bridge.go` | 2 | 2 |
| `tests/test_model_alias_probe_filter.py` | 2 | 2 |
| `tools/caps_upstream.py` | 2 | 2 |
| `tools/make_social_preview.py` | 2 | 2 |
| `tools/model_stream_check.py` | 2 | 2 |
| `tools/zgate-lifecycle/current-models.ps1` | 2 | 2 |
| `tools/zgate-lifecycle/install-lifecycle.ps1` | 2 | 2 |
| `.github/ISSUE_TEMPLATE/feature_request.yml` | 1 | 1 |
| `gateways/legacy-router/protocol_bridge.js` | 1 | 1 |
| `gateways/zgate/smoke_test.py` | 1 | 1 |
| `providers/opencode-go/probe/probe_models.py` | 1 | 1 |
| `sync-models.ps1` | 1 | 1 |
| `tests/test_model_alias_hop_order.py` | 1 | 1 |
| `tests/test_model_alias_qd_free.py` | 1 | 1 |
| `tools/zgate-lifecycle/deploy-zgate.ps1` | 1 | 1 |

### 2.7 E 类完整清单（25 文件 / 570 occ）

| 文件 | occ | 匹配行 |
|---|---|---|
| `docs/UPSTREAM.md` | 109 | 73 |
| `docs/TROUBLESHOOTING.md` | 54 | 47 |
| `docs/TOOLS.md` | 50 | 29 |
| `docs/MODEL-PROVIDERS.md` | 44 | 41 |
| `docs/MAINTENANCE.md` | 42 | 39 |
| `docs/ARCHITECTURE.md` | 37 | 31 |
| `docs/SECRETS.md` | 36 | 24 |
| `docs/PITFALLS.md` | 30 | 29 |
| `docs/DSH-FIRST.md` | 27 | 12 |
| `docs/QODER.md` | 24 | 23 |
| `docs/CAPABILITY-AUDIT.md` | 22 | 17 |
| `docs/BENCHMARKS.md` | 16 | 15 |
| `docs/MODEL-ALIAS.md` | 13 | 11 |
| `README.md` | 13 | 8 |
| `AGENTS.md` | 11 | 3 |
| `docs/QWEN.md` | 10 | 10 |
| `docs/CONSOLE.md` | 8 | 8 |
| `docs/README.md` | 5 | 3 |
| `CONTRIBUTING.md` | 4 | 4 |
| `docs/MODEL-QUICK-REF.md` | 4 | 4 |
| `docs/REVIEW-2026-11-10.md` | 3 | 3 |
| `docs/ZGATE-LIFECYCLE.md` | 3 | 3 |
| `docs/DOC-RULES.md` | 2 | 2 |
| `docs/MODEL-STREAM.md` | 2 | 1 |
| `docs/ROUTING-POLICY.md` | 1 | 1 |

### 2.8 F1 类完整清单（129 文件 / 2261 occ）

| 文件 | occ | 匹配行 |
|---|---|---|
| `.work/code-review-ledger.part.md` | 564 | 300 |
| `.work/agent-gemini-fullscan.json` | 208 | 187 |
| `.work/dsh-first-20261111/PROGRESS.md` | 175 | 158 |
| `.work/code-review-cimpl-final.md` | 137 | 129 |
| `.work/code-review-cimpl.md` | 132 | 129 |
| `.work/dsh-first-20261111/CHANGELOG.md` | 100 | 91 |
| `.work/memory-audit-20261110.md` | 77 | 50 |
| `.work/vf-secrets.txt` | 52 | 35 |
| `.work/dsh-rename-20261111/tools__dsh_sync.py` | 50 | 45 |
| `.work/evidence/agent-onboard-chain.md` | 47 | 36 |
| `.work/dsh-rename-20261111/providers__workbuddy__zcode_effective_body.js` | 42 | 38 |
| `.work/agent-opt-gateway/pre/docs__ARCHITECTURE.md.txt` | 37 | 31 |
| `.work/dsh-first-20261111/docs__DSH-FIRST.md` | 35 | 15 |
| `.work/evidence/agent-modelbus.md` | 29 | 20 |
| `.work/dsh-first-20261111/README.md` | 25 | 17 |
| `.work/dsh-rename-20261111/providers__workbuddy__workbuddy_probe_zcode.py` | 25 | 24 |
| `.work/evidence/agent-docs.md` | 25 | 22 |
| `.work/memory-audit-20261110-report.md` | 23 | 9 |
| `.work/model-stream/report-20261109T143509Z.json` | 22 | 22 |
| `.work/model-stream/report-20261109T151120Z.json` | 22 | 22 |
| `.work/model-stream/report-20261109T160259Z.json` | 22 | 22 |
| `.work/zcode-files.txt` | 22 | 20 |
| `.work/dsh-rename-20261111/providers__workbuddy__workbuddy_zcode_sync.py` | 21 | 18 |
| `.work/model-stream/latest.json` | 20 | 20 |
| `.work/model-stream/report-20261111T054355Z.json` | 20 | 20 |
| `.work/model-stream/report-20261111T054520Z.json` | 20 | 20 |
| `.work/dsh-rename-20261111/providers__qoder__qoder_zcode_sync.py` | 19 | 19 |
| `.work/evidence/agent-gate-integration.md` | 19 | 16 |
| `.work/model-stream/report-20261111T040703Z.json` | 18 | 18 |
| `.work/admission-price-pre.py` | 17 | 17 |
| `.work/dsh-tools-20261111/tools__model_caps.py` | 17 | 16 |
| `.work/evidence/agent-runtime.md` | 14 | 12 |
| `.work/dsh-rename-20261111/providers__qwen__qwen_zcode_sync.py` | 12 | 11 |
| `.work/dsh-rename-20261111/providers__qoder__qoder_probe_zcode.py` | 11 | 11 |
| `.work/dsh-first-20261111/CONTRIBUTING.md` | 9 | 7 |
| `.work/dsh-rename-20261111/tools__model_probe.py` | 8 | 8 |
| `.work/dsh-tools-20261111/tools__sync_report.py` | 8 | 8 |
| `.work/gemini_verify.py` | 6 | 6 |
| `.work/dsh-first-20261111/docs__README.md` | 5 | 4 |
| `.work/dsh-tools-20261111/tools__arena_leaderboard.py` | 5 | 5 |
| `.work/dsh-tools-20261111/tools__model_score.py` | 5 | 5 |
| `.work/agent-opt-gateway/pre/gateways__zgate__internal__config__config.go.txt` | 4 | 4 |
| `.work/dsh-first-20261111/AGENTS.md` | 4 | 2 |
| `.work/dsh-tools-20261111/gateways__legacy-router__unified-router.js` | 4 | 4 |
| `.work/gemini_diff.out` | 4 | 4 |
| `.work/gemini_diff.py` | 4 | 4 |
| `.work/agent-opt-gateway/pre/gateways__zgate__internal__bridge__bridge.go.txt` | 3 | 3 |
| `.work/agent-opt-gateway/pre/gateways__zgate__zgate.json.txt` | 3 | 3 |
| `.work/cap-probe.cjs` | 3 | 2 |
| `.work/dsh-rename-20261111/providers__workbuddy__workbuddy_fetch_pricing.py` | 3 | 3 |
| `.work/dsh-rename-20261111/sync-models.ps1` | 3 | 3 |
| `.work/dsh-tools-20261111/tools__caps_upstream.py` | 3 | 3 |
| `.work/zc_procs2.ps1` | 3 | 3 |
| `.work/zgate.json.bak-20261109-gemini-ttft.json` | 3 | 3 |
| `.work/agent-gemini-analysis.json` | 2 | 1 |
| `.work/agent-opt-gateway/pre/gateways__zgate__internal__alias__alias.go.txt` | 2 | 2 |
| `.work/agent-opt-gateway/pre/gateways__zgate__internal__router__router.go.txt` | 2 | 2 |
| `.work/dsh-first-20261111/SECURITY.md` | 2 | 2 |
| `.work/dsh-rename-20261111/providers__qwen__qwen_pool_probe.py` | 2 | 2 |
| `.work/dsh-tools-20261111/gateways__legacy-router__protocol_bridge.js` | 2 | 2 |
| `.work/dsh-tools-20261111/tools__model_stream_check.py` | 2 | 2 |
| `.work/gemini_alt_inspect.py` | 2 | 2 |
| `.work/gemini_e2e_probe.py` | 2 | 2 |
| `.work/gemini_newlog_inspect.py` | 2 | 2 |
| `.work/gemini_probe.py` | 2 | 2 |
| `.work/gemini_quota_inspect.py` | 2 | 2 |
| `.work/guard.log` | 2 | 1 |
| `.work/rt_probe1.py` | 2 | 1 |
| `.work/rt_probe2.py` | 2 | 1 |
| `.work/rt_probe3.py` | 2 | 1 |
| `.work/rt_probe4.py` | 2 | 1 |
| `.work/_scanB_measure.cjs` | 1 | 1 |
| `.work/agent-gemini-runtime/ports-output.txt` | 1 | 1 |
| `.work/arena_gem.py` | 1 | 1 |
| `.work/asar_probe.py` | 1 | 1 |
| `.work/asar_probe10.py` | 1 | 1 |
| `.work/asar_probe11.py` | 1 | 1 |
| `.work/asar_probe12.py` | 1 | 1 |
| `.work/asar_probe13.py` | 1 | 1 |
| `.work/asar_probe14.py` | 1 | 1 |
| `.work/asar_probe15.py` | 1 | 1 |
| `.work/asar_probe16.py` | 1 | 1 |
| `.work/asar_probe17.py` | 1 | 1 |
| `.work/asar_probe18.py` | 1 | 1 |
| `.work/asar_probe19.py` | 1 | 1 |
| `.work/asar_probe2.py` | 1 | 1 |
| `.work/asar_probe20.py` | 1 | 1 |
| `.work/asar_probe21.py` | 1 | 1 |
| `.work/asar_probe22.py` | 1 | 1 |
| `.work/asar_probe23.py` | 1 | 1 |
| `.work/asar_probe24.py` | 1 | 1 |
| `.work/asar_probe25.py` | 1 | 1 |
| `.work/asar_probe26.py` | 1 | 1 |
| `.work/asar_probe27.py` | 1 | 1 |
| `.work/asar_probe28.py` | 1 | 1 |
| `.work/asar_probe29.py` | 1 | 1 |
| `.work/asar_probe3.py` | 1 | 1 |
| `.work/asar_probe30.py` | 1 | 1 |
| `.work/asar_probe31.py` | 1 | 1 |
| `.work/asar_probe32.py` | 1 | 1 |
| `.work/asar_probe33.py` | 1 | 1 |
| `.work/asar_probe4.py` | 1 | 1 |
| `.work/asar_probe5.py` | 1 | 1 |
| `.work/asar_probe6.py` | 1 | 1 |
| `.work/asar_probe7.py` | 1 | 1 |
| `.work/asar_probe8.py` | 1 | 1 |
| `.work/asar_probe9.py` | 1 | 1 |
| `.work/diffs.py` | 1 | 1 |
| `.work/digest.py` | 1 | 1 |
| `.work/gem_call.py` | 1 | 1 |
| `.work/gem_probe.py` | 1 | 1 |
| `.work/gem_probe3.py` | 1 | 1 |
| `.work/gem_verify.py` | 1 | 1 |
| `.work/gemini_auth_status.py` | 1 | 1 |
| `.work/gemini_new502_inspect.py` | 1 | 1 |
| `.work/gemini_reqbody_inspect.py` | 1 | 1 |
| `.work/gemini_ttft_fix.py` | 1 | 1 |
| `.work/gemini_ttft_inspect.py` | 1 | 1 |
| `.work/inspect-provider-config.py` | 1 | 1 |
| `.work/model-stream/report-20261109T143302Z.json` | 1 | 1 |
| `.work/model-stream/report-20261109T145117Z.json` | 1 | 1 |
| `.work/model-stream/report-20261109T150405Z.json` | 1 | 1 |
| `.work/rt_probe5.py` | 1 | 1 |
| `.work/rt_probe6.py` | 1 | 1 |
| `.work/rt_probe7.py` | 1 | 1 |
| `.work/rt_probe8.py` | 1 | 1 |
| `.work/rule_dump.py` | 1 | 1 |
| `.work/verify-final.py` | 1 | 1 |
| `.work/zc_procs.ps1` | 1 | 1 |

### 2.9 F4 类完整清单（1 文件 / 1 occ）

| 文件 | occ | 匹配行 |
|---|---|---|
| `assets/icon.svg` | 1 | 1 |

### 2.10 F6 类完整清单（12 文件 / 98 occ）

| 文件 | occ | 匹配行 |
|---|---|---|
| `tools/dsh_sync.py.bak-effort-20261110125432` | 46 | 41 |
| `evidence/agent-effort-audit.md.bak-hy3xcause-20261110` | 20 | 12 |
| `gateways/zgate/main.go.bak-20261109-dup` | 5 | 5 |
| `gateways/zgate/zgate.json.bak-20261109-cp` | 3 | 3 |
| `gateways/zgate/zgate.json.bak-500retry-20261111-110328` | 3 | 3 |
| `gateways/zgate/zgate.json.bak-guard-scope-20261110143326` | 3 | 3 |
| `gateways/zgate/zgate.json.bak-hj-noheaderwatch-20261110-2128` | 3 | 3 |
| `gateways/zgate/zgate.json.bak-injectnotice-20261110083013` | 3 | 3 |
| `gateways/zgate/zgate.json.bak-nohedge-20261111-103343` | 3 | 3 |
| `gateways/zgate/zgate.json.bak-nokill-20261110-2132` | 3 | 3 |
| `gateways/zgate/zgate.json.bak-policy-HJ-out-20261110-2115` | 3 | 3 |
| `gateways/zgate/zgate.json.bak-prefer38-20261111-104746` | 3 | 3 |

### 2.11 F7 类完整清单（4 文件 / 44 occ）

| 文件 | occ | 匹配行 |
|---|---|---|
| `evidence/PROGRESS.workbuddy.md` | 21 | 19 |
| `third-party/README.md` | 19 | 4 |
| `.gitignore` | 3 | 3 |
| `evidence/gemini-merge-result.md` | 1 | 1 |

### 2.12 C 类（运行时路径 / 环境变量）文件清单

统计口径：活跃文件（D / E / F4 / F7）内出现 `ZCODE_*`、`WB_ZCODE_PROBE_FILE`、`~/.zcode`、`.zcode\`、`ZCodeGateway`、`ZCode.exe`、`ZcodeAIModels` 的行，共 **54 文件 / 317 处**。按拍板选 A，其中契约层条目原样保留；B 类与 A/A2 同类字符串按各自归类原样保留。

| 文件 | 类 | C 类出现处 |
|---|---|---|
| `docs/TROUBLESHOOTING.md` | E | 29 |
| `docs/MAINTENANCE.md` | E | 26 |
| `docs/TOOLS.md` | E | 26 |
| `docs/SECRETS.md` | E | 25 |
| `docs/MODEL-PROVIDERS.md` | E | 17 |
| `providers/workbuddy/effective_body.js` | D | 14 |
| `tools/dsh_sync.py` | D | 13 |
| `docs/DSH-FIRST.md` | E | 12 |
| `docs/CONSOLE.md` | E | 8 |
| `docs/MODEL-ALIAS.md` | E | 8 |
| `docs/CAPABILITY-AUDIT.md` | E | 7 |
| `docs/QODER.md` | E | 7 |
| `docs/UPSTREAM.md` | E | 7 |
| `evidence/PROGRESS.workbuddy.md` | F7 | 7 |
| `tools/model_caps.py` | D | 7 |
| `tools/rename-to-modelbus.ps1` | D | 7 |
| `AGENTS.md` | E | 6 |
| `docs/ARCHITECTURE.md` | E | 6 |
| `docs/BENCHMARKS.md` | E | 5 |
| `docs/QWEN.md` | E | 5 |
| `providers/workbuddy/workbuddy_probe.py` | D | 5 |
| `tools/model_alias.py` | D | 5 |
| `docs/PITFALLS.md` | E | 4 |
| `gateways/zgate/internal/config/config.go` | D | 4 |
| `tools/agent_profiles.py` | D | 4 |
| `tools/model_score.py` | D | 4 |
| `tools/sync_report.py` | D | 4 |
| `docs/ZGATE-LIFECYCLE.md` | E | 3 |
| `gateways/zgate/zgate.json` | D | 3 |
| `providers/workbuddy/workbuddy_sync.py` | D | 3 |
| `README.md` | E | 3 |
| `.gitignore` | F7 | 2 |
| `CONTRIBUTING.md` | E | 2 |
| `providers/qwen/qwen_sync.py` | D | 2 |
| `tests/test_dsh_sync_retry_policy.py` | D | 2 |
| `third-party/README.md` | F7 | 2 |
| `tools/arena_leaderboard.py` | D | 2 |
| `tools/caps_upstream.py` | D | 2 |
| `tools/model_probe.py` | D | 2 |
| `tools/zgate-lifecycle/current-models.ps1` | D | 2 |
| `tools/zgate-lifecycle/install-lifecycle.ps1` | D | 2 |
| `.github/ISSUE_TEMPLATE/bug_report.yml` | D | 1 |
| `docs/REVIEW-2026-11-10.md` | E | 1 |
| `docs/ROUTING-POLICY.md` | E | 1 |
| `gateways/legacy-router/unified-router.js` | D | 1 |
| `gateways/zgate/internal/alias/alias.go` | D | 1 |
| `providers/opencode-go/ops/go_model_sync.py` | D | 1 |
| `providers/qoder/qoder_sync.py` | D | 1 |
| `sync-models.ps1` | D | 1 |
| `tests/test_dsh_sync_efforts.py` | D | 1 |
| `tests/test_model_alias_hop_order.py` | D | 1 |
| `tests/test_model_alias_qd_free.py` | D | 1 |
| `tests/test_model_caps.py` | D | 1 |
| `tools/zgate-lifecycle/deploy-zgate.ps1` | D | 1 |

## 3 「当前字符串 → 目标字符串」映射表（按主代理拍板「选 A」）

### 3.1 落地口径总表（三层）

| 层 | 主代理裁决 | 本分片执行 |
|---|---|---|
| ① **契约层**：`ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` / `ZCODE_BUILTIN` / `ZCODE_GATEWAY_KEY` / `~/.zcode/v2/provider_config.json` / `zcode-main|free|saver` / `zcode-*` route id / `zcode-model-ledger.json` / `%LOCALAPPDATA%\ZCodeGateway\` / schema 键 / NOTICE 商标 / `third-party/zcode*` 原件 | **保持原样，零新增同名替代** | §3.4 KEEP；理由：第三方 ZCode 客户端与 DSH 宿主实际读取的真实契约，DSH 侧 `cordis.patch.yml` 的 route id 与 refs 键已绑定 `zcode-*` 命名，再造 `DSH_*` 优先会产生双写与静默漂移 |
| ② **实现层自造 env**：`WB_ZCODE_PROBE_FILE` / `ZCODE_API_TYPE` / `ZCODE_BASE_URL` / `ZCODE_MAX_OUTPUT_TOKENS` | 改中性名 `WB_PROBE_FILE` / `MB_API_TYPE` / `MB_BASE_URL` / `MB_MAX_OUTPUT_TOKENS`，**旧名保留 fallback 读取别名**（第 6 路子代理 `a427cdfe` 落地） | §3.2 MUST / §3.3 FALLBACK |
| ③ **第一方叙述性 ZCode**：docstring / 横幅 / 注释 / 本仓自设 User-Agent / 文档主语 | 改「DSH 主宿主 + 各类 agent」口径 | §3.5 TEXT |
| ④ **vendored 上游署名 + 历史记录** | 保持原样 | §2 A / A2 / B + §3.4 KEEP |

> 任务书原 C 类「DSH_* 优先 + ZCODE_* 兜底」映射表完整保留于 §5.3，明确标注「按 live 契约层保持原样，本轮未实施，仅作备选」；两条路线**不并列、不作同等推荐**。

### 3.2 必须改（MUST / FALLBACK：实现层自造标识符、文件名、env）

> 证据为作业期间取样行号；实施前用 `Select-String -LiteralPath <file> -Pattern '<old>'` 复核当前行号（并发分片可能已改动或已 `git mv`）。

| 当前 | 目标（主代理定名） | 策略 | 证据（file:line，取样值） |
|---|---|---|---|
| `workbuddy_zcode_sync.py` | `workbuddy_sync.py` | MUST | sync-models.ps1:228 / docs/DSH-FIRST.md:85 |
| `workbuddy_probe_zcode.py` | `workbuddy_probe.py` | MUST | providers/workbuddy/workbuddy_probe_zcode.py:75 / docs/DSH-FIRST.md:85 |
| `qoder_zcode_sync.py` | `qoder_sync.py` | MUST | sync-models.ps1:253 / docs/DSH-FIRST.md:85 |
| `qoder_probe_zcode.py` | `qoder_probe.py` | MUST | docs/DSH-FIRST.md:85 |
| `qwen_zcode_sync.py` | `qwen_sync.py` | MUST | docs/DSH-FIRST.md:85 |
| `zcode_effective_body.js` | `effective_body.js` | MUST | tools/dsh_sync.py:60 / tools/model_probe.py:45 / providers/workbuddy/workbuddy_probe_zcode.py:75 / docs/DSH-FIRST.md:85 |
| `zcode_effective_body` | `effective_body` | MUST | 活跃替换域 token 普查 |
| `zcode_body` | `effective_body` | MUST | providers/workbuddy/workbuddy_probe_zcode.py:110,282 |
| `_zcode_providers` | `_host_providers` | MUST | tools/dsh_sync.py:152 |
| `_zcode_sync` | `_host_sync` | MUST | 活跃替换域 token 普查 |
| `zcode_provider_config` | `provider_config_sink` | MUST | docs/DSH-FIRST.md:62（写入段收敛 providers/_sink/） |
| `wb_zcode_probe.json` | `wb_probe.json` | MUST | providers/workbuddy/workbuddy_zcode_sync.py:152 |
| `zcode_gateway_watch.ps1` | `gateway_watch.ps1` | MUST | docs/ARCHITECTURE.md:52-56,316（已退役脚本，文档过期口径） |
| `WB_ZCODE_PROBE_FILE` | `WB_PROBE_FILE` | FALLBACK | providers/workbuddy/workbuddy_probe_zcode.py:67 / workbuddy_zcode_sync.py:152 |
| `ZCODE_API_TYPE` | `MB_API_TYPE` | FALLBACK | providers/workbuddy/zcode_effective_body.js:231 |
| `ZCODE_BASE_URL` | `MB_BASE_URL` | FALLBACK | providers/workbuddy/zcode_effective_body.js:232 |
| `ZCODE_MAX_OUTPUT_TOKENS` | `MB_MAX_OUTPUT_TOKENS` | FALLBACK | providers/workbuddy/zcode_effective_body.js:237 |

### 3.3 保留兼容（FALLBACK：改名后旧名只作读取别名）

| 新名（优先读） | 旧名（fallback 读取别名） | 实现要点 |
|---|---|---|
| `WB_PROBE_FILE` | `WB_ZCODE_PROBE_FILE` | 读取顺序 `新名` → `旧名` → 默认值；旧名只保留一处兜底解析，不新写、不双写、不落盘偏好 |
| `MB_API_TYPE` | `ZCODE_API_TYPE` | 读取顺序 `新名` → `旧名` → 默认值；旧名只保留一处兜底解析，不新写、不双写、不落盘偏好 |
| `MB_BASE_URL` | `ZCODE_BASE_URL` | 读取顺序 `新名` → `旧名` → 默认值；旧名只保留一处兜底解析，不新写、不双写、不落盘偏好 |
| `MB_MAX_OUTPUT_TOKENS` | `ZCODE_MAX_OUTPUT_TOKENS` | 读取顺序 `新名` → `旧名` → 默认值；旧名只保留一处兜底解析，不新写、不双写、不落盘偏好 |

除上述 4 个自造 env 外，**所有 `ZCODE_*` 与 `~/.zcode/v2/*` 契约层条目零改动**（§3.4）。

### 3.4 原样保留（KEEP，改了即坏或属史实 / 上游事实）

| 类别 | 具体字符串 / 文件 | 理由 |
|---|---|---|
| 契约层 env | `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE`、`ZCODE_BUILTIN`、`ZCODE_GATEWAY_KEY`、`ZCODE_CONFIG` | 第三方 ZCode 客户端与 DSH 宿主实际读取的真实契约；拍板选 A 零新增替代 |
| 契约层路径 | `~/.zcode/v2/provider_config.json`、`~/.zcode/v2/model-alias-map.json`、`~/.zcode/v2/model_probe.json`、`~/.zcode/v2/quota-windows.json`、`~/.zcode/v2/arena-main.json`、`~/.zcode/v2/model-scores.json`、`%LOCALAPPDATA%\ZCodeGateway\`、`ZCode.exe`、`Programs/ZCode/resources/app.asar` | 外部真实读取位置 / 安装路径事实 |
| 契约层 ID / 台账 | `zcode-main`、`zcode-free`、`zcode-saver`、`zcode-*` route id、`zcode-model-ledger.json` | DSH 侧 `cordis.patch.yml` 的 route id 与 refs 键已绑定 `zcode-*` 命名 |
| 契约层 schema 键 | `providerConfigRules`、`modelConfigRules.providerModelRules`、`modelOrder`、`personalModelIds`、`optionSpecs.reasoningLevel.{values,map}` | 写进 ZCode 配置的真实 schema，外部世界定 |
| A 上游快照 | `third-party/zcode/**`、`third-party/zcodium/**`、`zcode-builtin.json`、`zcode-builtin-reasoning-rules.json`、`UPSTREAM.md`、`model-config.ts`、`schema.ts`、`rule-data-schema.ts` | vendored 上游原件，署名与内容事实 |
| A 许可证 | `NOTICE`（50 occ）、`LICENSE`、`third-party/zcode/LICENSE` | 版权与商标段 |
| A2 运行日志 | `ZCode/3.17.2`、`ZCode/3.17.1`、`ZCodeExecutor`（上游 User-Agent） | 上游请求运行史实 |
| B 历史记录 | `CHANGELOG.md`、`PROGRESS.md`、`memories/**`、`evidence/agent-*.md`、`docs/release-notes/**`、`docs/archive/**` | 史实保留 |
| 外部路径 / URL | `https://github.com/MVennn/ZcodeAIModels/issues/new/choose`、`ZcodeAIModels` 仓库名、Windows 计划任务名 | 外部标识事实 |
| F1 / F6 | `.work/**`、`*.bak-*` / `.log` / `__pycache__` | 临时产物与备份，随源文件同步，单独跳过 |

### 3.5 自然语言措辞（TEXT）

第一方 docstring / 横幅 / 注释 / 本仓自设 User-Agent / 文档主语里的「ZCode 客户端 / ZCode 中心」→「DSH 主宿主 + 各类 agent / 兼容投影 / 宿主」；`ZCode provider` →「宿主 provider」；错误提示「找不到 ZCode 配置」→「找不到宿主配置」。仓内 `docs/DSH-FIRST.md:3,21,23` 与 `AGENTS.md:6` 已给出方向：DSH 是主宿主，ZCode 降为兼容投影，会话 / 子代理 / headless / 服务插件等各类 agent 共用 `gateways/zgate` 单一入口。**注意**：A2 上游运行日志里的 User-Agent（`ZCode/3.17.2` / `ZCodeExecutor`）按 §3.4 KEEP，不属本层。

### 3.6 当前残留实证（生成时动态扫描活跃文件，取样 2026-11-11 15:59:35 (+08:00)）

| old | 活跃文件命中行数 | 前 4 个 file:line | 处置 |
|---|---|---|---|
| `workbuddy_zcode_sync.py` | 28 | `.github/ISSUE_TEMPLATE/bug_report.yml:65` / `docs/CAPABILITY-AUDIT.md:110` / `docs/CAPABILITY-AUDIT.md:255` / `docs/DSH-FIRST.md:85` | MUST |
| `workbuddy_probe_zcode.py` | 16 | `.github/ISSUE_TEMPLATE/bug_report.yml:64` / `docs/DSH-FIRST.md:85` / `docs/MAINTENANCE.md:129` / `docs/MAINTENANCE.md:130` | MUST |
| `qoder_zcode_sync.py` | 25 | `docs/CAPABILITY-AUDIT.md:112` / `docs/CAPABILITY-AUDIT.md:254` / `docs/DSH-FIRST.md:85` / `docs/MAINTENANCE.md:190` | MUST |
| `qoder_probe_zcode.py` | 13 | `docs/DSH-FIRST.md:85` / `docs/MAINTENANCE.md:417` / `docs/MODEL-PROVIDERS.md:495` / `docs/QODER.md:8` | MUST |
| `qwen_zcode_sync.py` | 10 | `docs/DSH-FIRST.md:85` / `docs/QWEN.md:169` / `docs/QWEN.md:176` / `docs/QWEN.md:234` | MUST |
| `zcode_effective_body.js` | 22 | `docs/CAPABILITY-AUDIT.md:26` / `docs/DSH-FIRST.md:85` / `docs/MAINTENANCE.md:153` / `docs/MODEL-ALIAS.md:567` | KEEP（契约层） |
| `zcode_effective_body` | 22 | `docs/CAPABILITY-AUDIT.md:26` / `docs/DSH-FIRST.md:85` / `docs/MAINTENANCE.md:153` / `docs/MODEL-ALIAS.md:567` | KEEP（契约层） |
| `zcode_body` | 3 | `providers/workbuddy/workbuddy_probe.py:110` / `providers/workbuddy/workbuddy_probe.py:265` / `providers/workbuddy/workbuddy_probe.py:282` | KEEP（契约层） |
| `_zcode_providers` | 2 | `tools/dsh_sync.py:152` / `tools/dsh_sync.py:577` | MUST |
| `_zcode_sync` | 59 | `.github/ISSUE_TEMPLATE/bug_report.yml:65` / `docs/CAPABILITY-AUDIT.md:110` / `docs/CAPABILITY-AUDIT.md:112` / `docs/CAPABILITY-AUDIT.md:254` | MUST |
| `zcode_provider_config` | 0 | （当前磁盘已无残留） | KEEP（契约层） |
| `wb_zcode_probe.json` | 13 | `.gitignore:33` / `docs/MAINTENANCE.md:165` / `docs/SECRETS.md:41` / `docs/SECRETS.md:115` | MUST |
| `zcode_gateway_watch.ps1` | 5 | `docs/ARCHITECTURE.md:27` / `docs/ARCHITECTURE.md:52` / `docs/ARCHITECTURE.md:212` / `docs/ARCHITECTURE.md:316` | KEEP（契约层） |
| `WB_ZCODE_PROBE_FILE` | 5 | `CONTRIBUTING.md:32` / `docs/SECRETS.md:115` / `docs/TROUBLESHOOTING.md:301` / `providers/workbuddy/workbuddy_probe.py:68` | FALLBACK |
| `ZCODE_API_TYPE` | 3 | `docs/SECRETS.md:117` / `providers/workbuddy/effective_body.js:44` / `providers/workbuddy/effective_body.js:232` | FALLBACK |
| `ZCODE_BASE_URL` | 2 | `providers/workbuddy/effective_body.js:45` / `providers/workbuddy/effective_body.js:233` | FALLBACK |
| `ZCODE_MAX_OUTPUT_TOKENS` | 2 | `providers/workbuddy/effective_body.js:46` / `providers/workbuddy/effective_body.js:238` | FALLBACK |
| `zcode-model-ledger.json` | 2 | `docs/PITFALLS.md:775` / `tools/dsh_sync.py:73` | KEEP（契约层） |
| `zcode-main` | 21 | `docs/MODEL-ALIAS.md:253` / `docs/MODEL-ALIAS.md:254` / `docs/PITFALLS.md:759` / `docs/PITFALLS.md:766` | KEEP（契约层） |
| `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` | 21 | `AGENTS.md:6` / `AGENTS.md:51` / `docs/DSH-FIRST.md:31` / `docs/PITFALLS.md:201` | KEEP（契约层） |
| `ZCODE_BUILTIN` | 14 | `AGENTS.md:6` / `AGENTS.md:52` / `CONTRIBUTING.md:33` / `docs/DSH-FIRST.md:31` | KEEP（契约层） |
| `ZCODE_GATEWAY_KEY` | 10 | `docs/TOOLS.md:35` / `tests/test_dsh_sync_retry_policy.py:109` / `tools/agent_profiles.py:14` / `tools/dsh_sync.py:21` | KEEP（契约层） |

说明：`count=0` 表示该字符串已被并发分片改掉或文件已 `git mv`；`KEEP（契约层）` 行的命中是**预期保留**，不是待办。实施替换以本表当前值为准，别按 §3.2 的取样行号硬改。

## 4 可直接执行的替换方案（按选 A）

### 4.1 执行顺序与回滚

1. **契约层零改动**：先确认 §3.4 全部条目不在替换白名单内；不新增任何 `DSH_*` 同名 env。
2. 备份：`Copy-Item` 逐文件到 `F:\Project\ModelBus\.work\dsh-rename-backup-<时间戳>\`（只进真实项目内 `.work/`，视图根零新建）。
3. 文件名：按 §3.2 用 `git mv` 改 6 个脚本（目标名 `workbuddy_sync.py` / `workbuddy_probe.py` / `effective_body.js` / `qoder_sync.py` / `qoder_probe.py` / `qwen_sync.py`），**同一批**改完 `tools/dsh_sync.py:60`、`tools/model_probe.py:45`、`providers/workbuddy/workbuddy_probe_zcode.py:75`、`sync-models.ps1:228,253` 五处路径引用（`docs/DSH-FIRST.md:35` 实列改名硬回归面）。该步由第 6 路子代理 `a427cdfe` 落地，主代理验收按磁盘复核。
4. 自造 env：先改代码读取逻辑为「新名 → 旧名 fallback → 默认值」，再替换字符串；单纯文本替换会打断兼容，顺序固定。4 个 `ZCODE_*` 契约 env 不动。
5. 叙述性措辞：D / E / F7 按 §3.5 改写主语；`docs/DSH-FIRST.md:31,32,35,85`、`AGENTS.md:6` 的完成态承诺由主代理验收后对齐，失败则把状态改回待落地。
6. 写入段收敛：三个 `*_zcode_sync.py` 写入段（`workbuddy` 364-371 / `qoder` 191-199 / `qwen` 345-352）收敛 `providers/_sink/zcode_provider_config.py`（`docs/DSH-FIRST.md:62`），避免多处各自写回。
7. `gateways/zgate/**` Go 代码改完按 `AGENTS.md` §6 走 `tools/zgate-lifecycle/restart-zgate.cmd` 换版（本分片未执行，由主代理按部署三步「备份 → md5 校验 → 受控重启」处理）。
8. 验收：§4.4 五条命令 + §1.10 复核命令比对 occ 变化（A / A2 / B 不变、D / E / F7 下降、4 个旧 env 名仍可 fallback 读取、契约层 `zcode-*` 与 `ZCODE_*` 命中数不变）。

### 4.2 逐文件 old→new（活跃替换域 75 文件 / 429 条 token 映射；单表，按文件分组排序）

策略码：`MUST` 实现层必须改 / `FALLBACK` 改中性名并保留旧名读取别名 / `KEEP` 契约层与上游原样保留 / `TEXT` 按上下文改写为「DSH 主宿主 / 各类 agent / 兼容投影」。token 内本机绝对路径已脱敏为 `<HOST_ABS_PATH>`；凭据值零输出，仅列环境变量名。行号 = 该文件内 token 首次出现行。

| 文件 | BOM | CRLF | 首次行 | old | new | 策略 |
|---|---|---|---|---|---|---|
| `.github/ISSUE_TEMPLATE/bug_report.yml` | 无 | 有 | 19 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `.github/ISSUE_TEMPLATE/bug_report.yml` | 无 | 有 | 39 | `zcode-version` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `.github/ISSUE_TEMPLATE/bug_report.yml` | 无 | 有 | 64 | `providers/workbuddy/workbuddy_probe_zcode.py` | `providers/workbuddy/workbuddy_probe.py` | MUST |
| `.github/ISSUE_TEMPLATE/bug_report.yml` | 无 | 有 | 65 | `providers/workbuddy/workbuddy_zcode_sync.py` | `providers/workbuddy/workbuddy_sync.py` | MUST |
| `.github/ISSUE_TEMPLATE/feature_request.yml` | 无 | 无 | 38 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `.gitignore` | 无 | 有 | 2 | `zcode-ai-models` | `—（契约层/上游原样保留）` | KEEP |
| `.gitignore` | 无 | 有 | 33 | `wb_zcode_probe.json` | `wb_probe.json` | MUST |
| `.gitignore` | 无 | 有 | 111 | `\ZcodeAIModels\logs\` | `—（契约层/上游原样保留）` | KEEP |
| `AGENTS.md` | 无 | 有 | 6 | `\ZCodeGateway\` | `—（契约层/上游原样保留）` | KEEP |
| `AGENTS.md` | 无 | 有 | 6 | `~/.zcode/v2/provider_config.json` | `—（契约层/上游原样保留）` | KEEP |
| `AGENTS.md` | 无 | 有 | 6 | `third-party/zcode` | `—（契约层/上游原样保留）` | KEEP |
| `AGENTS.md` | 无 | 有 | 6 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `AGENTS.md` | 无 | 有 | 6 | `ZCODE_BUILTIN` | `—（契约层/上游原样保留）` | KEEP |
| `AGENTS.md` | 无 | 有 | 6 | `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` | `—（契约层/上游原样保留）` | KEEP |
| `assets/icon.svg` | 无 | 无 | 1 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `CONTRIBUTING.md` | 无 | 有 | 32 | `WB_ZCODE_PROBE_FILE` | `WB_PROBE_FILE（旧名 WB_ZCODE_PROBE_FILE fallback 读取）` | FALLBACK |
| `CONTRIBUTING.md` | 无 | 有 | 33 | `ZCODE_BUILTIN` | `—（契约层/上游原样保留）` | KEEP |
| `CONTRIBUTING.md` | 无 | 有 | 53 | `third-party/zcode/` | `—（契约层/上游原样保留）` | KEEP |
| `CONTRIBUTING.md` | 无 | 有 | 54 | `third-party/zcode/UPSTREAM.md` | `—（契约层/上游原样保留）` | KEEP |
| `docs/ARCHITECTURE.md` | 无 | 有 | 5 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/ARCHITECTURE.md` | 无 | 有 | 27 | `workbuddy/zcode_gateway_watch.ps1` | `workbuddy/gateway_watch.ps1` | MUST |
| `docs/ARCHITECTURE.md` | 无 | 有 | 52 | `zcode_gateway_watch.ps1` | `—（契约层/上游原样保留）` | KEEP |
| `docs/ARCHITECTURE.md` | 无 | 有 | 142 | `~/.zcode/v2/model-alias-map.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/ARCHITECTURE.md` | 无 | 有 | 162 | `\ZCodeGateway\` | `—（契约层/上游原样保留）` | KEEP |
| `docs/BENCHMARKS.md` | 无 | 无 | 73 | `zcode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/BENCHMARKS.md` | 无 | 无 | 73 | `ZCODE` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/BENCHMARKS.md` | 无 | 无 | 180 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/BENCHMARKS.md` | 无 | 无 | 323 | `~/.zcode/v2/arena-main.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/BENCHMARKS.md` | 无 | 无 | 395 | `~/.zcode/v2/arena-leaderboard.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/BENCHMARKS.md` | 无 | 无 | 411 | `~/.zcode/v2/model-scores.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/CAPABILITY-AUDIT.md` | 无 | 无 | 7 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/CAPABILITY-AUDIT.md` | 无 | 无 | 26 | `providers/workbuddy/zcode_effective_body.js:104-164` | `providers/workbuddy/effective_body.js:104-164` | MUST |
| `docs/CAPABILITY-AUDIT.md` | 无 | 无 | 32 | `~/.zcode/v2/provider_config.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/CAPABILITY-AUDIT.md` | 无 | 无 | 36 | `third-party/zcode/zcode-builtin.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/CAPABILITY-AUDIT.md` | 无 | 无 | 61 | `zcode-builtin.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/CAPABILITY-AUDIT.md` | 无 | 无 | 110 | `providers/workbuddy/workbuddy_zcode_sync.py:284-333` | `providers/workbuddy/workbuddy_sync.py:284-333` | MUST |
| `docs/CAPABILITY-AUDIT.md` | 无 | 无 | 112 | `providers/qoder/qoder_zcode_sync.py:283` | `providers/qoder/qoder_sync.py:283` | MUST |
| `docs/CAPABILITY-AUDIT.md` | 无 | 无 | 254 | `providers/qoder/qoder_zcode_sync.py` | `providers/qoder/qoder_sync.py` | MUST |
| `docs/CAPABILITY-AUDIT.md` | 无 | 无 | 255 | `providers/workbuddy/workbuddy_zcode_sync.py` | `providers/workbuddy/workbuddy_sync.py` | MUST |
| `docs/CONSOLE.md` | 无 | 无 | 28 | `~/.zcode/v2/` | `—（契约层/上游原样保留）` | KEEP |
| `docs/CONSOLE.md` | 无 | 无 | 51 | `~/.zcode/v2/model-alias-map.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/CONSOLE.md` | 无 | 无 | 52 | `~/.zcode/v2/provider_config.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/CONSOLE.md` | 无 | 无 | 53 | `~/.zcode/v2/model_probe.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/CONSOLE.md` | 无 | 无 | 55 | `~/.zcode/v2/model-scores.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/CONSOLE.md` | 无 | 无 | 56 | `~/.zcode/v2/quota-windows.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/CONSOLE.md` | 无 | 无 | 57 | `~/.zcode/v2/arena-main.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/CONSOLE.md` | 无 | 无 | 63 | `/ZCodeGateway/zgate.log` | `—（契约层/上游原样保留）` | KEEP |
| `docs/DOC-RULES.md` | 无 | 有 | 48 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/DSH-FIRST.md` | 无 | 无 | 3 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/DSH-FIRST.md` | 无 | 无 | 31 | `\ZCodeGateway\` | `—（契约层/上游原样保留）` | KEEP |
| `docs/DSH-FIRST.md` | 无 | 无 | 31 | `~/.zcode/v2/provider_config.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/DSH-FIRST.md` | 无 | 无 | 31 | `third-party/zcode/` | `—（契约层/上游原样保留）` | KEEP |
| `docs/DSH-FIRST.md` | 无 | 无 | 31 | `third-party/zcodium/` | `—（契约层/上游原样保留）` | KEEP |
| `docs/DSH-FIRST.md` | 无 | 无 | 31 | `ZCODE_BUILTIN` | `—（契约层/上游原样保留）` | KEEP |
| `docs/DSH-FIRST.md` | 无 | 无 | 31 | `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` | `—（契约层/上游原样保留）` | KEEP |
| `docs/DSH-FIRST.md` | 无 | 无 | 50 | `zcode_provider_` | `—（契约层/上游原样保留）` | KEEP |
| `docs/DSH-FIRST.md` | 无 | 无 | 54 | `~/.zcode/v2/` | `—（契约层/上游原样保留）` | KEEP |
| `docs/DSH-FIRST.md` | 无 | 无 | 69 | `third-party/zcode/zcode-builtin.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/DSH-FIRST.md` | 无 | 无 | 71 | `~/.zcode/v2/model-alias-map.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/DSH-FIRST.md` | 无 | 无 | 85 | `qoder_probe_zcode.py` | `qoder_probe.py` | MUST |
| `docs/DSH-FIRST.md` | 无 | 无 | 85 | `qoder_zcode_sync.py` | `qoder_sync.py` | MUST |
| `docs/DSH-FIRST.md` | 无 | 无 | 85 | `qwen_zcode_sync.py` | `qwen_sync.py` | MUST |
| `docs/DSH-FIRST.md` | 无 | 无 | 85 | `workbuddy_probe_zcode.py` | `workbuddy_probe.py` | MUST |
| `docs/DSH-FIRST.md` | 无 | 无 | 85 | `workbuddy_zcode_sync.py` | `workbuddy_sync.py` | MUST |
| `docs/DSH-FIRST.md` | 无 | 无 | 85 | `zcode_effective_body.js` | `—（契约层/上游原样保留）` | KEEP |
| `docs/DSH-FIRST.md` | 无 | 无 | 127 | `zcode_gateway_watch.ps1` | `—（契约层/上游原样保留）` | KEEP |
| `docs/MAINTENANCE.md` | 无 | 有 | 12 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/MAINTENANCE.md` | 无 | 有 | 128 | `~/.zcode/v2/model_probe.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/MAINTENANCE.md` | 无 | 有 | 129 | `providers/workbuddy/workbuddy_probe_zcode.py` | `providers/workbuddy/workbuddy_probe.py` | MUST |
| `docs/MAINTENANCE.md` | 无 | 有 | 153 | `workbuddy_probe_zcode.py` | `workbuddy_probe.py` | MUST |
| `docs/MAINTENANCE.md` | 无 | 有 | 153 | `zcode_effective_body.js` | `—（契约层/上游原样保留）` | KEEP |
| `docs/MAINTENANCE.md` | 无 | 有 | 165 | `providers/workbuddy/cache/wb_zcode_probe.json` | `providers/workbuddy/cache/wb_probe.json` | MUST |
| `docs/MAINTENANCE.md` | 无 | 有 | 166 | `providers/workbuddy/logs/wb_zcode_probe.log` | `providers/workbuddy/logs/wb_probe.log` | MUST |
| `docs/MAINTENANCE.md` | 无 | 有 | 189 | `workbuddy_zcode_sync.py` | `workbuddy_sync.py` | MUST |
| `docs/MAINTENANCE.md` | 无 | 有 | 190 | `providers/qoder/qoder_zcode_sync.py` | `providers/qoder/qoder_sync.py` | MUST |
| `docs/MAINTENANCE.md` | 无 | 有 | 197 | `~/.zcode/v2/provider_config.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/MAINTENANCE.md` | 无 | 有 | 198 | `~/.zcode/v2/provider_config.json.manual-` | `—（契约层/上游原样保留）` | KEEP |
| `docs/MAINTENANCE.md` | 无 | 有 | 208 | `~/.zcode/v2/provider_config.json.bak-wbproxy-20261020-163812` | `—（契约层/上游原样保留）` | KEEP |
| `docs/MAINTENANCE.md` | 无 | 有 | 237 | `zcode-` | `—（契约层/上游原样保留）` | KEEP |
| `docs/MAINTENANCE.md` | 无 | 有 | 245 | `qoder_zcode_sync.py` | `qoder_sync.py` | MUST |
| `docs/MAINTENANCE.md` | 无 | 有 | 316 | `\ZCodeGateway` | `—（契约层/上游原样保留）` | KEEP |
| `docs/MAINTENANCE.md` | 无 | 有 | 321 | `\ZCodeGateway\ensure-zgate.vbs` | `—（契约层/上游原样保留）` | KEEP |
| `docs/MAINTENANCE.md` | 无 | 有 | 326 | `ZcodeAIModels-zgate-daemon` | `—（契约层/上游原样保留）` | KEEP |
| `docs/MAINTENANCE.md` | 无 | 有 | 328 | `\ZCodeGateway\autostart-backup-20261109\restore-autostart.ps1` | `—（契约层/上游原样保留）` | KEEP |
| `docs/MAINTENANCE.md` | 无 | 有 | 342 | `\ZCodeGateway\zgate.log` | `—（契约层/上游原样保留）` | KEEP |
| `docs/MAINTENANCE.md` | 无 | 有 | 368 | `~/.zcode/v2/model-alias-map.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/MAINTENANCE.md` | 无 | 有 | 378 | `\ZCodeGateway\` | `—（契约层/上游原样保留）` | KEEP |
| `docs/MAINTENANCE.md` | 无 | 有 | 417 | `qoder_probe_zcode.py` | `qoder_probe.py` | MUST |
| `docs/MODEL-ALIAS.md` | 无 | 无 | 16 | `~/.zcode/v2/provider_config.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/MODEL-ALIAS.md` | 无 | 无 | 16 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/MODEL-ALIAS.md` | 无 | 无 | 17 | `~/.zcode/v2/model-alias-map.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/MODEL-ALIAS.md` | 无 | 无 | 253 | `zcode-main` | `—（契约层/上游原样保留）` | KEEP |
| `docs/MODEL-ALIAS.md` | 无 | 无 | 422 | `~/.zcode/v2/arena-main.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/MODEL-ALIAS.md` | 无 | 无 | 473 | `~/.zcode/v2/model_probe.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/MODEL-ALIAS.md` | 无 | 无 | 499 | `qoder_zcode_sync.py` | `qoder_sync.py` | MUST |
| `docs/MODEL-ALIAS.md` | 无 | 无 | 499 | `workbuddy_zcode_sync.py` | `workbuddy_sync.py` | MUST |
| `docs/MODEL-ALIAS.md` | 无 | 无 | 567 | `providers/workbuddy/zcode_effective_body.js` | `providers/workbuddy/effective_body.js` | MUST |
| `docs/MODEL-PROVIDERS.md` | 无 | 有 | 3 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/MODEL-PROVIDERS.md` | 无 | 有 | 73 | `~/.zcode/v2/provider_config.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/MODEL-PROVIDERS.md` | 无 | 有 | 93 | `providers/workbuddy/workbuddy_zcode_sync.py` | `providers/workbuddy/workbuddy_sync.py` | MUST |
| `docs/MODEL-PROVIDERS.md` | 无 | 有 | 94 | `providers/qoder/qoder_zcode_sync.py` | `providers/qoder/qoder_sync.py` | MUST |
| `docs/MODEL-PROVIDERS.md` | 无 | 有 | 130 | `workbuddy_zcode_sync.py` | `workbuddy_sync.py` | MUST |
| `docs/MODEL-PROVIDERS.md` | 无 | 有 | 495 | `providers/qoder/qoder_probe_zcode.py` | `providers/qoder/qoder_probe.py` | MUST |
| `docs/MODEL-PROVIDERS.md` | 无 | 有 | 746 | `zcode_effective_body.js` | `—（契约层/上游原样保留）` | KEEP |
| `docs/MODEL-PROVIDERS.md` | 无 | 有 | 751 | `resources/config/provider/zcode-builtin.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/MODEL-PROVIDERS.md` | 无 | 有 | 763 | `providers/workbuddy/zcode_effective_body.js` | `providers/workbuddy/effective_body.js` | MUST |
| `docs/MODEL-PROVIDERS.md` | 无 | 有 | 785 | `qoder_zcode_sync.py` | `qoder_sync.py` | MUST |
| `docs/MODEL-QUICK-REF.md` | 无 | 有 | 8 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/MODEL-STREAM.md` | 无 | 无 | 29 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/MODEL-STREAM.md` | 无 | 无 | 29 | `zcode-` | `—（契约层/上游原样保留）` | KEEP |
| `docs/PITFALLS.md` | 无 | 无 | 6 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/PITFALLS.md` | 无 | 无 | 71 | `providers/workbuddy/workbuddy_probe_zcode.py` | `providers/workbuddy/workbuddy_probe.py` | MUST |
| `docs/PITFALLS.md` | 无 | 无 | 97 | `providers/workbuddy/zcode_effective_body.js` | `providers/workbuddy/effective_body.js` | MUST |
| `docs/PITFALLS.md` | 无 | 无 | 201 | `ZCODE_BUILTIN` | `—（契约层/上游原样保留）` | KEEP |
| `docs/PITFALLS.md` | 无 | 无 | 201 | `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` | `—（契约层/上游原样保留）` | KEEP |
| `docs/PITFALLS.md` | 无 | 无 | 312 | `~/.zcode/v2/model-alias-map.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/PITFALLS.md` | 无 | 无 | 759 | `zcode-main` | `—（契约层/上游原样保留）` | KEEP |
| `docs/PITFALLS.md` | 无 | 无 | 775 | `/zcode-model-ledger.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/QODER.md` | 无 | 有 | 8 | `qoder_probe_zcode.py` | `qoder_probe.py` | MUST |
| `docs/QODER.md` | 无 | 有 | 9 | `qoder_zcode_sync.py` | `qoder_sync.py` | MUST |
| `docs/QODER.md` | 无 | 有 | 15 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/QODER.md` | 无 | 有 | 80 | `providers/qoder/qoder_zcode_sync.py` | `providers/qoder/qoder_sync.py` | MUST |
| `docs/QODER.md` | 无 | 有 | 93 | `~/.zcode/v2/model-alias-map.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/QODER.md` | 无 | 有 | 135 | `providers/qoder/qoder_probe_zcode.py` | `providers/qoder/qoder_probe.py` | MUST |
| `docs/QWEN.md` | 无 | 有 | 92 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/QWEN.md` | 无 | 有 | 169 | `qwen_zcode_sync.py` | `qwen_sync.py` | MUST |
| `docs/QWEN.md` | 无 | 有 | 176 | `providers/qwen/qwen_zcode_sync.py` | `providers/qwen/qwen_sync.py` | MUST |
| `docs/README.md` | 无 | 无 | 28 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/README.md` | 无 | 无 | 59 | `ZCodium` | `—（契约层/上游原样保留）` | KEEP |
| `docs/REVIEW-2026-11-10.md` | 无 | 无 | 22 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/REVIEW-2026-11-10.md` | 无 | 无 | 40 | `~/.zcode/v2/provider_config.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/ROUTING-POLICY.md` | 无 | 无 | 241 | `~/.zcode/v2/model-alias-map.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/SECRETS.md` | 无 | 无 | 17 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/SECRETS.md` | 无 | 无 | 34 | `providers/qoder/qoder_zcode_sync.py` | `providers/qoder/qoder_sync.py` | MUST |
| `docs/SECRETS.md` | 无 | 无 | 34 | `qoder_probe_zcode.py` | `qoder_probe.py` | MUST |
| `docs/SECRETS.md` | 无 | 无 | 39 | `~/.zcode/v2/provider_config.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/SECRETS.md` | 无 | 无 | 41 | `providers/workbuddy/cache/wb_zcode_probe.json` | `providers/workbuddy/cache/wb_probe.json` | MUST |
| `docs/SECRETS.md` | 无 | 无 | 75 | `providers/workbuddy/workbuddy_probe_zcode.py` | `providers/workbuddy/workbuddy_probe.py` | MUST |
| `docs/SECRETS.md` | 无 | 无 | 75 | `providers/workbuddy/workbuddy_zcode_sync.py` | `providers/workbuddy/workbuddy_sync.py` | MUST |
| `docs/SECRETS.md` | 无 | 无 | 95 | `\.zcode\v2\provider_config.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/SECRETS.md` | 无 | 无 | 96 | `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` | `—（契约层/上游原样保留）` | KEEP |
| `docs/SECRETS.md` | 无 | 无 | 115 | `WB_ZCODE_PROBE_FILE` | `WB_PROBE_FILE（旧名 WB_ZCODE_PROBE_FILE fallback 读取）` | FALLBACK |
| `docs/SECRETS.md` | 无 | 无 | 117 | `providers/workbuddy/zcode_effective_body.js` | `providers/workbuddy/effective_body.js` | MUST |
| `docs/SECRETS.md` | 无 | 无 | 117 | `ZCODE_API_TYPE` | `MB_API_TYPE（旧名 ZCODE_API_TYPE fallback 读取）` | FALLBACK |
| `docs/SECRETS.md` | 无 | 无 | 117 | `ZCODE_BUILTIN` | `—（契约层/上游原样保留）` | KEEP |
| `docs/SECRETS.md` | 无 | 无 | 119 | `providers/qoder/qoder_probe_zcode.py` | `providers/qoder/qoder_probe.py` | MUST |
| `docs/SECRETS.md` | 无 | 无 | 122 | `providers/qwen/qwen_zcode_sync.py` | `providers/qwen/qwen_sync.py` | MUST |
| `docs/SECRETS.md` | 无 | 无 | 149 | `wb_zcode_probe.json` | `wb_probe.json` | MUST |
| `docs/SECRETS.md` | 无 | 无 | 150 | `wb_zcode_probe.log` | `wb_probe.log` | MUST |
| `docs/TOOLS.md` | 无 | 有 | 8 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/TOOLS.md` | 无 | 有 | 29 | `\ZCodeGateway\zgate.log` | `—（契约层/上游原样保留）` | KEEP |
| `docs/TOOLS.md` | 无 | 有 | 32 | `~/.zcode/v2/model-alias-map.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/TOOLS.md` | 无 | 有 | 33 | `~/.zcode/v2/arena-leaderboard.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/TOOLS.md` | 无 | 有 | 33 | `~/.zcode/v2/arena-main.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/TOOLS.md` | 无 | 有 | 34 | `~/.zcode/v2/model-sync-state.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/TOOLS.md` | 无 | 有 | 35 | `ZCODE_GATEWAY_KEY` | `—（契约层/上游原样保留）` | KEEP |
| `docs/TOOLS.md` | 无 | 有 | 35 | `zcode-` | `—（契约层/上游原样保留）` | KEEP |
| `docs/TOOLS.md` | 无 | 有 | 36 | `~/.zcode` | `—（契约层/上游原样保留）` | KEEP |
| `docs/TOOLS.md` | 无 | 有 | 38 | `~/.zcode/v2/model_probe.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/TOOLS.md` | 无 | 有 | 38 | `zcode_effective_body.js` | `—（契约层/上游原样保留）` | KEEP |
| `docs/TOOLS.md` | 无 | 有 | 42 | `providers/workbuddy/cache/wb_zcode_probe.json` | `providers/workbuddy/cache/wb_probe.json` | MUST |
| `docs/TOOLS.md` | 无 | 有 | 42 | `providers/workbuddy/workbuddy_probe_zcode.py` | `providers/workbuddy/workbuddy_probe.py` | MUST |
| `docs/TOOLS.md` | 无 | 有 | 42 | `workbuddy/logs/wb_zcode_probe.log` | `workbuddy/logs/wb_probe.log` | MUST |
| `docs/TOOLS.md` | 无 | 有 | 43 | `providers/workbuddy/workbuddy_zcode_sync.py` | `providers/workbuddy/workbuddy_sync.py` | MUST |
| `docs/TOOLS.md` | 无 | 有 | 44 | `probe_zcode.py` | `probe_host.py` | MUST |
| `docs/TOOLS.md` | 无 | 有 | 44 | `providers/workbuddy/zcode_effective_body.js` | `providers/workbuddy/effective_body.js` | MUST |
| `docs/TOOLS.md` | 无 | 有 | 48 | `providers/qoder/qoder_zcode_sync.py` | `providers/qoder/qoder_sync.py` | MUST |
| `docs/TOOLS.md` | 无 | 有 | 48 | `qoder_probe_zcode.py` | `qoder_probe.py` | MUST |
| `docs/TOOLS.md` | 无 | 有 | 49 | `providers/qoder/qoder_probe_zcode.py` | `providers/qoder/qoder_probe.py` | MUST |
| `docs/TOOLS.md` | 无 | 有 | 51 | `providers/qwen/qwen_zcode_sync.py` | `providers/qwen/qwen_sync.py` | MUST |
| `docs/TOOLS.md` | 无 | 有 | 52 | `qwen_zcode_sync.py` | `qwen_sync.py` | MUST |
| `docs/TOOLS.md` | 无 | 有 | 57 | `providers/opencode-go/probe/archive/validate_zcode_models.py` | `providers/opencode-go/probe/archive/validate_models.py` | MUST |
| `docs/TOOLS.md` | 无 | 有 | 58 | `workbuddy_probe_zcode.py` | `workbuddy_probe.py` | MUST |
| `docs/TOOLS.md` | 无 | 有 | 60 | `workbuddy_zcode_sync.py` | `workbuddy_sync.py` | MUST |
| `docs/TOOLS.md` | 无 | 有 | 61 | `qoder/qoder_zcode_sync.py` | `qoder/qoder_sync.py` | MUST |
| `docs/TOOLS.md` | 无 | 有 | 68 | `third-party/zcodium/reasoning-rules.js` | `—（契约层/上游原样保留）` | KEEP |
| `docs/TOOLS.md` | 无 | 有 | 69 | `third-party/zcodium/zcode-builtin-reasoning-rules.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/TOOLS.md` | 无 | 有 | 69 | `ZCodium` | `—（契约层/上游原样保留）` | KEEP |
| `docs/TOOLS.md` | 无 | 有 | 79 | `workbuddy/workbuddy_zcode_sync.py` | `workbuddy/workbuddy_sync.py` | MUST |
| `docs/TROUBLESHOOTING.md` | 无 | 有 | 12 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/TROUBLESHOOTING.md` | 无 | 有 | 32 | `~/.zcode/v2/provider_config.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/TROUBLESHOOTING.md` | 无 | 有 | 52 | `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` | `—（契约层/上游原样保留）` | KEEP |
| `docs/TROUBLESHOOTING.md` | 无 | 有 | 68 | `zcode_effective_body.js` | `—（契约层/上游原样保留）` | KEEP |
| `docs/TROUBLESHOOTING.md` | 无 | 有 | 109 | `providers/workbuddy/cache/wb_zcode_probe.json` | `providers/workbuddy/cache/wb_probe.json` | MUST |
| `docs/TROUBLESHOOTING.md` | 无 | 有 | 182 | `workbuddy_zcode_sync.py` | `workbuddy_sync.py` | MUST |
| `docs/TROUBLESHOOTING.md` | 无 | 有 | 293 | `workbuddy_probe_zcode.py` | `workbuddy_probe.py` | MUST |
| `docs/TROUBLESHOOTING.md` | 无 | 有 | 301 | `WB_ZCODE_PROBE_FILE` | `WB_PROBE_FILE（旧名 WB_ZCODE_PROBE_FILE fallback 读取）` | FALLBACK |
| `docs/TROUBLESHOOTING.md` | 无 | 有 | 320 | `.../ZCode/resources/config/provider/zcode-builtin.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/TROUBLESHOOTING.md` | 无 | 有 | 320 | `ZCODE_BUILTIN` | `—（契约层/上游原样保留）` | KEEP |
| `docs/TROUBLESHOOTING.md` | 无 | 有 | 339 | `ZCodeGateway` | `—（契约层/上游原样保留）` | KEEP |
| `docs/TROUBLESHOOTING.md` | 无 | 有 | 352 | `\ZCodeGateway\workbuddy.stderr.log` | `—（契约层/上游原样保留）` | KEEP |
| `docs/TROUBLESHOOTING.md` | 无 | 有 | 353 | `\ZCodeGateway\qoder.stderr.log` | `—（契约层/上游原样保留）` | KEEP |
| `docs/TROUBLESHOOTING.md` | 无 | 有 | 413 | `.zcode/v2/provider_config.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/TROUBLESHOOTING.md` | 无 | 有 | 445 | `providers/qoder/qoder_zcode_sync.py` | `providers/qoder/qoder_sync.py` | MUST |
| `docs/TROUBLESHOOTING.md` | 无 | 有 | 450 | `qoder_zcode_sync.py` | `qoder_sync.py` | MUST |
| `docs/TROUBLESHOOTING.md` | 无 | 有 | 467 | `~/.zcode/v2/model-alias-map.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/TROUBLESHOOTING.md` | 无 | 有 | 468 | `providers/workbuddy/zcode_effective_body.js` | `providers/workbuddy/effective_body.js` | MUST |
| `docs/TROUBLESHOOTING.md` | 无 | 有 | 602 | `<HOST_ABS_PATH>/ZCodeGateway/zgate.log` | `—（契约层/上游原样保留）` | KEEP |
| `docs/TROUBLESHOOTING.md` | 无 | 有 | 610 | `/ZCodeGateway/zgate.exe` | `—（契约层/上游原样保留）` | KEEP |
| `docs/UPSTREAM.md` | 无 | 有 | 5 | `../third-party/zcodium/` | `—（契约层/上游原样保留）` | KEEP |
| `docs/UPSTREAM.md` | 无 | 有 | 14 | `zcode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/UPSTREAM.md` | 无 | 有 | 15 | `ZCodium` | `—（契约层/上游原样保留）` | KEEP |
| `docs/UPSTREAM.md` | 无 | 有 | 16 | `ZCode-Agent-Kit` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/UPSTREAM.md` | 无 | 有 | 32 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/UPSTREAM.md` | 无 | 有 | 46 | `<HOST_ABS_PATH>/ZCode` | `—（契约层/上游原样保留）` | KEEP |
| `docs/UPSTREAM.md` | 无 | 有 | 46 | `zai-org/ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/UPSTREAM.md` | 无 | 有 | 47 | `<HOST_ABS_PATH>/zcode-api` | `—（契约层/上游原样保留）` | KEEP |
| `docs/UPSTREAM.md` | 无 | 有 | 47 | `TriDefender/zcode-api` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/UPSTREAM.md` | 无 | 有 | 48 | `<HOST_ABS_PATH>/zcode2api` | `—（契约层/上游原样保留）` | KEEP |
| `docs/UPSTREAM.md` | 无 | 有 | 48 | `liu5269/zcode2api` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/UPSTREAM.md` | 无 | 有 | 49 | `<HOST_ABS_PATH>/ZCodium-project/ZCodium` | `—（契约层/上游原样保留）` | KEEP |
| `docs/UPSTREAM.md` | 无 | 有 | 49 | `ZCodium-project/ZCodium` | `—（契约层/上游原样保留）` | KEEP |
| `docs/UPSTREAM.md` | 无 | 有 | 50 | `<HOST_ABS_PATH>/zcode-token-usage-statusbar` | `—（契约层/上游原样保留）` | KEEP |
| `docs/UPSTREAM.md` | 无 | 有 | 50 | `xhwxt/zcode-token-usage-statusbar` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/UPSTREAM.md` | 无 | 有 | 51 | `dengyie/zcode2api` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/UPSTREAM.md` | 无 | 有 | 51 | `<HOST_ABS_PATH>/zcode2api` | `—（契约层/上游原样保留）` | KEEP |
| `docs/UPSTREAM.md` | 无 | 有 | 52 | `Qoder/WorkBuddy/ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/UPSTREAM.md` | 无 | 有 | 53 | `<HOST_ABS_PATH>/ZCode-Agent-Kit` | `—（契约层/上游原样保留）` | KEEP |
| `docs/UPSTREAM.md` | 无 | 有 | 53 | `ZepiGit/ZCode-Agent-Kit` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/UPSTREAM.md` | 无 | 有 | 57 | `zcode-agent-kit` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/UPSTREAM.md` | 无 | 有 | 80 | `~/.zcode/cli/config.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/UPSTREAM.md` | 无 | 有 | 80 | `~/.zcode/v2/config.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/UPSTREAM.md` | 无 | 有 | 81 | `~/.zcode/v2/provider_config.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/UPSTREAM.md` | 无 | 有 | 84 | `workbuddy_probe_zcode.py` | `workbuddy_probe.py` | MUST |
| `docs/UPSTREAM.md` | 无 | 有 | 115 | `workbuddy_zcode_sync.py` | `workbuddy_sync.py` | MUST |
| `docs/UPSTREAM.md` | 无 | 有 | 239 | `providers/workbuddy/zcode_effective_body.js` | `providers/workbuddy/effective_body.js` | MUST |
| `docs/UPSTREAM.md` | 无 | 有 | 241 | `config/provider/zcode-builtin.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/UPSTREAM.md` | 无 | 有 | 324 | `../third-party/zcodium/reasoning-rules.js` | `—（契约层/上游原样保留）` | KEEP |
| `docs/UPSTREAM.md` | 无 | 有 | 328 | `third-party/zcodium/reasoning-rules.js` | `—（契约层/上游原样保留）` | KEEP |
| `docs/UPSTREAM.md` | 无 | 有 | 355 | `../third-party/zcodium/zcode-builtin-reasoning-rules.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/UPSTREAM.md` | 无 | 有 | 364 | `ZCODE_BUILTIN` | `—（契约层/上游原样保留）` | KEEP |
| `docs/UPSTREAM.md` | 无 | 有 | 365 | `/path/to/zcode-builtin.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/UPSTREAM.md` | 无 | 有 | 390 | `zcode-token-usage-statusbar` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/UPSTREAM.md` | 无 | 有 | 392 | `zcode-api` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/UPSTREAM.md` | 无 | 有 | 393 | `zcode2api` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `docs/UPSTREAM.md` | 无 | 有 | 397 | `third-party/zcodium/zcode-builtin-reasoning-rules.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/UPSTREAM.md` | 无 | 有 | 400 | `third-party/zcode/` | `—（契约层/上游原样保留）` | KEEP |
| `docs/UPSTREAM.md` | 无 | 有 | 400 | `zcode-builtin.json` | `—（契约层/上游原样保留）` | KEEP |
| `docs/ZGATE-LIFECYCLE.md` | 无 | 无 | 84 | `\ZCodeGateway` | `—（契约层/上游原样保留）` | KEEP |
| `docs/ZGATE-LIFECYCLE.md` | 无 | 无 | 299 | `\ZCodeGateway\zgate.log` | `—（契约层/上游原样保留）` | KEEP |
| `evidence/gemini-merge-result.md` | 无 | 无 | 42 | `zcode-main` | `—（契约层/上游原样保留）` | KEEP |
| `evidence/PROGRESS.workbuddy.md` | 无 | 无 | 1 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `evidence/PROGRESS.workbuddy.md` | 无 | 无 | 64 | `resources/config/provider/zcode-builtin.json` | `—（契约层/上游原样保留）` | KEEP |
| `evidence/PROGRESS.workbuddy.md` | 无 | 无 | 73 | `scripts/zcode_effective_body.js` | `scripts/effective_body.js` | MUST |
| `evidence/PROGRESS.workbuddy.md` | 无 | 无 | 81 | `scripts/workbuddy_probe_zcode.py` | `scripts/workbuddy_probe.py` | MUST |
| `evidence/PROGRESS.workbuddy.md` | 无 | 无 | 82 | `scripts/wb_zcode_probe.json` | `scripts/wb_probe.json` | MUST |
| `evidence/PROGRESS.workbuddy.md` | 无 | 无 | 84 | `scripts/workbuddy_zcode_sync.py` | `scripts/workbuddy_sync.py` | MUST |
| `evidence/PROGRESS.workbuddy.md` | 无 | 无 | 85 | `zcode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `evidence/PROGRESS.workbuddy.md` | 无 | 无 | 86 | `wb_zcode_probe.json` | `wb_probe.json` | MUST |
| `evidence/PROGRESS.workbuddy.md` | 无 | 无 | 94 | `zcode_effective_body.js` | `—（契约层/上游原样保留）` | KEEP |
| `evidence/PROGRESS.workbuddy.md` | 无 | 无 | 95 | `workbuddy_probe_zcode.py` | `workbuddy_probe.py` | MUST |
| `evidence/PROGRESS.workbuddy.md` | 无 | 无 | 97 | `workbuddy_zcode_sync.py` | `workbuddy_sync.py` | MUST |
| `gateways/legacy-router/protocol_bridge.js` | 无 | 无 | 5 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `gateways/legacy-router/unified-router.js` | 无 | 有 | 5 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `gateways/legacy-router/unified-router.js` | 无 | 有 | 64 | `process.env.ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` | `process.env.MB_PERSONAL_PROVIDER_CONFIG_FILE` | MUST |
| `gateways/legacy-router/unified-router.js` | 无 | 有 | 65 | `.zcode` | `—（契约层/上游原样保留）` | KEEP |
| `gateways/zgate/internal/alias/alias.go` | 无 | 无 | 1 | `~/.zcode/v2/model-alias-map.json` | `—（契约层/上游原样保留）` | KEEP |
| `gateways/zgate/internal/alias/alias.go` | 无 | 无 | 4 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `gateways/zgate/internal/bridge/bridge.go` | 无 | 无 | 586 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `gateways/zgate/internal/config/config.go` | 无 | 无 | 251 | `~/.zcode/v2/model-alias-map.json` | `—（契约层/上游原样保留）` | KEEP |
| `gateways/zgate/internal/config/config.go` | 无 | 无 | 257 | `~/.zcode/v2/provider_config.json` | `—（契约层/上游原样保留）` | KEEP |
| `gateways/zgate/internal/config/config.go` | 无 | 无 | 259 | `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` | `—（契约层/上游原样保留）` | KEEP |
| `gateways/zgate/internal/config/config.go` | 无 | 无 | 332 | `ZCodeGateway` | `—（契约层/上游原样保留）` | KEEP |
| `gateways/zgate/internal/router/router.go` | 无 | 无 | 5 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `gateways/zgate/main.go` | 无 | 无 | 1 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `gateways/zgate/smoke_test.py` | 无 | 有 | 22 | `.zcode` | `—（契约层/上游原样保留）` | KEEP |
| `gateways/zgate/zgate.json` | 无 | 无 | 3 | `~/.zcode/v2/model-alias-map.json` | `—（契约层/上游原样保留）` | KEEP |
| `gateways/zgate/zgate.json` | 无 | 无 | 4 | `~/.zcode/v2/provider_config.json` | `—（契约层/上游原样保留）` | KEEP |
| `gateways/zgate/zgate.json` | 无 | 无 | 73 | `/ZCodeGateway` | `—（契约层/上游原样保留）` | KEEP |
| `providers/opencode-go/ops/go_model_sync.py` | 无 | 无 | 10 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `providers/opencode-go/ops/go_model_sync.py` | 无 | 无 | 57 | `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` | `—（契约层/上游原样保留）` | KEEP |
| `providers/opencode-go/ops/go_model_sync.py` | 无 | 无 | 59 | `.zcode` | `—（契约层/上游原样保留）` | KEEP |
| `providers/opencode-go/probe/archive/validate_zcode_models.py` | 无 | 无 | 2 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `providers/opencode-go/probe/archive/validate_zcode_models.py` | 无 | 无 | 6 | `.zcode` | `—（契约层/上游原样保留）` | KEEP |
| `providers/opencode-go/probe/archive/validate_zcode_models.py` | 无 | 无 | 16 | `zcode-validate/1.0` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `providers/opencode-go/probe/bench_clean.py` | 无 | 无 | 49 | `zcode-bench/1.0` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `providers/opencode-go/probe/bench_models.py` | 无 | 无 | 69 | `zcode-bench/1.0` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `providers/opencode-go/probe/probe_models.py` | 无 | 无 | 43 | `zcode-probe/1.0` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `providers/opencode-go/probe/probe_protocols.py` | 无 | 无 | 44 | `zcode-probe/1.0` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `providers/qoder/qoder_probe.py` | 无 | 无 | 2 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `providers/qoder/qoder_probe.py` | 无 | 无 | 10 | `ZCode-native` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `providers/qoder/qoder_sync.py` | 无 | 有 | 2 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `providers/qoder/qoder_sync.py` | 无 | 有 | 116 | `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` | `—（契约层/上游原样保留）` | KEEP |
| `providers/qoder/qoder_sync.py` | 无 | 有 | 119 | `.zcode` | `—（契约层/上游原样保留）` | KEEP |
| `providers/qwen/qwen_sync.py` | 无 | 有 | 2 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `providers/qwen/qwen_sync.py` | 无 | 有 | 37 | `~/.zcode/v2/model_probe.json` | `—（契约层/上游原样保留）` | KEEP |
| `providers/qwen/qwen_sync.py` | 无 | 有 | 113 | `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` | `—（契约层/上游原样保留）` | KEEP |
| `providers/qwen/qwen_sync.py` | 无 | 有 | 116 | `.zcode` | `—（契约层/上游原样保留）` | KEEP |
| `providers/workbuddy/effective_body.js` | 无 | 无 | 3 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `providers/workbuddy/effective_body.js` | 无 | 无 | 4 | `zcode-builtin.json.` | `—（契约层/上游原样保留）` | KEEP |
| `providers/workbuddy/effective_body.js` | 无 | 无 | 8 | `zai-org/ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `providers/workbuddy/effective_body.js` | 无 | 无 | 9 | `third-party/zcode/.upstream-sha` | `—（契约层/上游原样保留）` | KEEP |
| `providers/workbuddy/effective_body.js` | 无 | 无 | 10 | `third-party/zcode/` | `—（契约层/上游原样保留）` | KEEP |
| `providers/workbuddy/effective_body.js` | 无 | 无 | 12 | `parseZCodeBuiltinModelConfigRules` | `—（契约层/上游原样保留）` | KEEP |
| `providers/workbuddy/effective_body.js` | 无 | 无 | 14 | `config/provider/zcode-builtin.json` | `—（契约层/上游原样保留）` | KEEP |
| `providers/workbuddy/effective_body.js` | 无 | 无 | 43 | `ZCODE_BUILTIN` | `—（契约层/上游原样保留）` | KEEP |
| `providers/workbuddy/effective_body.js` | 无 | 无 | 43 | `zcode-builtin.json` | `—（契约层/上游原样保留）` | KEEP |
| `providers/workbuddy/effective_body.js` | 无 | 无 | 44 | `ZCODE_API_TYPE` | `MB_API_TYPE（旧名 ZCODE_API_TYPE fallback 读取）` | FALLBACK |
| `providers/workbuddy/effective_body.js` | 无 | 无 | 45 | `ZCODE_BASE_URL` | `MB_BASE_URL（旧名 ZCODE_BASE_URL fallback 读取）` | FALLBACK |
| `providers/workbuddy/effective_body.js` | 无 | 无 | 57 | `process.env.ZCODE_BUILTIN` | `process.env.MB_BUILTIN` | MUST |
| `providers/workbuddy/effective_body.js` | 无 | 无 | 62 | `zcode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `providers/workbuddy/effective_body.js` | 无 | 无 | 63 | `third-party/zcode` | `—（契约层/上游原样保留）` | KEEP |
| `providers/workbuddy/effective_body.js` | 无 | 无 | 65 | `/zcode-builtin.json` | `—（契约层/上游原样保留）` | KEEP |
| `providers/workbuddy/effective_body.js` | 无 | 无 | 65 | `~/.zcode/v2/runtime/provider/` | `—（契约层/上游原样保留）` | KEEP |
| `providers/workbuddy/effective_body.js` | 无 | 无 | 66 | `.zcode` | `—（契约层/上游原样保留）` | KEEP |
| `providers/workbuddy/effective_body.js` | 无 | 无 | 181 | `process.env.ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` | `process.env.MB_PERSONAL_PROVIDER_CONFIG_FILE` | MUST |
| `providers/workbuddy/effective_body.js` | 无 | 无 | 231 | `process.env.ZCODE_API_TYPE` | `process.env.MB_API_TYPE` | MUST |
| `providers/workbuddy/effective_body.js` | 无 | 无 | 232 | `process.env.ZCODE_BASE_URL` | `process.env.MB_BASE_URL` | MUST |
| `providers/workbuddy/effective_body.js` | 无 | 无 | 237 | `process.env.ZCODE_MAX_OUTPUT_TOKENS` | `process.env.MB_MAX_OUTPUT_TOKENS` | MUST |
| `providers/workbuddy/workbuddy_probe.py` | 无 | 无 | 2 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `providers/workbuddy/workbuddy_probe.py` | 无 | 无 | 14 | `zcode-builtin.json` | `—（契约层/上游原样保留）` | KEEP |
| `providers/workbuddy/workbuddy_probe.py` | 无 | 无 | 36 | `ZCode-native` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `providers/workbuddy/workbuddy_probe.py` | 无 | 无 | 68 | `WB_ZCODE_PROBE_FILE` | `WB_PROBE_FILE（旧名 WB_ZCODE_PROBE_FILE fallback 读取）` | FALLBACK |
| `providers/workbuddy/workbuddy_probe.py` | 无 | 无 | 68 | `wb_zcode_probe.json` | `wb_probe.json` | MUST |
| `providers/workbuddy/workbuddy_probe.py` | 无 | 无 | 110 | `zcode_body` | `—（契约层/上游原样保留）` | KEEP |
| `providers/workbuddy/workbuddy_probe.py` | 无 | 无 | 267 | `zcode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `providers/workbuddy/workbuddy_sync.py` | 无 | 无 | 2 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `providers/workbuddy/workbuddy_sync.py` | 无 | 无 | 11 | `ZCode-side` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `providers/workbuddy/workbuddy_sync.py` | 无 | 无 | 145 | `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` | `—（契约层/上游原样保留）` | KEEP |
| `providers/workbuddy/workbuddy_sync.py` | 无 | 无 | 146 | `.zcode` | `—（契约层/上游原样保留）` | KEEP |
| `providers/workbuddy/workbuddy_sync.py` | 无 | 无 | 152 | `WB_ZCODE_PROBE_FILE` | `WB_PROBE_FILE（旧名 WB_ZCODE_PROBE_FILE fallback 读取）` | FALLBACK |
| `providers/workbuddy/workbuddy_sync.py` | 无 | 无 | 152 | `wb_zcode_probe.json` | `wb_probe.json` | MUST |
| `README.md` | 无 | 有 | 27 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `README.md` | 无 | 有 | 44 | `~/.zcode/v2/provider_config.json` | `—（契约层/上游原样保留）` | KEEP |
| `README.md` | 无 | 有 | 46 | `~/.zcode/v2/` | `—（契约层/上游原样保留）` | KEEP |
| `README.md` | 无 | 有 | 65 | `~/.zcode/v2/model_probe.json` | `—（契约层/上游原样保留）` | KEEP |
| `README.md` | 无 | 有 | 121 | `<HOST_ABS_PATH>/ZCode` | `—（契约层/上游原样保留）` | KEEP |
| `README.md` | 无 | 有 | 122 | `<HOST_ABS_PATH>/ZCodium-project/ZCodium` | `—（契约层/上游原样保留）` | KEEP |
| `README.md` | 无 | 有 | 122 | `ZCodium` | `—（契约层/上游原样保留）` | KEEP |
| `sync-models.ps1` | 有 | 无 | 291 | `.zcode\v2\model_probe.json` | `—（契约层/上游原样保留）` | KEEP |
| `tests/test_dsh_sync_efforts.py` | 无 | 无 | 7 | `zcode-` | `—（契约层/上游原样保留）` | KEEP |
| `tests/test_dsh_sync_efforts.py` | 无 | 无 | 72 | `zcode-free:` | `—（契约层/上游原样保留）` | KEEP |
| `tests/test_dsh_sync_efforts.py` | 无 | 无 | 100 | `zcode-free` | `—（契约层/上游原样保留）` | KEEP |
| `tests/test_dsh_sync_efforts.py` | 无 | 无 | 127 | `test_non_zcode_provider_still_preserved` | `test_non_provider_still_preserved` | MUST |
| `tests/test_dsh_sync_efforts.py` | 无 | 无 | 137 | `zcode-main` | `—（契约层/上游原样保留）` | KEEP |
| `tests/test_dsh_sync_retry_policy.py` | 无 | 无 | 2 | `zcode-` | `—（契约层/上游原样保留）` | KEEP |
| `tests/test_dsh_sync_retry_policy.py` | 无 | 无 | 39 | `zcode-free` | `—（契约层/上游原样保留）` | KEEP |
| `tests/test_dsh_sync_retry_policy.py` | 无 | 无 | 39 | `zcode-main` | `—（契约层/上游原样保留）` | KEEP |
| `tests/test_dsh_sync_retry_policy.py` | 无 | 无 | 39 | `zcode-saver` | `—（契约层/上游原样保留）` | KEEP |
| `tests/test_dsh_sync_retry_policy.py` | 无 | 无 | 95 | `zcode-main:` | `—（契约层/上游原样保留）` | KEEP |
| `tests/test_dsh_sync_retry_policy.py` | 无 | 无 | 101 | `zcode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `tests/test_dsh_sync_retry_policy.py` | 无 | 无 | 109 | `ZCODE_GATEWAY_KEY:` | `—（契约层/上游原样保留）` | KEEP |
| `tests/test_dsh_sync_retry_policy.py` | 无 | 无 | 203 | `test_every_zcode_provider_has_full_policy` | `test_every_provider_has_full_policy` | MUST |
| `tests/test_dsh_sync_retry_policy.py` | 无 | 无 | 206 | `zcode.items` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `tests/test_model_alias_hop_order.py` | 无 | 无 | 27 | `~/.zcode/v2/model-alias-map.json` | `—（契约层/上游原样保留）` | KEEP |
| `tests/test_model_alias_probe_filter.py` | 无 | 无 | 9 | `zcode-main` | `—（契约层/上游原样保留）` | KEEP |
| `tests/test_model_alias_qd_free.py` | 无 | 无 | 35 | `~/.zcode/v2/model-alias-map.json` | `—（契约层/上游原样保留）` | KEEP |
| `tests/test_model_caps.py` | 无 | 无 | 13 | `~/.zcode` | `—（契约层/上游原样保留）` | KEEP |
| `tests/test_model_caps.py` | 无 | 无 | 98 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `tests/test_model_caps.py` | 无 | 无 | 377 | `.zcode` | `—（契约层/上游原样保留）` | KEEP |
| `third-party/README.md` | 无 | 无 | 12 | `<HOST_ABS_PATH>/ZCode` | `—（契约层/上游原样保留）` | KEEP |
| `third-party/README.md` | 无 | 无 | 12 | `workbuddy/zcode_effective_body.js` | `workbuddy/effective_body.js` | MUST |
| `third-party/README.md` | 无 | 无 | 12 | `zai-org/ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `third-party/README.md` | 无 | 无 | 12 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `third-party/README.md` | 无 | 无 | 12 | `zcode-builtin.json` | `—（契约层/上游原样保留）` | KEEP |
| `third-party/README.md` | 无 | 无 | 12 | `zcode/` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `third-party/README.md` | 无 | 无 | 12 | `zcode/UPSTREAM.md` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `third-party/README.md` | 无 | 无 | 13 | `<HOST_ABS_PATH>/ZCodium-project/ZCodium` | `—（契约层/上游原样保留）` | KEEP |
| `third-party/README.md` | 无 | 无 | 13 | `ZCodium` | `—（契约层/上游原样保留）` | KEEP |
| `third-party/README.md` | 无 | 无 | 13 | `ZCodium-project/ZCodium` | `—（契约层/上游原样保留）` | KEEP |
| `third-party/README.md` | 无 | 无 | 13 | `zcodium/` | `—（契约层/上游原样保留）` | KEEP |
| `third-party/README.md` | 无 | 无 | 13 | `zcodium/UPSTREAM.md` | `—（契约层/上游原样保留）` | KEEP |
| `tools/agent_profiles.py` | 无 | 无 | 13 | `~/.zcode/v2/provider_config.json` | `—（契约层/上游原样保留）` | KEEP |
| `tools/agent_profiles.py` | 无 | 无 | 14 | `ZCODE_BUILTIN` | `—（契约层/上游原样保留）` | KEEP |
| `tools/agent_profiles.py` | 无 | 无 | 14 | `ZCODE_GATEWAY_KEY` | `—（契约层/上游原样保留）` | KEEP |
| `tools/agent_profiles.py` | 无 | 无 | 14 | `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` | `—（契约层/上游原样保留）` | KEEP |
| `tools/agent_profiles.py` | 无 | 无 | 15 | `zcode-free` | `—（契约层/上游原样保留）` | KEEP |
| `tools/agent_profiles.py` | 无 | 无 | 15 | `zcode-main` | `—（契约层/上游原样保留）` | KEEP |
| `tools/agent_profiles.py` | 无 | 无 | 15 | `zcode-saver` | `—（契约层/上游原样保留）` | KEEP |
| `tools/arena_leaderboard.py` | 无 | 无 | 4 | `~/.zcode/v2/` | `—（契约层/上游原样保留）` | KEEP |
| `tools/arena_leaderboard.py` | 无 | 无 | 21 | `~/.zcode/v2/arena-main.json` | `—（契约层/上游原样保留）` | KEEP |
| `tools/arena_leaderboard.py` | 无 | 无 | 57 | `.zcode` | `—（契约层/上游原样保留）` | KEEP |
| `tools/caps_upstream.py` | 无 | 无 | 36 | `~/.zcode/v2/model-alias-map.json` | `—（契约层/上游原样保留）` | KEEP |
| `tools/caps_upstream.py` | 无 | 无 | 39 | `~/.zcode/v2/provider_config.json` | `—（契约层/上游原样保留）` | KEEP |
| `tools/dsh_sync.py` | 无 | 无 | 2 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `tools/dsh_sync.py` | 无 | 无 | 4 | `~/.zcode/v2/provider_config.json` | `—（契约层/上游原样保留）` | KEEP |
| `tools/dsh_sync.py` | 无 | 无 | 8 | `zcode-main` | `—（契约层/上游原样保留）` | KEEP |
| `tools/dsh_sync.py` | 无 | 无 | 9 | `zcode-free` | `—（契约层/上游原样保留）` | KEEP |
| `tools/dsh_sync.py` | 无 | 无 | 9 | `zcode-saver` | `—（契约层/上游原样保留）` | KEEP |
| `tools/dsh_sync.py` | 无 | 无 | 15 | `zcode-` | `—（契约层/上游原样保留）` | KEEP |
| `tools/dsh_sync.py` | 无 | 无 | 21 | `ZCODE_GATEWAY_KEY` | `—（契约层/上游原样保留）` | KEEP |
| `tools/dsh_sync.py` | 无 | 无 | 61 | `ZCODE_CONFIG` | `—（契约层/上游原样保留）` | KEEP |
| `tools/dsh_sync.py` | 无 | 无 | 63 | `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` | `—（契约层/上游原样保留）` | KEEP |
| `tools/dsh_sync.py` | 无 | 无 | 64 | `.zcode` | `—（契约层/上游原样保留）` | KEEP |
| `tools/dsh_sync.py` | 无 | 无 | 73 | `zcode-model-ledger.json` | `—（契约层/上游原样保留）` | KEEP |
| `tools/dsh_sync.py` | 无 | 无 | 152 | `_zcode_providers` | `_host_providers` | MUST |
| `tools/dsh_sync.py` | 无 | 无 | 518 | `refs.ZCODE_GATEWAY_KEY` | `refs.MB_GATEWAY_KEY` | MUST |
| `tools/dsh_sync.py` | 无 | 无 | 525 | `ZCODE_GATEWAY_KEY:\s` | `—（契约层/上游原样保留）` | KEEP |
| `tools/dsh_sync.py` | 无 | 无 | 527 | `ZCODE_GATEWAY_KEY:` | `—（契约层/上游原样保留）` | KEEP |
| `tools/make_social_preview.py` | 无 | 无 | 45 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `tools/model_alias.py` | 无 | 无 | 2 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `tools/model_alias.py` | 无 | 无 | 33 | `~/.zcode/v2/arena-main.json` | `—（契约层/上游原样保留）` | KEEP |
| `tools/model_alias.py` | 无 | 无 | 73 | `.zcode` | `—（契约层/上游原样保留）` | KEEP |
| `tools/model_alias.py` | 无 | 无 | 471 | `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` | `—（契约层/上游原样保留）` | KEEP |
| `tools/model_alias.py` | 无 | 无 | 2080 | `zcode-main` | `—（契约层/上游原样保留）` | KEEP |
| `tools/model_alias.py` | 无 | 无 | 2145 | `~/.zcode/v2/model-scores.json` | `—（契约层/上游原样保留）` | KEEP |
| `tools/model_caps.py` | 无 | 无 | 7 | `~/.zcode/v2/` | `—（契约层/上游原样保留）` | KEEP |
| `tools/model_caps.py` | 无 | 无 | 7 | `third-party/zcode/` | `—（契约层/上游原样保留）` | KEEP |
| `tools/model_caps.py` | 无 | 无 | 22 | `third-party/zcode/model-config.ts` | `—（契约层/上游原样保留）` | KEEP |
| `tools/model_caps.py` | 无 | 无 | 55 | `~/.zcode` | `—（契约层/上游原样保留）` | KEEP |
| `tools/model_caps.py` | 无 | 无 | 100 | `~/.zcode/v2/model-alias-map.json` | `—（契约层/上游原样保留）` | KEEP |
| `tools/model_caps.py` | 无 | 无 | 101 | `third-party/zcode/zcode-builtin.json` | `—（契约层/上游原样保留）` | KEEP |
| `tools/model_caps.py` | 无 | 无 | 102 | `~/.zcode/v2/provider_config.json` | `—（契约层/上游原样保留）` | KEEP |
| `tools/model_caps.py` | 无 | 无 | 116 | `zcode-builtin.json` | `—（契约层/上游原样保留）` | KEEP |
| `tools/model_caps.py` | 无 | 无 | 783 | `.zcode` | `—（契约层/上游原样保留）` | KEEP |
| `tools/model_caps.py` | 无 | 无 | 788 | `~/.zcode/v2` | `—（契约层/上游原样保留）` | KEEP |
| `tools/model_probe.py` | 无 | 有 | 2 | `ZCode` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `tools/model_probe.py` | 无 | 有 | 29 | `~/.zcode/v2/model_probe.json` | `—（契约层/上游原样保留）` | KEEP |
| `tools/model_probe.py` | 无 | 有 | 46 | `.zcode` | `—（契约层/上游原样保留）` | KEEP |
| `tools/model_probe.py` | 无 | 有 | 55 | `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` | `—（契约层/上游原样保留）` | KEEP |
| `tools/model_score.py` | 无 | 无 | 5 | `~/.zcode/v2/` | `—（契约层/上游原样保留）` | KEEP |
| `tools/model_score.py` | 无 | 无 | 10 | `~/.zcode/v2/model-scores.json` | `—（契约层/上游原样保留）` | KEEP |
| `tools/model_score.py` | 无 | 无 | 57 | `.zcode` | `—（契约层/上游原样保留）` | KEEP |
| `tools/model_stream_check.py` | 无 | 无 | 140 | `zcode-` | `—（契约层/上游原样保留）` | KEEP |
| `tools/rename-to-modelbus.ps1` | 无 | 无 | 2 | `ZcodeAIModels` | `—（契约层/上游原样保留）` | KEEP |
| `tools/rename-to-modelbus.ps1` | 无 | 无 | 24 | `F:\Project\ZcodeAIModels` | `—（契约层/上游原样保留）` | KEEP |
| `tools/rename-to-modelbus.ps1` | 无 | 无 | 29 | `ZCodeGateway` | `—（契约层/上游原样保留）` | KEEP |
| `tools/rename-to-modelbus.ps1` | 无 | 无 | 132 | `F:\\Project\\ZcodeAIModels` | `—（契约层/上游原样保留）` | KEEP |
| `tools/rename-to-modelbus.ps1` | 无 | 无 | 168 | `.zcode\v2\setting.json` | `—（契约层/上游原样保留）` | KEEP |
| `tools/rename-to-modelbus.ps1` | 无 | 无 | 168 | `ZcodeSetting` | `按上下文改写：DSH 主宿主 / 各类 agent / 兼容投影` | TEXT |
| `tools/sync_report.py` | 无 | 无 | 5 | `~/.zcode/v2/` | `—（契约层/上游原样保留）` | KEEP |
| `tools/sync_report.py` | 无 | 无 | 13 | `~/.zcode/v2/model-sync-state.json` | `—（契约层/上游原样保留）` | KEEP |
| `tools/sync_report.py` | 无 | 无 | 37 | `.zcode` | `—（契约层/上游原样保留）` | KEEP |
| `tools/sync_report.py` | 无 | 无 | 51 | `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` | `—（契约层/上游原样保留）` | KEEP |
| `tools/zgate-lifecycle/current-models.ps1` | 有 | 无 | 46 | `.zcode\v2\model-alias-map.json` | `—（契约层/上游原样保留）` | KEEP |
| `tools/zgate-lifecycle/current-models.ps1` | 有 | 无 | 136 | `.zcode\v2\model_probe.json` | `—（契约层/上游原样保留）` | KEEP |
| `tools/zgate-lifecycle/deploy-zgate.ps1` | 有 | 无 | 51 | `ZCodeGateway` | `—（契约层/上游原样保留）` | KEEP |
| `tools/zgate-lifecycle/install-lifecycle.ps1` | 有 | 无 | 4 | `\ZCodeGateway` | `—（契约层/上游原样保留）` | KEEP |
| `tools/zgate-lifecycle/install-lifecycle.ps1` | 有 | 无 | 28 | `ZCodeGateway` | `—（契约层/上游原样保留）` | KEEP |

### 4.3 CRLF / BOM / 编码注意事项

- 命中文件带 **UTF-8 BOM**：`sync-models.ps1`、`tools/zgate-lifecycle/current-models.ps1`、`tools/zgate-lifecycle/deploy-zgate.ps1`、`tools/zgate-lifecycle/install-lifecycle.ps1`。改 `.ps1` 时按字节保留 BOM，或整份重存为 UTF-8 with BOM；`~/.dsh/AGENTS.md` §9 明确 PS5.1 按 GBK 读无 BOM UTF-8。
- 命中文本中 **含 CRLF 的共 54 个**（作业起点取样）；纯 CRLF 代表：`gateways/upstream/workbuddy/internal/server/handler.go`(2673/0)、`gateways/upstream/qoder/CHANGELOG.md`(1434/0)、`gateways/zgate/main.go.bak-20261109-dup`(998/0)、`docs/MODEL-PROVIDERS.md`(893/0)、`docs/TROUBLESHOOTING.md`(706/0)、`gateways/legacy-router/unified-router.js`(536/0)、`providers/qwen/qwen_zcode_sync.py`(505/0)。括号为 CRLF 数 / 独立 LF 数。
- `AGENTS.md` §9：shell 脚本必须 LF；改 `.sh` / `.cmd` 时保持 LF，混用换行会造成门禁与运行差异。
- 用 `edit` 做精确匹配前，CRLF 文件按 `dsh-edit-tool-exact-match` 读卡 `~/.dsh/procedures/工具-edit-CRLF精确改行失败.md`；`old_string` 命中多处时用更长上下文或按行号定位。
- 批量替换按字节保留原 BOM 与换行风格；整仓统一换行属额外变更，本方案予以排除。
- `.exe` / `.pyc` / `.db` 与 `*.bak-*` 跳过：`.exe` 重新编译、`.pyc` 由 Python 重建、`.db` 由索引工具重建、备份随源文件同步另存。

```powershell
$root = 'F:\Project\ModelBus'
$map = @{
  'WB_ZCODE_PROBE_FILE' = 'WB_PROBE_FILE'
  'ZCODE_API_TYPE' = 'MB_API_TYPE'; 'ZCODE_BASE_URL' = 'MB_BASE_URL'
  'ZCODE_MAX_OUTPUT_TOKENS' = 'MB_MAX_OUTPUT_TOKENS'
}
# 白名单：仅 §4.2 中策略为 MUST / FALLBACK 的活跃文件；KEEP / A / A2 / B / F1 / F6 一律排除
$allow = @('tools\dsh_sync.py', 'providers\workbuddy\effective_body.js', 'sync-models.ps1')
foreach ($rel in $allow) {
  $p = Join-Path $root $rel
  if (-not (Test-Path -LiteralPath $p)) { Write-Host "SKIP $rel"; continue }
  $bytes = [IO.File]::ReadAllBytes($p)
  $bom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
  $text = [Text.Encoding]::UTF8.GetString($bytes)
  $new = $text
  foreach ($k in $map.Keys) { $new = $new.Replace($k, $map[$k]) }
  if ($new -eq $text) { Write-Host "NOOP $rel"; continue }
  $enc = New-Object Text.UTF8Encoding($bom)
  [IO.File]::WriteAllText($p, $new, $enc)
  Write-Host "PATCHED $rel BOM=$bom"
}
```

说明：上面是**骨架**，`$allow` 需按 §4.2 全量补齐；`FALLBACK` 条目必须同步改代码读取逻辑（新名 → 旧名 fallback → 默认值），`KEEP` 条目从 `$map` 中排除。契约层 4 个 `ZCODE_*` env 不在 `$map` 内。

### 4.4 验收命令

```text
python -B -m unittest discover -s tests -q
python -B tools/check-project.py
python -B tools/check-docs.py
python -B tools/dsh_sync.py --check
python -B tools/model_caps.py --check
```

前四条 exit 0；第五条在批 1 落地后 exit 0（`docs/DSH-FIRST.md:140`）。再跑 §1.10 复核命令，确认 A / A2 / B occ 不变、D / E / F7 occ 下降、契约层 `zcode-*` / `ZCODE_*` 命中数不变、4 个旧 env 名仍可 fallback 读取。

## 5 口径裁决、快照说明与未采纳备选

### 5.1 主代理拍板：选 A（唯一执行口径）

主代理 15:54 裁决原文结论：**选 A —— 契约层保持原样，新增 `DSH_*` 同名 env 的方案列为未采纳备选**。理由：`ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` / `ZCODE_BUILTIN` / `ZCODE_GATEWAY_KEY` / `~/.zcode/v2/provider_config.json` / `zcode-main|free|saver` / `zcode-model-ledger.json` / `%LOCALAPPDATA%\ZCodeGateway\` / schema 键 / NOTICE 商标 / third-party 原件，都是第三方 ZCode 客户端与 DSH 宿主实际读取的真实契约；再造一套 `DSH_PERSONAL_PROVIDER_CONFIG_FILE` 优先会产生双写与静默漂移，且 DSH 侧 `cordis.patch.yml` 的 route id 与 refs 键已经绑定 `zcode-*` 命名。

| 分层 | 执行内容 | 落地方 |
|---|---|---|
| ① 契约层 | 上列全部保持原样，零新增同名替代 | 主代理口径，本分片 §3.4 KEEP |
| ② 实现层自造 env | `WB_ZCODE_PROBE_FILE` / `ZCODE_API_TYPE` / `ZCODE_BASE_URL` / `ZCODE_MAX_OUTPUT_TOKENS` → `WB_PROBE_FILE` / `MB_API_TYPE` / `MB_BASE_URL` / `MB_MAX_OUTPUT_TOKENS`，旧名保留 fallback 读取别名 | 第 6 路子代理 `a427cdfe` |
| ③ 第一方叙述性 ZCode | docstring / 横幅 / 注释 / User-Agent / 文档主语改「DSH 主宿主 + 各类 agent」 | 主代理并行分片 |
| ④ vendored 上游署名 + 历史记录 | `CHANGELOG.md` / `PROGRESS.md` / `evidence/agent-*` / `docs/archive` / `docs/release-notes` / `third-party/zcode*` 保持原样 | 全分片共同遵守 |

本报告 §3 / §4 已按 ①②③④ 重定稿；`AGENTS.md:6`、`docs/DSH-FIRST.md:23,31,32,35,85` 列为 E 类同步改写项，由主代理验收后对齐完成态。

### 5.2 取样时刻与进行中快照

- 报告主数 = 快照 **D**（2026-11-11 15:59:35 (+08:00) 按 §1.10 复核命令重跑）；快照 **A**（8794 occ / 1179 files / 264 命中文件，pwsh 8830，差 36 来自 6 个 PE `.exe.bak-*` 的 MZ 头 `4d5a9000…`）与快照 **B**（1187 files / 9129 occ / 271 命中文件）在 §1.6 作为历史漂移记录单列，变体分布 A 组在 §1.2 原样保留。
- 15:47 我读到的「文档声称已改名、磁盘 6 个 `*_zcode_*` 文件名仍在」是**进行中快照**：第 6 路正在执行 6 脚本 `git mv`，`docs/DSH-FIRST.md:35` / `:85` 写的是本轮完成态承诺。主代理验收按磁盘复核：新名存在 / 旧名零残留 / `git status` 出现改名 / `sync-models.ps1:228,253` 与 `tools/dsh_sync.py:60`、`tools/model_probe.py:45` 引用同步；失败则由主代理接管并把文档状态改回待落地。
- 本报告不把取样时点的不一致当作最终结论，取样编号仅用于标注时点。

### 5.3 未采纳备选（仅存档，不作推荐）

> **按 live 契约层保持原样，本轮未实施，仅作备选。** 下表是任务书原 C 类「`DSH_*` 优先 + `ZCODE_*` 兜底」映射表，完整保留备查；它与 §3 主方案**不并列、不作同等推荐**，主代理已裁决选 A，理由是双写与静默漂移风险以及 `cordis.patch.yml` 已绑定 `zcode-*`。

| 当前（契约层，实际保留） | 备选新名（未实施） | 备选兼容口径（未实施） |
|---|---|---|
| `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` | `DSH_PERSONAL_PROVIDER_CONFIG_FILE` | 读取顺序 `DSH_*` → `ZCODE_*` → 默认 |
| `ZCODE_BUILTIN` | `DSH_BUILTIN` | 同上 |
| `ZCODE_GATEWAY_KEY` | `DSH_GATEWAY_KEY` | 同上 |
| `ZCODE_CONFIG` | `DSH_CONFIG` | 同上 |
| `ZCODE_API_TYPE` | `DSH_API_TYPE` | 同上 |
| `ZCODE_BASE_URL` | `DSH_BASE_URL` | 同上 |
| `ZCODE_MAX_OUTPUT_TOKENS` | `DSH_MAX_OUTPUT_TOKENS` | 同上 |
| `WB_ZCODE_PROBE_FILE` | `WB_DSH_PROBE_FILE` | 同上 |
| `zcode-main / zcode-free / zcode-saver` | `dsh-main / dsh-free / dsh-saver` | 旧 ID 保留映射 |
| `zcode-（route id 前缀）` | `dsh-` | 旧前缀保留映射 |
| `zcode-model-ledger.json` | `dsh-model-ledger.json` | 旧文件名保留读取别名 |
| `~/.zcode/v2/*` | `新增 ~/.dsh/ 侧投影路径` | 两侧同步写入 |
| `*_zcode_sync.py / zcode_effective_body.js` | `*_dsh_sync.py / dsh_effective_body.js` | 旧名保留读取别名 |

备选方案若未来重启，必须同时回答「双写如何避免静默漂移」与「`cordis.patch.yml` route id / refs 键如何迁移」两个前置问题；本轮不处理。

### 5.4 部署边界

- `docs/DSH-FIRST.md:62` 的三个 `*_zcode_sync.py` 写入段收敛 `providers/_sink/zcode_provider_config.py`，与 §4.1 步骤 6 一致。
- `AGENTS.md` §6 与 `~/.dsh/AGENTS.md` §6 规定 zgate 换版走 `restart-zgate.cmd` / 部署三步，会话不自动重启长驻网关；本分片未触碰网关进程。

## 6 完成判据核对表

| # | 交付判据 | 结果 | 证据位置 |
|---|---|---|---|
| 1 | 总命中数 + 大小写变体分布 + 文件 Top30 计数（含复核命令） | 完成 | §1.1–§1.4、§1.10；Node 10425 / pwsh 10425；A 组变体原样保留 |
| 2 | 每类文件清单与计数（A–F） | 完成 | §2.2–§2.12；九类 occ 闭合 10425 |
| 3 | 当前字符串 → 目标字符串映射表（明确必须改 / 保留兼容 / 禁止改） | 完成 | §3.1–§3.6；按拍板选 A 重定稿 |
| 4 | 可直接执行替换方案（按文件分组逐条 old→new + CRLF/BOM 注意） | 完成 | §4.1–§4.4；75 个活跃文件 / 429 条逐条表 |
| 5 | 所有结论附 file:line 与可独立复现命令 / 数字 | 完成 | §1、§3.2、§3.6、§4.2、§5 逐条附行号 |
| 6 | 只读纪律：唯一写入产物为本报告，历史 / 第三方 / 配置原样保留 | 完成 | §0；未改 PROGRESS.md / docs / tests / provider_config.json |
| 7 | 凭据仅从环境变量读，报告零凭据值 | 完成 | §3 与 §4.2 仅列变量名，本机绝对路径已脱敏 |
| 8 | 未 git add / commit / push，未重启 zgate | 完成 | §0 |
| 9 | codegraph 未初始化时以 grep / glob / read 检索，未自行 init | 完成 | §0 |
| 10 | §13 进度可见（todo 首项四条件判定、动手前瞻句、阶段小结） | 完成 | 本会话 todo_write 清单 + 每步前瞻句 |
| 11 | 主代理拍板选 A 落地到 §3/§4，DSH_* 备选在 §5.3 标注「本轮未实施，仅作备选」且不与主方案并列 | 完成 | §3.1、§5.1、§5.3 |
| 12 | A/B 快照作为历史漂移单列，A 变体分布保留，当前值按复核命令重跑，取样时刻与快照编号写清 | 完成 | §1.2、§1.6、§5.2 |
| 13 | 第 6 路 git mv 进行中状态与主代理验收口径写明，不当最终结论 | 完成 | §1.6、§5.2 |
| 14 | 定稿阶段不再自行加载 skill | 完成 | §0；按主代理 15:50 / 15:54 指令 |
| 15 | send_message 回报主代理 | 完成后发送 | 父代理 session-90f67405-5d4e-4707-b280-3eba9af5856a |

---

> 本报告为 `zcode-census` 分片只读产物；替换实施由主代理按 §4 与第 6 路子代理统一执行，实施后请用 §1.10 复核命令重跑并比对各类 occ。
