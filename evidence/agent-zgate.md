# agent-zgate：上游 429 导致 DSH 持续重试/切渠道的配置点踩点

> **一句话**：45s/700ms 是 zgate 的 Go 常量（改配置无效、必须重建+受控重启），渠道优先级来自 alias map 的 `chain[]` 顺序（每请求热加载），workbuddy `soft_rate=600s` 对当前 6004 限流**根本不生效**（走的是上游重置墙钟），真正该补的是 `pool.model_fallback` 与 zgate 的 429 冷却对齐。

检索范围：`F:/Project/ZcodeAIModels/gateways`、`%LOCALAPPDATA%/ZCodeGateway/*.log`、`~/.zcode/v2/model-alias-map.json`。仓根 `.codegraph/` 存在但 `codegraph_status/explore` 均报数据库打开失败（WAL 只读），按约定退回 grep/glob/read，未建索引。全程只读生产配置，未重启任何长驻进程。

---

## 1. 结论：可直接执行的参数清单（优先级排序）

| # | 文件:行 | 配置键 / 常量 | 现值 | 建议值 | 生效方式 | 优先级 |
|---|---|---|---|---|---|---|
| 1 | `gateways/upstream/workbuddy/config.json:92` 的 `pool` 节（键缺失，运行态 `GET /panel/api/config` 回 `pool.model_fallback=null`；键定义 `cmd/server/config.go:413`） | `pool.model_fallback` | `null`（样例 `config.example.json:123` 为 `{}`） | `{"deepseek-v4.1-flash":"deepseek-v4-flash"}` | **热加载，无需重启**：只经 `POST /panel/api/config` 保存（`internal/panel/panel.go:290` → `cmd/server/main.go:859-878` 写 livecfg 快照 → `internal/server/handler.go:936-975` 下个请求按新表降级）。直接编辑 config.json **不生效**（cmd/server 全目录 grep `fsnotify/.watch` 命中 0）。`restartRequiredFields`(`main.go:950-993`) 不含此键，响应 `restart_required=[]` | **P0** |
| 2 | `~/.zcode/v2/model-alias-map.json:21-59`（`DeepSeek-4.1-Flash.chain[]`，generated_at `2026-11-05 12:00:42`）；同型 4 跳链另见 `:381-419`、`:442-480` | `chain[]` 数组顺序 = 渠道优先级 `(1/4)~(4/4)` | `WB:cn:deepseek-v4.1-flash` → `OC` → `OC@proxy` → `QW`（WB 为 **1/4**） | 把 WB 跳移到 `chain[3]`（QW 之前），即 `OC → OC@proxy → WB → QW`；或在生成器 `tools/model_alias.py:151` 的 `TAIL_HOPS` 追加 `("WB","cn:deepseek-v4.1-flash")` | **热加载，无需重启**：`internal/alias/alias.go:78-105` 按 mtime+size 每请求 `Reload()`（调用点 `router.go:248,608,877`）。`zgate reload` 也能触发 `s.aliases.Reload()`。注意生成器会周期性整份重写，见「未解决项」 | **P0** |
| 3 | `gateways/zgate/internal/router/router.go:51` | `rateLimitCooldown`（Go `const`，**无配置键**；`internal/config/config.go:44-59` 的 `Config` 无此字段，`zgate.json` 也无） | `45 * time.Second` | 对「带上游重置时刻」的 429 改为 `min(resetAt-now, 2h)`，无时刻时保留 `45s`；纯参数应急值 `300 * time.Second` | **不热加载**：改 Go 源码 → `python gateways/zgate/build.py` 重建 `zgate.exe` → md5 → 受控重启（`%LOCALAPPDATA%/ZCodeGateway/swap-zgate.ps1:1-41`）。`zgate reload`(`main.go:294-327` / `router.go:863-886`) 只重读 zgate.json/keys/children，**换不掉编译期常量**。本会话禁止重启 | **P0（代码）** |
| 4 | `gateways/zgate/internal/router/router.go:55` | `rateLimitBackoff`（Go `const`） | `700 * time.Millisecond`（无条件就地重试 1 次） | `retry429` 预算在「429 body 含 `6004` / `insufficient_quota` / `将在…重置`」时置 **0**（直接冷却+回落），仅对瞬时 429 保留 700ms；应急值 `1500ms` | 同 #3，重建+受控重启。改动落在 `router.go:544-558`（直转）与 `router.go:132-143`（桥接 `retryBridgeOn429`） | **P0（代码）** |
| 5 | `gateways/upstream/workbuddy/config.json:19` | `cooldown.soft_rate` | `"600s"` | `"120s"`（**仅对「无重置文案、无 Retry-After」的普通 429 生效**；不要指望它解决 6004，机制见 §2） | **热加载，无需重启**：经 `POST /panel/api/config`；`config.go:940-942` 解析 `SoftRateDur` → `main.go:384/520` 注入 `livecfg.Snapshot.SoftCooldown` → `handler.go:192-200` 每次调用读快照 → `main.go:861` 保存时整体替换快照。若设了 `WB2A_SOFT_RATE`(`config.go:675-676,832`)，保存路径用 env 覆盖文件值(`main.go:821`)，且改 env 需重启进程 | **P1** |
| 6 | `gateways/upstream/workbuddy/config.json:20` | `cooldown.soft_rate_max` | `"2h"` | `"30m"` | 同 #5 热加载：`main.go:888` `p.SetSoftRateMax(newCfg.SoftRateMaxDur)`；`internal/pool/cooldown.go:571-588` 的 `d <<= (streak-1)` 封顶。只影响无时刻分支与账号级 `CooldownSoftRate`(`cooldown.go:524-542`) | **P1** |
| 7 | `gateways/upstream/workbuddy/config.json:93-94` | `pool.max_in_flight` / `max_in_flight_global` | `3` / `2` | `2` / `1`（降低同账号并发、减少 429 产生） | **热加载**：`main.go:885-886` `p.SetMaxInFlight/SetMaxInFlightGlobal` | **P2** |
| 8 | `gateways/zgate/internal/router/router.go:60,46,64` | `transportRetryDelay` / `hopCooldown` / `timeoutCooldown` | `300ms` / `30m` / `5m` | `300ms` 保持；`hopCooldown` 降到 `5m`；`timeoutCooldown` 降到 `2m` | 同 #3，重建+受控重启 | **P2（代码）** |

