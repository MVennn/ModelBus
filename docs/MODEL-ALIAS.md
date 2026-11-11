# 统一模型命名与分组

> **一句话**：模型 ID 只用型号名（如 `DeepSeek-4.1-Flash`），同一型号跨渠道合并成一条
> 链路（WB 跳固定链首，其余按价格 / 前缀 / 渠道稳定排序）；**2026-10-28 起只保留三组**——主力（人工两条）、免费、
> 省钱（每厂商 1–2 个代表作；新厂商/新一代 ≤0.11 自动补位）。

---

## 1. 为什么需要 alias map

显示名不再带渠道和积分，路由无法从名字反推上游（`DeepSeek-4.1-Flash` 对应三个渠道的
三个上游跳）。因此同步脚本同时写两份：

| 文件 | 作用 |
|---|---|
| `~/.zcode/v2/provider_config.json` | ZCode 看到的三个 provider 与显示名列表 |
| `~/.zcode/v2/model-alias-map.json` | 显示名 → `{protocol, price, chain:[{channel, upstream, base, price}], group}`；路由读它 |

`chain` 是**有序链路**：路由从第一跳开始试，遇到 429 / 502 / 503 / 504 或
`400 model_unavailable` 就换下一跳。每一跳自带 `base`，所以一条链路可以横跨
WorkBuddy（7863）、Qoder（8790）、千问（远程 Messages）和 OpenCode-Go（远程）。

**与请求无关的 4xx 也算「这跳作废」**：`Model not exist`（上游没有这个 id）、
`Arrearage` / `AllocationQuota` / `FreeTierOnly`（额度耗尽）、以及 402，都会立即换
下一跳，并把该跳放进 **30 分钟冷却**（内存态，重启清零，`/health` 的 `cooling`
是当前数量）。没有这条，几十跳的集合体每轮都要先把死跳撞一遍。
集合体（池子）的定义见 [QWEN.md](QWEN.md) §4.5；当前 `pools.json` 为空，集合体已停用。

alias map **不含凭据**；上游 key 仍由路由按渠道从 `provider_config.json` /
`gateways/upstream/workbuddy/config.json` / `providers/qoder/.env.local` 读取。

---

## 2. 显示名格式

```
<型号>
```

例：`DeepSeek-4.1-Flash`、`GLM-5.3-Flash`、`Qwen-3.8-Max`、`Claude-Haiku-5.5`。

- **不再带渠道**（原 `W/` `O/` `Q/`）**和积分**（原 `/0.03/`）。
- 版本号保留点号（`4.1` / `3.8` / `2.6` / `5.3`），`Flash` 与 `Preview` 写全
  （`DeepSeek-4.1-Flash`、`HY4-Preview`），不缩成 `-Fs` / `-Pre`。
- 系列前缀保持可读：`DeepSeek`、`Qwen`、`GLM`、`MiniMax`、`Kimi`、`HY`、`MiMo`、
  `LongCat`、`Beam`、`Claude`、`GPT`、`Muse`、`Step`、`Space`。
- 变体只保留模型本身有意义的：`Flash`、`Preview`、`Pro`、`Max`、`Plus`、`Vision`。

**不造后缀（2026-11-06 用户口径）**：显示名只承载「这是哪个模型」，不承载档位、
渠道、积分。只有当上游确实存在两个不同模型、或同型号在协议上无法合并时才加后缀
（`-Free` / `-Msg` / `-Resp`）。档位名一律不进显示名：

| 上游 id | 显示名 | 依据 |
|---|---|---|
| `cn:hy4std` | `HY4` | 回包 `model` 就是 `hy4`，`-Std` 是 WorkBuddy 的档位 |
| `cn:hy4-preview` / `-f` / `-ctrl` / `-exp1..3` / `-x` | `HY4-Preview` | 八个入口同一上游，回包 `model` 都是 `hy4-preview` |
| `kimi-k2.8-preview` | `Kimi-K2.8-Preview` | 写全，不缩 `-Pre` |
| `step-5-preview` | `Step-5-Preview` | 同上 |
| `deepseek-v3-2-volc` | `DeepSeek-3.2` | `-volc` 是供应商后缀，不是型号 |

实现：`abbreviate()` 的兜底只做大小写规整（`flash` → `Flash`、`preview` → `Preview`），
不再把词首缩成两三个字母；`hy4-preview` 族走前缀规则统一归一。
回归：`tests/test_model_alias_naming.py`。

**同名冲突的两种处理：**

| 情况 | 做法 |
|---|---|
| 同型号既有免费档又有付费档 | **先合并**：免费档并入付费条目当第一跳（见 §3）。只有协议不同无法合并时才单独成条，且**真重名**才给免费那条加 `-Free`（当前无此情况） |
| 同名但协议不同（chat / messages / responses） | 桥接那条加 `-Msg` / `-Resp`（2026-10-28 首次触发：千问桥接版） |

`deepseek-v4.1-flash` 是唯一例外：免费档**并入**付费条目并放在链路第一跳，见 §3。

---

## 2.1 同类模型的判定（2026-11-06）

**判据不看名字，看上游回包。** 名字只是给人看的标签，同名不同模型（或不同名同模型）
都会让「合并 → 回落 → 计费」这套语义悄悄错位。

### 三级判据（按权威性）

| 级别 | 证据 | 判定 |
|---|---|---|
| L1 **权威** | 回复 JSON 的 `model` 字段（上游自报型号） | 相同 = 同一模型，可合并成一条链；不同 = 不同模型，永不合并 |
| L2 **确认** | `usage.quota.model` / `usage.credit` | quota 池相同 = 同一计费模型；`credit > 0` = 该桶实际扣分，**不得进免费组** |
| L3 **指纹** | 定价源的 `(ctx, out, list_rate)` 三元组 | 全等 = 同一模型的多个部署桶（如 `hy3` / `hy3-b` / `hy3-c`） |

