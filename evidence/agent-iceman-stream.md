# Iceman 流式 / 加密思考审计分片（只读取证）

> **一句话结论**：Iceman 现在**能流式、也能看到明文思考**；「不能流式 / 看不到思考」的旧观感由四层叠加造成 —— 其中 L1（DSH 不发 reasoning_effort）、L3（守卫没上场 / 探测超时 / 旧二进制）已修完并在 14:38 换版后用真请求验证通过，**唯一真·不可控的是上游按连接随机分流到加密后端（B 后端），且无参数可强制明文**；L2 探针的 WARN 是预算口径产物（768/2048 全被思考吃光），不是流式能力缺失。L4 展示层的「展开」修复在 14:25 被 profile 自动采集回退成 compact/completion/final，属于当前唯一**可自行补救**的残留。

- 审计时间：2026-11-10 14:26–14:56（本地）
- 工作目录：`F:\Project\ModelBus`（HEAD `e032924`，`git log --oneline | grep -i -E 'iceman|stream|encrypted|reasoning|思考'` 实测 4 条命中）
- 只读边界：未改任何源码 / 配置；仅新增本文件
- 线上实例：`http://127.0.0.1:7871/v1`，`zgate.exe` mtime 14:37、10,571,264 字节、PID 26972，启动日志 `14:38:03 zgate 0.3.0 已启动`

---

## 一、现状一行结论（拆成三问）

| 问题 | 答案 | 决定性证据 |
|---|---|---|
| 能不能流式？ | **能**。逐块 SSE 到达，块间隔 p95 = 0.02s | 实跑 2：`chunks 317 / maxGapS 5.45 / p95GapS 0.02 / totalS 14.99 / finish stop` |
| 能不能看到明文思考？ | **能**。明文 `reasoning_content` 以 1196 字逐块下发（`firstReasoningS 2.95`），且尾部只带 1 条 replay blob（`enc 1`），按 `docs/MODEL-STREAM.md:65-68` 的 B 判据（THINK=0 且 ENC>0）**不属于加密分流** | 实跑 2 全字段 |
| 卡在谁头上？ | **① 上游随机分流（不可控，只能重抽规避）② L4 展示层被 profile 自动采集回退（可控，改回去即可）③ L2 探针口径把「思考吃光预算」误读成模型问题（口径问题）** | 见第四、五、六节 |

补充：现在用户若仍觉得「看不到思考」，第一嫌疑不是上游、不是网关，而是 `~/.dsh/profiles/desktop/cordis.patch.yml:20-26` 已回到 `transcriptView: compact` / `collapseTiming: completion` / `foldedReplies: final` —— 整轮默认折叠，思考被收进折叠区。

---

## 二、分层证据表

### L1 契约层（`cordis.patch.yml` → 探针推导 kind）

| 项 | 值 / 位置 |
|---|---|
| 契约唯一来源 | `~/.dsh/profiles/<profile>/cordis.patch.yml` 里 `id=llm-pi-ai`、provider `zcode-*`；`docs/MODEL-STREAM.md:28-33` |
| Iceman kind | `reasoning_deepseek` → 必须吐思考 + 必须流式（`docs/MODEL-STREAM.md:37`；实测值见 `latest.json` `kind`） |
| Iceman 档位表 | `efforts {off: disabled, high: high}`，`expectedEffort high`，`wireEffort high`，`expectThinking true` |
| **L1 缺陷（已由 L3 兜底）** | DSH 真实请求体只有 `{"model":"Iceman","max_tokens":128000}`，**不带 `reasoning_effort`** —— 选择器无逐模型默认档位（Default 伪档位），见 `docs/PITFALLS.md:769` 与 `docs/PITFALLS.md:800`；`gateways/zgate/internal/config/config.go:72-79` 注释记同一事实 |
| 兜底参数 | `zgate.json:22 "forceEffort": "high"`、`:23 "forceEffortModels": ["Iceman","iceman-contributor-free"]`；实现 `router.go:1347-1386`（`injectThinkingEffort`） |