### 热加载 / 重启判定

- **改了就要重启**：`router.go` 的 5 个 `const`（45s/700ms/300ms/30m/5m）、`zgate.json` 的 `listen` / 新增 `children` / `aliasMap` 路径（`router.go:884`）、`WB2A_SOFT_RATE*` 环境变量、workbuddy `upstream.*` / `session_sticky.*`（`main.go:960-991` 列入 `restartRequiredFields`）。
- **改了立即生效**：alias map `chain[]`/`fallbacks`（`alias.go:78-105`）；workbuddy `cooldown.*`、`pool.*`、`models.*`、`thinking.*`（`main.go:859-932`）——**必须走 `POST /panel/api/config`**，直接改磁盘文件没有 watcher。
- **本会话限制**：`zgate` / `wb2api` 为长驻进程，全局 §6 禁止会话自动重启；#3/#4/#8 只给清单，不执行。

---

## 2. 机制与实况证据（不倒日志，只给计数与路径）

- **zgate 429 全链路**：`doForwardWith`(`router.go:480-561`) 收 429 → `rateLimitBackoff=700ms` 后重试同一跳一次（`:544-553`）→ 仍 429 触发 `onThrottled` → `markCoolingFor(hop, 45s)`（`:756-758`）→ `chainAccept(429)=false`（`:828-841`）→ 回落下一跳。桥接对应 `:132-143` / `:145-154`。冷却键 `channel|upstream|proxy`（`:75`）。
- **日志计数**（`%LOCALAPPDATA%/ZCodeGateway/zgate.log`，25601 行，2026-11-01 22:30 ~ 11-05 12:00）：`429 退避 700ms 后重试同一跳` **1038**、`退避后仍 429，冷却 45s` **1038**（**100% 就地重试失败**）、`冷却中，跳过` **4486**、`(1/4)` **5894**、`(4/4)` **9**、`配置已热加载` **0**。典型序列 `:24946-24952`：11:02:23 WB(1/4) → 700ms → 45s 冷却 → fallback OC(2/4)；此后 11:05:22、11:06:27、11:07:17… 约每 45–70s 重新撞一次 WB。
- **渠道优先级 `(1/4)~(4/4)`** 不是配置项，是 `attemptChain` 的 `index+1/len(t.Chain)` 打印：`router.go:739`（chat）、`:686`（桥接）；`t.Chain` 来自 `alias.Target.Chain`(`internal/alias/alias.go:47`)。顺序由 `tools/model_alias.py:941-949` 排序键生成（`TAIL_HOPS` `:151`、机场孪生跳 `with_airport_fallback` `:161-184` 排链尾），落到 alias map `chain[]`。`pool.account_priority`(`cmd/server/config.go:393`) 是 **workbuddy 账号级**优先级，与 `(1/4)` 无关。
- **workbuddy `soft_rate=600s` 如何生效**：`config.go:91/496` 定义与默认 → `:940-942` 解析 `SoftRateDur` → `main.go:384/520` 注入 `livecfg` 与 `server.Config` → `handler.go:192-200` `softCooldown()` 优先读热快照 → `handler.go:2290-2343` `applyErrorPolicy(ErrSoftRate)`。**三条分支**：① body 带「将在 … 重置」→ `upstream.ParseRateReset`(`internal/upstream/client.go:583-602`) → `CooldownSoftForModel(..., resetAt, ...)`(`internal/pool/cooldown.go:221-246`) 把 `modelCooldowns[model].Until` **直接设成上游墙钟**，不指数、不封顶、与 600s 无关；② `14003` 模型繁忙 → `CooldownModelBusy` 10s→1m（`cooldown.go:294-335`），也不吃 soft_rate；③ 只有「无重置文案、无 Retry-After」的普通 429 → `softDurationLocked(600s, hits)`(`cooldown.go:571-588`) 按 `600s→1200s→…→2h` 指数放大。另 `ErrAccountFault`(`handler.go:2423,2430`) 复用该基数。
- **当前真实锁不是 600s**：`workbuddy.stderr.log` 有 **1566** 条 `upstream 429 soft_rate`，样本 `:209`、`:577-580` 全是 `code:6004` +「将在 … UTC+8 重置」；`data/state.json` 显示 **4/4 账号** 的 `deepseek-v4.1-flash` 处于模型级冷却，`until` = 14:29:02 / 14:31:53 / 14:33:05 / 19:46:46 +08:00（2026-11-05），账号级 `cool_kind=0`、`soft_streak=0`。即锁的是「几小时的额度窗口」，而 zgate 每 45s 去重打一次。**调 `soft_rate` 对此零作用**，这是本次排障最关键的因果。
- **为什么 zgate 拿不到这个时刻**：workbuddy 全池 6004 时按 `handler.go:1967-1983` 回 `429` + 数字 `code:6004` + `type:insufficient_quota`，且**刻意不发 Retry-After**（`:1970-1972`：怕客户端按几十分钟静默挂起），封装见 `writeModelQuotaError`(`handler.go:2553-2567`)。重置时刻只在 body 文案里，zgate `doForwardWith` 只把 `head` 用于 `chainAccept`/`retryHint`（`:538-541,594`），未解析 → 只能吃固定 45s。
- **运行态锚点**：`zgate.log:24403-24410` 最后一次 `zgate 0.3.0 已启动 2026-11-05 10:20:28`（19 models）；`GET /panel/api/config` 带 Bearer 回 **200**，`cooldown={"soft_rate":"600s","soft_rate_max":"2h"}`、`pool.model_fallback=null`、`path=F:/Project/ZcodeAIModels/gateways/upstream/workbuddy/config.json`；不带鉴权回 401（`panel.go:312-314` + `httpauth.go:25-36`）。`:7871/health` 与 `:7863/panel/` 均 200。当前进程未设 `WB2A_SOFT_RATE` / `WB2A_SOFT_RATE_MAX`（`environment_managed_fields=null`）。

