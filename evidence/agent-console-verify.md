# 门禁与静态验证分片（agent-console-verify）

> **一句话**：3 个 .py 逐文件编译全 rc=0、零真值凭据、零 CDN 运行时外链；check-project.py exit 0 / 8 项通过，check-docs.py 本分片 19:18:49 实跑 exit 1（1 条未跟踪链接目标，按约定只记录、主线处理）。

---

## 0. 分片元信息

| 项 | 值 |
|---|---|
| subagentId | console-verify |
| 分片绝对路径 | F:\Project\ModelBus\evidence\agent-console-verify.md |
| 真实项目根 | F:\Project\ModelBus（未使用 F:\Project\_merged\DeepseekHarness\ModelBus junction 视图） |
| 采样时间 | 2026-11-12 19:10:02 起探测；19:14:55 首轮；19:18:48 ~ 19:18:49 +08:00 最终取证 |
| 环境 | Windows PowerShell 7.6.10；Python 3.12.10；git（C:\Program Files\Git\cmd\git.exe） |
| 写域 | 仅本文件。未改 PROGRESS.md / docs/ / tests/ / 任何配置 / tools\console\ 源码 / gateways/ |
| 进程约束 | 未启动或停止 7871 zgate 长驻网关；未改 /health 响应；未执行 git add / commit / push |
| 子进程可见性 | 全部经 [System.Diagnostics.ProcessStartInfo]：UseShellExecute=false + CreateNoWindow=true + WindowStyle=Hidden + RedirectStandardOutput/Error，无可见窗口 |
| 编码 | 每个子进程显式 PYTHONIOENCODING=utf-8、PYTHONUTF8=1，stdout/stderr 按 UTF-8 解码；PATH / SystemRoot / USERPROFILE / LOCALAPPDATA / TEMP 显式构造 |
| 临时目录 | %USERPROFILE%\AppData\Local\Temp\modelbus-console-verify-final-20261112-191848\（%.work 之外，未落源码树） |

## 1. 结论速览（3 条最关键）

| # | 结论 | 硬证据 |
|---|---|---|
| 1 | 门禁一绿一红：check-project.py **rc=0 / 8 项通过**；check-docs.py **rc=1**，唯一 FAIL 是 docs/reports/README.md 指向未跟踪的 MODEL-SYNC-20261112-1209.md | 见 §5 原始 stdout；git status 中该报告仍为 ?? |
| 2 | 3 个 .py 逐一 py_compile 全 rc=0；13 个文件脱敏扫描 25 条命中行全为字段名 / 脱敏正则 / 统计字段 / CSS mask-* 属性名子串，严正则复核 13 命中全为 sk-repeat、sk-position → **零真值凭据** | 见 §2、§3 |
| 3 | 零 CDN：4 个 HTML/CSS/JS 共 27 处 http(s):// 全在 vendor/tabler.min.css（注释主页、LICENSE、25 个 SVG XML 命名空间）；REMOTE_RESOURCE_REF_COUNT=0，index.html 4 个资源引用全为本地 / 路径 | 见 §4 |

补充：docs/README.md:33 的 CONSOLE.md 索引行存在、相对目标 docs/CONSOLE.md 存在、为纯文件链接（无锚点），docs/ 下 CONSOLE.md# 锚点引用 0 处，不存在锚点错配。

## 2. 逐文件 py_compile（不污染源码目录）

python 已在 PATH，定位原文：

```text
C:\WINDOWS\System32\where.exe python  →  RC=0
  %USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe
%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe --version  →  RC=0
  Python 3.12.10
C:\WINDOWS\System32\where.exe git  →  RC=0
  C:\Program Files\Git\cmd\git.exe
  C:\Program Files\Git\bin\git.exe
```

（python 已在 PATH，按任务书无需再跑 py -3；如实记录。）

编译命令原文（每个文件独立一次，cfile 定向 TEMP）：

```text
%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe -c "import os, py_compile, sys; src=sys.argv[1]; out=sys.argv[2]; os.makedirs(os.path.dirname(out), exist_ok=True); py_compile.compile(src, cfile=out, doraise=True); print('PY_COMPILE_OK ' + src + ' -> ' + out)" <SRC> <OUT>
```

