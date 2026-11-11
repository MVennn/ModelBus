# Gemini-3.8-Flash 记忆层 / 规则层盘点（只读）

> 结论：真正要动的 10 处——3 处整段/整行删除、4 处改行内表述、3 处改写但保留机制；其余 12 处命中是 Qwen3.8-Flash、AIS 链首跳、第三方目录清单、历史实测快照的误命中与存档，一律不动。

---

- 盘点时间：2026-11-11 15:00 前后（本地 Asia/Shanghai）
- 关键词：`gemini[-_ ]?3[._]8`、`3\.8[-_ ]?flash`、`3\.8flash`、`gemini3\.8`，外加 `HJ 单跳` / `HJ 渠道` / `hjm:` / `福利`（该模型绑定的路由表述）
- 只读纪律：未修改 `~/.mnemon`、`~/.dsh`、`~/.zcode` 下任何一个文件；本文件是本次唯一写入。
- 判定口径：**DELETE_ENTIRE** = 整条/整行/整节只讲这个模型，可删；**EDIT_LINE** = 行内提到，改成不含该模型的表述即可；**KEEP_REWRITE** = 讲的是渠道/路由机制、模型只是举例，换例子不能删；**KEEP** = 无关误命中或历史存档。
- 重要前提：`ais-gemini-3.8-flash` 是 **Gemini-AIS** 七跳链的链首跳（另一个模型），不是本次要删的 `Gemini-3.8-Flash`。凡命中这一串的，一律不在删除范围。

## 0. 总表

| 载体 | 命中行/条 | DELETE_ENTIRE | EDIT_LINE | KEEP_REWRITE | KEEP |
| --- | --- | --- | --- | --- | --- |
| Documents（active 45 篇） | 18 行 / 8 篇（另补上下文 3 行） | 2 | 2 | 2 | 12 |
| 热条目（MEMORY.md + memories.json） | 1 条（两载体同文） | 0 | 0 | 1 | 0 |
| 规则文档 `~/.dsh`（AGENTS / prompt-inject / skills / procedures / cordis） | 2 行 / 1 文件 | 1 | 0 | 0 | 1 |
| 经验教训库 lessons.json | 3 行 | 0 | 2 | 0 | 1 |
| zcode 历史副本 | 0 | 0 | 0 | 0 | 0 |
| documents/index.json（派生） | 2 行 | 0 | 0 | 0 | 2 |
| **合计（不含派生/备份）** | — | **3** | **4** | **3** | — |

## 1. Documents（`~\.mnemon\documents\active`，45 篇）

### 1.1 全表

| 文件 | 命中行 | 小节 | 处置 |
| --- | --- | --- | --- |
| modelbus-2026-11-06-f32b5c38.md | L4 / L50 / L75 / L105 / L114 | 概览、§1 表、§4 标题、§4 证据 | KEEP（5 行） |
| modelbus-2026-11-10-74a3e530.md | L53 | §2 修掉的三个缺陷 → ③ | EDIT_LINE |
| modelbus-推理档位与别名派生口径-da79c0b9.md | L131 / L133 | 别名派生口径表 | KEEP（2 行） |
| modelbus-gemini-ais-chain-3f6dda94.md | L4 / L22 / L35 / L61（+ §1.1 L43–L45） | 概览、开篇引文、§1 表、§2 七跳表、§1.1 | 混合，见 1.2 |
| modelbus-opencode-go-e56d26ad.md | L39 / L43 / L52 | 额度与价格带 | KEEP（3 行） |
| modelbus-zgate-12s-c90d1859.md | L51 | 响应头超时判据 | KEEP |
| modelbus-zgate-3-2026-11-11-0dc8208e.md | L50 / L52 | §三 实测证据 | KEEP |
| zcodeaimodels-workbuddy-669f6d6a.md | L251 | WorkBuddy 下架判定 | KEEP |

### 1.2 逐条判定（含命中行原文）

#### A1 `modelbus-2026-11-06-f32b5c38.md` — KEEP（误命中，5 行）

命中的全是 **Qwen3.8-Flash**（Qoder 渠道），与 `Gemini-3.8-Flash` 无关：