```text
L1 决定「能不能合并」   → 只有同 model 的桶才并进一条链
L2 决定「能不能标免费」 → 回包 credit 为 0 才允许 price=0
L3 决定「是不是同一代」 → ctx / out 不同 = 不同代，即使名字前缀相同
```

**名字（`ABBR` 表）只用于显示名覆盖，不参与合并判定。** 任何「因为名字像所以合并」
的推断都要用 L1 复核。

### 实测矩阵：HY 家族（2026-11-06，经 7863 直连，单问「17 乘以 23」）

| upstream | 回包 `model` | `quota.model` | 本次 `credit` | 现有显示名 | 现有组 |
|---|---|---|---|---|---|
| `cn:hy4free` | **hy4-free** | hy4 | 0 | `HY4-Free` | 免费 |
| `cn:hy4std` | **hy4** | （无） | 0.02 | —（0.29 超省钱档上限被裁） | — |
| `cn:hy4-preview` | **hy4-preview** | hy4-preview | 0.04 | —（同上） | — |
| `cn:hy4-preview-f` | **hy4-preview** | hy4-preview | 0.03 | `HY4-Pre` | 免费 |
| `cn:hy4-preview-ctrl` / `-exp` / `-exp1..3` | **hy4-preview** | （无） | 0.03–0.04 | `HY4-Pre`／`hy4-Pre-exp1..3` | — |
| `cn:hy3` / `-b` / `-c` | **hy3** | hy3 | 0 | `HY3` | 免费 |
| `cn:hy3-x` | **hy3-x** | （无） | 0.01 | `HY3-X` | 省钱 |

历史消耗（`gateways/upstream/workbuddy/data/usage.json` 聚合）：

| model | 请求数 | credit 合计 | 平均 |
|---|---|---|---|
| `hy4free` | 1154 | **0.00** | 0 |
| `hy4-preview-f` | 2420 | **6601.01** | **2.73** |
| `hy4-preview` | 864 | 0.22 | 0.0003 |
| `hy3` / `hy3-b` / `hy3-c` | 590 | 0.00 | 0 |
| `hy3-x` | 170 | 37.47 | 0.22 |

### 由此得到的三个结论

1. **`HY4-Free` 与 `HY4-Pre` 不是同类模型，不能合并。** L1 回包分别是 `hy4-free`
   与 `hy4-preview`（两个上游型号），L2 配额池分别是 `hy4` 与 `hy4-preview`，
   L2 计费是 0 与每次约 0.03 积分 —— 三条判据全指向「两个模型」。
2. **真正的同类是 `hy4-preview` 一族**：`hy4-preview` / `-f` / `-ctrl` / `-exp` /
   `-exp1..3` 回包都是 `hy4-preview`，属于同一模型的 8 个部署桶。现状把它们拆成
   `HY4-Pre` 与 `hy4-Pre-exp1..3` 四个显示名 —— 因为 `ABBR` 表只填了前 5 个变体，
   `exp1`/`exp2`/`exp3` 落到正则兜底（`preview`→`Pre` 但前缀没统一大写）。
3. **`cn:hy4-preview-f` 是资费口径 bug**：定价源里它的 `credits` 是空字符串、
   `list_rate` 是 0，于是被判 `price=0` 进「免费」组；实测每次请求扣约 0.03 积分，
   历史累计 6601 积分。「免费组 = 真不花钱」这个前提被破坏。

### 落地清单（按 L1 判据改造，未实施）

| # | 位置 | 改动 |
|---|---|---|
| 1 | 探活脚本 | 回包里提取 `model` / `usage.quota.model` / `usage.credit` 写进 `model_probe.json` 的结构化字段（现在只存原始 detail 字符串，判不了族） |
| 2 | `tools/model_alias.py` | 合并键从 `abbreviate(base_model)` 改为「L1 回包 model（缺失时退回名字 stem）」；`ABBR` 降级为显示名覆盖表 |
| 3 | `tools/model_alias.py` | `price` 判免费加一道 L2 校验：该 upstream 近期 `credit > 0` 时不允许 `price=0`（`hy4-preview-f` 立即从「免费」掉回付费档） |
| 4 | 同步报告 | 输出「显示名 → 上游 model → 桶列表 → 实际 credit」矩阵，新桶自动归类；判不出族的列「待确认」而不是静默给个脏名字 |

回归方式：用 `wb_pricing.json` 快照 + `usage.json` 聚合做夹具，断言
（a）`hy3`/`-b`/`-c` 仍合成一条；（b）`hy4-preview*` 八个桶合成一条；
（c）`hy4free` 与 `hy4-preview-f` 分属两条；（d）`hy4-preview-f` 不再进免费组。

回退：判定逻辑集中在新增的 `family_of()`，删掉调用即回到 `ABBR` 手填行为。

---

## 2.2 为什么会漏模型（2026-11-06）

用户问「是不是很多模型也跟着漏了」。按当前快照（`model-alias-map.json` 的已用跳
与各渠道 `/v1/models` 的全量列表做差）先给数量：

| 渠道 | 上游型号 | 进链 | 未进链 |
|---|---|---|---|
| WB | 39 | 11 | 28 |
| OC | 30 | 11 | 19 |
| QD | 12 | 4 | 8 |
| QW / QN | 1 / 1 | 1 / 1 | 0 / 0 |

**大头不是 bug，是设计**：条目只从 `provider_config.json` 的 `personalModelIds` 与
`providers/qwen/pools.json` 生成，上游 `/v1/models` 与价格表都不会自动建档。也就是
「上游有 39 个、我们只用 11 个」是白名单的必然结果。未进链的 28 条 WB 型号可分四类：

- **路由别名 / 不是模型**（8）：`auto`、`balanced-model`、`deep-model`、`fast-model`、
  `wb-lite`、`hunyuan-chat`、`hunyuan-image-alpha`、`hunyuan-image-edit`（多条 `list` 为空）。
