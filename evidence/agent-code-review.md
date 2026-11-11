# 第一方源码全量代码审查 + ZCode 专项适配台账（code-review 分片）

> **一句话**：五维审查定位 30 项证据带 file:line 的问题/记录；按主代理验收排除表把 ZCode 命中拆成契约层 113 行（勿动）与实现层净命中 129 行（96 必须改 / 24 历史勿动 / 9 可保留兼容），逐处台账附原文、分类与 DSH 目标形态。

---

## 0. 取样、范围与方法

- **主取样时刻**：`SAMPLE_AT=2026-11-11T07:57:49.610Z`（本地 15:57:49，node:fs 全量统计）；编码/换行/icon/历史残留另一次取样 `2026-11-11T15:59:37+08:00`；PowerShell 交叉复核 `2026-11-11T16:02`。
- **本仓已被多路子代理并发改动**，第 6 路 6 脚本 `git mv` 在我早期取样间隙落盘（`15:52` 复核确认），旧快照作废；主代理验收按当前磁盘复核。
- **范围**（任务书）：`tools/**`（.py/.ps1/.js）、`providers/**`（.py/.js）、`gateways/**`（.go/.py/.js/.json）、根 `sync-models.ps1`、`assets/icon.svg`；排除 `third-party/**`、`gateways/upstream/**`、`docs/**`、`memories/**`、`evidence/**`、`tests/**`、`catalog/**`、`.work/**`、`CHANGELOG.md`、`PROGRESS.md`、`NOTICE`、`*.bak*`、`*_test.go`。
- **纪律**：只读分析；唯一写产物本文件；凭据零落盘（报告只写环境变量名，不写任何值）；未改 `PROGRESS.md`/`docs/`/`tests/`/`provider_config.json`/配置；未 git add/commit/push；未重启 zgate。
- **检索**：`codegraph_status` 实测 `Not initialized`（按 AGENTS §3 不自行 init），全部用 `grep` / `glob` / `read` / `node:fs`；未加载新 skill。
- **可复跑命令**（PowerShell 7+，CMD 写法同理）：
```powershell
cd /d F:\Project\ModelBus
git -C F:\Project\ModelBus ls-files
$files = Get-ChildItem -Path F:\Project\ModelBus\tools,F:\Project\ModelBus\providers,F:\Project\ModelBus\gateways -Recurse -File | Where-Object { $_.Extension -in @('.py','.ps1','.js','.go') -and $_.FullName -notmatch '\\upstream\\' -and $_.Name -notmatch '_test\.go$|\.bak' }
Write-Output ('PS_FILES=' + $files.Count)
Write-Output ('PS_HITS=' + ($files | Select-String -Pattern 'zcode|zcodium|zc_').Count)
```
```powershell
# 旧脚本名在第一方可执行源码里应为 0 命中
Get-ChildItem F:\Project\ModelBus\tools,F:\Project\ModelBus\providers,F:\Project\ModelBus\gateways -Recurse -File -Include *.py,*.ps1,*.js,*.go | Select-String -Pattern 'workbuddy_zcode_sync|workbuddy_probe_zcode|zcode_effective_body|qoder_zcode_sync|qoder_probe_zcode|qwen_zcode_sync' | Measure-Object
```

### 数字基线（可独立复跑）

| 指标 | 值 | 口径 |
|---|---|---|
| `FILES` | 66 | 排除上述目录/文件名后的第一方 `.py/.ps1/.js/.go` + 根 `sync-models.ps1` |
| `BYTES` | 971440 | `node:fs.readFileSync().length` 逐文件累加 |
| `LINES` | 24282 | 按 `\r\n|\n|\r` 切分累加 |
| `HITS_TOTAL` | 242 | 正则 `(?i)zcode|zcodium|zc_` 逐行命中（含契约层） |
| `CONTRACT` | 113 | 契约层/历史/署名，按主代理验收排除表剔除 |
| `NET_C_IMPL` | 129 | 实现层净命中（台账逐处展开） |
| `BY_DIR` | tools 121 / providers 100 / gateways 20 / 根 `sync-models.ps1` 1 | 全量命中按一级目录 |
| `NET_BY_DIR` | providers 76 / tools 42 / gateways 11 | 净命中按一级目录 |
| `CONTRACT_BREAKDOWN` | C-PATH 64 / C-ENV 16 / C-ID 13 / C-KEY 8 / C-VENDORFILE 7 / C-APPDATA 5 | 见 §4 分类口径 |
| `TOOLS_GATEWAYS_NET` | 53 | 主代理要求单列的 tools/ + gateways/ 叙述性 ZCode 逐处清单 |
| git tracked | 232 | `git -C F:\Project\ModelBus ls-files`；byExt: md 102 / py 40 / go 39 / json 11 / ps1 9 / js 6 / yml 4 / 其余 |
| CRLF 文件 | 7 | `gateways/legacy-router/unified-router.js`、`gateways/zgate/smoke_test.py`、`providers/qoder/qoder_sync.py`、`providers/qwen/qwen_sync.py`、`tools/check-docs.py`、`tools/check-secrets.py`、`tools/model_probe.py` |
| UTF-8 BOM PS1 | 8 | `sync-models.ps1` + `tools/zgate-lifecycle/{current-models,deploy-zgate,ensure-zgate,install-lifecycle,install-sync-schedule,start-zgate-nw,swap-zgate}.ps1`（PS5.1 按 GBK 读无 BOM UTF-8 会乱码，BOM 是兼容标记，非缺陷） |
| `assets/icon.svg` | 1 命中 | `assets/icon.svg:1` `aria-label="AI 模型供应商接入 ZCode"`，属对外文案（叙述层） |
| 旧脚本名残留 | 681 命中 / 第一方源码 0 | 681 全在 `.work/` 备份、`docs/`、`evidence/agent-*.md`、`memories/`、`CHANGELOG.md`、`PROGRESS.md`、`third-party/`、`tools/rename-to-modelbus.ps1`（历史脚本自身）；第一方可执行源码 `OLDNAME_IN_FIRSTPARTY_SRC=0` |
| PowerShell 交叉复核 | `PS_FILES=65` `PS_HITS=241` | 与 node 的 66/242 正好差 1 文件 1 命中：PS 口径只扫三个子目录，漏根 `sync-models.ps1` 的那 1 处 C-PATH 字面量；两口径互证 |

---

## 1. 五维审查：问题清单（file:line / 严重度 / 证据 / 修复建议）

### ① 正确性

**[中] C1 探活结果两份路径字面量无共享参数 → 摘除静默失效**
- 证据：`sync-models.ps1:289` 调 `tools\model_probe.py` **未传 `--out`**；`sync-models.ps1:291` `$probeOut = Join-Path $env:USERPROFILE ".zcode\v2\model_probe.json"` 与 `tools/model_probe.py:46` `DEFAULT_OUT = Path.home() / ".zcode" / "v2" / "model_probe.json"` 分处 PowerShell/Python 硬写；`sync-models.ps1:297` `$probeAll = @($probeJson.PSObject.Properties).Count`；`sync-models.ps1:305` `if ($probeAll -gt 0 -and ($probeOk * 2 -ge $probeAll)) {`；`sync-models.ps1:309` `Say ("探活 $probeOk/$probeAll 可用，成功率过低，本轮不据此摘模型")`。
- 机制：任一方改默认，或 `USERPROFILE ≠ Path.home()`，或注入 `--config` 指向 fixture 后写入点偏移，`sync-models.ps1` 读到的文件为空/旧 → `$probeAll=0` → 走 `:309` 分支，本轮永远不按探活摘死型号，且无 WARN。注：`ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` 只改 `tools/model_probe.py:52-58 config_path()`，不改 `out`（早期「env 改向即恒 0」的表述已修正）。
- 建议：`sync-models.ps1:289` 显式传 `--out $probeOut`；或两边统一从 `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` 派生目录；解析失败/文件缺失时打 WARN。

**[中] C2 `model_probe.json` 非原子整份重写 + 静默清空 ever_ok 历史**
- 证据：`tools/model_probe.py:233-237` `results = json.loads(out_path.read_text(encoding="utf-8"))` / `except Exception:` / `results = {}`；`tools/model_probe.py:259` `"ever_ok": bool(previous.get("ever_ok")) or previous.get("status") == "ok" or status == "ok",`；`tools/model_probe.py:267` `out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")`（每个模型循环写一次整份）。
- 机制：进程中途被杀/并发写留半截 JSON；下次启动 `:236-237` 静默 `results={}`，`ever_ok` 历史全丢，历史上探活成功的型号会被判死摘除。
- 建议：照 `tools/dsh_sync.py:484-499 _atomic_write(path: Path, text: str) -> None`（`tmp = path.with_name(path.name + ".tmp-dshsync")` + `os.replace(tmp, path)` + 3 次 `PermissionError` 重试）改 tmp+replace；`:236` 改成 WARN + 保留上一份备份。