- L4 `description: "model_alias 静默漏模型的三层成因（裸名去重/缺价剔除/名单命中）、显示名去尾缀口径，以及 Qoder Qwen3.8-Flash 免费窗口关闭的实测证据与回退步骤"`
- L50 `| 裸名去重 | 同型号在不同渠道被当重复丢掉（Qwen3.8-Flash 被 OC 的 messages 条目占位，chat:qoder:Qwen3.8-Flash 补出来也被丢） | whitelist_items() 给条目打 explicit_channel；main 里显式渠道按 (渠道, 裸名) 比对，未写渠道的仍走裸名（旧行为不变） |`
- L75 `## 4. Qoder Qwen3.8-Flash 的免费窗口在 23:59 关掉了`
- L105 `- 快照 providers/qoder/cache/qd_prices.json：Qwen3.8-Flash 从 price 0.0 / valley 0.0 /`
- L114 `MERGE_FREE_GB 中的 qwen3.8-flash，再跑一次 python tools/model_alias.py --slot auto --apply`

处置 **KEEP**：理由——全是 Qwen 型号，`3.8-Flash` 只是同尾数巧合，删它会把 Qoder 那条价格链的记录掏空。

#### A2 `modelbus-2026-11-10-74a3e530.md` L53 — EDIT_LINE

- 小节：**§2 修掉的三个缺陷 → ③ Gemini 系被当装饰渠道整条清空**
- 原文：`Gemini-3.8-Flash / Gemini-AIS 挂在 hjm: / gem: 渠道，不在能力表里就被清 values；但实测 thinking_budget 0→16384 对应 reasoning_tokens 0→164，是真生效。`
- 处置 **EDIT_LINE**：改成 `Gemini-AIS 挂在 gem: 渠道，不在能力表里就被清 values；但实测 thinking_budget 0→16384 对应 reasoning_tokens 0→164，是真生效。`
- 理由：这一节讲的是判据从「渠道在白名单里」改成「有没有可求值表达式」，Gemini-AIS 一个例子就够支撑结论；删掉模型名不损失任何机制信息。

#### A3 `modelbus-推理档位与别名派生口径-da79c0b9.md` L131 / L133 — KEEP（误命中，2 行）

- L131 `| 聚合键 | 型号 + 协议；跨协议合并仅限 MERGE_ACROSS_PROTOCOL = {"deepseek-v4.1-flash","qwen3.8-flash"} |`
- L133 `| 免费合并 | MERGE_FREE_GB = {"deepseek-v4.1-flash","qwen3.8-flash"} 的免费跳并入同名付费条目，不单列 |`
- 处置 **KEEP**：Qwen3.8-Flash 的合并白名单，与 Gemini 无关。

#### A4 `modelbus-gemini-ais-chain-3f6dda94.md` — 混合（本批唯一需要拆结构的一篇）

这是「Gemini-AIS 七跳链 + HJ 单跳兜底」的结构正本，命中 4 行加 1 节：

1. **L4（front matter description）** — `description: "七跳同源降级链与 HJ 单跳跨站兜底的结构事实：链序与发车顺序、竞速/串行两形态、链首定节奏、渠道优先级四维、登记面四处、生效边界"`
   处置 **EDIT_LINE**：删「与 HJ 单跳跨站兜底」，改为 `七跳同源降级链的结构事实：…`。理由：description 是检索入口，留着会继续把这条线当现行结构。
2. **L22（开篇引文）** — `> 两条线各走各的：Gemini-AIS 是 GM 渠道内的七跳同源降级链，Gemini-3.8-Flash 是 HJ 渠道的单跳跨站兜底；选路只认「谁先能出字」，不认版本新旧。`
   处置 **KEEP_REWRITE**：改成 `> Gemini-AIS 是 GM 渠道内的七跳同源降级链；跨站换源兜底线已于 2026-11-11 随模型下线撤除。选路只认「谁先能出字」，不认版本新旧。` 理由：后半句是通用选路判据，必须留。
