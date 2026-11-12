# ModelBus 全仓审查分片（C 路 · 只读）

> 结论先行：全仓实测 1153 个文本文件 / 45,225,871 B；运行态 `gateways/` 990 文件约 165–168 MB（两次采样有增长）。最硬的资源热点是 `zgate.exe.bak-*` 6 份 64,514,048 B、请求日志 7 天 27,688,206 B / 40,351 行且未找到 retention、`~/.zcode/v2/provider_config.json.bak-*` 49 份 849,378 B。可证明行为等价的最小优化候选只有 2 个（PowerShell 参数数组去重、Python 校验读改用 with），其余一律只列观察并标「不建议本轮改」；7872 空闲，7871 由 zgate pid=17336 监听。本分片零源码改动、零配置改动、零服务重启、零 git 操作。

---

## 0. 边界与口径

| 项 | 口径 |
|---|---|
| 真实 git 根 | `F:/Project/ModelBus`（`git rev-parse --show-toplevel` 输出 `F:/Project/ModelBus`）；`F:/Project/_merged/DeepseekHarness/ModelBus` 只是 junction 视图，未在其中新建任何产物 |
| 本分片唯一产物 | `F:\Project\ModelBus\evidence\agent-audit.md` |
| 未触碰 | `PROGRESS.md`、`provider_config.json` / 任何配置、`docs/`、`tests/`、`gateways/`、任何现有源码 |
| git / 服务 | 未 add / commit / push；未重启 zgate / wb2api / mihomo；未调用任何 codegraph 工具、未 `codegraph init` |
| 检索方式 | 按用户硬约束「.codegraph/ 未初始化」处理，全程 `grep` / `glob` / `read` / PowerShell 7 只读命令 |
| 凭据 | 未读取任何 key / token / 口令的取值；报告只出现键名与 `<REDACTED-CREDENTIAL>` 占位，公开输出零真值 |
| 行数口径 | `Get-Content | Measure-Object -Line` 不计空行；`read` 的 totalLines 计空行，两者分别标注 |
| 时间敏感 | 长驻网关持续写盘，`gateways/`、`.work/`、`data/`、`request-logs/` 字节数随采样时刻变化；数字标注 2026-11-12 16:27–16:37 采样 |

---

## 1. 结构盘点（实测文件数 / 行数）

### 1.1 顶层目录体量（2026-11-12 16:27–16:31 采样）

| 目录 | files | bytes | text-lines |
|---|---:|---:|---:|
| gateways | 990 | 165112883（复测 168161265） | 219024 |
| .work | 333（复测 335） | 23963775（复测 24133519） | 62428 |
| .codegraph | 2 | 17428709 | 0 |
| evidence | 71 | 2027611 | 15964 |
| %SystemDrive%（字面量目录） | 5 | 1332016 | 0 |
| tools | 38 | 862648 | 8655 |
| docs | 42 | 676754 | 7214 |
| providers | 48 | 550436 | 7550 |
| tests | 26 | 273675 | 2073 |
| third-party | 11 | 252784 | 7647 |
| assets | 3 | 167480 | 0 |
| catalog | 3 | 55194 | 1686 |
| memories | 10 | 47012 | 340 |
| .github | 4 | 8807 | 213 |
| .githooks | 1 | 2914 | 0 |

细分：`.git/logs` 4 / 98705；`gateways/upstream/workbuddy/data` 18 / 29240509；`gateways/upstream/workbuddy/.git/logs` 11 / 5073；`providers/opencode-go/cache` 1 / 317；`providers/qoder/cache` 1 / 2744；`providers/workbuddy/cache` 9 / 127859；`providers/workbuddy/logs` 0。

### 1.2 语言构成（TOTAL_TEXT_FILES=1153 TOTAL_BYTES=45225871）

| 扩展名 | files | bytes | lines | 扩展名 | files | bytes | lines |
|---|---:|---:|---:|---|---:|---:|---:|
| .go | 450 | 4739218 | 113434 | .py | 258 | 3262258 | 66155 |
| .md | 200 | 5159521 | 46751 | .json | 89 | 2601044 | 39530 |
| .txt | 31 | 224706 | 5193 | .ps1 | 30 | 94259 | 1882 |
| .js | 24 | 519303 | 9763 | .bat | 17 | 11791 | 316 |
| .yml | 12 | 47358 | 1062 | .jsonl | 10 | 27830932 | 40552 |
| .sh | 8 | 25237 | 640 | .log | 8 | 171766 | 3404 |
| .mjs | 3 | 8111 | 148 | .html | 3 | 487611 | 7758 |
| .ts | 3 | 33796 | 833 | .cjs | 3 | 7149 | 105 |
| .vbs | 3 | 1372 | 30 | .cmd | 1 | 439 | 9 |

扩展名总数另有 `.pyc` 59、无扩展 9、`.exe` 5、`.db` 4、`.api_key_secret` 1、`.panel-token` 1、`.pid` 1（仅计数，未读内容）。按用户要求四类：Go 450、Python 258、PowerShell 30、VBS 3；其余主要体量在 `.jsonl`（27,830,932 B）与 `.md`（5,159,521 B）。

### 1.3 入口点与索引

`grep '^package main$'` 命中：`gateways/upstream/workbuddy/cmd/credit/main.go:15`、`cmd/login/main.go:18`、`cmd/server/main.go:2`、`cmd/signin/main.go:3`、`cmd/trial/main.go:20`、`internal/probe/probe_channel.go:19`、`internal/probe/probe169.go:26`、`gateways/zgate/main.go:15`（`main.go:44` `const version = "0.3.0"`，`main.go:54` `case serve`）。

`Get-Content | Measure-Object -Line`：`sync-models.ps1` 354 lines / 17133 B；`sync-models.vbs` 14 / 670；`README.md` 94 / 9830；`AGENTS.md` 79 / 7210。`read` 的 totalLines（含空行）分别为 399 / 17 / 129。

