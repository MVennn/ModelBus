# ModelBus 配置校验 × 推理档位保活 —— 链路地图（只读取证）

> **一句话**：zgate 侧对 `channelPolicy` 既不填默认值也不做任何校验（唯一等价自检 `ValidatePolicies` 写好了但**没有调用点**），所以「单跳渠道配了 channelPolicy」当前不会报错；两个 Python 脚本的档位保活改动把「写盘」与「守门」共用同一套继承逻辑，`--check` 与 `--apply` 走的是同一份函数，只是落盘分支不同。

---

## 0. 快照指纹与并发警告

调查期间 `config.go` / `router.go` / `race.go` / `policy.go` **正在被另一个会话持续修改**（14:52:46Z → 14:54:37Z 之间四次写入，改的是「策略逐跳取值 + 链首字节预算」）。本文件所有行号以**下表快照**为准；行号对不上时按下表 sha 判定版本，用「锚点字符串」grep 重新定位。

| 文件 | sha256(前12) | 行数 | mtime (UTC) |
|---|---|---|---|
| `gateways/zgate/internal/config/config.go` | `9d7602b86d29` | 510 | 2026-11-10T14:52:46Z |
| `gateways/zgate/zgate.json` | `1f2247bb2a0f` | 77 | 2026-11-10T13:22:56Z |
| `gateways/zgate/internal/router/router.go` | `0d921b6967b0` | 2383 | 2026-11-10T14:54:37Z |
| `gateways/zgate/internal/router/race.go` | `b57f96636003` | 644 | 2026-11-10T14:54:26Z |
| `gateways/zgate/internal/router/policy.go` | `5529055522f9` | 177 | 2026-11-10T14:53:57Z |
| `tools/model_alias.py` | `887355eddfda` | 2532 | 2026-11-10T13:15:29Z |
| `tools/dsh_sync.py` | `7427e00d318a` | 610 | 2026-11-10T13:17:29Z |

常用锚点（行号漂移时用这些字符串重新 grep）：`ChannelPolicy 是「按渠道」的路由策略`、`func ValidatePolicies`、`racePlan 是一条链的`、`def drifted_efforts`、`def _efforts_lost`。

---

## 1. `gateways/zgate/internal/config/config.go`

### 1.1 类型清单

| 类型 | 行号 | 说明 |
|---|---|---|
| `Log` | 15-20 | 日志目录/文件/maxMB |
| `Upstream` | 22-27 | `Base` / `Child` / `KeyEnv` |
| `Child` | 35-47 | 子进程：`Policy` / `IdleSeconds` / `Exe` / `Args` / `Cwd` / `Port` / `Health` / `StartTimeoutSeconds` / `Windows` |
| `ReasoningGuard` | 67-97 | 思考档位探针；`ProbeSeconds` 在 95-96 |
| `ChannelPolicy` | 104-140 | **本文主角**，见 1.2 |
| `Config` | 141-186 | 全局配置，见 1.4 |

### 1.2 `ChannelPolicy` 全部字段与零值语义（:104-140）

定义前有一段总体说明（原文）：

```
// ChannelPolicy 是「按渠道」的路由策略，只对显式配置过的渠道生效。
// 零值 = 全关 = 老行为逐字节不变：没有配置 channelPolicy 的渠道完全走原来的
// 串行链 + 30min/45s 冷却逻辑。
```

| 字段 | 行号 | JSON 键 | 零值语义（= 老行为） | 消费点 |
|---|---|---|---|---|
| `SoftCooldownSeconds` | 108 | `softCooldownSeconds` | 0 = 5xx 不冷却（仅 504 按 5min） | `router.go:152-158` 取值、`router.go:1632` 触发 |
| `SilenceCooldownSeconds` | 114 | `silenceCooldownSeconds` | 0 = 首块静默不冷却 | `router.go:161-167` 取值、`router.go:1015`/`1185` 触发 |
| `RateLimitBackoffMs` | 117 | `rateLimitBackoffMs` | 0 = 429 就地退避 700ms 再试同一跳；**负数 = 不就地重试直接换跳** | `router.go:950`（`inPlace429`） |
| `FirstBlockMs` | 122 | `firstBlockMs` | 0 = 关（空流一直挂着） | `router.go:955-956`、`1149`、`1188` |
| `HedgeAfterMs` | 125 | `hedgeAfterMs` | 0 = 不对冲 | `race.go:358`（每跳取最小正值） |
| `MaxParallel` | 127 | `maxParallel` | 0 = 2（最多叠一层） | `race.go:353-355`、`376-378` |
| `AuthFailCooldownHours` | 130 | `authFailCooldownHours` | 0 = 403 原样回客户端 | `router.go:242-252`、`router.go:1610` |
| `HeaderTimeoutSec` | 134-139 | `headerTimeoutSec` | 0 = 继承全局；**负数 = 该渠道不设看门狗** | `router.go:344-363` |