| # | SRC | OUT（TEMP） | RC | stdout | stderr |
|---|---|---|---|---|---|
| 1 | F:\Project\ModelBus\tools\console\actions.py | ...\pyc\tools_console_actions.py.pyc | 0 | PY_COMPILE_OK F:\Project\ModelBus\tools\console\actions.py -> %USERPROFILE%\AppData\Local\Temp\modelbus-console-verify-final-20261112-191848\pyc\tools_console_actions.py.pyc | <empty> |
| 2 | F:\Project\ModelBus\tools\console\server.py | ...\pyc\tools_console_server.py.pyc | 0 | PY_COMPILE_OK F:\Project\ModelBus\tools\console\server.py -> %USERPROFILE%\AppData\Local\Temp\modelbus-console-verify-final-20261112-191848\pyc\tools_console_server.py.pyc | <empty> |
| 3 | F:\Project\ModelBus\tools\console\sources.py | ...\pyc\tools_console_sources.py.pyc | 0 | PY_COMPILE_OK F:\Project\ModelBus\tools\console\sources.py -> %USERPROFILE%\AppData\Local\Temp\modelbus-console-verify-final-20261112-191848\pyc\tools_console_sources.py.pyc | <empty> |

汇总原文：

```text
PY_COMPILE_FILE_COUNT=3
PYC_OUTPUT_DIR=%USERPROFILE%\AppData\Local\Temp\modelbus-console-verify-final-20261112-191848\pyc
PYC_FILES:
  tools_console_actions.py.pyc 3781B
  tools_console_server.py.pyc 16436B
  tools_console_sources.py.pyc 32364B
```

**源码目录未被污染**：19:10:02 编译前探测清单已含 tools\console\__pycache__\actions.cpython-312.pyc / server.cpython-312.pyc / sources.cpython-312.pyc 共 3 个既有 .pyc（CONSOLE_COUNT=13、PY_COUNT=3、WEB_COUNT=4）；本次 3 个产物全部写入 TEMP\pyc，文件名带 tools_console_ 前缀，与源码树 __pycache__ 无重叠。

## 3. 脱敏扫描（tools/console/ 全部 13 个文件）

任务书正则：`(?i)(apikey|api_key|token|secret|cookie|sk-|bearer)`；逐文件逐行 latin-1 解码后匹配，二进制行标 [BINARY]。
扫描脚本 SHA256（落 TEMP，可复现）：

```text
sensitive_scan.py  = EC40985C44B6FDC798898915F70CDF73F14FBE10E1E4BBCD9A766A7DD38A2D8D
true_value_scan.py = D8260B4719B02E5A542B57F55783C17DD7F25415319CE474CC998E2D9952A8D8
cdn_scan.py        = AB5D56914F8A3343AD76EFFD9A52FA072EAE4C0399C01B085F780A3D24C2B45F
```

扫描文件清单（13 个，SCANNED_FILE_COUNT=13）：

```text
tools/console/__pycache__/actions.cpython-312.pyc, tools/console/__pycache__/server.cpython-312.pyc, tools/console/__pycache__/sources.cpython-312.pyc, tools/console/actions.py, tools/console/server.py, tools/console/sources.py, tools/console/start-console.ps1, tools/console/static/app.css, tools/console/static/app.js, tools/console/static/favicon.svg, tools/console/static/index.html, tools/console/static/vendor/LICENSE-tabler.txt, tools/console/static/vendor/tabler.min.css
```

### 3.1 命中行原文（SENSITIVE_MATCH_COUNT=25，RC=0，stderr <empty>）

