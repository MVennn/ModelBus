# 反代 / 模型提供商之间的适配性评估（子代理分片）

> 状态：终稿（已并入 lead 三批交叉实证；初稿 v1 曾先行落盘）
> 真实项目根：F:/Project/ModelBus，git 分支 main（junction 视图 F:/Project/_merged/DeepseekHarness 不是项目身份）
> 只读声明：本轮未修改任何源码/配置/文档/测试；未执行 --apply；未写 provider_config.json / cordis.patch.yml；未重启或停止任何网关进程；未打印任何凭据真值（只列变量名与结构/布尔值/字节数）；未做 git add/commit/push。唯一写入文件是本分片 evidence/agent-adaptation.md。
> 取证方式：codegraph_status 显示索引未初始化（且指向 junction 视图），按约定不自行 init，改用 grep / read / 运行态只读探测；文档自述仅用于标记冲突，结论一律以源码与运行态为准。
> 凭据真值：一律不落盘。下文所有 key 位置均为变量名、布尔值或文件字节数。
> 结论口径修正：初稿硬结论 3 曾写「/v1/messages 对 QD/WB/QW/QN 前缀与桥接目标直接 400」，经 lead 运行态 A/B/C 实测 + 本分片源码复核，该判据过宽，终稿已收紧为「统一入口不等于统一协议」（见 §1 结论 3 与 §2.5）。

## 0. 结论表（六上游，含运行态覆盖）

| 上游 | 协议形态（源码/运行态） | 适配点 | 已处理 | 未处理或风险 |
|---|---|---|---|---|
| OC（OpenCode-Go） | base https://opencode.ai/zen/go/v1；同域 chat / messages / responses 三协议；alias 链里可同时出现「直连」与「机场孪生」两跳 | 原生 chat 直转 + 协议桥（messages/responses 过 bridge）；鉴权头改写；地区 403 出口切换；逐跳回落与冷却；/v1/models 单家目录透传 | Bearer + opencode-cli/1.0 UA + X-Opencode-Session（F:/Project/ModelBus/gateways/zgate/internal/router/router.go:479-484）；模型 id 重写（router.go:1017-1031）；path/query 拼接（router.go:517）；hop.proxy 经 context 选 Transport（F:/Project/ModelBus/gateways/zgate/internal/router/egress.go:53-70）；RegionError 直连冷却 30min 且孪生跳另键（router.go:89、800-805）。运行态：GET /v1/models 与 /models 逐字节相同、HTTP 200、bytes=35541、data_len=30、首 id=deepseek-v4.1-flash（§9-H）；beam-free 走 (2/2) 孪生跳后直连「冷却中，跳过」（§9-K） | /v1/models 是 OC 单家 catalog 透传，不是 6 家聚合视图（router.go 全文件 grep /models\|v1/models\|catalog\|listModels 命中 0，§9-I）；未见 thinking 参数请求侧生成；未见各家错误码映射表；图片/多模态未见适配；裸 OC id 直发 /v1/messages 会原样透传到 OC 并拿到 401（§9-J 请求 B） |
| WB（WorkBuddy） | base http://127.0.0.1:7863/v1，本地子进程 wb2api.exe:7863，OpenAI chat 兼容 | ondemand 拉起 / 空闲回收；cn:/global: 前缀兜底；fallbacks 链内多模型回落；SSE 透传 | forwardHeaders 统一 Bearer（router.go:475-478）；prepare(child)（router.go:443-455）；forwardChain 按 chainAccept 回落（router.go:493-512）；children 配置（F:/Project/ModelBus/gateways/zgate/zgate.json:20-30）；doForwardWith 32KB 分块 Flush（router.go:604-626）。运行态：HY4-Free (1/1) POST /v1/chat/completions stream=true → HTTP 200、ct=text/event-stream、bytes=1409、首包 ": heartbeat" + chat.completion.chunk（§9-J 请求 C，本分片独立复现） | 子进程未就绪只 skip 本跳、不重试（router.go:705-708）；未见 WB 私有错误码（池冷却 400）单独映射，靠 hopFatal/chainAccept 的 marker 兜底 |
| QD（Qoder） | base http://127.0.0.1:8790/v1，本地 python 子进程 qoder_proxy.py:8790，OpenAI chat 兼容；qoder_proxy 自身也接 /messages 原生 Anthropic 报文 | qoder: 前缀去掉后重写 model（router.go:365-369）；统一入口的 /v1/messages 可按 model 命中透传 | 统一 Bearer、child 守护（zgate.json:31-41）；运行态：POST /v1/messages model=Qwen-3.8-Max（alias 统一名、不带前缀）→ HTTP 200、ct=application/json; charset=utf-8、bytes=338、首包 {"id": "msg_...", "type": "message", "role": "assistant", "model": "Qwen3.8-Max", "content": [], "stop_reason": "max_tokens", ...}；zgate.log "POST /messages model=Qwen-3.8-Max -> QD:Qwen3.8-Max (1/1)"（§9-J 请求 A + lead 回喂，本分片独立复现同形态）；说明 alias map 该条目 t.protocol=chat、hop.protocol=chat，故 routeChain 不拦（router.go:671-683） | 「带渠道前缀的裸 model + 非 chat 路径」才 400（窄条件，§2.5）；未见 QD 面板/签名层差异适配（zgate 只做透传）；未见多模态；原生 /v1/messages 由 qoder_proxy 自己接，不是 zgate 做的协议转换 |
| QW（千问） | base https://maas.qianwenaiapi.com/apps/anthropic/v1，只提供 Anthropic Messages（F:/Project/ModelBus/gateways/zgate/internal/config/config.go:164-165 注释 + F:/Project/ModelBus/gateways/zgate/internal/bridge/bridge.go:90 固定拼 /messages） | chat→Anthropic Messages 桥；x-api-key + anthropic-version 2023-06-01（bridge.go:83-89）；max_tokens 夹到 65536（bridge.go:809-825）；SSE 逐 delta 转 chat chunk（bridge.go:199-295） | 请求侧 system/tools/tool_result/tool_use/tool_choice（bridge.go:722-861）；响应侧 text/thinking/tool_use（bridge.go:971-1027）；流式 thinking_delta→reasoning_content（bridge.go:444-449）；额度耗尽 24h 冷却（router.go:74-78、828-862）。运行态：无主 channel，仅 DeepSeek-4.1-Flash 链里 1 跳 QW/messages（§9-G 统计），本轮未单独触发（lead 回喂） | 请求侧未见 thinking 参数生成（未见适配）；非文本 content part 被 textOf 丢弃（bridge.go:641-661）；错误码按子串 marker 判，未见 QW 私有码表；文档仍写「上游非流式」与现码冲突（§7） |
| QN（七牛） | base https://api.qnaigc.com/v1，同样只认 Anthropic Messages（config.go:185-186、router.go:396-420） | qn: 前缀去掉后走 Protocol:"messages" 桥（router.go:405-419）；桥接静默超时 504 + 5min 冷却（bridge.go:31-44、router.go:177-185）；429 退避 700ms 就地重试 | 同 QW 桥接能力；idleReader 看门狗（bridge.go:297-366）。运行态：POST /v1/chat/completions model=Conatus → HTTP 429、ct=application/json、bytes=164、首包 {"error":{"message":"bridge upstream error: Too many requests for this free model ...","type":"upstream_error"}}；zgate.log "POST /chat/completions model=Conatus -> QN:qiniu/conatus-free [messages] (1/1)" → "[router] QN\|qiniu/conatus-free\| 429，退避 700ms 后重试同一跳"（lead 回喂） | **latent gap（条件触发，非现行故障）**：router.go:474-485 的 switch 只有 WB/QD/QW/CP/OC，QN 不在内；当前 alias map 全 22 组里 QN 跳总数=1（Conatus，channel=QN、protocol=messages、base=https://api.qnaigc.com/v1、proxy=no，§9-G），走 bridge.Forward 自带 x-api-key（bridge.go:87）/ responses 分支 Bearer（bridge.go:97），不经过 forwardHeaders，所以当前不触发；若将来给 QN 加 chat 原生跳，forwardHeaders 不重设 Authorization 会保留客户端原始 Bearer → 潜在 401。其余同 QW（thinking 请求侧、多模态、错误码表未见适配） |
| CP（CLIProxyAPI） | base http://127.0.0.1:8317/v1，本机 Go 单二进制，OpenAI 兼容统一出口（config.go:174、zgate.json:42-52）；zgate.json 里唯一 windows=[] 的纯按需 child | 作为普通 chat 上游直转；health /v1/models（zgate.json:50）；key 来源与别名不一致见 §1 结论 2 | Bearer 覆盖客户端原始头（router.go:475-478 注释明确「漏掉 CP 会保留客户端原始 Bearer，被上游回 401 Invalid API key」）；ondemand 拉起。运行态：POST /v1/chat/completions model=Gemini-3.6-Flash → HTTP 200、ct=application/json、bytes=341、首包 {"id":"kJDxas6pBKrv694Phun2-QY","object":"chat.completion","model":"gemini-3.6-flash",...,"reasoning_content"...}；zgate.log "启动子进程 cliproxyapi: ...cli-proxy-api.exe [-config config.yaml]" → "子进程 cliproxyapi 就绪 pid=5740" → "POST /chat/completions model=Gemini-3.6-Flash -> CP:gemini-3.6-flash (1/1)"（lead 回喂） | zgate.json 未写 cliproxyEnvFile，靠 config.go:128-130 默认值；env 变量名 CLIPROXY_API_KEY 与回落变量 CLIPROXY_ACCESS_KEY 不一致（真值文件里确实是 CLIPROXY_ACCESS_KEY，§9-A）；未见 CP 的 Gemini /v1beta 入站面适配（zgate 只走 /v1 chat） |