- **旧一代**（10）：`deepseek-v3-1-lkeap` 0.52、`deepseek-v3-2-volc` 0.29、
  `deepseek-v4-flash` 0.17、`deepseek-v4-pro` 0.51、`glm-5.0-turbo` 0.95、`glm-5.2` 0.79、
  `minimax-m2.7` 0.26、`step-5-preview` 0.33、`kimi-k2.5` 0.45、`kimi-k2.8-preview` 0.77。
- **hy4-preview 同族 7 个桶**：全 0.29，回包都是 `hy4-preview`，按 §2.1 判据是同一个模型，
  只需一条（其中 `-preview-f` 的 `credits` 是空串，见 §3.1）。
- **贵旗舰**（3）：`glm-5.3` 0.69、`kimi-k3-1` 1.62、`kimi-k3.1-pro` 0.97 —— 超过
  `LOW_MAX = 0.11` 又不在主力名单，被价格闸挡掉。

真正会**静默漏**的只有三层，这才是需要修的地方：

1. **裸名去重吞掉同型号的不同渠道**。白名单补建原先只比「裸型号名」，`chat:qoder:…`
   与 OC 的同名条目撞车就被判重复丢掉（2026-11-06 Qwen3.8-Flash 事故）。已修：
   spec 写显式渠道（`qoder:` / `qwen:` / `cn:` / `global:` / `oc:`）即带
   `explicit_channel`，按 `(渠道, 裸名)` 比对。
2. **名单点名但查不到价 → 静默剔除**。`chat:Qwen3.8-Max` 就是这样：没写前缀 →
   classify 猜 OC → OC_PRICES 没有 `qwen3.8-max` → 跳被丢掉，主力 2 号位实际只剩
   QD 单跳、没有任何兜底，而且日志一个字都没有。已修：`_UNPRICED_HOPS` 收集缺价跳，
   汇总行打「具体跳：…」（最多 12 条），`--apply` 时可见。
3. **显式条目的跳命中不了名单**。`_picked()` / `_pick_rank()` 原来只比
   `<协议>:<上游>` 裸写法，写了 `chat:qoder:Qwen3.8-Max` 的跳既不进主力判定、
   也排不到名单名次（会被甩到组尾）。已修：`hop_specs()` 同时产出裸名与带渠道前缀的
   两种写法，两处共用。

补价这件事这次**没做**：用响应里的 `list_cost` 反推单价不可靠 —— OC 各厂的输入/输出
倍率不同（`deepseek-v4-pro` 用 peak 0.77/1.54 折算对得上实测，`mimo-v2.6-flash` 就对不上
`OC_PRICES` 里的 0.06），硬填会把价格闸算歪。现在的口径是「缺价必须可见」而不是
「猜一个价填进去」。

---

## 3. 跨渠道合并（chain）

链路第一维是渠道优先级：**WB 固定链首**（额度优先消费对象，不看价格），其余按价格升序、同价时 GB 优先于 CN；`QW` 预付额度由 `CHANNEL_RANK`（rank 2）钉在所有付费跳之后。链序硬规则见 `tools/model_alias.py` 与 `tests/test_model_alias_hop_order.py`。以 DeepSeek 为例：

```
DeepSeek-4.1-Flash
  1. WB  cn:deepseek-v4.1-flash          0.11   ← 面板现价
  2. OC  deepseek-v4.1-flash             0.11
  3. QW  deepseek-v4.1-flash             0.00   ← 一年期预付额度，钉在链尾
```

- 实际扣费看命中哪一跳；显示名不再体现价格。
- `MERGE_FREE_GB`（当前只有 `deepseek-v4.1-flash`）：免费档不单独成条，直接作为
  付费条目的第一跳。其它型号的免费档仍然单独成条（`-Free`）。
- 合并键是「型号 + 协议」，所以 chat 与 messages/responses 不会混在一条链路里。
- 生成器**幂等**：链路会写回 alias map 的 `chain`，下一次运行从 `chain` 还原全部跳，
  不会因为配置里只剩一个条目而丢掉其它渠道。

### 3.0 每跳自己的出口（`chain[].proxy`，2026-10-30 起）

`chain` 的每一跳可以带 `"proxy": "http://host:port"`，表示**这一跳走这个 HTTP 代理**，
不带就是直连。它解决的是「同一个上游、同一个域名，但有的型号只能从境外 IP 调」：
opencode 的型号共用 `opencode.ai`，规则层分不开，只有 `gpt-*` / `beam-free` /
`muse-spark-*` 拿 403 地区限制（`unsupported_country_region_territory` / `RegionError`）。

生成器给每条 OC 直连跳补一条**同上游的孪生跳**（`AIRPORT_PROXY`，默认
`<AIRPORT_PROXY>` —— 路由器上的入站固定绑 🤖 AI接口 组），**排在 `QW` 尾跳之前**：

```
GPT-6-Luna         1. OC gpt-6-luna 直连
                   2. OC gpt-6-luna @机场   ← 直连 403 才走它
DeepSeek-4.1-Flash 1. WB cn → 2. OC 直连 → 3. OC @机场 → 4. QW 直连
```

- zgate 把地区受限的 403 当「换出口」处理，不是「这一跳坏了」；冷却键 `hopKey`
  里含 proxy，否则直连那跳的 403 会把机场跳一起冷却掉（= 兜底被吃掉）。
- 机场孪生跳排在 `QW` 尾跳之前、紧跟 OC 直连跳；磁盘活数据链为 `WB → OC → OC@机场 → QW`。
- 改 `AIRPORT_PROXY` 时路由器侧必须同时有对应的 `listeners` 入站，
  否则这一跳直接连不上（见 ShellcrashRules `docs/ARCHITECTURE.md` §2.2）。
- **这个出口只对经过 zgate 的请求生效**。同步脚本（`go_model_sync.py`）自己发探测、
  不经过路由器，所以它把同一个 `AIRPORT_PROXY` 用在「直连地区受限 → 复测」上，
  否则会把这三个模型当死模型删掉（[PITFALLS.md](PITFALLS.md) §35）。改地址时两处同改。

### 3.1 价格是派生量，不继承

