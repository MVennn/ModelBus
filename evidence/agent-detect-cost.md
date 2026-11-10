# A 路验收记录：省掉零收益的骤降探活（m01007）

- 任务书：`ea8ca161-0cc9-40c8-804a-f226a1ed084d`「省掉零收益的骤降探活」，写域 `providers/workbuddy/workbuddy_fetch_pricing.py`。
- 线程结局：running 40+ 分钟未落分片，lead 于 2026-11-09 19:30 发 `interrupt_agent` accepted=true 停止；写域代码由 lead 独立复核通过，本记录按 §7 验收硬口径补写。
- 真实数字：pre sha12 `e9f8fae65ec0` → 中间态 `51463ff789eb` → post sha12 `b8c9b0b17469`；17372 B / 406 行 / 无 BOM / LF（CR=0）。

## 改了什么

1. 默认路径改为「列表骤降时零请求保留旧价、照常写表」：`workbuddy_fetch_pricing.py:48` docstring、`:334 if old and len(rows) < len(old) * 0.7:`、`:377 else:` 回全部旧行、`:383-385` 打印 `本轮未发探活请求，省 N 次模型调用（旧价全保留，连续多轮残缺再人工确认）`。
2. 显式开关：`:278-279 --probe` 供人工确认真实下架（逐个最小对话请求）；`:280-281 --no-probe` 旧语义保留（骤降直接拒写退出码 2），`:344 if args.no_probe and not args.force:`；`:348 elif args.force:`；`:351 elif args.probe and not args.dry_run:` —— 修复了 `--probe --dry-run` 会真实发请求的回归，报告模式永远零请求。
3. 今日实证依据：12:00 那轮 19 次 WB 逐个探活对最终 `wb_pricing.json（39 条）` 零影响（全按保留），故默认砍掉。

## 怎么验证（真实输出）

`python -m py_compile providers/workbuddy/workbuddy_fetch_pricing.py` exit=0。

离线夹具 `.work/verify-wb-pricing-offline.py`（固定 20 条上游 / removed=19 / monkeypatch fetch_models+probe_alive 不触网）`python .work/verify-wb-pricing-offline.py` 真实输出：

```
fixture: real wb_pricing.json rows=39; upstream returns 20 rows (triggers 骤降 branch)
  [default] probe_calls=0/exp0 exit=0/exp0 rows=39/exp39 zero_msg=True => PASS
  [--dry-run] probe_calls=0/exp0 exit=0/exp0 rows=39/exp39 zero_msg=True => PASS
  [--probe] probe_calls=19/exp19 exit=0/exp0 rows=39/exp39 zero_msg=False => PASS
  [--probe --dry-run] probe_calls=0/exp0 exit=0/exp0 rows=39/exp39 zero_msg=True => PASS
  [--no-probe] probe_calls=0/exp0 exit=2/exp2 rows=39/exp39 zero_msg=False => PASS
  [--no-probe --dry-run] probe_calls=0/exp0 exit=0/exp0 rows=39/exp39 zero_msg=False => PASS
RESULT: ALL_PASS
```

行为等价：默认路径产物 39 条与今日 12:00 真实 `wb_pricing.json` 逐对象全等；`normalize(20)` 往返精确相等；零请求证明见 `evidence/agent-detect-quality.md` 与 `.work/verify-zero-request-baseline.json`（model_probe.json / wb_pricing.json sha12 前后未变）。