**[中] C3 `--check` 也校验并写 DSH 凭据，无 apiKey 时整链 exit 2**
- 证据：`tools/dsh_sync.py:590` `patch_key = providers[0]["apiKey"]`；`:591-593` `_credentials_state(args.dsh_home / ".credentials.yaml", patch_key, args.apply)` 在 `--check` 也执行；`tools/dsh_sync.py:534` `def _credentials_state(path: Path, patch_key: str | None, apply: bool) -> tuple[bool, Path | None]:`；`:544-545` `if not patch_key:` / `raise DshSyncError("ZCode provider 配置里没有 gateway apiKey，无法写 DSH 凭据引用")`；`:644-649` `raise SystemExit(_main())` / `except DshSyncError` / `raise SystemExit(2)`。
- 机制：只读 check 依赖写路径前置条件；多 provider 时只认 `providers[0]`，key 不一致静默放过。`sync-models.ps1:345` 的 `--check` 因此可能非预期失败。
- 建议：`apply=True` 分支才做凭据校验；或 `--check` 只报「将变更」不抛错；校验所有 provider 的 apiKey 是否一致再取用。

**[中] C4 fixture 运行仍写真实 quota-windows**
- 证据：`tools/model_alias.py:2605` `write_quota_windows()` 无条件调用；`:1960` `QUOTA_WINDOWS = Path.home() / ".zcode" / "v2" / "quota-windows.json"`；`:1963` `def write_quota_windows(path: Path = QUOTA_WINDOWS) -> None:`。对照 `:2608-2611` 已加 fixture 保护（`if not args.no_dsh and args.config is None: sync_deepseek_harness(path)`）——说明 DSH 投影已守，但 quota-windows 单路径漏传。
- 建议：`write_quota_windows()` 按 `args.config` 派生 path，或加 `--quota-out` 显式传参。

**[中] C5 报告索引非原子重写 + 表头缺失时写成坏表 + EOL churn**
- 证据：`tools/sync_report.py:338` `def update_index(report_name: str, current: dict, changes: dict, baseline: bool) -> None:`；`:341` `text = index.read_text(encoding="utf-8")`；`:346` 表头 `"| 时间 | 报告 | 总数 | 新增 | 移除 |\n|---|---|---|---|---|\n"`；`:353` `header, _, rest = text.partition("|---|---|---|---|---|\n")`；`:355` `text = text.rstrip() + "\n" + row`；`:358` `index.write_text(text, encoding="utf-8")`。
- 机制：`read+partition+write` 非原子；CRLF 源每轮被 `write_text` 改成 LF 产生 EOL churn；索引文件存在但表头不是精确串时 `:354` `if not rest` 把 `row` 直接追加到文件尾，得到无表头的坏表。
- 建议：用 `_atomic_write` 同款；`:354` 无 rest 时重建标准表头再插 row；写回时保留原 EOL。

**[低] C6 DSH 投影文本级 YAML 定位 + 固定临时名 + 账本非原子**
- 证据：`tools/dsh_sync.py:351` `dsh_id = KNOWN_PROVIDER_IDS.get(provider_id)`、`:354` `dsh_id = "zcode-" + (slug or "group")`、`:471` `if not str(key).startswith("zcode-")` 成对前缀约定（契约层，记录）；`:391` 文本级定位、`:422-423` 找不到时把新块追加到文件尾；`:486` 固定 `.tmp-dshsync`；`:141-149` `_remember_model_ids` 用 `DSH_LEDGER.write_text(...)` 非原子。
- 建议：并发运行加文件锁/唯一 tmp 名；账本改 `_atomic_write`。

**[低] C7 `sync_report.py` 入口无异常包装**
- 证据：`tools/sync_report.py:410` `current = snapshot(alias_path(args.alias_map), config_path(args.config))` → `:82` `data = json.loads(alias_file.read_text(encoding="utf-8"))` / `:71` `cfg = json.loads(cfg_path.read_text(encoding="utf-8"))` 无 try/except；`:413` `previous = {} if baseline else json.loads(spath.read_text(encoding="utf-8"))` 同样。文件缺失/坏 JSON 直接 traceback（对比 `gateways/zgate/smoke_test.py:28-34` 已用 `raise SystemExit(...)` 包好）。
- 建议：入口包成 `SystemExit("…")`，退出码可预期。

**[低] C8 无效代理串静默退化直连 + 代理 transport 缓存无上限**
- 证据：`gateways/zgate/internal/router/egress.go:44` `cache map[string]*http.Transport`、`:50` `return &EgressRouter{base: base, cache: map[string]*http.Transport{}}`、`:56` `if t, ok := e.cache[proxy]; ok {`、`:62` `} else if u, err := url.Parse(proxy); err == nil {`、`:65` `e.cache[proxy] = t`。`url.Parse` 失败时无 else 分支、无 WARN，`t.Proxy` 保持 base 的直连。
- 建议：加 `else { WARN 无效 proxy，拒绝或显式直连 }`；`cache` 加上限/LRU。

**[低] C9 JS 别名缓存只比 mtime，不与 Go 同口径比 size（实测坐实）**
- 证据：`gateways/legacy-router/unified-router.js:194` `let aliasCache = { mtime: -1, data: null };`、`:199` `if (stat.mtimeMs !== aliasCache.mtime) {`、`:201` `mtime: stat.mtimeMs,`（未存 size）；同文件 `:158` `return `${p}:${st.mtimeMs}:${st.size}`;` 的 `keyStamp()` **已比 size**；`gateways/zgate/internal/alias/alias.go:88` `same := m.data != nil && stat.ModTime().Equal(m.mtime) && stat.Size() == m.size`（`:86-87` 注释明写 mtime 粒度问题）。
- 机制：文件系统时间戳粒度内改写且 mtime 被保留/未变、仅 size 变时，JS 旧路由漏加载新 alias map；Go 侧不会。
- 建议：`aliasCache` 增 `size` 字段，判据改成 `mtime !== || size !==`。

**[低] C10 探活静默 except / 配置读取无保护**
- 证据：`tools/model_probe.py:66-70` `load_alias()` 的 `except Exception: return {}`；`:108` `except Exception as exc:`（此处有 WARN，记录）；`:139`、`:193` 静默 `except`；`:223` `cfg = json.loads(config_path(args.config).read_text(encoding="utf-8"))` 无 try/except。
- 建议：缺 alias/坏配置打 WARN 且显式退出，别静默当空配置继续探测。

**[记录·非缺陷] C11 并发 Reload**：`gateways/zgate/internal/alias/alias.go:85-105` 并发各读一次、`:101-105` 写入顺序不定，但内容同源最终一致，可接受；不列为缺陷。

### ② 安全

**[低·记录] S1 key 明文写进 provider_config.json**：`providers/workbuddy/workbuddy_sync.py:776` `"access": {"type": "api-key", "apiKey": args.api_key},`。这是 ZCode 兼容投影的契约要求（脚本自己读配置），与 AGENTS §2「key 只从环境变量读、不进缓存/文档」口径有差异；文件 gitignored、本机不入库。建议：维持现状但文档标注「该文件是凭据载体，等同密钥库」，不要在报告/日志回显其值。
**[低] S2 上游错误正文前 300 字进异常/日志**：`providers/qoder/qoder_sync.py:132` `detail = exc.read().decode("utf-8", "replace")[:300]` + `:133` `raise SystemExit(f"GET {url} -> HTTP {exc.code}: {detail}") from exc`。上游若回显鉴权头片段会落盘到计划任务日志。建议：只留 HTTP code + 错误类型，或脱敏后再截断。
**[低] S3 上游正文落盘到探活结果**：`tools/model_probe.py:253` `"detail": (detail or error)[:300],`。本机 `~/.zcode/v2/model_probe.json` 不入库，但可能被 `sync_report.py` 的报告引用。建议：对 `detail` 做正则脱敏。
**[低] S4 读不了的文件当干净放行**：`tools/check-secrets.py:153-154` `except OSError:` / `continue`（`:133` 打开文件）。权限拒绝的文件会被门禁静默跳过。建议：记 `WARN` 并让门禁 exit 非 0 或至少可配置严格模式。
**[低] S5 子进程 Args 原样进日志**：`gateways/zgate/internal/supervisor/supervisor.go:251` `s.log.Infof("启动子进程 %s: %s %v (cwd=%s)", k.name, cfg.Exe, cfg.Args, cfg.Cwd)`。当前 `cfg.Args` 是路径参数，但若将来塞 token 会落盘。建议：对 Args 做与 `router.go:410 maskProxy` 同款脱敏。

**[正面·非缺陷] S6 无命令注入**：`gateways/zgate/main.go:431` `out, err := exec.Command("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script).CombinedOutput()`；`script` 由 `:425-430 fmt.Sprintf` 拼接，路径来自 `os.Executable()`/APPDATA，且 `:424` `psq := func(p string) string { return strings.ReplaceAll(p, "'", "''") }` 转义 PowerShell 单引号；`:429` 的 `ZCode 统一入口 (zgate)` 只是字符串描述。
**[正面·非缺陷] S7 代理凭据已脱敏**：`gateways/zgate/internal/router/router.go:410` `func maskProxy(proxy string) string {` / `:424` `return strings.Replace(u.String(), u.User.String()+"@", u.User.Username()+":***@", 1)` / `:430` `func hopKeyForLog(hop alias.Hop) string {`；`:427-429` 注释说明冷却表必须用原始 hopKey、日志一律用掩码。
**[正面·非缺陷] S8 凭据七通道加载**：`gateways/zgate/internal/keys/keys.go:1-2` 包注释 `// Package keys finds the upstream credentials without ever writing them`；`:124` `func Load(providerConfig, wbGatewayConfig, qoderEnvFile, qwenEnvFile, qiniuEnvFile, geminiEnvFile, hajimiEnvFile string) Set {`。

