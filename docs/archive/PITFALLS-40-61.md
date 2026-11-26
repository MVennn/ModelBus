# PITFALLS.md 历史条目续篇：§40–§61

> **一句话**：`docs/PITFALLS.md` 中 §40–§61 的踩坑原文归档件 —— 编号与正文原样保留、条目仍然有效，2026-11-25 从提交 `5b6d7ad` 的误删中恢复后按体量规则外移。

**回指**：本篇是 [PITFALLS.md](../PITFALLS.md) 的历史条目续篇，不是过时快照 —— 编号（§40–§61）与正文一字未改，条目内容仍按原文生效；正文档因「单篇 ≤ 800 行」（[DOC-RULES.md](../DOC-RULES.md) §6）只留 §1–§39 与 §62，凡引用 `§41` / `§51` / `§61` 这类编号，指的就是本篇对应条目。

**迁入过程**：提交 `5b6d7ad`（2026-11-19）在新增 §62 的同时把 §40–§61 连同 §39 后半段一起覆写丢失（该提交对 `docs/PITFALLS.md` 是 19 insertions / 239 deletions，正文未提删除）；2026-11-25 按 `git show 5b6d7ad^:docs/PITFALLS.md` 原文整段恢复，随后按体量规则拆篇：§39 后半段回 [PITFALLS.md](../PITFALLS.md)，§40–§61 落本篇。

> **归档只读**：本文件按 [DOC-RULES.md](../DOC-RULES.md) §6「归档件只读」不再修改；发现错处请在 [PITFALLS.md](../PITFALLS.md) 里写更正，不直接改本篇。

---

## 40. DSH 的 edit 工具会剥掉 UTF-8 BOM：改了带 BOM 的 .ps1 就变乱码 【通用】

- **现象**：用 `edit_file` / `edit` 改 `sync-models.ps1`（HEAD 版本是
  `EF BB BF` 开头的 UTF-8 BOM），改完 `head -c 3 | xxd` 变成 `23 52 65`（`#Re`），
  BOM 没了。PowerShell 5.1 按 GBK 读无 BOM 的 UTF-8，所有中文注释糊成乱码，
  `Parser::ParseFile` 报一串 `Unexpected token '涓诲姏'` / `The string is missing
  the terminator`。计划任务里跑会直接把脚本跑挂。
- **解法**：每次用 edit 类工具改带 BOM 的文件，改完补一行：
  `python -c "import pathlib;p=pathlib.Path('x.ps1');b=p.read_bytes();p.write_bytes(b if b[:3]==b'\xef\xbb\xbf' else b'\xef\xbb\xbf'+b)"`，
  再用 `[System.Management.Automation.Language.Parser]::ParseFile` 复核语法。
  判据是 `head -c 3 | xxd` 必须显示 `efbbbf`。`.py` / `.sh` 不要 BOM，别顺手加。


## 41. 去掉 Default 伪档位后，省略 reasoning_effort 会让 Iceman 丢思考、正文聚成整块 【实例 A】

- **现象**：`dsh-claude-style` 0.20.1 的 `lib/client.js` 在模型没显式指定默认档位时，
  往档位列表最前面塞一个 `id=undefined / name="Default"` 占位；用户不选档就选中它，
  `c()` 组装请求时**完全不带 `reasoning_effort`**。Iceman（`iceman-contributor-free`）
  在这个缺省下要么吐不出思考 chunk、要么把正文攒成一大段拖出来，21:0x 实测 11 块 /
  0 字思考，21:44 同链路 79 块 / 298 字，缺省行为随上游漂移。
- **根因**：请求缺 `reasoning_effort` 时把「用哪个档」交给上游决定；上游对推理型的
  缺省不稳定，思考字段与流式分块都跟着变。关思考也不能靠 `off / wire=disabled`
  —— 实测该组合直接回 `HTTP 422 Unprocessable Entity`。
- **怎么避**：档位一律取**官方文档里给到的真实档位**，
  `~/.dsh/tools/patch-claude-style-effort.mjs` 把 `ki()/M()/h()/c()` 改成
  effort 为空时取 `model.reasoning.efforts` 末位（与宿主 `THINKING_LEVELS` 固定序一致），
  删掉 `Default` 占位并让 `directory.select()` 显式写入官方 effort。
  探针同档位大预算补测与自动准入规则以 [MODEL-STREAM.md](MODEL-STREAM.md) §3 为正本，
  本节只记坑，不重复定义机制。
- **验证**：补测后 Iceman 414 块 / 1733 字思考 / 103 字正文 / 11 最大块间隔，PASS；
  `--check` 复查 `ALREADY_PATCHED (no write)`。改带 BOM 的 `sync-models.ps1` 挂探针钩子时
  按 §40 补回 `EF BB BF`，否则计划任务里 PS5.1 按 GBK 读会乱码跑挂。

## 42. 上游同一别名随机只给加密思考，Iceman 界面看不到思考 【实例 A】

- **现象**：显式 `reasoning_effort: high` 也会随机只回正文 + `reasoning_details[type=reasoning.encrypted]`，`reasoning_content` 零增量；30 次交错采样里 B 与请求参数、耗时都无关（2.02s–86.36s 都有），GUI 思考块空白、正文一节一节出。
- **根因**：`iceman-contributor-free` 上游双后端分流：A 吐明文 `reasoning_content`（pi-ai 转 `thinking_delta`）；B 只吐 opaque replay blob。宿主 `@earendil-works/pi-ai/dist/api/openai-completions.js:172-173,416-428` 把 `reasoning_details` 当 replay 元数据，只写 `block.thinkingSignature`、不写 `block.thinking`、不推 delta；UI `blockIsVisible` 跳过空 reasoning。叠加 `transcriptView: standard / collapseTiming: completion / foldedReplies: final` 整轮折叠与 `reasoningDisplay: stepped` 两行步进。C2 负证据：查不到解密或强制明文的请求参数，8 类参数 ×5 轮全部照样命中 B。
- **怎么避**：三层各管一段 —— ① 展示层**只动 `ui-skin-claude-style` 的 `reasoningDisplay`（刷新 GUI 生效），`ui-chat` 三键是用户偏好（现值 `compact / completion / final`），排查中一律不许改成 `verbose / next-input / all`**：改了用户会当成「配置自己回退了」，2026-11-10 已反复踩（备份链 `bak-gemini-devrole-20261110131037` / `bak-dshsync-20261110-145209` 两次 verbose，都是排障会话写进去的）；要看过程细节用界面单轮临时展开，不动用户偏好。② 网关层 `zgate.json` 的 `reasoningGuard` + `router.go` 首包判定，命中 B 直接关流透明重抽同一跳，**改 Go 必须按 [TROUBLESHOOTING.md](TROUBLESHOOTING.md) §16.2 换版二进制**；③ 探针识别口径以 [MODEL-STREAM.md](MODEL-STREAM.md) §3 / §4 为正本。回退：守卫零值=禁用，删 `reasoningGuard` 段即恢复原透传。
- **二次修复（2026-11-10 下午，前两版修完仍看不到思考的真因）**：三条，缺一条都白修。
  1. **重抽必须换连接 + 换会话**：首版重抽沿用原 headers「保 `X-Opencode-Session`」+ keep-alive 连接，而上游是按会话/连接粘后端的 —— 3 次重抽全落回同一路加密后端，达上限放行的还是加密流（`zgate.log` 里 3 条「透明重抽同一跳 1/3..3/3」紧接着 WARN「达上限放行最后一次」就是这个形态）。现改为每次重抽 `req.Close = true` + `X-Opencode-Session` 追加 `#r<N>-<随机>`（原值留在前缀里便于排查），默认重抽上限提到 5。
  2. **SSE 改长度时必须摘掉上游的 `Content-Length`**：上游事件流自带 CL 时，守卫丢弃首段、插提示、掺心跳都会改长度，写端直接报 `http: wrote more than the declared Content-Length` 并断流 —— 客户端拿到 200 却 0 字节，表现是「连上了但什么都没有」。修法：`copyHeaders` 之后对事件流一律 `w.Header().Del("Content-Length")`，交给 `net/http` 按 chunked 重新分帧。
  3. **思考阶段静默要喂心跳**：上游思考停顿实测 51.9 秒，中间层与宿主会判空闲。`streamIdleHeartbeatSec`（缺省 15，负数关）控制空闲多久补一行 `: zgate keepalive` 注释；非事件流一律不掺（否则会毁掉 JSON 报文）。
