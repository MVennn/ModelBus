> **一句话**：zgate 必须挂在计划任务父链上自启，换版必须走 `build.py --candidate` + `tools/zgate-lifecycle/restart-zgate.cmd` 受控流程；在 CMD/DSH 会话里直接拉起的实例会随会话树一起被回收。

# ZGATE-LIFECYCLE.md — zgate 生命周期正本

> **正本声明**：本篇是 zgate 进程生命周期（自启父链、换版、回滚、存活验证、故障定位）的唯一正本。
> 日常维护命令表见 [MAINTENANCE.md](MAINTENANCE.md) §8，故障现象与排查见
> [TROUBLESHOOTING.md](TROUBLESHOOTING.md) §16，编译期无窗坑见 [PITFALLS.md](PITFALLS.md) §20，
> 构建与工具清单见 [TOOLS.md](TOOLS.md)，运行架构与端口见 [ARCHITECTURE.md](ARCHITECTURE.md)，
> 凭据变量名见 [SECRETS.md](SECRETS.md) §3.5，文档单一正本规则见 [DOC-RULES.md](DOC-RULES.md)。

---

## 0. 一页速查

| 场景 | 唯一正确做法 | 禁止做法 |
|---|---|---|
| 开机自启 | 计划任务 `\ModelBus-zgate-hidden`（AtLogOn）→ `launch-zgate.vbs` → `start-zgate-nw.ps1` | `Start-Process`、`cmd /c`、HKCU Run、Startup 快捷方式 |
| 进程掉线兜底 | 计划任务 `\ModelBus-zgate-watchdog`（每 1 分钟）→ `ensure-zgate.vbs` → `ensure-zgate.ps1` | 会话内起常驻 PowerShell 守护 |
| 改了 `zgate.json` 策略 / 空闲 / 窗口 / 上游 base / 凭据 | `POST /admin/reload`（热加载配置与 `ApplyConfig(children)`，不换二进制） | 为了改策略去重启整个实例 |
| 改了监听地址 / 新增子进程 / alias map 路径 | `tools/zgate-lifecycle/restart-zgate.cmd` 受控换版 | 指望 `POST /admin/reload` 热加载这三项（源码 `router.go:984` 的 note 明确仍需重启） |
| 改了 `gateways/zgate/` 下的 Go 代码 | `tools/zgate-lifecycle/restart-zgate.cmd` 受控换版 | 裸 `go build .`、直接覆盖 `zgate.exe`、手工停进程 |
| 编译候选 | `python gateways/zgate/build.py --candidate` → `zgate.candidate.exe` | 在 `gateways/zgate/` 里裸跑 `go build .` |
| 验证存活 | 会话结束后另起会话 `curl http://127.0.0.1:7871/health` 仍 200 | 只看启动那一刻的 `/health` |

监听 `127.0.0.1:7871`；`zgate.json` 配 6 个 upstreams（OC / WB / QD / QW / QN / CP）与 3 个按需拉起的 child：
workbuddy `:7863`（health `/panel/`）、qoder `:8790`（health `/ping`）、cliproxyapi `:8317`（health `/v1/models`，
可执行文件 `third-party/cliproxyapi/cli-proxy-api.exe`），三者 policy 均为 `ondemand`、`idleSeconds=300`。

---

## 1. 为什么不能在会话里直接拉起

### 1.1 会话 Job Object 会回收整棵进程树

Windows 把 CMD / DSH / PowerShell 会话里的进程关联到同一个 Job Object。会话结束时，系统按作业对象回收**整棵进程树**，
不只是直接子进程。因此在 `run_code` / CMD 窗口里用 `Start-Process`、`cmd /c`、`Start-Job` 或 PowerShell 后台作业拉起的
`zgate.exe`，看起来 `/health` 立刻 200，但会话一结束（实测 2 秒内）就随父链一起消失。

### 1.2 DETACHED_PROCESS 与 `zgate serve -tray` 都不够

`DETACHED_PROCESS` 只脱离控制台，不脱离 Job Object；`zgate serve -tray` 同样不保证父进程树被回收时存活。
实测（`PROGRESS.md` 2026-11-09 批次）：`cmd /c`、`Start-Process` 启动的 DETACHED 子进程在会话结束后 2s 内消失；
只有**计划任务**起的普通 `serve` 跨 `run_code` 仍 `/health 200`。可靠父链是
Task Scheduler 服务（`svchost.exe`）→ `wscript.exe` → 脚本 → `zgate.exe`，它不属于任何交互会话的 Job Object。

### 1.3 硬规则

- **严禁**在会话里用 `Start-Process` / `cmd /c` 直接拉起 zgate。
- **严禁**用 HKCU `Run` 项、Startup 快捷方式、常驻 PowerShell 守护脚本替代计划任务。
- 拉起只走 `\ModelBus-zgate-hidden` 父链；改完 Go 代码由 agent 自动执行 `tools/zgate-lifecycle/restart-zgate.cmd`，
  不再要求用户手动重启。机器协议见仓库根 [AGENTS.md](../AGENTS.md) §6。

