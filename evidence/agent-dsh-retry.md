# DSH 侧 429 / 重试 / 切渠道优化点

> **一句话**：优先给三条 `llm-pi-ai` route 写各自的 `retryPolicy`，把 `RATE_LIMIT` 从默认可重试集合中摘掉、把 `maxRetries` 从 5 降到 0（或保守档 1）；`reasoning: high` 与默认模型是次级调优点；429 自动切模型在当前版本没有配置开关，只能靠默认模型/会话手动切，或新增 `agent/request-error` 恢复插件。本次只审计，未改动任何生产配置。

## 结论（可改哪几处、优先级）

### P0：直接消掉「5/5」和 429 长串重试 —— 三条 provider 的 `retryPolicy`

现值不是写在 profile 里的，而是插件默认值：`mode=normal`，`maxRetries=5`，`retryableCodes=[EMPTY_RESPONSE,RATE_LIMIT,SERVER,TIMEOUT,TRANSPORT]`，`initialDelayMs=500`，`maxDelayMs=10000`，`jitterRatio=0.1`。`~/profiles/desktop/cordis.patch.yml` 的 `llm-pi-ai.providers` 三个 route 均未写 `retryPolicy`，因此按 `dsh-llm/lib/types/retry-policy.js` 的缺省解析生效。

建议值（按「429 快速失败 / 立即允许人工切模型」）：

```yaml
# cordis.patch.yml，- id: llm-pi-ai / config.providers.<route> 下新增，三个 route 都要写：
retryPolicy:
  mode: normal
  maxRetries: 0
  retryableCodes: [EMPTY_RESPONSE, SERVER, TIMEOUT, TRANSPORT]
  backoff:
    initialDelayMs: 500
    maxDelayMs: 10000
    jitterRatio: 0.1
```

如果仍希望保留「一次快速重试」再交还控制权，把 `maxRetries` 改为 `1`，其它不变：

```yaml
retryPolicy:
  mode: normal
  maxRetries: 1
  retryableCodes: [EMPTY_RESPONSE, SERVER, TIMEOUT, TRANSPORT]
  backoff:
    initialDelayMs: 500
    maxDelayMs: 3000
    jitterRatio: 0.1
```

两条建议都把 `RATE_LIMIT` 从 `retryableCodes` 移除：`dsh-llm-retry/lib/index.js:160` 会直接 `return next()`，429 不再产生 `llm/retry` 事件；`maxRetries: 0` 是硬快速失败，`maxRetries: 1` 是保留一次非 429 抖动重试。`retryableCodes` 不得为空、不得重复（`retry-policy.js:101-109`）；`initialDelayMs <= maxDelayMs`，两者均 >0 且 `jitterRatio ∈ [0,1]`（`retry-policy.js:64-75`）。

按 route 落点的精确参数清单：