3. **L35（§1 表行）** — `| Gemini-3.8-Flash | 1 | HJ（哈基米 gemai.cc） | [福利]gemini-3.8-flash | 更便宜的独立估算价 | 跨站换源兜底 |`
   处置 **DELETE_ENTIRE**：整行只描述该模型，删行；同时把 §1 标题「两条线：同源降级 vs 跨站兜底」改成单线表述（标题本身不含关键词，但删行后不改成「一条线」会自相矛盾）。
4. **L61（§2 七跳表第 0 行）** — `| 0 | ais-gemini-3.8-flash | 链首、名字主人、显示名主人 | 「新一代优先」只在这一档成立 |`
   处置 **KEEP**：这是 Gemini-AIS 的链首跳，另一个模型；删了会把七跳链改成六跳，属误伤。
5. **§1.1「为什么拆，而不是留作链内兜底」（L39–L45）** — 三条理由
   - 第 1 条（L43）`链内兜底只吃链首的规则。对冲参数与响应头窗口都取 Chain[0] 的渠道策略…` → **KEEP_REWRITE**：这是纯机制，与 §4「链首决定整条链的节奏」重复，删这段前应把结论折进 §4 或保留一句；理由：机制不是模型事实。
   - 第 2、3 条（L44–L45，`AIS 整片不可用时，最优解是根本不试 AIS` / `「先降档还是先换站」应该让用户选`）→ **DELETE_ENTIRE**：只解释「为什么要拆出这个模型」，模型没了就没有解释对象。
   - 整节标题建议顺手改成 `### 1.1 链内兜底为什么留不住（机制）`，保留第 1 条即可。

#### A5 `modelbus-opencode-go-e56d26ad.md` L39 / L43 / L52 — KEEP（误命中，3 行）

- L39 `…Qwen3.8 Flash/Space Bunny/Hy4 $30…`
- L43 `**价格带**…Qwen3.8 Flash $0.15/$0.47…`
- L52 `- 多协议：…qwen3.8-max、qwen3.8-flash（chat+messages）`

处置 **KEEP**：OpenCode-Go 的 Qwen 价格与协议记录。

#### A6 `modelbus-zgate-12s-c90d1859.md` L51 — KEEP

- L51 `…实测上游 ais-gemini-3.8-flash 每次 60.241 s 才回 503…`
- 处置 **KEEP**：讲的是响应头超时该按「正常首头分位 × 3–4」定的判据，例子是 AIS 链首跳；换掉例子会丢掉「上游 60 s 才认输」这条实测锚点。

#### A7 `modelbus-zgate-3-2026-11-11-0dc8208e.md` L50 / L52 — KEEP

- 小节：**§三 实测证据（换版后 uptime 284s）**
- L50 `- 首批逐跳表：GM|ais-gemini-3.8-flash try 5 / ok 2；GM|ais-gemini-3.7-flash try 1 / ok 0；HJ|[福利]gemini-3.8-flash try 1 / e5xx 1；WB|cn:deepseek-v4.1-flash try 24 / ok 24。`
- L52 `读法：3.8 五次里成两次、3.7 的 try 非 0 = 失败后确实降级到下一跳；HJ 福利档冒过一次 5xx。`
- 处置 **KEEP**：带时间戳的实况快照，删掉等于篡改当天记录。若怕后人误读，只允许追加一句注记（`（HJ 该跳已于 2026-11-11 随 Gemini-3.8-Flash 下线）`），不动原数字。

#### A8 `zcodeaimodels-workbuddy-669f6d6a.md` L251 — KEEP

- 原文片段：`被判定下架的 27 个全是 global:（… deepseek-v4.1-flash(-sg)、gemini-3.8-flash、glm-5.2/5.3/5.3-flash …）`
- 处置 **KEEP**：这是 **WorkBuddy 面板自己的** global 别名下架清单，`gemini-3.8-flash` 是那一侧的商品名，不是本机 ModelBus 的 `Gemini-3.8-Flash` 条目。

## 2. 热条目（`runtime/MEMORY.md` + `runtime/memories.json`）

只命中 1 条，两个载体同文（MEMORY.md 第 4 条 / memories.json `entries[11]`，importance=critical，created 2026-11-10T06:23:48Z，updated 2026-11-11T03:59:11Z，164 字符）：

