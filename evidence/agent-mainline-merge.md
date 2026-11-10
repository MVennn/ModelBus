# 路 B｜只读：主力定义与「合并进主力」最小改动集

> **一句话**：本项目「主力」由 `tools/model_alias.py` 的 `MAIN_ORDER` 白名单单源定义，经 `--apply` 投影到 `provider_config.json` / `model-alias-map.json` / DSH `cordis.patch.yml` 三处运行时配置，再由 zgate 按 alias map 的 `chain` 逐跳消费；当前新加的 `ais-gemini-3.8-flash` 是**独立直连 provider**，与 2026-11-10 收敛掉的 `chat:cp:gemini-*` 旧反代不是同一套东西，旧 `cp:` legacy 键**不可复用**。

---

## 0. 分片元信息

| 项 | 值 |
|---|---|
| 路别 | 路 B｜只读审计（不改任何配置 / docs / tests / PROGRESS.md） |
| 工作区 | `F:\Project\ModelBus`（真实项目；`_merged\DeepseekHarness` 为 junction 视图，未在其下新建产物） |
| 分片 | `evidence/agent-mainline-merge.md`（本文件，唯一写入物） |
| 父代理 | `session-067dd58b-1a3d-4c6d-ab09-89d77faba75d` |
| 凭据口径 | 全文只出现环境变量名（`GEMINI_API_KEY` / `ZCODE_GATEWAY_KEY` 等），不出现任何 key/token 真值 |
| 真实 API 探测 | 0 次（全程静态证据 + 已有日志；新 provider 可调用次数很少，按任务书把实际请求留给主代理决定） |
| 网关重启 | 0 次（未重启 zgate / wb2api / mihomo） |
| git 写操作 | 0 次（未 add / commit / push） |

---

## 1. 结论先行

| # | 判定结论 | 可复查证据（文件:行号） |
|---|---|---|
| 1 | **主力是单源白名单**：`MAIN_ORDER` 是组内排序与「谁进主力」的唯一权威来源，`MAIN_IDS` 由它派生；`entry_group` 靠命中该名单判 `("main","manual")` | `tools/model_alias.py:100-105`、`:106-118`、`:119`、`:1477-1479` |
| 2 | 当前主力**只有 DeepSeek 三条**（`chat:cn:` / `chat:` / `messages:` 的 `deepseek-v4.1-flash`），2026-11-10 口径明确「主力组只放 DeepSeek，原反代通道已整体移除」 | `tools/model_alias.py:107-110`、`:112-117`；`CHANGELOG.md:23` |
| 3 | 竞技榜补候选受 `MAIN_UPSTREAM_HINTS = ("deepseek",)` 过滤，否则 MiMo-2.6-Flash / Space-Bunny 会被重新拉进主力 | `tools/model_alias.py:121-124`、`:1480-1484` |
| 4 | **WB 永远第一消费**：链内跳排序第一维 `CHANNEL_RANK["WB"]=0` 固定链首，不看价格、不受降级开关；限流交给 zgate 逐跳回落，不改链序 | `tools/model_alias.py:176-181`、`:183-193`、`:1206-1219`；`CHANGELOG.md:23` |
| 5 | **逐跳回落落点不在 zgate.json**，在 alias map 的 `chain` 数组；zgate 每请求热重读 alias map 并按 `index+1` 回落，429/502/503/504/regionBlocked 判不可接受 | `tools/model_alias.py:2036`、`:2079-2089`；`gateways/zgate/internal/router/router.go:284-296`、`:497-516`、`:735-746`、`:749-804`、`:992-1006` |
| 6 | **关键发现**：当前 DSH 里新加的 gemini 是 `cordis.patch.yml:253-260` 的独立 provider `gemini:`（直连 `https://catiecli.sukaka.top/v1`、读 `GEMINI_API_KEY`、单一 model `ais-gemini-3.8-flash`），**不在** `zcode-main:` 组内、也不在 quickProviders | `~/.dsh/profiles/desktop/cordis.patch.yml:42-72`、`:253-260`、`:348-350` |
| 7 | 它与 `CHANGELOG.md:23` 收敛掉的 **4 条 `chat:cp:gemini-*` 旧 CLIProxyAPI 反代（8317）完全不同**（id / 渠道 / baseURL 全异），旧 `cp:` legacy 键复用会把新 provider 错指回已下线反代 | `CHANGELOG.md:22-24`；`evidence/agent-cliproxyapi.md:63`、`:102`；旧键样本 `~/.zcode/v2/model-alias-map.json.bak-20261110-gemini-removal:908-915` |
| 8 | **DSH 投影会覆盖手工改动**：`dsh_sync.py` 每次按 `provider_config.json` 重写 `zcode-main` 段（保留非 `zcode-` provider），只改 patch 不落 `MAIN_ORDER` 会被下一次同步冲掉 | `tools/dsh_sync.py:126-158`、`:143`、`:264-296`、`:299-341`、`:344-362`；`sync-models.ps1:340-347` |
| 9 | **语义分叉**：只挂进 DSH 选择器（直连、不经 zgate）不受 WB 第一 / 逐跳回落约束也不享受冷却回落；要经 zgate 统一消费必须扩一整套 channel（撞 `check-project.py:65-69` 防回退门禁） | `tools/model_alias.py:1147`、`:1150-1151`、`:1321`；`gateways/zgate/internal/keys/keys.go:157-171`；`tools/check-project.py:65-69` |
| 10 | **排序陷阱**：`VENDOR_PREFIXES` 当前无 `("Gemini","GEM")`，`vendor_of` 会把 Gemini 判成 `OTHER`，而 `OTHER` 在 `ANONYMOUS_VENDORS` 里 → 新增条目会**沉到主力组最下面**（违反「有品牌按 id 排前面」偏好） | `tools/model_alias.py:818-823`、`:826-830`、`:369-372`、`:833-840`、`:1851-1853`；收敛删除证据 `CHANGELOG.md:23`（`MODEL_META` 清空含 ABBR/VENDOR_PREFIXES 同批） |
| 11 | 基线测试已 **2 处 FAIL，均为收敛前旧断言**，非新增 gemini 引起：`chat:qoder:Qwen3.8-Max` 不在 3 条 `MAIN_ORDER`、`entry_group` 对 `oc:qwen3.8-max` 返回 `('drop','')` 而非 `('main','manual')` | `tests/test_model_alias_naming.py:67-70`；`tests/test_model_alias_price.py:112-129`；实测 `python -m unittest discover -s tests -v` → `Ran 56 tests` / `FAILED (failures=2)` |
| 12 | 改配置前硬约定：`sync-models.ps1` 默认不 push、`--check` 必须与 `--apply` 同参；`model_alias.py --apply` 会自动备份两份配置，夹具必须用 `--config` +`--no-dsh` 避免覆写本机 profile | `AGENTS.md:45`；`sync-models.ps1:18-29`、`:309-314`；`tools/model_alias.py:2072-2089`、`:2093-2096` |

