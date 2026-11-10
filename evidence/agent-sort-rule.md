# agent-sort-rule：模型列表排序 / 匿名置底规则盘点

> **一句话**：「无公司/匿名模型排到列表下方」在 2026-10-21 WorkBuddy 反代排序链路里有原文与代码落点，但当前最终写入者 `tools/model_alias.py` 的免费组排序键已改成 `(HY 前缀优先, price, new_id)`，`tools/dsh_sync.py` 只继承 `modelOrder`，所以该规则对最终 ZCode / DSH 列表**初判不生效**。

## 结论

1. **规则原文（历史/采集层）**：`providers/workbuddy/workbuddy_zcode_sync.py:95-104` 的 `VENDOR_ORDER` 把 `"other"      # 匿名 / 未标注厂商` 放在厂商序列最后；`docs/MODEL-PROVIDERS.md:336-342` 把组内顺序写成「按模型公司分组：深度求索 → 智谱 → MiniMax → 月之暗面 → 小米 MiMo → 腾讯混元 → 阶跃星辰 → 匿名/其他」。这就是「没有厂商前缀/无法识别公司的模型置底」的可引用原文；`PROGRESS.md:144-153` 与 `CHANGELOG.md:989-995` 记录 2026-10-21 的制定批次。
2. **当前免费组排序键**：`tools/model_alias.py:1423-1430`：`rows.sort(key=lambda r: (0 if r["new_id"].startswith("HY") else 1, r["price"], r["new_id"]))`。三键分别是 `HY` 前缀优先标志、价格、显示名字典序；没有厂商/匿名维度。`docs/MODEL-ALIAS.md:132` 文档口径一致：「组内 `HY` 前缀置顶，其余按价格升序」。免费组准入只看价格 `entry_group()`（`tools/model_alias.py:1161-1163`：`price <= 0 -> free`）。
3. **DSH 投影的实际排序键**：`tools/dsh_sync.py` **不排序**，只继承两层列表顺序：`config.providerOrder`（`tools/dsh_sync.py:133,138`）决定 provider 顺序；每个 provider 的 `config.modelOrder`（缺失才用 `personalModelIds`，`tools/dsh_sync.py:143-144`）决定模型顺序；`_build_route()` 按该顺序逐个 append 到 `models`（`tools/dsh_sync.py:270-286`），`_merge_patch()` 用 `{**routes, **preserved}` 且 `yaml.safe_dump(..., sort_keys=False)`（`tools/dsh_sync.py:329-335,354`）保持插入顺序。所以 DSH 免费组的实际排序键 = `model_alias.py` 写进 `provider_config.json` 的 `modelOrder` 列表索引，等价于 `(HY优先, price, new_id)`。
4. **是否仍生效（初判）**：**最终列表不生效**。`sync-models.ps1:227` 仍跑旧 WorkBuddy 采集脚本，但 `sync-models.ps1:256` 随后跑 `tools/model_alias.py --slot auto --apply` 作为统一命名/分组最终写入者（`docs/TOOLS.md:32`，`docs/MAINTENANCE.md:245,247`）；`tools/model_alias.py:1547-1560` 用排序后的 `rows` 覆盖 `personalModelIds` 与 `modelOrder`，`tools/model_alias.py:1617-1624` 整份替换 `providerRules` 与 `providerOrder`，`tools/model_alias.py:1650-1651` 默认配置路径下再自动调用 `dsh_sync.py --apply`。旧规则只在 WorkBuddy 采集阶段短暂写过 `modelOrder`，随后被 `model_alias.py` 覆盖。
5. **运行态交叉验证**：`~/.zcode/v2/provider_config.json:47-63` 的 `opencode-go-chat-free.modelOrder` = `["HY3","HY4-Free","HY4-Pre","Beam","Conatus","Iceman","Kimi-K3"]`；`~/.dsh/profiles/desktop/cordis.patch.yml:83,96-142` 的 `zcode-free.models` 顺序完全相同。`Beam`、`Iceman`、`Conatus` 分别在第 4/5/6 位，前两个无厂商前缀，Conatus 被 `docs/QINIU.md:28-34` 明确记为「聚合/路由类产品，没有单一作者」，均未排到列表下方。`docs/reports/MODEL-SYNC-20261105-1200.md:36-47` 也列出同一组免费成员（报告按名称排序，不作为列表顺序证据）。

