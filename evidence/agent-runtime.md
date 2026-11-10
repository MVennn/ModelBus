# agent-runtime — ModelBus 网关运行态取证

> **一句话**：7871 上的 zgate 在跑，跑的是**今天的代码**（HEAD `bfd6b9e` + 工作区未提交改动，二进制 22:24:36 编译、进程 22:25:37 启动）；`/health` 与 `/v1/models` 能证明 Gemini-AIS 七跳、HJ 渠道、冷却计数、93 条目录都在跑，但**提前交卷 SSE / 思考守卫 / 竞速观测保鲜期**三条在端点上没有任何痕迹，只能靠发一次真请求验；7872 控制台没起。

- 取证时间：2026-11-10 22:36–22:47（+08:00）
- 取证方式：只读（curl / Node fetch / Get-CimInstance / 读日志与配置），未发任何推理请求、未重启任何进程
- 凭据处理：`/health` 只暴露 `key: true|false`，本文不含任何 key 值

---

## 1 端口与进程实况

| 端口 | 归属 | 状态 | PID | 进程启动时间 | 证据 |
|---|---|---|---|---|---|
| 127.0.0.1:7871 | zgate.exe（`F:\Project\ModelBus\gateways\zgate\zgate.exe serve`） | **在跑**，`/health` 200 | 31480 | **2026-11-10 22:25:37.911** | `Get-CimInstance Win32_Process`；netstat 见 3 条 ESTABLISHED↔127.0.0.1:7871 pid=31480 |
| 127.0.0.1:7872 | 只读控制台（docs/CONSOLE.md 设计稿） | **没起** | — | — | `Get-NetTCPConnection -LocalPort 7872` 计数 0；`fetch http://127.0.0.1:7872/` → fetch failed |
| 127.0.0.1:7863 | wb2api.exe（zgate 子进程 workbuddy） | 在跑 | 3128 | 2026-11-10 22:25:39.613 | health `children.workbuddy.pid=3128`；日志 `子进程 workbuddy 就绪 pid=3128` |
| 127.0.0.1:8790 | qoder 代理（zgate 子进程 qoder） | stopped（不在窗口） | — | — | health `children.qoder.state=stopped, idle_s=1047, in_window=false` |

其它相关进程（与本任务无关但占端口）：`node 34568`（billion-context, 127.0.0.1:18787, 22:22:19）、`node 9204`（dsh-ops watchdog, 14:00:47）、`node 30984`（22:41:31，本轮会话的 run_code 宿主）。

> **工具旁证异常**：本机 `netstat -ano` 与 `Get-NetTCPConnection` 都**没有**列出 `127.0.0.1:7871 LISTENING` 这一行，但 7871 上有 3 条 ESTABLISHED 且 `/health` 稳定 200。判定以**应用层响应**为准（7871 确实在服务），不以下面这两条命令的缺行反推「没监听」。

---

## 2 `/health` 全文（1528 字节，HTTP 200）

