# 排错手册

> **一句话**：按「现象 → 排查步骤 → 原因 / 解法」组织的排查流程 ——
> 标题就是检索词，搜到标题就搜到了解法。

**机制解释在 [PITFALLS.md](PITFALLS.md)**，本篇只讲怎么查、怎么修。

**每条都标了适用范围**：

| 标记 | 含义 |
|---|---|
| **【通用】** | 换任何供应商都成立 —— ZCode 客户端侧的行为、协议与配额机制 |
| **【实例 A】** | OpenCode-Go 特有（本仓实例一） |
| **【实例 B】** | WorkBuddy2API 网关特有（本仓实例二） |

通用条目照抄就能用；实例条目只在本仓这两个示例供应商上成立，
接自己的供应商时按「机制」那一列推断。

---

<a id="model-list-not-refreshed"></a>

## 1. ZCode 里模型列表不刷新 【通用】

**现象**：脚本跑完说「已写入」，但 ZCode 的模型列表里没有新模型；
或者过一会儿模型自己消失了。

**排查**

```bash
# 1) 确认脚本真的写进去了
python -c "import json,os; p=os.path.expanduser('~/.zcode/v2/provider_config.json'); c=json.load(open(p,encoding='utf-8')); r=c['config']['providerConfigRules']; rs=r['providerRules'] if isinstance(r,dict) else r; [print(x['providerId'], x.get('providerName'), len(x.get('config',{}).get('personalModelIds',[]))) for x in rs]"

# 2) 看备份确认脚本动过文件（时间戳对得上 = 写过了）
ls -lt ~/.zcode/v2/provider_config.json*

# 3) 确认 JSON 没写坏
python -c "import json,os; json.load(open(os.path.expanduser('~/.zcode/v2/provider_config.json'),encoding='utf-8')); print('JSON OK')"

# 4) 确认模型规则也在（provider 有模型但没 model rule = 不会出现在列表里）
python -c "import json,os; c=json.load(open(os.path.expanduser('~/.zcode/v2/provider_config.json'),encoding='utf-8')); m=c['config']['modelConfigRules']; rs=m['providerModelRules'] if isinstance(m,dict) else m; print(len(rs),'条模型规则')"
```

**原因 / 解法**（全部**【通用】**）

| 原因 | 解法 |
|---|---|
| ZCode 还没热重载（约 1 秒轮询） | 等 1~2 秒；仍不刷新就**重启客户端** |
| **ZCode 的 provider 设置界面在你写完之后又保存了一次**，整份写回覆盖了 | 写配置期间**不要在界面里改**；重新跑一次脚本 |
| 只写了 `personalModelIds` 没写 `modelConfigRules.providerModelRules` | 两个都要有（脚本会一起写） |
| `providerId` 与 `providerOrder` 里不一致 | `providerOrder` 里补上该 `providerId` |
| 写到了**另一个** `provider_config.json` | 检查环境变量 `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` 与实际路径是否一致 |

---

<a id="model-400"></a>

## 2. 某个模型 400 【通用】

**现象**：某个模型一发就 400，报 `ModelProtocolUnsupported` / `does not support this protocol`
/ `invalid request` 之类。

**排查**

```bash
# 1) 看 ZCode 会给这个模型发什么（复刻引擎规则，算真实 body）
cd workbuddy
node zcode_effective_body.js <model-id>

# 2) 看这个模型归在哪个 provider、什么协议
python -c "import json,os; c=json.load(open(os.path.expanduser('~/.zcode/v2/provider_config.json'),encoding='utf-8')); r=c['config']['providerConfigRules']; rs=r['providerRules'] if isinstance(r,dict) else r; [print(p['providerId'], p['config']['api']['type'], m) for p in rs for m in p['config'].get('personalModelIds',[]) if m=='<model-id>']"

# 3) OpenCode-Go 侧：三协议逐个试，看哪个不是 400
#    messages 协议只认 x-api-key，其余认 Authorization: Bearer
```

**原因 / 解法**

| 原因 | 适用范围 | 解法 |
|---|---|---|
| **协议放错**（模型不在这个 provider 的协议里） | **【通用】** | 挪到正确的 provider，见 [MODEL-PROVIDERS.md](MODEL-PROVIDERS.md) §2 |
| **ZCode 注入的思考字段上游不认** | **【通用】** | 给模型配 `optionSpecs.reasoningLevel.map = "{}"`，见 [PITFALLS.md](PITFALLS.md) §2 |
| `anthropic/messages` 用了 `Authorization: Bearer` | **【实例 A】** | 换成 `x-api-key`（OpenCode-Go 的 messages 端点只认这个头） |
| 缺 `x-opencode-session` | **【实例 A】** | ZCode 会自动带；其它客户端用 `opencode-header-proxy.js` |
| 上游要隐私授权（`trains on request data`） | **【实例 A】** | 去 OpenCode Console 的 workspace Privacy 里允许「付费且训练数据的端点」 |

> **通用做法**：400 先分清是「协议用错」还是「请求体里有上游不认的字段」。
> 前者改 provider 归属，后者改 `optionSpecs.reasoningLevel.map`。
> 供应商特有错误码只影响「是哪一类」的判断，不影响这两条解法。

---

<a id="model-503"></a>

## 3. 某个模型 503 【实例 B】

**现象**：某个 global 模型 503，报 `not allowed for user type`。

> **适用范围**：账号类型限制是 **WorkBuddy2API 网关**特有的 —— 它的账号池里
> 混了不同类型的号，类型不够格就 503。别的供应商若也按账号类型分档，症状类似。

**排查**

```bash
# 1) 看网关账号池的 realm 与类型
curl -s http://127.0.0.1:7863/status | python -m json.tool | head -60

# 2) 看被拒的模型在不在探测缓存里，状态是什么
python -c "import json; d=json.load(open('providers/workbuddy/cache/wb_zcode_probe.json',encoding='utf-8')); [print(k,v.get('status'),v.get('detail')) for k,v in d.items() if v.get('status')!='ok']"
```

**原因 / 解法**（均为**【实例 B】**）

| 原因 | 解法 |
|---|---|
| **账号类型不允许** —— 3 个 global 号是 `personal_free_user`，多数 global 高端模型上游直接拒 | **改配置没用**。唯一路径是换非该类型的账号。见 [MODEL-PROVIDERS.md](MODEL-PROVIDERS.md) §4.7 |
| 模型被网关锁（`model_locks`） | 查 `/status` 的 `model_locks`，等解锁日期 |
| 上游真的不可用（`11102 model not available`） | 换一个，或等上游恢复 |
| 池里没有健康账号（`no_healthy_account`） | 见第 4 条（打爆账号池） |