| 优先级 | 文件:行（现值位置） | 参数 | 现值 | 建议值 | 生效方式 |
|---|---|---|---|---|---|
| P0 | `~/.dsh/profiles/desktop/cordis.patch.yml:47` `zcode-main` | `retryPolicy` | 未写 → 默认 `normal/5/RATE_LIMIT` | `mode: normal; maxRetries: 0; retryableCodes: [EMPTY_RESPONSE, SERVER, TIMEOUT, TRANSPORT]; backoff: {initialDelayMs: 500, maxDelayMs: 10000, jitterRatio: 0.1}` | 热加载；HMR 监听 `cordis.patch.yml`，`providers` 为 volatile，`llm-pi-ai` 收到 `loader/volatile-update` 后 `registration.replace(routes)` |
| P0 | `~/.dsh/profiles/desktop/cordis.patch.yml:76` `zcode-free` | 同上 | 同上 | 同上 | 同上 |
| P0 | `~/.dsh/profiles/desktop/cordis.patch.yml:139` `zcode-saver` | 同上 | 同上 | 同上 | 同上 |
| P0（保守档） | 上述三处 | `retryPolicy.maxRetries` | 5 | 1 | 同上；并把 `maxDelayMs` 同时改为 `3000`，否则退避仍可到 10 秒 |
| P0（快速失败档） | 上述三处 | `retryPolicy.maxRetries` | 5 | 0 | 同上 |
| P0 | 上述三处 | `retryPolicy.retryableCodes` | `[EMPTY_RESPONSE,RATE_LIMIT,SERVER,TIMEOUT,TRANSPORT]` | `[EMPTY_RESPONSE,SERVER,TIMEOUT,TRANSPORT]` | 同上；`RATE_LIMIT` 不再进入 `llm-retry` 恢复器 |
| P1 | 上述三处 | `retryPolicy.backoff.maxDelayMs` | `10000` | `3000`（保留一次重试时） | 同上；同时是上游 `Retry-After` 的上限闸门 |
| P1 | 上述三处 | `retryPolicy.backoff.initialDelayMs` | `500` | `500` 保持不变 | 热加载；调小只影响非 429 抖动重试 |
| P1 | 上述三处 | `retryPolicy.backoff.jitterRatio` | `0.1` | `0.1` 保持不变 | 热加载 |
| P2 | `~/.dsh/profiles/desktop/cordis.patch.yml:49,78,141` | `reasoning` | `high` | `off`（仅当目标是降低单请求输出与排队成本；会改变模型行为，不属于严格行为等价优化） | 热加载；`profile.reasoning` 是请求默认档位，可用值 `off/minimal/low/medium/high/xhigh/max`，但每个模型只接受自己 `reasoningEfforts` 声明过的档位 |
| P3 | `~/.dsh/profiles/desktop/cordis.patch.yml:7-9` | `agent-default-model.provider/model/reasoningEffort` | `zcode-free / HY4-Pre / high` | 保持；仅在想把新会话默认切到可用渠道时改为 `zcode-main / DeepSeek-4.1-Flash / high` | 热加载影响此后创建的 agent；已有会话沿用持久 `requestHeader`，不回写历史 |

### P1：429 能否「快速失败」或「切模型」

- **快速失败：能，纯配置**。`retryableCodes` 去掉 `RATE_LIMIT`，或 `maxRetries: 0`。`dsh-client-ui-chat/lib/client.js:5288` 的 `5/5` 就是 `node.maxRetries`，值来自 `llm/retry` 事件的 `maxRetries` 字段，非 SDK 内部计数。
- **自动切 provider/model：当前版本没有配置开关**。`dsh-llm-retry/lib/index.js:116-149` 的恢复结果只有 `{kind:"retry"}`，失败步骤重跑时 `dsh-agent-loop/lib/index.js:1050-1052,1136-1146` 仍从同一持久 `requestHeader` 重建 `provider/model`；`dsh-llm-pi-ai/lib/index.js:467` 的 `allowedFallbackModels` 是 Anthropic compat 的 `withhold` 字段，不是失败转移列表。模型选择由 `dsh-agent/lib/index.js:166-192` 在 `agent/request` waterfall 注入，只跟随「会话级 model selection」，不看失败 code。
- **可实现自动切模型的位置**：新增一个监听 `agent/request-error` 的插件（与 `dsh-compaction-basic/lib/index.js:861-887`、`dsh-compaction-image-offload/lib/index.js:141-145` 同扩展点），在 `failure.code === "RATE_LIMIT"` 时改会话级 model selection 并返回 `{kind:"retry"}`，或返回非 retry 让轮次快速结束。该插件本身需要新代码，重启/重新加载插件后生效；不属于仅改 YAML 即可完成。代码片段落点：`dsh-agent-loop/lib/index.js:1136-1143` 的 payload 已带 `provider / failure / retryPolicy / signal`，但没有 `agent` 字段，恢复插件需从 `ctx.agents` 或已注册 model-control 服务定位目标会话。

### P2：默认模型与 provider 级 reasoning

