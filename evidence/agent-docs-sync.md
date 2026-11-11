# docs 口径改写同步报告（docs-sync 分片）

> **一句话**：把 docs/ 顶层 22 篇活文档从「ZCode 中心」叙述改成「DSH 主宿主 + 各类 agent / ZCode 为兼容投影」口径，同步 6 个已改名脚本的旧名路径，按 docs/DSH-FIRST.md §7 清单清掉过期口径，并完成主代理追加的 11 处精确窄替换；三道门禁两轮全绿。

## 0. 范围与边界

- **唯一写域**：`F:\Project\ModelBus\docs\` 顶层除 `DSH-FIRST.md` / `README.md` 外的活文档 `.md`（22 篇），以及本报告 `F:\Project\ModelBus\evidence\agent-docs-sync.md`。
- **禁区（未碰）**：`docs/DSH-FIRST.md`、`docs/README.md`（主代理独占）、`docs/archive/`、`docs/split/`、`docs/release-notes/`、`docs/reports/`（历史冻结）、根 `PROGRESS.md` / `CHANGELOG.md` / `AGENTS.md`、任何 `.py .ps1 .go .js .json`、`catalog/`、`tests/`、配置、凭据；无 git 操作、无 zgate 重启、无 skill 加载。
- **备份**：批 1 改前把 22 篇逐篇 `copyFile` 到 `F:\Project\ModelBus\.work\dsh-docs-20261111\<原名>`；批 2（主代理追加）改前再把 7 篇备份到 `F:\Project\ModelBus\.work\dsh-docs-20261111\pass2\<原名>`。台账/统计原料 `ledger-final.json`、`residue.json` 同目录。
- **编辑方法**：`fs.readFile` 原文 → `split(/(\r\n|\n)/)` 保留每行 EOL/BOM → 逐行唯一命中 `split/join` 替换 → 按原 EOL 拼回 → `fs.writeFile(Buffer.from(out,'utf8'))`；每轮改后重读复核行数/字节/CRLF/LF/BOM（见 §7）。批 2 每处先做全文唯一命中断言（11/11 全部恰好 1 命中）再落盘。未混用 `tools.read` 与 `readFile().split`。

## 1. 六旧名映射总表（docs 路径引用逐处同步，改后残留 0）

| 旧名 | 新名 |
|---|---|
| `workbuddy_zcode_sync.py` | `workbuddy_sync.py` |
| `workbuddy_probe_zcode.py` | `workbuddy_probe.py` |
| `zcode_effective_body.js` | `effective_body.js` |
| `qoder_zcode_sync.py` | `qoder_sync.py` |
| `qoder_probe_zcode.py` | `qoder_probe.py` |
| `qwen_zcode_sync.py` | `qwen_sync.py` |

改前 22 篇共 **97 次**旧名（DSH-FIRST.md 6 次、release-notes/0.6.0.md 1 次属禁区跳过），全部落新名；改后活文档旧名残留 **0**、新名出现 **98** 次（含 `TOOLS.md` 由叙述改写产生的 `workbuddy_probe.py` 1 次）。另有 1 处简写引用 `probe_zcode.py` → `workbuddy_probe.py`（`docs/TOOLS.md:44`→改后 :45，同目录硬依赖说明）。

## 2. 逐文件逐处替换台账（file:line，最小差异片段 old → new）

共 **136 处**，分布在 **15 篇**。行号为**改前原始行号**；`TOOLS.md` 因插入 1 行，其后改后行号 +1（已单独标注）。完整旧行/新行可用 `F:\Project\ModelBus\.work\dsh-docs-20261111\<文件名>` 与现文件按行对比复现。

### `docs/ARCHITECTURE.md`（5 处）

```
  46  "现状（2026-10-23 19:19 实测" → "历史快照（2026-10-23 19:19 实测；`zcode_gateway_watch.ps1` 已退役，现役生命周期由 `gateways/zgate` 托管"
  52  "" → "，已退役"
 251  "ZCode 四" → "兼容投影三"
 316  " `zcode_gateway_watch.ps1 -Install`" → "执行 `zgate install` 恢复自启（`zcode_gateway_watch.ps1` 已退役，不再作为回退）"
 331  "四" → "三"
