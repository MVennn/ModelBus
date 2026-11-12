<div align="center">

<img src="https://raw.githubusercontent.com/MVennn/ModelBus/main/assets/logo.png" width="128" alt="ModelBus">

# ModelBus

**DSH 主宿主 + 各类 agent 的模型目录与路由工具仓**

一份 `catalog/` 模型目录真源（能力字段逐条带出处），投影到 DSH 的 `cordis.patch.yml`；各类 agent 共用同一份路由策略。

![CI](https://github.com/MVennn/ModelBus/actions/workflows/ci.yml/badge.svg) ![源码仓库](https://img.shields.io/badge/源码仓库-GitHub-181717?logo=github&logoColor=white) ![问题反馈](https://img.shields.io/badge/问题反馈-Issues-181717?logo=github&logoColor=white) ![Python](https://img.shields.io/badge/Python-3-3776AB?logo=python&logoColor=white) ![Node.js](https://img.shields.io/badge/Node.js-18%2B-339933?logo=node.js&logoColor=white) ![License](https://img.shields.io/badge/License-MIT-blue)

</div>

---

## 这是什么

一个**工具仓库**，不是一个应用。它做三件事：

- **探测** —— 逐个模型试：能不能连、走哪种协议、工具调用能不能用、思考参数怎么关；
- **同步** —— 把探测结论整理成 provider 分组，按成本档 / 积分倍率写进 `catalog/` 真源，再投影到 DSH `cordis.patch.yml` 与兼容投影；
- **记录** —— 把踩过的坑、协议归属、参数矩阵固化成文档，换套餐时不用重试一遍。

**主宿主是 DSH**：`tools/dsh_sync.py` 把模型目录投影到 `~/.dsh/profiles/<profile>/cordis.patch.yml`，
DSH 会话、子代理与各类 agent 共用 `gateways/zgate` 单一入口（`127.0.0.1:7871`）；
ZCode 仍作为**兼容投影**保留，不再是中心。`tools/agent_profiles.py` 给每个 agent 提供只读投影接口。
方向、命名分层与落地批次见 [docs/DSH-FIRST.md](docs/DSH-FIRST.md)。

仓里的 `providers/opencode-go/`、`providers/workbuddy/` 与 `providers/qoder/` 是三个跑通的**完整示例**（OpenCode-Go 套餐、
WorkBuddy2API 网关、qoder2api-hub 网关）；现在统一成**三组**（主力 / 免费 / 省钱），
模型 ID 只用型号名（如 `DeepSeek-4.1-Flash`），同型号跨渠道合并成一条链路（WB 固定链首，其余按价格 / 前缀 / 渠道稳定排序），由 `tools/model_alias.py` 生成、`gateways/zgate`（Go，单进程，监听 `127.0.0.1:7871`）按 alias map 分流到 7 个 upstreams（OC / WB / QD / QW / QN / GM / HJ），并按需托管 2 个本地网关子进程（WorkBuddy `7863` / Qoder `8790`）。方法本身与供应商无关，接一个新供应商要做的四步见
[docs/MODEL-PROVIDERS.md](docs/MODEL-PROVIDERS.md) §0。

**边界**：本仓库**不含 DSH 宿主、也不含 ZCode 客户端**，只写宿主配置 —— DSH 侧 `cordis.patch.yml`、兼容投影 `provider_config.json`；
脚本只碰兼容投影里的三个位置 —— 落点与写法见
[docs/MODEL-PROVIDERS.md](docs/MODEL-PROVIDERS.md) §1。

## 环境要求

| 项 | 要求 |
|---|---|
| 主宿主 | **DSH（DeepSeekRuntime）**：读 `~/.dsh/profiles/<profile>/cordis.patch.yml`；会话 / 子代理 / 各类 agent 共用 `127.0.0.1:7871` 单一入口 |
| 兼容投影 | ZCode 桌面端（Windows，可选）：读 `~/.zcode/v2/provider_config.json` |
| 运行时 | Python 3（脚本只用标准库，例外两处：门面重生成脚本 `tools/make_social_preview.py` 需 numpy + Pillow，`tools/dsh_sync.py` 与 `tools/model_stream_check.py` 需 PyYAML）、Node.js 18+（跑探测/旧版路由）；统一入口 `gateways/zgate` 是**单个 Go 二进制**，日常运行不需要 Go（只有自行构建时需要 Go 1.22+，见 [docs/TOOLS.md](docs/TOOLS.md) §0） |
| 配置与凭据 | DSH 的 `cordis.patch.yml` + 兼容投影 `provider_config.json`（默认在 `~/.zcode/v2/`）；凭据只走环境变量，变量名与取值见 [docs/SECRETS.md](docs/SECRETS.md) |
| 网络 | 能直连你的供应商；三个 chat 组统一指向 `127.0.0.1:7871`（`zgate`），由它按需拉起 WorkBuddy 网关（`7863`）与 Qoder hub（`8790`）两个本地子进程。生命周期、自启与换版见 [docs/MAINTENANCE.md](docs/MAINTENANCE.md) §8、[docs/ZGATE-LIFECYCLE.md](docs/ZGATE-LIFECYCLE.md) |

## 使用

顺序不能乱：**先刷价格表 → 再探测 → 最后同步**。探测要慢 —— 一个模型间隔至少 20 秒，
太密会把对方的账号池打爆；同步是秒级的。

1. **准备环境变量** —— `OPENCODE_GO_KEY`（OpenCode-Go）、`WB_GATEWAY_KEY`（WorkBuddy 网关）、`QD_API_KEY`（Qoder 网关）、`QWEN_API_KEY` / `QWEN_BASE`（千问直连）、`QINIU_API_KEY`（七牛云 AI 网关）、`GEMINI_API_KEY`（GM 渠道）、`HJM_API_KEY`（HJ 渠道）—— 7 个 upstream 各读各的 keyEnv，变量名以 `gateways/zgate/internal/keys/keys.go` 为准；部分也可用 git-ignored 的 `providers/*/.env.local`（`gemini` / `hajimi` / `qwen` / `qiniu` / `qoder` 各一份）。凭据一律从环境变量读，只写变量名、不写真值，完整清单见 [docs/SECRETS.md](docs/SECRETS.md) §3.5。
2. **刷价格表** —— WorkBuddy 侧先跑 `providers/workbuddy/workbuddy_fetch_pricing.py`；
   OpenCode-Go 侧不用刷，同步脚本每次现拉目录与价格；Qoder 侧也不用刷，`qoder_sync.py` 每次现拉 `/v1/models`。
3. **探测** —— `providers/workbuddy/workbuddy_probe.py --sleep 20`、`providers/opencode-go/probe/probe_models.py`、
   `providers/qoder/qoder_probe.py`。必须按宿主生效请求体探测（`effective_body.js` 复刻的规则合并语义）：裸 body 能通不代表按宿主规则合并后能通。
4. **探测并归一化** —— 先更新主力候选（可选），再跑统一探测，最后由 `model_alias.py`
   生成三组 + alias map：

```bash
python tools/arena_leaderboard.py --refresh --write   # 可选：外部榜单 → 主力候选
python tools/model_score.py --write                   # 可选：榜单分 → 省钱组裁量依据
python tools/model_probe.py
python tools/model_alias.py --slot auto --arena --scores --probe-file ~/.zcode/v2/model_probe.json --apply
```

主力由两部分组成：人工 `MAIN_IDS` + 榜单候选（分数接近 DeepSeek 且积分 ≤ 0.11 的
已配置模型）。候选落在 `~/.zcode/v2/arena-main.json`，`model_alias.py` **带 `--arena` 才读**；
`--scores` 读 `tools/model_score.py --write` 产出的 `~/.zcode/v2/model-scores.json`，
只用来把省钱组里分数明显更低的白名单条目裁掉（只降不升）。两个文件缺失都按空处理、不报错。
榜单口径与 2026-10-23 的候选见 [docs/BENCHMARKS.md](docs/BENCHMARKS.md) §8，
性能进选型的依据见 §9。

一条命令跑完整条流水线（默认不推远端，带 `-Push` 才提交）：`powershell -NoProfile -ExecutionPolicy Bypass -File sync-models.ps1`，
Windows 计划任务 12:00 由 `sync-models.vbs` 调起。它按「Go 套餐 → WorkBuddy 倍率上限 0.3 →
Qoder → 统一命名与分组 → 同步报告」五段跑，逐段顺序与限速见
[docs/MAINTENANCE.md](docs/MAINTENANCE.md) §6。

旧的 `go_model_sync.py` / `workbuddy_sync.py` / `qoder_sync.py` 现在只作
**数据采集**；它们的旧 ID 会由 `model_alias.py` 归一化成统一的型号名。命名、
积分换算与桥接规则见
[docs/MODEL-ALIAS.md](docs/MODEL-ALIAS.md)。

`model_alias.py` 会**先备份再原子替换** `provider_config.json`；兼容投影端约 1 秒轮询该文件，DSH 侧消费 `cordis.patch.yml`，
写完一般不用重启宿主。统一入口（`gateways/zgate`）、alias map、协议桥与各脚本产物见
[docs/TOOLS.md](docs/TOOLS.md)，
命名与积分规则见
[docs/MODEL-ALIAS.md](docs/MODEL-ALIAS.md)，
日常刷新、限速与回退见
[docs/MAINTENANCE.md](docs/MAINTENANCE.md)。

## 可视化后台

控制台是**独立进程**，不塞进网关：`pwsh tools/console/start-console.ps1` 起在
`127.0.0.1:7872`（`-Port` 换端口、`-Check` 只自检不监听、`-Detach` 隐藏窗口并把输出落到 `.work/`）。

它只读汇总 13 个数据源（TTL 缓存 + 流式尾读 + 脱敏），17 条路由里唯一的写面是
`POST /api/actions/reload`，只转发 zgate 的 `POST /admin/reload` —— **不启停 zgate**。
页面清单、字段来源与验收口径见 [docs/CONSOLE.md](docs/CONSOLE.md)，启动器与产物见
[docs/TOOLS.md](docs/TOOLS.md)。

## 文档

除了上面的使用流程，深挖细节直接翻 [docs/README.md](docs/README.md)（23 篇正文按
「模型与 Provider / 流程与规范 / 排错与踩坑 / 参考资料」四类索引，每篇一句定位）。常翻的几篇：

| 想查什么 | 去哪 |
|---|---|
| 接新供应商、模型分组、命名与关思考参数 | [docs/MODEL-PROVIDERS.md](docs/MODEL-PROVIDERS.md)、[docs/MODEL-ALIAS.md](docs/MODEL-ALIAS.md) |
| 一条请求先打哪一跳、等多久、什么时候判死 | [docs/ROUTING-POLICY.md](docs/ROUTING-POLICY.md) |
| 上下文 / 输出上限 / 图片 / 工具 / 档位这些能力字段从哪来 | [docs/CAPABILITY-AUDIT.md](docs/CAPABILITY-AUDIT.md)、[docs/MODEL-STREAM.md](docs/MODEL-STREAM.md) |
| 进程、端口、目录两轴与当前架构 | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)、[docs/DSH-FIRST.md](docs/DSH-FIRST.md) |
| 脚本清单与各自产物 | [docs/TOOLS.md](docs/TOOLS.md) |
| 出问题了怎么查 / 为什么会这样 | [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)、[docs/PITFALLS.md](docs/PITFALLS.md) |
| 早期价格与实测快照（历史口径，不再更新） | [docs/MODEL-QUICK-REF.md](docs/MODEL-QUICK-REF.md) |
| 版本号、进位规则、每版改了什么 | [docs/VERSIONING.md](docs/VERSIONING.md)、[docs/release-notes/](docs/release-notes/README.md) |