---

## 2. 「主力」由哪几处共同定义（逐层 + 精确行号）

### 2.1 源码层：`tools/model_alias.py`（唯一权威）

| 常量 / 规则 | 当前值 | 行号 |
|---|---|---|
| `MAIN_ORDER` | `["chat:cn:deepseek-v4.1-flash", "chat:deepseek-v4.1-flash", "messages:deepseek-v4.1-flash"]`（3 条） | `:106-118` |
| `MAIN_IDS` | `set(MAIN_ORDER)` | `:119` |
| `MAIN_UPSTREAM_HINTS` | `("deepseek",)` | `:121-124` |
| `LOW_ORDER` / `LOW_PICKS` | 12 条 / `set(LOW_ORDER)` | `:136-154` |
| `VENDOR_QUOTA` | `2` | `:159` |
| `MERGE_FREE_GB` / `MERGE_ACROSS_PROTOCOL` | `{"deepseek-v4.1-flash", "qwen3.8-flash"}` | `:172` / `:174` |
| `WB_FIRST_CHANNELS` | `{"WB"}` | `:176-181` |
| `CHANNEL_RANK` | `{"WB":0,"OC":1,"QD":1,"QW":2,"QN":3}` | `:183-192` |
| `CHANNEL_RANK_DEFAULT` | `4` | `:193` |
| `CHANNEL_BASE` | `{"WB":WB_BASE,"QD":QD_BASE,"OC":OC_BASE,"QW":QW_BASE,"QN":QN_BASE}`（**无 CP / 无 GEM**） | `:1147` |
| `base_of` | `CHANNEL_BASE.get(channel, OC_BASE)` — 未知 channel **静默落 OC_BASE** | `:1150-1151` |
| `CHANNEL_PREFIX` | `{"CN":"cn:","GB":"global:","QD":"qoder:","OC":"oc:","QW":"qwen:","QN":"qn:"}`（任务书写作 `CHANNEL_PREF`，源码真名 `CHANNEL_PREFIX`） | `:1321` |
| `MODEL_META` | `{}`（收敛后清空，原放 CP Gemini 元数据） | `:295-299` |
| `ABBR` / `VENDOR_PREFIXES` | 含 DeepSeek 系列 / 16 个厂商前缀，**均无 Gemini** | `:301-367` / `:818-823` |
| `ANONYMOUS_VENDORS` | `("BEAM","SPB","CONATUS","OTHER")` | `:369-372` |
| `PROVIDER_MAIN/FREE/LOW` | `opencode-go-chat` / `-free` / `-fast`；`GROUPS=("main","free","low")` | `:75-84` |
| `ROUTER_BASE` | `http://127.0.0.1:7871/v1`（三组 provider 统一指向 zgate） | `:85-89` |

**主力筛选条件**（`entry_group`，`:1468-1503`）：

1. `:1475-1476` 集合体 pool 只按价格归 free/drop（防 91 跳快速池误吸进主力）；
2. `:1477-1479` `for hop in entry["chain"]: if _picked(entry, hop, MAIN_IDS): return "main","manual"` —— **命中白名单即主力，不看价格**；
3. `:1480-1484` arena 候选且 upstream 命中 `MAIN_UPSTREAM_HINTS` → `("main","arena")`；
4. `:1485-1503` 其余按 price / `LOW_PICKS` / auto 分 free / low / drop。

**别名生成规则**：

- `:1039-1072` `inventory()` 只从 `provider_rules(cfg)` 的 `config.personalModelIds` 收条目 → `:1056` `classify()` 定 channel → `:1060` `expand_hops()` 展开；
- `:871-1007` `classify()` 前缀映射：`cn:/global:`→WB、`oc:`→OC、`qoder:`→QD、`qwen:`→QW(messages)、`qn:`→QN(messages)、裸名→OC；**无 `cp:` / `gemini:` 分支**；
- `:750-794` `price_of()` 只算 QW/QN/WB/QD/OC，缺价 `return None` 被 `family_entries` 跳过（`:1171-1174`）—— 新 provider 若无价格源必须补 `price_of` 分支或 `OC_PRICES`；
- `:1010-1036` `whitelist_items()` 补白名单点名但配置里没有的型号，`explicit_channel` 仅认 `qoder: qwen: cn: global: wb: oc: qd:`（`:1032-1034`）；
- `:1154-1253` `family_entries()` 按 `(abbr, protocol)` 归并、`with_airport_fallback()` 补机场孪生跳、每跳写 `base_of(channel)`（`:1231`）、累积 `legacy_ids`（`:1243-1247`）；
- `:1324-1347` `hop_specs()` 生成 `<protocol>:<value>` / `<protocol>:<prefix><value>`，`_picked()` 用它对名单。

**组内排序**（模型选择器顺序，`:1830-1861`）：`main` 组 `rows.sort(key=lambda r: (anonymous_rank(r["abbr"]), _pick_rank(r, MAIN_ORDER), r["new_id"]))`（`:1851-1853`）；注释 `:1844-1849` 明确「匿名/无公司代号沉到每组最下面，优先于人工名单；DSH GUI 不做二次排序，这里排成什么顺序界面就是什么顺序」。

### 2.2 写回层：三份运行时配置（由 `--apply` 生成）

| 产物 | 写入点 | 当前内容（脱敏后键名/行数） |
|---|---|---|
| `~/.zcode/v2/provider_config.json` | `model_alias.py:2063-2077`（`providerConfigRules`/`providerOrder`/`providerModelRules`/`manualProviderModelRules` 全量重写 + 自动备份 `.bak-alias-<stamp>`） | 413 行；`:4` `providerOrder`、`:12` `opencode-go-chat`、`:24-25` `personalModelIds` 仅 `DeepSeek-4.1-Flash`、`:27-28` `modelOrder` 同、`:109` 首条 `providerModelRules` |
| `~/.zcode/v2/model-alias-map.json` | `model_alias.py:2079-2089`（`version/generated_at/slot/models/legacy` 原子替换） | 801 行；`:5` `models`（18 条）、`:6` `DeepSeek-4.1-Flash` 含 `:21` `chain`、`:713` `legacy`（86 条），`cp:` legacy 键 0 条 |
| `~/.dsh/profiles/desktop/cordis.patch.yml` | `model_alias.py:2093-2096` → `sync_deepseek_harness()`（`:1632-1668`）→ `tools/dsh_sync.py --apply`；`sync-models.ps1:340-347` 另有独立 `--check/--apply` | 532 行；`:42` `zcode-main:`、`:57-58` baseURL/apiKeyEnv、`:60` 唯一 model `DeepSeek-4.1-Flash`、`:66-72` reasoningEfforts/compat；`:253-260` 独立 `gemini:`；`:348-350` quickProviders |

