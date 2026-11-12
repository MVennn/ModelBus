# 分片 doc499：2026-11-12 20:26:55 AIS 流式 499 文档侧取证

> 落盘 F:\Project\ModelBus\evidence\agent-doc499.md（evidence/ 已存在，真实项目路径，junction 已穿透）。本分片只读 docs/ 全部 .md、%USERPROFILE%\.dsh\procedures 平铺卡库、PROGRESS.md；未改配置 / 源码 / 运行态，未重启或停止 zgate / wb2api / mihomo，未在 PC 上拨测代理节点，未开 builtin_browser；凭据 / token / key 一律 <REDACTED>。CodeGraph 按任务书只用 grep / glob / read，未 init、未 sync。

## 结论

**证据不足：缺 2026-11-12 20:26:55 该条请求的 zgate.log 行、catiecli 侧请求 ID 与 499 生成点、5.4s 客户端超时来源、本次请求是否带 tools 及 effort 档位、20:26:55 运行态 zgate.json / early_sse 生效快照，文档层不能定「实际成因」**；文档级最可能根因为「客户端在首块 / 首字节前主动取消，被 catiecli 侧记为 499 CLIENT_DISCONNECTED」（**由文档推论**，证据链见「## 证据」末段），现役链路六参数、§50 关系、499 既有口径、经验卡结论逐项见「## 证据」E1–E17。

## 证据

### ① 现役 AIS / Gemini-3.8-Flash 链路六参数（逐个确切值 + 路径:行号）

现役值以 `docs/ROUTING-POLICY.md:172` 的「## 8. 当前各渠道实际值」为准；该节 `:179` 正文含 11-11 10:35 / 10:47 / 11:03 三次变更，晚于 `docs/MODEL-PROVIDERS.md:588` 的「2026-11-10 21:30 第四次收敛」，且与 lead 下发的 MEMORY.md 现役口径逐项一致。

| 项 | 确切值 | 文档路径:行号 |
| --- | --- | --- |
| 跳数 | 3 跳，全 GM（3.8 → 3.7 → 3.6） | `docs/ROUTING-POLICY.md:230`、`:237-238`、`:242`；旁证 `docs/reports/MODEL-SYNC-20261112-1209.md:46` |
| headerTimeoutSec（GM） | -1（不设响应头看门狗） | `docs/ROUTING-POLICY.md:179` 表末列、`:194` |
| firstBlockMs（GM） | 0（不判首块） | `docs/ROUTING-POLICY.md:179` firstBlock 列、`:187` |
| hedge（hedgeAfterMs，GM） | 0（不对冲、单发串行） | `docs/ROUTING-POLICY.md:179` hedge 列、`:185`、`:187` |
| maxParallel（GM） | 1（任意时刻只有一路在路上） | `docs/ROUTING-POLICY.md:179` maxParallel 列、`:188` |
| 全局兜底 | upstreamHeaderTimeoutSec = 45 秒 | `docs/ROUTING-POLICY.md:183`、`:31`；旁证 `docs/TROUBLESHOOTING.md:670`、`docs/REVIEW-2026-11-10.md:85` |

补充现役值：`chainBudgetSec = -1`（整条链不设总预算，`docs/ROUTING-POLICY.md:183` / `:195`）；`earlyCommitMs 生效 8000ms / earlyKeepaliveSec 10s`（`docs/ROUTING-POLICY.md:183` / `:196`）。