```json
{"alias":{"models":20,"path":"~\\.zcode\\v2\\model-alias-map.json"},"children":{"qoder":{"idle_s":1047,"in_window":false,"last_error":"","policy":"ondemand","port":8790,"state":"stopped","windows":["08:58-09:15","20:58-21:15","21:58-22:15"]},"workbuddy":{"idle_s":4,"in_window":false,"last_error":"","pid":3128,"policy":"ondemand","port":7863,"state":"running","windows":["08:58-09:15","09:58-10:15","20:58-21:15","21:58-22:15"]}},"cooling":1,"gemini":{"base":"https://catiecli.sukaka.top/v1","child":"","key":true,"last_error":"","state":"up"},"hajimi":{"base":"https://api.gemai.cc/v1","child":"","key":true,"last_error":"","state":"up"},"ok":true,"opencode":{"base":"https://opencode.ai/zen/go/v1","child":"","key":true,"last_error":"","state":"up"},"qiniu":{"base":"https://api.qnaigc.com/v1","child":"","key":true,"last_error":"","state":"up"},"qoder":{"base":"http://127.0.0.1:8790/v1","child":"qoder","key":true,"last_error":"","state":"stopped"},"qwen":{"base":"https://maas.qianwenaiapi.com/apps/anthropic/v1","child":"","key":true,"last_error":"","state":"up"},"race":{"disabled":{},"hops":{"GM|ais-gemini-3.6-flash|":{"firstBlockMs":8528,"verdict":"ok","at":"22:28:24"},"GM|ais-gemini-3.7-flash|":{"firstBlockMs":0,"verdict":"Service Unavailable ","at":"22:28:20"},"GM|ais-gemini-3.8-flash|":{"firstBlockMs":0,"verdict":"Service Unavailable ","at":"22:28:16"}}},"uptime_s":1047,"workbuddy":{"base":"http://127.0.0.1:7863/v1","child":"workbuddy","key":true,"last_error":"","pid":3128,"state":"running"}}
```

字段解读（只列今天相关的）：

| 字段 | 值 | 含义 / 今天的对应改动 |
|---|---|---|
| `ok` | `true` | 网关存活 |
| `uptime_s` | 1047（22:43 采样） | 1047s ≈ 17.4min，与进程启动 22:25:37 吻合，**进程是新的** |
| `alias.models` / `alias.path` | `20` / `~\.zcode\v2\model-alias-map.json` | 别名表 20 条（今天 HJ 3.8 拆条后仍是 20） |
| `children.workbuddy` | `state=running, pid=3128, windows=[08:58-09:15, 09:58-10:15, 20:58-21:15, 21:58-22:15]` | 子进程窗口表 |
| `children.qoder` | `state=stopped, in_window=false` | 按需拉起，当前不在窗口 |
| `cooling` | `1` | 有 **1** 个上游键在软冷却中；与日志 `22:25:48 OC\|beam-free\| 地区受限（HTTP 403），冷却 30m0s` 吻合（30 分钟窗，到 22:55:48 才归零） |
| `gemini` | `state=up, base=https://catiecli.sukaka.top/v1, key=true, child=""` | GM 渠道（七跳链所在） |
| `hajimi` | `state=up, base=https://api.gemai.cc/v1, key=true, child=""` | **HJ 渠道今天新接入**，键就绪 |
| `opencode/qiniu/qwen/qoder/workbuddy` | 各 `state=up`（qoder 为 stopped） | 共 7 个渠道段，数量 = `keys.Channels` |
| `race.hops` | 3 条：`GM\|ais-gemini-3.6-flash\|` ok/8528ms/22:28:24；`3.7` SU/0/22:28:20；`3.8` SU/0/22:28:16 | **竞速跳首块观测表**，今天新增字段 |
| `race.disabled` | `{}` | 整渠道禁用表为空（GM 只是单跳/键冷却，没被整渠道判死） |

---

## 3 `/v1/models`（HTTP 200，93 条）

前 10 条（**按 id ASCII 排序**，即实际下发顺序）：

```
0 Beam            1 Claude-Haiku-5.5   2 Conatus        3 DeepSeek-4.1-Flash  4 GLM-5.3-Flash
5 GPT-6-Luna      6 Gemini-3.8-Flash   7 Gemini-AIS     8 HY3                 9 HY3-X
```

结构：`{object:"list", owned_by:"zgate", data:[...]}`，每条 `{id, object, owned_by, canonical_id, group, chain_hops}`。