### L2 探针层（`tools/model_stream_check.py`）

| 项 | 值 / 位置 |
|---|---|
| 加密判定 | `_encrypted_reasoning()` `tools/model_stream_check.py:210-222`，只数 `reasoning_details[type^=reasoning.encrypted]`；注释原文「宿主 pi-ai 把它当 replay 元数据丢弃、思考块留空」 |
| 字段出口 | `encryptedReasoning` 在 `tools/model_stream_check.py:307` 返回；正文/思考取自 `_delta_fields` `:198-207` |
| 判据 | `tools/model_stream_check.py:351-393`：`content==0 && reasoning==0`→FAIL；`content==0`→WARN「思考占满预算…」；`expectThinking && reasoningChars==0 && ENC>0`→「上游加密思考分流」 |
| **口径坑** | `docs/MODEL-STREAM.md:65-68` 明写「A 格式尾部也会带一条 replay detail，所以 B 判据是零明文思考且 ENC>0」——**ENC=1 单独不能判加密**，Iceman 明文流每次都在尾部带 1 条 |
| latest.json（旧基线） | `.work/model-stream/latest.json`，`generatedAt 2026-11-10T04:05:22Z`（12:05 写入，早于三/四次修复与 14:38 换版）；`summary {PASS 11, WARN 2, FAIL 0, SKIP 1, EXEMPT 1, RECOVERED 0}`，`contractCount 15`，`tested 4` |
| Iceman 条目全字段 | `http 200 / chunks 314 / reasoningChars 1475 / contentChars 0 / maxDelta 12 / firstMs 2078.0 / totalMs 16984.0 / tps 0.0 / tokTps 45.22 / finishReason "length" / completionTokens 768 / encryptedReasoning 1 / effort high / attempts 1 / state "WARN"`；`recoverProbe {maxTokens 2048, chunks 453, reasoningChars 1960, contentChars 0, finishReason "length", totalMs 34859.0}`；`reasons ["思考占满预算且同档位大预算补测未拿到正文","同档位 2048 预算补测仍未拿到正文"]` |
| 该 WARN 的真实含义 | **不是加密、不是不能流式**：思考 1475–1960 字把 768/2048 预算吃光，`finishReason "length"`；我用 2500 预算实跑立刻拿到正文（`contentChars 48 / finish stop`），说明只是探针预算相对 Iceman 思考长度偏小 |

### L3 网关守卫层（`gateways/zgate/internal/router/router.go`）