---

## 2. 现行自启：两个计划任务

### 2.1 主任务 `\ModelBus-zgate-hidden`

| 项 | 值 |
|---|---|
| 触发器 | AtLogOn（当前用户登录时） |
| 运行级别 | Interactive / Limited |
| 动作 | `wscript.exe //B //Nologo launch-zgate.vbs` → `start-zgate-nw.ps1` |
| 启动方式 | `ProcessStartInfo` + `UseShellExecute=$false` + `CreateNoWindow`，起**普通** `zgate.exe serve` |
| 生命周期 | 脚本拉起后立即退出，**不留驻留 PowerShell 进程** |

`start-zgate-nw.ps1` 只负责「无窗地起一次普通 serve」；它不做守护、不循环、不常驻。
无窗还依赖产物 PE 头 `Subsystem = 2`（WINDOWS_GUI）与 Win11 默认终端不接管，机制见 [PITFALLS.md](PITFALLS.md) §20。

### 2.2 看门狗 `\ModelBus-zgate-watchdog`

| 项 | 值 |
|---|---|
| 触发器 | 每 1 分钟（PT1M） |
| 动作 | `ensure-zgate.vbs` → `ensure-zgate.ps1` |
| 行为 | 探 `http://127.0.0.1:7871/health`，不通就经计划任务父链重新拉起；通就立即退出 |

### 2.3 已移除的旧链路

旧任务 `\ModelBus-zgate`、HKCU `Run` 里的 `daemon` 项、Startup 快捷方式均已移除；
`swap-zgate.ps1` / `start-zgate.bat` 改为兼容薄包装，转交计划任务，**不再**用 `Start-Process`。

### 2.4 安全脚本落点

`tools/zgate-lifecycle/install-lifecycle.ps1` 把 8 个生命周期脚本部署到 `%LOCALAPPDATA%\ZCodeGateway`，
校正两个计划任务动作，并写入 `zgate-paths.ps1`（路径由环境变量推导，脚本里不硬编码本机绝对路径）。

---

## 3. 为什么 `POST /admin/reload` 不能换版

`gateways/zgate/internal/supervisor/supervisor.go:473` 的 `ApplyConfig` 只更新**已有** child 的
policy、`idleSeconds` 与窗口：

```go
// ApplyConfig updates policies, idle thresholds and windows of existing children.
// New children need a restart (the executable and port layout is boot-time only).
func (s *Supervisor) ApplyConfig(cfg map[string]config.Child) (applied, unknownKeep, added []string) {
```

可执行文件与端口布局是**启动期**读死的。改了 Go 代码必须换二进制并重启实例；`/admin/reload` 只适合
改 `zgate.json` 的策略 / 空闲 / 窗口，不承担换版。

---

## 4. 换版流程（`deploy-zgate.ps1`）

`tools/zgate-lifecycle/restart-zgate.cmd` 是 CMD 入口，转交 `deploy-zgate.ps1`。九步全在计划任务父链下完成：

1. **编候选**：`python gateways/zgate/build.py --candidate` → `zgate.candidate.exe`，**不覆盖**运行中的 `zgate.exe`。
2. **停 watchdog**：暂停 `\ModelBus-zgate-watchdog`，避免停机窗口里被重新拉起。
3. **受控停机**：`Stop-Process -Name zgate`。
4. **备份**：当前 `zgate.exe` → `zgate.exe.bak-<时间戳>`。
5. **替换**：candidate 覆盖为 `zgate.exe`。
6. **拉起**：`schtasks /run /tn \ModelBus-zgate-hidden`（父链 = Task Scheduler，脱离会话 Job Object）。
7. **健康检查**：轮询 `http://127.0.0.1:7871/health`，`HealthRetries=40`。
8. **恢复 watchdog**：重新启用 `\ModelBus-zgate-watchdog`。
9. **失败回滚**：任一步失败 → 还原备份的旧二进制 → 恢复 watchdog → 重新 `schtasks /run`，停机窗口压到最短。

`-SkipBuild` 可用已就绪的 candidate 跳过第 1 步。换版期间 `/health` 会短暂不可用，属预期；
重建失败立即回退旧二进制，不能停着慢慢查（见 [TROUBLESHOOTING.md](TROUBLESHOOTING.md) §16.2）。

---

## 5. 三个入口命令

| 入口 | 命令 | 用途 |
|---|---|---|
| CMD 入口（agent 自动执行） | `tools/zgate-lifecycle/restart-zgate.cmd` | 改完 Go 代码后一键换版，转发 `deploy-zgate.ps1 %*` |
| 换版正本（PowerShell） | `powershell -NoProfile -ExecutionPolicy Bypass -File tools/zgate-lifecycle/deploy-zgate.ps1` | 九步流程本体，支持 `-SkipBuild` |
| 部署 / 校正（PowerShell） | `powershell -NoProfile -ExecutionPolicy Bypass -File tools/zgate-lifecycle/install-lifecycle.ps1` | 部署脚本到 `%LOCALAPPDATA%\ZCodeGateway`、校正两个任务动作 |

