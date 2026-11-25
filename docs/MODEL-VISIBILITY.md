# 模型隐藏名单（可逆的系统级开关）

> **一句话**：`.zcode/v2/model-hidden.json` 是隐藏的**单一真值开关**——`hide` 让目标在
> 选择器投影和 zgate 调用链里一起「消失」（连 alias map 条目都不写，zgate 点名不到）；
> `show` 后从源重算，条目和跳自动插回。隐藏不删源配置，全程可逆、幂等。

---

## 两级隐藏：型号/组（投影）与渠道（系统开关）

名单有三段，作用深度不同：

| 段 | 粒度 | hide 的效果 | show 的效果 |
| --- | --- | --- | --- |
| `channels` | 渠道级**真开关** | 该渠道的所有跳从 alias chain 里移除；纯该渠道的型号整条从 alias map 消失，zgate 侧也点名不到 | 从源重算，跳自动插回 |
| `models` | 单个型号（投影） | `config.enabled=false` 且不进 personalModelIds/modelOrder，选择器看不到；alias 条目照建 | 恢复投影 |
| `providers` | 整组（投影） | 整组不写投影规则 | 恢复整组 |

关键区别：`--model`/`--provider` 只是「选择器看不见」（zgate 仍能点名调用）；
`--channel` 是**系统级真开关**——它让该渠道在调用链里彻底消失，等于「和没了这个渠道一样」。
2026-11-18 按用户要求把 `--channel` 正规化成这个语义（此前只按主渠道藏型号，OC 跳仍留在
HY4 等型号的 chain 里，zgate 照样回落走 OC —— 与「隐藏 OC」的直觉相悖）。

命令 `hide --channel OC` 同时写 `channels` 段和按主渠道筛出的型号段，保证「选择器看不到」
与「调用链走不到」一致；`show --channel OC` 对称清除两段。