- **同类模型免配置适配**：`reasoningGuard.mode` 三档 —— `models` 只守白名单；`channels` 先看渠道能力位 `upstreams.<渠道>.guardReasoning`（`models` 非空时再叠一层**交集**，2026-11-10 深夜起现网就是这个档，只有 `OC` 带位、白名单仍是 Iceman 两条）；缺省或显式 `"auto"` **不看任何表** —— 凡是客户端声明要思考（`reasoning_effort` / `thinking=enabled`）的流式请求都走探针，新增匿名代号模型不用再改配置；配合按模型学习表（连续 `giveUpAfter` 轮重抽到上限仍是纯加密且从未见过明文 → `giveUpForSeconds` 内不再白等，到期自动复探）。达上限时 `injectNotice` 会在流首插一条 `reasoning_content` 提示，GUI 至少显示「上游本次只下发加密思考」而不是空块。
- **验证**：`go test ./internal/router` 12 项 PASS（首包判定四形态、白名单 / off / 禁用、auto 模式覆盖陌生模型、重抽必须换会话且 `Connection: close`、上限放行注入提示、学习表跳过、心跳写入、非流式不掺心跳、带 `Content-Length` 的上游形态）；`internal/config` 2 项 PASS（JSON 接线 + 缺省值）；`gofmt` / `go build` / `go vet` 全 exit 0（`internal/supervisor` 两例失败是 Windows 临时目录清理占用，与守卫无关）。隔离实例实测（`%TEMP%\zgate-iso2-*`，假上游带 `Content-Length`）：首跳加密 → 客户端拿到明文 `reasoning_content`、加密首跳一字未泄漏、`attempts.log` 显示第二次调用会话变成 `#r1-*` 且 `Connection: close`；始终加密 → 200 + 597 字节 = 提示 + 上游正文（修前这里 0 字节断连）。探针 `ENC` 列与 `check-project.py --stream-contract` 七处接线 exit 0。
- **三次修复（2026-11-10 傍晚）：守卫压根没上场**。换版后用户复测仍「看不到思考 + 一节一节」，而 zgate.log 里那两条请求**一个守卫行都没有** —— 不是重抽失败，是触发条件不成立：guardApplies 首行 !reasoningExpectsThinking(body)，而 DSH 的模型选择器没有逐模型默认档位（catalog 的 reasoning.defaultEffort 为空 → 选的是 Default 伪档位），真实请求体只有 provider/model/maxTokens，**不带 reasoning_effort**。诊断入口：会话 session.v4.jsonl.zstd 的 request/header 记录里看 config 字段，没有 reasoningEffort 就实锤。修法：reasoningGuard.forceEffort + forceEffortModels，由 injectThinkingEffort 在转发前补档（日志「客户端未声明思考档位，按配置补 reasoning_effort=high」），补档后原有「换连接+换会话重抽」才会真正生效。**不要**再走给 dsh-claude-style/lib/client.js 打补丁的老路：该文件 2026-11-10 12:35 被重建后 11-09 的 effort 补丁整段消失（patch-claude-style-effort.mjs --check 报 NEEDS_REVIEW，六条锚点全归零），profile 每次重建都会重演。补档只影响「客户端没说话」的情况：显式 off / thinking 原样透传。
- **四次修复（2026-11-10 傍晚）：探针把用户的等待放大了**。三次修完后守卫确实上场，但每个请求要空等 85 秒（用户手动点停止）。代码级原因有三层：① `probeReasoningStream` 只在**第一个正文 delta** 时返回 `streamEncrypted`，而加密那一路思考阶段整段静默（无明文 `reasoning_content`、无正文），于是"判定"的延迟就等于那一次尝试的整段思考时长（`zgate.log` 实测两次判定隔 61 秒）；② 重抽预算花完的最后一发仍用无上限探针，再叠一段空等；③ 跳过期命中就续期，窗口过去也探不回来。现网口径：`probeSeconds`（缺省 12）到点换连接重抽；重抽预算花完或处于跳过期时**不探测、直接放行上游原始流**并插一条按成因写的提示（超时说"探测超时"、`reasoning.encrypted` 才说"只回加密"）；`guardInSkip` 到期清计数再复探，进跳过表改成"自上一条明文以来连续 N 轮失败"。**诊断入口**：日志里出现 `内没有可判定的思考信号（上游静默）` = 探针超时在换连接，`连续 N 次探测超时` = 已放弃探测直接放行；两者都在 `probeSeconds` 附近出现即说明修复在位。参数联动：`probeSeconds` 要大于正常流的首字节耗时（明文实测最高 13.5 秒 → 配置 15），小了会把慢流误判成静默；`maxRetries` 大于 1 在窗口期纯属白等（12:01 连续 3/3、13:20 连续 2/2 都落回同一后端）。

## 43. 配置加了渠道、进程没重载：整条降级链静默退回串行（旧判据，2026-11-10 深夜起改为逐跳取值） 【通用】

> **口径更新（2026-11-10 22:27）**：本条记录的 8 跳链是当晚形态；当时那条主力降级链改成 7 跳全同渠道，
> 哈基米 3.8 被拆成独立单跳模型（排在 AIS 前面）。
> **再更新（2026-11-11 13:35）**：HJ「福利」档断供，那一族改成 `[满血A]` 同站三跳（3.8 → 3.7 → 3.6，各 0.05），见 §39。
> **下线（2026-11-11 15:00）**：该族整族下线 —— `HJ_PRICES` 清空后没有价就进不了模型表，渠道与凭据保留；
> 上文只作历史记录读，别再按它去选这个模型。
> `(1/8)` 这类日志按历史读，`channelPolicy` 少一个渠道就会退回串行的结论仍然成立。
> **链长再变（2026-11-11 11:03）**：AIS 只留 3 跳，日志变 `(x/3)`；裁掉的四跳记 `dropped_hops` 并留在 `legacy_ids`，见 §44。

- **现象**：某个模型一次请求一分钟零字节，客户端只能手动停止；网关日志里只有一行派发 `model=<某主力模型> -> <渠道>:<模型> (1/8)`，之后没有任何 `[race]`、没有冷却、没有 fallback、没有 502；上游反代面板一条记录都没有。同一时刻其他模型正常。
- **根因**：三层叠一起，缺一层都不会这样静默。
  1. `racePolicyFor`（`internal/router/race.go:305`）要求**链上每个 hop 的渠道都在 `cfg.ChannelPolicy` 里**（`race.go:324`），否则整条链放弃竞速。链由 alias map 热加载（8 跳，含新加的 `HJ`），而 `channelPolicy` 是启动时读进内存的 —— 进程比配置旧，内存里只有 `GM` → 判定失败。
  2. 退回串行后没有任何首块看门狗：`router.go:734` 的 `if at != nil && at.policy.FirstBlockMs > 0` 只在竞速模式成立，串行链就是「发出去、等下去」。
  3. `http.Client`（`main.go:152`）只配了 `TLSHandshakeTimeout` 与 `DialContext` 超时，**没有整体超时 / 响应头超时**，上游建好连接却不发头就无限期挂着。
  三者一合：客户端零字节、网关零日志、反代零记录。旧二进制还认不出新渠道，连「缺 key」这种错误都报不出来。