```text
zgate 判死权归上游：GM headerTimeoutSec=-1 / firstBlockMs=0 / hedge=0 / maxParallel=1，全局兜底 45s；AIS 链 11-11 起 3 跳全 GM，Gemini-3.8-Flash 走 HJ 单跳。正本 MODEL-PROVIDERS.md 4.11.3。
```

- 处置 **KEEP_REWRITE**（两载体必须同步改，`mnemon_runtime_memory replace` 一次到位）
- 建议改法：`zgate 判死权归上游：GM headerTimeoutSec=-1 / firstBlockMs=0 / hedge=0 / maxParallel=1，全局兜底 45s；AIS 链 11-11 起 3 跳全 GM，HJ 单跳线已随 Gemini-3.8-Flash 下线撤除。正本 MODEL-PROVIDERS.md 4.11.3。`
- 理由：这半条是路由机制（判死权归上游、超时与并发的取值），模型只是例子；整条删掉会把 GM 侧那套参数判据一起带走。

### 2.1 其余热条目文件

| 文件 | 命中 | 处置 |
| --- | --- | --- |
| `runtime\archived\MEMORY.md` L71 | 1 | KEEP（Qwen3.8-Flash 定价条目） |
| `runtime\archived\memories.jsonl` L29 | 1 | KEEP（同上，归档 JSONL） |
| `backups\pre-cleanup-20261110-1735\runtime\MEMORY.md` | 3 | KEEP（回滚快照，一律不动） |
| `backups\pre-cleanup-20261110-1735\runtime\memories.json` | 3 | KEEP（同上） |

## 3. 特别标注：一条里写了多个模型的热条目

**只有 1 条**，就是上面的 §2 那条。整条原文（164 字，≤300）：

> zgate 判死权归上游：GM headerTimeoutSec=-1 / firstBlockMs=0 / hedge=0 / maxParallel=1，全局兜底 45s；AIS 链 11-11 起 3 跳全 GM，Gemini-3.8-Flash 走 HJ 单跳。正本 MODEL-PROVIDERS.md 4.11.3。

为什么危险：这一条同时承载三件事——① GM 渠道的判死参数（`headerTimeoutSec=-1` / `firstBlockMs=0` / `hedge=0` / `maxParallel=1`）；② AIS 链已在 11-11 由 7 跳截成 3 跳的事实；③ 被删模型的路由。**整条删 = ①②一起没了**，只能 replace 改第 ③ 段。

次危险的是 Documents 侧同构写法：`modelbus-2026-11-10-74a3e530.md` L53（Gemini-3.8-Flash / Gemini-AIS 并列），整行删会把 Gemini-AIS 的档位证据一起删掉——所以判 EDIT_LINE 不是 DELETE。

## 4. 规则文档（`~/.dsh`）

| 位置 | 命中 | 处置 |
| --- | --- | --- |
| `~\.dsh\AGENTS.md` | 0 | 无 |
| `~\.dsh\prompt-inject.md` | 0 | 无 |
| `~\.dsh\skills\**\*.md`（23 个技能目录） | 0 | 无 |
| `~\.dsh\procedures\*.md`（38 张卡） | 0 | 无 |
| `~\.dsh\profiles\desktop\cordis.patch.yml` | 2 行 | 见下 |

### C1 `cordis.patch.yml` L70–L80 — DELETE_ENTIRE

- 位置：顶层 patch 条目 `- id: llm-pi-ai`（L36）→ `config.providers.zcode-main.models`（L39 / L56）里的第 2 个模型块。
- 原文（11 行）：

```yaml
          - id: Gemini-3.8-Flash
            contextWindow: 1048576
            maxTokens: 65536
            input:
              - text
              - image
            reasoningEfforts:
              'off': disabled
              low: low
              medium: medium
              high: high
```

- 处置 **DELETE_ENTIRE**：整块删（含 L70 的 `- id:` 行到 L80 的 `high: high`）。理由：这就是 DSH 侧模型条目本体，不删模型仍会出现在选择器里；同组还有 `DeepSeek-4.1-Flash`（L57）与 `Gemini-AIS`（L81），删中间一块不影响前后缩进。
- 附注：`- id: agent-default-model`（L4）的 `config.model` 是 `DeepSeek-4.1-Flash`（L8），不指向被删模型，无需改。

