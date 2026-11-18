# OpenCode Zen 免费模型接入 ModelBus：踩点文档

> **一句话**：把 OpenCode Zen 免费模型接进 ModelBus 要过两道门，本文档钉死接入点与可回滚落地步骤。
> **结论**：本文档是 2026-11-09 踩点快照。踩点结论（两道门、关键模型、回滚边界）有效；落地动作已在 2026-11-11 执行，现状是**已实现但当前停用**——Bun v1.4.4 已装、zen-relay 曾监听 8789、2026-11-17 停用（任务 `ModelBus-zen-relay-watchdog` 已 Disabled、8789 已关闭）。以 `CHANGELOG.md` 2026-11-17 条与 `providers/opencode-zen/README.md` 为准。

---

## 1. 目标与背景

把 OpenCode Zen 的免费模型（已取证样本 `big-pickle`）接进 ModelBus，让现有调用方继续走 zgate 统一入口，不必各自伪造 OpenCode 客户端。

这里要过的不是普通鉴权：免费档有两道独立门，缺一道就分别拿到 `403 FreeTierError` 或 `429 FreeUsageLimitError`。ModelBus 现有 Go 网关只能补 HTTP 头，改不了 TLS ClientHello，因此第二道门必须落在本地 Bun 代理层；zgate 只负责把 `ZF` 渠道指过去。

用户已决定**先出踩点文档、再决定是否落地**。本轮只写了本文和 `docs/README.md` 的一行索引；没有改 `provider_config.json`、`cordis.patch.yml`、`tests/`、`gateways/zgate/zgate.json` 真值、`PROGRESS.md`，也没有安装 Bun、改代码或重启网关。

数据来源：用户已完成的 jiesou / jcleng 插件实测（见第 6 节），加上 ModelBus 当前磁盘文件的行号核对；行号按 2026-11-17 只读复核时的状态记录，后续文件变动以实际为准。

---

## 2. 两道门机制

### 2.1 第一道：客户端指纹门

失败表现：`403 FreeTierError`。这道门只看 HTTP 请求头与请求体形状，zgate 完全可以在 `forwardHeaders` 里补齐。

| 检查项 | 必须值 / 形状 | 出处 |
|---|---|---|
| `User-Agent` | `opencode/<version>`；版本从 unpkg `opencode-ai@latest` 读，失败回退 `1.19.0` | 用户已取证：jiesou `src/index.ts:137-161` |
| session id | `ses_` + 12 位小写 hex + 14 位 base62；算法 `value=BigInt(ts)*0x1000n+BigInt(counter)`，descending 时取反，取高 6 字节拼 hex | 用户已取证：jiesou `src/index.ts:137-161` |
| session 头 | `x-opencode-session`、`x-opencode-session-id`、`x-session-affinity`、`X-Session-Id` 四个头同值 | 用户已取证：jiesou / jcleng 实测 |
| project / client | `x-opencode-project: global`；`x-opencode-client: cli` | 用户已取证：jiesou / jcleng 实测 |
| 禁止头 | 不发 `HTTP-Referer`，不发 `x-opencode-request`；发了即 403 | 用户已取证：jiesou 实测 |
| 工具声明 | 强制声明 `bash` + `read`（jcleng 是 `bash` / `glob` / `grep` / `read`）；请求体 `stream:true` | 用户已取证：jiesou / jcleng 实测 |
| 路径 | `/inference/v1`（免费档 Console 通用端点；不是 Go 凭据用的 `/zen/go/v1`） | 用户已取证：jiesou / jcleng 实测 |

### 2.2 第二道：运行时 TLS 指纹门

失败表现：`429 FreeUsageLimitError`。请求字节完全一样，只要出站 TLS ClientHello 指纹是 Node 的就 429，Bun 的才放行。系统提示词还要带 OpenCode 的 `<env>` 块，且包含 `Working directory:` 行；jcleng 用 `injectOpencodeSystemEnv` 注入解决。

zgate 是纯 Go 标准库网关（`go.mod` 无 `utls` 依赖），`router.go:1242` 走 `net/http`，没有 TLS 指纹伪装能力。这道门不能在 zgate 里修，必须新增一个本地 Bun 代理：接收 zgate 转发来的请求，补系统提示词 `<env>`，用 Bun 的 TLS 栈发往 OpenCode。jcleng 是完整参考实现（Dockerfile `CMD bun`，`MAX_COUNTER=63`）。

