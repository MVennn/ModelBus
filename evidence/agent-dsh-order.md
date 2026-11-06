# DSH 侧「模型下拉列表」当前生效顺序盘点

盘点时间：2026-11-05 22:29 CST。只读盘点，未修改任何配置/源码。

## 结论（先行）

1. **当前 GUI 生效顺序 = `~/.dsh/profiles/desktop/cordis.patch.yml` 里 `llm-pi-ai.providers` 的书写顺序，组内 = `models` 数组顺序。** 三个 `zcode-*` provider 按 `主力 → 免费 → 省钱` 排列，与 `~/.zcode/v2/provider_config.json` 的 `providerOrder` / `modelOrder` 逐条一致（2 / 7 / 10，共 19 个模型，strict 比对 `equal=true`）。
2. **「无公司/匿名模型排到下方」这条规则在 DSH 运行时尚未实现。** DSH GUI 唯一生效的排序函数是 `orderModelProviders()`：只把 `deepseek-account` / `deepseek-official` 提到前面，其余 provider 与每个 provider 内的模型都保持 catalog 原顺序；全文检索 DSH checkout 未见 `无公司` / `匿名模型` / `vendor` / `company` / `置底` 参与模型排序的代码。
3. **该规则在上游 ZCode 侧曾实现，但被当前最终写入者 `tools/model_alias.py --apply` 覆盖。** `workbuddy_zcode_sync.py` 的 `VENDOR_ORDER` 末位明确是 `"other" # 匿名 / 未标注厂商`（:103），`model_sort_key()` 按 `pinned → CN → VENDOR_ORDER → rate → id` 排序（:218–228），文档 `docs/MODEL-PROVIDERS.md:336–347` 也写明「匿名/其他」排末位；但日常同步链以 `model_alias.py` 为唯一最终写入者，其组内排序不含厂商/匿名维度（:1423–1430、:1547–1560），随后自动调用 `dsh_sync.py --apply` 把结果原样投影进 DSH patch（:1252–1288、:1650–1651）。
4. **偏差实况（按「匿名/无公司置底」口径）**：免费组 `Beam` / `Conatus` / `Iceman` 排在 `Kimi-K3` 之前，省钱组 `Space-Bunny` / `Muse-Spark1.3` / `GPT-6-Luna` 排在 `HY3-X` 之后但并未按「无公司统一置底」收束；且与旧 `VENDOR_ORDER`（腾讯混元 HY 在阶跃星辰之前、匿名/其他最末）不一致。当前 DSH 无二次排序覆盖，故 GUI 忠实呈现的是被覆盖后的顺序，不是旧规则顺序。
5. **`Reflection Beam` / `Tencent` 关键词**：在 `cordis.patch.yml`、`dsh_sync.py`、DSH checkout 的 `@deepseek-ai/*` 模型选择器代码中均为 0 命中；`Tencent` 只出现在 lighthouse/DevTools 第三方库（`dsh-experimental-inspector`，`lib/devtools/chunks/third-party-web-Dm5IRT3g.js:9193`）与 ZCode 上游说明文档，与模型下拉排序无关。

## 一、当前配置里的模型顺序原文（文件:行号）

正本：`<home>\.dsh\profiles\desktop\cordis.patch.yml`（即 `~/.dsh/profiles/desktop/cordis.patch.yml`），段 `- id: llm-pi-ai`（:44）→ `config.providers`（:46）。

```yaml
# cordis.patch.yml:47-82  zcode-main（主力）
47:       zcode-main:
48:         displayName: 主力
60:         models:
61:           - id: DeepSeek-4.1-Flash
74:           - id: Qwen-3.8-Max

# cordis.patch.yml:83-147  zcode-free（免费）
83:       zcode-free:
84:         displayName: 免费
96:         models:
97:           - id: HY3
106:           - id: HY4-Free
114:           - id: HY4-Pre
122:           - id: Beam
127:           - id: Conatus
132:           - id: Iceman
142:           - id: Kimi-K3

# cordis.patch.yml:148-245  zcode-saver（省钱）
148:       zcode-saver:
149:         displayName: 省钱
161:         models:
162:           - id: Qwen-3.8-Flash
167:           - id: GLM-5.3-Flash
177:           - id: MiniMax-M3.1-Flash
189:           - id: MiMo-2.6-Flash
199:           - id: MiMo-2.6-Pro
210:           - id: HY3-X
219:           - id: Claude-Haiku-5.5
224:           - id: Space-Bunny
236:           - id: Muse-Spark1.3
241:           - id: GPT-6-Luna
```