- **93 = 20 条别名 + 73 条 legacy 键**（`model-alias-map.json` 的 `models` 20 条、`legacy` 73 条，数目精确对齐）。
- `chain_hops` 分布：hops=1 共 19 条、hops=2 共 17 条、hops=3 共 16 条、hops=4 共 33 条、**hops=7 共 8 条**（`Gemini-AIS` 及其 7 个 `gem:ais-gemini-*` 跳）。
- `Gemini-3.8-Flash`：`group=主力, chain_hops=1`；`gem:ais-gemini-3.6-flash`：`canonical_id=Gemini-AIS, chain_hops=7`。
- 93 条中的 `gem:ais-gemini-3.5/3.6/3.7/3.8-flash`、`3.5-flash-lite`、`3.1-flash-lite`、`3-flash-preview` 就是 GM 七跳链的逐跳命名空间；`hjm:[福利]gemini-3.8-flash` 是 HJ 单跳键。

---

## 4 7872 控制台

**没在跑**：`Get-NetTCPConnection -LocalPort 7872` → 0 条；`http://127.0.0.1:7872/` → `fetch failed`（连接被拒）。
设计稿只在文档里（今天 `6771431 docs(console)`），未落成服务。对比：`http://127.0.0.1:7871/` 返回 404（zgate 只认 `/health`、`/v1/*`），`http://127.0.0.1:7863/` 返回 404 `404 page not found`（wb2api 面板在 `/panel/`）。

---

## 5 `provider_config.json` 结构（`~\.zcode\v2\provider_config.json`，15539 字节，mtime 20:57:38）

仓库里没有这个文件，它在 ZCode 用户目录（`zgate.json` 的 `providerConfig` 指向它）。顶层 `{schemaVersion:1, config:{providerOrder, providerConfigRules, modelConfigRules}}`。

- `providerOrder`（3 组）：`opencode-go-chat`(主力) / `opencode-go-chat-free`(免费) / `opencode-go-chat-fast`(省钱)
- `modelConfigRules.providerModelRules`：**20 条**，逐条带 `enabled / properties / optionSpecs`；`manualProviderModelRules` 为空

模型 → 所属 provider 映射（20 条全量）：

| 模型 | 组 | providerId |
|---|---|---|
| DeepSeek-4.1-Flash / Gemini-3.8-Flash / Gemini-AIS | 主力 | opencode-go-chat |
| HY3 / HY4-Free / Beam / Conatus / Iceman | 免费 | opencode-go-chat-free |
| HY4 / Qwen-3.8-Max / Qwen-3.8-Flash / GLM-5.3-Flash / MiniMax-M3.1-Flash / MiMo-2.6-Flash / MiMo-2.6-Pro / HY3-X / Claude-Haiku-5.5 / Muse-Spark1.3 / GPT-6-Luna / Space-Bunny | 省钱 | opencode-go-chat-fast |

网关侧的真实路由（`model-alias-map.json`，20 条，mtime 20:25:37，`generated_at 2026-11-10 20:25:37`）：

| 模型 | 组 | 渠道 | 价 | 跳数 | base | 前几跳 |
|---|---|---|---|---|---|---|
| DeepSeek-4.1-Flash | 主力 | WB | 0.11 | 4 | 127.0.0.1:7863 | cn:deepseek-v4.1-flash → deepseek-v4.1-flash → … |
| Gemini-3.8-Flash | 主力 | **HJ** | 0.05 | 1 | api.gemai.cc | [福利]gemini-3.8-flash |
| Gemini-AIS | 主力 | **GM** | 0.11 | **7** | catiecli.sukaka.top | 3.8 → 3.7 → 3.6 → 3.5 → 3.5-lite → 3.1-lite → 3-preview |
| HY3 / HY4-Free / HY4 / HY3-X / Space-Bunny | 免费/省钱 | WB | 0–0.29 | 1–3 | 127.0.0.1:7863 | cn:* |
| Beam / Iceman / MiMo-2.6-Flash / Claude-Haiku-5.5 / Muse-Spark1.3 / GPT-6-Luna | 免费/省钱 | OC | 0–0.09 | 2 | opencode.ai/zen/go | *-contributor-free / 同名 |
| Conatus | 免费 | QN | 0 | 1 | api.qnaigc.com | qiniu/conatus-free |
| Qwen-3.8-Max / Qwen-3.8-Flash | 省钱 | QD | 0.43 / 0.09 | 1 / 3 | 127.0.0.1:8790 | Qwen3.8-* |
| GLM-5.3-Flash / MiniMax-M3.1-Flash / MiMo-2.6-Pro | 省钱 | WB | 0.08 / 0.08 / 0.13 | 3–4 | 127.0.0.1:7863 | cn:* |