**运行态覆盖矩阵（lead 回喂 + 本分片独立复现交叉坐实）**：OC=GET /models 200 data=30 透传；OC+proxy=beam-free (2/2) 后直连冷却中跳过；WB=HY4-Free (1/1) 200 + SSE 200；QD=Qwen-3.8-Max /messages 200 触发 qoder 拉起；QW=无主 channel，仅 DeepSeek-4.1-Flash 链里有跳、本轮未单独触发；QN=Conatus 429 退避；CP=Gemini-3.6-Flash 200 触发 cliproxyapi 拉起。→ 6 个 upstream 全部在生产链路里，没有一个是纸面配置。/health 末次复测（§9-L）：HTTP 200、ok=true、cooling=1、alias.models=22、uptime_s=3004，children 三个全 running（workbuddy 30920 / qoder 5884 / cliproxyapi 5740，全部 policy=ondemand，last_error 全空），key 字段仅布尔值 true。

## 1. 硬结论（6 条，均带真实路径:行号 + 命令真实输出，台账见 §9）

1. **upstreams 里根本没有 path / search / proxy 字段，这三者分属三个不同层。** F:/Project/ModelBus/gateways/zgate/zgate.json:11-18 每个通道只有 base/child/keyEnv 的子集；F:/Project/ModelBus/gateways/zgate/internal/config/config.go:22-26 的 Upstream 结构体也只有 Base/Child/KeyEnv。命令真实输出（§9-A）：OC ['base'] / WB ['base','child'] / QD ['base','child'] / QW ['base','keyEnv'] / QN ['base','keyEnv'] / CP ['base','child','keyEnv']。path+search 由 router.go:998-1015 normalizePath 从入站 URL 动态生成（剥 /v1 前缀、保留 RawQuery），在 router.go:517 拼成 target := strings.TrimRight(base, "/") + path + search；proxy 挂在 alias map 每跳的 Hop.Proxy（F:/Project/ModelBus/gateways/zgate/internal/alias/alias.go:32），由 router.go:693 注入 context、egress.go:53-70 按代理串缓存 Transport。

2. **凭据来源六路分叉，且存在「文档自述 ≠ 源码」冲突，以源码/运行态为准。** F:/Project/ModelBus/gateways/zgate/internal/keys/keys.go:113-161 Load 先读环境变量 OPENCODE_GO_KEY / WB_GATEWAY_KEY / QD_API_KEY / QWEN_API_KEY / QINIU_API_KEY / CLIPROXY_API_KEY（keys.go:116-121），再回落 provider_config.json 规则、WB gateway config.json、各家 .env.local（keys.go:122-154）；CP 的回落却读 cliproxy.env 的 CLIPROXY_ACCESS_KEY（keys.go:155-158，源码原文注释「CLIProxyAPI 的客户端 key 存在它自己的 cliproxy.env（CLIPROXY_ACCESS_KEY）」）。仓库根 AGENTS.md §2 表格只写 CLIPROXY_API_KEY，与源码冲突。CliproxyEnvFile 在 config.go:128-130 默认 "../../third-party/cliproxyapi/cliproxy.env"，config.go:243 用 resolve() 展开（config.go:248-262：expandEnv → ~ → 相对 c.Dir → filepath.Clean）。命令真实输出（§9-A）：zgate.json cliproxyEnvFile key present: False；resolved: F:\Project\ModelBus\third-party\cliproxyapi\cliproxy.env exists: True；cliproxy.env 变量名 CLIPROXY_ACCESS_KEY / CLIPROXY_BASE_URL；CP 实测产物 cli-proxy-api.exe 77667840 B / config.yaml 3034 B / cliproxy.env 181 B（键名仅 CLIPROXY_BASE_URL、CLIPROXY_ACCESS_KEY，未打印值，lead 回喂）。

