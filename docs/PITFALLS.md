# 踩坑总汇

> **一句话**：这里解释**为什么**会出这些故障 —— 每一条都对应一次真实的排查，
> 机制讲清楚，步骤去 [TROUBLESHOOTING.md](TROUBLESHOOTING.md)。
>
> **读法**：标 **【通用】** 的坑换任何供应商都成立（ZCode 客户端侧的行为）；
> 标 **【实例 A】/【实例 B】** 的是本仓两个示例供应商特有的上游行为。

| 标记 | 适用范围 |
|---|---|
| **【通用】** | ZCode 客户端侧 —— 换任何供应商都成立 |
| **【实例 A】** | OpenCode-Go 特有 |
| **【实例 B】** | WorkBuddy2API 网关特有 |

---

## 1. 协议放错 → 400 `ModelProtocolUnsupported` 【通用】

**现象**：模型在某个 provider 下请求直接 400，报错里带 `ModelProtocolUnsupported`
或 `does not support this protocol`。

**机制**：OpenCode-Go 的模型分三种协议，**每个模型只认自己那一种**：

| 协议 | 端点 |
|---|---|
| `openai-chat-completions` | `/zen/go/v1/chat/completions` |
| `anthropic-messages` | `/zen/go/v1/messages` |
| `openai-responses` | `/zen/go/v1/responses` |

ZCode 的 provider 由 `api.type` 决定端点。**把模型塞进错误协议的 provider，
上游直接拒。** 这是本仓最大的一个坑 —— 一次探测实测里 34 个模型有 8 个在 chat 协议下
返回 `ModelProtocolUnsupported`（`grok-4.6`、`grok-4.7`、`gpt-6-luna`、`gpt-5.6-luna`、
`claude-haiku-5-5`、`minimax-m2.7`、`muse-spark-1.2/1.3-contributor`、
`gemini-4-argon-contributor`）。

**同族错误**：鉴权头也**分协议** —— `chat/completions` 与 `responses` 认
`Authorization: Bearer <key>`，`anthropic/messages` **只认** `x-api-key: <key>`。
用 Bearer 打 messages 会 401 `Go requires a credential`。

**解法**：按协议分 provider（本仓的「主力 / 免费 / 低耗 / 高耗 / 对话 / 响应」就是
这么分的），模型清单见 [MODEL-PROVIDERS.md](MODEL-PROVIDERS.md) §2。

---

## 2. ZCode 内置通用规则无条件发思考字段 → 400 【通用】

**现象**：`curl` 手搓同样的模型能通，**在 ZCode 里一发就 400**。

**机制**：ZCode 的内置规则 `modelConfigRules.modelApiRules` 里，第 3 条是
`openai-chat-completions` 的通用规则 `.*`，它的 `reasoningLevel.map` 表达式会
**无条件**注入四个字段：

```json
{
  "thinking": { "type": "enabled" },
  "enable_thinking": true,
  "reasoning_effort": "high",
  "reasoning": { "effort": "high" }
}
```

它**不检查模型是否支持**。上游不认其中任何一个字段就 400。

WorkBuddy 网关更糟一层：它的出站逻辑**只**重写 `reasoning_effort`（按模型
`supportedEfforts` 降级），**ZCode 发的 `thinking` / `enable_thinking` / `reasoning`
字段网关不删，原样透传给上游** → 上游不认就 400。

**解法**：

1. **探测必须用 ZCode 真实请求体**，不能拿裸 body 试 ——
   `providers/workbuddy/workbuddy_probe_zcode.py` 就是干这个的（先算真实 body，失败再退
   slim variant）。
2. 给模型配 `optionSpecs.reasoningLevel.map = "{}"` —— **发空 map 覆盖掉通用规则**，
   一个思考字段都不发。**2026-11-10 实测：现网 20 条规则里 0 条用这种写法**，早先那批
   （`beam-free`、`minimax-m3` 等）已经并组改名，别照旧清单去找；要复现这个手法，
   写前先跑 `python tools/model_alias.py --check` 看清现场。
3. 需要「显式关掉」而不是「不发」时，用 `{"thinking":{"type":"disabled"}}`。

**「curl 能通但 ZCode 400」的根因永远是这一条**，不是配置写错、不是模型下线。

---

## 3. `modelMatch` 是全匹配正则，不是子串匹配 【通用】

**机制**：ZCode 匹配规则用的正则是 `^(?:pattern)$`（大小写不敏感）。
所以：

- 写 `deepseek` **不会**匹配 `deepseek-v4.1-flash`；
- 想匹配前缀必须自己写 `.*deepseek.*`；
- 内置规则里 `.*deepseek-v4[.-]1-flash.*` 同时覆盖 `deepseek-v4.1-flash` 和
  `deepseek-v4-1-flash`（`[.-]` 兼容两种分隔符）。

**推论**：`cn:deepseek-v4.1-flash` 这种带前缀的 modelId，**内制的
`.*deepseek-v4[.-]1-flash.*` 也能匹配上**（因为是 `.*` 包裹的模式）——
但如果你自己写规则只写 `deepseek-v4.1-flash`，就**匹配不到** `cn:deepseek-v4.1-flash`。

**解法**：写规则一律用 `.*` 头尾包；改完用 `providers/workbuddy/zcode_effective_body.js`
验证命中的是哪一条。

---

## 4. 规则按序叠加，后者胜 【通用】

**机制**：ZCode 的 `ModelConfigRules.resolve()` **按规则列表顺序**遍历，
把每条命中规则的 config **覆盖**到累加器上 —— **后面的规则覆盖前面的**。

所以「通用规则在前、专属规则在后」这个布局是**必需的**：通用规则无条件注入思考字段，
专属规则（`.*deepseek-v4[.-]1-flash.*` 等）排在后面才能把它盖掉。

`optionSpecs.reasoningLevel.map` 也是同一个语义：**最后一条命中的规则**的 map 生效。

**坑点**：

- 往 `modelApiRules` 里**中间**插一条通用规则，会把后面所有专属规则的覆盖打乱；
- 自定义规则如果不排到通用规则**之后**，就会被通用规则盖回去；
- `apiTypeMatch` 不同的规则**不互相覆盖**（`anthropic-messages` 的规则不影响
  `openai-chat-completions` 的请求）。

**解法**：改规则后必须重算真实 body 验证，别凭记忆。

---

## 5. 探测必须用 ZCode 真实 body，且间隔 ≥ 20 秒 【通用机制 + 实例 B 的间隔值】

**现象（其一）**：探测结果全是 200，但 ZCode 里实际用不了（→ 见 §2）。

**现象（其二）**：探测跑到一半，接口开始返回 `no_healthy_account` / 429，
甚至**网关进程直接消失**。

**机制**：WorkBuddy 网关的账号池只有 4 个号（global 只有 3 个），
网关有**熔断与冷却**：一个号被快速打满就进冷却，池子里就没号可用了。
实测**4 秒间隔会把 global 全部打进 `no_healthy_account` 冷却**（首次探测即如此）。
必须 **≥ 20 秒间隔**。

同一现象在路由器那条线上也出现过：10 个子代理同时密集探测 → 负载冲到 2.6 → 看门狗复位；
批量审计**必须限速、串行化**。

**解法**：

- 探测间隔 ≥ 20 秒（`--sleep 20`）；
- 探测前先确认网关活着：`curl http://127.0.0.1:7863/status`；
- 探测脚本**支持断点续跑**（缓存写盘），中断后重跑不会重来一遍。

---

## 6. 免费池日配额耗尽 → 429（**不是配置问题，也不是模型下线**） 【通用】

**现象**：某个模型突然开始 429，错误里的 `Retry-After` 指向**次日 00:00 UTC**。

**机制**：免费 / 促销档模型有**日配额**，用完就是 429，冷却到次日零点。
这跟模型是否被弃用、配置是否写错**完全无关**。

**关键判断**：看到 `Retry-After` 落在次日 00:00 UTC，就知道是**日配额耗尽**，
**等次日再试**。此时去改配置、去重探、去改 provider 归属都是白费力气。

**另一个容易误判的点**：探针把 429 归类成 `rate_limited`，脚本会把它当成
「模型不可用」而排除掉 —— 于是模型从清单里**消失**了，看起来像「模型被下架」，
其实只是**当天用完了**。重探一次就回来了。

---

## 7. `modelProtocolUnsupported` 样本与协议归属 【实例 A 的样本】

**现象**：批量探测里大量 400，全是 `ModelProtocolUnsupported`。

**这不是故障，是这台机器的正常结果** —— 它说明**协议探测在正常工作**，
只是那个模型不归 chat 协议管。协议归属表见 [MODEL-PROVIDERS.md](MODEL-PROVIDERS.md) §2.8。

**但要注意两种 400 的区别**：

| 报错 | 含义 | 处理 |
|---|---|---|
| `ModelProtocolUnsupported` | 这个模型不走这个协议 | 换协议，别记成故障 |
| `trains on request data` / 隐私设置拦截 | workspace 没开「付费且训练数据的端点」 | 去 Console 开权限，脚本解决不了 |
| `401` | 凭据或权限问题 | 脚本解决不了，不收录 |

---

## 8. ZCode 配置会被界面覆盖 【通用】

**现象**：脚本写完配置、ZCode 也热重载了，但过了几分钟配置又变回原样。

**机制**：ZCode 的 provider 设置界面保存时**整份写回** `provider_config.json`，
把脚本刚写的部分覆盖掉。脚本写完那一刻是对的，几分钟后就回退了。

**解法**：**写配置期间不要在 ZCode 界面里同时改**。要改界面就先改完再跑脚本。

---

## 9. 明文凭据会随仓库一起走 【通用】

**现象（未来）**：仓库上传到公开 GitHub，**API key 一起公开了**。

**现状**：`providers/opencode-go/probe/` 下的 `probe_models.py`、`probe_protocols.py`、
`bench_models.py`、`bench_clean.py`、`thinking-off-probe.js` **已改为从 `OPENCODE_GO_KEY` 环境变量读取**；
`provider_config.json` 的 `.bak-*` 备份里也有 key。

**解法**：

- 脚本从**环境变量**读凭据（`WB_GATEWAY_KEY` / `WB_GATEWAY_BASE` /
  `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` / `ZCODE_BUILTIN` / `OPENCODE_SESSION`），
  规则见 [AGENTS.md](../AGENTS.md) §2；
- `.gitignore` 已排除 `*.key`、`*_key*`、`*.env`、`*.bak-*`；
- **上传前逐个 `grep` 一遍**，别靠 `.gitignore` 兜底。

---

## 10. 硬编码路径在拆仓后失效 【通用】

**现象**：脚本跑完了，但产物没落在预期位置。

**机制**：脚本里写死了某个绝对路径（尤其是**写死某个人的主目录**），
换台机器就失效 —— 报告落到旧目录、配置读的是不存在的路径。

