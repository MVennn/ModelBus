# 聚合性评估分片（agent-aggregation）— 终稿

> 真实项目根 `F:\Project\ModelBus`（git 分支 main）；junction 视图 `F:\Project\_merged\DeepseekHarness` 不是项目身份。
> 只读评估：未修改任何源码/配置/文档/测试，未执行 `--apply`，未写 `provider_config.json` / `cordis.patch.yml`，未重启/停止任何网关进程，未打印任何凭据真值（只记变量名与结构），未 git add/commit/push。只写本分片 `evidence/agent-aggregation.md`，未碰 PROGRESS.md / docs/ / tools/ / gateways/ / 共享文件。
> **总体判定：部分达到。** 单入口、单进程托管、alias 聚合链三项达到；**主因差距 = 命名空间分叉**：统一命名空间只对 ZCode 面板的 22 个统一名 + 94 个 legacy 键生效，`/v1/models` 对外列出的裸 id 有 16~19 个在标准 OpenAI 协议下直穿 OC，不过 alias 链 / 跨渠道回落 / 冷却 / 协议桥。次要差距 = `/health` 缺 CP 段与每通道 state/lastError/pid、鉴权非纯环境变量、统一入口不等于统一协议。

## 0. 取数口径（命令真实输出）

- `tools.working_directory({})` → `{"cwd":"F:\Project\ModelBus"}`。
- `tools.codegraph_status({})` 真实输出：`CodeGraph Status` / `[i] Project: F:\Project\_merged\DeepseekHarness` / `[!] Not initialized` / `[i] Run "codegraph init" to initialize`，exitCode 0。索引在 junction 视图下报未初始化；按 `~/.dsh/AGENTS.md` §3 与根 `AGENTS.md` §3 不自行 init，退回 grep / read / glob。
- 行号证据来自 `tools.read({file_path, offset, limit})` 与 `tools.grep({pattern, path})` 逐行输出；运行态证据来自 node `fs.readFileSync + JSON.parse`、`node fetch GET` 与 lead 回喂的 PowerShell `Get-Process WorkingSet64` / `zgate.log` 增量行。下文每条结论带「真实路径:行号 + 命令真实输出」。
- 委派判定（§7/§14）：≥3目标=是、≥3处同类=是、≥10次工具=是、多视角=否；运行时上下文 `Delegation depth for subagent: current 1, maximum 1, remaining levels 0`，本会话已是子代理，串行完成。

## 1. 规划侧承诺（逐条验收项，grep/read 真实输出）

| 编号 | 承诺 | 出处:行号 + 真实输出 |
|---|---|---|
| A1 | 收敛成「一个 Go 入口进程 + 6 个 upstream / 3 个按需 child」 | `docs/ARCHITECTURE.md:3-4` → `把「PowerShell 守护 + Node 路由 + 本地网关进程」收敛成` / `一个 Go 入口进程 + 6 个 upstream / 3 个按需拉起的 child（WB / Qoder / CLIProxyAPI）` |
| A2 | 单一入口 `127.0.0.1:7871`，chat 组全部指向 `/v1`，多上游不是多个对外入口 | `docs/ARCHITECTURE.md:8` → `zgate（Go）监听 127.0.0.1:7871`；`:33` → `四个 chat 组全部指向 http://127.0.0.1:7871/v1。三路是三段内部实现，不是三个对外入口。`；`:34-35` → `端口方案（7871 对外…）保持不变，provider_config.json 一个字节都不用改`；`:110` → `仍然只有 7871 对 ZCode 暴露`；`README.md:41` → `三个 chat 组统一指向 127.0.0.1:7871（zgate）` |
| A3 | 单进程托管 children（Job Object / 按需拉起 / 空闲 300s / 崩溃退避 / 单飞） | `docs/ARCHITECTURE.md:93` → `zgate serve | 常驻：监听 7871，做 alias 分流 + 协议桥 + 子进程守护`；`:111-112` → `Windows Job Object：JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`；`:113-115` → 单飞 + startTimeoutSeconds + 指数退避；`:399` → `P3 子进程回收 | 两个上游都用 ondemand（空闲 300 秒回收）`；`:456-459` → `两个 child 都改 ondemand` / `空闲阈值降到 300 秒` |
| A4 | 统一模型命名空间：同型号跨渠道合并成一条链路、模型 ID 只用型号名 | `README.md:26-27` → `现在统一成三组（主力 / 免费 / 省钱），模型 ID 只用型号名（如 DeepSeek-4.1-Flash），同型号跨渠道合并成一条链路（WB 固定链首…）`；`CHANGELOG.md:472-478` → `分组从四组收缩到三组` / `PROVIDER_* 改为三组` / `名单键改为 <协议>:<上游 id>`；`PROGRESS.md:760-769` → `统一模型命名…生成 ~/.zcode/v2/model-alias-map.json` |
| A5 | `/health` 统一视图：每通道 state(up/starting/down/degraded) + 最后一次错误 + PID + alias 条数 | `docs/ARCHITECTURE.md:161-162` → `/health 从"三家各自回显"升级为统一视图：每个通道的 state（up / starting / down / degraded）、最后一次错误、子进程 PID、alias 条数。`；`:95` → `zgate status | 打印各通道/子进程/alias 条数/最近错误` |
| A6 | 293.4MB → ~128MB（ZCode 关闭 ~20MB） | `docs/ARCHITECTURE.md:5` → `落地时实测常驻内存从 293.4（MB，改造前 4 进程）降到 ~128 MB（ZCode 关闭时 ~20 MB）`；`:41` → `~293.4 / ~128 MB`；`:436` → `99.3 MB（zgate 18.7 + Qoder 57.4 + wb2api 23.2）`；`:438` → `18.7 MB` |
| A7 | 统一鉴权 / 凭据只走环境变量，客户端不用自己带 key | `README.md:40` → `凭据只走环境变量`；`CHANGELOG.md:25` → `环境变量只写变量名：QWEN_API_KEY / QWEN_BASE / QD_API_KEY / CLIPROXY_API_KEY / QINIU_API_KEY，值一律从环境变量读`；`PROGRESS.md:778` → `按 channel 还原上游并注入 key` |
| A8 | 三个 chat 组（主力/免费/省钱） | `README.md:26` → `三组`；`:41` → `三个 chat 组`；`CHANGELOG.md:431` → `providerOrder 回到三组`；`:472` → `分组从四组收缩到三组：主力两条 + 免费 + 省钱` |
| A9 | `/admin/reload` 只热加载策略/空闲/窗口；换 Go 代码必须重启 | `CHANGELOG.md:26` → `POST /admin/reload 只热加载 zgate.json 的策略 / 空闲 / 窗口；换 Go 代码必须重启实例`；`docs/ARCHITECTURE.md:421-422` → 同口径并指向 `gateways/zgate/internal/supervisor/supervisor.go:473`；`:460` → `新增 child、监听地址、上游 base 仍需重启` |

