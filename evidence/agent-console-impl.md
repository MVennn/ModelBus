# ModelBus 控制台实现代码静态审查分片

> 结论先行：本分片逐文件通读了 F:\Project\ModelBus\tools\console\ 下 13 个文件（10 个文本文件全量 read、3 个 .pyc 取二进制元数据），核对了 7871 /health 与 /v1/models 的只读实测、网关路由源码与 .gitignore，产出 8 项要求的清单/数字/命令原文/退出码。实现整体是「独立 loopback 只读服务 + 唯一 reload 转发」，未发现改网关 /health 响应或启停 zgate 的代码；但存在 3 个会直接影响「数据对得上 / 能启动 / 能排障」的静态缺陷（见下），且自检门禁对网关不可达假绿。

## 三条最关键发现

1. **网关状态灯会把失败当在线** — tools/console/static/app.js:356 `setGatewayDot(bag["/api/gateway"] ? true : (bag["/api/overview"] ? !bag["/api/overview"].__err : undefined));`。all() 对失败返回 `{ __err: s.reason }`（truthy 对象），健康页只要请求过 /api/gateway，无论 502 都显示「网关在线」；总览页则因 bag 对象 truthy 走 `!__err` 为 false 显示「网关不可达」。这是「数据对不上」的直接来源。
2. **-Detach 没有停止方式，且提示用户看错日志文件** — tools/console/start-console.ps1:18-29 无 -PassThru / PID 文件 / Stop 分支 / 端口就绪探测；:27 只提示 `$out = .work/console.stdout.log`，但 tools/console/server.py:70 `sys.stderr.write("[console] %s - %s\n" % (self.address_string(), fmt % args))` 把全部访问日志写进 `$err = .work/console.stderr.log`。Start-Process 成功 ≠ 7872 已 listen，排障时按提示打开 stdout 只能看到 server.py:248 那一行启动语。
3. **自检假绿 + 数据面无单侧降级 + POST 无兜底** — tools/console/server.py:211-230 对 `UPSTREAM_DOWN` 只 WARN 不 FAIL，网关挂了 `--check` 仍 `result = PASS (0 failure(s))`；tools/console/sources.py:165-178 的 /api/gateway 串行 GET /health 与 /v1/models，任一失败整接口 502，sources.py:252-263 的 /api/prices 两个 JSON 任一缺失整页 404；tools/console/server.py:175-184 的 do_POST 只捕获 `sources.SourceError`，没有 do_GET:151-152 的 `except Exception` 兜底，异常时返回裸 HTML 500，前端 api() 显示「响应不是 JSON」。

## 0. 分片信息与取证口径

- subagentId：console-impl（由 lead 委派，delegation depth 1/1，剩余 0，未再派子代理）。
- 唯一写域：F:\Project\ModelBus\evidence\agent-console-impl.md；未改 PROGRESS.md / docs/ / tests/ / 配置 / tools/console/ 源码 / gateways/。
- 时间：2026-11-12 19:04–19:13 +08:00。lead 于 m00027 要求：「主线已独立跑完 v3 自检与 E2E 39 项全 PASS、浏览器渲染通过，准备结案。请立刻把你的静态审结论落到 F:\Project\ModelBus\evidence\agent-console-impl.md 并结束；若工具卡住就直接回报当前结论，不要继续展开检索。」→ 收到后停止检索，直接落盘。
- 静态范围：glob `tools/console/**/*` 得 13 个文件（见 §1）。server.py / sources.py / actions.py / start-console.ps1 / static/index.html / static/app.css / static/app.js / static/favicon.svg / static/vendor/LICENSE-tabler.txt 全量 read；static/vendor/tabler.min.css 全量 read 但第 7 行超长被 read 截断（见 §9）；3 个 .pyc 为二进制编译缓存，未逐字节人工通读，仅取长度/magic/mtime。
- 未做：未启动 7872 控制台、未启停 7871 zgate 长驻网关、未改 /health 响应、未执行 POST /admin/reload、未执行 git add / commit / push、未改任何源文件。对 7871 只发了 3 个只读 GET（/health、/v1/models、/models）。
- 一次索引副作用（如实记录）：按仓内 AGENTS.md §3 先跑 `codegraph status 'F:\Project\ModelBus'`（exit 0，Pending Changes: Modified: 2 files），再跑 `codegraph sync 'F:\Project\ModelBus'`（exit 0，Synced 2 changed files）。.codegraph/ 由 .gitignore:65 排除，非源码/配置改动。
- 3 个 .pyc 的 mtime 为 2026-11-12T19:06:00+08:00，非本分片生成（本分片未执行 server.py）；.gitignore:52-53 已排除 __pycache__/ 与 *.py[cod]。

## 0.1 用到的原始命令与退出码

全部为 pwsh 原生 PowerShell；未起任何子进程，未使用 Start-Process；下列命令均只读。

~~~text
[C1] Get-ChildItem -LiteralPath 'F:\Project\ModelBus\tools\console' -Recurse -File | Sort-Object FullName | ForEach-Object { '{0}|{1}' -f $_.FullName, $_.Length }
exitCode=0
输出：13 行，每行 <绝对路径>|<字节>，与 §1 表一致。

