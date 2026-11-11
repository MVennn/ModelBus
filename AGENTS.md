# AGENTS.md — 本仓库的机器协议

> **一句话**：四条硬规矩 —— **PROGRESS 按逻辑任务分家**、**凭据只走环境变量**、
> **有 CodeGraph 就先用 CodeGraph**、**改完 Go 代码自动走 `restart-zgate.cmd` 换版**。其它都能从 `docs/` 里查到。

**当前架构（2026-11-11 起）**：本仓以 **DSH 为主宿主**，会话 / 子代理 / headless / 服务插件等各类 agent 共用 `gateways/zgate` 单一入口与同一份路由策略；ZCode 降为兼容投影。实现层命名已去 ZCode，但**契约层一个字不动** —— `~/.zcode/v2/provider_config.json`、`ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` / `ZCODE_BUILTIN`、`third-party/zcode*` 原件、schema 键、`%LOCALAPPDATA%\ZCodeGateway\`、NOTICE 商标段照旧。三层命名口径与批次见 [docs/DSH-FIRST.md](docs/DSH-FIRST.md)。

---

## 1. PROGRESS：路径由逻辑任务决定，不是物理目录

**每个逻辑任务目录内有且仅有一个 `PROGRESS.md`。** 本仓当前的逻辑任务只有一个，
所以全仓只有一个进度文件：仓库根的 `PROGRESS.md`（追加式批次日志）。

- **不要**因为「起了个子代理」或「换了个子目录」就在别处再开一个 `PROGRESS.md`。
- **不要**把多个互不相关的任务写进同一个 `PROGRESS.md`。
- **子代理只写分片**：文件名 `evidence/agent-<name>.md`，**不碰任何共享文件**
  （不碰 `PROGRESS.md`、不碰 `provider_config.json`、不碰 `docs/`）。

> **为什么**：历史上 13 个并行子代理被要求「在任务根目录维护 PROGRESS.md」，
> 结果全部往同一个物理文件写，后写覆盖先写 —— 根 `PROGRESS.md` 一度被并发写坏，
> 同一篇里同一个批次标题出现两次，且步骤清单未勾选而状态写着「已完成」。
> 根因是把「任务根目录」理解成**物理目录**，而不是**逻辑任务**。
> 合并原则见 [docs/DOC-RULES.md](docs/DOC-RULES.md)。

写 `PROGRESS.md` 时按批次追加，格式照现有内容：

```
# YYYY-MM-DD 第 N 轮：<一句话主题>

## 任务目标
## 已完成变更      （- [x] 勾选式）
## 验收            （可复现的验证方式 + 结论）
## 待解决 / 注意事项
## 状态: 已完成
```

**每完成一个关键步骤（文件改动、命令执行成功）立即更新一次** —— 写入时间即心跳。

---

## 2. 凭据一律走环境变量

**不要把 key / 口令 / token 写进源码、文档、日志、缓存文件。**

| 凭据 | 怎么取 |
|---|---|
| OpenCode-Go 的 `oc_sk_…` | `provider_config.json` 里的 `providerConfigRules.providerRules[].config.access.apiKey`（脚本自己读） |
| WorkBuddy 网关 `api_key` | 环境变量 **`WB_GATEWAY_KEY`** |
| 网关地址 | 环境变量 **`WB_GATEWAY_BASE`**（默认 `http://127.0.0.1:7863`） |
| ZCode 配置文件路径 | 环境变量 **`ZCODE_PERSONAL_PROVIDER_CONFIG_FILE`** |
| ZCode 内置规则文件 | 环境变量 **`ZCODE_BUILTIN`** |
| 代理会话头 | 环境变量 **`OPENCODE_SESSION`** |
| Qoder 网关 key | 环境变量 **`QD_API_KEY`**（也可用 git-ignored 的 `providers/qoder/.env.local`） |
| 千问直连 | 环境变量 **`QWEN_API_KEY`** / **`QWEN_BASE`** |
| 七牛云 AI 网关 | 环境变量 **`QINIU_API_KEY`** |

> ✅ `providers/opencode-go/probe/` 下的 `probe_models.py`、`probe_protocols.py`、
> `bench_models.py`、`bench_clean.py`、`thinking-off-probe.js` 已统一读 `OPENCODE_GO_KEY` 环境变量；
> 文档与脚本口径一致，无需再改。

