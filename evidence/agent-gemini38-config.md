# Gemini-3.8-Flash 硬引用盘点（只读）

> 结论前置：仓内命中 **212 行 / 40 个文件**（14:5x 快照；15:05 复核已降到 **204 行 / 38 个文件**，见 §0），其中真正决定"这个模型存不存在"的只有 **9 个位置**，
> 其余全是文档、历史流水与测试夹具。删它**不会**影响任何别的模型 —— 它不在任何模型的 fallback 链里，是单族终点；
> 但有 **3 类"看着像它、其实属于 Gemini-AIS"** 的行，删错就打断 AIS 链。

- 生成：只读盘点子代理，2026-11-11，工作目录 `F:\Project\ModelBus`（真实项目；`F:\Project\_merged\DeepseekHarness\ModelBus` 是同一份的 junction）
- 期间未修改任何配置 / docs / tests / 脚本，未跑 git 写操作，未重启网关；本轮唯一写入 = 本文件
- 采集时刻仓内 `git status`：`M docs/PITFALLS.md`（**并行会话正在改**）、`?? evidence/agent-gemini38-memory.md`（并行分片）
- 仓外 live 真值读取时刻：`~/.zcode/v2/provider_config.json` 18233 B / mtime 2026-11-11 13:40:36；`model-alias-map.json` 27190 B / 同 mtime（**15:03:58 两者已被 `--apply` 重生成，见 §0.1**）

---

> ⚠ **本文 §2 的行号基于 14:5x 快照。** 15:03:58 主线已删完运行链路并重生成 live 配置：
> `tools/model_alias.py`、`catalog/upstream_caps.json`、`catalog/model_caps.json`、`tests/test_model_alias_hop_order.py`、
> `tests/test_model_alias_efforts.py`、`tests/test_dsh_sync_efforts.py` 均被改写（行号下移/失效），`docs/**` 行号仍有效。
> **先读 §0 现场复核，再回 §2 查"当初为什么这么设计"。**

## 0. 现场复核（2026-11-11 15:05，最该先看）

### 0.1 已确认完成（拿证据说话）

| 检查 | 结果 |
|---|---|
| `~/.zcode/v2/provider_config.json` | 17223 B / mtime 15:03:58 → `Gemini-3.8-Flash` **0 命中**（删除前 3 处：`:26,31,140`） |
| `~/.zcode/v2/model-alias-map.json` | 25401 B / 同 mtime → 7 处 "3.8" 字样**全部属 `Gemini-AIS`**（`:68-112` 的 `ais-gemini-3.8-flash` 家族 + `:848` legacy `gem:ais-gemini-3.8-flash`），**无 `Gemini-3.8-Flash` 条目** |
| `tools/model_alias.py` | `HJ_PRICES: dict = {}`（`:100`，带退役注释）；`price_of` 对 HJ 恒返 None（`:1063-1065`）；`MAIN_ORDER` / `HOP_PRIORITY` / `ABBR` 的 HJ 三跳全删；`EMPTY_ALLOWED` 只剩 `Gemini-AIS`（`:638-643`）；`hjm:` 分支**故意保留**（`:1327-1332`，给存量配置保渠道归属） |
| `catalog/upstream_caps.json` / `model_caps.json` | G38 条目已删；剩下的 `:54/:62/:63` 属 `Gemini-AIS`（`base` + 两个共享取证标签） |
| 测试（逐个实跑） | hop_order **10 ok**（原 11，删了 HJ 专用用例）/ efforts 14 ok / probe_filter 11 ok / naming 7 ok / price 15 ok / caps_upstream 12 ok / model_caps 21 ok / dsh_sync_efforts ok |
| 门禁 | `check-project.py` 8 项 OK（`upstreams=7`，HJ 渠道保留）；`check-docs.py` 46 篇全通过；`model_alias.py --check` **exit 0**（无本模型相关漂移） |
| 新增护栏 | `tests/test_model_alias_hop_order.py:174` `self.assertNotIn("Gemini-3.8-Flash", set(ma.ABBR.values()))` —— 防名字复活，这是"删得干净"的关键 |

### 0.2 残留清单（逐条判断）

| 位置（当前行号） | 内容 | 分类 | 判断 |
|---|---|---|---|
| **`catalog/upstream_caps_evidence.json:5-21`**（`:6` display、`:8` base、`:14-16` 三个 evidence 标签） | G38 取证条目整条还在 | CONFIG_MODEL_ENTRY | **唯一残留的"配置形状"对象**。删它不影响 AIS（`:22-34` 是 AIS 自己的条目）；不删也无害 —— `merge_evidence` 按 display 匹配、对不上就 `continue`（`tools/caps_upstream.py:263-267`），不会复活模型 |
| `tools/model_alias.py:96,1116-1117,1128-1129` | 注释仍拿 `[满血A]gemini-3.8-flash` 举例（大写 A 被 lower 化、档位前缀要剥） | CODE_LOGIC | 例子已无对应型号。建议换成仍在役的带前缀型号，否则后人没法照例子验证；**规则本身不能删** |
| `tools/model_alias.py:457-458,2542-2552` | 提到该名字的历史注释（`:457-458` 已被改写成"整族已下线"） | CODE_LOGIC | 保留：它们解释 legacy 卫生的由来 |
| `catalog/upstream_caps.json:62-63`、`catalog/upstream_caps_evidence.json:33-34` | `evidence:vendor-doc-gemini-3.8-flash-tools` / `-modalities` | CONFIG_MODEL_ENTRY | **属 `Gemini-AIS`**。任何"全局替换 3.8-flash"都会打掉 AIS 的 tool/img 取证来源 —— 这仍是全仓最容易被误伤的一处 |
| `docs/MODEL-PROVIDERS.md:688-728` | §4.11.5 整节（41 行）专属本模型 | DOC | 可直接删；节末 `:730` 是 §4.11.6，别越界 |
| `docs/CAPABILITY-AUDIT.md:125,163,201`、`docs/DSH-FIRST.md:68` | 计数句（"11 个 / 20 条 / 缺 N 条"） | DOC | 删成员必须**重算数字**，否则文档自证矛盾 |
| `docs/PITFALLS.md:914` | AIS 的处置建议把 `Gemini-3.8-Flash` 当替代模型 | DOC | **必须改写**，否则文档指引用户去找一个已下线的模型 |
| `docs/PITFALLS.md:760,851`、`TROUBLESHOOTING.md:649`、`REVIEW-2026-11-10.md:38` | 一句话里同时含 AIS 与 G38 | DOC | 只摘 G38 半句，保留 AIS 事迹 |
| `docs/ROUTING-POLICY.md:71`、`docs/REVIEW-2026-11-10.md:131` | 通用缺陷（单跳链沉默即自锁）拿它当唯一案例 | DOC | 改成通用描述，别把缺陷证据删掉 |
| `docs/BENCHMARKS.md:80,119` | 外部榜单（antigravity）同名型号 | DOC | 与仓内模型无关，**不要删** |
| `PROGRESS.md` 25 行 / `CHANGELOG.md` 13 行 / `evidence/*` 100 行 | 历史流水与过程分片（含本轮并行的 `agent-gemini38-memory.md` 22 行） | OTHER | **不要动**：`CHANGELOG.md:95` 记的"回退步骤"就是本次操作清单，PROGRESS 是拆族因果的唯一原始记录 |
| `~/.zcode/v2/*` | 已重生成 | — | 不要再手改（见 0.1），手改会被下一次 `--apply` 覆盖 |

