# ModelBus 代码 + 功能审查与 DSH 主导架构改造汇总（2026-11-11）

> **一句话**：本仓从「ZCode 客户端配置脚本集」改为「DSH 主宿主 + 各类 agent 共用模型供给与路由策略」，7 路子代理完成代码审查 / 功能审查 / ZCode 全仓普查 / 文档一致性 / 替换方案 / 6 脚本改名 / docs 同步，主代理落地全部代码改造并独立验收；契约层一字不动，全量门禁通过。

---

## 0. 任务与委派口径

- 用户原指令（m00001）：对 `F:\Project\ModelBus` 做代码审查、功能审查、ZCode 字符替换、ZCode 专项适配改为面向 DSH 适配；项目从 zcode 中心改为 dsh 和各类 agent，主要面向 dsh；允许多开子代理，不限 3 个。
- §7/§14 委派闸门四条件全命中（≥3 目标 / ≥3 处同类 / ≥10 次工具 / 多视角）→ 先派后做；用户当轮覆盖同批 ≤3 路上限，实派 **7 路**：ZCode 全仓普查、代码审查、功能审查、文档一致性、替换实施方案、6 脚本改名、docs 同步。
- 验收硬口径：self-report 一律不当结论，全部按磁盘复核（glob + read 行数/字节 + 独立复现关键数字 + git status）；`codegraph_status` = Not initialized，按仓规直接用 grep / glob / read，会话内不自行 init。
- 共享写域单写者：主代理独占门面 / 方向正本 / PROGRESS / CHANGELOG / 第一方 tools；第 6 路独占 6 脚本改名与 `tools/dsh_sync.py` 路径替换；第 7 路独占 docs/ 22 篇活文档；`docs/DSH-FIRST.md` 与 `docs/README.md` 由主代理独占排除。

## 1. 方向正本与三层命名口径（本轮拍板）

