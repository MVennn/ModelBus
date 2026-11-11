# ModelBus「去 ZCode 化」文档与配置一致性审计

> **一句话**：38 篇 docs 里 29 篇带 ZCode 口径（487 行），但改名真正会改坏的只有 6 类**外部契约**（配置 schema 键、`ZCODE_*` 环境变量、`~/.zcode` 路径、provider id、vendored 规则文件、脚本文件名），其余是叙述性称呼，可整体换成 agent / DSH 口径。

- 审计基线：`main` @ 只读；`ops_bash` 因 NTFS 硬链接耗尽不可用（EXECUTOR_UNAVAILABLE: link 'awk.exe' 失败），证据全部由 run_code 内 Node fs 直读磁盘取得。
- 本次只写本文件；未改代码 / 配置 / docs / PROGRESS.md / tests，未 commit，未触碰 7871 / 7863 / 8790。

---

## 〇、五条结论（先看这个）

1. **能力 + 档位在磁盘上只有一个源头**：`~/.zcode/v2/provider_config.json` 的 `optionSpecs.reasoningLevel` 与 `config.properties`；但**生效值**由内置 `modelApiRules` 的 `.*` 规则叠加，仓内 `third-party/zcode/zcode-builtin.json` 优先级最高（`providers/workbuddy/zcode_effective_body.js:62-63`）。动它 = 动全仓文档与投影的基准。
2. **`dsh_sync.py` 里没有 1000000 / 128000 这两个常量**（grep 零命中），它们是内置 `.*` 规则的产物；`tools/model_alias.py:366` 注释却说是「dsh_sync 的兜底值」。GLM-5.3-Flash 源 `maxOutputTokens.max=131072` 投影后为 `128000`（`~/.dsh/profiles/desktop/cordis.patch.yml:214-225`），上限确实掉一档。
3. **现役是三组不是四组**：`providerOrder` 只有 `opencode-go-chat / -free / -fast`，alias map 分组 主力 3 / 免费 5 / 省钱 12。docs 仍在写四组的有 `ARCHITECTURE.md:251,331`、`QODER.md:19-24,131,137,156,191`、`TROUBLESHOOTING.md:356,388`。
4. **`PITFALLS.md:73-76`「当前配了 5 个 `map="{}"`」已失效**：实测 20 条里空 map **0 条**，所列 5 个 modelId 全不在现行配置。机制成立、清单过期。
5. **新增一篇「DSH 主导」文档 = 2 处门禁硬性 + 3 处规则要求 + 2 处指针建议**；改名波及面 = 6 类必须保留 + 全量叙述可改（§四给 grep 校验命令）。

---

## 一、docs/ 命中盘点（格式「文件:行 → 讲什么口径」）

总览：29/38 篇命中、ZCode 字样 487 行。**机制正本**（MODEL-PROVIDERS / UPSTREAM / ARCHITECTURE / PITFALLS / MAINTENANCE / TOOLS / SECRETS）必改；**历史快照**（MODEL-QUICK-REF、archive/、release-notes/）按 `DOC-RULES.md:149-153` 可留旧口径。