**历史实例**：`providers/opencode-go/ops/go_model_sync.py` 的 `REPORT_DIR` 原先指着拆仓前的旧仓库目录，
报告会落到旧仓库去；ZCode 配置路径原先写死成某个开发者的主目录路径。
**拆仓时已修**：报告目录改为按脚本位置推导的本仓 `evidence/`（保留 `GO_SYNC_REPORT_DIR` 覆盖口）；
配置路径默认值改为按**当前用户主目录**推导（仍可用 `--config` 覆盖）。

**解法**：保持"路径由脚本自身位置推导 / 按当前用户主目录推导"这条约定 ——

- 新增脚本时用 `os.path.dirname(os.path.abspath(__file__))` 推导仓内路径；
- 涉及用户主目录的路径用 `os.path.expanduser("~")`，**不要写死用户名**；
- 提供环境变量或命令行参数覆盖口。

---

## 11. `wb_pricing.json` 的生成脚本（已补上，但别再手工维护） 【实例 B】

**现象**：想重探 WorkBuddy，脚本直接退出：
`wb_pricing.json missing - fetch pricing first`。

**机制**：价格表（模型倍率 / 上下文 / 输出上限 / effort 档位）是分档的**唯一输入**，
而它过去**只能手工维护** —— 全仓没有任何脚本能生成它。

**为什么重要**：限时免费会到期、倍率会调整，**价格表过期 = 分档过期 =
清单里的模型实际比标称的贵**。

**解法（已落地）**：`workbuddy_fetch_pricing.py` —— `GET /panel/api/models` → 归一化 →
写 `cache/wb_pricing.json`（写前自动备份），并打印**倍率变化 / 新增 / 下架**的摘要。

```bash
cd workbuddy
python workbuddy_fetch_pricing.py            # 写入
python workbuddy_fetch_pricing.py --dry-run  # 只看差异
```

字段含义见 [MODEL-PROVIDERS.md](MODEL-PROVIDERS.md) §4；
刷表频率与注意事项见 [MAINTENANCE.md](MAINTENANCE.md) §1.3；
**通用做法**（换供应商照这个做）见 [MAINTENANCE.md](MAINTENANCE.md) §1.1。

---

## 12. 一个 provider 只能一个 `baseUrl` → 跨上游必须路由 【通用】

**现象**：想把 WorkBuddy 模型和 OpenCode-Go 模型放进同一个 provider，结果要么 404 / 401，
要么只有一边能用。

**机制**：ZCode 的 `providerConfigRules[].config.api.baseUrl` 是 **provider 级**的；
模型级 `modelConfigRules` 只有 `enabled` / `properties` / `optionSpecs`，**没有** `baseUrl`。
一个 provider 下的所有模型共用同一个上游地址和 key，不能按模型换上游。

**解法**：本仓用 `gateways/zgate` 做本地入口 —— 四个 chat provider 指向
`http://127.0.0.1:7871/v1`，路由按 model 前缀把 `cn:` / `global:` 转到 WorkBuddy 网关，
其余转到 OpenCode-Go。代价是多一个常驻进程；它随 ZCode 起停（见
[MAINTENANCE.md](MAINTENANCE.md) §8）。**不要把路由端口暴露到公网**，也不要把两个
上游的 key 混进同一个 provider。

## 13. 凭据扫描的占位符不能整行放行

**现象**：`tools/check-secrets.py` 对「示例与真值同一行」完全失明。

**根因**：`PLACEHOLDER` 命中后整行 `continue`；行内出现 `example.com` / `<...>` /
`YOUR-` 时，同一行的真 `oc_sk_` / `sk-` token 不会被报。

**解法**：只豁免匹配片段本身（`m.group(0)`），示例 URL 仍按预期放行。

## 14. `gateways/upstream/workbuddy/` 是上游独立 clone，改动只在本地

**现象**：在网关里修了日志脱敏、示例配置、启动告警，`git status` 却什么都不显示，
CHANGELOG 里写的条目在远端仓里找不到对应代码。

**机制**：主仓 `.gitignore` 用 `/gateways/upstream/workbuddy/` **整目录**排除 —— 里面是
`auths/` 账号凭据、`config.json`（api_key）、`data/` 运行时状态与 `wb2api.exe`。
更新方式是 `git -C gateways/upstream/workbuddy pull --ff-only`，不是本仓管理。

**怎么避**：改网关代码前先确认它在不在 `git ls-files` 里；本地改动单独记账，
不要写进本仓 CHANGELOG（那里只记随仓分发的内容）。二进制重建后留 `.bak` 再替换。

## 15. 首次启动的日志与示例配置都不能带凭据

**现象**：网关首次启动时把自动生成的 `api_key` 明文打进 stdout；守护器把 stdout
落到 `logs/gateway.stdout.log`，等于凭据明文落盘。示例配置里的 `api_key` 是
`test_key`，而 README 的部署步骤要求 `cp` 这份文件。

**解法**：启动日志只提示「已写入该文件」，不打印值；示例配置用 `CHANGE_ME` 这类
一眼就知道要改的占位符；`api_key` 为空或仍是占位符、且监听地址不是回环时打 WARN。

**下次怎么避**：任何「首次运行自动生成凭据」的路径，都当成凭据泄露面审一遍 ——
日志、示例文件、错误信息、面板回显四个地方都要看。

## 16. 显示名不是上游模型 id，旧 sync 不能直接拿去探测

**现象**：`model_alias.py` 把配置里的模型重命名成 `DeepSeek-4.1-Fs` 这类
显示名后，`go_model_sync.py` 的「跑不通即清」会把显示名当上游模型 id 发给
`opencode.ai/zen/go/v1`。上游 404 → 判定「已不在任何清单」→ 下一次 `--apply` 全部
prune。它同时也认不出这些模型已经配置过，会把整个 Go 目录当新模型重评估一遍。

**机制**：显示名只对统一路由有意义（7871 读 alias map 还原上游名），上游网关没有
这个名字。任何「拿配置里的模型 id 直接打上游」的脚本，在重命名之后都会失效。

**解法**：体检前先读 `~/.zcode/v2/model-alias-map.json`，把显示名还原成
`upstream` 再探测；`channel` 是 `WB` / `QD` 的直接跳过（非 Go 套餐）。
`go_model_sync.py` 的 `display_alias()` + `probe_targets()` 就是这么做的。

**下次怎么避**：凡是消费 `personalModelIds` 并直接请求上游的脚本，先问一句
「这个 id 是显示名还是上游 id」；显示名一律经 alias map 还原，删除时仍用显示名
（配置里存的是它）。

## 17. 从 JS 移植时，`url.search` 自带 `?`，Go 的 `RawQuery` 不带

- **现象**：任何带查询参数的请求都 404/400，日志里路径和 query 粘在一起
  （`POST /chat/completionsstream=1`）。
- **根因**：JS 的 `url.search` 返回 `?a=b`，Go 的 `u.RawQuery` 只返回 `a=b`；
  移植时直接 `base + path + search`，少了一个分隔符。
- **解法**：拼接 query 时显式补 `?`（或在 `normalizePath` 里统一返回带 `?` 的串），
  并补一条「上游确实收到 query」的端到端测试 —— 只测 path 的用例发现不了。
- **验证**：`go test ./internal/router -run TestQueryString`。

## 18. 用 `dirname` 层数推仓库根，脚本一搬家就落错目录

- **现象**：同步报告跑到 `providers/evidence/`，与已入库的 `evidence/` 分家，
  下一次大扫除才发现。
- **根因**：`os.path.dirname(...)` 叠了三层，脚本在 `providers/opencode-go/ops/`
  下时只到 `providers/`；脚本从 `scripts/` 搬过来后层数没跟着改。
- **解法**：路径按「相对仓库根的固定层级」写，并在注释里标明层级；或者用
  `git rev-parse --show-toplevel` / 显式配置项。改目录结构时全局搜 `dirname(`。
- **验证**：跑一次 `--dry-run`，确认报告路径在 `evidence/` 下。

## 19. 价格源静默失败会把整个渠道的模型从配置里剔除

- **现象**：某次同步后某渠道的模型全没了，日志里只有「收录 N 个」，没有告警。
- **根因**：价格缓存读不到时函数返回空表，下游把「没有价格」当成「不可用」直接
  `continue`；`--apply` 随后重写配置，等于整批删除。
- **解法**：价格源不可用必须 stderr 告警；整渠道 100% 无价时拒绝写入
  （提供显式 `--force-unpriced` 绕过），并把「因缺价未收录 N 个」打进摘要。
- **验证**：临时改名价格缓存跑一次 `--apply`，确认退出码非零且配置未变。

## 20. 裸 `go build` 会把无窗 zgate 覆盖成控制台程序 【通用】

- **现象**：开机自启时弹出一个 cmd 控制台窗口，标题是快捷方式名
  （「ModelBus zgate」）；关掉那个窗口等于杀掉网关，模型全挂。
  有时窗口是「可见的」而不是最小化 —— 快捷方式里 `WindowStyle = 7`
  只对**有窗口**的程序生效，对控制台子系统程序不等于隐藏。
- **根因**：Windows PE 头里的 `Subsystem` 字段决定程序启动时要不要分配控制台。
  - `2` = `WINDOWS_GUI` → 无窗（设计要求）
  - `3` = `CONSOLE` → 一启动就分配一个真控制台窗口
  `-H windowsgui` 是**链接期** flag，只在那一次编译里生效。事后从源码看不出来，
  只能读产物的 PE 头。
- **回退是怎么发生的**：`go build` 在**单包**模式下会把可执行文件写到当前目录，
  所以在 `gateways/zgate/` 里跑一次裸 `go build .`，就把之前用
  `-ldflags "-H windowsgui"` 编好的无窗版**原地覆盖**成控制台版。
  （`go build ./...` 是多包模式，Go 只编译不落盘，**不会**覆盖 —— 实测确认。）
  产物在 `.gitignore` 里（`/gateways/zgate/*.exe`），所以 `git checkout` 救不回来。
- **为什么难发现**：覆盖发生在**编译期**，弹窗发生在**下次开机**，
  中间隔着一次重启；日志、git 历史、进程列表都看不出因果。
- **解法**：编译入口收口到 `gateways/zgate/build.py`（带 flag + 强制校验 PE 子系统）；
  检查用 `go vet ./...`，别在 `gateways/zgate/` 里裸跑 `go build`。
- **验证**：`python gateways/zgate/build.py --check` 打印
  `Subsystem = 2 → WINDOWS_GUI（无窗）`；`--cross-check` 会在临时目录交叉编译一份
  windows/amd64 再校验，CI 用这条（Linux 上也能真跑起来）。
- **2026-11-09 补充（Win11 终端接管）**：计划任务 / 快捷方式拉起**控制台子系统**程序时，
  Windows 11 的默认终端会让 `WindowsTerminal.exe`（父进程是 `svchost.exe` 的 Task Scheduler）
  接管它的 console 并显示成可见窗口，标题就是 exe 路径 —— 该 `wt` 进程的 `MainWindowHandle`
  非 0，而 zgate 自身 `MainWindowHandle` 是 0，很容易误判成"窗口是 zgate 弹的"。
  可靠的判断方式是对着 `wt` / `OpenConsole` 进程数做前后对照，而不是看标题。
  根治有两条，缺一不可：① 产物是 `Subsystem = 2`；② 启动链路用
  `CreateNoWindow`（`ProcessStartInfo` + `UseShellExecute=$false`）包一层，
  别让 Task Scheduler 直接 exec 控制台程序。现行自启见 `docs/MAINTENANCE.md` §8.1。