`chain` 里存的是「有哪些跳、怎么路由」；`chain[].price` 只是上一轮的记录，
**每轮都从价格源重算**（WB 价格表 / Qoder 在线接口 / OC 静态价表），永不沿用旧值。

- 上游已下架/被封的跳：源里查不到价 → 该跳直接剔除，不靠旧价赖在清单里。
- 价格源不可用（整渠道无价）：拒绝 `--apply`，除非显式 `--force-unpriced`。
- WB 价格表超过 **48 小时**未刷新会打 WARN；`--probe-file` 的探测结果默认超过
  **72 小时**按「未知」处理（`--probe-max-age-hours` 可调，0 = 不设限）。
  过期的 `ok` 会留住已下架的模型，过期的 `blocked` 会删掉还能用的模型，两个方向都错。
- `--probe-file` **不删主力组成员**（2026-11-11）：状态非 ok 的主力条目一律保留，
  只在 stderr 打 `WARN: 主力组成员本轮探测不健康…`；只有上游明确 `unavailable / 404`
  才照删。理由：DSH 的 `zcode-main` 型号表由这份配置直接投影，缺一条不是降级而是
  硬失败（`pi-ai provider "zcode-main" has no configured model "…"`），整场会话报废。
- 探活要给足输出预算：默认 `--max-tokens 256`。32 在「先思考再出字」的模型
  （Gemini / Doubao 档）上会被思考预算吃光，上游回 400，模型被误判成死型号
  （[PITFALLS.md](PITFALLS.md) §39）。
- `--check`：把重算结果与现有 alias map 比对，有漂移就以退出码 1 结束，不写盘。
  建议挂进定时任务 —— `sync_report.py` 比的是「上一版产物 vs 这一版」，
  一个稳定存在的偏差在它眼里永远是「无变化」。

> 事故背景（2026-10-28）：Step-5-Pre 的「独家限免」10-25 到期后已按 x0.33 计费，
> 配置里却一直挂在免费档 0.00，就是因为链路继承了 alias map 里的旧价。
> 同轮还抓出 MiMo-2.6-Pro（0.18 应为 0.13）和一条 Qoder 源故障时吃静态回退
> 留下的 0.0 假免费条目。

### 3.2 白名单显式渠道 + 跨协议合并：Qoder Qwen3.8-Flash（2026-11-06）

> **时效（2026-11-06 23:59 复核）**：免费窗口已经关闭。`/v1/models` 从
> `price 0.0 / valley 0.0` 变成 `price 0.04 / peak 0.1 / valley 0.04`（`is_free` 仍是
> `true`，字段自相矛盾），实测 `usage.billable` 从 `false` 变 `true`、`credits`
> 0.1638。它比 OC 的 0.09 便宜，仍然排链首，但已经不落免费组。下面的「0.0 / 不扣积分」
> 是 23:44 的事实，保留作历史依据。

Qoder 的 `Qwen3.8-Flash`（catalog key `qfmodel`）在官方目录里曾是
`price_factor 0.0 / original_price_factor 0.1 / is_free true`，错峰规则
`idle_time_model_credit_discount`（22:00–08:00 UTC+8 四折）之外，`/v1/models`
回的是 `price 0.0 / peak 0.1 / valley 0.0`。实测经 8790 打 6 次，usage 里
`billable: false`，账号额度 `remain 1400 / used 0` 纹丝不动 —— 确实不扣积分。

但它进不了链，卡在两处：

1. **裸名去重把新渠道的跳吞了**。条目只来自 `provider_config` 的
   `personalModelIds`，白名单补建按「裸型号名」比对（因为 `chat:Qwen3.8-Max`
   没写渠道时 classify 只能猜 OC）。`Qwen3.8-Flash` 已被 OC 的 messages 条目占位，
   于是 `chat:qoder:Qwen3.8-Flash` 补出来也被判重复丢掉。
   现在 `whitelist_items()` 会给条目打 `explicit_channel`（spec 里显式写了
   `qoder:` / `qwen:` / `cn:` / `global:` / `WB:` 等），main 里按
   `(渠道, 裸名)` 比对；没写渠道的仍走裸名，旧行为不变。
2. **QD 是 chat、OC 的 `qwen3.8-flash` 是 messages**，不跨协议合并就会拆成
   `Qwen-3.8-Flash` 与 `Qwen-3.8-Flash-Msg` 两个分身。现在
   `MERGE_ACROSS_PROTOCOL` 与 `MERGE_FREE_GB` 都加了 `qwen3.8-flash`。

结果是一条链、一个显示名（免费窗口内落免费组，关闭后落省钱组）：

```
Qwen-3.8-Flash   chain: QD:Qwen3.8-Flash -> OC:qwen3.8-flash -> OC:qwen3.8-flash(机场孪生)   price 0.00
```

QD 按峰谷计价（×`QD_FACTOR` 0.86）：夜里 valley 0.04 → 0.03，白天 peak 0.1 → 0.086，
两种都低于 OC 的 0.09；渠道 rank 里 OC 与 QD 同为 1，第二键是价格 —— 所以**链首
始终是 QD**，只有价格和分组在动：

- 错峰窗口（22:00–08:00）= 0.03 → 落**省钱组**（免费窗口期曾是 0.0 → 免费组）；
- 白天（12:00 的每日同步）= 0.086 → 也落**省钱组**，同一条链，同一个显示名。

分组会随上游调价摆动，属于预期，不是漂移（`--check` 用同参数复算，白天算白天、
夜里算夜里，两边都自洽）。回归断言不写死价格，只断言「QD 比 OC 兜底便宜且排链首」，
上游涨价越过 OC 时测试会红。

回归：`tests/test_model_alias_qd_free.py`（显式渠道标记 3 条 + 链首 QD 且最便宜 / 无分身 2 条）
与 `tests/test_model_alias_naming.py`（尾缀规则 + `oc:` 前缀解析）。
回退：删掉 `LOW_ORDER` 里的 `chat:qoder:Qwen3.8-Flash` 与两个 `MERGE_*` 常量里的
`qwen3.8-flash`，再跑一次 `--apply`。

