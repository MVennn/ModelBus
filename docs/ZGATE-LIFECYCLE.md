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
| 开机自启 | 计划任务 `\ModelBus-zgate-watchdog`（LogonTrigger 登录即拉起 + PT1M 每分钟兜底）→ `ensure-zgate.vbs` → `ensure-zgate.ps1` | `Start-Process`、`cmd /c`、HKCU Run、Startup 快捷方式 |
| 进程掉线兜底 | 计划任务 `\ModelBus-zgate-watchdog`（每 1 分钟）→ `ensure-zgate.vbs` → `ensure-zgate.ps1` | 会话内起常驻 PowerShell 守护 |
| 改了 `zgate.json` 策略 / 空闲 / 窗口 / 上游 base / 凭据 | `POST /admin/reload`（热加载配置与 `ApplyConfig(children)`，不换二进制） | 为了改策略去重启整个实例 |
| 改了监听地址 / 新增子进程 / alias map 路径 | `tools/zgate-lifecycle/restart-zgate.cmd` 受控换版 | 指望 `POST /admin/reload` 热加载这三项（源码 `router.go:984` 的 note 明确仍需重启） |
| 改了 `gateways/zgate/` 下的 Go 代码 | `tools/zgate-lifecycle/restart-zgate.cmd` 受控换版 | 裸 `go build .`、直接覆盖 `zgate.exe`、手工停进程 |
| 编译候选 | `python gateways/zgate/build.py --candidate` → `zgate.candidate.exe` | 在 `gateways/zgate/` 里裸跑 `go build .` |
| 验证存活 | 会话结束后另起会话 `curl http://127.0.0.1:7871/health` 仍 200 | 只看启动那一刻的 `/health` |

监听 `127.0.0.1:7871`；`zgate.json` 配 7 个 upstreams（OC / WB / QD / QW / QN / GM / HJ）与 2 个按需拉起的 child：
workbuddy `:7863`（health `/panel/`）、qoder `:8790`（health `/ping`），两者 policy 均为 `ondemand`、`idleSeconds=300`。

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
- 拉起只走 `\ModelBus-zgate-watchdog` 父链（`schtasks /run /tn ModelBus-zgate-watchdog`）；改完 Go 代码由 agent 自动执行 `tools/zgate-lifecycle/restart-zgate.cmd`，
  不再要求用户手动重启。机器协议见仓库根 [AGENTS.md](../AGENTS.md) §6。

---

## 2. 现行自启：单个计划任务

### 2.1 唯一任务 `\ModelBus-zgate-watchdog`

| 项 | 值 |
|---|---|
| 触发器 | LogonTrigger（当前用户 `MVENN-PC\SansK`）+ 每 1 分钟（PT1M，StartBoundary 2026-11-06T22:14:00） |
| 运行级别 | Interactive / Limited |
| 动作 | `wscript.exe //B //Nologo ensure-zgate.vbs` → `ensure-zgate.ps1`，`/health` 不通才拉起 |
| 启动方式 | `ProcessStartInfo` + `UseShellExecute=$false` + `CreateNoWindow`，起**普通** `zgate.exe serve` |
| 生命周期 | 脚本拉起后立即退出，**不留驻留 PowerShell 进程** |

`start-zgate-nw.ps1` 只负责「无窗地起一次普通 serve」；它不做守护、不循环、不常驻。
无窗还依赖产物 PE 头 `Subsystem = 2`（WINDOWS_GUI）与 Win11 默认终端不接管，机制见 [PITFALLS.md](PITFALLS.md) §20。

### 2.2 登录与即时拉起

| 项 | 值 |
|---|---|
| 登录后 | 立即由 §2.1 的唯一任务拉起（LogonTrigger）；漏跑由 PT1M 兜底 |
| 换版 / 立即拉起 | `schtasks /run /tn ModelBus-zgate-watchdog`（父链 = Task Scheduler，脱离会话 Job Object） |
| 备注 | 日常只用 `/query`、`/run`；改已有任务定义需提权（`Set-ScheduledTask` 在本机交互账户下报「拒绝访问」）。新建任务可 `Register-ScheduledTask` 带 `-Principal`（Interactive/Limited）直接注册；换触发器走「删 + 同名重新注册」（见 `~/.dsh/procedures/工具-Windows-非提权计划任务建改删权限边界.md`） |

### 2.3 已移除的旧链路

旧任务 `\ModelBus-zgate`、HKCU `Run` 里的 `daemon` 项、Startup 快捷方式均已移除；`\ModelBus-zgate-hidden`（AtLogOn）也已于 2026-11-11 删除
（备份 `%USERPROFILE%\.dsh\backups\task-ModelBus-zgate-hidden-20261111-142620.xml`）；`swap-zgate.ps1` / `start-zgate.bat` 改为兼容薄包装，转交计划任务，**不再**用 `Start-Process`。