```text
HIT|tools/console/__pycache__/sources.cpython-312.pyc:48:[BINARY]:request-logsz.(?i)(access[_-]?token|refresh[_-]?token|id[_-]?token|auth[_-]?token|secret|cookie|passwd|password|credential|authorization|api[_-]?key|private|sk-|bearer)z7(?i)(sk-[A-Za-z0-9_-]{6,}|Bearer\s+[A-Za-z0-9._-]{12,})z
HIT|tools/console/__pycache__/sources.cpython-312.pyc:168:[BINARY]:SECRET_NAME..searchr".....MASK..scrub..list.
HIT|tools/console/__pycache__/sources.cpython-312.pyc:169:[BINARY]:SECRET_VALUE..sub).ru.....k..vs....   r ...r|...r|...u...s..........#.t..
HIT|tools/console/__pycache__/sources.cpython-312.pyc:420:[BINARY]:total_tokensr....N).rq...r6.....int..floatr....s....  r ...r....z&traffic.<locals>.fn.<locals>.<genexpr> ...s?............G..t.!.. .......~.!6...e.
HIT|tools/console/__pycache__/sources.cpython-312.pyc:432:[BINARY]:..filer....r....r......ok_rate..avg_ms..tokens..by_model..by_status..hours..filesr....)..
HIT|tools/console/__pycache__/sources.cpython-312.pyc:476:[BINARY]:accessToken.
HIT|tools/console/__pycache__/sources.cpython-312.pyc:477:[BINARY]:refreshToken..expiresAt)...idr'...r(.....credential_present.
HIT|tools/console/sources.py:34:[TEXT]:# ................................................ token...request-logs ... total_tokens /
HIT|tools/console/sources.py:35:[TEXT]:# prompt_tokens / completion_tokens / cache_hit_tokens ................................................
HIT|tools/console/sources.py:36:[TEXT]:SECRET_NAME = re.compile(
HIT|tools/console/sources.py:37:[TEXT]:    r"(?i)(access[_-]?token|refresh[_-]?token|id[_-]?token|auth[_-]?token|"
HIT|tools/console/sources.py:38:[TEXT]:    r"secret|cookie|passwd|password|credential|authorization|api[_-]?key|private|sk-|bearer)"
HIT|tools/console/sources.py:40:[TEXT]:SECRET_VALUE = re.compile(r"(?i)(sk-[A-Za-z0-9_-]{6,}|Bearer\s+[A-Za-z0-9._-]{12,})")
HIT|tools/console/sources.py:128:[TEXT]:        return {k: (MASK if SECRET_NAME.search(str(k)) else scrub(v)) for k, v in obj.items()}
HIT|tools/console/sources.py:132:[TEXT]:        return SECRET_VALUE.sub(MASK, obj)
HIT|tools/console/sources.py:137:[TEXT]:    return SECRET_VALUE.sub(MASK, str(value or ""))[:width]
HIT|tools/console/sources.py:297:[TEXT]:        toks = sum(r.get("total_tokens") or 0 for r in rows
HIT|tools/console/sources.py:298:[TEXT]:                   if isinstance(r.get("total_tokens"), (int, float)))
HIT|tools/console/sources.py:311:[TEXT]:            "tokens": toks,
HIT|tools/console/sources.py:336:[TEXT]:                "credential_present": bool(au.get("accessToken") or au.get("refreshToken")),
HIT|tools/console/sources.py:451:[TEXT]:        tr = _safe(traffic, {"file": None, "count": 0, "ok_rate": 0, "avg_ms": 0, "tokens": 0})
HIT|tools/console/sources.py:470:[TEXT]:                        "tokens": tr.get("tokens", 0)},
HIT|tools/console/static/app.js:141:[TEXT]:      ["...... token", `<span class="num">${n(tr.tokens)}</span>`],
HIT|tools/console/static/app.js:254:[TEXT]:      kpi("...... token", n(d.tokens ?? 0), "total_tokens ......"),
HIT|tools/console/static/vendor/tabler.min.css:7:[TEXT]::root{--tblr-blue:oklch(54.6% 0.1724 254.2deg);--tblr-azure:oklch(66.26% 0.1358 246.81deg);--tblr-indigo:oklch(55.66% 0.2082 268.35deg);--tblr-purple:oklch(57.83% 0.2186 319.15deg);--tblr-pink:oklch(58.81% 0.201 5.25deg);--tblr-red:oklch(58.29% 0.1941 25.59deg);--tblr-orange:oklch(68.51% 0.1954 44.5...[TRUNCATED 300]
SENSITIVE_MATCH_COUNT=25
SCANNED_FILE_COUNT=13
```