### 0.3 还剩一件"没做也不影响"的事

若要给"这个名字永远不能复活"再加一道本机兜底，可在读真机 alias map 的用例里加 `assertNotIn("Gemini-3.8-Flash", alias_models)`。
注意那条测试读的是**本机** `~/.zcode/v2/model-alias-map.json`，换机器会 skip —— 只适合本机守门，不适合当 CI 唯一依据。

---

## 1. 口径：三个"同名不同物"，先分清再谈删

| 代号 | 是什么 | 位置 | 能不能删 |
|---|---|---|---|
| **G38** | 独立模型 `Gemini-3.8-Flash`：HJ（哈基米 gemai.cc）渠道、同站三跳 `[满血A]gemini-3.8-flash → 3.7 → 3.6`、价 0.05 | `tools/model_alias.py` 四张表 + catalog 三条目 + live alias map | **本次删除目标** |
| **AIS** | 模型 `Gemini-AIS`：GM（catiecli）渠道 7 个 `ais-gemini-*` 跳，链首正是 `ais-gemini-3.8-flash` | `ABBR` `:409`、`MAIN_ORDER` `:169-175`、`GM_PRICES` `:118` … | **不能删**，删了 Gemini-AIS 消失 |
| **WB38** | WB 面板目录里的 `global:gemini-3.8-flash`，显示名也叫 `Gemini-3.8-Flash` | 只在快照 `evidence/wb_panel_models.json`、`providers/workbuddy/archive/wb_model_status.json:68` | 仓内无配置引用；删 HJ 条目**不影响**它，用户仍可能在 WB 面板看到同名字样 |

**为什么必须分清**：正则 `3\.8[-_ ]?flash` 会同时命中 `[满血A]gemini-3.8-flash`（G38）和 `ais-gemini-3.8-flash`（AIS）。
两者只差 `ais-` 四个字符，删错一处就是"Gemini-AIS 少一跳 → 整条链换首跳"。

**第二个坑：G38 不是一个上游 id，是三个。** `:111-113` 三行价目、`:159-161` 三行主序、`:267-269` 三行跳序、`:416-418` 三行别名，
其中 **3.7 / 3.6 那 6 行不含 "3.8" 字样、正则抓不到**，但它们是同一个删除单元。只删 3.8 那三行会得到：
3.7 变成链首、显示名仍是 `Gemini-3.8-Flash`（`:417-418` 还在）—— 名字没消失、模型没消失，只是内容换成了 3.7，最难排查的一种"删不干净"。

**第三个事实（决定优先级）**：G38 当前**已不可用**——`:103-107` 注释记录 `[福利]` 档 2026-11-11 起 `model_not_found`（"No available channel for model"），
主力档已换 `[满血A]`。catalog 三条目里的 `base` 仍写 `[福利]gemini-3.8-flash`（陈旧），与代码的 `[满血A]` 不一致。

---

## 2. 逐条清单（每条带"删了会不会牵连别的模型"判断）

分类取值：`CONFIG_MODEL_ENTRY` 模型目录/列表条目 · `CONFIG_ALIAS` 别名/映射 · `CONFIG_CHANNEL` 渠道/上游/跳序参数 · `CODE_LOGIC` 代码里按模型名分支（含源码内注释）· `TEST` · `DOC` · `OTHER`

> 说明：源码内**注释**按 `CODE_LOGIC` 记 —— 它们记录"为什么这么写"，删代码不同步删注释，下一个人会照着假注释改。

### 2.1 `tools/model_alias.py`（G38 22 行 + 同族连带 4 行；**删除核心**）