[C2] Get-ChildItem -LiteralPath 'F:\Project\ModelBus\tools\console' -Recurse -File | Sort-Object FullName | ForEach-Object { $p=$_.FullName; $rel=$p.Substring('F:\Project\ModelBus\'.Length); $b=$_.Length; if ($_.Extension.ToLowerInvariant() -eq '.pyc') { $n='N/A(binary)' } else { $n=(Get-Content -LiteralPath $p).Count }; '{0}|bytes={1}|lines={2}' -f $rel,$b,$n }
exitCode=0
输出（节选，全量见 §1）：
tools\console\actions.py|bytes=2086|lines=57
tools\console\server.py|bytes=10175|lines=259
tools\console\sources.py|bytes=18586|lines=459
tools\console\start-console.ps1|bytes=1013|lines=32
tools\console\static\app.css|bytes=10717|lines=194
tools\console\static\app.js|bytes=26427|lines=419
tools\console\static\favicon.svg|bytes=247|lines=4
tools\console\static\index.html|bytes=4328|lines=91
tools\console\static\vendor\LICENSE-tabler.txt|bytes=1247|lines=25
tools\console\static\vendor\tabler.min.css|bytes=686736|lines=8
tools\console\__pycache__\actions.cpython-312.pyc|bytes=3761|lines=N/A(binary)
tools\console\__pycache__\server.cpython-312.pyc|bytes=16416|lines=N/A(binary)
tools\console\__pycache__\sources.cpython-312.pyc|bytes=32344|lines=N/A(binary)

[C3] try { $r=Invoke-WebRequest -Uri 'http://127.0.0.1:7871/health' -Method Get -UseBasicParsing -TimeoutSec 5; $c=$r.Content; $j=$c | ConvertFrom-Json; $keys=($j.PSObject.Properties.Name) -join ','; 'STATUS={0}|CTYPE={1}|BODYCHARS={2}|RAWLEN={3}|TOPKEYS={4}' -f $r.StatusCode,$r.Headers['Content-Type'],$c.Length,$r.RawContentLength,$keys } catch { 'ERR=' + $_.Exception.Message }
exitCode=0
输出：STATUS=200|CTYPE=System.String[]|BODYCHARS=2741|RAWLEN=2741|TOPKEYS=alias,chain,children,cooling,early,gemini,guard,hajimi,hops,ok,opencode,qiniu,qoder,qwen,race,upstream,uptime_s,workbuddy
说明：CTYPE=System.String[] 是 PowerShell 把 Headers 值数组直接 -f 格式化出的类型名，不是网关真实头；[C4] 用 -join ';' 修正。

[C4] $r=Invoke-WebRequest -Uri 'http://127.0.0.1:7871/health' -UseBasicParsing -TimeoutSec 5; $j=$r.Content | ConvertFrom-Json; 'CTYPE={0}' -f ($r.Headers['Content-Type'] -join ';'); foreach($name in 'workbuddy','qoder','qwen','qiniu','gemini','hajimi','opencode'){ $s=$j.$name; if($null -eq $s){'{0}=ABSENT' -f $name; continue}; $keys=($s.PSObject.Properties.Name) -join ','; $kv=($s.PSObject.Properties | Where-Object { $_.Name -match 'key|secret|token|auth' } | ForEach-Object { '{0}:{1}:len={2}' -f $_.Name, ($(if($null -eq $_.Value){'null'}else{$_.Value.GetType().Name})), ($(if($_.Value -is [string]){$_.Value.Length}else{0})) }) -join '|'; '{0}|keys={1}|sensitive={2}' -f $name,$keys,$kv }; 'TOPKEYCOUNT={0}' -f $j.PSObject.Properties.Count
exitCode=0
输出：
CTYPE=application/json; charset=utf-8
workbuddy|keys=base,child,key,last_error,pid,state|sensitive=key:Boolean:len=0
qoder|keys=base,child,key,last_error,state|sensitive=key:Boolean:len=0
qwen|keys=base,child,key,last_error,state|sensitive=key:Boolean:len=0
qiniu|keys=base,child,key,last_error,state|sensitive=key:Boolean:len=0
gemini|keys=base,child,key,last_error,state|sensitive=key:Boolean:len=0
hajimi|keys=base,child,key,last_error,state|sensitive=key:Boolean:len=0
opencode|keys=base,child,key,last_error,state|sensitive=key:Boolean:len=0
TOPKEYCOUNT=1
说明：7 段均含 key 且类型为 Boolean（存在性，无字符串值），符合凭据只记 has_key 的硬约束；TOPKEYCOUNT=1 是 PowerShell 对单个 PSCustomObject 取 .Count 的语义，实际 /health 顶层字段以 [C3] 的 TOPKEYS 18 个为准。

[C5] foreach($u in @('http://127.0.0.1:7871/v1/models','http://127.0.0.1:7871/models')){ try{ $r=Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 5; $j=$r.Content | ConvertFrom-Json; $n=if($j.data){@($j.data).Count}else{@($j).Count}; '{0}|STATUS={1}|CTYPE={2}|LEN={3}|TOP={4}|N={5}' -f $u,$r.StatusCode,($r.Headers['Content-Type'] -join ';'),$r.RawContentLength,(($j.PSObject.Properties.Name) -join ','),$n }catch{ '{0}|ERR={1}' -f $u,$_.Exception.Message } }
exitCode=0
输出：
http://127.0.0.1:7871/v1/models|STATUS=200|CTYPE=application/json; charset=utf-8|LEN=2193|TOP=catalog_total,data,object,owned_by,scope,total|N=18
http://127.0.0.1:7871/models|STATUS=200|CTYPE=application/json; charset=utf-8|LEN=2193|TOP=catalog_total,data,object,owned_by,scope,total|N=18

[C6] $p='F:\Project\ModelBus\tools\console\static\vendor\tabler.min.css'; $t=Get-Content -LiteralPath $p -Raw; $urls=[regex]::Matches($t,'https?://[^\s"''\)\]\<>,;]+') | ForEach-Object { $_.Value } | Sort-Object -Unique; 'URLS=' + ($urls -join '|'); 'URL_COUNT=' + $urls.Count; 'DATA_URI_COUNT=' + ([regex]::Matches($t,'url\(\s*["'']?data:')).Count; 'URL_FUNC_COUNT=' + ([regex]::Matches($t,'url\(')).Count; 'IMPORT_COUNT=' + ([regex]::Matches($t,'@import')).Count; 'FONT_FACE_COUNT=' + ([regex]::Matches($t,'@font-face')).Count; 'SOURCEMAP=' + ([regex]::Matches($t,'sourceMappingURL=([^\s*]+)') | ForEach-Object { $_.Groups[1].Value } | Select-Object -First 1)
exitCode=0
输出：URLS=http://www.w3.org/2000/svg|https://github.com/tabler/tabler/blob/master/LICENSE|https://tabler.io
URL_COUNT=3
DATA_URI_COUNT=25
URL_FUNC_COUNT=25
IMPORT_COUNT=0
FONT_FACE_COUNT=0
SOURCEMAP=tabler.min.css.map

[C7] Get-ChildItem -LiteralPath 'F:\Project\ModelBus\tools\console\__pycache__' -File | Sort-Object Name | ForEach-Object { $b=[System.IO.File]::ReadAllBytes($_.FullName); $magic=($b[0..3] | ForEach-Object { $_.ToString('X2') }) -join ' '; '{0}|bytes={1}|mtime={2}|magic={3}|flags={4}' -f $_.Name,$_.Length,$_.LastWriteTime.ToString('o'),$magic,([BitConverter]::ToString($b[4..7])) }
exitCode=0
输出：actions.cpython-312.pyc|bytes=3761|mtime=2026-11-12T19:06:00.1392994+08:00|magic=CB 0D 0D 0A|flags=00-00-00-00（server/sources 两行同 magic，字节 16416 / 32344）。

[C8] codegraph status 'F:\Project\ModelBus' -> exitCode=0；codegraph sync 'F:\Project\ModelBus' -> exitCode=0，Synced 2 changed files。
[C9] grep 工具：pattern "TODO|FIXME|XXX|HACK|WIP|未完成|待补" path tools/console -> matches: []（全目录零 TODO 标记）。
[C10] grep 工具：pattern "https?://|@import|url\(|<script|<link|src=|href=" path tools/console/static -> 命中见 §6。
[C11] grep 工具：pattern "admin/reload|/health|/v1/models" path gateways/zgate include *.go -> gateways/zgate/internal/router/router.go:583-585、:591-594 等，见 §8。
[C12] glob 工具：pattern "tools/console/**/*" -> 13 个路径；who_claims("evidence/agent-console-impl.md") -> 「无人占用」；claim_status -> 「当前没有登记的会话」。
~~~

## 1. 文件清单表（文件名 / 字节 / 行数 / 职责一句话）

字节与行数来自 [C1]/[C2]（pwsh Get-ChildItem.Length + Get-Content.Count，exit 0）。路径相对 F:\Project\ModelBus\。

| 文件名 | 字节 | 行数 | 职责一句话 |
|---|---:|---:|---|
| tools/console/server.py | 10175 | 259 | HTTP 层：ThreadingHTTPServer 路由、Host/Origin 校验、envelope、静态托管、SSE、--check 自检。 |
| tools/console/sources.py | 18586 | 459 | 只读数据层：13 个采集器把磁盘快照 / 网关 GET / 日志尾部收敛成脱敏结构。 |
| tools/console/actions.py | 2086 | 57 | 唯一写面：转发 POST /admin/reload 并留内存态动作记录。 |
| tools/console/start-console.ps1 | 1013 | 32 | 启动器：-Check 自检、前台运行、-Detach 隐窗后台与日志重定向。 |
| tools/console/static/index.html | 4328 | 91 | 单页骨架：侧栏 / 页头 / 8 页容器 / 重载确认弹层。 |
| tools/console/static/app.css | 10717 | 194 | 手写 Fluent 2 语义令牌（--mb-*）与到 Tabler --tblr-* 的桥接、项目专有类。 |
| tools/console/static/app.js | 26427 | 419 | hash 路由 8 页、envelope 消费、表格/KPI 渲染、SSE、主题、reload 弹层。 |
| tools/console/static/favicon.svg | 247 | 4 | 纯内联 SVG 图标，零外链。 |
| tools/console/static/vendor/tabler.min.css | 686736 | 8 | 本地 vendor 的 Tabler v1.7.4 压缩 CSS（第 7 行为 686k 单行）。 |
| tools/console/static/vendor/LICENSE-tabler.txt | 1247 | 25 | MIT 许可证与版本/来源说明文本。 |
| tools/console/__pycache__/server.cpython-312.pyc | 16416 | N/A（二进制） | CPython 3.12 编译缓存，非源码，.gitignore 排除。 |
| tools/console/__pycache__/sources.cpython-312.pyc | 32344 | N/A（二进制） | 同上。 |
| tools/console/__pycache__/actions.cpython-312.pyc | 3761 | N/A（二进制） | 同上；三者 magic 均 CB 0D 0D 0A（[C7]）。 |

合计 13 个文件；10 个文本文件按上表行数相加为 1548 行。

## 2. server.py 路由表 / 监听 / 只读性

### 2.1 返回体结构（原文 server.py:56-62）

~~~text
def ok_envelope(data, ttl_ms):
    return {"ok": True, "generated_at": sources._now(), "ttl_ms": ttl_ms, "data": data}

def err_envelope(code, message):
    return {"ok": False, "generated_at": sources._now(), "ttl_ms": 0,
            "data": None, "error": {"code": code, "message": message}}
~~~

静态资源走 _serve_static（server.py:103-122）：原始文件字节 + 对应 Content-Type + Cache-Control: no-cache；SSE 走 text/event-stream；do_HEAD 设 self._head=True 后复用 do_GET，输出 Content-Length 0 的空 body。

### 2.2 路由逐条（方法 + 路径 + 处理函数 + 返回体）

| 方法 | 路径 | 处理函数 / 位置 | 返回体 |
|---|---|---|---|
| GET/HEAD | / 、/index.html | _serve_static（STATIC_FILES :43-50） | 200 index.html 原始字节，text/html; charset=utf-8 |
| GET/HEAD | /app.css | _serve_static | 200 app.css 原始字节，text/css; charset=utf-8 |
| GET/HEAD | /app.js | _serve_static | 200 app.js 原始字节，application/javascript; charset=utf-8 |
| GET/HEAD | /favicon.svg | _serve_static | 200 favicon.svg 原始字节，image/svg+xml |
| GET/HEAD | /vendor/tabler.min.css | _serve_static | 200 vendor CSS 原始字节，text/css; charset=utf-8 |
| GET | /healthz | do_GET :132-134 | ok_envelope({"service":"console","port":PORT,"gateway":sources.GATEWAY}, 0) |
| GET | /api/actions/jobs | do_GET :135-136 | ok_envelope(actions.jobs(), 0) |
| GET | /api/logs/stream | _stream_logs :154-173 | SSE：每 2s 一帧 data: {"lines":[尾部20行],"at":ISO时间}\n\n，30 帧后 Connection: close；HEAD 为 200 + text/event-stream + 空 body |
| GET | /api/overview | sources.overview（ROUTES :29） | ok_envelope(overview(), 5000) |
| GET | /api/gateway | sources.gateway（:30） | ok_envelope(gateway(), 5000) |
| GET | /api/models | sources.aliases（:31） | ok_envelope(aliases(), 30000) |
| GET | /api/probe | sources.probe（:32） | ok_envelope(probe(), 30000) |
| GET | /api/prices | sources.prices（:33） | ok_envelope(prices(), 60000) |
| GET | /api/scores | sources.scores（:34） | ok_envelope(scores(), 60000) |
| GET | /api/quota | sources.quota（:35） | ok_envelope(quota(), 60000) |
| GET | /api/arena | sources.arena（:36） | ok_envelope(arena(), 300000) |
| GET | /api/traffic | sources.traffic（:37） | ok_envelope(traffic(), 15000) |
| GET | /api/accounts | sources.accounts（:38） | ok_envelope(accounts(), 60000) |
| GET | /api/logs | sources.logs（:39） | ok_envelope(logs(), 5000) |
| GET | /api/config | sources.config（:40） | ok_envelope(config(), 60000) |
| GET | /api/ops | sources.ops（:41） | ok_envelope(ops(), 30000) |
| POST | /api/actions/reload | actions.reload_gateway（:175-184） | 200 ok_envelope(entry,0)；JOB_BUSY→409、UPSTREAM_DOWN→502 等 err_envelope |
| 任意 GET | 未登记路径 | do_GET :144-145 | 404 err_envelope("BAD_REQUEST", f"unknown route {path}") |
| 任意 POST | 其他路径 | do_POST :179-180 | 404 err_envelope("BAD_REQUEST", f"unknown action {path}") |
| GET/POST | Host 不在白名单 | _host_ok :72-76 / :129-130 / :176-177 | 403 err_envelope("BAD_REQUEST", "host not allowed" / "origin not allowed") |
| GET | 数据源抛异常 | :149-152 | SourceError 按 STATUS :51-52 映射 404/500/502/400/409；其他 Exception → 500 err_envelope("PARSE_ERROR", f"{type(exc).__name__}: {exc}") |

ROUTES 共 13 条数据面，STATIC_FILES 共 6 条；STATUS = {"SOURCE_MISSING": 404, "PARSE_ERROR": 500, "UPSTREAM_DOWN": 502, "BAD_REQUEST": 400, "JOB_BUSY": 409}。

### 2.3 监听地址 / 端口 / 是否只读

- server.py:53 `PORT = 7872`；:236-237 `ap.add_argument("--port", type=int, default=7872)` / `ap.add_argument("--host", default="127.0.0.1")`；:240 `PORT = args.port`（_host_ok/_origin_ok 用动态 PORT）。
- :243-245 只放行 `("127.0.0.1", "localhost", "::1")`，否则 stderr `only loopback bind is allowed` 并 return 2；:246 `ThreadingHTTPServer((args.host, args.port), Handler)`，:247 `srv.daemon_threads = True`，:248 print 启动语，:250 `srv.serve_forever(poll_interval=0.5)`，:254 `srv.server_close()`。
- _host_ok 白名单含带端口与不带端口两种写法（:74-75），_origin_ok 仅接受带端口的 3 个 netloc（:83）。
- 只读性：13 个 GET + 6 个静态 + SSE 全部只读（Path.stat / read_bytes / _tail_bytes / 网关 GET）；唯一 POST /api/actions/reload 只发一个 HTTP 请求，不写文件、不启停进程（actions.py:3-5 注释与 :37-47 代码一致）。启动器 -Detach 会写 .work/console.stdout.log 与 .work/console.stderr.log，那是控制台自身运行日志，不是数据面写入。

## 3. sources.py 每个数据源函数（绝对路径 / 字段映射 / 降级）

路径常量（sources.py:21-27）：ROOT = F:\Project\ModelBus（Path(__file__).resolve().parents[2]）；HOME = Path.home()；ZV2 = ~/.zcode/v2；LOCALAPP = %LOCALAPPDATA%（缺省 HOME/AppData/Local）；ZGATE_DIR = %LOCALAPPDATA%\ZCodeGateway；GATEWAY = 环境变量 MODELBUS_GATEWAY，默认 http://127.0.0.1:7871；REQUEST_LOGS = ROOT/gateways/upstream/workbuddy/data/request-logs。统一脱敏：scrub（:117-125）、_clip（:128-129）、_mask_id（:132-138）、SECRET_NAME/SECRET_VALUE（:31-35）、MASK = "<redacted>"。

| 函数（行号） | 读取的绝对路径 | 字段映射 | 异常降级 |
|---|---|---|---|
| gateway() :165-178 | GET http://127.0.0.1:7871/health + /v1/models（默认） | health=scrub(data), health_bytes, health_content_type, models, models_content_type, gateway, polling_hint_ms=5000 | _get 任一失败→SourceError("UPSTREAM_DOWN")→502；无单侧降级；cached 5000ms |
| aliases() :181-201 | ~/.zcode/v2/model-alias-map.json | meta, version, generated_at, slot, count, legacy_count, rows[{name, ...scrub(spec)}] | 缺文件 SOURCE_MISSING→404；坏 JSON PARSE_ERROR→500；非 dict spec 走 value；cached 30000 |
| probe() :204-227 | ~/.zcode/v2/model_probe.json | meta, total, ok（status∈ok/healthy/200/true）, rows[{name,status,http,ms,provider,detail,ever_ok,ok_at,credit}] | 同上；非 dict 条目跳过；cached 30000 |
| scores() :230-240 | ~/.zcode/v2/model-scores.json | meta, checked_at, basis(scrub), count, rows[{name,...scrub(spec)}] | 同上；非 dict spec 静默丢弃；cached 60000 |
| quota() :243-249 | ~/.zcode/v2/quota-windows.json | meta, generated_at, windows(scrub) | 同上；cached 60000 |
| prices() :252-263 | ROOT/providers/workbuddy/cache/wb_pricing.json + ROOT/providers/qoder/cache/qd_prices.json | sources[_meta×2], workbuddy_count, qoder_count, workbuddy[], qoder[{name,...}] | 任一 _load_json 失败整接口 404/500，无单侧降级；qd 非 dict 会 AttributeError→500；cached 60000 |
| arena() :266-275 | ~/.zcode/v2/arena-leaderboard.json | meta, updatedAt, totals, standings, total_rows, rows 前 20, note | 同上；cached 300000 |
| traffic() :278-309 | ROOT/gateways/upstream/workbuddy/data/request-logs/requests-*.jsonl（按 mtime 倒序取最新） | file, meta, count, ok(ok is True), ok_rate, avg_ms, tokens(total_tokens), by_model/by_status/hours, files 前 10, note="tail 800 行流式采样，非全量统计" | 目录空/无匹配→SourceError("SOURCE_MISSING","request-logs/requests-*.jsonl")→404；坏 JSON 行 tail_jsonl 跳过；p.stat() 竞态未捕获；cached 15000 |
| accounts() :312-345 | ROOT/gateways/upstream/workbuddy/auths/*.json + ROOT/gateways/upstream/qoder/accounts/*.json + ~/.zcode/v2/provider_config.json + ~/.zcode/v2/credentials.json | workbuddy[{id掩码,nickname,uid掩码,credential_present布尔,expires_at,bytes}], qoder[{id掩码,bytes}]前20, provider_config{present,values:"never exported",meta}, credentials{present,values} | 单文件 _load_json 失败 continue；目录不存在→空列表；凭据值不导出；raw 非 dict 会 AttributeError（见 §7）；cached 60000 |
| logs() :348-361 | %LOCALAPPDATA%\ZCodeGateway\zgate.log + 同目录 *.log | gateway_tail[最多160行 _clip 240], tail_limit=160, files[_meta 前10按体积], note="仅 zgate.log 出行内容；其余日志只报体积，避免请求体泄漏" | zgate.log 不存在→lines=[]；目录不存在→files=[]；不抛；cached 5000 |
| config() :364-384 | 环境变量 MODELBUS_GATEWAY / WB_GATEWAY_KEY / WB_GATEWAY_BASE / ZCODE_PERSONAL_PROVIDER_CONFIG_FILE / ZCODE_BUILTIN + ~/.zcode/v2/{provider_config.json,credentials.json,model-sync-state.json,setting.json} | gateway, bind:"127.0.0.1", env[{name,configured}], files[{label,present,values,meta}], write_actions:["reload"], note | 只 is_file/stat 不读内容，不抛；cached 60000 |
| ops() :387-423 | ROOT/gateways/**/*.bak-* + REQUEST_LOGS/*.jsonl + ROOT/.work/** + ROOT/%SystemDrive%/** + ~/.zcode/v2/provider_config.json.bak-* + shutil.disk_usage(ROOT) | candidates[5 项 key,path,count,bytes,review], reclaimable_bytes(=bak+work+lit+cfg，不含 jl), disk{total,used,free}, policy="后台只读展示，不自动删除任何文件" | disk_usage OSError→disk={}；目录不存在→计数 0；cached 30000 |
| overview() :429-459 | 组合 gateway/probe/traffic/ops + /health 字段 | ok, uptime_s, alias_models, segments(7 段 state/key/child/base), cooling, guard, children(scrub), hops{total,ok}, probe{total,ok}, traffic{file,requests,ok_rate,avg_ms,tokens}, ops{reclaimable_bytes,top3}, health_bytes, generated_at | _safe 仅捕获 (SourceError, OSError, ValueError) 返回默认 dict；不捕获 AttributeError/TypeError/KeyError；cached 5000 |

辅助函数降级：cached（:54-64）TTL 内复用；_safe（:67-71）三类异常返默认值；_load_json（:74-81）缺文件 SOURCE_MISSING、坏编码/坏 JSON PARSE_ERROR；_tail_bytes（:84-96）尾部最多 max_bytes、decode(errors="replace")；tail_lines（:99-102）缺文件 SOURCE_MISSING；tail_jsonl（:105-114）跳过坏行；_meta（:141-150）OSError 返回 bytes=0/mtime=None；_get（:153-160）HTTPError/URLError/TimeoutError/OSError/JSONDecodeError 统一包成 UPSTREAM_DOWN。

## 4. actions.py 写操作（触发条件 / 外部调用 / 鉴权或确认）

| 操作 | 触发条件 | 调用的外部命令 / HTTP | 鉴权 / 确认 |
|---|---|---|---|
| reload_gateway() :29-57（唯一写面） | POST /api/actions/reload；server.py:176 先过 _host_ok + _origin_ok（必须带同源 Origin）；:179 路径精确匹配；actions.py:31-34 若 _STATE["running"] 为 True 抛 SourceError("JOB_BUSY","reload already running")→409 | Request(sources.GATEWAY + "/admin/reload", data=b"{}", method="POST", headers={"Content-Type":"application/json","Accept":"application/json"})，urlopen(req, timeout=10)；无 shell 命令、无 Start-Process、不写文件、不启停 zgate | 控制台侧：仅 Host + Origin 同源校验，无用户认证、无 token、无 CSRF token；网关侧 gateways/zgate/internal/router/router.go:591-594 `if path == "/admin/reload" { s.reload(w, r); return }` 前无鉴权分支（[C11] grep 证据）；前端确认：index.html:76-87 模态框 + app.js:402-416 「确认重载」点击后才 fetch。动作结果 entry{action,at,status,response,ok,error} 只存内存 _STATE["history"]（上限 20，:56） |
| jobs() :22-26（读，不是写） | GET /api/actions/jobs | 只读内存 _STATE | 无 |

补充：HTTPError/URLError/TimeoutError/OSError 在 :48-51 被转成 entry.ok=false 并附 status/error，不抛；:44 对网关响应用 sources.scrub 脱敏，非 JSON 用 _clip(raw,300)；:52-56 finally 复位 running 并裁剪历史。

## 5. start-console.ps1 启动方式

| 项 | 证据 |
|---|---|
| 参数 | :1-5 `param([int]$Port = 7872, [switch]$Check, [switch]$Detach)`；:8 `$ErrorActionPreference = "Stop"` |
| 解释器 | :9 `$py = (Get-Command python -ErrorAction Stop).Source`（PATH 中的 python，未 pinned 版本；[C7] pyc magic 显示 3.12） |
| 入口 / 根 | :10 `$entry = Join-Path $PSScriptRoot "server.py"`；:11 `$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path` |
| -Check | :13-16 `& $py $entry --check; exit $LASTEXITCODE` → server.py:241-242 run_check()，不监听端口 |
| 前台（默认） | :31-32 `& $py $entry --port $Port; exit $LASTEXITCODE`；server.py:249-252 Ctrl+C → KeyboardInterrupt → server_close() |
| -Detach 隐窗 | :18-29 建 `$work = .work`（不存在则 New-Item），:23-24 `$out = .work/console.stdout.log` / `$err = .work/console.stderr.log`；:25-26 `Start-Process -FilePath $py -ArgumentList @($entry, "--port", "$Port") -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err | Out-Null`；符合 AGENTS.md §17 的 -WindowStyle Hidden，本目录未发现缺 Hidden 的 Start-Process |
| 端口 | 启动器只传 --port $Port；--host 未传，server.py 默认 127.0.0.1；:27 `Write-Output "console detached on 127.0.0.1:$Port (log: $out)"` |
| 日志落点 | .work/console.stdout.log（仅 server.py:248 启动语一行 + print 自检）、.work/console.stderr.log（server.py:70 log_message 的全部访问日志与 traceback）；.work/ 由 .gitignore:104 排除 |
| 停止方式 | **脚本内没有**：无 -Stop 分支、无 -PassThru、无 PID 文件、无端口就绪探测。前台靠 Ctrl+C；Detach 后只能人工按 7872 端口反查 PID 再 Stop-Process（本分片未执行）。见 §7 第 2/3 条 |

## 6. 前端静态资源 / CDN 与外部域名 / Fluent 2 来源

### 6.1 静态资源清单与引用（全部同源根路径，零 CDN）

| 文件 | 字节 / 行 | 被谁引用 |
|---|---:|---|
| static/index.html | 4328 / 91 | STATIC_FILES "/"、"/index.html"；:8 /favicon.svg，:10 /vendor/tabler.min.css，:12 /app.css，:89 /app.js（defer） |
| static/app.css | 10717 / 194 | index.html:12 `<link rel="stylesheet" href="/app.css">`（后加载覆盖 vendor :root） |
| static/app.js | 26427 / 419 | index.html:89 `<script src="/app.js" defer></script>` |
| static/favicon.svg | 247 / 4 | index.html:8；STATIC_FILES "/favicon.svg" |
| static/vendor/tabler.min.css | 686736 / 8 | index.html:10；STATIC_FILES "/vendor/tabler.min.css" |
| static/vendor/LICENSE-tabler.txt | 1247 / 25 | 未被 HTML/JS 引用；STATIC_FILES 也未登记（访问 /vendor/LICENSE-tabler.txt 会 404 JSON） |
| （缺失）tabler.min.css.map | — | vendor CSS:8 末尾 `/*# sourceMappingURL=tabler.min.css.map */` 指向它，glob 清单无此文件，STATIC_FILES 未登记 |

### 6.2 CDN / 外部域名逐条（[C6]/[C10] 实测）

1. index.html:9 注释 `本地 vendor 单文件，零 CDN、零外链`；index.html 无任何 http(s) src/href，4 个资源全部 / 开头同源。
2. app.js:2 注释 `零外部依赖、零外网请求`；app.js 中 fetch 路径全部 /api/...，EventSource("/api/logs/stream")，无 URL 常量。
3. app.css 无 @import、无 url()（全文 read 确认），只定义变量与项目类。
4. favicon.svg:1 `xmlns="http://www.w3.org/2000/svg"` — XML 命名空间 URI，不发起网络请求。
5. static/vendor/tabler.min.css:2 注释 `Tabler v1.7.4 (https://tabler.io)` — 纯注释文本。
6. static/vendor/tabler.min.css:5 注释 `Licensed under MIT (https://github.com/tabler/tabler/blob/master/LICENSE)` — 纯注释文本。
7. static/vendor/tabler.min.css 第 7 行内 25 处 `url("data:image/svg+xml,... xmlns='http://www.w3.org/2000/svg' ...")` — 全部 data URI，URL_FUNC_COUNT=25、DATA_URI_COUNT=25、IMPORT_COUNT=0、FONT_FACE_COUNT=0（[C6]），其中 http://www.w3.org/2000/svg 只是 SVG 命名空间。
8. static/vendor/LICENSE-tabler.txt:23 `Source: https://github.com/tabler/tabler/blob/dev/LICENSE` — 许可证文本。
9. static/vendor/LICENSE-tabler.txt:24 `Version: @tabler/core@1.7.4 (release tag), https://github.com/tabler/tabler` — 许可证文本。
10. static/vendor/tabler.min.css:8 `/*# sourceMappingURL=tabler.min.css.map */` — 相对文件名（非 http），但目标文件不存在，DevTools 打开时会产生一次 404 同源请求。
11. [C6] 全文唯一 URL 集合 = ｛http://www.w3.org/2000/svg, https://github.com/tabler/tabler/blob/master/LICENSE, https://tabler.io｝，URL_COUNT=3，无一出现在 <script src> / <link href> / CSS @import / 远程 url() 中 → 运行期零 CDN、零外部资源加载成立；「零外链」仅指运行期，文件内确有 URL 文本与注释。

### 6.3 Fluent 2 是手写 CSS 还是 vendor 了库

两者都有，但分工不同：**Fluent 2 没有 vendor 任何官方库，是手写 CSS** —— static/app.css:1-9 注释明说「Tabler 1.7.4 外壳 + Fluent 2 设计规则」，:10-91 手写 --mb-*（Neutral/Brand/Status/Radius/Spacing/Type/Shadow，4px 刻度、4/6/8px 圆角、Segoe UI Variable 字体），:63-90 手写 Fluent 2 → --tblr-* 变量桥接，:93-126 手写 dark 主题覆盖，:128-194 手写项目专有类。**同时 vendor 了 Tabler 1.7.4**（tabler.min.css 686736 B + MIT LICENSE-tabler.txt），组件基础样式 .btn/.card/.table/.badge/.modal/.toast 走 Tabler 原生类。未发现 @fluentui/*、Fluent UI 的 JS/CSS 文件；无 CDN；无构建工具产物（无 package.json / node_modules 于本目录）。

## 7. 明显 bug / 未完成 / TODO / 硬编码 / 路径拼接隐患

[C9] 全目录 grep `TODO|FIXME|XXX|HACK|WIP|未完成|待补` 零命中，故以下均为代码事实而非显式 TODO 标记。逐条给「文件:行号 + 原文 + 为什么是问题」。

- **static/app.js:356** — `setGatewayDot(bag["/api/gateway"] ? true : (bag["/api/overview"] ? !bag["/api/overview"].__err : undefined));`；all()（:89-93）失败时写入 truthy 的 ｛__err: reason｝，健康页 502 也判定「网关在线」，总览页则恒判「网关不可达」；侧栏状态与真实 /health 不一致。
- **start-console.ps1:25-27** — `Start-Process -FilePath $py -ArgumentList @($entry, "--port", "$Port") -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err | Out-Null` / `Write-Output "console detached on 127.0.0.1:$Port (log: $out)"`；无 -PassThru / PID 文件 / Stop 分支 / 端口就绪探测，Start-Process 成功不等于 7872 listen，进程若因端口占用立刻退出只能在日志里看到。
- **server.py:70** — `sys.stderr.write("[console] %s - %s\n" % (self.address_string(), fmt % args))`；全部访问日志与异常写 stderr，而启动器 :27 只告诉用户 stdout 路径，排障会看错文件。
- **server.py:211-220** — `except sources.SourceError as exc:` / `if exc.code == "UPSTREAM_DOWN":` / `print(f"[check] WARN {path}: {exc.message}")`；网关不可达只 WARN 不加 failures，:229 `result = PASS`、:230 `return 0 if failures == 0 else 1` → --check 假绿。
- **server.py:224-229** — `sources._get("/health")` 异常同样 `print(f"[check] WARN gateway /health: {exc.message}")`；单独探测也不计失败，同上。
- **server.py:175-184** — do_POST 只有 `except sources.SourceError as exc:`，无 do_GET:151-152 的 `except Exception as exc:  # 页面必须拿到结构化错误，不能是裸 500`；actions.reload_gateway 若抛非 SourceError，BaseHTTPRequestHandler 回裸 HTML 500，app.js:82 的 resp.json().catch 显示「响应不是 JSON」。
- **sources.py:165-178** — `data, ctype = _get("/health")` 与 `models, ctype_models = _get("/v1/models")` 串行；任一 _get 抛 UPSTREAM_DOWN 整 /api/gateway 502，健康页无法只展示 /health；[C5] 实测两接口现均 200（2193 B / 18 条），但无单侧降级。
- **sources.py:252-259** — `wb = _load_json(wb_path)` / `qd = _load_json(qd_path)` / `qd_rows = [{"name": k, **scrub(v)} for k, v in qd.items() if isinstance(v, dict)]`；任一价目文件缺失整个 /api/prices 404（无单侧降级），qd 顶层若是数组则 AttributeError → 500。
- **static/app.js:402** — `gwSpan.textContent = "网关";`；index.html:80 的 `<span id="modal-gw">—</span>` 本应显示真实网关地址，/api/config.gateway 已提供该值却未取，用户点「确认重载」看不到目标 URL。
- **static/app.js:217** — `"网关响应一字不改；控制台只做 scrub 后展示"`；scrub 确实改了展示副本（掩码），「一字不改」应限定为「不改网关响应体」，与 index.html:68 `网关响应保持原样` 同样措辞过绝对。
- **static/index.html:68** — `只读后台 · 绑 127.0.0.1 · 网关响应保持原样 · 凭据值不出进程`；实际存在唯一 POST /api/actions/reload 写动作，server.py:3 自己写的是「独立只读服务… + 唯一 reload 动作」，footer 表述不自洽。
- **static/index.html:9** — `Tabler 1.7.4 · MIT · 42,052 stars · 本地 vendor 单文件，零 CDN、零外链`；stars 数字硬编码且本分片未外部核实（lead 要求停止检索）；vendor CSS 内含 3 个 URL 文本，「零外链」只在运行期成立。
- **static/vendor/tabler.min.css:8** — `/*# sourceMappingURL=tabler.min.css.map */`；glob 的 13 个文件里没有 .map，STATIC_FILES（server.py:43-50）也未登记，DevTools 打开样式面板会 404（同源，非外网）。
- **static/vendor/LICENSE-tabler.txt:23** — `Source: https://github.com/tabler/tabler/blob/dev/LICENSE` 与 tabler.min.css:5 的 `blob/master/LICENSE` 分支不一致，文档小差异。
- **server.py:74-75 / :83** — `allowed = {f"127.0.0.1:{PORT}", f"localhost:{PORT}", f"[::1]:{PORT}", "127.0.0.1", "localhost", "[::1]"}` 但 _origin_ok 只收带端口的 3 个 netloc；GET 允许无端口 Host、POST 强制带端口 Origin，校验口径不一致。
- **server.py:243 / :246** — `if args.host not in ("127.0.0.1", "localhost", "::1"):` 放行 ::1，但 `ThreadingHTTPServer((args.host, args.port), Handler)` 默认 address_family=AF_INET；--host ::1 能否绑定未验证（本分片未启动服务），属可疑代码路径。
- **server.py:51-52 / :130 / :177** — STATUS 把 `"BAD_REQUEST"` 映射 400，但 Host/Origin 拒绝硬编码 403 且回报 `err_envelope("BAD_REQUEST", ...)`；错误码与 HTTP 状态码不一致。
- **sources.py:23 / :366-372** — `ZV2 = HOME / ".zcode" / "v2"` 与固定的 `("provider_config.json", ZV2 / "provider_config.json")` 等 4 项；config() 只对 ZCODE_PERSONAL_PROVIDER_CONFIG_FILE 报 `configured` 布尔，files 不跟随该环境变量，若用户改了配置路径，配置页会误报「缺失」。
- **sources.py:26 / :154** — `GATEWAY = os.environ.get("MODELBUS_GATEWAY", "http://127.0.0.1:7871").rstrip("/")` + `req = Request(GATEWAY + path, headers={"Accept": "application/json"})`；字符串拼接，环境变量若含尾路径或 query 会拼出 /api/health 之类错误 URL。
- **sources.py:35** — `SECRET_VALUE = re.compile(r"(?i)(sk-[A-Za-z0-9_-]{6,}|Bearer\s+[A-Za-z0-9._-]{12,})")`；只认 `sk-` 前缀，不匹配 .gitignore:8 注释提到的 `oc_sk_…`（下划线变体）；若这类值出现在非敏感字段名下会漏抹（本目录当前不读那些 probe 文件）。
- **sources.py:157-160** — `raw = resp.read(4 << 20)` 固定 4 MB 上限；/health 现 2741 B（[C3]）、/v1/models 2193 B（[C5]）远低于上限，但一旦超 4 MB 被截断会 JSONDecodeError，被 :159 归入 UPSTREAM_DOWN（误报网关挂）而非 PARSE_ERROR。
- **sources.py:318-322** — `raw = _load_json(p)` 后 `acc, au = raw.get("account") or {}, raw.get("auth") or {}`；某 auth JSON 顶层若是数组，raw.get 抛 AttributeError，外层只 `except SourceError: continue`，整 /api/accounts 500。
- **sources.py:396 / :409** — `literal = ROOT / "%SystemDrive%"` / `{"key": "literal_systemdrive_dir", "path": "%SystemDrive%/", ...}`；这是对历史字面量目录的占用盘点，但展示成 %SystemDrive%/ 易被误读为环境变量展开，属硬编码路径产物。
- **sources.py:426 / static/app.js:112** — `SEGMENTS = ("workbuddy", "qoder", "qwen", "qiniu", "gemini", "hajimi", "opencode")` 与总览 KPI 副标题同一串硬编码；网关新增渠道段时 overview.segments 会漏（[C4] 实测 7 段均存在，当前一致）。
- **sources.py:67-71 / :431-435 / :442-446** — `_safe` 仅 `except (SourceError, OSError, ValueError): return default`；overview 里 `hops.values()`、`(h.get("alias") or {}).get("models")` 若 /health 结构变化抛 AttributeError 会直接 500，无兜底。
- **actions.py:17 / :37-39** — `_STATE = {"running": False, "history": []}` 纯内存；:37 `Request(sources.GATEWAY + "/admin/reload", data=b"{}", method="POST", headers={"Content-Type": "application/json", "Accept": "application/json"})` 无 Authorization / token；网关 router.go:591-594 直达 s.reload 无鉴权分支。历史记录进程重启即丢，无持久化审计。
- **static/app.js:372** — `sse.onerror = () => { if (box) box.textContent += "\n[流断开，页面会在下次切换时重连]"; };`；与 :271 文案「上限 60 秒后页面自动重连」及 server.py:162 `# 上限 60 s，页面自行重连` 矛盾（EventSource 未 close，浏览器默认立即重连），文案未完成。
- **static/app.js:360** — `if (page.id === "overview") timer = setInterval(loadPage, 10000);`；无请求序号 / AbortController，上一轮 await all() 未返回时下一次刷新会并发渲染并互相覆盖。
- **static/app.js:2** — `hash 路由 8 页，统一消费 {ok,generated_at,ttl_ms,data} 包，零外部依赖、零外网请求`；/api/logs/stream 是 SSE，不遵守 envelope，注释不严谨（轻微）。
- **start-console.ps1:9 / :25 / :11** — `$py = (Get-Command python -ErrorAction Stop).Source` 未 pinned（PATH 命中 Store 别名或非 3.12 会失败）；`-ArgumentList @($entry, "--port", "$Port")` 在 $entry 含空格时未加引号，Start-Process 拼接命令行会断参；:11 `Join-Path $PSScriptRoot "..\.."` 与 sources.py:21 `parents[2]` 两处独立推导项目根，移动目录需两处同步。
- **server.py:203-204** — `print(f"[check] handwritten static bytes = {hand_bytes} (budget 200 KB)")` / `print(f"[check] vendor static bytes = {vendor_bytes} (Tabler 1.7.4, offline)")`；版本 1.7.4 与 200 KB 预算硬编码在自检输出里，与 index.html:9 的 1.7.4 多处重复。
- **server.py:236 / :53 / start-console.ps1:2 / sources.py:380** — 7872 与 `"bind": "127.0.0.1"` 多处硬编码；--port 改端口后 config() 的 bind 仍正确（host 未变），但 index.html:68 只写 127.0.0.1 不含端口，属展示口径固定。

## 8. 与 /health 契约的一致性

- **不直接代理 7871**：控制台没有把 7871 的 /health 挂到自己的 /health 路径，也没有反向代理。它自己的健康端点是 server.py:132-134 的 `/healthz`，返回 `ok_envelope({"service": "console", "port": PORT, "gateway": sources.GATEWAY}, 0)`，与 7871 /health 完全独立。
- **/health 数据入口**：只有 sources.gateway()（sources.py:165-178）通过 `_get("/health")` 主动 GET `http://127.0.0.1:7871/health`，再包进 /api/gateway 的 `ok_envelope(..., 5000)`；另 run_check()（server.py:225）再 GET 一次做 WARN 级探测。前端健康页 app.js:198-218 消费 /api/gateway，把 h 展开成表格与 `JSON.stringify(h, null, 2)`。另有 sources.overview()（:431-458）从同一份 health 取 ok/uptime_s/alias/segments/cooling/guard/children/hops。
- **有没有改网关响应**：没有。网关 /health 由 gateways/zgate/internal/router/router.go:583-585 `if path == "/health" { s.health(w); return }` 自己生成；控制台侧只对展示副本做 `scrub(data)`（sources.py:170），从未写 gateways/、从未改 /health 处理、从未注册 /health 路由。实测 [C3]/[C4]：GET 127.0.0.1:7871/health → STATUS=200、ContentType=application/json; charset=utf-8、BODYCHARS=2741、RAWLEN=2741、顶层 18 键 `alias,chain,children,cooling,early,gemini,guard,hajimi,hops,ok,opencode,qiniu,qoder,qwen,race,upstream,uptime_s,workbuddy`；7 个渠道段均含 `key` 字段且类型为 Boolean（存在性），无字符串凭据值，符合硬约束③。[C5]：/v1/models 与 /models 均 200 / 2193 B / 18 条 / application/json; charset=utf-8。
- **scrub 与「一字不改」的边界**：SECRET_NAME（sources.py:31-34）匹配 api[_-]?key / *token / secret / cookie / authorization / sk- / bearer 等字段名，不匹配裸露的 `key` 字段名；[C4] 实测段内 `key` 是 Boolean，因此保持原样布尔（has_key 语义），既没改网关响应体，也没把存在性抹掉。展示副本中的 sk- / Bearer 字符串会被 MASK 替换，故 app.js:217 的「一字不改」应理解为「网关响应体不改」。
- **是否只读**：13 个数据面 GET + 6 个静态 + SSE 全部只读（磁盘 stat/read、日志 tail、网关 GET）；唯一 POST /api/actions/reload 只向 7871 /admin/reload 发一个 HTTP 请求（actions.py:37-47），不写配置、不碰凭据、不启停 zgate 长驻网关；server.py:246 只监听自己的 7872。启动器 -Detach 写 .work/*.log 属控制台自身日志，与网关响应无关。
- **结论**：与 /health 契约一致 —— 不代理、不改写、不启停、数据面只读；不一致处只有文案（app.js:217 / index.html:68 把「响应体不改」写成「一字不改/保持原样」，实际展示副本经 scrub）与 §7 的降级/自检问题。

## 9. 未解决项与取证限制

1. 未启动 7872 控制台、未启停 7871 zgate、未 POST /admin/reload，故端口监听、SSE 帧、reload 实际响应、-Detach 隐窗行为均为静态推断，未做端到端验证；lead 已独立跑 v3 自检 / E2E 39 项全 PASS / 浏览器渲染通过（m00027），本分片不重复。
2. static/vendor/tabler.min.css 第 7 行是 686,7xx B 的压缩单行，read 工具对超长行只返回前 2000 字符并附 `... (line truncated to 2000 chars)`；未逐字人工通读，已用 [C6] 对全文做正则派生扫描（URL_COUNT=3、url()=25 全 data URI、@import=0、@font-face=0、sourceMappingURL=tabler.min.css.map），结论限于这些派生指标。
3. 3 个 .pyc 为二进制编译缓存，未逐字节人工通读；仅记录字节数、magic CB 0D 0D 0A（CPython 3.12）、mtime，.gitignore:52-53 已排除。
4. index.html:9 的 `42,052 stars` 与 LICENSE-tabler.txt:24 的 `@tabler/core@1.7.4 (release tag)` 未经本分片外部核实（lead 要求停止检索），标为待核数字。
5. sources.py:176 注释 `# /health 每次触发 aliases.Reload()，别高频轮询` 声称的行为，本分片未在 gateways/zgate 源码中定位到该调用，标为注释待核。
6. --host ::1 在 ThreadingHTTPServer（默认 AF_INET）下能否绑定、--port 非 7872 时 _origin_ok 的带端口白名单是否仍自洽，均未运行时验证。
7. ZCODE_PERSONAL_PROVIDER_CONFIG_FILE 若被改到别处，config().files 仍指向默认 ~/.zcode/v2/provider_config.json（静态推断，未实测环境变量变更）。
8. codegraph_sync 的索引副作用已在 §0 记录；.codegraph/ 由 .gitignore:65 排除，git 工作树不新增源文件改动（本分片未跑 git status，未执行任何 git 写操作）。

## 10. 交付自检

- 写域唯一：本文件 F:\Project\ModelBus\evidence\agent-console-impl.md；claim_files 认领 → write → read 复核行数 → release_files 释放。
- 结论先行、简体中文、贴原始命令与 exitCode=0 / 原始输出；无凭据、key、token 值，只记 `key:Boolean` / `configured` / `credential_present` 等存在性。
- 回报格式：分片路径｜行数｜关键发现 3 条｜未解决项｜用到的原始命令（见本文件 §0.1 全文，回报里给摘要）。
