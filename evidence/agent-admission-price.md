# C 路验收记录：收录价格口径正规化（m01046 / m01047）

- 任务书：`51d15c47-4f36-41bb-a094-9f414628ff06`「审查收录价格口径正规化」，写域 `tools/model_alias.py`。
- 用户原话 m01046：「关于模型收录判断是不是得统一一下了…按照deepseek的标准走就好…关于价格转换我统一成了workbuddy的积分。你看看怎么改吧」；m01047：「还是按照之前的逻辑，只是正规化一点」。含义：行为完全不变，只把散落/隐式口径变显式、集中、可维护。
- 线程结局：修完注释顺序瑕疵后仍未落分片，lead 于 19:30 `interrupt_agent` accepted=true 停止；写域代码由 lead 独立复核通过，本记录补写。
- 真实数字：pre sha12 `87bf337b0bb5` → 首次落地 `6e7d07f037b7` → 修注释 `be1a6224f4de`；101689 B / 2168 行 / 无 BOM / LF。

## 改了什么（零行为改动）

1. `:241-259` 新增常量块：`DEEPSEEK_BASELINE_CREDITS = 0.11`、`LOW_MAX = DEEPSEEK_BASELINE_CREDITS`（原 `LOW_MAX = 0.11` 改为引用基准）、`QD_FACTOR = 0.86`、`USD_PER_WB_CREDIT = 3.409`。注释写明 DeepSeek 标准两层（价格基准 0.11 + 竞技榜 SCORE_MIN_INTEL）、各家价格一律统一折算为 WorkBuddy 积分后再比较、`OC_PRICES` 是「已折算完的结果表」运行时零折算、`price_of()` 是唯一取价出口、`QD: price_factor × QD_FACTOR` 是唯一运行时折算。
2. `:293-298` Gemini 4 Argon 注释顺序修正：先给 `input 2 / output 10（USD per 1M），按 1:1 混合 (2+10)/2 ÷ 3.409 = 1.76 积分。` 再写 `上式 ÷ 3.409 即 ÷ USD_PER_WB_CREDIT…`；`"gemini-4-argon": {"flat": 1.76},` 数值未动。
3. 配套口径：`docs/MODEL-ALIAS.md` `d3aa73e5c948→de0e087dea23` 插「2026-11-09 现行口径校准」（主力=DeepSeek-4.1-Flash 0.11 + 4 条 CP Gemini 0.00；HY4 0.29 与 Qwen3.8-Max 0.43 下沉省钱组；省钱组 12 条）；`PROGRESS.md:1302` 改为「手动改 `DEEPSEEK_BASELINE_CREDITS`（`LOW_MAX` 现引用该基准）」。

## 行为等价证明（真实输出）

`PYTHONIOENCODING=utf-8 python tools/model_alias.py --check --arena` exit=0，输出 `3994B` 与 `.work/verify-alias-check-before-utf8.txt` 逐字相等 `equal=true`，末行：

```
无漂移：现有 alias map 与按当前价格源重算的结果一致
```

stderr 两行 WARN（与改前一致，属既有真实状态非回归）：`WARN: cn:hy4-preview-f 的 credits/list_rate 都缺失，按同族挂牌价 0.29 计费（不当作免费；见 tools/model_alias.py wb_prices）`、`WARN: QD 价格源不可用（127.0.0.1:8790: <urlopen error [WinError 10061] 由于目标计算机积极拒绝，无法连接。>），已回落到上次成功的倍率快照`。

`python -m py_compile tools/model_alias.py` exit=0。`git diff -- tools/model_alias.py` 共 362 行，本轮增量仅常量/注释（`+DEEPSEEK_BASELINE_CREDITS = 0.11` / `-LOW_MAX = 0.11` → `+LOW_MAX = DEEPSEEK_BASELINE_CREDITS` / `+USD_PER_WB_CREDIT = 3.409`），其余为他人既有改动（`+    # 旗舰先行（用户 2026-11-09 从主力下沉…）` 等），数值/阈值/分支/执行顺序/输出格式一字未变。

一次假失败已排除：run_code 传空 process.env 报 `RuntimeError: Could not determine home directory.`（`tools/model_alias.py:73 DEFAULT_ARENA = Path.home() / ".zcode" / "v2" / "arena-main.json"`），改用 ops_bash 宿主完整环境即通过，属调用环境问题非代码回归。