| 位置 | 原文（截断） | 分类 | 判断：删了牵连谁 |
|---|---|---|---|
| tools/model_alias.py:95 | `# 哈基米（gemai.cc）福利通道：网页售卖站的 \`[福利]gemini-3.8-flash\` 是独立中转站上` | CODE_LOGIC | 纯注释，删了零影响；但它解释"为什么 id 带中文方括号不改写"，属设计理由，建议随代码一起改写成历史说明 |
| tools/model_alias.py:100 | `# Gemini-AIS 链里的一跳，而是独立模型 Gemini-3.8-Flash（见 ABBR 与 MAIN_ORDER）。` | CODE_LOGIC | 同上，纯注释；这句是"拆族"的唯一文字依据，删了后人会以为 HJ 还在 AIS 链里 |
| tools/model_alias.py:111 | `"[满血A]gemini-3.8-flash": 0.05,` | CONFIG_MODEL_ENTRY | **总闸**。`price_of` 查不到价 → 该跳被丢弃（`:92` 注释）；删这行模型就少一跳。不影响 AIS（AIS 价在 `GM_PRICES` `:118`）。**必须与 :112-113 一起删** |
| tools/model_alias.py:112-113（正则未命中，同族连带） | `"[满血A]gemini-3.7-flash": 0.05,` / `"[满血A]gemini-3.6-flash": 0.05,` | CONFIG_MODEL_ENTRY | 只删 3.8 会留下 3.7/3.6 自成两族、显示名退化为自动缩写 → 选择器里凭空多出两行 |
| tools/model_alias.py:154 | `# 哈基米档（HJ 渠道）2026-11-10 拆成独立模型 Gemini-3.8-Flash。` | CODE_LOGIC | 注释；同时解释"压在整个 chat:gem:* 之前"的用户口径，删代码后应改写为历史 |
| tools/model_alias.py:159 | `"chat:hjm:[满血A]gemini-3.8-flash",` | CONFIG_MODEL_ENTRY | 主力组顺序 + 点名候选的唯一权威；删 → 不再出现在 `zcode-main` 列表。`MAIN_IDS` 自动收缩，不影响其它 id。**与 :160-161 同删** |
| tools/model_alias.py:160-161（连带） | `"chat:hjm:[满血A]gemini-3.7-flash",` / `"…3.6-flash",` | CONFIG_MODEL_ENTRY | 若保留，`whitelist_items` 会让它们继续以 `Gemini-3.8-Flash` 之名进主力组 |
| tools/model_alias.py:264 | `# 2026-11-11 起 Gemini-3.8-Flash 是 HJ 同站三跳，必须显式写 0/1/2，` | CODE_LOGIC | 注释；这条同时说明"不写会并列按字符串序、链首变 3.6"，删代码时连同删 |
| tools/model_alias.py:267 | `"[满血A]gemini-3.8-flash": 0,` | CONFIG_CHANNEL | 跳序表；**删了不牵连 AIS**（AIS 在 `:270` 另有自己的 0）。但若保留 3.7/3.6（:268-269）而不删，3.7 自动成为链首 → 见 §1 第二个坑 |
| tools/model_alias.py:268-269（连带） | `"[满血A]gemini-3.7-flash": 1,` / `"…3.6-flash": 2,` | CONFIG_CHANNEL | 同族，必须同删；留着且删了 3.8 时仍是"模型还在"的状态 |
| tools/model_alias.py:410 | `# 哈基米档 2026-11-10 拆成独立族：显示名 Gemini-3.8-Flash（HJ 渠道）。` | CODE_LOGIC | 注释；解释"为什么从 AIS 摘出来"，是拆族决策的留存，建议改写不直删 |
| tools/model_alias.py:414 | `# 显示名仍是 Gemini-3.8-Flash（链首 3.8 持有名字，跳序 3.8 → 3.7 → 3.6）。` | CODE_LOGIC | 注释 |
| tools/model_alias.py:416 | `"gemini-3.8-flash": "Gemini-3.8-Flash",` | CONFIG_ALIAS | 名字主人。删 → 该 id 退回自动缩写（`abbreviate` `:1150` 会先剥 `[满血A]` 前缀）。**与 AIS 的 `:409` 完全独立**，互不影响 |
| tools/model_alias.py:417 | `"gemini-3.7-flash": "Gemini-3.8-Flash",` | CONFIG_ALIAS | 只删这行 → 3.7 以 `Gemini-3.7-Flash` 独立成活，模型没删掉 |
| tools/model_alias.py:418 | `"gemini-3.6-flash": "Gemini-3.8-Flash",` | CONFIG_ALIAS | 同上，3.6 独立成活 |
| tools/model_alias.py:491 | `# 自指形式 "Gemini-3.8-Flash" -> "Gemini-3.8-Flash"），改名后旧 target 不再是` | CONFIG_ALIAS | 描述 `NAME_RENAMES` 的自指过滤；删了无运行时影响，但这段逻辑是全仓"删模型不留脏 legacy"的保险，**代码必须留** |
| tools/model_alias.py:494 | `# 2026-11-10：原来这里有一条 "Gemini-3.8-Flash" -> "Gemini-AIS"。哈基米福利档拆出来` | CONFIG_ALIAS | 历史注释；**警告价值高**：若把它重新写回 `NAME_RENAMES`，老会话点 `Gemini-3.8-Flash` 会被解析到 `Gemini-AIS`（等于把 3.8 的会话导到另一家的模型） |
| tools/model_alias.py:683 | `"Gemini-3.8-Flash",` （`EMPTY_ALLOWED` 内） | CONFIG_ALIAS | 空档位白名单。删 → 每日 `drifted_efforts` 少一条豁免；模型消失后该条变死数据但无害。**不牵连 AIS**（`:682` 是另一条） |
| tools/model_alias.py:1155 | `# 而 \`[满血A]gemini-3.8-flash\` 这种 id 里的大写 A 在 .lower() 之后` | CODE_LOGIC | 注释；解释"去前缀"规则，**规则本身不能删**，否则显示名变 `A-gemini-3.8-Flash` |
| tools/model_alias.py:1168 | `# 不去掉的话显示名会变成 "A-gemini-3.8-Flash"，同一型号被拆成一堆名字。` | CODE_LOGIC | 注释；同上 |
| tools/model_alias.py:1368 | `# chat:hjm:[满血A]gemini-3.8-flash 走到这里。不写前缀会落到末尾 OC 兜底，` | CODE_LOGIC | `hjm:` 分支（`:1366-1381`）本体不含型号名，删模型**不用动分支**；分支删不删是"HJ 渠道整体退役"的决定 |
| tools/model_alias.py:2580 | `# 给了一个新模型，例如 2026-11-10 拆出来的 Gemini-3.8-Flash）。Resolve 先查` | CODE_LOGIC | 注释；描述 legacy 同名清理（`:2582-2583`），逻辑必须留 |
| tools/model_alias.py:2584-2585 | `# 显示名改名兼容（NAME_RENAMES）：旧名的自指条目（"Gemini-3.8-Flash" -> …` | CODE_LOGIC | 注释；这两行解释了 `:2596-2599` 的 `setdefault` 为何不够（两轮 `--apply` 实测过），是高价值历史 |
| tools/model_alias.py:2590 | `# （"Gemini-3.8-Flash" -> "Gemini-3.8-Flash"），key 已存在时 setdefault` | CODE_LOGIC | 注释；同上 |

### 2.2 `catalog/`（G38 16 行，三条目）

| 位置 | 原文（截断） | 分类 | 判断：删了牵连谁 |
|---|---|---|---|
| catalog/upstream_caps.json:52 | `"display": "Gemini-3.8-Flash",` | CONFIG_MODEL_ENTRY | 快照条目 `:51-68` 的键；`merge_evidence` 按 display 匹配（`tools/caps_upstream.py:263-267`），删掉后残留的 evidence 条目会 `continue` 跳过 —— **不会复活** |
| catalog/upstream_caps.json:54 | `"base": "[福利]gemini-3.8-flash",` | CONFIG_MODEL_ENTRY | 陈旧值：代码用 `[满血A]`。删条目前别拿它当"当前上游 id"依据 |
| catalog/upstream_caps.json:60 | `"context_window": "evidence:vendor-doc-gemini-3.8-flash-limits",` | CONFIG_MODEL_ENTRY | 字段来源标签，纯字符串、无注册表校验；**与 Gemini-AIS 条目共用同源标签**，见下行 |
| catalog/upstream_caps.json:61 | `"max_output_tokens": "evidence:vendor-doc-gemini-3.8-flash-limits",` | CONFIG_MODEL_ENTRY | 同上 |
| catalog/upstream_caps.json:62 | `"supports_tool_call": "evidence:vendor-doc-gemini-3.8-flash-tools",` | CONFIG_MODEL_ENTRY | 同源标签；**AIS 条目 :80 用的是同一个字符串** —— 这行可删（属 G38 条目），但那行不能删 |
| **catalog/upstream_caps.json:80** | `"supports_tool_call": "evidence:vendor-doc-gemini-3.8-flash-tools",` | CONFIG_MODEL_ENTRY | **⚠ 这是 Gemini-AIS 条目（:69-95）的行，不是 G38 的**。名字里带 3.8-flash 是因为同代文档同源；删它 = AIS 丢 tool 能力来源 |
| **catalog/upstream_caps.json:81** | `"supports_image": "evidence:vendor-doc-gemini-3.8-flash-modalities"` | CONFIG_MODEL_ENTRY | **⚠ 同属 Gemini-AIS**，删了 AIS 丢 image 来源 |
| catalog/upstream_caps_evidence.json:6 | `"display": "Gemini-3.8-Flash",` | CONFIG_MODEL_ENTRY | 取证覆盖层条目 `:5-21`；删掉不影响 AIS 的 `:22-34` 条目。残留也无害（`merge_evidence` 跳过未知 display） |
| catalog/upstream_caps_evidence.json:8 | `"base": "[福利]gemini-3.8-flash",` | CONFIG_MODEL_ENTRY | 同陈旧 base |
| catalog/upstream_caps_evidence.json:14 | `"context_window": "evidence:vendor-doc-gemini-3.8-flash-limits",` | CONFIG_MODEL_ENTRY | 纯标签 |
| catalog/upstream_caps_evidence.json:15 | `"max_output_tokens": "evidence:vendor-doc-gemini-3.8-flash-limits",` | CONFIG_MODEL_ENTRY | 纯标签 |
| catalog/upstream_caps_evidence.json:16 | `"supports_tool_call": "evidence:vendor-doc-gemini-3.8-flash-tools",` | CONFIG_MODEL_ENTRY | 纯标签；**与 AIS 条目 :33 同名标签，删除时只删 G38 段落里的那一处** |
| **catalog/upstream_caps_evidence.json:33** | `"supports_tool_call": "evidence:vendor-doc-gemini-3.8-flash-tools",` | CONFIG_MODEL_ENTRY | **⚠ 属 Gemini-AIS 条目** |
| **catalog/upstream_caps_evidence.json:34** | `"supports_image": "evidence:vendor-doc-gemini-3.8-flash-modalities"` | CONFIG_MODEL_ENTRY | **⚠ 属 Gemini-AIS 条目** |
| catalog/model_caps.json:91 | `"display": "Gemini-3.8-Flash",` | CONFIG_MODEL_ENTRY | 推导条目 `:90-145`（ctx 1048576 / max 65536 / reasoning 四档 / thinking_budget 0/1024/4096/16384）；AIS 条目 `:146-159` 独立 |
| catalog/model_caps.json:92 | `"base_model": "[福利]gemini-3.8-flash",` | CONFIG_MODEL_ENTRY | 同陈旧 base；`provenance.hops` 只有一条 HJ main |