---

## 3. 行为等价验证方法（可复现）

**A. 热改前基线**

```bat
cd /d <repo>
certutil -hashfile gateways\upstream\workbuddy\config.json MD5
curl -s "http://127.0.0.1:7871/health" > .work\health-before.json
curl -s -H "Authorization: Bearer %WB_GATEWAY_KEY%" "http://127.0.0.1:7863/panel/api/config" > .work\wb-config-before.json
```

`%WB_GATEWAY_KEY%` 取法遵全局 §6；未注入时面板 key 与 `config.json` 的 `api_key` 同源（`zgate/internal/keys/keys.go:117,128`），也可直接在面板配置页操作，不打印 key 明文。

**B. 应用热改（唯一允许的写路径）**

先把补丁写到 `.work/wb-patch.json`（内容如下，不含任何凭据）：

```json
{"cooldown":{"soft_rate":"120s","soft_rate_max":"30m"},"pool":{"model_fallback":{"deepseek-v4.1-flash":"deepseek-v4-flash"},"max_in_flight":2,"max_in_flight_global":1}}
```

```bat
curl -s -X POST "http://127.0.0.1:7863/panel/api/config" -H "Authorization: Bearer %WB_GATEWAY_KEY%" -H "Content-Type: application/json" --data-binary "@.work\wb-patch.json"
```

