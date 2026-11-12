# A 路分片：网关非代理端点契约与 /health 消费方核实

> **一句话结论**：7871 生产网关的非代理端点恰好三个（GET /health、GET /v1/models、POST /admin/reload），/health 默认响应永远是 `application/json; charset=utf-8`；已落地的 Fluent 2 后台（127.0.0.1:7872）与全部既有消费方都按 JSON 或状态码消费，因此**网关需要零改动**，后台只在独立进程侧读数据、只经 POST /admin/reload 做唯一写动作。

---

## 0. 分片边界与验收口径

- 真实项目根：`F:/Project/ModelBus`（`git rev-parse --show-toplevel` = `F:/Project/ModelBus`）；junction 视图 `F:/Project/_merged/DeepseekHarness/ModelBus` 未用于读写。
- 本分片只写 `evidence/agent-endpoints.md`；`PROGRESS.md`、`provider_config.json`、`docs/`、`tests/`、`gateways/` 源码、`tools/console/` 均未写入；无 git add / commit / push；长驻网关（zgate / wb2api / mihomo）未重启、未改配置、未实发 POST /admin/reload。
- 凭据口径：key / token / 口令一律未写入本文件；响应体里的上游 base 一律脱敏为 `<REDACTED-URL>`，本机用户目录脱敏为 `<REDACTED-USER>`；`key` 字段仅保留布尔语义。
- `.codegraph/` 未初始化（2026-11-12 实测），全部检索走 grep / glob / read；未执行 `codegraph init`。
- 验收：本文件含可复现命令（§10）与原始输出摘录（§3、§4、§6、§12），数字均可独立复现；self-report 未作为结论依据。

## 1. 结论先给

1. **网关零改动**。三个非代理端点已覆盖后台全部数据需求：指标走 /health，模型目录走 /v1/models，唯一写动作走 POST /admin/reload。
2. **/health 默认响应必须永远是 JSON**。`writeJSON` 统一设 `Content-Type: application/json; charset=utf-8`，无 HTML / 文本 / Accept 分支；`tools/console/sources.py` 的 `_get()` 直接 `json.loads`，非 JSON 即抛 `UPSTREAM_DOWN`。后台保持 7871 响应原样。
3. **后台是独立只读进程**：`tools/console/`（127.0.0.1:7872，Python 3.12 标准库，零 CDN / 零构建 / 零第三方包）已按 Microsoft Fluent 2 语义令牌落地，且是本次核查发现的**新增 /health 消费方**。
4. **轮询下限 ≥ 5 s**：`health()` 首行 `s.aliases.Reload()`，每次 /health 请求都会重读 alias map 文件；已落地后台用 `cached("gateway", 5000, fn)` 与 `polling_hint_ms: 5000` 对齐该约束。
5. 文档口径已由主线对齐：核查时 `docs/CONSOLE.md` 尚是「MD3 设计稿 v1，尚未落地」且写 /health「1166 字节」，与本轮 Fluent 2 要求及实测 2738 B 双重冲突；A 路按边界未写 docs/，已两次回报父代理，主线回告「已完成正本改写与门禁」。分片落盘时 `git status --porcelain` 显示 ` M docs/CONSOLE.md` / ` M docs/README.md`，冲突由主线消解。

## 2. 路由注册自证：非代理端点恰好三个

全 `gateways/` 只有一处生产路由注册与一处 serve 分支表：

| 位置 | 原文 | 作用 |
| --- | --- | --- |
| `gateways/zgate/internal/router/router.go:567` | `func (s *Server) Handler() http.Handler { return http.HandlerFunc(s.serveHTTP) }` | 全 gateways/ 唯一生产 Handler 注册 |
| `gateways/zgate/main.go:197` | `Handler:  router.New(cfg, ks, am, sup, client, log).Handler(),` | 挂到 7871 的 http.Server |
| `gateways/zgate/internal/router/router.go:569` | `func (s *Server) serveHTTP(w http.ResponseWriter, r *http.Request)` | 分派入口 |
| `gateways/zgate/internal/router/router.go:582` | `path, search := normalizePath(r)` | 归一化路径 |
| `gateways/zgate/internal/router/router.go:583-586` | `if path == "/health" { s.health(w); return }` | ① 非代理 |
| `gateways/zgate/internal/router/router.go:587-590` | `if path == "/models" { s.models(w, r); return }` | ② 非代理 |
| `gateways/zgate/internal/router/router.go:591-594` | `if path == "/admin/reload" { s.reload(w, r); return }` | ③ 非代理 |
| `gateways/zgate/internal/router/router.go:638-643` | `s.aliases.Reload()` → `routeAlias / routeFallback` | 其余路径全部走代理转发 |

- `/v1/models` 与 `/models` 同 handler 同响应：`gateways/zgate/internal/router/router.go:2000-2005` 的 `normalizePath` 在 `:2002` 写 `if strings.HasPrefix(path, "/v1") && (len(path) == 3 || path[3] == '/') { path = path[3:] }`，把 `/v1/models` 归一成 `/models`；`:2013-2014` 保留 `?` + RawQuery。测试 `gateways/zgate/internal/router/router_test.go:780-783` 断言 `get("/v1/models")` 与 `get("/models")` 字节相同；`:210-223` TestNormalizePath 覆盖 `/v1/chat/completions`、`/v1`、`/v1/`。
- 其余 `http.HandlerFunc` / `.Handle(` 命中全是 `*_test.go` 的 httptest stub 与 `gateways/zgate/internal/winproc/console_windows.go:86` 的 `var _ = syscall.Handle(0)` 噪音，非路由注册。
- 结论：无 `/metrics`、无模板引擎、无 CORS、无第四个非代理分支。`gateways/zgate/internal/config/config.go:245` 默认 `c.Listen = "127.0.0.1:7871"`。
- `gateways/legacy-router/unified-router.js:354-370` 另有一份 /health（`{"ok":true,"opencode":{"base","key"},"workbuddy":{...},"qoder":{...},"alias":{"path","models"}}`，字段少于 Go 版），它是 Node 回退入口，非 7871 生产，**不作为后台数据面**。