E1（现役模式原文）`docs/ROUTING-POLICY.md:174` 表头：「| 渠道 | soft | silence | rate | firstBlock | hedge | maxParallel | headerTimeout | 依据 |」；`:179` 逐字：「| GM | 15 | 0 | -1 | 0 | 0 | 1 | -1 | 11-11 10:35 起改**单发串行**：三个对冲字段全部归零，一次只发一跳、失败才换下一跳（用户口径：不并发、不浪费资格、等上游下判决）。3.8 实测首字 127.5s 仍能成功返回，本地按时间判死会把它误杀成 504。10:47 冷却再收紧 soft 60→15、busy 20→10…11:03 再补 `timeoutCooldownSeconds: 20`…与 `retry500Once: true` |」。
E2 `docs/ROUTING-POLICY.md:187-188`：「`hedgeAfterMs`、`firstBlockMs` 都写 0 → `racePlanFor` 返回 false → 走 `attemptChain` 串行链：」「按声明顺序一跳一跳试，**只有这一跳明确失败（4xx/5xx/网络错/缺 key/冷却中）才换下一跳**，任何时刻只有一路在路上。」
E3 `docs/ROUTING-POLICY.md:198`：「代价（已知且接受）：上游若真的挂死，请求会一直挂着直到客户端自己断开；`/health.race.hops` 不记录串行跳的首字耗时（该计数只在竞速路径里埋）…」
E4 跳数旁证 `docs/reports/MODEL-SYNC-20261112-1209.md:46`：「| `Gemini-AIS` | 主力 | 0.11 | GM:ais-gemini-3.8-flash@0.11 → GM:ais-gemini-3.7-flash@0.11 → GM:ais-gemini-3.6-flash@0.11 |」；`:15`「生成时间：2026-11-12 12:08:59」；`:34`「## 链路变化（无）」；`:17`「当前生效清单以 `%LOCALAPPDATA%/ModelBus/current-models.json` 为准」。另 `docs/MODEL-PROVIDERS.md:527`「**2026-11-11 11:03 起链上只留 3 跳**：3.8 → 3.7 → 3.6」、`:546`、`docs/PITFALLS.md:835`「AIS 只留 3 跳，日志变 `(x/3)`」、`docs/TROUBLESHOOTING.md:592` 同。
E5 口径冲突（**历史、非现役**）：`docs/MODEL-PROVIDERS.md:588`「当前真值（2026-11-10 21:30 第四次收敛：**判死权归上游**）」、`:592-593`「| `headerTimeoutSec` | **-1** | **-1** |」「| `firstBlockMs` | 0 | 0 |」、`:595`「| `hedgeAfterMs` | 18000 | 0 |」、`:596`「| `maxParallel` | 2 | 2 |」、`:597`「| `softCooldownSeconds` | 60 | 0 |」、`:653-655`「GM 只保留 `hedgeAfterMs: 18000` 做对冲…全局兜底从 12s 放回 45s」；`docs/TROUBLESHOOTING.md:666-670` 同 21:30 表；`docs/PITFALLS.md:858` 同；`PROGRESS.md:2973-2974` 更早（11-10 第十七轮）「channelPolicy.GM = soft 90 / silence 20 / rateLimitBackoffMs -1 / firstBlock 4000 / hedge 500 / maxParallel 2 / authFail 24」。裁决依据：`docs/ZGATE-LIFECYCLE.md:258`「| 对冲与并发 | 按链首渠道取值 → 按跳聚合（最小正 hedge、最大 maxParallel）→ 单发串行（对冲字段全归零） |」+ `docs/ROUTING-POLICY.md:179` 的 11-11 时间戳 + lead 的 MEMORY.md 现役口径。**本分片未读 zgate.json 运行态**（任务书禁改运行态、禁重启长驻网关），见未解决项。

### ② PITFALLS §50 与本次 499 是否同一触发链 / 文档有没有直接写「客户端等不到首块主动断开」

E6 §50 全文 `docs/PITFALLS.md:911-919`：`:911`「## 50. AIS 跳带 tools 只回思考不回正文，DSH 报「the turn degenerated again after the continuation nudge」 【实例 A】」；`:913`「会话 `sessionStats` 是 `ttftMs=25483 / llmMs=25483 / decodeTokens=0 / toolMs=0` —— 模型想了 25 秒然后什么都没有，正文和工具调用双零。」；`:914`「① 上游：GM 的 `ais-gemini-3.8-flash` 跳在请求**带 tools** 时随机退化成三种形态…② 网关：`hasContentDelta`（`internal/router/race.go:210`）的判定是 `if c.Delta.Content != "" || c.Delta.Reasoning != ""` —— **思考也算首块**，而 GM 的 `firstBlockMs=0` 又把首块看门狗关了，于是「只出思考、零正文」的 200 被当成功原样交给客户端，日志里既没有 fallback 也没有 error 行；③ DSH：`billion-context` 的 `retryEmptyTurn` 把「干净 stop + 有思考 + 零正文 + 零工具调用」判成退化」；`:916` 实测矩阵最短 14.6s（`reasoning_effort=off` 带工具回空参数工具调用）、最长 100s content=0，不带工具 33s 出 1761 字；`:919`「`reasoning` 只能证明上游活着，不能证明它给了可用的答案」。
E7 判定（**证据不足**）：§50 全节零 `499` / `CLIENT_DISCONNECTED` / `catiecli` / 「客户端等不到首块主动断开」字面；其结局是 **200 已下发**后 DSH 客户端判退化，触发器明写是「带 tools」，最短观测 14.6s；本次是 **5.4s / 499 / 无正文 / 客户端与 catiecli 断开**。两者共享的只有模型名 `ais-gemini-3.8-flash` 与 `firstBlockMs=0` 这一前置条件，文档未把两者连成同一触发链 → **证据不足，不能判为同一触发链**。
E8 「客户端等不到首块主动断开」：**文档没有这句直接写法**；最接近的「文档明写」在别处且措辞是「首字节 / 响应头」而非「首块」——`docs/TROUBLESHOOTING.md:678-679`「判死权交回上游之后还剩一个洞：上游 60 秒才给响应头时，这 60 秒里客户端一个字节都收不到，它自己就会判死重试 —— 本地不判死了，不代表客户端不判。」；`docs/TROUBLESHOOTING.md:625`「期间客户端等不到首字节会自动重试，所以后台看到两条。」；`docs/PITFALLS.md:847`「这期间 DSH 等不到首字节会自动重试，反代后台于是出现两条「请求中」。」；`docs/ROUTING-POLICY.md:198`「请求会一直挂着直到客户端自己断开」。这些均为 2026-11-10 机制说明，而 `docs/TROUBLESHOOTING.md:688` 配 early_sse 后写「客户端约 8 秒就拿到 200 + 心跳，不会自己判死」——与「5.4s 自断」存在张力，见未解决项。