- **2026-11-09 补充（换版路径收口）**：换版一律走 `python gateways/zgate/build.py --candidate`
  （编到 `zgate.candidate.exe`，不覆盖运行中的 `zgate.exe`）+
  `tools/zgate-lifecycle/restart-zgate.cmd` 受控换版；**禁止在会话里裸用 `Start-Process` /
  `cmd /c` 拉起 zgate** —— 这样起的进程落在 CMD/DSH 会话的 Job Object 里，会话结束整棵进程树
  被回收（实测 2s 内消失）。换版流程、双计划任务自启与失败回滚正本见
  [ZGATE-LIFECYCLE.md](ZGATE-LIFECYCLE.md)；`/admin/reload` 只热加载 `zgate.json` 的策略 /
  空闲 / 窗口，换 Go 代码必须重启实例（`gateways/zgate/internal/supervisor/supervisor.go:473`）。

## 21. 上游握手超时留 15s，会把一次失败拖成长尾 【通用】

- **现象**：机器人调用 `opencode.ai` 偶发 502，单次回复 22–32s；zgate 日志里
  `Post "https://opencode.ai/zen/go/v1/chat/completions": net/http: TLS handshake timeout`。
- **根因**：本机到 `opencode.ai` 走 fake-IP 透明代理，链路握手会抖（同一节点实测成功
  0.32s，坏窗口 0.6–7.7s，再往上就不返回了）。transport 的 `TLSHandshakeTimeout`
  是 15s，且 `http.Client` 没有整体 `Timeout` —— 一次坏叫要等满 15s 才回落，
  叠上 WorkBuddy 免费池的 429/503 再排队，回复就拖到 20 秒以上。
- **解法**：`TLSHandshakeTimeout` 收到 8s。**不要**顺手给 `http.Client` 设 `Timeout`：
  它覆盖整个响应体，流式（SSE）会被从中间截断，非流式的长推理也会被误杀。
- **验证**：`grep TLSHandshakeTimeout gateways/zgate/main.go` 应为 8s；
  坏窗口内单次失败的上限约为 8s，而不是 15s。

## 22. 派生数据落盘又回读 → 上游改价永久不生效 【通用】

- **现象**：上游限免到期/调价后，ZCode 里的积分和分组纹丝不动，同步报告也一直写
  「分组变化 0、链路变化 0」。2026-10-28 的 Step-5-Pre 就是这样：面板已是 x0.33、
  真实调用也在扣积分，配置里仍挂在「免费 @0.00」。
- **根因**：两层叠加。`expand_hops()` 把 alias map 里 `chain[].price` 原样带回，
  `family_entries()` 又优先用 `item["price"]`，`price_of()` 只在它是 `None` 时才跑；
  而 alias map 本身就是上一轮的输出。**输出成了下一轮的输入，一次写入等于永久冻结**。
- **为什么难发现**：`sync_report.py` 比的是「上一版产物 vs 这一版」，两边都来自同一份
  缓存时，稳定存在的偏差永远是「无变化」——报告越正常，越说明不了问题。
- **解法**：派生量（价格、分组、链路顺序）每轮从源重算，alias map 只存推不出来的
  身份信息；源里没有的 hop 直接剔除。另加 `--check`（重算 vs 现有 alias map，
  有漂移退出码 1）挂进定时任务。探测结论同理：超过 TTL 的 `ok` / `blocked` 一律
  按「未知」处理——过期的 ok 会留住死模型，过期的 blocked 会删掉活模型。
- **验证**：`python tools/model_alias.py --check` 退出码 0（幂等）；
  `python -m unittest discover -s tests -v` 里
  `test_chain_price_is_not_inherited` / `test_dead_hop_is_dropped` 通过。

## 23. 错误路径读异常属性，异常的字段契约必须先兜住 【通用】

- **现象**：上游排队（`10605` / `isQueued`）重试耗尽后，客户端什么也没收到；
  `qoder-proxy.err.log` 里是一条 `AttributeError: 'RateLimited' object has no
  attribute 'status'` 的线程 traceback，但 `/ping` 一直 200、进程也没退。
  同一时刻非流式请求拿到的是 502，而不是 429 + Retry-After。
- **根因**：两套异常并存。`UpstreamStatus` 有 `.status` / `.detail`，而排队转换
  `_as_rate_limited_for_queue()` 产出的是 `RateLimited`（只有 `.detail` / `.wait`）。
  流式 pump 的错误收尾统一写 `record_error(model, exc.status, ...)`，这个属性一缺，
  异常在 `do_POST` 里二次抛出 —— `BaseHTTPRequestHandler` 只打印 traceback，
  **不再发任何响应**。非流式路径则因为没有 `except RateLimited` 分支，掉进通用
  `except Exception` → 502，客户端看到的是「上游故障」而不是「请退避」。
- **为什么难发现**：崩在请求线程里，主线程与 `/ping` 不受影响；日志前一行还是
  HTTP 200（SSE 响应头已发），看不出请求其实没结束。
- **解法**：异常类自己承担错误路径的字段契约（`RateLimited.status = 429`、
  `retry_after` 与 `wait` 同源）；所有会进入错误收尾的聚合路径显式
  `except RateLimited` → `_rate_limited()`。**不要**在错误处理里用
  `getattr(exc, "status", 502)` 掩盖缺字段：状态码会被悄悄改成 502。
- **验证**：仓库内没有该场景的自动化测试（原记的 `tests/_test_issue71_queue_error_paths.py`
  从未入库，2026-11-04 订正）；以在线排队场景实测为准 —— 返回 `HTTP 429` 且日志无 traceback。

---

## 24. 控制台「有额度」不等于 API「能调用」；桥接基址必须带 `/v1` 【通用】

- **现象**：千问控制台「权益」页列着 506 条免费额度，但把清单直接播种进配置后，
  一部分模型请求回来 `400 InvalidParameter: Model not exist.`；换成别的写法又是
  `404 InvalidParameter: Not support`。
- **根因**两个，互不相关：
  1. 额度页是**商业化目录**，与 API 网关的可用集合不是同一份。
     `qwen3-max` / `qwen3-coder-plus` / `qwq-plus` 有额度但网关没有这些 id
     （`qwen-max` 才有）；`Model not exist.` 是唯一的判据。
  2. `zgate` 的协议桥把地址拼成 `TrimRight(base,"/") + "/messages"`，
     **不会**自己补 `/v1`。基址写成 `.../apps/anthropic` 就打到
     `/apps/anthropic/messages`，上游回 `Not support`（它的 404 不区分「路径不认识」
     与「模型不认识」，只看 `message` 字段）。
- **为什么难发现**：两种错误都是 4xx + 一句短语，`model_probe` 一律归类成
  `error`，看起来像「模型坏了」；而 `Not support` 其实是地址错，改价格/改模型都没用。
- **解法**：
  - 目录一律**先探测再收录**，不要信控制台列表（漏斗最后一层就是真实体探测）；
  - 配 `QW` 这类桥接上游时，基址写全 `…/v1`（`QWEN_BASE` 也一样）；
  - 看到 `Not support` 先查 base，看到 `Model not exist.` 才查 id。
- **验证**：`curl /health` 里 `qwen.base` 以 `/v1` 结尾；14 个收录模型
  `tools/model_probe.py` 全部 `ok`（2026-10-28）。

---

## 25. 桥接条目会抢走原型名，把聊天条目挤成 `-2` 【通用】

- **现象**：接入千问后，`GLM-5.3` / `Qwen-3.8-Max` / `DeepSeek-4-Pro` 的显示名还在，
  但指向从「Qoder 聊天」变成了「千问桥接」；原来的聊天条目改名成 `GLM-5.3-2`。
  老会话里选中的 `GLM-5.3` 于是静默换了渠道。
- **根因**：命名去重按**条目录入顺序**先到先得，而「免费组」在「高耗组」之前生成，
  桥接（messages）条目先拿到原型名，规则里「桥接那条加 `-Msg`」根本没被用上。
- **解法**：命名时先看**同一 abbr 存在哪些协议**——只要同时有 chat 与桥接，
  原型名永久留给 chat，桥接那条按协议加 `-Msg` / `-Resp`。这条与
  [MODEL-ALIAS.md](MODEL-ALIAS.md) §2 的规则一致，且与生成顺序无关。
- **验证**：`ListModels` 里 `GLM-5.3`(高耗/QD chat) 与 `GLM-5.3-Msg`(免费/QW)
  并存；`tools/model_alias.py --check` 零漂移；四组内无重复 id。

---

## 26. 合成条目过关时会被 inventory 按跳拆开，下一轮翻倍 【通用】

- **现象**：三个集合体（一条显示名派生 91 跳）写进配置后，下一轮
  `model_alias.py --apply` 里千问的模型条数从 17 跳到 117：每个跳都成了一条
  独立显示名（`qwen3-max`、`qwen-turbo`…），再下一轮还会继续膨胀。
- **根因**：`inventory()` 对配置里的每个 id 调 `expand_hops()`，而
  `expand_hops` 的语义是「把一条链展开成每一跳」，于是集合体被拆成了 91 个
  `(channel, upstream, protocol)` 单项；每项 base_model 不同 → `abbr` 不同 →
  各自成一个 family → 各自写回配置。名字还都是裸 id，因为 `ABBR` 里没有它们。
- **为什么难发现**：第一轮输出看起来完全正常（3 个池子 + 14 个单型号），
  膨胀发生在**下一轮**；`--check` 也不会报，因为两轮都是自洽的。
- **解法**：集合体在 alias map 里标 `kind: pool`；`classify()` 见到这个标记
  直接返回 `None` —— 池子只由 `pools.json` 生成，永不参与 inventory。
  配套给 `legacy` 加了守卫：带渠道前缀的 key 必须真能对上目标条目的某一跳，
  否则视为陈旧映射（否则一个旧 key 会把新模型静默指到别的条目上）。
- **验证**：连续跑两次 `model_alias.py --slot auto --apply`，alias map 条目数
  稳定在 52；`--check` 退出码 0。

## 27. 桥接模型整段缓冲 → 首字像卡死；改成流式后又必须保住回落安全 【通用】

- **现象**：走协议桥（Messages / Responses）的模型首字要等整段生成完才一次性
  吐出来（实测 Conatus 12.06s 才收到唯一一个 chunk，Qwen-3.8-Flash-Msg 5.07s
  单块），而原生 chat 模型 0.98s 就开始逐 token；用户体感是「很多模型首字很慢」。