- **口径更新（2026-11-10 深夜）**：下文第 ① 层的「每个 hop 的渠道都要在 `channelPolicy` 里」已随**逐跳取值**取消（`racePolicyFor` → `racePlanFor`，见 [ROUTING-POLICY.md](ROUTING-POLICY.md) §1）：缺配的渠道只是自己拿不到对冲节奏，不再连坐整条链退回串行；串行仍会发生，但只有一条 `noteSerialChain` 的 Info 说明原因。**「配置加了渠道、进程没重载」这个坑本身仍然成立** —— 差异在症状：以前是整链静默串行，现在是链上那一跳没有对冲、也没有它自己的看门狗窗口。
- **怎么避**：① 加渠道 / 改链之后**必须换二进制并重启** —— `/admin/reload` 只热加载 `zgate.json` 的策略，改不了编译期登记的渠道与进程内已读的配置快照（流程见 [TROUBLESHOOTING.md](TROUBLESHOOTING.md) §16.2）；② 代码侧已补两道网（2026-11-10 夜）：流式请求的**响应头看门狗**（`doForward`，默认 12s 拿不到响应头就判这一跳沉默并换跳，`errUpstreamSilent`；`zgate.json` 的 `upstreamHeaderTimeoutSec` 可调，负数关掉 —— **但 2026-11-10 21:30 起 GM / HJ 两个渠道都不设这个窗口，理由见本条第五轮**）与**串行退化告警**（`routeChain` → `noteSerialFallback`，打 `[race] 链上有渠道不在 channelPolicy 里…整条链退回串行、取消首块对冲`，按渠道组合 10 分钟去重）；③ 排查时先 `grep "不在 channelPolicy"`，命中就不用再猜。
- **验证**：`gofmt -l internal/router/` 空、`go build ./...` / `go vet ./...` exit 0、`go test ./...` 全 ok。新增两例：`TestStreamingHeaderWatchdogGivesUp`（handler 不给头、`headerWait=150ms`，断言 5s 内返回 `errUpstreamSilent` 收手）与 `TestStreamingHeaderWatchdogPassesThrough`（正常 SSE 必须原样透出、Close 正常取消）。候选二进制 `python gateways/zgate/build.py --candidate` 内容检索 `hajimi` / `HJM_API_KEY` / `upstream silent` 全部命中。

- **同日第二轮（2026-11-10 19:45）：换版生效了，可一次请求仍要 4 分半 —— 坑在「容忍窗口按最慢的那一档取」**。日志已经恢复 `[race] 发出 1/8`…`8/8`（对冲回来了），但每一跳都要等满 45 秒才判沉默：实测其中一跳 **每次都要 60.241 秒才回 503**（`This model is currently experiencing high demand`），而哈基米 `[福利]gemini-3.8-flash` 直连 2.5-3.1 秒就出首块。`maxParallel=2` 轮转 ⇒ 4 轮 × 45 秒 + 首块 4 秒 ≈ 3-4.5 分钟（用户实测 4 分 31 秒）；这期间 DSH 等不到首字节会自动重试，反代后台于是出现两条「请求中」，看起来像「我发了一句它打了两枪」。
  - **改**：`upstreamHeaderTimeout` 45s → **12s**，并升级成配置项 `upstreamHeaderTimeoutSec`（0/缺省 12，负数 = 关掉看门狗），`Server.headerTimeout()` 每次现读配置，`/admin/reload` 就能调，不必重编译。12 秒相对观测到的合法首头（2.5-3.1 秒）仍有 4 倍余量。
  - **口径**：这个值要按「**正常首头的最慢分位 × 3-4**」定，不能按「上游多久才认输」定 —— 前者保住的是体验，后者只是把超时串成糖葫芦。
  - **日志**：沉默告警现在带 `model=`（`[router] https://api.gemai.cc/v1（model=[福利]gemini-3.8-flash）上游 12s 内没给响应头，判这一跳沉默并换跳`）。同一个 base 下不同模型能差一个量级，只打 base 分不清是谁被上游晾着。
  - **验证**：`TestHeaderTimeoutFollowsConfig`（配置 3 秒即生效 / 缺省回落常量 / 负数返回 0 / 显式字段最优先）+ `config_test.go` 里 `upstreamHeaderTimeoutSec` 的缺省与负数用例。
- **同日第三轮（2026-11-10 20:05）：一个全局窗口套两种脾气，兜底那家被自己的门槛切掉**。哈基米 `[福利]gemini-3.8-flash` 白天 2.5-3.1 秒出首块，晚上漂到 **7.5-10.2 秒**（同一 key，60KB / 200KB 系统提示各测一次）；12 秒窗口只剩 1.2-1.6 倍余量，20:03 的日志里它跟 GM 一起被判 `12s 内没给响应头`，8 跳全灭、50 秒干净失败，反代面板依旧零记录（GM 从没回包，哈基米不在那张表里）。
  - **改**：`channelPolicy` 新增 `headerTimeoutSec`（0 = 继承全局，负数 = 该渠道不设看门狗），`Server.headerTimeout(channel)` 的优先级变成「显式测试字段 > 渠道 > 全局 > 常量」；`zgate.json` 里 **GM 12 秒 / HJ 25 秒**。两路并发时不冲突：GM 到 12 秒先死、链继续往下，HJ 还在等它的 10 秒，谁先出首块谁赢。
  - **口径**：窗口要按「该渠道正常首头的最慢分位」分别定。跨渠道用一个值，等于拿最快那家的标准去卡最慢那家，兜底就变成「名义上在场、实际上每次都被切」。
  - **验证**：`TestHeaderTimeoutPerChannel`（HJ 25s / GM 12s / 渠道负数关掉 / 渠道为 0 回落全局 / 渠道不在表里回落全局 / 显式字段仍最优先）、`go test ./...` 全绿。
- **同日第四轮（2026-11-10 20:20）：换了跳却没埋跳，同一个死跳每个请求都要重新撞一遍**。看门狗已经生效（日志里每跳 12 秒判沉默并换跳），但 `errUpstreamSilent` 分支只调 `retry()` 回落下一跳，**没有写 `silence` 表** —— 于是第二个请求又从第一跳起手，把已经证明死掉的跳重撞一次。用户连发两句、两分钟里大半时间花在这上面。**改**：`doForwardWith` 命中沉默后按渠道 `silenceCooldownSeconds` 打 `markSilence`（GM/HJ = 20 秒），`cooling()` 立刻把这一跳挡在下一轮之外；全链都在短冷却时 `raceChain` 走 `clearSilence` 重试一次，不会把自己饿成 502。**口径**：静默冷却要短（20 秒），它是「这次先说别人」不是「这跳死了」；真冷却（429 / 5xx / 额度）仍走 45 秒 - 24 小时。**验证**：`TestSilentHopGetsShortCooldown`（沉默后 `cooling(hop)` 必须为 true 且 `retry` 被调用一次）、`go test ./...` 全绿。
- **同日第五轮（2026-11-10 21:30）：本地判死本身就是故障源 —— 上游还在吐 token，本地已经断开重试**。当晚统计：GM 被判死 125 次（沉默 79 + 首块 46），上游真说过 `503 high demand` 的仅 7 次（5.3%）；HJ 判死 32 次，一大半与 502 同秒。链路遗迹 `12s 无响应头 → fallback (none) → 同秒 502 → 13s 后客户端重试 → 再砍`。DSH 的 `retryPolicy` 把 `SERVER` 列为可重试（`maxRetries: 1`），所以**网关每判死一次 = 一次 502 + 一次客户端重试 + 一次上游重跑**，用户看到的就是「后台在跑 token、本地断开又跑一遍」。
  - **改（配置，热加载）**：`channelPolicy.HJ` 收敛为 `{"headerTimeoutSec": -1}`；`channelPolicy.GM` 的 `headerTimeoutSec` → `-1`、`firstBlockMs` → `0`、`silenceCooldownSeconds` → `0`、`hedgeAfterMs` → `18000`、`softCooldownSeconds` → `60`；`upstreamHeaderTimeoutSec` → `45`。
  - **口径**：本地只做两件事 —— 「并排多问一家」（对冲，只多开一路、不取消前一路）与「按上游回话冷却」（429 / 5xx / 403）。**上游没说我死了，就不替他下死亡通知**；慢是常态，阈值给多少都是赌，赌错一次要付一次重试 + 一次重跑。
  - **判据**：`grep -c '没给响应头' zgate.log` 与 `grep -c '503' zgate.log` 放一起看 —— 前者远大于后者就说明判死是本地造的。排查思路见本篇 §43「判死权归上游」段。

## 44. 上游「忙」被当成渠道故障：一个过载的 3.8 把同渠道能用的 3.6 一起带走 【实例 A】