### ③ 全仓文档 499 / CLIENT_DISCONNECTED / catiecli 既有解释或处置口径（逐条路径:行号）

E9 命令 → 原始输出摘录：`grep({pattern:"499|CLIENT_DISCONNECTED|客户端与catiecli", path:"F:\Project\ModelBus\docs", include:"*.md"})` → `count=0, matches=[]`；`grep({pattern:"499|CLIENT_DISCONNECTED|客户端与catiecli", path:"F:\Project\ModelBus\CHANGELOG.md"})` → `count=0`；`grep({pattern:"20:26|2026-11-12 20|CLIENT_DISCONNECTED|客户端与catiecli", path:"F:\Project\ModelBus", include:"*.md"})` → `incident=0, incidentMatches=[]`；`grep({pattern:"CLIENT_DISCONNECTED|客户端与catiecli断开连接|客户端断开|主动断开|等不到首块", path:"F:\Project\ModelBus", include:"*.md"})` → `count=1`，唯一命中 `docs/MODEL-ALIAS.md:453`（见 E12）。→ **docs/ 下 499 字面零命中；全仓文档无 CLIENT_DISCONNECTED / 客户端与catiecli断开连接 的既有解释或处置口径**。
E10 全仓 `*.md` 的 `499` 共 21 命中，全部落在 `evidence/agent-*.md`，均为行号 / 计数 / 旧日志，无解释。唯一一条真实请求记录 `evidence/agent-gemini-code.md:400`：「140: [2026-11-09 19:01:56] [f9ef9b72] 499 |        3.012s | 127.0.0.1 | POST "/v1/chat/completions"」——11-09 CP 反代旧日志，无错误类型 / 错误文案，不是本次口径（该分片只读参考，不替其它路定论）。其余 `evidence/agent-aggregation.md:73,97`、`evidence/agent-code-review.md:62,198,258`、`evidence/agent-docs-review.md:373,379`、`evidence/agent-docs-sync.md:77`、`evidence/agent-endpoints.md:69`、`evidence/agent-gateway-lifecycle.md:2437,3878,4514`、`evidence/agent-gemini-logs.md:179,314`、`evidence/agent-gemini-memory-docs.md:459,462,508`、`evidence/agent-map-race.md:126`、`evidence/agent-zcode-census.md:920,921` 均为行号或数值。`PROGRESS.md` 的 499 命中 1 条，非故障解释。
E11 catiecli 在 docs/ 下共 7 处，逐条（**均为渠道描述 / 慢 / 忙，无一条解释 499 或给 499 处置**；凭据字样已脱敏）：
- `docs/MODEL-PROVIDERS.md:524`「## 4.11 谷歌 Gemini（catiecli 中转，本次实例五）」
- `docs/MODEL-PROVIDERS.md:532`「网关：`https://catiecli.sukaka.top/v1`，OpenAI 兼容，`GET /v1/models` 可自取目录。」
- `docs/PITFALLS.md:762`「1. `model_probe.py` 默认 `--max-tokens 32`。GM（catiecli）的 Gemini 是「先思考再出字」，」
- `docs/PITFALLS.md:864`「直连取证（Bearer <REDACTED> 打 catiecli）：短问四跳全 200（3.8 = 7.2s / 3.7 = 5.2s / 3.6 = 2.6s / 3.5-flash-lite = 10.8s）；同样的 1200 字长提示四跳全 503，耗时 3.4s / 10.3s / 22.4s / 4.3s。**这不是链路坏了，是模型忙**，且 503 来得慢（最长 22 秒），会白占看门狗窗口。」
- `docs/ROUTING-POLICY.md:103`「为什么 503 不能沿用整渠道冷却：catiecli 上 3.8 常态化过载，几十秒内能连撞三次，按渠道停 90 秒会把同渠道能用的 3.6 一起躺下…」
- `docs/REVIEW-2026-11-10.md:16`「| 渠道接入 | GM（catiecli）正式进主力组；新增 HJ（哈基米 gemai.cc）… |」
- `docs/TROUBLESHOOTING.md:660`「**根因**：`headerTimeoutSec` / `firstBlockMs` 这套看门狗把「上游慢」判成了「上游死」。而慢是这条链的常态（catiecli 3.8 常态 9-14s 才出正文，哈基米首头会从 2.5s 漂到 10s），判死阈值给多少都在赌，赌错的代价是**一次 502 + 一次重试 + 一次上游重跑**。」
E12 断开相关但**方向不同 / 非 499 口径**：`docs/MODEL-ALIAS.md:453-455`「- **空闲看门狗**：上游连上后连续 30 秒没有任何字节，桥接器主动断开并返回」「`504 upstream_timeout`（`DefaultIdle`）」（同 `docs/PITFALLS.md:606-610`）——桥接器断**上游**、返 504，不是「客户端与 catiecli 断开」；`docs/TROUBLESHOOTING.md:647,649,658` 与 `docs/PITFALLS.md:857`、`docs/MODEL-PROVIDERS.md:651` 是 2026-11-10 21:30「本地判死 → 502 → DSH `retryPolicy`（`maxRetries: 1`）→ 客户端重试 → 上游重跑」的旧机制，结局是 502 而非 499；`docs/CONSOLE.md:156,386` 是控制台日志页 SSE 断开提示，无关。
E13 处置口径（**最接近的既有机制，但文档没把它与 499 挂钩**）：`docs/TROUBLESHOOTING.md:681-684`「处置：流式请求在等响应头的空窗里先交卷 —— 超过 `earlyCommitMs`（缺省 8000 毫秒）还没人写响应头，就先回 `200 + Content-Type: text/event-stream`，之后每 `earlyKeepaliveSec`（缺省 10 秒）补一行 `: zgate keepalive` 注释心跳；上游最后失败时把错误改写成流内 `error` 事件 + `data: [DONE]`，不再回 502。」；`:688`「| 上游 60 秒才给响应头 | 客户端约 8 秒就拿到 200 + 心跳，不会自己判死 | … |」；`:693`「回退：`"earlyCommitMs": -1` 后 `/admin/reload`（需已换上新二进制；旧二进制忽略这两个键）。」；同口径 `docs/MODEL-PROVIDERS.md:659-667,674-675`（`:666`「**不再回一个客户端早就放弃的 502**」）。