### 2.3 两道门与两个插件的覆盖对比

| 项目 | 第一道门（403） | 第二道门（429） | 实现方式 | 可借鉴部分 |
|---|---|---|---|---|
| jiesou（39 星，MIT，更新 2026-11-11） | 过：伪造客户端指纹、session id、请求头、工具声明 | 不过：遇到 429 归为 IP 限流，声明不归它管 | DSH bundle，`dsh>=0.2.0-rc.2 <0.3` | 第一道门的头与 session id 算法、403 规避 |
| jcleng（18 星，MIT） | 过 | 过 | 纯 JS 指纹生成 + Bun 运行时 + `injectOpencodeSystemEnv` | 第二道门的 Bun TLS 指纹与 `<env>` 注入 |

落地取舍：第一道门可以放进 zgate `ZF` case，也可以放进 Bun 代理；第二道门只能放 Bun。建议两边都补齐第一道门（zgate 兜底、Bun 代理最终负责），避免后续换代理实现时重复踩 403。

---

## 3. ModelBus 接入点清单

下面只列文件和行号；本轮没有编辑这些文件。行号是 2026-11-17 对当前磁盘的轻量核对结果。

| 文件:行号 | 当前内容 | 落地时要做的事 |
|---|---|---|
| `gateways/zgate/zgate.json:15-59` | `channelPolicy` 现有配置 | 按需给 `ZF` 加策略；先沿用现有默认再决定是否单列 |
| `gateways/zgate/zgate.json:75-82` | `upstreams` 当前 6 个渠道（OC / WB / QD / QW / GM / HJ） | 新增 `ZF`，`base` 指向本地 Bun 代理 `http://127.0.0.1:PORT`（PORT 待定，例 `8789`） |
| `gateways/zgate/zgate.json:83-105` | `children` 现有托管进程 | 新增 Bun 子进程条目：`exe` 指向本地 bun，`args` 指向代理脚本，`cwd`/`port`/`health`/`startTimeoutSeconds` 按现有 child 模板 |
| `gateways/zgate/internal/config/config.go:21-47` | `Upstream{Base,Child,KeyEnv,GuardReasoning}`、`Child{Policy,IdleSeconds,Exe,Args,Cwd,Port,Health,StartTimeoutSeconds,Windows}` | 结构已含 base / child / keyEnv，无需改结构体 |
| `gateways/zgate/internal/router/router.go:1042-1072` | `forwardHeaders`，`OC` case 当前注 `opencode-cli/1.0` UA 与 `X-Opencode-Session` | 仿 `OC` 加 `ZF` case，注入第一道门全部头；`Authorization` 是否覆盖由 Bun 代理最终决定 |
| `gateways/zgate/internal/router/router.go:1242` | `req.Header = headers.Clone()` 后走 `net/http` | 确认这里不会把 Bun 代理需要的头丢掉；TLS 指纹不在这里解决 |
| `providers/opencode-go/ops/opencode-header-proxy.js:46-82` | 现成 Node 补头代理，监听 8787 | 参考其补头逻辑，改造成 Bun 版本地代理；不要直接沿用 Node 运行时过第二道门 |
| `tools/dsh_sync.py:762-812` | 读 provider 配置并投影到 `cordis.patch.yml` 的逻辑 | 新增 provider 后自动进 DSH；此文件当前有并行会话改动，本文只引用不修改 |
| `docs/MODEL-PROVIDERS.md:73-79` | provider 配置三个落点 | 落地后更新该文档；此文件当前有并行会话改动，本文只引用不修改 |
| `third-party/zcode/zcode-builtin.json:5291-5295` | `opencode-zen-chat` / `big-pickle` 模板 | 免费档走 Console 通用端点，确认模型仍在模板表里 |
| `docs/ARCHITECTURE.md:424` | 记录「Bun 单文件体积与内存都不比 Node 好」，评估后未采用 Bun | 本方案需要新装 Bun，等于推翻该历史判断，落地前要用户拍板 |

### 3.1 凭据与端点边界

