> **一句话**：2026-11-05（Asia/Shanghai）每日模型同步在调度链上尚未触发、尚未写入 —— 排查时点 11:53:56 未到 12:00 触发点，今天零同步产物。

# 调度链排障分片 · sync-scheduler

## 结论

**今天（2026-11-05）的触发/写入没有发生**：当前 `2026-11-05 11:53:56 +08:00`，两条触发线（Windows 计划任务 `\ZcodeAIModels 模型同步`、ZCode automation `automation-3e2f8a53-b408-4bf8-90ff-4a331a721f5c`）均定在每天 **12:00**，触发点尚未到达。**最后一次触发** = 2026-11-04 12:00:00（ZCode `automation_runs` 为 `dispatched / succeeded`）/ 2026-11-04 18:49:06（Windows 计划任务 `LastTaskResult=0`）；**最后一次写入产物收尾** = 2026-11-04 20:32:56。**失败点**不在今天，而在历史上 8 次 `skipped`，`error=computer_asleep_or_app_not_running`（机器睡眠或 ZCode App 未运行），以及本会话 Windows 任务查询接口报 `0x80070003` 导致 `LastRunTime/LastTaskResult/NextRunTime` 需由 lead 一手证据补齐。

## 进度清单

- [x] 判定委派闸门（主代理已派 3 路 task-1/2/3；本路剩余委派层级 0；单一写域冲突；依赖链必须串行 → 不再下派）
- [x] 读 `ZcodeAIModels/AGENTS.md` 与工作区根 `AGENTS.md`
- [x] 核 codegraph 索引状态（本会话实测 `Not initialized`，按 §3 退回 glob / grep / read）
- [x] 枚举 `sync-models.ps1` / `sync-models.vbs` 与调度关键词引用
- [x] 查 Windows 计划任务：LastRunTime / LastTaskResult / NextRunTime / 启用状态
- [x] 查 `~/.zcode/workspace/` 下 `default` 与 `179*` 自动化会话绑定
- [x] 查 2026-11-05 触发时间点与写入产物时间戳
- [x] 查机器开关机 / 事件日志，判定触发时刻是否在线
- [x] 汇总结论并写本分片
- [x] `team_task_update` 标 task-1 complete + `send_message` 回报 lead

> **阶段：调度链验收 ✅**
> 两条触发线、12:00 时间点、11-04 最后一次成功、8 次历史跳过均已落到原始输出；分片已落盘并回执 lead。

## 证据路径

| # | 路径 | 作用 |
|---|---|---|
| 1 | `~/.zcode/v2/tasks-index.sqlite` → `automation_runs` / `automations` / `tasks` | ZCode 12:00 自动化触发记录、会话绑定、cron 绑定 |
| 2 | Windows 计划任务 `\ZcodeAIModels 模型同步`（lead 一手 `schtasks /Query /FO LIST /V`） | 每天 12:00:00 触发；上次 11-04 18:49:06 结果 0；下次 2026/11/5 12:00:00 |
| 3 | `sync-models.vbs`、`sync-models.ps1` | 计划任务动作 `wscript.exe` → 无窗口拉起五段式 PS1 |
| 4 | `%LOCALAPPDATA%/ZcodeAIModels/_last-sync.txt` | 结构化摘要：最后一次同步时间 / 结果 / 报告 / 日志 |
| 5 | `%LOCALAPPDATA%/ZcodeAIModels/logs/sync-*.log` | 同步脚本运行日志（最后一次 11-04 20:32:56） |
| 6 | `docs/reports/MODEL-SYNC-*.md` | 报告产物（最新 11-04 20:32:56） |
| 7 | `docs/MAINTENANCE.md:245`、`PROGRESS.md:2070`、`CHANGELOG.md:36` | 每天 12:00 与 `automation-3e2f8a53-*` 的文档口径 |
| 8 | `~/.zcode/workspace/{default,1792763054934-*,1793153843780-*}` | 自动化会话目录实况 |
| 9 | Windows `System` 事件日志（Id 12/13/1074/6005/6006） | 11-05 开关机时间线 |
| 10 | `ZcodeAIModels/evidence/agent-sync-scheduler.md` | 本分片 |

## 关键原始输出 / 时间戳

### 1. 排查时点（未到 12:00 触发点）

```text
SAMPLE_NOW=2026-11-05 11:53:56 +08:00
LOCAL_TZ=China Standard Time
```

### 2. Windows 计划任务（lead 一手证据；本路查询接口报错原样保留）

```text
任务: \ZcodeAIModels 模型同步
动作: wscript.exe sync-models.vbs → powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File sync-models.ps1
上次运行时间: 2026/11/4 18:49:06    上次结果: 0
下次运行时间: 2026/11/5 12:00:00    计划: 每天 12:00:00
```

本会话直接查询同一对象的原始报错（不美化）：