## 2. 实况（源码 / 配置 / 运行态优先）

### 2.1 `gateways/zgate/zgate.json`（54 行，read offset=1 limit=54 真实输出）
- `gateways/zgate/zgate.json:2` → `  "listen": "127.0.0.1:7871"`；`:3` → `"aliasMap": "~/.zcode/v2/model-alias-map.json"`；`:4` → `"providerConfig": "~/.zcode/v2/provider_config.json"`；`:5-8` wbGatewayConfig / qoderEnvFile / qwenEnvFile / qiniuEnvFile 四个外置路径；`:9` → `"session": "unified-router"`；`:10` log dir `%LOCALAPPDATA%/ZCodeGateway`。
- `gateways/zgate/zgate.json:11-18` upstreams **恰好 6 个**：`OC` https://opencode.ai/zen/go/v1；`WB` 127.0.0.1:7863/v1 + child workbuddy；`QD` 127.0.0.1:8790/v1 + child qoder；`QW` maas.qianwenaiapi.com/apps/anthropic/v1 + keyEnv QWEN_API_KEY；`QN` api.qnaigc.com/v1 + keyEnv QINIU_API_KEY；`CP` 127.0.0.1:8317/v1 + child cliproxyapi + keyEnv CLIPROXY_API_KEY。OC/WB/QD 在 json 未写 keyEnv，由 `config.go:149-162` 默认值补。
- `gateways/zgate/zgate.json:19-53` children **恰好 3 个**，全 `policy: "ondemand"` + `idleSeconds: 300`：workbuddy（wb2api.exe / port 7863 / health /panel/ / startTimeout 30 / windows 4 档）、qoder（python qoder_proxy.py --port 8790 / port 8790 / health /ping / startTimeout 40 / windows 3 档）、cliproxyapi（cli-proxy-api.exe -config config.yaml / port 8317 / health /v1/models / startTimeout 30 / **windows []**）。

### 2.2 路由表（`gateways/zgate/internal/router/router.go`）
- `router.go:239` `func (s *Server) serveHTTP(...)`；`:247` `path, search := normalizePath(r)`；`:248-251` `if path == "/health" { s.health(w); return }`；`:252-255` `if path == "/admin/reload" { s.reload(w, r); return }`；`:257-272` 读 body 解 `model`；`:274` `isChat := path == "/chat/completions"`；`:275-278` 非 chat 且带前缀 → `400 WorkBuddy/Qoder/Qwen models only support chat/completions`；`:280` `s.aliases.Reload()`；`:281-284` Resolve 命中 → `routeAlias`；`:285` 否则 `routeFallback`。
- `router.go:998-1015` `normalizePath` 全文真实输出：`:1000-1002` `if strings.HasPrefix(path, "/v1") && (len(path) == 3 || path[3] == '/') { path = path[3:] }`；`:1011-1014` `RawQuery` 拼 `"?"+…`。**没有 `/v1/models`、`/v1/messages` 独立 handler**，只是剥 `/v1` 后走同一转发。
- **全量路由表结论**：固定分支仅 `/health`、`/admin/reload` 两条；`/v1/models`、`/v1/messages`、`/v1/chat/completions`、`/models`、`/chat/completions` 全部经 `normalizePath` → body.model → alias/前缀分流 → `forward`；`/admin/` 家族除 reload 外无实现。
- `router.go:963-986` reload 真实输出：`:964` 非 POST → 405；`:969` `next, err := config.Load(old.Path)`；`:974` `ks := keys.Load(next.ProviderConfig, …)`；`:975` `applied, stale, added := s.sup.ApplyConfig(next.Children)`；`:976` `setRuntime(next, ks)`；`:977` `s.aliases.Reload()`；`:984` note `监听地址、新增子进程与 alias map 路径仍需重启 zgate；配置、上游 base 与 key 已热加载`。

### 2.3 `/health` 返回体（`router.go:641-667` 全文真实输出）
- `:642` `s.aliases.Reload()`；`:643-650` `upstreamView(channel)` → `{"base": u.Base, "key": s.keyset().For(channel) != "", "child": u.Child}`；`:651-665` payload = `{ok:true, opencode, workbuddy, qoder, qwen, qiniu, alias:{path,models}, children: s.sup.States(), cooling, uptime_s}`；`:666` `writeJSON(w, 200, payload)`。
- **5 个通道段、缺 CP**；每通道只有 base / key(bool) / child，**无 state、无 lastError、无 pid、无 degraded**；children 明细来自 `supervisor.go:501-534` `States()`：`:508-518` state 仅 `stopped / starting / running / external / error`，`:519-527` entry = `policy,state,port,idle_s,in_window,windows,last_error`，`:528-530` `if k.proc != nil { entry["pid"] = k.proc.Pid() }`。
- 运行态 `node fetch GET http://127.0.0.1:7871/health` 真实输出（17:20 时点）：`status: 200 bytes: 1010`，`ok: true uptime_s: 2812 cooling: 2 alias.models: 22`，`top keys: ["alias","children","cooling","ok","opencode","qiniu","qoder","qwen","uptime_s","workbuddy"]`，`upstream sections: ["opencode","workbuddy","qoder","qwen","qiniu"]`，`has CP section: false`，`each upstream keys: {"opencode":["base","child","key"], …}`（5 段同构）。
- 运行态 children（17:20 时点）：`{"workbuddy":{"idle_s":3,"pid":30920,"policy":"ondemand","port":7863,"state":"running","windows":[4 档]},"qoder":{"idle_s":154,"pid":5884,"policy":"ondemand","port":8790,"state":"running","windows":[3 档]},"cliproxyapi":{"idle_s":24,"pid":5740,"policy":"ondemand","port":8317,"state":"running","windows":[]}}`。
- lead 回喂 17:16 时点：`HTTP 200 / ok=true / uptime_s=2590 / cooling=1 / alias.models=22 / 5 段 key 全 true / children=3（workbuddy running pid=30920、qoder stopped、cliproxyapi stopped）`。**两次差异是时点漂移，不是矛盾**：lead 回喂 17:17:30 请求 `Qwen-3.8-Max` 触发 qoder（17:17:33 就绪 pid=5884）、17:19:40 请求 `Gemini-3.6-Flash` 触发 cliproxyapi（就绪 pid=5740，windows=[] 从不时间窗自启），恰与 17:20 三 running 一致。