（脚本同时打印逐 token 的 MATCH_TOKEN 明细 100+ 行，此处按「列出命中行」口径贴全部 25 条 HIT；明细可由 TEMP 脚本原样复现。）

### 3.2 字段名/占位符 vs 真值 分类

| 分类 | 文件与行 | 条数 | 判定 |
|---|---|---|---|
| 编译产物符号/常量 | __pycache__/sources.cpython-312.pyc:48,168,169,420,432,476,477 | 7 | [BINARY]，是源码里脱敏正则与字段名的编译镜像，非真值 |
| 脱敏正则与掩码逻辑 | sources.py:36,37,38,40,128,132,137 | 7 | 正则定义 SECRET_NAME / SECRET_VALUE、MASK 替换，属检测规则本身 |
| 统计字段名/注释 | sources.py:34,35,297,298,311,451,470 | 7 | total_tokens / prompt_tokens / cache_hit_tokens / tokens 是计数指标名 |
| 凭据存在性布尔 | sources.py:336 | 1 | credential_present: bool(au.get("accessToken") or au.get("refreshToken"))，只记 has_key 式存在性，不落值 |
| UI 显示字段名 | static/app.js:141,254 | 2 | KPI 卡片显示「token」用量数字 |
| CSS 属性名子串 | static/vendor/tabler.min.css:7 | 1 | minified CSS 的 mask-repeat / mask-position 被 sk- 规则命中 |
| **合计** | | **25** | 全部为字段名 / 正则 / 占位符 / 统计指标 / 属性名 |

### 3.3 真值复核（更严正则）

复核正则：`(?i)(sk-[A-Za-z0-9_-]{6,}|Bearer\s+[A-Za-z0-9._-]{12,}|(?:api[_-]?key|secret|token|cookie)\s*[:=]\s*["'][^"']{8,}["'])`

```text
TRUE_VALUE_MATCH_COUNT=13
TRUE_VALUE_SCANNED_FILE_COUNT=13
13 条命中全部位于 tools/console/static/vendor/tabler.min.css:7，匹配文本仅两种：sk-repeat / sk-position
样例：TRUE_VALUE_HIT|tools/console/static/vendor/tabler.min.css:7|sk-repeat|:root{--tblr-blue:oklch(54.6% 0.1724 254.2deg);...[TRUNCATED 300]
样例：TRUE_VALUE_HIT|tools/console/static/vendor/tabler.min.css:7|sk-position|:root{--tblr-blue:oklch(54.6% 0.1724 254.2deg);...[TRUNCATED 300]
```

**零真值结论**：13 条全是 CSS mask-* 属性名被截断出的 sk- 前缀，不是 sk- 开头的 API key；全仓 tools/console/ 未发现任何 key / token / cookie 真实值。凭据相关代码只以字段名、检测正则、MASK 掩码、credential_present 存在性布尔形式出现，符合「只记 has_key 之类存在性」的脱敏红线。

**风险备注（只记录，不修）**：tools/console/__pycache__/ 下 3 个 .pyc 随 ?? tools/console/ 一起未跟踪；若主线整目录 git add，会把运行时编译产物带进版本库，建议提交前排除。

## 4. 零 CDN 核查

扫描范围：tools/console/static/ 下全部 .html / .css / .js（CDN_SCANNED_FILES=4）。RC=0，stderr <empty>。