```

### `docs/BENCHMARKS.md`（1 处）

```
 180  " ZCode " → "兼容投影"
```

### `docs/CAPABILITY-AUDIT.md`（6 处）

```
  26  "zcode_" → ""
 110  "zcode_" → ""
 112  "zcode_" → ""
 254  "zcode_" → ""
 255  "zcode_" → ""
 356  " ZCode " → "兼容投影"
```

### `docs/MAINTENANCE.md`（12 处）

```
  12  " 起**：ZCode " → "（历史口径，10-28 已并为三组）**：当时"
 129  "_zcode" → ""
 130  "_zcode" → ""
 151  " ZCode 真实 body" → "宿主生效请求体"
 153  "_zcode.py`（它先调 `zcode_" → ".py`（它先调 `"
 154  " ZCode 真实会发的 body" → "宿主生效请求体"
 189  "zcode_" → ""
 190  "zcode_" → ""
 245  "zcode_sync.py --max-rate 0.3 --apply`）；③ Qoder（`qoder_zcode" → "sync.py --max-rate 0.3 --apply`）；③ Qoder（`qoder"
 271  "zcode_" → ""
 406  "ZCode " → "兼容投影"
 417  "_zcode.py` / `qoder_zcode" → ".py` / `qoder"
```

### `docs/MODEL-ALIAS.md`（3 处）

```
 468  "真实 ZCode body " → "宿主生效请求体"
 499  "zcode_sync.py` / `go_model_sync.py` / `qoder_zcode" → "sync.py` / `go_model_sync.py` / `qoder"
 567  "zcode_" → ""
```

### `docs/MODEL-PROVIDERS.md`（22 处）

```
  37  "ZCode 真实" → "宿主生效"
  63  "ZCode " → "兼容投影"
  65  " ZCode 真实 body" → "宿主生效请求体"
  69  "ZCode " → "兼容投影"
  93  "zcode_" → ""
  94  "zcode_" → ""
 100  "zcode_" → ""
 101  "zcode_" → ""
 130  "zcode_" → ""
 289  "zcode_" → ""
 324  "zcode_" → ""
 361  "zcode_" → ""
 494  "zcode_" → ""
 495  "_zcode" → ""
 496  "zcode_" → ""
 713  "ZCode " → "兼容投影"
 725  "ZCode " → "兼容投影"
 746  "zcode_" → ""
 763  "zcode_effective_body.js` 就是复刻这套语义，用来算「ZCode 真实会发什么" → "effective_body.js` 就是复刻这套语义，用来算「宿主生效请求体"
 773  "zcode_" → ""
 784  "zcode_" → ""
 785  "zcode_" → ""
```

### `docs/MODEL-QUICK-REF.md`（4 处）

```
  64  "ZCode " → "兼容投影"
  78  "ZCode " → "兼容投影"
 100  "0" → "2"
 102  "audit/go-model-sync-" → "evidence/go-model-sync/"
```

### `docs/PITFALLS.md`（10 处）

```
   6  "（ZCode 客户端侧的行为" → "—— 主语是 DSH 主宿主（兼容投影为 ZCode 客户端"
  11  "ZCode 客户端" → "宿主"
  70  " ZCode 真实" → "宿主生效"
  71  "_zcode" → ""
  73  "" → "（历史手法，现网 0 实例）"
  74  "实测：现网 20 条规则里 0 条用这种写法**，早先那批" → "复核：现网 20 条规则里 0 条空 map，早先清单里的"
  75  "（`beam-free`、`minimax-m3` 等）已经并组改名，别照旧清单去找；要复现这个手法，" → "id（`beam-free`、`minimax-m3` 等）已并组改名且不在现网配置，旧清单已失效；"
  76  "写前先跑 `python tools/model_alias.py --check` 看清现场" → "该手法目前只剩历史复现用途；要看现场，写前先跑 `python tools/model_alias.py --check`"
  97  "zcode_" → ""
 123  " ZCode 真实 body" → "宿主生效请求体"