### 2.4 `alias.go` 热加载 / 分组键 / 6 上游归并
- `gateways/zgate/internal/alias/alias.go:51-57` `type file struct { Version int; GeneratedAt string; Slot string; Models map[string]Target; Legacy map[string]string }` → 顶层无分组数组，模型命名空间 = `Models` 的 key（对外显示名）；`:36-49` `Target` 含 `Group string`（分组键，中文组名）、`Chain []Hop`、`Fallbacks`、`LegacyIDs`；`:17-33` `Hop` 含 `Channel / Upstream / Base / Protocol / Proxy / Price`。
- `alias.go:78-105` `Reload()`：`:87` `same := m.data != nil && stat.ModTime().Equal(m.mtime) && stat.Size() == m.size`（mtime **+ size 双判**，比文档「按 mtime」更严）；`:78` 注释 `It is cheap enough to call per request.`；`:107-115` `Count()` = `len(m.data.Models)`；`:117-136` `Resolve()`：`:127` `if t, ok := m.data.Models[model]; ok`、`:130` `if display, ok := m.data.Legacy[model]; ok`、`:135` `return Target{}, false` —— **Go map 精确大小写敏感查找，Resolve 自身不调用 Reload**。
- 每请求热加载真实调用点在 `router.go:280`（serveHTTP 读 body 后），另 `:642`（health）、`:977`（reload）；启动 `main.go:150` `am := alias.New(cfg.AliasMap)`。
- 6 上游归并机制：`router.go:669-671` 注释 `routeChain walks a merged chain: every hop carries its own base, channel and upstream id, so one display name can span WorkBuddy, Qoder and OpenCode-Go.`；`:685-764` `attemptChain` 逐跳 `key := s.keyset().For(hop.Channel)`（`:699`）、`prepare(hop.Channel)`（`:705`）、`:717-741` 桥接 `bridge.Forward`、失败 `:757-759` 回落 index+1；`:693-698` 冷却跳过；`:743-752` 传输层重试 + `retryBridgeOn429`。

### 2.5 `~/.zcode/v2/model-alias-map.json` 只读结构与计数（**未 dump 任何含 key 的字段**）
- 命令真实输出（node `fs.readFileSync + JSON.parse`）：`aliasPath: C:\Users\<用户名>\.zcode\v2\model-alias-map.json`，`bytes: 27054`，`mtime: 2026-11-09T05:58:58.337Z`（= 2026-11-09 13:58:58 本地），`topKeys: ["version","generated_at","slot","models","legacy"]`，`version: 1 slot: auto generated_at: 2026-11-09 13:58:58`，`models_count: 22 legacy_count: 94`。
- `entryKeys: ["base","base_model","chain","channel","fallbacks","group","legacy_ids","main_reason","original","price","protocol","region","upstream"]`（13 键；比 lead 回喂的 12 键多 `main_reason`，`region` 键存在但全为空 → 与 lead「region 全空」一致，只是键名口径差一处）。
- `group: {"主力":5,"免费":5,"省钱":12}`、`protocol: {"chat":17,"messages":5}`、`main channel: {"WB":8,"CP":4,"OC":7,"QN":1,"QD":2}`（QW 无主 channel）、`chain hop dist: {"1":10,"2":7,"3":2,"4":3}`、`crossChannel: 4 singleChannel: 18`、`chain channel×proxy: {"WB":10,"OC":11,"OC+proxy":11,"QW":1,"CP":4,"QN":1,"QD":4}`。
- `contains provider_config ref in entries: false` → 条目内**没有** provider_config 引用；配置引用在 `gateways/zgate/zgate.json:4`（`~/.zcode/v2/provider_config.json`），只记路径不记内容。
- lead 回喂同值：`C:/Users/<用户名>/.zcode/v2/model-alias-map.json, 27054 B, version=1, slot=auto, generated_at=2026-11-09 13:58:58；models=22 / legacy=94；主 channel WB8/CP4/OC7/QN1/QD2；group 主力5/免费5/省钱12；protocol chat17/messages5；chain 1:10,2:7,3:2,4:3；跨多渠道链=4、单渠道链=18`。**独立复现一致**。
- `~/.zcode/v2/provider_config.json` 只读结构（不打印任何值）：`bytes: 12027`，`topKeys: ["schemaVersion","config"]`，`config keys: ["providerOrder","providerConfigRules","modelConfigRules"]`，`providerOrder: ["opencode-go-chat","opencode-go-chat-free","opencode-go-chat-fast"]`；`providerConfigRules` 是对象（`keys: ["providerRules"]`），其下 `providerRules` 为键 `"0","1","2"` 的对象 → 3 条 rule。lead 回喂 `personalModelIds` 计数 `opencode-go-chat=5 / opencode-go-chat-free=5 / opencode-go-chat-fast=12，合计 22，与 alias map models=22 一致`（本分片结构读到 3 条 rule 与 3 项 providerOrder，计数值以 lead 回喂为准）。