| 项 | 值 / 位置 |
|---|---|
| 上场条件 | `resp.StatusCode<300 && wantsStream && isEventStreamGuard(resp) && s.guardWanted(...)`，`router.go:631-715`；`isEventStreamGuard` `:1388-1390`（Content-Type 含 event-stream） |
| 思考声明判定 | `reasoningExpectsThinking` `router.go:1326-1341`（`reasoning_effort` 非空非 off 或 `thinking.type=enabled`）—— 这是三版「守卫没上场」的病灶，现由 `injectThinkingEffort` 在转发前补档（`:1347-1386`；日志「客户端未声明思考档位，按配置补 reasoning_effort=%q」，实跑 14:48:19 命中） |
| **判定条件（探针如何判 B）** | `probeReasoningStream` `router.go:1404-1476`：任一明文思考字段非空→`streamPlaintext` **立即返回**（`:1453-1456`）；先吐 content→`streamEncrypted` 立即返回（`:1458-1460`）；收尾见 `type^=reasoning.encrypted`→`streamEncrypted`（`:1462`）；否则 `streamUndetermined` |
| 探测时限 | `probeReasoningStreamDeadline` `router.go:1482-1505`（goroutine+select，到点 `timedOut=true`；须先 `Close` Body 解阻塞）；时限源 `ProbeSeconds`，`config.go:86` 缺省 12，`zgate.json:18` 实配 **15** |
| **重抽怎么换连接/换会话** | `router.go:556-564`：`if guardRetries > 0 { req.Close = true; ... req.Header.Set("X-Opencode-Session", guardRetrySession(base, guardRetries)) }`；`guardRetrySession` `:1533-1539` 生成为 `<原会话>#r<attempt>-<4字节随机hex>`；间隔 `guardRetryDelay=250ms` `:1509`。旧版沿用 keep-alive + 原会话头 → 3 次重抽全落回同一加密后端（`router.go:557-559` 注释记 2026-11-10 12:01 实测） |
| 三分支（达上限 / 跳过期 / 正常探测） | `router.go:646-668`：`guardInSkip`→直放（可选插 skip 提示）；`guardRetries>=MaxRetries`→记加密/超时并放行原始流（可选插提示）；default→探测（超时→`guardRetries++`+`250ms` 后 `continue` 重抽，加密→继续重抽直到上限） |
| **学习表结构** | `guardModelStat { plaintext int; encryptedOnly int; skipUntil time.Time }` `router.go:1513-1517`；存 `Server.guardMem map[string]*guardModelStat` `:49-50`（注释：重启清空不落盘）；累加 `guardNotePlaintext` `:1596-1602`（`plaintext++; encryptedOnly=0`）、`guardNoteEncryptedOnly` `:1605-1622`（`encryptedOnly++`，达 `GiveUpAfter` 置 `skipUntil=now+GiveUpForSeconds` 并 Warn） |
| 跳过期语义 | `guardInSkip` `router.go:1581-1594`：**到期清 `skipUntil` 与 `encryptedOnly` 再返回 false，不滑动续期**（四次修复点） |
| **达上限后客户端实际看到什么** | 仍是 200 + 完整可读正文流；只在思考块最前面多一条 `delta.reasoning_content` 提示。三条文案原文：加密→`router.go:1666-1681`「ⓘ 上游本次只下发加密思考（已重抽 %d 次仍未拿到明文），思考内容不可见，正文照常输出。」（chunk id `zgate-guard-notice`）；超时→`:1647-1662`「ⓘ 本次思考探测超时（上游思考阶段静默，已重抽 %d 次），已直接放行上游流；思考可能不可见或稍后出现，正文照常输出。」（`zgate-guard-timeout`）；跳过期→`:1628-1643`「ⓘ 该模型近期思考拿不到明文（上游加密或思考阶段静默），本次已跳过重抽直接放行；正文照常输出。」（`zgate-guard-skip`） |
| **Content-Length 摘除在哪** | `router.go:717-725`：`copyHeaders(w.Header(), resp.Header)` 之后 `if isEventStreamGuard(resp) { w.Header().Del("Content-Length") }`；注释 `:719-723`：保留旧 CL 会报 `http: wrote more than the declared Content-Length` 断流、客户端 200 却 0 字节 |
| 空闲心跳 | `router.go:737-742` 取 `StreamIdleHeartbeatSeconds`，非事件流置 0；写循环 `:743-813`，`timer.C` 分支写 `: zgate keepalive\n\n` + `Flush`（`:802-809`）。实配 `zgate.json:11 "streamIdleHeartbeatSec": 15` |

### L4 客户端展示层（DSH profile + 宿主 pi-ai）

| 项 | 值 / 位置 |
|---|---|
| 当前 ui-chat 实配 | `~/.dsh/profiles/desktop/cordis.patch.yml:20-26` → `transcriptView: compact` / `collapseTiming: completion` / `foldedReplies: final` / `performanceUsage: compact`（mtime 14:25） |
| 与修复记录不符 | `CHANGELOG.md:34` 声称已改 `verbose / next-input / all`；实际被 14:25 的自动采集覆盖（同目录有 `cordis.patch.yml.bak-autocapture-20261110142500` 等 5 份备份）→ **展示层修复已回退** |
| 仍在的项 | `cordis.patch.yml:330` `reasoningDisplay: continuous`（思考正文连续显示）未丢 |
| 宿主丢弃 encrypted 的位置 | `@earendil-works/pi-ai/dist/api/openai-completions.js:172-173,416-428`：把 `reasoning_details` 当 replay 元数据，只写 `block.thinkingSignature` 不写 `block.thinking`、不推 delta，`blockIsVisible` 跳过空 reasoning（`docs/PITFALLS.md:789` 记录；本次未二次复核 asar —— 该包不在 profile node_modules 内，`grep -ril 'reasoning.encrypted'` 只命中 `node_modules/billion-context/dist/{index.js,agent/opencode-native.js,agent/pi-native.js}`） |
| 结论 | L4 现在**不会**吞掉明文思考（明文走 `reasoning_content`→`thinking_delta`，与 encrypted 分支无关），只在「整轮折叠」上让用户一眼看不到；想立刻看见就把上述四项改回 `verbose/next-input/all` |