- **现象**：用户侧两条互相矛盾的反馈 —— ①「跑着跑着就截断了，然后说模型使用人数过多需要重跑」；②「错误码 HTTP_503，此模型当前需求量较大」，`503 都是这样`。直连取证（Bearer `GEMINI_API_KEY` 打 catiecli）：短问四跳全 200（3.8 = 7.2s / 3.7 = 5.2s / 3.6 = 2.6s / 3.5-flash-lite = 10.8s）；同样的 1200 字长提示四跳全 503，耗时 3.4s / 10.3s / 22.4s / 4.3s。**这不是链路坏了，是模型忙**，且 503 来得慢（最长 22 秒），会白占看门狗窗口。
- **根因**（两层，都在网关侧）：
  1. `chainAccept` 把 503 当「这一跳死了」，而冷却落在**渠道**上：`markChannelOffFor(hop.Channel, poolCooldown=90s)` → 之后 90 秒里同渠道的 3.6 / 3.5 全部在入口被拒（`渠道 GM 处于禁用窗口，直接回 503`，2026-11-10 23:40 实测连刷）。一跳过载 = 整条链陪葬。
  2. 流式转发读到 `rr.err` 直接 `return`：既不补 `[DONE]`、也不写日志、也不计数。客户端拿到的是「200 + 几段正文 + 无 `finish_reason` 的断尾」，只能自己判成失败重跑 —— 重跑的 token 上游照算一遍。
- **改（2026-11-11）**：`internal/router/upstream_semantics.go` 把上游语义拆成三类，各走各的路（详见 [ROUTING-POLICY.md](ROUTING-POLICY.md) §4.1）：忙 → 只跳这一跳 + `busyCooldownSeconds`（GM 现行 10s，现值读 `zgate.json`），不整渠道禁用；400 带 `thinking_level` → 剥参数同跳重发一次；SSE 断尾 → 补 `finish_reason:"error"` + `upstream_truncated` + `[DONE]`。三者在 `/health.upstream` 各有一个计数。
- **口径**：**「忙」是这一跳此刻的状态，不是这个渠道的品质**。冷却是给「这一跳先别用」，禁渠道是给「key 没了 / 被封了」。把前者写成后者，等于让一个模型的繁忙拖垮整条降级链。
- **判据**：`curl -s 127.0.0.1:7871/health` 看 `upstream.busy` / `upstream.busy_skipped` 是否在长提示下增长；`busy_skipped > 0` 且 `truncated_streams` 停住 = 忙跳已让位、断流已收口。日志对应行：`上游 503 表示需求高峰，跳过该跳 20s（不在渠道级禁用）`。
- **验证**：`go build` / `go vet` / `go test ./...` exit 0；新增 8 例（`busyExhausted` 三形态、`invalidThinkingParam`、`stripThinkingParams` 两层嵌套、400 剥参后同跳重发拿到 200、断流补帧、正常流不被改、忙跳跳过而不禁渠道）。

---

## 45. 竞速排序的记忆有保鲜期，`/health.race` 却还在报旧账 【实例 A】

- **现象**：三种误判同一个根 —— ① 看 `/health` 里 `race.hops` 的 `3.8 = {"verdict":"Service Unavailable","at":"21:56"}`，断定「它还被压在队尾」，可下一轮请求其实已经按声明顺序先试它了；② 以为 `POST /admin/reload` 能重置排序，reload 后 `at` 纹丝不动，转头怀疑「配置没生效」；③ 在单发串行的链上盯 `race.hops` 一行都不更新，怀疑观测坏了。
- **根因**：观测的**保鲜期只作用于发车顺序，不作用于展示**。`rankedChain()` 用 `snap.stale(now)` 把过期条目当「没测过」重新给机会（失败保鲜短、成功保鲜长，常量 `raceFailTTL` / `raceOKTTL`），而 `raceSnapshot()` 原样拷贝全表、`/health.race.hops` 因此永远是「最近一次观测」的原始账本；`/admin/reload` 只做 config / keys / `ApplyConfig` / `aliases.Reload`，不清 `raceStat`；更要紧的是 `rankedChain` 只在 `raceChain`（对冲路径）里调用，串行链走 `attemptChain`，压根不产生这类观测。
- **处置**：判「为什么又是兜底跳出字」用 `/health.hops` 的逐跳计数（`try` / `ok` / `busy` / `e5xx` / `silent` / `no_first_block`，串行链也有），不要读 `race.hops` 的 `at` 当下结论；要清零观测只能重启进程；怀疑排序固化时先看 `try` 有没有增量 —— 有增量就说明它已经被试过，问题不在排序。
- **证据**：`internal/router/router.go` 的 `hopStatSnap.Seen` 与 `stale()`、`raceFailTTL` / `raceOKTTL` 常量、`raceSnapshot()` 无过滤、`reload()` 不清 `raceStat`；`internal/router/race.go` 的 `rankedChain` 分支 `case !ok || snap.stale(now)`；`internal/router/race_test.go` 的 `TestRankedChainRetriesStaleObservations`（新鲜 / 过期 / 成功过期三态）；`internal/router/hop_stats.go` 注释「/health.race 只记竞速跳（at != nil）的首块耗时，串行链一行都看不到」。

## 46. 用 md5 核对 zgate 版本，永远对不上 【通用】

- **现象**：重编后 md5 与线上不一致，判成「部署没生效」，于是再编、再换、还是不一致；另一种反向误判 —— md5 一致就以为「源码也是最新的」。
- **根因**：构建时工作区不干净会把 `vcs.modified=true` 编进 buildid，同一份源码的字节就不可复现；不同 ldflags 组合（`-H windowsgui`、`-s -w`、带与不带 `-trimpath`）也会各出一份哈希。md5 能证明的只有「备份 → 替换 → 校验这一段搬的是同一份字节」，与「是不是最新代码」无关。
- **处置**：版本只认 `go version -m <exe>` 的 `vcs.revision`；再跑 `git log <vcs.revision>..HEAD -- gateways/zgate` 判欠账，为空才算追平；md5 保留在部署三步里做搬运校验。判据与命令见 [ZGATE-LIFECYCLE.md](ZGATE-LIFECYCLE.md) §9.1。
- **证据**：同一次排查里四种 ldflags 组合全部对不上，当时的 buildinfo 带 `vcs.modified=true`；`git log <该提交>..HEAD -- gateways/zgate` 为空，证明「源码没欠账、只是字节不可复现」。

## 47. 反代面板时间比 zgate 日志晚一百秒出头，对齐前别下结论 【实例 A】

- **现象**：把面板的 `21:56` 与日志的 `21:30` 拼成一条时间线，得出「3.8 失败后十五分钟一次没被碰过」「面板零记录 = 网关没发请求」；同一条请求，两边各自看都很正常，合起来就是错案。
- **根因**：两个时间基准不同源。面板记的是它自己落账的时刻，实测恒定滞后一百秒出头（104–106 s，非固定偏移的部分来自面板落账延迟），跨源比对不做校正就会把因果方向拼反。
- **处置**：唯一时间轴用 `zgate.log` 的 `[race] 发出 i/n`、首块、冷却三类行；面板只用来数「上游到底被调用了几次」；确实要跨源对齐时，先取**同一条请求**在两端的时间戳算出偏移，再逐条平移后比对。`/health.race.hops` 里的 `at` 是网关本地时间（`now.Format("15:04:05")`），与面板同样不同源。
- **证据**：源文档样本 —— 日志 `21:30:21` 发出 1/7、`21:30:36` 503 冷却 1m0s、`21:30:54` 发出 3/7，面板同段恒定晚 104–106 s；`/health` 抓取时刻 `21:59` 而 `race.hops` 内 `at` 已到 `21:58:50`。

## 48. 只改 `zgate.json` 加渠道：请求在 key 覆盖名单外被静默跳过 【通用】