### 2.6 `tools/model_alias.py` 分组 / 排序 / 去重 与 DSH 界面顺序
- `tools/model_alias.py:75-84` → `PROVIDER_MAIN = "opencode-go-chat"` / `PROVIDER_FREE = "opencode-go-chat-free"` / `PROVIDER_LOW = "opencode-go-chat-fast"` / `PROVIDER_IDS = [PROVIDER_MAIN, PROVIDER_FREE, PROVIDER_LOW]` / `PROVIDER_NAMES` 映射「主力/免费/省钱」/ `GROUPS = ("main","free","low")`。
- `tools/model_alias.py:202-203` → `CHANNEL_RANK = {"WB": 0, "CP": 0, "OC": 1, "QD": 1, "QW": 2, "QN": 3}` / `CHANNEL_RANK_DEFAULT = 4`；`:1235-1243` 链首排序按 CHANNEL_RANK（WB/CP 链首、QD 先于 OC）。
- `tools/model_alias.py:846` `def anonymous_rank(abbr: str) -> int:`；`:1411` `represented: dict[str, list[tuple[int, ...]]] = {}`、`:1424` `represented.setdefault(vendor, []).append(_version_of(entry))`、`:1450` `have = represented.get(vendor) or []`（按厂商版本去重/配额）；`:1488` `rows.sort(key=lambda r: (r[0], r[1]), reverse=True)`（候选池排序）。
- `tools/model_alias.py:1867` `def _pick_rank(row: dict, order: list[str]) -> int:`；**三处组内 `rows.sort`**：`:1885-1886` 主力 `(anonymous_rank, _pick_rank(MAIN_ORDER), new_id)`；`:1888-1889` 省钱 `(anonymous_rank, _pick_rank(LOW_ORDER), price, new_id)`；`:1892-1893` 免费 `(HY 优先, anonymous_rank, …)`；`:1541` `_GROUP_LABELS`、`:1799` `grouped = {key: [] for key in GROUPS}`、`:1936-1937` 打印分组计数、`:2101` `cfg["config"]["providerOrder"] = PROVIDER_IDS`。
- **DSH 侧界面顺序**：`tools/model_alias.py:849-850` 与 `:1881` 注释真实输出 → `DSH GUI 侧不做二次排序（orderModelProviders 只把 account/official 提前，组内保持 catalog 原序），所以「匿名置底」必须在这里生效`。全项目 grep `orderModelProviders|catalog|providerOrder` 114 命中：本仓**无 `orderModelProviders` 实现源码**，仅这两处注释；`tools/dsh_sync.py:133` `order = config.get("providerOrder") or list(rules)` → DSH 投影继承 `providerOrder → modelOrder` 原序、不二次排序，因此 `model_alias.py` 的组内排序就是最终 catalog 原序。`evidence/agent-sort-rule.md:9-10`（另一子代理分片，只读旁证）同口径：`tools/dsh_sync.py 不排序，只继承 providerOrder → modelOrder`。

### 2.7 鉴权 / 凭据（只记变量名与结构）
- `gateways/zgate/internal/keys/keys.go:20-23` `type Set struct { OC, WB, QD, QW, QN, CP string }`；`:113-162` `Load(...)`：`:116-121` env `OPENCODE_GO_KEY` / `WB_GATEWAY_KEY` / `QD_API_KEY` / `QWEN_API_KEY` / `QINIU_API_KEY` / `CLIPROXY_API_KEY`；`:122-160` 回退读 `provider_config.json` 的 `config.access.apiKey`、gateway `config.json` 的 `api_key`、各 `.env.local`；`:155-160` CP 回退读 `cliproxy.env` 的 `CLIPROXY_ACCESS_KEY`（与 `zgate.json:17` `keyEnv=CLIPROXY_API_KEY` 名称不一致）；`:165-181` `For(channel)` 覆盖 6 通道。
- `router.go:294-298` 空 key → `502 channel+" key not configured"`；`router.go:457-487` `forwardHeaders` 的 switch 只对 `WB, QD, QW, CP` 与 `OC` 设 `Authorization: Bearer`，**原生 chat 路径不含 QN**；桥接路径 `gateways/zgate/internal/bridge/bridge.go:83-89` 真实输出 → `"x-api-key": opts.Key`、`"anthropic-version": "2023-06-01"`、`"x-opencode-session": "unified-bridge"`，`:93-98` responses → `"authorization": "Bearer " + opts.Key`。
- `main.go:135` `ks := keys.Load(...)`、`:151` `sup := supervisor.New(cfg.Children, …)`、`:171` `ln, err := net.Listen("tcp", cfg.Listen)`、`:180` `go sup.Start()`、`:181-184` `srv := &http.Server{Handler: router.New(cfg, ks, am, sup, client, log).Handler(), ErrorLog: nil}` → **单监听器、单 Handler，无第二个 mux**；`:196-203` 遍历 `[]string{"OC","WB","QD","QW","QN","CP"}` 打 key 状态。
- `router.go:444-455` `prepare(channel)`：有 `upstream.Child` 才 `s.sup.Touch(child)` + `s.sup.Ensure(child)`；`gateways/zgate/internal/supervisor/supervisor.go:475-499` `ApplyConfig` 新增 child 只记入 `added` 不创建。

## 3. 【核心判定】命名空间分叉：统一入口 ≠ 统一命名空间 ≠ 统一协议