`tools/` 关键脚本字节：`model_alias.py` 128834、`dsh_sync.py` 37234、`model_stream_check.py` 29621、`model_caps.py` 43248、`check-docs.py` 8343、`check-project.py` 19833、`check-secrets.py` 8704、`sync_report.py` 20340、`arena_leaderboard.py` 16945、`model_probe.py` 12540、`model_score.py` 7895、`caps_upstream.py` 18464、`agent_profiles.py` 11983、`rename-to-modelbus.ps1` 12167。

目录树（depth<=2）：`.work/` 下 agent-gemini-runtime / agent-opt-gateway / b-opt / dsh-docs-20261111 / dsh-final-20261111 / dsh-first-20261111 / dsh-gate-20261111 / dsh-providers-20261111 / dsh-rename-20261111 / dsh-source-20261111 / dsh-tools-20261111 / evidence / gocache / model-stream / tmpdel；`docs/` 下 archive / release-notes / reports；`gateways/` 下 gateways / legacy-router / upstream / zgate；`providers/` 下 gemini / hajimi / opencode-go / qiniu / qoder / qwen / workbuddy；`third-party/` 下 zcode / zcodium；`tools/` 下 __pycache__ / zgate-lifecycle。

`docs/` 42 files；`docs/reports/` 10 files（9 份 `MODEL-SYNC-*.md` + `README.md`），`MODEL-SYNC-20261112-1209.md` 2817 B / mtime 2026-11-12 12:09:00。`evidence/` 71 份历史分片，最大 `agent-gateway-lifecycle.md` 432441 B、`agent-gemini-memory-docs.md` 147311 B、`agent-zcode-census.md` 112420 B —— `evidence/` 是历次 agent 报告集合，不是运行态数据源。

`docs/README.md:33` 原文索引仍为「MD3 选型（Beer CSS 单 CSS）」，与本轮「Microsoft Fluent 2」口径冲突，只读记录，未改 `docs/`。

---

## 2. 资源占用实测（每条给 文件:行 + 实测数字）

| # | 热点 | 文件:行（源码/配置证据） | 实测数字（2026-11-12 16:27–16:37） | 影响面 |
|---|---|---|---|---|
| H1 | zgate 二进制备份无上限 | `tools/zgate-lifecycle/install-lifecycle.ps1:78` `New-TimeSpan -Minutes 1` + `:83` `Register-ScheduledTask`；`tools/zgate-lifecycle/deploy-zgate.ps1:58` 部署日志追加（`[待补: deploy-zgate.ps1 备份语句行号]`） | `gateways/zgate/zgate.exe.bak-*` 6 份 64,514,048 B，单份 10,695,680–10,816,512 B；`.work/zgate.candidate.exe` 7,415,808 B、`.work/zgate-early-sse.exe` 10,695,680 B；`.work/` 合计 335 files / 24,133,519 B | 回滚链副本约 61.5 MiB + .work 候选约 17 MiB |
| H2 | 请求日志按天追加、未找到 retention | `gateways/upstream/workbuddy/internal/reqlog/reqlog.go:356` `ticker := time.NewTicker(time.Second)`；`docs/CONSOLE.md:59` 设计口径 30s | 7 files / 27,688,206 B / 40,351 行；oldest 2026-11-05 23:59:55，newest 2026-11-12 16:31:17；单日最大 `requests-2026-11-10.jsonl` 6,734,059 B / 9,753 行 | 磁盘随流量线性增长；明细行含 tokens / ttfb / attempts / credit |
| H3 | WB data 全量 JSON + 同名 .bak 双写 | `gateways/upstream/workbuddy/internal/usage/usage.go:37` `const flushInterval = 30 * time.Second`、`:129` ticker；`internal/balance/balance.go:31` 30min 采样、`:41` 30s flush、`:372` ticker | `data/` 18 files / 29,240,509 B；`usage.json` 401,887 B + `.bak` 401,886 B（16:30:19）、`credit-history.json` 256,620 + 256,621 B（16:26:51）、`state.json` 17,294 + 17,298 B（16:30:44）、`balance_history.json` 81,892 B（16:27:19） | 每次 flush 全量重写 + 等量备份，写放大约 2× |
| H4 | 配置/价目备份无上限 | `tools/model_alias.py:2594-2595`、`tools/dsh_sync.py:510-518`、`providers/opencode-go/ops/go_model_sync.py:903-906`、`providers/workbuddy/workbuddy_fetch_pricing.py:397` | `~/.zcode/v2/provider_config.json.bak-*` 49 份 / 849,378 B；`model-alias-map.json.bak-*` 4 份 / 99,994 B；`wb_pricing.json.bak-*` 7 份 / 99,411 B | copy2 全量副本，含 `apiKey` 键真值；只统计数量/字节 |
| H5 | 网关日志：主日志有轮转、子进程日志无 | `gateways/zgate/internal/logx/logx.go:30-34`、`:80-96`（5 MB 单份 `.1` 轮转）；`internal/supervisor/supervisor.go:241`/`:245` O_CREATE|O_APPEND 无轮转；`docs/CONSOLE.md:63` | `%LOCALAPPDATA%/ZCodeGateway` 60 files / 27,257,840 B（oldest 2026-10-23 19:37:58，newest 16:31:07）；`~/.zcode/v2/logs` 3 / 1,148,621 B；`%LOCALAPPDATA%/ModelBus/logs` 6 / 207,568 B；仓内 `gateways/upstream/qoder/qoder-proxy.err.log` 159,809 B | 子进程异常刷屏无上限；主日志 Rename 失败仍继续 append |
| H6 | 索引产物 | 无源码行（工具产物） | `.codegraph/codegraph.db` 17,428,480 B / mtime 2026-11-12 16:28:54；`.codegraph/.gitignore` 229 B / 2026-10-21 01:57:41 | 与用户「未初始化」口径冲突；本分片未用它检索 |
| H7 | `%SystemDrive%` 字面量垃圾目录 | `PROGRESS.md:2692/2739/2777`（历史清理记录） | 5 files / 1,332,016 B，含两个 Caches .db（662,488 / 308,840 B）与 `sgim_picface_cloud{_bak}.bin` | 环境变量未展开，历史清理后又出现 |
| H8 | 轮询 / 看门狗频率 | `tools/zgate-lifecycle/install-lifecycle.ps1:78` PT1M；`gateways/zgate/internal/supervisor/supervisor.go:368` 5s；`internal/router/early_sse.go:219` 默认 10s keepalive、`:234` ticker；`internal/alert/alert.go:20` 30s + `:264` ticker；`internal/proxypool/transport.go:424` 1s；`cmd/server/config.go:36/:39` 面板 0=前端缺省 5s；`docs/CONSOLE.md:41` | 常量即实测频率；`docs/CONSOLE.md:41` 明确「每次 /health 请求都会 `aliases.Reload()` 重读 alias map 文件，轮询间隔必须 ≥ 5s」 | 后台轮询若 <5s 会把 alias 文件重读放大成热点 |
| H9 | 连接池 / 无淘汰缓存 | `gateways/zgate/main.go:174` 100 / `:175` 32 / `:176` 90s / `:180` 8s / `:182` 30s；`internal/router/egress.go:44` `cache map[string]*http.Transport`、`:50` 空 map、`:59` `t := e.base.Clone()`、`:65` `e.cache[proxy] = t` | base 有硬上限；egress cache 按 proxy 字符串无上限无淘汰 | 见 P1-6 |
| H10 | 全量重写 / 重复计算 | `tools/caps_upstream.py:411` `open(path,"w")`；`tools/model_caps.py:133` `io.open(path,"wb")`；`tools/zgate-lifecycle/current-models.ps1:262` WriteAllText；`go_model_sync.py:696-701` tmp + `json.dump` + `os.replace`（已属原子写良好实践）；`sync-models.ps1:277/321-325` 统一命名写入 + 漂移二轮写入 | `grep shutil.copy2|json.dump|backup` 在 `tools/` 命中 39 行，含 5 处 backup 逻辑 | 同一份配置一轮同步最多写两轮 + 备份 |