- **根因**：`bridge.Forward` 调上游时写死 `stream: false`，收完整段 JSON 后才用
  `sseOf()` 合成一个 chat SSE chunk。上游完整生成的时间全被算进了首字。
- **解法**：`Options` 增加 `Stream` / `OnChunk`，`bridge.Forward` 在客户端要求
  流式时改调 `forwardStream`——上游按 `stream: true` 请求，边解析 SSE 边通过
  `OnChunk` 抛出 chat chunk。文本、`thinking`、`tool_use`（`input_json_delta`）、
  Responses 的 `function_call` 增量都要各自翻译。
- **代价与边界**：**每一跳都走流式**（2026-11-06 起；此前只允许链尾跳，于是「首跳就能成」
  的 messages 型号全被整段缓冲 —— 实测 Claude-Haiku-5.5 首字节 1.739s == 总耗时 1.739s、
  只有 4 条 data 行，放开后同题 2.227s / 3.676s、46 条 data 行）。回落安全靠三层兜住：
  ① 非 2xx 一定在写出任何字节之前以 JSON 返回（`finishBridge` 用 `cw.written` 判断）；
  ② 上游在流中途失败时，`bridge` 已在流内补 `[bridge stream error: …]` + `[DONE]` 并返回
  `Status: 200`（`bridge.go` 里 `if !emitted` 之外的分支），所以本来就走不到回落；
  ③ `router.attemptChain` 的回落条件加了 `!cw.written &&`，将来桥接若改了状态码，也写不出
  第二个响应体。
- **非流式那条路别再套流式的空闲上限**：非流式上游是整段生成完才吐字节，用
  `DefaultIdle = 30s` 判静默会把 >30s 的正常回答误判成 `upstream silent` 504；
  非流式改用 `DefaultIdleNonStream = DefaultTimeout`（120s），让总超时当唯一硬闸。
- **上游自己不流式就没办法**：Qoder 渠道直连实测首字 32.6s（`stream: true` 也
  一样），这是上游整段缓冲，桥接器改不了——这类模型别放主力。
- **验证**：`go test ./internal/bridge/...`（含流式文本、流式工具调用、上游报错三条用例）；
  `go test ./internal/router/ -run 'TestBridge'` 另覆盖三条：非链尾跳必须在上游完成前送出
  首个 chunk、地区 403 未写字节仍回落孪生跳、流已开始后断流（RST）只收口不回落。
  实测 `claude-haiku-5-5` / `gpt-6-luna` 工具调用流式返回 `finish_reason: tool_calls` 且参数完整。

## 28. zgate 停掉后忘了拉起来 = 全站模型不可用；启动必须带 `serve` 【通用】

- **现象**：为了让新二进制生效 `taskkill` 掉 zgate，之后用
  `start "" zgate.exe` 启动，进程立刻消失，`/health` 不通，ZCode 里所有模型
  一起报错。直接前台跑，报 `panic: slice bounds out of range [2:1]`
  （`main.loadConfig` 里的 `os.Args[2:]`）。
- **根因**：zgate 没有默认子命令，`usage()` 要求显式 `serve`；`os.Args[2:]`
  在只有 1 个参数时越界。另外 `zgate.exe` 是 GUI 子系统，用 `start` 时的参数
  传递方式容易被 shell 吞掉。
- **解法**：停旧进程 → `python gateways/zgate/build.py` 重新构建（会校验 PE
  子系统是 WINDOWS_GUI）→ 用显式参数列表启动：

  ```powershell
  Start-Process -FilePath '<工作区>\ModelBus\gateways\zgate\zgate.exe' `
    -ArgumentList 'serve' `
    -WorkingDirectory '<工作区>\ModelBus\gateways\zgate' -WindowStyle Hidden
  ```

   > ⚠️ **警示（2026-11-09）**：上面的 `Start-Process` 仅作「手工前台排查」的历史示例，
   > **不是现行自启 / 换版入口**。会话里这样拉起的进程归属 CMD/DSH 会话树，父进程退出后
   > 2s 内消失；现行自启走计划任务 `\ModelBus-zgate-hidden`，换版走
   > `tools/zgate-lifecycle/restart-zgate.cmd`，正本见 [ZGATE-LIFECYCLE.md](ZGATE-LIFECYCLE.md)。

  起来后必须验证：`netstat -ano | grep 7871` 有 LISTENING，且
  `curl http://127.0.0.1:7871/health` 返回 `"ok":true`。
- **教训**：**这是单点故障**。重启网关属于「会切断用户所有模型」的操作，
  停机窗口要压到最短，重建失败就立刻回退旧二进制，不能停着慢慢查。

## 29. 渠道级「一律免费」定价会把将来的付费模型也记成 0 【通用】

- **现象**：`price_of()` 对 `QN`（七牛）渠道无条件返回 0（只判 `QN_FREE_UNTIL`
  日期），不校验模型 id 是不是 `-free`。当前只收了两个限免模型所以看不出问题，
  一旦将来播种任何七牛付费模型，它会以 0 价进免费组，扣费完全不可见。
- **根因**：把「这家渠道现在有免费活动」当成了「这家渠道的一切都免费」。
- **解法**：按 **模型 id** 判定优惠，不按渠道。`QN` 分支先检查
  `upstream.endswith("-free")`，不是就返回 `None`（缺价 → 剔除）。千问的
  预付额度仍是渠道级（整账号共用一份 ¥300），所以 `QW` 保持渠道级。
- **验证**：`tests/test_model_alias_price.py` 的价格派生用例；`--check` 零漂移。

## 30. 组内排序交给「厂商最低价」会把常用模型挤到列表末尾 【通用】

- **现象**：省钱组按 `vendor_min`（每个厂商的最低价）排序后，MiMo 这类价格
  不是最低但最常用的模型被排到列表最后，用户要在选择器里翻到底才能点到。
- **根因**：排序键选了「价格」这个与使用频率无关的量，还按厂商聚合，等于让
  便宜厂商永久霸占前排。`set` 本身更是无序的，两次运行顺序还可能不同。
- **解法**：**顺序权收归人工有序列表**。`MAIN_ORDER` / `LOW_ORDER` 是唯一权威，
  `MAIN_IDS` / `LOW_PICKS` 由它们派生（`set(...)`），组内按列表下标排，未命中
  名单的排最后。这样「常用的在最前」是写死的，不受价格波动影响。
- **配套规则**：省钱组只留**各厂 1–2 个代表作**（小米留 Flash + Pro），前旗舰 /
  上一代（MiMo-2.5、GLM-5.2、Qwen-3.7 等）不进组；不在名单里的模型直接不收录，
  而不是「收进来排在后面」。
- **验证**：`--check` 零漂移；`/v1/models` 里组内顺序与 `LOW_ORDER` 逐项一致。

## 31. 模型自述不可信；集合体/中转模型没有单一作者 【通用】

- **现象**：问七牛 `qiniu/conatus-free`「你是谁」，它答「我是 deepseek-v4.1-flash」；
  但七牛官方把它描述成**多种模型的集合体**。问 `iceman-contributor-free`，它答
  「微软 AI 开发的 MAI 大语言模型」；而 `GET /v1/models` 的 `owned_by` 只有
  `opencode`（转售方），没有作者字段。两处自述都拿不出可核对的依据。
- **根因**：①自述是模型的生成结果，不是元数据 —— 见过大量带自家名字语料的模型会
  复读训练语料里的身份；②中转/聚合类产品（集合体、路由池、contributor 免费池）
  **本来就没有单一作者**，后端可能按请求换供应商，问「你是谁」本身就没有稳定答案。
- **口径**：**以 `GET /models` 的 `id` / `owned_by` 与结算账目为事实，自述只当参考**。
  `owned_by` 是转售方时不要推断模型作者；集合体只记「它是聚合体」，不追作者。
- **实操建议**：判断「值不值得用」看 AA 榜单分数、单价、上下文、实测速度与稳定性，
  不要用「它说自己是谁」下结论；同一模型两次自述不一致是正常现象，不是接口坏了。
- **验证**：`curl -s https://opencode.ai/zen/go/v1/models -H "Authorization: Bearer $KEY"`
  看 `owned_by`；七牛同理看 `/v1/models` 元数据。

## 32. 上游「连上但不说话」要设空闲上限；429 要先退避再摘跳 【通用】

- **现象 1**：七牛 Conatus（聚合端点）会接受连接后**一个字节都不发**，唯一的兜底是
  桥接 `DefaultTimeout`(120s) —— 用户端表现为「2 分钟没响应」，重试有时又好。
- **现象 2**：主力 DeepSeek 的首跳 WorkBuddy 频繁 429，每个请求都要先撞它一次再回落
  OC，白付一次往返；当 OC 同时 429 时整条链失败，用户得手动重试。
- **根因**：①只有「总超时」没有「空闲超时」，静默等待和正常慢生成无法区分；
  ②429 被当成普通失败直接回落，既没退避也没在跳级别记住「它现在很挤」。
- **解法**：
  1. 桥接（流式与非流式都）加**空闲看门狗** `DefaultIdle = 30s`：连续 30 秒没有任何
     字节就断开连接并返回 `504 upstream_timeout`。首块 role 延迟到真有数据时才写，
     这样超时前没写过任何 SSE，路由还能正常报错/回落。
  2. 429 先**就地退避 700ms 重试同一跳一次**（限流窗口通常很短），仍 429 才把该跳
     **短冷却 45 秒**；桥接上游静默超时（504）冷却 **5 分钟**，死跳仍是 30 分钟。
- **为什么冷却时长要分级**：429 是瞬时拥挤，冷却太久会白白弃用一个能用的跳；
  静默超时说明上游真僵死，冷却短了就每个请求都要再等一次 30 秒。
- **验证**：`go test ./...`（`TestForwardStreamIdleTimeout` 断言静默上游 200ms 内
  返回 504 且零 chunk）；实测 Conatus 从 120s 干等变为 30s 内可判定错误。

## 33. 「地区受限」不是这一跳坏了：403 不回落会让兜底跳永远轮不到 【通用】

- **现象**：`gpt-6-luna` 从中国 IP 直连 opencode 拿 403
  `unsupported_country_region_territory`，链上明明排了「同上游、经机场」的第二跳，
  zgate 却把 403 原样返回给客户端；`beam-free` 拿 `RegionError` 时同理。
- **根因**：两处判定都只顾了「跳坏了」的情况 ——
  ① `chainAccept` 只对 `429/502/503/504` 回落，403 一律 accept；
  ② 桥接路径（`messages` / `responses`）**根本不走** `chainAccept`，
  只判 `status >= 500 || 429 || hopFatal`，所以 `responses` 模型的地区 403 一定漏。
  另外 `hopFatal` 只认额度类关键字，地区受限不算 fatal 也不能算 accept。
