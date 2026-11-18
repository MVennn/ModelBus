# 模型隐藏名单（隐藏 ≠ 删除）

> **一句话**：型号或 provider 不想出现在模型选择器里时，把它们写进 `~/.zcode/v2/model-hidden.json`，
> 两条投影（ZCode 兼容投影、DSH）都跳过；源配置一条不删，恢复是一条命令。

---

## 为什么要有这一层

订阅会停、会换、会恢复。删配置最省事，但删了以后要重建：providerId、access.apiKey、
每个型号的 properties / optionSpecs、alias map 里的 chain —— 全靠记忆重写，十次九次漏。
所以「暂时不用」一律走隐藏：**定义留在源里，只是不投影**。

- 源（不动）：`~/.zcode/v2/provider_config.json`、`~/.zcode/v2/model-alias-map.json`
- 投影（受影响，两处都读同一份名单）：
  - ZCode 兼容投影：`provider_config.json` 里被藏型号 `config.enabled=false` 且不进 `personalModelIds` / `modelOrder`；
  - DSH 投影：`~/.dsh/profiles/<profile>/cordis.patch.yml` 里 `llm-pi-ai` 的 `providers`
- 名单（新增，本机状态，不进仓库）：`~/.zcode/v2/model-hidden.json`

环境变量 `MODEL_HIDDEN_FILE` 可覆盖名单路径（测试、对照实验用）。

---

## 名单格式

```json
{
  "version": 1,
  "updatedAt": "2026-11-17T23:51:29+0800",
  "providers": {},
  "models": {
    "DeepSeek-4.1-Flash-OC": {
      "reason": "OC 订阅暂停续费（2026-11-17），先藏起来不删",
      "at": "2026-11-17T23:50:00+0800",
      "channel": "OC"
    }
  }
}
```

- `providers`：按 providerId 整组隐藏（组内型号全部不投影，该组从 DSH 里消失）。
- `models`：按型号 id 隐藏；`reason` / `at` / `channel` 只给人看，不参与决策。
- 值为 `false` 视作未隐藏；文件缺失 / 损坏 / 不是对象 → 一律当空名单，投影照常，不阻断。

---

## 命令

工具：`tools/model_visibility.py`（改完名单默认立刻先跑 `model_alias.py --slot auto --apply` 重写 ZCode 兼容投影，再跑 `dsh_sync.py --apply` 投 DSH；DSH 热加载，不用重启）。

```powershell
python tools/model_visibility.py list                      # 看隐藏了什么、投影里还剩什么
python tools/model_visibility.py hide --channel OC --reason "OC 暂停续费"
python tools/model_visibility.py hide --model DeepSeek-4.1-Flash-OC Beam
python tools/model_visibility.py hide --provider opencode-go-chat-free
python tools/model_visibility.py show --channel OC          # 恢复该渠道
python tools/model_visibility.py show --all                 # 清空名单（全部恢复）
```

- `--channel` 取 alias map 的**主渠道**（`models[<id>].channel`），不是「链上出现过」。
  `HY4-Flash-Free` 主渠道是 WB、链上有 OC 回落，按主渠道筛不会误伤它；按「链上含 OC」筛会把它一起藏掉，那是错的。
- `--dry-run` 只打印选中了谁；`--no-sync` 只写名单不投影。

---

## 投影侧怎么实现

`tools/model_alias.py`（解析只此一份：`hidden_sets()`）：

1. 写 `provider_config.json` 时，名单里的型号 `config.enabled=false`，且不写进
   `personalModelIds` / `modelOrder` —— ZCode 的选择器只认这两个数组，所以看不到它；
2. 整组隐藏的 provider 不写 provider 规则，也不写该组型号规则；
3. alias map 照旧写入 —— 隐藏的型号在 zgate 侧仍能直接点名调用。

`tools/dsh_sync.py`（调用同一个 `model_alias.hidden_sets()`，两边解析不会漂）：

1. `_hidden_sets()` 读名单 → `(hidden_providers, hidden_models)`；
2. `_apply_hidden()` 在两条真源（`compat` / `dsh`）都载入之后统一过滤，整组隐藏或组内清空的分组直接跳过；
   全被藏光时抛 `DshSyncError` 退出，不写空投影；