### 3.1 运行态实证（lead 回喂 + 本分片独立复现）
- `GET /v1/models` 与 `GET /models`：`node fetch` 真实输出 → `GET /v1/models status: 200 bytes: 35541`、`GET /models status: 200 bytes: 35541`、`v1/models === /models byte-identical: true`；`{object,data}` 的 `data len=30`。lead 回喂同值 → **`OC 单家 catalog 透传，不是 6 家聚合**。
- lead 命名空间交叉命中（17:1x 时点）：30 个 id 中 `直接命中 22 统一名=8`、`命中 94 legacy 键=6`、`都不命中=16`，后者清单 `deepseek-v4-pro, glm-5.2, glm-5.3, grok-4.7, muse-spark-1.2-contributor, gpt-5.6-luna, hy4-preview, kimi-k2.7-code, kimi-k3, minimax-m3, longcat-2.0, step-5-preview, qwen3.7-plus, kimi-k3.1-pro, gemini-4-argon, crouton-alpha-free`。
- lead `zgate.log` 增量真实输出：`model=deepseek-v4-pro → "POST /chat/completions model=deepseek-v4-pro -> opencode"`；`model=kimi-k3 → "-> opencode"`（**直穿 OC，不过 alias 链 / 跨渠道回落 / 冷却 / 协议桥**）；对照 `model=HY4-Free → "-> WB:cn:hy4free (1/1)"`；`legacy["deepseek-v4.1-flash"]="DeepSeek-4.1-Flash"` 发该 id → `"-> WB:cn:deepseek-v4.1-flash (1/4)"`（命中 4 跳聚合链）。
- 本分片 17:20 独立复现 `node fetch + JSON.parse` 精确语义（`alias.go:127/:130` 是大小写敏感的 Go map 查找）：`catalog ids: 30 | Models[] 精确命中: 0 | Legacy[] 精确命中: 11 | 两者皆不命中 → routeFallback 默认 OC: 19`；`Legacy 精确命中 ids: ["deepseek-v4.1-flash","muse-spark-1.3-contributor","glm-5.3-flash","gpt-6-luna","claude-haiku-5-5","mimo-v2.6-flash","mimo-v2.6-pro","minimax-m3.1-flash","beam-free","qwen3.8-flash","iceman-contributor-free"]`；`直穿 OC 的 ids` = lead 16 个 + `hy3 / qwen3.8-max / hy4`。大小写不敏感口径下为 `unified=5 / legacy=8 / neither=17`（`ci unified: ["glm-5.3-flash","gpt-6-luna","hy3","minimax-m3.1-flash","hy4"]`）。
- **口径差异解释**：lead 的 `8/6/16` 与本分片 `0/11/19`（或 CI `5/8/17`）来自 catalog 时点漂移（本次 30 个 id 含 `hy3`、`qwen3.8-max`、`hy4`、`muse-spark-1.3-contributor`、`qwen3.8-flash` 等 lead 清单未列项）+ 大小写口径差异；**三套口径共同结论不变：30 个对外 id 中约一半（16~19 个）不被 `Resolve` 识别，标准 OpenAI 协议下全部落到默认 OC**。

### 3.2 源码机理（把现象钉到行号）
1. `router.go:280` `s.aliases.Reload()` → `:281` `s.aliases.Resolve(model)`；`alias.go:127` `m.data.Models[model]`、`:130` `m.data.Legacy[model]`、`:135` `return Target{}, false`（精确大小写）。
2. 未命中 → `router.go:285` `s.routeFallback(...)`；`:351` `channel := "OC"`；`:353` `base := cfg.Upstreams["OC"].Base`；`:354` `label := "opencode"`；`:356` `key := ks.OC`；`:357-433` switch 只对 `qoder:` / `qwen:` / `qn:` / `cn:` / `global:` 前缀改道（`:1130-1145` 前缀函数）；`:428-432` default 仍校验 OC key；`:439` `s.log.Infof("… model=%s -> %s", …, label)` 打 `-> opencode`；`:440` `s.forward(w, r, body, base, path, search, headers)`。
3. 命中才走 `router.go:288-348` `routeAlias` → `:289-291` `routeChain` → `attemptChain` 多跳跨渠道/回落/冷却/协议桥。因此 **16~19 个裸 id 既不进 alias 链也不进桥，等于 6 上游聚合能力对它们完全不生效**。
4. **统一入口不等于统一协议**：`router.go:274` `isChat := path == "/chat/completions"`；`:275-278` 非 chat 且带前缀 → `400 "WorkBuddy/Qoder/Qwen models only support chat/completions"`；`:303-307` `protocol != "chat"` 且 `!isChat` → `400 "<channel> bridged models only support chat/completions"`。lead 实测协议 400 结论修正：7871 把路径原样透传给上游（`/v1/messages` 无协议归一化），`messages` 桥只在 `/chat/completions` 入口生效；alias map 里 `protocol: messages=5` 条的可用性受此约束。

## 4. 「规划承诺 / 实况 / 达成? / 证据」表

| 规划承诺 | 实况 | 达成? | 证据（真实路径:行号 + 输出） |
|---|---|---|---|
| A1 一个 Go 入口 + 6 upstream / 3 child | 单监听器单 Handler；配置 6 upstreams / 3 children 齐全 | **达到** | `gateways/zgate/zgate.json:2,11-18,19-53`；`gateways/zgate/main.go:171,181-184` |
| A2 单一 7871 入口 | 只 `net.Listen("tcp", "127.0.0.1:7871")`；`/health` 200；`/v1/models` 200 bytes=35541 | **达到** | `gateways/zgate/zgate.json:2`；`gateways/zgate/main.go:171`；`node fetch GET /health status: 200`、`GET /v1/models status: 200 bytes: 35541` |
| A2b 一套模型命名空间 | alias map `Models` 22 个统一名是唯一命名空间，但 `/v1/models` 对外列 30 个 OC 裸 id，其中 16~19 个 `Resolve` 不命中 → `routeFallback` 默认 OC 直穿 | **部分达到（主因差距）** | `gateways/zgate/internal/alias/alias.go:51-57,127,130,135`；`gateways/zgate/internal/router/router.go:280-285,351-356,428-440`；`GET /v1/models data len=30`、`v1/models === /models byte-identical: true`；lead `zgate.log model=deepseek-v4-pro -> opencode` |
| A3 children 统一托管 | 3 child 全 ondemand / idle 300 / 窗口兜底；17:20 三 `state=running` `last_error=""`，PID 30920 / 5884 / 5740 | **达到** | `gateways/zgate/zgate.json:19-53`；`gateways/zgate/internal/router/router.go:444-455`；`gateways/zgate/internal/supervisor/supervisor.go:475-499,501-534`；`GET /health children` 3 running；lead 17:17:30 / 17:19:40 触发记录 |
| A4 统一模型命名空间 + 三组 | 三组由 `model_alias.py` 生成并写入 alias map（主力5/免费5/省钱12=22）；但对外 catalog 仍是 OC 单家 30 id | **部分达到** | `tools/model_alias.py:75-84,2101`；`alias map group {"主力":5,"免费":5,"省钱":12}`；`GET /v1/models data len=30` |
| A5 /health 统一视图 | 固定 200、5 段（缺 CP）、每通道仅 base/key/child；children 明细才有 state/last_error/pid；无 up/down/degraded | **部分达到** | `gateways/zgate/internal/router/router.go:641-667`；`gateways/zgate/internal/supervisor/supervisor.go:508-530`；`GET /health top keys` 10 项 / `has CP section: false` |
| A6 293.4→128MB | 17:16 当前负载实测 `zgate 30.8 MB + wb2api 33.2 MB = 64.0 MB`（qoder/CP 未启动）；文档另有 99.3 / 18.7 MB。**属不同时点口径，不判文档造假** | **达到（口径需注明时点）** | `docs/ARCHITECTURE.md:5,41,436,438`；lead `Get-Process WorkingSet64` 17:16 输出；`GET /health children` 时点漂移 |
| A7 统一鉴权 / 客户端不带 key | zgate 集中注入 6 套 key；但回退读 `provider_config.json` 的 `config.access.apiKey` / gateway `api_key` / `.env.local`；原生 chat 路径 QN 未注入；CP 的 env 名与文件回退名不一致；前缀回退仍允许客户端自己选渠道 | **部分达到** | `gateways/zgate/internal/keys/keys.go:113-162,165-181`；`gateways/zgate/internal/router/router.go:294-298,350-442,457-487`；`gateways/zgate/internal/bridge/bridge.go:83-98`；`gateways/zgate/zgate.json:17` |
| A8 三个 chat 组 | 源码 `PROVIDER_IDS` / `GROUPS` 各 3；`providerOrder` 3 项；文档 ARCHITECTURE / PROGRESS 历史段落仍写四组 | **达到（源码为准），文档冲突** | `tools/model_alias.py:75-84`；`provider_config.json providerOrder: ["opencode-go-chat","opencode-go-chat-free","opencode-go-chat-fast"]`；`README.md:26,41`；`CHANGELOG.md:472` |
| A9 /admin/reload 只热加载策略/空闲/窗口 | 源码是全量 `config.Load` + `keys.Load` + `setRuntime` + `ApplyConfig` + `aliases.Reload`，note 明写「配置、上游 base 与 key 已热加载」 | **文档过时，源码更宽** | `gateways/zgate/internal/router/router.go:963-986`；`CHANGELOG.md:26`；`docs/ARCHITECTURE.md:421-422` |
| 附：/v1/models、/v1/messages、/admin/... 全量路由 | 固定分支仅 `/health`、`/admin/reload`；`/v1/*` 靠 `normalizePath` 剥前缀 + 通用转发；无其它 admin 接口；`/v1/messages` 无协议归一化（非 chat 带前缀 → 400） | **与「全部列出」预期不符** | `gateways/zgate/internal/router/router.go:239-285,274-278,303-307,998-1015` |

## 5. 硬结论（5 条，每条带证据）

1. **【主因】聚合性 = 部分达到：单入口达成，统一命名空间分叉。** `gateways/zgate/zgate.json:2` + `gateways/zgate/main.go:171,181-184` 证明 7871 单入口单进程；但 `GET /v1/models status: 200 bytes: 35541` 与 `GET /models … byte-identical: true`、`data len=30` 证明对外 catalog 是 **OC 单家透传**；`alias.go:127/:130/:135` 的精确大小写 `Resolve` 只认 22 个统一名 + 94 个 legacy 键，剩余 16~19 个裸 id 由 `router.go:285,351-356,428-440` 落到 `channel="OC"` 直穿（lead `zgate.log model=deepseek-v4-pro -> opencode`、`model=kimi-k3 -> opencode`；对照 `HY4-Free -> WB:cn:hy4free (1/1)`、`deepseek-v4.1-flash -> WB:cn:deepseek-v4.1-flash (1/4)`）。**6 上游的 alias 链 / 跨渠道回落 / 冷却 / 协议桥只对可解析的名字生效**。
2. **聚合链本身是真落地、不是纸面代码。** `gateways/zgate/internal/alias/alias.go:36-49,17-33,51-57` 定义 `Target.Chain []Hop` 承载每跳 channel/base/protocol/proxy；`gateways/zgate/internal/router/router.go:669-671,685-764` 逐跳取 key、prepare、桥接、失败回落；alias map 实测 `chain hop dist {"1":10,"2":7,"3":2,"4":3}`、`crossChannel: 4`、`chain channel×proxy {"WB":10,"OC":11,"OC+proxy":11,"QW":1,"CP":4,"QN":1,"QD":4}`。运行态 lead 回喂 `zgate.log` 命中「冷却|退避|回落|429|region|quota」**2915 行**，尾部 `17:09-17:10 "[router] OC|beam-free| 冷却中，跳过"` 与 `17:19:45 "[router] QN|qiniu/conatus-free| 429，退避 700ms 后重试同一跳"`；`/health cooling` 0→1→2（本分片 17:20 读到 `cooling: 2`）。
3. **children 统一托管达到，且 3 个 child 都实测可按需拉起。** `gateways/zgate/zgate.json:19-53` 三个 `ondemand` + idle 300；`gateways/zgate/internal/router/router.go:444-455` `prepare()` → `sup.Touch + sup.Ensure`；`GET /health`（17:20）三个 `state=running` / `last_error=""` / `policy=ondemand`，PID workbuddy 30920、qoder 5884、cliproxyapi 5740；lead 回喂触发链 `17:17:30 Qwen-3.8-Max → qoder pid=5884`、`17:19:40 Gemini-3.6-Flash → cliproxyapi pid=5740（windows=[] 从不时间窗自启）`。lead 回喂 `build_candidate` 换版链存在（本分片未独立复核具体步骤，按 lead 口径记为托管可达性旁证，不作硬结论）；`gateways/zgate/internal/router/router.go:984` 明确「新增子进程仍需重启 zgate」。
4. **`/health` 统一视图部分达到，且文档自相矛盾。** 承诺 `docs/ARCHITECTURE.md:161-162` 要每通道 state(up/starting/down/degraded)+lastError+PID+alias 条数；实况 `router.go:643-665` 固定 200、5 段（缺 CP）、每段仅 `base/key/child`；`supervisor.go:508-530` 只有 stopped/starting/running/external/error 五态、pid 仅进程存活时存在。运行态 `GET /health top keys` 无 CP 段、`each upstream keys: ["base","child","key"]`。`docs/ARCHITECTURE.md:116` 自述「States() 也不含降级字段」与 :161 承诺冲突。
5. **鉴权集中但未统一，统一入口不等于统一协议。** `keys.go:113-162` 集中取 6 通道 key、`router.go:294-298` 空 key 即 502；但 `:122-160` 回退读 `provider_config.json` 的 `config.access.apiKey` 与 gateway `api_key`（与 `README.md:40`「凭据只走环境变量」冲突），`router.go:474-485` switch 未含 QN，`zgate.json:17` `CLIPROXY_API_KEY` 与 `keys.go:155-160` 文件回退 `CLIPROXY_ACCESS_KEY` 名称不一致，`router.go:350-442` 前缀回退证明客户端仍可自己选渠道；`router.go:274-278,303-307` 的非 chat 400 与 lead 实测协议 400 共同证明 7871 不归一化 `/v1/messages` 协议。

## 6. 文档 ↔ 源码/运行态冲突清单（以源码与运行态为准）

| # | 文档自述 | 源码/配置/运行态实况 | 裁定 |
|---|---|---|---|
| C1 | `docs/ARCHITECTURE.md:33,254,334` 四个 chat 组 / 四组 36 模型；`PROGRESS.md:760-830` 四组 43 模型；`router.go:1-6` 注释 `four chat providers` | `README.md:26,41`、`CHANGELOG.md:472-476` 三组；`tools/model_alias.py:75-84` `PROVIDER_IDS`/`GROUPS` 各 3；alias map `group {"主力":5,"免费":5,"省钱":12}`；`providerOrder` 3 项 | 现行三组；ARCHITECTURE 与 router 注释过时 |
| C2 | `docs/ARCHITECTURE.md:37` `1 个入口进程 + 2 个按需子进程`；`:399` `两个上游都用 ondemand`；`:456` `两个 child 都改 ondemand` | `zgate.json:19-53` 三个 children；`GET /health children` 3 项；`README.md:27,41` 三个本地子进程 | 3 个 child；ARCHITECTURE 旧稿 |
| C3 | `docs/ARCHITECTURE.md:5,41` 目标 ~128 MB；`:436` 同文档实测 99.3 MB | 17:16 当前负载实测 64.0 MB（zgate 30.8 + wb2api 33.2，qoder/CP 未启动） | **不同时点口径，不判文档造假**；报告须注明时点与负载 |
| C4 | `docs/ARCHITECTURE.md:161-162` /health 每通道四态 + lastError + PID | `router.go:643-665` 每通道仅 base/key/child；`supervisor.go:508-518` 五态 stopped/starting/running/external/error；`:116` 同文档自述无降级字段 | 承诺未落地，文档内部自相矛盾 |
| C5 | `CHANGELOG.md:26`、`docs/ARCHITECTURE.md:421-422` `/admin/reload 只热加载策略/空闲/窗口` | `router.go:969,974,976,977,984` 全量 `config.Load` + `keys.Load` + `setRuntime` + `ApplyConfig` + `aliases.Reload`，note 明写 base 与 key 已热加载 | 文档过时；源码为准 |
| C6 | `README.md:40` 凭据只走环境变量；`CHANGELOG.md:25` 值一律从环境变量读 | `keys.go:122-160` 回退读 `provider_config.json` 的 `config.access.apiKey`、gateway `api_key`、各 `.env.local` | 源码为准：env 优先但有多层文件回退 |
| C7 | `docs/ARCHITECTURE.md:144` alias「按 mtime 热加载」 | `alias.go:87` `ModTime().Equal(m.mtime) && stat.Size() == m.size` 双判；真实每请求调用点在 `router.go:280`（非 Resolve 内） | 文档漏了 size 与调用点 |
| C8 | 报告 `docs/reports/MODEL-SYNC-20261109-1201.md` 18 个（主力5/免费5/省钱8） | 现行 alias map = 22（`group {"主力":5,"免费":5,"省钱":12}`）、provider_config `personalModelIds` 5/5/12=22；产物 mtime 13:58 晚于 12:01 报告，`cordis.patch.yml` mtime 15:01；12:01 日志失败段数=0 | **报告与现行产物不同步，不是同步失败**；lead 回喂 |

## 7. lead 回喂交叉实证并入（关键词收口）

- **`/v1/models` 透传**：lead `HTTP 200 bytes=35541 / {object,data} / data len=30 / 与 GET /models 逐字节相同 → OC 单家 catalog 透传，不是 6 家聚合`；本分片 `node fetch` 独立复现 `v1/models === /models byte-identical: true`。
- **命名空间 16 裸 id 直穿**：lead `8 命中 22 统一名 / 6 命中 94 legacy / 16 都不命中` + `zgate.log -> opencode`；本分片按 `alias.go:127/:130` 精确语义复现为 `0 / 11 / 19`，CI 口径 `5 / 8 / 17`，差异来自 catalog 时点漂移与大小写口径，结论一致。
- **统一入口不等于统一协议**：lead 实测协议 400 修正；源码 `router.go:274-278,303-307` 非 chat 带前缀即 400，`/v1/messages` 无协议归一化，`messages` 桥只在 `/chat/completions` 生效。
- **6 upstream 运行态矩阵**：OC / WB / QD / QW / QN 在 `/health` 各有 1 段且 `key=true`（lead 17:16）；CP **无独立段**，但 alias map `main channel CP=4`、链内 `CP=4` 跳、`children.cliproxyapi state=running pid=5740 port=8317`，说明 CP 实际可达而 health 不可见；QW 无主 channel（仅链内 `QW:1`），与主 channel 分布 `{"WB":8,"CP":4,"OC":7,"QN":1,"QD":2}` 一致。
- **ondemand 两个 PID**：qoder 5884（17:17:33 就绪）、cliproxyapi 5740（17:19:40 就绪），workbuddy 30920 一直在；三者 `policy=ondemand` / `last_error=""`。
- **build_candidate 换版链**：lead 回喂存在（本分片未独立复核具体步骤，按 lead 口径记为托管可达性旁证）。
- **12:01 报告 18 vs 现行 22 可见性缺口**：见 C8。
- **内存时点口径**：17:16 `zgate 30.8 MB + wb2api 33.2 MB = 64.0 MB`，与 128 / 99.3 MB 属不同时点，不判文档造假。
- **冷却/回落运行态**：`/health cooling 0→1→2`；`zgate.log` 2915 行冷却/退避/回落/429/region/quota，含 `[router] OC|beam-free| 冷却中，跳过` 与 `[router] QN|qiniu/conatus-free| 429，退避 700ms 后重试同一跳`。

## 8. 限制与未决疑问

1. `orderModelProviders` 的 DSH 侧实现源码不在本仓，只在 `tools/model_alias.py:849-850` / `:1881` 注释出现；本仓只能证明 `tools/dsh_sync.py:133` 继承 `providerOrder → modelOrder` 原序不二次排序。「只把 account/official 提前」属注释口径，需到运行时目录复核。
2. `provider_config.json` 的 `personalModelIds` 三级嵌套（`config.providerConfigRules.providerRules` 为对象而非数组）本分片只读到结构与 3 条 rule，计数 5/5/12=22 采 lead 回喂；与 alias map 22 一致，可交叉印证。
3. `build_candidate` 换版链、`Get-Process WorkingSet64` 具体命令、`zgate.log` 2915 行 grep 均为 lead 回喂，本分片未独立重跑（按 lead「立即收口、勿再扩大检索」执行）。
4. `zgate.json:17` `CLIPROXY_API_KEY`（env）与 `keys.go:155-160` `CLIPROXY_ACCESS_KEY`（cliproxy.env 文件回退）是否同一凭据的两个来源，未核 `third-party/cliproxyapi/cliproxy.env` 结构（只记键名）；本分片只记变量名差异。
5. 30 个 catalog id 的 8/6/16 与 0/11/19 差异已解释为时点 + 大小写口径；若需单一权威数字，建议在固定时点同时冻结 `/v1/models` 响应与 alias map 再跑一次精确 `Resolve` 分类。

## 9. 改了什么 / 怎么验证

- **改了什么**：只写本分片 `F:\Project\ModelBus\evidence\agent-aggregation.md`（初稿 117 行 → 终稿），并入 lead 全部交叉实证、独立复现 alias map 结构计数与运行态 GET、补读 `normalizePath` / `routeFallback` / `Resolve` / `bridge` 源码机理；未改任何源码/配置/文档/测试，未碰 PROGRESS.md / docs/ / tools/ / gateways/ / 共享文件，未重启/停止网关，未打印凭据真值。
- **怎么验证**：`tools.read` / `tools.grep` 逐行行号 + `node fs.readFileSync + JSON.parse`（`bytes: 27054`、`models_count: 22 legacy_count: 94`、`group: {"主力":5,"免费":5,"省钱":12}`）+ `node fetch GET`（`/health 200 bytes 1010`、`/v1/models 200 bytes 35541`、`v1/models === /models byte-identical: true`、`catalog ids: 30 / Models[] 0 / Legacy[] 11 / bypass 19`）；终稿行数/字节由 `fs.statSync` 复核并回报 parent。

---
> 本文件由子代理 agent-aggregation 独立写入，证据以源码/配置/运行态为准；文档自述冲突已在 §6 逐条指出。


## lead 验收收口（2026-11-09 17:23，独立复现接管）

### 聚合性核心分叉：统一命名空间只对 ZCode 面板生效
GET /v1/models 实测 HTTP 200 bytes=35541，{object,data} data len=30；与 GET /models 逐字节相同 → OC 单家 catalog 透传（routeFallback default → s.forward 到 opencode），不是 6 家聚合视图。router.go 全文件 grep /models|v1/models|catalog|listModels 命中 0；zgate.log 佐证 "GET /models model=- -> opencode"。
/v1/models 的 30 个 id 里：直接命中 22 个统一名=8、命中 94 个 legacy 键=6、都不命中=16。都不命中 16 id = deepseek-v4-pro | glm-5.2 | glm-5.3 | grok-4.7 | muse-spark-1.2-contributor | gpt-5.6-luna | hy4-preview | kimi-k2.7-code | kimi-k3 | minimax-m3 | longcat-2.0 | step-5-preview | qwen3.7-plus | kimi-k3.1-pro | gemini-4-argon | crouton-alpha-free。
运行态探测（最小 chat 请求 + zgate.log 新增行）：model=deepseek-v4-pro → "POST /chat/completions model=deepseek-v4-pro -> opencode"；model=kimi-k3 → "-> opencode"（直穿 OC，不过 alias 链/跨渠道回落/冷却/协议桥）；对照 model=HY4-Free → "-> WB:cn:hy4free (1/1)"；legacy["deepseek-v4.1-flash"]="DeepSeek-4.1-Flash"，发该 id → "-> WB:cn:deepseek-v4.1-flash (1/4)"（命中 4 跳聚合链）。
→ 单入口 7871 达成；统一命名空间只对 ZCode 面板（22 统一名）+ 94 个 legacy 键生效；/v1/models 对外列的 16 个裸 id 在标准 OpenAI 协议下全部直穿 OC。这是「部分达到」的主因，比 /health 缺 CP 更关键。

### 真值口径（补齐初稿未决①~⑤）
  alias map = C:/Users/<用户名>/.zcode/v2/model-alias-map.json，27054 B，version=1 / slot=auto / generated_at=2026-11-09 13:58:58；顶层 version,generated_at,slot,models,legacy；models=22 组、legacy=94 键；每组 12-13 键（channel,region,upstream,base_model,base,protocol,original,price,group,fallbacks,chain,legacy_ids）。主 channel {"WB":8,"CP":4,"OC":7,"QN":1,"QD":2}（QW 无主 channel）；group 主力5/免费5/省钱12；protocol chat17/messages5；region 全空；chain 跳数 1:10,2:7,3:2,4:3；跨多渠道链=4、单渠道链=18；全链跳 channel×proxy 组合 {"WB":10,"OC":11,"OC+proxy":11,"QW":1,"CP":4,"QN":1,"QD":4}。
  provider_config.json 含 personalModelIds 的 rule 3 个：opencode-go-chat=5 / opencode-go-chat-free=5 / opencode-go-chat-fast=12，合计 22，与 alias map models=22 一致。
  GET /health 实测 HTTP 200：ok=true / uptime_s=2794 / cooling=2 / alias.models=22；顶层 5 段 opencode/workbuddy/qoder/qwen/qiniu 各 {base,child,key:bool} 且 key 全 true，无 CP 独立段；children 探测后三个全 running（workbuddy 30920 / qoder 5884 / cliproxyapi 5740，全 policy=ondemand、last_error 空）。对照 docs/ARCHITECTURE.md:161 承诺「每个通道 state / 最后一次错误 / 子进程 PID / alias 条数」，实际只给 key 布尔 + children 分离视图 → 统一视图不完整；docs/ARCHITECTURE.md:116 自述「States() 不含降级字段」与 :161 自相矛盾。
  运行态内存实测（Get-Process WorkingSet64）：zgate 30.8 MB + wb2api 33.2 MB = 64.0 MB（qoder/CP 拉起前）。与 docs/ARCHITECTURE.md 的 128 MB / 99.3 MB 属不同时点口径，判「需注明时点」，不判文档造假。
  冷却/回落运行态：zgate.log 命中「冷却|退避|回落|429|region|quota」共 2915 行；尾部 17:09-17:10 连续 "[router] OC|beam-free| 冷却中，跳过"、17:19:45 "[router] QN|qiniu/conatus-free| 429，退避 700ms 后重试同一跳"；/health cooling 0→1→2。→ 聚合链容错不是纸面代码。
  DSH orderModelProviders 实现不在本仓（在 dsh-client-ui-model-selection/lib/client.js:1101-1110，组内保持 catalog 原序），本仓只产三组与 alias map。

### 可见性缺口
docs/reports/MODEL-SYNC-20261109-1201.md 说 18 个模型（主力5/免费5/省钱8）且失败段数=0，但当前 alias map=22、provider_config=5/5/12=22；alias map/provider_config mtime 13:58 晚于 12:01 报告，cordis.patch.yml 15:01。→ 报告与现行产物不同步，缺一份「当前生效清单」的单一真值视图；不是同步失败。

### 聚合性终判定：部分达到
✅ 单入口 7871 / 6 upstream / 3 child 按需托管 / 一套 22 统一名 + 94 legacy 键 / 聚合链含跨渠道回落与冷却 / alias map 按 mtime 每请求热加载。
❌ /v1/models 是 OC 单家透传，16 个对外裸 id 直穿不聚合；/health 缺 CP 独立段且无每通道 state/lastError；鉴权来源分散在 env / provider_config / .env.local / child 四层，客户端仍可用渠道前缀自选渠道；报告口径与现行产物不同步。
