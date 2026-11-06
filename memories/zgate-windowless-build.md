# zgate 无窗产物的构建与守护

> **一句话**：zgate 必须按 GUI 子系统编译（`-H windowsgui`），构建入口只有
> `gateways/zgate/build.py`；别在 `gateways/zgate/` 里裸跑单包 `go build .` ——
> 它会把无窗版原地覆盖成控制台版，开机弹 cmd 窗口。

## 结论

| 事实 | 说明 |
|---|---|
| 无窗与否取决于 PE 头的 `Subsystem` | `2` = WINDOWS_GUI（无窗，设计要求）；`3` = CONSOLE（一启动就分配控制台窗口） |
| `-H windowsgui` 只在链接期生效 | 事后无法从源码判断，只能读产物 PE 头 → 所以编译后必须当场校验 |
| 回退真凶是**单包** `go build .` | 实测：`go build ./...`（多包）只编译不落盘、**不会**覆盖；`go build .`（单包）会原地覆盖 |
| 产物在 `.gitignore` 里 | `/gateways/zgate/*.exe` → 被覆盖后 **`git checkout` 救不回来**，只能带 flag 重编 |
| 快捷方式 `WindowStyle = 7` 不管用 | 「最小化」只对有窗口的程序有效，对控制台子系统程序**不等于隐藏** |
| 唯一构建入口 | `python gateways/zgate/build.py`（带 flag + 强制校验）；`--check` 只校验；`--cross-check` 交叉编译校验（Linux CI 上也生效，因为 `-H` 是 windows 链接器 flag） |

## agent 会话里起 zgate：只有 explorer 拉起能活

Windows **Job Object 会在 agent 会话结束时回收整棵进程树**。
实测 `nohup` / `setsid` / `Start-Process` 起的 zgate 都会随会话消失；
日志里表现为 `已启动` 之后**连「已退出」都没有**（被强杀，不是自己退的）。

活下来的办法：**用 explorer 拉起启动文件夹快捷方式**，父进程是 `explorer.exe`，
与登录自启同一条路径：

```
Start-Process explorer.exe -ArgumentList '"<启动文件夹>\ModelBus zgate.lnk"'
```

长期驻留靠**登录自启快捷方式**（`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\`），
不要靠 agent 起的进程。

## 自启三层与被 dsh 重启连带杀死（2026-11-06 实测）

| 事实 | 证据 / 说明 |
|---|---|
| 自启是**三层**，不是一层 | ① 启动文件夹 `ModelBus zgate.lnk`（Target=zgate.exe，Args=serve）；② 计划任务 `ModelBus-zgate`（LogonTrigger + PT30S）；③ 看门狗 `ModelBus-zgate-watchdog`（每 5 分钟，2026-11-06 已改 **PT1M**，动作 wscript → ensure-zgate.ps1） |
| 自启只在**登录那一刻**触发一次 | 它不是守护进程。登录之后任何一次「会话内 Start-Process / start-zgate.bat / swap-zgate.ps1」起的 zgate 都会顶替它，父链落到 dsh 的 Job Object 里 |
| dsh 重启为什么连坐 | dsh 退出时 TerminateJobObject 终止整棵子进程树；实测 13:27 被杀的那台，是 11:49 在会话里手工起的，不是 lnk 起的 |
| 自愈实测 | 13:30:46 看门狗拉起（13:30:49 日志「已启动」）；手动 Stop-Process 后 25s 由看门狗拉回。新 zgate 父进程是 Task Scheduler 下的 powershell，随后成孤儿，与 dsh 无关 |
| 结论 | 只要 zgate 由**登录自启 / 计划任务 / 看门狗**产生，重启 dsh 杀不到它；由会话产生就会陪葬 |
| 禁 | 会话里禁止 `Start-Process zgate.exe`、`start-zgate.bat`、`swap-zgate.ps1`。需要它起来用 `schtasks /run /tn ModelBus-zgate`（父链走 Task Scheduler）或等看门狗 |
| 秒级守护（尽力而为） | `%LOCALAPPDATA%\ZCodeGateway\zgate-daemon.ps1` + HKCU Run 键 `ModelBus-zgate-daemon`，登录时由 explorer 拉起、10s 轮询；实测该脚本从无控制台上下文（WMI Create / EncodedCommand）启动会秒退，只有交互式登录态能常驻，故看门狗仍是兜底 |

## 排错速查

```bash
# 产物是不是无窗版
python gateways/zgate/build.py --check

# 服务在不在
curl -s http://127.0.0.1:7871/health
gateways/zgate/zgate.exe status

# 有没有多余的控制台窗口
Get-Process conhost | Where-Object { $_.MainWindowTitle }
```

机制见 `docs/PITFALLS.md` §20，排错步骤见 `docs/TROUBLESHOOTING.md` §16，
构建命令正本见 `docs/MAINTENANCE.md` §8.1。