- 源（不动）：`~/.zcode/v2/provider_config.json`、`~/.zcode/v2/model-alias-map.json`
- 名单（唯一真值，本机状态，不进仓库）：`~/.zcode/v2/model-hidden.json`
- 消费方：`model_alias.py`（写 ZCode 兼容投影 + alias map）、`dsh_sync.py`（写 DSH 投影）、zgate（热加载 alias map）

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
  },
  "channels": {
    "OC": { "reason": "OC 整渠道关闭：所有 chain 里的 OC 跳移除", "at": "2026-11-18T16:00:00+0800" }
  }
}
```

- `channels`：渠道级真开关（键大写）。关掉后该渠道所有跳从 alias chain 移除，纯该渠道型号整条消失；
  `hide --channel`/`show --channel` 维护这一段。
- `providers`：按 providerId 整组隐藏（组内型号全部不投影，该组从 DSH 里消失）。
- `models`：按型号 id 隐藏；`reason` / `at` / `channel` 给人看（`channel` 供 `show --channel` 反查型号）。
- 值为 `false` 视作未隐藏；文件缺失 / 损坏 / 不是对象 → 一律当空名单，投影照常，不阻断。
- 老名单没有 `channels` 段 = 没有渠道开关，行为与旧版完全一致（向后兼容）。

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

- `hide --channel OC` 是**渠道级真开关**：写 `channels.OC`，同时把主渠道为 OC 的型号写进 `models`
  做选择器隐藏；重投影后 alias map 里所有 OC 跳被移除、纯 OC 型号整条消失，zgate 热加载立即生效（不用重启）。
- `--channel` 按 alias map 的**主渠道**（`models[<id>].channel`）筛型号，不是「链上出现过」；
  但渠道开关本身作用于**所有 chain 跳**（含回落跳）。所以 `HY4-Flash-Free`（主渠道 WB、链上有 OC）
  不会被写进 `models`，但它的 OC 回落跳会被 `channels.OC` 移除，chain 收窄成 WB-only —— 正是「隐藏 OC」的本意。
- `show --channel OC` 对称清除 `channels.OC` 与对应型号，重投影后跳自动插回（靠 alias 条目里的 `full_chain` 快照，见下）。
- `--dry-run` 只打印选中了谁；`--no-sync` 只写名单不投影。

---

## 投影侧怎么实现

解析集中在 `tools/model_alias.py`：`hidden_sets()` 给型号/provider 集合，`hidden_channels()` 给渠道开关集合。
两者都遵循「文件缺失 / 损坏 → 空集合、值为 false 视作未隐藏」的降级纪律。

**渠道级真开关（`channels`）**——在 `model_alias.py` 的 `--apply` 写盘阶段：

1. `hidden_channels()` 读开关；`chain_without_hidden_channels()` 对每条型号过滤掉开关渠道的跳；
2. 过滤后 chain 变空的型号整条跳过：不写 provider_config 规则、不写 alias 条目、不写 legacy —— zgate 侧点名不到；
3. 非空型号用过滤后的 chain 同步改写头字段（channel/upstream/price）与 fallbacks，保证 chain 与条目自洽；
4. **可逆的关键**：写 alias 条目时把隐藏前的完整链存进 `full_chain` 字段；下一轮 `classify()`
   重建时优先读 `full_chain`，所以 `show` 后被藏的跳自动插回。zgate 的 Go 结构没有这个字段，
   `json.Unmarshal` 自动忽略，不影响运行时；它纯粹是「开关可逆」的本地快照。

**型号/provider 级（`models`/`providers`）**——投影过滤：

1. 写 `provider_config.json` 时，名单里的型号 `config.enabled=false`，且不写进
   `personalModelIds` / `modelOrder` —— ZCode 的选择器只认这两个数组，所以看不到它；
2. 整组隐藏的 provider 不写 provider 规则，也不写该组型号规则。

`tools/dsh_sync.py`（调用同一个 `model_alias.hidden_sets()`，两边解析不会漂）：

1. `_hidden_sets()` 读名单 → `(hidden_providers, hidden_models)`；
2. `_apply_hidden()` 在两条真源（`compat` / `dsh`）都载入之后统一过滤，整组隐藏或组内清空的分组直接跳过；
   全被藏光时抛 `DshSyncError` 退出，不写空投影；
3. `_efforts_lost()` 跳过被隐藏的型号 —— 否则「源头有档位、投影没有」会被判成漂移，`--check` 永远报 1、每日同步白跑一轮；
4. `--export-inventory` **不过滤**：清单是 DSH 侧全集真源，隐藏只在投影那一步发生。

因此隐藏是幂等的：名单不变，chain 过滤结果稳定，`--check` = 0，同步不会反复重写。

**验证过的可逆循环**（临时副本连续 apply 四次）：基线 HY4=`[WB,OC,OC]` → hide 后 `[WB]`
（full_chain 存完整链）→ show 后 `[WB,OC,OC]` 自动插回 → 再 hide 又正确。

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

## 已落地的一次实例（2026-11-17，2026-11-18 升级为渠道开关）

OC（OpenCode Go）订阅暂停续费。最初按主渠道 `OC` 藏了 18 个纯 OC 型号（仅投影级）；
2026-11-18 用户要求「隐藏要和消失没区别、开启能插回」后，`--channel` 升级为系统级开关，
`channels.OC` 一开，连 HY4 等型号链上的 OC 回落跳也一并移除。隐藏命令不变：

```powershell
python tools/model_visibility.py hide --channel OC --reason "OC 订阅暂停续费（2026-11-17），先藏起来不删"
```

结果：DSH 投影从 3 组 29 个型号降到 3 组 11 个（主力 2 / 免费 2 / 省钱 7），`DeepSeek-4.1-Flash-OC` 一并消失。
保留的都是主渠道为 WB / QD 的型号：`DeepSeek-4.1-Flash`（WB→QW）、
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

- **单一真值**：名单只有 `model-hidden.json` 一个开关，ZCode 侧 `config.enabled=false`、DSH 投影、
  alias chain 过滤都由 `model_alias.py` 写盘时统一施加，不会出现两处漂移。
- **至少留一个 provider**：全藏光时 `dsh_sync.py` 直接报错退出，不会写出 DSH 无模型可选的 patch。
- **渠道开关 vs 型号隐藏的深度不同**：`--model`/`--provider` 只让选择器看不见（zgate 仍能点名调用）；
  `--channel` 是系统级真开关——连 alias map 条目都不写，zgate 侧点名不到。要「和消失没区别」用 `--channel`。
- **可逆靠 full_chain 快照**：hide 把截断链写进 alias，同时留 `full_chain` 完整快照；show 后 `classify()`
  优先读快照重建，被藏的跳自动插回。没有这个快照的话，show 只能读回截断态，跳会永久丢失。

---

## 验证

```powershell
python tools/model_visibility.py list                  # 名单 + 各组可见数
python tools/dsh_sync.py --check                        # exit 0 = 投影与名单/源配置一致
Select-String -Path "$env:USERPROFILE\.dsh\profiles\desktop\cordis.patch.yml" -Pattern "DeepSeek-4.1-Flash-OC"  # 无命中
```

相关：[DSH-FIRST.md](DSH-FIRST.md)（DSH 主宿主与投影口径）、[MODEL-ALIAS.md](MODEL-ALIAS.md)（主渠道与回落链）、[MAINTENANCE.md](MAINTENANCE.md)。