- Go 凭据（`oc_sk_`）不能用于免费档：`/zen/go/v1/chat/completions` 实测返回 `400 Model is unavailable`。免费档必须走 Console 通用端点（见 `third-party/zcode/zcode-builtin.json:5291-5295` 的 `opencode-zen-chat`），不能沿用 Go key（见 `memories/beam-free-daily-quota.md:24`）。
- key 只从环境变量读；本文不写任何凭据值。
- Big Pickle 是匿名免费模型，官方明确免费期数据可能用于改进模型；这是用户要拍板的数据代价，不是技术阻塞。

---

## 4. 可回滚最小落地步骤（历史方案，2026-11-11 已执行、2026-11-17 已停用）

以下保留当时方案供回滚参考，本轮（踩点）未执行；落地与停用记录见 `CHANGELOG.md` 2026-11-11 / 2026-11-17。原则：每一阶段先备份、再验证、失败按本阶段回滚；长驻网关禁止会话自动重启，受控重启前后按三步（备份 → md5 → 受控重启）执行。

### 阶段 0：前置拍板与准备

- 历史待确认项（2026-11-09 口径）：当时问是否新装 Bun；实测 Bun v1.4.4 已装（`~\.bun\bin\bun.exe`），Big Pickle 数据条款与端点/key 边界见下文。
- 备份：`docs/ZEN-FREE-INTEGRATION-PLAN.md` 所在仓库做一次可回溯快照（建议 `git status` 留痕 + 相关文件复制到 `.work/zen-free-backup/`）。
- 验证：`Get-Command bun` 实测 `~\.bun\bin\bun.exe` v1.4.4；Node v24.13.1。
- 回滚：阶段 0 只创建备份目录，删除该目录即回滚。

### 阶段 1：本地 Bun 代理（第二道门）

- 备份：新建文件前确认目标路径不存在；若已存在先复制备份。
- 操作：写一个本地 Bun HTTP 代理，参考 `opencode-header-proxy.js:46-82` 的补头逻辑，加入第一道门所有头、session id 算法、`injectOpencodeSystemEnv` 的 `<env>` 块（含 `Working directory:`）、`stream:true` 与工具声明；出站用 Bun TLS。监听 `127.0.0.1:PORT`，PORT 先用未占用端口（例 `8789`）。
- 验证：直接对代理发一条最小 chat 请求，预期不再出现 `403 FreeTierError` 或 `429 FreeUsageLimitError`；记录请求 / 响应关键头，不写 key 值。
- 回滚：删除新增代理脚本；未改任何真配置，无需重启网关。

### 阶段 2：zgate 渠道接入（第一道门兜底）

- 备份：`copy gateways\zgate\zgate.json .work\zen-free-backup\zgate.json.bak`；Go 源码若改也先复制备份。
- 操作：`zgate.json:75-82` 的 `upstreams` 加 `ZF` 指向 `http://127.0.0.1:8789`；`:83-105` 的 `children` 加 Bun 进程托管；`router.go:1042-1072` 仿 `OC` 加 `ZF` case 注第一道门头。
- 验证：改 Go 代码要跑对应测试；只改 `zgate.json` 可按 `tools/zgate-lifecycle/` 的换版流程生成 candidate 并做 md5 校验，不直接覆盖运行中的真值。
- 回滚：恢复备份的 `zgate.json` 与 Go 源码；按 lifecycle 受控重启一次回到原状态。

### 阶段 3：provider / DSH 投影

- 备份：`provider_config.json` 与 `cordis.patch.yml` 只在本机备份，不进 git；先确认 `tools/dsh_sync.py` 当前磁盘版本。
- 操作：在 provider 配置里加新 provider 指向 `ZF`；跑 `tools/dsh_sync.py` 自动投影到 `cordis.patch.yml`，新 provider 自动进 DSH。
- 验证：DSH 侧能看到新 provider / `big-pickle`，对 `ZF` 发一条 chat，确认端到端返回正常；`docs/MODEL-PROVIDERS.md` 的 provider 落点表同步更新。
- 回滚：恢复 provider 配置与 `cordis.patch.yml` 备份；重新跑同步确认旧状态。

### 阶段 4：收尾

- 跑该仓文档门禁 `tools/check-docs.py`，确认 `docs/README.md` 索引仍是活链。
- 更新 `docs/MODEL-PROVIDERS.md`、`docs/ARCHITECTURE.md` 中关于 Bun 的历史判断，并保留本次踩点文档作为决策记录。
- 全程不碰 `PROGRESS.md`、`tests/`、`gateways/zgate/zgate.json` 真值直接写入；真值变更只走 candidate + 受控重启。