### C2 `cordis.patch.yml` L204 `- id: Qwen-3.8-Flash` — KEEP

误命中：Qwen 型号。

## 5. 技能 / 经验卡

- `~/.dsh/skills/**/*.md`：0（23 个技能目录全扫）
- `~/.dsh/procedures/*.md`：0（38 张卡全扫）
- `~/.dsh/lessons/lessons.json`：3 行命中，见下（这一层不在原任务清单里，但属「经验卡」同类载体，一并判定）

### D1 `lessons.json` L45 — EDIT_LINE

- 原文片段（某条 `fix` 字段）：「④ EMPTY_ALLOWED 加 Gemini-AIS/Gemini-3.8-Flash 消除每天误报的档位漂移」
- 处置 **EDIT_LINE**：改成「④ EMPTY_ALLOWED 加 Gemini-AIS 消除每天误报的档位漂移」。理由：教训主体是探测/账本机制，型号只是当时的名单；留着会诱导后续会话把已删模型再写回白名单。

### D2 `lessons.json` L835 — EDIT_LINE（★最容易造成二次伤害的一条）

- 原文（`fix` 字段）：「写作与需要读文件的任务不挂 AIS，改 DeepSeek-4.1-Flash（WB ok=3296/try=3299）或 Gemini-3.8-Flash；AIS 只用于不调工具的纯对话且 effort=off（实测 20.6s 出 721 字，high 档更易空回）」
- 处置 **EDIT_LINE**：删「或 Gemini-3.8-Flash」。理由：这是一条**行动建议**，不是记录；模型删掉后它会让后续会话去选一个不存在的模型，且这句话会在 `error_lessons_search` 里被优先召回。

### D3 `lessons.json` L834 — KEEP

- 原文（`cause` 字段）提到 `GM 的 ais-gemini-3.8 跳三种退化`；是 AIS 链首跳的故障机制，不是被删模型。

## 6. zcode 历史副本（只读，不改）

