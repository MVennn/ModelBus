# DSH 主导：方向、命名分层与落地批次

> 一句话：**这个仓库现在是「模型目录真源 + 多宿主投影」——DSH 是主宿主，会话 / 子代理 / headless / 服务插件等各类 agent 共用同一份路由策略与 `gateways/zgate` 单一入口，ZCode 降为兼容投影；命名按三层口径分层处理，对外契约一个字不动。**

---

## 1. 这份文档管什么

- 管**方向**：谁主谁次、命名怎么分、哪些东西永远不能改名。
- 管**批次**：第一批今晚做什么、后面几批按什么顺序，各自验收口径。
- 不管**机制细节**：provider 落点看 [MODEL-PROVIDERS.md](MODEL-PROVIDERS.md)，命名与分组看 [MODEL-ALIAS.md](MODEL-ALIAS.md)，路由看 [ROUTING-POLICY.md](ROUTING-POLICY.md)，能力字段现状看 [CAPABILITY-AUDIT.md](CAPABILITY-AUDIT.md)。

判断标准只有一条：**同一份事实只在一处定义，下游只是投影**。凡是「谁最后跑谁写字段」的地方，都在本轮的整合清单里。

---

## 2. 现状与目标

| 维度 | 改造前 | 当前架构（2026-11-11 起） |
|---|---|---|
| 主宿主 | ZCode 桌面端读 `provider_config.json` | DSH 读 `cordis.patch.yml` 为主；各类 agent 共用 `127.0.0.1:7871` 单一入口；ZCode 保留为兼容投影 |
| 事实来源 | 三套脚本各自写自己那一段，谁后跑谁盖 | `catalog/` 一份模型目录真源，投影器只读不写回 |
| 命名 | 脚本名、函数名、文档主语都是 ZCode | 内部分层去 ZCode；对外契约原样保留 |
| 能力字段 | 20 条规则里 11 条没有真值，运行时被 builtin 通配规则兜成 1M / 128k | 每条都有出处（上游规则 / 人工补 / 明确 unknown），可 `--check` 复核 |
| 扩展 | 单客户端、单用户 | 多 agent 已是当前架构：`tools/agent_profiles.py` 提供只读投影接口，per-agent 预算 / 冷却按 `X-Agent-Id` 分桶（见 §6）。 |

### 2.1 三层命名口径

| 层 | 例子 | 处置 |
|---|---|---|
| **契约层**（外部世界定的，改了就坏） | `~/.zcode/v2/provider_config.json` 路径、`ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` / `ZCODE_BUILTIN`、`third-party/zcode/` 与 `third-party/zcodium/` 原件、写进 ZCode 配置的 schema 键（`providerConfigRules` / `modelConfigRules.providerModelRules` / `modelOrder` / `personalModelIds` / `optionSpecs.reasoningLevel.{values,map}`）、`%LOCALAPPDATA%\ZCodeGateway\`、NOTICE 里的版权与商标段 | **一个字都不动** |
| **实现层**（本仓自有命名，已改） | `workbuddy_sync.py` / `workbuddy_probe.py` / `effective_body.js` / `qoder_sync.py` / `qoder_probe.py` / `qwen_sync.py`（旧名见 §4 批 2 映射表）；自造 env `WB_PROBE_FILE` / `MB_API_TYPE` / `MB_BASE_URL` / `MB_MAX_OUTPUT_TOKENS`（旧名保留为读取别名）；门面与文档措辞 | 已改中性名，旧名只作 fallback 读取；主语统一成「DSH 主宿主 / 各类 agent / 兼容投影」 |
| **新层**（面向 agent 的词汇） | catalog（模型目录真源）、capabilities（能力元数据）、routing policy（路由策略）、host projection（宿主投影）、agent profile（代理档案） | 新建即用这套词，不再造 ZCode 词汇 |

改名硬回归面原本是 3 处按路径引用（`tools/dsh_sync.py:60`、`tools/model_probe.py:45`、`providers/workbuddy/workbuddy_probe.py:75`），外加 `sync-models.ps1:228,253`；本轮 6 个脚本与这些引用点同批改完，第一方代码里旧名零残留，复跑门禁见 §8。

---

## 3. 目标架构：一份真源，多个投影

```
            ┌──────────────────────────┐
            │ catalog/  模型目录真源     │  display id / base_model / 渠道链 /
            │ （capabilities + 出处）    │  能力字段 + source + confidence
            └───────────┬──────────────┘
                        │ 只读
      ┌─────────────────┼──────────────────┬─────────────────┐
      ▼                 ▼                  ▼                 ▼
 providers/_sink/   tools/dsh_sync.py   tools/agent_profiles.py
 zcode_provider_    （→ cordis.         （→ 每 agent 一套，
 config.py            patch.yml）         只读投影）
      │                 │
      ▼                 ▼
 ~/.zcode/v2/       ~/.dsh/profiles/<p>/
 provider_config.json   cordis.patch.yml
