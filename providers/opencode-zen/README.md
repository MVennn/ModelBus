# OpenCode Zen 免费档接入（TUI 专属模型）

> **一句话**：把 OpenCode TUI 专属免费模型通过本地 Bun 代理接进 ModelBus，两道门已过、全链路实测 200、cost=0。

---

## 它做什么

OpenCode Zen 有一批只在官方 TUI 免费档可用的模型，走 `/inference/v1` 端点，有两道门：403（HTTP 头指纹）和 429（Bun TLS ClientHello 指纹 + system 提示词 `<env>` 块）。Node/Go 直连必吃 429。本目录用本地 Bun 代理过门，zgate 只做转发。

上游实现来自 jcleng/opencode-free-provider（MIT，逐字部署在 `zen-relay/`），实测两道门均过；手写精简版曾实测 429，已弃用。

## 数据流

```
DSH/ZCode 客户端
  -> zgate 127.0.0.1:7871/v1  (alias: OC 渠道, key 复用 opencode-go)
  -> alias map 的 base=http://127.0.0.1:8789/v1
  -> zen-relay (Bun) 8789  [补四 session 头 + env 块 + Bun TLS 指纹]
  -> https://opencode.ai/inference/v1/chat/completions  (keyless, Bearer public)
```

## 关键实现（model_alias.py）

- `ZEN_FREE_BASE` / `ZEN_FREE_UPSTREAMS`：10 个 TUI 免费 upstream 逐条把 base 覆盖到 8789（其余 OC 模型仍走 zen/go）。含免费版 DeepSeek V4.1-Flash-1017（`deepseek-v4.1-flash-free`），靠 `SPLIT_CHANNEL_DISPLAY` 拆成独立条目 `DeepSeek-4.1-Flash-Free`，不并进 0.11 的付费主力。
- `INJECT_ORDER`：固定白名单，每日同步不会收录这批（不在 go 端点清单），靠它每次 alias 都注入。归 `oc:` 前缀走 OC 渠道，复用 OC key 过路由校验。
- `OC_PRICES` 补 `flat=0.00`；`EMPTY_ALLOWED` 补显示名（上游无 reasoning 档位）。
- 注意：`deepseek-v4.1-flash-free` 不注入——它与主力撞名会改写主力价格/链路（实测 --check 漂移）。

## 运维

- 代理进程由计划任务 `ModelBus-zen-relay-watchdog` 每 5 分钟健康检查 8789，不通则无窗拉起（`ensure-zen-relay.vbs` -> `start-zen-relay.ps1`）。
- Bun 路径：`%USERPROFILE%\.bun\bin\bun.exe`（v1.4.4，官方安装脚本）。
- 手动验证：`curl http://127.0.0.1:8789/health`；端到端：打 zgate 的 `/v1/chat/completions`，model=big-pickle。

## 来源

- 踩点方案：`docs/ZEN-FREE-INTEGRATION-PLAN.md`
- 逐字照抄清单：`%TEMP%/zen-impl-checklist.md`（session id / header / env 注入 / body）
- 上游实现：jcleng/opencode-free-provider（MIT）、jiesou/dsh-opencode-zen-free-provider（MIT）