同段 `apiKeyEnv: ZCODE_GATEWAY_KEY`（:59/:95/:160）只引用凭据名，无密钥值；`cordis.yml`（profile base）为空数组 `[]`，`patches/` 只有一个 `@m1khal3v__dsh-tool-codegraph@2.0.0.patch` 且 0 命中 `llm-pi-ai`，故 **profile 层无二次覆盖**。

严格比对命令与实况输出（工作区根执行）：

```text
zcode-main: start=47 end=82 config=2 patch=2 equal=true
zcode-free: start=83 end=147 config=7 patch=7 equal=true
zcode-saver: start=148 end=246 config=10 patch=10 equal=true
```

上游 `~/.zcode/v2/provider_config.json` 的 `modelOrder` 与上述三组逐字相同：

```text
opencode-go-chat (主力): ["DeepSeek-4.1-Flash","Qwen-3.8-Max"]
opencode-go-chat-free (免费): ["HY3","HY4-Free","HY4-Pre","Beam","Conatus","Iceman","Kimi-K3"]
opencode-go-chat-fast (省钱): ["Qwen-3.8-Flash","GLM-5.3-Flash","MiniMax-M3.1-Flash","MiMo-2.6-Flash","MiMo-2.6-Pro","HY3-X","Claude-Haiku-5.5","Space-Bunny","Muse-Spark1.3","GPT-6-Luna"]
```

## 二、GUI 排序逻辑落点（文件:行号）

实际安装目录（运行时上下文里的 `F:\Program Files\DeepSeekRuntime\...` 少一个空格；本机 `app.asar` 是目录而非归档）：

- `F:/Program Files/DeepSeekRuntime/resources/app.asar/dsh/node_modules/@deepseek-ai/dsh-client-ui-model-selection/lib/client.js:1101-1110` —— `orderModelProviders()` 定义；注释 `model order within each group is unchanged`（:1106）。
- 同文件 `:1171-1177` —— composer 下拉 `ModelSelect` 调用 `orderModelProviders(state.groups)`；`:1188-1195` 无查询时 `rankByName(..., "")` 保持原序，有查询时按名字前缀/匹配度重排；`:1196-1199` 展平顺序即最终下拉顺序。
- 同文件 `:1801-1814` —— `/model` 命令弹窗 `optionsOf()` 复用同一个 `orderModelProviders()`，`for (const model of group.models)` 原序输出。
- `.../dsh-client-ui-settings-models/lib/client.js:1196-1222` —— 设置页 Models provider 行 `joinProviderDirectory()` 用同一比较器（account=0 / official=1 / 其它=2），注释 `then other routes in their original order`（:1194）。
- `.../dsh-client-ui-model-selection/README.zh.md:74` —— 文档确认「两个入口共用提供方排序，组内 `rankByName`」。
- `.../dsh-api-session-controller/lib/types/catalog.js:10-59` —— Host 目录构造：`listProviders()` 顺序 + `listModels()` 顺序，`models.map` 不排序。
- `.../dsh-llm-pi-ai/lib/index.js:1887-1903`、`:1852-1860` —— `listModels()` 返回 `snapshot.models.getModels(provider).map(...)`，按配置模型表顺序；`.../dsh-llm/lib/index.js:2080-2100` 明确注释 `@returns detached model metadata in adapter-preferred order`。

关键代码原文：