TOP30 大文件原始摘录（字节 + 路径）：18821632 `gateways/upstream/workbuddy/wb2api.exe`；17428480 `.codegraph/codegraph.db`；10832896 `gateways/zgate/zgate.exe`；10816512 / 10797568 / 10797568 / 10717184 / 10695680 / 10689536 六份 `zgate.exe.bak-*`；10695680 `.work/zgate-early-sse.exe`；7415808 `.work/zgate.candidate.exe`；7354928 `gateways/upstream/qoder/umid/sgsdk.dll`；6734059 / 5994700 / 4117548 / 4088416 / 3775489 / 2950332 六份 `data/request-logs/requests-2026-11-*.jsonl`；432441 `evidence/agent-gateway-lifecycle.md`；401884 / 401649 `data/usage.json{,.bak}`；511669 `qoder_proxy.py`；510319 `qoder_proxy.cpython-312.pyc`。

---

## 3. 可证明行为等价的最小优化候选

判据来自 `~/.dsh/AGENTS.md` §6：性能优化 / 重构先给行为等价证明，证不出等价就别动。以下两条已给等价证明方法并附本分片实测矩阵；C 路只读，实际改码交主线。

### C1 · `providers/opencode-go/ops/go_model_sync.py:700` 校验读改用 with

- 现状：`:697` `tmp = path + ".tmp"`、`:698` `with open(tmp,"w",encoding="utf-8") as f:`、`:699` `json.dump(cfg,f,ensure_ascii=False,indent=2)`、`:700` `json.load(open(tmp, encoding="utf-8"))  # 写前校验`、`:701` `os.replace(tmp,path)`。
- 候选：把 `:700` 改成 `with open(tmp, encoding="utf-8") as f: json.load(f)`。只改校验读的文件生命周期，不改写入内容、不改 `os.replace` 时机。
- 等价证明方法（行为矩阵 + 字节差分）：① 对同一 `cfg` 分别跑原/新 `write_config`，`hashlib.sha256` 比对 `os.replace` 后目标文件字节（因 `:700` 只读不写，预期完全一致）；② valid JSON 的 `json.load` 返回值相等；③ invalid JSON 的异常类型与消息逐字相等；④ `python -W error::ResourceWarning` 下原写法触发未关闭文件告警、新写法不触发。
- 本分片已实测（Python 3.12，`%USERPROFILE%/AppData/Local/Programs/Python/Python312/python.exe`，见 §9 R7）：`C1_valid_equal= True`；`C1_invalid_same= True exc= JSONDecodeError | Expecting property name enclosed in double quotes: line 1 column 2 (char 1)`；`EXIT=0`。
- 影响：消除对 CPython 引用计数立即关闭文件句柄的依赖；Windows 上 `os.replace` 前若句柄未释放会替换失败。标 P2，等价已证，可列入本轮候选。

### C2 · `sync-models.ps1:275-277` 与 `:316-318` 公共参数数组去重

- 现状：`:275` `$scoreArgs = @("tools\model_alias.py","--slot","auto","--apply","--arena")`、`:276` `if ($scoresOn) { $scoreArgs += "--scores" }`；`:316` `$checkArgs = @("tools\model_alias.py","--check","--arena")`、`:317` `if ($scoresOn) { $checkArgs += "--scores" }`、`:318` `$checkArgs += $probeArgs`。
- 候选：抽 `$commonArgs = @("--arena"); if ($scoresOn) { $commonArgs += "--scores" }`，再 `$scoreArgs = @("tools\model_alias.py","--slot","auto","--apply") + $commonArgs`、`$checkArgs = @("tools\model_alias.py","--check") + $commonArgs + $probeArgs`。
- 等价证明方法：PowerShell 数组拼接行为矩阵，覆盖 `scoresOn ∈ {True,False}` × `probeArgs ∈ {@(), @('--probe-file','P')}` 共 4 组，比较 `-join '|'` 的字符串序列（`Invoke-Py` 用 `& $PY @args`，只依赖顺序与元素值）。
- 本分片已实测（见 §9 R6）：`scoresOn=True  probe=0  score_eq=True check_eq=True`；`scoresOn=True  probe=2  score_eq=True check_eq=True`；`scoresOn=False probe=0  score_eq=True check_eq=True`；`scoresOn=False probe=2  score_eq=True check_eq=True`。
- 边界：`sync-models.ps1:321-325` 漂移分支还有 `$scoreArgs2` / 复查参数，本矩阵只覆盖 `:275-277` 与 `:316-318`；若一并重构需把 `$scoreArgs2` 纳入同一矩阵复验。标 P2，等价已证（限定范围），可列入本轮候选。