**这张表最危险的一处**：`vendor-doc-gemini-3.8-flash-*` 这组取证标签被 **G38 与 AIS 两个条目共用**（`:62/:80` 与 `:16/:33`）。
按"代码里出现的字符串全局替换"的方式清理，会把 AIS 的能力来源一起抹掉。删时必须按 **条目边界**（`:51-68` / `:69-95`）删，不能按字符串删。

### 2.3 `tests/`（G38 11 行，3 个文件）

| 位置 | 原文（截断） | 分类 | 判断：删了牵连谁 |
|---|---|---|---|
| tests/test_model_alias_hop_order.py:120 | `# 直接用它」，于是它从 Gemini-AIS 链里摘出来，独立成模型 Gemini-3.8-Flash` | TEST | 注释；整类 `GeminiHopOrderTest`（`:109-137`）以 G38 为被测对象，删模型后这一组用例要整组删 |
| tests/test_model_alias_hop_order.py:125 | `HJ_HOP = "[满血A]gemini-3.8-flash"` | TEST | 同族夹具常量；删 |
| tests/test_model_alias_hop_order.py:126 | `HJ_HOPS = ["[满血A]gemini-3.8-flash", "[满血A]gemini-3.7-flash", "[满血A]gemini-3.6-flash"]` | TEST | 同族夹具；删 |
| tests/test_model_alias_hop_order.py:127 | `HJ_MODEL = "Gemini-3.8-Flash"` | TEST | 同族夹具；删 |
| tests/test_model_alias_hop_order.py:211 | `"主力组顺序：Gemini-3.8-Flash 必须排在 Gemini-AIS 之前",` | TEST | `test_main_order_puts_hajimi_before_ais`（`:204-212`）整条删；**它同时断言 AIS 的 `chat:gem:ais-gemini-3.8-flash` 在表中（`:210`）——删这个用例会一并失去 AIS 主序守卫**，建议把 AIS 那半条迁到别的用例 |
| tests/test_model_alias_hop_order.py:233 | `"磁盘上 Gemini-3.8-Flash 是 HJ 同站三跳（3.8 → 3.7 → 3.6）",` | TEST | `test_on_disk_alias_map_has_split_gemini_models`（`:219-235`）读**真机** `~/.zcode/v2/model-alias-map.json`；删模型必须同批改这条，否则必红。**这就是"删代码"和"重生成 live 配置"必须同一批落地**的原因 |
| tests/test_model_alias_efforts.py:93 | `entries = [_entry("Gemini-AIS", "[福利]gemini-3.8-flash", "gemini-3.8-flash",` | TEST | **属 AIS 夹具**（本节测档位继承）。名字里带 3.8 但断言的模型是 `Gemini-AIS`；不要跟着删 |
| tests/test_dsh_sync_efforts.py:137 | `rules = {("zcode-main", "Gemini-3.8-Flash"): {"optionSpecs": {"reasoningLevel": {` | TEST | 纯内存夹具，与真机无关；删模型后可改名为任意模型，断言逻辑不变 |
| tests/test_dsh_sync_efforts.py:141 | `routes = {"zcode-main": {"models": [{"id": "Gemini-3.8-Flash"}]}}` | TEST | 同夹具；不改也不会红（它不读真机） |
| tests/test_dsh_sync_efforts.py:145 | `rules = {("zcode-main", "Gemini-3.8-Flash"): {"optionSpecs": {"reasoningLevel": {` | TEST | 同夹具 |
| tests/test_dsh_sync_efforts.py:149 | `{"id": "Gemini-3.8-Flash", "reasoningEfforts": {"off": "disabled", "low": "low"}}` | TEST | 同夹具 |

**AIS 侧、绝不能动**：`tests/test_model_alias_hop_order.py:110`（GEMINI_HOPS 七条）、`:210`；
`tests/test_model_alias_probe_filter.py:34/64-68/112-115/127-138/146-153`；`tests/test_model_alias_naming.py:71`；
`tests/test_model_alias_price.py:122`；`tests/test_caps_upstream.py:172-215`；`tests/test_model_caps.py`（2 行 AIS 相关）。

### 2.4 `docs/`（G38 32 行 + 一个整节）

