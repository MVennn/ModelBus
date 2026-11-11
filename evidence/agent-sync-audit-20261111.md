# 同步链 / 探活链体检 — 2026-11-11

用户报障（m00001）：使用一次 ais 后，DSH 整场会话卡在 `pi-ai provider "zcode-main" has no configured model "Gemini-AIS"`；随后 ais 从配置里完全消失，Gemini-3.8-Flash 也不可用。

## 一、根因链（逐环有实测证据）

1. **11:02 那轮每日同步把 Gemini-AIS 摘掉了。** `model_probe.py` 默认 `--max-tokens 32`，GM（catiecli）的 Gemini 是「先思考再出字」，32 token 全被思考预算吃掉，上游回 400；记录写成 `status=timeout/error` 且 `ever_ok` 为空。
2. **`model_alias.py --probe-file` 的摘除逻辑把它当死型号删除。** 条件为「非 ok 且不在 transient-with-ever_ok」→ 直接 skip，主力组也不例外。
3. **Gemini-3.8-Flash 走的是 HJ「福利」档，该档在 gemai.cc 已断供**：`[福利]gemini-3.8-flash` 直连回 `model_not_found / No available channel for model`，zgate 日志写 `HJ:[福利]gemini-3.8-flash -> Service Unavailable model_not_found, fallback (none)` → 502。
4. **DSH 侧不降级、硬失败。** `tools/dsh_sync.py:145` 把 modelOrder / personalModelIds 直接投影成 zcode-main 的型号清单；清单里少一条，宿主就报 "has no configured model" 并卡死整场会话，不会回退到其他模型。
5. **静默。** 整条链没有任何一处把「这次少了一个上次还在的型号」说出来 —— 这是本次故障最难查的地方。

## 二、修复（已落盘、已验）

| # | 文件 | 改动 | 防的是哪一环 |
|---|---|---|---|
| 1 | tools/model_probe.py | `--max-tokens` 默认 32 → 256 | ①思考吃光预算被误判死型号 |
| 2 | sync-models.ps1 | 探活参数改 `--timeout 90 --max-tokens 256` | ①同上，落在定时任务这一侧 |
| 3 | tools/model_alias.py | `apply_probe_filter()`：主力组**只报不删**（suspect_main），真正 unavailable/404 仍照删；403 计入 blocked | ②④主力组成员被当场删除 |
| 4 | tools/dsh_sync.py | 新增 `zcode-model-ledger.json` 账本 + `_previous_model_ids()` / `_remember_model_ids()`，投影时 WARN 出「移除了上次还在这几个型号」 | ⑤静默少条 |
| 5 | tools/model_alias.py | `EMPTY_ALLOWED = {Gemini-AIS, Gemini-3.8-Flash}` | 每天误报「档位漂移 → 需要人工看」 |
| 6 | tools/model_alias.py | `drift_report()` 空表短路 + WARN | 空新表把整张表判成「全部消失」 |
| 7 | tools/model_stream_check.py | 200 且正文/思考全空 → `SKIP`（原来是 FAIL/WARN 边缘） | 空 completion 被当备注忽略 |
| 8 | tools/model_alias.py | HJ 换源：`[满血A]gemini-3.8/3.7/3.6-flash` 三跳 + HOP_PRIORITY 0/1/2 + ABBR 三条 | ③HJ 502 |
| 9 | tests/test_model_alias_hop_order.py / test_model_alias_probe_filter.py | 三跳断言 + 11 条 probe 过滤用例 | 回归 |

## 三、验证

- 直连 gemai.cc：`[福利]` 3.8/3.7/3.6 → model_not_found；`[满血A]/[满血B]/[满血C]/[满血F]/[官逆B]` 的 3.8-flash → 200（4.6–8.4s，max_tokens≥256）。账户 billing 正常。
- 经网关探活：DeepSeek-4.1-Flash / Gemini-3.8-Flash / Gemini-AIS 全 `ok http=200`。
- `py -3 -m unittest discover -s tests` = **135 tests OK**。
- `py -3 tools/model_alias.py --slot auto --arena --scores --check` = **exit 0「无漂移」**（修复前 exit 1）。
- 完整跑批：`sync-models.ps1` 13:36:01→13:43:56（约 8 分钟），流式准入探针 PASS 3 / WARN 3 / FAIL 0 / SKIP 1 / EXEMPT 1；报告 docs/reports/MODEL-SYNC-20261111-1343.md。
- 现网主力组：`DeepSeek-4.1-Flash, Gemini-3.8-Flash, Gemini-AIS`；alias map 里 Gemini-3.8-Flash chain = HJ:[满血A]gemini-3.8-flash → 3.7 → 3.6。

## 四、仍存疑（未改，等口径）

- **补丁自愈 apply-failed**：`~/.dsh/tools/patch-claude-style-effort.mjs --check` 报 `NEEDS_REVIEW (no write) - unexpected hit pattern`，六条规则命中数全 0 —— dsh-claude-style/lib/client.js 已不是 0.20.1 的构建，补丁规则需重写。
- **Qwen-3.8-Max / Qwen-3.8-Flash 直连超时**（--timeout 90 仍 timeout），上游排队，非本地故障；QW 走 messages 协议，与本次 DSH 卡死无因果关系。
- **32 个信号**：探活 20 条记录里 50 条超过 72 小时未更新（含非 contract 型号）—— 属历史账本，不影响主力。