---

## 4. 证不出等价 → 不建议本轮改

| # | 观察 | 风险 / 等价缺口 | 结论 |
|---|---|---|---|
| N1 | 6 份 `zgate.exe.bak-*` 64,514,048 B + `.work/` 两份候选 exe 共 18,111,488 B | 二进制是受控换版回滚链（`docs/ZGATE-LIFECYCLE.md`），删除后不可回滚；未证明哪个消费方在何时读哪一份 | **不建议本轮改** |
| N2 | `request-logs/*.jsonl` 7 files / 27,688,206 B 无 retention | 加保留天数会删掉流量页历史与审计证据；未找到清理实现，也未证明后台只依赖近 N 天 | **不建议本轮改** |
| N3 | `egress.go:65` cache 无上限、`:60-64` `url.Parse` 失败静默 | 加 LRU / 上限会改变长连接复用与代理切换时机；解析失败改为报错会改变请求是否成功 | **不建议本轮改** |
| N4 | 5 处 backup / 原子写重复（`dsh_sync.py:510-518`、`model_alias.py:2594-2595`、`workbuddy_sync.py:355`、`workbuddy_fetch_pricing.py:397`、`go_model_sync.py:696-701`） | 各处备份命名、触发时机、失败处理不同，抽公共 helper 需逐处字节差分，当前未证 | **不建议本轮改** |
| N5 | `sync-models.ps1:31` `$ErrorActionPreference = "Continue"`、`:263/:270/:289/:321/:356` `-Soft` | 改 `Stop` 或去掉 `-Soft` 会直接改变一轮同步的成败与退出码，明显不等价 | **不建议本轮改** |
| N6 | `%SystemDrive%/` 字面量目录 1,332,016 B、49 份配置备份 849,378 B | 删除属不可逆且备份含凭据真值；清理路径/保留份数需人拍板 | **不建议本轮改** |
| N7 | `README.md:45` Node 18+ vs 环境 Node 20+、`docs/README.md:33` MD3 vs Fluent 2 | 是文档口径，不是代码优化；`docs/` 在本分片禁改范围 | **不建议本轮改**（由主线处理） |

---

## 5. 可可视化资产清单（路径 / 关键字段 / 更新频率 / 脱敏红线）

「更新频率」列 = 本分片实测 mtime + 触发点 `文件:行`；TTL 建议引用现有设计稿 `docs/CONSOLE.md:49-69`（30s / 60s / 300s / 5s），那是设计口径不是本分片实测。「关键字段」一律只列键名 / 结构，不列取值。