- **解法**：
  1. 抽出 `regionBlocked(status, head)`，认两种真实写法
     （`unsupported_country_region_territory`、`RegionError`、`not available in your country`、
     `region, or territory not supported`），`chainAccept` 与两条桥接回落分支都问它。
  2. 冷却键 `hopKey` 里加 proxy：同上游的「直连跳」和「机场孪生跳」必须是两个键，
     否则直连的 403 会把机场跳一起冷却，兜底当场失效。
  3. 出口不要写在代码里 —— `chain[].proxy` 由 alias map 给（见 [MODEL-ALIAS](MODEL-ALIAS.md) §3.0），
     加/减受限型号只改生成器名单。
- **验证**：`go test ./internal/router/`（`TestRegionBlockedFallsThroughToNextHop`、
  `TestRegionBlockedHelper`、`TestHopKeySeparatesEgress`）；线上 `GPT-6-Luna`
  日志出现 `(1/2)` 直连 403 → `(2/2)` 机场 200。

## 34. 传输层瞬时失败没重试，一跳链直接 502；GET 健康检查看不出来 【通用】

- **现象**：2026-10-31 01:14 起浏览器里调 `Beam` 连续 502（它只有一跳机场兜底），
  zgate 日志 `Post "https://opencode.ai/zen/go/v1/chat/completions": EOF`。
  同期 `robots.txt`（GET）一直 200，`/proxies/<组>/delay` 也全绿。
- **根因 1（链路）**：机场节点到 opencode.ai 的路径对**大包**短暂黑洞 ——
  实测同一时刻 POST body ≥5 KB 全挂在 5.0s（curl `000`），≤2 KB 正常。
  GET 没有 body，所以 url-test / 健康检查完全看不出来（同 P32 的「健康检查过
  ≠ 数据面能用」）。
- **根因 2（代码）**：`doForwardWith` 对 `client.Do` 的传输层错误直接交给下一跳；
  一跳链没有下一跳，于是原样 502。
- **解法**：
  1. 传输层错误**先重试同一跳一次**（`transportRetryDelay` 300ms），
     `txRetry` 与 429 的 `attempt` 分开计数，互不吃预算；
  2. 桥接路径同样重试，但只在 `!cw.written`（还没写出任何 SSE）时做 ——
     已经吐了半截 chunk 再重试会重复输出。
  3. 只对 `EOF / TLS handshake timeout / connection reset / i/o timeout /
     broken pipe / connection refused` 这类「请求大概率没被受理」的错误重试；
     普通 5xx 不重试（上游可能已计费）。
- **排查口径**：怀疑链路时用 **POST 带 6 KB body** 探（`curl -x <proxy> --data-binary @b.json`），
  只看 GET/HEAD 会把这种路径判成健康。

## 35. 脚本自己发的探测绕过了路由器：地区 403 被当成「模型死了」删掉 【通用】

- **现象**：`go_model_sync.py --apply` 的「已配置模型体检」连续两轮（2026-11-02、2026-11-03）
  把 `Beam`(beam-free)、`GPT-6-Luna`(gpt-6-luna)、`Muse-Spark1.3` 判成
  「上游不可用：HTTP 403 This model is not available in your country」并从配置移除，
  随后 `model_alias.py` 把它们从三组里一并清掉 —— 客户端里这三个模型直接消失。
  但同一时刻从 7871 调它们完全正常。
- **根因**：P33 修的是**路由器**的回落（alias 机场孪生跳 + `regionBlocked`），
  而体检是脚本**自己**用 `urllib` 直接打 `https://opencode.ai/zen/go/v1`，
  根本不经过 zgate，自然拿不到那第二条出口 → 直连 403 → `stale_reason` 判「跑不通即清」。
  换句话说：**出口策略只修在路由器一侧，任何自建请求的脚本都得各修一遍**。
- **解法**：
  1. 探测遇到地区标记（与 zgate `regionBlocked` 同一套字符串：`unsupported_country_region_territory` /
     `RegionError` / `not available in your country` / `region, or territory not supported`）时，
     用 `AIRPORT_PROXY`（默认 `http://10.0.0.1:7896`）**复测一次**；
     只有机场也不通，才把 403 交给 `stale_reason` 移除。
  2. 复测只加在「已经决定要换出口」的那一次请求上（`http(..., proxy=)`），
     不做全局代理 —— 全量文档/模型清单请求仍走直连，别烧机场流量。
  3. 出口地址只有一个来源：`tools/model_alias.py` 的 `AIRPORT_PROXY`；
     脚本侧同值并允许 `GO_AIRPORT_PROXY` 覆盖、空值关闭。
  4. 报告里标出来：体检段出现 `⇄ N 个直连地区受限、经机场复测通过（保留）`，
     新模型行尾出现 `[经机场]`，便于和「真下架」区分。
- **验证**：
  - `python providers/opencode-go/ops/go_model_sync.py` → 三个模型重新出现在「建议收录」并带 `[经机场]`；
    `--apply` 后 `model_alias.py --check` 无漂移，三组恢复 18 个（主力 2 / 免费 6 / 省钱 10）。
  - 端到端：`curl 127.0.0.1:7871/v1/chat/completions -d '{"model":"Beam",...}'` 返回 200，
    zgate 日志 `(1/2)` 直连 403 → `(2/2)` 机场 200。
  - 反证：直连复测仍是 403，说明不是网络抖动而是出口问题。

- **2026-11-09 现行口径（解法已变，以上为来龙去脉）**：`go_model_sync.py`
  的「已配置模型体检」现在**不再发探测请求**，去留只看上游清单：
  `stale_reason(model, deprecated_dates, live, hint)` 只判官方弃用日 +
  实时 `/models` 与 Go 文档表里都查不到，不再用 403 判「跑不通即清」；
  `prune_is_suspicious(removed_count, configured_count, live_count)` 用
  `PRUNE_GUARD_RATIO=0.34` 给批量移除加刹车。`http(..., proxy=None)` 的
  proxy 参数仍保留，但四个调用点都不带 proxy —— **地区 403 复测**这条路径
  连同 `[经机场]` / `⇄ N 个…` 报告字样已随「零新增推理请求」一起停用。
  理由：脚本自建请求绕过 zgate，本就测不准；路由器侧 P33 的 alias 机场孪生跳
  才是现行出口策略，把脚本自己探活重新打开等于恢复零收益请求。

## 36. 检查脚本用 ✓ / ✗ 打结论：GBK 控制台下自己把自己判成失败 【通用】

- **现象**：Windows 中文控制台（`cp936`）跑 `python -I tools/check-docs.py`，
  最后一行 `print(f"✓ {n} 篇文档全部通过…")` 抛
  `UnicodeEncodeError: 'gbk' codec can't encode character '\u2713'`，
  脚本以**退出码 1** 结束 —— 检查其实全过，门禁却报红。
  CI（ubuntu-24.04）是 UTF-8，看不到这个问题，所以能长期潜伏。
- **根因**：`✓` U+2713 / `✗` U+2717 不在 cp936 码表里；Python 3.12 的
  `sys.stdout` 在管道与控制台下按 locale 编码（`gbk`），`print` 非 ASCII 直接抛。
  `python -I`（isolated 模式）把 `PYTHONIOENCODING` / `PYTHONUTF8` 一起忽略，
  所以「设个环境变量」不是解法 —— 必须改脚本本身。
- **解法**：脚本自身的结论行只用 ASCII 标记（本仓惯例 `[OK]` / `[FAIL]`），
  正文说明照旧写中文（GBK 覆盖得到）。确有字形需求时，在入口显式
  `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`；
  优先 ASCII —— 不改调用方环境就能复现同一结果。
- **验证**：
  - `python -I tools/check-docs.py` → `[OK] 52 篇文档全部通过…`，退出码 0；
  - `python -I tools/check-secrets.py` → `[OK] 已扫描 176 个文件…`，退出码 0；
  - 反证：把 `✓` 临时改回原样，同一命令退出码 1 并抛 `UnicodeEncodeError`。

## 37. 探活写了三年没人调用：结果文件不存在、没有时间戳、顺序还反了 【通用】

- **现象**：`model_alias.py --probe-file` 有完整的消费逻辑（:1731-1766：非 ok 的条目
  从分组里剔除），可 `moonshotai/kimi-k3-free` 在 2026-10-27 被上游 retired 之后，
  还稳稳占着免费组的位置，每次调用 502。`sync-models.ps1` 里 grep `model_probe`
  零命中 —— 结果文件从来没被生成过。
- **三个坑叠在一起，只修一个都不生效**：
  1. **没人跑**：每日同步从第四步直接跳到 `model_alias.py`，没有探活这一步，
     `--probe-file` 自然也没传。
  2. **没有时间戳**：`model_probe.py` 只写 `ok_at`（仅成功时才有），而
     `_fresh_probe` 按 `checked_at` 判新鲜度。实测 66 条记录全被判「超过 72 小时」，
     一律按未知处理 —— **未知不删除**，所以即使传了 `--probe-file` 也摘不掉任何模型。
     修法是每条都写 `checked_at`（ISO，本地时区）。
  3. **顺序反了**：探活要放在第一轮 `--apply` **之后**。白名单本轮新补进配置的型号
     （`cn:hy4std`）在第一轮之前不在配置里，探不到它，第二轮带 `--probe-file` 时会被
     判成 `probe not probed` 直接跳过 —— 等于新模型永远进不来。
- **解法**：`sync-models.ps1` 的次序改成「arena 刷新 → scores → apply → 探活 →
  带 `--probe-file` 再 apply → `--check`」，并在探活后统计可用率：
  `ok * 2 < total` 时不传 `--probe-file`。理由：大面积失败多半是网关或某个渠道整体
  挂了，此时按探活摘模型会把好型号一起删光。
- **验证**：19 个模型探活 18 ok / 1 error（Kimi-K3 → 502）；带 `--probe-file` 写入后
  免费组从 6 变 5，Kimi-K3 消失，经 7871 调用从 502 变成 400（未知模型）。

## 38. `--check` 和 `--apply` 参数不一样，每天报一次假漂移 【通用】

- **现象**：`sync-models.ps1` 里 `--apply` 带 `--arena`，`--check` 不带。arena 把
  `MiMo-2.6-Flash`、`Space-Bunny` 从省钱提进主力，于是 `--check` 每天都报
  「分组：MiMo-2.6-Flash 主力 → 省钱」两处漂移 → 触发二轮重写 → 复查仍报 → 日志常驻
  「复查仍有漂移，需要人工看」，实际配置完全正确。
- **根因**：`--check` 是「用当前参数重算一遍，和落盘的 alias map 比对」。参数不同就是
  拿两套规则比结果，报的漂移是参数差，不是数据差。
- **解法**：把 `--check` 的参数从 `--apply` 派生（同一个 `$checkArgs` 数组拼
  `--arena` / `--scores` / `--probe-file`），不要手写字面量。
- **验证**：`python tools/model_alias.py --check --arena --scores --probe-file …` →
  「无漂移」；去掉 `--arena` 就复现那两行漂移。

## 39. DSH 的 edit 工具会剥掉 UTF-8 BOM：改了带 BOM 的 .ps1 就变乱码 【通用】