## 3. 实测取活：GET /health 的响应头、完整字段与类型

7871 在跑（未重启）。可复现命令见 §10。

### 3.1 响应头原始输出摘录（curl.exe -s -D - -o NUL，2026-11-12 08:28:15 GMT / 08:31:46 GMT / 08:41:53 GMT 三次一致）

~~~text
HTTP/1.1 200 OK
Content-Length: 2738
Content-Type: application/json; charset=utf-8
Date: Thu, 12 Nov 2026 08:41:53 GMT
__CURL_EXIT__=0
~~~

> 长度随 `uptime_s` / `early` / `hops` 计数器位数浮动 2738–2739 B（pwsh Invoke-WebRequest 一次读到 2739）。`docs/CONSOLE.md:27` 的「1166 字节」是过期快照，非当前契约。

### 3.2 完整顶层字段与类型（pwsh `ConvertFrom-Json` 逐个取 `.GetType().Name` 复现，2026-11-12 约 16:38）

Go `json.Marshal` 按字母序输出，共 **18 个顶层键**：

| 顶层键 | .NET 类型 | 语义 / 样例（脱敏） | 来源 |
| --- | --- | --- | --- |
| `alias` | PSCustomObject | `{"models":18,"path":"C:/Users/<REDACTED-USER>/.zcode/v2/model-alias-map.json"}`（原值含反斜杠） | `router.go:1458-1467` |
| `chain` | PSCustomObject | `{"budget_s":0}` 链预算秒数 | `router.go:1487` |
| `children` | PSCustomObject | `sup.States()` 原样；qoder=`{"idle_s":16370,"in_window":false,"last_error":"","policy":"ondemand","port":8790,"state":"external","windows":["08:58-09:15","20:58-21:15","21:58-22:15"]}`；workbuddy 额外 `"pid":25732,"state":"running"` | `router.go:1458-1467` / `supervisor.go:513-546` |
| `cooling` | Int64 | `1`，冷却中渠道数 | `router.go:1458-1467` |
| `early` | PSCustomObject | `{"committed":40,"enabled":true,"failed_after_wait":0,"keepalive_s":10,"keepalives":499,"passed_in_window":4365,"window_ms":8000,"wrapped":4407}` 提前交卷计数 | `router.go:1480` |
| `gemini` `hajimi` `opencode` `qiniu` `qoder` `qwen` `workbuddy` | PSCustomObject（7 段） | `{"base":"<REDACTED-URL>","child":"","key":true,"last_error":"","state":"up"}`；本地 child 段 `child` 非空、`state` 为 `external`/`running`、额外 `pid` | `router.go:1405-1423,1430-1431,1469-1471` |
| `guard` | PSCustomObject | `{"channels":["OC"],"enabled":true,"mode":"channels","skipping":[]}` 思考守卫档位 | `router.go:1489` |
| `hops` | PSCustomObject | 键格式 `"<channel>|<upstream>|<proxy>"`（如 `"WB|cn:deepseek-v4.1-flash|"`），值 `{"busy":0,"e5xx":0,"no_first_block":0,"ok":N,"silent":0,"try":N}` | `router.go:1490-1494` |
| `ok` | Boolean | `true` | `router.go:1458-1467` |
| `race` | PSCustomObject | `{"disabled":{},"hops":{}}` | `router.go:1475-1476` |
| `upstream` | PSCustomObject | `{"busy":0,"busy_skipped":0,"thinking_strip":0,"truncated_streams":0}` | `router.go:1484` |
| `uptime_s` | Int64 | `26135`（进程启动秒数） | `router.go:1458-1467` |

### 3.3 响应体原始输出摘录（脱敏后；`base` 与本机用户名已按 §0 处理）

~~~json
{"alias":{"models":18,"path":"C:/Users/<REDACTED-USER>/.zcode/v2/model-alias-map.json"},"chain":{"budget_s":0},"children":{"qoder":{"idle_s":15739,"in_window":false,"last_error":"","policy":"ondemand","port":8790,"state":"external","windows":["08:58-09:15","20:58-21:15","21:58-22:15"]},"workbuddy":{"idle_s":3,"in_window":false,"last_error":"","pid":25732,"policy":"ondemand","port":7863,"state":"running","windows":["08:58-09:15","20:58-21:15","21:58-22:15","22:58-23:15"]}},"cooling":1,"early":{"committed":33,"enabled":true,"failed_after_wait":0,"keepalive_s":10,"keepalives":416,"passed_in_window":4298,"window_ms":8000,"wrapped":4334},"gemini":{"base":"<REDACTED-URL>","child":"","key":true,"last_error":"","state":"up"},"guard":{"channels":["OC"],"enabled":true,"mode":"channels","skipping":[]},"hajimi":{"base":"<REDACTED-URL>","child":"","key":true,"last_error":"","state":"up"},"hops":{"WB|cn:deepseek-v4.1-flash|":{"busy":0,"e5xx":0,"no_first_block":0,"ok":4298,"silent":0,"try":4334}},"ok":true,"opencode":{"base":"<REDACTED-URL>","child":"","key":true,"last_error":"","state":"up"},"qiniu":{"base":"<REDACTED-URL>","child":"","key":true,"last_error":"","state":"up"},"qoder":{"base":"http://127.0.0.1:8790/v1","child":"qoder","key":true,"last_error":"","state":"external"},"qwen":{"base":"<REDACTED-URL>","child":"","key":true,"last_error":"","state":"up"},"race":{"disabled":{},"hops":{}},"upstream":{"busy":0,"busy_skipped":0,"thinking_strip":0,"truncated_streams":0},"uptime_s":25504,"workbuddy":{"base":"http://127.0.0.1:7863/v1","child":"workbuddy","key":true,"last_error":"","pid":25732,"state":"running"}}
~~~

