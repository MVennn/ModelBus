# MODEL-STREAM — 流式 / 思考 / 输出 / TPS 自动准入

> **一句话**：模型只要进 `~/.dsh/profiles/<profile>/cordis.patch.yml` 的 `llm-pi-ai`
> 模型表，就自动纳入每日流式准入探针，新增模型不需要人工逐个测试。

本文是这套机制的**唯一正本**：契约从哪来、每天谁触发、怎么判、失败怎么自动恢复、
接线被拆了谁报警。命令里的 `<profile>` 默认 `desktop`，可用 `DSH_PROFILE` 覆盖；
网关默认 `http://127.0.0.1:7871/v1`，可用 `MODEL_GATEWAY_BASE` 覆盖。

---

## 1. 背景与要解决的问题

`Default` 伪档位让请求不带 `reasoning_effort`，推理模型因此丢思考、正文聚成整块；
根因、补丁与实测对照以 [PITFALLS.md](PITFALLS.md) §40 为正本，这里不重复定义。
准入机制只保留上游文档给出的真实档位（`disabled / low / medium / high / xhigh / max`
等，按宿主 `THINKING_LEVELS` 固定序），effort 为空时取 `model.reasoning.efforts` 末位
并显式写进请求。

| 现象 | 对准入判定的要求 |
|---|---|
| Iceman 看不到思考，输出一段一段拖出来 | 必须同时判思考 chunk 与分块间隔 |
| 有的模型不流式，或思考整段一次性吐出 | 必须按 SSE 逐块计数，不能只看最终正文 |
| 同一请求偶尔只给正文、思考完全空白 | 必须单列 `ENC` 加密分流，不能与模型故障混判 |

## 2. 单一契约（L1）

契约只有一个：`~/.dsh/profiles/<profile>/cordis.patch.yml` 里 `id=llm-pi-ai`、
provider 以 `zcode-` 开头的模型表。`tools/dsh_sync.py --apply` 从 ZCode 最终
`provider_config.json` 投影它，`tools/model_alias.py --apply` 会自动回调投影。

`tools/model_stream_check.py` 的 `load_contract()` 直接读这张表，按每个模型的
`reasoningEfforts` 与 `compat.thinkingFormat` 推导出三类：

| kind | 判定要求 |
|---|---|
| `reasoning_deepseek` | 必须吐思考 + 必须流式；首选档发真实 wire 值 |
| `reasoning_plain` | 必须流式；思考不强制 |
| `no_reasoning` | 必须流式；不判思考、不发 effort |

**模型进表即自动纳入**，没有第二份需要手工维护的清单。上游目录声明过档位却没写进
`values` 属于接入问题，规则见 [MODEL-PROVIDERS.md](MODEL-PROVIDERS.md) §5。

## 3. 活体探针（L2）

`tools/model_stream_check.py` 对每个待测模型发一条约 100 字的连续叙述提示，
用 SSE 逐块计数：chunk 数、思考字数、正文字数、最大块间隔、首块延迟、总耗时、
端到端字符速率（CPS，TPS 代理）、`finish_reason`。

增量选择由 `--changed` 负责，只打三类模型：

1. 指纹（`id + 档位列表 + kind + wire`）不在上次 `contract` 里的**新增 / 档位变更**模型；
2. 上次状态落在 `RETRY_STATES = {SKIP, FAIL, WARN, EXEMPT}` 的**待复查**模型；
3. 没有基线报告时退化为全量。

`PASS` 与 `RECOVERED` 不重复打，避免每天对全量模型白发一轮推理请求；
瞬态失败次日自动重测，豁免模型借此自动复通。`--model` 单测与 `--changed` 一样把结果
合并回全量视图，`latest.json` 恒为契约条数，手动单测不会破坏次日基线。

思考占满首选预算（`max_tokens=768`）时，**保持同一官方档位**把预算提到
`RECOVER_TOKENS=8192` 补测正文。预算给小必被思考吃满：2026-11-10 实测 Iceman
`high-2048` 思考 1899 字仍 `contentChars=0` / `fin=length`，`high-4096` 也没拿到正文；
`high-8192` 两次都出（549 块 / 思考 2322 字 / 正文 100 字 / `fin=stop`）。该模型思考长度
随机 1400–2700+ 字，补测预算按最坏情况给。
不退回省略 effort —— 那正是 `Default` 伪档位 bug 的根源；也不用
`off / wire=disabled` 关思考 —— 上游实测回 `HTTP 422`。