- **现象**：用 `edit_file` / `edit` 改 `sync-models.ps1`（HEAD 版本是
  `EF BB BF` 开头的 UTF-8 BOM），改完 `head -c 3 | xxd` 变成 `23 52 65`（`#Re`），
  BOM 没了。PowerShell 5.1 按 GBK 读无 BOM 的 UTF-8，所有中文注释糊成乱码，
  `Parser::ParseFile` 报一串 `Unexpected token '涓诲姏'` / `The string is missing
  the terminator`。计划任务里跑会直接把脚本跑挂。
- **解法**：每次用 edit 类工具改带 BOM 的文件，改完补一行：
  `python -c "import pathlib;p=pathlib.Path('x.ps1');b=p.read_bytes();p.write_bytes(b if b[:3]==b'\xef\xbb\xbf' else b'\xef\xbb\xbf'+b)"`，
  再用 `[System.Management.Automation.Language.Parser]::ParseFile` 复核语法。
  判据是 `head -c 3 | xxd` 必须显示 `efbbbf`。`.py` / `.sh` 不要 BOM，别顺手加。


## 40. 去掉 Default 伪档位后，省略 reasoning_effort 会让 Iceman 丢思考、正文聚成整块 【实例 A】

- **现象**：`dsh-claude-style` 0.20.1 的 `lib/client.js` 在模型没显式指定默认档位时，
  往档位列表最前面塞一个 `id=undefined / name="Default"` 占位；用户不选档就选中它，
  `c()` 组装请求时**完全不带 `reasoning_effort`**。Iceman（`iceman-contributor-free`）
  在这个缺省下要么吐不出思考 chunk、要么把正文攒成一大段拖出来，21:0x 实测 11 块 /
  0 字思考，21:44 同链路 79 块 / 298 字，缺省行为随上游漂移。
- **根因**：请求缺 `reasoning_effort` 时把「用哪个档」交给上游决定；上游对推理型的
  缺省不稳定，思考字段与流式分块都跟着变。关思考也不能靠 `off / wire=disabled`
  —— 实测该组合直接回 `HTTP 422 Unprocessable Entity`。
- **怎么避**：档位一律取**官方文档里给到的真实档位**，
  `~/.dsh/tools/patch-claude-style-effort.mjs` 把 `ki()/M()/h()/c()` 改成
  effort 为空时取 `model.reasoning.efforts` 末位（与宿主 `THINKING_LEVELS` 固定序一致），
  删掉 `Default` 占位并让 `directory.select()` 显式写入官方 effort。
  探针同档位大预算补测与自动准入规则以 [MODEL-STREAM.md](MODEL-STREAM.md) §3 为正本，
  本节只记坑，不重复定义机制。
- **验证**：补测后 Iceman 414 块 / 1733 字思考 / 103 字正文 / 11 最大块间隔，PASS；
  `--check` 复查 `ALREADY_PATCHED (no write)`。改带 BOM 的 `sync-models.ps1` 挂探针钩子时
  按 §39 补回 `EF BB BF`，否则计划任务里 PS5.1 按 GBK 读会乱码跑挂。

## 41. 上游同一别名随机只给加密思考，Iceman 界面看不到思考 【实例 A】

- **现象**：显式 `reasoning_effort: high` 也会随机只回正文 + `reasoning_details[type=reasoning.encrypted]`，`reasoning_content` 零增量；30 次交错采样里 B 与请求参数、耗时都无关（2.02s–86.36s 都有），GUI 思考块空白、正文一节一节出。
- **根因**：`iceman-contributor-free` 上游双后端分流：A 吐明文 `reasoning_content`（pi-ai 转 `thinking_delta`）；B 只吐 opaque replay blob。宿主 `@earendil-works/pi-ai/dist/api/openai-completions.js:172-173,416-428` 把 `reasoning_details` 当 replay 元数据，只写 `block.thinkingSignature`、不写 `block.thinking`、不推 delta；UI `blockIsVisible` 跳过空 reasoning。叠加 `transcriptView: standard / collapseTiming: completion / foldedReplies: final` 整轮折叠与 `reasoningDisplay: stepped` 两行步进。C2 负证据：查不到解密或强制明文的请求参数，8 类参数 ×5 轮全部照样命中 B。
- **怎么避**：三层各管一段 —— ① 展示层**只动 `ui-skin-claude-style` 的 `reasoningDisplay`（刷新 GUI 生效），`ui-chat` 三键是用户偏好（现值 `compact / completion / final`），排查中一律不许改成 `verbose / next-input / all`**：改了用户会当成「配置自己回退了」，2026-11-10 已反复踩（备份链 `bak-gemini-devrole-20261110131037` / `bak-dshsync-20261110-145209` 两次 verbose，都是排障会话写进去的）；要看过程细节用界面单轮临时展开，不动用户偏好。② 网关层 `zgate.json` 的 `reasoningGuard` + `router.go` 首包判定，命中 B 直接关流透明重抽同一跳，**改 Go 必须按 [TROUBLESHOOTING.md](TROUBLESHOOTING.md) §16.2 换版二进制**；③ 探针识别口径以 [MODEL-STREAM.md](MODEL-STREAM.md) §3 / §4 为正本。回退：守卫零值=禁用，删 `reasoningGuard` 段即恢复原透传。
- **二次修复（2026-11-10 下午，前两版修完仍看不到思考的真因）**：三条，缺一条都白修。
  1. **重抽必须换连接 + 换会话**：首版重抽沿用原 headers「保 `X-Opencode-Session`」+ keep-alive 连接，而上游是按会话/连接粘后端的 —— 3 次重抽全落回同一路加密后端，达上限放行的还是加密流（`zgate.log` 里 3 条「透明重抽同一跳 1/3..3/3」紧接着 WARN「达上限放行最后一次」就是这个形态）。现改为每次重抽 `req.Close = true` + `X-Opencode-Session` 追加 `#r<N>-<随机>`（原值留在前缀里便于排查），默认重抽上限提到 5。
  2. **SSE 改长度时必须摘掉上游的 `Content-Length`**：上游事件流自带 CL 时，守卫丢弃首段、插提示、掺心跳都会改长度，写端直接报 `http: wrote more than the declared Content-Length` 并断流 —— 客户端拿到 200 却 0 字节，表现是「连上了但什么都没有」。修法：`copyHeaders` 之后对事件流一律 `w.Header().Del("Content-Length")`，交给 `net/http` 按 chunked 重新分帧。
  3. **思考阶段静默要喂心跳**：上游思考停顿实测 51.9 秒，中间层与宿主会判空闲。`streamIdleHeartbeatSec`（缺省 15，负数关）控制空闲多久补一行 `: zgate keepalive` 注释；非事件流一律不掺（否则会毁掉 JSON 报文）。
- **同类模型免配置适配**：`reasoningGuard.mode` 三档 —— `models` 只守白名单；`channels` 先看渠道能力位 `upstreams.<渠道>.guardReasoning`（`models` 非空时再叠一层**交集**，2026-11-10 深夜起现网就是这个档，只有 `OC` 带位、白名单仍是 Iceman 两条）；缺省或显式 `"auto"` **不看任何表** —— 凡是客户端声明要思考（`reasoning_effort` / `thinking=enabled`）的流式请求都走探针，新增匿名代号模型不用再改配置；配合按模型学习表（连续 `giveUpAfter` 轮重抽到上限仍是纯加密且从未见过明文 → `giveUpForSeconds` 内不再白等，到期自动复探）。达上限时 `injectNotice` 会在流首插一条 `reasoning_content` 提示，GUI 至少显示「上游本次只下发加密思考」而不是空块。
- **验证**：`go test ./internal/router` 12 项 PASS（首包判定四形态、白名单 / off / 禁用、auto 模式覆盖陌生模型、重抽必须换会话且 `Connection: close`、上限放行注入提示、学习表跳过、心跳写入、非流式不掺心跳、带 `Content-Length` 的上游形态）；`internal/config` 2 项 PASS（JSON 接线 + 缺省值）；`gofmt` / `go build` / `go vet` 全 exit 0（`internal/supervisor` 两例失败是 Windows 临时目录清理占用，与守卫无关）。隔离实例实测（`%TEMP%\zgate-iso2-*`，假上游带 `Content-Length`）：首跳加密 → 客户端拿到明文 `reasoning_content`、加密首跳一字未泄漏、`attempts.log` 显示第二次调用会话变成 `#r1-*` 且 `Connection: close`；始终加密 → 200 + 597 字节 = 提示 + 上游正文（修前这里 0 字节断连）。探针 `ENC` 列与 `check-project.py --stream-contract` 七处接线 exit 0。
- **三次修复（2026-11-10 傍晚）：守卫压根没上场**。换版后用户复测仍「看不到思考 + 一节一节」，而 zgate.log 里那两条请求**一个守卫行都没有** —— 不是重抽失败，是触发条件不成立：guardApplies 首行 !reasoningExpectsThinking(body)，而 DSH 的模型选择器没有逐模型默认档位（catalog 的 reasoning.defaultEffort 为空 → 选的是 Default 伪档位），真实请求体只有 provider/model/maxTokens，**不带 reasoning_effort**。诊断入口：会话 session.v4.jsonl.zstd 的 request/header 记录里看 config 字段，没有 reasoningEffort 就实锤。修法：reasoningGuard.forceEffort + forceEffortModels，由 injectThinkingEffort 在转发前补档（日志「客户端未声明思考档位，按配置补 reasoning_effort=high」），补档后原有「换连接+换会话重抽」才会真正生效。**不要**再走给 dsh-claude-style/lib/client.js 打补丁的老路：该文件 2026-11-10 12:35 被重建后 11-09 的 effort 补丁整段消失（patch-claude-style-effort.mjs --check 报 NEEDS_REVIEW，六条锚点全归零），profile 每次重建都会重演。补档只影响「客户端没说话」的情况：显式 off / thinking 原样透传。
- **四次修复（2026-11-10 傍晚）：探针把用户的等待放大了**。三次修完后守卫确实上场，但每个请求要空等 85 秒（用户手动点停止）。代码级原因有三层：① `probeReasoningStream` 只在**第一个正文 delta** 时返回 `streamEncrypted`，而加密那一路思考阶段整段静默（无明文 `reasoning_content`、无正文），于是"判定"的延迟就等于那一次尝试的整段思考时长（`zgate.log` 实测两次判定隔 61 秒）；② 重抽预算花完的最后一发仍用无上限探针，再叠一段空等；③ 跳过期命中就续期，窗口过去也探不回来。现网口径：`probeSeconds`（缺省 12）到点换连接重抽；重抽预算花完或处于跳过期时**不探测、直接放行上游原始流**并插一条按成因写的提示（超时说"探测超时"、`reasoning.encrypted` 才说"只回加密"）；`guardInSkip` 到期清计数再复探，进跳过表改成"自上一条明文以来连续 N 轮失败"。**诊断入口**：日志里出现 `内没有可判定的思考信号（上游静默）` = 探针超时在换连接，`连续 N 次探测超时` = 已放弃探测直接放行；两者都在 `probeSeconds` 附近出现即说明修复在位。参数联动：`probeSeconds` 要大于正常流的首字节耗时（明文实测最高 13.5 秒 → 配置 15），小了会把慢流误判成静默；`maxRetries` 大于 1 在窗口期纯属白等（12:01 连续 3/3、13:20 连续 2/2 都落回同一后端）。