- `agent-default-model` 只有 `provider / model / reasoningEffort` 三字段（`dsh-agent-default-model/lib/index.js:21-25`），它在「新 agent 创建时」给出初始 selection，不参与失败恢复。
- 三条 route 的 `reasoning: high` 是 route 默认请求档位：`dsh-llm-pi-ai/lib/index.js:1953` 用 `options.reasoningEffort ?? profile.reasoning`，再经 `1785-1789` 校验模型支持；模型不声明 `high` 时会抛 `UNSUPPORTED_REASONING_EFFORT`，`dsh-llm/lib/index.js:718-724,2191-2198` 还有 prepareCall 层的同名校验。当前 `HY4-Pre` 声明 `high: high`（`cordis.patch.yml:105-112`），所以默认组合可服务。
- 把 `reasoning` 改低/改 `off` 会减少思考 token 和排队压力，但**会改变输出内容**，不能作为「行为等价」的验证对象；若只追求 429 不再重试，不应动它。
- 备份 `cordis.patch.yml.bak-reasoning-20261105-1052:7-8` 显示此前默认模型是 `zcode-main / DeepSeek-4.1-Flash`；当前已改成 `zcode-free / HY4-Pre`。这只影响新会话，不解释 429 重试次数。

### 代码级默认值（只读，不建议改 app.asar）

| 文件:行 | 现值 | 作用 |
|---|---|---|
| `app.asar/dsh/node_modules/@deepseek-ai/dsh-llm/lib/types/retry-policy.js:12-22` | `5 / 500 / 10000 / 0.1 / [EMPTY_RESPONSE,RATE_LIMIT,SERVER,TIMEOUT,TRANSPORT]` | 未配置 `retryPolicy` 时的全套默认值 |
| `app.asar/dsh/node_modules/@deepseek-ai/dsh-llm/lib/types/retry-policy.js:84-125` | `resolveRetryPolicy` | 校验并冻结每条 route 的策略 |
| `app.asar/dsh/node_modules/@deepseek-ai/dsh-llm/lib/index.js:1876,2243` | `registration.retryPolicy` → `preparedCall.retryPolicy` | 把策略随请求传给 agent loop |
| `app.asar/dsh/node_modules/@deepseek-ai/dsh-llm-pi-ai/lib/index.js:1080,1166-1176` | `RetryPolicySchema` / `resolveRetryPolicy` | YAML 字段入口与解析 |
| `app.asar/dsh/node_modules/@deepseek-ai/dsh-llm-pi-ai/lib/index.js:1764` | `maxRetries: 0` | 关闭 pi-ai SDK 自己的重试，所有可见尝试交给 DSH |
| `app.asar/dsh/node_modules/@deepseek-ai/dsh-llm-pi-ai/lib/index.js:1448-1458` | `429/rate.?limit → RATE_LIMIT` | 上游 429 的分类；先判 `QUOTA` 文案，再判 429 |
| `app.asar/dsh/node_modules/@deepseek-ai/dsh-llm-retry/lib/index.js:151-173` | 计数、退避、`Retry-After` | `previousRetry >= maxRetries` 停止；`providerRetryAfterMs > maxDelayMs` 时 normal 模式直接 `next()` |
| `app.asar/dsh/node_modules/@deepseek-ai/dsh-agent-loop/lib/index.js:1136-1146` | `agent/request-error` waterfall | 只有 `{kind:"retry"}` 才 `continue` 重跑同一请求 |
| `app.asar/dsh/node_modules/@deepseek-ai/dsh-client-ui-chat/lib/client.js:5285-5288` | `node.maxRetries` / `"∞"` | UI 上 `5/5` 的显示来源 |

改 `app.asar` 内这些常量属于改安装产物：不热加载、升级会覆盖、且影响所有 profile；用 per-provider `retryPolicy` 覆盖即可。

## 生效方式 / 热加载