### 1.3 `ChannelPolicy` 在 config 包里的“全生命周期”：只有 3 处引用

grep `ChannelPolicy` 在 `config.go` 只命中三行：注释 `:99`、类型定义 `:104`、字段声明 `:179`。

```
178|	ChainBudgetSec int                      `json:"chainBudgetSec"`
179|	ChannelPolicy  map[string]ChannelPolicy `json:"channelPolicy"`
```

即：**没有任何默认值填充、没有任何合法性校验、没有渠道名枚举校验**。

### 1.4 `applyDefaults()` 范围与关键默认值

`func (c *Config) applyDefaults()` 在 `:223`，到 `:395` 结束（`:397` 是 `resolvePaths`）。

| 项 | 行号 | 默认值 |
|---|---|---|
| `Listen` | 224-229 | `127.0.0.1:7871`，可被 `ZGATE_LISTEN` 覆盖 |
| `AliasMap` | 230-235 | `~/.zcode/v2/model-alias-map.json` |
| `ProviderConfig` | 236-241 | `~/.zcode/v2/provider_config.json` |
| `ReasoningGuard` | 248-273 | `MaxRetries=5`、`MaxProbeBytes=32768`、`Mode=auto`、`ProbeSeconds=12` … |
| `StreamIdleHeartbeatSeconds` | 291-294 | 15 |
| `EarlyCommitMs` | 297-299 | 8000（写 0 会被归一成 8000，关闭只能写负数） |
| `ChainBudgetSec` | 300-304 | 90（**新增**，见 1.6） |
| `EarlyKeepaliveSec` | 305-307 | 10 |
| `UpstreamHeaderTimeoutSec` | 308-310 | 12 |
| `Log` | 311-320 | `%LOCALAPPDATA%/ZCodeGateway` + `zgate.log` + 5MB |
| `Upstreams` | 322-380 | 兜底 OC/WB/QD/QW/QN/GM/HJ |
| `Children` | 381-394 | `IdleSeconds=900`、`StartTimeoutSeconds=25` |

**`applyDefaults` 一个字都没碰 `channelPolicy`**——这正是「零值 = 老行为」赖以成立的前提，也让「配了但字段全是 0」等于没配（除了 1.5 说的那一个副作用）。

### 1.5 校验函数在哪：`config` 包没有，等价物在 `router/policy.go:133`

`config.Load` 全文只有四步（`:189-221`）：`os.ReadFile` → `json.Unmarshal` → `applyDefaults()` → `resolvePaths()`，**没有 validate 分支**，也没有对未知渠道名/未知字段做拒绝。

真正的「策略 ↔ 链形态」自检写在 router 包里：

```
126|// ValidatePolicies 对照实际 alias 链检查 channelPolicy：
128|//   - 渠道**只**服务单跳模型、却配了对冲/冷却类字段 → Fatal（这些字段永远不会被读到，
129|//     留着的人会以为「对冲已经开了」…）
131|//   - 渠道同时服务多跳模型 → 只提示，不拦…
133|func ValidatePolicies(cfg *config.Config, am *alias.Map) []PolicyNote {
```

判据细节（`:85-106` `policyRaceFields`）：参与 Fatal 判定的字段只有 6 个 —— `hedgeAfterMs`、`firstBlockMs`、`maxParallel`、`silenceCooldownSeconds`、`softCooldownSeconds`、`rateLimitBackoffMs ≠ 0`。**`authFailCooldownHours` 与 `headerTimeoutSec` 不在判据里**，只配这两个不会触发任何告警。

**关键事实：`ValidatePolicies` 全仓没有任何调用点。** grep `ValidatePolicies` 在 `gateways/zgate` 只命中 `policy.go` 自身的注释与定义（`:9`、`:126`、`:133`），`router.New(:330-335)` 与 `keys.Load`/`ApplyConfig` 路径都不调它。同一份文件里 `withChainContext` 也只剩 `:64` 定义 + `router.go:1419` 一处调用（只传单跳标记，预算恒传 0），`s.chainBudget()`（`:75`）**零调用**。

### 1.6 结论：当前会不会对「单跳链的渠道配了 channelPolicy」报错？**不会**

三层理由，缺一不可：