---

<a id="probe-protocol-unsupported"></a>

## 4. 探测脚本报协议不支持 【通用】

**现象**：探针输出里大量 `ModelProtocolUnsupported`，或者脚本判定「三种协议都跑不通」。

> **适用范围**：机制是通用的 —— 上游按协议挑模型，探针逐个协议试，
> 于是「大部分模型报不支持」是**正常结果**不是故障。
> 探针的实现与脚本路径是本仓两个实例的（实例 A 的三协议探针、实例 B 的单协议探针）。

**排查**

```bash
# 1) 看探测结果原始数据
python -c "import json; d=json.load(open('providers/opencode-go/probe/results/20261019/probe_results.json',encoding='utf-8')); [print(k, v.get('status'), (v.get('err') or '')[:80]) for k,v in d.items() if v.get('status')!=200]"

# 2) WorkBuddy 侧：看探测缓存的状态分布
python -c "import json,collections; d=json.load(open('providers/workbuddy/cache/wb_zcode_probe.json',encoding='utf-8')); print(collections.Counter(v.get('status') for v in d.values()))"
```

**原因 / 解法**

| 原因 | 适用范围 | 解法 |
|---|---|---|
| **这不是故障** —— 探针就是在告诉你这个模型不走这个协议 | **【通用】** | 按 [MODEL-PROVIDERS.md](MODEL-PROVIDERS.md) §2.8 的协议表放 |
| 401（凭据 / 隐私授权） | **【通用】** | 脚本解决不了；先修凭据或 Console 权限 |
| 429 | **【通用】** | 日配额耗尽，见第 8 条 |
| `no_healthy_account` | **【实例 B】** | **探测间隔太短，把账号池打爆了** —— 用 `--sleep 20` 重跑（脚本支持断点续跑） |
| 429 / `no_healthy_account` 伴随**网关进程消失** | **【实例 B】** | 网关被打崩了，重启 `wb2api` 后再跑；**先确认 `/status` 可达** |
| `400 model_unavailable` + `upstream: 6004 model rate limit` | **【实例 B】** | 该模型的**全部账号**在冷却（模型级限流，不是账号池被打爆）。带 `fallbacks` 的显示名会自动改走备用区域（如 `global:` → `cn:`）；没有 fallback 的模型只能等，`gateway_hint` 里有最早解封时间 |

---

<a id="pricing-stale"></a>

## 5. 价格表过期 【通用机制 + 实例 B 的取数】

**现象**：模型清单看着对，实际花的积分比预期多；或者限时免费到期后倍率没变。

> **适用范围**：**机制通用** —— 任何供应商的目录接口都会变（涨价、促销到期、模型下架），
> 缓存下来的价格表一定会过期。**下面命令是实例 B 的**；
> 别的供应商换自己的目录接口与价格表路径即可（通用做法见
> [MAINTENANCE.md](MAINTENANCE.md) §1.1）。

**排查**

```bash
# 1) 看当前价格表里各模型的生效倍率
python -c "import json; d=json.load(open('providers/workbuddy/cache/wb_pricing.json',encoding='utf-8')); [print('%-32s list=%-6s eff=%s' % (m['id'], m.get('list_rate'), m.get('eff_rate'))) for m in sorted(d, key=lambda x: x.get('eff_rate') if x.get('eff_rate') is not None else 999)]"

# 2) 对比网关当前返回的倍率
curl -s http://127.0.0.1:7863/panel/api/models -H "Authorization: Bearer $WB_GATEWAY_KEY" | python -m json.tool | head -40
```

**原因 / 解法**

| 原因 | 解法 |
|---|---|
| 价格表**忘了刷新** | 跑 `providers/workbuddy/workbuddy_fetch_pricing.py`（`--dry-run` 先看差异）；别的供应商照 [MAINTENANCE.md](MAINTENANCE.md) §1.1 的通用做法用自己的取数脚本 |
| 限时免费到期（网关日志：`free tier ended, now 0.227 credits/1k`） | 统一模式重跑 `workbuddy_zcode_sync.py --apply`；分离模式重排四档 |
| 网关未重启时 `/panel/api/models` 只返回 34 个 global 模型 | 重启网关再取 |

---

<a id="config-overwritten"></a>

## 6. 同步后配置被覆盖 【通用】

**现象**：脚本写完是对的，几分钟后模型或 provider 没了 / 顺序变了。

**排查**

```bash
# 1) 看备份链，确认脚本写过了、之后又被改过
ls -lt ~/.zcode/v2/provider_config.json*

# 2) 对比备份内容，看是哪一版丢了什么
python -c "
import json,os,glob
p=os.path.expanduser('~/.zcode/v2/provider_config.json')
b=sorted(glob.glob(p+'.bak-*'), key=os.path.getmtime)[-1:]
for f in [p]+b:
    c=json.load(open(f,encoding='utf-8'))
    r=c['config']['providerConfigRules']; rs=r['providerRules'] if isinstance(r,dict) else r
    print(os.path.basename(f), [(x['providerId'], len(x['config'].get('personalModelIds',[]))) for x in rs])
"
```

**原因 / 解法**

| 原因 | 适用范围 | 解法 |
|---|---|---|
| **ZCode 界面保存时整份写回** | **【通用】** | 写配置期间不要在界面里改；重新跑脚本 |
| `workbuddy_zcode_sync.py` 默认**合并**到五个 OpenCode chat 组；`--separate` 才整条替换四个 `workbuddy-*` provider | **【实例 B】** | 统一模式只动 WorkBuddy 模型与五个 chat 组的 `baseUrl`；分离模式会冲掉 `workbuddy-*` 上手工加的模型 —— 加完要重跑脚本，别手改配置 |
| `go_model_sync.py` 把新模型追加到**组尾**，打乱了手工排的顺序 | **【实例 A】** | 组内顺序由脚本按版本号倒序排；要固定顺序就改脚本后重跑 |
| 别的脚本 / 别的会话也在写同一份配置 | **【通用】** | 同一时间只跑一个写入者 |

