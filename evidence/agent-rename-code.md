# evidence/agent-rename-code.md — 代码改名分片自验证报告

> 结论：6 个脚本已改名，**活跃第一方代码**里 6 个旧脚本名 0 残留（`tools/dsh_sync.py.bak-effort-20261110125432` 历史备份快照仍含 6 处，属「历史记录」保护域，按硬约束未改），9 个 `.py` 全部 `py_compile` EXIT=0，1 个 `.js` `node --check` EXIT=0，4 组自造 env 已改为「新名优先 + 旧名兜底」。本报告记录实测命令与退出码，供主代理独立复核（self-report 不当结论）。

生成时刻：2026-11-11 16:12 +08:00（Asia/Shanghai）。真实项目根 `F:\Project\ModelBus`；工作目录 `F:\Project\_merged\DeepseekHarness` 为 junction 视图，读写均穿透到真实路径。

---

## 1. old → new 对照表（任务 A：6 个 fs.rename）

| # | old | new | 磁盘状态 |
| --- | --- | --- | --- |
| 1 | `providers/workbuddy/workbuddy_zcode_sync.py` | `providers/workbuddy/workbuddy_sync.py` | 新名存在，旧名消失 |
| 2 | `providers/workbuddy/workbuddy_probe_zcode.py` | `providers/workbuddy/workbuddy_probe.py` | 新名存在，旧名消失 |
| 3 | `providers/workbuddy/zcode_effective_body.js` | `providers/workbuddy/effective_body.js` | 新名存在，旧名消失 |
| 4 | `providers/qoder/qoder_zcode_sync.py` | `providers/qoder/qoder_sync.py` | 新名存在，旧名消失 |
| 5 | `providers/qoder/qoder_probe_zcode.py` | `providers/qoder/qoder_probe.py` | 新名存在，旧名消失 |
| 6 | `providers/qwen/qwen_zcode_sync.py` | `providers/qwen/qwen_sync.py` | 新名存在，旧名消失 |

新名文件实测字节：providers/workbuddy/workbuddy_sync.py (35107B)；providers/workbuddy/workbuddy_probe.py (11286B)；providers/workbuddy/effective_body.js (13668B)；providers/qoder/qoder_sync.py (19581B)；providers/qoder/qoder_probe.py (10043B)；providers/qwen/qwen_sync.py (22058B)。
旧名实测：providers/workbuddy/workbuddy_zcode_sync.py gone=true；providers/workbuddy/workbuddy_probe_zcode.py gone=true；providers/workbuddy/zcode_effective_body.js gone=true；providers/qoder/qoder_zcode_sync.py gone=true；providers/qoder/qoder_probe_zcode.py gone=true；providers/qwen/qwen_zcode_sync.py gone=true。
使用 `fs.rename`（未执行 `git add` / `commit` / `push`）；`git status` 呈 `D` 旧名 + `??` 新名，git 在 add 时会自行识别为 rename。`git ls-files` 证实 6 个旧名仍在 HEAD 中，本分片未动索引。

## 2. 改动文件清单

**任务 B（代码引用同步，11 个磁盘路径）**：

| 文件 | 改动行 | 内容 |
| --- | --- | --- |
| `tools/dsh_sync.py` | 11,60,205,218,222,227 | `zcode_effective_body.js` → `effective_body.js`（逐行仅此字符串） |
| `tools/model_probe.py` | 6,45 | 同上，保留 281 CRLF + 3 bare LF |
| `providers/workbuddy/effective_body.js` | 36,40,41,227 | 自引用改新名；:181 `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` 一字不动 |
| `providers/workbuddy/workbuddy_sync.py` | 33,36,37,38,39,43,106,118,302,305,320,322,339 | 自引用/叙述按语义中性化；:145/:146 契约 env/path 逐字不动 |
| `providers/workbuddy/workbuddy_probe.py` | 9,44,45,75,78 | 自引用改新名 |
| `providers/workbuddy/workbuddy_fetch_pricing.py` | 12,17,26 | 指向 `workbuddy_sync.py`（严格按 old→new 表，未采用「同步脚本」中性词） |
| `providers/qoder/qoder_sync.py` | 28,29,30,31,32,33,38,361 | 自引用/用法改新名 |
| `providers/qoder/qoder_probe.py` | 20,26,27,28,29,46,58 | :46 `from qoder_sync import (`；:58 `EFFECTIVE_BODY = REPO / "workbuddy" / "effective_body.js"` |
| `providers/qwen/qwen_sync.py` | 33,34,35,36,37,38 | 用法改新名；:37 `~/.zcode/v2/model_probe.json` 契约路径不动 |
| `providers/qwen/qwen_pool_probe.py` | 6,140 | 指向 `qwen_sync.py` |
| `sync-models.ps1` | 228,253 | `providers\workbuddy\workbuddy_sync.py`、`providers\qoder\qoder_sync.py`；UTF-8 BOM + LF 原样保留，:291 契约路径不动 |