三份配置的路径优先级：`model_alias.py:375-399`（显式参数 → 环境变量 `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` / `UNIFIED_MODEL_MAP` / `ARENA_MAIN_FILE` → 默认 `~/.zcode/v2/...`）。

### 2.3 网关层：`gateways/zgate/zgate.json`

| 段 | 当前值 | 行号 |
|---|---|---|
| `listen` | `127.0.0.1:7871` | `:2` |
| `aliasMap` | `~/.zcode/v2/model-alias-map.json` | `:3` |
| `providerConfig` | `~/.zcode/v2/provider_config.json` | `:4` |
| `wbGatewayConfig/qoderEnvFile/qwenEnvFile/qiniuEnvFile` | 四个凭据引用路径 | `:5-8` |
| `reasoningGuard` | `enabled:true`, models `["Iceman","iceman-contributor-free"]`, `maxRetries:3`, `maxProbeBytes:32768` | `:10-15` |
| `upstreams` | 恰 **5 个**：OC / WB(+child workbuddy) / QD(+child qoder) / QW(`QWEN_API_KEY`) / QN(`QINIU_API_KEY`)；**无 CP** | `:17-23` |
| `children` | 恰 **2 个** `policy:ondemand` / `idleSeconds:300`：workbuddy(:7863, 4 档 windows, health `/panel/`, startTimeout 30)、qoder(:8790, 3 档 windows, health `/ping`, startTimeout 40) | `:24-47` |

**实际消费顺序与限流回落落点**：

- `zgate.json` **本身不含链序**；链序由 alias map 每个 model 的 `chain` 数组承载（`model_alias.py:2036`、`:2079-2089`）。
- 每请求 `s.aliases.Reload()` + `Resolve(model)`，`len(t.Chain)>0` 走 `routeChain`（`router.go:284-296`、`:735-746`）。
- `attemptChain()` 逐跳：`hop := t.Chain[index]`（`:754`）、`key := s.keyset().For(hop.Channel)`（`:763`），**缺 key 直接跳过该跳**（`:764-768`）、子进程未就绪跳过（`:769-773`）、按 `hop.Protocol` 派发（`:774-804`）；`index>=len` → 502 `all upstreams failed`（`:750-752`）。
- 回落判据 `chainAccept()`：429/502/503/504 与 regionBlocked/403/400-`model_unavailable` 返回 false（`router.go:992-1006`）；`forwardChain()` retry 走 `index+1`（`:497-516`）；`doForwardWith()` 429 就地退避一次（`:518-529`）。
- `keys.Set.For` 只 switch `OC/WB/QD/QW/QN`，default `return ""`（`gateways/zgate/internal/keys/keys.go:157-171`；`Load` 五参 `:113`、结构体 `:22`）——**新增 channel 不改这里必被跳空**。
- `forwardHeaders()` switch 也只列 `WB/QD/QW/QN` 与 `OC`（`router.go:461-490`）；`routeFallback()` 单 Target 回落仅按裸 id 前缀认这五个（`:354-445`）。

### 2.4 DSH 选择器层：`tools/dsh_sync.py`

`KNOWN_PROVIDER_IDS = {"opencode-go-chat":"zcode-main", ...}`（`:73`）→ `_zcode_providers()` 从 `providerOrder` + `modelOrder/personalModelIds` 取顺序（`:126-158`、`:143`）→ `_build_route()` 按 `modelIds` 顺序 append、**无二次排序**（`:264-296`）→ `_PatchDoc.replace()` 用 `yaml.safe_dump(sort_keys=False)` 重写整个 `llm-pi-ai` 段（`:299-341`）→ `_merge_patch()` 保留非 `zcode-` 前缀 provider（`:344-362`）。

> 因此：当前 `gemini:` 独立 provider 每次同步**会被保留**，但 `zcode-main` 的 models 会被 `provider_config.json` 投影**覆盖**。只手工改 patch 不持久。

---

## 3. 同步脚本：产出、调用链、备份/校验约定

### 3.1 param 块与主流程

| 脚本 | 关键点 | 行号 |
|---|---|---|
| `sync-models.ps1` | `#Requires -Version 5.1`；`param([switch]$Push)`，默认不 push，计划任务不带此开关、每天 12:00 只写报告 | `:1`、`:18-29` |
| | `$ROOT = "F:\Project\ModelBus"`，报告落 `docs\reports`，日志/摘要落 `%LOCALAPPDATA%\ModelBus`（避免 sync_report 的 git add 把本机绝对路径带进提交触发 CI check-secrets） | `:34`、`:36`、`:38-46` |
| | 五段流水线：`go_model_sync.py --apply`(`:212`) → workbuddy 采集/定价(`:216-228`) → qoder 按需启动+`qoder_zcode_sync.py --apply`(`:235-253`) → `arena_leaderboard.py`/`model_score.py`(`:263-274`) → **`model_alias.py --slot auto --apply --arena`**(`:275-277`) | `:212-277` |
| | `model_probe.py --timeout 45 --sleep 0.5 -Soft`(`:285`)；过半可信才加 `--probe-file`(`:301-306`)；**`--check` 必须与 `--apply` 同参**(`:309-314`)；漂移则二轮写入+复查(`:317-329`) | `:285-329` |
| | 解析 `## 主力 (N)`(`:333-338`) → `tools\dsh_sync.py --check`，不一致再 `--apply`(`:340-347`) → `model_stream_check.py --changed --soft`(`:352`) → `sync_report.py --write`（仅 `-Push` 才 `--push`，`:356-360`）→ `current-models.ps1` 只读刷新真值视图(`:363-366`) | `:333-366` |
| `sync-models.vbs` | 计划任务用 `wscript.exe`、`WScript.Shell.Run` 第二参数 0=隐藏窗口；`ps1 = "F:\Project\ModelBus\sync-models.ps1"`；`cmd = powershell.exe ... -File <ps1>`（**不带 -Push**）；`shell.Run cmd, 0, False` | `:3-5`、`:13-14`、`:17` |