## 42. 配置加了渠道、进程没重载：整条降级链静默退回串行 【通用】

> **口径更新（2026-11-10 22:27）**：本条记录的 8 跳链是当晚形态；现在 `Gemini-AIS` 是 7 跳全 GM，
> 哈基米福利 3.8 已拆成独立模型 `Gemini-3.8-Flash`（单跳 `HJ`、排在 AIS 前面）。
> `(1/8)` 这类日志按历史读，`channelPolicy` 少一个渠道就会退回串行的结论仍然成立。
> **链长再变（2026-11-11 11:03）**：AIS 只留 3 跳，日志变 `(x/3)`；裁掉的四跳记 `dropped_hops` 并留在 `legacy_ids`，见 §43。

- **现象**：某个模型一次请求一分钟零字节，客户端只能手动停止；网关日志里只有一行派发 `model=Gemini-AIS -> GM:ais-gemini-3.8-flash (1/8)`，之后没有任何 `[race]`、没有冷却、没有 fallback、没有 502；上游反代面板一条记录都没有。同一时刻其他模型正常。
- **根因**：三层叠一起，缺一层都不会这样静默。
  1. `racePolicyFor`（`internal/router/race.go:305`）要求**链上每个 hop 的渠道都在 `cfg.ChannelPolicy` 里**（`race.go:324`），否则整条链放弃竞速。链由 alias map 热加载（8 跳，含新加的 `HJ`），而 `channelPolicy` 是启动时读进内存的 —— 进程比配置旧，内存里只有 `GM` → 判定失败。
  2. 退回串行后没有任何首块看门狗：`router.go:734` 的 `if at != nil && at.policy.FirstBlockMs > 0` 只在竞速模式成立，串行链就是「发出去、等下去」。
  3. `http.Client`（`main.go:152`）只配了 `TLSHandshakeTimeout` 与 `DialContext` 超时，**没有整体超时 / 响应头超时**，上游建好连接却不发头就无限期挂着。
  三者一合：客户端零字节、网关零日志、反代零记录。旧二进制还认不出新渠道，连「缺 key」这种错误都报不出来。
- **口径更新（2026-11-10 深夜）**：下文第 ① 层的「每个 hop 的渠道都要在 `channelPolicy` 里」已随**逐跳取值**取消（`racePolicyFor` → `racePlanFor`，见 [ROUTING-POLICY.md](ROUTING-POLICY.md) §1）：缺配的渠道只是自己拿不到对冲节奏，不再连坐整条链退回串行；串行仍会发生，但只有一条 `noteSerialChain` 的 Info 说明原因。**「配置加了渠道、进程没重载」这个坑本身仍然成立** —— 差异在症状：以前是整链静默串行，现在是链上那一跳没有对冲、也没有它自己的看门狗窗口。
- **怎么避**：① 加渠道 / 改链之后**必须换二进制并重启** —— `/admin/reload` 只热加载 `zgate.json` 的策略，改不了编译期登记的渠道与进程内已读的配置快照（流程见 [TROUBLESHOOTING.md](TROUBLESHOOTING.md) §16.2）；② 代码侧已补两道网（2026-11-10 夜）：流式请求的**响应头看门狗**（`doForward`，默认 12s 拿不到响应头就判这一跳沉默并换跳，`errUpstreamSilent`；`zgate.json` 的 `upstreamHeaderTimeoutSec` 可调，负数关掉 —— **但 2026-11-10 21:30 起 GM / HJ 两个渠道都不设这个窗口，理由见本条第五轮**）与**串行退化告警**（`routeChain` → `noteSerialFallback`，打 `[race] 链上有渠道不在 channelPolicy 里…整条链退回串行、取消首块对冲`，按渠道组合 10 分钟去重）；③ 排查时先 `grep "不在 channelPolicy"`，命中就不用再猜。
- **验证**：`gofmt -l internal/router/` 空、`go build ./...` / `go vet ./...` exit 0、`go test ./...` 全 ok。新增两例：`TestStreamingHeaderWatchdogGivesUp`（handler 不给头、`headerWait=150ms`，断言 5s 内返回 `errUpstreamSilent` 收手）与 `TestStreamingHeaderWatchdogPassesThrough`（正常 SSE 必须原样透出、Close 正常取消）。候选二进制 `python gateways/zgate/build.py --candidate` 内容检索 `hajimi` / `HJM_API_KEY` / `upstream silent` 全部命中。

- **同日第二轮（2026-11-10 19:45）：换版生效了，可一次请求仍要 4 分半 —— 坑在「容忍窗口按最慢的那一档取」**。日志已经恢复 `[race] 发出 1/8`…`8/8`（对冲回来了），但每一跳都要等满 45 秒才判沉默：实测同一跳 `ais-gemini-3.8-flash` **每次都要 60.241 秒才回 503**（`This model is currently experiencing high demand`），而哈基米 `[福利]gemini-3.8-flash` 直连 2.5-3.1 秒就出首块。`maxParallel=2` 轮转 ⇒ 4 轮 × 45 秒 + 首块 4 秒 ≈ 3-4.5 分钟（用户实测 4 分 31 秒）；这期间 DSH 等不到首字节会自动重试，反代后台于是出现两条「请求中」，看起来像「我发了一句它打了两枪」。
  - **改**：`upstreamHeaderTimeout` 45s → **12s**，并升级成配置项 `upstreamHeaderTimeoutSec`（0/缺省 12，负数 = 关掉看门狗），`Server.headerTimeout()` 每次现读配置，`/admin/reload` 就能调，不必重编译。12 秒相对观测到的合法首头（2.5-3.1 秒）仍有 4 倍余量。
  - **口径**：这个值要按「**正常首头的最慢分位 × 3-4**」定，不能按「上游多久才认输」定 —— 前者保住的是体验，后者只是把超时串成糖葫芦。
  - **日志**：沉默告警现在带 `model=`（`[router] https://api.gemai.cc/v1（model=[福利]gemini-3.8-flash）上游 12s 内没给响应头，判这一跳沉默并换跳`）。同一个 base 下不同模型能差一个量级，只打 base 分不清是谁被上游晾着。
  - **验证**：`TestHeaderTimeoutFollowsConfig`（配置 3 秒即生效 / 缺省回落常量 / 负数返回 0 / 显式字段最优先）+ `config_test.go` 里 `upstreamHeaderTimeoutSec` 的缺省与负数用例。
- **同日第三轮（2026-11-10 20:05）：一个全局窗口套两种脾气，兜底那家被自己的门槛切掉**。哈基米 `[福利]gemini-3.8-flash` 白天 2.5-3.1 秒出首块，晚上漂到 **7.5-10.2 秒**（同一 key，60KB / 200KB 系统提示各测一次）；12 秒窗口只剩 1.2-1.6 倍余量，20:03 的日志里它跟 GM 一起被判 `12s 内没给响应头`，8 跳全灭、50 秒干净失败，反代面板依旧零记录（GM 从没回包，哈基米不在那张表里）。
  - **改**：`channelPolicy` 新增 `headerTimeoutSec`（0 = 继承全局，负数 = 该渠道不设看门狗），`Server.headerTimeout(channel)` 的优先级变成「显式测试字段 > 渠道 > 全局 > 常量」；`zgate.json` 里 **GM 12 秒 / HJ 25 秒**。两路并发时不冲突：GM 到 12 秒先死、链继续往下，HJ 还在等它的 10 秒，谁先出首块谁赢。
  - **口径**：窗口要按「该渠道正常首头的最慢分位」分别定。跨渠道用一个值，等于拿最快那家的标准去卡最慢那家，兜底就变成「名义上在场、实际上每次都被切」。
  - **验证**：`TestHeaderTimeoutPerChannel`（HJ 25s / GM 12s / 渠道负数关掉 / 渠道为 0 回落全局 / 渠道不在表里回落全局 / 显式字段仍最优先）、`go test ./...` 全绿。
- **同日第四轮（2026-11-10 20:20）：换了跳却没埋跳，同一个死跳每个请求都要重新撞一遍**。看门狗已经生效（日志里每跳 12 秒判沉默并换跳），但 `errUpstreamSilent` 分支只调 `retry()` 回落下一跳，**没有写 `silence` 表** —— 于是第二个请求又从第一跳起手，把已经证明死掉的跳重撞一次。用户连发两句、两分钟里大半时间花在这上面。**改**：`doForwardWith` 命中沉默后按渠道 `silenceCooldownSeconds` 打 `markSilence`（GM/HJ = 20 秒），`cooling()` 立刻把这一跳挡在下一轮之外；全链都在短冷却时 `raceChain` 走 `clearSilence` 重试一次，不会把自己饿成 502。**口径**：静默冷却要短（20 秒），它是「这次先说别人」不是「这跳死了」；真冷却（429 / 5xx / 额度）仍走 45 秒 - 24 小时。**验证**：`TestSilentHopGetsShortCooldown`（沉默后 `cooling(hop)` 必须为 true 且 `retry` 被调用一次）、`go test ./...` 全绿。
- **同日第五轮（2026-11-10 21:30）：本地判死本身就是故障源 —— 上游还在吐 token，本地已经断开重试**。当晚统计：GM 被判死 125 次（沉默 79 + 首块 46），上游真说过 `503 high demand` 的仅 7 次（5.3%）；HJ 判死 32 次，一大半与 502 同秒。链路遗迹 `12s 无响应头 → fallback (none) → 同秒 502 → 13s 后客户端重试 → 再砍`。DSH 的 `retryPolicy` 把 `SERVER` 列为可重试（`maxRetries: 1`），所以**网关每判死一次 = 一次 502 + 一次客户端重试 + 一次上游重跑**，用户看到的就是「后台在跑 token、本地断开又跑一遍」。
  - **改（配置，热加载）**：`channelPolicy.HJ` 收敛为 `{"headerTimeoutSec": -1}`；`channelPolicy.GM` 的 `headerTimeoutSec` → `-1`、`firstBlockMs` → `0`、`silenceCooldownSeconds` → `0`、`hedgeAfterMs` → `18000`、`softCooldownSeconds` → `60`；`upstreamHeaderTimeoutSec` → `45`。
  - **口径**：本地只做两件事 —— 「并排多问一家」（对冲，只多开一路、不取消前一路）与「按上游回话冷却」（429 / 5xx / 403）。**上游没说我死了，就不替他下死亡通知**；慢是常态，阈值给多少都是赌，赌错一次要付一次重试 + 一次重跑。
  - **判据**：`grep -c '没给响应头' zgate.log` 与 `grep -c '503' zgate.log` 放一起看 —— 前者远大于后者就说明判死是本地造的。详见 [TROUBLESHOOTING.md](TROUBLESHOOTING.md) §18.4。