```js
// dsh-client-ui-model-selection/lib/client.js:1104-1109
 * Put the account and official providers first, preserving every other relative order.
 * @returns a sorted copy; model order within each group is unchanged.
function orderModelProviders(groups) {
  return groups.toSorted((left, right) => (left.id === "deepseek-account" ? 0 : left.id === "deepseek-official" ? 1 : 2) - (right.id === "deepseek-account" ? 0 : right.id === "deepseek-official" ? 1 : 2));
}
```

**覆盖判定**：DSH 侧不存在「匿名模型置底」的 GUI 实现；也不存在把 patch 顺序重新排序的运行时覆盖。检索 `dsh-client-ui-model-selection`、`dsh-client-ui-settings-models`、`dsh-client-ui-deepseek-model-label-1017`、`dsh-web-frontend/dist/assets` 及全部 `@deepseek-ai/*` 包，`无公司` / `匿名模型` / `vendor` / `company` / `置底` 均未参与模型排序（命中的 `anonymous` 全是遥测用户 id、匿名管道、DevTools 等无关语义）。

## 三、与「匿名模型置底」规则的偏差

规则原始落点（ZCode 仓，真实路径 `F:\Project\ZcodeAIModels`）：

- `providers/workbuddy/workbuddy_zcode_sync.py:89-104` —— 注释「inside a region, group by vendor in VENDOR_ORDER」；`VENDOR_ORDER` 末位 `"other", # 匿名 / 未标注厂商`（:103），腾讯混元 `"hunyuan"`（:101）在阶跃星辰 `"stepfun"`（:102）之前。
- 同文件 `:218-228` —— `model_sort_key()` = `(pinned, CN优先, VENDOR_ORDER.index(vendor_of), rate, id)`；`:519-521` / `:650-653` 写 `personalModelIds` + `modelOrder`；`:676` 按同键排 `merged`。
- `docs/MODEL-PROVIDERS.md:336-347` —— 「深度求索 → 智谱 → MiniMax → 月之暗面 → 小米 MiMo → 腾讯混元 → 阶跃星辰 → 匿名/其他」，并指明正本是上述 `PINNED_MODEL_IDS / VENDOR_ORDER`，`--reorder-only --apply` 可只重排。
- `memories/zcode-ui-ordering-preferences.md:14` —— 用户偏好「模型按公司/厂商分组连续排列（…腾讯混元…）」；`How to apply`（同文件）要求「组内把常用/便宜的放前面」。

**被覆盖链（证据）**：

- `tools/model_alias.py:1423-1430` —— 当前最终组内排序：主力按 `MAIN_ORDER`、省钱按 `(LOW_ORDER, price, new_id)`、免费按 `(HY 优先, price, new_id)`；**无 `VENDOR_ORDER` / `other` 置底分支**。
- `tools/model_alias.py:1547-1560` —— 重写 `personalModelIds` / `modelOrder = ids`，其中 `ids` 来自上一步 `grouped[group]`。
- `tools/model_alias.py:300-301` 与 `:611-627` —— `VENDOR_ORDER` / `vendor_rank()` 仍存在，但当前 `grouped` 排序路径未调用 `vendor_rank()`；`:1083-1086` 的 `OTHER` 只用于「不自动收录」，不是排序置底。
- `tools/model_alias.py:1252-1288`、`:1650-1651` —— `--apply` 收尾自动 `sync_deepseek_harness()`，以 `dsh_sync.py --apply` 写 DSH patch；`sync-models.ps1:256-287` 每日 12:00 任务先跑两次 `model_alias.py --slot auto --apply`，再跑 `dsh_sync.py --check/--apply`。`PROGRESS.md:2063-2078`、`:2102-2111` 记录该自动投影已上线且 `--check` 退出 0。
- `tools/dsh_sync.py:143` —— `ids = pcfg.get("modelOrder") or pcfg.get("personalModelIds") or []`；`:271-286` 原序 `for model_id in provider["modelIds"]` 构造 `models`；`:344-362` 只替换 `llm-pi-ai` 段、不排序；`:329-336` `sort_keys=False`。
- `PROGRESS.md:803` / `CHANGELOG.md:663` —— 「旧 sync/probe 现在是数据采集器；最终写入只跑 `model_alias.py`」/「旧的三个 sync / 两个 probe 降级为数据采集与兼容；`model_alias.py` 是唯一最终写入者」。