| 位置 | 原文（截断） | 分类 | 判断：删了牵连谁 |
|---|---|---|---|
| docs/MODEL-PROVIDERS.md:688 | `### 4.11.5 跨站同代：\`Gemini-3.8-Flash\`（\`HJ\` 哈基米，主业是独立模型）` | DOC | **整节 `:688-728`（41 行）专属本模型**，节末 `:730` 是 §4.11.6。整节可删或改写为"已退役"；不牵连 AIS |
| docs/MODEL-PROVIDERS.md:529 | `> 跨站兜底（哈基米福利 3.8）已于 2026-11-10 拆成**独立模型 \`Gemini-3.8-Flash\`**、排在它前面，见 §4.11.5。` | DOC | 这句在 **§4.11 Gemini-AIS** 的开头。删掉它只删掉一个指针（安全），但 `:526-534` 是 AIS 章节，改这段要小心别碰 AIS 的描述 |
| docs/MODEL-PROVIDERS.md:572 | `哈基米的 \`[福利]gemini-3.8-flash\` 单独映射成 **\`Gemini-3.8-Flash\`**，自成一条单跳族。` | DOC | 位于 AIS 章节内、讲"分族"的段落（`:570-583`）；这里同时写着"否则 AIS 的 legacy_ids 会继续挂着 hjm:…"，**删了会丢 AIS legacy 卫生的理由** |
| docs/MODEL-PROVIDERS.md:576-578 | `- 主力组顺序由 \`MAIN_ORDER\` 决定：…之前，于是模型列表里 \`Gemini-3.8-Flash\` 压在 \`Gemini-AIS\` 上面（用户 2026-11-10 指定）。` | DOC | 同上段落，讲 AIS 与 G38 的相对位置；删后 AIS 段落仍自洽，但"用户指定顺序"的口径丢失 |
| docs/MODEL-PROVIDERS.md:583 | `否则 AIS 的 \`legacy_ids\` 会继续挂着 \`hjm:[福利]gemini-3.8-flash\`，同一个上游 id 两个 canonical。` | DOC | **这句是 AIS 侧的去重理由**，与 G38 是否删除无关；建议保留 |
| docs/MODEL-PROVIDERS.md:608 | `\`Gemini-3.8-Flash\` 那份仍然只作用于自己。完整口径见 [ROUTING-POLICY.md](ROUTING-POLICY.md)。` | DOC | 讲"按渠道分窗口"；删后 AIS 的窗口口径表述会缺一半对比 |
| docs/MODEL-PROVIDERS.md:695 | `\| 显示名 / 模型 id \| \`Gemini-3.8-Flash\`（连字符风格，与 \`DeepSeek-4.1-Flash\` 一致） \|` | DOC | §4.11.5 表内，随整节删 |
| docs/MODEL-PROVIDERS.md:699 | `\| 上游模型 id \| \`[福利]gemini-3.8-flash\`（原样带方括号与中文前缀，不做改写） \|` | DOC | 同上 |
| docs/MODEL-PROVIDERS.md:700 | `\| 模型名前缀 \| \`hjm:\`（\`chat:hjm:[福利]gemini-3.8-flash\`）…也是它 \`legacy_ids\` 的唯一一条 \|` | DOC | 同上；这条是 `hjm:` 前缀的唯一文档出处，若渠道保留要迁到别处 |
| docs/MODEL-PROVIDERS.md:720 | `\`Gemini-3.8-Flash\` 是哈基米单跳（4 秒级出字），\`Gemini-AIS\` 是 catiecli 降级链（现 3 跳）…` | DOC | 同上；这行同时描述 AIS，删的时候留 AIS 半句 |
| docs/PITFALLS.md:760 | `都是这句；模型选择器里 Gemini-AIS 与 Gemini-3.8-Flash 都不见了。` | DOC | **一行同时提到 AIS 与 G38**（同一次事故）。删掉半句会破坏事故复盘完整性；建议只去掉 G38 三字并注明已退役 |
| docs/PITFALLS.md:768 | `另外 Gemini-3.8-Flash 当时走的是 HJ \`[福利]gemini-3.8-flash\`，该档在 gemai.cc 已断供` | DOC | **这条就是"该模型已断供"的现场记录**，价值最高的历史证据之一；建议保留并标注"已随模型移除" |
| docs/PITFALLS.md:830 | `> 哈基米 3.8 已拆成独立模型 \`Gemini-3.8-Flash\`（排在 AIS 前面）。` | DOC | 提示框；随模型删 |
| docs/PITFALLS.md:849 | `- **日志**：沉默告警现在带 \`model=\`（\`[router] https://api.gemai.cc/v1（model=[福利]gemini-3.8-flash）…` | DOC | 这是"告警带模型名"这条通用改进的示例；模型删掉后示例失真 → 换一个别的型号举例，别整行删（那会删掉通用结论） |
| docs/PITFALLS.md:851 | `- **同日第三轮（2026-11-10 20:05）：一个全局窗口套两种脾气，兜底那家被自己的门槛切掉**…\`[福利]gemini-3.8-flash\` 白天 2.5-3.1 秒出首块…` | DOC | 与 AIS 的 45s→12s 事故同段（**同一段落里 AIS 与 HJ 对照**），删 HJ 半句会让 AIS 的对照失去参照物 |
| docs/PITFALLS.md:914 | `- **处置**：写作、需要读文件的任务不要挂 AIS，改用 \`DeepSeek-4.1-Flash\`…或 \`Gemini-3.8-Flash\`；AIS 只留给不调工具的纯对话…` | DOC | **处置建议里 G38 是 AIS 的替代品**。删 G38 后这条 AIS 的处置建议就失效，必须同步改掉，否则用户会照着文档去找一个不存在的模型 |
| docs/PITFALLS.md:915 | `- **证据**：直打 \`127.0.0.1:7871\` \`model=Gemini-AIS\` 的实测矩阵…` | DOC | 这行主体是 AIS 的证据；只含邻近上下文，删前先确认是否真含 G38 字样（本行命中的是 AIS 段落的延续） |
| docs/CAPABILITY-AUDIT.md:83 | `\| Gemini-3.8-Flash \| 主力 \| 1000000 \| 128000 \| 否 \| 无 \| 兜底 \|` | DOC | 能力表一行，随模型删；表结构不变，AIS 行独立 |
| docs/CAPABILITY-AUDIT.md:125 | `20 个模型里符合「三件套全中」的：\`Gemini-3.8-Flash\`、\`Gemini-AIS\`…**11 个**…` | DOC | **计数句**：删掉一个成员，11 个变 10 个、20 个变 19 个 → 整句要重算，否则文档自相矛盾 |
| docs/CAPABILITY-AUDIT.md:145 | `\| Gemini-3.8-Flash / Gemini-AIS \| 上游目录没有该字段…\| 兜底值，不是真值 \|` | DOC | **一行合并写两个模型**，删 G38 要改写为只剩 AIS |
| docs/CAPABILITY-AUDIT.md:155 | `\| Gemini-3.8-Flash \| 上游目录无该字段 \| 128000 \| 无从判断 \| 兜底值，不是真值 \|` | DOC | 表行，随模型删 |
| docs/CAPABILITY-AUDIT.md:163 | `…\`Gemini-3.8-Flash\`（WB 侧也支持）。` | DOC | 计数/列举句，同 `:125` 要重算 |
| docs/CAPABILITY-AUDIT.md:201 | `\| C 无来源 \| 5 \| Gemini-3.8-Flash、Gemini-AIS、Conatus…\| 上游目录里根本没有 effort 字段…` | DOC | **"5 个"计数行**，删 G38 要改成 4 |
| docs/CAPABILITY-AUDIT.md:344 | `\| Gemini-3.8-Flash \| 1048576 \| 65536 \| ✓ \| ✓ \| 官方 3.8 Flash 文档 + HJ 内联 PNG 实测 \|` | DOC | 表行；**这条是 catalog 三条目 ctx/max 的口径出处**，删 catalog 后再删它才一致 |
| docs/CAPABILITY-AUDIT.md:376 | `\| Gemini-3.8-Flash（HJ 单跳） \| 官方 Token limits / Modalities 页；内联 2×2 PNG 返回文本… \|` | DOC | 取证表行；**AIS 的 tool/img 证据正是引用这里**，删 G38 后 AIS 的取证出处会指向不存在章节 → 建议改写为"同代文档（3.8 Flash）"保留出处 |
| docs/TROUBLESHOOTING.md:589 | `> \`Gemini-3.8-Flash\`（单跳 \`HJ\`）。本节及 §18.1-§18.3 里出现的 \`(x/8)\` 与 HJ 跳都是当晚的历史日志，` | DOC | 章节导语；删掉后 §18 的"历史日志"上下文消失，读者会把 `(x/8)` 当成现状 → 应改写而非直删 |
| docs/TROUBLESHOOTING.md:633 | `**判据**：日志里 \`（channel=HJ model=[福利]gemini-3.8-flash）上游 12s 内没给响应头\`…` | DOC | 排障判据示例；通用结论（"窗口卡在抖动边缘"）要留，示例换型号 |
| docs/TROUBLESHOOTING.md:649 | `…模型是 \`Gemini-3.8-Flash\`（HJ 单跳）和 \`Gemini-AIS\`（GM 链，11-11 11:03 起 3 跳）。` | DOC | **同句含 AIS**，只删 G38 一半 |
| docs/ROUTING-POLICY.md:71 | `理由：单跳链冷却一跳 = 把这个模型整体关掉。当天的现场就是 Gemini-3.8-Flash 从「偶尔慢」变成「连片 502」…` | DOC | **路由策略的理由引用了 G38 作案例**；删 G38 后策略本身仍成立（单跳链自锁是通用问题，见 REVIEW:131），建议改为匿名案例 |
| docs/BENCHMARKS.md:80 | `\| 13 \| GEMINI-3.8-FLASH · HIGH \| \`antigravity\` \| 330.39 \| … \| 09-03 \|` | DOC | 外部榜单快照（antigravity 端口径），不是本仓模型配置；**删了不影响任何东西**，但它记录的是同名外部模型，删了会丢"榜上曾有这么个型号"的对照 |
| docs/BENCHMARKS.md:119 | `\| 小说创作 \| GEMINI-3.8-FLASH · HIGH（100.96 / 41.2） \| GEMINI-3.7-FLASH · HIGH（100.00 / 40.81） \| …` | DOC | 同上，榜单排名行 |
| docs/DSH-FIRST.md:68 | `…（缺失：Gemini-3.8-Flash / Gemini-AIS / Beam / …）` | DOC | **计数/列举句**，删 G38 要重算条数与首项 |
| docs/REVIEW-2026-11-10.md:20 | `\| 模型分族 \| 福利 3.8 从 AIS 链里摘出来，独立成 \`Gemini-3.8-Flash\`（单跳 HJ，价 0.05，主力组排在 AIS 前） \| \`58b7ce8\` \|` | DOC | 2026-11-10 复审结论行，带 commit 号；纯历史，删了不影响运行，但会切断"58b7ce8 做了什么"的索引 |
| docs/REVIEW-2026-11-10.md:33 | `\| GM / HJ 渠道接入 \| **生效（全局）** \| \`/health\` 七段 upstream 全 up（gemini / hajimi / opencode / qiniu / qwen / qoder / workbuddy）…\`/v1/models\` 93 条里含 \`hjm:[福利]gemini-3.8-flash\`；实打 \`model=Gemini-3.8-Flash\` → 200、响应头 4395ms \|` | DOC | 渠道接入的生效证据，**HJ 段与其它六个渠道并列**。删 G38 后这段的"实打 200"证据失效，但 `hajimi` 段本身仍可能在 /health 里 → 只删后半句 |
| docs/REVIEW-2026-11-10.md:38 | `\| 模型分族 \| **生效** \| alias map 里 \`Gemini-AIS\` 7 跳全 GM、\`Gemini-3.8-Flash\` 单跳 HJ；\`/v1/models\` 两条都在主力\` | DOC | **同格含 AIS**，删 G38 要留 AIS 那半 |
| docs/REVIEW-2026-11-10.md:51 | `\| 并发对冲 / 竞速 \| \`race.go:306-334\`：≥2 跳 + 流式 + **每跳协议都是 chat**… \| **1 个模型**：\`Gemini-AIS\`。\`Gemini-3.8-Flash\` 只有 1 跳，被「≥2 跳」挡掉 \|` | DOC | **删除安全性的硬证据**：G38 从未参与竞速/对冲，删它不改网关任何调度行为。但这一格是"全仓唯一一个不参与竞速的模型"的结论，删了要补一句"（现已无此例外）" |
| docs/REVIEW-2026-11-10.md:131 | `遗留项。单跳链沉默时 \`markSilence\` 打的是「唯一一跳」…对 \`Gemini-3.8-Flash\` 这种单跳模型等于自锁` | DOC | **一条仍未修的遗留项**（单跳链自锁）。删模型等于"回避"这个缺陷而不是修它 —— 若删，应在 ROUTING-POLICY 留下通用化描述 |
| docs/reports/MODEL-SYNC-20261111-1343.md:36-38,50 | `- \`Gemini-3.8-Flash\` / - 原：HJ:[福利]gemini-3.8-flash@0.05 / - 新：HJ:[满血A]…3.7…3.6` | DOC | 当天同步报告（`[福利]`→`[满血A]` 换档记录）；**这是唯一一处记录"三跳替换"的产物**，纯历史 |
| docs/reports/MODEL-SYNC-20261111-1207.md:26,50 | `\| \`Gemini-3.8-Flash\` \| 主力 \| 0.05 \|` | DOC | 同步报告表行，纯历史 |