```

### `docs/QODER.md`（18 处）

```
   3  "/免费/低耗/高耗" → " / 免费 / 省钱"
   4  "，共三组" → ""
   8  "_zcode" → ""
   9  "zcode_" → ""
  17  " ZCode " → "兼容投影"
  25  "/免费/低耗/高耗" → " / 免费 / 省钱"
  80  "zcode_" → ""
  86  "低耗" → "省钱"
  87  "高耗" → "省钱"
 135  "_zcode" → ""
 136  "zcode_" → ""
 143  "zcode_" → ""
 145  " ZCode 真实 body " → "宿主生效请求体"
 146  "_zcode" → ""
 149  "zcode_" → ""
 152  "_zcode" → ""
 153  "zcode_" → ""
 188  "_zcode" → ""
```

### `docs/QWEN.md`（6 处）

```
 124  " ZCode 真实 body " → "宿主生效请求体"
 169  "zcode_" → ""
 176  "zcode_" → ""
 234  "zcode_" → ""
 260  "zcode_" → ""
 261  "zcode_" → ""
```

### `docs/REVIEW-2026-11-10.md`（2 处）

```
  22  "ZCode 客户端" → "DSH 主宿主（兼容投影为 ZCode 客户端）"
  55  " ZCode 客户端" → "宿主"
```

### `docs/SECRETS.md`（10 处）

```
  34  "zcode_sync.py` / `qoder_probe_zcod" → "sync.py` / `qoder_prob"
  75  "_zcode.py`、`providers/workbuddy/workbuddy_zcode" → ".py`、`providers/workbuddy/workbuddy"
  88  "_zcode.py`、`providers/workbuddy/workbuddy_zcode" → ".py`、`providers/workbuddy/workbuddy"
  97  "zcode_" → ""
 113  "zcode_" → ""
 117  "zcode_" → ""
 119  "zcode_sync.py`、`providers/qoder/qoder_probe_zcod" → "sync.py`、`providers/qoder/qoder_prob"
 122  "zcode_" → ""
 123  "zcode_" → ""
 129  "zcode_sync.py`、`providers/qoder/qoder_probe_zcod" → "sync.py`、`providers/qoder/qoder_prob"
```

### `docs/TOOLS.md`（14 处）

```
  38  "(无)" → "| `tools/agent_profiles.py` | **DSH 主宿主下各类 agent 的只读模型投影**：以 `catalog/model_caps.json` 为唯一能力真源，为 session / subagent / headless / service-plugin 四类 profile 生成只读投影；`--list` 列出 profile、`--check` 对账漂移、`--json` 输出机器可读结果；**不写任何现网配置** | 只读投影（stdout / `--json`），无落盘写入 | ✅ 长期 |"   [新增索引行（改后行号 38，其后原始行号 +1）]
  38  "ZCode 真实 body**（`zcode_" → "宿主生效请求体**（`"
  42  "_zcode.py` | 用 **ZCode 真实 body" → ".py` | 用 **宿主生效请求体"
  43  "zcode_" → ""
  44  "zcode_effective_body.js` | 复刻 ZCode 引擎的规则解析顺序，算某 modelId **真实会发的请求体** | stdout JSON | ✅ 长期（`probe_zcod" → "effective_body.js` | 复刻兼容投影引擎的规则解析顺序，算某 modelId **真实会发的请求体** | stdout JSON | ✅ 长期（`workbuddy_prob"
  48  "zcode_sync.py` | **默认合并**：拉 qoder2api-hub `/v1/models` → 排除 `Auto`/`Fast` 别名 → 按 `price_factor` 把 `qoder:` 前缀模型并入三个 chat 组（主力 / 免费 / 省钱）；`--separate` 才写独立的 `qoder` provider；`--probe-file` 只保留探测 `ok`（或曾 ok 的瞬时限流），默认 `--max-price 0.8`。每天 12:00 定时任务里与 `qoder_probe_zcod" → "sync.py` | **默认合并**：拉 qoder2api-hub `/v1/models` → 排除 `Auto`/`Fast` 别名 → 按 `price_factor` 把 `qoder:` 前缀模型并入三个 chat 组（主力 / 免费 / 省钱）；`--separate` 才写独立的 `qoder` provider；`--probe-file` 只保留探测 `ok`（或曾 ok 的瞬时限流），默认 `--max-price 0.8`。每天 12:00 定时任务里与 `qoder_prob"
  49  "_zcode.py` | 用 **ZCode 真实 body**（复算 `zcode_" → ".py` | 用 **宿主生效请求体**（复算 `"
  51  "zcode_" → ""
  52  "zcode_" → ""
  58  "_zcode" → ""
  60  "zcode_" → ""
  61  "zcode_" → ""
  79  "zcode_" → ""
 101  "ZCode " → "兼容投影"