---

## 4. 三组规则（2026-10-28 起）

分组**不再按价格四档自动切**，而是「人工名单 + 价格兜底」。起因：实测 4 天 74.6 亿
token 里 86% 是 `DeepSeek-4.1-Flash` 一个模型，高耗组 16 条全部零使用。

| 组（providerId） | 装什么 | 判定 |
|---|---|---|
| **主力** `opencode-go-chat` | `HY4`（WB 单跳 0.29，竞技榜建模 #8 / 网页 #10）+ `DeepSeek-4.1-Flash`（四跳链：WB → OC → OC@机场 → QW）+ `Qwen-3.8-Max`（贵备份，QD 单跳 0.17；OC 同名跳缺价未收录）+ 竞技榜达标的两条（`MiMo-2.6-Flash` / `Space-Bunny`） | `MAIN_IDS`，键是 `<协议>:<上游 id>`（可写显式渠道，如 `chat:qoder:Qwen3.8-Max`），**不受价格上限约束**；白名单点名但配置里没有的型号会补建条目（见 §6） |
| **免费** `opencode-go-chat-free` | 真免费条目（当前 5 条：HY3 / HY4-Free / Beam / Conatus / Iceman） | 链路最低价 = 0；组内 `HY` 前缀置顶，其余按价格升序 |
| **省钱** `opencode-go-chat-fast` | **每个厂商 1–2 个最具代表性的现行产品**（当前 8 条）；前旗舰/上一代一律不收录 | 命中 `LOW_PICKS` 即进组，**不受 `LOW_MAX` 价格上限约束**（所以 MiMo-2.6-Pro 0.13 能在组里）；名单外另有一条 **自动补位**（见下） |
| ~~高耗~~ | 已删除 | 不在两个名单里且价格 > 0.11 → **不收录** |

为什么这么切：用户的实际选择只有「DeepSeek」和「免费」。按价格四档会让
16 个永远不点的贵模型占着选择器，也让主力被榜单越塞越肿。

> **2026-11-10 现行口径校准（上表与本节以下数条是 2026-10-28 快照）**：
> 用户 2026-11-10 把主力收敛为「仅 DeepSeek」——`MAIN_ORDER`
> （`tools/model_alias.py:106-128`）现为 `DeepSeek-4.1-Flash`（0.11）；原 4 条
> CP 主力档随反代整体下架。`HY4`（`cn:hy4std` 0.29）与 `Qwen-3.8-Max`
> （`qoder:Qwen3.8-Max` 0.43）已下沉省钱组（`LOW_ORDER:146-163`）。竞技榜候选由
> `MAIN_UPSTREAM_HINTS = ("deepseek",)` 过滤，`MiMo-2.6-Flash` /
> `Space-Bunny` 不再回灌主力。省钱组现行 **12 条**，`MiMo-2.6-Pro` 随价格源为
> **0.19**（`OC_PRICES:253`），不是上表的 0.13；上表「当前 8 条」同为旧快照。
> 分组真值以 `python tools/model_alias.py --check --arena` 输出与
> `%LOCALAPPDATA%/ModelBus/current-models.json` 为准。§4.2 的「分数 ≥ DeepSeek
> 基准 95% + 积分 ≤ 0.11」是榜单候选筛选（`tools/arena_leaderboard.py`），与
> `SCORE_MIN_INTEL = 85.0` / `SCORE_MIN_VALUE = 1.0`（`tools/model_alias.py:176-177`，
> 白名单分数替代门槛）是两处不同功能的阈值，不要互相套用。

三条硬口径：

- **名单的键必须带协议**（`chat:cn:deepseek-v4.1-flash`）。同一型号会以 chat 与
  messages 两种形态同时存在（千问桥接版），只写型号名会把两条一起吸进主力。
- **跨协议合并是例外而非默认**：`MERGE_ACROSS_PROTOCOL` 里的型号（目前
  `deepseek-v4.1-flash` 与 `qwen3.8-flash`）把 chat 与 messages 跳并成一条链，
  每跳自带 `protocol`，路由逐跳派发。`CHANNEL_RANK` 再把指定渠道钉到链尾（QW rank 2、QN rank 3），实现「先把月度额度用完，再用
  一年期预付额度」。
- **主力豁免价格上限**：白名单点名的条目不受 `LOW_MAX` 价格闸约束（现行主力仅 DeepSeek 0.11；历史上 `Qwen-3.8-Max` 0.17 曾是贵备份，2026-11-09 已下沉省钱组、现价 0.43），名单外超限模型一律不收录，
  所以 `--max-price` 只对非主力生效。
- **名单只管排序，不管建档**：条目只从 `provider_config` 的 `personalModelIds` 与池子
  文件生成，往 `MAIN_ORDER` 里加一个配置里没有的型号，不加 `whitelist_items()` 就什么
  都不会发生（2026-11-06 的 `cn:hy4std` 就是这么白写了一天）。现在白名单点名的缺失
  型号会从价格源补一条候选，持 `whitelisted` 标记，豁免 `LOW_MAX` 与 `VENDOR_QUOTA`。
- **榜单不再自动扩主力**：`arena_leaderboard.py` 仍能产候选，但
  `model_alias.py` 默认忽略，要 `--arena` 才生效。
- **顺序由人工名单决定，不按价格**：主力按 `MAIN_ORDER`、省钱按 `LOW_ORDER`
  的书写顺序排。旧实现按「厂商最低价」排序，会把便宜厂商顶到前面、把 MiMo 之类
  挤到列表末尾 —— 用户明确要求常用型号在最前，所以排序权收归名单。
- **省钱组只留各厂代表作**：每厂 1–2 个（小米是 Flash + Pro），旧代旗舰
  （如 MiMo-2.5、GLM-5.2、Qwen-3.7）不进组。
