# 生成侧字段溯源审计（agent-cap-gen）

> 一句话：20 条规则里只有 WB 渠道写下的 9 条带真实 properties（上游目录真值）；余 11 条的 contextWindow=1000000 / supportsToolCall=true 全是 ZCode builtin `.*` 兜底规则运行期补的，配置文件内无人回填，model_alias 只做 deepcopy 继承。

范围：只读审计；未改代码/配置/docs/PROGRESS.md，未 commit。口径差异：任务书写「8 条填了 contextWindow」，实测 **9 条**（20−11），多的一条是 `opencode-go-chat-fast / Space-Bunny`。

## 结论速览
| 问题 | 结论 |
|---|---|
| contextWindow 1000000 | 不是 model_alias/dsh_sync 常量；9 条=WB 上游真值，11 条=builtin 默认值 |
| supportsToolCall / supportsImage | 9 条=上游目录字段；11 条=builtin 兜底（tool 全开 true、image 默认 false），无探测 |
| reasoningLevel.values | 上游 efforts 原样搬入，model_alias 只继承不生成；disabled→off 靠 dsh_sync 投影期映射 |
| 11 条缺 contextWindow | 同步不跳过、配置不兜底，属无人回填；运行期吃 builtin 1000000/128000 |
| 每日同步 | 价格/链路/分组/档位每轮重算会漂；properties 一次写下再无人碰；DSH patch 每轮重画 |
| 只读核查 | model_alias --check 退出 1（4 处漂移=2 价格+2 链路，档位 0）；dsh_sync --check 退出 0 |

## 1. contextWindow 的 1000000

**a) 9 条带 properties = 上游目录真值（WB 写入）** `providers/workbuddy/workbuddy_zcode_sync.py:292`：
```python
ctx = int(model.get("context_length") or model.get("max_allowed_size") or 0)   # :285
props["contextWindow"] = ctx                                                   # :292
props["supportsToolCall"] = bool(model["supports_tool_call"])                  # :294
props["inputFormat"] = {"supportsImage": bool(model["supports_images"])}       # :296
cfg["optionSpecs"] = {"maxOutputTokens": {"max": out}}                         # :300
```
数据源是网关 `/panel/api/models`（同文件 `:231`），字段映射见 `providers/workbuddy/workbuddy_fetch_pricing.py:185-200`。落盘快照 `providers/workbuddy/cache/wb_pricing.json` 逐条对齐：`cn:deepseek-v4.1-flash ctx=1000000 out=128000`、`cn:hy3 192000/64000`、`cn:hy4std 960000/64000`、`cn:glm-5.3-flash 1000000/131072`、`cn:space-bunny 1000000/128000`。

**b) 余 11 条 = builtin 兜底默认值**，`third-party/zcode/zcode-builtin.json:933` 的 `"modelMatch": ".*"`：
```json
"contextWindow": 1000000,
"inputFormat": { "supportsImage": false, ... },
"supportsToolCall": true,
"optionSpecs": { "maxOutputTokens": { "max": 128000 }, "reasoningLevel": { "values": ["disabled","enabled"], "map": "{}" } }
```
实测（`node providers/workbuddy/zcode_effective_body.js` 跑全部 20 个 modelId）：这 11 条一律 `ctx=1000000 maxOut=128000 img=false matched=model,model-api,provider-model`；9 条保持自身 192000/960000/1000000。

**c) 两个脚本都没有这个常量**：`tools/model_alias.py:366` 注释「DSH 侧只能吃 dsh_sync 的兜底值（1000000 ctx / 128000 output）」**与代码不符** —— `tools/dsh_sync.py:327-330` 是 `ctx = _positive_int(meta.get("contextWindow"))`，取不到就不写该键；全仓 1000000 只出现在 `third-party/zcode/zcode-builtin.json`（与 PROGRESS.md 叙述）。

## 2. supportsToolCall / inputFormat.supportsImage

**9 条 = 上游目录字段**（`:294`/`:296`，无 fallback 分支、无探测脚本参与）。**11 条 = builtin 兜底**：tool 默认全开 true，image 默认 false。
实测后果：Gemini-AIS、Gemini-3.8-Flash、Qwen-3.8-Max、Claude-Haiku-5.5、Beam、Conatus、Iceman、Qwen-3.8-Flash、MiMo-2.6-Flash、Muse-Spark1.3、GPT-6-Luna 在 DSH patch 里都是 `input=text` —— Gemini/Haiku 系本可读图，属「没人写=默认 false」的假阴性。9 条带 properties 的全部 `supportsImage=true`。

