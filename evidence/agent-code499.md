## 结论

证据不足：缺「CLIENT_DISCONNECTED」/499 生成点（面板数据源与上游侧代码/日志）、5.4s 计时来源、面板记录与 zgate 日志的请求 ID 关联；本地仅确认 zgate 流式断开静默 return 且未产出 499、20:26:48 AIS 起跳 / 20:26:56 early 交卷 200，按任务口径不定实际成因。

## 证据

### ① 「CLIENT_DISCONNECTED」/499 由谁生成并写进后台请求面板

- E1（ModelBus 全仓源码无该串定义）命令 → 原始输出摘录：grep({pattern:"CLIENT_DISCONNECTED|客户端与catiecli断开连接|499", path:"F:\Project\ModelBus", include:"*.{go,js,ts,jsx,tsx,json,py,cmd,ps1,yaml,yml,md}"}) → 21 命中，逐条均为历史分片/文档里的行号、耗时数值与任务书副本；grep({pattern:"499|CLIENT_DISCONNECTED|客户端与.{0,20}断开连接", path:"F:\Project\ModelBus\gateways", include:"*.{go,js,ts,json}"}) → matches=0。范围含 gateways/zgate/**、gateways/legacy-router/**、tools/**、providers/**。.codegraph 按 lead 实测 Not initialized，未 init，直接用 grep/glob/read。
- E2（DSH 宿主解包目录内 dsh 包无 catiecli / CLIENT_DISCONNECTED 定义）命令 → 原始输出摘录：fs.readdirSync('F:/Program Files',{withFileTypes:true}).filter(d=>d.isDirectory()&&/^Deep/i.test(d.name)) → DEEP_DIR_CODES=[68,101,101,112,83,101,101,107,32,72,97,114,110,101,115,115] LEN=16（真实名含第 9 位空格，显示层渲染会变形，硬写注入路径必 ENOENT）；拼 resources/app/dsh → DSH_EXISTS=true，顶层条目 desktop-runtime.json / node_modules / package.json。grep({pattern:"catiecli", path:$APP, include:"*.{js,mjs,cjs,ts,tsx,jsx,json,md,yml,yaml}"}) → matches=0；grep({pattern:"CLIENT_DISCONNECTED|客户端与.{0,20}断开连接|后台请求|错误类型", path:$APP, ...}) → matches=13，逐条均为无关文档词（如 node_modules/@deepseek-ai/dsh/docs/upgrade-guide/v0.2.1-rc.4/model-listing-refresh/guide.zh.md:11 的「后台请求」、node_modules/@deepseek-ai/dsh-client-ui-agent-preset/src/client/guide-locales.ts:119 的「错误类型」），无 499 / 断开文案。grep 扫 %USERPROFILE%\.dsh\plugins 与 F:\Project\_merged\DeepseekHarness（js/mjs/cjs/ts/tsx/jsx/json/md/go/html）→ 各 matches=0。
- E3（宿主进程加载的确是这份解包目录）命令 → 原始输出摘录：Get-NetTCPConnection -State Listen → 127.0.0.1 8873 22284；进程命令行 → EXE=F:\Program Files\DeepSeekRuntime\DeepSeekRuntime.exe CMD="... --expose-internals ... resources\app\dsh\node_modules\@deepseek-ai\dsh-desktop-host\lib\index.js" "resources\app\dsh" %USERPROFILE%\.dsh\profiles\desktop ...（显示层渲染值）。resources 下无 app.asar 本体，仅有 app/、app.asar.unpacked/、app.asar.purge-20261112120035-f6b1.bak（208137981 B）。
- E4（11 个网关日志无该串；本机唯一字面 499 是 11-09 cliproxyapi 访问日志）命令 → 原始输出摘录：foreach *.log in %LOCALAPPDATA%\ZCodeGateway，Select-String -Pattern 'CLIENT_DISCONNECTED','客户端与catiecli断开连接','客户端与.{0,25}断开连接' → 11 个文件全 HITS=0；Select-String zgate.log -Pattern '\b499\b' → LITERAL499=0，-Pattern 'disconnected|断开连接' → DISCONNECTED=0；cliproxyapi.stdout.log 全文件唯一 499 行 → L140: [2026-11-09 19:01:56] [f9ef9b72] [warn ] [gin_logger.go:111] 499 |        3.012s |       127.0.0.1 | POST    "/v1/chat/completions"（同文另见 evidence/agent-gemini-code.md:400；该文件 :395 的 auth 值已在原分片脱敏为 <REDACTED-API-KEY>，本分片未复制）。
- E5（面板文案在本次可复核的本地源码/日志里缺位）命令 → 原始输出摘录：grep({pattern:"CLIENT_DISCONNECTED|客户端与catiecli断开连接", path:"%USERPROFILE%\.dsh\storages"}) 命中的是会话缓存里本任务书/其它任务书副本（如 session_projcache\sessions\456a8cbc-8ed3-4997-9f4c-529fe292cbe0.json:208），非代码定义；web_fetch http://127.0.0.1:8873/ → status=401 body="dsh web authentication required; reopen the URL printed by dsh web."（只读路由未取到面板数据；按浏览器纪律未开 builtin_browser、未触碰 DSH GUI）。purge bak 未逐字节扫（该 pwsh 会话 RG=NOT_FOUND），见未解决项。据 E1–E5：生成方证据不足，已排除 ModelBus 全仓源码、DSH 宿主 dsh 解包目录、.dsh\plugins、DeepseekHarness 源码、11 个 ZCodeGateway *.log；确切文件:行号与原始字符串缺。

### ② 5.4s 对应哪个超时/首块看门狗/空闲断开参数

- E6 现役配置实读：F:\Project\ModelBus\gateways\zgate\zgate.json:12 "streamIdleHeartbeatSec": 15、:13 "upstreamHeaderTimeoutSec": 45、:14 "chainBudgetSec": -1；:43-55 GM policy "firstBlockMs": 0(:47) / "hedgeAfterMs": 0(:48) / "maxParallel": 1(:49) / "headerTimeoutSec": -1(:52)。与 lead 给的 MEMORY.md 现役口径一致。
- E7 缺省值代码位置：F:\Project\ModelBus\gateways\zgate\internal\config\config.go:312-313「if c.StreamIdleHeartbeatSeconds == 0 { c.StreamIdleHeartbeatSeconds = 15 }」、:315-318「if c.EarlyCommitMs == 0 { c.EarlyCommitMs = 8000 }」；:181-182「EarlyKeepaliveSec int json:"earlyKeepaliveSec"」注释「0/缺省 = 10」；:183-189 UpstreamHeaderTimeoutSec 注释「0/缺省 = 12 秒，负数 = 关掉这个看门狗」+「2026-11-10 实测同一跳 catiecli ais-gemini-3.8-flash 要 60.2 秒才回 503」。
- E8 事发窗口实况：zgate.log L52054「2026-11-12 20:26:56 INFO  [early] 上游 8s 内没给响应头，先对客户端交卷 200（model=Gemini-AIS，心跳 10s）」；F:\Project\ModelBus\gateways\zgate\internal\router\early_sse.go:186-203 commitLocked 在 early 分支自设「Content-Type: text/event-stream; charset=utf-8」/「Cache-Control: no-cache」/「Connection: keep-alive」并删 Content-Length；:126-144 已交 200 后 code>=300 改写流内 error 事件。
- E9 5.4s 无对应配置：F:\Project\ModelBus\docs\TROUBLESHOOTING.md:577 现配置「reasoningGuard.probeSeconds = 15」；:625「同一跳 ais-gemini-3.8-flash 每次都要 60.241 秒才回 503 … 期间客户端等不到首字节会自动重试」；:658「DSH 的 retryPolicy 把 SERVER 列为可重试（maxRetries: 1）… 13 秒后客户端重试」。全仓 grep 5\.4s|5400|5\.4\b 只命中 F:\Project\ModelBus\docs\MODEL-PROVIDERS.md:563「| ais-gemini-3.1-flash-lite | 503，5.2s / 5.4s | 死跳 |」（另一模型的历史耗时）与各分片里的任务书副本。8s / 10s / 15s / 45s / 60.241s / 13s 均 ≠ 5.4s；20:26:48（L52050 起跳）→ 20:26:56（L52054 early 交卷）为 8s，亦 ≠ 5.4s。结论：5.4s 参数来源证据不足。

### ③ 流式 /v1/chat/completions 判「客户端断开」的条件（zgate 侧；均未产出 499）

- E10 SSE abort / context cancel：F:\Project\ModelBus\gateways\zgate\internal\router\race.go:548「baseCtx, cancelAll := context.WithCancel(r.Context())」、:553「ctx, cancel := context.WithCancel(baseCtx)」（客户端取消沿 baseCtx 传播到每跳上游请求，:560 起每跳 rr := r.WithContext(WithProxy(ctx, ...))）、:639-640「case <-r.Context().Done(): return」；F:\Project\ModelBus\gateways\zgate\internal\router\router.go:990「http.NewRequestWithContext(r.Context(), ...)」、:1013-1018 注释「客户端已经走了（用户中断 / 切模型 / 页面关掉）：这次请求作废，直接收工。」+「if r.Context().Err() != nil { return }」、:1385-1386「case <-r.Context().Done(): return」。
- E11 写失败（对端断开）：router.go:1365-1367「if _, writeErr := w.Write(rr.data); writeErr != nil { return }」；心跳写失败 :1378-1379 同样 return。
- E12 上游 EOF / 读错误：router.go:1324-1329「if readErr != nil { s.closeTruncated(w, flusher, model, true, tracker); return }」（补帧收口，未回状态码）；:1332-1334 注释「上游思考阶段常静默 30-60 秒（2026-11-10 实测 iceman 正文中断 51.9 秒），中间层和宿主都会把这当成「连上了但没说话」」。
- E13 读超时/首块看门狗：router.go:357-375 headerTimeout(channel) 对 HeaderTimeoutSec < 0 返回 0「这一渠道不要看门狗」、:911「if wait <= 0 || !wantsStream(body) { return s.client.Do(req) }」（GM 现役 -1 → 单跳头看门狗关闭）；:981-987 首块看门狗仅 at.policy.FirstBlockMs > 0 时生效（GM=0 → 关闭）；:1245-1253 peekFirstContent(streamSrc, firstBlock, r.Context())。router.go:894-947 doForward 的 timer 到点返回 &silentErr{wait: wait, budget: budgetBound}，上层 :1020-1065 写 504 / 502，未生成 499。
- E14 legacy 与协议桥：F:\Project\ModelBus\gateways\legacy-router\unified-router.js:273、:347「req.on('aborted', () => upstream.destroy());」、:260/:324「res.writeHead(upstreamRes.statusCode || 502, upstreamRes.headers);」；F:\Project\ModelBus\gateways\legacy-router\protocol_bridge.js:67「resolve({ status: response.statusCode || 502, json, text });」。只 destroy 上游 / 透传或兜底 502。
- E15 上游 base 实读：F:\Project\ModelBus\gateways\zgate\zgate.json:80「"GM": { "base": "https://catiecli.sukaka.top/v1", "keyEnv": "GEMINI_API_KEY" }」（凭据仅环境变量名，值未取）；F:\Project\ModelBus\gateways\zgate\internal\keys\keys.go:119「reGMBase = regexp.MustCompile("(?i)catiecli\.sukaka\.top")」；internal/config/config.go:381「Base: "https://catiecli.sukaka.top/v1"」。全仓无「客户端与catiecli断开连接」字样（E1）。

### ④ 20:20–20:35 请求日志与相邻原始行

- E16 文件存在（pwsh 原始输出）：ZGATE=5238002 bytes, LastWrite=11/12/2026 21:08:19；%LOCALAPPDATA%\ZCodeGateway\ 下 11 个 *.log：cliproxyapi.stderr.log / cliproxyapi.stdout.log / deploy-zgate.log / qoder.stderr.log / qoder.stdout.log / watchdog.log / workbuddy.stderr.log / workbuddy.stdout.log / zgate-daemon.log / zgate-launch.log / zgate.log；20:20–20:35 窗口 WINDOW_LINES=336。
- E17 与本次请求相邻的原始行（无凭据，原样）：Select-String zgate.log -Pattern '2026-11-12 20:26:4','2026-11-12 20:26:5','2026-11-12 20:27:0' →
  L52049: 2026-11-12 20:26:46 INFO  POST /chat/completions model=DeepSeek-4.1-Flash -> WB:cn:deepseek-v4.1-flash (1/4)
  L52050: 2026-11-12 20:26:48 INFO  POST /chat/completions model=Gemini-AIS -> GM:ais-gemini-3.8-flash (1/3)
  L52051: 2026-11-12 20:26:49 INFO  POST /chat/completions model=HY4-Free -> WB:cn:hy4free (1/1)
  L52052: 2026-11-12 20:26:55 INFO  POST /chat/completions model=HY4-Free -> WB:cn:hy4free (1/1)
  L52053: 2026-11-12 20:26:56 INFO  POST /chat/completions model=HY4-Free -> WB:cn:hy4free (1/1)
  L52054: 2026-11-12 20:26:56 INFO  [early] 上游 8s 内没给响应头，先对客户端交卷 200（model=Gemini-AIS，心跳 10s）
  L52055: 2026-11-12 20:26:58 INFO  POST /chat/completions model=HY4-Free -> WB:cn:hy4free (1/1)
  L52056: 2026-11-12 20:27:05 INFO  POST /chat/completions model=DeepSeek-4.1-Flash -> WB:cn:deepseek-v4.1-flash (1/4)
  同窗口另有 L51937: 2026-11-12 20:21:45 INFO  [race] 这条链走串行：GM:ais-gemini-3.8-flash -> GM:ais-gemini-3.7-flash -> GM:ais-gemini-3.6-flash（全链都没有要求对冲的跳）。
- E18 结论：有 20:20–20:35 请求日志，zgate.log 仅记起跳/early/串行决策，未记完成状态、耗时、错误码；窗口内无 ais-gemini-3.8-flash 与 499 / disconnected 相邻行（E4 全文件 LITERAL499=0 / DISCONNECTED=0）。workbuddy.stdout.log 20:26:5x N=16，全部是 deepseek/hy4 的 200/400/503 行与行号 #499 类噪声，无 Gemini-AIS / 499 状态 / 断开串（账号名、rid 等标识未摘录）。cliproxyapi.stdout.log 的 499 行日期为 2026-11-09（E4），非本窗口。

### 与 lead 已查教训对照（未重复查）

- E19 Lmwbrqdid：F:\Project\ModelBus\gateways\zgate\internal\router\race.go:210「if c.Delta.Content != "" || c.Delta.Reasoning != "" {」:211「return true }」（reasoning 也算首块）；本次 zgate.json:47 firstBlockMs: 0 与「关看门狗」前置一致，但 F:/Project/ModelBus/docs/PITFALLS.md §50 的结局是 200 已下发后的「只思考零正文」退化（带 tools、最短观测 14.6s），本次面板是 5.4s / 499 / 无正文，共享前置条件尚不足以判为同一触发链，证据不足。
- E20 Lmwbp7phv：事发日志 L52050 仍有 GM:ais-gemini-3.8-flash (1/3) 起跳、L51937 三跳全 GM，仅证 20:26 时 AIS 链在册且被实际选中；model_probe --max-tokens 32 误删属配置层历史，本次日志仅覆盖事发时刻。

## 未解决项

- 缺「CLIENT_DISCONNECTED」/499 生成点：本地已排除 ModelBus 全仓源码、DSH 宿主 resources\app\dsh 解包目录、%USERPROFILE%\.dsh\plugins、F:\Project\_merged\DeepseekHarness、11 个 ZCodeGateway *.log；仍缺后台请求面板的数据源/记账代码（含宿主侧文件:行号与原始字符串）、上游 catiecli / WB 网关侧 499 定义与本次请求 ID。
- 缺 5.4s 的来源：面板耗时计时起止、DSH retryPolicy 具体超时数值、catiecli 客户端超时；现有 8s / 10s / 15s / 45s / 13s / 60.241s 均对不上。
- 缺将面板那条 20:26:55 / 5.4s 与 zgate.log L52050 20:26:48 起跳、L52054 20:26:56 early 交卷对齐的请求 ID / 关联字段；zgate 日志未记完成状态。
- app.asar.purge-20261112120035-f6b1.bak（208137981 B）未逐字节扫（该 pwsh 会话 RG=NOT_FOUND，未用其它二进制串检索）；宿主 renderer/、lib/ 未做全量二进制串检索。
- web_fetch http://127.0.0.1:8873/ 返回 401，面板数据未取到；按浏览器纪律未开 builtin_browser、未触碰 DSH GUI。
- 运行态 zgate 进程实际加载的 zgate.json 是否等同仓内文件未验证（本次只读仓内配置与日志，运行态保持原样）；POST /admin/reload 等运行态快照未取。