- `cordis.patch.yml` 是 profile 的用户补丁层，`dsh-base/cordis.patch.yml:28-29` 默认挂 `@deepseek-ai/dsh-hmr`；`dsh-app-boot/lib/index.js:508-509,1041-1042` 把它标为 hot-reloaded 并作为最后一层读入，`3207` 明确「patch config replaces the whole config」。因此**改 `- id: llm-pi-ai` 的 `config` 时必须保留完整 `providers` 树**，把 `retryPolicy` 插到各 route 内部；不要另写一个只含 `retryPolicy` 的同 id 覆盖层，那会替换整份 config。
- `dsh-hmr/lib/index.js:849-873` 精确监听 `profile.patchPath` 与 home 层 `cordis.patch.yml`，`1319-1362` 变动后重读 patches 并 `recomposeProfile`。
- `dsh-llm-pi-ai/lib/index.js:1083` 的 `Config.providers` 是 `.volatile()`；`cordis-plugin-loader/lib/index.js:395-425` 在仅 volatile 值变化时发 `loader/volatile-update`；`dsh-llm-pi-ai/lib/index.js:2943-2965` 收到后比较 `registrationFacts()`（`2823-2828` 含 `retryPolicy`），变化即 `registration.replace(routes)`。
- **生效边界**：热加载后对新 `prepareCall()` 生效；`dsh-llm-pi-ai/lib/index.js:1659-1669` 明确一个请求从开始到结束锁定一份 snapshot，正在飞行的请求/已排定等待中的 `llm/retry` 不会被中途改写。已有会话的 `provider/model` 也不因改默认模型而变（`dsh-acp/lib/index.js:656-663,719-720`）。
- `retryPolicy` 改变会改变 `retryStateKey(provider, policyKey)`（`dsh-llm-retry/lib/index.js:50-67,94-106`），即开启一条新的重试计数链；旧的 `llmRetry` 投影不会延续到新策略。
- `dsh-llm-pi-ai` 的 `maxRetries: 0`（SDK 层）与 YAML `retryPolicy.maxRetries` 是两个不同参数：前者固定禁用 pi-ai 内部重试，后者控制 DSH 持久步骤重试，改 YAML 即可，不需要动代码。

## 行为等价验证方法

### A. 参数落地验证（不触发模型请求）

CMD：

```bat
cd /d "<runtime-install>"
DeepSeekRuntime.exe --dump-config --profile desktop > "%TEMP%\dsh-effective-before.yml"
```

把 `retryPolicy` 写入 `~/.dsh/profiles/desktop/cordis.patch.yml` 后，等 HMR 生效（`awaitWriteFinish` 稳定写入后自动 recompose，`dsh-hmr/lib/index.js:55-57,68-89`），再跑一次：

```bat
cd /d "<runtime-install>"
DeepSeekRuntime.exe --dump-config --profile desktop > "%TEMP%\dsh-effective-after.yml"
fc "%TEMP%\dsh-effective-before.yml" "%TEMP%\dsh-effective-after.yml"
findstr /C:"retryPolicy" /C:"maxRetries" /C:"retryableCodes" "%TEMP%\dsh-effective-after.yml"
```

通过判据：diff 只出现三个 `retryPolicy` 块；`findstr` 显示 `maxRetries: 0`（或 `1`）与不含 `RATE_LIMIT` 的 `retryableCodes`；`providers`、`models`、`apiKeyEnv`、`baseURL` 与 before 逐字节一致。等价矩阵里「成功请求 / 502 SERVER / 429 / TIMEOUT / TRANSPORT / EMPTY_RESPONSE」六类输入中，成功请求与 502/超时/传输/空响应仍按原 code 分类，仅 429 与重试预算发生变化；这是**有意的差异点**，不能要求全矩阵字节等价。

若 GUI 已运行，也可以在插件/模型页确认没有 `llm-pi-ai: configuration conflicts with an existing provider route` 报错（`dsh-llm-pi-ai/lib/index.js:2957-2964`）。

### B. 用本地夹具复现 429，观察 `llm/retry` 事件

临时把某条 route 的 `baseURL` 指向本地返回 429 的夹具（只改副本/临时 patch，验证完还原），或让现有 `http://127.0.0.1:7871/v1` 的上游返回 429。夹具响应：

```http
HTTP/1.1 429 Too Many Requests
Content-Type: application/json
Retry-After: 1

{"error":{"message":"rate limit exceeded","type":"rate_limit_error"}}
```

连续 5 次都返回 429。解压当前会话日志并统计：

```bat
zstd -dc --no-check "%USERPROFILE%\.dsh\sessions\--F-Project-_merged-DeepseekHarness--\<session-dir>\session.v4.jsonl.zstd" | findstr /C:""type":"llm/retry"" /C:"RATE_LIMIT" /C:"policyKey" > "%TEMP%\dsh-retry-events.txt"
```