```

三条硬规矩：

1. **投影器不写回真源**。`dsh_sync.py` 现在只向下游写，看到 `provider_config` 缺字段就自己兜一个默认值，这是上一轮 8 条漏填的直接来源；改成「真源没有就报出来」。
2. **能力字段必须带出处**。每条模型记 `source`（`site:<modelMatch>@<baseUrl>` / `manual` / `current` / `none`）与 `confidence`，`none` 的条目在报告里单列，不许拿 1M 顶上去。
3. **一次写入一个落点**。三个 `*_sync.py` 的写入段（`workbuddy` 364-371 / `qoder` 191-199 / `qwen` 345-352）收敛到 `providers/_sink/` 单点，谁要写兼容投影 `provider_config` 都走它；DSH 侧只由 `dsh_sync.py` 写 `cordis.patch.yml`。

### 3.1 能力字段为什么现在是错的

| 事实 | 证据 |
|---|---|
| 现网 19 条规则中 9 条带 `properties`，10 条只有 `optionSpecs.reasoningLevel` | `provider_config.json` 逐条核对（缺失：Gemini-AIS / Beam / Conatus / Iceman / Qwen-3.8-Max / Qwen-3.8-Flash / MiMo-2.6-Flash / Claude-Haiku-5.5 / Muse-Spark1.3 / GPT-6-Luna） |
| 这 10 条在运行时被 builtin 通配规则兜住 | `third-party/zcode/zcode-builtin.json` → `modelConfigRules.modelRules[0]`：`modelMatch: ".*"`，`contextWindow 1000000` / `maxTokens 128000` / `supportsToolCall true` / `supportsImage false` |
| 真值其实在仓里，只是没匹配上 | 同文件 `modelConfigRules.providerSiteRules` 54 条，27 条带能力字段，按 `(modelMatch, apiTypeMatch, baseUrlMatch)` 三元组生效；我们过去拿**显示别名**和 `127.0.0.1:7871` 的 baseUrl 去匹配，规则要的是 `deepseek-v4\.1-flash` 与 `https://opencode\.ai/zen/go/v1/?` |
| 映射现成 | `~/.zcode/v2/model-alias-map.json` 每条模型带 `base_model`，`chain[]` 每跳带 `base` / `protocol` / `channel`，正好拼出匹配三元组 |
| 后果 | ZCode / DSH 都按 `contextWindow` 定压缩阈值；1M 的声明把阈值推到 800k，长会话才会突然涨 token 与延迟 |

修法见 §4 批 1：`tools/model_caps.py` 从 alias map 反查 site 规则，把每条模型的能力字段连同出处生成 `catalog/model_caps.json`，`--check` 与现网逐字段比对。

**已落地（2026-11-11）**：光有「规则里写了什么」还不够 —— 规则只能证明「没写」，证明不了「真实上限」。新增 `tools/caps_upstream.py` 直连上游模型接口取真值（WB 面板 / OC / QN），`model_caps.py --upstream` 用真值压过规则解析结果，`--apply-source upstream:` 保证**规则推断值不落盘**。20 条里 16 条已是接口实测值，剩 Gemini×2 / Qwen-3.8-Max / HY3-X 四条标 `source=none` 不伪装。细节见 [CAPABILITY-AUDIT.md](CAPABILITY-AUDIT.md) §9。