```text
schtasks : ERROR: The system cannot find the path specified.
Get-ScheduledTask : The system cannot find the path specified. HRESULT 0x80070003
TaskScheduler/Operational: IsEnabled=False
Schedule 服务: Name=Schedule Status=Running StartType=Automatic
```

静态入口（`sync-models.vbs:3-17`、`sync-models.ps1:4-9,33-45,205-207,315-323`）：

```text
' 计划任务的动作指向本文件（wscript.exe），而不是 powershell.exe
ps1 = "<repo>\sync-models.ps1"
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & ps1 & """"
shell.Run cmd, 0, False
---
ZcodeAIModels 每日模型同步（Windows 计划任务入口）
迁移自 DeepSeekRuntime 的定时任务（原 schedule-4467b892-8205-44ec-8e03-fd0f018c1ab4）。
移到这里的原因：DSH 的 cron 只在 DSH 运行时才触发，关着就跳过；
$STAMP = Get-Date -Format "yyyyMMdd-HHmmss"
$SUMMARY = Join-Path $STATE_DIR "_last-sync.txt"
```

### 3. ZCode automation_runs（只读 SQLite，本路抽样 + lead 全表核验）

```text
DB=~/.zcode/v2/tasks-index.sqlite   CANDIDATE_TABLES=11
TABLE automation_runs COLS=run_id,automation_id,workspace_key,scheduled_at,trigger,model_selection,dispatch_status,outcome,session_id,error,attempts,created_at,updated_at   COUNT=25
TABLE automations COUNT=0
MATCH automation_runs needle=automation-3e2f8a53 rows=4
  ('automation-3e2f8a53-b408-4bf8-90ff-4a331a721f5c:1792641600000', 'automation-3e2f8a53-b408-4bf8-90ff-4a331a721f5c', '<repo>', 1792641600000, 'schedule', ..., 'dispatched', 'succeeded', 'session_3d61e6fc685347edf7c32bc640f55f7b', None, 0, 1792641619656, 1792641851847)
  ('...:manual:e4e80b96-...', ..., 1792683909822, 'manual', ..., 'dispatched', 'succeeded', 'session_55b95bcb-26c8-4c59-b1f2-98edc23af497', None, 1, ...)
--- lead 全表核验 ---
MAX_RUN_SCHEDULED=2026-11-04 12:00:00   dispatch=dispatched outcome=succeeded  session=sess_fc154a30...
11-02 / 11-03 / 11-04 连续三天 12:00 succeeded
历史 8 次 scheduled skipped  error=computer_asleep_or_app_not_running
TASKS_WITH_CRON=0   当前 ZCode/Electron 进程=0（仅 DeepSeekRuntime）
```

文档口径（`docs/MAINTENANCE.md:245`）：

```text
| **每天 12:00（定时任务 `automation-3e2f8a53-b408-4bf8-90ff-4a331a721f5c`）** | 五段顺序：① go_model_sync.py --apply … ⑤ sync_report.py --write --push |
PROGRESS.md:2070  - [x] 更新每天 12:00 自动化 prompt（automation-3e2f8a53-b408-4bf8-90ff-4a331a721f5c）
CHANGELOG.md:36   - 日常 12:00 自动化、docs/TOOLS.md、docs/MAINTENANCE.md 同步更新
```

### 4. 最后一次写入产物（全部停在 11-04，今天零新增）

```text
--- %LOCALAPPDATA%/ZcodeAIModels/_last-sync.txt ---
时间: 2026-11-04 20:32:56
结果: 成功
分组: 主力 2 / 免费 7 / 省钱 10
报告: <repo>\docs\reports\MODEL-SYNC-20261104-2032.md
日志: %LOCALAPPDATA%\ZcodeAIModels\logs\sync-20261104-203211.log
--- 目录实况 ---
LOG_COUNT=5  最新 2026-11-04 20:32:56 sync-20261104-203211.log
REPORTS_DIR 最新 2026-11-04 20:32:56 MODEL-SYNC-20261104-2032.md
2026-11-05 同步日志 / 报告: 0 个
```

lead 产物链补充：`provider_config.json` 2026-11-04 20:45:09、`model-alias-map.json` 2026-11-04 20:32:55、`model-sync-state.json` 2026-11-04 20:32:56；11-05 仅有 `~/.zcode/cli/config.json` 等 3 个插件文件（01:20–01:23）被写，与同步无关。

### 5. 触发点在线性 / 开关机时间线

```text
LastBootUpTime=11/05/2026 10:19:25    LocalDateTime=11/05/2026 11:46:56
2026-11-05 02:49:21 Id=1074  User32       | 发起关闭电源
2026-11-05 02:50:05 Id=6006  EventLog     | The Event log service was stopped.
2026-11-05 02:50:10 Id=13    Kernel-General | operating system is shutting down
2026-11-05 10:19:25 Id=12    Kernel-General | operating system started
2026-11-05 10:19:51 Id=6005  EventLog     | The Event log service was started.
```