- **名单外的自动补位**（2026-11-02 起，`pick_auto_low`）：省钱组不该因为「没写进
  名单」就丢掉**新冒出来的一家厂商**或**这家厂商更新的一代**。规则：价格 `0 < p ≤
  LOW_MAX` 且该厂商还没有任何代表（主力/省钱都没有），或新条目版本号高于现有代表
  → 自动收录；每厂商最多自动补 1 条（版本最高者，同版本取便宜的），人工点名的
  永远优先、自动条目排在组尾。老一代、同代兄弟型号仍然不收录。

改名单/改顺序 = 改 `tools/model_alias.py` 的 **`MAIN_ORDER` / `LOW_ORDER`**，
然后 `python tools/model_alias.py --slot auto --apply`。`MAIN_IDS` / `LOW_PICKS`
由这两个有序列表派生，不要再单独维护（两份字面量会漂移）。
**收缩名单要跑两次**：第一次落新分组，第二次才收敛名字（`-Msg` / `-Free`
后缀取决于同型号还有没有别的形态）。

### 4.1 峰谷价（早晚不同）

`model_alias.py` 支持 `--slot auto|peak|offpeak`：

- `auto`：Qoder 按 `price_factor_peak` / `price_factor_valley` 和 `off_peak`
  窗口（22:00–08:00，Asia/Shanghai）取当前价；WorkBuddy 用价格表里的 `eff_rate`
  （由 `workbuddy_fetch_pricing.py` 在时段边界刷新）。
- OpenCode-Go：**只有 DeepSeek V4.1 Flash / V4 Pro** 有峰谷价。峰时是 UTC
  周一至周五 01:00–04:00、06:00–10:00（北京时间 09:00–12:00、14:00–18:00），
  其余时间（含夜间和周末）为谷价；其他 OC 模型是固定价。
- `peak` / `offpeak`：显式取峰价 / 谷价，适合手动预演。

**名字不再随价格变化**：峰谷切换只会改变链路顺序、最低价和分组归属
（例如 Qoder 的 DeepSeek-Flash 谷价时进免费组、峰价时并进付费链路），
不会改显示名，老会话不受影响。

现行自动切换（北京时间）：**每天 12:00 一次**，由计划任务 `\ModelBus 模型同步`
调 `sync-models.vbs → sync-models.ps1`；第四段跑 `--slot auto --apply`，按运行时刻
取价，第五段落报告后刷新 `%LOCALAPPDATA%/ModelBus/current-models.json` 单一真值视图。

早期这里写「08:00 / 22:00 加工作日 09:00 / 12:00 / 14:00 / 18:00 各跑一次」，
属于过度承诺：完整流水线带榜单 `--write`、探活、漂移二轮写入等副作用，
`model_alias.py` 每次 `--apply` 还会刷新 `generated_at`，同参连跑两次 alias map
逐字节不同，多时段重跑会把「有漂移」误报成日常状态（推送自 2026-11-09 起已默认关闭，
只有显式 `-Push` 才提交，见 [MAINTENANCE.md](MAINTENANCE.md) §6）。
峰谷价本身仍由 `--slot auto` 在每次运行时按当前时间取价（见上文），
只是不再为边界时刻额外注册任务：下一次 12:00 同步会自然纠正。

手动预演仍可用：

```bash
python providers/workbuddy/workbuddy_fetch_pricing.py
python tools/model_alias.py --slot auto --apply
```

### 4.2 主力扩充（外部榜单，默认关闭）

2026-10-28 起**默认只用人工 `MAIN_IDS`**，榜单扩充需要显式 `--arena`。

1. **人工**：`model_alias.py` 里的 `MAIN_IDS`，按厂商/额度/协议挑，不随榜单变；
2. **榜单（opt-in）**：`tools/arena_leaderboard.py` 拉 ArenaGalleri 实时榜，按
   「分数 ≥ DeepSeek 基准 95%、积分 ≤ 0.11、非临时、≥50 局、积分 > 0」筛出候选，
   写 `~/.zcode/v2/arena-main.json`；`model_alias.py` 默认读它，任意一跳命中
   `(channel, upstream)` 就放进主力。

```bash
python tools/arena_leaderboard.py --refresh --apply   # 重拉 + 落候选 + 重写三组
python tools/arena_leaderboard.py --status            # 看当前候选
python tools/model_alias.py --no-arena --apply        # 回到纯人工主力（默认即是）
```

- 榜单口径、名字映射与 2026-10-23 的候选表见 [BENCHMARKS.md](BENCHMARKS.md) §8。
- **免费条目不进主力**（价格 = 0 留在免费组）；榜单掉出窗口的模型退回价格分组。
- 榜单每 10 分钟更新，但只有候选集合或规则变化才重写配置；分数波动不会引起 ID 抖动。
- 候选按谷价/eff/valley 判断，峰时切价不会改变主力成员。

## 5. 协议桥接

`gateways/zgate` 内置协议桥（原 `tools/protocol_bridge.js` 已退役），把 chat 请求转成：

- Anthropic Messages（`/v1/messages`，`x-api-key` + `anthropic-version`）
- OpenAI Responses（`/v1/responses`，Bearer）

上游按 **`stream: true`** 调用，桥接器边收边转成 chat SSE（2026-10-29 起）：
文本、`thinking` 推理、以及**工具调用增量**都是逐块转发，首字不再等整段生成完。

- 工具调用双向转换：`tools` / `tool_calls` / `tool_use` / `function_call`；
  流式下 `content_block_start`(tool_use) → `input_json_delta` → chat
  `tool_calls` 增量，收尾 `finish_reason` 为 `tool_calls`。
- **只有链尾跳走流式**：前面某跳失败还要能回落，已写出的半截 SSE 收不回来，
  所以非尾跳仍整段缓冲后一次写出。
- 上游在写出任何 chunk 前就报错（4xx/5xx）时，桥接器把真实错误码经 JSON
  回给客户端，不会留下一个挂起的空流。