### ③ 可维护性

**[中] M1 DSH 投影两条重复路径、口径不一致**
- 证据：`tools/model_alias.py:2008` `def sync_deepseek_harness(config_path: Path) -> None:` → `:2023-2031` `subprocess.run([sys.executable, str(script), "--apply", "--config", str(config_path)], cwd=str(REPO), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)`，`:2009-2015` docstring 明写 best-effort，`:2033` / `:2038` `"WARN: DeepSeekHarness 同步失败（ZCode 配置已写入）："` 只 WARN；另一条 `sync-models.ps1:345` `Invoke-Py "DSH 投影检查" @("tools\dsh_sync.py", "--check")`、`:348` `Invoke-Py "DSH 投影写入" @("tools\dsh_sync.py", "--apply")`。
- 机制：同一投影两处触发，一处 best-effort 吞错、一处严格 exit；计数/日志口径不一致，排障时难定哪条生效。
- 建议：收敛为单一入口（`sync-models.ps1` 只调 `model_alias.py`，或反之）；best-effort 那条把 stdout/exit 写进同一份日志。

**[低] M2 模块级 import 即退出**：`tools/dsh_sync.py:47-50` `try: import yaml` / `except ImportError:` / `sys.exit("dsh_sync.py 需要 PyYAML：python -m pip install pyyaml")`。被 import 时直接终止进程，测试/复用不友好。建议：延迟到 `_credentials_state` 内或抛可捕获异常。
**[低] M3 QN 兜底块整段重复**：`gateways/zgate/internal/config/config.go:369-377` 与 `:422-431` 两段七牛云 `c.Upstreams["QN"]` 兜底逐字相同（已读回核对）。建议：删其一或抽 `ensureQN()`。
**[低] M4 一次性脚本必然失败**：`tools/rename-to-modelbus.ps1:42-43` `if (-not (Test-Path -LiteralPath $SrcDir)) { Die "source missing: $SrcDir" }`，`:24` `$SrcDir = 'F:\Project\ZcodeAIModels'`；改名跑过后源目录不再存在 → 任何重跑都 ABORT。建议：归档为 `docs/archive/` 或顶部加「已执行勿重跑」守卫。
**[低·核实] M5 过期注释已修好（非缺陷）**：`docs/DSH-FIRST.md:126` 点名 `tools/model_alias.py:366` 注释称 dsh_sync 兜底 `1000000/128000`；实测 `tools/model_alias.py:363-368` 已自洽（`:365` `# 不会兜 1000000 / 128000 —— 要控阈值只能在这里按上游 id 补真值。`），`tools/dsh_sync.py` 中 `1000000|128000` grep 命中=0。
**[低·核实] M6 死代码注释属实**：`sync-models.ps1:282` 注释称 `--probe-file` 死代码；实测该轮确未传（`:289` 只传 `--timeout/--sleep/--max-tokens`），记录。

### ④ Windows 兼容

**[中] W1 批量重写为无 BOM UTF-8，PS5.1 会乱码**：`tools/rename-to-modelbus.ps1:250` `[System.IO.File]::WriteAllText($file.FullName, $body2, (New-Object System.Text.UTF8Encoding($false)))`（另 `:134` `$enc = New-Object System.Text.UTF8Encoding($false)`、`:139` 同款）把命中文件统一写成无 BOM UTF-8；AGENTS §9「PS5.1 按 GBK 读无 BOM UTF-8」会乱码。`:243` `Get-ChildItem -Recurse` 还会遍历 junction（AGENTS §2 禁止在视图根操作）。本仓 8 个 PS1 带 BOM 正是兼容标记（见 §0）。建议：写回时保留原 BOM/编码，或对该脚本加「已归档」标注。
**[低] W2 硬编码本机绝对路径**：`sync-models.ps1:34` `$ROOT       = "F:\Project\ModelBus"`、`:35` `$GIT_DIR    = "C:\Program Files\Git\cmd"`；`tools/check-secrets.py:58` 的本机用户目录正则不匹配这两个盘符路径，门禁不会报但换机即失效。建议：`$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path`；git 用 `Get-Command git` 探测。
**[低] W3 与 AGENTS §6 口径冲突**：`tools/rename-to-modelbus.ps1:213` `Start-Process -FilePath $Exe -ArgumentList 'serve' -WorkingDirectory $WorkDir -WindowStyle Hidden` 直接拉起 zgate（会话 Job Object 回收风险）；当前 §6 要求只走计划任务 `\ModelBus-zgate-watchdog`。该脚本是一次性改名脚本，建议补注释指向计划任务、不再执行此分支。

### ⑤ 错误处理与退出码

**[低] E1 静默 catch**：`tools/rename-to-modelbus.ps1:36` `function Die([string]$m) { Write-Host "ABORT: $m"; exit 1 }`、`:97` / `:220` `} catch { }`、`:247` `try { $body = [System.IO.File]::ReadAllText(...) } catch { continue }`；`tools/zgate-lifecycle/deploy-zgate.ps1:191` `try { Enable-ScheduledTask ... } catch { }`；`tools/zgate-lifecycle/ensure-zgate.ps1:16` `try { Write-EventLog ... } catch {}`（写事件日志失败被吞）。建议：至少 `Write-Warning`。
**[正向记录] E2 主链退出码**：`gateways/zgate/build.py:165` `sys.exit(main())`；`gateways/zgate/smoke_test.py:31` `raise SystemExit(f"读不到 alias map: {MAP_PATH} ({exc})")` / `:34` `raise SystemExit(f"alias map 里没有 models: {MAP_PATH}")` / `:129` `sys.exit(main())`；`tools/sync_report.py:465` `sys.exit(main())`；`tools/dsh_sync.py:644-649` `raise SystemExit(_main())` + `except DshSyncError` → `raise SystemExit(2)`；`sync-models.ps1:80/:84` `exit 2`；`providers/qoder/qoder_sync.py:367` / `providers/qwen/qwen_sync.py:455` `raise SystemExit(f"找不到 ZCode 配置：{path}")`；`tools/model_alias.py:2161` 同款。

---

## 2. 分类口径（主代理验收排除表）

按主代理回信 (m00112, m00113) 的三类分法，覆盖早期 M-ENVONLY 判断：

| 类 | 内容 | 处置 |
|---|---|---|
| **C-CONTRACT 契约层** | `~/.zcode/v2/*`、`ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` / `ZCODE_BUILTIN`、`ZCODE_GATEWAY_KEY`、`zcode-main|free|saver`、`zcode-model-ledger.json`、schema 键、`%LOCALAPPDATA%\ZCodeGateway\`、`third-party/zcode*` 原件与上游署名、NOTICE 商标段 | **历史勿动**，一律排除出净命中 |
| **H-HIST / H-VENDOR** | `CHANGELOG.md`、`PROGRESS.md`、`memories/`、`docs/`、`evidence/` 里的旧脚本名与旧叙述；vendored 上游署名 | **历史勿动** |
| **C-IMPL 实现层** | 叙述性 ZCode（注释/docstring/横幅/日志/对外文案）、脚本名、User-Agent、自造 env（`WB_ZCODE_PROBE_FILE`、`ZCODE_API_TYPE`、`ZCODE_BASE_URL`、`ZCODE_MAX_OUTPUT_TOKENS`）、`zcode_body` 标签与 `_zcode_providers` 符号 | **本轮改或留 fallback**；已改造的 `MB_*`/`WB_*` 新名优先 + 旧名兼容 |

契约层细分（113 行）：`C-PATH 64`（`.zcode` 路径字面量）、`C-ENV 16`、`C-ID 13`（`zcode-*` route 前缀）、`C-KEY 8`（`ZCODE_GATEWAY_KEY`）、`C-VENDORFILE 7`、`C-APPDATA 5`。
早期把 `ZCODE_GATEWAY_KEY` 分到「必须改」的判断作废；仅在 §1 观察项里按 AGENTS §2 凭据口径提一句，不改契约名。

第 6 路改名落地核对（15:52 取样）：6 个新名 `workbuddy_sync.py` / `workbuddy_probe.py` / `effective_body.js` / `qoder_sync.py` / `qoder_probe.py` / `qwen_sync.py` 全部存在，6 个旧名全部 `exists=false`；5 处硬编码引用已同步：`tools/dsh_sync.py:60` `EFFECTIVE_SCRIPT = REPO / "providers" / "workbuddy" / "effective_body.js"`、`tools/model_probe.py:45` `EFFECTIVE = REPO / "providers" / "workbuddy" / "effective_body.js"`、`providers/workbuddy/workbuddy_probe.py:75` `EFFECTIVE_BODY_SCRIPT = HERE / "effective_body.js"`、`sync-models.ps1:228` `"providers\workbuddy\workbuddy_sync.py"`、`sync-models.ps1:253` `"providers\qoder\qoder_sync.py"`。契约层 env 未动：`providers/workbuddy/workbuddy_sync.py:145` `"ZCODE_PERSONAL_PROVIDER_CONFIG_FILE",  # 契约层 env，不动`、`tools/dsh_sync.py:63`、`tools/model_probe.py:55`、`providers/qoder/qoder_sync.py:116`、`providers/qwen/qwen_sync.py:113`、`providers/workbuddy/effective_body.js:58/:182`。