### 3.4 关键实现原文（字段语义与「只露 has_key」）

~~~text
gateways/zgate/internal/router/router.go:1405-1423  var healthSegments = map[string]string{"OC":"opencode","WB":"workbuddy","QD":"qoder","QW":"qwen","QN":"qiniu","GM":"gemini","HJ":"hajimi"} + func healthSegmentName(channel string) string（未登记渠道 return strings.ToLower(channel)）
gateways/zgate/internal/router/router.go:1425       func (s *Server) health(w http.ResponseWriter)
gateways/zgate/internal/router/router.go:1426       s.aliases.Reload()
gateways/zgate/internal/router/router.go:1427       states := s.sup.States()
gateways/zgate/internal/router/router.go:1430-1431  hasKey := s.keyset().For(channel) != ""      // 只出 bool，凭据值不出进程
gateways/zgate/internal/router/router.go:1495       writeJSON(w, 200, payload)
gateways/zgate/internal/router/router.go:2564-2573  func writeJSON(w, status int, payload any)：:2569 w.Header().Set("Content-Type", "application/json; charset=utf-8")、:2570 Content-Length、:2571 WriteHeader、:2572 Write
gateways/zgate/internal/router/router.go:2567       兜底 {"error":{"message":"encode failed","type":"proxy_error"}}
gateways/zgate/internal/router/router.go:2575-2577  func errorBody(message, kind string) map[string]any { return map[string]any{"error": map[string]any{"message": message, "type": kind}} }
~~~

`gateways/zgate/internal/supervisor/supervisor.go:513-546` 的 `States()` 逐 child 出 `policy / state / port / idle_s / in_window / windows / last_error`，`:540-542` `if k.proc != nil { entry["pid"] = k.proc.Pid() }`；`state` 取值 `stopped|starting|running|external|error`。

### 3.5 方法约束复现（重要边界）

`serveHTTP` 只判 path、未判 method，所以 /health 对非 GET 方法也回同一 JSON：

~~~text
GET  /health => 200|2738
POST /health => 200|2738   （同一 JSON，非预期写动作）
HEAD /health => 200|0
GET  /models     => 200|2193
GET  /v1/models  => 200|2193   （与上者体首 120 字符相同）
~~~

后台一律按 **GET** 消费 /health；该现象只作契约记录，无需网关变更。

## 4. /v1/models 与 /admin/reload 的方法与响应体

### 4.1 GET /v1/models（= GET /models）

~~~text
HTTP/1.1 200 OK
Content-Length: 2193
Content-Type: application/json; charset=utf-8
Date: Thu, 12 Nov 2026 08:31:46 GMT
~~~

体首与字段类型（pwsh `ConvertFrom-Json`）：

~~~json
{"catalog_total":88,"data":[{"canonical_id":"Beam","chain_hops":2,"group":"免费","id":"Beam","object":"model","owned_by":"zgate"},"...共 18 条..."],"object":"list","owned_by":"zgate","scope":"canonical","total":18}
~~~

| 字段 | 类型 | 语义 |
| --- | --- | --- |
| `object` | String | 固定 `"list"` |
| `owned_by` | String | 固定 `"zgate"` |
| `scope` | String | `canonical` / `legacy` / `all`，缺省 `canonical` |
| `total` | Int64 | 本次返回条数（18） |
| `catalog_total` | Int64 | 全量目录条数（88） |
| `data` | Object[] | 条目字段 `id, object, owned_by, canonical_id, group, chain_hops` |

18 条 canonical id：Beam / Claude-Haiku-5.5 / Conatus / DeepSeek-4.1-Flash / GLM-5.3-Flash / GPT-6-Luna / Gemini-AIS / HY3 / HY3-X / HY4 / HY4-Free / Iceman / MiMo-2.6-Flash / MiniMax-M3.1-Flash / Muse-Spark1.3 / Qwen-3.8-Flash / Qwen-3.8-Max / Space-Bunny。

实现 `gateways/zgate/internal/router/router.go:1511-1543`：`all := s.aliases.Catalog()`；未知 scope 走 `writeJSON(w, 400, errorBody("unknown scope: "+scope+" (want canonical|legacy|all)", "invalid_request_error"))`。实测 `GET /v1/models?scope=nonsense`：

~~~text
HTTP/1.1 400 Bad Request
{"error":{"message":"unknown scope: nonsense (want canonical|legacy|all)","type":"invalid_request_error"}}
~~~

测试 `gateways/zgate/internal/router/router_test.go:766-864` TestModelsIsAggregatedCatalog 覆盖 /v1/models 与 /models 字节相同、scope 三档、unknown scope 400。

### 4.2 POST /admin/reload（唯一写动作，未实发）

硬约束要求不动长驻网关，故**未实发 POST**；响应体由源码 + 测试推导，并实测了 GET 被拒的 405 分支：

~~~text
HTTP/1.1 405 Method Not Allowed
Content-Length: 63
Content-Type: application/json; charset=utf-8

{"error":{"message":"use POST","type":"invalid_request_error"}}
~~~

`gateways/zgate/internal/router/router.go:1965-1988` 原文：