3. `_efforts_lost()` 跳过被隐藏的型号 —— 否则「源头有档位、投影没有」会被判成漂移，`--check` 永远报 1、每日同步白跑一轮；
4. `--export-inventory` **不过滤**：清单是 DSH 侧全集真源，隐藏只在投影那一步发生。

因此隐藏是幂等的：名单不变，`--check` = 0，同步不会反复重写。

---

## 自动任务

隐藏模型时通常要一起停掉每日重写模型表 / 守护 OC 免费代理的计划任务：

| 任务 | 与 OC 线的关系 | 隐藏时 |
|---|---|---|
| `ModelBus 模型同步`（每日 12:00） | 重写 provider_config / alias map / DSH 投影 | 停用 |
| `ModelBus-zen-relay-watchdog`（每 5 分钟） | 守护 8789 的 OC Zen 免费档代理 | 停用 |
| `ModelBus-zgate-watchdog`（登录 + 每分钟） | 网关本体，WB / GM / QD 线也靠它 | **保留** |

```powershell
Disable-ScheduledTask -TaskName "ModelBus 模型同步"            # 隐藏
Enable-ScheduledTask  -TaskName "ModelBus 模型同步"            # 恢复
```

停用不删除任务定义，触发器和动作都还在。

**停任务只是不再守护，已经起来的实例还活着。** zen-relay 是 `bun providers/opencode-zen/zen-relay/server.js` 起的 8789 监听，要单独停：

```powershell
Get-CimInstance Win32_Process -Filter "Name='bun.exe'" | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Get-NetTCPConnection -State Listen | Where-Object LocalPort -eq 8789   # 无输出 = 已关
```

2026-11-17 那次停的就是它（PID 18828）；watchdog 已停，所以不会再被拉起来。

> 2026-11-18 补：此前「隐藏只作用于 DSH」是当时的口径，ZCode 仍收到 18 个 OC 型号；现已改成两条投影共用同一份名单（`model_alias.hidden_sets()`），ZCode 侧同样看不到被藏型号。

---

## 已落地的一次实例（2026-11-17）

OC（OpenCode Go）订阅暂停续费，按主渠道 `OC` 隐藏 18 个纯 OC 型号：

```powershell
python tools/model_visibility.py hide --channel OC --reason "OC 订阅暂停续费（2026-11-17），先藏起来不删"
```

结果：DSH 投影从 3 组 29 个型号降到 3 组 11 个（主力 2 / 免费 2 / 省钱 7），`DeepSeek-4.1-Flash-OC` 一并消失。
保留的都是主渠道为 WB / GM / QD 的型号：`DeepSeek-4.1-Flash`（WB→QW）、`Gemini-4-Hydrogen`（GM）、
`HY4-Flash-Free`（WB）、`HY4` / `GLM-5.3-Flash` / `MiniMax-M3.1-Flash` / `HY4-Flash` / `Space-Bunny`（WB）、
`Qwen-3.8-Max` / `Qwen-3.8-Flash`（QD）。

恢复：

```powershell
python tools/model_visibility.py show --channel OC
Enable-ScheduledTask -TaskName "ModelBus 模型同步"
Enable-ScheduledTask -TaskName "ModelBus-zen-relay-watchdog"
```

---

## 边界

- **两条投影共用一份名单**：ZCode 侧的等价物是 `config.enabled=false` + 不进 `personalModelIds`，
  由 `model_alias.py` 在写盘时统一施加；名单只有 `model-hidden.json` 一个开关，不会出现两处漂移。
- **至少留一个 provider**：全藏光时 `dsh_sync.py` 直接报错退出，不会写出 DSH 无模型可选的 patch。
- **不是权限控制**：隐藏只影响投影，别名仍能被 `/v1/chat/completions` 直接点名调用（zgate 侧没变）。
  要真正拦住调用，得在 alias map 或渠道策略里做，那是另一层。

---

## 验证

```powershell
python tools/model_visibility.py list                  # 名单 + 各组可见数
python tools/dsh_sync.py --check                        # exit 0 = 投影与名单/源配置一致
Select-String -Path "$env:USERPROFILE\.dsh\profiles\desktop\cordis.patch.yml" -Pattern "DeepSeek-4.1-Flash-OC"  # 无命中
```

相关：[DSH-FIRST.md](DSH-FIRST.md)（DSH 主宿主与投影口径）、[MODEL-ALIAS.md](MODEL-ALIAS.md)（主渠道与回落链）、[MAINTENANCE.md](MAINTENANCE.md)。