---

## 5. 关键风险与未决项

| 风险 / 未决项 | 现状 | 对策 / 待定 |
|---|---|---|
| Bun 安装状态（历史项） | 踩点时 PATH 无 Bun；落地后实测 `~\.bun\bin\bun.exe` v1.4.4（Node v24.13.1）；`docs/ARCHITECTURE.md:424` 是早期评估记录 | 已安装；zen-relay 于 2026-11-17 停用，见 `CHANGELOG.md` |
| 第二道门只能在 Bun 层过 | zgate 纯 Go 标准库，`router.go:1242` 走 `net/http`，无 TLS 指纹伪装 | 必须在本地代理用 Bun TLS；不要把 429 误判成 zgate 头问题 |
| 第一道门两处重复 | zgate `ZF` case 与 Bun 代理都要补头 | 明确唯一真源（建议 Bun 代理最终负责，zgate 只兜底）后再写，避免 header 被覆盖或重复 |
| 端点与 key 边界 | Go 凭据 `oc_sk_` 在 `/zen/go/v1/chat/completions` 返 `400 Model is unavailable` | 免费档走 Console 通用端点（`opencode-zen-chat`），不沿用 Go key |
| 免费数据条款 | Big Pickle 匿名免费，数据可能用于改进模型 | 用户拍板是否接受；本轮不发送真实业务数据 |
| session id 版本漂移 | `opencode-ai@latest` 版本号从 unpkg 动态读取，回退 `1.19.0` | 落地脚本加版本缓存与失败回退；升级时重跑两道门验证 |
| 并行会话改动 | `dsh_sync.py` / `test_dsh_sync_efforts.py` / `docs/MODEL-PROVIDERS.md` 在 12:37–12:40 被其他会话改过 | 本文只如实引用当前磁盘状态，不修改这些文件；落地前重读最新版本 |
| 长驻网关不可自动重启 | zgate 可能正承载其他会话流量 | 所有真值变更走 candidate + md5 + 受控重启，禁止会话自动重启 |

---

## 6. 参考来源

### 6.1 用户已取证的外部项目

- jiesou（39 星，MIT，更新 2026-11-11，DSH bundle，`dsh>=0.2.0-rc.2 <0.3`）：过第一道门；本地克隆位置 `%TEMP%\zen-plugin-read`。关键算法出处 `jiesou src/index.ts:137-161`。
- jcleng（18 星，MIT）：两道门都过；参考实现 `bun` + `injectOpencodeSystemEnv` + `MAX_COUNTER=63`。本地克隆位置 `%TEMP%\zen-plugin-read`。
- unpkg `opencode-ai@latest`：用于读取 `User-Agent` 里的版本号，失败回退 `1.19.0`。
- 官方数据条款：Big Pickle 免费期数据可能用于改进模型（用户已取证结论，非本文新增判断）。

### 6.2 ModelBus 本地路径

- `gateways/zgate/zgate.json:15-59`、`gateways/zgate/zgate.json:75-82`、`gateways/zgate/zgate.json:83-105`：渠道策略、upstreams、children 接入点。
- `gateways/zgate/internal/config/config.go:21-47`：`Upstream` / `Child` 结构，字段已够。
- `gateways/zgate/internal/router/router.go:1042-1072`、`gateways/zgate/internal/router/router.go:1242`：`forwardHeaders` 注入点与 `net/http` 出站边界。
- `providers/opencode-go/ops/opencode-header-proxy.js:46-82`：现成 Node 补头代理，参考改 Bun 版。
- `tools/dsh_sync.py:762-812`：provider 配置投影到 DSH 的逻辑。
- `docs/MODEL-PROVIDERS.md:73-79`：provider 配置三个落点。
- `third-party/zcode/zcode-builtin.json:5291-5295`：`opencode-zen-chat` / `big-pickle` 模板。
- `docs/ARCHITECTURE.md:424`：历史评估未采用 Bun 的记录。
- `memories/beam-free-daily-quota.md:24`：Go key 不能用于免费档的记录。

### 6.3 文档边界

本文是踩点记录，不是实施变更单；任何真配置、代码、网关真值、测试文件、进度台账都没有被本轮修改。落地时需要单独走用户的拍板和备份流程。