## 证据路径（文件:行号）

### 规则原文与历史落点

| 路径 | 行号 | 内容 |
|---|---|---|
| `providers/workbuddy/workbuddy_zcode_sync.py` | 95-104 | `VENDOR_ORDER` 末位 `"other"      # 匿名 / 未标注厂商`；上一行注释 :92 写「group by vendor in VENDOR_ORDER」 |
| `providers/workbuddy/workbuddy_zcode_sync.py` | 195-215 | `vendor_of()` 对识别不出的 model id 返回 `"other"` |
| `providers/workbuddy/workbuddy_zcode_sync.py` | 218-228 | `model_sort_key() = (pinned, cn/global, VENDOR_ORDER.index(vendor_of(mid)), rate, mid)`，`other` 因索引最大而置底 |
| `providers/workbuddy/workbuddy_zcode_sync.py` | 519-521 / 650-653 | 把上述排序写进 `personalModelIds` / `modelOrder`；`--reorder-only` 同样应用 |
| `docs/MODEL-PROVIDERS.md` | 336-342 | 「按模型公司分组……匿名/其他」文档正本；:344-346 指向 `VENDOR_ORDER` 与 `--reorder-only` |
| `docs/MODEL-PROVIDERS.md` | 82,84 | `modelOrder` / `providerOrder` 的配置落点定义 |
| `memories/zcode-ui-ordering-preferences.md` | 10-20 | 用户偏好「常用的排最前、模型按公司/厂商分组、组内常用/便宜的放前面」；未写匿名置底 |
| `docs/archive/OPENCODE-GO-ANALYSIS.md` | 255-265 | 更早的厂商分组记录：chat 厂商链末尾为「其他」 |
| `PROGRESS.md` | 144-153,170 | 2026-10-21 批次：主力置顶 → CN 优先 → 按公司分组；改动 `PINNED_MODEL_IDS / VENDOR_ORDER / model_sort_key()` |
| `CHANGELOG.md` | 989-995 | 同批次 Changelog；:511-516 记录 2026-10-23 曾改成「组内按积分消耗、同厂商粘块」 |
| `CHANGELOG.md` | 218-220 | 2026-10-28 组内排序权收归人工 `MAIN_ORDER / LOW_ORDER`，不再按厂商最低价 |

### 当前排序代码

| 路径 | 行号 | 内容 |
|---|---|---|
| `tools/model_alias.py` | 104-105,121-127 | `MAIN_ORDER` / `LOW_ORDER` 为组内排序权威来源，明确不再按厂商最低价 |
| `tools/model_alias.py` | 300-301 | `VENDOR_ORDER = (..., "CONATUS", "OTHER")`，`OTHER` 仍在末位 |
| `tools/model_alias.py` | 619-627 | `vendor_of() -> OTHER` 与 `vendor_rank()` 定义 |
| `tools/model_alias.py` | 1083-1086 | `_vendor_of_entry()`：`OTHER` 不参与省钱组自动补位 |
| `tools/model_alias.py` | 1161-1163 | 免费组准入：`price <= 0 -> free`，不看厂商 |
| `tools/model_alias.py` | 1410-1430 | 组内排序：主力按 `MAIN_ORDER`、省钱按 `LOW_ORDER`、**免费按 `(HY优先, price, new_id)`** |
| `tools/model_alias.py` | 1547-1560 | 排序后的 `ids` 同时写入 `personalModelIds` 与 `modelOrder` |
| `tools/model_alias.py` | 1617-1624 | 整份替换 `providerRules` / `providerOrder`，覆盖上游采集脚本的顺序 |
| `tools/model_alias.py` | 1650-1651 | 默认路径下自动调用 `sync_deepseek_harness()` → `dsh_sync.py --apply` |
| `docs/MODEL-ALIAS.md` | 129-132,151-160 | 当前文档：免费组 `HY` 前缀置顶、其余按价格升序；主力/省钱按人工名单 |
| `docs/TOOLS.md` | 32,35 | `model_alias.py` 是最终写入者；`dsh_sync.py` 是 DSH 投影 |
| `docs/MAINTENANCE.md` | 9-16,245-247 | 三组口径、每日流水线与峰谷价重跑 `model_alias.py` |
| `sync-models.ps1` | 227,256,283-287 | 先跑 WorkBuddy 旧排序，再跑 `model_alias.py --apply`，最后 `dsh_sync.py --check/--apply` |
| `tools/model_alias.py` | 1252-1288 | `sync_deepseek_harness()` 自动投影实现 |