探针另设 `ENC` 列与 `encryptedReasoning` 字段，单计
`reasoning_details[type=reasoning.encrypted]`。A 格式尾部也会带一条 replay detail，
所以 B 分流的判据是「零明文思考（`THINK=0`）且 `ENC>0`」：此时理由写明
「上游加密思考分流」，不再含糊标成「声明 deepseek 思考但 reasoningChars=0」。
上游分流根因、展示层与网关层避法以 [PITFALLS.md](PITFALLS.md) §41 为正本，
这里只记探针口径，不重复定义机制。

产物是 `.work/model-stream/report-<UTC>.json` 与 `latest.json`（真实项目内，
`.gitignore` 排除），字段含 `contractCount`、`contract`、`models`、`summary`、
`thresholds`。工具表见 [TOOLS.md](TOOLS.md)。

## 4. 离线接线守卫（L3）

`tools/check-project.py --stream-contract` 是**离线**守卫：不发任何推理请求，
`.githooks/pre-commit` 与 `.github/workflows/ci.yml` 跑的无参数全量命令也包含它。

静态接线七处，掉一处就 `FAIL`：

| 检查 | 防止什么回退 |
|---|---|
| `sync-models.ps1` 含 `model_stream_check.py --changed --soft` 钩子 | 自动触发被删，新模型又没人测 |
| 探针含 `--changed` | 退化成每天全量或干脆不增量 |
| 探针含 `RECOVER_TOKENS` | 思考占满预算被误判为故障 |
| 探针含 `RETRY_STATES` | 瞬态 / 豁免模型次日不再复查 |
| 探针含 `reasoning.encrypted` / `encryptedReasoning` | 上游加密分流被含糊标成模型故障 |
| `docs/MODEL-STREAM.md` 存在 | 契约正本丢失 |
| `docs/README.md` 索引了它 | 正本变孤儿，规则没人找得到 |

报告分支只读本机 `latest.json`：能解析、`models` 为 list、条数等于 `contractCount`、
每行有 `state`、B 分流行带「加密思考分流」理由就记一条 `OK` 摘要；本机没有报告（CI 常态）记 `SKIP`。
**单个模型的健康状态只记录、不阻断提交** —— 活体探针绝不进 CI，CI 上没有
`127.0.0.1:7871` 网关。

## 5. 触发链：新增模型为什么不用手工测

```
上游清单 / 白名单 → model_alias.py --apply → dsh_sync.py --apply（投影 patch）
        → 每日 12:00 \ModelBus 模型同步 → sync-models.ps1 → 投影块之后
          model_stream_check.py --changed --soft（带 -Soft，不阻断流水线）
        → 次日复测待复查 / 豁免模型 → 上游修好自动 RECOVERED
```

Windows 计划任务 `\ModelBus 模型同步` 是唯一自动驱动，daily 12:00，
入口 `sync-models.vbs → sync-models.ps1`。**不新设计划任务**：探针复用这条链的
`-Soft` 分支，失败不阻断同步，接线由 L3 在提交前 / CI 里守住。
日常动作清单见 [MAINTENANCE.md](MAINTENANCE.md) §6。

一个模型从进表到被实测，全流程零人工：契约推导 → 增量选择 → 活体判定 →
报告落盘 → 待复查闭环。人只需要在上游真故障且长期不复通时，看
`tools/model_stream_exemptions.json` 里那条是否已被自动标成 `RECOVERED`。

## 6. 判定口径

| 项 | 口径 |
|---|---|
| 分块 | 正文 >= 24 字且（`chunks < 4` 或 `maxDelta > max(48, 正文*0.6)`）判大块聚合 → `WARN` |
| 速率 | `tps = 正文字符 / 总耗时`；低于 1.0 标 `WARN` 而非 `FAIL`（跨供应商波动可达 6 倍） |
| 瞬态 | 429 / 5xx / 超时 / 网络错误退避重试 2 次后仍失败 → `SKIP`，不算故障 |
| 上游限流 | 网关把排队 / 额度包成 `HTTP 200` + `{"error":{...}}` 的 SSE 首帧（如 10605 / RESOURCE_LIMIT）；探针识别后记 `SKIP`，不能判成「上游空 completion」 |
| 未实测 | 增量模式（`--changed` / `--model`）下契约里没轮到实测的模型补 `SKIP` 占位行，保证 `models` 条数恒等于 `contractCount`；占位行不带 `fingerprint`，次日仍会被选中补测 |
| 空正文 | 首选档思考占满预算 → 同档位 8192 补测；补测拿到正文且无其它问题 → `PASS` |
| 思考 | 仅 `reasoning_deepseek` 强制要求思考字数 > 0 |
| 加密分流 | `THINK=0` 且 `ENC>0` → `WARN`，理由写明「上游加密思考分流」；离线守卫复核该标注没丢 |
| 并发 | 默认 2（实测 6 会把网关打出假阴性） |