> **通用做法**：同步脚本对 provider 的写入策略各不相同 ——
> 有的**整条替换**（自己管的 provider 上你手工加的模型会被冲掉），
> 有的**只追加**（组内顺序会被打乱）。写自己的同步脚本时，
> **先想清楚「整条替换」还是「只追加」**，并在报错文案里说清楚。

回退方式见 [MAINTENANCE.md](MAINTENANCE.md) §4。

---

<a id="proxy-port-in-use"></a>

## 7. 代理端口被占用 【实例 A】

**现象**：`node opencode-header-proxy.js` 起不来，报 `EADDRINUSE`。

**排查**

```bash
# Windows
netstat -ano | grep 8787
tasklist | grep <PID>

# Git Bash / 通用
lsof -i :8787
```

**原因 / 解法**

| 原因 | 解法 |
|---|---|
| 上一次没退干净，进程还在跑 | `taskkill //PID <PID> //F`（Git Bash 里 `//` 转义） |
| 端口被别的程序占了 | 换端口：`node opencode-header-proxy.js --port 8788`，客户端 Base URL 跟着改 |
| 想同时开两个实例 | 用不同 `--port` 与 `--session` |

> 顺带：客户端 Base URL 填 `http://127.0.0.1:<port>/v1` 即可，
> 代理会把 `/v1` 或 `/zen/go/v1` 两种前缀都归一到上游的 `/zen/go/v1`。
> **代理不保存也不读取 API key**，key 照旧填在客户端里。

---

<a id="free-pool-429"></a>

## 8. 某个模型突然 429

**现象**：某模型开始 429，`Retry-After` 指向次日 00:00 UTC。

**排查**

```bash
# 1) 看错误里的 Retry-After
#    （ZCode 里看报错详情，或直接 curl 网关看响应头）
curl -si -X POST http://127.0.0.1:7863/v1/chat/completions \
  -H "Authorization: Bearer $WB_GATEWAY_KEY" -H "Content-Type: application/json" \
  -d '{"model":"<model-id>","messages":[{"role":"user","content":"hi"}],"max_tokens":16}' | head -20
```

**原因 / 解法**

| 原因 | 适用范围 | 解法 |
|---|---|---|
| **免费 / 促销档日配额耗尽** | **【通用】** | **等次日再试**。不是配置问题、不是模型下线 |
| 探针把 429 当成「不可用」而排除掉了 → 模型从清单消失 | **【通用】** | 重探一次就回来 |
| 真的撞上限流 | **【通用】** | 降并发、错开时段 |

> **通用做法**：429 + `Retry-After` 落在次日 00:00 UTC = **日配额耗尽**，
> 任何供应商的免费 / 促销档都可能是这个机制。此时改配置、重探、改 provider 归属都是白费力气。

---

<a id="probe-cache-missing"></a>

## 9. 探测脚本报 `wb_pricing.json missing` 【实例 B】

**现象**：`workbuddy_probe_zcode.py` 直接退出：
`wb_pricing.json missing - fetch pricing first`。

**原因 / 解法**

| 原因 | 解法 |
|---|---|
| 文件不存在 —— `.gitignore` 排除了 `/providers/workbuddy/cache/*.json`，**克隆后不会带过来** | 按网关面板手工重建（字段含义见 [MODEL-PROVIDERS.md](MODEL-PROVIDERS.md) §4），或用环境变量 `WB_PRICING_FILE` 指到别处 |
| 路径变了 | 检查 `WB_PRICING_FILE` / `WB_ZCODE_PROBE_FILE` 环境变量 |

---

<a id="node-missing"></a>

## 10. 探测脚本报 `cannot compute effective bodies` 【通用机制 + 实例 B 的脚本名】

**现象**：`warning: cannot compute effective bodies: ...`，探测结果全部按「最简 body」发。

> **适用范围**：机制是**通用**的 —— 算真实 body 依赖 Node.js 与 ZCode 内置规则文件，
> 拿不到就会退化成裸 body（结果不可信）。脚本名与目录依赖是实例 B 的。

**原因 / 解法**

| 原因 | 适用范围 | 解法 |
|---|---|---|
| 没装 Node.js | **【通用】** | 装 Node.js 并保证 `node` 在 PATH 里 |
| `zcode_effective_body.js` 不在 `workbuddy_probe_zcode.py` 同目录（**硬依赖**） | **【实例 B】** | 把两个文件放同一目录 |
| 找不到 ZCode 内置规则文件 | **【通用】** | 设 `ZCODE_BUILTIN` 指向 `.../ZCode/resources/config/provider/zcode-builtin.json` |
| 规则文件 JSON 坏了 | **【通用】** | 修好它；脚本会退化成发裸 body，结果**不可信**（见 [PITFALLS.md](PITFALLS.md) §2） |

---

<a id="gateway-lifecycle"></a>

## 11. 网关 / 统一入口没起来 【实例 B】

**现象**：WorkBuddy 模型连不上 `127.0.0.1:7863`，或三组（主力 / 免费 / 省钱）统一入口连不上 `127.0.0.1:7871`；
开机后 zgate 没生效；或者 Qoder 上游没在跑。

**排查**

```bash
# 1) 一次看全：服务是否在跑 / 子进程状态 / 端口 / 凭据有无
gateways/zgate/zgate.exe status

# 2) 看 zgate 日志（每个请求一行、子进程起停、错误；UTF-8）
python -c "import os; p=os.path.join(os.environ['LOCALAPPDATA'],'ZCodeGateway','zgate.log'); print(open(p,encoding='utf-8').read()[-3000:])"

# 3) 看开机自启在不在（现行是两个计划任务，不再是 Startup 快捷方式）
schtasks /query /tn "ModelBus-zgate-hidden" /fo LIST; schtasks /query /tn "ModelBus-zgate-watchdog" /fo LIST
```

**原因 / 解法**（均为**【实例 B】**）