1. `config.Load` 没有校验步骤（`:189-221`），JSON 里写什么都是静默接受；渠道名拼错同样静默（消费点处处是 `, ok` 取值，如 `router.go:198`、`router.go:349`）。
2. 唯一等价校验 `ValidatePolicies` 未接线 —— 写了 Fatal 判定分支，但没人调用，进程该起还是起。
3. 即使将来接线，也**不是**「单跳渠道配 policy」就报错，而是「该渠道**只**服务单跳模型 + 配了那 6 个字段」才 Fatal。按当前 alias 拓扑（第 6 节表），WB 与 QD 同时服务多跳链 → 只会提示；QN（只有 Conatus 单跳）与 QW（从不做链首）只要配上 `softCooldownSeconds`/`hedgeAfterMs` 之类就会 Fatal。

另外两点值得记在案：`ChainBudgetSec` 缺省 90(`:300-304`) 目前**完全无效**（`chainBudget()` 无调用点），所以 `headerTimeoutSec: -1` 的渠道在链层没有兜底上界；`config_test.go` 只测 ReasoningGuard，`channelPolicy` 零测试覆盖。

---

## 2. `gateways/zgate/zgate.json` 现状（77 行）

### 2.1 `channelPolicy` 只有两个渠道（`:14-28`）

| 字段 | `GM`（`:15-24`） | `HJ`（`:25-27`） |
|---|---|---|
| `softCooldownSeconds` | 60 | 未写（0） |
| `silenceCooldownSeconds` | 0 | 未写（0） |
| `rateLimitBackoffMs` | -1 | 未写（0） |
| `firstBlockMs` | 0 | 未写（0） |
| `hedgeAfterMs` | 18000 | 未写（0） |
| `maxParallel` | 2 | 未写（0→2） |
| `authFailCooldownHours` | 24 | 未写（0） |
| `headerTimeoutSec` | -1 | **-1** |

### 2.2 `upstreams` 名称清单（`:43-51`，共 7 个）

| 名 | base | child / keyEnv | 行号 |
|---|---|---|---|
| `OC` | `https://opencode.ai/zen/go/v1` | — | 44 |
| `WB` | `http://127.0.0.1:7863/v1` | child `workbuddy` | 45 |
| `QD` | `http://127.0.0.1:8790/v1` | child `qoder` | 46 |
| `QW` | `https://maas.qianwenaiapi.com/apps/anthropic/v1` | `QWEN_API_KEY` | 47 |
| `QN` | `https://api.qnaigc.com/v1` | `QINIU_API_KEY` | 48 |
| `GM` | `https://catiecli.sukaka.top/v1` | `GEMINI_API_KEY` | 49 |
| `HJ` | `https://api.gemai.cc/v1` | `HJM_API_KEY` | 50 |

### 2.3 完全没有 policy 的渠道：`WB` / `OC` / `QD` / `QN` / `QW`（5 个）

### 2.4 其它全局项

| 项 | 值 | 行号 |
|---|---|---|
| `streamIdleHeartbeatSec` | 15 | 12 |
| `upstreamHeaderTimeoutSec` | 45 | 13 |
| `reasoningGuard` | enabled / mode=models / models=[Iceman, iceman-contributor-free] / maxRetries 1 / probeSeconds 15 / giveUpAfter 1 / forceEffort high | 29-41 |
| `children.workbuddy` | ondemand / idle 300 / `wb2api.exe` / port 7863 / startTimeout 30 / windows 四条 | 53-63 |
| `children.qoder` | ondemand / idle 300 / `python qoder_proxy.py --port 8790` / startTimeout 40 / windows 三条 | 64-74 |

---

## 3. 「档位保活」未提交改动的语义

git status：`tools/model_alias.py`、`tools/dsh_sync.py` 均为 `M`（未提交）。新增测试文件 `tests/test_model_alias_efforts.py`、`tests/test_dsh_sync_efforts.py` 处于 `??` 未跟踪状态。

### 3.1 `tools/model_alias.py`（2532 行，新块 608-815）