判定：11-05 00:00–02:50 在线、02:50–10:19 关机、10:19 之后在线；**12:00 触发点在未来**，因此「机器当时关机」不构成今天的失败原因。11-04 12:00 那次机器在线（`succeeded`）。

### 6. `.zcode/workspace/` 会话绑定

```text
--- WORKSPACE ~/.zcode/workspace ---
  d----- 2026-10-23 21:44:14 1792763054934-c7ff280e-0c41-4d0d-8fb8-99432b3752a0
  d----- 2026-10-28 10:36:28 1793153843780-8d1b872c-6392-450e-9741-771e85cda239
  d----- 2026-10-19 13:20:45 default
  d----- 2026-11-03 19:00:25 draft-10e6273c-*（及另外 5 个 draft-*, 11-02）
WS default              ITEM_COUNT=29   文件 mtime 全部 2026-10-19（oc-*.js / PROGRESS*.md）
WS 1792763054934-*       ITEM_COUNT=0   SMALL_FILE_COUNT=0
WS 1793153843780-*       ITEM_COUNT=0   SMALL_FILE_COUNT=0
tasks 表: 1792763054934-* → session_dba2595d03da6822a0bdffef0cea8c77（空标题）
tasks 表: 1793153843780-* → session_f7e5efaf47525b2d9f610d2cc5b3c6ff（「每天到点弹 cmd 窗口」类会话）, session_5ced463561372fc1dd417c3ab3afc0d3
tasks 表: <repo> → session_3d61e6fc685347edf7c32bc640f55f7b（12:00 自动收录）, session_55b95bcb-..., session_880c82c2-...
automations 表 COUNT=0；tasks.cron_automation_id 无绑定；grep automation-session-binding 命中仅历史审查产物
```

判定：`default` 与两个 `179*` 目录均无 2026-11-05 写入，`179*` 为空目录；12:00 模型同步的会话绑定落在 `workspace_key=<repo>` 的 `automation_runs.session_id` 上，未发现指向 `179*` 的活跃绑定。

### 7. 索引状态（按 AGENTS.md §3 退回普通检索）

```text
CodeGraph Status  [i] Project: <workspace>
[!] Not initialized   [i] Run "codegraph init" to initialize
```

任务书记载的 `unable to open database file` 与本会话实测 `Not initialized` 都指向索引不可用；未执行 `codegraph init`，全程 glob / grep / read。

## 失败点

| 位置 | 原始输出 | 性质 |
|---|---|---|
| 今天 12:00 触发点 | `SAMPLE_NOW=2026-11-05 11:53:56 +08:00` < `NextRunTime=2026/11/5 12:00:00` | 未到点，非失败 |
| 历史 8 次 scheduled | `error=computer_asleep_or_app_not_running`, `outcome=skipped` | 真正的历史失败点：机器睡眠 / ZCode App 未运行 |
| 本会话 Windows 任务查询 | `HRESULT 0x80070003` / `ERROR: The system cannot find the path specified.` / `TaskScheduler/Operational IsEnabled=False` | 排查阻碍，已由 lead 一手 `schtasks /Query /FO LIST /V` 补齐 |
| 启动项 | `ZcodeAIModels zgate.lnk → zgate.exe serve` | 这是 zgate 常驻网关自启，不是模型同步计划任务，勿混 |

## 执行异常与修复（进度可见留痕）

```text
第一次 team_task_update(task-1, expected_revision=1, action="complete") 失败：
  ToolCallError: task mutation requires its owner or Team Lead
原始 team_task_get: id=task-1 revision=1 status=pending owner=<none>
修复：team_task_update(action="claim") → revision=2 status=in_progress owner=sync-scheduler
      team_task_update(expected_revision=2, action="complete") → revision=3 status=completed owner=sync-scheduler
send_message(target="lead") → {"sent":true}
分片复查：totalLines=178，首行即结论句。
```

对应清单项已标回「修复 task-1 无 owner 并完成 complete + 回报 lead」并勾掉；分片、任务板、lead 回执三方一致。

## 未解决项

- [待补: Windows 计划任务 `\ZcodeAIModels 模型同步` 的完整 XML（StartBoundary / Enabled / WakeToRun / StartWhenAvailable / Principal）在本会话未导出；`LastRunTime / LastTaskResult / NextRunTime` 采用 lead 一手证据]
- [待补: 12:00 之后本次是否真正触发并执行成功，需到点后复查 `automation_runs` 新行、`_last-sync.txt`、`logs/sync-20261105-*.log`、`docs/reports/MODEL-SYNC-20261105-*.md`]
- [待补: 11-04 12:00（ZCode automation）、18:49:06（Windows 计划任务）、20:32:56（五段式产物收尾）三者是否同一次流水线的不同阶段，调度链证据未串到同一 `run_id`]
- [待补: `automations` 表 0 行而 `automation_runs` 有 25 行的口径差异（任务定义已迁至 Windows 计划任务 / 或定义存于别处），本路只读未改配置]