**谁调用谁**：`计划任务 → sync-models.vbs → sync-models.ps1 → [Go/WB/Qoder 采集] → tools/model_alias.py --apply → sync_deepseek_harness() → tools/dsh_sync.py --apply → cordis.patch.yml`；外加 `sync-models.ps1:340-347` 的第二次 `dsh_sync --check/--apply` 兜底。

### 3.2 备份 / 校验硬约定

| 约定 | 证据 |
|---|---|
| 改 `sync-models.ps1` / `.vbs` 先**在副本或夹具跑通、比对产物 diff**，再动真实配置；参数不确定先读脚本头部 param 块，不猜 | `AGENTS.md:45` |
| `model_alias.py --apply` 自动 `shutil.copy2` 备份 `provider_config.json` 为 `.bak-alias-<stamp>`（`:2072-2077`），alias map 用 `.tmp` + `os.replace` 原子替换（`:2079-2089`） | `tools/model_alias.py:2072-2089` |
| 夹具/沙箱必须 `--config <fixture>`，`--no-dsh` 或 `--config` 非 None 时**不覆写本机 DSH profile**（注释：`fixture/sandbox must not overwrite local DSH profile`） | `tools/model_alias.py:2093-2096` |
| `dsh_sync.py --apply` 先 `_backup()` → `.bak-dshsync-<stamp>`，再 `os.replace`；`--check` 漂移 exit 1 | `tools/dsh_sync.py:383-390`、`:431`、`:26-27`、`:501-505` |
| 部署三步：备份 → md5 校验 → 受控重启；长驻网关禁止会话自动重启 | `~/.dsh/AGENTS.md:55-56` |
| 改 `gateways/zgate/` 下 Go 代码后走 `tools/zgate-lifecycle/restart-zgate.cmd` 换版；`POST /admin/reload` 只热加载策略/上游 base/凭据，**新增子进程 / alias map 路径仍需换版重启** | `AGENTS.md:105-106`；`CHANGELOG.md:45` |

**本次路 B 只读，未改脚本/配置；以上清单供主代理实际执行时逐条对照。**

---

## 4. 把新 gemini 合并进主力：两条语义 + 最小改动清单

> 主代理必须先定语义再动手。两条路线互斥，改动量差一个数量级。

### 4.0 前置事实（决定不能照抄旧 diff）

- 新 provider：`cordis.patch.yml:253-260`，`gemini:` / `displayName: Gemini` / `apiKeyEnv: GEMINI_API_KEY` / `api: openai-completions` / `baseURL: https://catiecli.sukaka.top/v1` / model `ais-gemini-3.8-flash`。
- 旧收敛对象：`CHANGELOG.md:23` 的 4 条 `chat:cp:gemini-*`，指向 `http://127.0.0.1:8317/v1` 的 CLIProxyAPI 反代（`:22` 已下线、移入 `.work/cliproxyapi-removed-20261110/`）。
- 当前 `provider_config.json` 与 `model-alias-map.json` 里 gemini/cp refs = 0；`main-group = ['DeepSeek-4.1-Flash']`（`~/.zcode/v2/model-alias-map.json:5-21`、`:713`）。

### 4.1 路线 A：DSH 选择器层合并（改动最小，保持直连、不经 zgate）

**语义**：把 `ais-gemini-3.8-flash` 作为一条主力显示项挂进 `zcode-main` 的 models/`modelOrder`，保留 `gemini:` 独立直连。因为它不经 `127.0.0.1:7871`，**不受 WB 第一消费 / zgate 逐跳回落约束，也不享受冷却/回落**；次数少当独立兜底条目、不抢 WB 首跳，正合「可调用次数很少」。

按顺序最小改动：

| 序 | 文件:行号 | 改动 | 语义 / 风险 |
|---|---|---|---|
| A1 | `tools/model_alias.py:106-118` | `MAIN_ORDER` 追加 1 条`"chat:ais-gemini-3.8-flash"`（或实际协议前缀，主代理复核） | 使 `entry_group:1477-1479` 判主力 + `_pick_rank:1834-1842` 定顺序；不落这里，`:2063-2070` 每次 --apply 都会把它从 provider_config 冲掉 |
| A2 | `tools/model_alias.py:301-367` / `:818-823` | 补 `ABBR["ais-gemini-3.8-flash"] = "Gemini-3.8-Flash"`（或合适显示名）+ `VENDOR_PREFIXES` 补 `("Gemini","GEM")` | **否则 `vendor_of:826-830` → `OTHER` → `anonymous_rank:833-840`=1 → `:1851-1853` 沉到主力组最下面**，违反「有品牌按 id 排前面」偏好 |
| A3 | `tools/model_alias.py:295-299` | `MODEL_META` 补 `ais-gemini-3.8-flash` 的 `properties/optionSpecs`（contextWindow / maxTokens / supportsImage / `reasoningLevel`） | `:2008-2014` 合入 `providerModelRules`；不补则 DSH 只吃 `dsh_sync.py:206-240` 兜底值 1000000/128000 |
| A4 | `tools/model_alias.py:750-794` | 补新渠道价格分支（或 `OC_PRICES` 条目） | 缺价 `return None` 会被 `family_entries:1171-1174` 跳过，白名单点名也生成不出来 |
| A5 | `tools/model_alias.py:121-124` | 视是否允许竞技榜把 gemini 拉进主力，决定 `MAIN_UPSTREAM_HINTS` 是否加 `"gemini"` | 不加=只有 A1 手动点名生效；加=榜单候选 `:1480-1484` 也能进主力，需评估次数少是否要放开 |
| A6 | 夹具验证：`python tools/model_alias.py --config <fixture> --alias-map <fixture> --slot auto --arena --no-dsh` → diff 产物 → 再 `--apply` 到真实配置（自动备份 `:2072-2089`）→ `--check` 同参(`sync-models.ps1:309-314`) | 遵守 `AGENTS.md:45` 先夹具后真实、比对产物 diff |
| A7 | `tools/dsh_sync.py --check` 再 `--apply`（`sync-models.ps1:340-347`） | 把投影写进 `cordis.patch.yml` 的 `zcode-main:`(`:42-72`)；`_merge_patch:344-362` 会保留 `gemini:` 独立 provider |
| A8 | 复核 `~/.dsh/profiles/desktop/cordis.patch.yml:348-350` quickProviders | 若希望新条目在选择器快捷组可见，需把对应 provider 列入；当前只有 `zcode-main`/`zcode-free` |