## 43. 上游「忙」被当成渠道故障：一个过载的 3.8 把同渠道能用的 3.6 一起带走 【实例 A】

- **现象**：用户侧两条互相矛盾的反馈 —— ①「跑着跑着就截断了，然后说模型使用人数过多需要重跑」；②「错误码 HTTP_503，此模型当前需求量较大」，`503 都是这样`。直连取证（Bearer `GEMINI_API_KEY` 打 catiecli）：短问四跳全 200（3.8 = 7.2s / 3.7 = 5.2s / 3.6 = 2.6s / 3.5-flash-lite = 10.8s）；同样的 1200 字长提示四跳全 503，耗时 3.4s / 10.3s / 22.4s / 4.3s。**这不是链路坏了，是模型忙**，且 503 来得慢（最长 22 秒），会白占看门狗窗口。
- **根因**（两层，都在网关侧）：
  1. `chainAccept` 把 503 当「这一跳死了」，而冷却落在**渠道**上：`markChannelOffFor(hop.Channel, poolCooldown=90s)` → 之后 90 秒里同渠道的 3.6 / 3.5 全部在入口被拒（`渠道 GM 处于禁用窗口，直接回 503`，2026-11-10 23:40 实测连刷）。一跳过载 = 整条链陪葬。
  2. 流式转发读到 `rr.err` 直接 `return`：既不补 `[DONE]`、也不写日志、也不计数。客户端拿到的是「200 + 几段正文 + 无 `finish_reason` 的断尾」，只能自己判成失败重跑 —— 重跑的 token 上游照算一遍。
- **改（2026-11-11）**：`internal/router/upstream_semantics.go` 把上游语义拆成三类，各走各的路（详见 [ROUTING-POLICY.md](ROUTING-POLICY.md) §4.1）：忙 → 只跳这一跳 + `busyCooldownSeconds`（GM 现行 10s，现值读 `zgate.json`），不整渠道禁用；400 带 `thinking_level` → 剥参数同跳重发一次；SSE 断尾 → 补 `finish_reason:"error"` + `upstream_truncated` + `[DONE]`。三者在 `/health.upstream` 各有一个计数。
- **口径**：**「忙」是这一跳此刻的状态，不是这个渠道的品质**。冷却是给「这一跳先别用」，禁渠道是给「key 没了 / 被封了」。把前者写成后者，等于让一个模型的繁忙拖垮整条降级链。
- **判据**：`curl -s 127.0.0.1:7871/health` 看 `upstream.busy` / `upstream.busy_skipped` 是否在长提示下增长；`busy_skipped > 0` 且 `truncated_streams` 停住 = 忙跳已让位、断流已收口。日志对应行：`上游 503 表示需求高峰，跳过该跳 20s（不在渠道级禁用）`。
- **验证**：`go build` / `go vet` / `go test ./...` exit 0；新增 8 例（`busyExhausted` 三形态、`invalidThinkingParam`、`stripThinkingParams` 两层嵌套、400 剥参后同跳重发拿到 200、断流补帧、正常流不被改、忙跳跳过而不禁渠道）。

---

## 44. 竞速排序的记忆有保鲜期，`/health.race` 却还在报旧账 【实例 A】

- **现象**：三种误判同一个根 —— ① 看 `/health` 里 `race.hops` 的 `3.8 = {"verdict":"Service Unavailable","at":"21:56"}`，断定「它还被压在队尾」，可下一轮请求其实已经按声明顺序先试它了；② 以为 `POST /admin/reload` 能重置排序，reload 后 `at` 纹丝不动，转头怀疑「配置没生效」；③ 在单发串行的链上盯 `race.hops` 一行都不更新，怀疑观测坏了。
- **根因**：观测的**保鲜期只作用于发车顺序，不作用于展示**。`rankedChain()` 用 `snap.stale(now)` 把过期条目当「没测过」重新给机会（失败保鲜短、成功保鲜长，常量 `raceFailTTL` / `raceOKTTL`），而 `raceSnapshot()` 原样拷贝全表、`/health.race.hops` 因此永远是「最近一次观测」的原始账本；`/admin/reload` 只做 config / keys / `ApplyConfig` / `aliases.Reload`，不清 `raceStat`；更要紧的是 `rankedChain` 只在 `raceChain`（对冲路径）里调用，串行链走 `attemptChain`，压根不产生这类观测。
- **处置**：判「为什么又是兜底跳出字」用 `/health.hops` 的逐跳计数（`try` / `ok` / `busy` / `e5xx` / `silent` / `no_first_block`，串行链也有），不要读 `race.hops` 的 `at` 当下结论；要清零观测只能重启进程；怀疑排序固化时先看 `try` 有没有增量 —— 有增量就说明它已经被试过，问题不在排序。
- **证据**：`internal/router/router.go` 的 `hopStatSnap.Seen` 与 `stale()`、`raceFailTTL` / `raceOKTTL` 常量、`raceSnapshot()` 无过滤、`reload()` 不清 `raceStat`；`internal/router/race.go` 的 `rankedChain` 分支 `case !ok || snap.stale(now)`；`internal/router/race_test.go` 的 `TestRankedChainRetriesStaleObservations`（新鲜 / 过期 / 成功过期三态）；`internal/router/hop_stats.go` 注释「/health.race 只记竞速跳（at != nil）的首块耗时，串行链一行都看不到」。

## 45. 用 md5 核对 zgate 版本，永远对不上 【通用】

- **现象**：重编后 md5 与线上不一致，判成「部署没生效」，于是再编、再换、还是不一致；另一种反向误判 —— md5 一致就以为「源码也是最新的」。
- **根因**：构建时工作区不干净会把 `vcs.modified=true` 编进 buildid，同一份源码的字节就不可复现；不同 ldflags 组合（`-H windowsgui`、`-s -w`、带与不带 `-trimpath`）也会各出一份哈希。md5 能证明的只有「备份 → 替换 → 校验这一段搬的是同一份字节」，与「是不是最新代码」无关。
- **处置**：版本只认 `go version -m <exe>` 的 `vcs.revision`；再跑 `git log <vcs.revision>..HEAD -- gateways/zgate` 判欠账，为空才算追平；md5 保留在部署三步里做搬运校验。判据与命令见 [ZGATE-LIFECYCLE.md](ZGATE-LIFECYCLE.md) §9.1。
- **证据**：同一次排查里四种 ldflags 组合全部对不上，当时的 buildinfo 带 `vcs.modified=true`；`git log <该提交>..HEAD -- gateways/zgate` 为空，证明「源码没欠账、只是字节不可复现」。

## 46. 反代面板时间比 zgate 日志晚一百秒出头，对齐前别下结论 【实例 A】

- **现象**：把面板的 `21:56` 与日志的 `21:30` 拼成一条时间线，得出「3.8 失败后十五分钟一次没被碰过」「面板零记录 = 网关没发请求」；同一条请求，两边各自看都很正常，合起来就是错案。
- **根因**：两个时间基准不同源。面板记的是它自己落账的时刻，实测恒定滞后一百秒出头（104–106 s，非固定偏移的部分来自面板落账延迟），跨源比对不做校正就会把因果方向拼反。
- **处置**：唯一时间轴用 `zgate.log` 的 `[race] 发出 i/n`、首块、冷却三类行；面板只用来数「上游到底被调用了几次」；确实要跨源对齐时，先取**同一条请求**在两端的时间戳算出偏移，再逐条平移后比对。`/health.race.hops` 里的 `at` 是网关本地时间（`now.Format("15:04:05")`），与面板同样不同源。
- **证据**：源文档样本 —— 日志 `21:30:21` 发出 1/7、`21:30:36` 503 冷却 1m0s、`21:30:54` 发出 3/7，面板同段恒定晚 104–106 s；`/health` 抓取时刻 `21:59` 而 `race.hops` 内 `at` 已到 `21:58:50`。

## 47. 只改 `zgate.json` 加渠道：请求在 key 覆盖名单外被静默跳过 【通用】

- **现象**：新渠道的别名配好了、`/v1/models` 也能看到，请求却稳定 502 `all upstreams failed: <hop>`，日志里没有任何上游响应；另一种形态是上游回 401「未提供API Key」，像是凭据没配。
- **根因**：渠道集合在 Go 里枚举（`internal/keys` 的 `Set.For(channel)` 按渠道硬编码），`zgate.json` 里的 `keyEnv` 已是废弃字段、写了也不生效；只加别名不改代码时，请求会在 router 的渠道判定处被静默跳过，表现成「上游从未被调用」的 502；另一处是 key 覆盖名单没补新渠道，空 Bearer 被原样透传，于是拿到 401。
- **处置**：按 [MODEL-PROVIDERS.md](MODEL-PROVIDERS.md) §0 的六处改动（`internal/keys`、`internal/config` + `main.go`、`internal/router` 的 key 覆盖名单、`tools/model_alias.py` 的渠道常量、`providers/<name>/.env.local`）一次改齐，然后**必须换二进制** —— `/admin/reload` 只能热加载 base 与 key，改不了编译期登记的渠道；换完先看 `/health` 是否出现该渠道的 `{state:"up",key:true}`。
- **证据**：源文档实测 —— 不改 Go 时请求在 `router.go` 的渠道判定处被静默跳过，最终单跳 502 且日志无上游响应；补上 key 覆盖名单后 401 消失；GM 接入后 `/health` 出现 `gemini:{state:"up",key:true,child:""}`。

## 48. 给链加长度上限时只截 `chain`：老 id 静默 404 【通用】

- **现象**：给 `tools/model_alias.py` 加 `CHAIN_CAP = {"Gemini-AIS": 3}` 后 `--apply`，别名表 legacy 从 73 条掉到 69 条，模型总数 93 掉到 89；老会话点名 `ais-gemini-3.5-flash` 这类 id 直接 404，选择器里也少了四条。
- **根因**：`family_entries()` 只用 `chain` 建链，而 `_consistent_legacy_ids()` 反过来拿「全量 hops 的 upstream ∪ 链上跳」校验 legacy 映射 —— 被裁掉的四跳既不在链上、又没有别的登记点，四条 `gem:ais-*` 映射就被当脏数据过滤了。
- **正解**：截链时把裁掉的跳记进 `entry["dropped_hops"]`，并在 `_consistent_legacy_ids()`、脏映射清理循环、`alias_models` 写盘三处把 `dropped_hops` 计入 upstream 集合。改完 legacy 回到 73、旧 id 仍解析到 `Gemini-AIS`，只是链不再真去打它们。
- **判据**：`--apply` 后立刻核 `models==20`、`legacy==73`、`len(AIS.chain)==3`、`len(AIS.dropped_hops)==4`；单测 `test_ais_chain_is_three_gm_hops_in_version_order` 同时锁链长、dropped 与 legacy 覆盖。
- **同类**：任何「先按名字聚合成一条链、再按上限裁剪」的生成器（工具清单、provider 目录、路由表）都有这个陷阱 —— 裁的是执行路径，不是身份。