| 函数/常量 | 行号 | 做什么 | 被谁调用 | 生效模式 |
|---|---|---|---|---|
| `EFFORT_CHANNELS` | 621 | 档位“真能发出去”的渠道白名单 `("WB","QD","OC","QN")` | `_effort_is_live` | 全部 |
| `_effort_values(rule_config)` | 624-630 | 取 `config.optionSpecs.reasoningLevel.values`，非 list 返回 `[]` | 多处 | 全部 |
| `_blank_effort_global(cfg)` | 633-640 | 整份配置一条档位都没有 = 上一轮被冲空（读取侧自愈开关） | `pick_rule_config`、`_inherit_efforts` | apply + check（经 `pick_rule_config`） |
| `EMPTY_ALLOWED` | 645 | 允许长期无档位的模型集合，**当前为空** | `drifted_efforts` | 仅 check |
| `drifted_efforts(cfg)` | 647-689 | 在内存里重算一遍继承链，报「上一轮有档位、这一轮算出为空」和「本来就是空、这轮也补不回来」两类；异常只 WARN 不崩（`:686-689`） | `main` 的 `--check` 分支 `:2327` | **仅 `--check`** |
| `pick_rule_config(entries, cfg, old_rules)` | 692-712 | 按 `raw`/`original`/`upstream`/`channel`/`name` 找旧 config 再 `_inherit_efforts`，返回 `{name: config}`，**不落盘** | `drifted_efforts:674`、写盘分支 `:2385` | apply + check |
| `_inherit_efforts(...)` | 715-740 | **只补不清**：自己已有可生效档位就一个字不动；没档位就从同族兄弟继承；落在“装饰渠道”才 `pop("reasoningLevel")`（`:733-738`，且只在全局非空时做） | `pick_rule_config:710` | apply + check |
| `_effort_is_live(entry, reasoning)` | 743-758 | 档位是否真能发出去：渠道在 `EFFORT_CHANNELS`，或 `map` 有非 `"{}"` 的表达式 | `_inherit_efforts`、`_enforce_non_chat_effort` | apply + check |
| `_enforce_non_chat_effort(config, entry)` | 761-780 | 非 chat 协议（messages/responses）：无 values → map 归 `"{}"`；live 则保留；否则 `pop values` + map 归 `"{}"` | 写盘分支 `:2414` | **仅 `--apply`** |
| `_same_family(base, other)` | 783-790 | 去掉最后一个 `-` 后缀后相同即同代（`mimo-v2.6-pro` / `-flash`） | `_sibling_effort` | apply + check |
| `_sibling_effort(entry, old_rules, entries)` | 793-813 | 同族、非 pool 条目里**已落盘**的档位 | `_inherit_efforts` | apply + check |

接入点（同一份逻辑被两处共用，这是改动的核心意图）：

```
2322|    if args.check:
2325|        # 档位守门：这一轮算出来的继承链会抹掉已落盘档位就判失败。
2327|        lost_efforts = drifted_efforts(cfg)
2334|        return 1 if (any(drift.values()) or lost_efforts) else 0
```

```
2382|    # 档位继承走 pick_rule_config：写盘与 --check 的漂移守门必须共用同一套逻辑，
2385|    inherited_configs = pick_rule_config(all_rows, cfg, old_rules)
2404|            config = copy.deepcopy(inherited_configs.get(str(row["new_id"])) or {})
2414|                _enforce_non_chat_effort(config, row)
```

`old_rules`（继承源）在 `:2114-2116` 构建，`sync_deepseek_harness(path)` 在 `:2525-2526` 调用，条件是 `not args.no_dsh and args.config is None`（即 `--apply` 且未显式指定 `--config`）。

**一处实现细节值得钉住**：`drifted_efforts` 的落盘快照必须在 `pick_rule_config` 之前取，且 `old_rules` 要 `deepcopy` 与 `work` 分离内存（`:664-673`）。否则 `pick_rule_config` 把继承结果写回同一份对象，比出来永远“没变”，守门变哑——代码注释里写着这是 2026-11-10 的实测事故。

### 3.2 `tools/dsh_sync.py`（610 行）

| 函数/常量 | 行号 | 做什么 | 被谁调用 | 生效模式 |
|---|---|---|---|---|
| `_USES_EFFORT_FIELD` | 73 | `re.compile(r"reasoning_effort")`，判断源头 map 是否真用 OpenAI 风格档位字段 | `_reasoning:297`、`:304` | 全部 |
| `_efforts_outside(values)` | 196-203 | 档位里 DSH 表达不了的部分（不在 `DSH_LEVELS` 且不是 `disabled`） | **无人调用（死代码）** | 无 |
| `_efforts_lost(rules, routes)` | 206-229 | 只报「源头有 values、投影 `reasoningEfforts` 为空」；反向退化由 `_keep_efforts` 兜，不算漂移 | `_main:564` | 全部（结论只在 check/apply 用） |
| `_reasoning(values, map_expr)` | 281-306 | 改动点：只有 map 里出现 `reasoning_effort` 才加 `compat.thinkingFormat=deepseek`（`:297-299`、`:304-305`），否则不加 | `_build_route` | 全部 |
| `_keep_efforts(routes, old_providers)` | 393-423 | 新路由没算出档位就沿用旧 patch 的 `reasoningEfforts`（连 `compat`），算出了以新为准；打「保留已有推理档位：」(`:422`) | `_merge_patch:431` | **全部模式（含 --check / dry-run）** |