同理，`provider_config.json` 的备份文件（`*.bak-*`）里也有 key ——
它们只留在本机，**绝不进版本库**（`.gitignore` 已排除）。

---

## 3. CodeGraph

**仓库根有 `.codegraph/` 就优先用它查符号与调用路径；没有就退回普通检索（Grep / Read / glob）。**

- 判断依据：仓库根存在 `.codegraph/` 目录才算已索引。当前索引**存在但可能陈旧**
  （`.codegraph/` 被 `.gitignore` 排除，不随仓库分发）。
- 每会话先跑一次 `codegraph_status` 看健康度；**会话内不自行 `codegraph init`**（索引是否重建由人决定），
  只有报 **stale** 才跑 `codegraph_sync`；索引缺失时用普通检索继续干活并提示人执行 `codegraph init`。
- 有索引时定向查用 `codegraph_explore` / `codegraph_callers` / `codegraph_callees` / `codegraph_node`；
  callers/callees/impact 不保证完整（会漏未解析的方法 / 泛型 / trait 派发边），要 100% 准确改用 grep。
- 无论有没有索引，**改动前后都要把 `docs/README.md` 的索引对齐**（孤儿文档零容忍）。

---

## 4. 目录两轴：`gateways/` 跑进程，`providers/` 跑脚本

- `gateways/` 只放**会被启动的东西**：`zgate`（Go 入口）、`legacy-router`（旧 Node 路由，回退用）、
  `upstream/{workbuddy,qoder}`（上游 clone，gitignored）。
- `providers/` 只放**手动执行的采集/探测/同步脚本**：`opencode-go/`、`workbuddy/`、`qoder/`。
- `tools/` 放跨供应商工具（`model_alias` / 榜单 / 探测 / 文档与密钥检查）。
- 判断规则一句话：会被启动 → `gateways/`；被手动执行 → `providers/`；跨供应商复用 → `tools/`。

## 5. 其它约定（简）

- **文档正本**：每条规则只在一篇文档里定义，其余位置只留一句话 + 链接。
  正本映射表见 [docs/DOC-RULES.md](docs/DOC-RULES.md) §2。
- **文档命名**：`docs/` 下一律 `ALL-CAPS-WITH-HYPHENS.md`（`release-notes/` 例外：
  文件名 = `versionName`，**不带 `v` 前缀**）。规则见 [docs/DOC-RULES.md](docs/DOC-RULES.md) §1。
- **链接**：一律相对链接 + 半角括号；锚点必须真实存在。
- **每篇文档开头**必须有 `> **一句话**：…` 引言块。
- **中文**：简体中文。务实，给结论，给证据；不确定的写「待补」并说明缺什么。
- **单篇 ≤ 800 行**。
- **不要 `git init` / `git add` / 提交**，除非明确要求。
- **不要动** `docs/MODEL-QUICK-REF.md`、`docs/archive/`、`evidence/`、`PROGRESS.md`
  与任何脚本，除非任务明确要求改它们。

---

## 6. zgate 换版硬规则

- **改完 `gateways/zgate/` 下的 Go 代码后，agent 自动执行 `tools/zgate-lifecycle/restart-zgate.cmd` 完成编译候选 + 受控换版，不再要求用户手动重启**；换 Go 代码必须换二进制。`POST /admin/reload` 热加载 `zgate.json` 的策略 / 空闲 / 窗口 / 上游 base / 凭据（`keys.Load` 六通道 + `ApplyConfig(children)` + `aliases.Reload()`，`router.go:963-986`）；监听地址 / 新增子进程 / alias map 路径仍需换版重启。
- **严禁在会话里用 `Start-Process` / `cmd /c` 直接拉起 zgate** —— 它们落在 CMD/DSH 会话的 Job Object 里，会话结束整棵进程树被回收；拉起只走计划任务 `\ModelBus-zgate-watchdog` 父链（2026-11-11 起合并为单任务，登录即拉起（LogonTrigger）+ 每分钟兜底（PT1M））。机制与换版流程见 [docs/ZGATE-LIFECYCLE.md](docs/ZGATE-LIFECYCLE.md)。