- `docs/DSH-FIRST.md` 从「ZCode 降为投影、多 agent 是远期」升级为**当前架构**：DSH 主宿主 + 会话 / 子代理 / headless / 服务插件各类 agent 共用 `gateways/zgate` 单一入口，ZCode 降为兼容投影。
- **契约层（一字不动）**：`~/.zcode/v2/provider_config.json` 等路径、`ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` / `ZCODE_BUILTIN` / `ZCODE_GATEWAY_KEY`、`third-party/zcode*` 上游原件、schema 键（`providerConfigRules` / `modelConfigRules.providerModelRules` / `optionSpecs.reasoningLevel`）、`%LOCALAPPDATA%\ZCodeGateway\`、`zcode-main|free|saver` 与 `zcode-*` route id、`zcode-model-ledger.json`、`refs.ZCODE_GATEWAY_KEY`、NOTICE 商标段、CHANGELOG / PROGRESS / memories / evidence / docs/archive / release-notes 历史记录。
- **实现层（改中性名 + 留旧名兜底）**：6 个脚本名、4 组自造 env、第一方 docstring / 注释 / 报错文案 / User-Agent、36 篇文档措辞。
- **新层（用 agent 词汇）**：catalog / capabilities / routing policy / host projection / agent profile。
- **拍板不采纳** census / replacement-plan 建议的「新增 DSH_* 同名 env 优先」：再造一套同名替代会双写静默漂移，DSH 侧 `cordis.patch.yml` 的 route id 与 refs 键已绑定 `zcode-*`；方案报告只读归档，不执行。

## 2. 代码审查结论（[agent-code-review.md](agent-code-review.md)，69486B / 408 行）

- 30 项五维审查，识别中优先 6 项：**C1** 探活两份路径字面量无共享参数（`sync-models.ps1:289` 未传 `--out`）、**C2** `model_probe.py:233-237/267` 非原子整份重写 + 静默清空 `ever_ok`、**C3** `dsh_sync.py --check` 触发凭据校验误报 exit 2、**C4** `model_alias.py:2605` fixture 仍写真 quota-windows、**C5** `sync_report.py:340-358` 索引非原子 + 坏表 + EOL churn、**M1** DSH 投影双路径（best-effort vs 严格）。另有 C9（别名缓存只比 mtime 不比 size）、W1（`rename-to-modelbus.ps1:250` 无 BOM 重写 PS5.1 乱码）。
- ZCode 台账：66 文件 / 971440B / 24282 行 / HITS_TOTAL=242 / CONTRACT=113 / NET_C_IMPL=129；129 行分类 = 必须改 96 / 历史勿动 24 / 可保留兼容 9。
- 本轮已修 **C3**（`--source dsh` + 无 key + 非 apply 时跳过 `_credentials_state` 强制校验，compat 默认路径逐字不变）；C1/C2/C4/C5/M1/C9/W1 列为后续演进，不改长驻链路。

## 3. 功能审查结论（[agent-functional-review.md](agent-functional-review.md)，44185B / 257 行）

- 链路实况：`sync-models.ps1:275-277` → `model_alias.py --apply` 写 `~/.zcode/v2/provider_config.json` + alias map（`model_alias.py:2588-2604`）；`:344-350` → `dsh_sync.py --check/--apply` 投影 DSH；`dsh_sync.py:152-196` 读兼容投影最终态。改造前**输入真源是 ZCode 配置**，各类 agent 零实现。
- 数字：SUM total=223 / contract=52 / zcode_path=25 / narrative=146；impl_total=123 / impl_contract=37；doc_total=100 / doc_contract=15。
- 14 项缺陷 D1–D14（现役写侧仍以 `model_alias.py` 写 ZCode 配置为最终真源、catalog 只有 3 个能力快照、DSH patch 双写、文档新脚本名与磁盘旧名不符、catalog 真源声明超前等）。
- 等价性对照 I1–I9（providerRules / providerOrder / providerName / modelOrder / baseUrl / apiKey / providerModelRules / ledger 上轮 modelIds / effective_body.js 输出）、O1–O5（providerId / providerName / modelIds / baseUrl / apiKey）、6 个派生字段、7 条等价红线 —— 成为本轮 `dsh_sync.py --source` 补丁的设计依据。
- Go 侧 `X-Agent-Id` / `agentId` / `agent_id` 在 `*.go` 零命中；per-agent 预算 / 冷却分桶属后续演进，本轮不动 Go 代码、不重启长驻 zgate。

## 4. ZCode 全仓普查（[agent-zcode-census.md](agent-zcode-census.md)，112420B / 1373 行）

- 快照（15:59 +08:00）：Node 与 pwsh 双口径闭合 **10425 occ / 1224 文件 / 293 命中文件 / 1157 文本 / 67 二进制 / 6622 命中行**；变体 ZCode 7231 / zcode 2619 / ZCODE 285 / Zcode 160 / ZCodium 80 / zcodium 50。
- 九类闭合：A 第三方署名 182 + A2 gateways/upstream 上游 clone 与 request-logs 5167 + B 历史记录 1799 + D 活跃第一方代码 303 + E 活文档 570 + F1 .work 2261 + F4 assets 1 + F6 备份/日志 98 + F7 根配置 44 = 10425。
- git TRACKED_TOTAL=232 / TRACKED_WITH_ZCODE=126 / TRACKED_OCC=2270；§4.2 75 个活跃文件 / 429 条 token 映射：MUST 94 / FALLBACK 8 / KEEP 248 / TEXT 79。
- 主代理独立复现 §1.11 命令后 occ 上升到 10425（新增 evidence 报告与 .work 备份所致，非活跃代码回退）；`git status --short --` 历史/第三方路径输出空，历史与第三方零改动独立复核通过。

## 5. 文档一致性（[agent-docs-review.md](agent-docs-review.md)，53091B / 442 行）

- T0 基线：docs `zcod`=463 / `DSH`=118，根 7 文件 31/2，全仓 1943；T1（15:44）docs 459/122、根 18/17。
- 30 篇文档 484 链接 / 436 本地目标 / **0 死链 / 0 锚点缺失**；根 README 24 个 github 绝对链接（18 个 `blob/main`）与 `docs/DOC-RULES.md:105-107` 相对链接纪律冲突，已由主代理把 18 个 `blob/main` 归零。
- 报告 §4 含可直接贴入的「DSH 面向适配」章节正文草稿，§7 含 docs/ 下 92 token 脚本名路径逐处清单。

## 6. 替换实施方案（[agent-replacement-plan.md](agent-replacement-plan.md)，53530B / 708 行，SHA256 `4F08C2A1…`）

- 7 节 + 16 项完成判据：目标架构、逐文件 old→new（6 映射 + 调用方 file:line + 函数签名精确值 + 兼容别名）、可直接运行 Python 替换脚本正文（显式 UTF-8、bytes 读写保留 BOM/原 EOL、`.work/replacement-backups/<stamp>` 备份 + manifest.json、`--rollback`、幂等、PER_RULE/RESIDUAL 统计）、回滚（五目录反序还原 + 单文件 `git checkout` 口径 + 硬禁止 `checkout -- .` / `reset --hard`）、验证清单（py_compile / node --check / go vet / PS ParseFile / 三门禁 / B1–B12 行为等价样例）、C1–C5/M1 优先级、完成判据核对表。
- 该分片只读分析，脚本正文**未执行**；主代理已按磁盘实况独立落地等价改造，报告仅作归档与回滚依据。

## 7. 落地改造清单（主代理 + 两路写域分片，均按磁盘复核）

| 项 | 产物 | 复核结果 |
|---|---|---|
| 门面 5 文件 + 方向正本 | `README.md` / `CONTRIBUTING.md` / `SECURITY.md` / `AGENTS.md` / `docs/README.md` / `docs/DSH-FIRST.md` | 主语改 DSH 主宿主 + 各类 agent；18 个 `blob/main` 绝对链接归零；行尾保留（CRLF/LF 逐文件实测） |
| 6 脚本改名（[agent-rename-code.md](agent-rename-code.md)，13534B / 166 行） | `workbuddy_sync.py` / `workbuddy_probe.py` / `effective_body.js` / `qoder_sync.py` / `qoder_probe.py` / `qwen_sync.py` | 6 新名全在、6 旧名全消失；11 文件引用同步；4 组自造 env 新名优先旧名兜底；9 条 py_compile + node --check EXIT=0；`dsh_sync.py` 与 `sync-models.ps1` 差异恰为 6 行 / 2 行 |
| 多 agent 只读投影 | `tools/agent_profiles.py`（11983B / 264 行）+ `tests/test_agent_profiles.py`（4152B / 108 行） | 以 `catalog/model_caps.json` 为唯一能力真源，session / subagent / headless / service-plugin 四类 profile；`--list` / `--check` / `--json`；14 项 unittest OK；不写任何现网配置 |
| DSH 原生真源开关 | `tools/dsh_sync.py`（37234B / 850 行）+ `tests/test_dsh_source.py`（7830B / 164 行） | `--source compat|dsh`（默认 compat 逐字节等价）/ `--export-inventory`（零凭据 `modelbus-inventory/v1`）/ `--no-catalog-caps`；dsh 源不读 ZCode 配置、不缩型号全集、无凭据 `--check` 不误报；10 项等价性测试 OK |
| 叙述层去 ZCode 专项表述 | 第一方 `tools/`、legacy-router JS、`model_alias.py`、`make_social_preview.py`、`providers/` | docstring / 注释 / 报错文案 / User-Agent 改「DSH 主宿主 / 兼容投影」口径；py_compile + node --check 全 EXIT=0；契约层 env / 路径 / route id / 上游署名 KEEP |
| docs 同步（[agent-docs-sync.md](agent-docs-sync.md)，24847B / 383 行） | docs/ 顶层 22 篇活文档 | 136 处逐处替换（15 篇）/ 97 次旧名路径落新名 / 改后 22 篇活文档六旧名残留 0 / 落新名 98 次；`docs/TOOLS.md:38` 补 `agent_profiles.py` 索引；`check-docs.py` / `check-project.py --semantic` / `unittest` 三门禁两轮 EXIT=0；主代理补发 11 处纯叙述窄替换全部唯一命中断言、二次备份、EOL/BOM 不变 |
| CHANGELOG / PROGRESS | `CHANGELOG.md` 未发布段 + `PROGRESS.md` 末批次 | 写入 DSH 主导架构段落与验收；`[[TASK_ALL_DONE]]` 仍在文件末尾，全仓唯一一份 PROGRESS |
| 过期口径收口 | `docs/MODEL-PROVIDERS.md:739` + `docs/DSH-FIRST.md` §7 | 现网真值 19 条规则 / 0 空 map / 3 组；过期事实改历史清单口径，8 处旧口径逐条标注，CRLF/LF 与 BOM 保持，备份 `.work/dsh-final-20261111/` |

## 8. 全量门禁（`.work/dsh-gate-20261111/gate-final.log`，全部改动落盘后复跑）

| 门禁 | 结果 |
|---|---|
| `python -B -m unittest discover -s tests -q` | **Ran 158 tests / OK / EXIT=0**（既有 WARN 为投影型号移除告警，非失败） |
| `python -B tools/check-docs.py` | **[OK] 46 篇文档全部通过**（链接 / 锚点 / 引言块 / 孤儿）/ EXIT=0 |
| `python -B tools/check-project.py` | **8 项通过** / EXIT=0（zgate.json 真值 / 正本指针 / 网关实现 / 同步策略 / 换行 BOM 13 脚本 / PS1 语法 7 脚本 / 流式准入 PASS 14 WARN 3 FAIL 0 / 接线七处） |
| `python -B tools/dsh_sync.py --check` | **模型表：无变化；凭据引用：无变化** / EXIT=0（Host/Compat: 3 provider / 19 模型；DSH 路由主力 2 / 免费 5 / 省钱 12） |
| `python -B tools/model_caps.py --check` | EXIT=1，差异 10 条能力真值；经 `git show HEAD:tools/model_caps.py` 基线复核**同 10 条**，属本轮前既有漂移（catalog 能力真值待补），非本次替换引入 |
| `py_compile` / `node --check` | 9 个 provider Python + 5 个 tools Python + 2 个 legacy JS + `effective_body.js` 全 EXIT=0 / PYCOMPILE_EXIT=0 |

最终复跑（全部改动落盘后）：`UNITTEST_EXIT=0` / `CHECKDOCS_EXIT=0` / `CHECKPROJECT_EXIT=0` / `DSHSYNC_CHECK_EXIT=0` / `PYCOMPILE_EXIT=0` / `MODELCAPS_CHECK_EXIT=1`（HEAD 基线同 10 条既有差异）。7 路子代理全部 `inactive`，分片产物按磁盘独立复核（字节 / 行数 / 标题 / 完成判据表），`git status` 与本轮改动清单一致；零 commit / push、零凭据写入、零 zgate 重启。

## 9. 边界与后续演进（本轮刻意不动）

- **`gateways/zgate/` 下 Go 代码 11 行叙述性 ZCode 注释不动**：`AGENTS.md:107` 改 Go 即触发 `tools/zgate-lifecycle/restart-zgate.cmd` 受控换版，`:108` 严禁 `Start-Process` / `cmd /c` 直接拉起；长驻网关禁止会话重启，`check-project.py` 不查 Go 二进制 hash 或源码行号。列为后续演进。
- **契约层零改动**：`~/.zcode/v2/*`、`ZCODE_*` env、schema 键、`third-party/zcode*`、NOTICE 商标、`zcode-*` route id 全部 KEEP（活跃域独立复核：`ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` 21、`ZCODE_GATEWAY_KEY` 11、`zcode-main` 24、`.zcode/v2/provider_config.json` 41、`third-party/zcode/` 14）。
- **model_caps 10 条能力真值差异**：catalog 真源补齐属独立能力审计批次（批 1），与本轮命名/适配改造解耦。
- **C1/C2/C4/C5/M1/C9/W1 与 Go 侧 X-Agent-Id 分桶**：后续演进，不在本轮行为等价改造范围。
- 本轮零 git commit / push、零凭据写入、零 zgate 重启、零长驻进程改动。
- docs-sync 交回的过期口径复核结果：现网 `providerModelRules` 19 条 / 空 map 0 条 / `providerRules` 3 组（独立读取现网配置取证）；**已收口** `docs/MODEL-PROVIDERS.md:739`（原「当前 ZCode 里配了空 map 的模型」改为历史清单口径并指向 `docs/PITFALLS.md` §2），并在 `docs/DSH-FIRST.md` §7 把 8 处过期口径逐条标注「已修 / 历史标注保留」。
- 按历史层保留：`docs/MODEL-QUICK-REF.md:8/:64/:78`（头部自带「历史快照，口径以 MODEL-PROVIDERS 为准」且 `AGENTS.md:100` 默认禁动）、`docs/MAINTENANCE.md:12`、`docs/ARCHITECTURE.md:53/:309/:379`（§1 历史快照与去路由化推演）、`docs/TROUBLESHOOTING.md:216/:367/:450/:479` 历史组数实录。`tools/model_alias.py:368-372` 注释复核后已是更正版本（「不写键、不兜 1000000/128000」），无需改动。其余叙述层「ZCode」字面量属界面行为 / 正本标题 / 热重载机制描述，需扩口径后统一。

## 10. 回滚路径

| 备份目录 | 覆盖 |
|---|---|
| `.work/dsh-first-20261111/` | 8 个门面/方向正本原态 |
| `.work/dsh-rename-20261111/` | 11 个改名引用文件 + 6 个 `.pre-narrative` |
| `.work/dsh-source-20261111/` | `dsh_sync.py.pre-patch.bak`、snippets.json、sandbox、pending |
| `.work/dsh-tools-20261111/` | 8 个第一方 tools / legacy-router 原态 |
| `.work/dsh-providers-20261111/` | 10 个 providers 原态 |
| `.work/dsh-docs-20261111/` | 22 篇活文档原态 + ledger-final.json + residue.json |
| `.work/dsh-final-20261111/` | CHANGELOG / PROGRESS 写入前原态 + `MODEL-PROVIDERS.md.bak` / `DSH-FIRST.md.pre7.bak` / `*.pre-final-close.bak` |
| `.work/dsh-gate-20261111/` | gate.log（中间态）、gate-final.log（最终复跑）、model_caps.HEAD.py 基线 |

回滚顺序按上表反序；契约层未动，还原备份并把 6 个新名改回旧名即可恢复改造前行为。严禁用 `git checkout -- .` / `git reset --hard` 覆盖既有未提交改动。

## 11. 分片产物清单（7 份，主代理按磁盘独立验收）

| 分片 | 文件 | 字节 | 行数 |
|---|---|---:|---:|
| ZCode 全仓普查 | [agent-zcode-census.md](agent-zcode-census.md) | 112420 | 1373 |
| 代码审查 | [agent-code-review.md](agent-code-review.md) | 69486 | 408 |
| 功能审查 | [agent-functional-review.md](agent-functional-review.md) | 44185 | 257 |
| 文档一致性 | [agent-docs-review.md](agent-docs-review.md) | 53091 | 442 |
| 替换实施方案 | [agent-replacement-plan.md](agent-replacement-plan.md) | 53530 | 708 |
| 6 脚本改名 | [agent-rename-code.md](agent-rename-code.md) | 13534 | 166 |
| docs 同步 | [agent-docs-sync.md](agent-docs-sync.md) | 24847 | 383 |

> 收尾脱敏：本轮推送前对 `agent-code-review.md` 中 1 处仓内绝对路径、既有分片 `agent-gemini38-memory.md` 中 11 处本机用户目录做了 `~` / 相对路径归一化；`check-secrets.py` 工作树扫描与 `--tracked-only` 双通道均为 exit 0。上表字节数为归一化后的磁盘实况。