### ④ 命中经验卡（按 card 命令读卡，卡是流程不是结论）

E14 教训库第一轮：命令 `error_lessons_search({query:"499 CLIENT_DISCONNECTED 客户端与catiecli断开连接 Gemini-AIS ais-gemini-3.8-flash 流式 首块 只思考零正文"})` → 原始输出 `matched=3, repeat=true, cardPointers=[]`：Lmwbrqdid（与 lead 已查一致：带 tools 退化 / `hasContentDelta`（`internal/router/race.go:210`）把 reasoning 算首块 / GM `firstBlockMs=0` 关首块看门狗 / 200 当成功下发；result 明写「定位到三层根因并写进 F:/Project/ModelBus/docs/PITFALLS.md §50」）、Lmwbp7phv（`model_probe --max-tokens 32` 让先思考模型思考预算吃光 → 同步链误删 Gemini-AIS）、Cmwbpc2uw24（Default 伪档位，无关）。**本轮无 cardPointers，无卡可读**。
E15 教训库第二轮：命令 `error_lessons_search({query:"499 客户端断开 CLIENT_DISCONNECTED 流式断开 首字节 超时 主动断开", limit:10})` → 原始输出 `matched=10, repeat=true, cardPointers=["Get-Content ~/.dsh/procedures/DeepseekHarness-工具-插件升级后补丁失效.md"]`（card-index Cmwbpc2uw20）。按 card 原命令读卡 → 原始输出摘录：`CARD_PATH=%USERPROFILE%\.dsh\procedures\DeepseekHarness-工具-插件升级后补丁失效.md` / `CARD_BYTES=3015` / 36 行。卡中结论**照录**（流程，不推翻重来）：`:8-10`「升级完立刻重跑补丁脚本（脚本幂等，可重复跑）：先 `node ~/.dsh/tools/<patch-script>.mjs --check` 预检、再去掉 `--check` 实打。」；`:17`「补 `node_modules` 里 minified 产物时一律按函数体/内容锚点定位，别硬编码压缩符号（升级即失配，且脚本只 warn 就 exit 0，静默失效）」；`:22`「升级是整包覆盖 node_modules，手改的字节没了」；`:24`「升级后不跑 --check → 静默回退，等到用的时候才发现」；`:30`「补丁版本键与插件版本强绑定，版本一变 pnpm 直接拒绝安装」；`:31`「写入备份统一走 `~/.dsh/tools/lib/safe-write.mjs`（tmp+rename 断 pnpm 硬链接）；原地写会改坏 store blob」。**该卡触发词是「插件升级后行为回退 / ERR_PNPM_UNUSED_PATCH」，与本次 499 无直接锚点，属宽泛查询的误召回；按「卡是流程不是结论」只并入流程，不用它定本次根因。**
E16 卡库中与现役串行模式相关的流程卡（任务书指定范围内主动核读）：`%USERPROFILE%\.dsh\procedures\zgate-竞速-raceStat过期与串行链观测.md`（29 行）→ 结论并入：`:12`「1. **先判走哪条路**：日志有 `[race] 发出 i/n` 才是竞速（`raceChain`）；没有就是串行（`attemptChain`），`raceStat` 压根不产生、`rankedChain` 也没上场。」；`:15`「4. **串行链看另一张表**：`/health.hops` 的 `try` / `ok` / `busy` / `e5xx` / `silent` / `no_first_block` 是逐跳计数，串行链也有。」；`:22`「真要重置观测 → 走 `docs/ZGATE-LIFECYCLE.md` §4 换版流程重启，不做会话内直接重启。」；`:29`「别照抄文档里的分钟数：保鲜期与冷却都是代码常量或配置项，值随版本变，读 `internal/router` 的常量与 `zgate.json`。」→ 该卡支撑「现役单发串行、不要拿 race / 竞速口径套本次请求」，并印证 `docs/ROUTING-POLICY.md:179,187`；其「不做会话内直接重启」与本分片硬约束一致。
E17 卡库全量锚点命令 → 原始输出摘录：`Get-ChildItem -LiteralPath %USERPROFILE%\.dsh\procedures -File -Filter '*.md' | Select-String -Pattern '499|断开|Gemini|AIS|流式|firstBlock|首块' -Encoding UTF8` → `PROCS_FILE_COUNT=37` / `PROCS_HIT_COUNT=1` / 唯一命中 `%USERPROFILE%\.dsh\procedures\_inbox.md:44`（金太阳策略详情页 ListView header，与本故障无关）。→ **卡库 37 张无 499 / CLIENT_DISCONNECTED / catiecli / 流式首块 专门卡**。