`_merge_patch` 在 `_main:553` 被**无条件**调用（早于所有模式分支），所以 `_keep_efforts` 在 `--check` 与裸 dry-run 里同样执行 —— 这意味着 `--check` 看到的 `reasoningEfforts` 已经被旧值补过，`_efforts_lost` 只有在「源头非空 **且** 旧 patch 也为空」时才会报。

### 3.3 影响面速查

| 函数 | `--check` | `--apply` | 裸 dry-run |
|---|---|---|---|
| `drifted_efforts` / `EMPTY_ALLOWED` | 是 | 否 | 否（`:2336-2338` 先 return 0） |
| `pick_rule_config` / `_inherit_efforts` / `_sibling_effort` / `_same_family` | 是（守门重算） | 是（决定写盘） | 否 |
| `_enforce_non_chat_effort` | 否 | 是 | 否 |
| `_keep_efforts` / `_efforts_lost` / `_reasoning` | 是 | 是 | 是 |

### 3.4 一个小的分支顺序问题（不影响安全，但会让 WARN 少一条）

`dsh_sync.py:595-600`：`if not changed and not key_changed:` 分支排在 `elif lost:` 之前，所以「有 lost 但模型表无变化」时不会打那句 `WARN: 上面列出的模型在源头有档位、投影后为空…`。lost 明细本身在 `:565-568` 已无条件打到 stderr，信息不丢，只是少了一句提示。

---

## 4. 入口与退出码语义

### 4.1 `tools/model_alias.py`

| 参数/分支 | 行号 | 行为 |
|---|---|---|
| `--apply` | 2025 | 写 `provider_config.json` + alias map，并在 `--config` 缺省时投影到 DSH |
| `--check` | 2026-2027 | 只做漂移检测，不写盘 |
| `--slot`（default `auto`） | 2034-2035 | 取价时段；`--check` 固定按 `auto` 口径重算（`:660-662`） |
| `--force-unpriced` | 2052 | 允许整渠道无价仍写盘 |
| `--no-dsh` | 2054 | `--apply` 时不投影 DSH |
| `return 1` #1 | **2320** | 存在整渠道无价的渠道 **且** 带 `--apply` **且** 未给 `--force-unpriced` |
| `return 1` #2 | **2334** | `--check` 下 `any(drift.values())`（价格/链路漂移）或档位漂移 |
| `return 0` | 2338 | 裸 dry-run |
| `return 0` | 2527 | 写盘成功（含 DSH 投影后） |

注意：`--apply` 与 `--check` **不是**互斥组（与 dsh_sync 不同）；两个都给时 `--check` 分支先 return，`--apply` 被跳过。

### 4.2 `tools/dsh_sync.py`

| 项 | 行号 | 说明 |
|---|---|---|
| `--apply` | 529 | 备份并写入 DSH patch 与凭据引用 |
| `--check` | 530 | 只检测；有漂移退出码 1 |
| 互斥组 | 528 | `add_mutually_exclusive_group()` —— 两个同给会直接 argparse 报错 |
| `return 1` | **571** | `changed or key_changed or lost` |
| `return 0` | 587 | 裸 dry-run |
| `return 0` | 601 | `--apply` 完成 |
| `exit 2` | 604-609 | `DshSyncError` → 打 `ERROR:` 后 `SystemExit(2)` |

退出码一句话：`0` = 无漂移/已写；`1` = 有漂移（model_alias 也可能是“拒绝写盘”）；`2` = 环境/配置错误（dsh_sync 专属）。

---

## 5. 实测（只读，未跑 `--apply`）

执行方式：`run_code` + Node `spawnSync` 直调 `python.exe`（本会话 `ops_bash` 因 hardlink 耗尽不可用，见 `OSError`/`EXECUTOR_UNAVAILABLE`），`PYTHONIOENCODING=utf-8`，PATH 显式包含 node 与 Python 目录。所有输出逐字照抄，**未出现任何凭据**（无需打码）。

### 5.1 `python -B tools/model_alias.py --check` → **exit 1**（4.2 秒）

关键输出（尾部）：

```
发现漂移 4 处（现有 alias map vs 当前价格源重算）：
  价格：Qwen-3.8-Flash  0.09 -> 0.03
  价格：Qwen-3.8-Max  0.43 -> 0.17
  链路：Qwen-3.8-Flash
    旧：QD:Qwen3.8-Flash@0.09 -> OC:qwen3.8-flash@0.09 -> OC:qwen3.8-flash@0.09
    新：QD:Qwen3.8-Flash@0.03 -> OC:qwen3.8-flash@0.09 -> OC:qwen3.8-flash@0.09
  链路：Qwen-3.8-Max
    旧：QD:Qwen3.8-Max@0.43
    新：QD:Qwen3.8-Max@0.17
```