## 反馈

接不上某个供应商、探测结果对不上、想要新的判定手法，都可以到
[Issues](https://github.com/MVennn/ModelBus/issues) 反馈；想参与贡献见
[CONTRIBUTING](CONTRIBUTING.md)，
安全问题按 [SECURITY](SECURITY.md) 报告。反馈时请带上：

- 跑的是哪个脚本、卡在哪一步、报错原文
- 涉及的模型与 provider、DSH profile 版本（或兼容宿主版本）
- 对应的环境变量是否已设置（**不要**把 key 贴出来）
- 探测的输出文件（`providers/workbuddy/cache/wb_pricing.json` 与 `wb_zcode_probe.json` 这类活数据快照，后者跑完探测才生成；发之前先扫一眼有没有凭据）

## 免责声明

本项目仅供学习与个人使用。

- 本仓库**不上传、不收集任何数据**；脚本只与你自己机器上的配置和你自己的模型网关交互
- 脚本会修改**你自己的**宿主配置（DSH `cordis.patch.yml` / 兼容投影 `provider_config.json`），写之前会自动备份，仍建议自己再备份一份
- 示例涉及的 `opencode.ai`、WorkBuddy2API、Qoder 与**你自行接入的其它供应商**都是**第三方服务**，
  本项目与它们不存在任何隶属、合作、授权或认可关系
- 模型价格、额度、可用性与隐私策略**一律以服务商当时的说明为准**，本仓文档只是某一时刻的快照；
  仓里的模型清单与分组按成本档 / 积分倍率排，是主观取舍，不是推荐
- 使用本项目产生的任何后果由使用者自行承担

「ZCode」「OpenCode Zen / Go」等商标、标识的权利均归其权利人所有。本项目与之不存在任何隶属、合作、授权、认可或支持关系。

## 开源鸣谢

本仓库建立在这些项目与服务之上（逐项声明见 [NOTICE](NOTICE)）：

| 项目 | 用途 |
|---|---|
| [**WorkBuddy2API Panel**](https://github.com/misakano7545/workbuddy2api-panel)（链路：`Sliverkiss/workbuddy2api` 已删库 → `linguo2625469/workbuddy2api-panel` 2026-10-21 停更 → 本仓现跟踪此分支） | 腾讯 CodeBuddy 多账号网关，WorkBuddy 侧全部请求都发给它（MIT；本仓不含其源码，只通过 HTTP 调用） |
| [**qoder2api-hub**](https://github.com/shuishuipingan/qoder2api-hub) | Qoder 账号网关，Qoder 侧全部请求都发给它（MIT；本仓不含其源码，只通过 HTTP 调用） |
| **Qoder**（qoder.com.cn / qoder.com） | Qoder 侧的模型服务与账号（商业服务） |
| **OpenCode Zen / Go**（opencode.ai） | 模型套餐与 API 网关，OpenCode-Go 侧全部请求都发给它（商业服务） |
| [**ZCode**](https://github.com/zai-org/ZCode) | 兼容投影宿主，本仓保留其配置落点并复刻其规则合并语义（Apache-2.0） |
| [**ZCodium**](https://github.com/ZCodium-project/ZCodium) | ZCode 的 MIT 授权独立审计 fork，思考规则切片的来源（MIT） |
| **Python 3** / **Node.js** | 脚本运行时 |

调研过的 14 个同类型项目，以及本仓实际复制的上游文件与来源凭证，见 [docs/UPSTREAM.md](docs/UPSTREAM.md)。

## 许可证

本项目以 [MIT License](LICENSE) 发布。第三方组件与服务的版权与条款声明见 [NOTICE](NOTICE)。