| 资产 | 实测路径 | 关键字段（仅键名） | 实测体量 / 更新频率 | 脱敏红线 |
|---|---|---|---|---|
| Provider 配置 | `~/.zcode/v2/provider_config.json` | `schemaVersion`；`config.providerOrder[3]`；`providerConfigRules.providerRules[3]`：providerId / providerName / config.group / access.apiKey / api.baseUrl / personalModelIds[2] / modelOrder[2]；`modelConfigRules.providerModelRules[18]`：modelId / enabled / contextWindow / supportsToolCall / maxOutputTokens / reasoningLevel / providerId；`manualProviderModelRules[0]` | 16,186 B，mtime 2026-11-12 12:05:54；触发 `sync-models.ps1:277` + `:321-325` | **只露 has_key**；`apiKey` 取值 `<REDACTED-CREDENTIAL>`；禁 apikey / token / cookie / secret / sk- 真值 |
| Alias 真值 | `~/.zcode/v2/model-alias-map.json` | models / legacy / generated_at；每模型 group / price / chain[] / fallbacks[] / legacy_ids[] / protocol（`docs/CONSOLE.md:51`） | 23,928 B，12:05:54；同上 | chain 可能含 baseUrl，只露结构不露完整 URL |
| 探针 | `~/.zcode/v2/model_probe.json` | 按模型 id：display / status / http / ms / detail / credit / provider | 49,389 B，12:05:53；`sync-models.ps1:289` `model_probe.py --timeout 90 --sleep 0.5 --max-tokens 256` | detail 可能含上游错误正文，展示前过滤 |
| 评分 | `~/.zcode/v2/model-scores.json` | basis[model, score, price, source] + models | 1,767 B，12:00:28；`sync-models.ps1:270` `model_score.py --write --quiet` | 无凭据 |
| 额度窗口 | `~/.zcode/v2/quota-windows.json` | windows[]{channel, until, days_left, note} | 621 B，12:05:54；`:277` 统一命名写入 | 无凭据 |
| 竞技榜 | `~/.zcode/v2/arena-main.json`、`arena-leaderboard.json` | 候选与实时榜 | 3,188 B / 117,012 B，12:00:28；`sync-models.ps1:263` `arena_leaderboard.py --refresh --force --write` | 无凭据 |
| 同步状态 | `~/.zcode/v2/model-sync-state.json` | models 数量 | 3,374 B，12:09:00；`sync-models.ps1:360-364` `sync_report.py --write` | 无凭据 |
| 流式准入 | `.work/model-stream/latest.json` | state / reasons / tps / firstMs / effort / finishReason（`docs/CONSOLE.md:54`） | `.work/model-stream` 11 files / 180,304 B；`sync-models.ps1:356` `model_stream_check.py --changed --soft` | 无凭据 |
| WB 价目 | `providers/workbuddy/cache/wb_pricing.json` | WB 折扣价 | 14,201 B，12:00:12；`sync-models.ps1:227-228` | 同目录 `provider_config.json.pre-alias-fix-*.bak` 可能含凭据，禁读 |
| Qoder 价目 | `providers/qoder/cache/qd_prices.json` | 峰谷价 | 2,744 B，12:05:55；`sync-models.ps1:253` | 无凭据 |
| Go 协议缓存 | `providers/opencode-go/cache/go_protocols.json` | 协议映射 | 317 B，12:00:12；`go_model_sync.py:895-896` | 无凭据 |
| 请求明细 | `gateways/upstream/workbuddy/data/request-logs/requests-YYYY-MM-DD.jsonl` | tokens / ttfb / attempts / credit（`docs/CONSOLE.md:59`） | 7 files / 27,688,206 B / 40,351 行；newest 16:31:17；`reqlog.go:356` 1s ticker 落盘 | **后台只做聚合**（行数、成功率、TTFB 分位、token 汇总）；禁展示原始行；原始行可能含 Authorization / cookie / prompt；本分片只输出行数与字节 |
| WB 用量与流水 | `gateways/upstream/workbuddy/data/{state,usage,credit-history,balance_history,task-jobs,task-runs,task-logs}.json` | 账号余额 / 信用 / 任务流水；`state.json` 含 uid 等标识 | 18 files / 29,240,509 B；usage 401,887 B（16:30:19）、credit-history 256,620 B（16:26:51）、state 17,294 B（16:30:44）；`usage.go:37/:129` 30s、`balance.go:31/:41/:372` 30min/30s | `auths/*.json` 与 state 只露数量与掩码；禁 accessToken / refreshToken / uid 全量 / token / cookie |
| WB 账号 | `gateways/upstream/workbuddy/auths/*.json` | 账号身份（`docs/CONSOLE.md:61` 实测 8 个） | 设计 TTL 300s；本分片未逐文件读取 | **只给数量与掩码**，取值一律 `<REDACTED-CREDENTIAL>` |
| Qoder 用量 | `gateways/upstream/qoder/usage/usage-summary.json`、`accounts/scheduler/state.json` | by_model / ttft_ms_sum / samples（`docs/CONSOLE.md:62`） | 设计 TTL 30s | 无凭据展示 |
| 网关日志 | `%LOCALAPPDATA%/ZCodeGateway/`（zgate.log 及 zgate-daemon / zgate-launch / deploy-zgate / watchdog / 子网关 stdout.stderr） | `时间 LEVEL msg`；日志内 uid 前 8 位（`logfmt.go:5/:41`） | 60 files / 27,257,840 B，oldest 2026-10-23 19:37:58，newest 16:31:07；zgate.log 5 MB 轮转（`logx.go:30-34`），子进程日志无轮转 | 响应过 `grep -iE 'apikey|token|cookie|secret|sk-'` 须零命中 |
| 生命周期 / 同步日志 | `%LOCALAPPDATA%/ModelBus/logs/`、`~/.zcode/v2/logs/` | sync-<stamp>.log / _last-sync.txt / current-models.json | 6 files / 207,568 B（oldest 11-06 23:30:37，newest 11-12 12:09:01）；`~/.zcode/v2/logs` 3 / 1,148,621 B；`sync-models.ps1:42-46/:103/:113` | `:224` 只记 key 长度，仍禁真值 |
| 同步报告 | `docs/reports/MODEL-SYNC-<YYYYMMDD-HHMM>.md` | 每次同步变化清单 | 9 files / 24,252 B；`MODEL-SYNC-20261112-1209.md` 2817 B / 12:09:00；`sync-models.ps1:360-364` | 只列模型 id，不列凭据 |
| 凭据类（只读存在性） | `gateways/upstream/workbuddy/config.json`、`~/.zcode/v2/credentials.json`（5,763 B）、`~/.zcode/v2/certs/`（2 files / 2,868 B）、`*.api_key_secret` / `*.panel-token` | 只统计文件存在与 `has_key` | 本分片**未读取任何取值** | **绝不进后台响应、绝不进报告**；`sync-models.ps1:216-225` 从 config.json 读 api_key 写 `$env:WB_GATEWAY_KEY` 且只日志长度；真值一律 `<REDACTED-CREDENTIAL>` |

后台聚合口径（供主线核对）：`docs/CONSOLE.md:122-133` 已有 8 页信息架构（总览 5s / 模型 30s / 价格 60s / 健康 30s / 流量 30s / 账号 30s / 日志 手动 / 运维 15s）；`docs/CONSOLE.md:41` 的「/health 轮询 ≥5s」是硬约束，因为它每次请求都 `aliases.Reload()` 重读 alias map。

---

## 6. 功能实现审查（P0 / P1 / P2）

**P0 = 已证实的服务中断、凭据真值外泄到公开输出、数据损坏。本轮 0 项**：7871 正常 Listen（见 §7）、`git status --short` 仅三处用户既有改动、未读取也未输出任何凭据取值。