### 2.4 安全脚本落点

`tools/zgate-lifecycle/install-lifecycle.ps1` 把 8 个生命周期脚本部署到 `%LOCALAPPDATA%\ZCodeGateway`，
校正计划任务动作，并写入 `zgate-paths.ps1`（路径由环境变量推导，脚本里不硬编码本机绝对路径）。

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
6. **拉起**：`schtasks /run /tn ModelBus-zgate-watchdog`（父链 = Task Scheduler，脱离会话 Job Object）。
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
| 部署 / 校正（PowerShell） | `powershell -NoProfile -ExecutionPolicy Bypass -File tools/zgate-lifecycle/install-lifecycle.ps1` | 部署脚本到 `%LOCALAPPDATA%\ZCodeGateway`、校正任务动作 |

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

5. 看任务状态与上次运行时间：

   ```cmd
   schtasks /query /tn \ModelBus-zgate-watchdog /v
   :: 现行只有这一个任务；若还看到 \ModelBus-zgate-hidden 说明有残留
   ```

6. 端口监听：`netstat -ano | findstr 7871` 应有 LISTENING。

若第 3 步变 502 / 连接拒绝，而第 1 步是 200，基本可判定进程被会话 Job Object 回收 —— 回到 §1，检查是不是
有人用 `Start-Process` / `cmd /c` 绕过了计划任务父链。

---

## 7. 常见故障

| 现象 | 根因 | 解法 |
|---|---|---|
| 会话里 `/health` 200，会话一关就 502 | 进程落在 CMD/DSH 会话 Job Object 里被整树回收 | 只走 `\ModelBus-zgate-watchdog` 父链；见 §1 |
| `DETACHED_PROCESS` / `serve -tray` 仍不存活 | 只脱离控制台，不脱离 Job Object | 同上，改用计划任务；见 §1.2 |
| 开机弹出 cmd 控制台窗口 | 产物 PE 头 `Subsystem = 3`（CONSOLE），或 Win11 默认终端接管 | 一律用 `gateways/zgate/build.py` 编（`-H windowsgui` + 校验 `Subsystem = 2`）+ `CreateNoWindow`；见 [PITFALLS.md](PITFALLS.md) §20 |
| 裸 `go build .` 后无窗版变控制台版 | 单包模式把 exe 原地覆盖，产物在 `.gitignore` 里救不回 | 编译入口收口到 `build.py`；见 [PITFALLS.md](PITFALLS.md) §20 |
| 改了 Go 代码但行为没变 | 只调了 `/admin/reload`，旧二进制没换 | 跑 `tools/zgate-lifecycle/restart-zgate.cmd`；见 §3 |
| 换版后 `/health` 一直不通 | 新二进制启动失败 / 端口占用 | `deploy-zgate.ps1` 自动回滚旧二进制并恢复 watchdog；查日志与 `netstat -ano \| findstr 7871` |
| watchdog 没恢复，掉线后不自愈 | 换版中断在停 watchdog 之后 | 重新启用任务，或用 `install-lifecycle.ps1` 校正动作 |
| 计划任务动作被改坏 | 手工改过任务 / 脚本路径迁移 | 跑 `install-lifecycle.ps1` 重新部署并校正 |
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

---

## 9. 版本判定、升级决策与回滚（2026-11-11 补）

> 本节只写「怎么判版本、什么时候才真要换二进制、换了怎么回滚、换完怎么证明真的生效」；九步换版流程、自启父链、存活验证的六步见 §2 / §4 / §6，此处不重述。

### 9.1 版本判定：只认 buildinfo 的 `vcs.revision`

换不换版的前提是「现在跑的是哪份代码」。这件事只有一个可靠证据：二进制内嵌 buildinfo 的提交号。

```cmd
go version -m gateways\zgate\zgate.exe
git log <vcs.revision>..HEAD -- gateways/zgate
python gateways/zgate/build.py --check
```

| 证据 | 能回答 | 回答不了 |
|---|---|---|
| `vcs.revision` | 这份 exe 是哪个提交编的 | 编译时工作区有没有未提交改动（只看得到 `vcs.modified`） |
| `vcs.modified=true` | 字节不可复现：工作区当时不干净，Git 状态戳记进了 buildid | 具体是哪几个文件没提交 |
| `git log <rev>..HEAD -- gateways/zgate` | 二进制之后网关代码还欠不欠账（空 = 不欠） | 非网关目录的改动 |
| md5 / SHA-256 | 备份 → 替换 → 校验这一段搬的是不是同一份字节 | 是不是最新代码 |
| CHANGELOG 的版本标题 | 仓库发布号（[VERSIONING.md](VERSIONING.md) 口径） | 二进制版本 —— 两者没有绑定关系 |