## 3. reasoningLevel.values 的来源与对齐

| 渠道 | 写入点 | 值来源 |
|---|---|---|
| WB | `workbuddy_zcode_sync.py:308-318` | `efforts`/`supported_efforts` 原样 + `can_disable` 为真时前置 `"disabled"`；覆写表 `EFFORT_VALUES = {}`（`:121`，空） |
| QD | `qoder_zcode_sync.py:281-283` | `model.reasoning_efforts` 原样，不补 disabled |
| OC | `go_model_sync.py:575-586` | 上游 efforts；`needs_no_thinking` 时只留 `{"reasoning_effort":reasoningLevel}`，`EFFORT_UNSUPPORTED`（`:95` muse 系）写 `map:"{}"` |
| 合并期 | `model_alias.py:715-741` `_inherit_efforts`、`:793` `_sibling_effort` | **只补不清**：有可生效档位一字不动，否则借同族兄弟已落盘值 |

对齐情况：DSH 档位集合是 `tools/dsh_sync.py:71` `DSH_LEVELS = {"off","minimal","low","medium","high","xhigh","max"}`，**没有 disabled**；`_reasoning`（`:281-305`）把 disabled 映射成 `off` 键，其余越界档位直接丢弃。**生成侧（WB/QD/OC）无一处用 DSH_LEVELS 校验 values**，能否在 DSH 体现全看投影；丢失只由 `_efforts_lost`（`:206`，`--check` 于 `:564` 调用）在「源头非空、投影为空」时报错。
map 里的 `reasoningLevel === "disabled" ? "none" : reasoningLevel` 写法**不在任何脚本**（`git log -S` 无结果、builtin 无该串），只在 provider_config.json 内 —— 写入者**未验证**。

## 4. 那 11 条缺 contextWindow 的模型

**既不跳过也不兜底 —— 压根没人管，运行期由 builtin 兜。**
- 跳过：否。`tools/model_alias.py:2404` 对 20 条一视同仁 `config = copy.deepcopy(inherited_configs.get(...))`。
- 配置内兜底：无。唯一补元数据钩子是 `model_alias.py:369` `MODEL_META = {}`（空表），`:2406` 起只在命中该表时补 `properties` → 永不触发。
- 回填：无。写 properties 的只有 WB sync；这 11 条上游在 OC/QD/QN/HJ/GM 侧，QD 只写 `optionSpecs.reasoningLevel`、OC 同。
- 表现：ZCode/DSH 都显示 1000000/128000，**看起来正常但其实是默认值**，真实上限更小时即超发。

## 5. 每日同步覆盖 / 补齐什么

| 字段 | 维护者 | 行为 |
|---|---|---|
| `config.enabled` | model_alias `:2405` | 每轮强制 true |
| `optionSpecs.reasoningLevel.values` | model_alias `:715-741` | 每轮重算继承链（装饰渠道会 pop），`drifted_efforts` 守门 |
| `properties.contextWindow / supportsToolCall / inputFormat` | 无 | deepcopy 继承旧 config，**一次写下再无人碰**；仅 WB sync 下次命中该型号才更新 |
| `optionSpecs.maxOutputTokens.max` | 无 | 同上，只继承 |
| 价格 / 链路 / 分组 / modelId | model_alias | **每轮重算，漂移高发** |
| DSH patch 的 `contextWindow/maxTokens/input/reasoningEfforts/retryPolicy` | dsh_sync `:281-333`、`:393`、RETRY_POLICY | 每轮整体重建；`_keep_efforts` 仅在新档位为空时保留旧值 |

> 配置侧「价格动、元数据冻」，投影侧「每轮重画」。