---

## 三、我做的两次活体实测（可复现）

命令形态（bash，经 zgate 7871；不改配置、只发一次请求）：

```bash
python - <<'PY'
import json,time,urllib.request
body={"model":"Iceman","messages":[{"role":"user","content":"用一句话解释为什么天空是蓝色的"}],
      "stream":True,"max_tokens":2500,"reasoning_effort":"high"}
req=urllib.request.Request("http://127.0.0.1:7871/v1/chat/completions",
    data=json.dumps(body).encode(),
    headers={"Content-Type":"application/json","Accept":"text/event-stream"},method="POST")
# 逐 data: 行解析 delta.reasoning_content / delta.content / reasoning_details，记录块间隔
PY
```

| 实测 | 请求 | 结果 |
|---|---|---|
| 1 | `max_tokens 600`，**不带** `reasoning_effort` | http 200 / chunks 353 / reasoningChars 1005 / contentChars 0 / encrypted 1 / first 2.91s / last 13.05s / finish `length` |
| 2 | `max_tokens 2500` + 显式 `reasoning_effort high` | http 200 / chunks 317 / reasoningChars 1196 / contentChars 48 / enc 1 / firstReasoning 2.95s / firstContent 14.97s / **maxGap 5.45s** / **p95Gap 0.02s** / total 14.99s / finish `stop` |

配套日志（`%LOCALAPPDATA%\ZCodeGateway\zgate.log`）：

- `14:48:19` model=Iceman → `OC:iceman-contributor-free (1/2)`，紧接「客户端未声明思考档位，按配置补 reasoning_effort="high"」；
- 其后**无任何**「换连接+换会话重抽」「跳过期内」「WARN 连续 N 轮没拿到明文」行 → 首轮即判 `streamPlaintext`，守卫放行原字节。
- 对照集（学习表在生产上真的会动）：`14:33:52–14:33:54` 另一模型 `cn:deepseek-v4.1-flash` 出现「重抽 1/1」→ WARN「连续 1 次没拿到明文思考，放行上游原始流」→ 之后十余条「在「近期拿不到明文思考」跳过期内，直接放行（不再探测）」。

**由此可判**：「一节一节」的观感不是块聚合（p95 间隔 0.02s），而是 ①思考阶段 2.9s 首字节 + 约 12s 纯思考静默（正文 14.97s 才出现，中间最大空档 5.45s）②客户端整轮折叠。

---

## 四、历次修复逐版复盘：每版做了什么、为什么没解决