### 文档级最可能根因证据链（明确区分「文档明写」与「由文档推论」）

**【文档明写】**
1. 现役 AIS 链 3 跳全 GM、单发串行：`headerTimeoutSec=-1` / `firstBlockMs=0` / `hedge=0` / `maxParallel=1` / `chainBudgetSec=-1`，全局 `upstreamHeaderTimeoutSec=45s`（`docs/ROUTING-POLICY.md:179,183,187-198`）；串行链没有首块看门狗（`docs/PITFALLS.md:840`「`router.go:734` 的 `if at != nil && at.policy.FirstBlockMs > 0` 只在竞速模式成立，串行链就是「发出去、等下去」。」）。含义：本地不判首块、不设响应头窗口、不并发、不设整链预算，首跳挂住就一直挂着。
2. 该链「慢」是常态：catiecli 3.8 常态 9-14s 才出正文（`docs/TROUBLESHOOTING.md:660`），历史实测 `ais-gemini-3.8-flash` 60.241s 才回 503（`:625`）；`docs/ROUTING-POLICY.md:179` 亦载「3.8 实测首字 127.5s 仍能成功返回」。
3. 客户端侧既有判据：`docs/ROUTING-POLICY.md:198`「上游若真的挂死，请求会一直挂着直到客户端自己断开」；`docs/TROUBLESHOOTING.md:678-679`「这 60 秒里客户端一个字节都收不到，它自己就会判死重试 —— 本地不判死了，不代表客户端不判」；`:625` / `docs/PITFALLS.md:847`「DSH 等不到首字节会自动重试」。
4. 缓解机制及其边界：early_sse 在 `earlyCommitMs=8000ms` 后先交卷 200 + SSE、每 10s 一条 `: zgate keepalive`（`docs/TROUBLESHOOTING.md:681-684,688` / `docs/MODEL-PROVIDERS.md:659-667`）；`:688` 明写「客户端约 8 秒就拿到 200 + 心跳，不会自己判死」，`:693` 明写该机制「需已换上新二进制；旧二进制忽略这两个键」。
5. docs/ 下 499 零命中、全仓文档无 CLIENT_DISCONNECTED 解释或处置口径（E9–E13）；§50 只覆盖「200 已下发后的退化」，不覆盖 499（E6–E7）。