3. **「统一入口不等于统一协议」：客户端直接发原生 Anthropic /v1/messages 时 zgate 不做协议转换，只按 model 命中把同一路径同一 body 透传给上游；zgate 只在「alias 条目明确写 protocol=messages/responses」或「chat 路径 + qwen:/qn: 前缀」时主动做 OpenAI↔Anthropic 双向桥。** 源码根因（§9-J）：router.go:274 isChat := path == "/chat/completions"；router.go:275-277 的 400 判定是 !isChat && (isQoder(model) || isWorkBuddy(model) || isQwen(model) || isQiniu(model))，而四个谓词定义在 router.go:1130-1145，全是前缀判定（"qoder:" / "qwen:" / "qn:" / "cn:" / "global:"），不是渠道判定。400 只命中「非 chat 路径 + 带渠道前缀的裸 model」这一窄条件。运行态 A/B/C（§9-J，本分片独立复现）：A. POST /v1/messages model=Qwen-3.8-Max（alias 统一名、不带前缀）→ HTTP 200、bytes=338、原生 Anthropic "type":"message"，zgate.log "POST /messages model=Qwen-3.8-Max -> QD:Qwen3.8-Max (1/1)"；B. POST /v1/messages model=qwen3.8-max（裸 OC id）→ HTTP 401、bytes=93、{"type":"error","error":{"type":"authentication_error","message":"Go requires a credential"}}，zgate.log "POST /messages model=qwen3.8-max -> opencode"（未命中 alias → routeFallback default router.go:428-432 → OC 透传）；C. POST /v1/chat/completions model=HY4-Free stream=true → HTTP 200、ct=text/event-stream、bytes=1409、": heartbeat" + chat.completion.chunk。→ 客户端仍需自己知道目标格式；上游认就 200、不认就 401/400。

4. **「直连 403 → 机场孪生跳」是配置生成 + 运行期判据两段式，冷却键确实带 proxy，且在运行态生效。** F:/Project/ModelBus/tools/model_alias.py:214 定义 AIRPORT_PROXY = "http://10.0.0.1:7896"，tools/model_alias.py:217-240 with_airport_fallback() 给 OC 直连跳补一条同上游、带 proxy 的孪生跳（排链尾、幂等）；Go 网关不硬编码该常量，只读 hop.proxy。识别：router.go:891-906 regionBlocked 认 403/400 + 四个 marker（unsupported_country_region_territory / RegionError / not available in your country / region, or territory not supported）；冷却判据 router.go:908-926 proxyTwinAfter 要求当前跳 Proxy=="" 且后面存在同 Channel、同 Upstream、Proxy!="" 的跳；命中才 markCoolingFor(hop, regionCooldown=30min)（router.go:800-805）。router.go:89 hopKey = Channel|Upstream|Proxy，故直连与机场是两个键；F:/Project/ModelBus/gateways/zgate/internal/router/egress_test.go:357-363 断言两者不相等，F:/Project/ModelBus/gateways/zgate/internal/router/router_test.go:498-557 断言 403→孪生 200 且第二请求跳过直连（directHits=1、airport requests=2），router_test.go:561-599 断言单跳链不冷却。运行态（§9-K）：/health cooling 从 0→1（beam-free 直连 403 被 regionCooldown 冷却，lead 回喂 uptime_s=2590 时点）、zgate.log 多条 "POST /chat/completions model=beam-free -> OC:beam-free [messages] (2/2)" 后出现 "[router] OC|beam-free| 冷却中，跳过"；本分片复测末次 /health cooling=1、uptime_s=3004（§9-L）。

5. **逐跳回落是递归 attemptChain，冷却按错误类型分级；「单跳链不冷却」的判据就是 proxyTwinAfter 返回 false。** router.go:685-822 attemptChain 对冷却中/缺 key/子进程未就绪都跳到 index+1（router.go:694-708）；router.go:815-821 chat 跳的 fallback 闭包切下一跳；router.go:928-942 chainAccept 让 429/502/503/504、region 403/400、400 model_unavailable 回落。时长（§9-M 常量行号）：hopCooldown 30min（router.go:46）、regionCooldown 30min（router.go:72）、quotaCooldown 24h（router.go:78）、rateLimitCooldown 45s + 就地退避 700ms（router.go:51/55）、timeoutCooldown 5min（router.go:64）、transportRetryDelay 300ms（router.go:60）。错误归一化（rawError 已删）现用：router.go:628-639 retryHint 只取 error.code 写日志；router.go:824-862 hopFatal/quotaExhausted 按 marker 判死跳；bridge.go:181-197 upstreamMessage 把上游 error.message / message / 原文归一成 OpenAI 风格 {"error":{"message":"bridge upstream error: ...","type":"upstream_error"}} 并保留真实状态码（QN Conatus 429 实测报文即此形态，§0 表）。全仓 grep rawError 真实输出（§9-E 末）：仅 PROGRESS.md:2600、2607、2687 三处历史描述，源码 0 命中。冷却计数时点差可解释：lead 在 uptime_s=2794 见 cooling=2（beam-free 直连 + QN 429 各一条），本分片在 uptime_s=3004 见 cooling=1 —— 429 用的是 45s 短冷却（rateLimitCooldown），已自然过期，恰印证分级时长。

6. **/v1/models 是 OC 单家 catalog 透传，不是 6 家聚合视图。** 命令真实输出（§9-H）：GET /v1/models 与 GET /models 同一请求对逐字节相同（byte_identical=True）、HTTP 200、bytes=35541、content-type=application/json、data_len=30、首 id=deepseek-v4.1-flash；§9-I 命令输出：grep -nE '/models|v1/models|catalog|listModels' gateways/zgate/internal/router/router.go → 0 匹配（grep_exit=1）。源码链路：normalizePath（router.go:998-1015）剥 /v1 前缀 → routeFallback default（router.go:428-432，channel="OC"、label="opencode"、base=cfg.Upstreams["OC"].Base）→ s.forward（router.go:440）→ doForwardWith（router.go:517）拼成 OC base+"/models"。zgate.log 佐证（§9-K）："GET /models model=- -> opencode" 多条。→ 未见按上游归一化的目录聚合。

## 2. router.go 转发家族逐函数（task 2）