**任务 C（自造 env 中性化 + 旧名读取别名，默认值不变）**：

| 新名（优先读） | 旧名（fallback） | 落点 |
| --- | --- | --- |
| `WB_PROBE_FILE` | `WB_ZCODE_PROBE_FILE` | `workbuddy_sync.py:152`、`workbuddy_probe.py:65-70` |
| `MB_API_TYPE` | `ZCODE_API_TYPE` | `effective_body.js:231` |
| `MB_BASE_URL` | `ZCODE_BASE_URL` | `effective_body.js:232` |
| `MB_MAX_OUTPUT_TOKENS` | `ZCODE_MAX_OUTPUT_TOKENS` | `effective_body.js:237` |

实现形式为嵌套 `os.environ.get("WB_PROBE_FILE", os.environ.get("WB_ZCODE_PROBE_FILE", <原默认值>))` 与 JS `opts.x || process.env.MB_X || process.env.ZCODE_X || <原默认值>`，语义等价于「新名优先 +旧名兜底 + 默认值不变」：`WB_PROBE_FILE` 未设时读旧名，旧名也未设时用原默认值 `CACHE_DIR / "wb_zcode_probe.json"`；`MB_*` 未设时回落 `ZCODE_*`，再回落 `openai-chat-completions` / `undefined` / `1024`。等价性实测（default / legacy 两档与改前一致，new / both 两档按预期由新名生效）已跑通，EXIT=0。

**叙述层（主代理 m00044 追加，6 个新脚本自身，共 28 行）**：6 处精确首行逐字按主代理给定文本改写（`workbuddy_sync.py:2`、`workbuddy_probe.py:2`、`effective_body.js:3`、`qoder_sync.py:2`、`qoder_probe.py:2`、`qwen_sync.py:2`），其余 22 行按「叙述性 ZCode → host / 主机」逐处判定（`workbuddy_sync.py:11`；`workbuddy_probe.py:12,30,36,77,83,86,111,125,150,269`；`qoder_sync.py:16,24,37,39,273,275,276`；`qoder_probe.py:5,7,10`；`qwen_sync.py:27`）。

**契约层 / vendored 一律未动**：`ZCODE_PERSONAL_PROVIDER_CONFIG_FILE`、`ZCODE_BUILTIN`、`ZCODE_GATEWAY_KEY`、`~/.zcode/v2/` 路径、`zcode-builtin.json`、`third-party/zcode/`、`zai-org/ZCode` 署名段（`effective_body.js:8-14`）、`zcode-main/free/saver`、schema 键、`zcode_body()` 函数名、状态值 `"zcode"` / `"zcode_body"`、运行时字符串字面量 `ZCODE_BUILTIN 指向的文件不存在` 等。逐行断言：`sync-models.ps1:291`、`effective_body.js:181/:182`、`workbuddy_sync.py:145/:146` 与备份逐字一致。

## 3. 备份路径