```

### `docs/TROUBLESHOOTING.md`（14 处）

```
  12  "ZCode 客户端" → "DSH 主宿主（兼容投影为 ZCode 客户端）"
  68  "zcode_" → ""
 182  "zcode_" → ""
 216  "zcode_" → ""
 293  "_zcode" → ""
 319  "zcode_effective_body.js` 不在 `workbuddy_probe_zcod" → "effective_body.js` 不在 `workbuddy_prob"
 356  "四" → "三"
 388  "四" → "三"
 425  "_zcode" → ""
 440  " ZCode" → "兼容投影 provider_config.json 的模型列表（DSH 侧由 cordis.patch.yml 投影）"
 445  "zcode_" → ""
 450  "ZCode 里没有 `qoder:` 模型 | `ListModels`；看五个 chat 组里是否有 `qoder:` 前缀的 model id + model rule；`curl http://127.0.0.1:7871/health` 的 `qoder.key`；8790 `/v1/models` 是否可达 | 同步没写，或被 ZCode 界面整份写回覆盖。重跑 `qoder_zcode" → "兼容投影配置里没有 `qoder:` 模型 | `ListModels`；看五个 chat 组里是否有 `qoder:` 前缀的 model id + model rule；`curl http://127.0.0.1:7871/health` 的 `qoder.key`；8790 `/v1/models` 是否可达 | 同步没写，或被 ZCode 界面整份写回覆盖。重跑 `qoder"
 468  "zcode_" → ""
 705  " ZCode 真实发了什么**（`providers/workbuddy/zcode_" → "宿主生效请求体**（`providers/workbuddy/"
```

### `docs/UPSTREAM.md`（9 处）

```
  84  "_zcode" → ""
 115  "zcode_" → ""
 136  " ZCode " → "兼容投影"
 239  "zcode_effective_body.js` 是**复刻** ZCode " → "effective_body.js` 是**复刻** 兼容投影"
 279  "ZCode 客户端" → "DSH 主宿主（兼容投影为 ZCode 客户端）"
 351  " 关于「ZCode 内置规则无条件发思考字段" → "「ZCode 内置通用规则无条件发思考字段 → 400"
 352  "此前只能靠**实测反推**。ZCodium 提供了这份规则的 MIT 原文，可以直接抄一小片当依据" → "过去只能靠**实测反推**；现已把 ZCodium 的 MIT 规则原文抄成可 diff 的最小切片（下），§2 的机制解释以该切片为准"
 415  "zcode_" → ""
 417  " ZCode 真实 body" → "宿主生效请求体"
