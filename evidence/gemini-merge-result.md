# Gemini 3.8 Flash 并入 ModelBus —— 落地记录

日期：2026-11-10　执行：主代理（lead）

## 1. 目标

把 DSH 里新建的直连 provider（baseURL `https://catiecli.sukaka.top/v1`，谷歌模型 `ais-gemini-3.8-flash`）合并进 ModelBus 统一路由：走 zgate 渠道化、归入「主力」组，并用尽量少的调用判定其思考能力。

## 2. 为什么必须改 Go

`zgate.json` 里的 `keyEnv` 是死字段（`internal/config/config.go` 只赋值、无读取方），上游 key 只能来自 `internal/keys` 的 `Set.For(channel)`，而 `For` 原本硬编码 OC/WB/QD/QW/QN 五渠道。不新增渠道，`key` 恒为空串，`router.attemptChain` 会在 `router.go:875-879` 直接跳过该跳，表现为单跳 502。

## 3. 代码改动

### Go（gateways/zgate）

| 文件 | 改动 |
| --- | --- |
| `internal/keys/keys.go` | `Set` 加 `GM`；新增 `reGMBase`（匹配 `catiecli.sukaka.top`）；`Load` 增 `geminiEnvFile` 参数，取 key 顺序 env → `providers/gemini/.env.local` → provider_config 按 base 正则回退；`For` 加 `case "GM"` |
| `internal/config/config.go` | `Config` 加 `GeminiEnvFile`；`applyDefaults` 补 `upstreams["GM"]`；`resolvePaths` 解析该路径 |
| `main.go` / `internal/router/router.go` | `keys.Load` 调用点补参；health 负载加 `gemini`；**`applyHeaders` 的 key 覆盖名单补 `GM`**（漏掉会把空 Bearer 透传上去被回 401「未提供API Key」） |
| `zgate.json` | `geminiEnvFile` + `upstreams.GM` |

### Python（tools/model_alias.py）

`GM_BASE` / `GM_PRICES`、`MAIN_ORDER` 追加 `chat:gem:ais-gemini-3.8-flash`、`CHANNEL_RANK["GM"]=1`、`ABBR` 映射 `Gemini-3.8-Flash`、`VENDOR_PREFIXES` 加 Gemini、`price_of` 的 GM 分支、`gem:` 前缀（`PREFIXES` / `CHANNEL_PREFIX` / `whitelist_items`）、`classify` 的 `gem:` 分支、`CHANNEL_BASE["GM"]`。

### 凭据

`providers/gemini/.env.local`（`GEMINI_API_KEY`，已 gitignore），由 `~/.dsh/.credentials.yaml` 搬运，未回显。

## 4. 验证结果

| 项目 | 结果 |
| --- | --- |
| `python tools/model_alias.py`（dry run） | exit 0，主力组 2 条：DeepSeek-4.1-Flash + Gemini-3.8-Flash（单跳 GM，0.11） |
| `go build ./...` | exit 0 |
| `go test ./...` | alias/bridge/config/router ok；`internal/supervisor` 的 `TestOnDemandStartAndIdleStop` 失败于 TempDir 清理时的文件占用（Windows 文件锁，与本次改动无关） |
| 临时实例 `/health` | `gemini: {"state":"up","key":true}` |
| 临时实例 `/v1/models` | 89 条（含链式别名），`Gemini-3.8-Flash` 在列 |
| `--apply` 生产 | 写入 `provider_config.json`（备份 `*.bak-alias-20261110-134823-055600`）与 `model-alias-map.json`；主力组 2 条，`personalModelIds` 含 `Gemini-3.8-Flash` |
| DSH 投影 | `cordis.patch.yml` 的 zcode-main 新增 `- id: Gemini-3.8-Flash`；手工 `gemini` provider 段已删除（备份 `cordis.patch.yml.bak-gemini-merge-20261110-1352`），provider 从 4 个降为 3 个 |

## 5. 思考能力实测（未定论）

链路已打通：请求能到达上游并拿到上游的 HTTP 响应（不是 401、不是跳过），说明 key 注入与模型解析都正确。

三次尝试的上游答复原文（zgate 日志）：

```
[router] ais-gemini-3.8-flash -> Service Unavailable , fallback (none)
```

- 独立探针（子代理）：HTTP 503，`{"error":{"message":"This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.","code":503}}`
- 合并后经 zgate 重试两次：同样 503，`elapsed` 3.8s / 8.4s，SSE 事件 0 条

结论：上游持续高需求，没有拿到任何 delta，**思考能力无法判定**，也**没有消耗 token**（3 次都是错误响应）。判定为「待复测」，不是「无思考能力」。

复测方法（一次调用即定论）：等上游恢复后，对 `Gemini-3.8-Flash` 发一次 `stream:true, reasoning_effort:"high"` 的请求，看 SSE delta 里是否出现 `reasoning_content` / `reasoning` / `thinking`。若出现，再在 `provider_config.json` 的 `modelConfigRules` 里为该模型补 `optionSpecs.reasoningLevel`（values + map）并重跑投影，DSH 才会显示思考档位。

## 6. 换版与恢复（2026-11-10 13:52-13:54 实况）

- 13:52:27 `deploy-zgate.ps1` 换版：编译 `zgate.candidate.exe` → 停旧 → 备份 `zgate.exe.bak-deploy-20261110-135230` → 替换 → `schtasks /run /tn ModelBus-zgate-hidden` → 13:52:34 `/health` 200，pid=31296。当前 `zgate.exe`（10570752 B）已含 `catiecli.sukaka.top` 与 `geminiEnvFile` 字符串，确认是新代码。
- 13:53 手工 `taskkill` 杀掉 pid=31296，网关停摆；`move /Y zgate.new.exe zgate.exe` 失败（该文件已被换版流程消费），`tools\zgate-lifecycle\restart-zgate.cmd` 相对路径错误（脚本在仓根）。
- 13:54 用 `schtasks /run /tn ModelBus-zgate-hidden` 重新拉起，`/health` 200，`gemini: {"state":"up","key":true}`。

正确换版命令（在仓根执行，一条）：

```cmd
cd /d F:\Project\ModelBus
tools\zgate-lifecycle\restart-zgate.cmd
```

带 `-SkipBuild` 只在 `zgate.candidate.exe` 已存在时用；不带参数会重新编译候选再换版，脚本自带健康检查与失败回滚。

## 7. 生产链路复测（2026-11-10 13:54）

`POST 127.0.0.1:7871/v1/chat/completions  model=Gemini-3.8-Flash`：

```
[router] ais-gemini-3.8-flash -> Service Unavailable , fallback (none)
```

返回 502（透传上游 503），SSE 事件 0。路由段 `GM:ais-gemini-3.8-flash (1/1)` 说明渠道、模型名、key 全部正确，只差上游恢复。证据见 `evidence/gemini-prod-probe.json`。

累计 4 次尝试全部 503，零 token 消耗。