---

## 3. ZCode 专项适配点代码台账

### 3.1 按文件汇总（净命中 129 行 / 25 个文件）

| 文件 | 净命中 | 主要分类 |
|---|---|---|
| `gateways\legacy-router\protocol_bridge.js` | 1 | 必须改 1 |
| `gateways\legacy-router\unified-router.js` | 1 | 必须改 1 |
| `gateways\zgate\internal\alias\alias.go` | 1 | 必须改 1 |
| `gateways\zgate\internal\bridge\bridge.go` | 2 | 必须改 2 |
| `gateways\zgate\internal\router\router.go` | 3 | 必须改 3 |
| `gateways\zgate\main.go` | 3 | 必须改 3 |
| `providers\opencode-go\ops\go_model_sync.py` | 5 | 必须改 5 |
| `providers\opencode-go\probe\archive\validate_zcode_models.py` | 3 | 必须改 3 |
| `providers\opencode-go\probe\bench_clean.py` | 3 | 必须改 3 |
| `providers\opencode-go\probe\bench_models.py` | 3 | 必须改 3 |
| `providers\opencode-go\probe\probe_models.py` | 1 | 必须改 1 |
| `providers\opencode-go\probe\probe_protocols.py` | 3 | 必须改 3 |
| `providers\qoder\qoder_probe.py` | 4 | 必须改 4 |
| `providers\qoder\qoder_sync.py` | 9 | 必须改 9 |
| `providers\qwen\qwen_sync.py` | 3 | 必须改 3 |
| `providers\workbuddy\effective_body.js` | 21 | 必须改 3 / 历史勿动 12 / 可保留兼容 6 |
| `providers\workbuddy\workbuddy_probe.py` | 18 | 必须改 16 / 历史勿动 1 / 可保留兼容 1 |
| `providers\workbuddy\workbuddy_sync.py` | 3 | 必须改 2 / 可保留兼容 1 |
| `tools\dsh_sync.py` | 21 | 必须改 18 / 历史勿动 3 |
| `tools\make_social_preview.py` | 2 | 必须改 2 |
| `tools\model_alias.py` | 7 | 必须改 7 |
| `tools\model_caps.py` | 2 | 历史勿动 2 |
| `tools\model_probe.py` | 1 | 必须改 1 |
| `tools\model_stream_check.py` | 1 | 历史勿动 1 |
| `tools\rename-to-modelbus.ps1` | 8 | 历史勿动 5 / 必须改 3 |

### 3.2 tools/ 与 gateways/ 叙述性 ZCode 逐处清单（主代理要求单列，53 行）

| # | file:line | 原文 | 分类 |
|---|---|---|---|
| 1 | `gateways\legacy-router\protocol_bridge.js:5` | `* DSH is the primary host; the ZCode client is one compatibility projection.` | 可保留兼容 |
| 2 | `gateways\legacy-router\unified-router.js:5` | `* DSH (DeepSeek Harness) 是主宿主；ZCode 客户端降为只读兼容投影。` | 必须改 |
| 3 | `gateways\zgate\internal\alias\alias.go:4` | `// The file is rewritten by tools/model_alias.py while ZCode is running, so it is` | 必须改 |
| 4 | `gateways\zgate\internal\bridge\bridge.go:586` | `// sseOf renders the chat SSE ZCode expects from a non-streaming chat response.` | 必须改 |
| 5 | `gateways\zgate\internal\bridge\bridge.go:821` | `// ZCode 会按客户端设置发 128000 这类值，不夹住就是硬 400，整条链都过不去。` | 必须改 |
| 6 | `gateways\zgate\internal\router\router.go:5` | `// and the same error envelopes, so ZCode's four chat providers keep working` | 必须改 |
| 7 | `gateways\zgate\internal\router\router.go:1499` | `// 这里（normalizePath 去掉 /v1），ZCode 看到的是 zgate-owned catalog，不再是` | 必须改 |
| 8 | `gateways\zgate\internal\router\router.go:2035` | `// wantsStream 返回客户端（ZCode）是否请求了 SSE 流式输出。桥接模型上游也按流式请求，` | 必须改 |
| 9 | `gateways\zgate\main.go:1` | `// zgate is the single entry point for ZCode's chat providers.` | 必须改 |
| 10 | `gateways\zgate\main.go:101` | `fmt.Printf(\`zgate %s —— ZCode 统一入口（路由 + 协议桥 + 子进程守护）` | 必须改 |
| 11 | `gateways\zgate\main.go:429` | `"$s.WindowStyle = 7; $s.Description = 'ZCode 统一入口 (zgate)'; $s.Save()",` | 必须改 |
| 12 | `tools\dsh_sync.py:2` | `"""Project ZCode's final model groups into DeepSeekRuntime's llm-pi-ai profile.` | 必须改 |
| 13 | `tools\dsh_sync.py:11` | `copied from the resolved ZCode metadata (\`\`effective_body.js\`\`);` | 必须改 |
| 14 | `tools\dsh_sync.py:12` | `* ZCode models whose effective \`\`reasoningLevel.map\`\` is \`\`{}\`\` deliberately` | 必须改 |
| 15 | `tools\dsh_sync.py:15` | `* all other patch entries and non-\`\`zcode-*\`\` DSH providers are preserved;` | 历史勿动 |
| 16 | `tools\dsh_sync.py:16` | `* every \`\`zcode-*\`\` route carries the module-level \`\`RETRY_POLICY\`\` (429` | 历史勿动 |
| 17 | `tools\dsh_sync.py:30` | `not modify the repository or ZCode's config. DSH hot-reloads the profile patch,` | 必须改 |
| 18 | `tools\dsh_sync.py:61` | `ZCODE_CONFIG = Path(` | 必须改 |
| 19 | `tools\dsh_sync.py:125` | `raise DshSyncError(f"找不到 ZCode 配置：{path}") from exc` | 必须改 |
| 20 | `tools\dsh_sync.py:127` | `raise DshSyncError(f"ZCode 配置不是合法 JSON：{path}（{exc}）") from exc` | 必须改 |
| 21 | `tools\dsh_sync.py:152` | `def _zcode_providers(cfg: dict[str, Any]) -> list[dict[str, Any]]:` | 必须改 |
| 22 | `tools\dsh_sync.py:161` | `raise DshSyncError("ZCode 配置缺少 config.providerConfigRules.providerRules") from exc` | 必须改 |
| 23 | `tools\dsh_sync.py:195` | `raise DshSyncError("ZCode 配置里没有任何含模型的 provider")` | 必须改 |
| 24 | `tools\dsh_sync.py:245` | `ZCode 配置是档位的唯一正本；DSH 侧只是投影。投影把一条非空档位写成空，用户` | 必须改 |
| 25 | `tools\dsh_sync.py:318` | `"""Map ZCode's effective reasoning rule to llm-pi-ai's schema."""` | 必须改 |
| 26 | `tools\dsh_sync.py:374` | `# 每条 zcode-* route 独立拷贝，避免改一条污染常量或其它 route。` | 历史勿动 |
| 27 | `tools\dsh_sync.py:432` | `ZCode 源头的 optionSpecs 缺失或退化（map="{}"、只留开关）时，生成器只能写出` | 必须改 |
| 28 | `tools\dsh_sync.py:545` | `raise DshSyncError("ZCode provider 配置里没有 gateway apiKey，无法写 DSH 凭据引用")` | 必须改 |
| 29 | `tools\dsh_sync.py:563` | `parser = argparse.ArgumentParser(description="同步 ZCode 最终模型到 DeepSeekRuntime llm-pi-ai")` | 必须改 |
| 30 | `tools\dsh_sync.py:569` | `parser.add_argument("--config", type=Path, default=ZCODE_CONFIG, help="ZCode provider_config.json")` | 必须改 |
| 31 | `tools\dsh_sync.py:577` | `providers = _zcode_providers(cfg)` | 必须改 |
| 32 | `tools\dsh_sync.py:595` | `print(f"ZCode      : {len(providers)} 个 provider / {sum(len(p['modelIds']) for p in providers)} 个模型")` | 必须改 |
| 33 | `tools\make_social_preview.py:45` | `"subtitle": "把模型供应商接进 ZCode 客户端的脚本与文档",` | 必须改 |
| 34 | `tools\make_social_preview.py:46` | `"tagline": "不改 ZCode 的代码，只写它的配置文件。",` | 必须改 |
| 35 | `tools\model_alias.py:2` | `"""Rebuild ZCode's model list as four credit-based groups with stable aliases.` | 必须改 |
| 36 | `tools\model_alias.py:2009` | `"""Project the just-written ZCode config into a local DeepSeekRuntime install.` | 必须改 |
| 37 | `tools\model_alias.py:2012` | `and a bad DSH profile must never turn a successful ZCode sync into a failed` | 必须改 |
| 38 | `tools\model_alias.py:2038` | `"WARN: DeepSeekHarness 同步失败（ZCode 配置已写入）："` | 必须改 |
| 39 | `tools\model_alias.py:2161` | `raise SystemExit(f"找不到 ZCode 配置：{path}")` | 必须改 |
| 40 | `tools\model_alias.py:2213` | `# the old rules. A renamed id no longer matches ZCode's builtin patterns,` | 必须改 |
| 41 | `tools\model_alias.py:2608` | `# Only project the real ZCode config by default. A caller using --config for` | 必须改 |
| 42 | `tools\model_caps.py:116` | `仓里的 zcode-builtin.json 含裸 0xad 字节，严格 utf-8 解码可能失败，因此先按` | 历史勿动 |
| 43 | `tools\model_caps.py:1028` | `parser.add_argument("--builtin", default=DEFAULT_BUILTIN, help="zcode-builtin.json 路径")` | 历史勿动 |
| 44 | `tools\model_probe.py:2` | `"""Probe the unified four-group model list with the exact body ZCode sends.` | 必须改 |
| 45 | `tools\model_stream_check.py:526` | `print("ERROR: patch 里没有 zcode-* 模型", file=sys.stderr)` | 历史勿动 |
| 46 | `tools\rename-to-modelbus.ps1:2` | `rename-to-modelbus.ps1 - one-shot project rename: ZcodeAIModels -> ModelBus` | 历史勿动 |
| 47 | `tools\rename-to-modelbus.ps1:24` | `$SrcDir   = 'F:\Project\ZcodeAIModels'` | 历史勿动 |
| 48 | `tools\rename-to-modelbus.ps1:27` | `$OldToken = 'ZcodeAIModels'` | 历史勿动 |
| 49 | `tools\rename-to-modelbus.ps1:131` | `# ZcodeAIModels -> ModelBus keeps the drive/prefix, so token replacement alone` | 历史勿动 |
| 50 | `tools\rename-to-modelbus.ps1:132` | `# already fixes every JSON-escaped form (F:\\Project\\ZcodeAIModels) too.` | 历史勿动 |
| 51 | `tools\rename-to-modelbus.ps1:169` | `Act "patch $ZcodeSetting (workspacePath)"` | 必须改 |
| 52 | `tools\rename-to-modelbus.ps1:170` | `if (-not $DryRun -and (Test-Path -LiteralPath $ZcodeSetting)) {` | 必须改 |
| 53 | `tools\rename-to-modelbus.ps1:171` | `if (PatchTextFile $ZcodeSetting) { Say "      patched setting.json" }` | 必须改 |