改前 `fs.copyFile`（`COPYFILE_EXCL`）备份 11 个文件到 `F:\Project\ModelBus\.work\dsh-rename-20261111\`（路径分隔符用 `__`）：

```
providers__workbuddy__workbuddy_zcode_sync.py          34968 B
providers__workbuddy__workbuddy_probe_zcode.py        11251 B
providers__workbuddy__zcode_effective_body.js         13540 B
providers__workbuddy__workbuddy_fetch_pricing.py      17372 B
providers__qoder__qoder_zcode_sync.py                 19619 B
providers__qoder__qoder_probe_zcode.py                10081 B
providers__qwen__qwen_zcode_sync.py                   22065 B
providers__qwen__qwen_pool_probe.py                    5693 B
tools__dsh_sync.py                                    27492 B
tools__model_probe.py                                 12552 B
sync-models.ps1                                       17145 B
```

叙述层改动前另存 6 个 `.pre-narrative` 快照（同目录）：`providers__workbuddy__workbuddy_sync.py.pre-narrative`(35055B)、`providers__workbuddy__workbuddy_probe.py.pre-narrative`(11254B)、`providers__workbuddy__effective_body.js.pre-narrative`(13665B)、`providers__qoder__qoder_sync.py.pre-narrative`(19571B)、`providers__qoder__qoder_probe.py.pre-narrative`(10039B)、`providers__qwen__qwen_sync.py.pre-narrative`(22029B)。

字节特征核验：11 个改动文件 BOM / CRLF / bare-LF 计数与备份一致（`FEATURES_IDENTICAL=true`）；`sync-models.ps1` 保持 UTF-8 BOM + 0 CRLF + LF；`tools/model_probe.py` 保持 281 CRLF + 3 bare LF；`qoder_sync.py` / `qwen_sync.py` 保持全 CRLF。

## 4. 残留检查结论

原始字节扫描（非 grep 文本匹配，逐文件 `fs.readFile` Buffer → UTF-8 字符串 → 正则），范围 `tools/`、`providers/`、`gateways/`、`sync-models.ps1`：

```
SCAN_SCOPE = tools/ providers/ gateways/ sync-models.ps1 (逐文件原始 Buffer → UTF-8 → 正则)
SCANNED_FILES_TOTAL = 930
ACTIVE_FIRST_PARTY_FILES = 906
ACTIVE_OLD_NAME_HITS = 0
ACTIVE_OLD_NAMED_FILES = []
HISTORICAL_SNAPSHOT_FILES = 24
HISTORICAL_OLD_NAME_HITS = 6
HISTORICAL_HIT_DETAIL = ["tools/dsh_sync.py.bak-effort-20261110125432 x6"]
OLD_NAME_TOKEN_TALLY = {"zcode_effective_body":6}
HISTORY_EXCLUDE_PATTERN = /\.bak-|\.pre-narrative|\.orig$|\.pyc$|\.bak$/i
```

正则：`workbuddy_zcode_sync|workbuddy_probe_zcode|zcode_effective_body|qoder_zcode_sync|qoder_probe_zcode|qwen_zcode_sync`。

结论分两层：

- **活跃第一方代码 = 906 个文件，旧名命中 0 处，0 残留**。文件名层面也无任何旧名文件（`OLD_NAMED_FILES = []`）。
- **历史备份快照**：`tools/dsh_sync.py.bak-effort-20261110125432` 含 6 处 `zcode_effective_body.js`。该文件是 2026-11-10 的脚本历史快照，属任务书「CHANGELOG 与历史记录」保护域，且不在任务 A/B 列明的文件清单内，故按硬约束**未改动**；主代理独立复核时请排除 `*.bak-*` / `*.pre-narrative` / `*.orig` / `*.pyc` / `*.bak`，否则全量 grep 会看到 6 而非 0。

`docs/`、`evidence/`、`CHANGELOG.md`、`PROGRESS.md`、`third-party/` 及历史记录属主代理或保护域，不在本分片改动范围。

自造 env 旧名 token 在 `providers/` 剩下的出现全部是 fallback 读取 / 兼容性注释（`WB_ZCODE_PROBE_FILE`×2、`ZCODE_API_TYPE` / `ZCODE_BASE_URL` / `ZCODE_MAX_OUTPUT_TOKENS` 各在注释与 `||` 兜底里），符合任务 C「旧名保留为读取别名」。

## 5. 验证命令与退出码

环境：Python 3.12.10、Node v24.13.1；`pwsh` 调用 `exitCode=0`。`PYTHONPYCACHEPREFIX` 指到 `.work\dsh-rename-20261111\pycache`，避免 `__pycache__` 污染仓内。

```text
=== PY_COMPILE ===
PYCOMPILE providers\workbuddy\workbuddy_sync.py EXIT=0
PYCOMPILE providers\workbuddy\workbuddy_probe.py EXIT=0
PYCOMPILE providers\qoder\qoder_sync.py EXIT=0
PYCOMPILE providers\qoder\qoder_probe.py EXIT=0
PYCOMPILE providers\qwen\qwen_sync.py EXIT=0
PYCOMPILE providers\workbuddy\workbuddy_fetch_pricing.py EXIT=0
PYCOMPILE providers\qwen\qwen_pool_probe.py EXIT=0
PYCOMPILE tools\dsh_sync.py EXIT=0
PYCOMPILE tools\model_probe.py EXIT=0
=== NODE_CHECK ===
NODECHECK providers/workbuddy/effective_body.js EXIT=0
=== GIT_STATUS_SCOPED ===
 D providers/qoder/qoder_probe_zcode.py
 D providers/qoder/qoder_zcode_sync.py
 M providers/qwen/qwen_pool_probe.py
 D providers/qwen/qwen_zcode_sync.py
 M providers/workbuddy/workbuddy_fetch_pricing.py
 D providers/workbuddy/workbuddy_probe_zcode.py
 D providers/workbuddy/workbuddy_zcode_sync.py
 D providers/workbuddy/zcode_effective_body.js
 M sync-models.ps1
 M tools/arena_leaderboard.py
 M tools/caps_upstream.py
 M tools/dsh_sync.py
 M tools/model_alias.py
 M tools/model_caps.py
 M tools/model_probe.py
 M tools/model_score.py
 M tools/sync_report.py