**`docs/MODEL-ALIAS.md` / `docs/MODEL-QUICK-REF.md`**：宽口径扫到 12 + 2 行，但**全部是 `Gemini-AIS`**，G38 零命中 —— 不要动。

### 2.5 运行时数据与快照（G38 3 行，非配置）

| 位置 | 原文（截断） | 分类 | 判断：删了牵连谁 |
|---|---|---|---|
| gateways/upstream/workbuddy/data/usage.json:1 | `…"r":"global","u":"5ca3…","m":"gemini-3.8-flash"…`（2 个桶，`s:h:2026-10-20T15`） | OTHER | WB 用量账本历史桶（2026-10-20）。**是账，不是配置**；删模型不需要动它，改了等于伪造历史用量 |
| providers/workbuddy/archive/wb_model_status.json:68 | `"global:gemini-3.8-flash": { "status": "blocked", "http": 503, "detail": "not allowed for user type", …}` | OTHER | 归档探活快照；证明 **WB 侧那条 3.8 早已 blocked**。与 HJ 的 G38 是两个对象，删 HJ 不影响它 |
| evidence/wb_panel_models.json:1 | `…"max_output_tokens":65536,"name":"Gemini-3.8-Flash","only_reasoning":true…` | OTHER | WB 面板目录快照（WB38）。**它的存在说明"面板里还能看到同名模型"**，别把它当 HJ 条目的残留来删 |

### 2.6 历史流水与并行分片（G38 78 + 38 行，聚合）

| 位置 | 条数 | 分类 | 判断 |
|---|---|---|---|
| PROGRESS.md | 25（`:2450,2474,2495,2946,2955,2957,2988,3021,3022,3029,3139,3143,3145,3242,3244,3249,3251,3252,3257,3259,3261,3302,3325,3408,3435`） | OTHER | 全仓唯一进度流水的历史轮次（第二十三轮=拆族、HJ 接入、逐跳取值…）。**禁止改**：它是"为什么拆族"的原始记录，且单写者 |
| CHANGELOG.md | 13（`:42,46,47,48,49,69,73,87,95,112,116,123,131`） | OTHER | 发布历史。`:95` 记着**回退步骤**（"删 HOP_PRIORITY 里 [福利] 那行 + ABBR 对应行 + MAIN_ORDER 里 chat:hjm:…"）—— 本次清理可以直接照它做，是现成的操作清单 |
| evidence/agent-gemini-*.md 等 19 个分片 | 78 | OTHER | 前几轮 Gemini 接入 / 取证 / 合并的**过程快照**，含 `agent-gemini-memory-docs.md`(16)、`agent-runtime.md`(9)、`gemini-merge-result.md`(7)、`agent-gemini-ais-alias.md`(7) 等。删了不影响运行；其中 `evidence/agent-gemini38-memory.md` 是本轮并行分片（`??` 未入库），不认识也不许写 |