stdout 共 57 行（含 20 个模型的清单），**没有出现「推理档位漂移」字样** → `drifted_efforts(cfg)` 返回空，退出码 1 完全由价格漂移造成。stderr 三条 WARN：

```
WARN: cn:hy4-preview-f 的 credits/list_rate 都缺失，按同族挂牌价 0.29 计费（不当作免费；见 tools/model_alias.py wb_prices）
WARN: QD 价格源不可用（127.0.0.1:8790: <urlopen error [WinError 10061] 由于目标计算机积极拒绝，无法连接。>），已回落到上次成功的倍率快照
```

（第一条出现两次 —— 白名单与链路两条路径各打一次。）QD 价格源当下不可用是**环境事实**，不是脚本缺陷。

### 5.2 `python -B tools/dsh_sync.py --check` → **exit 0**（0.2 秒）

```
ZCode      : 3 个 provider / 20 个模型
DSH 路由   : 主力 3；免费 5；省钱 12
patch      : ~\.dsh\profiles\desktop\cordis.patch.yml
模型表     : 无变化；凭据引用：无变化
```

stderr 为空，无 lost 档位行（`_efforts_lost` 返回空）。

### 5.3 陷阱（实测复现）：PATH 里没有 node 时结论反转

同一条命令，PATH 去掉 node 目录后：

```
$ python -B tools/dsh_sync.py --check   → exit 1
stderr: WARN: 找不到 node 或 zcode_effective_body.js，改用 provider_config 元数据
stdout: 模型表 : 有变化；凭据引用：无变化
```

即 `dsh_sync.py --check` 的绿/红**依赖 node 与 `providers/workbuddy/zcode_effective_body.js` 可用**；计划任务里若 PATH 不含 node，这个门禁会永久变红（假阳性）。

### 5.4 复现命令（CMD）

```bat
cd /d F:\Project\ModelBus
set PATH=~\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin;%PATH%
python -B tools\model_alias.py --check
echo exit=%ERRORLEVEL%
python -B tools\dsh_sync.py --check
echo exit=%ERRORLEVEL%
```

---

## 6. 若要给 WB/OC/QD/QN/QW 补 `channelPolicy`：最小安全值建议

### 6.1 先看三条硬约束（都由当前代码决定，不是风格偏好）

1. **冷却唯一一跳 = 直接 502。** 冷却命中在 `router.go:1453-1456`（`fail("冷却中")` → 下一跳），链走完在 `router.go:1435-1437` 回 `502 all upstreams failed`。当前有 7 个单跳模型：`Conatus`(QN)、`Gemini-3.8-Flash`(HJ)、`HY3-X`/`HY4`/`HY4-Free`/`Space-Bunny`(WB)、`Qwen-3.8-Max`(QD)。**只要某渠道带单跳模型，就不能给它 `softCooldownSeconds`**（5xx 冷却），否则一次上游 503 会把这一个模型锁死整段冷却时间。
2. **单跳保护只覆盖「静默」，不覆盖软冷却/504。** `router.go:1418-1420` 只给单跳链塞 `singleHop` 标记，`router.go:1014` 用它跳过 `markSilence`；`softCooldownSeconds`(`:1632`) 与 `status==504 → timeoutCooldown 5min`(`:1626-1630`) 不看这个标记。所以「静默冷却」对单跳渠道相对安全，软冷却不安全。
3. **一进 map 就激活渠道级 90s 暂停。** `markChannelOffFor`（`router.go:197-205`）的唯一门槛是「渠道名在 `ChannelPolicy` 里」，触发条件是 `poolDown`（401/403/429/503 且 body 含「没有可用的 api key / no available api key」，`router.go:210-224`）——命中即暂停整渠道 90s（`poolCooldown`，`router.go:193`）。这是「配了全 0 的 policy」唯一的额外副作用。

再加两条与对冲相关的事实（这是 14:52-14:54Z 那轮改动带来的变化，与旧文档口径不同）：

4. **对冲不再要求「全链都配 policy」。** `racePlanFor`（`race.go:336-380`）条件只有：≥2 跳、客户端要流式、**每跳协议都是 chat**；然后 `race.go:351-364` 取各跳 `hedgeAfterMs` 的最小正值、`firstBlockMs` 的最小正值，`maxParallel` 取最大（兜底 2）。链首不再特权，`noteSerialChain`（`race.go:390-422`）只在「全链没人要求竞速」时留一行日志。
5. **`headerTimeoutSec: -1` 现在没有链层兜底。** `ChainBudgetSec` 缺省 90 但 `s.chainBudget()` 零调用（`policy.go:75`），`routeChain` 只在单跳时传 `withChainContext(ctx, 0, true)`（`router.go:1419`）。对本地子进程（WB/QD）写 -1 = 子进程卡死时请求一直挂着，只剩 `earlyCommitMs` 8s 交卷 + 心跳在骗客户端。