> **A 路结论**：`zgate.json` / Go `keys.For` / `check-project.py` 门禁**都不用动**；但「合并进主力」只是显示层同组，流量仍直连第三方，不进 `chain`。若用户要的是「走主力链路消费」，必须走 B 路。

### 4.2 路线 B：经 zgate 7871 统一消费（改动大，撞防回退门禁）

**语义**：新 provider 作为一个**新 channel**（例如 `GEM`）接进 alias map 的 `chain`，享受 WB 第一 + 逐跳回落。因 `MAIN_ORDER` 里 WB=0 固定链首（`:192`），次数少的 GEM 应排在 `CHANNEL_RANK` 高值（链尾兜底），避免抢首跳。

按顺序最小改动（比 A 多出的部分）：

| 序 | 文件:行号 | 改动 | 语义 / 风险 |
|---|---|---|---|
| B0 | 同 A1–A5 | 先完成主力白名单、品牌、元数据、价格 | 同上 |
| B1 | `tools/model_alias.py:183-193` | `CHANNEL_RANK` 加 `"GEM": <链尾值>`（建议 ≥3，别用 0） | 决定链内位置；用 0 会与 WB 并列抢首跳，违背「WB 永远第一消费」(`:176-181`) |
| B2 | `tools/model_alias.py:1147` | `CHANNEL_BASE["GEM"] = <新 baseURL>` | 不补则 `base_of:1150-1151` 静默落 `OC_BASE`，hop.base 指错上游 |
| B3 | `tools/model_alias.py:1321` | `CHANNEL_PREFIX` 补 `"GEM": "gemini:"` | `hop_specs:1324-1341` 才能生成 `chat:gemini:...` 供 `_picked` 命中 |
| B4 | `tools/model_alias.py:871-1007` | `classify()` 补 `gemini:` 前缀 → channel `GEM`；`whitelist_items:1032-1034` 的 `explicit_channel` 也要认 | 否则裸名默认 OC(`:997-1007`)、`cp:/gemini:` 不算显式渠道 |
| B5 | `gateways/zgate/zgate.json:17-23` | 加 1 个 upstream（base + `keyEnv`，值走环境变量） | 现役 5 upstream；`CHANGELOG.md:22` 刚收敛成 5 |
| B6 | `gateways/zgate/internal/keys/keys.go:22`、`:113`、`:157-171` | `Set` 结构体 / `Load` 参数 / `For` switch 扩 `GEM` | **不改 `For` 则 `router.go:764-768` 因空 key 直接跳过该跳** |
| B7 | `gateways/zgate/internal/router/router.go:461-490`、`:354-445` | `forwardHeaders` switch 与 `routeFallback` 裸 id 前缀补 `GEM` | 否则 header 注入/单 Target 回落口径不全 |
| B8 | `gateways/zgate/main.go:135/193/271`、`internal/config/config.go` | 五通道数组/默认 upstream/路径解析扩第六通道 | `CHANGELOG.md:25` 去 CP 时同步改过五件 Go 文件 |
| B9 | `tools/check-project.py:65-69`、`:100-122`、`:139-146` | 防回退 STALE 正则（`6 个 upstreams` / `3 个 children` / `8317` / `CLIPROXY_API_KEY`）与 `/health` 五段断言需同步决策 | 直接把旧 CP 口径写回会撞门禁；新 channel 是否算「第 6 个 upstream」要主代理显式定口径 |
| B10 | 换版：Go 代码改完走 `tools/zgate-lifecycle/restart-zgate.cmd`；**本会话禁重启长驻网关**，由主代理按 `AGENTS.md:105-106` / `~/.dsh/AGENTS.md:55-56` 决定时机 | 新增子进程 / alias map 路径需换版重启；`POST /admin/reload` 不够 |

### 4.3 两条路线对三个硬口径的影响（对照表）

| 口径 | 路线 A（DSH 选择器直连） | 路线 B（经 zgate chain） |
|---|---|---|
| WB 第一消费 | **不受影响**：新条目不经 7871，不进 `chain`，`CHANNEL_RANK:192` 原样 | **必须保**：新 channel rank 排链尾，WB=0 不动（`model_alias.py:176-181`、`:192`）；否则把次数少的源顶到首跳 |
| zgate 逐跳回落 | **不享受**：直连第三方，429/冷却/regionBlocked 回落全无（`router.go:749-804` 不经过） | **享受**：`chain` + `attemptChain` `index+1`（`router.go:497-516`、`:992-1006`）；缺 `keys.For` 会被 `:764-768` 跳空 |
| 模型选择器排序 | 进 `zcode-main` 组，顺序由 `MAIN_ORDER` + `anonymous_rank` 决定（`model_alias.py:1851-1853`）；**必须补 `VENDOR_PREFIXES` 的 Gemini 前缀**否则沉底 | 同左；另 `dsh_sync.py:264-296` 按 `modelIds` 顺序 append、无二次排序 |

---

## 5. tests：新增 gemini 主力条目会受影响的用例与期望值