### 3.3 全量逐处台账（129 行：file:line + 原文 + 任务书分类 + 主代理子类 + 建议 DSH 目标形态）

分类合计：**必须改 96 / 历史勿动 24 / 可保留兼容 9**。tools+gateways 53 行（必须改 41 / 历史勿动 11 / 可保留兼容 1）；providers 76 行（必须改 55 / 历史勿动 13 / 可保留兼容 8）。「可保留兼容」9 行 = 8 行已落地的 `MB_*`/`WB_*` 新名 + 旧名 fallback（`providers/workbuddy/effective_body.js:44-46/:232/:233/:238`、`providers/workbuddy/workbuddy_sync.py:152`、`providers/workbuddy/workbuddy_probe.py:67`）+ 1 行已改成 DSH-first 目标措辞的注释（`gateways/legacy-router/protocol_bridge.js:5`）；后者虽仍含 `ZCode` 词面，但已是「DSH 主宿主 + ZCode 兼容投影」正确表述，保留即可，无需再改。

| # | file:line | 原文 | 分类（任务书） | 主代理口径子类 | 建议 DSH 目标形态 |
|---|---|---|---|---|---|
| 1 | `gateways\legacy-router\protocol_bridge.js:5` | `* DSH is the primary host; the ZCode client is one compatibility projection.` | 可保留兼容 | 已改造：DSH-first 表述 | 本行已是「DSH 主宿主 + ZCode 兼容投影」目标措辞，保留即可，无需再改 |
| 2 | `gateways\legacy-router\unified-router.js:5` | `* DSH (DeepSeek Harness) 是主宿主；ZCode 客户端降为只读兼容投影。` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 3 | `gateways\zgate\internal\alias\alias.go:4` | `// The file is rewritten by tools/model_alias.py while ZCode is running, so it is` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 4 | `gateways\zgate\internal\bridge\bridge.go:586` | `// sseOf renders the chat SSE ZCode expects from a non-streaming chat response.` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 5 | `gateways\zgate\internal\bridge\bridge.go:821` | `// ZCode 会按客户端设置发 128000 这类值，不夹住就是硬 400，整条链都过不去。` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 6 | `gateways\zgate\internal\router\router.go:5` | `// and the same error envelopes, so ZCode's four chat providers keep working` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 7 | `gateways\zgate\internal\router\router.go:1499` | `// 这里（normalizePath 去掉 /v1），ZCode 看到的是 zgate-owned catalog，不再是` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 8 | `gateways\zgate\internal\router\router.go:2035` | `// wantsStream 返回客户端（ZCode）是否请求了 SSE 流式输出。桥接模型上游也按流式请求，` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 9 | `gateways\zgate\main.go:1` | `// zgate is the single entry point for ZCode's chat providers.` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 10 | `gateways\zgate\main.go:101` | `fmt.Printf(\`zgate %s —— ZCode 统一入口（路由 + 协议桥 + 子进程守护）` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 11 | `gateways\zgate\main.go:429` | `"$s.WindowStyle = 7; $s.Description = 'ZCode 统一入口 (zgate)'; $s.Save()",` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 12 | `providers\opencode-go\ops\go_model_sync.py:10` | `④ 写进 ZCode 配置的同三个落点（见 docs/MODEL-PROVIDERS.md §1）。` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 13 | `providers\opencode-go\ops\go_model_sync.py:11` | `**与供应商无关的部分**：ZCode 侧的写入方式、思考参数覆盖机制、探测必须用真实 body。` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 14 | `providers\opencode-go\ops\go_model_sync.py:15` | `每天跑一次，检测 Go 套餐是否新增模型，对符合收录标准的模型自动写进 ZCode 的` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 15 | `providers\opencode-go\ops\go_model_sync.py:56` | `# ZCode 客户端配置：默认按「当前用户主目录」推导，不要写死某个人的用户名。` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 16 | `providers\opencode-go\ops\go_model_sync.py:187` | `这个字段是「上游说这个型号支持哪些档位」的唯一权威来源；ZCode 侧不写` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 17 | `providers\opencode-go\probe\archive\validate_zcode_models.py:2` | `"""Validate every model configured in ZCode against its provider protocol."""` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 18 | `providers\opencode-go\probe\archive\validate_zcode_models.py:5` | `# ZCode 客户端配置：按「当前用户主目录」推导，不要写死某个人的用户名` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 19 | `providers\opencode-go\probe\archive\validate_zcode_models.py:16` | `UA = "zcode-validate/1.0"` | 必须改 | C-IMPL 实现层旧名（UA/函数/字段） | zcode-* UA → modelbus-*；zcode_body → mb_body；used="zcode" → "native" |
| 20 | `providers\opencode-go\probe\bench_clean.py:49` | `"User-Agent": "zcode-bench/1.0", "x-opencode-session": f"sb-{mid}",` | 必须改 | C-IMPL 实现层旧名（UA/函数/字段） | zcode-* UA → modelbus-*；zcode_body → mb_body；used="zcode" → "native" |
| 21 | `providers\opencode-go\probe\bench_clean.py:56` | `"Content-Type": "application/json", "User-Agent": "zcode-bench/1.0",` | 必须改 | C-IMPL 实现层旧名（UA/函数/字段） | zcode-* UA → modelbus-*；zcode_body → mb_body；used="zcode" → "native" |
| 22 | `providers\opencode-go\probe\bench_clean.py:63` | `"User-Agent": "zcode-bench/1.0", "x-opencode-session": f"sb-{mid}",` | 必须改 | C-IMPL 实现层旧名（UA/函数/字段） | zcode-* UA → modelbus-*；zcode_body → mb_body；used="zcode" → "native" |
| 23 | `providers\opencode-go\probe\bench_models.py:69` | `"User-Agent": "zcode-bench/1.0", "x-opencode-session": f"b-{mid}"})` | 必须改 | C-IMPL 实现层旧名（UA/函数/字段） | zcode-* UA → modelbus-*；zcode_body → mb_body；used="zcode" → "native" |
| 24 | `providers\opencode-go\probe\bench_models.py:80` | `"Content-Type": "application/json", "User-Agent": "zcode-bench/1.0",` | 必须改 | C-IMPL 实现层旧名（UA/函数/字段） | zcode-* UA → modelbus-*；zcode_body → mb_body；used="zcode" → "native" |
| 25 | `providers\opencode-go\probe\bench_models.py:93` | `"User-Agent": "zcode-bench/1.0", "x-opencode-session": f"b-{mid}"})` | 必须改 | C-IMPL 实现层旧名（UA/函数/字段） | zcode-* UA → modelbus-*；zcode_body → mb_body；used="zcode" → "native" |
| 26 | `providers\opencode-go\probe\probe_models.py:43` | `"User-Agent": "zcode-probe/1.0",` | 必须改 | C-IMPL 实现层旧名（UA/函数/字段） | zcode-* UA → modelbus-*；zcode_body → mb_body；used="zcode" → "native" |
| 27 | `providers\opencode-go\probe\probe_protocols.py:44` | `"User-Agent": "zcode-probe/1.0", "x-opencode-session": f"p-{mid}"})` | 必须改 | C-IMPL 实现层旧名（UA/函数/字段） | zcode-* UA → modelbus-*；zcode_body → mb_body；used="zcode" → "native" |
| 28 | `providers\opencode-go\probe\probe_protocols.py:51` | `"Content-Type": "application/json", "User-Agent": "zcode-probe/1.0",` | 必须改 | C-IMPL 实现层旧名（UA/函数/字段） | zcode-* UA → modelbus-*；zcode_body → mb_body；used="zcode" → "native" |
| 29 | `providers\opencode-go\probe\probe_protocols.py:58` | `"User-Agent": "zcode-probe/1.0", "x-opencode-session": f"p-{mid}"})` | 必须改 | C-IMPL 实现层旧名（UA/函数/字段） | zcode-* UA → modelbus-*；zcode_body → mb_body；used="zcode" → "native" |
| 30 | `providers\qoder\qoder_probe.py:2` | `"""Probe Qoder models with the exact body ZCode will send.` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 31 | `providers\qoder\qoder_probe.py:5` | `\`qoder:\` prefix, i.e. the same path ZCode uses after the merge. The catalog is` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 32 | `providers\qoder\qoder_probe.py:7` | `models that are currently not in the ZCode config (e.g. the queued free` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 33 | `providers\qoder\qoder_probe.py:10` | `ok            HTTP 200 with the ZCode-native body` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 34 | `providers\qoder\qoder_sync.py:2` | `"""Sync Qoder models from qoder2api-hub into ZCode's existing chat tiers.` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 35 | `providers\qoder\qoder_sync.py:16` | `ZCode provider list stays at seven entries.` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 36 | `providers\qoder\qoder_sync.py:24` | `\`qoder/.env.local\` (gitignored), and the ZCode config write is backed up first.` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 37 | `providers\qoder\qoder_sync.py:37` | `* ZCode hot-reloads provider_config.json (~1s polling); no restart is needed.` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 38 | `providers\qoder\qoder_sync.py:39` | `body ZCode sends and writes \`qoder_probe.json\`. \`--probe-file\` keeps only` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 39 | `providers\qoder\qoder_sync.py:273` | `"""模型级规则：把 Qoder 目录里的 reasoning_efforts 写成 ZCode 的档位表。` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 40 | `providers\qoder\qoder_sync.py:275` | `不写 values 的话 ZCode 落到兜底规则 \`.*\`（["disabled","enabled"]），界面只剩` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 41 | `providers\qoder\qoder_sync.py:276` | `思考开关、上游声明的低档发不出去。**顺序 = 下拉顺序**，且 ZCode 拿最后一档` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 42 | `providers\qoder\qoder_sync.py:367` | `raise SystemExit(f"找不到 ZCode 配置：{path}")` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 43 | `providers\qwen\qwen_sync.py:2` | `"""Warm-start ZCode with the Qwen platform's free-quota models.` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 44 | `providers\qwen\qwen_sync.py:27` | `them all into one ZCode group is unusable in the picker, and each one costs a` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 45 | `providers\qwen\qwen_sync.py:455` | `raise SystemExit(f"找不到 ZCode 配置：{path}")` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 46 | `providers\workbuddy\effective_body.js:3` | `* Compute the exact request-body fields ZCode will send for a given model id,` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 47 | `providers\workbuddy\effective_body.js:4` | `* by replaying the engine's own rule resolution against zcode-builtin.json.` | 历史勿动 | H-VENDOR / 契约文件名 | 保持（vendored 上游署名与 zcode-builtin.json 契约文件名，勿动） |
| 48 | `providers\workbuddy\effective_body.js:8` | `* 上游：zai-org/ZCode（Apache-2.0）` | 历史勿动 | H-VENDOR / 契约文件名 | 保持（vendored 上游署名与 zcode-builtin.json 契约文件名，勿动） |
| 49 | `providers\workbuddy\effective_body.js:12` | `*     packages/provider/src/config/schema.ts       → parseZCodeBuiltinModelConfigRules()（扁平化顺序）` | 历史勿动 | H-VENDOR / 契约文件名 | 保持（vendored 上游署名与 zcode-builtin.json 契约文件名，勿动） |
| 50 | `providers\workbuddy\effective_body.js:14` | `*     config/provider/zcode-builtin.json           → 规则数据` | 历史勿动 | H-VENDOR / 契约文件名 | 保持（vendored 上游署名与 zcode-builtin.json 契约文件名，勿动） |
| 51 | `providers\workbuddy\effective_body.js:44` | `*   MB_API_TYPE   请求的 api type（默认 openai-chat-completions；旧名 ZCODE_API_TYPE 兼容）` | 可保留兼容 | 已改造：新名优先 + 旧名 fallback | MB_* / WB_* 新名 env 优先，ZCODE_* / WB_ZCODE_* 作兼容别名 |
| 52 | `providers\workbuddy\effective_body.js:45` | `*   MB_BASE_URL   请求的 base URL（provider-site 规则要靠它命中；旧名 ZCODE_BASE_URL 兼容）` | 可保留兼容 | 已改造：新名优先 + 旧名 fallback | MB_* / WB_* 新名 env 优先，ZCODE_* / WB_ZCODE_* 作兼容别名 |
| 53 | `providers\workbuddy\effective_body.js:46` | `*   MB_MAX_OUTPUT_TOKENS  调用方 max output tokens（旧名 ZCODE_MAX_OUTPUT_TOKENS 兼容）` | 可保留兼容 | 已改造：新名优先 + 旧名 fallback | MB_* / WB_* 新名 env 优先，ZCODE_* / WB_ZCODE_* 作兼容别名 |
| 54 | `providers\workbuddy\effective_body.js:55` | `// ── 1. 找到 zcode-builtin.json ────────────────────────────────────────────` | 历史勿动 | H-VENDOR / 契约文件名 | 保持（vendored 上游署名与 zcode-builtin.json 契约文件名，勿动） |
| 55 | `providers\workbuddy\effective_body.js:56` | `// 顺序：环境变量 → 仓内 vendor 的开源版本 → 本机 ZCode 运行时 → 桌面版安装目录` | 历史勿动 | H-VENDOR / 契约文件名 | 保持（vendored 上游署名与 zcode-builtin.json 契约文件名，勿动） |
| 56 | `providers\workbuddy\effective_body.js:63` | `const vendored = path.join(REPO, 'third-party', 'zcode', 'zcode-builtin.json');` | 历史勿动 | H-VENDOR / 契约文件名 | 保持（vendored 上游署名与 zcode-builtin.json 契约文件名，勿动） |
| 57 | `providers\workbuddy\effective_body.js:77` | `const f = path.join(vDir, ep, 'zcode-builtin.json');` | 历史勿动 | H-VENDOR / 契约文件名 | 保持（vendored 上游署名与 zcode-builtin.json 契约文件名，勿动） |
| 58 | `providers\workbuddy\effective_body.js:84` | `return { path: found[0], from: \`本机 ZCode 运行时（最新：${path.basename(path.dirname(found[0]))}）\` };` | 历史勿动 | H-VENDOR / 契约文件名 | 保持（vendored 上游署名与 zcode-builtin.json 契约文件名，勿动） |
| 59 | `providers\workbuddy\effective_body.js:91` | `path.join(os.homedir(), 'AppData', 'Local', 'Programs', 'ZCode'),` | 历史勿动 | H-VENDOR / 契约文件名 | 保持（vendored 上游署名与 zcode-builtin.json 契约文件名，勿动） |
| 60 | `providers\workbuddy\effective_body.js:94` | `const f = path.join(root, 'resources', 'config', 'provider', 'zcode-builtin.json');` | 历史勿动 | H-VENDOR / 契约文件名 | 保持（vendored 上游署名与 zcode-builtin.json 契约文件名，勿动） |
| 61 | `providers\workbuddy\effective_body.js:95` | `if (fs.existsSync(f)) return { path: f, from: 'ZCode 桌面版安装目录' };` | 历史勿动 | H-VENDOR / 契约文件名 | 保持（vendored 上游署名与 zcode-builtin.json 契约文件名，勿动） |
| 62 | `providers\workbuddy\effective_body.js:178` | `// The builtin file only contains ZCode's shipped rules. Per-model overrides` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 63 | `providers\workbuddy\effective_body.js:232` | `const API_TYPE = opts.apiType \\|\\| process.env.MB_API_TYPE \\|\\| process.env.ZCODE_API_TYPE \\|\\| 'openai-chat-completions';` | 可保留兼容 | 已改造：新名优先 + 旧名 fallback | MB_* / WB_* 新名 env 优先，ZCODE_* / WB_ZCODE_* 作兼容别名 |
| 64 | `providers\workbuddy\effective_body.js:233` | `const BASE_URL = opts.baseUrl \\|\\| process.env.MB_BASE_URL \\|\\| process.env.ZCODE_BASE_URL \\|\\| undefined;` | 可保留兼容 | 已改造：新名优先 + 旧名 fallback | MB_* / WB_* 新名 env 优先，ZCODE_* / WB_ZCODE_* 作兼容别名 |
| 65 | `providers\workbuddy\effective_body.js:238` | `const MAX_TOKENS = opts.maxTokens \\|\\| Number(process.env.MB_MAX_OUTPUT_TOKENS \\|\\| process.env.ZCODE_MAX_OUTPUT_TOKENS) \\|\\| 1024;` | 可保留兼容 | 已改造：新名优先 + 旧名 fallback | MB_* / WB_* 新名 env 优先，ZCODE_* / WB_ZCODE_* 作兼容别名 |
| 66 | `providers\workbuddy\effective_body.js:248` | `// ZCode 的默认推理档位 = 解析出的 values 列表里的**最后一档**：` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 67 | `providers\workbuddy\workbuddy_probe.py:2` | `r"""Probe WorkBuddy gateway models with the EXACT body ZCode will send.` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 68 | `providers\workbuddy\workbuddy_probe.py:12` | `ZCode's builtin \`modelConfigRules.modelApiRules\` inject extra thinking fields` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 69 | `providers\workbuddy\workbuddy_probe.py:14` | `zcode-builtin.json):` | 历史勿动 | H-VENDOR / 契约文件名 | 保持（vendored 上游署名与 zcode-builtin.json 契约文件名，勿动） |
| 70 | `providers\workbuddy\workbuddy_probe.py:30` | `400s in ZCode while a plain curl works. This probe replays the body ZCode` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 71 | `providers\workbuddy\workbuddy_probe.py:36` | `ok        - HTTP 200 with the primary (ZCode-native) body` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 72 | `providers\workbuddy\workbuddy_probe.py:68` | `os.environ.get("WB_ZCODE_PROBE_FILE", CACHE_DIR / "wb_zcode_probe.json"),` | 可保留兼容 | 已改造：新名优先 + 旧名 fallback | MB_* / WB_* 新名 env 优先，ZCODE_* / WB_ZCODE_* 作兼容别名 |
| 73 | `providers\workbuddy\workbuddy_probe.py:77` | `# Cache of model id -> ZCode's effective thinking body, computed by replaying` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 74 | `providers\workbuddy\workbuddy_probe.py:83` | `"""Ask Node for the exact body ZCode sends for each model id.` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 75 | `providers\workbuddy\workbuddy_probe.py:86` | `ZCode's map expressions resolves to *our* request's value — upstream applies` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 76 | `providers\workbuddy\workbuddy_probe.py:110` | `def zcode_body(model: str, max_tokens: int = 24) -> dict:` | 必须改 | C-IMPL 实现层旧名（UA/函数/字段） | zcode-* UA → modelbus-*；zcode_body → mb_body；used="zcode" → "native" |
| 77 | `providers\workbuddy\workbuddy_probe.py:111` | `"""Build the request body ZCode would send for this model."""` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 78 | `providers\workbuddy\workbuddy_probe.py:125` | `"""Short label for the shape ZCode uses (for logging)."""` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 79 | `providers\workbuddy\workbuddy_probe.py:150` | `"""Slimmer bodies tried when ZCode's native body is rejected."""` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 80 | `providers\workbuddy\workbuddy_probe.py:265` | `code, resp = http_json(zcode_body(mid))` | 必须改 | C-IMPL 实现层旧名（UA/函数/字段） | zcode-* UA → modelbus-*；zcode_body → mb_body；used="zcode" → "native" |
| 81 | `providers\workbuddy\workbuddy_probe.py:267` | `used = "zcode"` | 必须改 | C-IMPL 实现层旧名（UA/函数/字段） | zcode-* UA → modelbus-*；zcode_body → mb_body；used="zcode" → "native" |
| 82 | `providers\workbuddy\workbuddy_probe.py:269` | `# ZCode's native body was rejected - find a slimmer one that works.` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 83 | `providers\workbuddy\workbuddy_probe.py:274` | `st, detail, used = "fallback", f"zcode body rejected; '{alt}' works", alt` | 必须改 | C-IMPL 实现层旧名（UA/函数/字段） | zcode-* UA → modelbus-*；zcode_body → mb_body；used="zcode" → "native" |
| 84 | `providers\workbuddy\workbuddy_probe.py:282` | `"zcode_body": kind,` | 必须改 | C-IMPL 实现层旧名（UA/函数/字段） | zcode-* UA → modelbus-*；zcode_body → mb_body；used="zcode" → "native" |
| 85 | `providers\workbuddy\workbuddy_sync.py:2` | `"""Sync WorkBuddy2API gateway models into ZCode as tiered personal providers.` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 86 | `providers\workbuddy\workbuddy_sync.py:11` | `§1).  The ZCode-side write path itself is provider-neutral.` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 87 | `providers\workbuddy\workbuddy_sync.py:152` | `PROBE_FILE = Path(os.environ.get("WB_PROBE_FILE", os.environ.get("WB_ZCODE_PROBE_FILE", CACHE_DIR / "wb_zcode_probe.json")))` | 可保留兼容 | 已改造：新名优先 + 旧名 fallback | MB_* / WB_* 新名 env 优先，ZCODE_* / WB_ZCODE_* 作兼容别名 |
| 88 | `tools\dsh_sync.py:2` | `"""Project ZCode's final model groups into DeepSeekRuntime's llm-pi-ai profile.` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 89 | `tools\dsh_sync.py:11` | `copied from the resolved ZCode metadata (\`\`effective_body.js\`\`);` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 90 | `tools\dsh_sync.py:12` | `* ZCode models whose effective \`\`reasoningLevel.map\`\` is \`\`{}\`\` deliberately` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 91 | `tools\dsh_sync.py:15` | `* all other patch entries and non-\`\`zcode-*\`\` DSH providers are preserved;` | 历史勿动 | C-ID 契约层 route 前缀 | 保持 zcode-main\|free\|saver 前缀（契约层 id，勿动） |
| 92 | `tools\dsh_sync.py:16` | `* every \`\`zcode-*\`\` route carries the module-level \`\`RETRY_POLICY\`\` (429` | 历史勿动 | C-ID 契约层 route 前缀 | 保持 zcode-main\|free\|saver 前缀（契约层 id，勿动） |
| 93 | `tools\dsh_sync.py:30` | `not modify the repository or ZCode's config. DSH hot-reloads the profile patch,` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 94 | `tools\dsh_sync.py:61` | `ZCODE_CONFIG = Path(` | 必须改 | C-IMPL 实现层符号名 | _zcode_providers → _source_providers；ZCODE_CONFIG → SOURCE_CONFIG（env 名保持契约） |
| 95 | `tools\dsh_sync.py:125` | `raise DshSyncError(f"找不到 ZCode 配置：{path}") from exc` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 96 | `tools\dsh_sync.py:127` | `raise DshSyncError(f"ZCode 配置不是合法 JSON：{path}（{exc}）") from exc` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 97 | `tools\dsh_sync.py:152` | `def _zcode_providers(cfg: dict[str, Any]) -> list[dict[str, Any]]:` | 必须改 | C-IMPL 实现层符号名 | _zcode_providers → _source_providers；ZCODE_CONFIG → SOURCE_CONFIG（env 名保持契约） |
| 98 | `tools\dsh_sync.py:161` | `raise DshSyncError("ZCode 配置缺少 config.providerConfigRules.providerRules") from exc` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 99 | `tools\dsh_sync.py:195` | `raise DshSyncError("ZCode 配置里没有任何含模型的 provider")` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 100 | `tools\dsh_sync.py:245` | `ZCode 配置是档位的唯一正本；DSH 侧只是投影。投影把一条非空档位写成空，用户` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 101 | `tools\dsh_sync.py:318` | `"""Map ZCode's effective reasoning rule to llm-pi-ai's schema."""` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 102 | `tools\dsh_sync.py:374` | `# 每条 zcode-* route 独立拷贝，避免改一条污染常量或其它 route。` | 历史勿动 | C-ID 契约层 route 前缀 | 保持 zcode-main\|free\|saver 前缀（契约层 id，勿动） |
| 103 | `tools\dsh_sync.py:432` | `ZCode 源头的 optionSpecs 缺失或退化（map="{}"、只留开关）时，生成器只能写出` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 104 | `tools\dsh_sync.py:545` | `raise DshSyncError("ZCode provider 配置里没有 gateway apiKey，无法写 DSH 凭据引用")` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 105 | `tools\dsh_sync.py:563` | `parser = argparse.ArgumentParser(description="同步 ZCode 最终模型到 DeepSeekRuntime llm-pi-ai")` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 106 | `tools\dsh_sync.py:569` | `parser.add_argument("--config", type=Path, default=ZCODE_CONFIG, help="ZCode provider_config.json")` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 107 | `tools\dsh_sync.py:577` | `providers = _zcode_providers(cfg)` | 必须改 | C-IMPL 实现层符号名 | _zcode_providers → _source_providers；ZCODE_CONFIG → SOURCE_CONFIG（env 名保持契约） |
| 108 | `tools\dsh_sync.py:595` | `print(f"ZCode      : {len(providers)} 个 provider / {sum(len(p['modelIds']) for p in providers)} 个模型")` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 109 | `tools\make_social_preview.py:45` | `"subtitle": "把模型供应商接进 ZCode 客户端的脚本与文档",` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 110 | `tools\make_social_preview.py:46` | `"tagline": "不改 ZCode 的代码，只写它的配置文件。",` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 111 | `tools\model_alias.py:2` | `"""Rebuild ZCode's model list as four credit-based groups with stable aliases.` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 112 | `tools\model_alias.py:2009` | `"""Project the just-written ZCode config into a local DeepSeekRuntime install.` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 113 | `tools\model_alias.py:2012` | `and a bad DSH profile must never turn a successful ZCode sync into a failed` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 114 | `tools\model_alias.py:2038` | `"WARN: DeepSeekHarness 同步失败（ZCode 配置已写入）："` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 115 | `tools\model_alias.py:2161` | `raise SystemExit(f"找不到 ZCode 配置：{path}")` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 116 | `tools\model_alias.py:2213` | `# the old rules. A renamed id no longer matches ZCode's builtin patterns,` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 117 | `tools\model_alias.py:2608` | `# Only project the real ZCode config by default. A caller using --config for` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 118 | `tools\model_caps.py:116` | `仓里的 zcode-builtin.json 含裸 0xad 字节，严格 utf-8 解码可能失败，因此先按` | 历史勿动 | H-VENDOR / 契约文件名 | 保持（vendored 上游署名与 zcode-builtin.json 契约文件名，勿动） |
| 119 | `tools\model_caps.py:1028` | `parser.add_argument("--builtin", default=DEFAULT_BUILTIN, help="zcode-builtin.json 路径")` | 历史勿动 | H-VENDOR / 契约文件名 | 保持（vendored 上游署名与 zcode-builtin.json 契约文件名，勿动） |
| 120 | `tools\model_probe.py:2` | `"""Probe the unified four-group model list with the exact body ZCode sends.` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 121 | `tools\model_stream_check.py:526` | `print("ERROR: patch 里没有 zcode-* 模型", file=sys.stderr)` | 历史勿动 | C-ID 契约层 route 前缀 | 保持 zcode-main\|free\|saver 前缀（契约层 id，勿动） |
| 122 | `tools\rename-to-modelbus.ps1:2` | `rename-to-modelbus.ps1 - one-shot project rename: ZcodeAIModels -> ModelBus` | 历史勿动 | H-HIST 一次性迁移脚本 | 保持（脚本已跑过，归档勿再执行） |
| 123 | `tools\rename-to-modelbus.ps1:24` | `$SrcDir   = 'F:\Project\ZcodeAIModels'` | 历史勿动 | H-HIST 一次性迁移脚本 | 保持（脚本已跑过，归档勿再执行） |
| 124 | `tools\rename-to-modelbus.ps1:27` | `$OldToken = 'ZcodeAIModels'` | 历史勿动 | H-HIST 一次性迁移脚本 | 保持（脚本已跑过，归档勿再执行） |
| 125 | `tools\rename-to-modelbus.ps1:131` | `# ZcodeAIModels -> ModelBus keeps the drive/prefix, so token replacement alone` | 历史勿动 | H-HIST 一次性迁移脚本 | 保持（脚本已跑过，归档勿再执行） |
| 126 | `tools\rename-to-modelbus.ps1:132` | `# already fixes every JSON-escaped form (F:\\Project\\ZcodeAIModels) too.` | 历史勿动 | H-HIST 一次性迁移脚本 | 保持（脚本已跑过，归档勿再执行） |
| 127 | `tools\rename-to-modelbus.ps1:169` | `Act "patch $ZcodeSetting (workspacePath)"` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 128 | `tools\rename-to-modelbus.ps1:170` | `if (-not $DryRun -and (Test-Path -LiteralPath $ZcodeSetting)) {` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |
| 129 | `tools\rename-to-modelbus.ps1:171` | `if (PatchTextFile $ZcodeSetting) { Say "      patched setting.json" }` | 必须改 | C-IMPL 叙述性 ZCode | 注释/docstring/横幅/日志改「DSH 主宿主 + ZCode 兼容投影」中性表述 |