### 6.2 每渠道一行建议

| 渠道 | 建议值（JSON 片段） | 为什么这么选 |
|---|---|---|
| **WB** | `{"softCooldownSeconds":0,"silenceCooldownSeconds":0,"rateLimitBackoffMs":0,"firstBlockMs":0,"hedgeAfterMs":18000,"maxParallel":2,"authFailCooldownHours":0,"headerTimeoutSec":0}` | WB 扛着 4 个单跳模型（HY3-X/HY4/HY4-Free/Space-Bunny），软冷却一定不能开 → `softCooldownSeconds:0`；静默冷却虽受 `router.go:1014` 保护，但它同样是「唯一一跳」的渠道，静默本身不需要冷却（下一请求自然会重试），保守取 0。`hedgeAfterMs:18000` 是给 `HY3`(WB×3)、`GLM-5.3-Flash`、`MiniMax-M3.1-Flash`、`MiMo-2.6-Pro` 这四条全 chat 多跳链用的——18s 与 GM 的既有值对齐，单跳链在 `race.go:337` 直接 false，完全不受影响。`headerTimeoutSec:0` 继承全局 45s：WB 是本地 `wb2api.exe`，「45 秒不给响应头」几乎只可能是子进程卡死，需要一个上界（且链预算当前不可用）。`authFailCooldownHours:0`：WB 的 401 是本机 key 配置问题，写死小时级禁用会把主力渠道整天摁住。 |
| **OC** | `{"softCooldownSeconds":60,"silenceCooldownSeconds":20,"rateLimitBackoffMs":-1,"firstBlockMs":0,"hedgeAfterMs":0,"maxParallel":2,"authFailCooldownHours":0,"headerTimeoutSec":0}` | OC 是唯一**从不做单跳**的渠道（11 条多跳链：链首 6、中间 6、链尾 10），所以软冷却/静默冷却都没有「冷却唯一一跳」的风险，可以放心开：5xx 冷却 60s 跨过 opencode.ai 的 503 窗口，静默冷却 20s（比软冷却短，符合 `config.go:109-113` 的设计意图）。`rateLimitBackoffMs:-1`：429 时不再白等 700ms，直接落到下一跳（OC 后面常有孪生 OC 跳或链尾兜底）。`hedgeAfterMs:0`：OC 链里值得对冲的只有 `Iceman`(OC→OC) 与 `MiMo-2.6-Flash`(OC→OC)，两跳是**同渠道同上游**，对冲等于并发打同一个 key，收益是首字更快、代价是 2 倍计费与更早撞 429——要开就单独开（见 6.3）。`headerTimeoutSec:0`：OC 的慢是真的慢（iceman 首块 51.9s 属流内静默，靠 `streamIdleHeartbeatSec` 兜，与头超时无关），45s 头超时对 opencode.ai 不算紧。 |
| **QD** | `{"softCooldownSeconds":0,"silenceCooldownSeconds":20,"rateLimitBackoffMs":-1,"firstBlockMs":0,"hedgeAfterMs":0,"maxParallel":2,"authFailCooldownHours":0,"headerTimeoutSec":0}` | QD 有唯一一个单跳模型 `Qwen-3.8-Max` → `softCooldownSeconds` 必须 0（5xx 会直接把它变 502）。静默冷却可以给 20s：单跳链由 `router.go:1014` 跳过埋点，多跳链（`GLM`/`MiniMax`/`Qwen-3.8-Flash`）里 QD 是中间跳，冷却能省掉「每请求先撞一遍 40s 才启动的 python 代理」；再说 QD 子进程未就绪已由 `prepare()`(`router.go:1464-1468`) 快速失败兜住。`rateLimitBackoffMs:-1`：Qoder 的 429 换跳比原地等更划算（链上 OC 通常可用）。`hedgeAfterMs:0`：QD 所在链的瓶颈是子进程冷启动（`startTimeoutSeconds:40`），对冲会在启动窗口里再压一路，反而更糟。 |
| **QN** | **建议不配**（若必须占位：`{"softCooldownSeconds":0,"silenceCooldownSeconds":0,"rateLimitBackoffMs":0,"firstBlockMs":0,"hedgeAfterMs":0,"maxParallel":2,"authFailCooldownHours":0,"headerTimeoutSec":0}`） | QN 只服务 `Conatus` 一条**单跳**链：任何冷却都等于「把唯一的模型关一会儿」，任何对冲都进不了 `racePlanFor` 的 ≥2 跳门槛。全 0 配置的唯一效果是激活 `markChannelOffFor` 的 90s 渠道暂停（对七牛这种正常供应商是纯噪声），以及将来 `ValidatePolicies` 若接线会直接 Fatal（渠道只服务单跳 + 配了冷却类字段）。既然收益为零，最小安全值就是「不写这一项」。 |
| **QW** | **建议不配** | QW 只出现在 `DeepSeek-4.1-Flash` 的链尾且是 `messages` 协议跳（alias map 里该 hop `protocol=messages`）。两个结论：① `racePlanFor` 要求每跳 chat（`race.go:344-348`），这条链永远走串行，给 QW 配对冲/首块窗口一个字都读不到；② 它是链尾，冷却它只会在「前三跳全挂」时省一次往返，换来的却是激活 90s 渠道级暂停。同理，`ValidatePolicies` 接线后 QW 会因「无单跳、无多跳链首」的边角判据被 Fatal。 |