### 2.7 仓外 live 真值（**真正生效的地方**，不是仓内文件）

| 位置 | 内容 | 分类 | 判断 |
|---|---|---|---|
| `~/.zcode/v2/provider_config.json:26,31` | 两个 `personalModelIds` / `modelOrder` 数组里各一条 `"Gemini-3.8-Flash"` | CONFIG_MODEL_ENTRY | **客户端模型列表就靠这两行**。仓内删干净但这里还在 → 选择器照样列出、点了没模型可路由 |
| `~/.zcode/v2/provider_config.json:140` | `"modelId": "Gemini-3.8-Flash"` 的 `modelRule`（contextWindow 1048576 / maxOutputTokens 65536 / reasoning 四档 + thinking_budget / providerId `opencode-go-chat`） | CONFIG_MODEL_ENTRY | 档位配置；`:167-174` 是 `Gemini-AIS` 的同类规则，两条相邻，**手删极易误删 AIS 那条** |
| `~/.zcode/v2/model-alias-map.json:68-115` | G38 条目：`:71` upstream `[满血A]gemini-3.8-flash`、`:72` base_model `[满血A]gemini-3.6-flash`、`:75` original `hjm:[满血A]gemini-3.8-flash`、`:79-80` chain 后两跳、`:112-114` legacy 三条 | CONFIG_ALIAS | 运行时别名表；`:118-175` 紧随其后的是 `Gemini-AIS`（`:121` `ais-gemini-3.8-flash`） |
| `~/.zcode/v2/model-alias-map.json:898,906-908` | legacy 总表：`:906-908` 三条 `hjm:[满血A]gemini-3.8/3.7/3.6-flash → Gemini-3.8-Flash`（`:898-904` 是 AIS 的七条 `gem:ais-*`） | CONFIG_ALIAS | **不要手删**。`model_alias.py` 重生成时会：带前缀且对不上任何跳的 legacy 被 `:2568-2577` 清掉；裸名留给历史解析 |

---

## 3. 三段汇总（**删除前的计划视图**，15:0x 复核显示 ①② 已基本落地；当前残留与证据见 §0）

### ① 直接可删（不牵连任何别的模型）

| # | 对象 | 位置 | 备注 |
|---|---|---|---|
| 1 | HJ 价目 3 行 | `tools/model_alias.py:111-113` | 只删 `:111` 会留 3.7/3.6 成族 |
| 2 | 主力组顺序 3 行 | `tools/model_alias.py:159-161` | `MAIN_IDS` 自动收缩 |
| 3 | 跳序 3 行 | `tools/model_alias.py:267-269` | 不留 3.7 当链首 |
| 4 | 别名 3 行 | `tools/model_alias.py:416-418` | 与 AIS 的 `:409` 无耦合 |
| 5 | 空档豁免 1 行 | `tools/model_alias.py:683` | 模型没了它就是死条目 |
| 6 | 机制注释 | `tools/model_alias.py:95,100,154,264,410,414,491,494,1155,1168,1368,2580,2584,2585,2590` | 建议改写成"2026-11-11 已退役"而不是直删，避免后人照假注释改 |
| 7 | catalog 三条目 | `catalog/upstream_caps.json:51-68`、`catalog/upstream_caps_evidence.json:5-21`、`catalog/model_caps.json:90-145` | **按条目边界删，不按字符串删**（见 ②） |
| 8 | 专属文档整节 | `docs/MODEL-PROVIDERS.md:688-728`（§4.11.5） | 唯一整节专属本模型 |
| 9 | 纯表行/计数行 | `docs/CAPABILITY-AUDIT.md:83,155`、`docs/BENCHMARKS.md:80,119`、`docs/reports/*` 6 行 | 计数句（`:125,163,201`、`DSH-FIRST:68`）删后必须重算数字 |
| 10 | live 两文件 | 由 `python tools/model_alias.py --apply` 重生成，**不要手改** | 手改会被下一次同步覆盖，且容易误删相邻的 AIS 条目 |

### ② 改了会影响别处（影响面写清）

| 位置 | 影响面 | 处理建议 |
|---|---|---|
| **`catalog/upstream_caps.json:80-81`、`catalog/upstream_caps_evidence.json:33-34`** | **看起来是 G38 的"3.8-flash"取证标签，实际属于 `Gemini-AIS` 条目**。删了 AIS 的 tool / image 能力来源消失（`field_sources` 变悬空字符串） | 只删 G38 条目内（`:60-63` / `:14-17`）的那几处；标签本身在 AIS 段落保留 |
| `tools/model_alias.py:409`（ABBR）、`:169-175`（MAIN_ORDER 七条 `gem:`）、`:270-276`（HOP_PRIORITY）、`:118`（GM_PRICES）、`:288`（CHAIN_CAP） | 全是 `Gemini-AIS` 的登记点。删一条 = AIS 少一跳或改变跳序 | 一个字都别动 |
| `docs/PITFALLS.md:914` | 这是 **AIS 的处置建议**，把 G38 当"替代模型"。删 G38 后该建议指向不存在的模型 | 必须同批改写（换成 `DeepSeek-4.1-Flash` 等现存项） |
| `docs/CAPABILITY-AUDIT.md:125,163,201`、`docs/DSH-FIRST.md:68` | 计数句（"11 个 / 5 个 / 20 个"）。删成员不重算 → 文档自相矛盾，`check-docs.py` 不一定抓得住 | 同批重算并复核 |
| `docs/PITFALLS.md:760,851`、`docs/TROUBLESHOOTING.md:649`、`docs/REVIEW-2026-11-10.md:38` | **一句话里同时有 AIS 与 G38**（同一次事故的对照） | 只摘 G38 半句，保留 AIS 事迹 |
| `docs/REVIEW-2026-11-10.md:131`、`docs/ROUTING-POLICY.md:71` | 记录的是**通用缺陷**（单跳链沉默即自锁），G38 只是案例。删案例 = 抹掉缺陷存在过的证据 | 改为通用描述，不要把段落删掉 |
| `docs/PITFALLS.md` 整体 | **当前已被并行会话修改**（`git status: M docs/PITFALLS.md`） | 单写者原则：动手前先确认该会话已收工，否则必冲突 |
| `tests/test_model_alias_hop_order.py:204-212` | 该用例一半断言 G38、一半断言 AIS（`:210`） | 删用例前把 AIS 那半条迁到别的用例 |
| `tools/check-project.py` 若要一起退役 HJ 渠道 | 需同时改 5 处：`zgate.json` 的 `upstreams`+`channelPolicy`、`keys.go` 的 `Channels`+`Set` 字段、`router.go` 的 `applyHeaders`；且 `:115` 的字面断言 `case "WB", "QD", "QW", "QN", "GM", "HJ"` 与 `:69` 的"6 个 upstreams = 旧口径"会**立刻变红** | **只删模型时渠道全保留 = 零门禁变化**（推荐）。渠道退役是另一个任务 |

### ③ 需要跑测试验证（指出具体文件）