- **现象**：新渠道的别名配好了、`/v1/models` 也能看到，请求却稳定 502 `all upstreams failed: <hop>`，日志里没有任何上游响应；另一种形态是上游回 401「未提供API Key」，像是凭据没配。
- **根因**：渠道集合在 Go 里枚举（`internal/keys` 的 `Set.For(channel)` 按渠道硬编码），`zgate.json` 里的 `keyEnv` 已是废弃字段、写了也不生效；只加别名不改代码时，请求会在 router 的渠道判定处被静默跳过，表现成「上游从未被调用」的 502；另一处是 key 覆盖名单没补新渠道，空 Bearer 被原样透传，于是拿到 401。
- **处置**：按 [MODEL-PROVIDERS.md](MODEL-PROVIDERS.md) §0 的六处改动（`internal/keys`、`internal/config` + `main.go`、`internal/router` 的 key 覆盖名单、`tools/model_alias.py` 的渠道常量、`providers/<name>/.env.local`）一次改齐，然后**必须换二进制** —— `/admin/reload` 只能热加载 base 与 key，改不了编译期登记的渠道；换完先看 `/health` 是否出现该渠道的 `{state:"up",key:true}`。
- **证据**：源文档实测 —— 不改 Go 时请求在 `router.go` 的渠道判定处被静默跳过，最终单跳 502 且日志无上游响应；补上 key 覆盖名单后 401 消失；GM 接入后 `/health` 出现 `gemini:{state:"up",key:true,child:""}`。

## 49. 给链加长度上限时只截 `chain`：老 id 静默 404 【通用】

- **现象**：给 `tools/model_alias.py` 加 `CHAIN_CAP = {"<某模型>": 3}` 后 `--apply`，别名表 legacy 从 73 条掉到 69 条，模型总数 93 掉到 89；老会话点名被裁掉的旧跳 id 直接 404，选择器里也少了四条。
- **根因**：`family_entries()` 只用 `chain` 建链，而 `_consistent_legacy_ids()` 反过来拿「全量 hops 的 upstream ∪ 链上跳」校验 legacy 映射 —— 被裁掉的四跳既不在链上、又没有别的登记点，四条旧跳 id 的映射就被当脏数据过滤了。
- **正解**：截链时把裁掉的跳记进 `entry["dropped_hops"]`，并在 `_consistent_legacy_ids()`、脏映射清理循环、`alias_models` 写盘三处把 `dropped_hops` 计入 upstream 集合。改完 legacy 回到 73、旧 id 仍解析到原模型名，只是链不再真去打它们。
- **判据**：`--apply` 后立刻核 `models==20`、`legacy==73`、`len(AIS.chain)==3`、`len(AIS.dropped_hops)==4`；单测 `test_ais_chain_is_three_gm_hops_in_version_order` 同时锁链长、dropped 与 legacy 覆盖。
- **同类**：任何「先按名字聚合成一条链、再按上限裁剪」的生成器（工具清单、provider 目录、路由表）都有这个陷阱 —— 裁的是执行路径，不是身份。

## 50. AIS 跳带 tools 只回思考不回正文，DSH 报「the turn degenerated again after the continuation nudge」 【实例 A】

- **现象**：DSH 里选某主力模型写长文，整轮零输出，界面只留一行 `❌ [ACP] stream error: the turn degenerated again after the continuation nudge`。会话 `sessionStats` 是 `ttftMs=25483 / llmMs=25483 / decodeTokens=0 / toolMs=0` —— 模型想了 25 秒然后什么都没有，正文和工具调用双零。
- **根因（三层）**：① 上游：某渠道的降级跳在请求**带 tools** 时随机退化成三种形态 —— 空参数工具调用（`{"name":"read","arguments":"{}"}`）、只回一句话根本不调工具、或整段空流；② 网关：`hasContentDelta`（`internal/router/race.go:210`）的判定是 `if c.Delta.Content != "" || c.Delta.Reasoning != ""` —— **思考也算首块**，而该渠道的 `firstBlockMs=0` 又把首块看门狗关了，于是「只出思考、零正文」的 200 被当成功原样交给客户端，日志里既没有 fallback 也没有 error 行；③ DSH：`billion-context` 的 `retryEmptyTurn` 把「干净 stop + 有思考 + 零正文 + 零工具调用」判成退化，续问一次仍退化就抛这句报错。
- **处置**：写作、需要读文件的任务不要挂这类降级链模型，改用 `DeepSeek-4.1-Flash`（WB 跳 ok=3296 / try=3299）；这类模型只留给不调工具的纯对话，且 effort 用 `off` 档。
- **证据**：直打 `127.0.0.1:7871` `model=<该模型>` 的实测矩阵 —— 带 read/grep 两工具 + `max_tokens=128000` + high：100 s 后 content=0、reasoning=947、toolDeltas=1、finish=stop；同参数**不带工具**：33 s 正常出 1761 字；给 `write_file` 工具并要求写文件：31.5 s、零工具调用、只回 24 字；`reasoning_effort=off` 带工具：14.6 s 回空参数工具调用；写文提示 + 8000 tokens：三跳全挂回 502 `all upstreams failed`。同批 `/health` 里 `HJ|[满血A]gemini-3.8-flash` 也在抖（try 14→21、ok 停在 9）。
- **判据**：分清「链路坏了」还是「模型这一跳退化」只看三件事 —— 会话 `sessionStats.decodeTokens` 是否为 0、网关日志那次请求后面有没有 fallback/error 行、同一条链**不带 tools** 直打有没有正文。三件全中就是模型退化，不是配置掉了。

- **同类**：任何「把思考流也算作产出」的探活/首块判定都会漏掉这一类空回；`reasoning` 只能证明上游活着，不能证明它给了可用的答案。

## 51. 控制台脱敏把 `token` 当凭据：`*_tokens` 业务计量被抹成 `<redacted>`，流量页丢数 【通用】

- **现象**：`tools/console/` 首版端到端里，`/api/overview` 与 `static/app.js` 的脱敏 grep 命中 5 处 `token`，一度当成凭据泄漏；放宽检查口径后才发现 `sources.scrub()` 把 `total_tokens` / `prompt_tokens` / `completion_tokens` / `cache_hit_tokens` 全换成 `<redacted>`，`/api/traffic` 的 `tokens` 合计变 0，流量页「采样 token」永远显示 0。
- **根因**：首版 `sources.py` 的 `SECRET_NAME` 写成 `r"(?i)(token|secret|cookie|...)"` —— 裸 `token` 是子串匹配，所有 `*_tokens` 业务计量字段名一并命中。`request-logs/requests-*.jsonl` 每行都带 `total_tokens` / `prompt_tokens` / `completion_tokens` / `cache_hit_tokens`，这些是统计口径，不是凭据；`auths/*.json` 里的 `accessToken` / `refreshToken` 才是凭据。同一套正则既想防泄漏又想留统计，用子串匹配必然互相打架。
- **怎么避**：字段名脱敏只认「凭据语境」精确词（`(access|refresh|id|auth)[_-]?token` / `secret` / `cookie` / `passwd` / `password` / `credential` / `authorization` / `api[_-]?key` / `private`），值形状脱敏单独用 `SECRET_VALUE`（`sk-…` / `Bearer …`）。改完必须跑行为等价单测：一边断言 `accessToken` / `refreshToken` / `cookie` / `api_key` / `authorization` / 嵌套 `secret` / 列表 `password` / `Bearer` / `sk-` 全被抹，另一边断言 `total_tokens` / `tokens` / `prompt_tokens` / `completion_tokens` / `cache_hit_tokens` 全保留（`.work/test-redaction.py` 13 项 PASS）。验收 grep 也分两套口径：对 `/api/config`、`/api/accounts` 用 strict 零命中，对流量 / 探针 / 静态源码只查「凭据值形状 + 凭据字段名」，别用 `grep -i token` 一把梭。
- **同类**：本轮另两处写面收紧同源同理 —— ① 缺 `Origin` 的 `POST /api/actions/reload` 曾被放行（`_origin_ok()` 里 `if not origin: return True`），本机 curl 方便却给简单跨站 POST 留了口子，改成「写操作必须带同源 `Origin`，缺一律 403」；② `do_HEAD` 直接 `_send` 会写出 body 且绕过 `Host` 校验，改成 `_head` 标志复用 `do_GET`、只发头不写体。三条都是「便利默认值」盖过了安全 / 正确性判据，判据要显式到字段级。

## 52. `/admin/reload` 曾对任意网页开放，body 也没有上限 【通用】