| 原因 | 解法 |
|---|---|
| zgate 没在跑（没装自启 / 被杀） | 前台 `gateways/zgate/zgate.exe serve` 看报错；再跑 `tools/zgate-lifecycle/install-lifecycle.ps1` 校正两个计划任务，或 `schtasks /run /tn "ModelBus-zgate-hidden"` 立即拉起（`zgate.exe install` 只管旧的启动文件夹快捷方式，正常不跑） |
| 7871 被别的进程占着 | `zgate.exe serve` 会明确报「监听失败」；用 `netstat -ano \| findstr 7871` 找出占用者 |
| 配置路径不对（`gateways/zgate/zgate.json`） | `zgate.exe status` 第一段会打印实际读到的配置、alias map 与日志路径 |
| WorkBuddy 冷启动失败 | 看 `%LOCALAPPDATA%\ZCodeGateway\workbuddy.stderr.log`；确认 `gateways/upstream/workbuddy/wb2api.exe` 与 `config.json` 存在（clone 整目录被 `.gitignore` 排除，**克隆后不会自带**，重建见 [MAINTENANCE.md](MAINTENANCE.md) §8.4） |
| Qoder 冷启动失败 | 看 `%LOCALAPPDATA%\ZCodeGateway\qoder.stderr.log`；确认 `python` 在 PATH、`gateways/upstream/qoder/` 完整 |
| 端口被占但健康检查不通 | zgate 会拒绝重复启动并报「端口被占用且健康检查不通」；先清掉占用进程 |
| 子进程老是退出 | 默认 `ondemand` 模式下 WB 空闲 15 分钟会被回收，这是正常行为；不是「挂了」 |
| `status` 的 Provider 段显示 key 缺失 | 四组没指向 7871，或 provider 里没有 apiKey：重跑 `python tools/model_alias.py --slot auto --apply`，或检查 `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` |
| 想彻底回到手动 | `zgate.exe uninstall` 移除自启；网关仍可用 `gateways/upstream/workbuddy/run.bat`、Qoder 用 `start-qoder-proxy.bat` 单独起 |

> zgate 常驻（约 19 MB），不跟随 ZCode 起停：它自己按策略管 2 个子进程
> （workbuddy / qoder，均 `ondemand` + `windows` 定时窗口兜底）。ZCode 最小化到托盘不影响任何进程，
> 这是预期行为。生命周期设计与配置项见 [MAINTENANCE.md](MAINTENANCE.md) §8。

---

## 12. 所有 chat 模型 502 / 连不上 127.0.0.1:7871 【实例 B】

**现象**：ZCode 里主力 / 免费 / 低耗 / 高耗 / 备用的模型都报 502 或 connection refused；
对话 / 响应正常（这两个组直连 OpenCode-Go，不经过统一入口）。

**排查**

```bash
# 1) 路由健康检查（只返回 key 是否存在，不返回值）
curl -sS http://127.0.0.1:7871/health

# 2) 看服务与子进程状态
gateways/zgate/zgate.exe status

# 3) 看日志
python -c "import os; p=os.path.join(os.environ['LOCALAPPDATA'],'ZCodeGateway','zgate.log'); print(open(p,encoding='utf-8',errors='replace').read()[-3000:])"
```

**原因 / 解法**（均为**【实例 B】**）

| 原因 | 解法 |
|---|---|
| 入口没起 | `gateways/zgate/zgate.exe serve` 前台启动排错，或 `zgate.exe install` 重建自启 |
| 7871 被别的进程占用 | `Get-NetTCPConnection -LocalPort 7871`；换 `ZGATE_LISTEN` 后同步改四组的 `baseUrl` |
| 缺 OpenCode key | 设置 `OPENCODE_GO_KEY`，或检查 `provider_config.json` 里 OpenCode provider 的 `access.apiKey` |
| 缺 WorkBuddy key | 设置 `WB_GATEWAY_KEY`，或检查 `gateways/upstream/workbuddy/config.json` 的 `api_key` |
| 只有 WorkBuddy 模型 502 | 网关没起 / 没就绪；看 `gateway.stderr.log` |
| 对话 / 响应正常，chat 全挂 | 就是路由问题；这两组不经过路由，所以能正常工作 |

> `/health` 返回的 `key` 是布尔值（是否读到 key），**不会返回 key 本身**。
> 路由只监听 `127.0.0.1`，不要改成 `0.0.0.0`。

---

## 13. 每日自动收录的体检刷出一片 400 / 403 【通用机制 + 实例 B 的误报】

**现象**：跑完 `go_model_sync.py` 或每日自动收录任务，输出里「已配置模型体检」
一片异常，例如 `cn:hy3 探测异常: error (HTTP 400)`、`gpt-6-luna 探测异常:
error (HTTP 403)`，但同步本身「建议收录 0 个、配置未改动」，模型在 ZCode 里
也用得好好的。

**排查**

```bash
# 1) 分清「真坏」和「探错上游」：WorkBuddy 模型（cn:* / global:*）走本机统一路由，
#    不该拿 OpenCode-Go 的公共 API 去探
curl -sS -X POST http://127.0.0.1:7871/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(python -c "import json,pathlib;print(next(r['config']['access']['apiKey'] for r in json.loads((pathlib.Path.home()/'.zcode/v2/provider_config.json').read_text(encoding='utf-8'))['config']['providerConfigRules']['providerRules'] if r['providerId']=='opencode-go-chat-free'))")" \
  -d '{"model":"cn:hy3","messages":[{"role":"user","content":"hi"}],"max_tokens":16}'

# 2) 403 地区限制类：先查代理侧（本仓的代理在 OpenWrt 上，见下方「原因」）
# 3) 402 / 400 Unsupported model：直接复现，看上游原话
python -c "import json,pathlib,urllib.request,urllib.error; ..."   # 复刻探针请求
```

**原因 / 解法**