**今天新增/改动过的条目**（拿今天 4 个备份做结构对比，备份文件名的时分不可信、以内容为准）：

| 对比基线 | 模型条数 | 差异 |
|---|---|---|
| `bak-alias-20261110-120017`（12:00 快照） | 44 | 当时还混着 `cn:*`/`qoder:*`/longcat 等 26 条，后清理成 19–20 条；`Gemini-3.8-Flash`、`Gemini-AIS` 均**尚未存在** |
| `bak-alias-20261110-145209` | 19 | 只缺 `Gemini-AIS` |
| `bak-alias-20261110-180629` | 19 | 只缺 `Gemini-3.8-Flash` |
| `bak-alias-20261110-202537` | 20 | 与当前**模型集合完全一致** |
| `bak-effort-20261110125143` | 20 | 12 个模型的 `optionSpecs.reasoningLevel` 由空 map 变成实值（Gemini-3.8-Flash / Gemini-AIS / Beam / Conatus / Iceman / Qwen-3.8-Flash / MiMo-2.6-Flash / MiMo-2.6-Pro / Claude-Haiku-5.5 / Muse-Spark1.3 / GPT-6-Luna 等） |

结论：**今天真正落进 provider_config 的只有两件事** —— ① 模型集合清理 + 新增 `Gemini-AIS`、`Gemini-3.8-Flash`；② 12 个模型的推理档位（`reasoningLevel.values` + `map` 表达式，Gemini 系走 `thinking_budget` 1024/4096/16384，其余走 `reasoning_effort`）。

---

## 6 二进制溯源：跑的是不是今天的代码

| 证据 | 值 |
|---|---|
| 进程 | pid 31480，`zgate.exe serve`，**启动 2026-11-10 22:25:37.911** |
| 可执行文件 | `F:\Project\ModelBus\gateways\zgate\zgate.exe`，10717184 字节，**mtime 2026-11-10 22:24:36** |
| Go buildinfo `vcs.revision` | `bfd6b9e7dddc4e8ea7db618e04bdba33992206e6` = **当前 HEAD `bfd6b9e`** |
| Go buildinfo `vcs.time` | `2026-11-10T14:08:29Z`（= 22:08:29 +08，即 HEAD 提交时刻） |
| Go buildinfo `vcs.modified` | **`true`** → 编译时工作区是脏的，未提交改动也编进去了 |
| 二进制内字符串 | `streamIdleHeartbeatSec` / `earlyCommitMs` / `earlyKeepaliveSec` / `zgate keepalive` / `silenceCooldownSeconds` / `headerTimeoutSec` / `reasoningGuard` / `forceEffortModels` / `hajimiEnvFile` 全部命中 |
| 源码 vs 二进制时序 | `race.go` 22:16:16、`router.go` 22:16:12、`race_test.go` 22:17:40，**全部早于 22:24:36 的编译**；`gateways/zgate` 下无任何 `.go/.json` 比二进制新 |
| 启动日志 | `22:25:37 zgate 0.3.0 已启动: http://127.0.0.1:7871/v1`、`配置文件 : ...\zgate.json`、`alias map : ...model-alias-map.json (20 models)` |

**判定：跑的就是今天的代码**（HEAD `bfd6b9e` + 22:16 的未提交竞速改动），不是旧进程、不是旧二进制。启动于 22:25，此后有真实流量（`/health uptime_s`、日志 273 条 DeepSeek 请求、4 条 Gemini-AIS 请求）。

