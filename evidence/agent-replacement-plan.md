# replacement-plan 分片报告：ZCode 专项适配 → 面向 DSH 与各类 agent

> 一句话：采用「契约层零改动 + 实现层中性化 + DSH 主消费方 / 各类 agent 次级消费方」双层架构；逐文件 old→new、可直接运行的替换脚本、回滚与门禁清单全部给全，脚本在本分片内未执行。

---

## 0. 基线与证据口径

- **取样时刻**：2026-11-11 15:26–15:52 +08:00。本仓同时被多路并行分片改动（主代理消息 m00062 / m00075 / m00076 / m00082 确认），所有 file:line 与数字均标注该快照；主代理验收按当前磁盘复核。
- **真实项目根**：`F:\Project\ModelBus`。`git -C "F:\Project\ModelBus" rev-parse --show-toplevel` 输出 `F:/Project/ModelBus`，分支 `main`。会话工作区 `F:\Project\_merged\DeepseekHarness` 是 junction 合并视图，全程穿透真实路径。
- **独立复核数字**（Node fs 直读 UTF-8，排除 .git/node_modules/.codegraph/.work/evidence/memories/third-party/__pycache__/gateways\upstream/docs\archive/docs\release-notes/*.bak/%SystemDrive%/二进制）：活跃第一方文本 `TOTAL_TEXT_FILES=166`、含 `zcode` 的文件 `MATCHED_FILES=76`、命中总数 `TOTAL_HITS=1220`。分桶（文件数/命中数）：`docs 22/511、providers 13/152、tools 14/135、tests 6/33、gateways 9/24、PROGRESS.md 1/175、CHANGELOG.md 1/100、NOTICE 1/39、README.md 1/22`。
- 旁证（不作结论）：`tools.grep pattern "[Zz][Cc][Oo][Dd][Ee]" path F:\Project\ModelBus` → `matches_total=1900`；PowerShell `Select-String` 扫 1048 文本候选 → `TOTAL_HITS=3412`。差异来自扫描范围（后者含 .work/evidence/二进制解码），故以 166/76/1220 为方案基线。
- 换行/编码实证：`.gitattributes:6` `* text=auto eol=lf`；`.editorconfig:5-8,21-22` `charset=utf-8 / end_of_line=lf`、`[*.{bat,cmd,ps1}] end_of_line=crlf`。但工作树实测部分 `docs/*.md` 为 CRLF、`tools/*.py` 多为 LF、`sync-models.ps1` 与 `tools/zgate-lifecycle/{current-models,deploy-zgate,install-lifecycle}.ps1` 带 UTF-8 BOM。**替换脚本按「读 bytes → 保留 BOM → 逐文件保留原 EOL」实现，绝不统一 normalize。**
- CodeGraph：`codegraph_status` 在会话 cwd 报 `[!] Not initialized`，带 `projectPath=F:\Project\ModelBus` 报 `[ERR] Failed to get status: unable to open database file`；按任务书与 `~/.dsh/procedures/DeepseekHarness-工具-codegraph-索引只读.md:14-16` 零 init、零 sync，检索一律 grep / glob / read。
- 门禁脚本实存（`glob "tools/check-*.py"`）：`tools/check-docs.py`、`tools/check-secrets.py`、`tools/check-project.py`。
- `git -C "F:\Project\ModelBus" status --short`（15:45 取样）已有 20+ 个 `M`（AGENTS.md / README.md / docs/DSH-FIRST.md / tools/model_alias.py / tests/* 等）与 2 个未跟踪分片报告 → **回滚必须逐文件按备份还原，禁止 `git checkout -- .` / `git reset --hard`**。
- 主代理 16:24 消息（m00082，属 self-report，本分片未独立复核）：门面 / 方向正本 / 工具叙述层 / `tools/agent_profiles.py`（14 测试）/ 6 脚本改名 / `dsh_sync.py --source` 补丁已完成，全量 158 测试 OK、专项 10 测试 OK。本分片基线仍是 15:52 取样（当时 135 OK，见 `docs/DSH-FIRST.md:134-140`）。

---

## 1. 「DSH 面向」目标架构

### 1.1 消费方位阶

| 位阶 | 消费方 | 读什么 | 由谁写 |
|---|---|---|---|
| 主消费方 | **DSH（DeepSeekRuntime）**：会话 / 子代理 / headless / 服务插件 | `~/.dsh/profiles/<profile>/cordis.patch.yml` 的 `llm-pi-ai` 路由 + `~/.dsh/.credentials.yaml` 的 refs | `tools/dsh_sync.py --apply` |
| 次级消费方 | **各类 agent**（经 `X-Agent-Id` 分桶，缺省 `default`） | `tools/agent_profiles.py` 只读投影接口 + `gateways/zgate` 单一入口 `127.0.0.1:7871` | 只读，不写真源 |
| 兼容投影 | ZCode 桌面端（可选） | `~/.zcode/v2/provider_config.json` / `~/.zcode/v2/model-alias-map.json` | `tools/model_alias.py` + 各 provider 同步脚本 |

证据：`AGENTS.md:6`（并发后写入）「本仓以 **DSH 为主宿主**，会话 / 子代理 / headless / 服务插件等各类 agent 共用 `gateways/zgate` 单一入口」；`README.md:7-9,25-28,43-44`；`docs/DSH-FIRST.md:3,21,25,109-111`。

### 1.2 三层命名口径（沿用 `docs/DSH-FIRST.md:27-33` 与 `evidence/agent-dshfirst-naming.md:3`）

| 层 | 内容 | 处置 |
|---|---|---|
| **契约层** | `~/.zcode/v2/provider_config.json`、`~/.zcode/v2/model-alias-map.json`、`ZCODE_PERSONAL_PROVIDER_CONFIG_FILE`、`ZCODE_BUILTIN`、`ZCODE_GATEWAY_KEY`、`third-party/zcode*` / `zcodium*` 原件、ZCode schema 键（`providerConfigRules` / `modelConfigRules.providerModelRules` / `optionSpecs.reasoningLevel.{values,map}`）、`%LOCALAPPDATA%\ZCodeGateway\`、DSH 对外 route id `zcode-main/zcode-free/zcode-saver`、NOTICE/LICENSE 署名与商标段 | **一个字零改动** |
| **实现层** | 本仓自有脚本名、函数名、自造环境变量、docstring 主语、文档叙述 | 改中性名；旧名保留为读取别名 / fallback |
| **新层** | catalog（模型目录真源）、capabilities、routing policy、host projection、agent profile | 新建即用这套词 |

**决策与理由**：route id `zcode-*` 归契约层而非实现层，因为 `tools/dsh_sync.py:76-80,354,471`、`tests/test_dsh_sync_retry_policy.py:39`、`tools/model_stream_check.py:140,526` 与用户已生成的 profile patch 都按该前缀识别；改名同时破坏 DSH 侧与门禁。内部经 `adapter.route_id()` 语义映射即可，字节保持。

### 1.3 provider 命名统一约定

- DSH 对外 id 保持 `zcode-main` / `zcode-free` / `zcode-saver`（`tools/dsh_sync.py:76-80` `KNOWN_PROVIDER_IDS`）；新增走 `"zcode-" + slug`（`tools/dsh_sync.py:351-354`）。
- 源头 provider id（`opencode-go-chat` 等）属 ZCode 配置 schema，零改动。
- 内部语义名统一 `catalog source` → `route policy` → `host projection`；`_zcode_providers()` → `_source_providers()`。

### 1.4 配置路径统一约定

| 用途 | 目标态（主） | 兼容回退 | 证据 |
|---|---|---|---|
| DSH profile patch | `$DSH_HOME/profiles/$DSH_PROFILE/cordis.patch.yml`（默认 `~/.dsh/profiles/desktop/`） | 无 | `tools/dsh_sync.py:67-68,572`；`tools/model_alias.py:2016-2019` |
| DSH 凭据 | `$DSH_HOME/.credentials.yaml` 的 `refs.ZCODE_GATEWAY_KEY` | 无 | `tools/dsh_sync.py:517-531,592` |
| 投影账本 | `$DSH_HOME/profiles/$DSH_PROFILE/zcode-model-ledger.json` | 无 | `tools/dsh_sync.py:73,132,146` |
| 模型目录真源 | `$DSH_MODEL_CATALOG` 或仓库 `catalog/`（`catalog/model_caps.json` 实存） | `$MODELBUS_CATALOG` → `$ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` → `~/.zcode/v2/provider_config.json` | `tools/dsh_sync.py:61-66` |
| 兼容投影 alias map | `$UNIFIED_MODEL_MAP` | `~/.zcode/v2/model-alias-map.json` | `tools/model_alias.py:477-483`；`gateways/zgate/zgate.json:3` |

`gateways/zgate/zgate.json:3-4,73` 与 `gateways/zgate/internal/config/config.go:251,257,259,332` 是长驻网关热读契约，零改动；改 aliasMap 路径按 `AGENTS.md §6` 需换版重启，本任务禁止重启长驻网关，故排除。

### 1.5 环境变量：DSH_* 为主、ZCODE_* 兼容回退

| 新名（优先） | 旧名（fallback） | 语义 | 落点 |
|---|---|---|---|
| `DSH_HOME` / `DSH_PROFILE` | 无（已就位） | DSH 宿主根 / profile | `tools/dsh_sync.py:67-68` |
| `DSH_MODEL_CATALOG` | `MODELBUS_CATALOG` → `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` | 目录真源路径 | 6 个 `config_path()` |
| `MB_BUILTIN` | `ZCODE_BUILTIN`（契约，保留） | builtin 规则文件 | `providers/workbuddy/effective_body.js:57-60` |
| `MB_API_TYPE` / `MB_BASE_URL` / `MB_MAX_OUTPUT_TOKENS` | `ZCODE_API_TYPE` / `ZCODE_BASE_URL` / `ZCODE_MAX_OUTPUT_TOKENS` | effective body 求值参数 | `providers/workbuddy/effective_body.js:231-237` |
| `WB_PROBE_FILE` | `WB_ZCODE_PROBE_FILE` | 探测缓存路径 | `providers/workbuddy/workbuddy_probe.py:65-68`、`workbuddy_sync.py:152` |
| **零改动** | `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` / `ZCODE_BUILTIN` / `ZCODE_GATEWAY_KEY` / `UNIFIED_MODEL_MAP` / `WB_GATEWAY_KEY` / `QD_API_KEY` / `OPENCODE_GO_KEY` | 外部契约与凭据 | `AGENTS.md §2` |

形式：`process.env.MB_API_TYPE || process.env.ZCODE_API_TYPE || 'openai-chat-completions'`；`os.environ.get("DSH_MODEL_CATALOG") or os.environ.get("MODELBUS_CATALOG") or os.environ.get("ZCODE_PERSONAL_PROVIDER_CONFIG_FILE")`。**新名先读，旧名兜底，旧部署零感知**。凭据只从环境变量读，脚本与报告零写入真值。

### 1.6 脚本 / 模块命名统一约定

`<vendor>_sync.py`（写兼容投影）、`<vendor>_probe.py`（探测）、`effective_body.js`（规则求值）、`tools/dsh_sync.py`（DSH 投影器）、`tools/agent_profiles.py`（agent 只读投影）、`providers/_sink/`（写入段收敛位，`docs/DSH-FIRST.md:60-62`）。目录两轴照 `AGENTS.md §4`：会被启动 → `gateways/`；手动执行 → `providers/`；跨供应商 → `tools/`。

---

## 2. 逐文件替换方案

### 2.1 六个文件名 old→new（`evidence/agent-dshfirst-naming.md:65-79`；15:52 实测主代理已落地改名）

| # | old | new | 重命名 | 兼容别名 | 调用方更新点（file:line） |
|---|---|---|---|---|---|
| 1 | `providers/workbuddy/workbuddy_zcode_sync.py` | `providers/workbuddy/workbuddy_sync.py` | 已 | 不保留导入别名 | `sync-models.ps1:228`、`workbuddy_fetch_pricing.py:12,17,26`、`.github/ISSUE_TEMPLATE/bug_report.yml:65` |
| 2 | `providers/workbuddy/workbuddy_probe_zcode.py` | `providers/workbuddy/workbuddy_probe.py` | 已 | 不保留导入别名 | `.github/ISSUE_TEMPLATE/bug_report.yml:64`、`workbuddy_sync.py:33`、`README.md:57` |
| 3 | `providers/workbuddy/zcode_effective_body.js` | `providers/workbuddy/effective_body.js` | 已 | 不保留 | **`tools/dsh_sync.py:60,205,218,222,227`、`tools/model_probe.py:6,45`、`providers/workbuddy/workbuddy_probe.py:75,78`、`providers/qoder/qoder_probe.py:58`、自身 usage `:40-41,227`** |
| 4 | `providers/qoder/qoder_zcode_sync.py` | `providers/qoder/qoder_sync.py` | 已 | `from qoder_zcode_sync import` → `from qoder_sync import` | `sync-models.ps1:253`、`providers/qoder/qoder_probe.py:46`、`qoder_sync.py:28-32,361` |
| 5 | `providers/qoder/qoder_probe_zcode.py` | `providers/qoder/qoder_probe.py` | 已 | 不保留 | `qoder_sync.py:38,361` |
| 6 | `providers/qwen/qwen_zcode_sync.py` | `providers/qwen/qwen_sync.py` | 已 | 不保留 | `qwen_pool_probe.py:6,140` |

**关键发现（M1，阻断级，15:52 快照）**：6 个新文件名已存在，但调用方仍指旧名：`tools/dsh_sync.py:60` `EFFECTIVE_SCRIPT = REPO / "providers" / "workbuddy" / "zcode_effective_body.js"`、`tools/model_probe.py:45` 同串、`sync-models.ps1:228,253` 仍是 `workbuddy_zcode_sync.py` / `qoder_zcode_sync.py`。运行即 `FileNotFoundError` / `ModuleNotFoundError`。这是 `docs/DSH-FIRST.md:35` 点名的「改名硬回归面」，也是替换脚本第一优先级规则。主代理 16:24 报已补齐，验收仍须复核磁盘。

### 2.2 env 新名优先、旧名兜底（BLOCK 规则，逐字 old→new）

```text
# providers/workbuddy/effective_body.js:57
old: const env = process.env.ZCODE_BUILTIN;
new: const env = process.env.MB_BUILTIN || process.env.ZCODE_BUILTIN;

# :231
old: const API_TYPE = opts.apiType || process.env.ZCODE_API_TYPE || 'openai-chat-completions';
new: const API_TYPE = opts.apiType || process.env.MB_API_TYPE || process.env.ZCODE_API_TYPE || 'openai-chat-completions';

# :232
old: const BASE_URL = opts.baseUrl || process.env.ZCODE_BASE_URL || undefined;
new: const BASE_URL = opts.baseUrl || process.env.MB_BASE_URL || process.env.ZCODE_BASE_URL || undefined;

# :237
old: const MAX_TOKENS = opts.maxTokens || Number(process.env.ZCODE_MAX_OUTPUT_TOKENS) || 1024;
new: const MAX_TOKENS = opts.maxTokens || Number(process.env.MB_MAX_OUTPUT_TOKENS || process.env.ZCODE_MAX_OUTPUT_TOKENS) || 1024;

# :181-182（契约路径零改动，仅把新名前置为可选覆盖）
old: const file = process.env.ZCODE_PERSONAL_PROVIDER_CONFIG_FILE ||
new: const file = process.env.DSH_MODEL_CATALOG || process.env.MODELBUS_CATALOG ||
  process.env.ZCODE_PERSONAL_PROVIDER_CONFIG_FILE ||

# 6 个 config_path() 公共行（tools/model_alias.py:471、tools/model_probe.py:55、
# tools/sync_report.py:48、providers/qoder/qoder_sync.py:116、
# providers/qwen/qwen_sync.py:113、providers/workbuddy/workbuddy_sync.py:145）
old: env = os.environ.get("ZCODE_PERSONAL_PROVIDER_CONFIG_FILE")
new: env = (os.environ.get("DSH_MODEL_CATALOG") or os.environ.get("MODELBUS_CATALOG")
           or os.environ.get("ZCODE_PERSONAL_PROVIDER_CONFIG_FILE"))

# tools/dsh_sync.py:61-66
old: ZCODE_CONFIG = Path(
    os.environ.get(
        "ZCODE_PERSONAL_PROVIDER_CONFIG_FILE",
new: CATALOG_CONFIG = Path(
    os.environ.get("DSH_MODEL_CATALOG")
    or os.environ.get("MODELBUS_CATALOG")
    or os.environ.get(
        "ZCODE_PERSONAL_PROVIDER_CONFIG_FILE",

# providers/workbuddy/workbuddy_probe.py:65-68 / workbuddy_sync.py:152
old: Path(os.environ.get("WB_ZCODE_PROBE_FILE", CACHE_DIR / "wb_zcode_probe.json"))
new: Path(os.environ.get("WB_PROBE_FILE") or os.environ.get("WB_ZCODE_PROBE_FILE")
          or (CACHE_DIR / "wb_probe.json"))
```

旧名保留为 fallback；`ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` / `ZCODE_BUILTIN` / `ZCODE_GATEWAY_KEY` 字符串本身零删除。

### 2.3 实现层符号中性化（保留 Python 兼容别名）

```text
# tools/dsh_sync.py:152
old: def _zcode_providers(cfg: dict[str, Any]) -> list[dict[str, Any]]:
new: def _source_providers(cfg: dict[str, Any]) -> list[dict[str, Any]]:
# 函数定义结束后追加：_zcode_providers = _source_providers  # 兼容别名
# :577
old: providers = _zcode_providers(cfg)
new: providers = _source_providers(cfg)

# providers/workbuddy/workbuddy_probe.py:110
old: def zcode_body(model: str, max_tokens: int = 24) -> dict:
new: def effective_body(model: str, max_tokens: int = 24) -> dict:
# 追加：zcode_body = effective_body  # 兼容别名
# :265
old: code, resp = http_json(zcode_body(mid))
new: code, resp = http_json(effective_body(mid))
# :282 产物键 zcode_body 是输出契约，保留并新增同值 effective_body 键
```

函数签名精确值（`grep "def .*\("` 复核）：`tools/dsh_sync.py:152` `def _zcode_providers(cfg: dict[str, Any]) -> list[dict[str, Any]]:`、`:317` `def _reasoning(values: list[Any], map_expr: Any) -> dict[str, Any]:`、`:349` `def _build_route(provider: dict[str, Any], effective: dict[str, Any], rules: dict[tuple[str, str], dict[str, Any]]) -> tuple[str, dict[str, Any]]:`、`:462` `def _merge_patch(text: str, routes: dict[str, Any]) -> tuple[str, bool, dict[str, Any]]:`、`:517` `def _update_credentials_text(text: str, key: str) -> str:`、`:562` `def _main(argv: list[str] | None = None) -> int:`、`tools/model_alias.py:468,477,2008,2064` `config_path/alias_path/sync_deepseek_harness/apply_probe_filter`、`providers/workbuddy/workbuddy_probe.py:110` `def zcode_body(model: str, max_tokens: int = 24) -> dict:`。**签名、返回类型、参数顺序零变更**，仅改名 + 别名。

### 2.4 docstring / 注释 / 文档措辞（NARRATIVE 规则，只改主语，契约词零删除）

```text
tools/dsh_sync.py:2    old "Project ZCode's final model groups into DeepSeekRuntime's llm-pi-ai profile."
                       new "Project the model catalog into DSH's llm-pi-ai profile (primary host)."
tools/dsh_sync.py:4    old "The daily model sync writes ~/.zcode/v2/provider_config.json through"
                       new "The daily model sync writes the compatibility projection ~/.zcode/v2/provider_config.json through"
tools/dsh_sync.py:8-9  "every ZCode provider becomes a DSH route" → "every catalog source provider becomes a DSH route"
tools/dsh_sync.py:30   "not modify the repository or ZCode's config. DSH hot-reloads the profile patch,"
                       → "leave the repository and the compatibility projection read-only. DSH is the primary consumer; it hot-reloads the profile patch,"
tools/dsh_sync.py:125,127,161,195,245,318,432,545,563,569,595   "ZCode 配置/源头/provider" → "目录真源/兼容投影"
tools/model_alias.py:2 old "Rebuild ZCode's model list as four credit-based groups with stable aliases."
                       new "Rebuild the model catalog as credit-based groups with stable aliases; project it to DSH (primary) and the ZCode compatibility host."
tools/model_alias.py:2009-2012,2038  "just-written ZCode config / optional client" → "just-written catalog projection / DSH primary host"
tools/model_probe.py:2  old "Probe the unified four-group model list with the exact body ZCode sends."
                       new "Probe the unified catalog with the effective body the host sends (DSH primary; ZCode compatibility projection kept)."
tools/make_social_preview.py:45-46  "把模型供应商接进 ZCode 客户端的脚本与文档" → "把模型目录投影给 DSH 与各类 agent 的脚本与文档"；
                       "不改 ZCode 的代码，只写它的配置文件。" → "DSH 是主宿主；兼容投影只写配置，宿主代码零改动。"
README.md / CONTRIBUTING.md / SECURITY.md / docs/**（--include-docs 才启用）
                       "ZCode 中心" → "DSH 主宿主"；"给 ZCode 客户端写配置的脚本集" → "面向 DSH 与各类 agent 的模型目录投影"
```

**零删除**：`~/.zcode/v2/...` 全部路径字面、`ZCODE_*` 变量名、`third-party/zcode*`、ZCode schema 键、`README.md:109,121-122` 商标/鸣谢段、NOTICE 全篇。`tools/model_caps.py:18,97` 对 `third-party/zcode/model-config.ts` / `zcode-builtin.json` 的引用属第三方正本引用，零改动。

### 2.5 明确零改动清单（脚本硬排除）

`PROGRESS.md`、`CHANGELOG.md`、`memories/`、`evidence/agent-*.md`、`docs/archive/`、`docs/release-notes/`、`third-party/zcode*` 与 `third-party/zcodium*`、`LICENSE`、`NOTICE`、`provider_config.json` 与任何配置真值、`gateways/zgate/zgate.json`、`tests/**`、`.github/**`（默认）、`*.bak*`、`.work/**`、`gateways/upstream/**`、`providers/*/cache/**`、二进制与 `%SystemDrive%` 伪路径。`tests/**` 的同步改法由主代理按 2.1/2.2 执行（本分片只读分析且属共享写域）。

### 2.6 逐文件明细（file:line / old→new / 重命名 / 别名 / 调用方）

```text
tools/dsh_sync.py:60       "zcode_effective_body.js" → "effective_body.js"                       否 否 是(自身)
tools/dsh_sync.py:61-66    ZCODE_CONFIG → CATALOG_CONFIG + DSH_MODEL_CATALOG/MODELBUS_CATALOG 优先  否 旧名兜底 是(:569,:577)
tools/dsh_sync.py:73       账本名 zcode-model-ledger.json 零改动（DSH profile 内投影产物）         否 否 否
tools/dsh_sync.py:76-80    KNOWN_PROVIDER_IDS 三个 zcode-* id 零改动                             否 是(契约) 否
tools/dsh_sync.py:125,127,161,195,245,318,432,545,563,569,595  叙述主语 → 目录真源/兼容投影     否 否 否
tools/dsh_sync.py:152,577  _zcode_providers → _source_providers + 别名                           否 是 是
tools/dsh_sync.py:205,218,222,227  WARN 文案文件名                                             否 否 否
tools/dsh_sync.py:354      dsh_id = "zcode-" + slug 零改动                                      否 是(契约) 否
tools/dsh_sync.py:471      startswith("zcode-") 零改动                                          否 是(契约) 否
tools/dsh_sync.py:517-531  refs.ZCODE_GATEWAY_KEY 全段零改动                                    否 是(契约) 否
tools/model_alias.py:2,33,73,122,157,199,471-474,1960,2009-2012,2038,2080-2081,2145,2161,2213,2608  叙述/路径；config_path 按 2.2 加 DSH_* 优先  否 旧名兜底 是(:2024)
tools/model_probe.py:6,29,45-47,55-58  effective_body.js 名 + DSH_* 优先                          否 旧名兜底 是
tools/model_caps.py:7,18,51,96-98,112,147,189,216,779-791,1021-1046  仅叙述；路径与第三方引用零改动  否 否 否
tools/sync_report.py:10,34-35,48-51,60,66,406  DSH_* 优先 + 叙述                                 否 旧名兜底 否
tools/arena_leaderboard.py:18,54-56,111  User-Agent "ZCodeAIModels-arena/1.0" → "ModelBus-arena/1.0"  否 否 否
tools/model_score.py:7,28,54-55,153 / tools/caps_upstream.py:4,34,37  叙述 + DSH_* 优先            否 旧名兜底 否
tools/model_stream_check.py:140,526  startswith("zcode-") 与 "zcode-* 模型" 零改动                  否 是(契约) 否
tools/make_social_preview.py:45-46  门面文案                                                    否 否 否
sync-models.ps1:228,253    两个脚本旧名 → 新名（M1 阻断）                                        否 否 是
sync-models.ps1:291        ~/.zcode\v2\model_probe.json 契约路径零改动                             否 否 否
providers/workbuddy/workbuddy_sync.py:2,11,33,36-39,43,106,118,145-146,152,302-305,320-322,339  文件名/叙述/WB_PROBE_FILE  已 旧名兜底 是
providers/workbuddy/workbuddy_probe.py:2,9-14,30,36,44-45,67-68,75,77-78,83,86,110-111,125,150,265-282  文件名/叙述/effective_body 别名  已 是 是
providers/workbuddy/effective_body.js:3-14,36,40-46,54-99,177,181-182,227,231-237,247  usage/env/叙述；third-party 与 ZCODE_* 零删除  已 旧名兜底 是
providers/workbuddy/workbuddy_fetch_pricing.py:12,17,26  分档脚本名                                否 否 是
providers/qoder/qoder_sync.py:2,16,24,28-32,37-39,116-119,273-276,361,367  import 名/叙述/DSH_*  已 否 是(qoder_probe.py:46)
providers/qoder/qoder_probe.py:2,5,7,10,20,26-29,46,58   import + EFFECTIVE_BODY 路径              已 否 否
providers/qwen/qwen_sync.py:2,27,33-38,113-116,455 / qwen_pool_probe.py:6,140 文件名/叙述/DSH_*  已 旧名兜底 是
providers/opencode-go/ops/go_model_sync.py:10-11,15,56-59,187  叙述 + DSH_* 优先                 否 旧名兜底 否
providers/opencode-go/probe/{probe_protocols,bench_models,bench_clean,probe_models}.py  "zcode-probe/1.0"/"zcode-bench/1.0" → "modelbus-probe/1.0"/"modelbus-bench/1.0"  否 否 否
gateways/zgate/main.go:1,101,429  "ZCode 统一入口" → "DSH / 各类 agent 统一入口"；zgate.json:3-4,73 零改动  否 否 否（Go 改动需换版重启，本任务禁止 → 默认排除）
gateways/zgate/internal/{config/config.go,router/router.go,alias/alias.go,bridge/bridge.go}  仅注释叙述，路径字面零改动；默认排除
gateways/legacy-router/unified-router.js:7,62-63,193 / protocol_bridge.js:8,11  仅注释，ZCODE_* 路径零改动  否 否 否
tools/zgate-lifecycle/{current-models,deploy-zgate,install-lifecycle}.ps1  路径字面零改动（BOM+CRLF）  否 否 否
tests/**（6 文件 33 命中）  由主代理按 2.1/2.2 同步，本脚本排除
.github/ISSUE_TEMPLATE/{bug_report,feature_request}.yml  选项里的旧脚本名 → 新名；默认排除、--include-meta 启用
```

---

## 3. 可直接运行的替换脚本（正文；本分片未执行）

设计约束：显式 UTF-8；按 bytes 读取、保留 UTF-8 BOM、逐文件保留原 EOL（替换只发生在行内，行尾字节零触碰）；逐文件备份到 `.work/replacement-backups/<stamp>/`；只改白名单文件；改后统计并打印 diff 摘要；默认 dry-run；支持幂等重跑与按 stamp 回滚；零凭据读写。

```python
#!/usr/bin/env python3
"""replacement-plan: ZCode 专项适配 → DSH 主宿主 / 各类 agent（可回滚）。

用法（从仓根运行）：
    python tools/apply_dsh_first.py                 # dry-run，只打印统计与 diff 摘要
    python tools/apply_dsh_first.py --apply        # 备份 + 写白名单文件
    python tools/apply_dsh_first.py --include-docs # 连 docs 叙述一起处理
    python tools/apply_dsh_first.py --include-meta # 连 .github 模板一起处理
    python tools/apply_dsh_first.py --rollback <stamp>

约定：读 bytes → 保留 BOM → 原 EOL 原样回写；白名单外文件一律跳过；
历史/第三方/配置/tests/evidence/.work 硬排除；凭据零读写。
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path.cwd()
BACKUP_ROOT = ROOT / ".work" / "replacement-backups"

CODE_WHITELIST = {
    "tools/dsh_sync.py", "tools/model_alias.py", "tools/model_probe.py",
    "tools/model_caps.py", "tools/caps_upstream.py", "tools/model_score.py",
    "tools/arena_leaderboard.py", "tools/sync_report.py",
    "tools/model_stream_check.py", "tools/make_social_preview.py",
    "sync-models.ps1",
    "providers/workbuddy/workbuddy_sync.py", "providers/workbuddy/workbuddy_probe.py",
    "providers/workbuddy/effective_body.js", "providers/workbuddy/workbuddy_fetch_pricing.py",
    "providers/qoder/qoder_sync.py", "providers/qoder/qoder_probe.py",
    "providers/qwen/qwen_sync.py", "providers/qwen/qwen_pool_probe.py",
    "providers/opencode-go/ops/go_model_sync.py",
    "providers/opencode-go/probe/probe_protocols.py",
    "providers/opencode-go/probe/bench_models.py",
    "providers/opencode-go/probe/bench_clean.py",
    "providers/opencode-go/probe/probe_models.py",
}
# 旧名仍在磁盘时（并发改名未落地）也纳入，保证脚本可独立跑在任何快照上
CODE_WHITELIST |= {
    "providers/workbuddy/workbuddy_zcode_sync.py",
    "providers/workbuddy/workbuddy_probe_zcode.py",
    "providers/workbuddy/zcode_effective_body.js",
    "providers/qoder/qoder_zcode_sync.py", "providers/qoder/qoder_probe_zcode.py",
    "providers/qwen/qwen_zcode_sync.py",
}
DOC_WHITELIST = {"README.md", "AGENTS.md", "CONTRIBUTING.md", "SECURITY.md"}
META_WHITELIST = {
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
}
EXCLUDE_PREFIX = (
    "PROGRESS.md", "CHANGELOG.md", "NOTICE", "LICENSE",
    "memories/", "evidence/", ".work/", "third-party/", "tests/",
    "docs/archive/", "docs/release-notes/", "gateways/upstream/",
    "gateways/zgate/",          # 改 Go 需换版重启；本任务禁止
    ".git/", "node_modules/", "__pycache__/",
)
EXCLUDE_SUFFIX = (".bak", ".tmp", ".png", ".jpg", ".ico", ".pdf", ".exe")

# (id, old, new, scopes)  scopes ∈ {"code","doc","meta"}
LITERAL = [
    ("R1-effective-js", "zcode_effective_body.js", "effective_body.js", {"code"}),
    ("R1-wb-sync", "workbuddy_zcode_sync.py", "workbuddy_sync.py", {"code", "meta"}),
    ("R1-wb-probe", "workbuddy_probe_zcode.py", "workbuddy_probe.py", {"code", "meta"}),
    ("R1-qd-sync", "qoder_zcode_sync.py", "qoder_sync.py", {"code"}),
    ("R1-qd-probe", "qoder_probe_zcode.py", "qoder_probe.py", {"code"}),
    ("R1-qw-sync", "qwen_zcode_sync.py", "qwen_sync.py", {"code"}),
    ("R2-wb-cache", "wb_zcode_probe.json", "wb_probe.json", {"code"}),
    ("R2-ua-probe", '"zcode-probe/1.0"', '"modelbus-probe/1.0"', {"code"}),
    ("R2-ua-bench", '"zcode-bench/1.0"', '"modelbus-bench/1.0"', {"code"}),
    ("R2-ua-arena", '"ZCodeAIModels-arena/1.0"', '"ModelBus-arena/1.0"', {"code"}),
    ("R3-dsh-sync-doc", "Project ZCode's final model groups into DeepSeekRuntime's llm-pi-ai profile.",
     "Project the model catalog into DSH's llm-pi-ai profile (primary host).", {"code"}),
    ("R3-alias-doc", "Rebuild ZCode's model list as four credit-based groups with stable aliases.",
     "Rebuild the model catalog as credit-based groups with stable aliases; project it to DSH (primary) and the ZCode compatibility host.", {"code"}),
    ("R3-probe-doc", "Probe the unified four-group model list with the exact body ZCode sends.",
     "Probe the unified catalog with the effective body the host sends (DSH primary; ZCode compatibility projection kept).", {"code"}),
    ("R3-preview-1", "把模型供应商接进 ZCode 客户端的脚本与文档",
     "把模型目录投影给 DSH 与各类 agent 的脚本与文档", {"code"}),
    ("R3-preview-2", "不改 ZCode 的代码，只写它的配置文件。",
     "DSH 是主宿主；兼容投影只写配置，宿主代码零改动。", {"code"}),
    ("R3-dsh-sync-fn", "def _zcode_providers(cfg: dict[str, Any]) -> list[dict[str, Any]]:",
     "def _source_providers(cfg: dict[str, Any]) -> list[dict[str, Any]]:", {"code"}),
    ("R3-dsh-sync-call", "providers = _zcode_providers(cfg)",
     "providers = _source_providers(cfg)", {"code"}),
    ("R3-probe-fn", "def zcode_body(model: str, max_tokens: int = 24) -> dict:",
     "def effective_body(model: str, max_tokens: int = 24) -> dict:", {"code"}),
    ("R3-probe-call", "code, resp = http_json(zcode_body(mid))",
     "code, resp = http_json(effective_body(mid))", {"code"}),
    ("R4-narrative", "ZCode 中心", "DSH 主宿主", {"code", "doc"}),
    ("R4-narrative2", "给 ZCode 客户端写配置的脚本集",
     "面向 DSH 与各类 agent 的模型目录投影", {"doc"}),
    ("R4-main-go", "ZCode 统一入口", "DSH / 各类 agent 统一入口", {"code"}),
]
BLOCK = [
    ("E1-js-builtin",
     "const env = process.env.ZCODE_BUILTIN;",
     "const env = process.env.MB_BUILTIN || process.env.ZCODE_BUILTIN;", {"code"}),
    ("E2-js-api",
     "const API_TYPE = opts.apiType || process.env.ZCODE_API_TYPE || 'openai-chat-completions';",
     "const API_TYPE = opts.apiType || process.env.MB_API_TYPE || process.env.ZCODE_API_TYPE || 'openai-chat-completions';", {"code"}),
    ("E3-js-base",
     "const BASE_URL = opts.baseUrl || process.env.ZCODE_BASE_URL || undefined;",
     "const BASE_URL = opts.baseUrl || process.env.MB_BASE_URL || process.env.ZCODE_BASE_URL || undefined;", {"code"}),
    ("E4-js-tokens",
     "const MAX_TOKENS = opts.maxTokens || Number(process.env.ZCODE_MAX_OUTPUT_TOKENS) || 1024;",
     "const MAX_TOKENS = opts.maxTokens || Number(process.env.MB_MAX_OUTPUT_TOKENS || process.env.ZCODE_MAX_OUTPUT_TOKENS) || 1024;", {"code"}),
    ("E5-js-config",
     "const file = process.env.ZCODE_PERSONAL_PROVIDER_CONFIG_FILE ||\n    path.join(os.homedir(), '.zcode', 'v2', 'provider_config.json');",
     "const file = process.env.DSH_MODEL_CATALOG || process.env.MODELBUS_CATALOG ||\n    process.env.ZCODE_PERSONAL_PROVIDER_CONFIG_FILE ||\n    path.join(os.homedir(), '.zcode', 'v2', 'provider_config.json');", {"code"}),
    ("E6-py-config",
     'env = os.environ.get("ZCODE_PERSONAL_PROVIDER_CONFIG_FILE")',
     'env = (os.environ.get("DSH_MODEL_CATALOG") or os.environ.get("MODELBUS_CATALOG")\n           or os.environ.get("ZCODE_PERSONAL_PROVIDER_CONFIG_FILE"))', {"code"}),
    ("E7-dsh-config",
     'ZCODE_CONFIG = Path(\n    os.environ.get(\n        "ZCODE_PERSONAL_PROVIDER_CONFIG_FILE",',
     'CATALOG_CONFIG = Path(\n    os.environ.get("DSH_MODEL_CATALOG")\n    or os.environ.get("MODELBUS_CATALOG")\n    or os.environ.get(\n        "ZCODE_PERSONAL_PROVIDER_CONFIG_FILE",', {"code"}),
    ("E8-wb-probe",
     'Path(os.environ.get("WB_ZCODE_PROBE_FILE", CACHE_DIR / "wb_zcode_probe.json"))',
     'Path(os.environ.get("WB_PROBE_FILE") or os.environ.get("WB_ZCODE_PROBE_FILE")\n          or (CACHE_DIR / "wb_probe.json"))', {"code"}),
]
# 兼容别名：anchor 行之后插入（保持旧符号可导入）
ALIASES = [
    ("tools/dsh_sync.py", "def _source_providers(cfg: dict[str, Any]) -> list[dict[str, Any]]:",
     "_zcode_providers = _source_providers  # 兼容别名，旧调用方零感知"),
    ("providers/workbuddy/workbuddy_probe.py", "def effective_body(model: str, max_tokens: int = 24) -> dict:",
     "zcode_body = effective_body  # 兼容别名"),
    ("providers/workbuddy/workbuddy_probe_zcode.py", "def effective_body(model: str, max_tokens: int = 24) -> dict:",
     "zcode_body = effective_body  # 兼容别名"),
]


def eol_of(text: str) -> str:
    i = text.find("\n")
    return "\r\n" if i > 0 and text[i - 1] == "\r" else "\n"


def is_excluded(rel: str) -> bool:
    r = rel.replace("\\", "/")
    return r.startswith(EXCLUDE_PREFIX) or r.endswith(EXCLUDE_SUFFIX)


def load_rules(scopes: set[str]):
    return [(rid, old, new) for rid, old, new, sc in LITERAL + BLOCK if sc & scopes]


def apply_text(rel: str, text: str, rules, aliases):
    total, detail = 0, []
    for rid, old, new in rules:
        n = text.count(old)
        if n:
            text = text.replace(old, new)
            total += n
            detail.append({"rule": rid, "count": n})
    key = rel.replace("\\", "/")
    for arel, anchor, alias_line in aliases:
        if key != arel or alias_line in text:
            continue
        if anchor in text:
            eol = eol_of(text)
            text = text.replace(anchor, anchor + eol + alias_line, 1)
            total += 1
            detail.append({"rule": "ALIAS:" + arel, "count": 1})
    return text, total, detail


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="DSH-first replacement (reversible)")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--include-docs", action="store_true")
    ap.add_argument("--include-meta", action="store_true")
    ap.add_argument("--go", action="store_true", help="连 gateways/zgate Go 注释一起改（需换版重启）")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--rollback", metavar="STAMP")
    ap.add_argument("--max-diff-lines", type=int, default=40)
    args = ap.parse_args(argv)

    global ROOT, BACKUP_ROOT
    ROOT = Path(args.root).resolve()
    BACKUP_ROOT = ROOT / ".work" / "replacement-backups"

    if args.rollback:
        src = BACKUP_ROOT / args.rollback
        manifest = src / "manifest.json"
        if not manifest.exists():
            print("ERROR: 备份不存在: " + str(manifest), file=sys.stderr)
            return 2
        entries = json.loads(manifest.read_text(encoding="utf-8"))["files"]
        for item in entries:
            dst = ROOT / item["rel"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src / item["rel"], dst)
            print("RESTORED " + item["rel"])
        print("ROLLBACK_OK files=%d stamp=%s" % (len(entries), args.rollback))
        return 0

    scopes = {"code"}
    if args.include_docs:
        scopes.add("doc")
    if args.include_meta:
        scopes.add("meta")
    whitelist = set(CODE_WHITELIST)
    if args.include_docs:
        whitelist |= DOC_WHITELIST
    if args.include_meta:
        whitelist |= META_WHITELIST
    if args.go:
        whitelist |= {
            "gateways/zgate/main.go", "gateways/zgate/internal/router/router.go",
            "gateways/zgate/internal/alias/alias.go", "gateways/zgate/internal/bridge/bridge.go",
        }
    rules = load_rules(scopes)

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = BACKUP_ROOT / stamp
    changed, skipped, manifest_files, grand = [], [], [], 0

    for rel in sorted(whitelist):
        if is_excluded(rel) and not (args.go and rel.startswith("gateways/zgate/")):
            skipped.append(rel + " (excluded)")
            continue
        p = ROOT / rel
        if not p.exists():
            skipped.append(rel + " (missing)")
            continue
        raw = p.read_bytes()
        bom = raw.startswith(b"\xef\xbb\xbf")
        body = raw[3:] if bom else raw
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError as exc:
            skipped.append(rel + " (decode: %s)" % exc)
            continue
        new_text, n, detail = apply_text(rel, text, rules, ALIASES)
        if n == 0 or new_text == text:
            skipped.append(rel + " (no-change)")
            continue
        out = (b"\xef\xbb\xbf" if bom else b"") + new_text.encode("utf-8")
        diff = list(difflib.unified_diff(
            text.splitlines(keepends=True), new_text.splitlines(keepends=True),
            fromfile="a/" + rel, tofile="b/" + rel, n=1))
        eol = eol_of(text)
        manifest_files.append({
            "rel": rel, "sha256_before": hashlib.sha256(raw).hexdigest(),
            "sha256_after": hashlib.sha256(out).hexdigest(),
            "bytes_before": len(raw), "bytes_after": len(out),
            "eol": "CRLF" if eol == "\r\n" else "LF", "bom": bom,
            "replacements": n, "detail": detail,
        })
        if args.apply:
            (backup / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, backup / rel)
            p.write_bytes(out)
        changed.append((rel, n, len(diff)))
        grand += n
        print("CHANGED %-62s replacements=%-3d diff_lines=%d eol=%s bom=%s" %
              (rel, n, len(diff), "CRLF" if eol == "\r\n" else "LF", bom))
        for line in diff[: args.max_diff_lines]:
            print("   " + line.rstrip("\r\n"))
        if len(diff) > args.max_diff_lines:
            print("   ... (%d more diff lines)" % (len(diff) - args.max_diff_lines))

    if args.apply and manifest_files:
        (backup / "manifest.json").write_text(
            json.dumps({"stamp": stamp, "scopes": sorted(scopes), "files": manifest_files},
                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("BACKUP  " + str(backup))
        print("MANIFEST " + str(backup / "manifest.json"))

    residual = {}
    for rel, _, _ in changed:
        q = ROOT / rel
        if q.exists():
            t = q.read_bytes().decode("utf-8-sig", errors="replace")
            residual[rel] = sum(1 for ln in t.splitlines() if "zcode" in ln.lower())
    print("\n=== SUMMARY mode=%s scopes=%s ===" % ("APPLY" if args.apply else "DRY-RUN", ",".join(sorted(scopes))))
    print("WHITELIST=%d CHANGED=%d SKIPPED=%d REPLACEMENTS=%d" %
          (len(whitelist), len(changed), len(skipped), grand))
    print("PER_RULE=" + json.dumps(
        {d["rule"]: d["count"] for f in manifest_files for d in f["detail"]},
        ensure_ascii=False))
    print("RESIDUAL_zcode_lines_after=" + json.dumps(residual, ensure_ascii=False))
    for s in skipped[:15]:
        print("SKIP " + s)
    if len(skipped) > 15:
        print("SKIP ... (%d more)" % (len(skipped) - 15))
    if not args.apply:
        print("DRY-RUN: 磁盘零变更；确认后加 --apply。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**脚本语义保证**：`text.replace` 只作用于行内字面，CRLF / LF 字节原样回写；BOM 以 `b"\xef\xbb\xbf"` 显式重建；E6/E7/E8 的 old 串在多个文件重复出现，`replace` 天然全量生效；old 不存在即计入 `no-change`，重复执行幂等；`--rollback` 只还原 manifest 里记录的原始 bytes，零触碰其他文件。

---

## 4. 回滚方案

### 4.1 备份位置

| 来源 | 路径（真实项目内） | 内容 |
|---|---|---|
| 本脚本（设计） | `F:\Project\ModelBus\.work\replacement-backups\<UTC stamp>\` | 逐文件原始 bytes + `manifest.json`（sha256_before/after、bytes、eol、bom、逐规则条数） |
| 并行分片实存（主代理 m00082 口径，self-report 未独立复核） | `.work/dsh-first-20261111` | 门面 / 方向正本批次备份 |
| 同上 | `.work/dsh-rename-20261111` | 6 脚本改名批次备份 |
| 同上 | `.work/dsh-source-20261111` | `dsh_sync.py --source` 补丁批次备份 |
| 同上 | `.work/dsh-tools-20261111` | 第一方工具叙述层批次备份 |
| 同上 | `.work/dsh-providers-20261111` | providers/ 叙述层批次备份（主代理 m00088 口径） |

`.work/` 已被 `.gitignore` 与 `tools/check-docs.py:25-27` 排除，零入库。五个并行备份目录与本脚本备份目录互不覆盖；回滚时按批次反序还原（providers → tools → source → rename → first），每步之间跑一次门禁。

### 4.2 首选回滚（精确、无副作用）

```powershell
python -B tools\apply_dsh_first.py --rollback 20261111T080000Z
Get-ChildItem -LiteralPath "F:\Project\ModelBus\.work" -Directory | Where-Object Name -Like "dsh-*-20261111" | Select-Object FullName
```

脚本按 manifest 逐文件 `shutil.copyfile` 还原，输出 `RESTORED <rel>` 与 `ROLLBACK_OK files=N stamp=...`。并行批次的备份目录用同目录内 `*.bak-*` / 原始副本按 `Copy-Item -LiteralPath` 逐文件还原，还原前先 `Get-ChildItem -Recurse` 列出清单核对目标绝对路径（禁止对 junction 用 Remove-Item -Recurse）。

### 4.3 git checkout 口径（受限使用）

仅对「替换前在 `git status --short` 中为干净、且本次只被本脚本改动」的单个文件可用：

```powershell
git -C "F:\Project\ModelBus" status --short -- tools\dsh_sync.py
git -C "F:\Project\ModelBus" checkout -- tools\dsh_sync.py
```

**硬禁止** `git checkout -- .`、`git reset --hard`、`git clean -fd`：15:45 取样工作树已有 20+ 并行分片改动，全量回滚会毁掉他人成果（`AGENTS.md §1` 的并发写坏教训）。零 `git add/commit/push`。

### 4.4 行为等价验证（回滚后）

- 字节级：`Get-FileHash -Algorithm SHA256 <rel>` 与 `manifest.json` 的 `sha256_before` 逐项比对，要求 100% 相等；EOL/BOM 与 manifest 一致。
- 行为级：`python -B tools/dsh_sync.py --check` 与 `python -B -m unittest discover -s tests -q` 的退出码与输出同基线（§5.4 的 B1–B12）。
- 零重启：全程 `POST /admin/reload` 与计划任务父链零触碰；`zgate` 二进制与 `zgate.json` 零变更（`AGENTS.md §6`）。

---

## 5. 验证清单

### 5.1 语法检查（按文件类型，全部用真实可执行文件）

```powershell
$env:PYTHONIOENCODING = "utf-8"
python -B -m py_compile tools\dsh_sync.py tools\model_alias.py tools\model_probe.py tools\sync_report.py tools\model_caps.py tools\caps_upstream.py tools\model_score.py tools\arena_leaderboard.py tools\model_stream_check.py tools\make_social_preview.py providers\workbuddy\workbuddy_sync.py providers\workbuddy\workbuddy_probe.py providers\workbuddy\workbuddy_fetch_pricing.py providers\qoder\qoder_sync.py providers\qoder\qoder_probe.py providers\qwen\qwen_sync.py providers\qwen\qwen_pool_probe.py providers\opencode-go\ops\go_model_sync.py providers\opencode-go\probe\probe_protocols.py providers\opencode-go\probe\bench_models.py providers\opencode-go\probe\bench_clean.py providers\opencode-go\probe\probe_models.py tools\apply_dsh_first.py

# Node 必须用真实 node.exe（process.execPath 在 Electron 宿主下会报 Chromium disk_cache ERROR）
$NODE_EXE = (Get-Command node.exe).Source
& $NODE_EXE --check providers\workbuddy\effective_body.js
& $NODE_EXE --check gateways\legacy-router\unified-router.js
& $NODE_EXE --check gateways\legacy-router\protocol_bridge.js

# PowerShell 解析检查（PS1 带 BOM/CRLF，解析器按原样读）
[System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path sync-models.ps1), [ref]$null, [ref]$null) | Out-Null

# Go：本方案默认零改 Go；若主代理启用 --go，则在 gateways\zgate 下跑
$GO_EXE = (Get-Command go.exe).Source
Push-Location "F:\Project\ModelBus\gateways\zgate"; & $GO_EXE vet ./...; & $GO_EXE build ./...; Pop-Location
```

依据 `~/.dsh/skills/windows-spawn-toolchain-invocation/references/recipes.md:11-15,53-55,67-87,96-102`：Python 需 `PYTHONIOENCODING=utf-8` 与 `encoding:"utf8"` 成对；Node 需 `(Get-Command node.exe).Source`；Go 钩子 PATH 首位放 Go bin；git 命令一律 `-C` 指真实仓。

### 5.2 三道门禁命令与退出码（逐条贴 exit code）

```powershell
python -B tools\check-docs.py    ; "check-docs exit=$LASTEXITCODE"
python -B tools\check-secrets.py ; "check-secrets exit=$LASTEXITCODE"
python -B tools\check-project.py ; "check-project exit=$LASTEXITCODE"
python -B -m unittest discover -s tests -q ; "unittest exit=$LASTEXITCODE"
python -B tools\dsh_sync.py --check ; "dsh_sync --check exit=$LASTEXITCODE"
python -B tools\model_alias.py --check ; "model_alias --check exit=$LASTEXITCODE"
```

| 门禁 | 通过 | 失败 | 依据 |
|---|---|---|---|
| `tools/check-docs.py` | `exit=0` | `exit=1`（相对链接 / 锚点 / 一句话引言 / 孤儿文档） | `tools/check-docs.py:4-12,159-169` |
| `tools/check-secrets.py` | `exit=0` | `exit=1` 发现疑似敏感信息；`exit=2` 自身故障（git 不可用） | `tools/check-secrets.py:8-17` |
| `tools/check-project.py` | `exit=0` | `exit=1`（zgate.json 语义 / 换行 BOM / PS1 语法 / 流式准入接线） | `tools/check-project.py:2-18` |

补充细分命令：`python -B tools/check-project.py --lineendings`、`--ps1`、`--stream-contract`、`python -B tools/check-docs.py docs\`（仅当启用 `--include-docs`）。测试基线：本分片取样时 135 OK（`docs/DSH-FIRST.md:134-140`），主代理 16:24 报 158 OK + 专项 10 OK（self-report，验收须复跑）。**门禁绿 ≠ 命名零残留**，必须叠加 5.3。

### 5.3 替换后 grep 残留复核（分「应保留」与「应清零」两组）

```powershell
# A. 应清零：实现层旧文件名 / 旧自造 env（期望 0 命中）
git -C "F:\Project\ModelBus" grep -n -E "zcode_effective_body|_zcode_sync|_probe_zcode|workbuddy_zcode|qoder_zcode|qwen_zcode|WB_ZCODE_PROBE_FILE|ZCode 中心|zcode-probe/1.0|zcode-bench/1.0" -- ':!PROGRESS.md' ':!CHANGELOG.md' ':!evidence' ':!memories' ':!third-party' ':!.work' ':!tests' ':!docs/archive' ':!docs/release-notes'

# B. 应保留：契约层（命中数 > 0 且逐条人工确认，零删除）
git -C "F:\Project\ModelBus" grep -n -F "~/.zcode/v2/provider_config.json"
git -C "F:\Project\ModelBus" grep -n -F "~/.zcode/v2/model-alias-map.json"
git -C "F:\Project\ModelBus" grep -n -E "ZCODE_PERSONAL_PROVIDER_CONFIG_FILE|ZCODE_BUILTIN|ZCODE_GATEWAY_KEY"
git -C "F:\Project\ModelBus" grep -n -F "third-party/zcode"
git -C "F:\Project\ModelBus" grep -n -E "zcode-main|zcode-free|zcode-saver"
git -C "F:\Project\ModelBus" grep -n -F "ZCodeGateway"

# C. 新名生效：新名与 fallback 同时存在
git -C "F:\Project\ModelBus" grep -n -E "DSH_MODEL_CATALOG|MB_API_TYPE|MB_BASE_URL|WB_PROBE_FILE|effective_body.js|agent_profiles.py"

# D. 数字复核（与基线 166/76/1220 对照，口径见 §0）
python -B -c "import pathlib,re; root=pathlib.Path('.'); skip={'.git','node_modules','.codegraph','.work','evidence','memories','third-party','__pycache__'}; fs=[p for p in root.rglob('*') if p.is_file() and not any(s in p.parts for s in skip) and 'gateways/upstream' not in p.as_posix() and 'docs/archive' not in p.as_posix() and 'docs/release-notes' not in p.as_posix() and '.bak' not in p.name]; hits=[(p,len(re.findall('zcode',p.read_text(encoding='utf-8',errors='replace'),re.I))) for p in fs]; print('TOTAL_TEXT_FILES=%d MATCHED_FILES=%d TOTAL_HITS=%d'%(len(fs),sum(1 for _,n in hits if n),sum(n for _,n in hits)))"
```

### 5.4 关键函数行为对比（输入/输出样例，替换前后必须逐项相等）

| # | 函数 / 命令 | 输入样例 | 期望输出（保持不变） | 证据 |
|---|---|---|---|---|
| B1 | `tools/model_alias.py:468 config_path(None)` | 三 env 全空 | `Path.home()/".zcode"/"v2"/"provider_config.json"` | `:468-474` |
| B2 | 同上 | `DSH_MODEL_CATALOG=/tmp/a.json` 且 `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE=/tmp/b.json` | `/tmp/a.json`（新名优先） | 2.2 E6 |
| B3 | 同上 | 仅 `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE=/tmp/b.json` | `/tmp/b.json`（旧名兜底） | 2.2 E6 |
| B4 | `tools/dsh_sync.py:317 _reasoning(values, map_expr)` | `["off","minimal","high"], {}` | 不含 `reasoningEfforts` 键（空 map 退化保护） | `:12-14,432` |
| B5 | 同上 | `["disabled","low","high"], {"low":"reasoning_effort"}` | efforts 含 minimal/medium 映射且 `_USES_EFFORT_FIELD` 命中 | `:74,317-343` |
| B6 | `tools/dsh_sync.py:349 _build_route(...)` | `providerId="opencode-go-chat"` | `dsh_id == "zcode-main"` 且 route 含 `apiKeyEnv="ZCODE_GATEWAY_KEY"`、`baseURL`、`RETRY_POLICY` | `:76-80,349-381` |
| B7 | `tools/dsh_sync.py:462 _merge_patch(text, routes)` | 含 `custom-keep` provider 的旧 patch + 3 个 `zcode-*` routes | `custom-keep` 原样保留；仅 `zcode-*` 段重建 | `:471`；`tests/test_dsh_sync_retry_policy.py:101,211` |
| B8 | `tools/dsh_sync.py:517 _update_credentials_text` | 已有 `refs:` 且带注释的 patch | 只改 `ZCODE_GATEWAY_KEY` 行，注释与其它 refs 保持 | `:518-531` |
| B9 | `providers/workbuddy/effective_body.js` | `node effective_body.js --api-type openai-chat-completions DeepSeek-4.1-Flash` | 输出 JSON 与旧脚本逐字节一致（body/values/level 契约键） | `:36,231-237` |
| B10 | `workbuddy_probe.py effective_body("X")` / 别名 `zcode_body("X")` | 同一 model id | 两个返回值相等；产物同时含 `zcode_body` 与 `effective_body` 键 | `:110,265,282` |
| B11 | `python -B tools/dsh_sync.py --check`（同一 `--config` fixture） | 替换前 / 替换后各跑一次 | stdout 逐行 diff 为空、exit code 相同 | `:562-595` |
| B12 | `python -B -m unittest discover -s tests -q` | 全量 | 基线 135 OK / 主代理报 158 OK，exit 0 | `docs/DSH-FIRST.md:134-140` |

行为等价证明口径（`~/.dsh/AGENTS.md §6`）：B1–B12 全绿 + `manifest.json` 的 `bytes_before/after` 可解释每一行差异，才算证出等价；证不出即按 §4.2 回滚。

---

## 6. C1–C5 / M1 缺陷与修复优先级建议

| 优先级 | 编号 | 缺陷（15:52 取样实测） | 修复动作 | 证据 |
|---|---|---|---|---|
| **P0 阻断** | **M1** | 6 个脚本已改名，调用方仍引旧名：`tools/dsh_sync.py:60` / `tools/model_probe.py:45` / `sync-models.ps1:228,253` / `providers/qoder/qoder_probe.py:46,58` | 跑替换脚本 R1 六条（dry-run 后 `--apply`），立即 `py_compile` + `dsh_sync.py --check` | `docs/DSH-FIRST.md:35` |
| P1 | C3 | `DSH_MODEL_CATALOG` 原生真源开关在 15:52 尚未落地，`tools/dsh_sync.py:61-66` 仍单一 `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` 入口（主代理 16:24 报已补 `--source`） | E6/E7 规则；合并时以「新名优先、旧名兜底」为唯一口径，避免双写 | `README.md:9,25` |
| P1 | C2 | 自造 env 旧名未中性化：`effective_body.js:231-237` 的 ZCODE_API_TYPE/BASE_URL/MAX_OUTPUT_TOKENS、`WB_ZCODE_PROBE_FILE`，与 `docs/DSH-FIRST.md:32` 声称的 `MB_*` / `WB_PROBE_FILE` 不一致 | E1–E5、E8；旧名保留 fallback | `docs/DSH-FIRST.md:32` |
| P2 | C5 | 旁支引用旧文件名：`.github/ISSUE_TEMPLATE/bug_report.yml:64-65`、`workbuddy_fetch_pricing.py:12,17,26`、`qwen_pool_probe.py:6,140`、`qoder_sync.py:361` —— 门禁不查，用户复制即失败 | R1 + `--include-meta` | `tools/check-docs.py:4-12` |
| P3 | C1 | `effective_body.js:40-41,227` usage / 注释仍写 `node zcode_effective_body.js` | R1 字面替换（自身文件也在白名单） | `:40-41,227` |
| P3 | C4 | docstring 主语仍是 ZCode：`tools/dsh_sync.py:2,4,8-21,30`、`tools/model_alias.py:2`、`tools/model_probe.py:2` | R3/R4 叙述规则；`--include-docs` 时连 README/CONTRIBUTING 一起 | `README.md:7-9` 已改，正文待对齐 |

**修复顺序**：M1 → C3/C2（同批，env 语义闭合）→ C5 → C1 → C4；每批之间跑 §5.2 三道门禁 + §5.3 A 组零命中。`gateways/zgate/**` 注释（C4 的一部分）默认排除，因其改动按 `AGENTS.md §6` 需换版重启，本任务禁止重启长驻网关。

---

## 7. 完成判据核对表

| # | 判据（任务书 / 主代理催办） | 落点 | 状态 |
|---|---|---|---|
| 1 | ①「DSH 面向」目标架构：DSH 主消费方、各类 agent 次级消费方，provider 命名 / 配置路径 `~/.dsh/...` / 环境变量 `DSH_*` 主 `ZCODE_*` 回退 / 脚本命名统一约定 | §1.1–§1.6 | ✅ |
| 2 | ②逐文件替换方案（file:line、old→new、重命名、兼容别名、调用方） | §2.1–§2.6 | ✅ |
| 3 | ③可直接运行的 Python 替换脚本正文（显式 UTF-8、保留 CRLF/EOL 与 BOM、逐文件备份 .work/、只改白名单、改后统计与 diff 摘要），**未执行** | §3 | ✅ 未执行 |
| 4 | ④回滚方案（备份位置、git checkout 口径、行为等价验证） | §4.1–§4.4 | ✅ |
| 5 | ⑤验证清单（py_compile / node --check / go vet、check-docs.py / check-secrets.py / check-project.py、残留 grep、B1–B12 行为样例） | §5.1–§5.4 | ✅ |
| 6 | 目标架构三层口径（契约层零改动 / 实现层中性化 / 新层） | §1.2 | ✅ |
| 7 | 6 个 old→new 映射 | §2.1 表 | ✅ |
| 8 | env 新名优先旧名兜底 | §1.5 / §2.2 / §3 E1–E8 | ✅ |
| 9 | 回滚步骤（.work 备份位置：`replacement-backups/<stamp>` + `dsh-first-20261111 / dsh-rename-20261111 / dsh-source-20261111 / dsh-tools-20261111 / dsh-providers-20261111`） | §4.1–§4.3 | ✅ |
| 10 | 全量门禁验证清单（三道门禁命令 + 退出码 0/1/2） | §5.2 | ✅ |
| 11 | C1–C5 / M1 缺陷修复优先级建议 | §6 | ✅ |
| 12 | 所有结论附 file:line 与可独立复现命令/数字；数字标注取样时刻 | §0 + 全篇 | ✅ |
| 13 | 历史记录（CHANGELOG/PROGRESS/memories/evidence/agent-*）、third-party/zcode*、LICENSE/NOTICE/第三方署名零改动 | §2.5 / §3 EXCLUDE | ✅ |
| 14 | `PROGRESS.md` / docs/ / tests/ / `provider_config.json` / 配置零改动；零 git add/commit/push；零重启 zgate；凭据零写入 | 本分片只读分析，唯一写域为本报告 | ✅ |
| 15 | 报告落在 `F:\Project\ModelBus\evidence\agent-replacement-plan.md` | 本文件 | ✅ |
| 16 | `send_message` 报回父代理 `session-90f67405-5d4e-4707-b280-3eba9af5856a`（路径/字节/行数 + 关键结论），并 release_files | 落盘后执行 | ✅ |