| 现象 | 原因 | 解法 |
|---|---|---|
| 18 个 `cn:*` / `global:*` 全部 400 `Model is unavailable` | **误报**：`go_model_sync.py` 的体检固定探 OpenCode-Go 的公共 API（`https://opencode.ai/zen/go/v1`），而这些模型在统一路由并组后由本机网关供给，OpenCode-Go 那边本来就没有 | 体检要按模型 id 前缀分流上游；在脚本改好前，**这 18 条不用管**，WorkBuddy 侧的真实状态看 `workbuddy_probe_zcode.py` 的结果 |
| `beam-free` / `gpt-6-luna` / `gpt-5.6-luna` / `muse-spark-*` 403 `RegionError` | 出口 IP 落在不支持的地区。**本仓的出网代理在 OpenWrt 上（ShellCrash 透明代理），本机没有系统代理** | **2026-11-03 起体检自带机场复测**：直连 403 → 自动用 `AIRPORT_PROXY`（`10.0.0.1:7896`）再探一次，通过就保留并在报告里标 `⇄` / `[经机场]`；只有机场也不通才判「上游不可用」移除（[PITFALLS.md](PITFALLS.md) §35）。若两个出口都 403，再去查 OpenWrt 侧的 ShellCrash 规则 / 节点；**不要**在任务里加「先开梯子」这类前置条件 |
| `mimo-v2.5-pro` 400 `Unsupported model` | 上游已下架该模型，与网络无关 | 无需手动处理：`go_model_sync.py --apply` 按「跑不通即清」直接移除，复通后自动加回 |
| `longcat-2.0` / `longcat-2.5-preview-free` 402 `Endpoint is unavailable` | 上游端点不可用，与网络无关 | 同上：自动移除，等上游恢复后自动加回 |
| `cn:hy4-preview-f` / `global:hy4-preview-f` 没被收录 | **已修**：`rate_of` 原先只看原始 `credits`（免费条目为空串）→ 判成 `None` → 按「无公布倍率」排除 | 现改为优先用归一化的 `eff_rate` / `list_rate`，两个免费 `-f` 已进免代档（见 [MAINTENANCE.md](MAINTENANCE.md) §7 待办 7） |
| `cn:deepseek-v4.1-flash` 503 `no_healthy_account` | 账号池里唯一那个 CN 账号上，该模型被 **6004 模型频率限制**锁住 | 查 `curl -sS http://127.0.0.1:7863/status` 的 `model_locks`（含 `unlock_at`），到点自愈；`global:` 同款通常正常 |

> 代理位置：本仓的出网代理在 **OpenWrt 路由器上**（ShellCrash 透明代理），
> 本机系统代理是关的、也没有代理客户端。所以「地区限制」类报错一律先查路由器侧，
> 详见 [SECRETS.md](SECRETS.md) 与 [PITFALLS.md](PITFALLS.md)。

---

## 14. Qoder（qoder2api-hub，8790）【实例 C】

先分三层确认：服务活着、账号可用、模型写进 ZCode。

```bash
curl -s http://127.0.0.1:8790/ping
curl -s http://127.0.0.1:8790/health        # accounts / api_key_required / risk.queue
python providers/qoder/qoder_zcode_sync.py            # dry run：模型清单与 provider 计划
```

| 现象 | 怎么查 | 原因 / 解法 |
|---|---|---|
| ZCode 里没有 `qoder:` 模型 | `ListModels`；看五个 chat 组里是否有 `qoder:` 前缀的 model id + model rule；`curl http://127.0.0.1:7871/health` 的 `qoder.key`；8790 `/v1/models` 是否可达 | 同步没写，或被 ZCode 界面整份写回覆盖。重跑 `qoder_zcode_sync.py --apply`，不要与界面同时保存 |
| 请求 401 | `providers/qoder/.env.local` 的 `QD_API_KEY` 与 `gateways/upstream/qoder/accounts/settings.json` 是否一致；`--separate` 模式再看 provider_config 里的 `qoder` apiKey | 合并模式 key 只在 `.env.local` / 7871 路由；三处不一致时轮换后一起改，再重启 hub 与路由 |
| 7871 `/health` 里 `qoder.key=false` 或 `qoder:` 请求 502 `Qoder key not configured` | 路由启动时没读到 `QD_API_KEY` | 确认 `providers/qoder/.env.local` 存在且可读，然后重启路由（zgate 会自动拉起） |
| 502 / `10605` / `isQueued` | `/health` 的 `risk.queue`；`providers/qoder/qoder_probe.json` 的状态 | 上游排队，不是本地故障。免费 `Qwen3.8-Flash` 最容易中，`DeepSeek-Flash` 也会（64s 后 200，或 90s+ 后 502）。`--probe-file` 只看 `ever_ok`：曾 200 的模型遇排队仍保留，只有从未成功过的才会被排除 |
| 400 `invalid JSON body` | 请求体是否由 GBK shell 拼接、含中文 | 本地编码问题，不是网关。用 Python/UTF-8 或 UTF-8 文件发请求 |
| 8790 没监听 / 看板打不开 | `netstat -ano | findstr 8790`；`qoder-proxy.log` / `qoder-proxy.err.log` | `start-qoder-proxy.bat`；端口冲突则换端口并同步 `qoder` provider 的 `baseUrl` |
| 签到没加积分 | `accounts/scheduler/state.json` 的日志；看板签到记录 | 已签到是幂等；CN 活动可能未下发；国际版按设备去重。本机 2026-10-23 CN 已 +100 |
| OAuth 一直 `pending` | 浏览器是否完成授权；`state` 是否过期 | 重新 `POST /accounts/login/start`，15 分钟内完成授权 |

完整操作与边界见 [QODER.md](QODER.md)。

---

## 15. 统一命名 / alias map / 协议桥 【实例 C】

| 现象 | 怎么查 | 原因 / 解法 |
|---|---|---|
| 模型名变成 `WB:` / `OC:` / `QD:` | 四个 provider 的 `personalModelIds`；`~/.zcode/v2/model-alias-map.json` 的条数；`GET 7871/health` 的 `alias.models` | 正常；由 `tools/model_alias.py` 生成。名字不对就重跑它 |
| `OC:MiniMax-M3` / `OC:Beam` 400 `thinking` | `node providers/workbuddy/zcode_effective_body.js --provider-id <pid> <model>` 的 body 是否只剩 `max_completion_tokens` | 这两类模型需要空 map；`model_alias.py` 会从旧规则复制，丢了就重跑 |
| 桥接模型 502 `bridge upstream error` | 7871 日志；OC key；请求头是否有 `x-opencode-session` / 正常 UA | 桥接器已带 `opencode-cli/1.0` + `unified-bridge`；检查 OpenCode key |
| 旧 ID（`cn:` / `qoder:` / bare OC）还能用 | alias map 的 `legacy` | 正常，老会话兼容；价格变化时旧显示名也会进 legacy |
| WB GB 模型 503 `no_healthy_account` | `curl 127.0.0.1:7863/status` 的账号池 | 池冷却，按瞬时限流处理，不删模型 |
| 调价后模型名变了 | alias map 的 `legacy` | 预期：积分写进显示名；老会话仍可路由 |

---

## 16. 开机弹 cmd 控制台窗口（zgate 不是无窗版）【实例 B】

**现象**：登录后弹出一个 cmd 控制台窗口，标题是快捷方式名「ModelBus zgate」；
关掉它网关就死，四个 chat 组全 502。

**排查**