- **空闲看门狗**：上游连上后连续 30 秒没有任何字节，桥接器主动断开并返回
  `504 upstream_timeout`（`DefaultIdle`）。没有它，静默的聚合端点会一直等到
  120 秒总超时，用户端就是「两分钟没响应」。
- **429 处理**：先就地退避 700ms 重试同一跳一次；仍 429 才短冷却 45 秒；
  桥接上游静默超时冷却 5 分钟；模型不存在 / 额度耗尽等死跳仍冷却 30 分钟。
- 链路里的桥接跳失败（5xx / 429 / 503）会自动换下一跳。

---

## 6. 生成与探测

```bash
# 0. 重拉外部榜单，更新主力候选（候选没变时不会触发重写）
python tools/arena_leaderboard.py --refresh --write

# 1. 用真实 ZCode body 探测全部模型（经 7871，按 provider 套用 optionSpecs）
python tools/model_probe.py

# 2. 生成三组 + alias map；只保留探测 ok（或曾 ok 的瞬时限流）的模型
python tools/model_alias.py --slot auto --arena --scores \
  --probe-file ~/.zcode/v2/model_probe.json --apply

# 3. 漂移自检：重算结果应与刚落盘的 alias map 完全一致（退出码 0）
#    参数必须和上一步一模一样 —— 只写 --check 时，arena 把某个型号从省钱提到主力
#    会被当成漂移，每天都要无效重写两轮
python tools/model_alias.py --check --arena --scores \
  --probe-file ~/.zcode/v2/model_probe.json
```

- **顺序不能颠倒**：探活要在第一轮 `--apply` 之后跑。本轮新补进配置的型号（例如
  白名单补入的 `cn:hy4std`）在第一轮之前根本不在配置里，探不到它，第二轮带
  `--probe-file` 时会被判成 `probe not probed` 直接跳过。`sync-models.ps1` 的第四步
  就是按「apply → 探活 → 带 probe 再 apply」这个次序写的。
- **白名单是权威，但只管排序不管建档**：条目只从 `provider_config` 与池子文件生成，
  所以白名单点名一个配置里没有的型号时，`whitelist_items()` 会从价格源补一条候选
  （按裸名比对，没有渠道前缀的写法不会被另猜一个渠道）。补进来的条目持有
  `whitelisted` 标记，不受 `LOW_MAX` 价格闸与 `VENDOR_QUOTA` 配额限制。
- 探测结果只在 72 小时内有效（`--probe-max-age-hours`）；过期按「未知」处理，
  **未知不删除**。每条记录都写 `checked_at`，没有它的记录会被整份当成过期。

- 只预演：去掉 `--apply`。
- 备份：`provider_config.json.bak-alias-<时间戳>`。
- 回归测试：`python -m unittest discover -s tests -v`（价格派生、死跳剔除、漂移检测、
  探测过期）。
- 旧 ID（`cn:` / `global:` / `qoder:` / 裸 OC，以及旧的 `W/0.03/…` 显示名）会进
  alias map 的 `legacy`，老会话仍可路由；改名链会自动追到最终名字。
- 旧的 `workbuddy_zcode_sync.py` / `go_model_sync.py` / `qoder_zcode_sync.py`
  现在只当**数据采集器**：它们写旧 ID，随后由 `model_alias.py` 归一化。不要
  在 `model_alias.py` 之后单独跑它们的 `--apply`，否则会临时把旧 ID 写回去
  （实测会把 `cn:*` 原始 id 混进分组的 `personalModelIds`，下一次生成的命名顺序
  也会跟着变）。

---

## 7. 已知边界

- 价格不进 ID 后，**改名只发生在型号/版本变化时**；峰谷切换只影响分组归属。
- 峰谷重写按 §4.1 的时段跑；不跑则分组停在最后一次生成的时段。
- `no_healthy_account` / `400 model_unavailable`（WorkBuddy 池冷却或模型级限流）
  会触发下一跳；没有下一跳时才报 502。
- `deepseek-v4-flash-vision-exp` 没有公布价格，暂不收录；`minimax-m2.7` 价格已公布
  （$0.30/$1.20 → 积分 0.22），2026-10-26 起收录。
- 桥接模型已改为流式（§5）；**非链尾跳**仍是整段缓冲，这是为回落安全付出的代价。
- 上游自己不流式时（实测 Qoder 渠道整段缓冲，首字 ~32s），桥接器无法改变，
  只能等上游；这类慢模型不要放进主力。
- 别名表是本地活数据，不入库；`provider_config.json` 与备份同样不入库。
- 榜单接口不可用时用本地缓存；缓存也没有就跳过扩充，人工 `MAIN_IDS` 仍生效。
- 同名不同协议的条目靠 `-Msg` / `-Resp` 区分；免费条目默认不加后缀，只有与
  付费条目**真重名且无法合并**时才加 `-Free`。

---

## 9. 维度补遗（2026-11-11 记忆合并落地）

> 本节收录链序、目录条数、档位投影、守门前提、ondemand 唤醒五组判据；每节只写仓内别处没有或已过时的部分。

### 9.1 链序第一维：`CHANNEL_RANK`（`TAIL_HOPS` 已退役）

链序是**三维排序**：渠道 rank → 跳级优先级 → 折算价升序。第一维现值：

| rank | 渠道 | 语义 |
|---|---|---|
| 0 | WB | 额度优先消费，固定链首，不看价格；`WB_FIRST_CHANNELS` 另做硬保护 |
| 1 | OC / QD / GM / HJ | 平价付费档，同档内按价格排 |
| 2 | QW | 一年期预付额度，排在所有付费跳之后（原 `TAIL_HOPS` 的等价表达） |
| 3 | QN | 限免渠道排最后；免费不等于优先烧，价值是兜底 |
| 4 | 未登记渠道 | `CHANNEL_RANK_DEFAULT` |

第二维 `HOP_PRIORITY` 只服务「同价多跳」：GM 的 7 个 Gemini Flash 档同价，靠 (价格, upstream 字符串) 排会把 `3.5` 排到 `3.8` 前面，于是把「新一代先试」写成显式数字表（0…6），表外取 99，行为与此表引入前一致。