验收断言：响应 `ok=true` 且 `restart_required=[]`；`GET /panel/api/config` 四键回显新值；`config.json` MD5 变化但 diff **只有**上述键（`saveConfig` 深合并 `main.go:812,998`，并生成 `config.json.bak`）；`/health` 的 `uptime_s` 持续递增且无归零（证明没重启）；`workbuddy.stderr.log` 出现 `model fallback: deepseek-v4.1-flash -> deepseek-v4-flash`（`handler.go:965`）；`zgate.log` 中 `退避后仍 429，冷却 45s` 不再按 45–70s 周期刷出。回滚：把同一 POST 的键改回原值即可，`restartRequiredFields` 自动清空待重启项（`main.go:946-949`）。

**C. 代码改动（#3/#4/#8）的等价证明：本地行为矩阵，不动运行进程**

```bat
set GOCACHE=<workspace>\.work\zgate-cache
set GOTMPDIR=<workspace>\.work\zgate-tmp
cd /d <repo>\gateways\zgate
go test ./internal/router ./internal/alias ./internal/bridge -run "TestFallbackChainRetriesOn503|TestPrefixFallbackWhenMapIsEmpty|TestFallbackChainRetriesOnModelUnavailable|TestHopFatal|TestChatPath504CoolsTheHop|TestTransportFailureDoesNotConsume429Backoff|TestHopProxyIsUsed|TestHopKeySeparatesEgress|TestHopWithoutProxyStaysDirect|TestRegionBlockedFallsThroughToNextHop" -count=1
cd /d <repo>\gateways\upstream\workbuddy
go test ./cmd/server -run "TestSoftRateMaxParsedFromFile|TestSoftRateMaxEmptyFallsBackToDefault|TestBadSoftRateMax|TestEnvironmentManagedFieldsMatchesValidOverrides|TestRestartRequiredIncludesAllAssemblyFields" -count=1
go test ./internal/server ./internal/pool -run "TestChatSoftCoolsOnRateLimitBody|TestApplyErrorPolicySoftRateExponentialBackoff|TestNewHandlerSoftCooldownDefault|TestModelFallbackOn6004|TestModelFallbackNoConfigKeepsOldBehavior|TestChatModelQuotaLockedReturns429|TestCooldownSoftExponentialBackoff|TestCooldownSoftCappedBySoftRateMax|TestCooldownSoftForModelParsedUntil|TestCooldownModelBusyShortWindow|TestModelsAllowedHotReloadViaLive" -count=1
```

**已实跑输出**（临时缓存方案下，退出码全 0）：

```text
GOCACHE=F:/Project/_merged/DeepseekHarness/.work/zgate-cache
ok  zgate/internal/router   2.651s
ok  zgate/internal/alias    0.033s [no tests to run]
ok  zgate/internal/bridge   0.597s [no tests to run]
ZGATE_EXIT=0
ok  github.com/misakano7545/workbuddy2api-panel/cmd/server   0.816s
WBCONFIG_EXIT=0
ok  github.com/misakano7545/workbuddy2api-panel/internal/server 2.715s
ok  github.com/misakano7545/workbuddy2api-panel/internal/pool   0.344s
WBSERVER_EXIT=0
```

默认 `GOCACHE` 的失败原文（**必须换缓存路径**）：`failed to initialize build cache at <home>\AppData\Local\go-build: mkdir <home>\AppData\Local\go-build\00: Access is denied.`；`GOCACHE=off` 同样失败于 `mkdir <home>\AppData\Local\Temp\go-build861414084: Access is denied.`；`<repo>\.work\zgate-gocache` 在 bash 下也 `Access is denied`。合并工作区 `.work/zgate-cache` 实测可写。`python build.py --check` 属部署前额外校验，本会话未执行，不声称通过。