辅助：`python gateways/zgate/build.py --candidate`（编候选）、
`python gateways/zgate/build.py --check`（校验 PE 子系统）、
`POST /admin/reload`（只热加载 `zgate.json` 策略）。
脚本清单与产物见 [TOOLS.md](TOOLS.md)。

---

## 6. 验证：CMD/DSH 会话退出后是否仍存活

按下面顺序做，缺一不可：

1. 在会话 A 里换版或触发自启后，立刻 `curl http://127.0.0.1:7871/health` 应返回 `"ok":true`。
2. **关掉会话 A**（这一步是关键 —— 只看启动那一刻不算验证）。
3. 另起会话 B，再 `curl http://127.0.0.1:7871/health`，仍须 200。
4. 看进程父链，父进程应是 Task Scheduler 服务（`svchost.exe`）而非 `powershell.exe` / `cmd.exe`：

   ```powershell
   Get-CimInstance Win32_Process -Filter "Name='zgate.exe'" | Select-Object ProcessId,ParentProcessId,CommandLine
   ```

5. 看两个任务状态与上次运行时间：

   ```cmd
   schtasks /query /tn \ModelBus-zgate-hidden /v
   schtasks /query /tn \ModelBus-zgate-watchdog /v
   ```

6. 端口监听：`netstat -ano | findstr 7871` 应有 LISTENING。

若第 3 步变 502 / 连接拒绝，而第 1 步是 200，基本可判定进程被会话 Job Object 回收 —— 回到 §1，检查是不是
有人用 `Start-Process` / `cmd /c` 绕过了计划任务父链。

---

## 7. 常见故障

| 现象 | 根因 | 解法 |
|---|---|---|
| 会话里 `/health` 200，会话一关就 502 | 进程落在 CMD/DSH 会话 Job Object 里被整树回收 | 只走 `\ModelBus-zgate-hidden` 父链；见 §1 |
| `DETACHED_PROCESS` / `serve -tray` 仍不存活 | 只脱离控制台，不脱离 Job Object | 同上，改用计划任务；见 §1.2 |
| 开机弹出 cmd 控制台窗口 | 产物 PE 头 `Subsystem = 3`（CONSOLE），或 Win11 默认终端接管 | 一律用 `gateways/zgate/build.py` 编（`-H windowsgui` + 校验 `Subsystem = 2`）+ `CreateNoWindow`；见 [PITFALLS.md](PITFALLS.md) §20 |
| 裸 `go build .` 后无窗版变控制台版 | 单包模式把 exe 原地覆盖，产物在 `.gitignore` 里救不回 | 编译入口收口到 `build.py`；见 [PITFALLS.md](PITFALLS.md) §20 |
| 改了 Go 代码但行为没变 | 只调了 `/admin/reload`，旧二进制没换 | 跑 `tools/zgate-lifecycle/restart-zgate.cmd`；见 §3 |
| 换版后 `/health` 一直不通 | 新二进制启动失败 / 端口占用 | `deploy-zgate.ps1` 自动回滚旧二进制并恢复 watchdog；查日志与 `netstat -ano \| findstr 7871` |
| watchdog 没恢复，掉线后不自愈 | 换版中断在停 watchdog 之后 | 重新启用任务，或用 `install-lifecycle.ps1` 校正动作 |
| 两个计划任务动作被改坏 | 手工改过任务 / 脚本路径迁移 | 跑 `install-lifecycle.ps1` 重新部署并校正 |
| 编译候选把运行中的 exe 覆盖了 | 没带 `--candidate` | 一律 `python gateways/zgate/build.py --candidate`，产物名 `zgate.candidate.exe` |

---

## 8. 规则与边界

- 长驻网关（`zgate` / `wb2api` / `mihomo`）**禁止会话自动重启**（会话流量可能正经过它）；
  本仓例外是 agent 改完 Go 代码后按 §4 走 `restart-zgate.cmd` 受控换版。
- 部署三步：备份 → 校验 → 受控重启；失败自动回滚，停机窗口压到最短。
- 文档不写本机绝对路径（用相对路径或 `%LOCALAPPDATA%` 推导）；凭据只写环境变量名，不写真值，
  清单见 [SECRETS.md](SECRETS.md) §3.5 与仓库根 [AGENTS.md](../AGENTS.md) §2。
- 本篇只定义生命周期；端口与 upstream 拓扑正本在 [ARCHITECTURE.md](ARCHITECTURE.md)，
  工具与产物正本在 [TOOLS.md](TOOLS.md)，日常命令表在 [MAINTENANCE.md](MAINTENANCE.md) §8。
