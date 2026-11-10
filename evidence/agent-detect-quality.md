# B 路验收记录：零请求复用探测信号（m01007 + hy4free 担心）

- 任务书：`83680d1c-59f3-4eee-aea1-fa44fea8ee83`「零请求复用探测信号」，写域 `tools/zgate-lifecycle/current-models.ps1`。
- 线程结局：inactive（40 分钟未动写域、未落分片），lead 按 §7 验收硬口径 `interrupt_agent` accepted=true 接管并完整实现。
- 真实数字：pre sha12 `087d1c591651` / 129 行 / 5207 B → post sha12 `c1492bdd6b00` / 265 行 / 11687 B；BOM=true / CR=0 保持（PS5.1 中文注释必须 BOM+LF）。

## 改了什么

1. 只读复用 `~/.zcode/v2/model_probe.json` 已采字段，新增三个零请求质量信号：`billing_suspect`（免费组 chain 上游反查 credit>0 + 显示名/上游名带 free 且 credit>0 兜底；去重键 id|upstream）、`stale_models`（严格判据「有 ok_at 且距今 >7 天 且本轮 status != ok」，无 ok_at 归 unknown 不硬判）、`slow_models`（ms>10000）。
2. 顶层补 `data_as_of`（alias map generated_at）/ `probe_as_of`（全表 checked_at 最大值）/ `probe_source`，原有 `total=22 / legacy_keys=94 / groups` 与 note 全保留；note 点名「历史事件 cn:hy4-preview-f 曾被判免费却累计扣 6601 积分，已按 0.29 计费修复；只告警、不删模型、不改价、不发请求」。
3. 解析统一用 `JavaScriptSerializer`（PS5.1 `ConvertFrom-Json` 大小写不敏感会把 `glm-5.3-flash` 与 `GLM-5.3-Flash` 判重复键）；候选 key 兼容 `qn:qiniu/conatus-free` 带渠道前缀。

## 怎么验证（真实输出）

`powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/zgate-lifecycle/current-models.ps1` exit=0，stdout 逐字：

```
真值视图已写入 %LOCALAPPDATA%/ModelBus/current-models.json  total=22  legacy_keys=94  billing_suspect=0  stale=0  slow=1
```

（stdout 中的本机用户目录按 `docs/SECRETS.md` 脱敏为 `%LOCALAPPDATA%`；其余逐字未改。）

生成 JSON 独立验收：`total=22 legacy_keys=94 groups={"主力":5,"免费":5,"省钱":12}`；`data_as_of=2026-11-09 13:58:58 probe_as_of=2026-11-09T12:01:49 alias_generated_at=2026-11-09 13:58:58 slot=auto`；`billing_suspect=0 stale_models=0 slow_models=1`；`slow_models[0]={"id":"cn:minimax-m3","display":"WB:CN-MiniMax-M3:0.25","ms":30031,"status":"ok"}`；`note_has_6601=true note_has_no_request=true`；`models=22 / upstreams=6 / children=3`。

脚本零网络调用审计：`urlopen=false / Invoke-WebRequest=false / Invoke-RestMethod=false / curl=false / Start-Process=false / /v1/chat=false / chat/completions=false`。

## 零新增推理请求证明

`.work/verify-zero-request-baseline.json` 基线对比（基线结构是嵌套 `file` 对象）：

- `~/.zcode/v2/model_probe.json` now `{bytes:48352, sha12:d379ca4d178b}` == baseline → UNCHANGED=true
- `F:/Project/ModelBus/providers/workbuddy/cache/wb_pricing.json` now `{bytes:14201, sha12:f39f306f1bcb}` == baseline → UNCHANGED=true
- `gateways/upstream/workbuddy/data/usage.json` 是网关运行态持续写（saved 19:04:22→19:26:22 / buckets 1217→1219 / total_q 42914→43084 / total_cr 15804.13→15808.66，delta_q=170 delta_cr=4.53）属会话与用户流量；本轮所有脚本只读它或不碰它，不算本轮发推理请求。教训：`usage.json` 的 `c`=completion tokens，真实扣费积分字段是 `cr`（`gateways/upstream/workbuddy/internal/usage/usage.go:67/77`）。

## hy4free 担心：记录里有，真凶不是 hy4free

本机聚合 usage.json buckets 按 model（零请求）：`hy4free q=2095 cr=0.00 cn=2062 桶=62 零积分桶=62`（62/62 全零 = 真免费，比 11-06 文档快照 1154 次/0.00 更强）；真凶是同族 `cn:hy4-preview-f`（显示名 HY4-Pre）`q=2462 cr=6601.08 cr/q=2.6812`。

文档硬证据：`CHANGELOG.md:83-84`「`cn:hy4-preview-f` 的 `credits` 是空字符串、`list_rate` 是 0，被判成免费；历史 2420 次请求实际扣了 6601 积分。」；`CHANGELOG.md:92-93`「`wb_prices()` 重写为两遍…`hy4-preview-f` 由 0.00 变 0.29」；`docs/MODEL-ALIAS.md:120-125`「`HY4-Free` 与 `HY4-Pre` 不是同类模型，不能合并」。已修（回填 0.29 + 不进免费组），本路 `billing_suspect` 守的正是「免费标签 vs 实际扣费」漂移复发。