?? providers/qoder/qoder_probe.py
?? providers/qoder/qoder_sync.py
?? providers/qwen/qwen_sync.py
?? providers/workbuddy/effective_body.js
?? providers/workbuddy/workbuddy_probe.py
?? providers/workbuddy/workbuddy_sync.py
?? tools/agent_profiles.py
GIT_STATUS EXIT=0
```

逐条判读：9 条 `python -B -m py_compile` 全部 `EXIT=0`；`node --check providers/workbuddy/effective_body.js` `EXIT=0`；`git status --short -- providers tools sync-models.ps1` `EXIT=0`。`py_compile` 覆盖全部 9 个改过的 `.py`；`node --check` 覆盖唯一改过的 `.js`。

补充等价性（首轮复验，叙述层改动前后均通过）：`ENV_PY_EQUIV EXIT=0`（default / legacy 两档 `EQUIV=True`；new / both 两档 `EQUIV=False` 为预期——新名生效而旧文件不认识新名）；`ENV_JS_EQUIV EXIT=0`（同理）。

## 6. git 改名证据

上面 `GIT_STATUS_SCOPED` 段为实测输出：`D` 6 个旧名 + `??` 6 个新名（git add 时识别为 rename）。本分片写入的 `M` 恰好 5 个：`providers/qwen/qwen_pool_probe.py`、`providers/workbuddy/workbuddy_fetch_pricing.py`、`sync-models.ps1`、`tools/dsh_sync.py`、`tools/model_probe.py`。同一时刻 git status 里还出现 `M tools/arena_leaderboard.py`、`tools/caps_upstream.py`、`tools/model_alias.py`、`tools/model_caps.py`、`tools/model_score.py`、`tools/sync_report.py` 与 `?? tools/agent_profiles.py`，这些是主代理 / 并行只读或写入分片的同期产物，**非本分片写入**；按「当前态数字以取样时刻为准」记录，不逐个归因。

## 7. 写域边界声明（给主代理）

`tools/dsh_sync.py` 相对备份逐行 diff **恰好 6 行**，全部是任务 B 原任务书明确列明的 `zcode_effective_body.js` → `effective_body.js` 字符串同步（L11 是 docstring 内的脚本名、L60 是 `EFFECTIVE_SCRIPT` 路径、L205/218/222/227 是 warn 文案里的脚本名）。本分片**未做**叙述层改写、未动 argparse description / print 标签结构 / `_main` 结构 / `--source` 相关任何行。主代理落盘 `--source compat|dsh` 补丁时请保留这 6 行里的新名 `effective_body.js`（若 pending 片段基于旧态整篇覆盖，需把这 6 处一并带上，否则任务 B 会漏）。`sync-models.ps1` 相对备份恰好 2 行差异（L228、L253），L291 契约路径逐字未动。

## 8. 硬约束遵守

未调用 `skill`；未执行 `git add` / `commit` / `push`；未重启 `zgate` 或任何长驻进程；未写凭据明文；未改 `docs/`、`tests/`、`PROGRESS.md`、`CHANGELOG.md`、其他 `evidence/agent-*.md`、`third-party/`、`NOTICE`/`LICENSE`、`provider_config.json` 及其 `*.bak-*`；本分片唯一报告即本文件。