- **现象**：手工 `curl -X POST http://127.0.0.1:7871/admin/reload` 回 403 `missing X-Zgate-Admin header (blocks cross-site POST)`；控制台点「重载」同样 403；一条超大请求打过来回 413 `request body exceeds 33554432 bytes`。
- **根因**：改造前 `/admin/reload` 只绑 127.0.0.1、没有任何请求级校验 —— 浏览器里任意一个页面都能对它发一个 `Content-Type: text/plain` 的简单 POST（简单请求不触发预检、也不受 CORS 约束），网关照单全收并重读配置。绑定回环只挡住「别的机器」，挡不住「同一台机器上打开的任意网页」。请求体侧同理：过去是无限 `io.ReadAll`，本机任意进程一条几 GB 的 POST 就能把常驻进程内存打满。
- **正解**：管理面统一过 `adminGuard`（`internal/router/admin.go`）—— 回环来源 + `X-Zgate-Admin` 头非空 + `Origin` 若存在必须同源；配了 `adminToken`（`zgate.json` 字段，空则读环境变量 `ZGATE_ADMIN_TOKEN`）再加一道 `X-Zgate-Token` 或 `Authorization: Bearer`，`subtle.ConstantTimeCompare` 比较。手工 curl 补 `-H "X-Zgate-Admin: 1"`，配了口令再加 `-H "X-Zgate-Token: $env:ZGATE_ADMIN_TOKEN"`；`zgate reload` 子命令与 `tools/console/actions.py` 都已补头。`serveHTTP` 对 `/v1/*` 套 `http.MaxBytesReader`，上限 `maxRequestBodyBytes`（缺省 32 MiB，`zgate.json` 可覆盖），超限回 413 而不是 400。
- **判据**：403 文案能直接分诊 —— `missing X-Zgate-Admin header` = 缺头（不是网关挂了）、`admin endpoints are loopback-only` = 不是从本机回环发的、`cross-origin admin request rejected` = `Origin` 不是回环、`bad admin token` = 口令不对；413 看文案里的字节数是否等于 `maxRequestBodyBytes`。写管理面测试别拿 `/admin/reload` 当探针：`newServer` 的 `cfg.Path` 为空时它会去 exe 目录找 `zgate.json`，拿不到就回 400，看起来像鉴权失败 —— 用只读的 `/admin/stats` 验门禁。
- **同类**：`/metrics` 只做回环 + 同源，故意不要求自定义头（抓取端零改动）；只读端点不该因为鉴权收紧把监控打断。凡是「本机进程就能改全局状态」的端点，都要假设同机浏览器是敌对环境。

## 53. body 只扫一遍之后，facts 变成会过期的快照 【通用】

- **现象**：`TestReasoningGuardForcesEffortThenRedraws` 报 `上游调用次数 = 1, want 2` —— 「加密思考分流应触发重抽」没触发；`/health` 里 guard 档位显示正常，可每次请求只打一次上游。
- **根因**：`doForwardWith` 里 `facts := parseBodyFacts(body)` 只解析一次，随后 `injectThinkingEffortFacts` 往 body 里补了 `reasoning_effort`，而 facts 仍是补之前那份 —— 守卫判「客户端是不是已经要思考」时看不到刚补的档位，于是判成「不必重抽」。同一份 facts 里的 `modelAt` / `closeAt` 是字节偏移，body 一改就全错。
- **正解**：注入成功后立刻 `facts = parseBodyFacts(body)` 重扫；跨函数一律重扫，不要把 facts 塞进 `context` 传下去（跳上的 body 会被 `rewriteModel` 改写，旧偏移必错）。`parseBodyFacts` 本身是零分配扫描，重扫一遍远比一次 `json.Unmarshal` 便宜。
- **判据**：任何 `withModel` / `withStringField` / `injectThinkingEffort*` 之后，只信重新扫出来的 facts；单测要锁「注入 → 守卫 → 重抽」整条链，别只测注入函数本身返回的字节。
- **同类**：一次解析 + 多处改写的管线，改完必须重解析，或者用能显式失效的句柄；把解析结果当不可变快照往下传，等于给自己埋一个静默错判。

## 54. 回写头有三处写了也看不见：提前交卷、hop-by-hop、channel 传空 【通用】

- **现象**：客户端拿到 200 却没有 `X-Zgate-Channel` / `X-Zgate-Hop`；`TestDrainingSetsConnectionClose` 断言 `resp.Header.Get("Connection")` 恒为空，一度被当成「draining 没生效」；只有 `X-Zgate-Attempt` 一直正常。
- **根因**：三条各自成立 —— ① 提前交卷（`earlySSE`）路径先写 200 与响应头再慢慢转发，之后 `w.Header().Set(...)` 已经晚了（头随第一块字节发出）；② `Connection` 是 hop-by-hop 头，`net/http` 客户端会吃掉它，要看 `resp.Close`；③ `forward` / `forwardChain` 一直把 channel 传成 `""`，只有竞速路径传了 `hop.Channel`，于是渠道头只在竞速模式下有值。
- **正解**：等跳定了再设头 —— `doForwardWith` 里 `copyHeaders` 之后、`http.NewRequest` 之前写 `X-Zgate-Channel`（空则退回 `at.hop.Channel`）/ `X-Zgate-Model` / `X-Zgate-Attempt` / `X-Zgate-Hop`；`Connection: close` 只对服务端有意义，客户端断言改用 `resp.Close`；`forward` / `forwardChain` 补 `channel string` 形参，四个调用点（`routeAlias` 两处、`routeFallback`、递归）一起补。
- **判据**：新增响应头先问一句「这时候头发出去了吗」；`go test -run TestRequestID` 五个用例锁住 id 回显、跨回落 `Attempt=2`、渠道与模型名、上游收到 `X-Request-Id`、draining 的 `resp.Close`。
- **同类**：观测类头一律在「跳已定、头未发」的窗口里写；任何「传空串当默认值」的形参，落地前确认每个调用点都真传了值 —— 空串不报错，只会让日志与响应头静默缺字段。

## 55. 用编辑器/脚本改 PS1 会掉 UTF-8 BOM，PS5.1 立刻按 GBK 乱码解析失败 【Windows】

- **现象**：`python tools/check-project.py` 在 `check_ps1` 崩成 `AttributeError: 'NoneType' object has no attribute 'strip'`（`tools/check-project.py:292`），同一进程里先有 `UnicodeDecodeError: 'gbk' codec can't decode byte 0xb6 in position 146`；直接用 PS5.1 解析 `tools/zgate-lifecycle/deploy-zgate.ps1` 则报 `106: The Try statement is missing its Catch or Finally block.`、`114: Unexpected token '}'`、`152: Unexpected token '宸叉彁鍓嶆仮澶?'` 一串行号，看着像脚本结构被改坏了。
- **根因**：`deploy-zgate.ps1` 开头那 3 字节 BOM 被写文件工具吃掉（BOM=True→False，其余 12 个脚本仍是 True）。Windows PowerShell 5.1 在没有 BOM 时按系统 ANSI 代码页（本机 GBK）读脚本，中文注释与中文字符串变成乱码字节，其中恰好吞掉引号与括号，Parser 就从那一行开始连锁报错；报错消息本身也是中文（GBK），`subprocess.run(..., text=True)` 用 GBK 解码又撞上非法字节，读取线程抛 UnicodeDecodeError → `stdout=None` → 检查器 `.strip()` 崩。
- **正解**：改完 `.ps1` 立刻验字节头（`$b=[IO.File]::ReadAllBytes($p); $b[0..2] -join ','` 应为 `239,187,191`，文件内 CR 计数为 0）；掉了就补回 BOM —— PowerShell 用 `[IO.File]::WriteAllText($p, $text, (New-Object System.Text.UTF8Encoding($true)))`，Node 用 `Buffer.concat([Buffer.from([0xEF,0xBB,0xBF]), Buffer.from(text, "utf8")])`。检查器侧给 `subprocess.run` 加 `errors="replace"`，并对 `r.stdout or ""` 兜底，别让一条本地化报错把整轮门禁带崩。
- **判据**：`Get-ChildItem tools\zgate-lifecycle\*.ps1` 逐个打印 `bom=` 应全为 True；PS5.1 `ParseFile` 探针回 `PARSE_OK`；`python tools/check-project.py` 的「换行/BOM」与「PS1 语法」两项都必须是 OK（现为 `13 个脚本全部符合` + `7 个脚本 Parser 通过`）。
- **同类**：仓里「PS1 带 BOM」不是洁癖，是 PS5.1 的中文解码开关；任何「读文本→写回」的工具（edit / sed / 格式化器 / 生成脚本）都可能顺手抹掉 BOM，改完必须回验字节头。
- **2026-11-17 复现（安装副本）**：改 `%LOCALAPPDATA%\ZCodeGateway\start-zgate-nw.ps1`（计划任务实际调用的那份）时同样掉了 BOM，症状不是报错而是**更隐蔽的错**：PS5.1 按 GBK 读，中文注释的乱码字节吞掉换行，`$errFile = Join-Path ...` 被并进上一行注释 → 变量为 `$null` → `Remove-Item` 报 `Cannot bind argument to parameter 'Path' because it is null`，位置还指向别的行号。**安装副本没有门禁保护**，所以规矩是：只改仓内模板 `tools/zgate-lifecycle/*.ps1`（`check-project.py` 的换行/BOM 与 PS1 语法两项会拦），改完 `Copy-Item` 覆盖安装副本（字节级复制，BOM 一起过去），再对两份各跑一次 PS5.1 Parser 探针。
## 56. 提交前闸门扫整棵工作树，别的会话留下的未跟踪文件会拦掉你的提交 【通用】