---

## 4. 完成判据核对表

| # | 任务书判据 | 完成情况 | 证据 |
|---|---|---|---|
| 1 | 对第一方源码做**全量**代码审查 | ✅ | 66 文件 / 971440 B / 24282 行全扫；41 文件批量深读聚合 + 关键段落逐行 read；§1 五维共 30 项 |
| 2 | 维度①正确性（空值/异常/边界、解析与编码、并发与竞态、重试与幂等） | ✅ | C1–C11，含非原子写、静默 except、JS/Go 缓存口径、并发账本 |
| 3 | 维度②安全（硬编码 key/token、命令注入、路径穿越、日志泄露、SSRF 面） | ✅ | S1–S8（问题 5 项 + 正面非缺陷 3 项），注入面逐字核 `main.go:424/431` |
| 4 | 维度③可维护性（死代码、重复逻辑、过时注释、命名与 ZCode 耦合） | ✅ | M1–M6，含两条 DSH 投影、QN 重复块、过期注释实测已修 |
| 5 | 维度④Windows 兼容（路径分隔符、编码、CRLF、PS5.1） | ✅ | W1–W3 + §0 的 CRLF 7 / BOM 8 基线 |
| 6 | 维度⑤错误处理与退出码 | ✅ | E1–E2，静默 catch 与主链 `SystemExit`/`exit 2` 逐条 |
| 7 | 每个问题写 file:line、严重度、证据、修复建议 | ✅ | §1 每条四要素齐备，行号按 `15:57–16:00` 当前磁盘态复核 |
| 8 | ZCode 专项台账：逐处 file:line + 原文 + 分类（必须改/可保留兼容/历史勿动）+ 建议 DSH 目标形态 | ✅ | §3.3 共 129 行，六列齐备（# / file:line / 原文 / 任务书分类 / 主代理子类 / DSH 目标形态）；§3.1 按文件 25 行、§3.2 tools/gateways 53 行 |
| 9 | 结论附可独立复现的命令/数字；数字自己跑 grep/Select-String 复核 | ✅ | §0 双口径：node:fs `242/129` + PowerShell `PS_HITS=241`（差 1 已解释）；旧名源码零残留复跑 |
| 10 | 凭据/key 只从环境变量读，绝不写进文件与汇报 | ✅ | 报告只出现 env 名与 `apiKey` 字段名，零值 |
| 11 | 只读；唯一写产物 `evidence/agent-<name>.md`；不碰共享文件/配置；不 git 操作；不重启网关 | ✅ | 仅写本文件；`.work/` 下 5 个中间表为分析暂存 |
| 12 | codegraph 未初始化 → 普通检索，不自行 init | ✅ | `codegraph_status` 实测 Not initialized |
| 13 | 报告结尾列「完成判据核对表」 | ✅ | 本表 |
| 14 | 用 `send_message` 把关键结论报回主代理 `session-90f67405-5d4e-4707-b280-3eba9af5856a` | ✅ | 中期结论已报（messageId 38899617-e7d5-4398-a547-bd89f1ec8447）；落盘后回报路径/字节/行数 |

## 5. 限制与备注

- 数字随多路并发改动持续漂移（改名前基线 68 文件 / 963690 B / 24080 行 → 15:52 的 64 / 962849 / 24065 → 15:57 的 66 / 971440 / 24282）；本报告固定以 `SAMPLE_AT=2026-11-11T07:57:49.610Z` 为准，主代理验收按当前磁盘复核。
- 早期「6 个新脚本名不存在」的快照已被第 6 路落地作废；`docs/DSH-FIRST.md:35` 自称「第一方代码里旧名零残留」与实测不符（净命中 129 行实现层叙述性 ZCode 仍在），该落差已中期报主代理。
- 台账中间产物在 `.work/`：`code-review-ledger.part.md`（旧口径，已作废）、`code-review-cimpl.md`、`code-review-cimpl-final.md`、`code-review-ledger-table.md`、`code-review-tg-table.md`、`code-review-byfile-table.md`、`b12-full.md`（任务书原文恢复件，落在 `~/.dsh/profiles/desktop/.work/b12-full.md`）。
- 未做运行期/端到端实测（本分片只读），§1 的机制判断来自逐行 read + 静态数据流；C1/C3/C4/C9 建议由主代理在 fixture 上跑一次复现后再定修复优先级。