**为什么 md5 对不上是常态**：构建目录不干净时 `vcs.modified=true` 被编进 buildid，同一份源码、
不同 ldflags 组合（`-H windowsgui`、`-s -w`、带与不带 `-trimpath`）实测全部对不上；
工作区干净后重建只能保证**语义一致**，不保证哈希一致。所以 md5 的用途限定在「同一次构建的搬运校验」，
版本比对一律回到 `vcs.revision`。

**判据**：`vcs.revision` 等于预期提交 **且** `git log <rev>..HEAD -- gateways/zgate` 为空，
才算「跑的就是 HEAD 的网关代码」。

### 9.2 升级决策树：先给改动分类，再选入口

| 改动落在哪 | 入口 | 依据 |
|---|---|---|
| `zgate.json` 的策略 / 空闲 / 窗口 / 上游 base / key | `POST /admin/reload`（或 `zgate.exe reload`） | 热加载覆盖 config、上游 base、凭据、子进程策略（`router.go` 的 `reload`） |
| alias map（统一名 → 链） | 重新生成后即生效，必要时 reload | alias 按 mtime 热加载 |
| 监听地址 / 新增子进程 / alias map 路径 | 换版（§4 九步） | 这三项是启动期读死的 |
| `gateways/zgate/` 下的 Go 代码（含新增渠道、守卫、冷却语义） | 换版（§4 九步） | 渠道集合与进程内快照都是编译期/启动期的 |
| 只改文档、只改 `tools/` 里的检查脚本 | 都不动 | 不改变运行态 |

**换版前先判版本**：先按 9.1 记下 `vcs.revision` 与 `zgate.exe` 的备份名，再动。
没有基线的「换版成功」只是「进程起来了」。

**工作区有未提交改动时**：换版会把当时的文件状态编进去，产物带 `vcs.modified=true`，
事后无法用 revision 反推内容。要么先让工作区干净，要么在换版记录里写清「本次含未提交改动」
并列明文件 —— 否则下一个人只能靠 diff 考古。

### 9.3 参数随版本变化：读三层真值，不读文档里的表

任何写进文档的参数表都只是**某一刻的快照**。参数现值的读取顺序固定为：

| 顺序 | 真值来源 | 说明 |
|---|---|---|
| 1 | `gateways/zgate/zgate.json` | 运行实例真正加载的那份；可被环境变量覆盖时以覆盖为准 |
| 2 | `internal/config` 的缺省值与常量 | 配置没写时生效的东西（`headerTimeout` 的 0 / 负值语义、TTL 常量、冷却常量） |
| 3 | `curl http://127.0.0.1:7871/health` 的生效段 | 证明「这一刻」真的在用哪个值，绕过热加载是否生效的争论 |
| 4 | 文档参数表 | 只用来理解取值理由，不用来抄数字 |

各参数族**变过什么**（只记口径变化，不记数字）：

| 参数族 | 口径变化 | 现行定义在哪 |
|---|---|---|
| 响应头等待窗口 | 写死常量 → 全局 `upstreamHeaderTimeoutSec` → 渠道级 `channelPolicy.<CH>.headerTimeoutSec` 覆盖（0 = 继承全局，负数 = 该渠道不设窗口） | [ROUTING-POLICY.md](ROUTING-POLICY.md) §1，值看 `zgate.json` |
| 判死与冷却 | 本地按阈值判死 → 判死权交还上游 → 上游语义三分类（忙 / 参数不认 / 断流）各走各的路 | [ROUTING-POLICY.md](ROUTING-POLICY.md) §4、§4.1 |
| 对冲与并发 | 按链首渠道取值 → 按跳聚合（最小正 hedge、最大 maxParallel）→ 单发串行（对冲字段全归零） | [ROUTING-POLICY.md](ROUTING-POLICY.md) §1、§8.1 |
| 竞速观测 | 只留最近一次且永不过期 → 失败短保鲜 / 成功长保鲜，过期当「没测过」重新给机会 | `internal/router/router.go` 的 `raceFailTTL` / `raceOKTTL` 两个常量 |
| 观测面 | 五段（early / chain / guard / race / upstream）→ 增 `hops`（逐跳 try / ok / busy / e5xx / silent / no_first_block） | `curl /health`，段义见 [ROUTING-POLICY.md](ROUTING-POLICY.md) §7 |
| 思考守卫作用域 | `auto`（不看表）→ `models`（白名单）→ `channels`（渠道能力位 + 白名单交集） | [ROUTING-POLICY.md](ROUTING-POLICY.md) §7.1 |
| 渠道集合 | 5 → 6 → 7（本地子进程仍是 2 个） | `zgate.json` 的 `upstreams` / `children`，由 `tools/check-project.py` 与源码比对 |