| 级别 | 问题 | 文件:行 | 影响面 / 实测证据 |
|---|---|---|---|
| P1-1 | 请求日志无保留策略 | `gateways/upstream/workbuddy/internal/reqlog/reqlog.go:356`；grep cleanup/rotate/retention 未发现实现 | 7 files / 27,688,206 B / 40,351 行且 16:31:17 仍在写；后台只能聚合，不能展示原始行 |
| P1-2 | 配置备份无上限且副本含凭据 | `tools/model_alias.py:2594-2595`、`tools/dsh_sync.py:510-518`、`go_model_sync.py:903-906` | 49+4+7 份 / 849,378+99,994+99,411 B；copy2 是全量副本，含 `apiKey` 键真值 |
| P1-3 | 日志写入错误被吞、轮转失败继续 append | `gateways/zgate/internal/logx/logx.go:57` `n, _ := l.file.WriteString(line)`、`:85-87` | 轮转失败时单文件可无限增长且无告警；目录已达 27,257,840 B |
| P1-4 | 子进程 stdout/stderr 无轮转 | `gateways/zgate/internal/supervisor/supervisor.go:241`/`:245` O_CREATE|O_APPEND|O_WRONLY | 子进程刷屏直接打满磁盘；`qoder-proxy.err.log` 已 159,809 B |
| P1-5 | 同步流水线失败被吞 | `sync-models.ps1:31` Continue、`:263/:270/:289/:321/:356` `-Soft`、`:296-300` ConvertFrom-Json 失败仅 `Say` | 探针 JSON 损坏时静默跳过 `--probe-file`（`:305` 过半才带），最终 `:399` exit 仍可能为 0 |
| P1-6 | egress transport 缓存无上限 + 解析错误静默 | `gateways/zgate/internal/router/egress.go:44/:50/:59-65`（`:60-64` `url.Parse` err 分支无显式处理，`:65` 仍入缓存） | 异常 proxy 串静默走默认 transport 且无日志；map 按串无限增长；`main.go:174-176` 的 100/32/90s 只约束 base |
| P2-1 | 硬编码绝对路径 | `sync-models.ps1:34-35`（`F:\Project\ModelBus` / `C:\Program Files\Git\cmd`）、`sync-models.vbs:13`、`tools/rename-to-modelbus.ps1:24-26` | 4 处；迁移 / 异机执行失效 |
| P2-2 | 编码历史包袱（GBK / UTF-8 / BOM） | `sync-models.ps1:66-76`（已主动设 PYTHONIOENCODING / PYTHONUTF8 / UTF8NoBom / chcp 65001，注释解释 936 双重编码）、`tools/rename-to-modelbus.ps1:250` 无 BOM UTF8Encoding($false)、`evidence/agent-code-review.md:128`、`CHANGELOG.md:420/424/446` | PS5.1 按 GBK 读无 BOM UTF-8 会乱码；老宿主跑重命名脚本风险 |
| P2-3 | 备份 / 原子写重复 5 处 | `tools/dsh_sync.py:510-518`、`tools/model_alias.py:2594-2595`、`providers/workbuddy/workbuddy_sync.py:355`、`workbuddy_fetch_pricing.py:397`、`go_model_sync.py:696-701` | G_dup total=39；命名 / 时机 / 失败处理不一致，等价未证 |
| P2-4 | `%SystemDrive%` 字面量垃圾目录 | `PROGRESS.md:2692/2739/2777` | 5 files / 1,332,016 B；环境变量未展开，清理后又出现 |
| P2-5 | 文档口径与 Fluent 2 冲突 | `docs/README.md:33`、`docs/CONSOLE.md:33-69` | 索引仍写 MD3 / Beer CSS；本分片禁改 docs/ |
| P2-6 | README 版本 / 间隔口径 | `README.md:45` Node 18+（环境为 Node 20+）、`:51/:57` sleep 20 vs `sync-models.ps1:289` sleep 0.5 | 属不同工具，但读者易混 |
| P2-7 | VBS 注释过期 | `sync-models.vbs:7` 称日志写 `F:\Project\ModelBus\docs\reports\` | 实际 `sync-models.ps1:42-46` 写 `%LOCALAPPDATA%\ModelBus\logs\`；排障会找错目录 |
| P2-8 | `.codegraph` 口径冲突 | `.codegraph/.gitignore` 229 B / 2026-10-21 01:57:41；`codegraph.db` 17,428,480 B / 2026-11-12 16:28:54 | 用户口径「未初始化」；本分片按硬约束只用 grep/glob/read，未 init、未调 codegraph 工具 |

---

## 7. 端口检查（供主线定后台端口）

- **7872：空闲** —— `Get-NetTCPConnection -LocalPort 7872` 零匹配，`netstat -ano | Select-String ':7872'` 零行。可作独立后台监听端口。
- **7871：已占用** —— `zgate` pid=17336，`Path=F:\Project\ModelBus\gateways\zgate\zgate.exe`，Listen；`Get-NetTCPConnection -LocalPort 7871` 列出 12 条 Established，对端 pid 11720 多条。
- 原始输出摘录：`TCP    127.0.0.1:7871         0.0.0.0:0              LISTENING       17336`。
- `docs/CONSOLE.md:29/43` 记录网关非代理端点只有 `GET /health`、`GET /models`、`POST /admin/reload`，且 `/health` 有 5 个按 JSON 解析的消费方 —— 后台应独立在 7872，不改网关响应。本分片未请求任何端点、未重启服务。

---

## 8. 外部事实卡（Microsoft Fluent 2 版本锚点）

> 本分片 C 路不承担选库，未展开 stars / pushed_at 对比；以下为已查确切值，供主线核对后台设计规则的版本锚点。

- `来源 https://api.github.com/repos/microsoft/fluentui/contents/packages/web-components/package.json（gh api ... -H 'Accept: application/vnd.github.raw+json'）｜确切值 @fluentui/web-components 3.2.1 / MIT｜适用版本 Fluent 2 Web Components 3.2.1｜查证时间 2026-11-12 16:37｜用于核对 Microsoft Fluent 2 后台设计规则的版本锚点`
- `来源 https://api.github.com/repos/microsoft/fluentui/releases/latest｜确切值 @fluentui/react-provider_v9.22.23 / 2026-10-29T01:05:26Z / https://github.com/microsoft/fluentui/releases/tag/%40fluentui/react-provider_v9.22.23｜适用版本 microsoft/fluentui 仓库最新 release tag｜查证时间 2026-11-12 16:37｜用于说明 monorepo 最新 tag 是 React provider 子包、不能当作 Web Components 版本`

---

## 9. 可复现命令与原始输出摘录

以下命令为本分片使用的 PowerShell 7 等价复现形式；工作目录 `F:\Project\ModelBus`。所有摘录均经脱敏检查（只有路径、字节数、行数、端口、进程名，无凭据取值）。