## 7. 豁免与自动复通

`tools/model_stream_exemptions.json` 只记上游真故障模型，每条带 `recoverWhen`。
探针**仍会实测它们**：满足条件标 `RECOVERED`（提示可删条目），否则标 `EXEMPT`
（不计 `FAIL`）。当前两条：Muse-Spark1.3（空 completion，`contentChars>0` 复通）、
Claude-Haiku-5.5（403，`http!=403` 复通）。上游修好后无需人工改清单。

## 8. 手动命令与退出码

| 命令 | 用途 |
|---|---|
| `python tools/model_stream_check.py` | 全量矩阵（人工复核） |
| `python tools/model_stream_check.py --changed` | 只测新增 / 档位变更 / 待复查 |
| `python tools/model_stream_check.py --changed --soft` | 每日同步链尾同款，不阻断 |
| `python tools/model_stream_check.py --model Iceman` | 单测（结果仍合并回全量视图） |
| `python tools/model_stream_check.py --deep` | 额外找「未声明档位的隐藏思考能力」 |
| `python tools/check-project.py --stream-contract` | 离线接线守卫 |
| `python tools/model_stream_check.py --no-heal` | 跳过插件补丁自愈 |

退出码：`0` 无 `FAIL`；`1` 存在 `FAIL`（`--soft` 下仍返回 0）；
`2` 配置 / 依赖错误。`check-project.py` 有 `FAIL` 返回 1，全 `SKIP` 也返回 0。

## 9. 边界

- 活体探针只在本机每日同步链尾跑；CI / pre-commit 只跑离线守卫。
- 报告与证据是中间产物，落在真实项目 `.work/` 内，不进版本库。
- 改带 BOM 的 `sync-models.ps1` 必须保留 `EF BB BF` + LF，见 [PITFALLS.md](PITFALLS.md) §39。
- 网关守卫是 Go 代码，必须换 `zgate.exe` 才生效；`/admin/reload` 只热加载 `zgate.json`，流程见 [TROUBLESHOOTING.md](TROUBLESHOOTING.md) §16.2。
- 文档规则（单一正本、索引、孤儿、体量）见 [DOC-RULES.md](DOC-RULES.md)。

---

## 10. 同类模型免配置适配（网关守卫 auto 模式）

上游把思考加密、只回 `reasoning_details[type=reasoning.encrypted]` 这件事**不是某个模型专属**：
同一个别名会按会话/连接粘到不同后端，任何走 deepseek 系思考协议的新模型都可能踩到。
所以适配责任放在网关，不放在模型表。

| 层 | 谁来适配 | 新增同类模型要不要动 |
|---|---|---|
| L1 契约（`cordis.patch.yml` 模型表） | 同步脚本 | 要（这是模型进表的唯一入口） |
| L2 探针（`model_stream_check.py`） | 读 L1 自动纳入 | **不要**，进表即被测 |
| L3 网关守卫（`reasoningGuard`） | `mode: "auto"` + 学习表 | **不要**，声明要思考的流式请求自动探针 |

**判定与动作**（`gateways/zgate/internal/router/router.go`）：客户端声明思考（`reasoning_effort` 非空非 `off`，或 `thinking.type=enabled`）→ 首个 SSE delta 若先给正文、零明文 thinking → 判「加密分流」→ 关流、换连接、换会话头重抽同一跳（`maxRetries`，缺省 5）→ 拿到明文就原字节续上；始终拿不到就注入一条可读提示（`injectNotice`）后放行，并按模型记进学习表。

**学习表口径**：连续 `giveUpAfter`（缺省 2）轮「重抽到上限仍是纯加密」且从未见过明文 → `giveUpForSeconds`（缺省 600）内不再白等（每轮省掉几十秒），到期自动复探；一旦某轮拿到明文立刻清零。表只在内存里，重启清空。

**调参速查**

```json
"reasoningGuard": {
  "enabled": true,
  "mode": "auto",            // auto 不看 models 白名单；写 "models" 才只守白名单
  "maxRetries": 5,            // 重抽次数（每次换连接 + 换会话）
  "maxProbeBytes": 32768,
  "injectNotice": true,       // 达上限时插 ⓘ 提示，避免空思考块
  "giveUpAfter": 2,
  "giveUpForSeconds": 600
},
"streamIdleHeartbeatSec": 15  // 空闲心跳（负数=关）；非事件流不掺
```

**踩坑提醒**：`Content-Length` 必须摘（`router.go` 对事件流 `Del("Content-Length")`），否则摘首段/插提示/掺心跳都会触发 `wrote more than the declared Content-Length` 断流，客户端 200 却 0 字节。细节见 [PITFALLS.md](PITFALLS.md) §41。