### DSH 投影与测试

| 路径 | 行号 | 内容 |
|---|---|---|
| `tools/dsh_sync.py` | 8-10,29-30 | 读 ZCode 最终配置、投影三组到 DSH，不修改仓库/ZCode 配置 |
| `tools/dsh_sync.py` | 72-76 | `opencode-go-chat-free -> zcode-free` |
| `tools/dsh_sync.py` | 126-158 | `providerOrder` → `modelOrder`（`personalModelIds` 兜底），原样保留列表 |
| `tools/dsh_sync.py` | 264-296 | `_build_route()` 按 `modelIds` 顺序 append `models`，无 `sort` |
| `tools/dsh_sync.py` | 329-335,344-362 | `sort_keys=False` 输出；`{**routes, **preserved}` 保持 zcode 路由插入顺序 |
| `tools/dsh_sync.py` | 457-470,481-495 | `_main()` 组装 routes、merge、dry-run 输出 |
| `tests/test_dsh_sync_retry_policy.py` | 41-45,57,83,216-219 | 夹具 `MODELS` / `modelOrder` / `providerOrder`；断言 `[m["id"] for m in route["models"]] == MODELS[pid]`，证明投影保持顺序 |
| `tests/test_model_alias_price.py` | 112-128 | 只测免费组准入（0 价进免费），没有组内排序断言 |
| `tests/test_model_alias_hop_order.py` | 1-9,62-92 | 测链路内 hop 顺序（WB 链首、QW 链尾），不是列表组间/组内顺序 |
| `tests/` 4 个 py 文件 | — | 全量 `grep` 无「匿名/置底/列表下方/未标注/vendor_rank/免费组排序」断言：该规则无回归测试 |

### 运行态（只读核对）

| 路径 | 行号 | 内容 |
|---|---|---|
| `~/.zcode/v2/provider_config.json` | 6,35,47-63 | `providerOrder` 三组；免费组 `personalModelIds` 与 `modelOrder` 均为 `HY3, HY4-Free, HY4-Pre, Beam, Conatus, Iceman, Kimi-K3` |
| `~/.dsh/profiles/desktop/cordis.patch.yml` | 83,96-142 | `zcode-free` 的 7 条 `models` 与上表逐项同序 |
| `docs/reports/MODEL-SYNC-20261105-1200.md` | 36-47 | 当日免费成员清单（按名称排序，仅核对成员集合） |
| `docs/QINIU.md` | 28-34 | Conatus 是聚合端点、没有单一作者；`tools/model_alias.py:237-238,615` 仍给它 `CONATUS` 前缀标记 |

## 关键代码摘录

```python
# providers/workbuddy/workbuddy_zcode_sync.py:95-104
VENDOR_ORDER = (
    "deepseek",   # 深度求索
    "zhipu",      # 智谱 GLM
    "minimax",    # MiniMax
    "kimi",       # 月之暗面
    "mimo",       # 小米 MiMo
    "hunyuan",    # 腾讯混元
    "stepfun",    # 阶跃星辰
    "other",      # 匿名 / 未标注厂商
)

# providers/workbuddy/workbuddy_zcode_sync.py:218-228
def model_sort_key(rec: dict) -> tuple:
    mid = str(rec["id"])
    rate = rec.get("_rate")
    return (
        0 if mid in PINNED_MODEL_IDS else 1,
        0 if mid.startswith("cn:") else 1,
        VENDOR_ORDER.index(vendor_of(mid)),
        rate if isinstance(rate, (int, float)) else 999.0,
        mid,
    )
```