| 文件 | 为什么 | 期望 |
|---|---|---|
| `tests/test_model_alias_hop_order.py` | **必须改**：`:109-137` 夹具、`:171-177` `test_hajimi_is_standalone_same_site_chain`、`:187-191` HJ 跳序断言、`:204-212` 主序、`:219-235` **读真机 alias map** 的磁盘守卫 | 改完 `Ran N tests ... OK`；`:219-235` 与 live 重生成必须同批 |
| `tests/test_model_alias_efforts.py` | 回归底线（`:92-103` 夹具属 AIS，不该变） | 14 项 ok |
| `tests/test_model_alias_probe_filter.py` | 主力组保留逻辑，夹具默认 `ais-gemini-3.8-flash` | 11 项 ok |
| `tests/test_model_alias_naming.py` | `:71` 断言 `chat:gem:ais-gemini-3.8-flash` 在 `MAIN_ORDER` | 7 项 ok |
| `tests/test_model_alias_price.py` | 同价/0 价拆族规则（与"价不能写 0.0"直接相关） | 15 项 ok |
| `tests/test_dsh_sync_efforts.py` | 档位继承夹具用了 G38 作 key | 改夹具后 ok |
| `tests/test_caps_upstream.py`、`tests/test_model_caps.py` | catalog 条目改动后的消费者 | ok |
| `tools/check-project.py` / `tools/check-docs.py` / `tools/check-secrets.py` | 项目门禁、文档链接、密钥扫描 | exit 0 |
| `python tools/model_alias.py --check` | 漂移守门；删模型后 `EMPTY_ALLOWED` 少一条不应报警 | 无漂移 |
| `python tools/dsh_sync.py --check` | 档位投影守门 | 无漂移 |

**基线（本轮实跑，供回归对照）**：`python -B -m unittest discover -s tests -p <每个 test_model_alias_*.py> -v` → hop_order 11 ok / naming 7 ok / probe_filter 11 ok / efforts 14 ok / price 15 ok，共 **58 项全 ok**。
（`-B` 是为了不生成 `__pycache__`；注意直接用 `python -m unittest tests.test_x` 会 ModuleNotFoundError，必须用 `discover -s tests`。）

---

## 4. 能力位 / 分组判断：它到底是"什么位子上的模型"

| 位子 | 是/否 | 证据 | 删掉后的影响 |
|---|---|---|---|
| **主力组**（`zcode-main` / provider `opencode-go-chat`） | **是** | `MAIN_ORDER:159-161` 排在整套 `chat:gem:*` 之前；live `provider_config.json:26,31` 的 `personalModelIds`/`modelOrder` 里有它 | 主力组少一条。因它排在 AIS **上面**，删后 `Gemini-AIS` 自动上移到第一位 —— 这是唯一可感知的序位变化 |
| **备用组 / 兜底组** | **否** | 拆分前它是 AIS 链的链内兜底；2026-11-10 拆出后不再进任何 `fallbacks` | 无影响。**它不在任何其它模型的 fallback 链里**，这是本次删除风险低的根本原因 |
| **自身的降级链** | 是（同站 3 跳） | `chain: HJ [满血A]3.8 → 3.7 → 3.6`，`HOP_PRIORITY` 0/1/2 | 跨站无备胎：HJ 挂了就整条死。这也是 ROUTING-POLICY 里"单跳链自锁"那条遗留项的由来 |
| **限流 / 冷却表** | 否（走渠道策略） | `channelPolicy.HJ` 只剩 `{"headerTimeoutSec": -1}`；无独立 rate-limit 条目 | 删模型不动 `zgate.json`；HJ 渠道若变零模型，该渠道策略成为死配置（无害） |
| **路由链 / 跳序表** | 是 | `HOP_PRIORITY:267-269`、`CHANNEL_RANK["HJ"]=1` | 只影响自己这一族 |
| **Channel 前缀路由** | 是 | `hjm:` 前缀（`PREFIXES:1221`、分支 `:1366-1381`） | 删模型不必删前缀；渠道退役才删 |
| **定价 / 账单位** | 是 | `HJ_PRICES` 0.05/跳（AIS 是 0.11/次） | 删后无残留影响；**注意不能把价写成 0.0**（`:109-110` 的拆族规则） |
| **能力位（caps）** | 是 | ctx 1048576 / max_out 65536 / tool ✓ / img ✓ / reasoning `disabled,low,medium,high` + `thinking_budget` 0/1024/4096/16384 | 三张 catalog 表各少一条 |
| **客户端选择器位** | 是 | live `provider_config.json` 的 `modelRule:140` + 两个 id 数组 + alias map | 必须靠 `--apply` 重生成，手删易误伤 AIS（`:167-174`） |
| **WB 面板位（另一个对象）** | 是（同名） | `evidence/wb_panel_models.json`（`global:gemini-3.8-flash`，`only_reasoning:true`）、archive 里 503 `not allowed for user type` | 删 HJ 的 G38 **不会**让这个消失 |

---

## 5. 复现命令（全部只读，PowerShell 原生）

```powershell
Set-Location F:\Project\ModelBus
# 窄口径：Gemini 专属（315 行 / 49 文件）
Get-ChildItem -Recurse -File -Include *.json,*.py,*.ps1,*.psm1,*.vbs,*.cmd,*.yml,*.yaml,*.toml,*.md,*.txt |
  Where-Object { $_.FullName -notmatch '\.git\\|node_modules\\|__pycache__\\|\.work\\|\.log$' } |
  Select-String -Pattern 'gemini\s*[-_ ]?\s*3[._]8' |
  Group-Object Path | Sort-Object Count -Descending

# 区分 G38 与 AIS
Select-String -Path tools\model_alias.py -Pattern 'gemini\s*[-_ ]?\s*3[._]8' | ForEach-Object { $_.LineNumber.ToString() + ' | ' + $_.Line.Trim() }

# 仓外 live
Select-String -Path "$env:USERPROFILE\.zcode\v2\provider_config.json","$env:USERPROFILE\.zcode\v2\model-alias-map.json" -Pattern 'Gemini-3\.8-Flash|\[满血A\]gemini-3\.8'
```

**检索口径提醒**：本机无 ripgrep，`rg` 不可用，一律 `Select-String`；宽口径（`3\.8.*flash`）会带出 Qwen 家族
（`Qwen3.8-Flash` / `Qwen-3.8-Max` / `qwen3.8-flash-next` 等），**与 Gemini 无关**，统计时必须剔掉：宽 619 行 / 104 文件 → 窄 315 行 / 49 文件。

---

## 6. 本次盘点的边界

- 只读：未改 `provider_config.json`、`docs/`、`tests/`、`PROGRESS.md`、任何配置与脚本；未跑 git 写操作、未重启网关
- 未探测 HJ 上游当前状态（`api.gemai.cc` 是否需要联网/凭据）："已断供"结论来自代码注释 `tools/model_alias.py:103-107` 与 `docs/PITFALLS.md:768`，不是本轮实测
- `.work/` 下的 6 个备份（`provider_config.bak-*`、`candidate*.json`）按任务要求排除，未计入
- `gateways/upstream/qoder/`、`providers/opencode-go/`、`providers/qwen/`、`third-party/zcode/zcode-builtin.json` 的 gemini 命中经逐条核对**均与 3.8-Flash 无关**（是 `gemini-3.5-flash`、`gemini-4-argon`、Qwen3.8 等）
- `HJ` 渠道凭据 `providers/hajimi/.env.local`（143 B）存在但内容未读取；若渠道退役需单独处置，**不在本次范围**