**【由文档推论】（以下不是文档原话，禁止当定论）**
- 推论 A：本次耗时 5.4s < 8s earlyCommit 窗口。若该流式请求在 5.4s 内确实一个字节都没收到，则客户端在首块 / 首字节前取消，catiecli 侧把这条被取消的请求记为 `499 CLIENT_DISCONNECTED`「客户端与catiecli断开连接 499」——这是把明写 1 / 2 / 3 串起来的最贴近解释。
- 推论 B：要让推论 A 成立，还需解释「为何 8s 交卷没兜住」：要么 early_sse 未生效 / 未换上带它的二进制（明写 4 的边界），要么客户端另有约 5s 的超时（文档未给该值），要么 499 是 catiecli 侧自己的断开计时而非 DSH 客户端超时。三者文档均无判据 → **证据不足**。
- 推论 C：§50 的「只思考零正文」与本次「无正文」共享 `firstBlockMs=0`（§50 `:914` 明写这项让 200 空回被当成功），但 §50 最短观测 14.6s 且结局为 200 + DSH 判退化，本次 5.4s + 499，时间尺度与结局均不符 → 判为同一触发链**证据不足**。

## 未解决项

- 缺 2026-11-12 20:26:55 该条请求的 `zgate.log` 行：`[race] 发出 i/n` 或串行 `(1/3)`、首帧时间、fallback / error / 冷却行。按 E16 卡 `:12` 先判竞速还是串行，再按 `:15` 取 `/health.hops` 的 `silent / no_first_block` 计数（本分片禁读运行态，未取）。
- 缺 catiecli 侧该请求的请求 ID 与 499 生成点；「客户端与catiecli断开连接」的「客户端」指 DSH / zgate / catiecli 反代的哪一层未定。
- 缺 5.4s 这个数的来源：文档只给 `earlyCommitMs=8000` / `earlyKeepaliveSec=10s` / catiecli 9-14s 出正文 / 60.241s 回 503 / 3.8 首字 127.5s，没有任何 5.4s 超时配置；需查 DSH `retryPolicy` 或 catiecli 客户端超时（`docs/TROUBLESHOOTING.md:658` 只给 `maxRetries: 1` 与「13 秒后客户端重试」）。
- 缺本次请求体是否带 tools（§50 唯一明写触发器）与 `reasoning_effort` 档位；无法判定 §50 退化是否参与。
- 缺 20:26:55 运行态 `zgate.json` / early_sse 是否真生效的快照（`docs/reports/MODEL-SYNC-20261112-1209.md:17` 指当前生效清单以 `%LOCALAPPDATA%/ModelBus/current-models.json` 为准）。本分片按任务书未改运行态、未重启 / 停止长驻网关、未拨测代理节点、未取 /health。
- 文档口径冲突未由运行态复核：`docs/MODEL-PROVIDERS.md:588-599`（21:30，hedge 18000 / maxParallel 2 / soft 60）vs `docs/ROUTING-POLICY.md:179`（11-11，hedge 0 / maxParallel 1 / soft 15）；本分片按更晚时间线 + lead 的 MEMORY.md 口径取后者，若运行态是前者则 ① 需改。
- docs/ 下 `499` 零命中、全仓文档无 `CLIENT_DISCONNECTED` 既有口径、卡库 37 张无专门卡 → 本次 499 属**文档未覆盖**现象，处置口径只能由 lead 结合日志 / 运行态另立。