```python
# tools/model_alias.py:1423-1430
for group, rows in grouped.items():
    if group == "main":
        rows.sort(key=lambda r: (_pick_rank(r, MAIN_ORDER), r["new_id"]))
    elif group == "low":
        rows.sort(key=lambda r: (_pick_rank(r, LOW_ORDER), r["price"], r["new_id"]))
    else:
        # 免费组：常用优先（HY3 > HY4 > 其它），再按价格
        rows.sort(key=lambda r: (0 if r["new_id"].startswith("HY") else 1, r["price"], r["new_id"]))
```

```python
# tools/dsh_sync.py:133,143-144,271
order = config.get("providerOrder") or list(rules)
...
ids = pcfg.get("modelOrder") or pcfg.get("personalModelIds") or []
ids = [str(mid) for mid in ids if str(mid).strip()]
...
for model_id in provider["modelIds"]:
    ...
    models.append(model)
```

## 初判依据（为什么是不生效，而非仅文档过时）

- `tools/model_alias.py` 的 `VENDOR_ORDER` 仍把 `OTHER` 放最后，但 `vendor_rank()` 在 `*.py` 全量 grep 中只有定义、没有调用点；`_vendor_of_entry()` 只把 `OTHER` 排除在省钱组自动补位之外，不参与列表排序。
- 免费组全部 `price=0` 时，`price` 键退化为并列，最终由 `new_id` 字典序决定：`Beam < Conatus < Iceman < Kimi-K3`，所以无厂商前缀/匿名成员夹在中间而非置底。
- 旧 `model_sort_key()` 仍在 `sync-models.ps1:227` 跑，但 `sync-models.ps1:256` 的 `model_alias.py --apply` 在它之后整份重写 `providerRules/providerOrder`（`tools/model_alias.py:1617-1625`），`sync-models.ps1:283-287` 再把重写结果投影到 DSH；活配置与 DSH patch 的同序结果与此完全一致。
- `tests/` 对该规则零覆盖，说明它既没有测试钉住，也没有被当作当前契约维护。

## 未解决项

1. **用户原话正本**：仓内未找到逐字写着「无公司/匿名（没有厂商前缀）的模型优先排到列表下方」的原文；最接近的是 `providers/workbuddy/workbuddy_zcode_sync.py:103` 与 `docs/MODEL-PROVIDERS.md:341` 的「匿名/其他」链尾，以及 `memories/zcode-ui-ordering-preferences.md:13` 的「常用优先」。若 lead 需要逐字用户指令，需到会话历史/记忆正本核对；本分片按代码与文档可引用口径给出。
2. **关键词 `Reflection`**：对本仓 `*.md/py/json/yml/yaml/js/ts/go/txt/ps1/vbs` 做大小写不敏感全量 grep 零命中；疑似外部模型名或旧会话词，不在当前代码/文档/测试里。
3. **`docs/MODEL-ALIAS.md:132` 写「当前 6 条」**，活配置与 DSH patch 为 7 条（多 `Beam`）；这是文档条数滞后，不影响排序键结论。
4. **CodeGraph**：本仓 `.codegraph/codegraph.db` 存在，但 `codegraph_status({projectPath})` 返回 `[ERR] Failed to get status: unable to open database file`，按 AGENTS.md §3 退回 grep/glob/read；未执行 `codegraph init`（只读盘点）。
5. 本结论是 **self-report 初判**；lead 需独立复现，重点跑只读核对：`grep -n "rows.sort\|modelOrder\|providerOrder" tools/model_alias.py tools/dsh_sync.py`，再解析 `~/.zcode/v2/provider_config.json` 与 `~/.dsh/profiles/desktop/cordis.patch.yml` 的 `zcode-free` 顺序。