---

## 4. 落地批次

| 批次 | 内容 | 验收 | 状态 |
|---|---|---|---|
| **批 1 能力真值** | `tools/model_caps.py`（解析 + `--check` / `--apply --target`）、`catalog/model_caps.json`（真源）、`tests/test_model_caps.py`；备份后把 11 条补进 `provider_config.json` | `--check` 覆盖 20 条、`unittest` exit 0、`provider_config` 与 `cordis.patch.yml` 逐字段一致 | 已落地 2026-11-11（见 §3.1） |
| **批 2 命名去 ZCode + DSH 适配** | 6 个脚本改名（`workbuddy_zcode_sync.py`→`workbuddy_sync.py`、`workbuddy_probe_zcode.py`→`workbuddy_probe.py`、`zcode_effective_body.js`→`effective_body.js`、`qoder_zcode_sync.py`→`qoder_sync.py`、`qoder_probe_zcode.py`→`qoder_probe.py`、`qwen_zcode_sync.py`→`qwen_sync.py`）+ 路径引用与自造 env 别名同批改；门面主语改「DSH 主宿主 + 各类 agent」；新增 `tools/agent_profiles.py` | `check-docs` / `check-project` / `unittest` 全绿；第一方代码旧脚本名零残留；`sync-models.ps1` 夹具跑通并比对产物 diff | **本轮落地（2026-11-11）** |
| **批 3 DSH 控制面** | `~/.dsh/plugins/src/modelbus-control/`：`llm/stream` 改写 provider/model 做路由，`ctx.webServer.register` 开 `/api/modelbus/*`（catalog / route / observe / budget） | 插件在本机 profile 加载成功；`/health`、`/v1/models` 契约不变 | 待排 |
| **批 4 多 agent** | 已是当前架构的扩展维度：`tools/agent_profiles.py` 给每类 agent 提供只读投影；per-agent 预算与冷却按 `X-Agent-Id`（或 preset id）分桶，`chainBudgetSec` / 冷却表按桶存 | 两个 agent 并发不断言互相污染；单 agent 行为与现在一致 | 接口本轮落地；分桶按 §6 演进 |

批 1 不动网关、不动长驻进程，只读配置 + 写一个副本后再落真身（`provider_config.json.bak-<时间戳>`，失败可秒回滚）。

---

## 5. DSH 侧接缝（哪些能用，哪些我们自己扛）

| 能力 | DSH 现状 | 本仓怎么接 |
|---|---|---|
| 模型目录写回 | 只读 `cordis.patch.yml`，消费字段白名单：`contextWindow` / `defaultMaxTokens` / `inputModalities` / `reasoning.efforts` / `systemPromptUpdate` / `toolUpdate` + 选择器 badge；`cost` / `vendor` / 通用 `capabilities` **不被读** | `tools/dsh_sync.py` 只投这几个字段，多投等于自语 |
| 路由改写 | `ctx.llm`（`registerAdapter` / `listModels` / `resolveModelInfo`）+ `llm/stream` waterfall，官方注释明确可用于 routing | 批 3 的插件在 waterfall 里改 provider/model，不走代理进程复活 |
| 按 agent 选模型 | 四条路：`agent-default-model`（Host 级默认）、session 级 GUI 选择（子会话继承、改设置只影响新会话）、subagent 的 `modelSelection` / `modelDiscovery`、preset **没有** model 字段（只能塞服务插件） | 粒度只到 provider；per-agent 上游组 / 权重 / 冷却必须在 zgate 侧做 |
| 外部服务接入 | 插件 `ctx.webServer.register`（宿主不鉴权，route 自理）、Typert RPC / `@Remote`、`dsh-sdk-jsonrpc-server`（stdio 按 sessionId 驱动）、`dsh --profile headless --json` | 控制面走 `/api/modelbus/*`，每条自己校验 token |
| 跨上游竞速 / 冷却记忆 / 额度台账 / 计价 / 别名 / 目录写回 / 外部调度 / 每 agent 独立工作目录 | **DSH 侧没有** | 保留在 zgate + `tools/`，这是本仓的长期价值，不是过渡物 |

