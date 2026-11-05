- 2026-11-05 踩坑：仓根存在 .codegraph/codegraph.db，但 codegraph_status / codegraph_explore（相对与绝对 projectPath 均试过）报 `unable to open database file`；按任务书不建索引，退回 grep/glob/read 定向检索。
- 2026-11-05 踩坑：ops_bash 是 bash，`cd /d <repo>\...` 报 `cd: too many arguments`；改用 ops_bash 的 workdir 参数（相对会话根写 ZcodeAIModels）即可，heredoc 原样可用。
- 2026-11-05 踩坑：全量 `python -m unittest discover -s tests -v` 35 项中仅 test_dsh_sync_retry_policy.DryRunProjectedProvidersTest.setUpClass 报 `PermissionError: [WinError 5] 拒绝访问 .work\dsh-sync-retry-fixture-*`；`.work` 已存在但新建子目录被拒，属本机 ACL/并发夹具，改单跑 `-p "test_model_alias_demote.py"` 即 2/2 OK。
- 2026-11-05 踩坑：未 --apply 时 `python tools/model_alias.py --check` 退出码 1 是预期漂移，报告里 8 处均为 `@0` vs `@0.0` 的价格格式差；优化后的 `DeepSeek-4.1-Flash` 链顺序在旧/新两侧一致（OC->OC->WB->QW），无需改生成器。

## 2026-11-05 验收：上游 429 限流优化固化进生成器

结论：`DEMOTE_HOPS` 与 `family_entries` 的 0.5 权重已写进 `tools/model_alias.py` 源码，
每天 12:00 的定时同步只是重跑本脚本，不再依赖手工改产物；dry-run 输出可见优化后的链。
全程 dry-run / --check / unittest，未跑 --apply，未动 PROGRESS.md、docs/、tests/ 下既有测试、
`~/.zcode`、`~/.dsh`、config.json。`M tools/dsh_sync.py` 与其余未跟踪分片是并行任务产物，本分片不涉及。

### 文件:行（均为仓库内相对路径，落盘后行号）

| 位置 | 内容 |
| --- | --- |
| `tools/model_alias.py:151` | `TAIL_HOPS = {("QW", "deepseek-v4.1-flash")}`，原有尾跳，排序权重 1 |
| `tools/model_alias.py:153-158` | 新增 `DEMOTE_HOPS = {("WB", "cn:deepseek-v4.1-flash")}`；注释固化「12:00 同步只重跑脚本，规则随源码固化，不会被同步产物冲回 WB 打头」，并写明回退只需删该集合 |
| `tools/model_alias.py:948-958` | `family_entries` 排序 key：`TAIL_HOPS`→1、`DEMOTE_HOPS`→0.5、普通跳→0；后接 price / cn-global / channel / upstream 原次序不变 |
| `tools/model_alias.py:960` | `group = with_airport_fallback(group)` 位置未动，机场孪生跳仍由 `tools/model_alias.py:166-189` 追加到链尾，未被 0.5 权重挤掉 |
| `tools/model_alias.py:1476-1479` | dry-run 增加 `chain: OC:... -> ...` 输出行，让优化后的值在 `--no-arena --no-pools` 输出里直接可见 |
| `tests/test_model_alias_demote.py:23-38` | `_hop()` 夹具，构造 WB / OC 直连 / OC 机场孪生 / QW 四跳 |
| `tests/test_model_alias_demote.py:42-52` | `_chain()` 调真实 `ma.family_entries()`，不复制排序 lambda |
| `tests/test_model_alias_demote.py:54-65` | `test_demote_between_normal_and_tail`：断言 chain 为 OC -> OC -> WB -> QW，并断言 `DEMOTE_HOPS` 含 WB 跳 |
| `tests/test_model_alias_demote.py:67-79` | `test_airport_twin_stays_last`：断言机场孪生跳唯一、落位后整链仍是 OC -> OC -> WB -> QW、QW 保持链尾 |

### diff 摘要

`git diff -- tools/model_alias.py`（exit 0）三段 hunk，`git diff --stat -- tools/model_alias.py`
输出 `tools/model_alias.py | 17 ++++++++++++++++-` / `1 file changed, 16 insertions(+), 1 deletion(-)`：

1. `@@ -150,6 +150,13 @@` 新增 `DEMOTE_HOPS` 定义 + 7 行注释（含定时同步不冲掉手工改动的说明）。
2. `@@ -938,8 +945,12 @@` 排序 key 由 `1 if TAIL_HOPS else 0` 改成三元
   `1 if TAIL_HOPS else 0.5 if DEMOTE_HOPS else 0`，并加 2 行权重说明；
   `with_airport_fallback` 调用未改。
3. `@@ -1462,6 +1473,10 @@` dry-run 每个条目下多打印一行 `chain: ...`。

新增未跟踪文件：`tests/test_model_alias_demote.py`（83 行）、本分片。
`git status --short -- tools/model_alias.py tests/test_model_alias_demote.py evidence/agent-model-alias-hardening.md`
→ `M tools/model_alias.py` / `?? tests/test_model_alias_demote.py` / `?? evidence/agent-model-alias-hardening.md`。
三处源码/测试改动均由 `edit` 工具真正落盘；分片由 `edit` 追加，保留上方 4 条踩坑记录。

### 测试命令与退出码（cwd = 仓库根 ZcodeAIModels）

实测 git-bash，`PYTHONIOENCODING=utf-8` 避免中文乱码：

```bash
PYTHONIOENCODING=utf-8 python -m unittest discover -s tests -p 'test_model_alias_demote.py' -v
# PY_EXIT=0
# test_airport_twin_stays_last ... ok
# test_demote_between_normal_and_tail ... ok
# Ran 2 tests in 0.000s / OK

PYTHONIOENCODING=utf-8 python tools/model_alias.py --no-arena --no-pools
# PY_EXIT=0
#   DeepSeek-4.1-Flash   deepseek-v4.1-flash   chat   0.11
#   chain: OC:deepseek-v4.1-flash -> OC:deepseek-v4.1-flash -> WB:cn:deepseek-v4.1-flash -> QW:deepseek-v4.1-flash
# dry run；加 --apply 写入 provider_config.json 与 alias map

PYTHONIOENCODING=utf-8 python tools/model_alias.py --check --no-arena --no-pools
# PY_EXIT=1
# 发现漂移 8 处（现有 alias map vs 当前价格源重算）：均为 @0 vs @0.0 的价格格式差；
# DeepSeek-4.1-Flash 旧/新链均为 OC->OC->WB->QW，链顺序零漂移

git diff -- tools/model_alias.py
# exit 0
```

CMD 复现写法：

```bat
cd /d <仓库根>
set PYTHONIOENCODING=utf-8
python -m unittest discover -s tests -p test_model_alias_demote.py -v
python tools\model_alias.py --no-arena --no-pools
```

已修正的失败入口（原始报错留存）：`python -m unittest -v tests.test_model_alias_demote`
→ `EXIT=1`，`ModuleNotFoundError: No module named 'tests.test_model_alias_demote'`
（`tests/` 无 `__init__.py`，包路径导入失败）；改用 `unittest discover -s tests -p` 后 2/2 通过。
`--check` 的 `PY_EXIT=1` 是 `drift_report` 对价格格式差异的预期返回，不是本次改动的失败。