**举例（历史值，禁止照抄）**：2026-11-10 白天一度把 GM 的窗口压到十几秒、并发开到 3、对冲提前到百毫秒级，
当晚因「本地判死 125 次、上游真说忙只有 7 次」全部回退。这组数字只能说明「口径会被推翻」，不能当现值。

**硬规则**：改参数先看 `/health` 的生效值，再决定改哪个键；改完 reload 后**再看一次**，
确认 `chain.budget_s` / `guard.mode` / `race.hops` / `upstream` 与文件一致 —— 这一步能同时排掉
「改错键」「配置没被读」「热加载路径没走到」三种情况。

### 9.4 回滚路径：四层，按影响面从小到大

| 层 | 回滚物 | 怎么生效 | 怎么验 |
|---|---|---|---|
| 配置 | `gateways/zgate/zgate.json.bak-<purpose>-<ts>` | 覆盖后 `POST /admin/reload` | `/health` 的 chain / guard / upstream 与文件一致 |
| 别名 | alias map 生成前的备份（生成脚本自带 `.bak-<ts>`） | 重跑生成（必要时 reload） | `/v1/models?scope=canonical` 的 `total` / `catalog_total` |
| 二进制 | `zgate.exe.bak-<ts>`（`deploy-zgate.ps1` 失败自动回滚） | 暂停 watchdog → 覆盖 → `schtasks /run /tn ModelBus-zgate-watchdog` → 轮询 `/health` → 恢复 watchdog | 9.5 全套 |
| 代码 | 反向提交后重新走 §4 九步 | 换版 | 同上，并核 `vcs.revision` |

原则三条：

1. **一步一验**：回滚与验证成对做，不要连回两层再一起验 —— 混起来分不清是哪一层救回来的。
2. **先停 watchdog 再换二进制**：不然停机窗口里会被看门狗按旧 exe 拉起，出现「回滚了但进程还是新的」。
3. **停机窗口只做一件事**：回滚失败就承认失败并把旧二进制放回原位，别在窗口里现场改代码。

### 9.5 验证：存活不等于生效

§6 的六步回答的是「进程会不会被会话树带走」。换版/改参之后还要回答「新的东西到底有没有在工作」：

| 检查 | 命令 | 它证明什么 |
|---|---|---|
| 产物形态 | `python gateways/zgate/build.py --check` | PE 子系统是 GUI（无窗），不是控制台 |
| 版本 | `go version -m gateways\zgate\zgate.exe` | 跑的是预期提交（见 9.1） |
| 配置生效 | `curl -s http://127.0.0.1:7871/health` | `ok:true`；`chain.budget_s` 与文件一致；`guard.mode` 是预期档位 |
| 观测接上 | 同上，看 `hops` 段 | 真实请求后该跳 `try` 有增量；`silent` / `no_first_block` / `busy` 能看到失败形态 |
| 目录对外 | `curl -s "http://127.0.0.1:7871/v1/models?scope=canonical"` | `total` 与 `catalog_total` 是两回事，别混读 |
| 自启状态 | `schtasks /query /tn \ModelBus-zgate-watchdog /v` | 单任务 Ready，上次运行时间对得上 |
| 父链 | `Get-CimInstance Win32_Process -Filter "Name='zgate.exe'"` | 父进程在 Task Scheduler 侧，不是某个终端 |
| 日志 | `type "%LOCALAPPDATA%\ZCodeGateway\zgate.log"` | 有换版/加载行；没有反复的 `port already up` 或绑定冲突 |
| 实请求 | 发一条真实流式请求，看日志 `(i/n)` 与首块 | 路由到预期跳，不是每次都落在兜底跳 |

**换版后 5 分钟观察窗**：只做三件事 —— 发一次请求、看 `hops` 增量、看日志有没有 `silent` / `no_first_block` 连片。
这三件事都正常就收工；异常按「先回滚再查」走 9.4。

### 9.6 本节边界

- 换版九步、单计划任务、`install-lifecycle.ps1` 的动作校正：§2、§4、§5。
- 参数为什么这么取值、逐跳怎么聚合、上游语义三分类： [ROUTING-POLICY.md](ROUTING-POLICY.md)。
- 已知故障形态与现场处置： [TROUBLESHOOTING.md](TROUBLESHOOTING.md) §16、§18；坑的机制见 [PITFALLS.md](PITFALLS.md) §20、§41–§47。
- 加渠道要改哪六处： [MODEL-PROVIDERS.md](MODEL-PROVIDERS.md) §0。