- 路径：`~\.zcode\cli\memories\`
- 实际结构：`projects\draft-<uuid>\memory\*.md`，**共 3 个文件**（`dsh-profile-config-encoding.md`、`dsh-startup-verification.md`、`MEMORY.md`）
- **命中 0**：无需任何动作。
- 顺带更正一条常驻口径：`~/.dsh/AGENTS.md` 记忆节写「`~/.zcode/cli/memories/` 是历史副本（100 个文件已全量导入）」，与实测不符——当前只剩 3 个文件。这条口径本身要不要改由主线决定（不含模型名）。

## 7. 派生索引 `documents/index.json`

- 命中 2 行：L679（Qwen3.8-Flash 的 description）、L1448（**archived** 文档标题 `ModelBus：Gemini 3.8 同代兜底拆为独立模型 Gemini-3.8-Flash（HJ 单跳，AIS 回到 7 跳）`）。
- 处置：**不改手写**。index.json 由 `node ~/.dsh/tools/sync-doc-index.mjs` 从 documents 重建；文档改完后跑一次并核 `sizeBytes` / `contentHash` 对齐。

## 8. 推荐动作清单（去重、按载体、可直接照做）

### 8.1 规则文档层（1 处）

1. `~/.dsh/profiles/desktop/cordis.patch.yml` 删 L70–L80 整整 11 行（`- id: Gemini-3.8-Flash` 到 `high: high`）——**DELETE_ENTIRE**。删完确认同组还剩 `DeepSeek-4.1-Flash` 与 `Gemini-AIS` 两条，YAML 缩进未变。

### 8.2 热条目层（1 条，两载体同步）

2. `~/.mnemon/runtime/MEMORY.md` 第 4 条 + `~/.mnemon/runtime/memories.json` `entries[11]`：把末段 `Gemini-3.8-Flash 走 HJ 单跳。` 改成 `HJ 单跳线已随 Gemini-3.8-Flash 下线撤除。`——**KEEP_REWRITE**，两处文本必须一致。
3. 改完跑 `node ~/.dsh/tools/check-memory-hygiene.mjs`，要 exit 0。

### 8.3 Documents 层（3 处）

4. `documents/active/modelbus-gemini-ais-chain-3f6dda94.md`：删 §1 表行 L35（**DELETE_ENTIRE**）+ 删 §1.1 第 2、3 条理由 L44–L45（**DELETE_ENTIRE**）。
5. 同文件：改 L4 description 去掉「与 HJ 单跳跨站兜底」（**EDIT_LINE**）；改 L22 开篇为单线表述 + 下线说明（**KEEP_REWRITE**）；§1 标题「两条线」改「一条线」；§1.1 保留第 1 条机制句（**KEEP_REWRITE**，建议折进 §4）。
6. `documents/active/modelbus-2026-11-10-74a3e530.md` L53：删 `Gemini-3.8-Flash / ` 与 `hjm:`，只留 `gem:`（**EDIT_LINE**）。

### 8.4 经验卡层（2 处）

7. `~/.dsh/lessons/lessons.json` L45：`EMPTY_ALLOWED 加 Gemini-AIS/Gemini-3.8-Flash` → `EMPTY_ALLOWED 加 Gemini-AIS`（**EDIT_LINE**）。
8. 同文件 L835：删「或 Gemini-3.8-Flash」（**EDIT_LINE**）——优先级最高，别漏。

### 8.5 索引与复核

9. 跑 `node ~/.dsh/tools/sync-doc-index.mjs`（先 `--dry-run` 看 diff）重建 `documents/index.json`。
10. 复核（只读）：对上述各文件跑 `Select-String -Pattern gemini-3\.8-flash|Gemini-3\.8-Flash`，应只剩历史存档类命中（`zgate-3` 实测表、`zcodeaimodels-workbuddy` 第三方清单、AIS 链首 `ais-gemini-3.8-flash`）。

### 8.6 明确不要动

- `zcodeaimodels-workbuddy-669f6d6a.md` L251、`modelbus-zgate-3-2026-11-11-0dc8208e.md` L50/L52、`modelbus-zgate-12s-c90d1859.md` L51、chain 文档 L61、全部 Qwen 命中行。
- `~/.zcode/cli/memories\`（0 命中）。
- `~/.mnemon/backups\pre-cleanup-20261110-1735\`（回滚材料，3 + 3 处命中保留）。

## 9. 范围外提示（我不动，供主线决策）

- **archived 文档**（`documents/archived`，22 篇有命中）：`modelbus-gemini-3-8-gemini-3-8-flash-hj-ais-7-023d9dd3.md` 15 处、`modelbus-hj-gemai-cc-gemini-ais-8-3e8f2a47.md` 12 处、`modelbus-gemini-ais-merged-20261110.md` 8 处、`modelbus-gemini-ais-11db4792.md` 5 处、`zgate-ops-merged-20261110.md` 5 处，其余 17 篇 1–3 处。这些是本次拆分的**正本档案**，建议整篇归档保留，不做编辑。
- **`~/.dsh` 其他子树**：命中集中在 `storages\session_projcache\sessions\*.json`（上百个会话转录）、`.work\sweep-20261110-quarantine\projcache\*`、`cache\dsh-claude-style\*`、`evidence\mem-sweep-D.md`（19 处）等——都是会话缓存与历史产物，不是规则载体，删了会破坏历史对话。

## 10. 复核命令（只读，PowerShell 原生路径）

```powershell
$pat = 'gemini[-_ ]?3[._]8|3\.8[-_ ]?flash|gemini3\.8|HJ ?单跳|HJ ?渠道'
Select-String -Path '~\.mnemon\documents\active\*.md' -Pattern $pat -CaseSensitive:$false | Measure-Object
Select-String -Path '~\.dsh\profiles\desktop\cordis.patch.yml' -Pattern $pat -CaseSensitive:$false
Select-String -Path '~\.mnemon\runtime\MEMORY.md' -Pattern $pat -CaseSensitive:$false
Select-String -Path '~\.dsh\lessons\lessons.json' -Pattern $pat -CaseSensitive:$false
```