| 用例 | 当前断言 / 期望 | 行号 | 新增主力条目后 |
|---|---|---|---|
| `test_model_alias_naming.py::test_main_order_names_the_oc_hop_explicitly` | `assertIn("chat:qoder:Qwen3.8-Max", ma.MAIN_ORDER)` + `assertIn("chat:oc:qwen3.8-max", ma.MAIN_ORDER)` | `:67-70` | **当前已 FAIL**（收敛前旧断言）；改 `MAIN_ORDER` 后仍 FAIL，需同步更新为新的 3+1 条白名单。本分片禁改 tests/ |
| `test_model_alias_price.py::test_group_rules` | `entry_group(entry_for("oc:qwen3.8-max", 0.43)) == ("main","manual")`（主力看名单豁免价格） | `:112-129` | **当前已 FAIL** 返回 `('drop','')`；若新 gemini 进 `MAIN_IDS`，应补一条 `entry_for(...gemini...)` 断言 `("main","manual")` |
| `test_model_alias_hop_order.py` | 5 条 WB 链首守卫：`chain[0]["channel"]=="WB"`、同价/更贵均 WB 打头、QW 尾跳+机场孪生跳倒数第二、`assertFalse(hasattr(ma,"DEMOTE_HOPS"))` + `assertEqual(ma.WB_FIRST_CHANNELS,{"WB"})`、磁盘 alias map 每条含 WB 的链 WB 必须 index 0 | `:62-103` | 走 B 路加新 channel 后仍须全绿；A 路不进 chain 不受影响。这是「WB 第一」的可执行验收 |
| `test_model_alias_qd_free.py` | `explicit_channel` 标记（qoder:/cn:/裸名）、Qwen-3.8-Flash 链首 QD 且有 OC 兜底、无 `-Msg/-Resp` 分身 | `:38-57`、`:69-92`、`:94-100` | 若 `classify` 新增 `gemini:` 前缀，需补对应 `explicit_channel` 断言 |
| `test_dsh_sync_retry_policy.py` | 固定夹具 `PROVIDER_IDS`/`DSH_IDS`/MODELS，`test_models_are_complete` 断言 modelOrder 顺序 == MODELS、`reasoningLevel.map=="{}"` 时不生成 `reasoningEfforts` | `:38-45`、`:216-228` | 新主力条目会改 `provider_config` 的 `modelOrder`；夹具需补该 id，且思考适配若写 `reasoningLevel.map` 非空，`reasoningEfforts` 断言要跟着变 |
| `test_go_sync_list_only.py` | `gemini-4-argon 只提供 generate-content，本客户端用不了`、`assertNotIn("gemini-4-argon", protos)` | `:85-90` | Go 清单用例，与主力/DSH 无关，不受影响 |

**基线实测**（只读，未改测试）：`cd "F:/Project/ModelBus" && python -m unittest discover -s tests -v` → `Ran 56 tests in 0.015s` / `FAILED (failures=2)`，两处原文：

- `AssertionError: 'chat:qoder:Qwen3.8-Max' not found in ['chat:cn:deepseek-v4.1-flash', 'chat:deepseek-v4.1-flash', 'messages:deepseek-v4.1-flash']`（`tests/test_model_alias_naming.py:69`）
- `AssertionError: Tuples differ: ('drop', '') != ('main', 'manual')`（`tests/test_model_alias_price.py:123`）

> 这两处 FAIL 是 2026-11-10「主力收敛」后遗留的旧断言，**不是新增 gemini 引起**；主代理实际改动后须区分「旧 FAIL」与「新回归」。

---

## 6. 对照 `CHANGELOG.md:20-28`「主力收敛」的反向操作：加回主力精确 diff 清单

> **重要**：下列是「把 2026-11-10 收敛掉的旧 CP 四型号原样加回」的反向模板，**仅作参考**；新 `ais-gemini-3.8-flash` 的 id / channel / baseURL 全异，照抄会把新 provider 接回已下线 8317 反代。收敛前 HEAD 值来自 `git diff`（只读，最新 `tools/model_alias.py` 提交 `2341d3f`）。

### 6.1 `tools/model_alias.py` 反向项（HEAD 旧值 → 当前值）

| 位置（HEAD 行号） | 收敛前值 | 当前对应行 | 反向操作 |
|---|---|---|---|
| `HEAD:110-113` | 4 条 `"chat:cp:gemini-3.6-flash"` / `"chat:cp:gemini-3-flash-preview"` / `"chat:cp:gemini-3.5-flash-lite"` / `"chat:cp:gemini-3.1-flash-lite"` | `tools/model_alias.py:106-118` | 追加到 `MAIN_ORDER`（顺序按原 4 条）；新 provider 则**只加 1 条新 id** |
| `HEAD:122` | `MAIN_UPSTREAM_HINTS = ("deepseek", "gemini")` | `:124` | 放开竞技榜 gemini 候选；对应 `entry_group:1480-1484` |
| `HEAD:192` | `CHANNEL_RANK = {"WB":0,"CP":0,"OC":1,"QD":1,"QW":2,"QN":3}` | `:192` | **注意 `CP:0` 与 WB 并列首跳**；新 channel 不应复用该值（见 4.3） |
| `HEAD:283` | `"gemini-4-argon": {"flat": 1.76}` | `OC_PRICES:257-283` | 新 provider 需自己的价格项或 `price_of:750-794` 分支 |
| `HEAD:299-315` | `MODEL_META` 含 `gemini-4-argon`：contextWindow 1048576 / supportsToolCall / supportsImage / maxOutputTokens 65536 / reasoningLevel `disabled,low,medium,high` | `:299` (`{}`) | 思考适配落点；按 `:2008-2018` 合入 `providerModelRules` |
| `HEAD:309` 附近 | `ABBR` 四条 CP Gemini + `"gemini-4-argon": "Gemini-4-Argon"` | `:301-367` | 显示名映射 |
| `HEAD:789-794` | `price_of` 的 `if channel == "CP": return 0.0` | `:750-794` | 旧反代零价；新 provider 按真实计费，别照抄 0.0 |
| `HEAD:818-820` | `VENDOR_PREFIXES` 含 `("Gemini", "GEM")` | `:818-823` | **关键**：不恢复这条，新 Gemini 会被判 `OTHER` 沉底（见 4.1-A2） |
| `HEAD:944-958` | `classify()` 的 `if model.startswith("cp:")` 返回 `channel="CP"` | `:871-1007` | 新前缀应另起（`gemini:` / `GEM`），不要复用 `cp:` |
| `HEAD:1144-1145` | `CHANNEL_BASE["CP"] = "http://127.0.0.1:8317/v1"` | `:1147` | 新 baseURL 是 `https://catiecli.sukaka.top/v1`（`cordis.patch.yml:257`），**不可复用 8317** |
| `HEAD:1321` | `CHANNEL_PREFIX["CP"] = "cp:"` | `:1321` | 新前缀另起 |
| `HEAD:1474-1483` | `entry_group` CP 白名单闸：`if all(hop["channel"]=="CP" ...) and not any(_picked(...MAIN_IDS)): return "drop","cp-whitelist"` | `:1468-1503` | 收敛已删；新 provider 若走 A 路不需要这道闸 |

### 6.2 运行时三配置反向项