结论：**DSH 负责 agent 运行时，ModelBus 负责模型供给与路由策略**。两者边界就是 `cordis.patch.yml`（目录）与 `llm/stream`（路由改写点）。

---

## 6. 多 agent 适配（DSH 主宿主的当前架构）

- 计账维度：请求头 `X-Agent-Id`（缺省 `default`），zgate 侧 `bucket(agentId)` 挂 `chainBudgetSec`、冷却表、并发上限；不引入新进程。
- 投影维度：`tools/agent_profiles.py` 按 `catalog` 为每类 agent 生成**只读**的 `cordis.patch.yml` 片段（同一份映射投影成多份）；本轮已落地函数签名、`--list` / `--check` 与「写仍单写者」红线，per-agent 分桶预算见上一条。
- 隔离红线：per-agent 只允许**读**同一份 catalog；写 provider_config / patch 仍然单写者，避免多 agent 并发写同一份配置。

---

## 7. 顺手要清的过期口径（本轮已收口）

2026-11-10 审计实测到的 8 处，本轮逐条核对并按「已修 / 历史标注保留」收口（改一行就够，不重写整篇）：

| 位置 | 问题 | 本轮状态 |
|---|---|---|
| `docs/ARCHITECTURE.md:251,331` vs `:75-76` | 同篇「四组」与「三组」打架，现役是三组 | 已修：`:251` / `:331` 均为三组；`:53` / `:309` / `:379` 的「四组」属 §1 历史快照与去路由化推演，保留 |
| `docs/QODER.md` 六处 vs `:92` | 同上 | 已修：`:19` / `:92` 已标「旧文档四组已并组」 |
| `docs/TROUBLESHOOTING.md:356,388` vs `:329` | 组数不一致 | 已修：三处均为三组 |
| `docs/MAINTENANCE.md:12` | 时点倒挂 | 已修：`:10-12` 已标「历史口径，10-28 已并为三组」 |
| `docs/PITFALLS.md:73-76` | 空 map 清单过期 | 已修：`:73-76` 改为「历史手法，现网 0 实例」 |
| `tools/model_alias.py:366` | 注释称「dsh_sync 兜底 1000000/128000」 | 已修：现注释为「不写键，落宿主自己默认值，不会兜 1000000 / 128000」 |
| `docs/ARCHITECTURE.md:52-56,316` | 把已退役的 `zcode_gateway_watch.ps1` 当现状与回退命令 | 已修：`:46` / `:52` / `:316` 均标「已退役 / 不再作为回退」 |
| `docs/MODEL-QUICK-REF.md:102` / `docs/UPSTREAM.md:351` | 死路径与悬空修订引用 | 已核：`:102` 的 `go_model_sync.py` 路径在位，`:351` 的 PITFALLS §2 在位；`docs/MODEL-QUICK-REF.md` 头部自带「历史快照」声明，按 `AGENTS.md:100` 冻结 |

本轮新增收口 1 处：`docs/MODEL-PROVIDERS.md:739` 原写「当前 ZCode 里配了空 map 的模型」，与现网
`providerModelRules` 19 条 / 空 map 0 条冲突，已改为历史清单口径并指向 `docs/PITFALLS.md` §2。

---

## 8. 验收口径（照跑即可）

```text
python -B -m unittest discover -s tests -q
python -B tools/check-project.py
python -B tools/check-docs.py
python -B tools/dsh_sync.py --check
python -B tools/model_caps.py --check
```

前四条必须 exit 0；最后一条在批 1 落地后必须 exit 0，非 0 即代表 `catalog` 与现网配置漂移，按输出逐字段修，不许改门禁。