```bash
# 1) 直接读 PE 头，看 Subsystem 是 2（GUI 无窗）还是 3（CONSOLE 控制台）
python gateways/zgate/build.py --check

# 2) 看这个窗口是不是 zgate 带来的
Get-CimInstance Win32_Process -Filter "Name='zgate.exe'" | Select ProcessId,ParentProcessId,CommandLine

# 3) 看是不是编译期被覆盖过（看 exe 修改时间 vs 提交时间）
ls -la gateways/zgate/zgate.exe
```

**原因 / 解法**（均为**【实例 B】**）

| 原因 | 解法 |
|---|---|
| 产物是控制台程序（`Subsystem = 3`） | 在 `gateways/zgate/` 里裸跑过 `go build .`（单包模式会原地覆盖产物）。用 `python gateways/zgate/build.py` 重编，它带 `-H windowsgui` 并强制校验 PE 子系统 |
| 产物是控制台程序，但 exe 正被占用改不动 | zgate 在运行时 Windows 会锁住文件。先停掉（zgate 没有 `stop` 子命令）：`Stop-Process -Id <pid> -Force`；再重编、再起 |
| 快捷方式 `WindowStyle = 7` 没用 | 「最小化」只对有窗口的程序有效，对控制台子系统程序**不等于隐藏**。而且实测那个窗口既没最小化、也是可见的 —— 唯一解法是让产物本身是 GUI 子系统 |
| 想确认没有别的控制台窗口 | `Get-Process conhost | Where-Object { $_.MainWindowTitle }`；无输出即没有 |
| 窗口没了但服务也没了 | zgate 被 agent 会话结束时连带清掉了（进程树回收）。要让 Task Scheduler 当父进程才活得下来：`schtasks /run /tn "ModelBus-zgate-hidden"`，或等看门狗（PT1M）自动拉回；会话里直接 `Start-Process zgate.exe` 会被回收 |

> 机制解释见 [PITFALLS.md](PITFALLS.md) §20；构建命令与脚本见
> [MAINTENANCE.md](MAINTENANCE.md) §8.1。

### 16.1 终端里起的 zgate 随窗口关闭而死

**现象**：在 cmd / Windows Terminal 里敲 `zgate serve`（或双击 exe），网关跑起来；一关那个窗口，三组统一入口立刻全 502，`/health` 拒连。

**原因**：`zgate serve` 是前台进程，控制台窗口关闭会给窗口内所有进程发 `CTRL_CLOSE_EVENT`；子进程（wb2api 等）挂在 zgate 的 Job Object 上一起走。这不是 bug，是前台进程的正常语义 —— 要让网关活过终端，就得让终端不是它的父。

**解法**（0.3.0 起）

```cmd
:: 后台起，立刻返回；关掉这个窗口不影响网关
zgate.exe serve -tray
```

- `serve -tray` 用 `DETACHED_PROCESS` 拉一个**无父进程**的副本：副本没有控制台，收不到关窗事件；拉起方退出后副本照常服务。
- 拉起方通过环境变量把自身 PID 传给副本，副本每 2 秒查一次：拉起它的进程消失就自己退出，不留孤儿占端口。日志里是 `拉起方 <pid> 已退出，后台副本随之停止`。
- 前台 `zgate serve` 现在打完启动横幅就 `FreeConsole` 解放控制台，避免留下半死的 `conhost`；输出仍写日志文件，重定向（`zgate status > out.txt`）不受影响。
- **2026-11-09 起的现行自启不是快捷方式、也不是 `serve -tray`**：两个计划任务
  `\ModelBus-zgate-hidden`（AtLogOn，Interactive/Limited → `wscript //B //Nologo launch-zgate.vbs`
  → `start-zgate-nw.ps1` 起普通 `serve`）与 `\ModelBus-zgate-watchdog`（PT1M → `ensure-zgate.vbs`
  → `ensure-zgate.ps1`）。`zgate install` / `uninstall` 只管旧的启动文件夹快捷方式，正常情况下不跑。
  `swap-zgate.ps1` / `start-zgate.bat` 已改为兼容薄包装转交计划任务，**不再用 `Start-Process`**。
  旧的 `\ModelBus-zgate` 任务、HKCU Run daemon、Startup 快捷方式均已移除。

**验证**

```cmd
zgate.exe serve -tray
:: 应有一行「已在后台启动: <exe> (pid N, ready=true)；停止: Stop-Process -Id N」
curl http://127.0.0.1:7871/health
:: 关掉这个窗口再开一个：/health 仍 200
```

**注意**：`DETACHED_PROCESS` 只表示「不共享控制台」，不保证**调用方整棵进程树被回收**时仍存活（`cmd /c`、`Start-Process` 结束后会连带带走，已实测）。要彻底解耦，用计划任务启动 —— 自启走的就是这条路。

### 16.2 改完 Go 代码怎么自动换版

**现象**：改了 `gateways/zgate/` 下的 Go 代码，`POST /admin/reload` 之后新逻辑没生效。

**原因**：`/admin/reload` 热加载 `zgate.json` 的策略 / 空闲阈值 / 定时窗口 / 上游 base / 凭据
（`gateways/zgate/internal/router/router.go:963-986`：`config.Load` + `keys.Load` 六通道 + `ApplyConfig(children)` + `setRuntime` + `aliases.Reload()`），不替换二进制；
监听地址 / 新增子进程 / alias map 路径与 Go 代码变更必须换 `zgate.exe` 并重启实例。

**解法**：agent 改完 Go 代码后自动执行 `tools/zgate-lifecycle/restart-zgate.cmd`（CMD 入口，
转交 `deploy-zgate.ps1`）：`build.py --candidate` 编到 `zgate.candidate.exe`（不覆盖运行中的 exe）
→ 暂停 watchdog → `Stop-Process zgate` → 备份 → 替换 → `schtasks /run /tn ModelBus-zgate-hidden`
→ `/health` 轮询 → 恢复 watchdog → 失败自动回滚。全过程不需要用户手动重启。

**注意**：严禁在会话里用 `Start-Process` / `cmd /c` 直接拉起 zgate —— 它们落在 CMD/DSH 会话的
Job Object 里，会话结束整棵进程树被回收（实测 2s 内子进程消失）。机制与完整流程见
[ZGATE-LIFECYCLE.md](ZGATE-LIFECYCLE.md)。

---

## 17. Iceman 看不到思考、输出一节一节出 【实例 A】