---

## 7 今天的改动 × 运行态可观测性

### 7.1 运行态**能**看到（有硬证据）

| 改动 | 端点/日志证据 | 全局还是局部 |
|---|---|---|
| `1c42f03` 接入 HJ 哈基米渠道 | `/health.hajimi = {state:up, base:api.gemai.cc, key:true}`；`/v1/models` 有 `hjm:[福利]gemini-3.8-flash` | 新增 1 个渠道，**只影响挂 HJ 的模型**（当前仅 `Gemini-3.8-Flash`） |
| `58b7ce8` 哈基米 3.8 拆成独立模型 | 别名表 20 条里 `Gemini-3.8-Flash → HJ / 0.05 / 1 跳`；`/v1/models` 第 7 位 `Gemini-3.8-Flash`（chain_hops=1） | 局部（单模型） |
| `f52450e` Gemini-AIS 七跳降级链 + 首字对冲 | `/v1/models` 8 条 `hops=7`；`/health.race.hops` 三条 GM 跳的 `firstBlockMs/verdict/at`；日志 `22:27:56 [race] 发出 1/7 GM\|ais-gemini-3.8-flash\|` → 22:28:16 503 → `发出 3/7 ...3.6-flash` → `4/7 ...3.5-flash` | 局部（GM 渠道） |
| `1c42f03` 静默冷却 / 软冷却 | `/health.cooling=1`；日志 `22:25:48 OC\|beam-free\| 地区受限（HTTP 403），冷却 30m0s`、`22:28:16 GM\|ais-gemini-3.8-flash\| 上游 HTTP 503，冷却 1m0s` | 全局机制，按跳/按键生效 |
| `1c42f03`+`8c9825c` 判死权归上游（GM/HJ 关本地看门狗） | `zgate.json`：`channelPolicy.GM/HJ.headerTimeoutSec = -1`（`router.go:346-348` `<0 → return 0` 即关看门狗）；对照日志里旧行为 `19:38:40 上游 45s 内没给响应头，判这一跳沉默并换跳`，**22:25 重启后该消息 0 条** | **局部**：只有 GM/HJ，其余渠道仍走全局 `upstreamHeaderTimeoutSec=45` |
| `96e274d`+`f52450e` 目录汇总 | `/v1/models` 93 条、`owned_by=zgate`、带 `group/chain_hops` | 全局（所有模型） |
| `9adde7f` `/health` 段表由 `keys.Channels` 驱动 | `/health` 出现 7 个渠道段（opencode/workbuddy/qoder/qwen/qiniu/gemini/hajimi），无硬编码残留 | 全局（新增渠道自动出段） |

### 7.2 运行态**看不到**（代码/配置层存在，端点上无痕迹）

