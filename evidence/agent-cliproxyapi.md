# CLIProxyAPI 本地网关落地证据（router-for-me/CLIProxyAPI v8.0.61）

- 执行时间：2026-11-09 11:38–11:50（Asia/Shanghai）
- 落点：`F:\Project\ModelBus\third-party\cliproxyapi\`
- 范围：只做网关本体；未碰 `provider_config.json` / `model_alias.py` / `sync-models.ps1` / `docs/`
- 权限：无管理员、未改任何系统代理设置

## 1. 结论

网关已起来并只监听回环 `127.0.0.1:8317`：无 key → `401`，带 key → `200` 空模型列表，POST `/v1/chat/completions` → `400 model_not_found` 的明确 JSON 错误（进程不崩、错误进 error 日志）。
上游凭证尚未配置，符合"网关通、上游未接"的预期状态。

| 项 | 值 |
| --- | --- |
| 二进制 | `cli-proxy-api.exe` |
| 版本 | **8.0.61**，commit `681ce41b`，BuiltAt `2026-11-08T14:32:51Z`（二进制 `--version` 自报） |
| 字节数 | 77,667,840 B（exe）；25,663,680 B（下载的 zip） |
| exe sha256 | `3088e345b4537c934b849ae6238e5478de47cf0076cb3ee88750d942f78a38b0` |
| zip sha256 | `e6dbe1337d17b993c6fa6d75d71f2e98db6ea3653af73a4217956f0c53e025b5`（与官方 `checksums.txt` 逐字一致） |
| 后台 job | `bash-80952f9cb8e84050`（status: running） |
| 进程 | `cli-proxy-api.exe` PID **20672**，启动 `2026/11/9 11:45:23`，Path `F:\Project\ModelBus\third-party\cliproxyapi\cli-proxy-api.exe` |
| 监听 | `127.0.0.1:8317`（回环独占，见 §5） |
| 客户端 key | 已生成（32 位十六进制），明文只在 `third-party\cliproxyapi\config.yaml` 第 21 行 与 `third-party\cliproxyapi\cliproxy.env`，本报告不回显 |

## 2. 上游资产与获取方式

未认证 GitHub API 确实限流（`api.github.com` 返回 `"API rate limit exceeded for 66.90.99.58"`），改走两条路：

1. `gh release list --repo router-for-me/CLIProxyAPI --limit 3` → 最新 `v8.0.61  Latest  2026-11-08T14:31:53Z`（次新 v8.0.60、v8.0.59）；`gh release view` 给出全量资产名与字节数；
2. 直链下载不受限流影响：`https://github.com/router-for-me/CLIProxyAPI/releases/download/v8.0.61/CLIProxyAPI_8.0.61_windows_amd64.zip`，同时取 `checksums.txt` 校验。

资产清单（release 内，`gh` 报告值与本地实测值一致）：`checksums.txt 1084 / darwin_aarch64 23385527 / darwin_amd64 25334948 / freebsd_* / linux_* / windows_aarch64 22895393 / windows_amd64 25663680`。

## 3. 目录落地（照 `third-party/` 既有约定）

`third-party/` 现有 `zcode/`、`zcodium/` 的约定是：每个子目录一份 `UPSTREAM.md` 写来源 URL / 钉住的版本 / 许可 / 文件对应 / 怎么更新，上游文件原样保留，本仓派生件单独标注。本次照办：

```
third-party/cliproxyapi/
  cli-proxy-api.exe      77,667,840 B  上游原样（.gitignore 排除，77 MB 不入库）
  config.example.yaml        81,819 B  上游原样（v8 template，1353 行，未改）
  README.md                  33,063 B  上游原样
  README_CN.md               31,143 B  上游原样
  LICENSE                     1,137 B  上游原样（MIT）
  config.yaml                 2,297 B  本仓派生：最小可用配置（含客户端 key）
  cliproxy.env                  181 B  本仓派生：同一 key 的 env 形态（CLIPROXY_BASE_URL / CLIPROXY_ACCESS_KEY）
  .gitignore                     96 B  排除 config.yaml / cliproxy.env / *.env / exe / auths / logs / kv.db
  UPSTREAM.md                 3,7xx B  来源凭证（URL / v8.0.61 / commit / 双 sha256 / 更新命令）
  auths/                           运行时产物：kv.db（32,768 B）+ logs/
```