| 版本 | 做了什么 | 为什么当时没解决 | 证据 |
|---|---|---|---|
| 第 1 版（`CHANGELOG.md:32-38`） | 展示层展开（`verbose/next-input/all` + `reasoningDisplay continuous`）；网关 `reasoningGuard` 首版（上限 3）；探针加 ENC 列 | ①**线上 zgate.exe 是旧二进制**（PID 17852 未动、不含守卫代码）→ 代码在仓里、进程里没有；②重抽沿用原 headers 保 `X-Opencode-Session`，上游按会话粘后端，3 次重抽全落回同一路加密；③SSE 未摘 `Content-Length`，摘首段即断流 | `CHANGELOG.md:37`；`router.go:557-559` 注释 |
| 第 2 版（`CHANGELOG.md:41-50`） | 重抽换连接（`req.Close=true`）+ 换会话头（`#r<N>-<hex>`）、上限 5；`Del("Content-Length")`；`streamIdleHeartbeatSec`；`mode auto` + 学习表 + `injectNotice` | 12:59 换版后确实命中「重抽 1/5」，但**守卫入口条件写错**：`guardApplies` 首行要求 `reasoningExpectsThinking(body)`，而 DSH 真实请求体 `{"model":"Iceman","max_tokens":128000}` 不带 `reasoning_effort` → 守卫整条链被短路，13:10 两条请求全程无守卫日志 | `docs/PITFALLS.md:800`；`CHANGELOG.md:52-59`；`router.go:1326-1341` |
| 第 3 版（`CHANGELOG.md:52-59` / `PITFALLS.md:800`） | `reasoningGuard.forceEffort` + `forceEffortModels`，转发前 `injectThinkingEffort` 补 `reasoning_effort`；不再依赖前端补丁 | 修好了「上场」，但**探测本身把等待放大到 85 秒**：`probeReasoningStream` 只在「第一个正文 delta」返回 `streamEncrypted`，而加密路思考阶段整段静默（无明文无正文）→ 判定延迟=整段思考（日志两次判定隔 61 秒）；且预算花完最后一发仍用无上限探针。用户侧感受是「卡住不说话」 | `docs/PITFALLS.md:801`；`router.go:1458-1460`（先吐 content 才判加密） |
| 第 4 版（`CHANGELOG.md:61-71` / `PITFALLS.md:801`） | ① `probeSeconds` 硬时限（到点即重抽）② 预算/跳过期不探测直接放行 ③ 提示按成因分三种 ④ 跳过期到期清计数；配置 `maxRetries 1 / probeSeconds 15 / giveUpAfter 1 / maxProbeBytes 32768 / giveUpForSeconds 600`；隔离实例首轮 1,263ms 拿到明文、第二轮 2ms 直通 | 代码侧 19 项 PASS，但**换版是 14:38 才落地**（`zgate.log 14:38:03 zgate 0.3.0 已启动`，exe mtime 14:37 / PID 26972）；14:07:49 那一版仍是旧的。所以 14:38 之前的任何「还是不行」结论都对应旧二进制 | `zgate.json:16-21`；`config.go:86`；`PITFALLS.md:801` |

**一句话归纳**：四版不是四个 bug，是四道串联关卡 —— 旧二进制 → 守卫没上场 → 探测把等待放大 → 学习表/时限缺位。任一关卡没通，用户看到的都是同一个现象（「看不到思考 / 卡着不动」），所以每版都像「修了没用」。

**版本一致性核对**：`git cat-file -p HEAD:gateways/zgate/zgate.json` 实测已经是 `maxRetries 1 / probeSeconds 15 / giveUpAfter 1`，与工作区一致；`git status --porcelain` 只有 ` M gateways/zgate/zgate.json`（脏的是别的字段，本次未能用 `git diff` 取值 —— 本机 `ops_bash` 下 `git diff`/`git show` 稳定返回空输出，属工具限制，已改用 `git cat-file` 重定向绕开）。

---

## 五、L2 探针口径问题（会造成「看起来没修好」）

1. **ENC 单独不可判**：Iceman 每次明文流尾部都带 1 条 `reasoning_details[type=reasoning.encrypted]`（实测 2 次均 `enc 1`），这是 replay 元数据，不是 B 后端。正确判据 `THINK=0 && ENC>0`（`docs/MODEL-STREAM.md:65-68`）。若有人只盯 ENC 列，会误判「还在加密」。
2. **预算相对 Iceman 偏小**：768 → 1475 字思考，2048 → 1960 字思考，两次都 `finishReason "length"`、`contentChars 0` → `WARN`；而 2500 预算实跑拿到 48 字正文且 `finish stop`。探针的「思考占满预算」是**预算口径**结论，不是模型缺陷。
3. **`tps` 被正文口径拖成 0.0**：`tps = 正文字符/总耗时`（`docs/MODEL-STREAM.md:121`），正文为 0 时 tps 必然 0，看板上像「不流式」；真实的思考吐字速率应看 `tokTps 45.22`（latest.json）与块间隔 `p95GapS 0.02`。
4. **旧基线陈旧**：`.work/model-stream/latest.json` 是 12:05 的，早于三/四次修复与 14:38 换版；拿它下「网关没修好」的结论是时间错位。

