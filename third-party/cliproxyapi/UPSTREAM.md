# router-for-me/CLIProxyAPI —— 来源凭证

> **一句话**：本目录是 CLIProxyAPI 官方 release 的 **原样二进制 + 原样示例配置**，
> 作为 ModelBus 的本地 OpenAI 兼容网关跑在 `127.0.0.1:8317`。

---

## 1. 上游

| 项 | 值 |
| --- | --- |
| 仓库 | `router-for-me/CLIProxyAPI` |
| URL | <https://github.com/router-for-me/CLIProxyAPI> |
| 许可 | **MIT**（全文见本目录 `LICENSE`，原样未改） |
| 钉住的 release | **v8.0.61**（Latest，发布 `2026-11-08T14:31:53Z`） |
| 构建 commit | `681ce41b`（二进制自报） |
| 构建时间 | `2026-11-08T14:32:51Z` |
| 资产 | `CLIProxyAPI_8.0.61_windows_amd64.zip`，25,663,680 B |
| zip sha256 | `e6dbe1337d17b993c6fa6d75d71f2e98db6ea3653af73a4217956f0c53e025b5`（与官方 `checksums.txt` 一致） |
| exe sha256 | `3088e345b4537c934b849ae6238e5478de47cf0076cb3ee88750d942f78a38b0`，77,667,840 B |

## 2. 包含哪些文件、对应上游哪个路径

| 本地文件 | 上游路径 | 性质 |
| --- | --- | --- |
| `cli-proxy-api.exe` | release 资产根目录 | **原样**（未改一个字节）；77 MB 的二进制由本目录 `.gitignore` 排除，按第 5 节重新下载 |
| `config.example.yaml` | release 资产根目录 | **原样**（v8 布局模板，1353 行） |
| `README.md` / `README_CN.md` | release 资产根目录 | **原样** |
| `LICENSE` | release 资产根目录 | **原样**（MIT 全文） |
| `config.yaml` | —— | **本仓派生**：照 `config.example.yaml` 的 v8 布局写的最小可用配置（含客户端 key，已加入本目录 `.gitignore`） |
| `cliproxy.env` | —— | **本仓派生**：同一客户端 key 的 env 形态，供客户端脚本读取（已 gitignore） |
| `auths/` | —— | **运行时产物**：`kv.db` + `logs/` + OAuth 凭证（已 gitignore） |

## 3. 本仓怎么用

1. 后台启动：`cli-proxy-api.exe -config config.yaml`（只监听 `127.0.0.1:8317`）；
2. 客户端拿 `access.api-keys` 里的 key 走 `/v1/models`、`/v1/chat/completions`（OpenAI 兼容面）；
3. 上游模型由根 `api-keys`（API key 组）或 `./auths`（OAuth 凭证）提供，二者都不配时 `/v1/models` 返回空列表 —— 这是"网关通、上游未接"的正常状态。

## 4. 8.0.61 实测到的两个事实（写死在 `config.yaml` 的注释里）

- `api-keys` 下真正会被装载的组只有 `gemini / claude / codex / xai / meta / vertex-compat / openai-compat`；
  启动摘要逐项列出这些通道，**没有 antigravity**。
- `api-keys.antigravity` 不报错也不装载（启动摘要仍 `0 clients`），**未知组名同样静默忽略** —— 所以"启动没报错"不能当作"配置生效"。
  Antigravity 的正规入口是 OAuth：`cli-proxy-api.exe -antigravity-login`，凭证落在 `oauth.auth-dir`（本目录 `./auths`）。

## 5. 怎么更新

```bash
gh release view --repo router-for-me/CLIProxyAPI --json tagName,assets   # 认版本与资产名
curl -sSL -o cliproxyapi.zip \
  https://github.com/router-for-me/CLIProxyAPI/releases/download/v8.0.61/CLIProxyAPI_8.0.61_windows_amd64.zip
curl -sSL -o checksums.txt \
  https://github.com/router-for-me/CLIProxyAPI/releases/download/v8.0.61/checksums.txt
sha256sum -c <(grep windows_amd64.zip checksums.txt)   # 先校验再解压
```

> 未认证 GitHub API 会限流（`api.github.com` 403），下载走 `releases/download/` 直链不受影响；
> 查版本用 `gh`（已登录）比 curl API 稳。

更新后同步改本文件第 1 节的 release / commit / sha256 三处，并重跑第 4 节的两个实测结论（新版本可能补齐 antigravity 的 api-keys 支持）。

## 6. 许可

MIT —— 可自由再分发，保留版权声明与许可全文。本目录保留了上游 `LICENSE` 全文，满足该条件。