### 6.3 若要真的启用对冲，先把这三件事定清楚

1. **计费翻倍已不是理论**：`maxParallel` 兜底 2（`race.go:376-378`），`raceChain` 会真的并发两路（`race.go:552-566`、`607`/`633`），且「另一路立刻取消」只在拿到首块之后（`race.go:58-80` 的 `claim`），失败窗口内是双份上游消耗。
2. **只对这些模型生效**：全 chat 且 ≥2 跳 → `GLM-5.3-Flash`、`MiniMax-M3.1-Flash`、`MiMo-2.6-Pro`、`HY3`、`Iceman`、`MiMo-2.6-Flash`。`DeepSeek-4.1-Flash`（QW 是 messages）与 `Qwen-3.8-Flash`（OC 两跳是 messages）**永远不会**进对冲分支。
3. **观测口径**：`/health` 已暴露 `firstBlockMs`/`verdict`（`router.go:254-262`、`:319`），`rankedChain` 用这些观测调整发车顺序（`race.go:450-484`）。建议先只开 `firstBlockMs`（看门狗，不发第二路），看几天 `/health` 的 `firstBlockMs` 分布，再决定 `hedgeAfterMs` 定 18s 还是 20s。

### 6.4 落地顺序（若要动手，最小风险路径）

1. 先只加 **OC** 一项（唯一无单跳、冷却最安全的渠道），跑 24h 看 `/health` 与 `zgate.log` 里 `冷却中，跳过` 的频次是否异常上升；
2. 再加 **QD**（`softCooldownSeconds` 保持 0）；
3. **WB** 只加 `hedgeAfterMs`，且必须同时确认 alias map 里没有任何「WB 单跳 + 流式」的组合被误开（当前 4 个单跳都是 `len(chain)==1`，`race.go:337` 已挡掉）；
4. `QN`/`QW` 不配；
5. 改完 `zgate.json` 只需要 `POST /admin/reload`（`router.go:1585-…` 的 `reload`，policy 从 `cfg` 现读，无需换版）。

### 6.5 风险清单

| 风险 | 触发条件 | 后果 | 规避 |
|---|---|---|---|
| 单跳模型被 5xx 冷却锁死 | 带单跳模型的渠道配了 `softCooldownSeconds>0` | 该模型整段冷却期回 502（`router.go:1435-1437`） | WB/QD 的 `softCooldownSeconds` 保持 0 |
| 渠道级 90s 暂停 | 渠道进 map 且上游回「没有可用的 api key」 | 整渠道暂停 90s，所有模型受影响 | QN/QW 不配；其余渠道注意 401/403 body 文案 |
| 小时级整渠道禁用 | `authFailCooldownHours>0` + 认证类错误 | 渠道被摁住到「额度续上或重启进程」 | 一律 0 |
| 请求无上界挂住 | `headerTimeoutSec:-1` 且链预算未接线 | 客户端转圈直到自己超时，上游被白算一遍 | 本地子进程（WB/QD）不写 -1 |
| 对冲双计费 | `hedgeAfterMs>0` 且链全 chat ≥2 跳 | 首块失败窗口内双份上游消耗 | 先开 `firstBlockMs` 观察，再定 `hedgeAfterMs` |
| 守门变哑（脚本侧） | `drifted_efforts` 快照与 `pick_rule_config` 共用内存 | 档位被清空却不报错 | 已按 `model_alias.py:664-673` 的 deepcopy 实现 |