```text
FILE_LINE_HITS tools/console/static/app.css = 0
FILE_LINE_HITS tools/console/static/app.js = 0
RESOURCE_REF|tools/console/static/index.html:8:/favicon.svg
RESOURCE_REF|tools/console/static/index.html:10:/vendor/tabler.min.css
RESOURCE_REF|tools/console/static/index.html:12:/app.css
RESOURCE_REF|tools/console/static/index.html:89:/app.js
FILE_LINE_HITS tools/console/static/index.html = 0
URL|tools/console/static/vendor/tabler.min.css:2:https://tabler.io
URL|tools/console/static/vendor/tabler.min.css:5:https://github.com/tabler/tabler/blob/master/LICENSE
URL|tools/console/static/vendor/tabler.min.css:7:http://www.w3.org/2000/svg   （共 25 处，均为内嵌 SVG data URI 的 XML 命名空间）
FILE_LINE_HITS tools/console/static/vendor/tabler.min.css = 3
CDN_URL_MATCHES=27
CDN_LINE_MATCHES=3
REMOTE_RESOURCE_REF_COUNT=0
CDN_SCANNED_FILES=4
CDN_FILE_LIST=tools/console/static/app.css,tools/console/static/app.js,tools/console/static/index.html,tools/console/static/vendor/tabler.min.css
```

外链归类：27 处 = 1 处 https://tabler.io（vendor 文件头注释里的项目主页）+ 1 处 https://github.com/tabler/tabler/blob/master/LICENSE（文件头注释里的许可证链接）+ 25 处 http://www.w3.org/2000/svg（第 7 行 SVG data URI 的 XML 命名空间，不发起网络请求）。app.css / app.js / index.html 三处业务文件 http(s):// 命中均为 0。

index.html:9 原文佐证：`<!-- Tabler 1.7.4 · MIT · 42,052 stars · 本地 vendor 单文件，零 CDN、零外链 -->`；<script>/<link>/<img> 全部为本地 / 路径，REMOTE_RESOURCE_REF_COUNT=0。

**结论：运行时零 CDN / 零远端资源加载**。

## 5. 门禁脚本（贴退出码与原始输出）

### 5.1 PYTHONIOENCODING=utf-8 python tools/check-docs.py → **RC=1**

```text
EXE=%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe
ARGV=tools\check-docs.py
RC=1
--- STDOUT ---
[FAIL] 1 个问题：
    docs/reports/README.md: 链接目标不会进仓库（未跟踪或被 .git/info/exclude 挡住）→ MODEL-SYNC-20261112-1209.md
--- STDERR ---
<empty>
```

按分片约定「若报链接目标不在仓库只记录、不要 git add -N（主线处理）」，本分片**未执行任何 git add**，只记录。git status 中 ?? docs/reports/MODEL-SYNC-20261112-1209.md 此刻仍为未跟踪，正是该 FAIL 的成因。

> **与主线口径的差异（如实回报）**：lead 于 19:14 消息称 check-docs.py exit 0；本分片 19:18:49 独立实跑为 exit 1。差异来自该链接目标在本分片采样时仍未被跟踪；主线做完 git add -N 或等价处理后需复跑确认。此条不改写、不隐藏。

### 5.2 PYTHONIOENCODING=utf-8 python tools/check-project.py → **RC=0**

```text
EXE=%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe
ARGV=tools\check-project.py
RC=0
--- STDOUT ---
[OK] zgate.json 真值: children=2 ports=7863,8790 upstreams=7
[OK] 正本指针: bridge.go 在位且含 forwardStream，门面无退役 JS 正本口径
[OK] 网关实现: /v1/models 聚合 + /health 段表由 keys.Channels 驱动 + QN/GM/HJ Bearer 在位
[OK] 同步策略: 默认不 push（-Push 才推）+ §35 现行不发探测口径在位
[OK] 换行/BOM: 13 个脚本全部符合（PS1 BOM+LF / CMD·VBS·sh 无 BOM+LF）
[SKIP] PS1 语法: 本机无 powershell/pwsh（CI ubuntu 跳过）
[OK] 流式准入报告: 18 条全量视图可解析；PASS 13 / WARN 1 / FAIL 0 / SKIP 2 / EXEMPT 0 / RECOVERED 2（模型健康只记录，不阻断提交）
[OK] 流式准入接线: 同步钩子 / --changed / RECOVER_TOKENS / RETRY_STATES / 加密分流识别 / 契约正本 / 索引 七处全在位
[OK] check-project: 8 项通过（语义 / 换行BOM / PS1 / 流式接线）
--- STDERR ---
<empty>
```