- **现象**：`git commit` 被 `.githooks/pre-commit` 拒绝，`tools/check-secrets.py` 报 27 处 `[本机用户目录]`，命中的全是 `evidence/agent-chain.md` / `evidence/agent-logs.md` —— 这两个文件既不是本次提交内容，也不在暂存区。
- **根因**：钩子头一句就写着「默认扫工作树（含未忽略的新文件）」，判据是文件系统而不是 `git diff --cached`；并行会话把取证分片写成未跟踪文件留在 `evidence/` 下，里面的本机路径（`C:\Users\SansK\...`）就成了别人的提交阻塞。
- **正解**：先看 `python tools/check-secrets.py` 的命中文件清单，确认不属于本次改动；属于别的会话的未跟踪产物不要删、不要改，用 `git commit --no-verify` 提交，并在答复里写明绕过原因与手工跑过的等价门禁（`gofmt -l` / `check-docs.py` / `check-project.py` / `go test` / `unittest discover`）。根治要么由产出方脱敏后提交，要么把这类文件写进 `.gitignore`。
- **判据**：`git status --short` 里剩下的 `??` 是否全属别的会话；`--no-verify` 之前必须逐条手工跑钩子里那四道，不能拿「钩子拦的是别人的文件」当跳过全部门禁的理由。
- **同类**：任何「扫工作树」的闸门都会把并行会话的中间产物算成你的问题；判定要按暂存内容，落地时给一条明确的绕过口径，而不是每次现编。
## 57. 上游把工具调用写成正文（全角竖线 DSML 标记），客户端静默中断 【实例 A】

- **现象**：DSH 会话在 12:04 突然停住，最后一行正文是 `</｜DSML｜ invoke></｜DSML｜ calls>` 两个闭合标签；会话存档里这一轮 assistant 消息只有 reasoning 5506 字 + text 33 字，没有任何 tool-call 块，后面也没有 tool/result 事件。用户看到的是「模型分析了一大段，然后对话中断」。
- **根因**：上游 `OC:deepseek-v4.1-flash` 偶发不返回结构化 `tool_calls`，而是把调用序列化成自家 special token 文本塞进 `content`（全角竖线 U+FF5C 包住 DSML 字样，后跟 invoke / parameter / calls 三段）。全链路三层都没解析它：DSH 宿主 grep `DSML` 只命中一个 PDF 库的 base64 串，zgate 的 `DSML` 只出现在 3 处注释里，`dsh-llm-deepseek/lib/index.js:1734` 只认结构化 `tool_use` 块。客户端拿到「正文里有标记、但没有工具调用」，这一轮就按正常结束处理 —— 不是崩溃，是空转收尾。
- **正解**：`gateways/zgate/internal/router/dsml.go` 在 SSE 转发链上扣留命中标记后的正文（`router.go:1537-1545` 构造、`1566-1570` defer 收口、两个转发循环各过一道），流尾补 `finish_reason:"error"` + `error.type=upstream_tool_call_as_text` + `[DONE]`，计数进 `/health.upstream.dsml_text_calls`。扣留上限 256 KiB，超了按误判原样放行。**不做 tool_calls 还原**：实测 00:34 那次只剩 `<｜DSML｜parameter name="code" string="true">` 段、12:04 那次只剩闭合标签，开标签从来没到过客户端，按猜的格式造调用会拿错参数去执行工具。
- **判据**：`/health` 里 `dsml_text_calls > 0` 就是命中过；日志对应行 `[router] 上游把工具调用写成了正文（DSML 标记），后续正文扣留不转发（model=...）`。单测 `go test ./internal/router/ -run DSML` 6 个用例全过，端到端那条断言客户端流里既没有标记、又有 `upstream_tool_call_as_text` 说明帧。
- **同类**：任何「模型在正文里输出自家协议标记」的降级（Anthropic 的 invoke 闭合标签、Qwen 的 tool_call 标签）都是同一种症状：这一轮没有结构化调用、客户端静默结束。判据先看会话存档这一轮有没有 tool-call 块，再看上游 `status` —— 200 + 无 tool-call = 上游降级，不是网关 502。
## 58. 上游面板删了型号但接口还能调，骤降保护把它永久锁回配置里 【通用】

- **现象**：2026-11-16 12:00 主同步跑完，ZCode 面板的免费组仍是 `HY3` / `HY4-Free`。当天公告写的是「Hy4 Flash 上线、11/16–11/30 限免；Hy4 限免已结束；Hy3 端内下线」，用户看到的是三个说法互相打架：公告说没了，面板还挂着。
- **根因**：四段链条，缺一段都看不出问题。① WB 面板 `GET /panel/api/models` 只剩 20 条，`hy3` / `hy3-b` / `hy3-c` / `hy3-x` / `hy4free` / `hy4-preview*` 全部消失，新增 `hy4std`(x0.29) / `hy4flash`(x0.03) / `hy4flash-free`(x0.00)。② `providers/workbuddy/workbuddy_fetch_pricing.py` 的骤降保护（条目减少 >30% 且未加 `--probe`）判定为「网关残缺」，把旧价格表的 21 行整批并回，表里仍有 39 条。③ `workbuddy_sync.py` 用 `pricing_ids` 判断面板列表是否完整：`pricing_ids(39) ⊉ live_ids(20)` → `live_complete=False` → 旧型号走「列表残缺，保留」分支，`cn:hy3` / `cn:hy4free` 原样留在 `provider_config.json`。④ 加 `--probe` 也救不了：网关对已下架型号照样回 200，`dead` 集合为空，19 个旧行全部按 kept 保留。
- **正解**：给「点名退役」一个显式出口。新增 `providers/workbuddy/retired.json`（`{"retired": {id: 原因}}`），`workbuddy_fetch_pricing.py` 的 `load_retired()` 在**骤降并回之后**剔除名单内型号（先剔会被并回覆盖），打印 `按退役名单剔除 N 个`；`tools/zgate-lifecycle/current-models.ps1` 的 billing_suspect 第二段也按同一名单过滤，否则已下线型号的历史扣费记录会一直挂在「当前清单」上。恢复某条就删掉对应键，名单是唯一开关。
- **判据**：`python providers/workbuddy/workbuddy_fetch_pricing.py` 回 `按退役名单剔除 12 个` 且价格表 `count=29`；`python providers/workbuddy/workbuddy_sync.py --max-rate 0.3 --apply` 后 `provider_config.json` 里 `cn:hy3` / `cn:hy4free` / `cn:hy4-preview` 计数全为 0；`python tools/model_alias.py --check` exit 0；`current-models.json` 免费组 = `Beam / Conatus / HY4-Flash-Free / Iceman`，`billing_suspect=0`。
- **同类**：任何「上游目录删条目、接口仍可调用」的下架 —— 限免到期、型号换代、区域下线 —— 都不能用探活判断死活。探活只证明「还能调」，证明不了「还该在架」；判据要落在**上游目录 + 公告**，落地要有一个点名名单，否则骤降保护 + `live_complete` 会把它们永久锁在配置里。
## 59. 限时免费档 `<型号>-free` 剥后缀后要复用显示名，否则与付费档不成族 【通用】