| 配置 | 收敛删了什么 | 备份证据（精确行号） | 反向操作 |
|---|---|---|---|
| `~/.zcode/v2/provider_config.json` | `opencode-go-chat` 的 4 个 Gemini 型号 + 4 条 `providerModelRules` | `.bak-20261110-gemini-removal:24-36`（`personalModelIds`/`modelOrder` 含 `DeepSeek-4.1-Flash` + 4 条 `Gemini-*`）、`:144/:166/:188/:210` 四条 `modelId: Gemini-*`；当前 `:24-28` 只剩 1 条 | 由 `model_alias.py:1984-1998`/`:2063-2070` 重新生成，**不要手改** |
| `~/.zcode/v2/model-alias-map.json` | 4 个 `Gemini-*` model + 4 个 `cp:gemini-*` legacy + 4 个 `Gemini-*` legacy | `.bak-20261110-gemini-removal:68-172`（4 个 model 块，每块 `original: cp:gemini-*`、`legacy_ids[0]=cp:gemini-*`）、`:908-915`（`cp:gemini-3.1-flash-lite`→`Gemini-3.1-Flash-Lite` 等 4+4 条 legacy）；当前 `:5`/`:713` 已无 | 由 `:1964-1973`/`:2044-2045`/`:2079-2089` 自动生成新 legacy |
| `~/.dsh/profiles/desktop/cordis.patch.yml` | `zcode-main` models 里 4 个 `- id: Gemini-*`（各 contextWindow 262144 / maxTokens 16384 / input text） | `.bak-20261110-gemini-removal:71/:76/:81/:86`（当前 `:60` 只剩 `DeepSeek-4.1-Flash`） | 由 `dsh_sync.py:264-296`/`:299-341` 投影；**当前 `:253-260` 的新 `gemini:` 是收敛之后另加的独立 provider** |

三份 `.bak-20261110-gemini-removal` 实测在位（只列大小，未读真值）：`provider_config.json.bak-20261110-gemini-removal` 13731 B、`model-alias-map.json.bak-20261110-gemini-removal` 27054 B、`cordis.patch.yml.bak-20261110-gemini-removal` 18651 B；当前对应 10610 B / 22683 B / 18790 B。`CHANGELOG.md:28` 回退靠这三份 + `.work/cliproxyapi-removed-20261110/`。

### 6.3 Go / 网关 / 门禁反向项

| 文件 | 收敛改了什么 | 行号 / 证据 |
|---|---|---|
| `gateways/zgate/zgate.json` | 删 `CP` upstream（`http://127.0.0.1:8317/v1` + `child: cliproxyapi` + `keyEnv: CLIPROXY_API_KEY`）与 `children.cliproxyapi`（ondemand / idleSeconds 1800 / windows [] / port 8317 / health `/v1/models`） | 当前 `:17-23` / `:24-47`；`CHANGELOG.md:22` |
| `gateways/zgate/internal/config/config.go` | 去 `CliproxyEnvFile` 字段、applyDefaults 里 CP 默认 upstream、resolvePaths 里 CP 路径解析 | `CHANGELOG.md:25` |
| `gateways/zgate/internal/keys/keys.go` | `Load` 六参→五参、`Set` 去 CP、`case "WB","QD","QW","QN","CP"`→四 channel | 当前 `:22` / `:113` / `:157-171` |
| `gateways/zgate/main.go` | `:135/:193/:271` 六通道数组→五通道 | `CHANGELOG.md:25` |
| `gateways/zgate/internal/router/router.go` / `router_test.go` | 去 `/health` 第六段与测试段名 | `CHANGELOG.md:25` |
| `tools/check-project.py` | 加 5 条防回退 STALE 正则 + `/health` 六段→五段 + README 8317/CLIProxyAPI 反向断言翻成残留检测 | `:65-69`、`:100-122`、`:139-146`；`CHANGELOG.md:26` |
| 11 篇 docs / README / AGENTS | 统一改 5 upstream / 2 child，删 `docs/MODEL-PROVIDERS.md` §4.11、`docs/ARCHITECTURE.md` CP 架构图行 | `CHANGELOG.md:26` |

### 6.4 `cp:` legacy 键是否复用：**不复用**

- 旧键样本 `~/.zcode/v2/model-alias-map.json.bak-20261110-gemini-removal:908-915`：`cp:gemini-3.1-flash-lite` / `cp:gemini-3.5-flash-lite` / `cp:gemini-3.6-flash` / `cp:gemini-3-flash-preview` → 分别指向 4 个旧 `Gemini-*` 显示名，其 model 块 `original` 也是 `cp:gemini-*`（`:75/:102/:129/:156`），chain 的 `base` 是已下线的 8317（`CHANGELOG.md:22`）。
- 新 provider id 是 `ais-gemini-3.8-flash`（`cordis.patch.yml:259`）、baseURL 是 `https://catiecli.sukaka.top/v1`（`:257`）、`apiKeyEnv: GEMINI_API_KEY`（`:255`），与 `cp:` 前缀无映射关系。
- 复用后果：`classify:900-918` legacy 解析会把新 id 错指回旧 chain（`_bare(upstream)` 对不上则置 None，但 `cp:` 键若被误挂会指向 8317）。
- 正确做法：按 `model_alias.py:1964-1973` 让 `--apply` 自动生成 `legacy[<raw>]` / `legacy[<original>]` → 新 `new_id`；如需兼容旧客户端 id，另起**新前缀** legacy（例如 `gemini:ais-gemini-3.8-flash`），不碰 `cp:` 命名空间。

---

## 7. 思考适配的落点（供主代理 / 路 A、C 复核，本路只定位不改）

| 层 | 关键行 | 说明 |
|---|---|---|
| 元数据入口 | `tools/model_alias.py:295-299` `MODEL_META`、`:2008-2014` | 按上游 id 补 `properties/optionSpecs.reasoningLevel`，合入 `providerModelRules` |
| 协议闸 | `tools/model_alias.py:2015-2018` | `if row["protocol"] != "chat": reasoning["map"] = "{}"` —— **非 chat 协议强制空推理映射** |
| DSH 投影 | `tools/dsh_sync.py:243-257` | `map == "{}"` → `return {}`（不写 `reasoningEfforts`）；disabled 档写 `{"off":"disabled"}` + `compat.thinkingFormat=deepseek`（`cordis.patch.yml:66-72` 为 DeepSeek 的实例）；非 disabled 档写 `reasoningEfforts` |
| 档位集合 | `tools/dsh_sync.py:60-76` `DSH_LEVELS = {"off","minimal","low","medium","high","xhigh","max"}` | 新 `reasoningLevel.values` 必须落在此集合 |
| 响应侧 | `evidence/agent-adaptation.md:74`、`:248` | 旧 CP 响应侧已接 `thinking_delta` / reasoning summary；`POST /v1/chat/completions model=Gemini-3.6-Flash -> HTTP 200 ct=application/json bytes=341` |
| 旧例 | `evidence/agent-admission-price.md:11`、`evidence/agent-cliproxyapi.md:63/:102/:104`、`evidence/agent-gateway-lifecycle.md:1807/:2602/:3420/:3743/:4141/:4182` | `map` 最后一条命中规则生效；`map` 表达式作用域只有 `reasoningLevel` 与 `maxOutputTokens` 两个自由变量 |
| 网关侧 guard | `gateways/zgate/zgate.json:10-15` `reasoningGuard` | 当前只对 `Iceman` / `iceman-contributor-free` 生效，新 gemini 是否纳入需主代理定 |