~~~text
:1966-1969  if r.Method != http.MethodPost { writeJSON(w, 405, errorBody("use POST", "invalid_request_error")); return }
:1971       next, err := config.Load(old.Path)   // 失败 400 "配置读取失败: "+err.Error() / "configuration_error"
:1976       ks := keys.Load(next.ProviderConfig, next.WBGatewayConfig, next.QoderEnvFile, next.QwenEnvFile, next.QiniuEnvFile, next.GeminiEnvFile, next.HajimiEnvFile)
:1977       applied, stale, added := s.sup.ApplyConfig(next.Children)
:1978       s.setRuntime(next, ks)
:1979       s.aliases.Reload()
:1981-1987  成功 200 {"ok":true,"applied":applied,"stale":stale,"added":added,"note":"监听地址、新增子进程与 alias map 路径仍需重启 zgate；配置、上游 base 与 key 已热加载"}
~~~

成功体字段：`ok`(bool) / `applied`([]string) / `stale`([]string) / `added`([]string) / `note`(string)。`gateways/zgate/internal/supervisor/supervisor.go:487-510` `func (s *Supervisor) ApplyConfig(cfg map[string]config.Child) (applied, unknownKeep, added []string)`。测试 `gateways/zgate/internal/router/router_test.go:257-304` TestAdminReloadAppliesPolicy：POST 200、`sup.States()["qoder"]["policy"]=="ondemand"`、GET 必须 405（错误原文 `"GET must be rejected, got %d"`）。`docs/ARCHITECTURE.md` 与 AGENTS.md §6 一致：reload 热加载策略 / 空闲 / 窗口 / 上游 base / 凭据，监听地址与新增子进程仍需换版重启。

## 5. /health 消费方全清单与「按什么结构解析」

判据：**/health 默认响应必须永远是 JSON，后台保持网关响应原样**。消费方分三类。

### 5.1 按 JSON 结构解析（Go 侧）

| 文件:行 | 解析结构 |
| --- | --- |
| `gateways/zgate/main.go:337-357` `func probeHealth(listen string) ([]byte, int)` | `client.Get("http://" + host + "/health")`，Timeout 2 s，body 上限 `1<<20`，返回 `(buf, resp.StatusCode)` |
| `gateways/zgate/main.go:295-323` `status()` | `json.Unmarshal(body, &health)`，struct 为 `Alias{Models int json:"models"}` / `UptimeS int json:"uptime_s"` / `Children map[string]any json:"children"`；逐项取 `state/pid/port/idle_s/last_error` |
| `gateways/zgate/main.go:360-384` `func reload() error` | `client.Post("http://"+host+"/admin/reload", "application/json", nil)`，`resp.StatusCode != 200` 报 `"HTTP %d: %s"`，再 `json.Unmarshal(raw, &out)` |
| `gateways/zgate/internal/router/router_test.go:184-208` TestHealthExposesNoKeys | `json.Unmarshal`，失败原文 `"health is not JSON: %s"`；断言 `body["ok"] != true` 与 `body["workbuddy"].(map[string]any)["key"] != true`，泄露报错 `"/health leaked a key: %s"` |
| `gateways/zgate/internal/router/router_test.go:732-764` TestHealthHasEveryChannelSegmentWithState | 遍历 `keys.Channels`，断言每段为 `map[string]any` 且含 `state` / `last_error`，段名唯一 |
| `gateways/zgate/internal/router/upstream_semantics_test.go:120,153,209` | 断言 `/health.upstream.thinking_strip` / `truncated_streams` / `busy` 计数 |

### 5.2 按 JSON 结构解析（新增：已落地 Fluent 2 后台）

| 文件:行 | 解析结构 |
| --- | --- |
| `tools/console/sources.py:150-157` `def _get(path, timeout=2.5)` | `Request(GATEWAY+path, headers={"Accept":"application/json"})` → `resp.read(4<<20)` → `json.loads(raw.decode("utf-8","replace"))`；异常 `raise SourceError("UPSTREAM_DOWN", f"gateway {path}: {type(exc).__name__}: {exc}")`，**非 JSON 直接失败** |
| `tools/console/sources.py:162-175` `def gateway()` | 同时 `_get("/health")` + `_get("/v1/models")`，返回 `health`(`scrub` 后) / `health_bytes` / `health_content_type` / `models` / `models_content_type` / `gateway` / `polling_hint_ms: 5000`；`return cached("gateway", 5000, fn)` |
| `tools/console/sources.py:423-456` `SEGMENTS` + `def overview()` | 按 `h.get("ok")` / `uptime_s` / `(h.get("alias") or {}).get("models")` / `cooling` / `guard` / `scrub(h.get("children") or {})` / `hops` 解析；7 段取 `state/key/child/base`；`return cached("overview", 5000, fn)` |
| `tools/console/server.py:180-211` `def run_check()` | `:206 sources._get("/health")` → `:207 "[check] OK   gateway /health"`，失败只 WARN 不 FAIL |
| `tools/console/static/app.js:73-80` `async function api(path)` | 统一消费 `{ok,generated_at,ttl_ms,data}` 包；非 JSON 报 `code PARSE_ERROR`「响应不是 JSON」 |

### 5.3 只判状态码 / 只判端口（脚本、看门狗、静态门禁）