**现象**：开了思考强度，`Iceman` 界面仍完全看不到思考，正文一段一段拖出来；直连网关有时又能看到思考。

**排查步骤**：

1. 看探针 `ENC` 列：`python tools/model_stream_check.py --model Iceman --no-heal`；`THINK=0` 且 `ENC>0` = 上游加密分流，不是模型故障。
2. 看展示配置（**只读，不改**）：`~/.dsh/profiles/<profile>/cordis.patch.yml` 的 `ui-chat` 现值、`ui-skin-claude-style` 有没有 `reasoningDisplay`。`ui-chat` 三键（`transcriptView / collapseTiming / foldedReplies`）是用户偏好，用户要的是 `compact / completion / final`，排查时**不许**改成 `verbose / next-input / all` —— 一改用户就以为配置自己回退，见 [PITFALLS.md](PITFALLS.md) §41-①。
3. 看网关守卫是否真生效：`zgate.json` 有 `reasoningGuard` 不等于二进制有新代码 —— 改过 Go 就必须换 `zgate.exe`（§16.2），`/admin/reload` 只热加载配置。守卫日志这几行就能定性：
   - `上游返回加密思考分流…换连接+换会话重抽 1/5`：探针判定成功，正在重抽（行里带上游模型名，一眼能看出是哪个模型被判成加密分流）；
   - 下一行 `连续 N 次加密思考，达上限放行最后一次` 之后的流首出现 `ⓘ 上游本次只下发加密思考`：上游这一段窗口全在加密后端，属上游行为；
   - `模型 "iceman-contributor-free" 1s 内没有可判定的思考信号（上游静默），换连接+换会话重抽 1/1`：探针到 `probeSeconds` 还没信号，正在换连接重抽（加密那一路思考阶段整段静默，只有第一块正文才判得出来，所以必须设时限）；
   - `连续 N 次探测超时（上游思考阶段静默），放行上游原始流` / `在「近期拿不到明文思考」跳过期内，直接放行（不再探测）`：这轮不再探测，客户端直接拿到上游原始流 + 一条提示（`ⓘ 本次思考探测超时…` 或 `ⓘ 该模型近期思考拿不到明文…`），正文照常输出；
   - 完全没有这两行：要么模型没声明思考（`reasoning_effort` 空 / `off`），要么二进制是旧的（老版本日志写的是「透明重抽同一跳」）。
4. 采样确认：同一请求连打 10 轮，A / B 与参数无关即上游分流，不要再调 `thinking` / `reasoning_effort`（8 类参数 ×5 轮已证无效）。
5. **客户端 200 但 0 字节 / 流被掐断**：看网关日志有没有 `wrote more than the declared Content-Length`，有就是上游 SSE 自带 CL 而守卫改了长度 —— 现代码对事件流一律摘 CL 走 chunked，仍复现说明二进制是旧的。
6. **守卫一次都没触发**（日志里只有 `POST … model=Iceman`，没有重抽行）：先看宿主真实请求体有没有 `reasoning_effort` —— 会话 `session.v4.jsonl.zstd` 的 `request/header` 里 `"config"` 只有 provider/model/maxTokens 就是没有。守卫的触发条件是「客户端声明要思考」，DSH 的 "Default" 伪档位不声明，于是守卫连上场机会都没有。现网关注解：`zgate.json` 的 `reasoningGuard.forceEffort: "high"` + `forceEffortModels` 让网关替客户端补档（日志 `客户端未声明思考档位，按配置补 reasoning_effort="high"`）；补档后守卫才会接管加密分流。显式关思考（`off`）不受影响。
7. **每个请求都要先空等十几秒才出字**：正常流被 `probeSeconds` 误判成静默了。看日志有没有 `内没有可判定的思考信号（上游静默）` —— 有就说明探针没等到首块。先量正常流的首字节耗时（`tools/model_stream_check.py` 的 TTFB），把 `reasoningGuard.probeSeconds` 调到明显大于它（现配置 15，明文实测最高 13.5 秒）；窗口期把 `maxRetries` 调大的做法无效，重抽几乎必然落回同一后端，只会让用户多等。想完全关掉这套探测就把 `probeSeconds` 设负数并把 `maxRetries` 设 0。
8. **新模型也这样怎么办**：不用改 `models` 白名单，`mode: "auto"` 已覆盖「客户端声明要思考」的所有流式请求；真要停手只把 `giveUpAfter` / `giveUpForSeconds` 调小调大。适配规则见 [PITFALLS.md](PITFALLS.md) §41「同类模型免配置适配」与 [MODEL-STREAM.md](MODEL-STREAM.md) §10。

**原因 / 解法**：根因与三层避法以 [PITFALLS.md](PITFALLS.md) §41 为正本；探针口径见 [MODEL-STREAM.md](MODEL-STREAM.md) §3。展示层只动 `reasoningDisplay`（刷新 GUI 即生效），`ui-chat` 折叠三键属于用户偏好，不动；

---

## 18. 某个模型一分钟没有任何输出，反代面板也没有记录 【通用】

**现象**：选 `Gemini-AIS` 发一句话，客户端一分钟零字节（最后手动点「停止」）；上游反代后台**一条请求记录都没有**；同一时刻别的模型（DeepSeek 系）一切正常。

> **口径更新（2026-11-10 22:27）**：`Gemini-AIS` 现在是 **7 跳全 GM** 链，哈基米福利 3.8 已拆成独立模型
> `Gemini-3.8-Flash`（单跳 `HJ`）。本节及 §18.1-§18.3 里出现的 `(x/8)` 与 HJ 跳都是当晚的历史日志，
> 排障时按 `(x/7)` 对照，别把「链里没有 HJ」当成回归。见 [MODEL-PROVIDERS.md](MODEL-PROVIDERS.md) §4.11.5。


**一句话结论**：降级链上多了一个新渠道，运行中的 `zgate.exe` 内存里没有对应的 `channelPolicy` → 整条链静默退回串行 → 首跳把连接挂住却不给响应头，而串行链没有首块超时，于是两头都静默。

**排查步骤**：

1. **看日志尾部是不是「只有派发行、没有后续」**：

   ```bash
   tail -80 "$LOCALAPPDATA/ZCodeGateway/zgate.log" | grep -E "model=Gemini-AIS|\[race\]"
   ```

   只有 `POST /chat/completions model=Gemini-AIS -> GM:ais-gemini-3.8-flash (1/8)`、完全没有 `[race] 发出 1/8` → 走的是串行链，竞速根本没上场（`[race] 发出` 是在起 goroutine 之前打印的，没有它就不是竞速）。