- forward（router.go:489-491）：直接 doForwardWith(..., nil, nil, nil)，无 accept、无 retry，失败即 502。
- forwardChain（router.go:493-512）：旧式「同 base 下多模型名」链；index>=len 返回 502 "all upstreams failed: "+strings.Join(chain," -> ")；rewriteModel 改 model；retry 闭包切 chain[index+1]；doForwardWith 传 chainAccept。
- doForwardWith（router.go:514-626）：拼 target := strings.TrimRight(base, "/") + path + search（router.go:517）；克隆 headers、设 ContentLength、client.Do；传输层失败重试同跳一次（300ms）后 retry(err.Error())；accept 非 nil 时 4xx 读最多 8192B 头部，429 就地退避 700ms 一次再 onThrottled；成功响应 copyHeaders + WriteHeader + 32KB 分块 Flush（SSE 可透传，运行态 HY4-Free 实测 200 text/event-stream）。
- forwardHeaders（router.go:457-487）：剔除 hopByHop（router.go:203-213 九项）、host、content-length、accept-encoding；UA 缺省 unified-router/1.0；switch 命中 "WB","QD","QW","CP" → h.Set("Authorization","Bearer "+key)（router.go:475-478，注释明确 CP 必须覆盖原始 Bearer 否则上游 401 Invalid API key）；"OC" → Bearer + opencode-cli/1.0 + X-Opencode-Session（router.go:479-484）。**QN 不在 switch 内**（latent gap，见 §0 表 QN 行两档判定）。
- attemptChain（router.go:685-822）：新式「每跳自带 base/channel/protocol/proxy」混合链，chat 跳走 doForwardWith，桥接跳走 bridge.Forward；router.go:693 每跳 WithProxy 覆盖 context；非 2xx 且未写出 chunk 才回落（router.go:775-783）。
- /v1/models 与 /v1/messages 的路由差异：无专用分支，差异来自 normalizePath（router.go:998-1015）剥 /v1 后的 isChat 判据与 alias 命中结果。/v1/models 被原样转发成 OC base+"/models"（结论 6）；/v1/messages 是 isChat=false，但 400 只在「带渠道前缀的裸 model」或「alias 条目 protocol!=chat」时触发（结论 3 + §2.5），命中 chat 协议的 alias 条目则原路径原 body 透传。

### 2.5 初稿结论 3 的修正记录（保留判据收紧过程，避免 lead 误以为原判仍在）

初稿写「/v1/messages 因 isChat=false，对 QD/WB/QW/QN 前缀模型直接 400（router.go:275-277），桥接 alias/chain 目标也 400（router.go:303-307、676-678）」。逐字收紧后：router.go:275-277 的 400 条件是「!isChat && 四个前缀谓词之一」，四个谓词（router.go:1130-1145）只看 model 字符串前缀，与渠道无关；router.go:303-307 只在 t.Protocol != "chat" 时拦，router.go:676-678 同理，而 alias map 里 Qwen-3.8-Max / HY4-Free 的 t.protocol 与 hop.protocol 都是 chat（§9-J alias 明细），所以放行。正确结论见 §1 结论 3：「统一入口不等于统一协议」，400 是窄条件。运行态 A/B/C 直接证伪了初稿的宽判据。

## 3. anthropic ↔ openai 桥接、凭据链与回归网（task 3）

- F:/Project/ModelBus/gateways/zgate/internal/bridge/bridge.go:75-149 Forward：messages → chatToAnthropic + headers {"content-type":"application/json","user-agent":"opencode-cli/1.0","x-opencode-session":"unified-bridge","x-api-key":opts.Key,"anthropic-version":"2023-06-01"}（bridge.go:83-89）+ POST base+"/messages"（bridge.go:90）；responses → chatToResponses + "authorization":"Bearer "+opts.Key（bridge.go:97）+ POST base+"/responses"（bridge.go:99）；未知协议 500。**桥的鉴权自带，不依赖 forwardHeaders**，这是 QN Conatus messages 跳当前不触发 401 的直接原因。
- 流式：bridge.go:115-119 只要 opts.Stream && OnChunk != nil 就走 forwardStream（bridge.go:199-295），声明 Accept: text/event-stream，逐 delta 转 chat.completion.chunk 并 flush；streamAnthropic（bridge.go:368-469）处理 text_delta / thinking_delta / input_json_delta / tool_use，streamResponses（bridge.go:471-554）处理 output_text.delta / function_call 增量。首块 role 延迟到真有数据，写出后失败只能在流里补错误并 [DONE]（bridge.go:279-282）。
- 请求侧：chatToAnthropic（bridge.go:722-861）system→system、tool→tool_result、assistant→text/tool_use、tools→input_schema、stop→stop_sequences、tool_choice→auto/none/tool，max_tokens 缺省 4096、>65536 夹到 65536（bridge.go:809-825，注释引用上游区间 [1,65536] 与 ZCode 128000 的实例）；chatToResponses（bridge.go:863-967）system→instructions、tool→function_call_output、max_output_tokens 等。
- 响应侧：anthropicToChat（bridge.go:971-1027）与 responsesToChat（bridge.go:1029-1106）统一成 chat.completion，thinking→reasoning_content、tool_use→tool_calls、finish_reason stop/tool_calls/length；usageOf（bridge.go:1126-1138）把 input_tokens/output_tokens 换名；sseOf（bridge.go:583-637）把非流式响应合成 chat SSE。
- 凭据：keys.go:113-161 六路；config.go:128-130/243 CliproxyEnvFile 默认与 resolve；F:/Project/ModelBus/gateways/zgate/main.go:119-136 与 router.go:974 两处 keys.Load 都传 cfg.CliproxyEnvFile。运行态 env 变量名列表见 §9-A（无真值）。
- **适配性正面结论：协议桥有完整回归网，且正本已迁 Go。** 命令真实输出（§9-M）：grep -c '^func Test' → bridge_test.go 11 / stream_test.go 3 / egress_test.go 14 / router_test.go 15 / quota_test.go 3 / alias_test.go 3（合计 49 个 Test 函数）；bridge_test.go 覆盖 TestChatToAnthropicMovesSystemAndTools / TestAnthropicToChatKeepsReasoningAndTools / TestChatToResponses / TestResponsesToChat / TestSSEShape / TestForwardStreamAnthropicToolCall / TestForwardTimesOut / TestIdleReaderTripsOnSilence 等；router_test.go 含 TestRegionBlocked403CoolsTheDirectHopOnly:498 / TestRegionBlockedDoesNotCoolALoneHop:561 / TestQoderModelOnlySupportsChat:167 / TestQueryStringIsForwarded:230 等。tools/protocol_bridge.js 实测 ABSENT（ls 报 "No such file or directory"），而 bridge.go:2 仍写 "It is a faithful port of tools/protocol_bridge.js." —— 属陈旧注释，正本已是 Go，标注为文档/注释冲突（§7 第 6 条）。