## 4. `config.yaml` 字段清单（脱敏，key 用 `<REDACTED>`）

| 行 | 字段 | 值 | 说明 |
| --- | --- | --- | --- |
| 9 | `config-version` | `8` | v8 布局；写错其他值会报 `unsupported config-version (expected 8)` |
| 11–13 | `server.host` / `server.port` | `"127.0.0.1"` / `8317` | 只监听回环 |
| 15–17 | `management.disable-control-panel` / `disable-auto-update-panel` | `true` / `true` | 不下载、不暴露管理面板（实测默认会去 GitHub 抓面板资产，且撞限流） |
| 19–21 | `access.api-keys` | `- "<REDACTED>"` | **客户端**鉴权 key（不是上游 key），32 位十六进制 |
| 23–24 | `oauth.auth-dir` | `"./auths"` | OAuth 凭证目录，相对本目录，antigravity 等走这里 |
| 26–30 | 注释 | —— | 实测结论写死在注释里（api-keys 支持哪些组、antigravity 走 OAuth） |
| 32 | `# api-keys:` | 注释 | 上游 API key 组的根，默认整段注释 |
| 34–42 | `# gemini:` … | 注释占位 | name / priority / base-url / models[].name+alias / keys[].api-key |
| 46–54 | `# antigravity:` … | 注释占位 | 同形字段样例；8.0.61 下该组不装载客户端 |

没有配 `management.secret-key` → 管理 API 直接 404（不需要，也不留口子）；没有配 `requests.proxy-url` → 不走代理。

## 5. 监听状态与三条验证（原始返回，均截断到 ≤300 字）

### 5.1 监听证据（`netstat` 在这台机器上不显示该 LISTENING 行，改用三条硬证据）

1. 同端口再绑定 → `127.0.0.1:8317 -> EADDRINUSE`（被占用）；
2. 通配绑定 → `0.0.0.0:8317 -> listening`（空闲）⇒ 监听只落在回环，不是 0.0.0.0；
3. 局域网地址 → `http://10.0.0.28:8317/v1/models → ECONNREFUSED` ⇒ 外部不可达。

> 旁注：本机 `netstat -ano` 的 LISTENING 段只列 7 条且大量 `PID 0` 记录（安全软件/过滤驱动迹象），`Get-NetTCPConnection` 的 CIM 查询也报查询不到。所以不拿 netstat 当结论，用上面三条 + 实际 HTTP 应答当证据。

### 5.2 三条验证

**① 无凭证 `GET /v1/models` → 401（期望值）**
```text
$ curl -s -o NUL -w "%{http_code}" http://127.0.0.1:8317/v1/models
401

$ curl -s -i http://127.0.0.1:8317/v1/models
HTTP/1.1 401 Unauthorized
Content-Type: application/json; charset=utf-8
Content-Length: 27

{"error":"Missing API key"}
```

**② 带 access key `GET /v1/models` → 200，空列表（上游未配）**
```text
$ curl -s -H "Authorization: Bearer <REDACTED>" http://127.0.0.1:8317/v1/models
{"data":[],"object":"list"}
```

**③ `POST /v1/chat/completions` 最小请求 → 400，明确报错不崩**
```text
$ curl -s -w "\n[http %{http_code}]" -H "Authorization: Bearer <REDACTED>" -H "Content-Type: application/json" \
    -d '{"model":"gemini-2.5-flash","messages":[{"role":"user","content":"ping"}],"max_tokens":16}' \
    http://127.0.0.1:8317/v1/chat/completions
{"error":{"message":"unknown provider for model gemini-2.5-flash","type":"invalid_request_error","code":"model_not_found","param":"model"}}
[http 400]
```

**④ 额外一条：错误 key → `401 {"error":"Invalid API key"}`**（区分"没给 key"与"key 不对"，便于客户端排错）

### 5.3 错误落盘证据

进程没崩，两个 400 各留一份请求日志（目录 `third-party/cliproxyapi/auths/logs/`）：

- `error-v1-chat-completions-2026-11-09T114608-5e7f8d12.log`（1,440 B）
- `error-v1-chat-completions-2026-11-09T114639-ccb32853.log`（1,337 B）

日志首行 `Version: 8.0.61`，内含 `URL: /v1/chat/completions`、`Status: 400`、请求体与响应体（Authorization 由程序自身打了码）。