2. **搜那条 WARN**：`grep "不在 channelPolicy" zgate.log`。命中即坐实第 1 步的原因，处置见 [PITFALLS.md](PITFALLS.md) §42。
3. **核对二进制与配置的时序**：`/health` 的 `uptime_s` 反推进程启动时刻，与 `zgate.exe` 的 mtime、`model-alias-map.json` 的 `generated_at` 对比。进程启动早于「改链 / 加渠道」= 内存里是旧配置。也可以直接查二进制里有没有新代码：

   ```bash
   python -c "import os;s=open(os.path.expandvars(r'%LOCALAPPDATA%/ZCodeGateway/zgate.exe'),'rb').read(); print(b'hajimi' in s, b'upstream silent' in s)"
   ```

   两个都 `False` = 换版没生效。
4. **反代后台没记录本身就是证据**：反代要开始回包时才记账，请求停在「连接建好、响应头没发」这一段不会留痕；配合客户端零字节，指向的是上游首字节沉默，而不是「请求根本没发出去」。
5. **换版后复验**：`curl -s http://127.0.0.1:7871/health` 的 `segments` 里应出现 `hajimi`；再打一次目标模型，日志应有 `[race] 发出 1/8` 与最终赢家那一跳。

**原因 / 解法**：正本见 [PITFALLS.md](PITFALLS.md) §42，机制见 [MODEL-PROVIDERS.md](MODEL-PROVIDERS.md) §4.11.3 第 7 条。两件事都要做：① 换二进制（§16.2）；② 确认 `/health` 列出 `hajimi`（没列就是还在旧进程）。

### 18.1 换版之后有输出了，但一次请求仍要 3-4 分钟（2026-11-10 19:45 实测）

**现象**：换成新二进制后不再零字节，可一次请求要 3-4.5 分钟才出结果（用户实测 4 分 31 秒，期间界面只有「请求中」，反代后台同一句话出现两条记录）。

**怎么判**：`grep -E "\[race\] 发出|上游 .* 内没给响应头" zgate.log | tail -30`。若每一跳之间都稳定隔约 45 秒、且末尾是「全部 8 跳都没给出可用的首块」，就不是链路问题，是**容忍窗口太长**：那一跳其实早就该被判死了。

**根因**：同一跳 `ais-gemini-3.8-flash` 每次都要 60.241 秒才回 503 high demand（实测响应头耗时 60241ms），45 秒的响应头看门狗每次都等满；`maxParallel=2` 轮转 8 跳 = 4 轮。期间客户端等不到首字节会自动重试，所以后台看到两条。

**处置**：`zgate.json` 的 `upstreamHeaderTimeoutSec`（缺省 12，负数关闭）调到 10-15 之间，`/admin/reload` 即生效，不用重编译。12 秒对正常首头（哈基米福利跳实测 2.5-3.1 秒）有 4 倍余量，全灭时最坏 4 轮 × 12 秒 ≈ 48 秒就给出结论。

### 18.2 全体跳都沉默、几十秒后干净失败，兜底那家其实能回（2026-11-10 20:03 实测）

**现象**：一次请求在 50 秒左右干脆地失败，日志里 8 跳全部 `上游 12s 内没给响应头`，包括哈基米那一跳；可单独打哈基米却是有响应的（当晚 7.5-10.2 秒出首头），反代面板依旧一条记录都没有。

**判据**：日志里 `（channel=HJ model=[福利]gemini-3.8-flash）上游 12s 内没给响应头` —— 说明不是这条腿坏了，是**窗口卡在它抖动的边缘**。当天更早时候同一跳只要 2.5-3.1 秒，晚上漂到 7.5-10.2 秒，12 秒只剩 1.2-1.6 倍余量，赶上排队就被切。

**处置**：给渠道单独设窗口 —— `zgate.json` 的 `channelPolicy.HJ.headerTimeoutSec = 25`（GM 保持 12）。两路同时在场时 GM 到 12 秒先被判死、链继续往下走，哈基米那一路还在等它的 10 秒，谁先出首块谁赢。RPM/TPM 面板上哈基米那一栏能证明它在正常出码，只是慢。

### 18.3 换了跳却没埋跳：同一个死跳每个请求都要重新撞一遍（2026-11-10 20:20 实测）

**现象**：首块看门狗已经生效（日志里每跳 12 秒判沉默、按序换跳），但**每一次**请求都要从第一跳起手重新等一遍 —— 用户连发两句，两分钟里大部分时间都花在「撞已知死跳」上。

**判据**：日志里反复出现同一跳的 `上游 12s 内没给响应头`，而它前面从没有 `冷却中，跳过` 这行。说明换跳做了、冷却没做：`errUpstreamSilent` 分支只调 `retry()` 回落下一跳，跳的 `silence` 表一次都没写。

**处置**：沉默也埋（`router.go` 的 `doForwardWith`，命中 `errUpstreamSilent` 后按渠道 `silenceCooldownSeconds` 打 `markSilence`，GM/HJ 各 20 秒）。埋了之后日志应变成「第一轮 12 秒判沉默 → 打 `沉默，静默冷却 20s 后再试这一跳` → 下一个请求直接 `冷却中，跳过` 到哈基米」。全链都在短冷却时 `raceChain` 会清掉软冷却重试一次（`clearSilence`），不会因为冷却把自己饿成 502。

**口径**：静默冷却要短（20 秒）；它只是「这次先说别人」，不是「这跳死了」。真冷却（429 / 5xx / 额度过期）仍走 45 秒 - 24 小时那一套。

---

## 附：通用排查顺序

**换任何供应商都按这个顺序**（括号里是本仓三个实例的具体命令）：

1. **先确认服务活着**（实例 B：`curl http://127.0.0.1:7863/status`；
   实例 A：`curl https://opencode.ai/zen/go/v1/models`；
   实例 C：`curl http://127.0.0.1:8790/health`）。
2. **再看配置写没写进去**（`provider_config.json` + `.bak-*` 备份链）。
3. **再看 ZCode 真实发了什么**（`providers/workbuddy/zcode_effective_body.js`）。
4. **最后才怀疑上游** —— 大部分「上游坏了」其实是本地配置或请求体的问题。