| 文件:行 | 消费方式 |
| --- | --- |
| `tools/rename-to-modelbus.ps1:214-223` | 循环 40×500 ms `Invoke-WebRequest 'http://127.0.0.1:7871/health' -TimeoutSec 2 -UseBasicParsing`；`if ($resp.StatusCode -eq 200) { $healthy = $true; break }`；`:223 "HEALTH FAIL - rolling back"`。**只判 200，不解析体** |
| `tools/zgate-lifecycle/deploy-zgate.ps1:20,72-77,176` | `:20 [string]$HealthUrl = 'http://127.0.0.1:7871/health'`；`function Test-Health([string]$url) { try { $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3; return ($r.StatusCode -eq 200) } catch { return $false } }`；日志「换版完成：/health 200」。**只判 200** |
| `tools/zgate-lifecycle/ensure-zgate.ps1:2,5-14` | `:2 "ModelBus-zgate-watchdog 每分钟跑一次：7871 不通才调同目录 start-zgate-nw.ps1"`；`$c = New-Object System.Net.Sockets.TcpClient` + `$c.Connect('127.0.0.1', 7871)`；`if (Test-Up) { exit 0 }`。**仅 TCP 端口判活，不发 HTTP** |
| `tools/zgate-lifecycle/start-zgate-nw.ps1:2,16` | 由计划任务经 `ensure-zgate.vbs` 调用，`:16 $port = 7871`；不碰 /health |
| `tools/zgate-lifecycle/install-lifecycle.ps1:15,46-47,66` | `$WatchdogTask = 'ModelBus-zgate-watchdog'`、`$wantWatchArg = '//B //Nologo ' + (Join-Path $LocalDir 'ensure-zgate.vbs')`；看门狗链路全程按端口判活 |
| `tools/check-project.py:103-166` `def check_gateway(results: list) -> None` | **静态源码断言**，不发请求：`:114 'func (s *Server) models('`、`:115 'case "WB", "QD", "QW", "QN", "GM", "HJ"'`、`:128 "if 'var Channels = []string{' not in keyfile"`、`:130 "if 'for _, channel := range keys.Channels' not in router"`、`:132 "if 'func healthSegmentName(' not in router"`、`:134 "if 'func (m *Map) Catalog(' not in alias"`。FAIL 原文：「keys.go: 缺 var Channels：渠道登记点丢失，/health 段表无源可循」「router.go: /health 未遍历 keys.Channels，新增渠道会漏段」「router.go: 缺 healthSegmentName()，渠道到段名的映射丢失」；`:163` OK 文案「网关实现: /v1/models 聚合 + /health 段表由 keys.Channels 驱动 + QN/GM/HJ Bearer 在位」；`:141,168 json.load(f)` 只读本地 zgate.json |

全仓扫描口径：`glob` 得 31 个 `*.ps1`、3 个 `*.vbs`、1 个 `*.cmd`；`*.vbs` 对 `/health|7871|Invoke-WebRequest|StatusCode` 零命中，`*.cmd` 零命中（`ensure-zgate.vbs` / `launch-zgate.vbs` / `sync-models.vbs` 只做 `WScript.Shell.Run(...,0,False)` 隐窗转调 ps1）。`tools/*.py` 的 `urllib` / `json.loads` 命中全是本地文件与上游 API（`tools/model_probe.py:128,135`、`tools/arena_leaderboard.py:110-118`、`tools/model_alias.py:983-988`、`tools/caps_upstream.py:57-64`、`tools/model_stream_check.py:237,265`），与 /health 无关。全仓代码命中（已滤 docs/evidence/.work）：`*.py` 13 处、`*.go` 40 处、`*.js` 2 处、`*.ts` 0 处。

> 判据落地：既有脚本只判 200 或端口，Go 侧与新增后台都按 JSON 结构解析；`tools/console/sources.py` 的 `json.loads` 与 `router_test.go:184-208` 的 `"health is not JSON: %s"` 共同把「/health 默认响应必须永远是 JSON」变成硬约束。后台保持 7871 响应原样即可满足全部消费方。

## 6. 重大发现：tools/console/ 已落地 Fluent 2 后台，是新增 /health 消费方

`git status --porcelain` 出现 `?? tools/console/`；`git ls-files tools/console` 为空（HEAD=95b3b3c）。共 8 文件：`sources.py` / `actions.py` / `server.py` / `start-console.ps1` / `static/{index.html,app.css,app.js,favicon.svg}`。

- `tools/console/sources.py:26` `GATEWAY = os.environ.get("MODELBUS_GATEWAY", "http://127.0.0.1:7871").rstrip("/")`；`:29-33` `SECRET_NAME = re.compile(r"(?i)(token|secret|cookie|passwd|password|credential|authorization|api[_-]?key|private|sk-)")` + `SECRET_VALUE`（sk- / Bearer）+ `MASK = "<redacted>"`；`:114-122` `def scrub(obj)` 把命中凭据名的键值换 MASK。采集器 TTL：gateway/overview/logs 5000、traffic 15000、aliases/probe/models/ops 30000、scores/quota/prices/accounts/config 60000、arena 300000。`:309-342 accounts()` 只报 `credential_present` 布尔、uid 用 `_mask_id`、`"provider_config": {"present", "values": "never exported"}`；`:361-381 config()` env 只报 `configured` 布尔。
- `tools/console/server.py`：`:28-42` 13 条 `/api/*` 路由；`:52 PORT = 7872`；`:71-82` Host/Origin 白名单只放 `127.0.0.1` / `localhost` / `[::1]`（:7872）；`:84-98` `Cache-Control: no-store` / `X-Content-Type-Options: nosniff` / `Referrer-Policy: no-referrer`；`:127-129` 自身 `/healthz` 返回 `{"service":"console","port":PORT,"gateway":sources.GATEWAY}`；`:168-177` 唯一写面 `POST /api/actions/reload`。
- `tools/console/actions.py:1-6,29-57`：文档串「只允许把 POST /admin/reload 转发给网关，其他动作一律不落地…不重启进程、不写配置、不碰凭据」；`reload_gateway()` 用 `Request(sources.GATEWAY + "/admin/reload", data=b"{}", method="POST", ...)`，`urlopen(timeout=10)`、`json.loads` 后 `sources.scrub`、`entry["ok"] = 200 <= status < 300`；并发抛 `SourceError("JOB_BUSY", "reload already running")`，history 上限 20。
- 前端已按 Fluent 2：`tools/console/static/app.css:1-3`「ModelBus 控制台 · Fluent 2 设计规则」「令牌命名对齐 Fluent UI v9 / Fluent 2 Web 语义（colorNeutral* / colorBrand* / colorPalette* / shadow*）」；`:8-20` Neutral（`--mb-fg-1:#242424` / `--mb-stroke-1:#D1D1D1` / `--mb-bg-1:#FFFFFF`）、`:23-27` Brand（`#0F6CBD` / `#115EA3` / `#0C3B5E` / `#EBF3FC`）、`:41-53` Radius/Spacing/Type/Shadow 与 `--mb-font:"Segoe UI Variable"`。`app.js:7-16` 8 页（overview/models/prices/health/traffic/accounts/logs/ops）；`index.html:35,44,54`「重载网关」按钮、确认弹窗、页脚「只读后台 · 绑 127.0.0.1 · 网关响应保持原样 · 凭据值不出进程」。
- 自检实测（只读，未启动常驻服务）：