**R1 · 根与语言构成**

```powershell
git -C 'F:/Project/ModelBus' rev-parse --show-toplevel
git -C 'F:/Project/ModelBus' status --short
git -C 'F:/Project/ModelBus' branch --show-current
Get-ChildItem -LiteralPath 'F:/Project/ModelBus' -Force -Recurse -File |
  Where-Object { $_.FullName -notlike '*\.git\*' } |
  Group-Object Extension | Sort-Object Count -Descending |
  ForEach-Object { '{0,-8} {1}' -f $_.Count, $_.Name }
```

原始输出摘录：

```text
GIT_ROOT=F:/Project/ModelBus
CWD=F:\Project\ModelBus
branch main
 M docs/reports/README.md
?? docs/reports/MODEL-SYNC-20261112-1209.md
?? evidence/go-model-sync-20261112-120012.md
TOTAL_TEXT_FILES=1153 TOTAL_BYTES=45225871
.go 450 4739218 113434
.py 258 3262258 66155
.md 200 5159521 46751
.jsonl 10 27830932 40552
.ps1 30 94259 1882
.vbs 3 1372 30
```

**R2 · 目录体量 / 大文件**

```powershell
Get-ChildItem -LiteralPath 'F:/Project/ModelBus' -Directory -Force | ForEach-Object {
  $fs = Get-ChildItem -LiteralPath $_.FullName -Recurse -File -Force -ErrorAction SilentlyContinue
  '{0,-18} files={1,-5} bytes={2}' -f $_.Name, $fs.Count, (($fs | Measure-Object Length -Sum).Sum)
}
Get-ChildItem -LiteralPath 'F:/Project/ModelBus' -Recurse -File -Force -ErrorAction SilentlyContinue |
  Sort-Object Length -Descending | Select-Object -First 30 |
  ForEach-Object { '{0,-10} {1}' -f $_.Length, $_.FullName }
```

原始输出摘录：

```text
gateways           files=990   bytes=165112883
.work              files=333   bytes=23963775
.codegraph         files=2     bytes=17428709
evidence           files=71    bytes=2027611
18821632 gateways\upstream\workbuddy\wb2api.exe
17428480 .codegraph\codegraph.db
10832896 gateways\zgate\zgate.exe
6734059 gateways\upstream\workbuddy\data\request-logs\requests-2026-11-10.jsonl
401884 gateways\upstream\workbuddy\data\usage.json
```

**R3 · 备份分组与日志目录**

```powershell
$z = Join-Path $env:USERPROFILE '.zcode\v2'
$r = 'F:/Project/ModelBus'
function Grp($label,$items){ '{0,-46} count={1,-4} bytes={2}' -f $label,$items.Count,(($items|Measure-Object Length -Sum).Sum) }
Grp 'gateways/zgate/zgate.exe.bak-*' (Get-ChildItem -File -Force -LiteralPath (Join-Path $r 'gateways\zgate') | Where-Object {$_.Name -like 'zgate.exe.bak-*'})
Grp 'provider_config.json.bak-*' (Get-ChildItem -File -Force -LiteralPath $z | Where-Object {$_.Name -like 'provider_config.json.bak-*'})
Grp 'wb_pricing.json.bak-*' (Get-ChildItem -File -Force -LiteralPath (Join-Path $r 'providers\workbuddy\cache') | Where-Object {$_.Name -like 'wb_pricing.json.bak-*'})
foreach($p in @((Join-Path $env:USERPROFILE '.zcode\v2\logs'),(Join-Path $env:LOCALAPPDATA 'ZCodeGateway'),(Join-Path $env:LOCALAPPDATA 'ModelBus\logs'),(Join-Path $r 'gateways\upstream\workbuddy\data\request-logs'))){
  $fs = Get-ChildItem -Recurse -File -Force -LiteralPath $p -ErrorAction SilentlyContinue
  '{0}  files={1} bytes={2} oldest={3} newest={4}' -f $p,$fs.Count,(($fs|Measure-Object Length -Sum).Sum),($fs|Sort-Object LastWriteTime|Select-Object -First 1).LastWriteTime,($fs|Sort-Object LastWriteTime -Descending|Select-Object -First 1).LastWriteTime
}
```

原始输出摘录：

```text
gateways/zgate/zgate.exe.bak-*                 count=6    bytes=64514048
provider_config.json.bak-*                     count=49   bytes=849378
wb_pricing.json.bak-*                          count=7    bytes=99411
model-alias-map.json.bak-* count=4 bytes=99994
%USERPROFILE%\.zcode\v2\logs  EXISTS files=3 bytes=1148621 oldest=2026-11-06 20:42:00 newest=2026-11-11 22:56:12
%USERPROFILE%\AppData\Local\ZCodeGateway  EXISTS files=60 bytes=27257840 oldest=2026-10-23 19:37:58 newest=2026-11-12 16:31:07
%USERPROFILE%\AppData\Local\ModelBus\logs  EXISTS files=6 bytes=207568 oldest=2026-11-06 23:30:37 newest=2026-11-12 12:09:01
F:/Project/ModelBus/gateways/zgate/logs  MISSING
F:/Project/ModelBus/gateways/upstream/workbuddy/data/request-logs  EXISTS files=7 bytes=27688206 oldest=2026-11-05 23:59:55 newest=2026-11-12 16:31:17
ZCODE_V2 files=87 bytes=11438854
```

**R4 · 请求日志逐文件行数**

```powershell
$p = 'F:/Project/ModelBus/gateways/upstream/workbuddy/data/request-logs'
$tot = 0; $ln = 0
Get-ChildItem -File -Force -LiteralPath $p | Sort-Object Name | ForEach-Object {
  $n = (Get-Content -LiteralPath $_.FullName | Measure-Object -Line).Lines
  $tot += $_.Length; $ln += $n
  '{0}  bytes={1,-9} lines={2}' -f $_.Name, $_.Length, $n
}
'TOTAL files={0} bytes={1} lines={2}' -f (Get-ChildItem -File -LiteralPath $p).Count, $tot, $ln
```