（[SKIP] 一条如实保留：脚本自报本机无 powershell/pwsh；本机实际有 PowerShell 7.6.10，属脚本自身探测口径，不影响 rc=0 与 8 项通过结论。）

## 6. git 原文

### 6.1 git -C F:\Project\ModelBus status --short → RC=0，stderr <empty>

```text
 M PROGRESS.md
 M docs/CONSOLE.md
 M docs/MAINTENANCE.md
 M docs/PITFALLS.md
 M docs/README.md
 M docs/TOOLS.md
 M docs/reports/README.md
?? docs/reports/MODEL-SYNC-20261112-1209.md
?? evidence/agent-audit.md
?? evidence/agent-endpoints.md
?? evidence/go-model-sync-20261112-120012.md
?? tools/console/
```

### 6.2 git -C F:\Project\ModelBus diff --stat → RC=0

```text
--- STDOUT ---
 PROGRESS.md            |  78 +++++++++
 docs/CONSOLE.md        | 450 ++++++++++++++++++++++++++-----------------------
 docs/MAINTENANCE.md    |   3 +
 docs/PITFALLS.md       |   7 +
 docs/README.md         |   2 +-
 docs/TOOLS.md          |   1 +
 docs/reports/README.md |   1 +
 7 files changed, 331 insertions(+), 211 deletions(-)
--- STDERR ---
warning: in the working copy of 'docs/MAINTENANCE.md', CRLF will be replaced by LF the next time Git touches it
warning: in the working copy of 'docs/TOOLS.md', CRLF will be replaced by LF the next time Git touches it
warning: in the working copy of 'docs/reports/README.md', CRLF will be replaced by LF the next time Git touches it
```

变化说明（非臆测，两次实跑快照）：19:14:55 首轮为 PROGRESS.md | 37 ++++ / 7 files changed, 290 insertions(+), 211 deletions(-)；19:18:49 复跑为 78 +++++ / 331 insertions(+)。主线并行追加 PROGRESS.md，属预期，diff --stat 原文以 19:18:49 为准。3 条 CRLF warning 原样保留，未做任何换行改动。

## 7. docs/README.md 的 CONSOLE.md 索引行与锚点

原始命令：Select-String -LiteralPath F:\Project\ModelBus\docs\README.md -Pattern `CONSOLE\.md` -Encoding utf8；全 docs/ 递归搜 CONSOLE\.md#；读 docs/CONSOLE.md 首行。

索引行原文（docs/README.md:33，INDEX_MATCH_COUNT=1）：

```text
docs/README.md:33:| [CONSOLE.md](CONSOLE.md) | **可视化后台正本（2026-11-12 已落地 v3）**：Tabler 1.7.4 高星后台外壳 + Microsoft Fluent 2 语义令牌桥接与十二条落地规则、8 页信息架构与字段来源、独立 Python 服务而非塞进网关的取舍、统一响应包与静态/vendor 路由、脱敏红线与同源 POST 校验、资源占用只读候选、验收实测 |
INDEX_LINK_TARGET=docs/CONSOLE.md
INDEX_TARGET_EXISTS=True
CONSOLE_H1:
  # ModelBus 控制台（Console）
ANCHOR_REF_COUNT=0
```

结论：索引行**存在**且唯一；链接为纯相对文件链接 `[CONSOLE.md](CONSOLE.md)`，不含 # 锚点，目标 docs/CONSOLE.md 实际存在（H1 = `# ModelBus 控制台（Console）`）；docs/ 下 CONSOLE.md# 形式的锚点引用 0 处，因此**不存在锚点对不上的问题**。

## 8. 执行器异常（已自愈，不影响取证）

两次 run_code 解析失败，原始报错照贴；取证数据全部来自修复后的重跑：

```text
Error: code run failed (exception): Expected ident
  （把 PowerShell here-string '...' 直接塞进 TS 模板字面量，解析器提前断句）
glob search failed (exit 2): rg: F:\Program Files\DeepSeekRuntime\resources\app.asar\dsh: IO error for operation on ...: 系统找不到指定的路径。 (os error 3)
  （运行时 checkout 实为 F:\Program Files\DeepSeek Harness\...，带空格；Test-Path 复核为 False）
```