`TAIL_HOPS` 常量已从 `tools/model_alias.py` 删除，被 `CHANNEL_RANK` 取代（散落在旧记忆与历史台账里的 `TAIL_HOPS` 一律按 rank 2/3 读）。

**`DEMOTE_HOPS` 不可复活**：把 WB 跳降到 OC 之后躲限流，曾导致整条会话静默跑在 opencode 上计费。限流只许由 zgate 逐跳回落处理，回归由 `tests/test_model_alias_hop_order.py` 守。

### 9.2 目录条数的四个数：20 / 47 / 56 / 73

| 数 | 含义 | 出处 |
|---|---|---|
| 20 | alias 聚合后的模型条数，= zgate `canonical` 命名空间条数 | `model-alias-map.json` `models` 键数 |
| 47 | 20 条名下的跳数总和（一条链 1～4 跳） | 逐条累加 `chain[].length` |
| 56 | WB 面板对话目录条目（cn 22 + global 34）；网关未重启时只有 34 个 global | `/panel/api/models` |
| 73 | 历史 id → 现值 id 的映射条数（legacy 命名空间） | `model-alias-map.json` `legacy` |

`canonical` / `legacy` 分段与 93 = 20 + 73 在 [ROUTING-POLICY.md](ROUTING-POLICY.md) §scope 表已有，本节只补「四数并列 + 47 跳 + 56 面板」的对照与判据。

判据：**面板条数属「CLI 菜单口径」，`/v1/models` 条数属「网关承诺口径」，两者不必相等也不该相等。**「面板 56 个、`/v1/models` 20 个」是正常态。查一个名字是否还在，用 `?scope=all` 看它是否只以 legacy 身份存在 —— 只在 legacy 意味着「可以继续用，但新配置不该再用这个名字」。

### 9.3 档位投影到客户端：四层链与 `_efforts_lost` 守门

ZCode `optionSpecs.reasoningLevel.values` 只是第二层，之后还有请求体与客户端投影两层，任一断链都表现为「只剩一个默认档」：

| 层 | 正本 | 断链现象 | 判据 |
|---|---|---|---|
| L2 | `values`（末位 = 默认档） | 下拉只有开关 | 读配置 values 是否为空 |
| L3 | `map` 表达式 | 档位可选但不生效 | `node providers/workbuddy/zcode_effective_body.js <模型id>` |
| L4 | `tools/dsh_sync.py` `_reasoning()` | 客户端档位消失或只剩 Default | `python tools/dsh_sync.py --check` |

L4 投影规则（顺序不可换）：`map` 为 `"{}"` → 直接给空档位；否则取 `DSH_LEVELS = {off,minimal,low,medium,high,xhigh,max}` 内的项；含 `disabled` 时加 `off → disabled`，若除 `off` 再无档位则补 `high → high`；仅当 `map` 含 `reasoning_effort` 才追加 `compat.thinkingFormat="deepseek"`（Gemini 系与「只有开关」的模型套 deepseek 格式会发上游不认的字段）。不在 `DSH_LEVELS` 又非 `disabled` 的档位名**静默丢弃**。

两种 drift 要分开判：

| 类型 | 判据 | 表现 |
|---|---|---|
| alias drift | `model_alias.py --check` 同参数复算与现有 map 不一致 | 退出 1，不写盘 |
| 投影 drift | `_efforts_lost()`：源头 values 非空、投影为空 | `--check` 失败 / `--apply` WARN |

反方向（源头退化、客户端保留旧档位）由 `_keep_efforts()` 承接，属**刻意保留，不算漂移** —— 把它也报出来会让每日检查长期红，最后没人看。

### 9.4 守门规则的三条生效前提（现网现值）

`reasoningGuard` 只有三条同时成立才真的重抽，缺一条就静默不上场：

| 序 | 条件 | 现值 |
|---|---|---|
| ① | mode 覆盖该模型 | `mode="channels"`，`models=["Iceman","iceman-contributor-free"]` |
| ② | 请求被判为「期望思考」 | `guardApplies` 首行 `!reasoningExpectsThinking` 直放 —— **body 必须真带 `reasoning_effort`** |
| ③ | 允许再抽 | `maxRetries=1`、`probeSeconds=15`、`maxProbeBytes=32768` |

兜底两条：`forceEffort="high"` + `forceEffortModels` 两项（补回条件②的字段）；`giveUpAfter=1` / `giveUpForSeconds=600` 学习表是**内存态**，重启清零。`injectNotice=false`：那段提示按「跳过窗口」状态显示，与思考块是否明文无关，会让人以为已经跳过而实际仍在等 15 秒；关它不改变等待时长，改动后 `POST /admin/reload` 热加载。

调不动的旋钮：`probeSeconds` / `maxRetries` 调大只会让等待变长；上游双后端随机分流回加密 blob 时，没有任何参数能强制明文。

### 9.5 ondemand 子进程：用一个「别名表里不存在」的名字唤醒

zgate 的 `routeAttempt` 走 `bridge.Forward` 时**不会**调用 `s.prepare()`，只有 `routeFallback` 末尾才会 prepare。所以想唤醒一个 `ondemand` 子进程，必须拿**不在 alias map 里的模型名**发请求：名字一旦在别名表里，请求会被当成正常路由直接转发出去，子进程永远不启，表现为长时间挂住而不是报错。同理，判断端口是否被占要 `dial` 而不是 `bind` —— 同端口 `net.Listen` 能成功，`bind` 判占用必然误判成「没占」。

---

## 8. 相关

- 价格 / 协议来源：[MODEL-PROVIDERS.md](MODEL-PROVIDERS.md)
- 外部榜单与主力扩充口径：[BENCHMARKS.md](BENCHMARKS.md) §8
- 工具清单：[TOOLS.md](TOOLS.md)
- 日常维护：[MAINTENANCE.md](MAINTENANCE.md)
- Qoder 专用链路：[QODER.md](QODER.md)