## 6. 只读核查（实测）
```
python -B tools/model_alias.py --check   → exit 1
python -B tools/dsh_sync.py --check      → exit 0
```
model_alias --check 输出：
```
发现漂移 4 处（现有 alias map vs 当前价格源重算）：
  价格：Qwen-3.8-Flash  0.09 -> 0.03
  价格：Qwen-3.8-Max  0.43 -> 0.17
  链路：Qwen-3.8-Flash  旧 QD:Qwen3.8-Flash@0.09 -> OC:qwen3.8-flash@0.09 -> OC:qwen3.8-flash@0.09
                        新 QD:Qwen3.8-Flash@0.03 -> OC:qwen3.8-flash@0.09 -> OC:qwen3.8-flash@0.09
  链路：Qwen-3.8-Max    旧 QD:Qwen3.8-Max@0.43   新 QD:Qwen3.8-Max@0.17
```
拆分：**价格漂移 2 处**、**链路漂移 2 处**（同两个模型、价格变导致跳签名变，同一根因）、**档位漂移 0 处**（`drifted_efforts` 无输出 → 20 条档位本轮不会被清空）。
stderr 旁证：`WARN: QD 价格源不可用（127.0.0.1:8790: <urlopen error [WinError 10061] ...>），已回落到上次成功的倍率快照`；`WARN: cn:hy4-preview-f 的 credits/list_rate 都缺失，按同族挂牌价 0.29 计费` → 这两笔是「价格漂移」，非元数据问题。
dsh_sync --check 输出：`ZCode: 3 个 provider / 20 个模型`；`DSH 路由: 主力 3；免费 5；省钱 12`；`模型表: 无变化；凭据引用：无变化`。node 在 PATH（v24.13.1），`zcode_effective_body.js` 正常执行，**无 node 缺失假阳性**；当前 patch 与 provider_config 投影完全一致。

## 字段 × 来源矩阵

| 字段 | 来源 | 依据 |
|---|---|---|
| `config.enabled` | 常量表 | model_alias.py:2405 |
| `properties.contextWindow`（9 条） | **上游真值** | workbuddy_zcode_sync.py:285,292 ← wb_pricing.json |
| `properties.contextWindow`（11 条） | **默认值**（builtin `.*`） | zcode-builtin.json:933,937；实测 effective 全 1000000 |
| `properties.supportsToolCall`（9 条） | 上游真值 | workbuddy_zcode_sync.py:294 |
| `properties.supportsToolCall`（11 条） | 默认值（全开 true） | zcode-builtin.json:946 |
| `inputFormat.supportsImage`（9 条） | 上游真值 | workbuddy_zcode_sync.py:296 |
| `inputFormat.supportsImage`（11 条） | 默认值 false（假阴性） | zcode-builtin.json:940 |
| `maxOutputTokens.max`（9 条） | 上游真值 | workbuddy_zcode_sync.py:300 |
| `maxOutputTokens.max`（11 条） | 默认值 128000 | zcode-builtin.json:955 |
| `reasoningLevel.values` | 上游 efforts + 继承链 | WB:308-318 / QD:281-283 / OC:575-586 / alias:715-741 |
| `reasoningLevel.map` | 上游判定 + 手写 | OC go_model_sync:579；其余串不在仓内（来源未验证） |
| `reasoningLevel` 与 DSH 档位对齐 | 投影期映射（默认） | dsh_sync.py:71,281-305 |
| 价格 / 积分 / 分组 | 上游真值 + 常量表兜底 | model_alias wb_prices/qd_prices、OC_PRICES/QD_PRICES |
| 11 条 properties 回填 | **无人回填** | MODEL_META 空表（model_alias.py:369）；QD/OC 不写 properties |
| DSH patch 各字段 | 每轮重画 | dsh_sync.py:281-333,393,RETRY_POLICY |

## 未验证 / 环境备注
- **未验证**：`=== "disabled" ? "none"` 类 map 的确切写入者（仓内与 git 历史均无此串）。
- **未验证**：每日定时任务实际调用链（`model_alias.py:659` 注释提到 `sync-models.ps1` 默认 auto），未读该 ps1。
- **未验证**：WB 网关 `/panel/api/models` 当前返回是否与 `wb_pricing.json` 快照一致（本次未联网）。
- **环境备注**：会话中途 `ops_bash` 报 `EXECUTOR_UNAVAILABLE: Niubash preparation failed ... winuxcmd/usr/bin/arch.exe (mode 100666)`，改用 run_code 内 `node:child_process.spawnSync`（显式构造 PATH/SystemRoot/USERPROFILE/TEMP，`PYTHONUTF8=1`）完成全部命令，结论不受影响。