原始输出摘录：

```text
requests-2026-11-05.jsonl  bytes=2950332   lines=4494
requests-2026-11-06.jsonl  bytes=3775489   lines=5409
requests-2026-11-07.jsonl  bytes=27662     lines=39
requests-2026-11-09.jsonl  bytes=4117548   lines=5948
requests-2026-11-10.jsonl  bytes=6734059   lines=9753
requests-2026-11-11.jsonl  bytes=5994700   lines=8832
requests-2026-11-12.jsonl  bytes=4088416   lines=5876
TOTAL files=7 bytes=27688206 lines=40351
```

**R5 · 端口**

```powershell
Get-NetTCPConnection -LocalPort 7872 -ErrorAction SilentlyContinue
Get-NetTCPConnection -LocalPort 7871 -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,State,OwningProcess
netstat -ano | Select-String ':7871',':7872'
Get-Process -Id 17336 | Select-Object Id,ProcessName,Path
```

原始输出摘录：

```text
127.0.0.1 7871 Listen 17336
TCP    127.0.0.1:7871         0.0.0.0:0              LISTENING       17336
Id     ProcessName Path
17336  zgate       F:\Project\ModelBus\gateways\zgate\zgate.exe
```

（`7872` 无 Get-NetTCPConnection 匹配、netstat 无 `:7872` 行。）

**R6 · 行为等价矩阵（C2）**

```powershell
foreach($s in @($true,$false)){ foreach($pr in @(@(),@('--probe-file','P'))){
  $oldScore=@('tools/model_alias.py','--slot','auto','--apply','--arena'); if($s){$oldScore += '--scores'}
  $oldCheck=@('tools/model_alias.py','--check','--arena'); if($s){$oldCheck += '--scores'}; $oldCheck += $pr
  $common=@('--arena'); if($s){$common += '--scores'}
  $newScore=@('tools/model_alias.py','--slot','auto','--apply')+$common
  $newCheck=@('tools/model_alias.py','--check')+$common+$pr
  '{0,-5} {1,-2} {2} {3}' -f $s,$pr.Count,(($newScore -join '|') -eq ($oldScore -join '|')),(($newCheck -join '|') -eq ($oldCheck -join '|'))
}}
```

原始输出摘录：

```text
scoresOn=True  probe=0  score_eq=True check_eq=True
scoresOn=True  probe=2  score_eq=True check_eq=True
scoresOn=False probe=0  score_eq=True check_eq=True
scoresOn=False probe=2  score_eq=True check_eq=True
```

**R7 · Python 文件句柄等价（C1）**

```powershell
python -c @'
import json, os, tempfile
p = os.path.join(tempfile.gettempdir(), 'c1-valid.json')
q = os.path.join(tempfile.gettempdir(), 'c1-invalid.json')
with open(p,'w',encoding='utf-8') as f: json.dump({'a':1,'b':[2,3]}, f, ensure_ascii=False, indent=2)
with open(q,'w',encoding='utf-8') as f: f.write('{not json')
a = json.load(open(p, encoding='utf-8'))
with open(p, encoding='utf-8') as f: b = json.load(f)
print('C1_valid_equal=', a == b)
def exc(fn):
    try: fn()
    except Exception as e: return (type(e).__name__, str(e))
    return ('NO_EXC','')
e1 = exc(lambda: json.load(open(q, encoding='utf-8')))
def withread():
    with open(q, encoding='utf-8') as f: json.load(f)
e2 = exc(withread)
print('C1_invalid_same=', e1 == e2, 'exc=', e1[0], '|', e1[1])
os.remove(p); os.remove(q)
'@
```

原始输出摘录：

```text
PY=%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe
C1_valid_equal= True
C1_invalid_same= True exc= JSONDecodeError | Expecting property name enclosed in double quotes: line 1 column 2 (char 1)
EXIT=0
```

**R8 · Fluent 2 事实卡取值命令**

```powershell
gh api 'repos/microsoft/fluentui/contents/packages/web-components/package.json' -H 'Accept: application/vnd.github.raw+json' | ConvertFrom-Json | Select-Object name,version,license
gh api 'repos/microsoft/fluentui/releases/latest' --jq '.tag_name + " | " + .published_at + " | " + .html_url'
```

原始输出摘录：

```text
GH=C:\Program Files\GitHub CLI\gh.exe
FACT name=@fluentui/web-components version=3.2.1 license=MIT
RELEASE=@fluentui/react-provider_v9.22.23 | 2026-10-29T01:05:26Z | https://github.com/microsoft/fluentui/releases/tag/%40fluentui/react-provider_v9.22.23
```

---

## 10. 交付与限制

- 本分片只写 `F:\Project\ModelBus\evidence\agent-audit.md`；未改 `PROGRESS.md`、任何配置、`docs/`、`tests/`、`gateways/`、任何现有源码。
- 未 `git add` / `commit` / `push`；未重启任何服务；未调用 codegraph 工具；未读取任何 key / token / 口令取值。
- 三处用户既有未提交改动（`docs/reports/README.md`、`docs/reports/MODEL-SYNC-20261112-1209.md`、`evidence/go-model-sync-20261112-120012.md`）只记录、未触碰。
- 信息缺口：`[待补: tools/zgate-lifecycle/deploy-zgate.ps1 备份语句行号]`（H1 只取到同脚本 `:58` 日志追加行）；`[待补: auths/*.json 与 gateways/zgate/zgate.json 的逐文件实测字节/mtime]`（按父代理「不要继续展开新检索」停止）；`[待补: request-logs 清理实现的有无由主线二次确认]`（本分片 grep 未命中实现）。
- 所有资源数字为 2026-11-12 16:27–16:37 采样，长驻进程持续写盘，主线复现时以当前时刻为准；关键数字（7 / 27,688,206 / 40,351、6 / 64,514,048、49 / 849,378、7871 pid 17336）已在本分片内两次独立采样或由行数命令复算。