- 改前基线：应看到 `policyKey` 为 `["normal",5,["EMPTY_RESPONSE","RATE_LIMIT","SERVER","TIMEOUT","TRANSPORT"],500,10000,0.1]`，`retry` 从 1 递增到 5，`maxRetries: 5`，`failure.code: "RATE_LIMIT"`。
- `maxRetries: 0` + 去掉 `RATE_LIMIT` 后：`llm/retry` 事件数为 0，轮次直接以 `RATE_LIMIT` 结束；UI 不再出现 `n/5`。
- `maxRetries: 1` + 去掉 `RATE_LIMIT` 后：429 仍是 0 次重试；若同一夹具改返回 502，`SERVER` 会产生最多 1 次 `llm/retry`，`maxRetries: 1`，`delayMs <= 3000`。
- 热加载等价检查：先发一条请求让它进入 `llm/retry` 等待，再改 `cordis.patch.yml`；该次等待的 `delayMs` / `maxRetries` 保持旧策略，下一条新请求才用新 `policyKey`。这对应 `dsh-llm-pi-ai/lib/index.js:1659-1669` 的快照语义。

### C. 现网日志的实测锚点

本机会话 `~/.dsh/sessions/--F-Project-_merged-DeepseekHarness--/a2ed8c91-12f9-4873-b396-cc667f6f048d/session.v4.jsonl.zstd` 已出现 `llm/retry` 事件：`provider=zcode-free`、`mode=normal`、`policyKey=["normal",5,["EMPTY_RESPONSE","RATE_LIMIT","SERVER","TIMEOUT","TRANSPORT"],500,10000,0.1]`、`retry=1..2`、`maxRetries=5`；当时 `failure.code="SERVER"`（502 `all upstreams failed: WB:cn:hy4-preview-f`）。同一 `policyKey` 对 `RATE_LIMIT` 同样适用，证明默认策略就是「5/5」来源。多个并行子会话（`bfd6f175…`、`f2f9b15e…`、`b37dce1a…`）重复出现相同 `policyKey`，不是某条会话的局部状态。

## 证据路径

- `~/.dsh/profiles/desktop/cordis.patch.yml:4-9,44-52,76-80,139-143,105-112`：默认模型、三条 route、route 级 `reasoning: high`、当前默认模型 `HY4-Pre` 的档位声明；全文件无 `retryPolicy`。
- `~/.dsh/profiles/desktop/cordis.yml:1-4`：profile 根为空数组，明确只改 `cordis.patch.yml`。
- `~/.dsh/profiles/desktop/cordis.patch.yml.bak-reasoning-20261105-1052:4-9`：改前默认 `zcode-main / DeepSeek-4.1-Flash`。
- `app.asar/dsh/node_modules/@deepseek-ai/dsh-base/cordis.patch.yml:28-29,90-100,135-136`：HMR 默认挂载、base 默认模型 `deepseek-official/deepseek-flash`、`llm-retry` 与 `llm-pi-ai` 的挂载 id。
- `app.asar/dsh/node_modules/@deepseek-ai/dsh-llm/lib/types/retry-policy.js:12-22,58-76,84-125`：默认 5 次、退避、合法键、normal/always 解析。
- `app.asar/dsh/node_modules/@deepseek-ai/dsh-llm/lib/index.js:1876,2233-2243,2041-2043`：策略注册与随 `preparedCall` 传递。
- `app.asar/dsh/node_modules/@deepseek-ai/dsh-llm-pi-ai/lib/index.js:1049-1083,1166-1176,1448-1458,1513-1521,1659-1669,1753-1765,1785-1789,1884-1885,1953,2823-2828,2943-2965`：YAML schema、策略解析、429 分类、SDK 重试关闭、reasoning 默认、热重注册。
- `app.asar/dsh/node_modules/@deepseek-ai/dsh-llm-pi-ai/README.zh.md:38,51-53,75-89,119,259`：`retryPolicy` 位于每个 profile、默认 5 次、429 分为 `RATE_LIMIT` / `QUOTA`、SDK 重试保持禁用。
- `app.asar/dsh/node_modules/@deepseek-ai/dsh-llm-retry/lib/index.js:24-29,44-67,116-149,151-183`：插件自身零配置、退避公式、`Retry-After` 闸门、计数与 `agent/request-error` 监听。
- `app.asar/dsh/node_modules/@deepseek-ai/dsh-llm-retry/README.zh.md:38-50,54-58,129-135`：示例 `retryPolicy`、默认 5 次、always 模式风险、重试边界。
- `app.asar/dsh/node_modules/@deepseek-ai/dsh-agent-loop/lib/index.js:1050-1052,1136-1146,1175-1197`：失败后只 `retry` 同一持久请求，模型来自 `agent/request` waterfall。
- `app.asar/dsh/node_modules/@deepseek-ai/dsh-agent/lib/index.js:166-204`：会话级 model selection 的注入与切模型提示，不看失败 code。
- `app.asar/dsh/node_modules/@deepseek-ai/dsh-agent-default-model/lib/index.js:21-25,38-45,53-65`：默认模型三字段、读取与保存。
- `app.asar/dsh/node_modules/@deepseek-ai/dsh-agent-default-model/README.zh.md:44-50,71`：`currentSelection()` 只用于新 agent。
- `app.asar/dsh/node_modules/@deepseek-ai/dsh-acp/lib/index.js:656-663,718-720`：resume 时优先恢复持久 request header，避免默认模型改写旧会话。
- `app.asar/dsh/node_modules/@deepseek-ai/dsh-client-ui-chat/lib/client.js:5285-5288`：UI 重试计数显示 `node.retry / node.maxRetries`。
- `app.asar/dsh/node_modules/@deepseek-ai/dsh-hmr/lib/index.js:49-121,849-873,1319-1362`：精确文件监听、refresh、recompose。
- `app.asar/dsh/node_modules/@deepseek-ai/dsh-app-boot/lib/index.js:490-509,1041-1042,1127-1136,3197-3207,3782-3783,3993-4004`：patch 层顺序、hot-reloaded 标记、`patch config replaces the whole config`、重组成入口。
- `app.asar/dsh/node_modules/@deepseek-ai/cordis-plugin-loader/lib/index.js:395-425`：volatile 配置变更发 `loader/volatile-update`。
- `app.asar/dsh/node_modules/@deepseek-ai/dsh-compaction-basic/lib/index.js:861-887`、`dsh-compaction-image-offload/lib/index.js:141-145`：现有 `agent/request-error` 恢复插件范例。
- `~/.dsh/sessions/--F-Project-_merged-DeepseekHarness--/a2ed8c91-12f9-4873-b396-cc667f6f048d/session.v4.jsonl.zstd`：实测 `llm/retry` 事件与 `policyKey`。