---

## 六、上游「不可控」的具体边界

**真不可控（只能重抽规避、无法消除）**

1. 上游同一别名 `iceman-contributor-free` 有 A/B 双后端：A 回明文 `reasoning_content`，B 只回 opaque `reasoning_details[reasoning.encrypted]`（`docs/PITFALLS.md:789`）。分流与请求参数无关：显式 `high` 也随机命中，30 次交错采样 2.02s–86.36s。
2. **没有可解密或强制明文的请求参数**：8 类参数 × 5 轮全部照样命中 B（`docs/PITFALLS.md:792` C2 负证据）。也就是说加密 blob 在客户端侧本质上不可读。
3. 因此 B 命中时，网关能做的只有三件：换连接+换会话重抽（提高拿到 A 的概率）、注入一行可读提示（不让思考块全空）、把模型记进学习表省掉后续几百秒白等。**它改不了上游这一次给的是 B**。

**可补救（本地就能改，不用等上游）**

1. 展示层：把 `~/.dsh/profiles/desktop/cordis.patch.yml:20-26` 改回 `transcriptView: verbose` / `collapseTiming: next-input` / `foldedReplies: all` —— 这是当前「看不到思考」的最大单一原因，且已确认是 14:25 自动采集回退。
2. L1 缺档：给模型表补逐模型 `defaultEffort`，或继续依赖网关 `forceEffort`（现覆盖 Iceman 与 `iceman-contributor-free` 两个名字，新增同类模型要加进 `forceEffortModels` —— 这是 auto 模式目前唯一的「配置残留」，`gateways/zgate/internal/router/router.go:1347-1386`）。
3. 探针口径：Iceman 单列抬高 `maxTokens`（≥2500）或把「思考占满预算」降级为 INFO，避免每日基线持续 WARN 掩盖真故障。
4. 体感等待：`probeSeconds` 要大于首字节耗时（明文实测最高 13.5s → 现配 15）；当前 `maxRetries 1` 在「B 命中且首字节正常」的窗口里意味着**只重抽一次**就放行 —— 想提高拿到明文的概率就把 `maxRetries` 提到 2–3，代价是失败时最多多等 2×15s。

**只能等上游（写明当前无法给方案）**

- 解密 B 的 blob：无算法/无密钥渠道，公开协议里只有 `reasoning_details` 透传。
- 让上游固定走 A：无会话亲和性参数可控（会话头 `X-Opencode-Session` 只影响粘哪一路，不能指定「明文那一路」）。
- 上游 A 后端思考阶段本身静默（首字节 2.9s 后 12s 无正文）：这是模型思考时长，不是流式协议问题，网关无法拆分。

---

## 七、待补 / 环境限制

- `@earendil-works/pi-ai` 的 `openai-completions.js:172-173,416-428` 未二次复核：该包在 DSH 宿主 asar 内，本次 `F:\Program Files\DeepSeekRuntime\resources` 路径不存在、`ops_bash` 对含空格 Program Files 路径多次返回空输出（exit null），未取得宿主安装根。相关结论沿用 `docs/PITFALLS.md:789` 的既有取证。
- `git diff` / `git show` 在本机 `ops_bash` 下稳定返回空输出，`zgate.json` 脏行具体是哪个字段未确认（已用 `git cat-file` 证明提交版与工作区的 guard 关键值一致）。
- 未做：把加密 B 的命中率量化（需连续数十次真实请求，超出只读审计时间窗；已知 `PITFALLS.md:789` 的 30 次交错采样结论）。