修法：PowerShell 命令改字符串数组 .join(换行)；Python 辅助脚本 UTF-8→Base64 后由 pwsh 解码落 TEMP 再执行；本报告的反引号/围栏用占位符还原。修复后一次跑通 12 组 Invoke-Capture，全部拿到 RC 与原始 stdout/stderr。跨会话教训库命中同类 Lmwbwppqz / Lmwbu36n6，已按会话要求补记一条。

## 9. 原始命令清单（可整行复制复核）

```text
C:\WINDOWS\System32\where.exe python
C:\WINDOWS\System32\where.exe git
%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe --version
%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe -c "import os, py_compile, sys; src=sys.argv[1]; out=sys.argv[2]; os.makedirs(os.path.dirname(out), exist_ok=True); py_compile.compile(src, cfile=out, doraise=True); print('PY_COMPILE_OK ' + src + ' -> ' + out)" <SRC> <OUT>
%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe %TEMP%\modelbus-console-verify-final-20261112-191848\sensitive_scan.py F:\Project\ModelBus
%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe %TEMP%\modelbus-console-verify-final-20261112-191848\true_value_scan.py F:\Project\ModelBus
%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe %TEMP%\modelbus-console-verify-final-20261112-191848\cdn_scan.py F:\Project\ModelBus
PYTHONIOENCODING=utf-8 %USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe tools\check-docs.py
PYTHONIOENCODING=utf-8 %USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe tools\check-project.py
"C:\Program Files\Git\cmd\git.exe" -C F:\Project\ModelBus status --short
"C:\Program Files\Git\cmd\git.exe" -C F:\Project\ModelBus diff --stat
Select-String -LiteralPath F:\Project\ModelBus\docs\README.md -Pattern 'CONSOLE\.md' -Encoding utf8
Get-ChildItem -LiteralPath F:\Project\ModelBus\docs -Recurse -File -Filter *.md | Select-String -Pattern 'CONSOLE\.md#' -Encoding utf8
Get-Content -LiteralPath F:\Project\ModelBus\docs\CONSOLE.md -TotalCount 1 -Encoding utf8
```

（所有子进程统一 env：PATH=%USERPROFILE%\AppData\Local\Programs\Python\Python312;%USERPROFILE%\AppData\Local\Programs\Python\Python312\Scripts;C:\Program Files\Git\cmd;C:\Program Files\Git\bin;C:\WINDOWS\System32;C:\WINDOWS；SystemRoot=C:\WINDOWS；USERPROFILE=%USERPROFILE%；LOCALAPPDATA=%USERPROFILE%\AppData\Local；TEMP/TMP=%TEMP%；PYTHONIOENCODING=utf-8；PYTHONUTF8=1；cwd=F:\Project\ModelBus。）

## 10. 未解决项 / 交回主线

1. **check-docs.py exit 1**：docs/reports/README.md → MODEL-SYNC-20261112-1209.md 未跟踪。按约定本分片未 git add -N，请主线处理后复跑到 exit 0。
2. **tools/console/__pycache__/ 3 个 .pyc** 随 ?? tools/console/ 未跟踪，整目录提交前建议排除（只记录，未修）。
3. **3 条 CRLF→LF warning** 来自 git diff --stat（MAINTENANCE.md / TOOLS.md / reports/README.md），如实记录，未改任何换行。
4. 7872 后台「能启动、能打开、数据对得上」的运行态 E2E 不属本分片范围；本分片只做静态门禁与脱敏验证，未启停任何服务。

## 11. 自检

- 本文件写入后由本分片用 read 工具回读一次确认行数，行数在给 lead 的回报中给出。
- self-report 不作结论：以上每个数字 / rc / 输出行均来自 19:18:48~19:18:49 的实际命令 stdout/stderr，落在 TEMP 的三个 .py 扫描脚本带 SHA256 可复现。
- 本分片只验证，未修任何文件（写域仅本证据文件）。