## 4. 地区 403 与代理孪生跳（task 4）

链路：tools/model_alias.py:214/217-240 生成 [直连 OC 跳, 机场孪生 OC 跳(proxy http://10.0.0.1:7896)] → alias.go:32 读 hop.proxy → router.go:693 WithProxy 注入 context → egress.go:53-70 EgressRouter 按串缓存带 ProxyURL 的 Transport → 直连撞 403 RegionError → regionBlocked(router.go:891-906) 命中 → chainAccept(router.go:928-942) 返回 false 回落 → accept 闭包在 proxyTwinAfter(router.go:908-926) 为真时冷却直连跳 30min（router.go:800-805）→ 下一请求 cooling(hop)(router.go:119-131) 跳过直连、直接走孪生跳。冷却键带 proxy（router.go:89），日志用 maskProxy 脱敏（router.go:95-117、egress_test.go:365-403 断言带 userinfo 的 proxy 只在日志掩码、冷却键保留原始串）。运行态实况：/health cooling 0→1→2（§9-K/§9-L）、zgate.log beam-free (2/2) 与「冷却中，跳过」多条；alias map 统计 proxy 跳 11 个、proxy 取值唯一 ['http://10.0.0.1:7896']（§9-G）。grep 真实输出见 §9-E（AIRPORT_PROXY / RegionError / hopKey 相关命中 119 条，rawError 全仓仅 3 条且全在 PROGRESS.md 历史记录）。

## 5. 逐跳回落与单跳判据（task 5）

- 失败切下一跳：router.go:503-510（旧链 retry 闭包）、router.go:815-821（新链 fallback 闭包）、router.go:757-760 与 778-781（桥接跳）。
- 冷却 30min：hopCooldown（router.go:46）与 regionCooldown（router.go:72）；24h/45s/5min/300ms 见 §1 结论 5 与 §9-M。
- 单跳链不冷却判据：proxyTwinAfter（router.go:912-925）在当前跳已带 proxy、或链尾无同 Channel/同 Upstream/带 proxy 的孪生跳时返回 false；注释 router.go:909-911 明说否则会把真实 403 变成 "all upstreams failed" 502。router_test.go:561-599 用两次请求都真撞上游（hits=2）来断言。

## 6. 协议差异边界（task 6）

| 差异 | 结论 | 源码证据 |
|---|---|---|
| 流式 SSE | 已处理（且比文件头注释更新），运行态实测通 | bridge.go:115-119、199-295、368-554、583-637；router.go:1071-1111 bridgeChunkWriter；doForwardWith 32KB Flush（router.go:604-626）。运行态 HY4-Free stream=true → HTTP 200 text/event-stream bytes=1409（§9-J 请求 C）。冲突：bridge.go:4-7 仍写「Upstream calls are non-streaming ... one chunk」，docs/MODEL-PROVIDERS.md:488 写「上游非流式」——均为陈旧自述，以现码与运行态为准 |
| thinking 参数 | 响应侧已接（thinking_delta / reasoning summary → reasoning_content）；**请求侧未见适配** | bridge.go:444-449、986-988、1074-1084；chatToAnthropic(722-861)/chatToResponses(863-967) 全文未生成 thinking / reasoning 字段；docs/MODEL-PROVIDERS.md:492「桥不转发思考字段 → 始终思考；reasoningLevel.map 必须为 \"{}\"」是 ZCode 侧配置口径，非 zgate 适配（lead 回喂要求保持此判定） |
| tool_use | 已处理，且有回归网 | 请求 bridge.go:734-769、790-807、847-859、875-911、918-935、955-965；响应 bridge.go:989-1006、1053-1073；流式 bridge.go:411-430、450-464、501-550；finish_reason tool_calls（bridge.go:284-289）；bridge_test.go TestForwardStreamAnthropicToolCall / TestChatToAnthropicMovesSystemAndTools / TestAnthropicToChatKeepsReasoningAndTools（§9-M） |
| max_tokens 下限 | **未见下限 1 的显式适配**；只做 <=0→4096、>65536→65536 | bridge.go:809-825（注释引用上游区间 [1,65536]，但代码没有 min(1,...) 分支）；responses 侧 max_output_tokens 只在 >0 时透传（bridge.go:946-952） |
| 图片 / 多模态 | **未见适配** | textOf（bridge.go:641-661）只取 string 或 part.text / part.content 字符串，image_url 等非文本 part 被丢弃；chatToAnthropic 默认分支只造 {"type":"text"} 块（bridge.go:777-780） |
| 各家错误码 | 部分（marker 子串 + 统一 OpenAI 风格 envelope），**未见按上游分别映射的码表** | router.go:824-862、883-906、928-942、628-639；bridge.go:121-130、181-197、221-225、269-283；QN Conatus 429 实测被归一成 {"error":{"message":"bridge upstream error: ...","type":"upstream_error"}}（§0/§9-J），不是各家原始码 |

## 7. 文档 / 注释 / 源码 / 运行态冲突清单

1. AGENTS.md §2「CP 凭据 CLIPROXY_API_KEY」vs keys.go:155-158 回落读 CLIPROXY_ACCESS_KEY（env 文件实测变量名同为 CLIPROXY_ACCESS_KEY，§9-A；真值文件 cliproxy.env 181 B、键名仅 CLIPROXY_BASE_URL/CLIPROXY_ACCESS_KEY，lead 回喂）。以源码与运行态为准。
2. bridge.go:4-7 与 docs/MODEL-PROVIDERS.md:488「上游非流式 / 一个 chunk」vs bridge.go:115-119、199-295 的真实流式转发 + HY4-Free SSE 200 实测。以源码与运行态为准。
3. docs/MODEL-PROVIDERS.md:480-482「QW 只有 /v1/messages，/v1/models 与 OpenAI 兼容路径都是 404」是 QW 上游事实；zgate 侧 router.go:998-1015/517 仍会把 /v1/models 透传成 OC base+"/models"（结论 6）—— 两者层面不同，不作矛盾，但需注明 zgate 未做目录归一、且默认落到 OC 而非 QW。
4. docs/ZGATE-LIFECYCLE.md:24-26「6 个 upstreams + 3 个 ondemand child」与 zgate.json:11-53 一致；运行态 /health（§9-L）三个 child 全 running、policy=ondemand、last_error 全空，与策略一致。
5. bridge.go:2「faithful port of tools/protocol_bridge.js」vs 实测 tools/protocol_bridge.js ABSENT（§9-M）—— 正本已迁 Go，注释陈旧。
6. 本分片初稿宽判据「/v1/messages 对前缀/桥接目标直接 400」vs 运行态 A/B/C（§2.5）—— 已收紧为「统一入口不等于统一协议」。
7. CodeGraph：codegraph_status 输出项目为 F:\Project\_merged\DeepseekHarness 且 Not initialized（§9-F），按仓库 AGENTS.md §3 不自行 init，建议由人执行 codegraph init / codegraph_sync 后再用索引。
8. 可见性缺口（lead 回喂，本分片未独立复现）：12:01 报告记 18 个模型 vs 现行 alias.models=22；命名空间 16 个裸 id 直穿；build_candidate 换版链。这些属 lead 侧生命周期/可见性证据，本分片只记录指针，不下独立结论。

## 8. 未决疑问（已收紧）

- 本轮未执行 go test（只读约束下避免生成构建产物）；§3 的「回归网齐全」是源码级 grep -c 计数 + lead 回喂的测试名清单，非本分片跑出的测试退出码。若 lead 需要测试真实输出，需明确授权 go test ./...。
- QN 的 forwardHeaders 缺口已按 lead 要求分两档写清：当前不触发（唯一 QN 跳是 messages 桥、自带鉴权）、条件触发（将来加 chat 原生跳时保留客户端原始 Bearer）。无需再列为现行故障。
- /v1/models 已实测坐实为 OC 单家透传（结论 6），不再列为未决。
- alias map 22 模型中 CP/QN 跳数已统计（§9-G：CP hops=4、QN hops=1、QW hops=1、含 CP/QN 的模型 5 个），不再列为未决。
- QW 本轮未单独触发运行态请求（仅链里 1 跳、lead 回喂）；其适配结论来自源码与 bridge 回归网。
- cooling 计数随时点变化（lead 见 2、本分片末次见 1），差额由 rateLimitCooldown=45s 自然过期解释，已在结论 5 写明，不构成矛盾。

## 9. 命令台账（真实输出；凭据仅变量名/布尔值/字节数）

~~~text
§9-A  ops_bash: python 读 zgate.json 字段 + 环境文件变量名 + wc -l
---cliproxy.env resolve target---
zgate.json cliproxyEnvFile key present: False
upstreams keys: ['OC', 'WB', 'QD', 'QW', 'QN', 'CP']
upstream fields per channel:
  OC ['base']
  WB ['base', 'child']
  QD ['base', 'child']
  QW ['base', 'keyEnv']
  QN ['base', 'keyEnv']
  CP ['base', 'child', 'keyEnv']
---resolved paths (names only)---
resolved: F:\Project\ModelBus\third-party\cliproxyapi\cliproxy.env exists: True
alias: C:/Users/<用户名>/.zcode/v2/model-alias-map.json exists: True
---env files variable names only---
[providers/qoder/.env.local]  QD_API_KEY / QD_PANEL_PASSWORD
[providers/qwen/.env.local]   QWEN_API_KEY / QWEN_BASE
[providers/qiniu/.env.local]  QINIU_API_KEY / QINIU_BASE
[third-party/cliproxyapi/cliproxy.env]  CLIPROXY_ACCESS_KEY / CLIPROXY_BASE_URL
[gateways/upstream/workbuddy/config.json]  (JSON，无 KEY=VALUE 行)
wc -l：54 gateways/zgate/zgate.json；1152 gateways/zgate/internal/router/router.go；1154 gateways/zgate/internal/bridge/bridge.go；181 gateways/zgate/internal/keys/keys.go；323 gateways/zgate/internal/config/config.go；519 gateways/zgate/main.go；71 gateways/zgate/internal/router/egress.go；136 gateways/zgate/internal/alias/alias.go。

§9-B  ops_bash: pwd / git rev-parse --show-toplevel / git branch --show-current / git status --short
/f/Project/ModelBus
---TOPLEVEL---
F:/Project/ModelBus
---BRANCH---
main
---STATUS---
 M .githooks/pre-commit
 M .github/workflows/ci.yml
 M AGENTS.md
 M CHANGELOG.md
 M PROGRESS.md
 M README.md
 M docs/ARCHITECTURE.md
 M docs/DOC-RULES.md
 M docs/MAINTENANCE.md
 M docs/MODEL-PROVIDERS.md
 M docs/PITFALLS.md
 M docs/README.md
 M docs/SECRETS.md
 M docs/TOOLS.md
 M docs/TROUBLESHOOTING.md
 M gateways/zgate/build.py
 M gateways/zgate/internal/config/config.go
 M gateways/zgate/internal/keys/keys.go
 M gateways/zgate/internal/router/router.go
 M gateways/zgate/internal/winproc/console_other.go
 M gateways/zgate/internal/winproc/console_windows.go
 M gateways/zgate/internal/winproc/winproc_other.go
 M gateways/zgate/internal/winproc/winproc_windows.go
 M gateways/zgate/main.go
 M gateways/zgate/zgate.json
 M memories/zgate-windowless-build.md
 M providers/qoder/cache/qd_prices.json
 M tools/model_alias.py
?? %SystemDrive%/
?? docs/ZGATE-LIFECYCLE.md
?? evidence/agent-cliproxyapi.md
?? evidence/agent-gateway-lifecycle.md
?? evidence/agent-sort-rule.md
?? evidence/go-model-sync-20261106-120006.md
?? evidence/go-model-sync-20261106-232822.md
?? evidence/go-model-sync-20261109-120007.md
?? gateways/zgate/.restart.log
?? gateways/zgate/zgate.exe.prev
?? third-party/cliproxyapi/
?? tools/check-project.py
?? tools/zgate-lifecycle/
[exitCode 0, STDERR empty；M 条目均为本分片开始前既有，非本分片造成]

§9-C  grep /v1/models|models|rawError in gateways/zgate（节选）
gateways\zgate\main.go:207: log.Infof("alias map  : %s (%d models)", cfg.AliasMap, n)
gateways\zgate\internal\router\router.go:660: "models": s.aliases.Count(),
gateways\zgate\internal\router\router.go:276: writeJSON(w, 400, errorBody("WorkBuddy/Qoder/Qwen models only support chat/completions", "invalid_request_error"))
gateways\zgate\internal\router\router.go:305: writeJSON(w, 400, errorBody(channel+" bridged models only support chat/completions", "invalid_request_error"))
gateways\zgate\internal\router\router.go:677: writeJSON(w, 400, errorBody("bridged models only support chat/completions", "invalid_request_error"))

§9-D  ops_bash: curl -sS -m 5 http://127.0.0.1:7871/health（初稿时点）
{"alias":{"models":22,"path":"C:\\Users\\<用户名>\\.zcode\\v2\\model-alias-map.json"},"children":{"cliproxyapi":{"idle_s":2157,"in_window":false,"last_error":"","policy":"ondemand","port":8317,"state":"stopped","windows":[]},"qoder":{"idle_s":2157,"in_window":false,"last_error":"","policy":"ondemand","port":8790,"state":"stopped","windows":["08:58-09:15","20:58-21:15","21:58-22:15"]},"workbuddy":{"idle_s":5,"in_window":false,"last_error":"","pid":30920,"policy":"ondemand","port":7863,"state":"running","windows":["08:58-09:15","09:58-10:15","20:58-21:15","21:58-22:15"]}},"cooling":1,"ok":true,"opencode":{"base":"https://opencode.ai/zen/go/v1","child":"","key":true},"qiniu":{"base":"https://api.qnaigc.com/v1","child":"","key":true},"qoder":{"base":"http://127.0.0.1:8790/v1","child":"qoder","key":true},"qwen":{"base":"https://maas.qianwenai.com/apps/anthropic/v1","child":"","key":true},"uptime_s":2157,"workbuddy":{"base":"http://127.0.0.1:7863/v1","child":"workbuddy","key":true}}
[HTTP 200]

§9-E  grep AIRPORT_PROXY|7896|airport|unsupported_country_region_territory|RegionError（119 命中，节选）
tools\model_alias.py:214: AIRPORT_PROXY = "http://10.0.0.1:7896"
tools\model_alias.py:217: def with_airport_fallback(hops: list[dict]) -> list[dict]:
tools\model_alias.py:237:         twin["proxy"] = AIRPORT_PROXY
tools\model_alias.py:1250:             group = with_airport_fallback(group)
gateways\zgate\internal\router\router.go:69: // 直连那跳每次都 403 RegionError ...
gateways\zgate\internal\router\router.go:896: []byte("unsupported_country_region_territory"),
gateways\zgate\internal\router\router.go:897: []byte("RegionError"),
gateways\zgate\internal\router\egress_test.go:360: if hopKey(direct) == hopKey(viaAirport) {
grep rawError whole repo（3 命中，全部在 PROGRESS.md 历史记录）:
PROGRESS.md:2600 / 2607 / 2687（gateways/zgate 下 0 命中）

§9-F  codegraph_status
CodeGraph Status
[i] Project: F:\Project\_merged\DeepseekHarness
[!] Not initialized
[i] Run "codegraph init" to initialize

§9-G  ops_bash: python 统计运行时 alias map（C:/Users/<用户名>/.zcode/v2/model-alias-map.json）
models= 22
top channel/protocol: {('WB', 'chat'): 8, ('CP', 'chat'): 4, ('OC', 'messages'): 4, ('QN', 'messages'): 1, ('OC', 'chat'): 3, ('QD', 'chat'): 2}
total hops= 42
hop channel/protocol: {('WB', 'chat'): 10, ('OC', 'chat'): 12, ('QW', 'messages'): 1, ('CP', 'chat'): 4, ('OC', 'messages'): 10, ('QN', 'messages'): 1, ('QD', 'chat'): 4}
hop proxy count= 11
proxy values: ['http://10.0.0.1:7896']
CP hops= 4
QN hops= 1
QW hops= 1
models with CP/QN in chain= 5
QN/CP/QW 跳明细：
DeepSeek-4.1-Flash hop 3 channel= QW protocol= messages base= https://maas.qianwenaiapi.com/apps/anthropic/v1 proxy= <none>
Gemini-3.6-Flash hop 0 channel= CP protocol= chat base= http://127.0.0.1:8317/v1 proxy= <none>
Gemini-3-Flash hop 0 channel= CP protocol= chat base= http://127.0.0.1:8317/v1 proxy= <none>
Gemini-3.5-Flash-Lite hop 0 channel= CP protocol= chat base= http://127.0.0.1:8317/v1 proxy= <none>
Gemini-3.1-Flash-Lite hop 0 channel= CP protocol= chat base= http://127.0.0.1:8317/v1 proxy= <none>
Conatus hop 0 channel= QN protocol= messages base= https://api.qnaigc.com/v1 proxy= <none> upstream= qiniu/conatus-free
Qwen-3.8-Max top channel= QD protocol= chat upstream= Qwen3.8-Max base= http://127.0.0.1:8790/v1（hop 0 同 QD/chat）
HY4-Free top channel= WB protocol= chat upstream= cn:hy4free base= http://127.0.0.1:7863/v1（hop 0 同 WB/chat）

§9-H  ops_bash: python GET /v1/models 与 /models 逐字节比对（本分片独立复现，同一请求对）
/v1/models HTTP 200 bytes 35541 md5 ee5962a0e6513fcb2de4dd671ecc7ecf ct application/json data_len 30 first_id deepseek-v4.1-flash
/models    HTTP 200 bytes 35541 md5 ee5962a0e6513fcb2de4dd671ecc7ecf ct application/json data_len 30 first_id deepseek-v4.1-flash
same_request_pair_byte_identical= True
（md5 为同一时刻请求对的共同值；不同时刻因目录动态字段会变化，但同对始终一致。lead 回喂同值：HTTP 200, bytes=35541, data len=30, 首 id=deepseek-v4.1-flash）

§9-I  ops_bash: grep -nE '/models|v1/models|catalog|listModels' gateways/zgate/internal/router/router.go
--- grep /models|v1/models|catalog|listModels in router.go ---
grep_exit=1
（0 匹配）

§9-J  ops_bash: 本分片独立复现 lead 的 A/B/C 三次最小请求（无客户端凭据，max_tokens=1）
=== lead 交叉证据 A/B/C 独立复现 ===
/v1/messages model=Qwen-3.8-Max HTTP 200 ct= application/json; charset=utf-8 bytes= 338
   first= {"id": "msg_63e5250b087f429986705f63", "type": "message", "role": "assistant", "model": "Qwen3.8-Max", "content": [], "stop_reason": "max_tokens", "stop_sequence": null, "usage": {"input_tokens": 6, ...
/v1/messages model=qwen3.8-max HTTP 401 ct= application/json bytes= 93
   first= {"type":"error","error":{"type":"authentication_error","message":"Go requires a credential"}}
/v1/chat/completions model=HY4-Free HTTP 200 ct= text/event-stream bytes= 1409
   first= : heartbeat\n\ndata: {"choices":[{"delta":{"role":"assistant"},"finish_reason":null,"index":0}],"created":1794216155,"id":"d6790d7d2ebf40618a6a8aef3763e55d","model":"hy4-free","object":"chat.completion.chunk","usage":null}\n\ndata: {"choices":[{"delta":{"reasoning_content":"Okay"},...
lead 回喂原始 A/B/C 与 zgate.log 新增行：
  A. POST /v1/messages model=Qwen-3.8-Max → HTTP 200 ct=application/json; charset=utf-8 bytes=338 首包 {"id": "msg_4a205e2a91a7475b82c0c3f0", ...}；zgate.log 17:17:33 "POST /messages model=Qwen-3.8-Max -> QD:Qwen3.8-Max (1/1)"
  B. POST /v1/messages model=qwen3.8-max → HTTP 401 bytes=93；zgate.log 17:17:34 "POST /messages model=qwen3.8-max -> opencode"
  C. POST /v1/chat/completions model=HY4-Free stream=true → HTTP 200 ct=text/event-stream bytes=1409 ": heartbeat" + chat.completion.chunk
  CP（lead 回喂 17:19:40）：POST /v1/chat/completions model=Gemini-3.6-Flash → HTTP 200 ct=application/json bytes=341 首包 {"id":"kJDxas6pBKrv694Phun2-QY","object":"chat.completion","model":"gemini-3.6-flash",...,"reasoning_content"...}；zgate.log "启动子进程 cliproxyapi: ...cli-proxy-api.exe [-config config.yaml]" → "子进程 cliproxyapi 就绪 pid=5740" → "POST /chat/completions model=Gemini-3.6-Flash -> CP:gemini-3.6-flash (1/1)"
  QN（lead 回喂 17:19:44）：POST /v1/chat/completions model=Conatus → HTTP 429 ct=application/json bytes=164 首包 {"error":{"message":"bridge upstream error: Too many requests for this free model ...","type":"upstream_error"}}；zgate.log "POST /chat/completions model=Conatus -> QN:qiniu/conatus-free [messages] (1/1)" → 17:19:45 "[router] QN|qiniu/conatus-free| 429，退避 700ms 后重试同一跳"

§9-K  ops_bash: 只读读 C:\Users\<用户名>\AppData\Local\ZCodeGateway\zgate.log（控制台中文为 GBK/mojibake，UTF-8 解码可定位）
log_path= C:\Users\<用户名>\AppData\Local\ZCodeGateway\zgate.log exists= True
bytes= 886078 lines= 9342 matched= 4353
2026-11-09 17:10:05 INFO  POST /chat/completions model=beam-free -> OC:beam-free [messages] (2/2)
2026-11-09 17:10:05 INFO  [router] OC|beam-free| 冷却中，跳过（原文为控制台 GBK 字节，lead 回喂同串）
2026-11-09 17:10:23 INFO  GET /models model=- -> opencode
2026-11-09 17:17:58 INFO  GET /models model=- -> opencode
2026-11-09 17:19:23 INFO  GET /models model=- -> opencode
2026-11-09 17:20:41 INFO  GET /models model=- -> opencode
（多次 GET /models 均落 opencode，与结论 6 一致；lead 回喂 cooling 0→1 at uptime_s=2590）

§9-L  ops_bash: 末次 /health 只读复测（本分片）
health HTTP 200 bytes 1012 ok True cooling 1 alias_models 22 uptime_s 3004
children_state {'cliproxyapi': ('running', 5740), 'qoder': ('running', 5884), 'workbuddy': ('running', 30920)}
key_booleans {'opencode': True, 'qiniu': True, 'qoder': True, 'qwen': True, 'workbuddy': True}
（lead 回喂 uptime_s=2794 时 cooling=2、三个 child 全 running、workbuddy 30920 / qoder 5884 / cliproxyapi 5740，last_error 全空；差额由 45s rateLimitCooldown 过期解释）

§9-M  ops_bash: 测试计数 / 常量行号 / protocol_bridge.js 存在性
=== test func counts ===
gateways/zgate/internal/bridge/bridge_test.go : 11
gateways/zgate/internal/router/stream_test.go : 3
gateways/zgate/internal/router/egress_test.go : 14
gateways/zgate/internal/router/router_test.go : 15
gateways/zgate/internal/router/quota_test.go : 3
gateways/zgate/internal/alias/alias_test.go : 3
=== protocol_bridge.js presence ===
ls: cannot access 'tools/protocol_bridge.js': No such file or directory
ABSENT
=== bridge.go port comment ===
2:// OpenAI Responses and back. It is a faithful port of tools/protocol_bridge.js.
=== cooldown constants & keys ===
45:// hopCooldown 是死跳的默认冷却时长；与额度窗口同一量级的短周期，够跨过一轮使用。
46:const hopCooldown = 30 * time.Minute
51:const rateLimitCooldown = 45 * time.Second
55:const rateLimitBackoff = 700 * time.Millisecond
60:const transportRetryDelay = 300 * time.Millisecond
64:const timeoutCooldown = 5 * time.Minute
72:const regionCooldown = 30 * time.Minute
78:const quotaCooldown = 24 * time.Hour
89:func hopKey(hop alias.Hop) string { return hop.Channel + "|" + hop.Upstream + "|" + hop.Proxy }
115:func hopKeyForLog(hop alias.Hop) string {
119:func (s *Server) cooling(hop alias.Hop) bool {
156:func (s *Server) markCoolingFor(hop alias.Hop, d time.Duration) {
891:func regionBlocked(status int, head []byte) bool {
912:func proxyTwinAfter(chain []alias.Hop, index int) bool {
929:func chainAccept(status int, head []byte) bool {
~~~

## 10. 方法学备注

- 每条结论均挂真实路径:行号；命令真实输出集中 §9 台账（§9-A~M）并逐条引用；章节编号已从初稿的 §10-A~G 统一为 §9-A~M。
- 运行态证据优先级：实时 HTTP 响应与 zgate.log > 运行时 alias map / env 文件结构 > 源码 > 文档自述/注释。
- lead 三批交叉实证（m00040 / m00059 / m00066 / m00070）已逐条并入：/v1/models 透传（结论 6）、原生 /v1/messages 判据收紧（结论 3 + §2.5）、QN 两档判定（§0 表）、回归网（§3）、运行态覆盖矩阵与 ondemand PID（§0 表末段）、CP/QN 实测（§9-J）、cooling 时点差（结论 5）。lead 侧未独立复现的「命名空间 16 裸 id 直穿 / build_candidate 换版链 / 12:01 报告 18 vs 现行 22 可见性缺口」只在 §7 第 8 条留指针，不下独立结论。
- 本分片为子代理独占产物，未触碰 PROGRESS.md、docs/、tools/、gateways/ 及任何共享文件；唯一写入 F:/Project/ModelBus/evidence/agent-adaptation.md。