**偏差清单**：

| 位置 | 旧规则期望 | 当前 DSH 配置/GUI 实况 | 偏差 |
| --- | --- | --- | --- |
| 免费组 | 有厂商的在前，`匿名/其他` 统一置底 | `Beam`(:122) / `Conatus`(:127) / `Iceman`(:132) 在 `Kimi-K3`(:142) 之前 | 未把无公司/匿名条目收束到组尾；且 `HY*`（腾讯混元）被 `model_alias.py:1430` 单独提前 |
| 省钱组 | `… → HY(腾讯) → STEP → 匿名/其他` | `HY3-X`(:210) 之后依次为 `Claude-Haiku-5.5`(:219) / `Space-Bunny`(:224) / `Muse-Spark1.3`(:236) / `GPT-6-Luna`(:241) | 厂商序列被 `LOW_ORDER + 价格 + id` 取代；`Claude/GPT/Muse/Space` 等有前缀厂商混在 HY 之后，匿名项未按 `other` 统一置底 |
| 全链路 | DSH GUI 据 vendor 二次排序 | DSH 只按 catalog 原序渲染 | GUI 运行时尚未实现该规则，不存在「实现后被覆盖」的 DSH 代码；是上游规则被最终写入者覆盖后原样透传 |
| 关键词 | `Reflection Beam` / `Tencent` 参与排序 | 0 命中（模型选择器路径） | 与排序无关；`Tencent` 仅见 DevTools 第三方库 `…/dsh-experimental-inspector/lib/devtools/chunks/third-party-web-Dm5IRT3g.js:9193` |

## 四、验证方式（只读命令，可复现）

```bash
# 1) 当前 patch 的模型顺序原文
sed -n '44,246p' ~/.dsh/profiles/desktop/cordis.patch.yml

# 2) GUI 排序落点
grep -n "orderModelProviders\|rankByName\|joinProviderDirectory" \
  "F:/Program Files/DeepSeekRuntime/resources/app.asar/dsh/node_modules/@deepseek-ai/dsh-client-ui-model-selection/lib/client.js" \
  "F:/Program Files/DeepSeekRuntime/resources/app.asar/dsh/node_modules/@deepseek-ai/dsh-client-ui-settings-models/lib/client.js"

# 3) 旧「匿名置底」规则与当前覆盖点
grep -n "VENDOR_ORDER\|model_sort_key\|匿名\|rows.sort\|modelOrder\|sync_deepseek_harness" \
  F:/Project/ZcodeAIModels/providers/workbuddy/workbuddy_zcode_sync.py \
  F:/Project/ZcodeAIModels/tools/model_alias.py \
  F:/Project/ZcodeAIModels/tools/dsh_sync.py
```

`dsh_sync.py --check` 与 `model_alias.py --check` 均为退出码 0 / 无漂移（见 `PROGRESS.md:2074-2078`、`:2111`），本次盘点未执行写模式，配置文件 mtime 保持 `2026-11-05 21:56`。

## 五、未解决项

- `dsh-client-ui-primitives` 在本机 checkout 的 `@deepseek-ai/` 下未以含 `primitive` 的目录名出现，`rankByName` 实现体未能定位到文件:行号；但其调用点 `dsh-client-ui-model-selection/lib/client.js:1190` 与文档 `README.zh.md:74` 已确认「空查询保持宿主顺序、有查询按名字匹配度重排」，不影响本盘点结论。
- `Reflection Beam` 作为完整词在本次盘点范围内 0 命中；若它指向某个未部署的模型别名/外部计划，需 [待补: 该词的来源文档或期望位置] 才能判定是否属于「匿名置底」范围。当前 patch 中只有 `Beam`（:122）。
- 未在浏览器中抓取实时 DOM 下拉渲染顺序（本任务限定纯只读盘点、不启动/刷新 GUI）；结论基于当前落盘的 profile patch + 运行中安装的 DSH 打包代码，二者由 `dsh_sync.py` 与 `listModels` 链直接连通。