~~~text
$ python tools/console/server.py --check
[check] static bytes = 44105 (budget 200 KB)
[check] OK   /api/overview ...（13 个 /api/* 全 OK）
[check] OK   gateway /health
[check] result = PASS (0 failure(s))
EXIT=0
~~~

紧接着 `curl.exe -s -D - --max-time 5 http://127.0.0.1:7871/health -o NUL` → `HTTP/1.1 200 OK` / `Content-Length: 2738` / `Content-Type: application/json; charset=utf-8` / `Date: Thu, 12 Nov 2026 08:41:53 GMT` / `CURL_EXIT=0`，证实自检后 7871 契约未变。

> 文档冲突（A 路按边界未写 docs/，由主线对齐）：`docs/CONSOLE.md:3,5,15` 仍写「MD3 单页后台」「设计稿 v1（2026-11-10），尚未落地」「Beer CSS 5」；`:27` 写「/health 只出 JSON，1166 字节」；`:29,41,43` 的三端点表、`aliases.Reload()` ≥5 s 轮询、reload `{ok, applied, stale, added, note}` 与实测一致；`docs/README.md:33` 索引也写 MD3。已两次 `send_message` 回报父代理（`a9b34ab4-fe61-430b-b40b-b77edba41f8c`、`db468d9b-7a7e-493f-a182-972ab4a9eff4`），主线回告已完成正本改写与门禁，落盘时 `git status --porcelain` 已显示 ` M docs/CONSOLE.md` / ` M docs/README.md`；本分片保留核查时的原始证据行号，便于复核历史差异。

## 7. docs 对齐（字段语义）

- `docs/ARCHITECTURE.md:114`：/health 七段 upstream 各带 `base / key / child / state / last_error`（本地 child 取 `sup.States()`，远程由 key 推 `up` / `no_key`），`children` 段是 `sup.States()` 原样（含 `state / pid / idle_s / last_error`）。与 §3.2 逐项吻合。
- `docs/ARCHITECTURE.md:159-160`：/health 已落地为统一视图，七段 upstream（OC / WB / QD / QW / QN / GM / HJ）加 `children`、`alias.models`、`cooling`、`uptime_s`，以及 2026-11-10 新增的 `early`（提前交卷计数）、`chain`（链预算）、`guard`（思考守卫档位）；GET /v1/models 返回 alias 聚合 catalog，`?scope=` 分 canonical / legacy / all（缺省 canonical）。与 §3、§4 吻合。
- `docs/ARCHITECTURE.md:92` zgate serve 监听 7871；`:94` `zgate status --json`；`:415-417` watchdog /health 不通就拉回（与 §5.3 的 `ensure-zgate.ps1` 端口判活互补）。
- `docs/CONSOLE.md` 全文 360 行已读：`:14` 独立 `127.0.0.1:7872`、`:16` 8 个页面、`:41` 表注「每次请求都会 aliases.Reload()，轮询间隔必须 ≥ 5s」、`:73-81` 列 5 个 /health 消费方并结论「/health 的默认响应永远是 JSON」、`:99` P3 可选 Accept: text/html → 302（约 10 行 + 换版，本次未启用，故零改动成立）、`:204-237` API 契约、`:279-288` 脱敏、`:331-340` 验收（含「/health 契约不变」「`grep -iE 'apikey|token|cookie|secret|sk-'` 零命中」）。`:73-81` 的 5 个消费方需补上 `tools/console/sources.py` 这一新增消费方。

## 8. 后台可消费数据契约表

| 端点 | 方法 | 字段 | 语义 | 建议刷新频率 | 脱敏红线 |
| --- | --- | --- | --- | --- | --- |
| `/health` | GET（POST/HEAD 亦回同一 JSON，后台只按 GET 消费） | `ok`, `uptime_s`, `alias.models`, `alias.path`, `children.*`, `cooling`, `early.*`, `chain.budget_s`, `guard.*`, `hops.*`, `race.*`, `upstream.*`, 7 段 `{base,key,child,state,last_error}` | 网关统一运行视图：存活、进程启动秒数、alias 条数、子进程状态、冷却数、提前交卷计数、链预算、思考守卫、逐跳计数、竞速快照、上游信号计数、七渠道状态 | **≥ 5 s**（`health()` 首行 `aliases.Reload()` 重读文件；已落地后台 `cached("gateway",5000,fn)`）；指标看板 5 s，逐跳 trend 15 s | `key` 只可展示 `true/false`（源码只算 `hasKey`）；`base` 上游 URL 出报告/公开页面一律 `<REDACTED-URL>`；`alias.path` 含本机用户名，出报告脱敏 `<REDACTED-USER>`；`last_error` 可能含上游报错串，展示前过 `scrub`；`children.*.pid` 属本机进程信息，对外页面可只留 `state` |
| `/v1/models`（= `/models`，`?scope=canonical|legacy|all`） | GET | `object`, `owned_by`, `scope`, `total`, `catalog_total`, `data[]{id,object,owned_by,canonical_id,group,chain_hops}` | alias 聚合目录；`canonical` 缺省（实测 18/88），`all` 出全量 | **30 s 起**（目录变更低频；已落地 `/api/models` TTL 30000）；用户手动切 scope 时按需取，非法 scope 返回 400 `errorBody` | `group` 为业务分组文案（如「免费」），无凭据；`id` 为模型别名，按原样展示；`canonical_id` 不得与上游 key 拼接展示 |
| `/admin/reload` | **POST only**（GET 实测 405） | 成功 `{ok,applied,stale,added,note}`；失败 400 `{error:{message,type}}`；`keys.Load` 六通道 + `ApplyConfig(children)` + `aliases.Reload()` | 热加载策略 / 空闲 / 窗口 / 上游 base / 凭据；监听地址、新增子进程、alias map 路径仍需换版重启 | **仅用户显式点击时触发**，禁止后台定时轮询；已落地 `actions.reload_gateway()` 有 `JOB_BUSY` 并发闸 + history 上限 20 | 请求体固定 `b"{}"`；响应 `note` 为固定文案；`applied/stale/added` 只含 child 名；任何 key/token/口令都不进请求、不进日志、不进前端 history（`sources.scrub` 统一兜底） |
| `（后台自身）` `/api/gateway` `/api/overview` 等 13 条 + `/healthz` | GET | `{ok,generated_at,ttl_ms,data}` 包；`health_bytes` / `health_content_type` / `polling_hint_ms` | 后台 127.0.0.1:7872 对 7871 的只读投影，Host/Origin 白名单 + `no-store` | 见 `server.py:28-42` 逐路由 TTL | 后台自身 `/healthz` 回显 `sources.GATEWAY`（默认 `http://127.0.0.1:7871`），无凭据；`accounts/config` 只出 `credential_present` / `configured` 布尔 |

补充红线：后台对外响应统一过 `grep -iE 'apikey|token|cookie|secret|sk-'` 须零命中；`sources.py:29-33,114-122` 的 `SECRET_NAME` / `SECRET_VALUE` / `scrub` 把 `token|secret|cookie|passwd|password|credential|authorization|api[_-]?key|private|sk-` 命中键整体替换为 `<redacted>`；`docs/CONSOLE.md:279-288,331-340` 同口径。

## 9. 明确结论：网关是否需要零改动

**需要零改动。** 依据链：

1. 数据面完备：`router.go:583-594` 三个非代理分支已覆盖「指标（/health）+ 目录（/v1/models）+ 唯一写动作（POST /admin/reload）」；`normalizePath` 让 `/v1/models` 与 `/models` 等价，无需新增路由。
2. 契约稳定：`writeJSON` 统一 `application/json; charset=utf-8` + `Content-Length`，无 Accept 分支；7 段由 `keys.Channels` + `healthSegmentName` 驱动，新增渠道自动出段（`tools/check-project.py:128-132` 静态守门），后台无需网关为新字段开洞。
3. 消费方兼容：既有脚本只判 200 / 端口，Go 侧按 `json.Unmarshal` 结构解析，`tools/console/sources.py` 按 `json.loads` + `scrub` 解析；所有消费方都要求 JSON 原样。后台改 7871 响应会同时破坏 `router_test.go:184-208`、`main.go:295-323` 与 `sources.py:150-157`。
4. 已落地实现自证：`tools/console/` 在零网关改动前提下 `server.py --check` exit 0、13 条 `/api/*` 全 OK、`[check] OK   gateway /health`；`actions.py` 唯一写动作只转发 POST /admin/reload。
5. 资源面同理：`health()` 每次 `aliases.Reload()`，把后台轮询压到 ≥5 s 即可，无需在网关侧加缓存或新端点；`docs/CONSOLE.md:99` 的 Accept: text/html → 302 属可选 P3，本次未启用。

因此后台边界 = **独立 127.0.0.1:7872 只读进程 + 三个既有端点 + ≥5 s 轮询 + 凭据只露布尔**，7871 监听、响应、进程与配置全部保持原样。

## 10. 可复现命令清单（Windows PowerShell 7 / CMD 均可整行复制）

~~~powershell
cd /d F:ProjectModelBus
git rev-parse --show-toplevel
git status --porcelain
curl.exe -s -D - -o NUL --max-time 5 http://127.0.0.1:7871/health
curl.exe -s --max-time 5 http://127.0.0.1:7871/health
curl.exe -s -D - -o NUL --max-time 5 http://127.0.0.1:7871/v1/models
curl.exe -s --max-time 5 http://127.0.0.1:7871/v1/models
curl.exe -s -D - --max-time 5 http://127.0.0.1:7871/v1/models?scope=nonsense
curl.exe -s -D - --max-time 5 http://127.0.0.1:7871/admin/reload
curl.exe -s -o NUL -w "%{http_code}|%{size_download}" -X POST --max-time 5 http://127.0.0.1:7871/health
python tools/console/server.py --check
git ls-files tools/console
~~~

路由与消费方静态复核（`grep` 用仓内工具，ugrep 语法）：

~~~powershell
Select-String -Path gatewayszgateinternalouterouter.go -Pattern 'path == "/health"','path == "/models"','path == "/admin/reload"','func writeJSON','func healthSegmentName' | ForEach-Object { "$($_.Path):$($_.LineNumber): $($_.Line.Trim())" }
Select-String -Path toolsconsolesources.py -Pattern 'MODELBUS_GATEWAY','json.loads','polling_hint_ms','def scrub' | ForEach-Object { "$($_.Path):$($_.LineNumber): $($_.Line.Trim())" }
Select-String -Path toolscheck-project.py -Pattern 'var Channels','for _, channel := range keys.Channels','func healthSegmentName' | ForEach-Object { "$($_.Path):$($_.LineNumber): $($_.Line.Trim())" }
~~~

> `curl.exe -w` 的 `%{http_code}` / `%{size_download}` 在 PowerShell 里放在双引号内可原样传给 curl；若用 CMD 直接跑则去掉外层引号转义即可。所有命令均为只读探测，未重启任何服务、未实发 POST /admin/reload。

## 11. 外部事实卡（用于「后台设计规则 Fluent 2」对齐）

| 来源 URL | 确切值 | 适用版本 | 查证时间 | 用于哪步 |
| --- | --- | --- | --- | --- |
| `gh api repos/microsoft/fluentui --jq '{full_name, stargazers_count, pushed_at, license: .license.spdx_id, default_branch}'` | `{"default_branch":"master","full_name":"microsoft/fluentui","license":"NOASSERTION","pushed_at":"2026-11-12T01:42:15Z","stargazers_count":20400}`；tags 前 8 = v6.0.0-beta1 / v4.40.2-hotfix2 / v0.70.0 / v0.69.0 / v0.69.0-hotfix1 / v0.68.1 / v0.68.0 / v0.67.0 | microsoft/fluentui 当前 master | 2026-11-12 16:43:32 +08:00 | §6 核对已落地后台的 Fluent 2 体系归属与选库基线 |
| `https://fluent2.microsoft.design/color-tokens` | `colorNeutralBackground1` / `colorNeutralForeground1` / `colorNeutralStroke1` / `colorBrandBackground` 等别名令牌按 neutral / brand / status / generic 分组；light 用 white、grey[16] 等全局色，dark 用 grey[96] 等 | Fluent 2 Design System（官方） | 2026-11-12 16:43 | §6 核对 `tools/console/static/app.css:8-39` 语义令牌命名 |
| `https://learn.microsoft.com/power-apps/developer/component-framework/fluent-modern-theming` | 平台主题使用 Fluent UI v9 tokens；示例 `<platform-library name="Fluent" version="9.46.2" />`、`import { makeStyles, tokens } from "@fluentui/react-components"` | Power Apps 现代主题文档 | 2026-11-12 16:43 | §6 确认 Fluent 2 Web = Fluent UI v9 令牌体系 |
| `https://github.com/microsoft/fluentui/blob/master/packages/tokens/src/types.ts` + `https://open-design.ai/design-system/microsoft-fluent` | `colorBrandBackground=#0f6cbd`、`Hover=#115ea3`、`Pressed=#0c3b5e`、`Background2=#ebf3fc`；`colorNeutralForeground1=#242424` / `2=#424242`；`colorNeutralStroke1=#d1d1d1` / `2=#e0e0e0`；`colorNeutralBackground1=#ffffff` / `2=#fafafa` / `3=#f5f5f5`；`fontFamilyBase='Segoe UI'` | Fluent UI v9 webLightTheme（brandWeb 解析值） | 2026-11-12 16:43 | §6 与 `app.css:8-53` 逐项比对，判定已落地后台符合 Fluent 2 |

## 12. 边界、未验证项与既有用户改动

- **未验证项**：POST /admin/reload 的成功响应体未实发（硬约束：不动长驻网关、不重启服务），由 `router.go:1965-1988` + `router_test.go:257-304` + `docs/ARCHITECTURE.md` 推导；GET 405 分支已实测。若主线需要端到端，请在受控换版窗口执行并单独留证。
- **长度浮动**：`Content-Length` 2738–2739 B 随计数器位数变化；`docs/CONSOLE.md:27` 的 1166 B 为过期快照。
- **legacy 回退**：`gateways/legacy-router/unified-router.js:354-370` 的 /health 字段较少，非 7871 生产，后台以 Go 版为唯一数据面。
- **既有用户改动（只记录，未触碰）**：`git status --porcelain` = ` M docs/reports/README.md`、`?? docs/reports/MODEL-SYNC-20261112-1209.md`、`?? evidence/go-model-sync-20261112-120012.md`、`?? tools/console/`（后者为本轮发现的已落地后台）。本分片写入后新增 `?? evidence/agent-endpoints.md`。
- **过程教训**：`grep` 带 `include: "*.mjs"` / `"*.sh"` 在空匹配时报 `rg: No files were searched, which means ripgrep probably applied a filter you didn't expect.`（exit 2）；对可能零文件的 include 一律用容错包裹。`run_code` 内 PowerShell 命令含反引号或 JS 正则 `(?i)` 会触发语法错，改用普通字符串数组拼接命令、JS 侧用大小写无关拆分脱敏。
- **分片自校验**：`Select-String -LiteralPath evidence/agent-endpoints.md -Pattern 'apikey|token=|cookie=|secret=|sk-[A-Za-z0-9]'` 得 `SECRET_HITS=2`，两处命中分别为 §7 与 §8 里引用的**门禁规则字面量**（`grep -iE 'apikey|token|cookie|secret|sk-'` 与 `SECRET_NAME` 正则说明），不是真实凭据；该门禁约束的是后台对外响应体，本分片未写入任何 key / token / 口令。行数两种口径：`Measure-Object -Line` = 238（不含空行），`[System.IO.File]::ReadAllLines` = 318（含 80 个空行），物理行数以 318 为准。

---

**分片状态**：A 路完成。产物唯一：`evidence/agent-endpoints.md`。网关零改动结论已成立，后台数据面边界已定。