**行为矩阵判据**（改前/改后逐格对比，证不出等价就不要动）：

| 输入夹具 | 期望（改前 → 改后不变的部分） | 期望（改后变化的部分） |
|---|---|---|
| 瞬时 429 → 200 | 2 次上游请求、客户端 200、字节一致 | 保持 700ms 就地重试 1 次 |
| 429+6004 带「将在 T 重置」 | 客户端 429 + `code:6004` + 上游原文、回落 `(2/4)` | zgate 对 WB 跳冷却到 T（改前 45s），T 前 `冷却中，跳过` 不再叠加 `700ms 重试` |
| 429 无时刻、无 Retry-After | `chainAccept=false`、按 `soft_rate` 阶梯冷却 | 冷却上限 2h → 30m，基数 600s → 120s |
| 传输层 EOF → 429 → 200 | `TestTransportFailureDoesNotConsume429Backoff`：恰好 3 次尝试 | 不变 |
| 504 / 403 地区受限 / 400 | `hopFatal` 判定、桥接回落、冷却分级不变 | 不变 |
| alias map 同内容重写 | `zgate status` 的 `alias.models=19`、链 JSON 字节一致 | 只调顺序时 `(1/4)` 由 WB 变 OC，`uptime_s` 不归零 |

**D. 需要重启那一档的部署三步**（本会话不执行）：`python gateways/zgate/build.py` → `certutil -hashfile gateways/zgate/zgate.exe MD5` 前后对比 → `%LOCALAPPDATA%/ZCodeGateway/swap-zgate.ps1`（自带备份/停/换/起/轮询 `/health`/失败回滚，`:1-41`）。

---

## 4. 证据路径（文件:行）

| 主题 | 路径:行 |
|---|---|
| 45s / 700ms / 300ms / 30m / 5m 常量 | `gateways/zgate/internal/router/router.go:46,51,55,60,64` |
| 429 就地重试与 45s 冷却落点 | 同文件 `:132-154`（桥接）、`:480-561`（直转）、`:739-759`（链）、`:828-841`(`chainAccept`) |
| 冷却表 / hopKey / 跳过 | 同文件 `:39-42,75,105-128,660-664` |
| `(1/4)~(4/4)` 打印 | 同文件 `:686`, `:739`；`internal/alias/alias.go:17-33,47` |
| alias map 每请求热加载 | `internal/alias/alias.go:78-105`；调用 `router.go:248,608,877` |
| zgate.json 无 429 参数 | `gateways/zgate/zgate.json:1-42`；`internal/config/config.go:44-59,96-195` |
| zgate reload 能力边界 | `gateways/zgate/main.go:294-327`；`internal/router/router.go:859-886` |
| 渠道顺序生成器 | `tools/model_alias.py:146-151,161-184,891-970`（尤其 `:927`、`:941-949`） |
| 当前链顺序 | `~/.zcode/v2/model-alias-map.json:21-59`（DeepSeek）、`:381-419`（GLM）、`:442-480`（MiniMax）；`generated_at` `:3` |
| soft_rate 定义/默认/env/校验 | `gateways/upstream/workbuddy/cmd/server/config.go:87-95,496-497,675-680,827-833,940-949`；`config.example.json:26-28`；`config.json:18-21` |
| 热应用闭环 | `cmd/server/main.go:379-394,469-488,513-527,742-747,789-932,946-993`；`internal/panel/config.go:15-68`；`internal/panel/panel.go:289-290,312-314`；`internal/livecfg/livecfg.go:17-47,89-113` |
| 600s 的三条分支 | `internal/server/handler.go:191-200,2290-2343,2421-2430`；`internal/pool/cooldown.go:209-283,294-335,511-588`；`internal/upstream/client.go:470-502,577-602` |
| 6004 回包（无 Retry-After） | `internal/server/handler.go:1863-2043,2538-2567` |
| model_fallback 键与行为 | `cmd/server/config.go:405-413`；`internal/server/handler.go:923-975`；`internal/server/model_fallback_test.go:128-157,291-324`；`internal/upstream/model.json:81-89` |
| 运行态日志与状态 | `%LOCALAPPDATA%/ZCodeGateway/zgate.log:24403-24410,24946-24952`；`workbuddy.stderr.log:209,577-580`；`gateways/upstream/workbuddy/data/state.json`（4 账号 modelCooldowns） |
| 长驻进程与部署脚本 | `%LOCALAPPDATA%/ZCodeGateway/swap-zgate.ps1:1-41`, `ensure-zgate.ps1:1-26`, `start-zgate.bat:1-7`；`gateways/zgate/build.py:1-22`；`gateways/upstream/workbuddy/run.bat:12`, `stop-gateway.bat:3` |