## 6. 有上游凭证后要改哪几行（指向本仓 `third-party/cliproxyapi/config.yaml` 自己的行号）

### 6.1 Gemini（API key 组，已验证可装载）

1. **第 42 行** 把 `"REPLACE_WITH_GEMINI_KEY"` 换成真 key；同一组要加第二个 key 就照第 41–42 行的缩进再抄一条 `- api-key: "..."`。
2. **第 32–42 行（`api-keys:` 到 Gemini 段的最后一行）块选，删掉每行开头的 `# `（井号 + 一个空格，两字符）**：删完第 32 行变成顶格 `api-keys:`，第 34 行 `gemini:`，缩进自动成型。
3. **第 43–54 行保持注释**（别删它们的 `#`），antigravity 占位组就保持关闭。
4. 想换模型：改 **第 39 行** `name`（上游模型 id）与 **第 40 行** `alias`（客户端看到的 id）；别改第 37 行 `base-url`，除非走自建反代。

**这套取消注释的做法已实测（两种删法都试过）**：只删 32–42 行、或删 32–54 行，临时配置（端口分别改 8396 / 8397）启动后摘要都是
`server clients and configuration updated: 1 clients (0 auth entries + 1 Gemini API keys + …)`，即组确实装载。
同一份配置若把 `antigravity` 组也解开，摘要仍为 `0 clients` —— 该组在 8.0.61 不生效。

### 6.2 Antigravity（不是 api-keys 能接的，走 OAuth）

- **不用改 config.yaml**：第 24 行 `oauth.auth-dir: "./auths"` 已经是落点。
- 执行 `third-party\cliproxyapi\cli-proxy-api.exe -antigravity-login`（走 OAuth），凭证 JSON 落进 `auths/\`；再直接用 `taskkill /PID 20672 /F` 重启进程（当前 job `bash-80952f9cb8e84050` 一并结束）。
- 已有别的机器导出的 antigravity auth JSON，直接丢进 `auths/\` 即可，启动摘要里 `auth entries` 会变成 1。
- 内核日志声称有 file watcher 监控 config 与 auth 目录（`file watcher started for config and auth directory changes`），即改配置可能热加载；**这条未实测**，改完仍按重启处理最稳。

## 7. 起停与复现

```bash
# 起（后台，等价于本次 job）
cd "F:/Project/ModelBus/third-party/cliproxyapi" && ./cli-proxy-api.exe -config config.yaml

# 停（本次运行的 PID）
taskkill /PID 20672 /F        # CMD；job 侧用 job_kill bash-80952f9cb8e84050

# 环境变量（客户端的取法）
CLIPROXY_BASE_URL=http://127.0.0.1:8317
CLIPROXY_ACCESS_KEY=<REDACTED>   # 见 third-party/cliproxyapi/cliproxy.env
```

## 8. 需要知道的三件事

1. `config.yaml` 与 `cliproxy.env` 含明文客户端 key，已由 `third-party/cliproxyapi/.gitignore` 排除；exe 77 MB 同样排除（按 `UPSTREAM.md` 第 5 节可重下，sha256 已钉）。
2. 上游"未配置"与"配置错"在 8.0.61 表现不同：未配置 → `/v1/models` 空列表 + chat 报 `model_not_found`；未知组名/不支持的组（如 `api-keys.antigravity`）→ 启动不报错、照样 `0 clients`，属于静默忽略，别拿"启动成功"当"配置生效"。
3. 管理面板默认会去 GitHub 抓资产（本次实测撞限流后落到 fallback 页），故 `disable-control-panel` / `disable-auto-update-panel` 都置 `true`；要用管理面板再改第 16–17 行。

## 9. 执行环境异常记录（不影响结论）

`ops_bash` 在本次会话中途返回 `EXECUTOR_UNAVAILABLE: Niubash preparation failed: UNKNOWN: unknown error, link '…\winuxcmd\usr\bin\awk.exe' -> '…\winuxcmd\usr\bin\awk.exe'`（dsh-ops 0.5.1 执行树并发缺陷），此后 shell 不可用；§2 之后的下载校验之外的验证改用 Windows `curl.exe` / `tasklist` / Node 直接发起请求完成，证据等价且都是原始返回。网关进程本身不受影响，仍在运行。