> 本路按「可调用次数很少，最多 1 次 maxTokens 极小请求，没把握只给方案」的约束：**未发任何真实探测**。若主代理要验证思考能力，建议单发 1 次 `maxTokens` 极小、带 `reasoning` 开关的 `chat/completions`，先看响应是否出现 `thinking_delta` / `reasoning_content` / `reasoning`，再决定 `reasoningLevel.map` 表达式；凭据只从 `GEMINI_API_KEY` 环境变量读。

---

## 8. 主代理必须亲自复核的点

| # | 复核项 | 为什么必须本人定 | 证据 |
|---|---|---|---|
| 1 | **语义选 A 还是 B**：「合并到主力内」是只进 DSH 选择器同组（直连、不经 zgate），还是接进 zgate `chain` 统一消费 | 两条改动量差一个数量级；B 要动 Go + 换版 + 撞门禁，且本会话/子代理无权重启长驻网关 | `cordis.patch.yml:42-72` vs `:253-260`；`model_alias.py:1147`；`keys.go:157-171`；`~/.dsh/AGENTS.md:55-56` |
| 2 | 新 provider 的**真实协议 / id 前缀 / 是否支持 `chat/completions`**：`ais-gemini-3.8-flash` 只是 patch 里的 id，`MAIN_ORDER` 该写 `chat:...` 还是 `messages:...` 未定 | 写错 protocol 会触发 `:2015-2018` 强制空推理映射，思考适配直接失效；`classify:920-988` 也会定错 channel | `cordis.patch.yml:256-260`；`model_alias.py:100-102`、`:871-1007` |
| 3 | **恢复 `("Gemini","GEM")` 厂商前缀**（或 `ABBR` 映射），否则新条目被判 `OTHER` 沉到主力组最下面 | 直接违反记忆里的排序偏好「有品牌可识别型号按 id 顺序排前面」 | `model_alias.py:818-823`、`:826-830`、`:369-372`、`:833-840`、`:1851-1853`；收敛删除 `CHANGELOG.md:23` |
| 4 | 新 channel 的 `CHANNEL_RANK` 取值必须**排在链尾**，不能复用旧 `CP:0` | `CP:0` 与 WB 并列首跳，会把「可调用次数很少」的源顶成第一消费，违背 WB 永远第一 | `HEAD tools/model_alias.py:192`；当前 `:176-181`、`:192` |
| 5 | 旧 `cp:` legacy 键**不复用**、旧 8317 反代**不恢复** | 新 baseURL 完全不同；复用会错指回已下线反代，且 `check-project.py:65-69` 有 8317/CLIPROXY_API_KEY 防回退门禁 | `cordis.patch.yml:257`；`.bak...:908-915`；`CHANGELOG.md:22-24` |
| 6 | 若走 B 路，`tools/check-project.py:65-69` / `:100-122` / `:139-146` 的防回退门禁口径**是否调整**、11 篇 docs 是否同步 | `CHANGELOG.md:26` 刚把 6 upstream/3 child 全翻成残留检测，新增第 6 个 upstream 会撞门禁 | `tools/check-project.py:65-69`；`CHANGELOG.md:26` |
| 7 | `tests` 里 **2 处收敛前旧 FAIL** 与「新增 gemini 后的新期望」要分开处理；本分片禁改 tests/ | 不区分会把旧债误判成新回归 | `tests/test_model_alias_naming.py:67-70`；`tests/test_model_alias_price.py:112-129`；基线 `FAILED (failures=2)` |
| 8 | 实际改动前**夹具跑通 + 产物 diff**，再用真实配置 `--apply`；`--check` 与 `--apply` 同参；`dsh_sync --check/--apply` 二次投影 | 直接手改三份运行时配置会被下一次同步覆盖 | `AGENTS.md:45`；`sync-models.ps1:309-314/:340-347`；`model_alias.py:2093-2096` |
| 9 | 思考适配是否发那 **1 次极小探测**、以及 `reasoningLevel.map` 表达式 | 次数少；本路按约束未发，实际请求留主代理 | `tools/dsh_sync.py:243-257`；`evidence/agent-adaptation.md:74/:248`；`evidence/agent-gateway-lifecycle.md:4182` |
| 10 | **换版时机**：B 路改了 Go 代码，需 `tools/zgate-lifecycle/restart-zgate.cmd` 受控换版；本会话禁重启长驻网关 | 部署三步备份→md5→受控重启；`POST /admin/reload` 对新增子进程/alias map 路径无效 | `AGENTS.md:105-106`；`~/.dsh/AGENTS.md:55-56`；`CHANGELOG.md:45` |

---

## 9. 本分片做了什么 / 没做什么

- **做了**：通读 `tools/model_alias.py`（2101 行）、`sync-models.ps1`（395 行）、`sync-models.vbs`（17 行）、`gateways/zgate/zgate.json`（48 行）、`tests/` 全 6 个用例、`CHANGELOG.md:20-28`；只读解析三份运行时配置及其 `.bak-20261110-gemini-removal`（脱敏，不回显凭据）；只读 `git diff` 取收敛前 HEAD 旧值；跑基线 `unittest` 记录 `FAILED (failures=2)`；核对 `dsh_sync.py` / `router.go` / `keys.go` / `alias.go` / `check-project.py` 的逐行机制。
- **没做**：未写任何配置 / docs / tests / PROGRESS.md；未发真实 API 探测；未重启任何网关；未 git add/commit/push；未把 key/token 写进文件或回报。
- **失败与规避**（保留原文供复查）：`python -c "<多行>"` 在 MSYS Bash 把 `\n` 当续行符 → `SyntaxError: unexpected character after line continuation character`，改用 `python -c "import base64;exec(base64.b64decode('<b64>'))"`；`read(limit=3000)` → `ToolCallError: limit must be less than or equal to 2000`，改分段 `limit<=2000`。均无副作用。