```

### 口径归类说明

- **六旧名映射**：`zcode_` / `_zcode` / `zcode_sync.py` 等片段归零；命令、参数、链接目标、行内 `provider_config.json` 路径保持不变。
- **叙述性主语**：「ZCode 客户端」→ 每文件首次写全「DSH 主宿主（兼容投影为 ZCode 客户端）」、同文件后续简称「宿主」；「ZCode 的真实请求体 / ZCode 真实 body / ZCode 真实会发什么」→「宿主生效请求体」；「ZCode 引擎的规则解析顺序」→「兼容投影引擎的规则解析顺序」；「ZCode 里没有」→「兼容投影配置里没有」。
- **「写进 ZCode 的模型列表」**：精确串磁盘 0 命中；最近变体 `docs/TROUBLESHOOTING.md:440` 改为「模型写进兼容投影 provider_config.json 的模型列表（DSH 侧由 cordis.patch.yml 投影）。」。
- **docs/DSH-FIRST.md §7 过期口径**（真值取 docs 现行章节与 `gateways/zgate/zgate.json`）：
  - `docs/ARCHITECTURE.md:251,331` 四组→三组（真值 `:75-76`）；`:46` 现状标题改「历史快照」并标注 `zcode_gateway_watch.ps1` 已退役；`:52` 实测表标注「已退役」；`:316` 回退改 `zgate install`。
  - `docs/QODER.md:3,4,17,25,86,87` 六处四组→三组（真值 `:92` 与 `:19-21`）。
  - `docs/TROUBLESHOOTING.md:356,388` 四组→三组（真值 `:329`）。
  - `docs/MAINTENANCE.md:12` 时点倒挂：补「（历史口径，10-28 已并为三组）」并把现在时改「当时」。
  - `docs/PITFALLS.md:73-76` 空 map 清单过期：明确「历史手法，现网 0 实例」「现网 20 条规则里 0 条空 map」「旧清单已失效」「只剩历史复现用途」。
  - `docs/MODEL-QUICK-REF.md:102` 死路径 `audit/go-model-sync-*.md` → `evidence/go-model-sync/*.md`（依据 `docs/MAINTENANCE.md:169`）；`:100` 10:00 → 12:00（依据 `docs/MAINTENANCE.md:245`）。
  - `docs/UPSTREAM.md:351-352` 悬空修订引用：改为指向 `docs/PITFALLS.md` §2 现行标题并说明 MIT 切片已落地。
- **docs/TOOLS.md 补索引**：`tools/caps_upstream.py`（:37）之后新增 `tools/agent_profiles.py` 一行（改后 :38）：以 `catalog/model_caps.json` 为唯一能力真源，为 session / subagent / headless / service-plugin 四类 profile 生成只读投影，`--list` / `--check` / `--json`，不写任何现网配置。新增 `.py` 不进 `check-docs.py` 的 `collect()`，行内代码引用不产生新死链。
- **批 2：主代理 16:37 追加的 11 处窄替换**（全部唯一命中 1/1 断言通过、保留行尾、二次备份）：
  - `docs/CAPABILITY-AUDIT.md:356` 改它只为 ZCode 侧一致 → 兼容投影侧一致；`docs/BENCHMARKS.md:180` 它在 ZCode 侧走 → 兼容投影侧走；
  - `docs/MAINTENANCE.md:406` / `docs/TOOLS.md:102` ZCode 侧没有独立 `qoder` provider → 兼容投影侧没有独立 `qoder` provider；
  - `docs/MODEL-QUICK-REF.md:64` ZCode 侧已配空 map、` :78` ZCode 侧已给 → 兼容投影侧；
  - `docs/MODEL-PROVIDERS.md:63,69,713,725` 「ZCode 侧的落点 / 关系 / 通用机制 / 怎么配」→「兼容投影侧」（含 `## 1.` 与 `### 5.2` 两处标题；`check-docs.py` 全仓无 `#` 锚点链接，改标题安全）；
  - `docs/UPSTREAM.md:136` 直接写进 ZCode 配置 → 直接写进兼容投影配置。

## 3. 跳过项及原因

- **契约层一个字不动**：`~/.zcode/v2/provider_config.json`、`~/.zcode/v2/model_probe.json`、`ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` / `ZCODE_BUILTIN` / `ZCODE_GATEWAY_KEY`、`ZCODE_API_TYPE` / `ZCODE_BASE_URL` / `ZCODE_MAX_OUTPUT_TOKENS`（旧名 fallback 说明）、`zcode-main` / `zcode-free` / `zcode-saver`、`zcode-model-ledger.json`、`%LOCALAPPDATA%\ZCodeGateway\`、schema 键 `providerConfigRules` / `modelConfigRules.providerModelRules` / `modelOrder` / `personalModelIds` / `optionSpecs.reasoningLevel`、`third-party/zcode*` 路径。
- **docs/DSH-FIRST.md:31**（契约层清单）、**:85**（映射表）：主代理独占，保留。
- **docs/PITFALLS.md:6 / docs/TROUBLESHOOTING.md:12 / docs/UPSTREAM.md:279 / docs/REVIEW-2026-11-10.md:22**：本轮新写入或保留的「DSH 主宿主（兼容投影为 ZCode 客户端）」全写口径，主代理明确要求保留。
- **docs/REVIEW-2026-11-10.md:22 复核结论**：重读确认为「2026-11-10 改动复盘」表格的**结论列**，当前已是「**仅 DSH 主宿主（兼容投影为 ZCode 客户端）可见**，网关不读 optionSpecs；且尚未落盘」——属历史复盘记录原句 + 已采用 DSH 全写口径，无纯叙述性残留；按主代理「若是历史记录原句则保留并标注」分支**保留，特此标注**。
- **docs/release-notes/*** 历史发布说明：冻结不动。
- **docs/SECRETS.md env 表**：「谁在读」列指向旧脚本名的**已改新名**（:34/:75/:88/:97/:113/:117/:119/:122/:123/:129），env 名本身（含 `ZCODE_*`）保持原样。
- **NOTICE 商标与第三方署名**：AnyBridge / zen-proxy / ZCodium / zai-org/ZCode / MIT / Apache-2.0 原文、`third-party/zcodium/*` 切片全部保持。
- **历史事故/快照描述里的 ZCode 原词**：`docs/ARCHITECTURE.md` 2026-10-23 实测段、`docs/TROUBLESHOOTING.md:479` 事故实录「四个 chat 组全 502」、`docs/QODER.md:95-106` 2026-10-23 快照表等，按任务书保留。
- **显式映射外的叙述**：`ZCode 界面保存整份写回`、`ZCode 约 1 秒热重载`、`ZCode 内置规则`、`ZCode 原生四件套`、`ZCode provider 列表` 等属技术事实/界面行为/正本标题，任务书要求「保持技术事实、行号、命令、参数、链接目标不变」，故有意保留（见 §5）。
- **tools/model_alias.py:366 注释**（§7 清单）：称「dsh_sync 兜底 1000000/128000」，`dsh_sync.py` 内实际零命中；属代码文件，本分片禁碰，**仅在此记录一条**，交主代理处理。

## 4. 三道门禁（实跑两轮，贴退出码原文）

工作目录 `F:\Project\ModelBus`，`$env:PYTHONIOENCODING='utf-8'`。批 1 与批 2 落盘后各跑一轮，**两轮 exit 全 0**；下方为批 2 后（最终态）输出。

```
$ python -B tools/check-docs.py
[OK] 46 篇文档全部通过（链接 / 锚点 / 引言块 / 孤儿）
EXIT_CODE=0

$ python -B tools/check-project.py --semantic
[OK] zgate.json 真值: children=2 ports=7863,8790 upstreams=7
[OK] 正本指针: bridge.go 在位且含 forwardStream，门面无退役 JS 正本口径
[OK] 网关实现: /v1/models 聚合 + /health 段表由 keys.Channels 驱动 + QN/GM/HJ Bearer 在位
[OK] 同步策略: 默认不 push（-Push 才推）+ §35 现行不发探测口径在位
[OK] check-project: 4 项通过（语义 / 换行BOM / PS1 / 流式接线）
EXIT_CODE=0

$ python -B -m unittest discover -s tests -q
----------------------------------------------------------------------
Ran 158 tests in 0.624s

OK
EXIT_CODE=0
```

- `check-docs.py`：孤儿 / 死链 / 锚点 / 引言块判据全绿（46 篇）；批 1 后同为 `[OK] 46 篇… EXIT_CODE=0`。
- `check-project.py --semantic`：4 项通过；批 1 后同为 `EXIT_CODE=0`。
- `unittest`：158 tests OK（批 1 `0.501s` / 批 2 `0.624s`）；stderr 的 `WARN: ... 投影到 DSH 时移除了 ... 型号` 与「推理档位投影后为空」是测试夹具既有告警，exit 0。

## 5. 改后 docs/*.md 的 ZCode 残留分类统计

口径：顶层 24 篇 `.md`（含主代理独占的 `DSH-FIRST.md` / `README.md`），按「含 ZCode/zcode/ZCODE/ZCodium 字样的行」逐行归一类（优先级：契约层 > 第三方署名 > 历史记录 > 叙述层），一行只计一次。为**批 2 后最终态**重算值。

| 分类 | 行数 | 定性 |
|---|---:|---|
| 契约层 | 129 | 配置路径 / 环境变量 / schema 键 / 退役脚本名（实测行）/ 第三方规则切片路径；按要求原样保留 |
| 叙述层 | 156 | 未在显式映射内的技术事实与界面行为描述（热重载、界面写回、内置规则、provider 侧、起停联动等），按「保持技术事实不变」有意保留；含本轮新写入的「兼容投影为 ZCode 客户端」全写口径 4 处 |
| 历史记录 | 14 | 带日期的实测/快照/事故/沿革/已退役标注，按「历史事故描述里的 ZCode 原词保留」 |
| 第三方署名 | 25 | 上游仓库名 / license / NOTICE / MIT 原文 / fork / vendored 说明，全部保持 |
| **合计** | 324 | |

逐文件分布（契约 / 叙述 / 历史 / 三方）：

| 文件 | 契约 | 叙述 | 历史 | 三方 |
|---|---:|---:|---:|---:|
| `ARCHITECTURE.md` | 2 | 25 | 4 | 0 |
| `BENCHMARKS.md` | 5 | 9 | 0 | 0 |
| `CAPABILITY-AUDIT.md` | 6 | 6 | 0 | 0 |
| `CONSOLE.md` | 8 | 0 | 0 | 0 |
| `DOC-RULES.md` | 0 | 2 | 0 | 0 |
| `DSH-FIRST.md` | 4 | 6 | 2 | 0 |
| `MAINTENANCE.md` | 16 | 11 | 0 | 0 |
| `MODEL-ALIAS.md` | 8 | 0 | 0 | 0 |
| `MODEL-PROVIDERS.md` | 5 | 14 | 0 | 0 |
| `MODEL-QUICK-REF.md` | 0 | 2 | 0 | 0 |
| `MODEL-STREAM.md` | 0 | 1 | 0 | 0 |
| `PITFALLS.md` | 7 | 17 | 0 | 0 |
| `QODER.md` | 1 | 8 | 1 | 0 |
| `QWEN.md` | 0 | 4 | 0 | 0 |
| `README.md` | 0 | 1 | 0 | 2 |
| `REVIEW-2026-11-10.md` | 1 | 1 | 0 | 0 |
| `ROUTING-POLICY.md` | 1 | 0 | 0 | 0 |
| `SECRETS.md` | 8 | 7 | 1 | 0 |
| `TOOLS.md` | 12 | 4 | 4 | 0 |
| `TROUBLESHOOTING.md` | 20 | 17 | 0 | 0 |
| `UPSTREAM.md` | 22 | 21 | 2 | 23 |
| `ZGATE-LIFECYCLE.md` | 3 | 0 | 0 | 0 |

叙述层残留重点（有意保留，非漏改）：`docs/PITFALLS.md:45,179`、`docs/TROUBLESHOOTING.md:23`、`docs/MAINTENANCE.md:224`、`docs/QODER.md:78`、`docs/UPSTREAM.md:42,63` 等正本/章节标题与机制描述；主代理追加的 11 处「ZCode 侧」已全部改为「兼容投影侧」。

## 6. 未解决项（交主代理/后续批次）

1. `docs/MODEL-QUICK-REF.md:8`（「4 组 + 对话/响应，共 6 个 provider」）、`:64`、`:78`（「给 beam-free/minimax-m3 配了空 map」）与 `docs/PITFALLS.md:73-76` 已更正的「现网 0 条空 map / 三组」口径不一致；§7 未点名这些行，未动，建议后续统一。
2. `docs/MODEL-PROVIDERS.md:739`（「当前 ZCode 里配了空 map 的模型 Kimi-K3/Conatus/…」）同样与 PITFALLS 更正口径冲突；未点名，未动。
3. `docs/TROUBLESHOOTING.md:367`（四组/备用）、`:216` / `:450`（五个 chat 组）、`:479`（事故实录四个 chat 组）属历史/§7 未点名组数，保留。
4. `tools/model_alias.py:366` 注释过期（见 §3），代码文件禁碰，仅记录。
5. 若要全面把叙述层其余行的「ZCode」换成 DSH 措辞，需扩授权到「界面行为/正本标题/热重载机制」等描述并同步 `docs/DSH-FIRST.md` 三层口径；本分片按显式映射 + 主代理追加清单收口，未越界。

## 7. 复核证据（改后逐文件字节 / 行数 / EOL / BOM，实读最终值）

六旧名残留 **0**、落新名 **98** 次。

```
ARCHITECTURE.md            B= 30733 L= 475 CRLF= 474 LF=   0 BOM=false
BENCHMARKS.md              B= 28114 L= 462 CRLF=   0 LF= 461 BOM=false
CAPABILITY-AUDIT.md        B= 27135 L= 380 CRLF=   0 LF= 379 BOM=false
CONSOLE.md                 B= 23660 L= 361 CRLF=   0 LF= 360 BOM=false
DOC-RULES.md               B= 11705 L= 167 CRLF= 166 LF=   0 BOM=false
DSH-FIRST.md               B= 12830 L= 143 CRLF=   0 LF= 142 BOM=false  [主代理独占，本分片未写]
MAINTENANCE.md             B= 34326 L= 447 CRLF= 446 LF=   0 BOM=false
MODEL-ALIAS.md             B= 40330 L= 608 CRLF=   0 LF= 607 BOM=false
MODEL-PROVIDERS.md         B= 65109 L= 894 CRLF= 893 LF=   0 BOM=false
MODEL-QUICK-REF.md         B=  7348 L= 105 CRLF= 104 LF=   0 BOM=false
MODEL-STREAM.md            B= 12608 L= 198 CRLF=   0 LF= 197 BOM=false
PITFALLS.md                B= 84913 L= 920 CRLF=   0 LF= 919 BOM=false
QINIU.md                   B=  4852 L= 110 CRLF=   0 LF= 109 BOM=false
QODER.md                   B= 11415 L= 205 CRLF= 204 LF=   0 BOM=false
QWEN.md                    B= 18867 L= 355 CRLF= 354 LF=   0 BOM=false
README.md                  B=  8315 L=  70 CRLF=   0 LF=  69 BOM=false  [主代理独占，本分片未写]
REVIEW-2026-11-10.md       B= 18650 L= 185 CRLF=   0 LF= 184 BOM=false
ROUTING-POLICY.md          B= 19365 L= 278 CRLF=   0 LF= 277 BOM=false
SECRETS.md                 B= 21798 L= 348 CRLF=   0 LF= 347 BOM=false
TOOLS.md                   B= 20969 L= 111 CRLF= 107 LF=   3 BOM=false
TROUBLESHOOTING.md         B= 50844 L= 707 CRLF= 706 LF=   0 BOM=false
UPSTREAM.md                B= 29109 L= 430 CRLF= 429 LF=   0 BOM=false
VERSIONING.md              B=  6391 L= 108 CRLF=   0 LF= 107 BOM=false
ZGATE-LIFECYCLE.md         B= 21766 L= 311 CRLF=   0 LF= 310 BOM=false
```

> 本报告 self-report 不作结论；主代理按 glob + read 行数/字节 + 独立 grep 复核。