## 未解决项

- `dsh-llm-pi-ai` 的错误分类只拿到 pi-ai 的 `errorMessage` 字符串（`dsh-llm-pi-ai/lib/index.js:1513-1521`），**未解析 429 响应头 `Retry-After`**；`providerRetryAfterMs` 只有 `dsh-llm-deepseek/lib/index.js:1781-1787` 会填。若上游 429 携带 `Retry-After: 60`，当前 `normal` 策略不会据此等待 60 秒，仍按本地退避；建议值把它直接快速失败，反而更符合「不要拖住会话」的目标。若需要「精确按 Retry-After 等待后再试」，需改适配器从响应头构造 `providerRetryAfterMs`，并把 `maxDelayMs` 提到 `>=60000`（`dsh-llm-retry/lib/index.js:168-171` 的闸门）。
- 当前 `QUOTA` 文案判定先于 429（`dsh-llm-pi-ai/lib/index.js:1450-1451`），上游若把额度耗尽写成 `429 quota exceeded` 会被归为 `QUOTA`；`QUOTA` 本来就不在默认 `retryableCodes`，不会重试。若上游把 429 写成 `429 too many requests` 而无 quota 文案，则归 `RATE_LIMIT`，正是本文配置处理的目标。
- 自动切 provider/model 需要新增 `agent/request-error` 恢复插件或改 `dsh-agent` 的 model selection；`allowedFallbackModels` 是 Anthropic compat 保留字段（`dsh-llm-pi-ai/lib/index.js:448-468`），配置它不会形成失败转移链。
- 本机 `DeepSeekRuntime.exe --dump-config` 的退出行为未在本次只读审计中实跑（避免启动第二个实例干扰现有 GUI）；验证段给出的是按 `dsh-app-boot` 的 `--dump-config` schema 说明与 profile 启动参数写出的复现命令，执行前在测试 profile/副本上跑一次即可确认 CLI 参数拼写。