| 主题 | 文档:行 → 口径 |
|---|---|
| 架构 | `ARCHITECTURE.md:5,27,31-34` → 结论「293.4MB→~128MB」「对 ZCode 已只有一路、`provider_config.json` 一字节不改」 |
| 架构 | `ARCHITECTURE.md:52-56,212` → 现状表含 `zcode_gateway_watch.ps1` 124.2MB；同篇称其已退役→`zgate install` |
| 架构 | `ARCHITECTURE.md:75-76,101,108,142,162` → 每 provider 只能一个 `api.baseUrl` 故三组共用 7871；拓扑图；alias map 热加载；日志落 `%LOCALAPPDATA%\ZCodeGateway\` |
| 架构 | `ARCHITECTURE.md:251,316,327` → 验收「四组模型列表不变」、回退步 `zcode_gateway_watch.ps1 -Install`、「开 ZCode 2s 就绪」 |
| 路由 | `ARCHITECTURE.md:309` + `MODEL-ALIAS.md:16-17,415,461-492` → 单点崩溃全线不可用；按 alias map `chain` 分流而非按组；生成三组 + 协议桥的命令序列 |
| 路由/流式 | `MODEL-PROVIDERS.md:826`（`cordis.patch.yml` 的 `llm-pi-ai` 路由表）+ `MODEL-STREAM.md:3,28-30,173`（契约以 patch 为准，常量见 `tools/model_stream_check.py:64`） |
| 模型目录 | `MODEL-PROVIDERS.md:3,37-38,63-73` → 开篇定位、四步法（探测用 ZCode 真实 body / 只写三个落点）、「ZCode 侧的关系」正本节 + 完整路径 |
| 模型目录 | `MODEL-PROVIDERS.md:78-79,84,93-95,100-106` → 三处落点（providerModelRules / providerOrder / personalModelIds）、约 1 秒轮询、三脚本写入行为、dry-run 与界面互斥 |
| 模型目录 | `MODEL-PROVIDERS.md:130-132,289-302,339` → 三个 chat provider、分离模式四档、PINNED_MODEL_IDS |
| 模型目录 | `MODEL-PROVIDERS.md:358-359,465-474,493,521-522,674` → 档位取决于 `reasoningLevel.values`；Qoder 原生四件套 + map 覆写；桥不转发思考→必须 `"{}"`；排序与未定论项 |
| 模型目录 | `MODEL-PROVIDERS.md:711,723-747,764-783` → §5.2 五种 map 形态、空 map 清单（**已过期**）、§5.4 下拉只由 values 生成、默认档 = `values.at(-1)` |
| 模型目录 | `README.md:14-15`（索引定位语，含「ZCode 配置落点」）+ `MODEL-QUICK-REF.md:8,64,78,96,102`（历史速查，`:102` 死路径） |
| 模型目录 | `CAPABILITY-AUDIT.md:3,11,101-105,173,185-229` → 能力/档位真实来源审计：三层规则叠加、`.*` 兜底魔数、20 模型逐字段对账、**131072→128000** 差额、五类修法 |
| 流式 | `MODEL-STREAM.md:14-16,41-52,60-65,128,145-148` → 档位与 `reasoning.encrypted` 分流口径（进表即纳入自动化） |
| 流式 | `REVIEW-2026-11-10.md:22,40,55,105-107,151,181` + `release-notes/0.6.0.md:19` → 档位只覆盖 1/20 模型的判定；0.6.0 是历史快照不必改 |
| 排障 | `TROUBLESHOOTING.md:12,23-52` → 图例「【通用】= ZCode 客户端侧」；「ZCode 里模型列表不刷新」全套（读配置 / 备份链 / 1s 热重载 / 界面整份写回） |
| 排障 | `TROUBLESHOOTING.md:66-71,82-88,197-215,270,293-320` → 看真实 body、map `"{}"`、403/400 误报、`workbuddy_probe_zcode.py` 直接退出的目录硬依赖与 `ZCODE_BUILTIN` |
| 排障 | `TROUBLESHOOTING.md:339-360,567,702` → zgate 常驻不跟随 ZCode 起停；只读看 `cordis.patch.yml` 的 ui-chat；三步收尾 |
| 排障 | `QODER.md:8-9,15,24,55,78-80,93,122,135-167,188-192`、`QWEN.md:92,124,137,169,176,234-275`、`QINIU.md:71` → 三家渠道并入「四组」（Qoder 处过期）、各自 `provider_config` 落点与档位取值 |
| 坑 | `PITFALLS.md:45-79` → §2 核心：内置 `modelApiRules` 第 3 条 `.*` 无条件注入 4 个思考字段→400，解法空 map（清单过期） |
| 坑 | `PITFALLS.md:85-97,104-110` → 正则 `^(?:pattern)$` 大小写不敏感；`ModelConfigRules.resolve()` 最后命中者生效 |
| 坑 | `PITFALLS.md:6,11,30,123-125,179-186,216,259-265,312` → 读法图例、探测铁律 ≥20s、界面整份写回覆盖、历史坑、provider 级 baseUrl、体检前读 alias map |
| 工具 | `TOOLS.md:8,21,27-37` → 「`model_alias.py` 是 ZCode 配置唯一最终写入者」、客户端定义、`dsh_sync.py` 重写 patch |
| 工具 | `TOOLS.md:40-50,55-67,73,77-99` → 三脚本/两 probe 降级为数据采集、产物表（含 `~/.zcode/v2/*`）、2026-10-28 起三组、统一与 `--separate` |
| 工具 | `MAINTENANCE.md:12,128-130,151-166` → 分组沿革、每日命令（`--probe-file ~/.zcode/v2/model_probe.json`）、探测必须用真实 body |
| 工具 | `MAINTENANCE.md:188-215,224-237,245-253,316-342,368-378,406-417` → 四个 `--apply` 备份名与 cp 回退、「ZCode 配置热重载」、五段流水线、生命周期与 `zgate.json` 键 |
| 工具 | `SECRETS.md:17,30-41,69-75,91-102,109-136,149-155,170-183,203-206` → 凭据位置表、**3.4 ZCode 配置文件路径**（含覆盖变量）、环境变量表（`ZCODE_BUILTIN`「不是凭据、是协议开关」）、自查红线 |
| 上游 | `UPSTREAM.md:42-57,63-115` → ZCode 生态同类项目表、AnyBridge 写入路径（与本仓同文件）、抄的两条做法 |
| 上游 | `UPSTREAM.md:233-241,255-286,320-347,351-426` → ZCodium 即规则原文、`reasoningLevel`→4 字段映射、commit `3c5b227` revision 33 逐字一致、随仓 4 个原样文件、两处待落地；`archive/OPENCODE-GO-ANALYSIS.md:15-274` 归档只读 |
| 规则层 | `DOC-RULES.md:48,50` → 正本映射表两条（「脚本改 ZCode 配置的哪几处」「与 ZCode 界面互斥」）；改名后映射表仍须保留指向的正文标题 |

---

## 二、`docs/README.md` 索引结构与新文档落点

**结构**：`README.md:1-6` 标题 + 「一句话」块；`README.md:10/22/38/45` 分**四类** —— 一、模型与 Provider；二、流程与规范；三、排错与踩坑；四、参考资料。前三类表格为 `| 文档 | 一句话定位 |`（`:12-13,24-25,40-41`），第四类为 `| 位置 | 一句话定位 |`（`:47-48`，混排仓内文档与仓库根文件）。

**每条格式**：`| [文件名.md](文件名.md) | **正本标签**：具体内容，30~60 字一行读完 |`（`DOC-RULES.md:147-148`「索引行 = 定位，不是摘要」）；文件名 `ALL-CAPS-WITH-HYPHENS.md`（`DOC-RULES.md:24-33`）。

**插哪**：放**二、流程与规范**（`README.md:26-36` 表格，建议 `ARCHITECTURE.md` 之后、`MAINTENANCE.md` 之前）—— 讲的是投影管道与口径，不是某个 provider 的参数；若主题偏「能力/档位怎么进 DSH」，则归**一、模型与 Provider**，紧邻 `CAPABILITY-AUDIT.md`。

| # | 同步位置 | 性质 |
|---|---|---|
| 1 | `docs/README.md` 对应类别加一行 | **门禁硬性**：`tools/check-docs.py:166-169` 判孤儿，未进索引即 FAIL |
| 2 | 新文档开头 10 行内的 `> **一句话**：…` | **门禁硬性**：`tools/check-docs.py:159-164` |
| 3 | `DOC-RULES.md:12-17` 类别「现有成员」列 | 规则要求（`:8-20`），门禁不查，不加即失真 |
| 4 | `DOC-RULES.md:44-66` 正本映射表加一行（若成「DSH 投影」正本） | 规则要求（`:37-40` 单一正本） |
| 5 | `DOC-RULES.md:122-138` 变更触发矩阵加一行（若定新口径） | 规则要求 |
| 6 | 指针：`MODEL-PROVIDERS.md:69-73` §1 与 `TOOLS.md:35` 各加「投影口径见 X.md」 | 建议，避免两处写全文 |
| 7 | `PROGRESS.md` 追加批次（对外可见再动 `CHANGELOG.md`） | 台账惯例 |

> 落地后跑 `python tools/check-docs.py`（链接 / 锚点 / 引言块 / 孤儿）与 `python tools/check-project.py`（`:55` 门面、`:312-326` 流式接线 7 项断言）。`evidence/` 在 `check-docs.py:25-35` 的 SKIP_DIRS 内，本审计文件不参与门禁。

---

## 三、配置副本面（谁是源、谁生成、改哪个会漂）

| 副本 | 源 / 生成者 | 消费方 | 改它会怎样 |
|---|---|---|---|
| `~/.zcode/v2/provider_config.json`（15539B，20 条） | **唯一源**；写者 `model_alias.py --apply`（`:2025`）、`workbuddy_zcode_sync.py`、`qoder_zcode_sync.py`、qwen 同步、`go_model_sync.py --apply`（`:708`） | ZCode（~1s 轮询）、`dsh_sync.py`、`zcode_effective_body.js:176-182` | 手改会被下次 `--apply` 覆盖；与界面同时写会被整份写回冲掉（`PITFALLS.md:179-186`） |
| `~/.dsh/profiles/desktop/cordis.patch.yml` | **由 `dsh_sync.py --apply` 生成**（`:431` 出 routes；备份 `.bak-dshsync-`，`MAINTENANCE.md:192`） | DSH 宿主（热加载） | 手改必被覆盖；**唯一会掉能力的副本**：131072→128000（`:214-225`） |
| `third-party/zcode/zcode-builtin.json`（+ schema 三件套，pin `3c5b227`） | 上游原文 vendor（`third-party/zcode/.upstream-sha`） | `zcode_effective_body.js:62-63` **最高优先** | 等于改全仓 effective body 基准（1000000/128000 魔数出自此），文档/测试/投影全漂，应视为只读 |
| `~/.zcode/v2/runtime/provider/<plat>/<ver>/<ep>/zcode-builtin.json` | ZCode 安装时写入（`:65-76`） | 同上，次优先 | ZCode 升级即变；vendor 在场时不读它 |
| `<安装目录>/resources/config/provider/zcode-builtin.json` | 安装包自带（`:93`） | 兜底 | 仅以上都缺时生效；`TROUBLESHOOTING.md:293-320` 的 `ZCODE_BUILTIN` 指这里 |
| `third-party/zcodium/zcode-builtin-reasoning-rules.json` + `reasoning-rules.js` | ZCodium 切片（`UPSTREAM.md:343-356`） | `node ... reasoning-rules.js check` | 只影响校验结论，不进投影；改了 `UPSTREAM` 的「逐字 4 条」结论失真 |
| `providers/workbuddy/cache/wb_pricing.json` | `workbuddy_fetch_pricing.py`（`:3,:96`） | `workbuddy_zcode_sync.py:151`（唯一价格输入）、`model_alias.py:69` | 手改价格 → 分组与链序漂 |
| `providers/workbuddy/cache/wb_zcode_probe.json` | `workbuddy_probe_zcode.py`（`WB_ZCODE_PROBE_FILE` 可覆盖） | `TROUBLESHOOTING.md:109,140` | **当前不存在**，docs 仍在引用 → 命令空结果（失效引用，不是漂） |
| `~/.zcode/v2/model_probe.json`（46994B） | `tools/model_probe.py`（`sync-models.ps1:287`） | `model_alias.py --probe-file` | 手改 `status/ever_ok` → 模型误收/误删组 |
| `~/.zcode/v2/model-alias-map.json`（27511B，20 条） | `model_alias.py --apply` | `zgate.json.aliasMap`、`ARCHITECTURE.md:142` | 只有 channel/price/group/chain，**无能力与档位**；`dsh_sync` 不读它 → 只影响路由 |
| `evidence/*.json`（`wb_panel_models.json` 29211B 等） | `go_model_sync.py` 默认写本仓 `evidence/`（`:63-65`，与 `providers/evidence/` 分家）/ 面板快照 | 只读证据 | `DOC-RULES.md:152` 归档只读，改它等于伪造证据 |

**判据**：能力/档位真源 = `provider_config` 的 `optionSpecs`；**生效值** = 内置 `.*` 规则覆盖后的 effective body（vendor 优先）；`cordis.patch.yml` 是唯一会掉能力的末端副本；alias map / probe / pricing 在路由、筛选、价格三条别的轴上。

---

## 四、改名波及清单（zcode → agent / dsh）

### A. 必须保留（外部契约，改了会断）

| 类别 | 具体字符串 | 依据 |
|---|---|---|
| 配置 schema 键 | `modelConfigRules`、`providerModelRules`、`providerConfigRules`、`modelApiRules`、`providerOrder`、`personalModelIds`、`modelId`/`providerId`、`config.enabled`/`.properties`、`optionSpecs`、`reasoningLevel.values`/`.map`、`maxOutputTokens.max`、`inputFormat.supportsImage`、`supportsToolCall`、`contextWindow` | ZCode 读写，写错整份配置失效（`MODEL-PROVIDERS.md:78-79`） |
| 环境变量 | `ZCODE_BUILTIN`、`ZCODE_PERSONAL_PROVIDER_CONFIG_FILE`、`ZCODE_API_TYPE`、`ZCODE_BASE_URL`、`ZCODE_CONFIG`、`ZCODE_MAX_OUTPUT_TOKENS`、`ZCODE_PROBE_FILE`、`ZCODE_GATEWAY_KEY`（凭据键名） | 代码真实读取点 `zcode_effective_body.js:57-60`、`tools/dsh_sync.py`、`workbuddy_probe_zcode.py`；`SECRETS.md:109-136` |
| 路径 | `~/.zcode/v2/provider_config.json`、`model-alias-map.json`、`model_probe.json`、`runtime/provider/...`、`%LOCALAPPDATA%\ZCodeGateway\` | 硬编码：`workbuddy_zcode_sync.py:146`、`go_model_sync.py:59`、`model_alias.py:481,490`、`sync-models.ps1:287` |
| provider id | 源侧 `opencode-go-chat`/`-free`/`-fast`；DSH 侧 `zcode-main`/`zcode-free`/`zcode-saver` | `tools/dsh_sync.py:8-9,75-77`、`cordis.patch.yml:7`、tests 13 处断言 |
| 脚本文件名 | `workbuddy_zcode_sync.py`（`sync-models.ps1:228`）、`qoder_zcode_sync.py`（`:253`）、`zcode_effective_body.js`、`zcode-builtin.json` | 计划任务按路径调用，改名即每日 12:00 流水线断 |
| 上游事实 | `zai-org/ZCode`、Apache-2.0 归属、`UPSTREAM.md:46-53` 仓库名/许可证、`NOTICE`、`README.md:53` | 改名即事实错误、许可证声明失真 |

### B. 可改（纯叙述）

「ZCode 客户端 / ZCode 里 / ZCode 侧 / 对 ZCode 来说 / 关 ZCode 迁移顺序 / 开 ZCode 2s 就绪」，以及 `MODEL-PROVIDERS.md:69` 标题、`TROUBLESHOOTING.md:12` 图例、`README.md:14` 定位语、`DOC-RULES.md:48,50` 描述文字（键名保留即可）。**判据：删掉 ZCode 后意思不变 = 叙述；删掉后读者不知道该改哪个文件/字段 = 契约。**

### C. 校验命令（git-bash；PowerShell 用 `Select-String` 或 `git grep --no-index`）

```bash
cd /f/Project/ModelBus
# 1) 契约面清点：这些命中必须保留
git grep -n -E 'ZCODE_[A-Z_]+' -- docs tools providers gateways
git grep -n -E 'providerModelRules|providerConfigRules|modelApiRules|optionSpecs|reasoningLevel|maxOutputTokens' -- docs
git grep -n -F '.zcode' -- docs tools providers sync-models.ps1
# 2) 反向：改完后只应剩「叙述性 ZCode」
git grep -n -i 'zcode' -- docs | grep -viE 'ZCODE_|~/[.]zcode|providerModelRules|optionSpecs|reasoningLevel|zcode-builtin|zcode-main|zcode-free|zcode-saver|zcode_effective_body|workbuddy_zcode_sync|qoder_zcode_sync|zai-org/ZCode|ZCodeGateway'
# 3) 门禁复验
python tools/check-docs.py && python tools/check-project.py
```

第 2 条输出应**只剩**「ZCode 客户端」「在 ZCode 里」这类句子；出现 `ZCODE_*`、路径、id 即改过头。

---

## 五、已过期 / 自相矛盾口径（8 条，均带实证）

1. **同篇四组 vs 三组**：`ARCHITECTURE.md:75-76` 写「三组（主力/免费/省钱）」，`:251` 验收写「ZCode **四组**模型列表不变」、`:331` 写「**四组**共 36 个模型」；实测 `providerOrder` 三条、分组 3/5/12。
2. **QODER.md 内部打架**：`:19-24,131,137,156,191` 六处「四组」，同文 `:92` 已写「分组也早从四组并成三组」。
3. **排错步骤写死四组**：`TROUBLESHOOTING.md:356`「四组没指向 7871」、`:388`「同步改四组的 `baseUrl`」，同文 `:329` 是三组 —— 照 `:388` 操作会漏改或错改。
4. **分组时点倒挂**：`MAINTENANCE.md:9-10` 已声明「2026-10-28 起三组，下文四组是 10-23 历史口径」，紧接 `:12` 却以「**2026-10-23 起**：统一为四组…最终写入者是」作正文开头，读起来像现行。
5. **空 map 清单过期**：`PITFALLS.md:73-76` 列 5 个 `map="{}"`（`beam-free` / `minimax-m3.1-flash-free` / `minimax-m3` / `muse-spark-1.3-contributor` / `muse-spark-1.2-contributor`），实测 20 条里空 map **0 条**且 5 个 id 全不在配置；`MODEL-PROVIDERS.md:737-747` 同源过期。
6. **`model_alias.py:366` 注释与代码不符**：注释称「DSH 侧只能吃 dsh_sync 的兜底值（1000000 ctx / 128000 output）」，`tools/dsh_sync.py` 内这两个数字 grep 零命中；值来自内置 `.*` 规则（`CAPABILITY-AUDIT.md:185-214`），且 `131072` 被投成 `128000`（`:173`）。
7. **退役脚本仍当现状与回退命令**：`ARCHITECTURE.md:52-56` 把 `zcode_gateway_watch.ps1`（124.2MB）列进现状表、`:316` 把「重新 `zcode_gateway_watch.ps1 -Install`」写成回退步，而 `:212` 自己说已退役、仓内无此文件（glob 零命中）。
8. **死路径与悬空引用**：`MODEL-QUICK-REF.md:102` 指向 `scripts/go_model_sync.py`（仓内无 `scripts/`，真实路径 `providers/opencode-go/ops/go_model_sync.py`）；`UPSTREAM.md:351` 称「PITFALLS.md §2 结论需修订」，而 `PITFALLS.md:79` 仍是「根因永远是这一条」，待修订项没有落点。

> 复核口径：`provider_config` 9 条「无 map」/ 11 条「有 map」/ **0 条「空 map」**，9 条全字段、11 条仅 `reasoningLevel` —— 与 `CAPABILITY-AUDIT.md:101` 一致，说明该篇能力对账未过期；过期的是「空 map 清单」与「四组」两处。