---

## 5. 未解决项

1. **链顺序改动不持久**：`~/.zcode/v2/model-alias-map.json` 在本次踩点期间被 `tools/model_alias.py --slot auto --apply` 整份重写（`generated_at` 由 `2026-11-04 20:32:55` 变 `2026-11-05 12:00:42`，对应 `docs/reports/MODEL-SYNC-20261105-1200.md:14`）；11:49/11:52 日志里 `(1/4)=OC`，12:00 文件又变回 `(1/4)=WB`。持久改优先级必须改 `tools/model_alias.py:151` 的 `TAIL_HOPS` 或 `:941-949` 排序键，该文件在 `tools/`（本分片写域之外、亦超出 `gateways/` 检索范围），交父代理/调度器分片处理。
2. **跨层修 45s 需要新增代码**：workbuddy 有意不发 `Retry-After`（`handler.go:1970-1972`），重置时刻只在 body 文案；zgate `doForwardWith` 未解析。要让 zgate 冷却对齐墙钟，需在 `router.go:538-558` 读 `head` 解析 `code:6004` + 重置时间并传给 `markCoolingFor`，或由 workbuddy 增补一个不触发客户端长挂的自定义头。两条都属改代码 + 重建 + 受控重启，**本会话未实现、未验证**。
3. **长驻进程身份未取到**：`Get-CimInstance` / `Get-Process -Id 25512,13428` / `tasklist` 均返回空（`Get-Process -Name zgate,wb2api` 报「找不到进程」），但 `netstat` 显示 `:7863` PID 25512、`:7871` PID 13428 在 LISTENING，两个 health 均 200。运行态锚点改用 `zgate.log:24403` 的启动行与 `/health` uptime（`web_fetch` 对 loopback 返回非公网地址错误，需本地 curl/PowerShell）。进程创建时间/PID 与二进制 md5 的对应关系 `[待补: 需要可读的进程枚举权限]`。
4. **6004 的等价模型只验证了测试夹具**：`deepseek-v4-flash` 存在于 `internal/upstream/model.json:81`，`TestModelFallbackOn6004`(`model_fallback_test.go:130-157`) 断言上游依次收到 `[v4.1, v4]` 并 200；但生产 4 个账号对该等价模型的真实额度/价格未实测，`[待补: v4-flash 在 4 个账号上的 6004 状态]`。WB 跳用的是 `cn:deepseek-v4.1-flash`，`applyErrorPolicy` 会 `SplitRealmPrefix`(`handler.go:2298`) 再查表，裸名键可覆盖；若只对 cn 域降级，用 `cn:deepseek-v4.1-flash` 前缀键（`model_fallback_test.go:298-324`）。
5. **Go 测试缓存限制**：默认 `%LOCALAPPDATA%/go-build` 与 `%TEMP%/go-build*` 均 `Access is denied`；`diagnose-windows-sandbox-acl` 技能可修，但需一次性审批且会改目录权限，本会话改用合并工作区 `.work/zgate-cache` 绕过（已验证 exit=0）。若换机器复现，先指定 `GOCACHE`/`GOTMPDIR`。
6. **委派闸门**：本分片本身由父代理派发；当前 `depth=1/1, remaining=0`，运行时禁止再下派。按 `~/.dsh/AGENTS.md §7/§14` 判定已进 GUI 清单：`≥3目标=否、≥3处同类=是、≥10次工具=是、多视角=否`，不委派理由 `单一写域冲突` + `依赖链必须串行` + `子代理深度上限`。分片路径 `evidence/agent-zgate.md`，写前 `who_claims` 确认无人占用并 `claim_files` 认领。