| 改动 | 为什么看不到 | 怎么才能验 |
|---|---|---|
| `bfd6b9e` 流式提前交卷 + SSE 心跳 | `/health` 无对应字段；代码只在交卷时写 `: zgate keepalive` 注释行，**不打日志**（全日志 24691 行里 `提前交卷`/`keepalive` 0 命中）。运行态是**开启**状态：`zgate.json` 未写 `earlyCommitMs`，`config.go:277-278` 把 0 归一成 **8000ms** | 发一次 streaming 请求，挑一个 8s 内不回响应头的跳（如 GM 3.8），观察是否立刻 200 + `text/event-stream` 且每 10s 一条 `: zgate keepalive` |
| `e032924` 思考守卫 `reasoningGuard` | `zgate.json` 有段落（`mode=models, models=[Iceman, iceman-contributor-free], forceEffort=high`），但 `/health` 不输出；日志 22:25 后 `reasoning` 只 1 条命中（非守卫事件） | 对 `Iceman` 发一次带非法段的请求，看是否被改写/重试 |
| 未提交 `raceFailTTL=10m / raceOKTTL=1h` 观测保鲜期 | `hopStatSnap.Seen` 是 `json:"-"`，`/health.race.hops` 只给 `firstBlockMs/verdict/at`，看不出「已过期」 | 3.8 在 22:28:16 被判 SU；**22:38:16 之后再发 Gemini-AIS，若 `[race] 发出 1/7` 回到 3.8，即证明保鲜期生效**（截至本报告 22:47 无此类请求，未验证） |
| 未提交 `tools/model_alias.py` / `dsh_sync.py`（推理档位继承 + 漂移守门） | 纯 Python 工具侧，不进程网关；`provider_config.json` mtime **20:57:38**，早于两个脚本改动的 21:15/21:17 → **本轮改动还没写进配置** | 跑 `python tools/model_alias.py --check`（只读模式）看漂移报告 |
| `12` 个模型的 `optionSpecs.reasoningLevel` | 网关**不读** `optionSpecs`（`keys.Load` 只取 `providerRules[].config.access.apiKey`，`keys.go:50-65`），`/v1/models` 也不带档位 | 只有 ZCode 客户端能体现（模型选择器的推理档下拉） |
| 7872 控制台 | 服务未启动 | 需要单独起（本任务禁止改配置/起进程） |

---

## 8 未提交改动现状（`git status`）

```
 M gateways/zgate/internal/router/race.go        (7 +/-)   mtime 22:16:16
 M gateways/zgate/internal/router/race_test.go   (33 +)    mtime 22:17:40
 M gateways/zgate/internal/router/router.go      (31 +/-)  mtime 22:16:12
 M tools/dsh_sync.py                             (97 +/-)  mtime 21:17:29
 M tools/model_alias.py                          (238 +/-) mtime 21:15:29
?? tests/test_dsh_sync_efforts.py                mtime 21:12:07
?? tests/test_model_alias_efforts.py             mtime 21:16:14
```

- **前三个 Go 文件已经编进运行中的二进制**（都早于 22:24:36 编译，buildinfo `vcs.modified=true`）。
- 后四个是 Python/测试侧（`EFFORT_CHANNELS`、`drifted_efforts` 档位继承与漂移守门），与网关进程无关。
- 无 `provider_config.json` 的未提交副本落在仓库里（它不在版本库）。

---

## 9 复现命令（只读）

```bat
curl -s -m 8 http://127.0.0.1:7871/health
curl -s -m 10 http://127.0.0.1:7871/v1/models
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter 'ProcessId=31480' | Select ProcessId,Name,CreationDate,ExecutablePath"
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 7872 -ErrorAction SilentlyContinue"
git -C F:\Project\ModelBus log --since=2026-11-10T00:00:00 --pretty="%h|%ad|%s" --date=format:%H:%M
```

二进制溯源（不依赖 strings 工具）：`zgate.exe` 内 `\xff Go buildinf:` 魔数后跟 `vcs.revision` / `vcs.time` / `vcs.modified` 明文段。

日志：`%LOCALAPPDATA%\ZCodeGateway\zgate.log`（2476106 字节，24691 行，最后写入 22:41:41）。

---

## 10 待补 / 风险

- **未验证项**：提前交卷（需慢跳 streaming）、思考守卫（需发请求）、竞速保鲜期过期（需 22:38 后再发 Gemini-AIS）。本任务限定只读、且不允许干扰线上会话流量，故只给出判据不发请求。
- `/health.cooling` 只有计数没有键名；定位到具体跳需读日志 `冷却 NmNs` 行。
- `/health` 不输出 `channelPolicy` 实况（`headerTimeoutSec=-1` 只能从 `zgate.json` + 代码语义 + 「22:25 后无 45s 沉默告警」三条旁证推断）。
- 7872 控制台未启动，`docs/CONSOLE.md` 的页面清单目前只有设计态。