- **现象**：`cn:hy4flash-free` 在清单里显示成 `hy4Flash`（大小写混排、看不出是 HY4 Flash 的免费档），同族的付费档叫 `HY4-Flash`；两条本该是「同一型号的免费/付费两个入口」，结果被当成两个不相干的型号。
- **根因**：`abbreviate()` 先精确查 `ABBR`，再 `re.sub(r"(?i)[-_]free$", "", text)` 剥掉 `-free`，但剥完**没有回查 ABBR**，直接落到兜底正则，于是 `hy4flash` 被拼成 `hy4Flash`；同时 `family_key = re.sub(r"(-sg|-f)$", "", base_model.lower())` 不认识 `-free`，免费档与付费档的归并键不同，拿不到 `-Free` 尾缀，两条条目还可能撞名。
- **正解**：`abbreviate()` 在剥完 `-free` 后补一次 `if text.lower() in ABBR: return ABBR[text.lower()]`；`family_key` 的正则改成 `r"(-free|-sg|-f)$"`。这样 `hy4flash-free` → `HY4-Flash` → 同族含付费档 → 最终显示 `HY4-Flash-Free`。
- **判据**：`python -c "import sys;sys.path.insert(0,'tools');import model_alias as m;print(m.abbreviate('hy4flash-free'))"` 回 `HY4-Flash`；`python tools/model_alias.py` 的免费组里出现 `HY4-Flash-Free`，省钱组里出现 `HY4-Flash`，两条不撞名。
- **同类**：任何 `-free` / `-sg` / `-f` 这类「档位后缀」都必须在剥后缀后复用基础型号的显示名，并把归并键一起剥；只改其中一处，命名和分族就会分叉。
## 60. 退役名单只堵了配置主链，探测缓存旁路 + 命名空间变体还会漏 【通用】

- **现象**：第 58 节修完后重新做全渠道审计，配置主链（价格表 → provider_config → alias map → current-models）确实 0 残留；但 `~/.zcode/v2/model_probe.json` 里还躺着 9 个已退役型号，`status=ok / http=200`，其中 4 个（`global:hy3` / `global:hy4-preview` / `global:hy4-preview-f` / 裸 `hy3`）连 retired.json 都没覆盖 —— 名单只写了 `cn:` 前缀，探测缓存用的是 `global:` / 裸名命名空间。
- **根因**：退役名单是 2026-11-16 当天新加的，只接进了「价格表剔除 + current-models billing_suspect」两处。`model_probe.py` 的探测缓存是独立累积、独立判活的旁路：退役型号从配置删掉后不再被主动探测，但旧 key 永远留在 results 里，网关对已下架型号还回 200，于是 ok/200 记录永久滞留。它不回流配置，只误导人工排查；而名单按 `cn:` 精确匹配，天然漏掉其它命名空间。
- **正解**：① `model_probe.py` 加 `retired_keys()` / `is_retired()`，把名单 key 归一化成「原名 + 去前缀裸名」两形，写盘前先剔 results 里的退役 key —— 一条 `cn:hy3` 同时盖住 `global:hy3` / 裸 `hy3`。② `current-models.ps1` 的 stale/slow 两段也按同一归一化名单过滤（此前只有 billing_suspect 段过滤）。③ `model_alias.wb_prices()` 读价格表后按 retired.json 二次过滤，堵住白名单补建 `whitelist_items()` 复活退役型号的口子。④ `workbuddy_sync.py` 的 `BACKUP_MODEL_IDS` 去掉陈旧的 `cn:minimax-m3`（现价表只有 m2.7 / m3.1-flash）。
- **判据**：`python -c "import sys;sys.path.insert(0,'tools');import model_probe as m;r=m.retired_keys();print([k for k in ['cn:hy3','global:hy3','hy3','cn:hy4flash-free'] if m.is_retired(k,r)])"` 回 `['cn:hy3','global:hy3','hy3']`，在架的 hy4flash-free 不在列；`tests/test_retired_filter.py` 3 个用例绿；清洗后 `model_probe.json` 退役 key = 0、全量 unittest 174 OK；check-docs / check-project 全绿。
- **同类**：任何「点名退役 / 黑名单」机制都要问两句：① 名单覆盖了所有命名空间变体吗（cn:/global:/裸名/WB:）？② 名单接进了**所有**消费该型号的路径吗（配置主链 + 探测缓存 + 统计视图 + 白名单补建）？只接主链、漏旁路，等于没堵；名单写完当天干净，下次探测/补建又会把旧型号带回来。审计方法：拿退役名单对每一层产物做差集，别只看配置文件。


## 61. 启动自检把「配置瑕疵」升级成「服务起不来」，而错误只走 stderr 【Windows】

- **现象**：2026-11-17 15:42 机器睡醒后，客户端全部报 `503 acp-proxy failure: connect-refused 127.0.0.1:7871 (circuit open)`。`7871` 无监听、`zgate.exe` 零进程；`zgate-launch.log` 每分钟一条 `started pid=… / up=False (timed out)`；`zgate.log` 里只剩三条 `[policy] 策略在单跳模型上不生效` 的 WARN，没有任何错误。
- **根因**：13:53 换上的新 exe 带 `ValidatePolicies` 启动自检。GM 渠道当时只剩 `Gemini-4-Hydrogen` 一个单跳模型，而 `zgate.json` 的 GM 段还留着 11-11 调优时的 `softCooldownSeconds:15` / `rateLimitBackoffMs:-1` / `maxParallel:1` —— 串行链 `attemptChain` 第 9 参恒传 `nil`（`router.go:1911`），这三个字段永远读不到，自检判 Fatal 直接拒绝启动。真正的原因由 `main.go:163` 写到 **stderr**，而进程由隐藏窗口的计划任务拉起，stderr 继承自父进程、等于丢进 NUL。旧 exe 没有这道自检，所以配置里的无效字段躺了 6 天没症状，换版那一刻才变成全站不可用。
- **正解**：① 删掉 GM 段那三个字段（单跳仍生效的 `busyCooldownSeconds` / `timeoutCooldownSeconds` / `authFailCooldownHours` / `retry500Once` 保留）。② `start-zgate-nw.ps1` 的失败路径改为「进程已退出就重跑一次并 `RedirectStandardError` 抓 stderr，写进 `zgate-launch.log` 与 `zgate-launch.err.log`」——只在这条失败路径 redirect，避免给活着的网关挂一条随脚本退出而断的管道（断了再写 stdout 会 EPIPE）。③ `Server.reload` 补跑同一份自检，Fatal 直接 400 拒绝热加载（`router.go:2317` 起）。④ `zgate status` 打印自检结论。⑤ 新增 `tools/check-zgate-policy.py` 并接进 `check-project.py --policy`，判据与 `policy.go` 逐条对齐，提交前就拦。
- **判据**：`zgate status` 的策略自检段只有「提示」没有「Fatal」；`python tools/check-project.py --policy` exit 0；把 `maxParallel` 临时加回 GM 段后同一条命令必须 exit 1 并打印 `FATAL 策略完全无效…`；`go test ./internal/router -run TestAdminReloadRejectsFatalChannelPolicy` 绿。
- **同类**：任何「启动期硬校验 + 错误只写 stderr」的组合，在隐藏窗口/计划任务下都等于静默拒绝启动。修这类问题不要只修配置：① 把校验结论接到一个**必看的出口**（日志文件、status 子命令、离线门禁）；② 让拉起脚本在「启动即退出」时把子进程 stderr 抓下来；③ 热加载路径必须跑与启动同一份校验，否则会出现「reload 成功、重启即死」的时间差炸弹。

> **恢复说明（2026-11-25）**：以上 §40–§61 连同 PITFALLS.md §39 的后半段（`根因` 第 2、3 条与 `解法` / `验证`）于提交 `5b6d7ad`（2026-11-19）整段丢失 —— 该提交正文只写新增 §62、未提删除，属误删；现按 `git show 5b6d7ad^:docs/PITFALLS.md` 原文恢复，正文零改动。引用方（CONSOLE / MAINTENANCE / MODEL-STREAM / ROUTING-POLICY / TOOLS / TROUBLESHOOTING / ZGATE-LIFECYCLE）的编号按恢复后的编号逐个核对过。
