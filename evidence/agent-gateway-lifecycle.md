# zgate 网关生命周期只读调研（agent-gateway-lifecycle）

> 取证时间：2026-11-09T07:43:02.931Z（Asia/Shanghai +08:00）；项目根 `F:\Project\ModelBus`；分支 `main`；本报告全程只读，未重启/停止任何网关，未打印任何凭据，未执行 git add/commit/push，未改动 `PROGRESS.md`。
> 用户痛点：关闭 CMD 会杀死在 CMD 里运行的网关后台；期望「改完代码自动生效」且「DSH 或 CMD 退出后网关不死」。

## 0. 环境与取证口径

- 工作区 `F:\Project\_merged\DeepseekHarness` 是 junction 视图；`Get-Item` 实测 `LinkType : Junction` / `Target : {F:\Project\ModelBus}`，`git rev-parse --show-toplevel` 穿透为 `F:/Project/ModelBus`。所有结论路径均为真实项目根。
- 代码证据优先用真实根 `codegraph explore`（索引存在但陈旧），再直读当前磁盘源码；凡 `explore` 标注 "changed on disk after the last index sync" 的文件一律以磁盘为准。
- 凭据：`third-party/cliproxyapi/config.yaml` 含 `access.api-keys` 真值，本报告只记录文件存在与路径，不展开内容；`config.example.yaml` 为公开模板。

命令：```text
CMD: git -C "F:\Project\ModelBus" rev-parse --show-toplevel
```
exitCode=128；stdout 0 字符
真实输出（stdout）：
```text
(空)
```
stderr：
```text
fatal: cannot change to '"F:\Project\ModelBus"': Invalid argument

```
executor error：Command failed: cmd.exe /c git -C "F:\Project\ModelBus" rev-parse --show-toplevel
fatal: cannot change to '"F:\Project\ModelBus"': Invalid argument


命令：```text
CMD: git -C "F:\Project\ModelBus" rev-parse --abbrev-ref HEAD
```
exitCode=128；stdout 0 字符
真实输出（stdout）：
```text
(空)
```
stderr：
```text
fatal: cannot change to '"F:\Project\ModelBus"': Invalid argument

```
executor error：Command failed: cmd.exe /c git -C "F:\Project\ModelBus" rev-parse --abbrev-ref HEAD
fatal: cannot change to '"F:\Project\ModelBus"': Invalid argument


命令：```text
CMD: git -C "F:\Project\ModelBus" status --short
```
exitCode=128；stdout 0 字符
真实输出（stdout）：
```text
(空)
```
stderr：
```text
fatal: cannot change to '"F:\Project\ModelBus"': Invalid argument

```
executor error：Command failed: cmd.exe /c git -C "F:\Project\ModelBus" status --short
fatal: cannot change to '"F:\Project\ModelBus"': Invalid argument


命令：```text
PowerShell -NoProfile -EncodedCommand <base64> -- script: Get-Item -Force 'F:\Project\_merged\DeepseekHarness\ModelBus' | Select-Object FullName,LinkType,Target,Attributes | Format-List | Out-String -Width 400
```
exitCode=0；stdout 167 字符
真实输出（stdout）：
```text


FullName   : F:\Project\_merged\DeepseekHarness\ModelBus
LinkType   : Junction
Target     : {F:\Project\ModelBus}
Attributes : Directory, ReparsePoint





```
stderr：
```text
#< CLIXML
<Objs Version="1.1.0.1" xmlns="http://schemas.microsoft.com/powershell/2004/04"><Obj S="progress" RefId="0"><TN RefId="0"><T>System.Management.Automation.PSCustomObject</T><T>System.Object</T></TN><MS><I64 N="SourceId">1</I64><PR N="Record"><AV>正在准备首次使用模块。</AV><AI>0</AI><Nil /><PI>-1</PI><PC>-1</PC><T>Completed</T><SR>-1</SR><SD> </SD></PR></MS></Obj><Obj S="progress" RefId="1"><TNRef RefId="0" /><MS><I64 N="SourceId">1</I64><PR N="Record"><AV>正在准备首次使用模块。</AV><AI>0</AI><Nil /><PI>-1</PI><PC>-1</PC><T>Completed</T><SR>-1</SR><SD> </SD></PR></MS></Obj></Objs>
```

命令：```text
CMD: dir F:\Project\_merged\DeepseekHarness /AL
```
exitCode=0；stdout 251 字符
真实输出（stdout）：
```text
 ������ F �еľ��� ����
 �������к��� 5D3B-0BAE

 F:\Project\_merged\DeepseekHarness ��Ŀ¼

2026/11/06  22:02    <JUNCTION>     ModelBus [F:\Project\ModelBus]
               0 ���ļ�              0 �ֽ�
               1 ��Ŀ¼ 354,419,003,392 �����ֽ�

```

命令：```text
CMD: codegraph status
```
exitCode=0；stdout 686 字符
真实输出（stdout）：
```text

CodeGraph Status

Project: F:\Project\ModelBus

Index Statistics:
  Files:     62
  Nodes:     1,565
  Edges:     3,687
  DB Size:   16.62 MB
  Backend:   node:sqlite - built-in (full WAL)
  Journal:   wal

Nodes by Kind:
  function        520
  import          366
  variable        269
  method          154
  constant        90
  file            58
  property        31
  type_alias      29
  struct          28
  class           19
  interface       1

Files by Language:
  python          26
  go              23
  javascript      6
  yaml            4
  typescript      3

Pending Changes:
  Added:     8 files
  Modified:  26 files
[i] Run "codegraph sync" to update the index


```

命令：```text
CMD: codegraph explore "zgate main supervisor restart reload"
```
exitCode=0；stdout 9061 字符
真实输出（stdout）：
```text
**Exploration: "zgate main supervisor restart reload"**

Found 13 symbols across 1 file.

**Blast radius — what depends on these (update/verify before editing)**

- `reload` (gateways/zgate/internal/router/router.go:863) — 1 caller in `gateways/zgate/internal/router/router.go`; tested via callers: `gateways/zgate/internal/router/egress_test.go`, `gateways/zgate/internal/router/router_test.go`
- `Supervisor` (gateways/zgate/internal/supervisor/supervisor.go:56) — 3 callers in `gateways/zgate/internal/supervisor/supervisor.go`, `gateways/zgate/internal/router/router.go`; tests: `gateways/zgate/internal/supervisor/supervisor_windows_test.go`
- `reload` (gateways/zgate/main.go:295) — 1 caller in `gateways/zgate/main.go`; no tests found within 3 caller hops
- `Reload` (gateways/zgate/internal/alias/alias.go:79) — 3 callers in `gateways/zgate/internal/alias/alias.go`; tests: `gateways/zgate/internal/alias/alias_test.go`

**Source Code**

> The code below is the **verbatim, current on-disk source** of these files — re-read from disk on this call and line-numbered, byte-for-byte identical to what the Read tool returns. It is NOT a summary, outline, or stale cache. Treat each block as a Read you have already performed: do not Read a file shown here. (Exception: files flagged "⚠ changed on disk" below drifted from the index after their last sync — their source is omitted rather than risk a mis-sliced block; Read those specific files.)

**`gateways/zgate/main.go`** — ⚠ changed on disk after the last index sync — source omitted (indexed line ranges no longer match, so a slice could show the wrong code). Read this file directly for current content; the change is picked up on that project's next index sync.

**`gateways/zgate/internal/router/router.go`** — ⚠ changed on disk after the last index sync — source omitted (indexed line ranges no longer match, so a slice could show the wrong code). Read this file directly for current content; the change is picked up on that project's next index sync.

**`providers/workbuddy/workbuddy_fetch_pricing.py`** — ⚠ changed on disk after the last index sync — source omitted (indexed line ranges no longer match, so a slice could show the wrong code). Read this file directly for current content; the change is picked up on that project's next index sync.

**`gateways/zgate/build.py`** — main(function), check_subsystem(function), build_cross_check(function), build_native(function), ZDIR(variable), +8 more

```python
1	#!/usr/bin/env python3
2	# -*- coding: utf-8 -*-
3	"""构建 zgate，并校验产物是 GUI 子系统（Windows 上零窗口）。
4	
5	用法：
6	    python gateways/zgate/build.py              # 构建（Windows: 产物 zgate.exe）+ 校验 PE 子系统
7	    python gateways/zgate/build.py --check      # 只校验现有 gateways/zgate/zgate.exe，不编译
8	    python gateways/zgate/build.py --cross-check# 交叉编译一份 windows/amd64 到临时目录并校验（CI 用，可在 Linux 上跑）
9	
10	为什么需要这个脚本：
11	    `go build ./...` 会把 main 包的可执行文件**写到当前目录**，静默覆盖掉
12	    按 GUI 子系统编译的 zgate.exe —— 登录自启就会弹出一个 cmd 控制台窗口，
13	    关掉那个窗口等于杀掉网关。`-H windowsgui` 只在链接期生效，事后无法从
14	    源码判断，只能校验产物的 PE 头。所以：编译入口收口到这里，并强制校验。
15	
16	    仓库里的等价物：
17	      - 正本构建命令：docs/MAINTENANCE.md §8.1
18	      - 机制解释：    docs/PITFALLS.md §20
19	      - 排错步骤：    docs/TROUBLESHOOTING.md §13
20	
21	退出码：0 通过 / 1 失败。
22	"""
23	from __future__ import annotations
24	
25	import os
26	import struct
27	import subprocess
28	import sys
29	import tempfile
30	
31	# 本脚本位于 <repo>/gateways/zgate/，仓库根要上溯两层
32	ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
33	ZDIR = os.path.join(ROOT, "gateways", "zgate")
34	EXE = os.path.join(ZDIR, "zgate.exe")
35	
36	# PE Subsystem 取值
37	SUBSYSTEM_CONSOLE = 3
38	SUBSYSTEM_WINDOWS_GUI = 2
39	SUBSYSTEM_NAMES = {
40	    2: "WINDOWS_GUI（无窗）",
41	    3: "CONSOLE（控制台，会弹窗）",
42	}
43	
44	# 链接期 flag：把产物切成 GUI 子系统，Windows 启动时不分配控制台窗口
45	WINDOWSGUI_LDFLAGS = "-H windowsgui"
46	
47	
48	def read_subsystem(path: str) -> int:
49	    """读 PE 头的 Subsystem 字段。返回 2=GUI / 3=CONSOLE。"""
50	    with open(path, "rb") as fh:
51	        head = fh.read(0x1000)
52	    if head[:2] != b"MZ":
53	        raise ValueError(f"不是合法的 PE 文件：{path}")
54	    pe_off = struct.unpack_from("<I", head, 0x3C)[0]
55	    if head[pe_off:pe_off + 4] != b"PE\x00\x00":
56	        raise ValueError(f"PE 签名缺失：{path}")
57	    # Optional Header 从 PE+24 开始，Subsystem 在其中偏移 0x44
58	    return struct.unpack_from("<H", head, pe_off + 24 + 0x44)[0]
59	
60	
61	def check_subsystem(path: str) -> int:
62	    """校验产物是 GUI 子系统。不合格返回 1。"""
63	    try:
64	        sub = read_subsystem(path)
65	    except (OSError, ValueError) as exc:
66	        print(f"[FAIL] {exc}")
67	        return 1
68	    name = SUBSYSTEM_NAMES.get(sub, f"未知({sub})")
69	    if sub == SUBSYSTEM_WINDOWS_GUI:
70	        print(f"[ OK ] Subsystem = {sub} → {name}    {path}")
71	        return 0
72	    print(f"[FAIL] Subsystem = {sub} → {name}    {path}")
73	    print(f"       这个产物一启动就会分配控制台窗口。"
74	          f"用 `python gateways/zgate/build.py` 重新构建，"
75	          f"别裸跑 `go
```

## 1. 所有启动 / 构建 / 停止脚本（递归盘点 + 逐个说明）

清单来自 PowerShell `Get-ChildItem -Recurse -File -Force`，真实输出：
```text
.github\ISSUE_TEMPLATE\bug_report.yml
.github\ISSUE_TEMPLATE\config.yml
.github\ISSUE_TEMPLATE\feature_request.yml
.github\workflows\ci.yml
.work\restart_zgate.ps1
.work\run_candidate.ps1
.work\start_cp.ps1
.work\zc_procs.ps1
.work\zc_procs2.ps1
gateways\upstream\qoder\.github\workflows\docker-publish.yml
gateways\upstream\qoder\.github\workflows\tests.yml
gateways\upstream\qoder\allow-firewall.bat
gateways\upstream\qoder\allow-firewall.sh
gateways\upstream\qoder\docker-compose.yml
gateways\upstream\qoder\start-qoder-proxy.bat
gateways\upstream\qoder\start-qoder-proxy.sh
gateways\upstream\qoder\start-qoder-proxy-lan.bat
gateways\upstream\qoder\start-qoder-proxy-lan.sh
gateways\upstream\qoder\stop-qoder-proxy.bat
gateways\upstream\qoder\stop-qoder-proxy.sh
gateways\upstream\workbuddy\.github\workflows\autobot.yml
gateways\upstream\workbuddy\.github\workflows\binaries.yml
gateways\upstream\workbuddy\.github\workflows\docker-ghcr.yml
gateways\upstream\workbuddy\AutoBot.yml
gateways\upstream\workbuddy\credit.sh
gateways\upstream\workbuddy\docker-compose.yml
gateways\upstream\workbuddy\login.sh
gateways\upstream\workbuddy\run.bat
gateways\upstream\workbuddy\signin.sh
gateways\upstream\workbuddy\stop-gateway.bat
sync-models.ps1
sync-models.vbs
third-party\cliproxyapi\config.example.yaml
third-party\cliproxyapi\config.yaml
tools\rename-to-modelbus.ps1


```

`gateways/zgate` 目录递归清单真实输出：
```text
gateways\zgate\.restart.log
gateways\zgate\build.py
gateways\zgate\build.py.dshclaim
gateways\zgate\go.mod
gateways\zgate\internal\alias\alias.go
gateways\zgate\internal\alias\alias_test.go
gateways\zgate\internal\bridge\bridge.go
gateways\zgate\internal\bridge\bridge.go.dshclaim
gateways\zgate\internal\bridge\bridge_test.go
gateways\zgate\internal\bridge\id.go
gateways\zgate\internal\config\config.go
gateways\zgate\internal\config\config.go.dshclaim
gateways\zgate\internal\keys\keys.go
gateways\zgate\internal\logx\console_other.go
gateways\zgate\internal\logx\console_windows.go
gateways\zgate\internal\logx\logx.go
gateways\zgate\internal\router\egress.go
gateways\zgate\internal\router\egress_test.go
gateways\zgate\internal\router\quota_test.go
gateways\zgate\internal\router\router.go
gateways\zgate\internal\router\router.go.dshclaim
gateways\zgate\internal\router\router_test.go
gateways\zgate\internal\router\router_test.go.dshclaim
gateways\zgate\internal\router\stream_test.go
gateways\zgate\internal\supervisor\supervisor.go
gateways\zgate\internal\supervisor\supervisor_windows_test.go
gateways\zgate\internal\supervisor\windows_test.go
gateways\zgate\internal\winproc\console_other.go
gateways\zgate\internal\winproc\console_other.go.bak-20261109-detach
gateways\zgate\internal\winproc\console_windows.go
gateways\zgate\internal\winproc\console_windows.go.bak-20261109-detach
gateways\zgate\internal\winproc\winproc.go
gateways\zgate\internal\winproc\winproc_other.go
gateways\zgate\internal\winproc\winproc_windows.go
gateways\zgate\internal\winproc\winproc_windows.go.dshclaim
gateways\zgate\main.go
gateways\zgate\main.go.bak-20261109-dup
gateways\zgate\main.go.dshclaim
gateways\zgate\smoke_test.py
gateways\zgate\zgate.exe
gateways\zgate\zgate.exe.bak-20261109
gateways\zgate\zgate.exe.bak-20261109-lonehop
gateways\zgate\zgate.exe.prev
gateways\zgate\zgate.exe~
gateways\zgate\zgate.json
gateways\zgate\zgate.json.bak-20261109-cp


```

关键字是否含有，逐文件由 PowerShell `Select-String` 与逐行正则双重核对；`Select-String` 真实输出（排除 `config.yaml` 真值文件）：
```text
.github\workflows\ci.yml:46:unformatted=$(gofmt -l gateways/zgate)
.github\workflows\ci.yml:54:working-directory: gateways/zgate
.github\workflows\ci.yml:55:run: go build ./... && go test ./...
.github\workflows\ci.yml:60:run: python3 gateways/zgate/build.py --cross-check
.work\restart_zgate.ps1:2:$dir = "F:\Project\ModelBus\gateways\zgate"
.work\restart_zgate.ps1:3:$exe = Join-Path $dir "zgate.exe"
.work\restart_zgate.ps1:5:$bak = Join-Path $dir "zgate.exe.prev"
.work\restart_zgate.ps1:6:$log = Join-Path $dir ".restart.log"
.work\restart_zgate.ps1:8:Start-Sleep -Seconds 20
.work\restart_zgate.ps1:11:Stop-Process -Name zgate -Force -ErrorAction SilentlyContinue
.work\restart_zgate.ps1:12:Start-Sleep -Seconds 1
.work\restart_zgate.ps1:14:Start-Process -FilePath $exe -WorkingDirectory $dir -WindowStyle Hidden
.work\restart_zgate.ps1:17:Start-Sleep -Milliseconds 700
.work\restart_zgate.ps1:26:Stop-Process -Name zgate -Force -ErrorAction SilentlyContinue
.work\restart_zgate.ps1:27:Start-Sleep -Seconds 1
.work\restart_zgate.ps1:29:Start-Process -FilePath $exe -WorkingDirectory $dir -WindowStyle Hidden
.work\run_candidate.ps1:2:$env:ZGATE_CONFIG = "F:\Project\ModelBus\gateways\zgate\zgate.json"
.work\run_candidate.ps1:3:$p = Start-Process -FilePath "F:\Project\ModelBus\.work\zgate.candidate.exe" -WorkingDirectory "F:\Project\ModelBus\gateways\zgate" -WindowStyle Hidden -PassThru
.work\start_cp.ps1:2:$p1 = Start-Process -FilePath "$dir\cli-proxy-api.exe" -ArgumentList "-config","config.yaml" -WorkingDirectory $dir -WindowStyle Hidden -RedirectStandardOutput "$dir\run.out.log" -RedirectStandardError "$dir\run.err.log" -PassThru
.work\start_cp.ps1:3:Start-Sleep -Seconds 3
.work\start_cp.ps1:4:$p2 = Start-Process -FilePath "$dir\cli-proxy-api.exe" -ArgumentList "-antigravity-login","-no-browser" -WorkingDirectory $dir -WindowStyle Hidden -RedirectStandardOutput "$dir\aglogin3.log" -RedirectStandardError "$dir\aglogin3.err" -PassThru
.work\start_cp.ps1:5:Start-Sleep -Seconds 4
gateways\upstream\qoder\_diag_gateway.py:2:"""_diag_gateway.py —— 网关存活与流式自检（一条命令回答“为什么 harness 不吐字”）
gateways\upstream\qoder\_diag_gateway.py:12:python _diag_gateway.py                 # 只做 1-3
gateways\upstream\qoder\_diag_gateway.py:13:python _diag_gateway.py --chat          # 追加真实流式自检
gateways\upstream\qoder\_diag_gateway.py:14:python _diag_gateway.py --port 8790 --model Qwen3.8-Flash --key <API_KEY>
gateways\upstream\qoder\_diag_gateway.py:66:"remote gateway" % host)
gateways\upstream\qoder\_test_qoder.py:1:"""Deterministic offline tests for the Qoder gateway.
gateways\upstream\qoder\_test_qoder.py:129:url = "https://gateway.qoder.com.cn" + P.CHAT_PATH
gateways\upstream\qoder\_test_qoder.py:1483:print("[10] gateway plumbing")
gateways\upstream\qoder\_test_qoder.py:1653:print("[19] gateway host failover (official intl api3 -> api2/api1; CN single host)")
gateways\upstream\qoder\_test_qoder.py:1656:check("gateway_candidates: intl primary is api3 with api2/api1 fallbacks",
gateways\upstream\qoder\_test_qoder.py:1657:A.gateway_candidates("intl") == ["https://api3.qoder.sh",
gateways\upstream\qoder\_test_qoder.py:1660:A.gateway_candidates("intl"))
gateways\upstream\qoder\_test_qoder.py:1661:check("gateway_candidates: cn has a single official host",
gateways\upstream\qoder\_test_qoder.py:1662:A.gateway_candidates("cn") == ["https://gateway.qoder.com.cn"],
gateways\upstream\qoder\_test_qoder.py:1663:A.gateway_candidates("cn"))
gateways\upstream\qoder\_test_qoder.py:3284:_gate_restart28 = _s2_28._allow_complement_checkin(_S28.CYCLE_STARTUP)
gateways\upstream\qoder\_test_qoder.py:3292:_gate_first28 = _gate_second28 = _gate_restart28 = _gate_hour28 = None
gateways\upstream\qoder\_test_qoder.py:3309:_gate_restart28 is False, _gate_restart28)
gateways\upstream\qoder\_verify_models.py:163:print(f"FATAL: gateway returned HTTP {e.code} for realm={realm} "
gateways\upstream\qoder\_verify_models.py:167:print(f"FATAL: gateway unreachable at {args.base}: {e}")
gateways\upstream\qoder\_verify_models.py:173:rep = {"official": len(official), "gateway": len(gw),
gateways\upstream\qoder\_verify_models.py:176:"gateway_only": sorted(set(gw) - set(official))}
gateways\upstream\qoder\_verify_models.py:180:f"official={len(official)} gateway={len(gw)} =====")
gateways\upstream\qoder\_verify_models.py:185:check(realm, key, "missing in gateway", False)
gateways\upstream\qoder\_verify_models.py:289:check(realm, "*", "no official model missing in gateway",
gateways\upstream\qoder\_verify_models.py:291:check(realm, "*", "no unknown model injected by gateway",
gateways\upstream\qoder\_verify_models.py:292:not rep["gateway_only"], rep["gateway_only"])
gateways\upstream\qoder\_verify_models.py:294:f"gateway_only={rep['gateway_only']}")
gateways\upstream\qoder\_verify_models.py:296:print("  gateway list: " + " | ".join(
gateways\upstream\qoder\allow-firewall.bat:20:"Start-Process -Verb RunAs -Wait -FilePath 'netsh' -ArgumentList 'advfirewall','firewall','add','rule',^
gateways\upstream\qoder\allow-firewall.sh:44:firewall-cmd --reload
gateways\upstream\qoder\allow-firewall.sh:48:echo "  sudo firewall-cmd --permanent --remove-port=$PORT/tcp && sudo firewall-cmd --reload"
gateways\upstream\qoder\docker-compose.yml:8:restart: unless-stopped
gateways\upstream\qoder\qoder_accounts.py:46:"gateway": "https://gateway.qoder.com.cn",
gateways\upstream\qoder\qoder_accounts.py:70:"gateway": os.environ.get("QD_INTL_GATEWAY") or "https://api3.qoder.sh",
gateways\upstream\qoder\qoder_accounts.py:71:"gateway_fallbacks": ("https://api2.qoder.sh", "https://api1.qoder.sh"),
gateways\upstream\qoder\qoder_accounts.py:955:def gateway_candidates(realm):
gateways\upstream\qoder\qoder_accounts.py:961:out = [cfg["gateway"]]
gateways\upstream\qoder\qoder_accounts.py:962:for host in cfg.get("gateway_fallbacks") or ():
gateways\upstream\qoder\qoder_accounts.py:1213:# 198.18.0.0/15 (RFC 2544 benchmarking) 与 fdfe:dcba:9876::/48 被 Clash/mihomo
gateways\upstream\qoder\qoder_accounts.py:2440:log("campaigns: hidden list recovered with minimal machine headers "
gateways\upstream\qoder\qoder_agents.py:38:PROVIDER_NAME = "Qoder Gateway"
gateways\upstream\qoder\qoder_agents.py:835:def fetch_models_from_gateway(base_url, api_key, timeout=10):
gateways\upstream\qoder\qoder_agents.py:851:"the gateway rejected the API key (HTTP 401)")
gateways\upstream\qoder\qoder_agents.py:852:raise AgentConfigError("gateway /v1/models failed: HTTP %s" % exc.code)
gateways\upstream\qoder\qoder_agents.py:855:"gateway /v1/models returned invalid JSON: %s" % exc)
gateways\upstream\qoder\qoder_agents.py:858:"cannot reach the gateway /v1/models: %s" % exc)
gateways\upstream\qoder\qoder_agents.py:944:models = fetch_models_from_gateway(base_url, api_key)
gateways\upstream\qoder\qoder_agents.py:945:print("fetched %d models from the gateway" % len(models))
gateways\upstream\qoder\qoder_catalog.py:1:"""Official per-realm model catalog for the Qoder gateway — FULL FIDELITY.
gateways\upstream\qoder\qoder_catalog.py:887:# 国内版 (qoder.com.cn / gateway.qoder.com.cn) 官方 chat 场景全字段快照
gateways\upstream\qoder\qoder_fingerprint.py:3:无论是国内版 (qoder.com.cn / gateway.qoder.com.cn) 还是国际版
gateways\upstream\qoder\qoder_proxy.py:11:-> POST {gateway}/algo/api/v2/service/pro/sse/agent_chat_generation
gateways\upstream\qoder\qoder_proxy.py:60:from qoder_accounts import (get_realm_config, gateway_candidates,
gateways\upstream\qoder\qoder_proxy.py:103:# 198.18.0.0/15 (RFC 2544 benchmarking) 与 fdfe:dcba:9876::/48 被 Clash/mihomo
gateways\upstream\qoder\qoder_proxy.py:304:if not ctypes.windll.kernel32.SetConsoleCtrlHandler(handler, True):
gateways\upstream\qoder\qoder_proxy.py:422:# lives in accounts/settings.json, so a restart no longer forces a re-login.
gateways\upstream\qoder\qoder_proxy.py:2042:def gateway_models_for_agents(realm=None):
gateways\upstream\qoder\qoder_proxy.py:2509:for host in gateway_candidates(r):
gateways\upstream\qoder\qoder_proxy.py:2819:"""Drop the empty noise fields the gateway pads deltas with."""
gateways\upstream\qoder\qoder_proxy.py:6481:hosts = gateway_candidates(account.realm)
gateways\upstream\qoder\qoder_proxy.py:6577:"(try %d/%d): %s - switching gateway host to %s"
gateways\upstream\qoder\qoder_proxy.py:6887:log("upstream error hidden in HTTP 200 envelope: kind=%s status=%s "
gateways\upstream\qoder\qoder_proxy.py:8581:return self._json(200, gateway_models_for_agents(realm_q))
gateways\upstream\qoder\qoder_proxy.py:9207:if payload.get("restart_scheduler"):
gateways\upstream\qoder\qoder_proxy.py:9211:reply["scheduler"] = "restarted"
gateways\upstream\qoder\qoder_proxy.py:9625:acc_realm(account))["gateway"]),
gateways\upstream\qoder\qoder_proxy.py:10340:restarted = qoder_updater.schedule_restart(_LAUNCH_ARGV, delay=1.5)
gateways\upstream\qoder\qoder_proxy.py:10341:log("update: %s -> %s (%d files, backup=%s), restarting=%s"
gateways\upstream\qoder\qoder_proxy.py:10343:res.get("backup") or "-", restarted), tag="update")
gateways\upstream\qoder\qoder_proxy.py:10344:return self._json(200, dict(res, restarting=restarted))
gateways\upstream\qoder\qoder_proxy.py:10397:models = qoder_agents.fetch_models_from_gateway(
gateways\upstream\qoder\qoder_proxy.py:10426:"this gateway speaks Chat Completions and Responses. "
gateways\upstream\qoder\qoder_proxy.py:10901:"Change it in the panel, or restart with --panel-password.",
gateways\upstream\qoder\qoder_proxy.py:10933:"rate-limit or queue the intl gateway from datacenter IPs. "
gateways\upstream\qoder\qoder_proxy.py:11083:# 进程生命周期内保持 handler 引用：SetConsoleCtrlHandler 存的是裸指针，
gateways\upstream\qoder\qoder_settings.py:1:"""Runtime settings for the Qoder gateway: panel password and API keys.
gateways\upstream\qoder\qoder_settings.py:4:panel survives a restart without editing the launcher .bat files. The panel
gateways\upstream\qoder\qoder_settings.py:131:LAN mode must never ship a well-known default: the gateway spends the
gateways\upstream\qoder\qoder_settings.py:134:restarts. Returns (key, created) so the caller can tell the user whether
gateways\upstream\qoder\qoder_settings.py:225:# source of truth and the list survives a restart.
gateways\upstream\qoder\qoder_settings.py:380:崩溃自愈、升级后 restart）浏览器就得重新登录——「更安全」的默认值在
gateways\upstream\qoder\qoder_updater.py:263:def schedule_restart(argv, delay=1.2):
gateways\upstream\qoder\qoder_updater.py:276:_log("restart failed: %s" % exc, level="ERROR")
gateways\upstream\qoder\scripts\risk_diag.py:180:hosts = ["gateway.qoder.com.cn", "openapi.qoder.com.cn",
gateways\upstream\qoder\start-qoder-proxy.bat:78:powershell -NoProfile -ExecutionPolicy Bypass -Command "$q = [char]34; $args = @(($q + $env:QD_SCRIPT + $q), '--port', $env:QD_PORT, '--pid-file', ($q + $env:QD_PIDFILE + $q)); $p = Start-Process -FilePath $env:QD_EXE -ArgumentList $args -WindowStyle Hidden -RedirectStandardOutput $env:QD_LOGFILE -RedirectStandardError $env:QD_ERRFILE -PassThru; 
```

结论：`*.cmd` 无命中；`Makefile` 无命中；`*.service` 无命中。`gateways/zgate` 下没有任何 `.ps1/.vbs/.cmd/.bat/.sh/Makefile/*.service/*.yaml`；zgate 的启动逻辑在 Go 源码 `main.go`（`serve` / `serve -tray` / `install` / `detach`）和 Python 构建脚本 `build.py`，不在脚本文件里。

| 真实路径 | 作用 | Start-Process | schtasks / ScheduledTask | sc create / NSSM | go build / GOOS | Start-Process 隐藏 / WScript.Shell | Stop-Process / taskkill |
|---|---|---|---|---|---|---|---|
| .github/ISSUE_TEMPLATE/bug_report.yml | 配置 / CI / compose 声明文件，非 zgate 启动器 | 无 | 无 | 无 | 无 | 无 | 无 |
| .github/ISSUE_TEMPLATE/config.yml | 配置 / CI / compose 声明文件，非 zgate 启动器 | 无 | 无 | 无 | 无 | 无 | 无 |
| .github/ISSUE_TEMPLATE/feature_request.yml | 配置 / CI / compose 声明文件，非 zgate 启动器 | 无 | 无 | 无 | 无 | 无 | 无 |
| .github/workflows/ci.yml | GitHub Actions：go build ./...、go test ./...、build.py --cross-check | 无 | 无 | 无 | 有 | 无 | 无 |
| .work/restart_zgate.ps1 | 手工 zgate 受控重启脚本（含 Stop-Process / Start-Process / 备份交换） | 有 | 无 | 无 | 无 | 有 | 有 |
| .work/run_candidate.ps1 | 手工用 7872 端口试跑 zgate.candidate.exe | 有 | 无 | 无 | 无 | 有 | 无 |
| .work/start_cp.ps1 | 手工启动 CLIProxyAPI server/login 两进程 | 有 | 无 | 无 | 无 | 有 | 无 |
| .work/zc_procs.ps1 | 一次性进程调查脚本 | 无 | 无 | 无 | 无 | 无 | 无 |
| .work/zc_procs2.ps1 | 一次性进程调查脚本 | 无 | 无 | 无 | 无 | 无 | 无 |
| gateways/upstream/qoder/.github/workflows/docker-publish.yml | 配置 / CI / compose 声明文件，非 zgate 启动器 | 无 | 无 | 无 | 无 | 无 | 无 |
| gateways/upstream/qoder/.github/workflows/tests.yml | 配置 / CI / compose 声明文件，非 zgate 启动器 | 无 | 无 | 无 | 无 | 无 | 无 |
| gateways/upstream/qoder/allow-firewall.bat | 防火墙放行脚本 | 有 | 无 | 无 | 无 | 无 | 无 |
| gateways/upstream/qoder/allow-firewall.sh | 防火墙放行脚本 | 无 | 无 | 无 | 无 | 无 | 无 |
| gateways/upstream/qoder/docker-compose.yml | 配置 / CI / compose 声明文件，非 zgate 启动器 | 无 | 无 | 无 | 无 | 无 | 无 |
| gateways/upstream/qoder/start-qoder-proxy-lan.bat | Qoder 代理启动脚本（LAN 变体监听 0.0.0.0） | 无 | 无 | 无 | 无 | 无 | 无 |
| gateways/upstream/qoder/start-qoder-proxy-lan.sh | Qoder 代理启动脚本（LAN 变体监听 0.0.0.0） | 无 | 无 | 无 | 无 | 无 | 无 |
| gateways/upstream/qoder/start-qoder-proxy.bat | Qoder 代理启动脚本（LAN 变体监听 0.0.0.0） | 有 | 无 | 无 | 无 | 有 | 无 |
| gateways/upstream/qoder/start-qoder-proxy.sh | Qoder 代理启动脚本（LAN 变体监听 0.0.0.0） | 无 | 无 | 无 | 无 | 无 | 无 |
| gateways/upstream/qoder/stop-qoder-proxy.bat | Qoder 代理停止脚本 | 无 | 无 | 无 | 无 | 无 | 有 |
| gateways/upstream/qoder/stop-qoder-proxy.sh | Qoder 代理停止脚本 | 无 | 无 | 无 | 无 | 无 | 无 |
| gateways/upstream/workbuddy/.github/workflows/autobot.yml | 配置 / CI / compose 声明文件，非 zgate 启动器 | 无 | 无 | 无 | 无 | 无 | 无 |
| gateways/upstream/workbuddy/.github/workflows/binaries.yml | 配置 / CI / compose 声明文件，非 zgate 启动器 | 无 | 无 | 无 | 有 | 无 | 无 |
| gateways/upstream/workbuddy/.github/workflows/docker-ghcr.yml | 配置 / CI / compose 声明文件，非 zgate 启动器 | 无 | 无 | 无 | 无 | 无 | 无 |
| gateways/upstream/workbuddy/AutoBot.yml | 配置 / CI / compose 声明文件，非 zgate 启动器 | 无 | 无 | 无 | 无 | 无 | 无 |
| gateways/upstream/workbuddy/credit.sh | WorkBuddy 手动采集/登录脚本 | 无 | 无 | 无 | 有 | 无 | 无 |
| gateways/upstream/workbuddy/docker-compose.yml | 配置 / CI / compose 声明文件，非 zgate 启动器 | 无 | 无 | 无 | 无 | 无 | 无 |
| gateways/upstream/workbuddy/login.sh | WorkBuddy 手动采集/登录脚本 | 无 | 无 | 无 | 有 | 无 | 无 |
| gateways/upstream/workbuddy/run.bat | WorkBuddy 上游启动脚本 | 无 | 无 | 无 | 无 | 无 | 无 |
| gateways/upstream/workbuddy/signin.sh | WorkBuddy 手动采集/登录脚本 | 无 | 无 | 无 | 有 | 无 | 无 |
| gateways/upstream/workbuddy/stop-gateway.bat | WorkBuddy 上游停止脚本 | 无 | 无 | 无 | 无 | 无 | 有 |
| sync-models.ps1 | 每日模型同步流水线（Windows 计划任务入口）；会按需隐藏启动 qoder 代理 | 有 | 无 | 无 | 无 | 有 | 无 |
| sync-models.vbs | 计划任务用无窗口包装器，隐藏启动 sync-models.ps1 | 无 | 无 | 无 | 无 | 有 | 无 |
| third-party/cliproxyapi/config.example.yaml | 配置 / CI / compose 声明文件，非 zgate 启动器 | 无 | 无 | 无 | 有 | 无 | 无 |
| third-party/cliproxyapi/config.yaml（含凭据真值，按约束未展开内容） | 配置 / CI / compose 声明文件，非 zgate 启动器 | 无 | 无 | 无 | 无 | 无 | 无 |
| tools/rename-to-modelbus.ps1 | 一次性仓库改名脚本 | 有 | 有 | 无 | 无 | 有 | 有 |

关键脚本逐行摘录（真实行号）：
```text
sync-models.ps1:1: ﻿#Requires -Version 5.1
sync-models.ps1:4:     ModelBus 每日模型同步（Windows 计划任务入口）
sync-models.ps1:7:     迁移自 DeepSeekRuntime 的定时任务（原 schedule-4467b892-8205-44ec-8e03-fd0f018c1ab4）。
sync-models.ps1:8:     移到这里的原因：DSH 的 cron 只在 DSH 运行时才触发，关着就跳过；
sync-models.ps1:9:                 而且有待命定时任务时，DSH 每次退出都要弹确认框。
sync-models.ps1:22:     powershell -NoProfile -ExecutionPolicy Bypass -File sync-models.ps1
sync-models.ps1:23:     powershell -NoProfile -ExecutionPolicy Bypass -File sync-models.ps1 -NoPush
sync-models.ps1:33: $ROOT       = "F:\Project\ModelBus"
sync-models.ps1:62: # 计划任务的 PATH 很干净，git / python 都得自己补
sync-models.ps1:194: function Wait-Port {
sync-models.ps1:195:     param([string]$TargetHost = "127.0.0.1", [int]$Port, [int]$Seconds = 60)
sync-models.ps1:196:     $deadline = (Get-Date).AddSeconds($Seconds)
sync-models.ps1:197:     while ((Get-Date) -lt $deadline) {
sync-models.ps1:198:         if (Test-Port $TargetHost $Port) { return $true }
sync-models.ps1:199:         Start-Sleep -Seconds 2
sync-models.ps1:200:     }
sync-models.ps1:201:     return (Test-Port $TargetHost $Port)
sync-models.ps1:232: # Qoder 的模型清单从 hub 的 live catalog 拉，需要 8790 的 qoder 代理先起来。
sync-models.ps1:233: # 代理是 detached 启动的，调用后立即返回，用端口轮询等它起来。
sync-models.ps1:234: if (-not (Test-Port "127.0.0.1" 8790)) {
sync-models.ps1:235:     Say "8790 未监听，启动 qoder 代理"
sync-models.ps1:236:     $bat = Join-Path $ROOT "gateways\upstream\qoder\start-qoder-proxy.bat"
sync-models.ps1:237:     if (Test-Path $bat) {
sync-models.ps1:238:         Start-Process -FilePath $bat -WorkingDirectory (Split-Path $bat) -WindowStyle Hidden
sync-models.ps1:239:         if (Wait-Port "127.0.0.1" 8790 90) {
sync-models.ps1:240:             Say "8790 已就绪"
sync-models.ps1:241:         } else {
sync-models.ps1:242:             Say "8790 启动超时，Qoder 段大概率会失败"
sync-models.ps1:243:         }
sync-models.ps1:244:     } else {
sync-models.ps1:245:         Say "找不到 start-qoder-proxy.bat"
sync-models.ps1:246:     }
sync-models.ps1:247: } else {
sync-models.ps1:248:     Say "8790 已在监听"
sync-models.ps1:249: }
sync-models.ps1:376: # 弹通知告诉用户结果（无 cmd 窗口时这是唯一的可见反馈）
sync-models.ps1:377: Show-SyncToast -Main $mainN -Free $freeN -Saving $saveN -ReportPath $reportPath -LogPath $LOG
sync-models.vbs:1: ' sync-models.vbs — 无窗口启动模型同步
sync-models.vbs:2: '
sync-models.vbs:3: ' 计划任务的动作指向本文件（wscript.exe），而不是 powershell.exe：
sync-models.vbs:4: '   WScript.Shell.Run 的第二个参数 0 = 隐藏窗口，所以整个 PowerShell
sync-models.vbs:5: '   进程树都不会闪出 cmd / 控制台窗口。
sync-models.vbs:10: Dim shell, ps1, cmd
sync-models.vbs:11: Set shell = CreateObject("WScript.Shell")
sync-models.vbs:12: 
sync-models.vbs:13: ps1 = "F:\Project\ModelBus\sync-models.ps1"
sync-models.vbs:14: cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & ps1 & """"
sync-models.vbs:15: 
sync-models.vbs:16: ' 0 = 隐藏, False = 不等待（wscript 立即退出，同步在后台跑完）
sync-models.vbs:17: shell.Run cmd, 0, False
.work/restart_zgate.ps1:1: $ErrorActionPreference = "Continue"
.work/restart_zgate.ps1:2: $dir = "F:\Project\ModelBus\gateways\zgate"
.work/restart_zgate.ps1:3: $exe = Join-Path $dir "zgate.exe"
.work/restart_zgate.ps1:4: $cand = "F:\Project\ModelBus\.work\zgate.candidate.exe"
.work/restart_zgate.ps1:5: $bak = Join-Path $dir "zgate.exe.prev"
.work/restart_zgate.ps1:6: $log = Join-Path $dir ".restart.log"
.work/restart_zgate.ps1:7: "start $(Get-Date -Format o)" | Out-File $log -Encoding utf8
.work/restart_zgate.ps1:8: Start-Sleep -Seconds 20
.work/restart_zgate.ps1:9: try {
.work/restart_zgate.ps1:10:   Copy-Item $exe $bak -Force
.work/restart_zgate.ps1:11:   Stop-Process -Name zgate -Force -ErrorAction SilentlyContinue
.work/restart_zgate.ps1:12:   Start-Sleep -Seconds 1
.work/restart_zgate.ps1:13:   Copy-Item $cand $exe -Force
.work/restart_zgate.ps1:14:   Start-Process -FilePath $exe -WorkingDirectory $dir -WindowStyle Hidden
.work/restart_zgate.ps1:15:   $ok = $false
.work/restart_zgate.ps1:16:   for ($i = 0; $i -lt 24; $i++) {
.work/restart_zgate.ps1:17:     Start-Sleep -Milliseconds 700
.work/restart_zgate.ps1:18:     try {
.work/restart_zgate.ps1:19:       $resp = Invoke-WebRequest -Uri "http://127.0.0.1:7871/health" -TimeoutSec 2 -UseBasicParsing
.work/restart_zgate.ps1:20:       if ($resp.StatusCode -eq 200) { $ok = $true; break }
.work/run_candidate.ps1:1: $env:ZGATE_LISTEN = "127.0.0.1:7872"
.work/run_candidate.ps1:2: $env:ZGATE_CONFIG = "F:\Project\ModelBus\gateways\zgate\zgate.json"
.work/run_candidate.ps1:3: $p = Start-Process -FilePath "F:\Project\ModelBus\.work\zgate.candidate.exe" -WorkingDirectory "F:\Project\ModelBus\gateways\zgate" -WindowStyle Hidden -PassThru
.work/run_candidate.ps1:4: Write-Output ("pid=" + $p.Id)
.work/start_cp.ps1:1: $dir = "F:\Project\ModelBus\third-party\cliproxyapi"
.work/start_cp.ps1:2: $p1 = Start-Process -FilePath "$dir\cli-proxy-api.exe" -ArgumentList "-config","config.yaml" -WorkingDirectory $dir -WindowStyle Hidden -RedirectStandardOutput "$dir\run.out.log" -RedirectStandardError "$dir\run.err.log" -PassThru
.work/start_cp.ps1:3: Start-Sleep -Seconds 3
.work/start_cp.ps1:4: $p2 = Start-Process -FilePath "$dir\cli-proxy-api.exe" -ArgumentList "-antigravity-login","-no-browser" -WorkingDirectory $dir -WindowStyle Hidden -RedirectStandardOutput "$dir\aglogin3.log" -RedirectStandardError "$dir\aglogin3.err" -PassThru
.work/start_cp.ps1:5: Start-Sleep -Seconds 4
.work/start_cp.ps1:6: Write-Output ("server=" + $p1.Id + " login=" + $p2.Id)
.work/start_cp.ps1:7: 
.work/start_cp.ps1:8: 
.work/start_cp.ps1:9: 
.work/start_cp.ps1:10: 
gateways/zgate/build.py:3: """构建 zgate，并校验产物是 GUI 子系统（Windows 上零窗口）。
gateways/zgate/build.py:5: 用法：
gateways/zgate/build.py:6:     python gateways/zgate/build.py              # 构建（Windows: 产物 zgate.exe）+ 校验 PE 子系统
gateways/zgate/build.py:7:     python gateways/zgate/build.py --check      # 只校验现有 gateways/zgate/zgate.exe，不编译
gateways/zgate/build.py:8:     python gateways/zgate/build.py --cross-check# 交叉编译一份 windows/amd64 到临时目录并校验（CI 用，可在 Linux 上跑）
gateways/zgate/build.py:9: 
gateways/zgate/build.py:10: 为什么需要这个脚本：
gateways/zgate/build.py:11:     `go build ./...` 会把 main 包的可执行文件**写到当前目录**，静默覆盖掉
gateways/zgate/build.py:12:     按 GUI 子系统编译的 zgate.exe —— 登录自启就会弹出一个 cmd 控制台窗口，
gateways/zgate/build.py:13:     关掉那个窗口等于杀掉网关。`-H windowsgui` 只在链接期生效，事后无法从
gateways/zgate/build.py:34: EXE = os.path.join(ZDIR, "zgate.exe")
gateways/zgate/build.py:37: SUBSYSTEM_CONSOLE = 3
gateways/zgate/build.py:44: # 链接期 flag：把产物切成 GUI 子系统，Windows 启动时不分配控制台窗口
gateways/zgate/build.py:45: WINDOWSGUI_LDFLAGS = "-H windowsgui"
gateways/zgate/build.py:89:     """在 Windows 上构建 zgate.exe（带 windowsgui flag）并校验。"""
gateways/zgate/build.py:90:     if sys.platform != "win32":
gateways/zgate/build.py:91:         print("[SKIP] 本机不是 Windows，跳过原生构建（CI 用 --cross-check）。")
gateways/zgate/build.py:92:         return 0
gateways/zgate/build.py:93:     if os.path.exists(EXE):
gateways/zgate/build.py:94:         print(f"[INFO] 目标已存在：{EXE}")
gateways/zgate/build.py:95:         print("       若 zgate 正在运行，Windows 会锁住文件导致覆盖失败 ——")
gateways/zgate/build.py:96:         print("       先停掉 zgate（zgate 没有 stop 子命令：Stop-Process -Id <pid> -Force），")
gateways/zgate/build.py:97:         print("       或直接用 --check 只校验不编译。")
gateways/zgate/build.py:98:     rc = run(["go", "build", "-C", "gateways/zgate", "-ldflags", WINDOWSGUI_LDFLAGS,
gateways/zgate/build.py:99:               "-o", "zgate.exe", "."], cwd=ROOT)
gateways/zgate/build.py:100:     if rc != 0:
gateways/zgate/build.py:101:         print(f"[FAIL] go build 退出码 {rc}")
gateways/zgate/build.py:102:         return 1
gateways/zgate/build.py:103:     return check_subsystem(EXE)
gateways/zgate/build.py:109:     `-H windowsgui` 是 windows 链接器的 flag，交叉编译到 windows 目标时同样生效，
gateways/zgate/build.py:110:     所以这套校验在 Linux CI 上也能真跑起来（而不是只在本机生效）。
gateways/zgate/build.py:111:     """
gateways/zgate/build.py:112:     with tempfile.TemporaryDirectory(prefix="zgate-cross-") as tmp:
gateways/zgate/build.py:113:         out = os.path.join(tmp, "zgate.exe")
gateways/zgate/build.py:114:         rc = run(["go", "build", "-C", "gateways/zgate", "-ldflags", WINDOWSGUI_LDFLAGS,
gateways/zgate/build.py:115:                   "-o", out, "."], cwd=ROOT,
gateways/zgate/build.py:116:                  env={"GOOS": "windows", "GOARCH": "amd64"})
gateways/zgate/build.py:130:     if "--check" in sys.argv:
gateways/zgate/build.py:131:         print("== 校验现有产物 ==")
gateways/zgate/build.py:132:         if not os.path.exists(EXE):
gateways/zgate/build.py:133:             print(f"[FAIL] 不存在 {EXE}")
gateways/zgate/build.py:134:             return 1
gateways/zgate/build.py:135:         return check_subsystem(EXE)
gateways/zgate/build.py:136:     print("== 构建 zgate ==")
gateways/zgate/build.py:137:     return build_native()
.github/workflows/ci.yml:43:       - name: Go 格式
.github/workflows/ci.yml:44:         # 失败时列出具体文件，避免只看到 exit 1 还得本地复现排查。
.github/workflows/ci.yml:45:         run: |
.github/workflows/ci.yml:46:           unformatted=$(gofmt -l gateways/zgate)
.github/workflows/ci.yml:47:           if [ -n "$unformatted" ]; then
.github/workflows/ci.yml:48:             echo "::error::以下文件未过 gofmt（先 gofmt -w 再提交）："
.github/workflows/ci.yml:49:             echo "$unformatted"
.github/workflows/ci.yml:50:             exit 1
.github/workflows/ci.yml:51:           fi
.github/workflows/ci.yml:52: 
.github/workflows/ci.yml:53:       - name: Go 构建与测试
.github/workflows/ci.yml:54:         working-directory: gateways/zgate
.github/workflows/ci.yml:55:         run: go build ./... && go test ./...
.github/workflows/ci.yml:56: 
.github/workflows/ci.yml:57:       - name: zgate 无窗产物校验（PE Subsystem 必须为 GUI）
.github/workflows/ci.yml:58:         # 交叉编译一份 windows/amd64 出来，校验 PE 头的 Subsystem = 2（WINDOWS_GUI）。
.github/workflows/ci.yml:59:         # 忘了 -H windowsgui 会退回 CONSOLE(3)，开机自启就弹 cmd 窗口。机制见 docs/PITFALLS.md §20。
.github/workflows/ci.yml:60:         run: python3 gateways/zgate/build.py --cross-check
gateways/zgate/.restart.log:1: ﻿start 2026-11-09T13:48:24.1140359+08:00
gateways/zgate/.restart.log:2: OK swapped 2026-11-09T13:48:46.2137899+08:00
```

构建产物与替换痕迹（`Get-FileHash` / `Get-Item` 真实输出）：
```text

FullName                                                            Length CreationTime       LastWriteTime     
--------                                                            ------ ------------       -------------     
F:\Project\ModelBus\gateways\zgate\zgate.exe                      10516480 2026/11/9 14:49:36 2026/11/9 14:49:36
F:\Project\ModelBus\gateways\zgate\zgate.exe.prev                  7415808 2026/11/9 13:48:44 2026/11/9 12:50:48
F:\Project\ModelBus\gateways\zgate\zgate.exe~                     10508800 2026/11/9 14:10:00 2026/11/9 14:23:42
F:\Project\ModelBus\gateways\zgate\zgate.exe.bak-20261109          7415808 2026/11/9 12:59:27 2026/11/9 12:50:48
F:\Project\ModelBus\gateways\zgate\zgate.exe.bak-20261109-lonehop 10508800 2026/11/9 14:23:48 2026/11/9 14:23:42
F:\Project\ModelBus\gateways\zgate\.restart.log                         90 2026/11/9 13:14:40 2026/11/9 13:48:46




Path                                                              Hash                                                            
----                                                              ----                                                            
F:\Project\ModelBus\gateways\zgate\zgate.exe                      D4FD43805F0691AC8CA8EFCC4FB7DCED3B0EEDA6AAD35227717D630A41E039CC
F:\Project\ModelBus\gateways\zgate\zgate.exe.prev                 DC39F88CB116108956BDDB2E68B19ABB3F483F3CEDFA8F9BABF149E96C9C2465
F:\Project\ModelBus\gateways\zgate\zgate.exe.bak-20261109         DC39F88CB116108956BDDB2E68B19ABB3F483F3CEDFA8F9BABF149E96C9C2465
F:\Project\ModelBus\gateways\zgate\zgate.exe.bak-20261109-lonehop FB700059C2C36BCBAB9D897250BDFEC0BEF068E31D2312AFC1A37F5ED9D95EAD




```

PE 子系统校验（`build.py --check` 真实输出）：
命令：```text
CMD: python gateways/zgate/build.py --check
```
exitCode=0；stdout 110 字符
真实输出（stdout）：
```text
== У�����в��� ==
[ OK ] Subsystem = 2 �� WINDOWS_GUI���޴���    F:\Project\ModelBus\gateways\zgate\zgate.exe

```

## 2. `gateways/zgate/internal/winproc/` 四文件全文语义（逐字签名）

用户点名的四个文件均存在；目录里还有第五个公共文件 `winproc.go` 与两个 `.bak-20261109-detach` 备份。下面签名与常量逐字取自当前磁盘。

### 2.1 `console_other.go`（`//go:build !windows`）
```text
gateways/zgate/internal/winproc/console_other.go:1: //go:build !windows
gateways/zgate/internal/winproc/console_other.go:2: 
gateways/zgate/internal/winproc/console_other.go:3: package winproc
gateways/zgate/internal/winproc/console_other.go:4: 
gateways/zgate/internal/winproc/console_other.go:5: // AttachParentConsole is a no-op outside Windows.
gateways/zgate/internal/winproc/console_other.go:6: func AttachParentConsole() bool { return true }
gateways/zgate/internal/winproc/console_other.go:7: 
gateways/zgate/internal/winproc/console_other.go:8: // DetachConsole is a no-op outside Windows.
gateways/zgate/internal/winproc/console_other.go:9: func DetachConsole() bool { return false }
```
- 语义：非 Windows 下 `AttachParentConsole()` 直接返回 `true`、`DetachConsole()` 返回 `false`；无 `FreeConsole`、无进程标志。

### 2.2 `console_windows.go`（`//go:build windows`）
```text
gateways/zgate/internal/winproc/console_windows.go:1: //go:build windows
gateways/zgate/internal/winproc/console_windows.go:2: 
gateways/zgate/internal/winproc/console_windows.go:3: package winproc
gateways/zgate/internal/winproc/console_windows.go:4: 
gateways/zgate/internal/winproc/console_windows.go:5: import (
gateways/zgate/internal/winproc/console_windows.go:6: 	"os"
gateways/zgate/internal/winproc/console_windows.go:7: 	"syscall"
gateways/zgate/internal/winproc/console_windows.go:8: )
gateways/zgate/internal/winproc/console_windows.go:9: 
gateways/zgate/internal/winproc/console_windows.go:10: const (
gateways/zgate/internal/winproc/console_windows.go:11: 	attachParentProcess = ^uintptr(0) // (DWORD)-1
gateways/zgate/internal/winproc/console_windows.go:12: 
gateways/zgate/internal/winproc/console_windows.go:13: 	stdOutputHandle = ^uintptr(10) // (DWORD)-11, STD_OUTPUT_HANDLE
gateways/zgate/internal/winproc/console_windows.go:14: 
gateways/zgate/internal/winproc/console_windows.go:15: 	fileTypeUnknown = 0 // invalid handle
gateways/zgate/internal/winproc/console_windows.go:16: 	fileTypeDisk    = 1 // redirection to a file
gateways/zgate/internal/winproc/console_windows.go:17: 	fileTypeChar    = 2 // console screen buffer
gateways/zgate/internal/winproc/console_windows.go:18: 	fileTypePipe    = 3 // mintty / CI / child_process
gateways/zgate/internal/winproc/console_windows.go:19: )
gateways/zgate/internal/winproc/console_windows.go:20: 
gateways/zgate/internal/winproc/console_windows.go:21: var (
gateways/zgate/internal/winproc/console_windows.go:22: 	procAttachConsole = kernel32.NewProc("AttachConsole")
gateways/zgate/internal/winproc/console_windows.go:23: 	procGetStdHandle  = kernel32.NewProc("GetStdHandle")
gateways/zgate/internal/winproc/console_windows.go:24: 	procGetFileType   = kernel32.NewProc("GetFileType")
gateways/zgate/internal/winproc/console_windows.go:25: 	procFreeConsole   = kernel32.NewProc("FreeConsole")
gateways/zgate/internal/winproc/console_windows.go:26: )
gateways/zgate/internal/winproc/console_windows.go:27: 
gateways/zgate/internal/winproc/console_windows.go:28: // AttachParentConsole rebinds stdout/stderr to the terminal that launched us.
gateways/zgate/internal/winproc/console_windows.go:29: //
gateways/zgate/internal/winproc/console_windows.go:30: // zgate is built as a GUI-subsystem binary so autostart never flashes a console
gateways/zgate/internal/winproc/console_windows.go:31: // window. Inherited handles that already work — pipes (mintty, CI, scripts) and
gateways/zgate/internal/winproc/console_windows.go:32: // file redirections — must be left alone, or output would be swallowed by a
gateways/zgate/internal/winproc/console_windows.go:33: // hidden conhost and `zgate status > file` would be empty. Only when stdout is
gateways/zgate/internal/winproc/console_windows.go:34: // unusable or a raw console handle do we attach to the parent's console, so
gateways/zgate/internal/winproc/console_windows.go:35: // running from cmd / PowerShell still prints.
gateways/zgate/internal/winproc/console_windows.go:36: //
gateways/zgate/internal/winproc/console_windows.go:37: // The catch: a Windows console window closes with its last attached process.
gateways/zgate/internal/winproc/console_windows.go:38: // Since zgate survives the shell that started it (closing the console does not
gateways/zgate/internal/winproc/console_windows.go:39: // kill it — only Ctrl+C or taskkill does), an attached console would sit there
gateways/zgate/internal/winproc/console_windows.go:40: // half-dead for as long as the gateway runs. DetachConsole undoes the attach
gateways/zgate/internal/winproc/console_windows.go:41: // once the boot banner is out, which keeps the terminal readable and gives the
gateways/zgate/internal/winproc/console_windows.go:42: // console window back to its shell.
gateways/zgate/internal/winproc/console_windows.go:43: func AttachParentConsole() bool {
gateways/zgate/internal/winproc/console_windows.go:44: 	if keepInheritedStdio() {
gateways/zgate/internal/winproc/console_windows.go:45: 		return true
gateways/zgate/internal/winproc/console_windows.go:46: 	}
gateways/zgate/internal/winproc/console_windows.go:47: 	ok, _, _ := procAttachConsole.Call(attachParentProcess)
gateways/zgate/internal/winproc/console_windows.go:48: 	if ok == 0 {
gateways/zgate/internal/winproc/console_windows.go:49: 		return false
gateways/zgate/internal/winproc/console_windows.go:50: 	}
gateways/zgate/internal/winproc/console_windows.go:51: 	if out, err := os.OpenFile("CONOUT$", os.O_WRONLY, 0); err == nil {
gateways/zgate/internal/winproc/console_windows.go:52: 		os.Stdout = out
gateways/zgate/internal/winproc/console_windows.go:53: 		os.Stderr = out
gateways/zgate/internal/winproc/console_windows.go:54: 	}
gateways/zgate/internal/winproc/console_windows.go:55: 	return true
gateways/zgate/internal/winproc/console_windows.go:56: }
gateways/zgate/internal/winproc/console_windows.go:57: 
gateways/zgate/internal/winproc/console_windows.go:58: // DetachConsole releases a console taken by AttachParentConsole: output keeps
gateways/zgate/internal/winproc/console_windows.go:59: // going to the zgate log file, and the shell's window is free to close.
gateways/zgate/internal/winproc/console_windows.go:60: //
gateways/zgate/internal/winproc/console_windows.go:61: // Handles we inherited (pipe / file) are left alone — detaching would break a
gateways/zgate/internal/winproc/console_windows.go:62: // caller that deliberately captured our output. A failed detach is harmless:
gateways/zgate/internal/winproc/console_windows.go:63: // the process keeps running, the console simply stays shared.
gateways/zgate/internal/winproc/console_windows.go:64: func DetachConsole() bool {
gateways/zgate/internal/winproc/console_windows.go:65: 	if keepInheritedStdio() {
gateways/zgate/internal/winproc/console_windows.go:66: 		return false
gateways/zgate/internal/winproc/console_windows.go:67: 	}
gateways/zgate/internal/winproc/console_windows.go:68: 	ok, _, _ := procFreeConsole.Call()
gateways/zgate/internal/winproc/console_windows.go:69: 	return ok != 0
gateways/zgate/internal/winproc/console_windows.go:70: }
gateways/zgate/internal/winproc/console_windows.go:71: 
gateways/zgate/internal/winproc/console_windows.go:72: func keepInheritedStdio() bool {
gateways/zgate/internal/winproc/console_windows.go:73: 	out, _, _ := procGetStdHandle.Call(stdOutputHandle)
gateways/zgate/internal/winproc/console_windows.go:74: 	if out == 0 {
gateways/zgate/internal/winproc/console_windows.go:75: 		return false
gateways/zgate/internal/winproc/console_windows.go:76: 	}
gateways/zgate/internal/winproc/console_windows.go:77: 	ft, _, _ := procGetFileType.Call(out)
gateways/zgate/internal/winproc/console_windows.go:78: 	switch uintptr(ft) {
gateways/zgate/internal/winproc/console_windows.go:79: 	case fileTypeDisk, fileTypePipe:
gateways/zgate/internal/winproc/console_windows.go:80: 		return true
gateways/zgate/internal/winproc/console_windows.go:81: 	default: // unknown (invalid) or char (console): try attaching instead
gateways/zgate/internal/winproc/console_windows.go:82: 		return false
gateways/zgate/internal/winproc/console_windows.go:83: 	}
gateways/zgate/internal/winproc/console_windows.go:84: }
gateways/zgate/internal/winproc/console_windows.go:85: 
gateways/zgate/internal/winproc/console_windows.go:86: var _ = syscall.Handle(0)
```
- 有 `FreeConsole`：`:25 procFreeConsole = kernel32.NewProc("FreeConsole")`、`:64 func DetachConsole() bool`、`:68 ok, _, _ := procFreeConsole.Call()`。
- 有父控制台附着：`:22 procAttachConsole = kernel32.NewProc("AttachConsole")`、`:43 func AttachParentConsole() bool`、`:47 procAttachConsole.Call(attachParentProcess)`，随后 `os.OpenFile("CONOUT$", ...)` 重绑 `os.Stdout/os.Stderr`。
- 无 `SetConsoleCtrlHandler`、无 `GenerateConsoleCtrlEvent`、无 `ShowWindow/SW_HIDE`、无 `CREATE_*` 常量（那些在 `winproc_windows.go`）。
- 注释 `:37-42` 明确设计前提：`Since zgate survives the shell that started it (closing the console does not kill it — only Ctrl+C or taskkill does)`；`DetachConsole undoes the attach once the boot banner is out`，即启动横幅打完后释放控制台，避免 CMD 窗口因最后一个附着进程不退而「半死」挂着。

### 2.3 `winproc_other.go`（`//go:build !windows`）
```text
gateways/zgate/internal/winproc/winproc_other.go:1: //go:build !windows
gateways/zgate/internal/winproc/winproc_other.go:2: 
gateways/zgate/internal/winproc/winproc_other.go:3: package winproc
gateways/zgate/internal/winproc/winproc_other.go:4: 
gateways/zgate/internal/winproc/winproc_other.go:5: import (
gateways/zgate/internal/winproc/winproc_other.go:6: 	"net"
gateways/zgate/internal/winproc/winproc_other.go:7: 	"os"
gateways/zgate/internal/winproc/winproc_other.go:8: 	"os/exec"
gateways/zgate/internal/winproc/winproc_other.go:9: 	"syscall"
gateways/zgate/internal/winproc/winproc_other.go:10: 	"time"
gateways/zgate/internal/winproc/winproc_other.go:11: )
gateways/zgate/internal/winproc/winproc_other.go:12: 
gateways/zgate/internal/winproc/winproc_other.go:13: func (p *Process) start() error {
gateways/zgate/internal/winproc/winproc_other.go:14: 	p.cmd.SysProcAttr = nil
gateways/zgate/internal/winproc/winproc_other.go:15: 	return p.cmd.Start()
gateways/zgate/internal/winproc/winproc_other.go:16: }
gateways/zgate/internal/winproc/winproc_other.go:17: 
gateways/zgate/internal/winproc/winproc_other.go:18: func (p *Process) kill() error {
gateways/zgate/internal/winproc/winproc_other.go:19: 	if p == nil || p.cmd.Process == nil {
gateways/zgate/internal/winproc/winproc_other.go:20: 		return nil
gateways/zgate/internal/winproc/winproc_other.go:21: 	}
gateways/zgate/internal/winproc/winproc_other.go:22: 	return p.cmd.Process.Kill()
gateways/zgate/internal/winproc/winproc_other.go:23: }
gateways/zgate/internal/winproc/winproc_other.go:24: 
gateways/zgate/internal/winproc/winproc_other.go:25: func (p *Process) release() {}
gateways/zgate/internal/winproc/winproc_other.go:26: 
gateways/zgate/internal/winproc/winproc_other.go:27: // PortBusy reports whether something accepts connections on the loopback port.
gateways/zgate/internal/winproc/winproc_other.go:28: func PortBusy(port int) bool {
gateways/zgate/internal/winproc/winproc_other.go:29: 	conn, err := net.DialTimeout("tcp", listenAddr(port), 300*time.Millisecond)
gateways/zgate/internal/winproc/winproc_other.go:30: 	if err != nil {
gateways/zgate/internal/winproc/winproc_other.go:31: 		return false
gateways/zgate/internal/winproc/winproc_other.go:32: 	}
gateways/zgate/internal/winproc/winproc_other.go:33: 	_ = conn.Close()
gateways/zgate/internal/winproc/winproc_other.go:34: 	return true
gateways/zgate/internal/winproc/winproc_other.go:35: }
gateways/zgate/internal/winproc/winproc_other.go:36: 
gateways/zgate/internal/winproc/winproc_other.go:37: // detachedAttr has no effect outside Windows; the child simply inherits.
gateways/zgate/internal/winproc/winproc_other.go:38: func DetachedAttr() *syscall.SysProcAttr { return nil }
gateways/zgate/internal/winproc/winproc_other.go:39: 
gateways/zgate/internal/winproc/winproc_other.go:40: var _ = exec.Command
gateways/zgate/internal/winproc/winproc_other.go:41: 
gateways/zgate/internal/winproc/winproc_other.go:42: // ProcessAlive reports whether pid still names a running process.
gateways/zgate/internal/winproc/winproc_other.go:43: func ProcessAlive(pid uint32) bool {
gateways/zgate/internal/winproc/winproc_other.go:44: 	if pid == 0 {
gateways/zgate/internal/winproc/winproc_other.go:45: 		return false
gateways/zgate/internal/winproc/winproc_other.go:46: 	}
gateways/zgate/internal/winproc/winproc_other.go:47: 	p, err := os.FindProcess(int(pid))
gateways/zgate/internal/winproc/winproc_other.go:48: 	if err != nil {
gateways/zgate/internal/winproc/winproc_other.go:49: 		return false
gateways/zgate/internal/winproc/winproc_other.go:50: 	}
gateways/zgate/internal/winproc/winproc_other.go:51: 	return p.Signal(syscall.Signal(0)) == nil
gateways/zgate/internal/winproc/winproc_other.go:52: }
```
- 签名：`func (p *Process) start() error`、`func (p *Process) kill() error`、`func (p *Process) release()`、`func PortBusy(port int) bool`、`func DetachedAttr() *syscall.SysProcAttr { return nil }`、`func ProcessAlive(pid uint32) bool`。非 Windows 无 Job Object、无 DETACHED。

### 2.4 `winproc_windows.go`（`//go:build windows`）
```text
gateways/zgate/internal/winproc/winproc_windows.go:1: //go:build windows
gateways/zgate/internal/winproc/winproc_windows.go:2: 
gateways/zgate/internal/winproc/winproc_windows.go:3: package winproc
gateways/zgate/internal/winproc/winproc_windows.go:4: 
gateways/zgate/internal/winproc/winproc_windows.go:5: import (
gateways/zgate/internal/winproc/winproc_windows.go:6: 	"net"
gateways/zgate/internal/winproc/winproc_windows.go:7: 	"syscall"
gateways/zgate/internal/winproc/winproc_windows.go:8: 	"time"
gateways/zgate/internal/winproc/winproc_windows.go:9: 	"unsafe"
gateways/zgate/internal/winproc/winproc_windows.go:10: )
gateways/zgate/internal/winproc/winproc_windows.go:11: 
gateways/zgate/internal/winproc/winproc_windows.go:12: const (
gateways/zgate/internal/winproc/winproc_windows.go:13: 	createNoWindow = 0x08000000
gateways/zgate/internal/winproc/winproc_windows.go:14: 	createNewGroup = 0x00000200
gateways/zgate/internal/winproc/winproc_windows.go:15: 	detachedProcess = 0x00000008
gateways/zgate/internal/winproc/winproc_windows.go:16: 
gateways/zgate/internal/winproc/winproc_windows.go:17: 	jobObjectExtendedLimitInformation = 9
gateways/zgate/internal/winproc/winproc_windows.go:18: 	jobObjectLimitKillOnJobClose      = 0x00002000
gateways/zgate/internal/winproc/winproc_windows.go:19: 
gateways/zgate/internal/winproc/winproc_windows.go:20: 	processAllAccess = 0x1F0FFF
gateways/zgate/internal/winproc/winproc_windows.go:21: )
gateways/zgate/internal/winproc/winproc_windows.go:22: 
gateways/zgate/internal/winproc/winproc_windows.go:23: var (
gateways/zgate/internal/winproc/winproc_windows.go:24: 	kernel32                 = syscall.NewLazyDLL("kernel32.dll")
gateways/zgate/internal/winproc/winproc_windows.go:25: 	procCreateJobObjectW     = kernel32.NewProc("CreateJobObjectW")
gateways/zgate/internal/winproc/winproc_windows.go:26: 	procSetInformationJobObj = kernel32.NewProc("SetInformationJobObject")
gateways/zgate/internal/winproc/winproc_windows.go:27: 	procAssignProcessToJob   = kernel32.NewProc("AssignProcessToJobObject")
gateways/zgate/internal/winproc/winproc_windows.go:28: 	procTerminateJobObject   = kernel32.NewProc("TerminateJobObject")
gateways/zgate/internal/winproc/winproc_windows.go:29: 	procCloseHandle          = kernel32.NewProc("CloseHandle")
gateways/zgate/internal/winproc/winproc_windows.go:30: 	procOpenProcess          = kernel32.NewProc("OpenProcess")
gateways/zgate/internal/winproc/winproc_windows.go:31: 	procGetExitCodeProcess   = kernel32.NewProc("GetExitCodeProcess")
gateways/zgate/internal/winproc/winproc_windows.go:32: )
gateways/zgate/internal/winproc/winproc_windows.go:33: 
gateways/zgate/internal/winproc/winproc_windows.go:34: type jobBasicLimit struct {
gateways/zgate/internal/winproc/winproc_windows.go:35: 	PerProcessUserTimeLimit int64
gateways/zgate/internal/winproc/winproc_windows.go:36: 	PerJobUserTimeLimit     int64
gateways/zgate/internal/winproc/winproc_windows.go:37: 	LimitFlags              uint32
gateways/zgate/internal/winproc/winproc_windows.go:38: 	MinimumWorkingSetSize   uintptr
gateways/zgate/internal/winproc/winproc_windows.go:39: 	MaximumWorkingSetSize   uintptr
gateways/zgate/internal/winproc/winproc_windows.go:40: 	ActiveProcessLimit      uint32
gateways/zgate/internal/winproc/winproc_windows.go:41: 	Affinity                uintptr
gateways/zgate/internal/winproc/winproc_windows.go:42: 	PriorityClass           uint32
gateways/zgate/internal/winproc/winproc_windows.go:43: 	SchedulingClass         uint32
gateways/zgate/internal/winproc/winproc_windows.go:44: }
gateways/zgate/internal/winproc/winproc_windows.go:45: 
gateways/zgate/internal/winproc/winproc_windows.go:46: type ioCounters struct {
gateways/zgate/internal/winproc/winproc_windows.go:47: 	ReadOperationCount  uint64
gateways/zgate/internal/winproc/winproc_windows.go:48: 	WriteOperationCount uint64
gateways/zgate/internal/winproc/winproc_windows.go:49: 	OtherOperationCount uint64
gateways/zgate/internal/winproc/winproc_windows.go:50: 	ReadTransferCount   uint64
gateways/zgate/internal/winproc/winproc_windows.go:51: 	WriteTransferCount  uint64
gateways/zgate/internal/winproc/winproc_windows.go:52: 	OtherTransferCount  uint64
gateways/zgate/internal/winproc/winproc_windows.go:53: }
gateways/zgate/internal/winproc/winproc_windows.go:54: 
gateways/zgate/internal/winproc/winproc_windows.go:55: type jobExtendedLimit struct {
gateways/zgate/internal/winproc/winproc_windows.go:56: 	BasicLimitInformation jobBasicLimit
gateways/zgate/internal/winproc/winproc_windows.go:57: 	IOInfo                ioCounters
gateways/zgate/internal/winproc/winproc_windows.go:58: 	ProcessMemoryLimit    uintptr
gateways/zgate/internal/winproc/winproc_windows.go:59: 	JobMemoryLimit        uintptr
gateways/zgate/internal/winproc/winproc_windows.go:60: 	PeakProcessMemoryUsed uintptr
gateways/zgate/internal/winproc/winproc_windows.go:61: 	PeakJobMemoryUsed     uintptr
gateways/zgate/internal/winproc/winproc_windows.go:62: }
gateways/zgate/internal/winproc/winproc_windows.go:63: 
gateways/zgate/internal/winproc/winproc_windows.go:64: func (p *Process) start() error {
gateways/zgate/internal/winproc/winproc_windows.go:65: 	p.cmd.SysProcAttr = &syscall.SysProcAttr{
gateways/zgate/internal/winproc/winproc_windows.go:66: 		CreationFlags: createNoWindow | createNewGroup,
gateways/zgate/internal/winproc/winproc_windows.go:67: 		HideWindow:    true,
gateways/zgate/internal/winproc/winproc_windows.go:68: 	}
gateways/zgate/internal/winproc/winproc_windows.go:69: 	if err := p.cmd.Start(); err != nil {
gateways/zgate/internal/winproc/winproc_windows.go:70: 		return err
gateways/zgate/internal/winproc/winproc_windows.go:71: 	}
gateways/zgate/internal/winproc/winproc_windows.go:72: 
gateways/zgate/internal/winproc/winproc_windows.go:73: 	job, _, _ := procCreateJobObjectW.Call(0, 0)
gateways/zgate/internal/winproc/winproc_windows.go:74: 	if job == 0 {
gateways/zgate/internal/winproc/winproc_windows.go:75: 		return nil
gateways/zgate/internal/winproc/winproc_windows.go:76: 	}
gateways/zgate/internal/winproc/winproc_windows.go:77: 	info := jobExtendedLimit{}
gateways/zgate/internal/winproc/winproc_windows.go:78: 	info.BasicLimitInformation.LimitFlags = jobObjectLimitKillOnJobClose
gateways/zgate/internal/winproc/winproc_windows.go:79: 	procSetInformationJobObj.Call(
gateways/zgate/internal/winproc/winproc_windows.go:80: 		job,
gateways/zgate/internal/winproc/winproc_windows.go:81: 		uintptr(jobObjectExtendedLimitInformation),
gateways/zgate/internal/winproc/winproc_windows.go:82: 		uintptr(unsafe.Pointer(&info)),
gateways/zgate/internal/winproc/winproc_windows.go:83: 		unsafe.Sizeof(info),
gateways/zgate/internal/winproc/winproc_windows.go:84: 	)
gateways/zgate/internal/winproc/winproc_windows.go:85: 	// Assigning can fail if the child already exited; that is not fatal.
gateways/zgate/internal/winproc/winproc_windows.go:86: 	if ph, err := syscall.OpenProcess(processAllAccess, false, uint32(p.cmd.Process.Pid)); err == nil {
gateways/zgate/internal/winproc/winproc_windows.go:87: 		procAssignProcessToJob.Call(job, uintptr(ph))
gateways/zgate/internal/winproc/winproc_windows.go:88: 		procCloseHandle.Call(uintptr(ph))
gateways/zgate/internal/winproc/winproc_windows.go:89: 	}
gateways/zgate/internal/winproc/winproc_windows.go:90: 	p.job = job
gateways/zgate/internal/winproc/winproc_windows.go:91: 	return nil
gateways/zgate/internal/winproc/winproc_windows.go:92: }
gateways/zgate/internal/winproc/winproc_windows.go:93: 
gateways/zgate/internal/winproc/winproc_windows.go:94: func (p *Process) kill() error {
gateways/zgate/internal/winproc/winproc_windows.go:95: 	if p == nil || p.cmd.Process == nil {
gateways/zgate/internal/winproc/winproc_windows.go:96: 		return nil
gateways/zgate/internal/winproc/winproc_windows.go:97: 	}
gateways/zgate/internal/winproc/winproc_windows.go:98: 	if p.job != 0 {
gateways/zgate/internal/winproc/winproc_windows.go:99: 		procTerminateJobObject.Call(p.job, 1)
gateways/zgate/internal/winproc/winproc_windows.go:100: 	}
gateways/zgate/internal/winproc/winproc_windows.go:101: 	return p.cmd.Process.Kill()
gateways/zgate/internal/winproc/winproc_windows.go:102: }
gateways/zgate/internal/winproc/winproc_windows.go:103: 
gateways/zgate/internal/winproc/winproc_windows.go:104: func (p *Process) release() {
gateways/zgate/internal/winproc/winproc_windows.go:105: 	if p.job != 0 {
gateways/zgate/internal/winproc/winproc_windows.go:106: 		procCloseHandle.Call(p.job)
gateways/zgate/internal/winproc/winproc_windows.go:107: 		p.job = 0
gateways/zgate/internal/winproc/winproc_windows.go:108: 	}
gateways/zgate/internal/winproc/winproc_windows.go:109: }
gateways/zgate/internal/winproc/winproc_windows.go:110: 
gateways/zgate/internal/winproc/winproc_windows.go:111: // PortBusy reports whether something accepts connections on the loopback port.
gateways/zgate/internal/winproc/winproc_windows.go:112: //
gateways/zgate/internal/winproc/winproc_windows.go:113: // A plain bind() is not enough on Windows: the gateway binds 0.0.0.0:7863 and a
gateways/zgate/internal/winproc/winproc_windows.go:114: // second listen on 127.0.0.1:7863 still succeeds, which made zgate think the
gateways/zgate/internal/winproc/winproc_windows.go:115: // port was free while wb2api was serving on it.
gateways/zgate/internal/winproc/winproc_windows.go:116: func PortBusy(port int) bool {
gateways/zgate/internal/winproc/winproc_windows.go:117: 	conn, err := net.DialTimeout("tcp", listenAddr(port), 300*time.Millisecond)
gateways/zgate/internal/winproc/winproc_windows.go:118: 	if err != nil {
gateways/zgate/internal/winproc/winproc_windows.go:119: 		return false
gateways/zgate/internal/winproc/winproc_windows.go:120: 	}
gateways/zgate/internal/winproc/winproc_windows.go:121: 	_ = conn.Close()
gateways/zgate/internal/winproc/winproc_windows.go:122: 	return true
gateways/zgate/internal/winproc/winproc_windows.go:123: }
gateways/zgate/internal/winproc/winproc_windows.go:124: 
gateways/zgate/internal/winproc/winproc_windows.go:125: // detachedAttr keeps a child alive after the launching console disappears:
gateways/zgate/internal/winproc/winproc_windows.go:126: // the child gets no console at all, so a console-window close cannot send it
gateways/zgate/internal/winproc/winproc_windows.go:127: // CTRL_CLOSE_EVENT, and the parent may exit immediately after Start.
gateways/zgate/internal/winproc/winproc_windows.go:128: func DetachedAttr() *syscall.SysProcAttr {
gateways/zgate/internal/winproc/winproc_windows.go:129: 	return &syscall.SysProcAttr{
gateways/zgate/internal/winproc/winproc_windows.go:130: 		CreationFlags: detachedProcess | createNewGroup | createNoWindow,
gateways/zgate/internal/winproc/winproc_windows.go:131: 		HideWindow:    true,
gateways/zgate/internal/winproc/winproc_windows.go:132: 	}
gateways/zgate/internal/winproc/winproc_windows.go:133: }
gateways/zgate/internal/winproc/winproc_windows.go:134: 
gateways/zgate/internal/winproc/winproc_windows.go:135: const (
gateways/zgate/internal/winproc/winproc_windows.go:136: 	processQueryLimitedInformation = 0x1000
gateways/zgate/internal/winproc/winproc_windows.go:137: 	stillActive                    = 259
gateways/zgate/internal/winproc/winproc_windows.go:138: )
gateways/zgate/internal/winproc/winproc_windows.go:139: 
gateways/zgate/internal/winproc/winproc_windows.go:140: // ProcessAlive reports whether pid still names a running process.
gateways/zgate/internal/winproc/winproc_windows.go:141: //
gateways/zgate/internal/winproc/winproc_windows.go:142: // OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION) works for processes in any
gateways/zgate/internal/winproc/winproc_windows.go:143: // session, which is what the -tray launcher needs: its parent may be a
gateways/zgate/internal/winproc/winproc_windows.go:144: // terminal in another session. A PID can be reused, but the launcher is our
gateways/zgate/internal/winproc/winproc_windows.go:145: // direct parent and the check runs every two seconds, so the window is tiny.
gateways/zgate/internal/winproc/winproc_windows.go:146: func ProcessAlive(pid uint32) bool {
gateways/zgate/internal/winproc/winproc_windows.go:147: 	if pid == 0 {
gateways/zgate/internal/winproc/winproc_windows.go:148: 		return false
gateways/zgate/internal/winproc/winproc_windows.go:149: 	}
gateways/zgate/internal/winproc/winproc_windows.go:150: 	h, _, _ := procOpenProcess.Call(processQueryLimitedInformation, 0, uintptr(pid))
gateways/zgate/internal/winproc/winproc_windows.go:151: 	if h == 0 {
gateways/zgate/internal/winproc/winproc_windows.go:152: 		return false
gateways/zgate/internal/winproc/winproc_windows.go:153: 	}
gateways/zgate/internal/winproc/winproc_windows.go:154: 	defer procCloseHandle.Call(h)
gateways/zgate/internal/winproc/winproc_windows.go:155: 	var code uint32
gateways/zgate/internal/winproc/winproc_windows.go:156: 	ok, _, _ := procGetExitCodeProcess.Call(h, uintptr(unsafe.Pointer(&code)))
gateways/zgate/internal/winproc/winproc_windows.go:157: 	if ok == 0 {
gateways/zgate/internal/winproc/winproc_windows.go:158: 		return true // handle valid but query failed: assume alive, do not kill
gateways/zgate/internal/winproc/winproc_windows.go:159: 	}
gateways/zgate/internal/winproc/winproc_windows.go:160: 	return code == stillActive
gateways/zgate/internal/winproc/winproc_windows.go:161: }
```
- 常量逐字：`:13 createNoWindow = 0x08000000`、`:14 createNewGroup = 0x00000200`、`:15 detachedProcess = 0x00000008`、`:18 jobObjectLimitKillOnJobClose = 0x00002000`、`:20 processAllAccess = 0x1F0FFF`、`:136 processQueryLimitedInformation = 0x1000`、`:137 stillActive = 259`。
- **有 `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP`（:65-68）**：`func (p *Process) start() error` 里 `p.cmd.SysProcAttr = &syscall.SysProcAttr{ CreationFlags: createNoWindow | createNewGroup, HideWindow: true }`，随后 `CreateJobObjectW` + `SetInformationJobObject(JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)` + `AssignProcessToJobObject`（:73-90）。
- **有 `DETACHED_PROCESS`（:128-132）**：`func DetachedAttr() *syscall.SysProcAttr` 返回 `CreationFlags: detachedProcess | createNewGroup | createNoWindow, HideWindow: true`；注释 `:125-127` 写明「child gets no console at all, so a console-window close cannot send it CTRL_CLOSE_EVENT」。
- **无 `CREATE_BREAKAWAY_FROM_JOB`**：全文件无该常量/标志；相反 `:18` 用的是 `KILL_ON_JOB_CLOSE`，`winproc.go:3-5` 注释强调关闭 zgate 会把子进程一起带走、避免孤儿占 7863/8790。
- **无 `SetConsoleCtrlHandler`**：zgate 的信号处理在 `main.go:209-210 signal.Notify(sig, os.Interrupt, syscall.SIGTERM)`，不是 Win32 console control handler。
- 隐藏窗口：`HideWindow: true`（:67、:131）+ `createNoWindow`；GUI 子系统由 `build.py` 的 `-H windowsgui` 在链接期保证，二者配合避免登录自启弹 CMD 窗口。

### 2.5 公共 `winproc.go`
```text
gateways/zgate/internal/winproc/winproc.go:1: // Package winproc starts and stops child processes.
gateways/zgate/internal/winproc/winproc.go:2: //
gateways/zgate/internal/winproc/winproc.go:3: // On Windows every child is put into its own Job Object with
gateways/zgate/internal/winproc/winproc.go:4: // JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, so closing zgate (or crashing it) takes the
gateways/zgate/internal/winproc/winproc.go:5: // children down with it instead of leaving orphans holding 7863 / 8790.
gateways/zgate/internal/winproc/winproc.go:6: package winproc
gateways/zgate/internal/winproc/winproc.go:7: 
gateways/zgate/internal/winproc/winproc.go:8: import (
gateways/zgate/internal/winproc/winproc.go:9: 	"io"
gateways/zgate/internal/winproc/winproc.go:10: 	"os/exec"
gateways/zgate/internal/winproc/winproc.go:11: 	"strconv"
gateways/zgate/internal/winproc/winproc.go:12: 	"sync"
gateways/zgate/internal/winproc/winproc.go:13: )
gateways/zgate/internal/winproc/winproc.go:14: 
gateways/zgate/internal/winproc/winproc.go:15: func listenAddr(port int) string { return "127.0.0.1:" + strconv.Itoa(port) }
gateways/zgate/internal/winproc/winproc.go:16: 
gateways/zgate/internal/winproc/winproc.go:17: // Process is a supervised child.
gateways/zgate/internal/winproc/winproc.go:18: type Process struct {
gateways/zgate/internal/winproc/winproc.go:19: 	cmd      *exec.Cmd
gateways/zgate/internal/winproc/winproc.go:20: 	job      uintptr
gateways/zgate/internal/winproc/winproc.go:21: 	releaseO sync.Once
gateways/zgate/internal/winproc/winproc.go:22: 	done     chan struct{}
gateways/zgate/internal/winproc/winproc.go:23: 	err      error
gateways/zgate/internal/winproc/winproc.go:24: }
gateways/zgate/internal/winproc/winproc.go:25: 
gateways/zgate/internal/winproc/winproc.go:26: // Start launches exe in dir with args, wiring stdout/stderr to out/errOut.
gateways/zgate/internal/winproc/winproc.go:27: func Start(exe string, args []string, dir string, out, errOut io.Writer) (*Process, error) {
gateways/zgate/internal/winproc/winproc.go:28: 	cmd := exec.Command(exe, args...)
gateways/zgate/internal/winproc/winproc.go:29: 	cmd.Dir = dir
gateways/zgate/internal/winproc/winproc.go:30: 	cmd.Stdout = out
gateways/zgate/internal/winproc/winproc.go:31: 	cmd.Stderr = errOut
gateways/zgate/internal/winproc/winproc.go:32: 	p := &Process{cmd: cmd, done: make(chan struct{})}
gateways/zgate/internal/winproc/winproc.go:33: 	if err := p.start(); err != nil {
gateways/zgate/internal/winproc/winproc.go:34: 		return nil, err
gateways/zgate/internal/winproc/winproc.go:35: 	}
gateways/zgate/internal/winproc/winproc.go:36: 	go func() {
gateways/zgate/internal/winproc/winproc.go:37: 		p.err = cmd.Wait()
gateways/zgate/internal/winproc/winproc.go:38: 		close(p.done)
gateways/zgate/internal/winproc/winproc.go:39: 	}()
gateways/zgate/internal/winproc/winproc.go:40: 	return p, nil
gateways/zgate/internal/winproc/winproc.go:41: }
gateways/zgate/internal/winproc/winproc.go:42: 
gateways/zgate/internal/winproc/winproc.go:43: // Pid is the child's process id (0 before start).
gateways/zgate/internal/winproc/winproc.go:44: func (p *Process) Pid() int {
gateways/zgate/internal/winproc/winproc.go:45: 	if p == nil || p.cmd.Process == nil {
gateways/zgate/internal/winproc/winproc.go:46: 		return 0
gateways/zgate/internal/winproc/winproc.go:47: 	}
gateways/zgate/internal/winproc/winproc.go:48: 	return p.cmd.Process.Pid
gateways/zgate/internal/winproc/winproc.go:49: }
gateways/zgate/internal/winproc/winproc.go:50: 
gateways/zgate/internal/winproc/winproc.go:51: // Done is closed when the child exits.
gateways/zgate/internal/winproc/winproc.go:52: func (p *Process) Done() <-chan struct{} { return p.done }
gateways/zgate/internal/winproc/winproc.go:53: 
gateways/zgate/internal/winproc/winproc.go:54: // Err is the exit error, valid after Done is closed.
gateways/zgate/internal/winproc/winproc.go:55: func (p *Process) Err() error { return p.err }
gateways/zgate/internal/winproc/winproc.go:56: 
gateways/zgate/internal/winproc/winproc.go:57: // Kill terminates the child and everything it spawned.
gateways/zgate/internal/winproc/winproc.go:58: func (p *Process) Kill() error { return p.kill() }
gateways/zgate/internal/winproc/winproc.go:59: 
gateways/zgate/internal/winproc/winproc.go:60: // Release drops OS handles; safe to call more than once and from several
gateways/zgate/internal/winproc/winproc.go:61: // goroutines (the monitor and an explicit stop can both get here).
gateways/zgate/internal/winproc/winproc.go:62: func (p *Process) Release() {
gateways/zgate/internal/winproc/winproc.go:63: 	p.releaseO.Do(func() {
gateways/zgate/internal/winproc/winproc.go:64: 		p.release()
gateways/zgate/internal/winproc/winproc.go:65: 	})
gateways/zgate/internal/winproc/winproc.go:66: }
```

### 2.6 四文件能力总表

| 能力 | 落点 | 现状 |
|---|---|---|
| FreeConsole | `console_windows.go:25,64,68` | 有（启动横幅后释放父控制台） |
| CREATE_NO_WINDOW | `winproc_windows.go:13,66,130` | 有 |
| DETACHED_PROCESS | `winproc_windows.go:15,130` | 有（仅 `DetachedAttr()`，`serve -tray` 用） |
| CREATE_NEW_PROCESS_GROUP | `winproc_windows.go:14,66,130` | 有 |
| CREATE_BREAKAWAY_FROM_JOB | 全目录 | **无**；反向使用 `KILL_ON_JOB_CLOSE` |
| SetConsoleCtrlHandler | 全目录 | **无**；由 Go `signal.Notify` 处理 SIGINT/SIGTERM |
| 窗口隐藏 | `HideWindow: true`（:67,:131）+ `-H windowsgui` + `.vbs/Start-Process -WindowStyle Hidden` | 有 |
| 父进程退出后存活 | `main.go:424-440` | 有 `DETACHED_PROCESS` 副本，但 `:440` 自身注释承认不保证父进程树回收时存活 |

## 3. `gateways/zgate/internal/supervisor/` 全文能力

包含 `supervisor.go`（586 行）、`supervisor_windows_test.go`（103 行）、`windows_test.go`（113 行）。所有 `func` 签名与关键常量逐字：
```text
gateways/zgate/internal/supervisor/supervisor.go:32: type window struct {
gateways/zgate/internal/supervisor/supervisor.go:37: type kid struct {
gateways/zgate/internal/supervisor/supervisor.go:56: type Supervisor struct {
gateways/zgate/internal/supervisor/supervisor.go:68: func New(cfg map[string]config.Child, logDir string, log *logx.Logger) *Supervisor {
gateways/zgate/internal/supervisor/supervisor.go:89: func normalize(child *config.Child) {
gateways/zgate/internal/supervisor/supervisor.go:103: func (s *Supervisor) Start() {
gateways/zgate/internal/supervisor/supervisor.go:125: func (s *Supervisor) Stop() {
gateways/zgate/internal/supervisor/supervisor.go:147: func (s *Supervisor) Ensure(name string) error {
gateways/zgate/internal/supervisor/supervisor.go:214: func (s *Supervisor) Touch(name string) {
gateways/zgate/internal/supervisor/supervisor.go:222: func (s *Supervisor) startChild(k *kid, cfg config.Child) error {
gateways/zgate/internal/supervisor/supervisor.go:294: func (s *Supervisor) watch(name string, proc *winproc.Process) {
gateways/zgate/internal/supervisor/supervisor.go:323: func (s *Supervisor) stopChild(name, reason string) {
gateways/zgate/internal/supervisor/supervisor.go:354: func (s *Supervisor) loop() {
gateways/zgate/internal/supervisor/supervisor.go:356: 	ticker := time.NewTicker(5 * time.Second)
gateways/zgate/internal/supervisor/supervisor.go:368: type action struct {
gateways/zgate/internal/supervisor/supervisor.go:375: func (s *Supervisor) tick() {
gateways/zgate/internal/supervisor/supervisor.go:388: 		forced := k.cfg.Policy == "always" || inAnyWindow(k.windows, now)
gateways/zgate/internal/supervisor/supervisor.go:389: 		if forced {
gateways/zgate/internal/supervisor/supervisor.go:390: 			if k.proc == nil && !now.Before(k.nextTry) {
gateways/zgate/internal/supervisor/supervisor.go:391: 				actions = append(actions, action{name: name, start: true})
gateways/zgate/internal/supervisor/supervisor.go:392: 			}
gateways/zgate/internal/supervisor/supervisor.go:395: 		if k.proc != nil && now.Sub(k.lastUsed) > time.Duration(k.cfg.IdleSeconds)*time.Second {
gateways/zgate/internal/supervisor/supervisor.go:396: 			actions = append(actions, action{name: name, stop: true})
gateways/zgate/internal/supervisor/supervisor.go:397: 		}
gateways/zgate/internal/supervisor/supervisor.go:423: 			if err := s.Ensure(a.name); err != nil {
gateways/zgate/internal/supervisor/supervisor.go:424: 				s.mu.Lock()
gateways/zgate/internal/supervisor/supervisor.go:425: 				if k := s.kids[a.name]; k != nil {
gateways/zgate/internal/supervisor/supervisor.go:426: 					k.failCount++
gateways/zgate/internal/supervisor/supervisor.go:427: 					k.nextTry = time.Now().Add(backoff(k.failCount))
gateways/zgate/internal/supervisor/supervisor.go:428: 				}
gateways/zgate/internal/supervisor/supervisor.go:429: 				s.mu.Unlock()
gateways/zgate/internal/supervisor/supervisor.go:430: 				s.log.Warnf("子进程 %s 自动重启失败（第 %d 次）: %v", a.name, s.failCountOf(a.name), err)
gateways/zgate/internal/supervisor/supervisor.go:436: // backoff is 1s, 2s, 4s, ... capped at 60s.
gateways/zgate/internal/supervisor/supervisor.go:437: func backoff(fails int) time.Duration {
gateways/zgate/internal/supervisor/supervisor.go:438: 	if fails <= 0 {
gateways/zgate/internal/supervisor/supervisor.go:439: 		return 0
gateways/zgate/internal/supervisor/supervisor.go:440: 	}
gateways/zgate/internal/supervisor/supervisor.go:441: 	if fails > 7 {
gateways/zgate/internal/supervisor/supervisor.go:442: 		fails = 7
gateways/zgate/internal/supervisor/supervisor.go:443: 	}
gateways/zgate/internal/supervisor/supervisor.go:444: 	d := time.Second << uint(fails-1)
gateways/zgate/internal/supervisor/supervisor.go:445: 	if d > time.Minute {
gateways/zgate/internal/supervisor/supervisor.go:446: 		d = time.Minute
gateways/zgate/internal/supervisor/supervisor.go:447: 	}
gateways/zgate/internal/supervisor/supervisor.go:448: 	return d
gateways/zgate/internal/supervisor/supervisor.go:451: func (s *Supervisor) failCountOf(name string) int {
gateways/zgate/internal/supervisor/supervisor.go:460: func (s *Supervisor) healthy(url string) bool {
gateways/zgate/internal/supervisor/supervisor.go:473: // ApplyConfig updates policies, idle thresholds and windows of existing children.
gateways/zgate/internal/supervisor/supervisor.go:474: // New children need a restart (the executable and port layout is boot-time only).
gateways/zgate/internal/supervisor/supervisor.go:475: func (s *Supervisor) ApplyConfig(cfg map[string]config.Child) (applied, unknownKeep, added []string) {
gateways/zgate/internal/supervisor/supervisor.go:502: func (s *Supervisor) States() map[string]any {
gateways/zgate/internal/supervisor/supervisor.go:537: func parseWindows(specs []string) []window {
gateways/zgate/internal/supervisor/supervisor.go:554: func parseClock(s string) (int, bool) {
gateways/zgate/internal/supervisor/supervisor.go:567: func inAnyWindow(windows []window, t time.Time) bool {
```

自愈拉起：有。`supervisor.go:354-366` `loop()` 用 `time.NewTicker(5 * time.Second)`；`:388` `forced := k.cfg.Policy == "always" || inAnyWindow(k.windows, now)`；`:390-392` 当 `k.proc == nil && !now.Before(k.nextTry)` 追加 `action{start:true}`；`:423-430` 调 `s.Ensure(a.name)`，失败 `failCount++` / `nextTry = now + backoff(...)` 并打日志「子进程 %s 自动重启失败（第 %d 次）」；`:437-448` 退避 1s/2s/4s… 上限 60s。
子进程重启：有，`TestAlwaysRestartsAfterCrash`（`supervisor_windows_test.go:60-101`）真实杀掉 `proc.Kill()` 后断言新 PID 且 `state == "running"`。
优雅退出：`Stop()`（:125）置 `stopping` 并 `stopChild`；`stopChild`（:323-352）`Kill()` 后等 `Done()` 最多 5s 再 `Release()`；`watch`（:294-321）在子进程自行退出时清状态、关日志句柄。注意 `kill()` 是 `TerminateJobObject + Process.Kill()`，**不是**向子进程发 SIGTERM 的优雅关闭。
**二进制变更检测：无**。`:473-475` 原文 `// New children need a restart (the executable and port layout is boot-time only).`；`ApplyConfig` 只更新已有 child 的 `Policy / IdleSeconds / Windows`，新增 child 仅进 `added` 列表、需重启 zgate。全包无 `fsnotify`、无 `os.Stat(ModTime)`、无自身 exe 哈希/替换逻辑。
接管的外部实例：`Ensure()` 在端口已忙时标记 `external`，`:383-385` 每 5s 只轮询 health；`:403-413` health 失败才转为由 zgate 管理。这不等于「自动替换磁盘上的新二进制」。

测试签名与断言：
```text
gateways/zgate/internal/supervisor/supervisor_windows_test.go:14: func newTestSup(t *testing.T, child config.Child) (*Supervisor, *logx.Logger) {
gateways/zgate/internal/supervisor/supervisor_windows_test.go:25: func TestOnDemandStartAndIdleStop(t *testing.T) {
gateways/zgate/internal/supervisor/supervisor_windows_test.go:48: 	// The monitor ticks every 5s; idle is 1s, so one tick must reclaim it.
gateways/zgate/internal/supervisor/supervisor_windows_test.go:60: func TestAlwaysRestartsAfterCrash(t *testing.T) {
gateways/zgate/internal/supervisor/supervisor_windows_test.go:91: 	_ = proc.Kill()
gateways/zgate/internal/supervisor/supervisor_windows_test.go:96: 		if state["state"] == "running" && state["pid"] != first["pid"] {
gateways/zgate/internal/supervisor/windows_test.go:11: func at(hour, minute int) time.Time {
gateways/zgate/internal/supervisor/windows_test.go:15: func TestParseWindows(t *testing.T) {
gateways/zgate/internal/supervisor/windows_test.go:28: func TestInAnyWindow(t *testing.T) {
gateways/zgate/internal/supervisor/windows_test.go:51: func TestApplyConfigUpdatesPolicyAndWindows(t *testing.T) {
gateways/zgate/internal/supervisor/windows_test.go:94: func TestBackoffGrowsAndCaps(t *testing.T) {
gateways/zgate/internal/supervisor/windows_test.go:106: func TestNormalizeDefaults(t *testing.T) {
```

## 4. router / main 的 reload、admin、graceful、listener 继承

`main.go` 与 `router.go` 被 CodeGraph 标注为「磁盘已漂移」，以下全部直读当前磁盘。

### 4.1 main 包（当前磁盘 516 行）
```text
gateways/zgate/main.go:1: // zgate is the single entry point for ZCode's four chat providers.
gateways/zgate/main.go:2: //
gateways/zgate/main.go:3: //	zgate serve       listen on 127.0.0.1:7871: alias routing, protocol bridge,
gateways/zgate/main.go:4: //	                  child process supervision (dies with its console window)
gateways/zgate/main.go:5: //	zgate serve -tray same, but as a detached copy that outlives the terminal
gateways/zgate/main.go:6: //	zgate status      one-shot report (works whether or not serve is running)
gateways/zgate/main.go:7: //	zgate install     register a logon scheduled task
gateways/zgate/main.go:8: //	zgate uninstall   remove it
gateways/zgate/main.go:9: //
gateways/zgate/main.go:10: // The port, paths and child commands live in zgate.json next to the binary.
gateways/zgate/main.go:40: const version = "0.3.0"
gateways/zgate/main.go:42: const taskName = "ModelBus-zgate"
gateways/zgate/main.go:44: func main() {
gateways/zgate/main.go:45: 	winproc.AttachParentConsole()
gateways/zgate/main.go:64: 		if err := serve(); err != nil {
gateways/zgate/main.go:65: 			fmt.Fprintln(os.Stderr, "zgate serve:", err)
gateways/zgate/main.go:66: 			os.Exit(1)
gateways/zgate/main.go:67: 		}
gateways/zgate/main.go:68: 	case "status":
gateways/zgate/main.go:69: 		if err := status(); err != nil {
gateways/zgate/main.go:70: 			fmt.Fprintln(os.Stderr, "zgate status:", err)
gateways/zgate/main.go:71: 			os.Exit(1)
gateways/zgate/main.go:72: 		}
gateways/zgate/main.go:73: 	case "reload":
gateways/zgate/main.go:74: 		if err := reload(); err != nil {
gateways/zgate/main.go:75: 			fmt.Fprintln(os.Stderr, "zgate reload:", err)
gateways/zgate/main.go:76: 			os.Exit(1)
gateways/zgate/main.go:98: func usage() {
gateways/zgate/main.go:99: 	fmt.Printf(`zgate %s —— ZCode 统一入口（路由 + 协议桥 + 子进程守护）
gateways/zgate/main.go:100: 
gateways/zgate/main.go:101: 用法:
gateways/zgate/main.go:102:   zgate serve        前台运行（终端里用；关闭终端/Ctrl+C 会结束它）
gateways/zgate/main.go:103:   zgate serve -tray  后台运行（拉一个无父进程的副本后立即返回，关终端不影响）
gateways/zgate/main.go:104:   zgate status       打印配置、健康与子进程状态（不碰日志文件）
gateways/zgate/main.go:105:   zgate reload       让运行中的实例热加载 zgate.json（策略/空闲/窗口）
gateways/zgate/main.go:115: func loadConfig() (*config.Config, keys.Set, error) {
gateways/zgate/main.go:116: 	cfgPath := ""
gateways/zgate/main.go:117: 	fs := flag.NewFlagSet("zgate", flag.ContinueOnError)
gateways/zgate/main.go:118: 	fs.StringVar(&cfgPath, "config", "", "zgate.json 路径")
gateways/zgate/main.go:119: 	// os.Args[1] is the subcommand, so flags start at os.Args[2]. 无参数启动（双击 exe）
gateways/zgate/main.go:120: 	// 时 os.Args[2:] 是越界切片，会 panic 而不是打 usage —— 先兜住长度。
gateways/zgate/main.go:121: 	var rest []string
gateways/zgate/main.go:122: 	if len(os.Args) > 2 {
gateways/zgate/main.go:123: 		rest = os.Args[2:]
gateways/zgate/main.go:124: 	}
gateways/zgate/main.go:125: 	_ = fs.Parse(rest)
gateways/zgate/main.go:126: 
gateways/zgate/main.go:127: 	cfg, err := config.Load(cfgPath)
gateways/zgate/main.go:128: 	if err != nil {
gateways/zgate/main.go:129: 		return nil, keys.Set{}, err
gateways/zgate/main.go:130: 	}
gateways/zgate/main.go:131: 	ks := keys.Load(cfg.ProviderConfig, cfg.WBGatewayConfig, cfg.QoderEnvFile, cfg.QwenEnvFile, cfg.QiniuEnvFile, cfg.CliproxyEnvFile)
gateways/zgate/main.go:135: func serve() error {
gateways/zgate/main.go:136: 	cfg, ks, err := loadConfig()
gateways/zgate/main.go:137: 	if err != nil {
gateways/zgate/main.go:138: 		return err
gateways/zgate/main.go:139: 	}
gateways/zgate/main.go:140: 	log, err := logx.Open(cfg.Log.Dir, cfg.Log.File, cfg.Log.MaxMB)
gateways/zgate/main.go:141: 	if err != nil {
gateways/zgate/main.go:142: 		return err
gateways/zgate/main.go:143: 	}
gateways/zgate/main.go:144: 	defer log.Close()
gateways/zgate/main.go:145: 
gateways/zgate/main.go:146: 	am := alias.New(cfg.AliasMap)
gateways/zgate/main.go:147: 	sup := supervisor.New(cfg.Children, log.Dir(), log)
gateways/zgate/main.go:167: 	ln, err := net.Listen("tcp", cfg.Listen)
gateways/zgate/main.go:168: 	if err != nil {
gateways/zgate/main.go:169: 		log.Errorf("监听 %s 失败: %v（是否已有实例在跑？）", cfg.Listen, err)
gateways/zgate/main.go:170: 		return fmt.Errorf("监听 %s 失败: %w", cfg.Listen, err)
gateways/zgate/main.go:171: 	}
gateways/zgate/main.go:172: 
gateways/zgate/main.go:173: 	// Boot children in the background: Start() runs the boot list serially and
gateways/zgate/main.go:174: 	// each child can take StartTimeoutSeconds, while the HTTP server should be
gateways/zgate/main.go:175: 	// accepting requests during that window.
gateways/zgate/main.go:176: 	go sup.Start()
gateways/zgate/main.go:183: 	// 控制台，这样关掉那个窗口不会再留下一个半死的控制台（网关本身照常运行，
gateways/zgate/main.go:184: 	// 输出只走日志文件）。用管道/重定向启动的调用方不受影响。
gateways/zgate/main.go:185: 	winproc.DetachConsole()
gateways/zgate/main.go:186: 	// 由 serve -tray 拉起的副本带 ZGATE_PARENT_PID：拉起它的进程一旦消失
gateways/zgate/main.go:187: 	// （关掉终端、cmd 被 taskkill），副本自己退出，不留孤儿占端口。
gateways/zgate/main.go:207: 	go func() { errCh <- srv.Serve(ln) }()
gateways/zgate/main.go:208: 
gateways/zgate/main.go:209: 	sig := make(chan os.Signal, 1)
gateways/zgate/main.go:210: 	signal.Notify(sig, os.Interrupt, syscall.SIGTERM)
gateways/zgate/main.go:211: 
gateways/zgate/main.go:212: 	select {
gateways/zgate/main.go:213: 	case s := <-sig:
gateways/zgate/main.go:214: 		log.Infof("收到 %v，正在退出", s)
gateways/zgate/main.go:215: 	case err := <-errCh:
gateways/zgate/main.go:216: 		if err != nil && err != http.ErrServerClosed {
gateways/zgate/main.go:217: 			sup.Stop()
gateways/zgate/main.go:218: 			return err
gateways/zgate/main.go:219: 		}
gateways/zgate/main.go:220: 	}
gateways/zgate/main.go:221: 
gateways/zgate/main.go:222: 	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
gateways/zgate/main.go:223: 	defer cancel()
gateways/zgate/main.go:224: 	_ = srv.Shutdown(ctx)
gateways/zgate/main.go:225: 	sup.Stop()
gateways/zgate/main.go:226: 	log.Infof("已退出")
gateways/zgate/main.go:232: func superviseLauncher(log *logx.Logger) {
gateways/zgate/main.go:233: 	raw := os.Getenv("ZGATE_PARENT_PID")
gateways/zgate/main.go:234: 	if raw == "" {
gateways/zgate/main.go:235: 		return
gateways/zgate/main.go:236: 	}
gateways/zgate/main.go:237: 	ppid, err := strconv.Atoi(raw)
gateways/zgate/main.go:238: 	if err != nil || ppid <= 0 {
gateways/zgate/main.go:239: 		return
gateways/zgate/main.go:240: 	}
gateways/zgate/main.go:241: 	for {
gateways/zgate/main.go:242: 		time.Sleep(2 * time.Second)
gateways/zgate/main.go:243: 		if !winproc.ProcessAlive(uint32(ppid)) {
gateways/zgate/main.go:244: 			log.Infof("拉起方 %d 已退出，后台副本随之停止", ppid)
gateways/zgate/main.go:245: 			os.Exit(0)
gateways/zgate/main.go:246: 		}
gateways/zgate/main.go:247: 	}
gateways/zgate/main.go:248: }
gateways/zgate/main.go:249: 
gateways/zgate/main.go:250: func childSuffix(child string) string {
gateways/zgate/main.go:257: func status() error {
gateways/zgate/main.go:258: 	cfg, ks, err := loadConfig()
gateways/zgate/main.go:259: 	if err != nil {
gateways/zgate/main.go:260: 		return err
gateways/zgate/main.go:261: 	}
gateways/zgate/main.go:262: 
gateways/zgate/main.go:263: 	fmt.Printf("zgate %s\n", version)
gateways/zgate/main.go:264: 	fmt.Printf("配置      : %s\n", cfg.Path)
gateways/zgate/main.go:265: 	fmt.Printf("监听      : http://%s/v1\n", cfg.Listen)
gateways/zgate/main.go:266: 	fmt.Printf("alias map : %s\n", cfg.AliasMap)
gateways/zgate/main.go:267: 	fmt.Printf("日志      : %s\n\n", filepath.Join(cfg.Log.Dir, cfg.Log.File))
gateways/zgate/main.go:268: 
gateways/zgate/main.go:269: 	fmt.Println("凭据（只报有无）:")
gateways/zgate/main.go:270: 	for _, name := range []string{"OC", "WB", "QD", "QW", "QN", "CP"} {
gateways/zgate/main.go:271: 		want := ks.For(name) != ""
gateways/zgate/main.go:272: 		fmt.Printf("  %-3s %-8s %s\n", name, yesNo(want), cfg.Upstreams[name].Base)
gateways/zgate/main.go:273: 	}
gateways/zgate/main.go:274: 	fmt.Println()
gateways/zgate/main.go:275: 
gateways/zgate/main.go:276: 	body, code := probeHealth(cfg.Listen)
gateways/zgate/main.go:277: 	if body == nil {
gateways/zgate/main.go:278: 		fmt.Printf("服务状态  : 未运行（健康检查不可达，HTTP %d）\n", code)
gateways/zgate/main.go:279: 	} else {
gateways/zgate/main.go:280: 		fmt.Printf("服务状态  : 运行中（HTTP %d）\n", code)
gateways/zgate/main.go:281: 		var health struct {
gateways/zgate/main.go:318: func probeHealth(listen string) ([]byte, int) {
gateways/zgate/main.go:319: 	host := listen
gateways/zgate/main.go:320: 	if strings.HasPrefix(host, ":") {
gateways/zgate/main.go:321: 		host = "127.0.0.1" + host
gateways/zgate/main.go:322: 	}
gateways/zgate/main.go:323: 	client := &http.Client{Timeout: 2 * time.Second}
gateways/zgate/main.go:324: 	resp, err := client.Get("http://" + host + "/health")
gateways/zgate/main.go:341: // reload asks the running instance to re-read zgate.json.
gateways/zgate/main.go:342: func reload() error {
gateways/zgate/main.go:343: 	cfg, _, err := loadConfig()
gateways/zgate/main.go:344: 	if err != nil {
gateways/zgate/main.go:345: 		return err
gateways/zgate/main.go:346: 	}
gateways/zgate/main.go:347: 	host := cfg.Listen
gateways/zgate/main.go:348: 	if strings.HasPrefix(host, ":") {
gateways/zgate/main.go:349: 		host = "127.0.0.1" + host
gateways/zgate/main.go:350: 	}
gateways/zgate/main.go:351: 	client := &http.Client{Timeout: 5 * time.Second}
gateways/zgate/main.go:352: 	resp, err := client.Post("http://"+host+"/admin/reload", "application/json", nil)
gateways/zgate/main.go:353: 	if err != nil {
gateways/zgate/main.go:354: 		return fmt.Errorf("连不上 %s（服务没在跑？）: %w", host, err)
gateways/zgate/main.go:355: 	}
gateways/zgate/main.go:356: 	defer resp.Body.Close()
gateways/zgate/main.go:357: 	raw, _ := io.ReadAll(resp.Body)
gateways/zgate/main.go:358: 	if resp.StatusCode != 200 {
gateways/zgate/main.go:359: 		return fmt.Errorf("HTTP %d: %s", resp.StatusCode, raw)
gateways/zgate/main.go:360: 	}
gateways/zgate/main.go:361: 	var out map[string]any
gateways/zgate/main.go:362: 	if err := json.Unmarshal(raw, &out); err != nil {
gateways/zgate/main.go:363: 		fmt.Println(string(raw))
gateways/zgate/main.go:364: 		return nil
gateways/zgate/main.go:365: 	}
gateways/zgate/main.go:366: 	fmt.Printf("已热加载：生效 %v\n", out["applied"])
gateways/zgate/main.go:367: 	if stale, ok := out["stale"].([]any); ok && len(stale) > 0 {
gateways/zgate/main.go:368: 		fmt.Printf("配置里已删除但仍由本进程管理：%v（重启后彻底移除）\n", stale)
gateways/zgate/main.go:369: 	}
gateways/zgate/main.go:370: 	if added, ok := out["added"].([]any); ok && len(added) > 0 {
gateways/zgate/main.go:371: 		fmt.Printf("新增子进程：%v（需要重启 zgate 才会生效）\n", added)
gateways/zgate/main.go:376: func startupLinkPath() (string, error) {
gateways/zgate/main.go:377: 	appData := os.Getenv("APPDATA")
gateways/zgate/main.go:378: 	if appData == "" {
gateways/zgate/main.go:379: 		return "", fmt.Errorf("APPDATA 未设置")
gateways/zgate/main.go:380: 	}
gateways/zgate/main.go:381: 	dir := filepath.Join(appData, "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
gateways/zgate/main.go:382: 	if err := os.MkdirAll(dir, 0o755); err != nil {
gateways/zgate/main.go:383: 		return "", err
gateways/zgate/main.go:384: 	}
gateways/zgate/main.go:385: 	return filepath.Join(dir, "ModelBus zgate.lnk"), nil
gateways/zgate/main.go:386: }
gateways/zgate/main.go:387: 
gateways/zgate/main.go:388: func install() error {
gateways/zgate/main.go:402: 	// schtasks ONLOGON needs elevation; a Startup shortcut does not, and it is
gateways/zgate/main.go:403: 	// the mechanism the old PowerShell watchdog already used.
gateways/zgate/main.go:404: 	// PowerShell single-quoted strings escape a quote by doubling it.
gateways/zgate/main.go:405: 	psq := func(p string) string { return strings.ReplaceAll(p, "'", "''") }
gateways/zgate/main.go:406: 	script := fmt.Sprintf(
gateways/zgate/main.go:407: 		"$ws = New-Object -ComObject WScript.Shell; "+
gateways/zgate/main.go:408: 			"$s = $ws.CreateShortcut('%s'); "+
gateways/zgate/main.go:409: 			"$s.TargetPath = '%s'; $s.Arguments = 'serve -tray'; $s.WorkingDirectory = '%s'; "+
gateways/zgate/main.go:410: 			"$s.WindowStyle = 7; $s.Description = 'ZCode 统一入口 (zgate)'; $s.Save()",
gateways/zgate/main.go:411: 		psq(link), psq(exe), psq(workDir))
gateways/zgate/main.go:412: 	out, err := exec.Command("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script).CombinedOutput()
gateways/zgate/main.go:413: 	if err != nil {
gateways/zgate/main.go:414: 		return fmt.Errorf("创建启动快捷方式失败: %v\n%s", err, out)
gateways/zgate/main.go:415: 	}
gateways/zgate/main.go:416: 	fmt.Printf("已注册登录自启: %s（目标: %s serve -tray，后台实例）\n", link, exe)
gateways/zgate/main.go:424: // Because the child is a GUI-subsystem binary started with DETACHED_PROCESS,
gateways/zgate/main.go:425: // closing the console window that launched the wrapper cannot take it down:
gateways/zgate/main.go:426: // the process has no console to receive CTRL_CLOSE_EVENT on. A failed listen
gateways/zgate/main.go:427: // (another instance already on the port) is reported by the child through
gateways/zgate/main.go:428: // `zgate status`, not here.
gateways/zgate/main.go:429: func detach() error {
gateways/zgate/main.go:430: 	exe, err := os.Executable()
gateways/zgate/main.go:431: 	if err != nil {
gateways/zgate/main.go:432: 		return err
gateways/zgate/main.go:433: 	}
gateways/zgate/main.go:434: 	exe, _ = filepath.Abs(exe)
gateways/zgate/main.go:435: 	cmd := exec.Command(exe, "serve")
gateways/zgate/main.go:436: 	cmd.Dir = filepath.Dir(exe)
gateways/zgate/main.go:437: 	cmd.Env = os.Environ()
gateways/zgate/main.go:438: 	cmd.SysProcAttr = winproc.DetachedAttr()
gateways/zgate/main.go:439: 	// 把「后台副本的父进程 = 本进程」交给子进程：子进程看到父消失后自己退出。
gateways/zgate/main.go:440: 	// Windows 的 DETACHED_PROCESS 只表示不共享控制台，不保证父进程树被回收时仍存活
gateways/zgate/main.go:441: 	// （实测 cmd /c 退出后子进程跟着消失），显式约定比依赖未定义行为可靠。
gateways/zgate/main.go:442: 	cmd.Env = append(cmd.Env, fmt.Sprintf("ZGATE_PARENT_PID=%d", os.Getpid()))
gateways/zgate/main.go:443: 	if err := cmd.Start(); err != nil {
gateways/zgate/main.go:444: 		return fmt.Errorf("启动后台实例失败: %w", err)
gateways/zgate/main.go:445: 	}
gateways/zgate/main.go:446: 	pid := cmd.Process.Pid
gateways/zgate/main.go:447: 	_ = cmd.Process.Release()
gateways/zgate/main.go:448: 	// 子进程是 GUI 子系统的无控制台进程；这里把「已启动」写进日志，
gateways/zgate/main.go:449: 	// 因为直接双击/计划任务启动时没有可读的 stdout。探测到端口就绪才回话。
gateways/zgate/main.go:450: 	ready := waitListening(2 * time.Second)
gateways/zgate/main.go:451: 	line := fmt.Sprintf("已在后台启动: %s (pid %d, ready=%v)；停止: Stop-Process -Id %d", exe, pid, ready, pid)
gateways/zgate/main.go:465: func waitListening(d time.Duration) bool {
gateways/zgate/main.go:466: 	cfg, err := config.Load("")
gateways/zgate/main.go:467: 	if err != nil {
gateways/zgate/main.go:468: 		return false
gateways/zgate/main.go:469: 	}
gateways/zgate/main.go:470: 	deadline := time.Now().Add(d)
gateways/zgate/main.go:471: 	for time.Now().Before(deadline) {
gateways/zgate/main.go:472: 		conn, err := net.DialTimeout("tcp", cfg.Listen, 200*time.Millisecond)
gateways/zgate/main.go:473: 		if err == nil {
gateways/zgate/main.go:474: 			_ = conn.Close()
gateways/zgate/main.go:475: 			return true
gateways/zgate/main.go:476: 		}
gateways/zgate/main.go:477: 		time.Sleep(100 * time.Millisecond)
gateways/zgate/main.go:478: 	}
gateways/zgate/main.go:479: 	return false
gateways/zgate/main.go:480: }
gateways/zgate/main.go:481: 
gateways/zgate/main.go:482: func uninstall() error {
```
- 有 `reload` 子命令：`:73 case "reload"` → `func reload() error`（:342）→ `client.Post("http://"+host+"/admin/reload", ...)`（:352）；`:371` 明说「新增子进程：%v（需要重启 zgate 才会生效）」。
- 有 `SIGHUP`？**无**：全 main/router/config 用 `Select-String` 查 `SIGHUP` 无命中（见下）。
- 有 `syscall.SIGTERM` + graceful shutdown：`:209-210 signal.Notify(sig, os.Interrupt, syscall.SIGTERM)`、`:224 _ = srv.Shutdown(ctx)`、`:225 sup.Stop()`。
- 有 admin endpoint：`/admin/reload` 由 router 提供；`/health`（`main.go:324`、`router.go:248`）；无 `/debug`、无 `/control`。
- **listener 继承：无**。`main.go:167 ln, err := net.Listen("tcp", cfg.Listen)`、`:207 srv.Serve(ln)`；`SO_REUSEPORT/SO_REUSEADDR`、`net.FileListener`、`ExtraFiles`、`ListenConfig`、`syscall.Exec` 全部无命中（见 4.3）。新旧进程不能直接共享同一个监听套接字做无缝切换。
- 启动/守护：`serve -tray` 由 `detach()`（:429-451）用 `exec.Command(exe, "serve")` + `winproc.DetachedAttr()` 起后台副本；`:440` 原文注释 `Windows 的 DETACHED_PROCESS 只表示不共享控制台，不保证父进程树被回收时仍存活`；`superviseLauncher`（:232）在 CMD/终端父进程消失时让副本自行退出（这正是「DSH/CMD 关闭网关消失」的潜在机制，须与运行实况对照）。
- `install()`（:388-416）**不是 schtasks / sc create / NSSM**：`:402-403` 注释 `schtasks ONLOGON needs elevation; a Startup shortcut does not`，用 PowerShell `WScript.Shell` 创建「启动」文件夹快捷方式（`$s.WindowStyle = 7`，目标 `zgate.exe serve -tray`）；`const taskName = "ModelBus-zgate"`（:42）只是常量名，不代表已注册计划任务。

### 4.2 router 包（当前磁盘 1153 行）
```text
gateways/zgate/internal/router/router.go:30: type Server struct {
gateways/zgate/internal/router/router.go:46: const hopCooldown = 30 * time.Minute
gateways/zgate/internal/router/router.go:51: const rateLimitCooldown = 45 * time.Second
gateways/zgate/internal/router/router.go:55: const rateLimitBackoff = 700 * time.Millisecond
gateways/zgate/internal/router/router.go:60: const transportRetryDelay = 300 * time.Millisecond
gateways/zgate/internal/router/router.go:64: const timeoutCooldown = 5 * time.Minute
gateways/zgate/internal/router/router.go:72: const regionCooldown = 30 * time.Minute
gateways/zgate/internal/router/router.go:78: const quotaCooldown = 24 * time.Hour
gateways/zgate/internal/router/router.go:81: func New(cfg *config.Config, ks keys.Set, am *alias.Map, sup *supervisor.Supervisor, client *http.Client, log *logx.Logger) *Server {
gateways/zgate/internal/router/router.go:215: // Config returns the current configuration; it can be swapped by /admin/reload.
gateways/zgate/internal/router/router.go:216: func (s *Server) Config() *config.Config {
gateways/zgate/internal/router/router.go:217: 	s.cfgMu.RLock()
gateways/zgate/internal/router/router.go:218: 	defer s.cfgMu.RUnlock()
gateways/zgate/internal/router/router.go:219: 	return s.cfg
gateways/zgate/internal/router/router.go:220: }
gateways/zgate/internal/router/router.go:221: 
gateways/zgate/internal/router/router.go:222: func (s *Server) setRuntime(cfg *config.Config, ks keys.Set) {
gateways/zgate/internal/router/router.go:237: func (s *Server) Handler() http.Handler { return http.HandlerFunc(s.serveHTTP) }
gateways/zgate/internal/router/router.go:238: 
gateways/zgate/internal/router/router.go:239: func (s *Server) serveHTTP(w http.ResponseWriter, r *http.Request) {
gateways/zgate/internal/router/router.go:240: 	defer func() {
gateways/zgate/internal/router/router.go:241: 		if rec := recover(); rec != nil {
gateways/zgate/internal/router/router.go:242: 			s.log.Errorf("panic on %s %s: %v", r.Method, r.URL.Path, rec)
gateways/zgate/internal/router/router.go:243: 			writeJSON(w, 500, errorBody("unified-router error: panic", "proxy_error"))
gateways/zgate/internal/router/router.go:244: 		}
gateways/zgate/internal/router/router.go:245: 	}()
gateways/zgate/internal/router/router.go:246: 
gateways/zgate/internal/router/router.go:247: 	path, search := normalizePath(r)
gateways/zgate/internal/router/router.go:248: 	if path == "/health" {
gateways/zgate/internal/router/router.go:249: 		s.health(w)
gateways/zgate/internal/router/router.go:250: 		return
gateways/zgate/internal/router/router.go:251: 	}
gateways/zgate/internal/router/router.go:252: 	if path == "/admin/reload" {
gateways/zgate/internal/router/router.go:253: 		s.reload(w, r)
gateways/zgate/internal/router/router.go:266: 		var probe struct {
gateways/zgate/internal/router/router.go:267: 			Model string `json:"model"`
gateways/zgate/internal/router/router.go:268: 		}
gateways/zgate/internal/router/router.go:269: 		if err := json.Unmarshal(body, &probe); err == nil {
gateways/zgate/internal/router/router.go:270: 			model = probe.Model
gateways/zgate/internal/router/router.go:271: 		}
gateways/zgate/internal/router/router.go:272: 	}
gateways/zgate/internal/router/router.go:273: 
gateways/zgate/internal/router/router.go:274: 	isChat := path == "/chat/completions"
gateways/zgate/internal/router/router.go:275: 	if !isChat && (isQoder(model) || isWorkBuddy(model) || isQwen(model) || isQiniu(model)) {
gateways/zgate/internal/router/router.go:276: 		writeJSON(w, 400, errorBody("WorkBuddy/Qoder/Qwen models only support chat/completions", "invalid_request_error"))
gateways/zgate/internal/router/router.go:277: 		return
gateways/zgate/internal/router/router.go:278: 	}
gateways/zgate/internal/router/router.go:279: 
gateways/zgate/internal/router/router.go:280: 	s.aliases.Reload()
gateways/zgate/internal/router/router.go:281: 	if target, ok := s.aliases.Resolve(model); ok {
gateways/zgate/internal/router/router.go:282: 		s.routeAlias(w, r, body, model, target, path, search, isChat)
gateways/zgate/internal/router/router.go:444: func (s *Server) prepare(channel string) error {
gateways/zgate/internal/router/router.go:450: 	if err := s.sup.Ensure(upstream.Child); err != nil {
gateways/zgate/internal/router/router.go:641: func (s *Server) health(w http.ResponseWriter) {
gateways/zgate/internal/router/router.go:642: 	s.aliases.Reload()
gateways/zgate/internal/router/router.go:959: // reload re-reads zgate.json and applies the parts that can change at runtime:
gateways/zgate/internal/router/router.go:960: // config values, upstream bases, credentials, child policies, idle thresholds
gateways/zgate/internal/router/router.go:961: // and windows. The listen address, newly added children and a changed alias-map
gateways/zgate/internal/router/router.go:962: // path still need a restart.
gateways/zgate/internal/router/router.go:963: func (s *Server) reload(w http.ResponseWriter, r *http.Request) {
gateways/zgate/internal/router/router.go:964: 	if r.Method != http.MethodPost {
gateways/zgate/internal/router/router.go:965: 		writeJSON(w, 405, errorBody("use POST", "invalid_request_error"))
gateways/zgate/internal/router/router.go:966: 		return
gateways/zgate/internal/router/router.go:967: 	}
gateways/zgate/internal/router/router.go:968: 	old := s.Config()
gateways/zgate/internal/router/router.go:969: 	next, err := config.Load(old.Path)
gateways/zgate/internal/router/router.go:970: 	if err != nil {
gateways/zgate/internal/router/router.go:971: 		writeJSON(w, 400, errorBody("配置读取失败: "+err.Error(), "configuration_error"))
gateways/zgate/internal/router/router.go:972: 		return
gateways/zgate/internal/router/router.go:973: 	}
gateways/zgate/internal/router/router.go:974: 	ks := keys.Load(next.ProviderConfig, next.WBGatewayConfig, next.QoderEnvFile, next.QwenEnvFile, next.QiniuEnvFile, next.CliproxyEnvFile)
gateways/zgate/internal/router/router.go:975: 	applied, stale, added := s.sup.ApplyConfig(next.Children)
gateways/zgate/internal/router/router.go:976: 	s.setRuntime(next, ks)
gateways/zgate/internal/router/router.go:977: 	s.aliases.Reload()
gateways/zgate/internal/router/router.go:978: 	s.log.Infof("配置已热加载: %s（生效 %v）", next.Path, applied)
gateways/zgate/internal/router/router.go:979: 	writeJSON(w, 200, map[string]any{
gateways/zgate/internal/router/router.go:980: 		"ok":      true,
gateways/zgate/internal/router/router.go:981: 		"applied": applied,
gateways/zgate/internal/router/router.go:982: 		"stale":   stale,
gateways/zgate/internal/router/router.go:983: 		"added":   added,
gateways/zgate/internal/router/router.go:984: 		"note":    "监听地址、新增子进程与 alias map 路径仍需重启 zgate；配置、上游 base 与 key 已热加载",
gateways/zgate/internal/router/router.go:985: 	})
```
- `/admin/reload`（:252-253）→ `func (s *Server) reload`（:963）→ `config.Load(old.Path)`（:969）→ `keys.Load(...)`（:974）→ `s.sup.ApplyConfig(next.Children)`（:975）→ `s.aliases.Reload()`（:977）；返回 `:984 "note": "监听地址、新增子进程与 alias map 路径仍需重启 zgate；配置、上游 base 与 key 已热加载"`。也就是**热加载范围 = 已有上游 base / key / 子进程策略 / 空闲窗口；不含监听地址、新子进程、alias map 路径，更不含 Go 二进制代码本身**。
- `/health`（:248、:641）里 `:642 s.aliases.Reload()`；`serveHTTP` 里 `:280 s.aliases.Reload()` —— alias 是每请求惰性检查 ModTime/Size。

### 4.3 能力否定项的 PowerShell 真实输出
```text
source keyword Select-String（reload/admin/signal/net.Listen 等命中）：
gateways\zgate\main.go:45:winproc.AttachParentConsole()
gateways\zgate\main.go:64:if err := serve(); err != nil {
gateways\zgate\main.go:73:case "reload":
gateways\zgate\main.go:74:if err := reload(); err != nil {
gateways\zgate\main.go:75:fmt.Fprintln(os.Stderr, "zgate reload:", err)
gateways\zgate\main.go:105:zgate reload       让运行中的实例热加载 zgate.json（策略/空闲/窗口）
gateways\zgate\main.go:127:cfg, err := config.Load(cfgPath)
gateways\zgate\main.go:131:ks := keys.Load(cfg.ProviderConfig, cfg.WBGatewayConfig, cfg.QoderEnvFile, cfg.QwenEnvFile, cfg.QiniuEnvFile, cfg.CliproxyEnvFile)
gateways\zgate\main.go:135:func serve() error {
gateways\zgate\main.go:167:ln, err := net.Listen("tcp", cfg.Listen)
gateways\zgate\main.go:185:winproc.DetachConsole()
gateways\zgate\main.go:207:go func() { errCh <- srv.Serve(ln) }()
gateways\zgate\main.go:210:signal.Notify(sig, os.Interrupt, syscall.SIGTERM)
gateways\zgate\main.go:224:_ = srv.Shutdown(ctx)
gateways\zgate\main.go:324:resp, err := client.Get("http://" + host + "/health")
gateways\zgate\main.go:341:// reload asks the running instance to re-read zgate.json.
gateways\zgate\main.go:342:func reload() error {
gateways\zgate\main.go:352:resp, err := client.Post("http://"+host+"/admin/reload", "application/json", nil)
gateways\zgate\main.go:389:exe, err := os.Executable()
gateways\zgate\main.go:424:// Because the child is a GUI-subsystem binary started with DETACHED_PROCESS,
gateways\zgate\main.go:430:exe, err := os.Executable()
gateways\zgate\main.go:440:// Windows 的 DETACHED_PROCESS 只表示不共享控制台，不保证父进程树被回收时仍存活
gateways\zgate\main.go:454:if cfg, err := config.Load(""); err == nil {
gateways\zgate\main.go:464:// 这里复用 config.Load，失败就当没就绪）。
gateways\zgate\main.go:466:cfg, err := config.Load("")
gateways\zgate\internal\router\router.go:215:// Config returns the current configuration; it can be swapped by /admin/reload.
gateways\zgate\internal\router\router.go:229:// keyset returns the current credentials; /admin/reload can swap them.
gateways\zgate\internal\router\router.go:248:if path == "/health" {
gateways\zgate\internal\router\router.go:252:if path == "/admin/reload" {
gateways\zgate\internal\router\router.go:253:s.reload(w, r)
gateways\zgate\internal\router\router.go:280:s.aliases.Reload()
gateways\zgate\internal\router\router.go:642:s.aliases.Reload()
gateways\zgate\internal\router\router.go:959:// reload re-reads zgate.json and applies the parts that can change at runtime:
gateways\zgate\internal\router\router.go:962:// path still need a restart.
gateways\zgate\internal\router\router.go:963:func (s *Server) reload(w http.ResponseWriter, r *http.Request) {
gateways\zgate\internal\router\router.go:969:next, err := config.Load(old.Path)
gateways\zgate\internal\router\router.go:974:ks := keys.Load(next.ProviderConfig, next.WBGatewayConfig, next.QoderEnvFile, next.QwenEnvFile, next.QiniuEnvFile, next.CliproxyEnvFile)
gateways\zgate\internal\router\router.go:975:applied, stale, added := s.sup.ApplyConfig(next.Children)
gateways\zgate\internal\router\router.go:977:s.aliases.Reload()
gateways\zgate\internal\config\config.go:1:// Package config loads zgate.json and applies defaults, env overrides and
gateways\zgate\internal\config\config.go:68:exe, err := os.Executable()
gateways\zgate\internal\alias\alias.go:59:// Map is a hot-reloading view of the alias file.
gateways\zgate\internal\alias\alias.go:71:m.Reload()
gateways\zgate\internal\alias\alias.go:78:// Reload re-reads the file when it changed. It is cheap enough to call per request.
gateways\zgate\internal\alias\alias.go:79:func (m *Map) Reload() {
gateways\zgate\internal\alias\alias.go:87:same := m.data != nil && stat.ModTime().Equal(m.mtime) && stat.Size() == m.size
gateways\zgate\internal\alias\alias.go:102:m.mtime = stat.ModTime()
gateways\zgate\internal\supervisor\supervisor.go:185:// Copy under the lock: ApplyConfig may replace k.cfg at any time and
gateways\zgate\internal\supervisor\supervisor.go:356:ticker := time.NewTicker(5 * time.Second)
gateways\zgate\internal\supervisor\supervisor.go:473:// ApplyConfig updates policies, idle thresholds and windows of existing children.
gateways\zgate\internal\supervisor\supervisor.go:474:// New children need a restart (the executable and port layout is boot-time only).
gateways\zgate\internal\supervisor\supervisor.go:475:func (s *Supervisor) ApplyConfig(cfg map[string]config.Child) (applied, unknownKeep, added []string) {
gateways\zgate\internal\supervisor\supervisor.go:501:// States is the /health view of every child.
gateways\zgate\internal\winproc\winproc_windows.go:67:HideWindow:    true,
gateways\zgate\internal\winproc\winproc_windows.go:131:HideWindow:    true,
gateways\zgate\internal\winproc\console_windows.go:25:procFreeConsole   = kernel32.NewProc("FreeConsole")
gateways\zgate\internal\winproc\console_windows.go:28:// AttachParentConsole rebinds stdout/stderr to the terminal that launched us.
gateways\zgate\internal\winproc\console_windows.go:40:// half-dead for as long as the gateway runs. DetachConsole undoes the attach
gateways\zgate\internal\winproc\console_windows.go:43:func AttachParentConsole() bool {
gateways\zgate\internal\winproc\console_windows.go:58:// DetachConsole releases a console taken by AttachParentConsole: output keeps
gateways\zgate\internal\winproc\console_windows.go:64:func DetachConsole() bool {
gateways\zgate\internal\winproc\console_windows.go:68:ok, _, _ := procFreeConsole.Call()



listener 继承 / SIGHUP / debug / control 专项：
无命中


二进制变更检测 / fsnotify / syscall.Exec 专项：
F:\Project\ModelBus\gateways\zgate\main.go:389:exe, err := os.Executable()
F:\Project\ModelBus\gateways\zgate\main.go:430:exe, err := os.Executable()
F:\Project\ModelBus\gateways\zgate\internal\supervisor\supervisor.go:276:go s.watch(k.name, proc)
F:\Project\ModelBus\gateways\zgate\internal\supervisor\supervisor.go:294:func (s *Supervisor) watch(name string, proc *winproc.Process) {
F:\Project\ModelBus\gateways\zgate\internal\config\config.go:68:exe, err := os.Executable()


```

## 5. 配置热加载能力

`gateways/zgate/internal/config/config.go`（324 行）签名与关键行：
```text
gateways/zgate/internal/config/config.go:15: type Log struct {
gateways/zgate/internal/config/config.go:16: 	Dir   string `json:"dir"`
gateways/zgate/internal/config/config.go:17: 	File  string `json:"file"`
gateways/zgate/internal/config/config.go:18: 	MaxMB int    `json:"maxMB"`
gateways/zgate/internal/config/config.go:19: }
gateways/zgate/internal/config/config.go:20: 
gateways/zgate/internal/config/config.go:21: // Upstream is one channel: where it lives and which child (if any) serves it.
gateways/zgate/internal/config/config.go:22: type Upstream struct {
gateways/zgate/internal/config/config.go:29: type Child struct {
gateways/zgate/internal/config/config.go:30: 	Policy              string   `json:"policy"` // always | ondemand
gateways/zgate/internal/config/config.go:31: 	IdleSeconds         int      `json:"idleSeconds"`
gateways/zgate/internal/config/config.go:32: 	Exe                 string   `json:"exe"`
gateways/zgate/internal/config/config.go:33: 	Args                []string `json:"args"`
gateways/zgate/internal/config/config.go:34: 	Cwd                 string   `json:"cwd"`
gateways/zgate/internal/config/config.go:35: 	Port                int      `json:"port"`
gateways/zgate/internal/config/config.go:36: 	Health              string   `json:"health"`
gateways/zgate/internal/config/config.go:37: 	StartTimeoutSeconds int      `json:"startTimeoutSeconds"`
gateways/zgate/internal/config/config.go:38: 	// Windows are local-time "HH:MM-HH:MM" ranges during which the child is
gateways/zgate/internal/config/config.go:39: 	// treated as policy=always (sign-in / keepalive slots). Empty means never.
gateways/zgate/internal/config/config.go:40: 	Windows []string `json:"windows"`
gateways/zgate/internal/config/config.go:41: }
gateways/zgate/internal/config/config.go:42: 
gateways/zgate/internal/config/config.go:43: // Config is the whole file.
gateways/zgate/internal/config/config.go:44: type Config struct {
gateways/zgate/internal/config/config.go:62: // Load reads path (or the default next to the binary) and normalises it.
gateways/zgate/internal/config/config.go:63: func Load(path string) (*Config, error) {
gateways/zgate/internal/config/config.go:64: 	if path == "" {
gateways/zgate/internal/config/config.go:65: 		path = os.Getenv("ZGATE_CONFIG")
gateways/zgate/internal/config/config.go:66: 	}
gateways/zgate/internal/config/config.go:67: 	if path == "" {
gateways/zgate/internal/config/config.go:68: 		exe, err := os.Executable()
gateways/zgate/internal/config/config.go:69: 		if err == nil {
gateways/zgate/internal/config/config.go:70: 			path = filepath.Join(filepath.Dir(exe), "zgate.json")
gateways/zgate/internal/config/config.go:97: func (c *Config) applyDefaults() {
gateways/zgate/internal/config/config.go:212: func (c *Config) resolvePaths() error {
gateways/zgate/internal/config/config.go:248: func (c *Config) resolve(p string) string {
gateways/zgate/internal/config/config.go:266: func (c *Config) resolveExe(p string) string {
gateways/zgate/internal/config/config.go:283: func (c *Config) resolveArg(a string) string {
gateways/zgate/internal/config/config.go:294: var rePercentVar = regexp.MustCompile(`%([A-Za-z_][A-Za-z0-9_]*)%`)
gateways/zgate/internal/config/config.go:296: func expandEnv(s string) string {
```
- `func Load(path string) (*Config, error)`（:63）只在启动时（`:68-70` 默认 `filepath.Join(filepath.Dir(exe), "zgate.json")`）和 `/admin/reload`（`router.go:969`）被调用；**没有 `Reload()` 方法**，没有 `Watch()`/`fsnotify`，没有 `NewTicker` 定时，也没有信号触发。
`gateways/zgate/internal/alias/alias.go`（137 行）：
```text
gateways/zgate/internal/alias/alias.go:59: // Map is a hot-reloading view of the alias file.
gateways/zgate/internal/alias/alias.go:60: type Map struct {
gateways/zgate/internal/alias/alias.go:69: func New(path string) *Map {
gateways/zgate/internal/alias/alias.go:70: 	m := &Map{path: path}
gateways/zgate/internal/alias/alias.go:71: 	m.Reload()
gateways/zgate/internal/alias/alias.go:72: 	return m
gateways/zgate/internal/alias/alias.go:73: }
gateways/zgate/internal/alias/alias.go:74: 
gateways/zgate/internal/alias/alias.go:75: // Path is the file this map watches.
gateways/zgate/internal/alias/alias.go:76: func (m *Map) Path() string { return m.path }
gateways/zgate/internal/alias/alias.go:77: 
gateways/zgate/internal/alias/alias.go:78: // Reload re-reads the file when it changed. It is cheap enough to call per request.
gateways/zgate/internal/alias/alias.go:79: func (m *Map) Reload() {
gateways/zgate/internal/alias/alias.go:87: 	same := m.data != nil && stat.ModTime().Equal(m.mtime) && stat.Size() == m.size
gateways/zgate/internal/alias/alias.go:96: 	var next file
gateways/zgate/internal/alias/alias.go:97: 	if err := json.Unmarshal(raw, &next); err != nil {
gateways/zgate/internal/alias/alias.go:98: 		return
gateways/zgate/internal/alias/alias.go:99: 	}
gateways/zgate/internal/alias/alias.go:100: 	m.mu.Lock()
gateways/zgate/internal/alias/alias.go:101: 	m.data = &next
gateways/zgate/internal/alias/alias.go:102: 	m.mtime = stat.ModTime()
gateways/zgate/internal/alias/alias.go:108: func (m *Map) Count() int {
gateways/zgate/internal/alias/alias.go:118: func (m *Map) Resolve(model string) (Target, bool) {
```
- `func (m *Map) Reload()`（:79）用 `stat.ModTime().Equal(m.mtime) && stat.Size() == m.size`（:87）判断文件是否变化，:102 更新 mtime；注释 `:78 "Reload re-reads the file when it changed. It is cheap enough to call per request."`。这是**每请求惰性轮询**，不是 watch；且只覆盖 alias map 文件，不覆盖 `zgate.json` 与 exe。
- `keys.Load`（`keys.go:113`）读环境变量与配置文件，`keys.go:25 env()` 从 `os.Getenv` 取；`/admin/reload` 会重跑一次，但环境变量变化需要启动该进程的环境已变更，运行中进程读不到后来才设的外部环境变量。
- **结论：配置热加载是「HTTP 手动触发 + 局部生效」；改 Go 代码后自动生效完全不存在**，必须换二进制并重启进程。

## 6. 文档与 PROGRESS 相关段落（原文 + 行号）

检索范围：`AGENTS.md`、`README.md`、`PROGRESS.md`、`CHANGELOG.md`、`CONTRIBUTING.md`、`SECURITY.md`、`docs/**/*.md`（排除 `docs/archive/`）、`memories/**/*.md`。正则：`重启|生效|旧二进制|生产实例|守护|自愈|服务|计划任务|自启|后台|热加载|reload|restart|scheduled task|Startup|登录|自动替换|自动生效|杀死|DSH|zgate|wb2api|mihomo|gateway|DETACHED|windowsgui|Job Object|Stop-Process`。下面按文件给出命中行及上下各 1 行原文（真实行号）。

### AGENTS.md
```text
  ...
  AGENTS.md:46: | OpenCode-Go 的 `oc_sk_…` | `provider_config.json` 里的 `providerConfigRules.providerRules[].config.access.apiKey`（脚本自己读） |
  AGENTS.md:47: | WorkBuddy 网关 `api_key` | 环境变量 **`WB_GATEWAY_KEY`** |
  AGENTS.md:48: | 网关地址 | 环境变量 **`WB_GATEWAY_BASE`**（默认 `http://127.0.0.1:7863`） |
  AGENTS.md:49: | ZCode 配置文件路径 | 环境变量 **`ZCODE_PERSONAL_PROVIDER_CONFIG_FILE`** |
  ...
  AGENTS.md:73: 
  AGENTS.md:74: ## 4. 目录两轴：`gateways/` 跑进程，`providers/` 跑脚本
  AGENTS.md:75: 
  AGENTS.md:76: - `gateways/` 只放**会被启动的东西**：`zgate`（Go 入口）、`legacy-router`（旧 Node 路由，回退用）、
  AGENTS.md:77:   `upstream/{workbuddy,qoder}`（上游 clone，gitignored）。
  ...
  AGENTS.md:79: - `tools/` 放跨供应商工具（`model_alias` / 榜单 / 探测 / 文档与密钥检查）。
  AGENTS.md:80: - 判断规则一句话：会被启动 → `gateways/`；被手动执行 → `providers/`；跨供应商复用 → `tools/`。
  AGENTS.md:81: 
```
### CHANGELOG.md
```text
  ...
  CHANGELOG.md:62: 
  CHANGELOG.md:63: ### 选型修三处硬伤：HY4 归位、探活真正生效、渠道排序表（2026-11-06）
  CHANGELOG.md:64: 
  ...
  CHANGELOG.md:125:      版本高者优先、同版本贵者优先；免费组不占配额）。
  CHANGELOG.md:126:   5. `gateways/zgate/internal/router/router.go` —— 新增 `quotaCooldown = 24h` 与
  CHANGELOG.md:127:      `quotaExhausted`：额度烧光类的 4xx（`Free quota exhausted` / `AllocationQuota` /
  ...
  CHANGELOG.md:134: 
  CHANGELOG.md:135: ### zgate：地区受限 403 冷却该跳（2026-11-06）
  CHANGELOG.md:136: 
  ...
  CHANGELOG.md:139:   `403 RegionError: This model is not available in your country`、机场出口 200；
  CHANGELOG.md:140:   `zgate.log` 尾部 4000 行里 hop1=367 / hop2=367 / `403 fallback`=359 —— 每个请求都先
  CHANGELOG.md:141:   白撞一次直连 403 再回落。原因是 `regionBlocked()` 只让 `chainAccept` 返回 false（回落），
  CHANGELOG.md:142:   从不冷却该跳，于是同一跳每次都要重试。
  CHANGELOG.md:143: - 改动（`gateways/zgate/internal/router/router.go`）：新增 `regionCooldown = 30m`；
  CHANGELOG.md:144:   chat 路径 `accept` 闭包与桥接路径都改为「地区受限 403 **且** 链里存在同 channel + 同
  ...
  CHANGELOG.md:157:   beam，硬排会把两个坏型号的 403 提前；运行期学习更准。
  CHANGELOG.md:158: - 生效：候选二进制 `%LOCALAPPDATA%\ZCodeGateway\zgate-0.3.0-cand.exe`，需要用户执行
  CHANGELOG.md:159:   `swap-zgate.ps1` 受控重启后生效（长驻网关不由会话重启）。
  CHANGELOG.md:160: 
  ...
  CHANGELOG.md:162: 
  CHANGELOG.md:163: ### zgate：桥接流式不再限制在链尾跳（2026-11-06）
  CHANGELOG.md:164: 
  ...
  CHANGELOG.md:174: 
  CHANGELOG.md:175: - 改动（`gateways/zgate/internal/router/router.go`）：门控改为 `streaming := wantsStream(body)`。
  CHANGELOG.md:176:   安全性不变：非 2xx 在任何字节写出之前就以 `Result` 返回，回落逻辑照旧；200 之后断流本来也回不了落。
  CHANGELOG.md:177: - 顺带修（`gateways/zgate/internal/bridge/bridge.go`）：非流式路径的空闲看门狗用的是流式那档 `DefaultIdle = 30s`。
  CHANGELOG.md:178:   非流式上游只有整段生成完才吐字节，生成超过 30 秒的正常回答会被误判成 `upstream silent ... 504`；
  CHANGELOG.md:179:   新增 `DefaultIdleNonStream = DefaultTimeout`（120s），让总超时当唯一硬闸。
  CHANGELOG.md:180: - 测试：新增 `gateways/zgate/internal/router/stream_test.go` —— `TestBridgeStreamsOnNonTailHop`
  CHANGELOG.md:181:   （首跳上游先吐 A 再阻塞，客户端必须在上游完成前收到第一个 chunk）、
  CHANGELOG.md:182:   `TestBridgeRegionBlockedFallsBackWithStream`（流式上行撞 403 RegionError 仍要回落孪生跳并冷却）。
  CHANGELOG.md:183: - 候选二进制 md5 `c96615631f3a52baf5adaa1a17375064`，等用户执行 `swap-zgate.ps1` 生效。
  CHANGELOG.md:184: - 回落护栏：`attemptChain` 的回落条件加 `!cw.written &&`。`bridge` 目前在「已写过 chunk」之后
  ...
  CHANGELOG.md:188:   客户端必须只看到「流内报错 + 收口」、下一跳零命中、状态码仍 200）。
  CHANGELOG.md:189: - 现网已于 21:10:28 换上流式修复版 `c9661563…`（`gateways/zgate/zgate.exe`，上一版存为
  CHANGELOG.md:190:   `%LOCALAPPDATA%\ZCodeGateway\zgate.exe.bak-20261106-211027`）；同题实测 Claude-Haiku-5.5
  CHANGELOG.md:191:   `ttfb 2.227s / total 3.676s`、46 条 data 行（改动前 `1.739s / 1.739s`、4 条）。
  CHANGELOG.md:192: - 含回落护栏的新候选是 `f66ef8f97f992caad1eb248ae928cdde`（`%LOCALAPPDATA%\ZCodeGateway\zgate-0.3.0-cand.exe`）。
  CHANGELOG.md:193:   护栏分支今日不可达，与现网行为等价，等下次换二进制时一并生效，无需为此单独重启网关。
  CHANGELOG.md:194: 
  ...
  CHANGELOG.md:206:   `TAIL_HOPS`（QW 一年期预付尾跳），其余按价格 / 前缀 / 渠道 / 名称稳定排序。
  CHANGELOG.md:207: - 改动：`DEMOTE_HOPS` 常量与排序分支**整段删除**（不是清空），限流改由 zgate
  CHANGELOG.md:208:   逐跳回落处理；`~/.zcode/v2/model-alias-map.json` 里 `DeepSeek-4.1-Flash` 的链改回
  CHANGELOG.md:209:   `WB -> OC -> OC -> QW`（zgate 按 mtime 每请求热加载别名表，未重启长驻网关）；
  CHANGELOG.md:210:   `~/.dsh/tools/demote-throttled-hop.mjs` 已替换为拒绝执行的废弃桩，原实现留档
  CHANGELOG.md:211:   `~/.dsh/backups/demote-throttled-hop.mjs.disabled-20261105`。
  CHANGELOG.md:212: - 测试：`tests/test_model_alias_demote.py` 换成 `tests/test_model_alias_hop_order.py`，
  ...
  CHANGELOG.md:215:   型号 WB 不在第 0 位即红。全量 44 用例通过。
  CHANGELOG.md:216: - 实测：15:45:11 zgate 按需拉起 `wb2api.exe`（pid 40640），请求改走
  CHANGELOG.md:217:   `WB:cn:deepseek-v4.1-flash` 并返回 200；生成器 dry-run 的 19 条链里 9 条含 WB，
  ...
  CHANGELOG.md:232: 
  CHANGELOG.md:233: - 新增 `tools/dsh_sync.py`：读取 ZCode 最终三组，重写 DeepSeekRuntime
  CHANGELOG.md:234:   `~/.dsh/profiles/desktop/cordis.patch.yml` 的 `llm-pi-ai` 段；保留其他 patch
  CHANGELOG.md:235:   条目与非 `zcode-*` provider，`reasoningLevel.map="{}"` 的模型不写 reasoningEfforts
  CHANGELOG.md:236: - 使用默认 ZCode 配置路径时，`tools/model_alias.py --apply` 会在写完后自动调用它；
  CHANGELOG.md:237:   DSH 未安装跳过，失败只告警不阻断；`--config` 沙盒不投影，`--no-dsh` 可关闭
  CHANGELOG.md:238: - 日常 12:00 自动化、`docs/TOOLS.md`、`docs/MAINTENANCE.md` 同步更新
  ...
  CHANGELOG.md:242: - 上游 `40d98f9 → e6dd088`（27 个提交），本地保留 `.gitignore` / `main.go` 脱敏两处补丁；
  CHANGELOG.md:243:   `go test ./...` 全通过后重编并替换 `wb2api.exe`
  CHANGELOG.md:244: - 面板目录回到 20 条：新增 `cn:hy4free`（0 分，显示 `HY4-Free`，进免费组）与
  ...
  CHANGELOG.md:261: - `docs/PITFALLS.md` §71 删掉从未入库的测试文件引用，验证方式改为在线实测
  CHANGELOG.md:262: - `docs/TOOLS.md` zgate 行 Qoder 策略 `always` → `ondemand`（与 zgate.json 一致）
  CHANGELOG.md:263: - `memories/opencode-go-zcode-models.md` 更新为现行定时任务（12:00 / `automation-3e2f8a53-*`）
  ...
  CHANGELOG.md:279: 
  CHANGELOG.md:280: ### zgate 安全微优化：hopKey 脱敏、chat 504 冷却对齐、idleReader 竞态修复（2026-11-01）
  CHANGELOG.md:281: 
  ...
  CHANGELOG.md:306: - `go vet ./...` + `go test ./... -count=1` 全绿；`tests/test_model_alias_price.py`
  CHANGELOG.md:307:   10/10；`python gateways/zgate/build.py` 重建并过 PE 子系统校验（GUI）。
  CHANGELOG.md:308:   **zgate.exe 是构建产物（不入库）：本轮已重建，运行中的网关仍是旧镜像，需人工
  CHANGELOG.md:309:   重启后才生效**
  CHANGELOG.md:310: 
  ...
  CHANGELOG.md:312: 
  CHANGELOG.md:313: 对 10-26 后三笔 zgate 网络提交（f8084ec / 502fc16 / 3dcb126）做增量审查发现的
  CHANGELOG.md:314: 三处明显错误，均为让代码回到其自身文档口径，不改设计：
  ...
  CHANGELOG.md:331:   （502fc16 起链尾带机场孪生跳，该测试 10-30 起本地跑必挂）
  CHANGELOG.md:332: - `go test ./... -count=1` 全绿；`python gateways/zgate/build.py` 重建产物并过
  CHANGELOG.md:333:   PE 子系统校验（GUI）。**zgate.exe 是构建产物（不入库）：改动需重建 + 重启
  CHANGELOG.md:334:   网关进程才生效**
  CHANGELOG.md:335: 
  ...
  CHANGELOG.md:338: - 事故：机场节点到 opencode.ai 的路径对大包短暂黑洞（POST ≥5 KB 挂 5s，GET 正常），
  CHANGELOG.md:339:   zgate 把 `client.Do` 的 EOF 直接交给下一跳，一跳链（`Beam`）没有下一跳 → 502
  CHANGELOG.md:340: - 修：`doForwardWith` 里传输层错误先重试同一跳一次（300ms，`txRetry` 与 429 的
  CHANGELOG.md:341:   `attempt` 分开计数）；桥接路径同样重试，但只在 `!cw.written` 时做，避免重复输出
  CHANGELOG.md:342: - 只重试 `EOF / TLS handshake timeout / connection reset / i/o timeout / broken pipe /
  CHANGELOG.md:343:   connection refused`；普通 5xx 不重试（上游可能已计费）
  ...
  CHANGELOG.md:349: - alias map 的每一跳新增可选 `proxy` 字段：同一 upstream 可以在链里出现两次、只差出口。
  CHANGELOG.md:350:   `alias.Hop` 加 `Proxy`，zgate 用 `EgressRouter`（按请求 context 挑 `*http.Transport`）
  CHANGELOG.md:351:   实现，`bridge.Forward` / `doForwardWith` 签名都不动
  ...
  CHANGELOG.md:384: 
  CHANGELOG.md:385: - **首字慢的根因修复**：`zgate` 协议桥调上游时写死 `stream: false`，整段生成完
  CHANGELOG.md:386:   才合成一个 chat SSE chunk —— 实测 Conatus 12.06s 才收到第一个（也是唯一的）
  ...
  CHANGELOG.md:415: - 新渠道 `QN`：`https://api.qnaigc.com/v1`（只提供 Anthropic Messages），
  CHANGELOG.md:416:   经 `zgate` 协议桥接入，`qn:` 前缀裸 id 也能直接落对上游
  CHANGELOG.md:417: - `qiniu/conatus-free` → 显示名 **`Conatus`**（后于 2026-10-29 去掉 `-Free` 后缀），进免费组；
  ...
  CHANGELOG.md:452:   千问 messages 0.00`。第三跳用 `TAIL_HOPS` 钉在链尾（OC 月度额度先用完，¥300 一年期兜底）
  CHANGELOG.md:453: - `gateways/zgate`：链路支持**混协议**——`alias.Hop` 增加 `protocol` 字段，
  CHANGELOG.md:454:   `attemptChain` 按每跳自己的协议派发（chat 直转 / messages·responses 过桥）
  ...
  CHANGELOG.md:482:   （118 个家族的控制台快照）、`.env.local`（`QWEN_API_KEY`，gitignored）
  CHANGELOG.md:483: - 新增 `QW` 渠道：`gateways/zgate` 的 `config.go` / `keys.go` / `router.go` /
  CHANGELOG.md:484:   `main.go` / `zgate.json` —— 上游只提供 **Anthropic Messages**（`/v1/models` 与
  CHANGELOG.md:485:   OpenAI 兼容路径均 404），经既有协议桥转发；`/health` 增 `qwen` 视图
  ...
  CHANGELOG.md:500:   `tools/model_alias.py --pools/--no-pools` 负责把池子写成合成条目（`kind: pool`）；
  CHANGELOG.md:501:   `gateways/zgate` 新增**死跳判定与 30 分钟冷却**（`Model not exist` / 额度耗尽 / 402
  CHANGELOG.md:502:   一律换下一跳，并记住该跳，`/health` 暴露 `cooling`）
  ...
  CHANGELOG.md:505: 
  CHANGELOG.md:506: - 修复 `gateways/upstream/qoder/qoder_proxy.py` —— `RateLimited` 补上
  CHANGELOG.md:507:   `status=429` / `retry_after`。此前排队重试耗尽后，流式请求的 pump 错误处理读
  ...
  CHANGELOG.md:537: 
  CHANGELOG.md:538: ### zgate 上游握手超时 15s → 8s（2026-10-27）
  CHANGELOG.md:539: 
  CHANGELOG.md:540: - 调整 `gateways/zgate/main.go` —— `http.Transport.TLSHandshakeTimeout` 由 15s 收到 8s。
  CHANGELOG.md:541:   透明代理链路握手会抖（实测正常 0.32s、坏窗口 0.6–7.7s、再往上完全不返回），
  ...
  CHANGELOG.md:548: 
  CHANGELOG.md:549: ### zgate 构建入口收口 + 无窗产物防回退（2026-10-27）
  CHANGELOG.md:550: 
  CHANGELOG.md:551: - **新增 `gateways/zgate/build.py` —— zgate 的唯一构建入口**。带 `-H windowsgui`
  CHANGELOG.md:552:   编译（GUI 子系统 → 登录自启零窗口），并**强制校验产物的 PE `Subsystem` 必须是 2**，
  CHANGELOG.md:553:   不合格直接非零退出。三个用法：
  CHANGELOG.md:554:   - `python gateways/zgate/build.py` —— 构建（Windows）+ 校验；
  CHANGELOG.md:555:   - `python gateways/zgate/build.py --check` —— 只校验现有产物，不编译；
  CHANGELOG.md:556:   - `python gateways/zgate/build.py --cross-check` —— 交叉编译一份 windows/amd64
  CHANGELOG.md:557:     到临时目录再校验；`-H windowsgui` 是 windows 链接器 flag，**交叉编译时同样生效**，
  CHANGELOG.md:558:     所以这条校验在 Linux CI 上也能真跑起来。
  ...
  CHANGELOG.md:562:   静默顶掉无窗版。两者后果相同，但归因要精确到单包命令。
  CHANGELOG.md:563: - **补上「为什么会回退」的这一环**：`-H windowsgui` 是**链接期** flag，只在那一次编译里
  CHANGELOG.md:564:   生效，事后无法从源码判断，只能读产物的 PE 头 —— 所以光在文档里写对命令不够，
  CHANGELOG.md:565:   必须有工具在编译后当场校验。文档记对了、手滑一次就回退（10-26 即如此）。
  CHANGELOG.md:566: - **CI 增加一步** `python3 gateways/zgate/build.py --cross-check` —— flag 丢了在 CI 就红，
  CHANGELOG.md:567:   不用等下次开机才发现弹窗。
  ...
  CHANGELOG.md:572:   - `docs/TROUBLESHOOTING.md` §16（新增）—— 排错：现象 → 排查 → 原因/解法；
  CHANGELOG.md:573:   - `docs/MAINTENANCE.md` §8.1 —— 构建命令正本改为 `python gateways/zgate/build.py`，
  CHANGELOG.md:574:     并写明**别在 `gateways/zgate/` 里裸跑 `go build .`**，检查用 `go vet ./...`；
  CHANGELOG.md:575:   - `docs/TOOLS.md` —— 把 `build.py` 登记进工具清单。
  ...
  CHANGELOG.md:577:   版本化记忆仍在本仓 `memories/`。
  CHANGELOG.md:578: - **本机状态核实（不入库）**：`gateways/zgate/zgate.exe` 的 `Subsystem` 已是 2；
  CHANGELOG.md:579:   但开工时 **zgate 进程根本没在跑**（7871 / 7863 / 8790 全部无人监听）。
  CHANGELOG.md:580:   根因是 **Windows Job Object 随 agent 会话结束回收整棵进程树** ——
  CHANGELOG.md:581:   日志里 `11:10:30 已启动` 之后连「已退出」都没有，进程被强杀；
  CHANGELOG.md:582:   而 ZCode app-server 新进程建于 `11:10:51`，与死亡时间吻合。
  CHANGELOG.md:583:   已用 explorer 拉起启动文件夹快捷方式恢复（父进程 explorer.exe，与登录自启同一条路径，
  CHANGELOG.md:584:   能存活；`nohup` / `setsid` / `Start-Process` 起的都会被回收）。
  ...
  CHANGELOG.md:589: 
  CHANGELOG.md:590: 无。原有 `go build -C gateways/zgate -ldflags "-H windowsgui" -o zgate.exe .`
  CHANGELOG.md:591: 仍然可用，`build.py` 只是把它包起来并加上产物校验。
  ...
  CHANGELOG.md:594: 
  CHANGELOG.md:595: 删掉 `gateways/zgate/build.py` 与 CI 里那一步即可，其余改动（文档、`.gitignore`）
  CHANGELOG.md:596: 无行为影响。已发布的 `zgate.exe` 不入库，回退不影响已装好的二进制。
  CHANGELOG.md:597: 
  ...
  CHANGELOG.md:606:   `opencode-go-chat-slow`，messages / responses 模型也按成本进四组，协议差异交给
  CHANGELOG.md:607:   zgate 按 alias map 桥接；`workbuddy_zcode_sync.py` 的备用档并入高耗。
  CHANGELOG.md:608:   新增协议提示缓存 `providers/opencode-go/cache/go_protocols.json`（不入库），
  ...
  CHANGELOG.md:623:   而从未探测的模型反而保留；改为瞬态保留并留痕。
  CHANGELOG.md:624: - 修复 zgate 查询串转发 —— `RawQuery` 不含 `?`，带 query 的请求路径被拼成
  CHANGELOG.md:625:   `.../completionsstream=1`（移植自 JS 的 `url.search`，语义差一个字符）；
  CHANGELOG.md:626:   补 `?` 并新增 `TestQueryStringIsForwarded`
  CHANGELOG.md:627: - 修复 zgate 其余项 —— 错误体改为限长 `ReadAll`（单次 `Read` 会拿到不完整片段）；
  CHANGELOG.md:628:   转发前去掉 `Accept-Encoding`（transport 禁用了透明解压，压缩体让
  ...
  CHANGELOG.md:630:   `r.Context()`；`attemptBridge` 只对 5xx/429 回退、末跳透传真实错误；
  CHANGELOG.md:631:   `/admin/reload` 同步热加载 key；`startChild` 锁外读 cfg 的竞态；alias 热加载
  CHANGELOG.md:632:   同时比较 mtime 与 size；boot 改为后台执行（先起 monitor，`Stop` 加守卫）；
  CHANGELOG.md:633:   `stop:""` 不再变成 `[""]`、错误文本按 rune 截断；install 的 PowerShell 单引号转义
  ...
  CHANGELOG.md:638: - 验证 —— `go build ./...` / `go vet ./...` / `go test ./...` 全绿（含新回归测试）；
  CHANGELOG.md:639:   相关 Python `py_compile`、JS `node --check` 通过；zgate 重建后 7871 端到端
  CHANGELOG.md:640:   （chat / messages / responses）由四组制批次实测 200
  ...
  CHANGELOG.md:643: 
  CHANGELOG.md:644: - **新增 `gateways/zgate`（Go）**：一个二进制顶掉原来的 Node 路由（`tools/unified-router.js`）
  CHANGELOG.md:645:   与 PowerShell 守护器（`workbuddy/zcode_gateway_watch.ps1`）。监听 `127.0.0.1:7871`，
  CHANGELOG.md:646:   做 alias 分流、chat ↔ messages/responses 协议桥、以及两个上游子进程的起停。
  CHANGELOG.md:647: - **子进程策略**：WorkBuddy `ondemand`（首个 WB 请求拉起，空闲 900 秒回收）；
  CHANGELOG.md:648:   Qoder `always`（签到不能停）。子进程装在 Windows Job Object 里，zgate 挂了不会留下孤儿。
  CHANGELOG.md:649: - **内存实测**：改造前 4 个进程 293.4 MB（PowerShell 守护器 124.2 + Node 路由 71.5 +
  CHANGELOG.md:650:   Qoder 70.1 + wb2api 27.6）；改造后 3 个进程 **99.3 MB**（zgate 18.5 + Qoder 57.2 + wb2api 23.2）；
  CHANGELOG.md:651:   WB 空闲回收后 76.1 MB；只留 zgate 时 18.5 MB。
  CHANGELOG.md:652: - **等价性**：新入口在 7971 与旧路由并行跑了 9 个用例（OC/WB/QD chat、messages 桥、
  CHANGELOG.md:653:   responses 桥、三种流式、未知模型），状态码/响应形态/SSE 事件序列 9/9 一致，之后才切到 7871。
  CHANGELOG.md:654:   `gateways/zgate/smoke_test.py` 保留为常设冒烟（6 项）。
  CHANGELOG.md:655: - **目录重构（破坏性）**：`workbuddy/gateway` → `gateways/upstream/workbuddy`；
  CHANGELOG.md:656:   `qoder/gateway` → `gateways/upstream/qoder`；三家采集脚本 → `providers/<vendor>/`；
  CHANGELOG.md:657:   旧 JS 路由 → `gateways/legacy-router/`（回退用，保留一个版本）。
  CHANGELOG.md:658:   `.gitignore`、4 个脚本的硬编码路径、19 篇文档与模板的路径已同步；
  CHANGELOG.md:659:   `zcode_gateway_watch.ps1/.vbs` 已删除，`.gitignore` 里两份过期备份也已清理。
  CHANGELOG.md:660: - **启动方式（破坏性）**：`zgate install` 写登录自启快捷方式（`schtasks ONLOGON` 在普通权限下
  CHANGELOG.md:661:   被拒绝）；`zgate status` 一次看全服务、子进程、端口与凭据有无；配置在
  CHANGELOG.md:662:   `gateways/zgate/zgate.json`。
  CHANGELOG.md:663: - **偏差说明**：没有实现「跟随 ZCode 主进程」——在 Go 里判主进程要读 PEB 命令行，代价高且脆；
  CHANGELOG.md:664:   改成 zgate 常驻（19 MB），顺带可以用 `always` 策略让 WorkBuddy 的定时任务在 ZCode 关闭时也跑。
  CHANGELOG.md:665: - **验证**：`go test ./...`（bridge/alias/router/supervisor 共 12 个用例）+ `go vet` + `gofmt`
  CHANGELOG.md:666:   全绿；四条通道真实请求 200；WB 冷启动 1.6 秒；CI 增加 Go 格式/构建/测试步骤。
  CHANGELOG.md:667: - **回退**：`zgate uninstall` → `node gateways/legacy-router/unified-router.js` 并手动起
  CHANGELOG.md:668:   `gateways/upstream/workbuddy/run.bat`；或 `git revert` 本次提交。
  CHANGELOG.md:669: 
  CHANGELOG.md:670: ### 追加：两个网关全部改按需 + 签到窗口 + 热加载（2026-10-23 晚）
  CHANGELOG.md:671: 
  ...
  CHANGELOG.md:675:   默认 WB 四档（9 / 10 / 21 / 22 点前后）、Qoder 三档（9 / 21 / 22 点），保住签到与保活。
  CHANGELOG.md:676: - **新增 `zgate reload` / `POST /admin/reload`**：策略、空闲阈值、窗口可热加载；
  CHANGELOG.md:677:   新增 child、监听地址与上游 base 仍需重启。
  CHANGELOG.md:678: - **修复**：协议桥补 120s 超时；`Process.Release` 改 `sync.Once`（double CloseHandle）；
  CHANGELOG.md:679:   `external` 接管实例纳入 5 秒健康轮询；重启退避改成 1s→2s→…→60s；日志运行期按 5 MB 轮转；
  CHANGELOG.md:680:   `zgate status` 不再打开写句柄；`qoder:` 前缀大小写不敏感；删除 `WaitExit` / `Missing` /
  CHANGELOG.md:681:   `Redacted` 等死代码。
  CHANGELOG.md:682: - **修复 回退链**：WorkBuddy 把上游 6004 模型限流转成 `400 {"code":"model_unavailable"}`，
  CHANGELOG.md:683:   旧逻辑只在 429/502/503/504 上重试，导致 `global:` → `cn:` 的回退从未生效。现在这种 400
  CHANGELOG.md:684:   按「池故障」触发回退，普通 400（参数错误）仍然直通不重试。
  CHANGELOG.md:685: - **配置解析修正**：`args` 里以 `/` 开头的参数（如 `cmd /c`）不再被当成路径解析。
  CHANGELOG.md:686: - **验证**：旁路实例实测「启动不起、窗内起、reload 后回收」；`go test ./...` 24 个用例全绿。
  CHANGELOG.md:687: 
  ...
  CHANGELOG.md:697:   `--write --push` 会再 `git add/commit/push`。日常自动化的最后一步加它。
  CHANGELOG.md:698: - 结果：28 个模型（主力 6 / 免费 5 / 低耗 8 / 高耗 9），排序与命名已线上生效。
  CHANGELOG.md:699: 
  ...
  CHANGELOG.md:716: - 结果：28 个模型（主力 6 / 免费 5 / 低耗 8 / 高耗 9）。
  CHANGELOG.md:717: - 上线：新二进制 + 新配置 + 新 alias map 由一次性计划任务在 21:41 一起替换并重启。
  CHANGELOG.md:718: 
  ...
  CHANGELOG.md:843: 
  CHANGELOG.md:844: - 新增 `qoder/` 适配器：qoder2api-hub（MIT）clone 到 `qoder/gateway/`（整目录
  CHANGELOG.md:845:   gitignore），默认 `127.0.0.1:8790`；API key 与面板密码持久化在
  ...
  CHANGELOG.md:865: 
  CHANGELOG.md:866: ### 追加：登录自启零窗口落地（2026-10-26）
  CHANGELOG.md:867: 
  CHANGELOG.md:868: - **zgate 改按 GUI 子系统构建**（`go build -ldflags "-H windowsgui"`，命令正本见
  CHANGELOG.md:869:   [docs/MAINTENANCE.md](docs/MAINTENANCE.md) §8.1）。此前发布的二进制实际是控制台程序，
  CHANGELOG.md:870:   登录自启会挂一个最小化 cmd 窗口：中文按 GBK 显示成乱码（日志本身是 UTF-8，没坏），
  CHANGELOG.md:871:   而且关掉该窗口等于杀掉网关。GUI 子系统下零窗口，日志只落
  CHANGELOG.md:872:   `%LOCALAPPDATA%\ZCodeGateway\zgate.log`。
  CHANGELOG.md:873: - **修复 `AttachParentConsole` 吞输出**：旧逻辑无条件把 stdout/stderr 重绑到父控制台，
  ...
  CHANGELOG.md:875:   继承句柄类型，管道/文件保留原样，只在句柄无效或本就是控制台时才接管 ——
  CHANGELOG.md:876:   `zgate status` 在 Git Bash、cmd、PowerShell 里都照常打印。
  CHANGELOG.md:877: - **顺带修复**：CHANGELOG 0.3.0 段落里四个小节整块重复的历史残留（并发写坏），
  ...
  CHANGELOG.md:990: - 修复 自动化 —— 重建每日自动收录任务为每天 **12:00**；取网关 key 的来源从
  CHANGELOG.md:991:   `provider_config.json` 的 `workbuddy-low` 改成 `workbuddy/gateway/config.json`
  CHANGELOG.md:992:   的 `api_key`（统一路由并组后 `workbuddy-*` provider 已不存在，原写法抛
  ...
  CHANGELOG.md:1001: 
  CHANGELOG.md:1002: ### 守护器生命周期加固（2026-10-21 深夜）
  CHANGELOG.md:1003: 
  CHANGELOG.md:1004: 排查「关掉 ZCode 后 wb2api 还在」：停止分支本来就有（当天 23:51 实测停过一次），
  CHANGELOG.md:1005: 真正的问题是主进程只按 PID 判活、ZCode 退出后 2–5 秒又被拉起会**静默**取消停止、
  CHANGELOG.md:1006: 守护器不在场时遗留的网关 / 路由没人清。
  CHANGELOG.md:1007: 
  CHANGELOG.md:1008: - 修复 脚本 —— `workbuddy/zcode_gateway_watch.ps1` 主进程改用**进程句柄**判存活
  CHANGELOG.md:1009:   （`Process.HasExited`），PID 被系统复用不再把已退出的 ZCode 误判成还在跑；
  CHANGELOG.md:1010:   连续两次认不出主进程才按退出处理
  CHANGELOG.md:1011: - 修复 脚本 —— **启动对账**：守护器启动时若没有 ZCode 主进程却还有网关 / 路由在监听，
  CHANGELOG.md:1012:   按遗留进程清掉（`-KeepOrphans` 可跳过，用于手动常驻网关）
  CHANGELOG.md:1013: - 修复 脚本 —— 停止时若没接管过 pid，按端口反查网关 / 路由再校验进程名与命令行，
  CHANGELOG.md:1014:   上次守护器留下的孤儿不会漏杀
  CHANGELOG.md:1015: - 调整 脚本 —— 宽限期 / 排空期 ZCode 回来都会写日志并取消停止（排空期回来还会把已停的
  CHANGELOG.md:1016:   统一路由立刻拉回）；排空上限默认 `30` → `5` 秒
  CHANGELOG.md:1017: - 新增 脚本 —— 每 15 分钟一条心跳日志（`-HeartbeatSeconds`），日志里没有心跳即说明守护器没了；
  CHANGELOG.md:1018:   `-Status` 增加脚本版本、守护器 pid，并在守护器进程早于脚本修改时间时提示「加载的是旧代码」
  CHANGELOG.md:1019: - 调整 文档 —— TOOLS / MAINTENANCE §8 / TROUBLESHOOTING §11 同步；补「关窗 ≠ 退出」
  ...
  CHANGELOG.md:1193: 
  CHANGELOG.md:1194: 反代（`wb2api`）不再需要手动开 cmd 拉起，网关寿命跟随 ZCode：
  CHANGELOG.md:1195: 
  CHANGELOG.md:1196: - 新增 脚本 —— `workbuddy/zcode_gateway_watch.ps1`：无窗口守护器。ZCode 启动 →
  CHANGELOG.md:1197:   静默拉起 `wb2api`（清空 HTTP(S)_PROXY，与 `run.bat` 一致）；ZCode 全部退出 →
  CHANGELOG.md:1198:   宽限 8 秒后停网关；运行期间每 15 秒探活，网关挂了自动重启（失败退避 60 秒）
  CHANGELOG.md:1199: - 新增 脚本 —— `workbuddy/zcode_gateway_watch.vbs`：wscript 无窗口启动上述 ps1，
  CHANGELOG.md:1200:   不出现控制台窗口
  CHANGELOG.md:1201: - 新增 开关 —— `-Install` 在启动文件夹注册快捷方式（登录自启）并立即启动守护器；
  CHANGELOG.md:1202:   `-Uninstall` 移除自启并停守护器；`-Status` 一次看 ZCode / 网关 / 守护器；
  CHANGELOG.md:1203:   `-DryRun` 只记状态迁移，用于验证状态机
  ...
  CHANGELOG.md:1212: 
  CHANGELOG.md:1213: - 变更 目录 —— 旧网关目录 `<旧网关安装目录>` → `workbuddy/gateway/`
  CHANGELOG.md:1214:   （含上游 `.git`、`config.json`、`auths/`、`data/`、`wb2api.exe`）；旧目录已删除
  CHANGELOG.md:1215: - 变更 忽略 —— 主仓 `.gitignore` 整目录排除 `workbuddy/gateway/`（账号凭据、密钥、
  CHANGELOG.md:1216:   运行时状态、二进制都不进公开仓库）；网关仍可用
  CHANGELOG.md:1217:   `git -C workbuddy/gateway pull --ff-only` 更新
  CHANGELOG.md:1218: - 变更 脚本 —— `zcode_gateway_watch.ps1` 的默认网关目录改为按脚本位置推导
  CHANGELOG.md:1219:   `<仓库>/workbuddy/gateway`（`WB_GATEWAY_DIR` 仍可覆盖）
  CHANGELOG.md:1220: - 变更 工具 —— `tools/check-docs.py` 跳过 `workbuddy/gateway/`（不入库的上游 clone）
  CHANGELOG.md:1221: - 调整 文档 —— MAINTENANCE §8（更新 / 重建网关目录的步骤）、TOOLS、SECRETS、
  ...
  CHANGELOG.md:1226: 
  CHANGELOG.md:1227: 守护器从「按进程名数数」升级为「盯主进程 + 就绪判定 + 排空」：
  CHANGELOG.md:1228: 
  ...
  CHANGELOG.md:1284:   模型再重放，避免重复
  CHANGELOG.md:1285: - 变更 守护器 —— `zcode_gateway_watch.ps1` 随 ZCode 启停统一路由；`-Status` 显示
  CHANGELOG.md:1286:   路由与五个 chat 组；新增 `-RouterPort` / `-RouterScript` / `-NoRouter`；
  ...
  CHANGELOG.md:1289:   TROUBLESHOOTING §11 / §12、PITFALLS §12、SECRETS、docs/README
  CHANGELOG.md:1290: - 说明 —— 统一路由是本地进程；ZCode 不开时由守护器停掉。回退：恢复
  CHANGELOG.md:1291:   `.bak-unified-*`，或 `workbuddy_zcode_sync.py --separate --apply` 重建四档
```
### CONTRIBUTING.md
```text
  ...
  CONTRIBUTING.md:12: 
  CONTRIBUTING.md:13: 统一入口 `gateways/zgate` 是 Go 代码，改完这样验：
  CONTRIBUTING.md:14: 
  CONTRIBUTING.md:15: ```bash
  CONTRIBUTING.md:16: cd gateways/zgate
  CONTRIBUTING.md:17: gofmt -l . && go vet ./... && go test ./...   # 单元测试（不联网）
  CONTRIBUTING.md:18: go build -o zgate.exe .
  CONTRIBUTING.md:19: ./zgate.exe status                             # 看服务/子进程/端口
  CONTRIBUTING.md:20: python smoke_test.py                           # 四条通道各打一发（会花少量额度）
  ...
  CONTRIBUTING.md:27: | `OPENCODE_GO_KEY` | OpenCode-Go 的 API key |
  CONTRIBUTING.md:28: | `WB_GATEWAY_KEY` | WorkBuddy 网关的 api_key |
  CONTRIBUTING.md:29: | `WB_GATEWAY_BASE` | 网关地址（默认 `http://127.0.0.1:7863`） |
  CONTRIBUTING.md:30: | `WB_PRICING_FILE` / `WB_ZCODE_PROBE_FILE` | 价格表 / 探测缓存路径 |
```
### PROGRESS.md
```text
  ...
  PROGRESS.md:25: - 19/19 模型规则与 providerId 一一对应；provider 顺序 主力→免费→低耗→高耗→对话→备用；文件 8591 字节、JSON 合法。
  PROGRESS.md:26: - 引擎 1s 轮询热加载，日志无 provider config 报错；写入后未被应用覆盖。
  PROGRESS.md:27: - 直连实测（2026-10-19 22:50）：关思考 `thinking:{type:"disabled"}` 有效 = longcat-2.0（3.6s→1.7s）、longcat-2.5-preview-free（8.7s→7.4s）、minimax-m3、deepseek-v4.1-flash（2.5s→1.4s）；`minimax-m3.1-flash-free` 用 `enable_thinking:false`（1.2s），`thinking:disabled` 会 400；glm-5.3-flash 三种参数都关不掉；beam-free 不需要关。
  ...
  PROGRESS.md:64: 
  PROGRESS.md:65: # 2026-10-20 10:00-10:50：全服务复盘（10 个子代理）+ 两次事故 + 干净出口体系
  PROGRESS.md:66: 
  ...
  PROGRESS.md:68: 
  PROGRESS.md:69: **同一个出口 IP，各家服务方的判定完全不同**——第三方 GeoIP 一律不可信：
  PROGRESS.md:70: 
  PROGRESS.md:71: | 服务 | 判定口径 | 实测结果（出口 <REDACTED-EXIT-IP>） |
  PROGRESS.md:72: |---|---|---|
  ...
  PROGRESS.md:80: 
  PROGRESS.md:81: **逐服务实测清单**（8 份报告在 `audit/agent-*.md`）：
  PROGRESS.md:82: - Google 判 CN 的节点 12 个；OpenAI 只封 3 个（香港WAP×3）；**交集 = 香港WAP**。
  ...
  PROGRESS.md:97:   YouTube 全族 + api.github.com）→ **一次 Google 会话只有一个出口 IP**，不再分裂。
  PROGRESS.md:98: - `🎥 NETFLIX` / `🎥 DISNEY` **保持新加坡**（印区不提供该服务，挪过去会制造新故障）。
  PROGRESS.md:99: - `🐟 漏网之鱼`（唯一 Match 兜底）**保持通用池**（全压单点更糟）。
  ...
  PROGRESS.md:104:    **恢复零人工干预**（配置/nft/分组选择/cron 全部自动回来）→ 反而验证了持久化工作 ✓。
  PROGRESS.md:105: 2. **10:43 OOM 杀 mihomo**：`Killed process CrashCore anon-rss:77240kB` → 代理整体下线。
  PROGRESS.md:106:    链路：hotupdate 关服务 → 进程被 OOM 杀 → **重启要拉订阅、而拉订阅又需要代理** → 死锁 → 代理起不来。
  PROGRESS.md:107:    修法：① 守护进程加"最近 30 分钟存活记录"状态文件，OOM 后能自动拉起（不依赖 pid 文件）；
  PROGRESS.md:108:         ② 清掉子代理在 tmpfs 留下的 48MB 垃圾（/tmp 51MB→3MB，可用内存 51MB→77MB）；
  ...
  PROGRESS.md:114: - `ai-api-check.sh` 1–15 节全绿；nft 四表齐备；内存 69MB avail；overlay 45%；负载 0.38。
  PROGRESS.md:115: - 守护进程每 5 分钟自愈：出口组漂移、nft 表缺失、静默回退、OOM 后拉起、内存水位告警。
  PROGRESS.md:116: 
  ...
  PROGRESS.md:167: ## 待解决 / 注意事项
  PROGRESS.md:168: - 复核时发现促销漂移：`cn:hy4-preview` 生效价已变 0（`0x`）、`cn:glm-5.2` 促销 x0.50。
  PROGRESS.md:169:   本次只重排未改档，下次完整 `workbuddy_zcode_sync.py --apply` 会把 `cn:hy4-preview` 挪进免代。
  ...
  PROGRESS.md:248: ## 任务目标
  PROGRESS.md:249: 用户要求：不要再手动开 cmd 拉起 `wb2api` 再开 ZCode —— 打开 ZCode 时反代自动就绪，
  PROGRESS.md:250: 关闭 ZCode 时反代跟着停；日常只点 ZCode。
  ...
  PROGRESS.md:252: ## 已完成变更
  PROGRESS.md:253: - [x] 新增 `workbuddy/zcode_gateway_watch.ps1`：无窗口守护器。ZCode 进程出现 → 静默拉起网关；
  PROGRESS.md:254:   全部退出 → 宽限 8 秒后停；运行期间每 15 秒探活，网关挂了自动重启（失败退避 60 秒）
  PROGRESS.md:255: - [x] 新增 `workbuddy/zcode_gateway_watch.vbs`：用 wscript 无窗口启动 ps1
  PROGRESS.md:256: - [x] `-Install` 注册开机自启（`%APPDATA%\...\Startup\ZCode Gateway Watch.lnk` →
  PROGRESS.md:257:   `wscript.exe "<工作区>\ZcodeAIModels\workbuddy\zcode_gateway_watch.vbs"`）并立即启动守护器
  PROGRESS.md:258: - [x] 接管原先 `run.bat` 手动拉起的网关；杀掉旧 cmd 树后 1 秒内静默重启（新 pid，无窗口）
  PROGRESS.md:259: - [x] 文档：TOOLS 工具表、MAINTENANCE §8（新增，原「相关文档」改 §9）、
  ...
  PROGRESS.md:262: ## 验收
  PROGRESS.md:263: - `-Status`：ZCode 运行中 / 网关监听 7863 / 守护器运行中；
  PROGRESS.md:264:   日志 `%LOCALAPPDATA%\ZCodeGateway\watchdog.log`（UTF-8）。
  PROGRESS.md:265: - 杀掉手动 cmd 树后日志：`网关无响应，尝试重启` → `已静默启动网关 pid=32400` → `网关就绪`；
  PROGRESS.md:266:   新进程 `MainWindowHandle=0`（无窗口）。
  PROGRESS.md:267: - 干跑状态机（`-DryRun -ProcessName ping`）：进程出现 → `将拉起网关`；退出 2 秒后 → `将停止网关`。
  PROGRESS.md:268: - 开机自启快捷方式目标 / 参数 / 工作目录已核对；当前守护器与 wscript 均无可见窗口。
  PROGRESS.md:269: 
  ...
  PROGRESS.md:274:   状态机已用假进程名干跑验证；下次正常关 ZCode 可看日志确认。
  PROGRESS.md:275: - 回退到手动：`zcode_gateway_watch.ps1 -Uninstall`，之后照旧 `run.bat` / `stop-gateway.bat`。
  PROGRESS.md:276: 
  ...
  PROGRESS.md:280: 
  PROGRESS.md:281: # 2026-10-21 网关目录并入本仓：上游无更新，clone 迁到 workbuddy/gateway
  PROGRESS.md:282: 
  ...
  PROGRESS.md:289:   0 ahead / 0 behind，无更新
  PROGRESS.md:290: - [x] 用 robocopy 把整个 clone（216 个文件，含 `.git`）复制到 `workbuddy/gateway/`；
  PROGRESS.md:291:   源码 / 配置 / 二进制哈希一致
  PROGRESS.md:292: - [x] 停旧守护器与旧网关 → 最后一次同步 `data/`、`auths/`、`config.json` →
  PROGRESS.md:293:   从新目录启动（pid 17924）→ `/panel/` 200 → 新守护器（pid 36472）接管
  PROGRESS.md:294: - [x] 删除旧目录 `E:\Tool\AITool\workbuddy2api-panel`（数据已迁走）
  PROGRESS.md:295: - [x] `zcode_gateway_watch.ps1` 默认目录改为 `$PSScriptRoot\gateway`；主仓 `.gitignore`
  PROGRESS.md:296:   排除整个 `workbuddy/gateway/`；`tools/check-docs.py` 跳过该目录
  PROGRESS.md:297: - [x] 文档：MAINTENANCE §8、TOOLS、SECRETS、TROUBLESHOOTING §11、NOTICE、CHANGELOG
  ...
  PROGRESS.md:300: - `-Status`：网关监听 7863（pid 17924，路径
  PROGRESS.md:301:   `<工作区>\ZcodeAIModels\workbuddy\gateway\wb2api.exe`），守护器运行中；
  PROGRESS.md:302:   网关日志显示恢复 139 个用量桶、4 个账号、cn / global 模型速率正常。
  PROGRESS.md:303: - `/panel/` 200；当前 ZCode 会话（走 workbuddy-low）请求正常。
  PROGRESS.md:304: - `git status` 不显示 `workbuddy/gateway/`（整目录已忽略）。
  PROGRESS.md:305: - 旧目录 `Test-Path` = False。
  ...
  PROGRESS.md:307: ## 待解决 / 注意事项
  PROGRESS.md:308: - 新机器 / 新克隆没有 `workbuddy/gateway/`（被 .gitignore 排除）：按 MAINTENANCE §8 的
  PROGRESS.md:309:   `git clone` + `config.json` + `auths/` + `go build` 重建。
  ...
  PROGRESS.md:311:   `go.mod` 把 redis 提为直接依赖），以后 `git pull` 前留意冲突。
  PROGRESS.md:312: - 上游后续更新：`git -C workbuddy/gateway pull --ff-only`。
  PROGRESS.md:313: 
  ...
  PROGRESS.md:320: ## 任务目标
  PROGRESS.md:321: 用户要求：联动、优化，让 ZCode 适配更好。落点放在守护器与 ZCode 的联动机制上
  PROGRESS.md:322: （provider 的模型元数据已齐全，不在本次改动范围）。
  ...
  PROGRESS.md:337: - `-Status`：主进程 pid=18360（共 37 个 ZCode 进程）、网关 pid=17924 且 `/panel/` 200、
  PROGRESS.md:338:   守护器运行中；低代 8 / 免代 6 / 高代 4 三个 provider 全部 `[OK；key 已配置]`。
  PROGRESS.md:339: - 干跑（`-DryRun -ProcessName ping`）：`检测到 ping 主进程启动` → `将拉起网关`；
  PROGRESS.md:340:   退出 2 秒后 `主进程已退出，2s 后停网关` → `将停止网关`。
  PROGRESS.md:341: - 新守护器（pid 23172）启动后日志显示 `检测到 ZCode 主进程启动（pid=18360）` →
  PROGRESS.md:342:   `网关已在监听...接管`；网关未重启，当前会话无断流。
  PROGRESS.md:343: - GUI / 渲染子进程（共 37 个）不影响主进程判定；`-Status` 的 provider 校验可读且不打印 key。
  ...
  PROGRESS.md:378: 
  PROGRESS.md:379: # 2026-10-21 守护器退出路径加固（关 ZCode 后 wb2api 残留）
  PROGRESS.md:380: 
  PROGRESS.md:381: ## 任务目标
  PROGRESS.md:382: 用户报告：wb2api 只跟随 ZCode 启动，不跟随退出。查清真实原因，
  PROGRESS.md:383: 并让网关 / 统一路由可靠地跟着 ZCode 主进程退出。
  ...
  PROGRESS.md:387:       当天 10 次托盘退出里 9 次在 2–5 秒内又被拉起，正好落在 8 秒宽限内 →
  PROGRESS.md:388:       守护器按设计取消停止（旧版不写这条日志）；23:51 那次间隔 18 秒，
  PROGRESS.md:389:       真实停过一次（8 秒宽限 + 30 秒排空），证明停止分支本身是通的。
  PROGRESS.md:390: - [x] `zcode_gateway_watch.ps1`：主进程改用 `Process.HasExited` 按句柄判存活，
  PROGRESS.md:391:       PID 被复用不再把已退出的 ZCode 误判成还在跑；连续两次认不出才按退出处理。
  ...
  PROGRESS.md:393:       （`-KeepOrphans` 跳过）。
  PROGRESS.md:394: - [x] 停止时 pid 未知 → 按端口反查，并校验 `wb2api` 进程名 / `unified-router.js` 命令行。
  PROGRESS.md:395: - [x] 宽限 / 排空期 ZCode 回来：写日志、取消停止；排空期回来立刻重新拉起路由。
  PROGRESS.md:396: - [x] 排空上限默认 30 → 5 秒；新增 15 分钟心跳（`-HeartbeatSeconds`）；
  PROGRESS.md:397:       `-Status` 显示脚本版本 / 守护器 pid，并在守护器进程早于脚本修改时间时提示旧代码。
  PROGRESS.md:398: - [x] 换上新守护器（pid 40976，VBS 无窗口启动），原网关 35732 / 路由 43136 被接管，未断流。
  PROGRESS.md:399: - [x] 文档：TOOLS、MAINTENANCE §8、TROUBLESHOOTING §11、CHANGELOG。
  ...
  PROGRESS.md:402: - 语法：`[Parser]::ParseFile` → SYNTAX OK。
  PROGRESS.md:403: - `-Status`：`守护器：运行中 v2026-10-21.2（pid=40976）`；网关 35732 `/panel/` 200；
  PROGRESS.md:404:   路由 43136 `/health` 就绪；五个 chat 组全部 `[OK；key 已配置]`。
  ...
  PROGRESS.md:415: - 若之后又出现「ZCode 长时间不在但网关还在」：先看 `watchdog.log` 是否有心跳和停止记录；
  PROGRESS.md:416:   没有心跳说明守护器被结束，`-Install` 重装即可，启动对账会清掉遗留进程。
  PROGRESS.md:417: 
  ...
  PROGRESS.md:434:       `免费/minimax-m3.1-flash-free`；prompt 取网关 key 改读
  PROGRESS.md:435:       `workbuddy/gateway/config.json` 的 `api_key`（原 `workbuddy-low` 在统一路由
  PROGRESS.md:436:       并组后已不存在，会抛 `StopIteration`）。
  ...
  PROGRESS.md:449: - 凭据复核：全仓无明文 key（`oc_sk_` 全文检索只命中文档里的前缀说明），
  PROGRESS.md:450:   `workbuddy/cache/` 与 `workbuddy/gateway/` 仍被 `.gitignore` 排除。
  PROGRESS.md:451: 
  ...
  PROGRESS.md:461: - **cn:deepseek-v4.1-flash 曾在 503**：唯一 CN 账号上该模型被 6004 模型频率限制锁住
  PROGRESS.md:462:   （网关 `/status` 的 `model_locks` 里有 `unlock_at`），到点自愈。
  PROGRESS.md:463: - 代理在 **OpenWrt 侧 ShellCrash**（网关透明代理），本机没有代理客户端；
  ...
  PROGRESS.md:503: - [x] 记账：CHANGELOG「收尾大扫除」段（含两笔脱敏提交）、本批次、MAINTENANCE §10 维护记录
  PROGRESS.md:504: - [x] 保留：`workbuddy/gateway/`（含凭据与二进制）、`.codegraph/`、`evidence/`、
  PROGRESS.md:505:       `opencode-go/probe/results/`、`workbuddy/cache/` 活数据、`workbuddy/logs/wb_zcode_probe.log`
  ...
  PROGRESS.md:579: ## 待解决 / 注意事项
  PROGRESS.md:580: - 历史提交 `92baac2` 的旧 blob 仍在 GitHub 上（force-push 不会立刻删服务端旧对象），
  PROGRESS.md:581:   旧 SHA 仍能读到泄漏内容。要彻底清需 `git filter-repo --replace-text` 重写并强推，
  ...
  PROGRESS.md:626: ## 任务目标
  PROGRESS.md:627: 用户后台看到 mimo 系列 + longcat 系列请求全 400/402。排查根因，并落实
  PROGRESS.md:628: 「跑不通就清掉，复通了下次同步再加回」的永久策略。
  ...
  PROGRESS.md:651:   配置未改动（与现状一致）；`longcat`/`mimo-v2.5-pro` 等确死的仍正常判不收录。
  PROGRESS.md:652: - 策略生效验证：下次若这些模型再 400/402/5xx，Go 同步 `--apply` 会直接 prune_model，
  PROGRESS.md:653:   不再只打 ⚠。
  ...
  PROGRESS.md:673: ## 已完成变更
  PROGRESS.md:674: - [x] clone `qoder2api-hub` 到 `qoder/gateway/`（整目录 gitignore，含自己的 `.git`）
  PROGRESS.md:675: - [x] 8790 启动：API key + 面板密码持久化到 `accounts/settings.json`，改用
  PROGRESS.md:676:       `start-qoder-proxy.bat` detached 运行；`qoder/.env.local` 只给脚本读
  PROGRESS.md:677: - [x] Qoder CN OAuth 设备授权，账号入库（`qoder.com.cn`，personal_professional_trial）；
  ...
  PROGRESS.md:701:   按「跑不通即清」暂不收录；复通后重新 probe + sync 会自动加回
  PROGRESS.md:702: - 免费 `DeepSeek-Flash` 也会排队：2026-10-23 17:10 服务端 64s 后 200，
  PROGRESS.md:703:   17:14 复测 93.9s 后 502（10605，queueCount 0）；probe 结果已加 `ever_ok`，
  PROGRESS.md:704:   排队/超时不误杀曾 200 的模型，只有从未成功过的才会被排除
  PROGRESS.md:705: - qoder2api-hub 目前是常驻 detached 进程，**未**接进 `zcode_gateway_watch.ps1`；
  PROGRESS.md:706:   重启机器后需要手动 `start-qoder-proxy.bat`（或以后再加守护）
  PROGRESS.md:707: - ZCode CLI 没有 `--model` 参数，无法用一条命令指定 `qoder/...` 做端到端对话；
  ...
  PROGRESS.md:732:       `--direct` 可直连 8790
  PROGRESS.md:733: - [x] 重启 7871 路由；写入合并配置：免费 1 个、低耗 2 个、高耗 4 个 Qoder 模型；
  PROGRESS.md:734:       provider 列表仍是 7 个
  ...
  PROGRESS.md:780: - [x] `workbuddy/zcode_effective_body.js`：叠加用户 `providerModelRules`，
  PROGRESS.md:781:       让新 ID 的 `map="{}"` 在探测里生效
  PROGRESS.md:782: - [x] `go_model_sync.py`：`WB:`/`OC:`/`QD:` 视作非 Go 模型跳过
  ...
  PROGRESS.md:885: ## 待解决 / 注意事项
  PROGRESS.md:886: - 5 个 WB GB 模型仍在池冷却；fallback 已生效，但 CN 号也冷却时会返回 503
  PROGRESS.md:887: - 自动峰谷切换需要 08:00/22:00 + 工作日 09:00/12:00/14:00/18:00 跑
  ...
  PROGRESS.md:1074:       `Step-5-Pre` / `LongCat-25-Pre`；`abbreviate()` 兜底新增
  PROGRESS.md:1075:       `preview\b -> Pre`（未列入 `ABBR` 的新模型也生效）
  PROGRESS.md:1076: - [x] 重跑 `model_alias.py --slot auto --apply`，四组与 alias map 重新生成
  ...
  PROGRESS.md:1096: 
  PROGRESS.md:1097: # 2026-10-23 第 N+13 轮：运行架构整合（zgate 单入口 + 目录两轴）
  PROGRESS.md:1098: 
  ...
  PROGRESS.md:1100: 用户确认 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) 的提案：把三个反代收进一个目录，
  PROGRESS.md:1101: 能用 Go 合并的合并，减少常驻内存；当前「每家一个目录 + 路由在 tools + 守护器在 workbuddy」
  PROGRESS.md:1102: 的结构不再适合仓库体量，一并整理可删可并的东西。
  ...
  PROGRESS.md:1104: ## 已完成变更
  PROGRESS.md:1105: - [x] 新增 `gateways/zgate`（Go 1.22，零第三方依赖）：7871 路由 + alias map 热加载 +
  PROGRESS.md:1106:       chat ↔ Anthropic Messages / OpenAI Responses 协议桥 + 子进程守护
  PROGRESS.md:1107:       （Job Object / 单飞拉起 / 健康检查 / 空闲回收 / 崩溃退避重启）
  PROGRESS.md:1108: - [x] 子命令：`serve` / `status` / `install` / `uninstall` / `version`；配置 `zgate.json`；
  PROGRESS.md:1109:       GUI 子系统 + `AttachConsole`，计划任务不闪窗、终端里照常输出
  PROGRESS.md:1110: - [x] 等价性：旧路由与新入口并行（7871 / 7971）跑 9 个用例，9/9 一致后才切流
  PROGRESS.md:1111: - [x] 目录重构：`workbuddy/gateway` → `gateways/upstream/workbuddy`，
  PROGRESS.md:1112:       `qoder/gateway` → `gateways/upstream/qoder`，三家脚本 → `providers/<vendor>/`，
  PROGRESS.md:1113:       旧 JS 路由 → `gateways/legacy-router/`（回退用）
  PROGRESS.md:1114: - [x] 同步修改：`.gitignore`、`tools/model_alias.py`、`tools/model_probe.py`、
  PROGRESS.md:1115:       `tools/check-docs.py`、`tools/check-secrets.py`、旧路由的两处凭据回退路径
  PROGRESS.md:1116: - [x] 删除：`zcode_gateway_watch.ps1` / `.vbs`、3 份过期的 `wb_pricing.json.bak-*`、
  PROGRESS.md:1117:       `__pycache__`
  PROGRESS.md:1118: - [x] 文档：`MAINTENANCE.md` §8 重写（zgate 生命周期/配置/日志/上游更新）、
  PROGRESS.md:1119:       `TOOLS.md` 工具表重排、`TROUBLESHOOTING.md` §11/§12 改写、
  ...
  PROGRESS.md:1125: - [x] 测试：`bridge` / `alias` / `router` / `supervisor` 共 12 个用例 + 冒烟
  PROGRESS.md:1126:       `gateways/zgate/smoke_test.py`；CI 增加 Go 格式 / 构建 / 测试
  PROGRESS.md:1127: 
  ...
  PROGRESS.md:1131: - 切换后冒烟 6/6：四条通道 + 两种桥 + 流式；WB 冷启动 1.6 秒
  PROGRESS.md:1132: - 内存（WorkingSet）：改造前 293.4 MB（4 进程）→ 99.3 MB（zgate 18.5 + Qoder 57.2 + wb2api 23.2）；
  PROGRESS.md:1133:   WB 空闲回收后 76.1 MB
  PROGRESS.md:1134: - 端口：7871 = zgate，7863 = wb2api（子进程），8790 = qoder（子进程），7863 只在 WB 请求后出现
  PROGRESS.md:1135: - 登录自启：`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\ZcodeAIModels zgate.lnk`
  PROGRESS.md:1136: - `python tools/check-docs.py`（25 篇）、`python tools/check-secrets.py`（97 文件）通过
  ...
  PROGRESS.md:1139: - **切 7871 会断掉正在走这条路由的会话** —— 本轮切换时把正在跑这份工作的会话也断了
  PROGRESS.md:1140:   （用户当时切了模型才恢复）。以后重启 zgate 前先在 ZCode 里切到直连模型。
  PROGRESS.md:1141: - `gateways/legacy-router/` 保留一个版本作回退；确认稳定后删除。
  PROGRESS.md:1142: - Qoder 仍是 `always`；`ondemand` / 窗口档未启用 —— 需要先实测「窗口拉起能补签」。
  ...
  PROGRESS.md:1144:   `children.workbuddy.policy` 改成 `always`（多占约 23 MB）。
  PROGRESS.md:1145: - `zgate.exe` 不入库，换机器要 `cd gateways/zgate && go build -ldflags "-s -w" -o zgate.exe .`。
  PROGRESS.md:1146: 
  ...
  PROGRESS.md:1159: - [x] **P1 句柄双关闭**：`winproc.Process.Release` 改 `sync.Once`
  PROGRESS.md:1160: - [x] **P1 接管实例监控**：`tick` 对 `external` 子进程每 5 秒健康检查，失败转回自管并自动重启
  PROGRESS.md:1161: - [x] **P1 日志运行时轮转**：`logx` 按累计写入量在 5 MB 处 rename + 重开；`status` 不再打开写句柄
  PROGRESS.md:1162: - [x] **全部按需**：`zgate.json` 两个 child 都改 `ondemand` + `idleSeconds: 300`
  PROGRESS.md:1163: - [x] **签到窗口**：新增 `children.*.windows`（`HH:MM-HH:MM`，支持跨午夜）；
  PROGRESS.md:1164:       WB 四档、Qoder 三档；窗内按 `always`，窗口结束后按空闲回收
  PROGRESS.md:1165: - [x] **热加载**：`POST /admin/reload` + `zgate reload`（策略 / 空闲 / 窗口生效；
  PROGRESS.md:1166:       新增 child、监听地址、上游 base 仍需重启）
  PROGRESS.md:1167: - [x] **退避**：1s→2s→4s→…→60s（与 ARCHITECTURE §3.2 一致）
  ...
  PROGRESS.md:1171: - [x] **冒烟改造**：`smoke_test.py` 从 alias map 按渠道挑最低价模型，不再写死 ID
  PROGRESS.md:1172: - [x] 文档：`MAINTENANCE.md` §8（策略表 / 窗口表 / reload 命令）、`ARCHITECTURE.md` §10.6、
  PROGRESS.md:1173:       `TOOLS.md`、`CHANGELOG.md`、`release-notes/0.3.0.md`
  ...
  PROGRESS.md:1175: ## 验收
  PROGRESS.md:1176: - `go test ./...` 20 个用例全绿（新增窗口解析/跨午夜、ApplyConfig、退避、桥超时、reload）
  PROGRESS.md:1177: - `go vet` / `gofmt -l` 干净；`check-docs`（25 篇）/ `check-secrets`（97 文件）通过
  PROGRESS.md:1178: - 旁路实例（7971）实测：启动时无窗口的子进程保持 `stopped`；窗口内自动 `running`；
  PROGRESS.md:1179:   `POST /admin/reload` 去掉窗口 + `idleSeconds=1` 后一个 tick 内回到 `stopped`
  PROGRESS.md:1180: - 二进制已构建为 `gateways/zgate/zgate-next.exe`（运行中的 `zgate.exe` 被锁，需重启替换）
  PROGRESS.md:1181: 
  PROGRESS.md:1182: ## 待解决 / 注意事项
  PROGRESS.md:1183: - **替换需要重启 zgate**：已安排延迟执行（停 → 覆盖 → 起 → 等 /health）并写
  PROGRESS.md:1184:   `%LOCALAPPDATA%\ZCodeGateway\update-0.3.1.log`；这一步会中断经过 7871 的在途请求（约 2 秒）
  PROGRESS.md:1185: - 重启后两个子进程都应为 `stopped`；第一条 WB / Qoder 消息会有 1–2 秒冷启动
  PROGRESS.md:1186: - 签到窗口能否真正补签，还需要观察一个真实 09:00 / 21:00 窗口（Qoder 启动巡检
  ...
  PROGRESS.md:1192: 
  PROGRESS.md:1193: - 二进制替换与重启已由一次性计划任务完成（20:33:02 停 → 替换 → 20:33:04 健康），
  PROGRESS.md:1194:   日志 `%LOCALAPPDATA%\ZCodeGateway\update-0.3.1.log`；任务已删除。
  PROGRESS.md:1195: - 线上生效：两个 child 都是 `ondemand`，`windows` 已在 `/health` 可见；Qoder 空闲已回收（stopped）。
  PROGRESS.md:1196: - **回退链缺陷已修并上线**：WB 把上游 6004 转成 `400 model_unavailable`，旧逻辑不重试；
  ...
  PROGRESS.md:1223:       `CHANGELOG.md`
  PROGRESS.md:1224: - [x] `gateways/zgate/smoke_test.py` 改为每个渠道取最便宜的前 3 个候选逐个试，
  PROGRESS.md:1225:       冷却中的模型不再让整轮冒烟假红
  ...
  PROGRESS.md:1231:   `W/0.03/DeepSeek-4.1-Fs` 200、`Q/0.09/GLM-5.3-Fs` 200、`O/0.06/MiMo-2.6-Fs` 200；
  PROGRESS.md:1232:   旧名 `O/0.06/MiMo-26-Fs` 也仍 200（legacy 生效）
  PROGRESS.md:1233: - `check-docs` 25 篇通过
  ...
  PROGRESS.md:1237: - 冒烟时 OC 桥接出现过两次 `EOF`（HTTP/2 连接复用导致的上游瞬断，重试即 200）；
  PROGRESS.md:1238:   考虑把 zgate 的 Transport 切回 HTTP/1.1（与旧 Node 路由一致）或对 EOF 做一次重试，
  PROGRESS.md:1239:   需要再重启一次 zgate，留待下次空档
  PROGRESS.md:1240: - Qoder `DeepSeek-Flash` 仍偶发 `10605` 限流（既有问题）
  ...
  PROGRESS.md:1323: - [x] `MAINTENANCE.md` §6 的每日自动化补第 ⑤ 步；`TOOLS.md` 增加工具条目
  PROGRESS.md:1324: - [x] 线上应用：28 个模型（主力 6 / 免费 5 / 低耗 8 / 高耗 9），无需重启 zgate
  PROGRESS.md:1325: 
  ...
  PROGRESS.md:1340: 
  PROGRESS.md:1341: # 2026-10-26 第 N+18 轮：zgate 登录自启零窗口（GUI 子系统）+ 修管道吞输出
  PROGRESS.md:1342: 
  PROGRESS.md:1343: ## 任务目标
  PROGRESS.md:1344: 用户反馈：开机弹 cmd 窗口、中文乱码；并问 zgate 为何不跟随 ZCode 启动。
  PROGRESS.md:1345: 结论：设计本就要求 GUI 子系统无窗构建，但已发布的二进制是裸 `go build` 的
  PROGRESS.md:1346: 控制台程序；乱码是 UTF-8 日志 tee 进 GBK 控制台；跟随 ZCode 的方案 0.3.0
  PROGRESS.md:1347: 已按 [ARCHITECTURE.md](docs/ARCHITECTURE.md) §10.2 有意放弃（19 MB 常驻换
  PROGRESS.md:1348: 签到窗口与 ZCode 解耦），维持登录自启。用户确认后按 GUI 子系统重编译落地。
  PROGRESS.md:1349: 
  PROGRESS.md:1350: ## 已完成变更
  PROGRESS.md:1351: - [x] `gateways/zgate/internal/winproc/console_windows.go`：`AttachParentConsole`
  PROGRESS.md:1352:       改为先判 `GetStdHandle`+`GetFileType` —— 管道/文件句柄保留原样（旧逻辑
  ...
  PROGRESS.md:1354:       仅句柄无效或本就是控制台时才 attach 父控制台
  PROGRESS.md:1355: - [x] 重编译 `zgate.exe`：`go build -C gateways/zgate -ldflags "-H windowsgui"
  PROGRESS.md:1356:       -o zgate.exe .`（`file` 验证为 GUI 子系统；exe 不入库）
  PROGRESS.md:1357: - [x] `zgate.json`、启动文件夹快捷方式零改动（GUI 下 WindowStyle 自然失效）
  PROGRESS.md:1358: - [x] 文档：`MAINTENANCE.md` §8.1 加「重新构建 zgate」命令行 + 无窗行为与
  PROGRESS.md:1359:       忘带 flag 的后果说明（构建命令正本）；`CHANGELOG.md` 0.3.0 追加
  PROGRESS.md:1360:       「登录自启零窗口落地」小节；`docs/release-notes/0.3.0.md` 补一行
  PROGRESS.md:1361: - [x] 顺带修复：`CHANGELOG.md` 0.3.0 段落四个小节整块重复的历史残留（并发写坏），
  ...
  PROGRESS.md:1365: - `go vet` / `gofmt -l` / `go test ./...`（bridge/alias/router/supervisor）全绿
  PROGRESS.md:1366: - `zgate.exe version`/`status`：Git Bash 管道、cmd `> 文件` 重定向均正常输出
  PROGRESS.md:1367: - 分离启动后 `MainWindowHandle=0`（无任何窗口）、`/health` 200（28 个 alias 模型、
  PROGRESS.md:1368:   三上游 key 齐、两子进程按需未起 —— 不在签到窗口内，符合预期）
  PROGRESS.md:1369: - 日志文件 `%LOCALAPPDATA%\ZCodeGateway\zgate.log` UTF-8 正常，无控制台 tee
  PROGRESS.md:1370: - `python tools/check-docs.py`（27 篇）、`python tools/check-secrets.py`（125 文件）通过
  ...
  PROGRESS.md:1374:   控制台窗口即杀网关，正是本轮要消除的故障路径；07:54 起新实例已无窗运行
  PROGRESS.md:1375: - `gateways/zgate/zgate-next.exe` 是 0.3.0 开发期被文件锁时的暂存产物（仍为
  PROGRESS.md:1376:   控制台程序、未被任何脚本引用），可手动删除
  PROGRESS.md:1377: - 0.3.0 尚未打 tag，本轮并入 0.3.0 段落；`zgate` 二进制内版本串仍是 0.3.0
  PROGRESS.md:1378: 
  ...
  PROGRESS.md:1389: ## 已完成变更
  PROGRESS.md:1390: - [x] **Step 3 Qoder 已完成并落盘**：8790 子代理被 zgate 按策略停掉（08:17 不在
  PROGRESS.md:1391:       签到窗口），先 `start-qoder-proxy.bat` 起 `qoder_proxy.py`（本地、可逆，
  ...
  PROGRESS.md:1448: - [x] `model_alias.py`：`classify()` 对无 alias 记录的裸 OC id 读协议提示缓存
  PROGRESS.md:1449:   （`protocol_hints()`），把 messages/responses 正确写进 alias map 供 zgate 桥接。
  PROGRESS.md:1450:   保留其 fold-and-wipe 原行为（REMOVE_PROVIDERS 未用，实际靠覆盖 4 组删除）。
  ...
  PROGRESS.md:1481: 
  PROGRESS.md:1482: # 2026-10-27 第 N+19 轮：zgate 无窗产物回退的根因定位 + 构建入口收口
  PROGRESS.md:1483: 
  PROGRESS.md:1484: ## 任务目标
  PROGRESS.md:1485: 用户给了一份结论：现在跑的 `zgate.exe` 不是无窗版，被重新编译成控制台程序，
  PROGRESS.md:1486: 根因是 10-26 10:50 的 `d508570` 那轮跑了裸 `go build` 覆盖了产物；
  PROGRESS.md:1487: 并建议「在 `gateways/zgate/` 里用 `go vet ./...` 而不是裸 `go build ./...`」，
  PROGRESS.md:1488: 必要时加一个构建后校验 Subsystem 的脚本防止再犯。
  PROGRESS.md:1489: 本轮任务：**核实这份结论的真伪**，把服务恢复，并落地防再犯。
  PROGRESS.md:1490: 
  ...
  PROGRESS.md:1496:         两者结论相同（产物被覆盖成控制台版），但归因要精确到单包命令。
  PROGRESS.md:1497:   - 「`-H windowsgui` 是正本命令」正确；但**光靠文档约束不够**，10-26 就是文档
  PROGRESS.md:1498:         写对了、手滑一次就回退。
  PROGRESS.md:1499: - [x] **现状核实（本轮开工时的真实状态，与用户结论不同）**
  PROGRESS.md:1500:   - `gateways/zgate/zgate.exe` 的 PE `Subsystem` **已是 2（WINDOWS_GUI）**，
  PROGRESS.md:1501:         文件时间 10-27 11:10:29 —— 已被用正确 flag 重编过，**弹窗问题已消失**。
  PROGRESS.md:1502:   - 但 **zgate 进程根本不在跑**：7871 / 7863 / 8790 三个端口全部无人监听；
  PROGRESS.md:1503:         `zgate.exe status` 自报「未运行（健康检查不可达，HTTP 0）」。
  PROGRESS.md:1504:   - 日志 `zgate.log` 给出完整故事：`11:08:50 收到 terminated`（旧的控制台版被停）
  PROGRESS.md:1505:         → `11:10:30 已启动`（GUI 版起来过）→ 此后再无日志、**连「已退出」都没有**
  PROGRESS.md:1506:         → 进程被强杀。ZCode app-server 新进程 PID 5960 建于 `11:10:51`，
  PROGRESS.md:1507:         与 zgate 死亡时间吻合 —— **上个 agent 会话结束时，Windows Job Object
  PROGRESS.md:1508:         把进程树一起回收了**。这是「11:10 起过一次、现在又没了」的真正原因。
  PROGRESS.md:1509:   - 快捷方式 `ZcodeAIModels zgate.lnk` 仍指向同一个 exe（未被改动），
  PROGRESS.md:1510:         下次登录会跑 GUI 版 → 零窗口。
  PROGRESS.md:1511:   - exe 在 `.gitignore`（`/gateways/zgate/*.exe`）里，**git 救不回来**，只能带 flag 重编。
  PROGRESS.md:1512: - [x] **恢复服务**：经 `explorer.exe` 拉起启动文件夹快捷方式
  PROGRESS.md:1513:       （与登录自启同一条路径，父进程是 explorer.exe，能存活）；
  PROGRESS.md:1514:       实测 `nohup` / `setsid` / `Start-Process` 三种方式起的进程都会随
  PROGRESS.md:1515:       agent 沙箱回收而消失，**只有 explorer 这条路活下来**。
  PROGRESS.md:1516: - [x] **新增 `gateways/zgate/build.py`**（构建入口收口 + 强制校验 PE 子系统）
  PROGRESS.md:1517:   - `--check`：只校验现有产物的 PE `Subsystem`（读 PE 头，不编译）
  PROGRESS.md:1518:   - `--cross-check`：交叉编译一份 windows/amd64 到临时目录再校验 ——
  PROGRESS.md:1519:         `-H windowsgui` 是 windows 链接器 flag，**交叉编译时同样生效**，
  PROGRESS.md:1520:         所以这条校验在 **Linux CI 上也能真跑起来**
  PROGRESS.md:1521:   - 默认：带 `-H windowsgui` 编译并校验，不合格非零退出
  PROGRESS.md:1522: - [x] **CI 加一步**（`.github/workflows/ci.yml`）：
  PROGRESS.md:1523:       `python3 gateways/zgate/build.py --cross-check` —— flag 丢了会在 CI 就红，
  PROGRESS.md:1524:         不用等下次开机才发现弹窗
  ...
  PROGRESS.md:1530:         含「exe 被占用改不动怎么办」「怎么确认没有别的控制台窗口」
  PROGRESS.md:1531:   - `docs/MAINTENANCE.md` §8.1：构建命令正本改为 `python gateways/zgate/build.py`，
  PROGRESS.md:1532:         并写明**别在 `gateways/zgate/` 里裸跑 `go build .`**，检查用 `go vet ./...`
  PROGRESS.md:1533: 
  PROGRESS.md:1534: ## 验收
  PROGRESS.md:1535: - `python gateways/zgate/build.py --check` → `Subsystem = 2 → WINDOWS_GUI（无窗）`（exit 0）
  PROGRESS.md:1536: - `python gateways/zgate/build.py --cross-check` → 交叉编译产物同样 `Subsystem = 2`（exit 0）
  PROGRESS.md:1537: - `go build .`（临时目录副本）→ 产出 `Subsystem = 3`，确认单包命令确实是回退真凶
  PROGRESS.md:1538: - `go build ./...`（临时目录副本）→ 无 `.exe` 落盘，确认多包模式不覆盖
  PROGRESS.md:1539: - 服务恢复：`curl 127.0.0.1:7871/health` → `ok:true`、`alias.models=31`、
  PROGRESS.md:1540:       `uptime_s` 持续增长；进程 PID 21496 父级 `explorer.exe`
  ...
  PROGRESS.md:1543: - 无控制台窗口：`Get-Process conhost | Where-Object { $_.MainWindowTitle }` → 无输出
  PROGRESS.md:1544: - `gofmt -l gateways/zgate` → 空；`go vet ./...` → exit 0
  PROGRESS.md:1545: - `python tools/check-docs.py` → 31 篇全过；`python tools/check-secrets.py` → 无泄露
  ...
  PROGRESS.md:1550:   CI 与本机 Go 版本不一致这件事本轮没动。
  PROGRESS.md:1551: - ⚠️ 本轮新增文件 `gateways/zgate/build.py` 与三处文档改动**未提交**
  PROGRESS.md:1552:   （按仓库约定不擅自 commit）；`evidence/go-model-sync-20261026-120234.md`
  PROGRESS.md:1553:   是上一轮遗留的未跟踪文件，同样未动。
  PROGRESS.md:1554: - ⚠️ zgate 由 agent 会话启动仍会被回收。要长期驻留，**靠登录自启快捷方式**
  PROGRESS.md:1555:   （explorer 拉起，父进程 explorer.exe），不要靠 agent 起的进程。
  PROGRESS.md:1556: - 备注：仓库里还留着一个 `gateways/zgate/zgate-next.exe`（10-23 的产物），
  PROGRESS.md:1557:   与 `zgate.exe` 无关，本轮没动。
  PROGRESS.md:1558: 
  ...
  PROGRESS.md:1563: ## 任务目标
  PROGRESS.md:1564: 确认 WorkBuddy2API Panel 停更后有无接手项目，并把 `gateways/upstream/workbuddy` 切到可持续维护的基线上。
  PROGRESS.md:1565: 
  ...
  PROGRESS.md:1574:       `insecureKeyWarning`（覆盖空 key 与 `test_key`），故旧补丁的 `CHANGE_ME` 改动不再需要。
  PROGRESS.md:1575: - [x] 构建 `wb2api.exe`（`go.mod` 要求 Go ≥ 1.26.10，`GOTOOLCHAIN=auto` 自动拉取工具链），
  PROGRESS.md:1576:       替换线上二进制，由 zgate 按需重启子进程。
  PROGRESS.md:1577: - [x] 文档对齐：`README.md` 鸣谢表、`docs/MAINTENANCE.md` §8.4（更新命令 / 新机器重建 / 血缘与回滚）。
  ...
  PROGRESS.md:1590: - ⚠️ `misakano7545` 是个人分叉（作者自述「更新随缘」），非官方延续；回滚用
  PROGRESS.md:1591:   `git checkout panel-final-73a7560` 或 `.workbuddy/backup/wb2api-panel-final.exe`。
  PROGRESS.md:1592: - ⚠️ 上游自 2026-10-23 起收紧非官方客户端识别，该风险所有分支共享，换仓库解决不了。
  ...
  PROGRESS.md:1631:   `provider_config.json`，两个写入者互读对方产物。本轮实测到配置里混进了
  PROGRESS.md:1632:   `cn:*` 原始 id（与显示名并存），加重启才归一。正解是收口成单一写入者，
  PROGRESS.md:1633:   或让采集脚本只写 cache。
  ...
  PROGRESS.md:1680:       的四组口径改为三组。
  PROGRESS.md:1681: - [x] **运维事故并修复**：改二进制时 `taskkill` 掉 zgate 后没拉起，导致 ZCode
  PROGRESS.md:1682:       全部模型不可用（用户临时拉 opencode 顶上）。根因：zgate 无默认子命令，
  PROGRESS.md:1683:       裸启动 `os.Args[2:]` 越界 panic。已用 `Start-Process ... 'serve'` 恢复，
  ...
  PROGRESS.md:1687: 
  PROGRESS.md:1688: - `go build ./...` + `go test ./...`（gateways/zgate）全绿；新增 3 条流式用例。
  PROGRESS.md:1689: - `python -m unittest discover -s tests -v` → 10 passed。
  ...
  PROGRESS.md:1691: - `python tools/check-docs.py` → 40 篇全部通过。
  PROGRESS.md:1692: - zgate 重启后：`/health` `"ok":true`、`alias.models=19`、7871 LISTENING。
  PROGRESS.md:1693: - **实测首字（经 7871，流式）**：`claude-haiku-5-5` 0.95–1.05s、
  ...
  PROGRESS.md:1707:   两块（无正文）。三者都属上游行为，已记录，未改配置。
  PROGRESS.md:1708: - ⚠️ **zgate 是单点**：重启窗口内全站不可用。以后改二进制应「先构建到临时文件 →
  PROGRESS.md:1709:   确认成功 → 再停机切换」，或至少停机后立刻拉起并验 `/health`。
  ...
  PROGRESS.md:1746: - [x] 新增 `TestForwardStreamIdleTimeout`（静默上游 → 空闲上限内 504 且零 chunk）。
  PROGRESS.md:1747: - [x] 二进制用「先构建 `zgate-next.exe` → 停机 → 替换 → `Start-Process ... serve`」
  PROGRESS.md:1748:       的安全顺序切换，没有再出现上一轮「停完忘了拉起」的中断。
  ...
  PROGRESS.md:1751: 
  PROGRESS.md:1752: - `go build ./...` + `go test ./...`（gateways/zgate）全绿，含新增空闲超时用例。
  PROGRESS.md:1753: - 重启后 `/health` `"ok":true`、`alias.models=19`、7871 LISTENING。
  PROGRESS.md:1754: - 实测 `DeepSeek-4.1-Flash` 0.85s；`Conatus` 本次 6.06s 正常返回（僵死是间歇的，
  ...
  PROGRESS.md:1776: 客户端契约对齐（反检测加固）、新增思考档位策略、删除夜猫子排程、/v1/models 只列官方菜单。
  PROGRESS.md:1777: 把本地克隆 `misakano-base` 升级到发布标签 `v2026.10.30.1049` 并重建 `wb2api.exe`，验证可用。
  PROGRESS.md:1778: 
  PROGRESS.md:1779: ## 已完成变更
  PROGRESS.md:1780: - [x] 停旧网关（pid 3432）、备份旧 exe `wb2api.exe.bak-20261030-192325`。
  PROGRESS.md:1781: - [x] `git stash` 本地改动（main.go key 不打印修复 + run/stop 脚本 + .gitignore 密钥）→ `git checkout v2026.10.30.1049`（纯快进，HEAD 是该 tag 祖先，无冲突）→ `git stash pop` 干净恢复本地 key 修复。
  PROGRESS.md:1782: - [x] 清理 `config.json`：删已失效的 `blackcat_hours`/`blackcat_enabled` 两行；补 `thinking` 默认节（`client_priority:true` 尊重 ZCode 档位）、`cn` 段、`watchdog`（关）。JSON 校验通过。
  PROGRESS.md:1783: - [x] `cd cmd/server && go build -o ../../wb2api.exe .`（Go 1.26.10，go.mod 要求 1.26.10 匹配）→ 新 exe 16.4 MB，PE32+。
  PROGRESS.md:1784: - [x] 启动新网关（pid 25608），`/panel/` 返回 200。
  ...
  PROGRESS.md:1791: - 新 exe 进程存在、`/panel/` 200、`/panel/api/models` 返回 52 条（全 cn）。
  PROGRESS.md:1792: - cn 域实测聊天成功，思考档位按 ZCode 发送体执行（client_priority 默认生效）。
  PROGRESS.md:1793: - fetch/probe 脚本无 `TypeError`、正常输出倍率变化与新增。
  ...
  PROGRESS.md:1797: - **global 账号缺失**：若需恢复 global 模型（gpt/grok/kimi-k3 等），须先把 global 账号加回 `auths/` 与 `data/state.json`。现状下 sync --apply 会把 ZCode 的 WB 模型缩减为 20 个 cn 模型（符合"跑不通即清"策略，但属用户可见缩减，故未自动 --apply，等用户拍板）。
  PROGRESS.md:1798: - 若确认只保留 cn：在 WB 网关跑 `workbuddy_zcode_sync.py --apply` 即可；统一路由 `127.0.0.1:7871` 当前已服务 28 模型，sync 写入后 ~1s 热加载生效。
  PROGRESS.md:1799: - 旧 `server.log`（10-15）已陈旧；新进程日志去向待定（run.bat 直跑 stdout 未落盘），不影响运行。
  ...
  PROGRESS.md:1816: ### 关键发现：网关实时目录从 52 缩到 19（账号权限，非构建回归）
  PROGRESS.md:1817: - 升级后首次 `fetch_pricing.py` 拿到 52 条，是旧进程 `data/state.json` 缓存的目录在重启后被新进程短暂回放；约 15 分钟后网关按**当前单个 cn 账号**实探，目录收敛为 **19 条**（`/panel/api/models` 实测 19，`fetch_pricing.py` 二次跑报「52→19，减少 64%，疑似临时残缺」并**拒绝写入**）。
  PROGRESS.md:1818: - 实测账号 `Empty.(72abae7f)` 健康（credits 1782，ZCode 正用 `cn:hy3` 在跑）；`cn:deepseek-v4-flash`/`cn:minimax-m2.7`/`cn:wb-lite` 均 200，`cn:glm-4.6` 400 `model_unavailable`（该账号当前不可用）。
  ...
  PROGRESS.md:1860: 
  PROGRESS.md:1861: # 2026-11-01 增量代码审查：10-26 后的 zgate 网络三连提交 + 同期工具/供应商改动
  PROGRESS.md:1862: 
  ...
  PROGRESS.md:1881:       断言未跟上 502fc16 的链尾机场孪生跳，10-30 起本地必挂。更新断言
  PROGRESS.md:1882: - [x] `python gateways/zgate/build.py` 重建产物并过 PE 子系统校验（GUI, Subsystem=2）
  PROGRESS.md:1883: 
  ...
  PROGRESS.md:1906: 
  PROGRESS.md:1907: # 2026-11-01 zgate 安全微优化：hopKey 脱敏、chat 504 冷却对齐、idleReader 竞态
  PROGRESS.md:1908: 
  ...
  PROGRESS.md:1923: - [x] `go vet ./...` + `go test ./... -count=1` 全绿；`tests/` Python 另跑（10/10）
  PROGRESS.md:1924: - [x] `python gateways/zgate/build.py` 重建 + PE 校验（不重启生产网关）
  PROGRESS.md:1925: - [x] `python tools/check-docs.py` + `check-secrets.py`；CHANGELOG [未发布] 补段
  ...
  PROGRESS.md:1934:   `check-secrets.py` 133 文件无敏感
  PROGRESS.md:1935: - `build.py` 重建 OK（Subsystem=2 GUI）；生产进程未动 —— **运行中的 zgate 仍是旧
  PROGRESS.md:1936:   镜像，待人工重启后生效**
  PROGRESS.md:1937: - race 检测器本机不可用（`-race` 需 cgo + gcc，本机无 gcc）：idleReader 改动以
  ...
  PROGRESS.md:1961: ## 已完成变更
  PROGRESS.md:1962: - [x] WorkBuddy2API 上游更新：clone 从 `v2026.10.30.1049` 跟到 `misakano/main`（+52 提交），保留本地三处补丁，`goproxy.cn` 构建，临时端口验证后原子替换 `wb2api.exe`（备份 `wb2api.exe.bak-20261102-130504`）。
  PROGRESS.md:1963: - [x] `go_model_sync.py` 体检改走机场（`HTTPS_PROXY=http://10.0.0.1:7896`）：Beam / GPT-6-Luna / Muse-Spark 的地区受限 403 不再误判为「上游不可用」。
  ...
  PROGRESS.md:1965: - [x] `tools/model_alias.py`：新增 `pick_auto_low()` —— 新厂商或新一代且 ≤0.11 自动进省钱组（每厂商最多 1 条）；Qoder 倍率落快照 `providers/qoder/cache/qd_prices.json`，8790 停着时不再丢定价。
  PROGRESS.md:1966: - [x] `gateways/zgate`：客户端取消后提前返回，不再打印「300ms 后重试同一跳」的假重试日志；新增 `TestClientCancelDoesNotRetry`。
  PROGRESS.md:1967: - [x] zgate 二进制换新：`%LOCALAPPDATA%\ZCodeGateway\swap-zgate.ps1`（预检→备份→停→换→起→轮询 health→失败回滚），另留 `start-zgate.bat` 手动拉起。
  PROGRESS.md:1968: 
  ...
  PROGRESS.md:1976: - 网关目录只剩 20 条是**账号侧 CLI 菜单收窄**（新版本同样如此），已用探活机制兜住，不再阻塞价格表更新。
  PROGRESS.md:1977: - zgate 换二进制会断 2-3 秒所有聊天流量，必须在「不需要模型回复」的工具调用里做。
  PROGRESS.md:1978: - `evidence/go-model-sync-*.md` 三个运行产物未入库。
  ...
  PROGRESS.md:1996:       `efforts`/`supported_efforts` 自动写 `optionSpecs.reasoningLevel.values`；
  PROGRESS.md:1997:       只对 low/high 两档模型生效（五档模型会把默认档从 high 抬到 max，属改费用，未动）；
  PROGRESS.md:1998:       probe fallback 的 map 改写改成 merge，不再覆盖 values。
  ...
  PROGRESS.md:2031: - `ListModels`（引擎自己的判定）确认：`DeepSeek-4.1-Flash` → `levels: disabled,low,high,max
  PROGRESS.md:2032:   (default max)`、`HY3`/`HY3-X` → `low,high (default high)`；配置**热加载**，无需重启。
  PROGRESS.md:2033: - 第三轮后 `ListModels`：8/18 有真档位（DeepSeek-4.1-Flash、Qwen-3.8-Max、GLM-5.3-Flash、
  ...
  PROGRESS.md:2062: ## 任务目标
  PROGRESS.md:2063: 把 DeepSeekRuntime（DSH）纳入模型更新链路：ZCode 最终三组每次由 `model_alias.py --apply` 写入后，自动同步到 DSH 的 `llm-pi-ai` 路由，避免手工重复导入。
  PROGRESS.md:2064: 
  PROGRESS.md:2065: ## 已完成变更
  PROGRESS.md:2066: - [x] 新增 `tools/dsh_sync.py`：读 ZCode 最终 `provider_config.json`，用 `zcode_effective_body.js` 取有效元数据，重写 `~/.dsh/profiles/desktop/cordis.patch.yml` 的 `llm-pi-ai` 段；保留其他 patch 条目与非 `zcode-*` provider。
  PROGRESS.md:2067: - [x] 思考档位按 ZCode 有效 `reasoningLevel.map` 投影：`map="{}"` 的模型不写 `reasoningEfforts`；`disabled` 档写 `off: disabled` 并配 `thinkingFormat: deepseek`。
  PROGRESS.md:2068: - [x] DSH 凭据只维护 `~/.dsh/.credentials.yaml` 的 `ZCODE_GATEWAY_KEY` 引用；patch 不写明文；写前备份 `*.bak-dshsync-<时间戳>`，`--check` 可做漂移检测。
  PROGRESS.md:2069: - [x] `tools/model_alias.py --apply` 在默认 ZCode 配置路径下自动调用 `dsh_sync.py --apply`；`--config` 沙盒不投影；DSH 未安装跳过，失败只告警不阻断；新增 `--no-dsh` 关闭。
  PROGRESS.md:2070: - [x] 更新每天 12:00 自动化 prompt（`automation-3e2f8a53-b408-4bf8-90ff-4a331a721f5c`）：说明自动投影、WARN 处理与最终回复口径。
  ...
  PROGRESS.md:2073: ## 验收
  PROGRESS.md:2074: - `python -I tools/dsh_sync.py`：3 个 provider / 18 个模型，模型表与凭据引用均「无变化」。
  PROGRESS.md:2075: - `python -I tools/dsh_sync.py --check`：退出码 0。
  PROGRESS.md:2076: - `python -I tools/model_alias.py --check`：退出码 1，仍报 1 处既有漂移（DeepSeek-4.1-Flash 的 OC 跳 0.11→0.22），与本轮 DSH 改动无关；下一轮定时 `--apply` 会收口。
  PROGRESS.md:2077: - 临时 DSH 副本测试：新增模型能写入、移除模型能删除、非 `zcode-*` provider 保留、凭据变更能更新、二次 `--check` 为 0、备份文件不互相覆盖。
  PROGRESS.md:2078: - `python -I -m py_compile tools/dsh_sync.py tools/model_alias.py` 通过；`model_alias.sync_deepseek_harness()` 对真实配置调用输出「DeepSeekHarness 同步：无变化」。
  PROGRESS.md:2079: - DSH 模型选择器已显示 `主力 / 免费 / 省钱` 三组 18 个模型；此前实测 HY3 与 DeepSeek-4.1-Flash（思考开/关）经 7871 均 HTTP 200。
  PROGRESS.md:2080: 
  PROGRESS.md:2081: ## 待解决 / 注意事项
  PROGRESS.md:2082: - `tools/dsh_sync.py` 新增 PyYAML 依赖（仅该脚本）；`docs/TOOLS.md` 已标明。
  PROGRESS.md:2083: - 自动投影只针对本机 `DSH_HOME` 下的 `desktop` profile；换 profile 用 `DSH_PROFILE`，换 DSH 安装用 `DSH_HOME`。
  PROGRESS.md:2084: - 若 DSH 未运行，写入仍有效，下次启动生效；若 DSH patch 被 DSH UI 同时改写，`--check` 会报漂移，重跑 `--apply` 即可。
  PROGRESS.md:2085: 
  ...
  PROGRESS.md:2097: - [x] 保留本地两处补丁：`.gitignore` 本地 secrets/log 忽略；`cmd/server/main.go` 首次生成配置时不打印 api_key。
  PROGRESS.md:2098: - [x] `go test ./...` 全部通过；`go build -trimpath -o wb2api.exe.new ./cmd/server` 成功。
  PROGRESS.md:2099: - [x] 旧二进制备份为 `wb2api.exe.bak-20261104-144556`；停旧进程后用重试替换为 18,821,632 字节新二进制，zgate 已按需拉起新进程。
  PROGRESS.md:2100: - [x] `workbuddy_fetch_pricing.py` 刷新价格表：面板 20 条，新增 `cn:hy4free`（0 分）与 `cn:hy4std`（0.29）；旧表 17 个可调型号经逐条探活保留，价格表 39 行。
  ...
  PROGRESS.md:2104: - [x] `providers/workbuddy/workbuddy_fetch_pricing.py` 最终 `✓` 改为 ASCII `[OK]`，修掉 GBK 控制台写盘后 `UnicodeEncodeError`（fetch 现在退出 0）。
  PROGRESS.md:2105: - [x] DSH 自动投影：`model_alias --apply` 调用 `dsh_sync.py`，DeepSeekHarness 同步为 3 个 provider / 19 个模型。
  PROGRESS.md:2106: 
  ...
  PROGRESS.md:2110: - ZCode 三组：主力 2（DeepSeek-4.1-Flash、Qwen-3.8-Max）/ 免费 7（含 HY4-Free）/ 省钱 10；`model_alias --check` 退出 0。
  PROGRESS.md:2111: - `dsh_sync.py --check` 退出 0；DSH 选择器/配置为同一 19 个模型。
  PROGRESS.md:2112: - `workbuddy_fetch_pricing.py` 复跑退出 0，价格表 39 行。
  ...
  PROGRESS.md:2123: 
  PROGRESS.md:2124: # 2026-11-06 第十一轮：zgate 地区受限 403 冷却（Beam 403/200 抖动）
  PROGRESS.md:2125: 
  ...
  PROGRESS.md:2131: - 直连出口实测永远 `403 {"type":"error","error":{"type":"RegionError","message":"This model is not available in your country"}}`，机场出口 200（复测两次一致）。
  PROGRESS.md:2132: - `zgate.log` 尾部 4000 行：hop1=367、hop2=367、`403 fallback`=359 —— 几乎每个 beam 请求都先白撞一次直连 403。
  PROGRESS.md:2133: - 缺陷在 router：`regionBlocked()` 只让 `chainAccept` 返回 false（回落），从不冷却该跳；同一跳于是每次都重新尝试。11 个 OC 型号里 beam-free 是唯一「直连 403 / 机场 200」可修的；gpt-6-luna、muse-spark-1.3-contributor 机场同样 400（并非机场节点漂移，是上游整体不收），其余 8 个直连机场都 200。
  ...
  PROGRESS.md:2135: ## 已完成变更
  PROGRESS.md:2136: - [x] `gateways/zgate/internal/router/router.go`：新增 `regionCooldown = 30 * time.Minute`；chat 路径 `accept` 闭包与桥接路径都改为「地区受限 403 且链里存在同 channel+同 upstream 的带出口孪生跳（`proxyTwinAfter`）→ 冷却这一跳 30min」，日志写明「同上游机场孪生跳继续可用」。冷却键 `hopKey` 带 proxy，所以孪生跳是另一个键，不会被一起吃。
  PROGRESS.md:2137: - [x] 只在有孪生跳时冷却：单跳链或无同上游出口跳时不冷却，避免把真实 403 变成即时 `502 all upstreams failed`。
  ...
  PROGRESS.md:2139: - [x] `main.go`：无参数启动（双击 exe）时 `os.Args[2:]` 越界 panic，改成先判长度再 `flag.Parse`，现在正常打 usage/报缺配置。
  PROGRESS.md:2140: - [x] 候选二进制 `%LOCALAPPDATA%\ZCodeGateway\zgate-0.3.0-cand.exe`（md5 `b3903b20ce6296d0e7fa18196eed639c`，10,465,792 B）；现网 `gateways/zgate/zgate.exe` 仍是 11-02 13:16 的构建（md5 `5e0bac151a5cbd50a0aa3050b2a809ad`），**等用户执行 `swap-zgate.ps1` 受控重启**（脚本自带备份/健康轮询/失败回滚）。
  PROGRESS.md:2141: 
  ...
  PROGRESS.md:2144: - `go test ./internal/router/ -run Region -v`：`TestRegionBlocked403CoolsTheDirectHopOnly` PASS、`TestRegionBlockedDoesNotCoolALoneHop` PASS。
  PROGRESS.md:2145: - 候选二进制烟测：`version` → `zgate 0.3.0`；无参数 → 报缺配置后退出，不再 panic。
  PROGRESS.md:2146: 
  PROGRESS.md:2147: ## 待解决 / 注意事项
  PROGRESS.md:2148: - 重启后每 30 分钟窗口仍会有 1 次直连 403（首个请求学到之后走机场），面板上不再成片；想要零 403 得让 alias 生成器把孪生跳排前，但只有 beam-free 被证实机场可用，静态清单会误伤 gpt-6-luna/muse-spark，故不做。
  PROGRESS.md:2149: - 未改 `tools/model_alias.py` 链序；未重启网关（AGENTS：长驻网关由用户重启）；本轮未提交/推送。
  PROGRESS.md:2150: 
  PROGRESS.md:2151: # 2026-11-06 第十二轮：zgate 桥接流式（TTFB / TPS）
  PROGRESS.md:2152: 
  ...
  PROGRESS.md:2167: - [x] 新增 `internal/router/stream_test.go`：`TestBridgeStreamsOnNonTailHop`、`TestBridgeRegionBlockedFallsBackWithStream`。
  PROGRESS.md:2168: - [x] 候选二进制 `%LOCALAPPDATA%\ZCodeGateway\zgate-0.3.0-cand.exe` md5 `c96615631f3a52baf5adaa1a17375064`；等用户跑 `swap-zgate.ps1`。
  PROGRESS.md:2169: 
  ...
  PROGRESS.md:2187:   并补上非流式空闲上限的坑。
  PROGRESS.md:2188: - 现网核对：`gateways/zgate/zgate.exe` md5 `c9661563…`、进程 21:10:28 起、/health 200 —— 用户已跑过
  PROGRESS.md:2189:   `swap-zgate.ps1`，流式修复已在线上。同题实测 Claude-Haiku-5.5 `ttfb 2.227s / total 3.676s`、46 条 data。
  PROGRESS.md:2190: - 新候选（含护栏）md5 `f66ef8f97f992caad1eb248ae928cdde`；护栏不可达，与现网行为等价，不为此重启。
  PROGRESS.md:2191: 
  ...
  PROGRESS.md:2194: - 目录 F:\Project\ZcodeAIModels → F:\Project\ModelBus；junction、_merged AGENTS.md、启动项快捷方式同步。
  PROGRESS.md:2195: - 搬目录前必须停看门狗并 kill zgate / wb2api / qoder_proxy，否则 exe 被映射 + CWD 在目录内导致 ERROR_ACCESS_DENIED；Move-Item 半搬后用 robocopy /MOVE /E /R:1 /W:1 补齐。
  PROGRESS.md:2196: - 网关起不来根因（实测）：robocopy 带过来 **Low Mandatory Level**，项目树里的 exe 以 Low IL 启动，写 C:\Users\<user>\AppData\Local\ZCodeGateway 一律 Access is denied；用 Go 探针测到 .work 下 RID=0x2000、gateways\zgate 下 RID=0x1000 证实。修复：icacls "F:\Project\ModelBus" /setintegritylevel "(OI)(CI)medium" /T /C /Q。
  PROGRESS.md:2197: - 计划任务：ModelBus 模型同步、ModelBus-zgate-watchdog 已建（Disabled）；旧 ZcodeAIModels-zgate 已由管理员删除，ModelBus-zgate 已建（ONLOGON、Interactive only、Run As SansK，已关掉电池限制与 72h 时长上限）；配置按可执行文件同目录解析，所以 Start In 为空不影响；与启动项快捷方式并存时，后起者卡 net.Listen 失败即退出、不会起重复子进程。
  PROGRESS.md:2198: - 仓库：17 个文件把 ZcodeAIModels 换成 ModelBus（历史文档 CHANGELOG/PROGRESS/evidence/release-notes 保留原名）；go vet / go build 通过；tools/check-docs.py exit 0。
  ...
  PROGRESS.md:2218: | 5 | `tools/model_alias.py` | `--scores` / `--no-scores`、`pick_scores_dropped`（只降不升）、`VENDOR_QUOTA = 2` + `pick_quota_dropped` |
  PROGRESS.md:2219: | 6 | `gateways/zgate/internal/router/router.go` | `quotaCooldown = 24h` + `quotaExhausted`：额度烧光类 4xx 按一天冷却，不再每 30 分钟重撞 |
  PROGRESS.md:2220: 
  ...
  PROGRESS.md:2235: 
  PROGRESS.md:2236: - 口径全文写进 `docs/BENCHMARKS.md` §9（三段链路 / 三档分数 / 门槛与只降不升 / 配额 / 首次生效变化 / 回退）。
  PROGRESS.md:2237: - 「体能分」与 AA 两套量纲不混算：竞技榜基准是 1094 分 + 0.11 积分，不是 342.40 + 1.20。
  ...
  PROGRESS.md:2278: 
  PROGRESS.md:2279: # 2026-11-06 第十五轮：选型三处硬伤修复（HY4 归位 / 探活生效 / 渠道排序表）
  PROGRESS.md:2280: 
  ...
  PROGRESS.md:2331: 
  PROGRESS.md:2332: - Qoder 本机反代 8790 的 /v1/models（Bearer key 取自 gateways/upstream/qoder/accounts/settings.json）：
  PROGRESS.md:2333:   Qwen3.8-Flash price 0.0 / peak 0.1 / valley 0.0 / is_free true；同表 Qwen3.8-Max 0.2（free true）、
  ...
  PROGRESS.md:2335:   Kimi-K2.8-Preview 0.8、Kimi-K3.1-Pro 1.0、DeepSeek-V4-Pro 0.5、Auto 0.5、Fast 0.8。
  PROGRESS.md:2336: - gateways/upstream/qoder/qoder_catalog.py:375 起 qfmodel 条目：display_name Qwen3.8-Flash、format openai、
  PROGRESS.md:2337:   price_factor 0.0、original_price_factor 0.1、is_free true、max_input_tokens 180000。
  ...
  PROGRESS.md:2368: - 经 7871 实测 200（2.07s），网关日志 model=Qwen-3.8-Flash -> QD:Qwen3.8-Flash (1/3)
  PROGRESS.md:2369:   ⇒ alias map 热更新生效，不需要重启 zgate。
  PROGRESS.md:2370: - --check --arena --scores → 无漂移（exit 0）；unittest 49 passed（44 + 新增 5）。
  ...
  PROGRESS.md:2423: 
  PROGRESS.md:2424: ## 2026-11-09 开机弹两个 cmd 窗口：根因与自启收敛
  PROGRESS.md:2425: 
  PROGRESS.md:2426: - **现象**：开机弹两个 cmd 窗口（实为 Win11 Windows Terminal 接管的 console，标题是 zgate.exe 路径）。
  PROGRESS.md:2427: - **根因**：`gateways/zgate/zgate.exe` 被裸 `go build .` 覆盖成控制台版（`build.py --check` 报
  PROGRESS.md:2428:   `Subsystem = 3`，10469888B / 11-06 22:55，与 `zgate-0.3.0-cand.exe` 同尺寸）；叠加自启有三条重复路径
  PROGRESS.md:2429:   （启动文件夹 lnk + HKCU Run daemon + 计划任务 `ModelBus-zgate`），第二实例抢 7871 失败退出。
  PROGRESS.md:2430: - **修复**：`mv zgate.exe .work/zgate.exe.console-bak-20261109` → `python gateways/zgate/build.py`
  PROGRESS.md:2431:   → `Subsystem = 2 → WINDOWS_GUI`（10490368B / 07:24）；删除启动文件夹 `ModelBus zgate.lnk`、
  PROGRESS.md:2432:   HKCU Run 值 `ZcodeAIModels-zgate-daemon`（并杀掉 pid 9804）、计划任务 `\ModelBus-zgate`
  PROGRESS.md:2433:   （UAC `schtasks /Delete /F`）；新增 `\ModelBus-zgate-hidden`（AtLogOn → `launch-zgate.vbs` →
  PROGRESS.md:2434:   `start-zgate-nw.ps1`，`CreateNoWindow`，跑完自退）；`ensure-zgate.ps1` 的启动动作改为调用
  PROGRESS.md:2435:   `start-zgate-nw.ps1`，看门狗 `\ModelBus-zgate-watchdog` 保持 PT1M 启用。
  PROGRESS.md:2436: - **未动**：`CSPPassword.ahk.lnk`（itzmx 加密包自动填密码，有用，保留）；`cmd.exe /C AMDRSServ.exe`
  PROGRESS.md:2437:   （AMD 机制，hwnd=0 不弹窗）；当前 zgate pid 5388 未重启（AGENTS §6 禁止会话内重启长驻网关），
  PROGRESS.md:2438:   它继续在 7871 服务，其可见 wt 窗口随下次重启消失。
  PROGRESS.md:2439: - **文档**：`docs/MAINTENANCE.md` §8.1、`docs/ARCHITECTURE.md` §3.1 + §10.2、`docs/PITFALLS.md` §20、
  PROGRESS.md:2440:   `docs/TROUBLESHOOTING.md` §16 已同步；`memories/zgate-windowless-build.md` 新增「自启收敛」章节。
  PROGRESS.md:2441:   备份与回滚：`%LOCALAPPDATA%\ZCodeGateway\autostart-backup-20261109\restore-autostart.ps1`。
  PROGRESS.md:2442: - **验证**：`build.py --check` = Subsystem 2；`wscript //B //Nologo launch-zgate.vbs` →
  PROGRESS.md:2443:   `zgate-launch.log` 记 `port already up, skip` 且 wt/OpenConsole 计数不增；watchdog 07:26:01
  PROGRESS.md:2444:   LastTaskResult=0；`curl /health` = 200；`python tools/check-docs.py` 35 篇全通。
  ...
  PROGRESS.md:2454:   四个 Gemini 0.00；Gemini-4-Argon 因 1.76 > 0.11 被跳过，不再落在任何路由上。
  PROGRESS.md:2455: - **热载**：正确端点是 `POST http://127.0.0.1:7871/admin/reload`（`/reload` 返回 000），返回
  PROGRESS.md:2456:   `{"applied":["workbuddy","qoder","cliproxyapi"],"ok":true}`。
  ...
  PROGRESS.md:2459:   换模型换协议一致。需账号验证或改用 `api-keys.gemini` + 真 API key。
  PROGRESS.md:2460: - **网关换版**：`.work/restart_zgate.ps1` 已跑完（`OK swapped 2026-11-09T13:15:27`），zgate.log 13:15:26 出现
  PROGRESS.md:2461:   `CP : http://127.0.0.1:8317/v1 (key=ok, child=cliproxyapi)`，CP 渠道注册成功。
  PROGRESS.md:2462: - **坑**：`zgate.exe` / `zgate.exe.bak-20261109` / `.work/zgate.candidate.exe` 三者 md5 相同
  PROGRESS.md:2463:   （9a6ced21cac6061dab90d74f94f49018），备份脚本抓到的是已替换的新文件，旧二进制未真正保留，回滚需重编旧代码。
  PROGRESS.md:2464: - **入库卫生**：`third-party/cliproxyapi/.gitignore` 追加 `*.err`；删掉 aglogin*.err/.work_test.json/run.*.log；
  ...
  PROGRESS.md:2479: - **三个 bug（都已修）**：
  PROGRESS.md:2480:   1. `gateways/zgate/zgate.json` 的 cliproxyapi child 路径写成 `../third-party/...`，解析成
  PROGRESS.md:2481:      `gateways/third-party/...` → 日志 `fork/exec ...: The directory name is invalid`。改为 `../../third-party/...`。
  PROGRESS.md:2482:   2. `gateways/zgate/internal/router/router.go:474` 的 `switch channel` 只有 WB/QD/QW/OC，**漏了 CP** →
  PROGRESS.md:2483:      转发时保留客户端 Bearer，CLIProxyAPI 回 `401 {"error":"Invalid API key"}`。已加 CP 到第一个 case。
  PROGRESS.md:2484:   3. 重编后 zgate.exe 需要换版才生效（restart 脚本备份名改 `zgate.exe.prev`，无条件覆盖）。
  PROGRESS.md:2485: - **主力**：Gemini-3.6-Flash / Gemini-3-Flash(3-flash-preview) / Gemini-3.5-Flash-Lite / Gemini-3.1-Flash-Lite，
  PROGRESS.md:2486:   全部 0.00；3.7-flash 因经 CP 常 503 过载且直连 104s 不进主力，仍留在 CP 模型列表可手动选。
  PROGRESS.md:2487: - **验证**：`python .work/e2e_final.py` 四型号并发打 zgate 7871 → 全部 200，1.1-2.1s；
  PROGRESS.md:2488:   `/admin/reload` 返回 applied=[cliproxyapi workbuddy qoder]；zgate.log 记
  PROGRESS.md:2489:   `POST /chat/completions model=Gemini-3.5-Flash-Lite -> CP:gemini-3.5-flash-lite (1/1)`。
  PROGRESS.md:2490: - **antigravity OAuth**：用户称已登录验证，实测仍 `403 VALIDATION_REQUIRED`（凭证在 auths/，模型仍列出但不可用）。
  PROGRESS.md:2491: 
  ...
  PROGRESS.md:2520:   `cooling=2`（Conatus 502 与另一条，日志无 cooling 行，属路由层计数，不影响主力）。
  PROGRESS.md:2521: - 未追踪项：`gateways/zgate/.restart.log`、`gateways/zgate/zgate.exe.prev`、`third-party/cliproxyapi/`。
  PROGRESS.md:2522: 
  ...
  PROGRESS.md:2527: - **现象**：首发 Gemini-3.6-Flash 偶发，随后 45 秒内所有 Gemini 请求全 502
  PROGRESS.md:2528:   （`{"error":{"message":"all upstreams failed: OC:gm"}}` 类），zgate 日志
  PROGRESS.md:2529:   `429 退避 700ms 后重试同一跳` → `退避后仍 429，冷却 45s` → `冷却中，跳过`。
  ...
  PROGRESS.md:2532:      每分钟 250k input token 的瞬时限流（上游回 `Please retry in 59.15s`）没在 CP 内部消化，
  PROGRESS.md:2533:      直接把 429 透给 zgate；`gemini-3.7-flash` 的 503 UNAVAILABLE 同理。
  PROGRESS.md:2534:   2. Gemini 别名是 **chain 长度 1**，走 `routeAlias` 的单跳分支 `s.forward` →
  ...
  PROGRESS.md:2537: - **改法**：
  PROGRESS.md:2538:   - `gateways/zgate/internal/router/router.go`：单跳分支改走新增的 `forwardSingle`：
  PROGRESS.md:2539:     传输层失败重试 1 次（`transportRetryDelay`）；>=400 读 8KB 响应头，429 退避
  ...
  PROGRESS.md:2550:     `TestRegionBlockedDoesNotCoolALoneHop` 均 PASS。
  PROGRESS.md:2551:   - 离线端到端（`.work/zgate-fix-20261109`，桩 18317 前两次 429、隔离实例 17871 单跳指向桩）：
  PROGRESS.md:2552:     请求 1 → `退避 700ms 后重试同一跳` → `退避后仍 429，冷却 45s` → 502（706ms，2 次命中桩）；
  PROGRESS.md:2553:     请求 2/3 冷却期内 → 502（0~1ms，不再打上游）；冷却过期后 → 200，桩计数连续递增。
  PROGRESS.md:2554:   - 生产实例未重启（仍是旧二进制），改后 `/health` 与四型号探测不受影响。
  PROGRESS.md:2555: - **待生效**：CP 的 `routing` 段要 zgate reload/重启 child 才读到，zgate 新二进制同理 ——
  PROGRESS.md:2556:   按规矩不自动重启长驻网关，由人工择时执行 `gateways/zgate` 重启 + child 拉起。
  PROGRESS.md:2557: 
  PROGRESS.md:2558: ## 2026-11-09 14:4x zgate 前台进程随终端关闭而死
  PROGRESS.md:2559: 
  PROGRESS.md:2560: - **现象**：在 Windows Terminal / cmd 里起 zgate（父链 WindowsTerminal → cmd → zgate），
  PROGRESS.md:2561:   一关窗口网关就结束，四个 chat 组全 502；用户问「为什么不能在 cmd 里拉起」。
  PROGRESS.md:2562: - **根因**：`zgate serve` 是前台进程，控制台窗口关闭对窗内所有进程发
  PROGRESS.md:2563:   `CTRL_CLOSE_EVENT`；wb2api 等子进程又挂在 zgate 的 Job Object（KILL_ON_JOB_CLOSE）上，
  PROGRESS.md:2564:   一起走。产物本身已是 GUI 子系统，但 GUI 子系统只要 `AttachParentConsole()` 成功仍会
  PROGRESS.md:2565:   成为控制台的一员。
  PROGRESS.md:2566: - **改法**（`gateways/zgate`）：
  PROGRESS.md:2567:   - `internal/winproc/console_windows.go`：新增 `DetachConsole()`（`FreeConsole` + 只对
  PROGRESS.md:2568:     控制台句柄生效，pipe/文件重定向不动）；`main.go` 的 `serve()` 打完启动横幅后调用，
  PROGRESS.md:2569:     前台运行不再留半死 conhost，`zgate status > out.txt` 依旧有输出。
  PROGRESS.md:2570:   - `main.go`：新增 `serve -tray`（别名 `--tray` / `-background`）→ `detach()`，
  PROGRESS.md:2571:     以 `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW` 拉起副本后立即返回；
  PROGRESS.md:2572:     副本无控制台，收不到关窗事件。拉起方把自身 PID 放进 `ZGATE_PARENT_PID`，
  PROGRESS.md:2573:     `serve()` 里的 `superviseLauncher` 每 2s 用 `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)`
  PROGRESS.md:2574:     +`GetExitCodeProcess` 判断拉起方是否还在，没了就 `os.Exit(0)`，不留孤儿占端口。
  PROGRESS.md:2575:   - `internal/winproc/winproc_{windows,other}.go`：新增 `DetachedAttr()`、`ProcessAlive()`。
  PROGRESS.md:2576:   - `install()`：登录自启快捷方式的目标参数由 `serve` 改成 `serve -tray`。
  PROGRESS.md:2577:   - 备份：`main.go.bak-20261109-dup`、`console_windows.go.bak-20261109-detach`、
  ...
  PROGRESS.md:2581:     `python build.py` 成功，`--check` 报 `Subsystem = 2 → WINDOWS_GUI`，产物 10516480 B。
  PROGRESS.md:2582:   - 隔离实例（`ZGATE_CONFIG` 指向 `.work/zgate-detach-verify`，端口 17991）：
  PROGRESS.md:2583:     `serve -tray` 输出「已在后台启动: <exe> (pid N, ready=true)；停止: Stop-Process -Id N」
  PROGRESS.md:2584:     且同一行落日志；拉起方退出后 2s 内日志出现「拉起方 <pid> 已退出，后台副本随之停止」，
  PROGRESS.md:2585:     进程消失、端口释放（预期行为）。
  PROGRESS.md:2586:   - 计划任务（schtasks 一次性任务，父为 Task Scheduler）起的普通 `serve`：跨 run_code
  PROGRESS.md:2587:     仍然 `/health` 200，证明「与调用方解耦后不会被进程树回收带走」。
  PROGRESS.md:2588:   - **发现**：`cmd /c`、`Start-Process` 这类结束整棵进程树的方式仍会带走
  PROGRESS.md:2589:     `DETACHED_PROCESS` 子进程（实测 2s 内消失）；彻底解耦只能靠计划任务启动（自启即此路径）。
  PROGRESS.md:2590: - **待生效**：生产实例（旧二进制）仍在跑，按规矩不自动重启；人工执行
  PROGRESS.md:2591:   `Stop-Process -Id <pid> -Force` 后用 `zgate.exe serve -tray` 重起即可。
  PROGRESS.md:2592: 
```
### README.md
```text
  ...
  README.md:26: WorkBuddy2API 网关、qoder2api-hub 网关）；现在统一成**三组**（主力 / 免费 / 省钱），
  README.md:27: 模型 ID 只用型号名（如 `DeepSeek-4.1-Flash`），同型号跨渠道合并成一条链路（WB 固定链首，其余按价格 / 前缀 / 渠道稳定排序），由 `tools/model_alias.py` 生成、`gateways/zgate`（Go，单进程）按 alias map 分流并托管两个本地网关。方法本身与供应商无关，接一个新供应商要做的四步见
  README.md:28: [docs/MODEL-PROVIDERS.md](https://github.com/MVennn/ModelBus/blob/main/docs/MODEL-PROVIDERS.md) §0。
  ...
  README.md:38: | 客户端 | ZCode 桌面端（Windows） |
  README.md:39: | 运行时 | Python 3（脚本只用标准库；门面重生成脚本 `tools/make_social_preview.py` 例外，需 numpy + Pillow）、Node.js 18+（跑探测/旧版路由）；统一入口 `gateways/zgate` 是**单个 Go 二进制**，日常运行不需要 Go（只有自行构建时需要 Go 1.22+，见 [docs/TOOLS.md](https://github.com/MVennn/ModelBus/blob/main/docs/TOOLS.md) §0） |
  README.md:40: | 配置与凭据 | ZCode 的 `provider_config.json`（默认在 `~/.zcode/v2/`）；凭据只走环境变量，变量名与取值见 [docs/SECRETS.md](https://github.com/MVennn/ModelBus/blob/main/docs/SECRETS.md) |
  README.md:41: | 网络 | 能直连你的供应商；三个 chat 组统一指向 `127.0.0.1:7871`（`zgate`），由它按需拉起 WorkBuddy 网关（`7863`）与 Qoder hub（`8790`）。生命周期与自启见 [docs/MAINTENANCE.md](https://github.com/MVennn/ModelBus/blob/main/docs/MAINTENANCE.md) §8 |
  README.md:42: 
  ...
  README.md:47: 
  README.md:48: 1. **准备环境变量** —— `OPENCODE_GO_KEY`（OpenCode-Go）、`WB_GATEWAY_KEY`（WorkBuddy 网关）、`QD_API_KEY`（Qoder 网关；也可用 git-ignored 的 `providers/qoder/.env.local`）。
  README.md:49: 2. **刷价格表** —— WorkBuddy 侧先跑 `providers/workbuddy/workbuddy_fetch_pricing.py`；
  ...
  README.md:71: `model_alias.py` 会**先备份再原子替换** `provider_config.json`；ZCode 约 1 秒轮询该文件，
  README.md:72: 写完一般不用重启客户端。统一入口（`gateways/zgate`）、alias map、协议桥与各脚本产物见
  README.md:73: [docs/TOOLS.md](https://github.com/MVennn/ModelBus/blob/main/docs/TOOLS.md)，
  ...
  README.md:96: - 脚本会修改**你自己的** ZCode 配置文件，写之前会自动备份，仍建议自己再备份一份
  README.md:97: - 示例涉及的 `opencode.ai`、WorkBuddy2API、Qoder 与**你自行接入的其它供应商**都是**第三方服务**，
  README.md:98:   本项目与它们不存在任何隶属、合作、授权或认可关系
  README.md:99: - 模型价格、额度、可用性与隐私策略**一律以服务商当时的说明为准**，本仓文档只是某一时刻的快照；
  README.md:100:   仓里的模型清单与分组按成本档 / 积分倍率排，是主观取舍，不是推荐
  ...
  README.md:106: 
  README.md:107: 本仓库建立在这些项目与服务之上（逐项声明见 [NOTICE](https://github.com/MVennn/ModelBus/blob/main/NOTICE)）：
  README.md:108: 
  ...
  README.md:112: | [**qoder2api-hub**](https://github.com/shuishuipingan/qoder2api-hub) | Qoder 账号网关，Qoder 侧全部请求都发给它（MIT；本仓不含其源码，只通过 HTTP 调用） |
  README.md:113: | **Qoder**（qoder.com.cn / qoder.com） | Qoder 侧的模型服务与账号（商业服务） |
  README.md:114: | **OpenCode Zen / Go**（opencode.ai） | 模型套餐与 API 网关，OpenCode-Go 侧全部请求都发给它（商业服务） |
  README.md:115: | [**ZCode**](https://github.com/zai-org/ZCode) | 目标客户端，本仓改它的配置并复刻它的请求体语义（Apache-2.0） |
  ...
  README.md:122: 
  README.md:123: 本项目以 [MIT License](https://github.com/MVennn/ModelBus/blob/main/LICENSE) 发布。第三方组件与服务的版权与条款声明见 [NOTICE](https://github.com/MVennn/ModelBus/blob/main/NOTICE)。
  README.md:124: 
```
### docs/ARCHITECTURE.md
```text
  ...
  docs/ARCHITECTURE.md:2: 
  docs/ARCHITECTURE.md:3: > **一句话**：把现在的「PowerShell 守护 + Node 路由 + 两个上游进程」收敛成
  docs/ARCHITECTURE.md:4: > **一个 Go 入口进程 + 按需拉起的子进程**，实测常驻内存 293 MB → ~128 MB
  ...
  docs/ARCHITECTURE.md:7: **状态：已落地（2026-10-23）。**
  docs/ARCHITECTURE.md:8: 运行层现在是 `gateways/`：`zgate`（Go）监听 7871 并托管两个子进程；
  docs/ARCHITECTURE.md:9: 接入层是 `providers/`。落地差异与实测数据见 §10，日常操作见
  ...
  docs/ARCHITECTURE.md:17: 
  docs/ARCHITECTURE.md:18: 三个网关里有两个是**上游 clone**：WorkBuddy2API（Go，`wb2api.exe`）和
  docs/ARCHITECTURE.md:19: qoder2api-hub（Python，`qoder_proxy.py`）。把它们"合进一个进程"等于重写上万个
  ...
  docs/ARCHITECTURE.md:26: | 入口路由 | `tools/unified-router.js`（Node） | 71.5 MB | ✅ 可以并入一个 Go 二进制 |
  docs/ARCHITECTURE.md:27: | 生命周期守护 | `workbuddy/zcode_gateway_watch.ps1`（PowerShell，常驻） | 124.2 MB | ✅ 必须换掉，PowerShell 常驻太贵 |
  docs/ARCHITECTURE.md:28: | WorkBuddy 上游 | `wb2api.exe` | 27.6 MB | ❌ 上游 clone，保留为子进程 |
  docs/ARCHITECTURE.md:29: | Qoder 上游 | `qoder_proxy.py` | 70.1 MB | ❌ 上游 clone，保留为子进程 |
  ...
  docs/ARCHITECTURE.md:41: | ZCode 开着，只用 OpenCode-Go | ~293 MB | ~20-48 MB（子进程按需/空闲回收） |
  docs/ARCHITECTURE.md:42: | ZCode 关着 | ~194 MB（守护器 + Qoder 常驻） | ~20 MB（任务窗口内 ~90 MB） |
  docs/ARCHITECTURE.md:43: 
  ...
  docs/ARCHITECTURE.md:51: |---|---|---|---|---|---|
  docs/ARCHITECTURE.md:52: | 1 | `powershell.exe`（`zcode_gateway_watch.ps1`） | — | **124.2** | 启动文件夹快捷方式 → `.vbs` | 网关/路由死了没人拉起；ZCode 关掉后网关不回收 |
  docs/ARCHITECTURE.md:53: | 2 | `node.exe tools/unified-router.js` | 7871 | **71.5** | #1 | **四组全挂**（路由在关键路径上） |
  docs/ARCHITECTURE.md:54: | 3 | `python.exe qoder_proxy.py` | 8790 | **70.1** | `start-qoder-proxy.bat`（detached，24/7） | 只有 `qoder:` 模型不可用 |
  docs/ARCHITECTURE.md:55: | 4 | `wb2api.exe` | 7863 | **27.6** | #1 | 只有 `cn:` / `global:` 模型不可用 |
  docs/ARCHITECTURE.md:56: | | **合计** | | **293.4** | | |
  docs/ARCHITECTURE.md:57: 
  docs/ARCHITECTURE.md:58: 四个进程、四条生命周期、四套日志（`watchdog.log` + `gateway.*.log` + `router.*.log` +
  docs/ARCHITECTURE.md:59: `qoder-proxy*.log`），三种实现语言（PowerShell / Node / Python）。
  docs/ARCHITECTURE.md:60: 
  docs/ARCHITECTURE.md:61: 参考基线（同一台机器实测，空载 HTTP 服务）：
  docs/ARCHITECTURE.md:62: 
  docs/ARCHITECTURE.md:63: - 极简 Go HTTP 服务：**8.3 MB**
  docs/ARCHITECTURE.md:64: - 极简 Node HTTP 服务：**46.6 MB**
  docs/ARCHITECTURE.md:65: 
  docs/ARCHITECTURE.md:66: 也就是说 Node 路由的 71.5 MB 里，约 47 MB 是运行时本身；PowerShell 守护器的
  docs/ARCHITECTURE.md:67: 124 MB 里几乎全是运行时 —— **换实现语言的收益比优化代码大得多**。
  ...
  docs/ARCHITECTURE.md:83: 
  docs/ARCHITECTURE.md:84: ## 3. 方案：`zgate`（一个 Go 二进制）
  docs/ARCHITECTURE.md:85: 
  ...
  docs/ARCHITECTURE.md:91: |---|---|
  docs/ARCHITECTURE.md:92: | `zgate serve` | 常驻：监听 7871，做 alias 分流 + 协议桥 + 子进程守护 |
  docs/ARCHITECTURE.md:93: | `zgate serve -tray` | 同上，但以 `DETACHED_PROCESS` 拉起无父进程副本后立即返回；关掉终端不影响网关 |
  docs/ARCHITECTURE.md:94: | `zgate status` | 打印各通道/子进程/alias 条数/最近错误（`--json` 给脚本用） |
  docs/ARCHITECTURE.md:95: | `zgate install` / `uninstall` | 注册 / 移除启动文件夹快捷方式 `ModelBus zgate.lnk`（不需要管理员）。现行自启已改为计划任务 `\ModelBus-zgate-hidden`（见 §10.2），这两个命令平时不用跑 |
  docs/ARCHITECTURE.md:96: | `zgate replay` | 拿录制的黄金样本回放，和 JS 路由的结果做逐字段比对（见 §6.1） |
  docs/ARCHITECTURE.md:97: 
  ...
  docs/ARCHITECTURE.md:100: ```
  docs/ARCHITECTURE.md:101: ZCode ──▶ 127.0.0.1:7871  zgate (Go, ~20 MB)
  docs/ARCHITECTURE.md:102:              │
  docs/ARCHITECTURE.md:103:              ├─ alias 未命中/OC 通道 ──▶ https://opencode.ai/zen/go/v1（远程，无本地进程）
  docs/ARCHITECTURE.md:104:              ├─ WB 通道 ──▶ 子进程 wb2api.exe :7863   （按需拉起 / 空闲回收）
  docs/ARCHITECTURE.md:105:              └─ QD 通道 ──▶ 子进程 python qoder_proxy.py :8790（按需拉起 / 空闲回收）
  ...
  docs/ARCHITECTURE.md:108: - **监听面不变**：仍然只有 7871 对 ZCode 暴露；7863 / 8790 继续只绑 `127.0.0.1`。
  docs/ARCHITECTURE.md:109: - **子进程用 Windows Job Object 托管**：`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`，
  docs/ARCHITECTURE.md:110:   zgate 崩了/被结束，子进程一起收掉，不会留孤儿（现在靠 PowerShell 启动时对账清理）。
  docs/ARCHITECTURE.md:111: - **单飞（single-flight）拉起**：同一通道并发首请求只触发一次启动，其余请求排队等
  docs/ARCHITECTURE.md:112:   健康检查就绪（`zgate.json` 的 `startTimeoutSeconds`：WB 30 s / Qoder 40 s，源码缺省 25 s，超时返回 503 而不是挂死）。
  docs/ARCHITECTURE.md:113: - **崩溃重启**：带指数退避（1s → 2s → 4s → … → 60s，见 `internal/supervisor/supervisor.go`）；
  docs/ARCHITECTURE.md:114:   `failCount` 只喂给退避计算，**没有降级标记**，`/health` 的 `States()` 也不含降级字段。
  ...
  docs/ARCHITECTURE.md:138: ```
  docs/ARCHITECTURE.md:139: gateways/zgate/
  docs/ARCHITECTURE.md:140: ├─ main.go                 # 子命令分发
  docs/ARCHITECTURE.md:141: ├─ config.json             # 端口 / 超时 / 回收阈值 / 子进程命令（不含凭据）
  docs/ARCHITECTURE.md:142: ├─ internal/alias/         # 读 ~/.zcode/v2/model-alias-map.json，按 mtime 热加载
  docs/ARCHITECTURE.md:143: ├─ internal/bridge/        # chat ↔ messages/responses + SSE 合成（protocol_bridge.js 的等价物）
  ...
  docs/ARCHITECTURE.md:145: ├─ internal/supervisor/    # 子进程起停、健康检查、空闲回收、退避、窗口调度
  docs/ARCHITECTURE.md:146: ├─ internal/winproc/       # Job Object、进程树终止、端口就绪探测
  docs/ARCHITECTURE.md:147: └─ internal/probe/         # 可选：把 model_probe.py 的探测请求也搬进来
  ...
  docs/ARCHITECTURE.md:156: 1. `opencode-go/ops/opencode-header-proxy.js`（8787，给第三方客户端补
  docs/ARCHITECTURE.md:157:    `x-opencode-session`）→ zgate 的第二个监听器，`config.json` 里 `profiles.client-headers`。
  docs/ARCHITECTURE.md:158:    它现在根本没在跑，但迟早要跑，别再多一个 Node 进程。
  ...
  docs/ARCHITECTURE.md:160:    （`up` / `starting` / `down` / `degraded`）、最后一次错误、子进程 PID、alias 条数。
  docs/ARCHITECTURE.md:161: 3. 日志合并：`zgate.log`（按大小轮转）+ 子进程 stdout/stderr 各一份，
  docs/ARCHITECTURE.md:162:    目录统一到 `%LOCALAPPDATA%\ZCodeGateway\`。今天的四套日志名保留一版兼容。
  docs/ARCHITECTURE.md:163: 
  ...
  docs/ARCHITECTURE.md:171: |---|---|
  docs/ARCHITECTURE.md:172: | 同一家供应商的"要跑的进程"和"要跑的脚本"混在一个目录 | `workbuddy/gateway/`（clone，235 文件 48 MB）与 `workbuddy/*.py`（采集脚本）同级 |
  docs/ARCHITECTURE.md:173: | 运行层没有统一的家 | 路由在 `tools/`，守护器在 `workbuddy/`，Qoder 启动脚本在 `qoder/gateway/` |
  docs/ARCHITECTURE.md:174: | 上游 clone 嵌两层 | `qoder/gateway/` 里再套 `docs/`、`scripts/`、`accounts/`，进入仓库后很难判断"哪些是上游、哪些是我们的" |
  docs/ARCHITECTURE.md:175: 
  ...
  docs/ARCHITECTURE.md:182: ModelBus/
  docs/ARCHITECTURE.md:183: ├─ gateways/                    # 【运行层】唯一会产出进程的目录
  docs/ARCHITECTURE.md:184: │  ├─ zgate/                    #   我们的 Go 入口（源码 + config.json）
  docs/ARCHITECTURE.md:185: │  ├─ upstream/
  docs/ARCHITECTURE.md:186: │  │  ├─ workbuddy/             #   ← workbuddy/gateway（clone，gitignored）
  docs/ARCHITECTURE.md:187: │  │  └─ qoder/                 #   ← qoder/gateway（clone，gitignored）
  docs/ARCHITECTURE.md:188: │  └─ runtime/                  #   日志 / pid / 状态（gitignored）
  ...
  docs/ARCHITECTURE.md:198: 
  docs/ARCHITECTURE.md:199: 判断规则一句话：**会被启动的东西进 `gateways/`，被手动执行的东西进 `providers/`，
  docs/ARCHITECTURE.md:200: 跨供应商复用的进 `tools/`。**
  ...
  docs/ARCHITECTURE.md:205: |---|---|
  docs/ARCHITECTURE.md:206: | `workbuddy/gateway/` | `gateways/upstream/workbuddy/` |
  docs/ARCHITECTURE.md:207: | `qoder/gateway/` | `gateways/upstream/qoder/` |
  docs/ARCHITECTURE.md:208: | `tools/unified-router.js`、`tools/protocol_bridge.js` | 迁入 `gateways/zgate/` 并重写为 Go；JS 版留在 `gateways/legacy-router/` 作回退 |
  docs/ARCHITECTURE.md:209: | `opencode-go/ops/opencode-header-proxy.js` | 先留在 `providers/opencode-go/ops/`，P3 后由 zgate profile 取代 |
  docs/ARCHITECTURE.md:210: | `opencode-go/{ops,probe}/` | `providers/opencode-go/` |
  docs/ARCHITECTURE.md:211: | `workbuddy/*.py`、`workbuddy/cache/`、`workbuddy/logs/` | `providers/workbuddy/` |
  docs/ARCHITECTURE.md:212: | `workbuddy/zcode_gateway_watch.ps1` / `.vbs` | 退役 → `zgate install`（P2 后删除） |
  docs/ARCHITECTURE.md:213: | `qoder/*.py`、`qoder/.env.local` | `providers/qoder/` |
  ...
  docs/ARCHITECTURE.md:217: 
  docs/ARCHITECTURE.md:218: 1. 关 ZCode；停守护器、停路由；`workbuddy/gateway/stop-gateway.bat`；
  docs/ARCHITECTURE.md:219:    `qoder/gateway/stop-qoder-proxy.bat`（**Qoder 必须停，它的 cwd 就在被移动的目录里**）。
  docs/ARCHITECTURE.md:220: 2. tracked 文件用 `git mv`；两个 clone 是独立 `.git`，用普通 `mv`（保留 `.git`，
  docs/ARCHITECTURE.md:221:    上游更新命令随之改为 `git -C gateways/upstream/qoder pull --ff-only`）。
  docs/ARCHITECTURE.md:222: 3. 改 `.gitignore`：`/workbuddy/gateway/` → `/gateways/upstream/workbuddy/`，
  docs/ARCHITECTURE.md:223:    `/qoder/gateway/` → `/gateways/upstream/qoder/`，`/workbuddy/cache/*.json` →
  docs/ARCHITECTURE.md:224:    `/providers/workbuddy/cache/*.json`，另加 `/gateways/runtime/`、`*.exe`。
  docs/ARCHITECTURE.md:225: 4. 改代码里的硬编码路径（**已定位，共 4 个文件**）：
  ...
  docs/ARCHITECTURE.md:230:    `.github/ISSUE_TEMPLATE/bug_report.yml` 里共有 130 处路径。
  docs/ARCHITECTURE.md:231:    做法：`git grep -l 'workbuddy/gateway\|qoder/gateway\|opencode-go/\|tools/unified-router'`
  docs/ARCHITECTURE.md:232:    一次改完，再用同一命令确认归零。
  docs/ARCHITECTURE.md:233: 6. 重建启动入口：`qoder` 的 `start-*.bat` 用 `%~dp0` 自推导，移动后仍可用；
  docs/ARCHITECTURE.md:234:    WorkBuddy 的 `run.bat` / `stop-gateway.bat` 同理。P2 之后统一收归 `zgate`。
  docs/ARCHITECTURE.md:235: 7. CI 跑一遍：`python tools/check-docs.py`、`python tools/check-secrets.py`、
  ...
  docs/ARCHITECTURE.md:238: > **要不要搬？** 建议搬，而且现在搬 —— tracked 文件才 97 个，越晚成本越高。
  docs/ARCHITECTURE.md:239: > 若不想承担 130 处引用的改动，最小替代方案是只新建 `gateways/`，
  docs/ARCHITECTURE.md:240: > 把两个 clone 搬进去、`zgate` 放进去，`providers/` 暂缓 —— 省一半改动，结构仍改善。
  docs/ARCHITECTURE.md:241: 
  ...
  docs/ARCHITECTURE.md:250: - 做 §4.3 的移动 + 引用修正。
  docs/ARCHITECTURE.md:251: - 验收：`check-docs` / `check-secrets` 通过；ZCode 四组模型列表不变；三个网关重启后可用。
  docs/ARCHITECTURE.md:252: 
  docs/ARCHITECTURE.md:253: ### P1 · Go 守护器顶掉 PowerShell（1 天，省 ~114 MB）
  docs/ARCHITECTURE.md:254: 
  docs/ARCHITECTURE.md:255: - 只写 `internal/supervisor` + `internal/winproc` + `install/status`；路由仍是 Node。
  docs/ARCHITECTURE.md:256: - 行为对齐今天：跟随 ZCode 主进程、8 s 宽限、5 s 排空、崩溃重启、心跳、孤儿清理。
  docs/ARCHITECTURE.md:257: - 验收：见 §7 的 1–6 项。
  docs/ARCHITECTURE.md:258: 
  docs/ARCHITECTURE.md:259: > 若不想引入 Go：把守护逻辑并进 `unified-router.js` 也能省掉这 114 MB（仍是一个
  docs/ARCHITECTURE.md:260: > Node 进程 71.5 MB），代码量约 300 行。这是**方案乙**，见 §8 选项 A。
  ...
  docs/ARCHITECTURE.md:263: 
  docs/ARCHITECTURE.md:264: - `internal/alias`、`internal/bridge`、`internal/router`；`zgate replay` 黄金回归先绿再接。
  docs/ARCHITECTURE.md:265: - 端口、路径、错误码、SSE 分片节奏保持兼容。
  ...
  docs/ARCHITECTURE.md:297: 2. 样本存 `evidence/golden/`（脱敏后可用）。
  docs/ARCHITECTURE.md:298: 3. `zgate replay --golden evidence/golden/` 逐条比对：状态码相等、JSON 归一后深比较
  docs/ARCHITECTURE.md:299:    相等、SSE 事件序列（`event` 类型 + `[DONE]`）相等。
  ...
  docs/ARCHITECTURE.md:305: |---|---|---|
  docs/ARCHITECTURE.md:306: | 子进程杀不干净（端口占用） | 重启失败 / 端口冲突 | Job Object + 端口就绪探测 + 启动前按 PID/端口对账 |
  docs/ARCHITECTURE.md:307: | 按需拉起引入首字延迟（1–3 s） | 体验下降 | 默认 `always` 起步；`on-demand` 只对 WB 开；健康检查预热 |
  docs/ARCHITECTURE.md:308: | 防护软件拦新 exe | 起不来 | 本地构建、不随仓库发 exe；首次运行加白 |
  docs/ARCHITECTURE.md:309: | 单点：zgate 崩了四组全挂 | 全渠道不可用 | 计划任务"失败即重启"；`/health` 里暴露自身存活；子进程独立进程仍可直连兜底 |
  docs/ARCHITECTURE.md:310: | 迁移期间 JS 路由和 Go 路由抢 7871 | 启动失败 | 迁移只在 ZCode 关闭时做；端口占用时 `zgate` 拒绝启动并明确报错 |
  docs/ARCHITECTURE.md:311: | 目录搬迁漏改引用 | 脚本静默失败 | `git grep` 归零检查 + CI 里加一条路径存在性断言 |
  ...
  docs/ARCHITECTURE.md:315: - P0：`git revert` 一个提交（clone 是 untracked，搬回即可）。
  docs/ARCHITECTURE.md:316: - P1：`zgate uninstall` → 重新 `zcode_gateway_watch.ps1 -Install`。
  docs/ARCHITECTURE.md:317: - P2：`config.json` 里 `router.impl = "node"`，仍可回落 JS 版（保留一个版本）。
  docs/ARCHITECTURE.md:318: - P3：`config.json` 里把通道改回 `always`，重启即恢复今天行为。
  docs/ARCHITECTURE.md:319: 
  ...
  docs/ARCHITECTURE.md:327: | 2 | ZCode 起停联动 | 开 ZCode → 子进程在 2 s 内就绪；关 ZCode → 宽限期后回收，端口释放 |
  docs/ARCHITECTURE.md:328: | 3 | 崩溃重启 | `Stop-Process` 掉子进程 → 5 s 内自动回来；`/health` 反映状态变化 |
  docs/ARCHITECTURE.md:329: | 4 | 孤儿清理 | 强杀 zgate → 子进程随之退出（Job Object 生效） |
  docs/ARCHITECTURE.md:330: | 5 | 心跳/日志 | 15 min 一条心跳；日志轮转正常，UTF-8 不乱码 |
  docs/ARCHITECTURE.md:331: | 6 | 不回归 | 四组共 36 个模型的列表、`baseUrl` 与今天完全一致 |
  docs/ARCHITECTURE.md:332: | 7 | 黄金回归 | `zgate replay` 全绿（§6.1） |
  docs/ARCHITECTURE.md:333: | 8 | 流式 | 三个渠道各挑一个流式请求，首字时间与今天同量级，SSE 无截断 |
  ...
  docs/ARCHITECTURE.md:348: |---|---|---|---|
  docs/ARCHITECTURE.md:349: | A | 入口换成 Go，还是保守地把守护并进现有 Node 路由？ | ① Go 一体（293→128，去 Node 依赖）② Node 一体（293→169，改动最小） | **①**：Go 1.26 已装，桥+路由共 ~1500 行，换掉 946 行 JS/PS1，维护面积不增；②可作为第一步 |
  docs/ARCHITECTURE.md:350: | B | 目录一次搬完（`gateways/` + `providers/`），还是只搬 clone？ | ① 全搬（130 处引用）② 只搬 clone | **①**：tracked 仅 97 个文件，现在搬最便宜 |
  docs/ARCHITECTURE.md:351: | C | Qoder 允许按需停吗（会影响 09:00 / 21:00 签到）？ | ① 保持 24/7 ② 切 `scheduled` 窗口 | **②但要先实测**：窗口拉起后 `_allow_complement_checkin` 是否真补签；不成立就退回 ① |
  docs/ARCHITECTURE.md:352: | D | WorkBuddy 的签到/夜猫子/额度刷新要不要顺手修好（现在是"ZCode 关着就不跑"）？ | ① 维持现状 ② 交给 zgate 定时窗口 | **②**：反正要写调度器，顺手补上，等于免费修一个既有缺陷 |
  docs/ARCHITECTURE.md:353: | E | JS 路由保留多久？ | ① P2 后立即删 ② 留一个版本作回退 | **②**：留到 P3 验收通过再删 |
  ...
  docs/ARCHITECTURE.md:362: # 各进程常驻内存
  docs/ARCHITECTURE.md:363: Get-CimInstance Win32_Process -Filter "Name='node.exe' or Name='python.exe' or Name='wb2api.exe' or Name='powershell.exe'" |
  docs/ARCHITECTURE.md:364:   Select-Object ProcessId,Name,CommandLine,
  ...
  docs/ARCHITECTURE.md:380: | **换现成聚合器**（CLIProxyAPI / OmniRoute / Agent2API / LiteLLM） | 能替 Node 路由，但要重接 alias map、协议桥、思考参数矩阵；WB/QD 的面板、签到、额度都在上游进程里，聚合器替不掉。等于用黑盒换 50 MB，回归风险高于自研 |
  docs/ARCHITECTURE.md:381: | **把两个上游重写成 Go 或嵌进本进程** | wb2api（Go 上游，含 panel/auths/定时任务）与 qoder_proxy（Python 1.1 万行，含 OAuth/签名/风控/调度/看板）重写成本以月计，且放弃 `git pull` 更新通道。**不可行** |
  docs/ARCHITECTURE.md:382: | **加一层 Nginx/Caddy 统一反代** | 只是把两段跳转变三段，多一个进程，内存反而涨 |
  ...
  docs/ARCHITECTURE.md:392: |---|---|
  docs/ARCHITECTURE.md:393: | P0 目录重构 | 完成。`gateways/{zgate,legacy-router,upstream/{workbuddy,qoder}}` + `providers/{opencode-go,workbuddy,qoder}`；4 个脚本的硬编码路径、`.gitignore`、19 篇文档/模板的路径全部改齐，`check-docs` / `check-secrets` 通过 |
  docs/ARCHITECTURE.md:394: | P1 守护器 | 完成，但**没有**按原计划跟随 ZCode 主进程 —— 见 §10.2 |
  docs/ARCHITECTURE.md:395: | P2 路由 + 协议桥 | 完成。Go 实现约 2000 行（含测试），替换 857 行 JS |
  ...
  docs/ARCHITECTURE.md:400: 1. **去掉了「跟随 ZCode 主进程」**。在 Go 里判 ZCode 主进程要读 PEB 命令行（`--type=` 过滤），
  docs/ARCHITECTURE.md:401:    实现成本高且脆弱。改成 **zgate 常驻 + 子进程策略**：zgate 约 19 MB，常驻代价远小于原来的
  docs/ARCHITECTURE.md:402:    PowerShell 守护器（124 MB），还顺手解决了「ZCode 关着时 WorkBuddy 定时任务不跑」的老问题 ——
  docs/ARCHITECTURE.md:403:    把 `children.workbuddy.policy` 设成 `always` 即可让它 24/7 跑。
  docs/ARCHITECTURE.md:404: 2. **自启用登录计划任务**。早期 `schtasks /create /sc ONLOGON` 在非管理员权限下返回「拒绝访问」，于是改用
  docs/ARCHITECTURE.md:405:    启动文件夹快捷方式；2026-11-09 起收敛为计划任务 `\ModelBus-zgate-hidden`（AtLogOn、当前用户 Interactive，
  docs/ARCHITECTURE.md:406:    `Register-ScheduledTask` 不需要提权）→ `wscript //B //Nologo launch-zgate.vbs` → `start-zgate-nw.ps1`
  docs/ARCHITECTURE.md:407:    （`CreateNoWindow` 拉起 `zgate serve`，端口已占则直接退出）。两条附加约束：产物必须是 **GUI 子系统**
  docs/ARCHITECTURE.md:408:    （否则 Win11 的 Windows Terminal 接管 console 照样弹窗，`-WindowStyle Hidden` 和 lnk 的 `WindowStyle=7` 都拦不住），
  ...
  docs/ARCHITECTURE.md:411:    而是给任意 child 加的 `windows` 列表，窗内按 `always` 处理。
  docs/ARCHITECTURE.md:412: 4. **旧 JS 路由保留**在 `gateways/legacy-router/`，作为回退；P3 验收通过后可删。
  docs/ARCHITECTURE.md:413: 
  ...
  docs/ARCHITECTURE.md:418: 三种流式 / 未知模型，**9/9 一致**。之后切到 7871，四条通道各打一发真实请求全部 200；
  docs/ARCHITECTURE.md:419: WB 冷启动 1.6 秒，Qoder 由 zgate 启动后 `/ping` 200。
  docs/ARCHITECTURE.md:420: 
  ...
  docs/ARCHITECTURE.md:424: |---|---|---|
  docs/ARCHITECTURE.md:425: | 三路都在用 | 293.4 MB（4 进程） | **99.3 MB**（zgate 18.7 + Qoder 57.4 + wb2api 23.2） |
  docs/ARCHITECTURE.md:426: | WB 空闲 15 分钟回收后 | — | **76.1 MB**（zgate + Qoder） |
  docs/ARCHITECTURE.md:427: | 全部停掉只剩 zgate | — | **18.7 MB** |
  docs/ARCHITECTURE.md:428: 
  ...
  docs/ARCHITECTURE.md:433: 
  docs/ARCHITECTURE.md:434: - WB 首次请求多 1–2 秒冷启动（旧守护器在 ZCode 启动时就常驻了）。
  docs/ARCHITECTURE.md:435:   不能接受就把 `children.workbuddy.policy` 改成 `always`。
  ...
  docs/ARCHITECTURE.md:448: | 空闲阈值降到 300 秒 | 一次对话结束后 5 分钟内回收 |
  docs/ARCHITECTURE.md:449: | 新增 `zgate reload` + `POST /admin/reload` | 改策略/窗口/阈值不用重启；新增 child、监听地址、上游 base 仍需重启 |
  docs/ARCHITECTURE.md:450: 
  ...
  docs/ARCHITECTURE.md:454: - `Process.Release` 改为 `sync.Once`，消除监控 goroutine 与主动停止的 double CloseHandle；
  docs/ARCHITECTURE.md:455: - 接管的 `external` 实例每 5 秒做一次健康检查，死了会转回 zgate 管理并自动重启；
  docs/ARCHITECTURE.md:456: - 重启退避改成 1s→2s→4s→…→60s（与 §3.2 一致）；
  docs/ARCHITECTURE.md:457: - 日志在运行期按 5 MB 轮转（常驻进程原来只有启动时轮转）；`zgate status` 不再打开写句柄；
  docs/ARCHITECTURE.md:458: - **回退链补齐**：WB 的 `400 model_unavailable`（上游 6004 模型级限流）原来不触发 region fallback，
  ...
  docs/ARCHITECTURE.md:464: - 启动时不带窗口的子进程保持 `stopped`；窗口内的子进程自动 `running`；
  docs/ARCHITECTURE.md:465: - `POST /admin/reload` 去掉窗口并把 `idleSeconds` 设 1 后，一个 tick 内回到 `stopped`；
  docs/ARCHITECTURE.md:466: - 单元测试新增：窗口解析/跨午夜、`ApplyConfig`、退避序列、桥超时、`/admin/reload`，共 24 个用例。
  docs/ARCHITECTURE.md:467: 
```
### docs/BENCHMARKS.md
```text
  ...
  docs/BENCHMARKS.md:71: | 4 | QWEN3.8-FLASH · XHIGH | `qoder` | 372.95 | 96.19 | 91.05 | 94.00 | 91.71 | 08-31 |
  docs/BENCHMARKS.md:72: | 5 | DEEPSEEK-V4-PRO-0821凌晨灰测 · MAX | `dsh` | 367.55 | 91.84 | 95.17 | 96.00 | 84.54 | 08-21 |
  docs/BENCHMARKS.md:73: | 6 | GLM-5.3 (ZCODE) | `zcode` | 351.01 | 87.19 | 85.64 | 96.00 | 82.18 | 08-16 |
  ...
  docs/BENCHMARKS.md:77: | 10 | QWEN3.8 · MAX-0902 · XHIGH | `qoder` | 344.43 | 90.84 | 87.48 | 80.00 | 86.11 | 09-02 |
  docs/BENCHMARKS.md:78: | 11 | DEEPSEEK-V4.1-FLASH-E0910 · MAX | `dsh` | 342.40 | 87.77 | 89.55 | 79.50 | 85.58 | 09-08 |
  docs/BENCHMARKS.md:79: | 12 | GLM-5.3-FLASH · MAX | `zcode` | 334.15 | 84.45 | 85.68 | 81.00 | 83.02 | 08-30 |
  ...
  docs/BENCHMARKS.md:87: | 20 | MUSE-SPARK-1.2-CONTRIBUTOR · XHIGH | `zcode` | 313.30 | 81.94 | 78.78 | 74.00 | 78.58 | 08-19 |
  docs/BENCHMARKS.md:88: | 21 | DSV4F0731 · MAX | `dsh-jspace` | 311.02 | 78.62 | 84.06 | 70.00 | 78.34 | 08-17 |
  docs/BENCHMARKS.md:89: | 22 | GROK-4.6 · XHIGH | `cursor` | 308.82 | 80.06 | 85.18 | 79.00 | 64.58 | 08-15 |
  ...
  docs/BENCHMARKS.md:92: | 25 | MINIMAX-M3 · THINKING | `workbuddy` | 279.78 | 83.30 | 66.28 | 62.00 | 68.20 | 08-10 |
  docs/BENCHMARKS.md:93: | 26 | DSV4F-VE-OCGO · MAX | `dsh` | 245.70 | 69.76 | 75.55 | 33.00 | 67.39 | 08-31 |
  docs/BENCHMARKS.md:94: | 27 | SEED-2.1-PRO | `trae` | 244.35 | 73.11 | 59.91 | 64.00 | 47.33 | 08-12 |
  ...
  docs/BENCHMARKS.md:136: |---|---|---:|---:|---|
  docs/BENCHMARKS.md:137: | 主力（OpenCode-Go） | `deepseek-v4.1-flash` | #11 | 342.40 | `dsh` |
  docs/BENCHMARKS.md:138: | 低耗（OpenCode-Go） | `glm-5.3-flash` | #12 | 334.15 | `zcode` |
  ...
  docs/BENCHMARKS.md:140: | 长上下文（OpenCode-Go） | `minimax-m3` | #25 | 279.78 | `workbuddy` |
  docs/BENCHMARKS.md:141: | 后台批量（OpenCode-Go） | `hy3` | #28 | 237.47 | `workbuddy` |
  docs/BENCHMARKS.md:142: | WorkBuddy 网关（高代 / 免代） | `hy4-preview` | #7 | 350.71 | `workbuddy` |
  ...
  docs/BENCHMARKS.md:165: | `minimax-m3` | 文字 | 83.30 | 知识 68.20 | 后端 62.00 | 长上下文 / chat |
  docs/BENCHMARKS.md:166: | `hy3` | 前端 | 71.01 | 后端 64.00 | 知识 46.97 | 后台批量 / chat |
  docs/BENCHMARKS.md:167: | `glm-5.3`（未收录） | 后端 | 96.00 | 文字 87.19 | 知识 82.18 | 仅知协议 |
  ...
  docs/BENCHMARKS.md:257:   只适合不敏感的活。
  docs/BENCHMARKS.md:258: - **`hy3` 智力只有 69.4，但价格指数 48.3、性价比 1.43**，仍归低耗（便宜的后台批量），
  docs/BENCHMARKS.md:259:   不是「因为分数低就淘汰」。
  ...
  docs/BENCHMARKS.md:450: 
  docs/BENCHMARKS.md:451: ### 9.5 2026-11-06 首次生效的变化
  docs/BENCHMARKS.md:452: 
```
### docs/DOC-RULES.md
```text
  ...
  docs/DOC-RULES.md:62: | PROGRESS 的路径规则、凭据规则 | 仓库根 [AGENTS.md](../AGENTS.md) |
  docs/DOC-RULES.md:63: | 第三方组件与服务的声明 | 仓库根 [NOTICE](../NOTICE) |
  docs/DOC-RULES.md:64: | 同类项目调研与随仓分发的上游文件来源 | [UPSTREAM.md](UPSTREAM.md) + [../third-party/README.md](../third-party/README.md) |
```
### docs/MAINTENANCE.md
```text
  ...
  docs/MAINTENANCE.md:75: | `promo` / `promo_label` | 促销价与标签（"限时免费"、"Free now"） | 同上 |
  docs/MAINTENANCE.md:76: | `list_rate` / `eff_rate` | 牌价倍率 / 生效倍率 | `promo_credits` 优先，回落 `credits` |
  docs/MAINTENANCE.md:77: | `ctx` / `out` | 上下文长度 / 输出上限 | 同上 |
  ...
  docs/MAINTENANCE.md:86: curl -s http://127.0.0.1:7863/panel/api/models \
  docs/MAINTENANCE.md:87:   -H "Authorization: Bearer $WB_GATEWAY_KEY" | python -m json.tool | head -40
  docs/MAINTENANCE.md:88: ```
  docs/MAINTENANCE.md:89: 
  docs/MAINTENANCE.md:90: > ⚠️ 网关**未重启时** `/panel/api/models` 可能是残缺的（2026-11-02 实测一个跑了半天的
  docs/MAINTENANCE.md:91: > 子进程只回 2 个出图模型），重启子进程即恢复。取数前先看条数是否明显偏少。
  docs/MAINTENANCE.md:92: 
  ...
  docs/MAINTENANCE.md:191: | `tools/model_alias.py --apply` | `provider_config.json.bak-alias-<时间戳>` | 同上（`.tmp-alias` → `os.replace`） |
  docs/MAINTENANCE.md:192: | `tools/dsh_sync.py --apply`（通常由 `model_alias.py --apply` 自动调用） | `cordis.patch.yml.bak-dshsync-<时间戳>`、`.credentials.yaml.bak-dshsync-<时间戳>` | 只替换 DSH profile 的 `llm-pi-ai` 段；写临时文件后 `os.replace` |
  docs/MAINTENANCE.md:193: 
  ...
  docs/MAINTENANCE.md:214: 
  docs/MAINTENANCE.md:215: 回退后 **ZCode 约 1 秒内会热重载**回旧配置，不用重启。
  docs/MAINTENANCE.md:216: 
  ...
  docs/MAINTENANCE.md:225: 
  docs/MAINTENANCE.md:226: **ZCode 约 1 秒轮询 `provider_config.json`** —— 脚本写完一般不用重启客户端。
  docs/MAINTENANCE.md:227: 
  ...
  docs/MAINTENANCE.md:231: | 写完等 1~2 秒再看列表 | 轮询不是瞬时的 |
  docs/MAINTENANCE.md:232: | 仍不刷新就重启客户端 | 极少数情况下客户端没在轮询 |
  docs/MAINTENANCE.md:233: | 重启客户端**不影响**配置 | 配置在磁盘上，不在客户端里 |
  docs/MAINTENANCE.md:234: | `providerId` 不要随便改 | 旧会话可能引用它；改 `providerName`（显示名）才安全 |
  ...
  docs/MAINTENANCE.md:236: 
  docs/MAINTENANCE.md:237: **DeepSeekRuntime 同理**：`tools/dsh_sync.py --apply` 写的是 `~/.dsh/profiles/desktop/cordis.patch.yml`，DSH 会热加载，不需要重启；DSH 没运行也不影响写入，下次启动生效。它只替换 `llm-pi-ai` 段，保留其他 patch 条目和非 `zcode-*` provider。
  docs/MAINTENANCE.md:238: 
  ...
  docs/MAINTENANCE.md:244: |---|---|
  docs/MAINTENANCE.md:245: | **每天 12:00（定时任务 `automation-3e2f8a53-b408-4bf8-90ff-4a331a721f5c`）** | 五段顺序：① `python providers/opencode-go/ops/go_model_sync.py --apply`（体检对地区受限型号自动经机场复测，**不要**再用「403 就删」的旧口径判读）；② WorkBuddy（`workbuddy_fetch_pricing.py` → `workbuddy_probe_zcode.py --max-rate 0.3 --sleep 20` → `workbuddy_zcode_sync.py --max-rate 0.3 --apply`）；③ Qoder（`qoder_probe_zcode.py --timeout 90 --sleep 3` → `qoder_zcode_sync.py --probe-file providers/qoder/qoder_probe.json --apply`）；④ `python tools/model_alias.py --slot auto --apply` 归一化三组与 alias map，并自动调用 `tools/dsh_sync.py --apply` 把最终三组投影到本机 DeepSeekRuntime（使用默认 ZCode 配置路径时；DSH 未安装自动跳过；失败只告警不阻断；`--no-dsh` 可关闭），随后 `python tools/model_alias.py --check` 确认无漂移；⑤ `python tools/sync_report.py --write --push` 生成 `docs/reports/MODEL-SYNC-<时间>.md`（写明新增 / 移除 / 分组 / 链路变化）、更新报告索引并提交推送。手动补跑也按这个顺序；**不要在 ④ 之后单独跑旧 sync 的 `--apply`** |
  docs/MAINTENANCE.md:246: | **每天（可选，全量体检）** | `python tools/model_probe.py` → `python tools/model_alias.py --slot auto --probe-file ~/.zcode/v2/model_probe.json --apply`；定时任务不跑全量 probe，各 sync 自带定向探测。规则见 [MODEL-ALIAS.md](MODEL-ALIAS.md) §6 |
  docs/MAINTENANCE.md:247: | **每天 08:00 / 22:00 + 工作日 09:00 / 12:00 / 14:00 / 18:00** | `python providers/workbuddy/workbuddy_fetch_pricing.py` → `python tools/model_alias.py --slot auto --apply`（峰谷价切换，见 [MODEL-ALIAS.md](MODEL-ALIAS.md) §4.1；默认配置路径下也会自动同步 DSH） |
  docs/MAINTENANCE.md:248: | **每月** | 复核 [MODEL-PROVIDERS.md](MODEL-PROVIDERS.md) 里的价格 / 额度（`wb_pricing.json` 已由每日任务自动刷新） |
  ...
  docs/MAINTENANCE.md:275: 
  docs/MAINTENANCE.md:276: ## 8. 网关生命周期（zgate）
  docs/MAINTENANCE.md:277: 
  docs/MAINTENANCE.md:278: 2026-10-23 起，三个反代由**一个进程**托管：`gateways/zgate`（Go，约 19 MB）。
  docs/MAINTENANCE.md:279: 它监听 `127.0.0.1:7871`，按 alias map 把四个 chat provider 的请求分流到三条上游，
  ...
  docs/MAINTENANCE.md:284: | OpenCode-Go | 远程 | — | 直连，无本地进程 |
  docs/MAINTENANCE.md:285: | WorkBuddy（`wb2api`） | 7863 | zgate 的子进程 | `ondemand`：首个 WB 请求时拉起，空闲 300 秒回收 |
  docs/MAINTENANCE.md:286: | Qoder（`qoder_proxy.py`） | 8790 | zgate 的子进程 | `ondemand`：同上，随用随拉 |
  docs/MAINTENANCE.md:287: 
  docs/MAINTENANCE.md:288: 两个上游都**不常驻**：没人用就一个都不起，zgate 自己只占约 19 MB。
  docs/MAINTENANCE.md:289: 签到 / 保活这类定时任务靠 `children.*.windows` 兜底 —— 窗口内按 `always` 处理，
  ...
  docs/MAINTENANCE.md:296: 
  docs/MAINTENANCE.md:297: 策略与窗口写在 `gateways/zgate/zgate.json`，改完用 `zgate.exe reload` 热加载
  docs/MAINTENANCE.md:298: （新增子进程、监听地址、上游 base 仍要重启）。
  docs/MAINTENANCE.md:299: 子进程装在 **Job Object** 里，zgate 崩溃或被结束时会一起收掉，不会留下占着 7863 / 8790 的孤儿。
  docs/MAINTENANCE.md:300: 
  ...
  docs/MAINTENANCE.md:304: |---|---|
  docs/MAINTENANCE.md:305: | 看状态（服务是否在跑 / 子进程 / 端口 / 凭据有无） | `gateways/zgate/zgate.exe status` |
  docs/MAINTENANCE.md:306: | 前台启动（排错用；正常由登录自启拉起） | `gateways/zgate/zgate.exe serve` |
  docs/MAINTENANCE.md:307: | 注册登录自启 | `gateways/zgate/zgate.exe install` |
  docs/MAINTENANCE.md:308: | 移除登录自启 | `gateways/zgate/zgate.exe uninstall` |
  docs/MAINTENANCE.md:309: | 热加载策略/窗口（改完 `zgate.json`） | `gateways/zgate/zgate.exe reload` |
  docs/MAINTENANCE.md:310: | 健康检查 | `curl http://127.0.0.1:7871/health`（含每个子进程的 `state` / `pid` / `idle_s`） |
  docs/MAINTENANCE.md:311: | 只重启 WorkBuddy 上游 | `taskkill /IM wb2api.exe /F`，下一次 WB 请求自动拉起 |
  docs/MAINTENANCE.md:312: | 只重启 Qoder 上游 | `taskkill /IM python.exe /F` 后用下面的 bat 兜底，或重启 zgate |
  docs/MAINTENANCE.md:313: | 重新构建 zgate | `python gateways/zgate/build.py` |
  docs/MAINTENANCE.md:314: 
  docs/MAINTENANCE.md:315: 自启方式（**2026-11-09 起**）是**计划任务 `\ModelBus-zgate-hidden`**（AtLogOn，当前用户、Interactive、Limited，
  docs/MAINTENANCE.md:316: 无需管理员）：`wscript //B //Nologo %LOCALAPPDATA%\ZCodeGateway\launch-zgate.vbs` →
  docs/MAINTENANCE.md:317: `start-zgate-nw.ps1`（用 `CreateNoWindow` 拉起 `zgate.exe serve`；端口已占用则写 `port already up, skip`
  docs/MAINTENANCE.md:318: 直接退出；脚本跑完即退，**不留驻留进程**）。兜底看门狗 `\ModelBus-zgate-watchdog` 每 1 分钟
  docs/MAINTENANCE.md:319: → `ensure-zgate.vbs` → 同一个 `start-zgate-nw.ps1`。
  docs/MAINTENANCE.md:320: 
  docs/MAINTENANCE.md:321: 旧的启动文件夹快捷方式 `ModelBus zgate.lnk`、HKCU Run 的 `ZcodeAIModels-zgate-daemon`、以及
  docs/MAINTENANCE.md:322: 直接跑 exe 的旧任务 `\ModelBus-zgate` 都已移除（2026-11-09；备份与回滚：
  docs/MAINTENANCE.md:323: `%LOCALAPPDATA%\ZCodeGateway\autostart-backup-20261109\restore-autostart.ps1`，需管理员）。
  docs/MAINTENANCE.md:324: `zgate install` / `uninstall` 仍只管启动文件夹快捷方式，正常情况下不需要再跑——重跑会多出一条
  docs/MAINTENANCE.md:325: 自启路径并让第二实例在 `zgate.log` 里留下 `bind: Only one usage of each socket address` 噪音。
  docs/MAINTENANCE.md:326: 
  docs/MAINTENANCE.md:327: zgate 按 **GUI 子系统**编译（`-H windowsgui` 就是干这个的）：登录自启
  docs/MAINTENANCE.md:328: **零窗口、零乱码**，日志只落 `%LOCALAPPDATA%\ZCodeGateway\zgate.log`；在终端里跑
  docs/MAINTENANCE.md:329: `status` / `version` 时会把输出挂回当时的终端（管道与 `> 文件` 重定向不受影响）。
  ...
  docs/MAINTENANCE.md:332: 
  docs/MAINTENANCE.md:333: 所以**构建入口收口在 `gateways/zgate/build.py`**：它带 `-H windowsgui` 编译，
  docs/MAINTENANCE.md:334: 并**强制校验产物的 PE `Subsystem` 必须是 2（GUI）**，不合格直接非零退出。
  ...
  docs/MAINTENANCE.md:338: |---|---|---|
  docs/MAINTENANCE.md:339: | 构建（Windows） | `python gateways/zgate/build.py` | 编出 `gateways/zgate/zgate.exe` 并校验；exe 正被 zgate 占用时会提示先停进程 |
  docs/MAINTENANCE.md:340: | 只校验现有产物 | `python gateways/zgate/build.py --check` | 不编译，只读 PE 头；用于「现在到底是不是无窗版」 |
  docs/MAINTENANCE.md:341: | 交叉编译校验（CI） | `python gateways/zgate/build.py --cross-check` | 交叉编译一份 windows/amd64 到临时目录再校验；`-H windowsgui` 是 windows 链接器 flag，**在 Linux 上同样生效**，所以 CI 能真跑起来 |
  docs/MAINTENANCE.md:342: 
  docs/MAINTENANCE.md:343: > ⚠️ **别在 `gateways/zgate/` 目录里裸跑 `go build .`** —— 单包模式会把可执行文件
  docs/MAINTENANCE.md:344: > **原地覆盖**到当前目录，把无窗版换成控制台版，且产物在 `.gitignore` 里，
  ...
  docs/MAINTENANCE.md:348: 
  docs/MAINTENANCE.md:349: ### 8.2 配置项（`gateways/zgate/zgate.json`）
  docs/MAINTENANCE.md:350: 
  ...
  docs/MAINTENANCE.md:352: |---|---|---|
  docs/MAINTENANCE.md:353: | `listen` | `127.0.0.1:7871` | 四个 chat provider 的 `baseUrl` 指向这里；环境变量 `ZGATE_LISTEN` 可覆盖 |
  docs/MAINTENANCE.md:354: | `aliasMap` | `~/.zcode/v2/model-alias-map.json` | 显示名 → 上游；按 mtime 热加载，改完不用重启 |
  docs/MAINTENANCE.md:355: | `providerConfig` | `~/.zcode/v2/provider_config.json` | 凭据兜底来源 |
  ...
  docs/MAINTENANCE.md:363: 
  docs/MAINTENANCE.md:364: | 文件（`%LOCALAPPDATA%\ZCodeGateway\`） | 内容 |
  docs/MAINTENANCE.md:365: |---|---|
  docs/MAINTENANCE.md:366: | `zgate.log` | 路由日志（每个请求一行 `model=… -> 通道`）、子进程起停、错误；超过 5 MB 轮转为 `.1` |
  docs/MAINTENANCE.md:367: | `workbuddy.stdout.log` / `.stderr.log` | WorkBuddy 上游输出 |
  docs/MAINTENANCE.md:368: | `qoder.stdout.log` / `.stderr.log` | Qoder 上游输出（Qoder 自己还会写 `gateways/upstream/qoder/qoder-proxy.log`） |
  docs/MAINTENANCE.md:369: 
  ...
  docs/MAINTENANCE.md:375: |---|---|
  docs/MAINTENANCE.md:376: | 更新 WorkBuddy 上游 | `git -C gateways/upstream/workbuddy pull --ff-only`（当前分支 `misakano-base`，跟踪 `misakano/main`），再 `taskkill /IM wb2api.exe /F`（下次请求自动重启） |
  docs/MAINTENANCE.md:377: | 更新 Qoder 上游 | `git -C gateways/upstream/qoder pull --ff-only`，再重启 zgate |
  docs/MAINTENANCE.md:378: | 新机器重建 WorkBuddy | `git clone https://github.com/misakano7545/workbuddy2api-panel.git gateways/upstream/workbuddy`，按 `config.example.json` 建 `config.json`、放 `auths/`，`go build -o wb2api.exe ./cmd/server`（`go.mod` 要求 Go ≥ 1.26.10，`GOTOOLCHAIN=auto` 会自动拉工具链） |
  docs/MAINTENANCE.md:379: | WorkBuddy 上游血缘与回滚 | 链路 `Sliverkiss/workbuddy2api`（已删库）→ `linguo2625469/workbuddy2api-panel`（2026-10-21 停更，末版 `73a7560` 已打 tag `panel-final-73a7560`）→ `misakano7545/workbuddy2api-panel`（现跟踪）。回滚：`git checkout panel-final-73a7560`（detached HEAD）后重编；停更版二进制备份见 `.workbuddy/backup/`（不入库）。二进制回滚点口径（**2026-11-01 调整**）：`gateways/upstream/workbuddy/` 下只保留现役 `wb2api.exe` 与**最新一份** `wb2api.exe.bak-<时间戳>`，更早的备份已清理 |
  docs/MAINTENANCE.md:380: | 新机器重建 Qoder | 见 [QODER.md](QODER.md) §2 |
  ...
  docs/MAINTENANCE.md:390: 
  docs/MAINTENANCE.md:391: Qoder 由 zgate 托管（默认 `ondemand`，签到/保活窗口自动唤醒），
  docs/MAINTENANCE.md:392: `qoder:` 模型经 7871 分流；ZCode 侧没有独立 `qoder` provider。
  ...
  docs/MAINTENANCE.md:395: |---|---|
  docs/MAINTENANCE.md:396: | 看状态 | `gateways/zgate/zgate.exe status`，或 `curl http://127.0.0.1:8790/ping` |
  docs/MAINTENANCE.md:397: | 手动兜底启动（zgate 不在时） | `gateways/upstream/qoder/start-qoder-proxy.bat` |
  docs/MAINTENANCE.md:398: | 手动兜底停止 | `gateways/upstream/qoder/stop-qoder-proxy.bat` |
  docs/MAINTENANCE.md:399: | 日志 | `gateways/upstream/qoder/qoder-proxy.log`；zgate 侧见 §8.3 |
  docs/MAINTENANCE.md:400: | 签到状态 | `gateways/upstream/qoder/accounts/scheduler/state.json` |
  docs/MAINTENANCE.md:401: | 每日同步 | `python tools/model_probe.py`（可加 `--group 免费`）→ `python tools/model_alias.py --slot auto --probe-file ~/.zcode/v2/model_probe.json --apply`；Qoder 显示名为 `Q/积分/型号` |
  ...
  docs/MAINTENANCE.md:429: | 2026-10-23 | 统一模型命名：四组（主力/免费/低耗/高耗）、`渠道/积分/型号`、alias map、协议桥接 | 43 个模型 / 4 个 provider；37 ok，5 个 WB GB 因池冷却暂为瞬时限流 |
  docs/MAINTENANCE.md:430: | 2026-10-23 | 接入 Qoder：qoder2api-hub clone 到 `gateways/upstream/qoder`（8790）、OAuth 账号、独立 `qoder` provider、同步/探测脚本与文档 | 7 个模型探测 200；免费 `DeepSeek-Flash` 1.1s；`Qwen3.8-Flash` 因 10605 排队暂不收录 |
  docs/MAINTENANCE.md:431: | 2026-10-22 | 收尾大扫除：清 `__pycache__` 与过期定价备份；对齐模型计数 / 快照日期、Release 说明反馈入口、AGENTS 的 CodeGraph 状态 | 仓库 53109K → 53053K；`python tools/check-docs.py` 通过 |
```
### docs/MODEL-ALIAS.md
```text
  ...
  docs/MODEL-ALIAS.md:24: `Arrearage` / `AllocationQuota` / `FreeTierOnly`（额度耗尽）、以及 402，都会立即换
  docs/MODEL-ALIAS.md:25: 下一跳，并把该跳放进 **30 分钟冷却**（内存态，重启清零，`/health` 的 `cooling`
  docs/MODEL-ALIAS.md:26: 是当前数量）。没有这条，几十跳的集合体每轮都要先把死跳撞一遍。
  ...
  docs/MODEL-ALIAS.md:29: alias map **不含凭据**；上游 key 仍由路由按渠道从 `provider_config.json` /
  docs/MODEL-ALIAS.md:30: `gateways/upstream/workbuddy/config.json` / `providers/qoder/.env.local` 读取。
  docs/MODEL-ALIAS.md:31: 
  ...
  docs/MODEL-ALIAS.md:109: 
  docs/MODEL-ALIAS.md:110: 历史消耗（`gateways/upstream/workbuddy/data/usage.json` 聚合）：
  docs/MODEL-ALIAS.md:111: 
  ...
  docs/MODEL-ALIAS.md:231: 
  docs/MODEL-ALIAS.md:232: - zgate 把地区受限的 403 当「换出口」处理，不是「这一跳坏了」；冷却键 `hopKey`
  docs/MODEL-ALIAS.md:233:   里含 proxy，否则直连那跳的 403 会把机场跳一起冷却掉（= 兜底被吃掉）。
  ...
  docs/MODEL-ALIAS.md:236:   否则这一跳直接连不上（见 ShellcrashRules `docs/ARCHITECTURE.md` §2.2）。
  docs/MODEL-ALIAS.md:237: - **这个出口只对经过 zgate 的请求生效**。同步脚本（`go_model_sync.py`）自己发探测、
  docs/MODEL-ALIAS.md:238:   不经过路由器，所以它把同一个 `AIRPORT_PROXY` 用在「直连地区受限 → 复测」上，
  ...
  docs/MODEL-ALIAS.md:334: - **主力豁免价格上限**：贵备份 `Qwen-3.8-Max` 现价 0.17，其余超限模型一律不收录，
  docs/MODEL-ALIAS.md:335:   所以 `--max-price` 只对非主力生效。
  docs/MODEL-ALIAS.md:336: - **名单只管排序，不管建档**：条目只从 `provider_config` 的 `personalModelIds` 与池子
  ...
  docs/MODEL-ALIAS.md:340: - **榜单不再自动扩主力**：`arena_leaderboard.py` 仍能产候选，但
  docs/MODEL-ALIAS.md:341:   `model_alias.py` 默认忽略，要 `--arena` 才生效。
  docs/MODEL-ALIAS.md:342: - **顺序由人工名单决定，不按价格**：主力按 `MAIN_ORDER`、省钱按 `LOW_ORDER`
  ...
  docs/MODEL-ALIAS.md:405: 
  docs/MODEL-ALIAS.md:406: `gateways/zgate` 内置协议桥（原 `tools/protocol_bridge.js` 已退役），把 chat 请求转成：
  docs/MODEL-ALIAS.md:407: 
  ...
  docs/MODEL-ALIAS.md:486: - 别名表是本地活数据，不入库；`provider_config.json` 与备份同样不入库。
  docs/MODEL-ALIAS.md:487: - 榜单接口不可用时用本地缓存；缓存也没有就跳过扩充，人工 `MAIN_IDS` 仍生效。
  docs/MODEL-ALIAS.md:488: - 同名不同协议的条目靠 `-Msg` / `-Resp` 区分；免费条目默认不加后缀，只有与
```
### docs/MODEL-PROVIDERS.md
```text
  ...
  docs/MODEL-PROVIDERS.md:16: > 逐次变更见根 `CHANGELOG.md`；**现役三组与命名的唯一正本是 [MODEL-ALIAS.md](MODEL-ALIAS.md) §4**。
  docs/MODEL-PROVIDERS.md:17: 价格 / 额度 / 倍率随服务商变动，改之前先看 [MAINTENANCE.md](MAINTENANCE.md) §1。
  docs/MODEL-PROVIDERS.md:18: 
  ...
  docs/MODEL-PROVIDERS.md:44: |---|---|---|
  docs/MODEL-PROVIDERS.md:45: | 计价单位 | 美元 / M token（输入 / 输出单价） | 积分倍率（`credits` 牌价 / `promo_credits` 生效价） |
  docs/MODEL-PROVIDERS.md:46: | 「这个模型多耐用」 | 额度可撑输出 = 月额度 ÷ 输出单价 | 倍率越小越便宜 |
  ...
  docs/MODEL-PROVIDERS.md:56: 第四个实例（千问）只有 **Anthropic Messages** 端点、没有 `/v1/models`，所以目录靠
  docs/MODEL-PROVIDERS.md:57: 控制台导出、协议靠 zgate 桥；它是 `QW` 渠道，模型 id 加 `qwen:` 前缀，见 §4.10。
  docs/MODEL-PROVIDERS.md:58: 它的价不是「越便宜越好」而是**限时 0 积分**（试用额度，2026-12-15 到期）。
  ...
  docs/MODEL-PROVIDERS.md:82: 
  docs/MODEL-PROVIDERS.md:83: **ZCode 约 1 秒轮询该配置**，写完一般不用重启客户端；但**不要在 ZCode 的 provider
  docs/MODEL-PROVIDERS.md:84: 设置界面里同时改** —— 界面保存时会整份写回，把脚本写的覆盖掉
  ...
  docs/MODEL-PROVIDERS.md:126: > **2026-10-21 起为统一模式**：五个 chat provider 的 `api.baseUrl` 指向
  docs/MODEL-PROVIDERS.md:127: > `gateways/zgate`（`http://127.0.0.1:7871/v1`），模型列表同时包含
  docs/MODEL-PROVIDERS.md:128: > OpenCode-Go 与 WorkBuddy；路由按 model 前缀分流。`对话` / `响应` 仍直连 OpenCode。
  ...
  docs/MODEL-PROVIDERS.md:170: | mimo-v2.5 | 仅 chat | ✅ 已实测 | 待补 | 0.14 / 0.28 | $60 | **214M** | 同上，稍快 |
  docs/MODEL-PROVIDERS.md:171: | hy3 | 仅 chat | ✅ 已实测 | 待补 | 0.14 / 0.58 | $60 | 103M | 慢，后台任务 |
  docs/MODEL-PROVIDERS.md:172: 
  ...
  docs/MODEL-PROVIDERS.md:255: 
  docs/MODEL-PROVIDERS.md:256: 网关：`wb2api` 面板版（MIT），默认 `http://127.0.0.1:7863`，OpenAI 兼容。
  docs/MODEL-PROVIDERS.md:257: 把腾讯 CodeBuddy 账号池变成 OpenAI 兼容 API。模型 id 形如 `cn:xxx` / `global:xxx`。
  ...
  docs/MODEL-PROVIDERS.md:260: > 保留 `.gitignore` 与 `main.go` 不打印 api_key 两处本地补丁；`go test ./...` 通过后重编并替换
  docs/MODEL-PROVIDERS.md:261: > `wb2api.exe`。面板目录回到 20 条，新增 `cn:hy4free`（0 分，显示名 `HY4-Free`，进免费组）与
  docs/MODEL-PROVIDERS.md:262: > `cn:hy4std`（0.29，未收录）；旧表 17 个仍可调型号经探活保留。下文 §4.0/§4.2 的五组分档表是
  ...
  docs/MODEL-PROVIDERS.md:264: 
  docs/MODEL-PROVIDERS.md:265: 网关生命周期由 `gateways/zgate` 托管（WB 按需拉起、空闲回收；Qoder 常驻），
  docs/MODEL-PROVIDERS.md:266: 全部退出 → 停），安装与副作用见 [MAINTENANCE.md](MAINTENANCE.md) §8。
  ...
  docs/MODEL-PROVIDERS.md:270: 默认**不再创建** `workbuddy-*` 四个 provider。18 个 WorkBuddy 模型并入 §2 的五个
  docs/MODEL-PROVIDERS.md:271: chat 组，四个 chat 组（历史口径）的 `api.baseUrl` 指向本地入口 `gateways/zgate`
  docs/MODEL-PROVIDERS.md:272: （`http://127.0.0.1:7871/v1`）。路由按 model 分流：
  ...
  docs/MODEL-PROVIDERS.md:285: - `对话` / `响应` 仍直连 OpenCode-Go，不经过路由。
  docs/MODEL-PROVIDERS.md:286: - 入口由 `gateways/zgate` 常驻（登录自启）；手动启动
  docs/MODEL-PROVIDERS.md:287:   `gateways/zgate/zgate.exe serve`，健康检查 `GET http://127.0.0.1:7871/health`。
  docs/MODEL-PROVIDERS.md:288: - **分离模式**：`workbuddy_zcode_sync.py --separate --apply` 会重建 §4.2 的四个
  ...
  docs/MODEL-PROVIDERS.md:292: 
  docs/MODEL-PROVIDERS.md:293: - `/panel/api/models` 与 `/v1/models` 同源。**注意**：网关未重启时 `/panel/api/models`
  docs/MODEL-PROVIDERS.md:294:   只返回 34 个 global 模型，重启后返回全部 56 个（cn 22 + global 34）。
  docs/MODEL-PROVIDERS.md:295: - **路由别名**（无自身价格，只是路由到别的模型）—— 一律排除：
  ...
  docs/MODEL-PROVIDERS.md:303: 
  docs/MODEL-PROVIDERS.md:304: `credits` = 牌价，`promo_credits` = 生效价（取 `promo_credits` 优先）。
  docs/MODEL-PROVIDERS.md:305: **倍率越小越便宜**。
  ...
  docs/MODEL-PROVIDERS.md:309: | `workbuddy-low` | 低代 | 0 < 倍率 ≤ 0.16（主力价位） | 8 |
  docs/MODEL-PROVIDERS.md:310: | `workbuddy-free` | 免代 | 生效价 = 0.00 | 5 |
  docs/MODEL-PROVIDERS.md:311: | `workbuddy-high` | 高代 | 0.16 < 倍率 ≤ 0.30 | 3 |
  ...
  docs/MODEL-PROVIDERS.md:342: 
  docs/MODEL-PROVIDERS.md:343: > **2026-10-21 促销漂移已并入分档**：`cn:hy4-preview` 生效价回到 `x0.29` →
  docs/MODEL-PROVIDERS.md:344: > 从免代移到高代（统一模式下它在 `opencode-go-chat-slow`）；
  ...
  docs/MODEL-PROVIDERS.md:346: 
  docs/MODEL-PROVIDERS.md:347: ### 4.3 免代 `workbuddy-free`（分离模式，生效倍率 0.00）
  docs/MODEL-PROVIDERS.md:348: 
  ...
  docs/MODEL-PROVIDERS.md:481: （`/v1/messages`），`x-api-key` + `anthropic-version: 2023-06-01`；`/v1/models` 与
  docs/MODEL-PROVIDERS.md:482: OpenAI 兼容路径都是 404。所以它走 zgate 的协议桥，模型 id 加 `qwen:` 前缀并入免费组。
  docs/MODEL-PROVIDERS.md:483: 完整操作与筛选过程见 [QWEN.md](QWEN.md)。
  ...
  docs/MODEL-PROVIDERS.md:507: |---|---|
  docs/MODEL-PROVIDERS.md:508: | 渠道 | `CP`，zgate 按需拉起（`policy: ondemand`），空闲回收 |
  docs/MODEL-PROVIDERS.md:509: | 凭证 | AI Studio **API key**（`api-keys.gemini`），请求头 `x-goog-api-key` |
  ...
  docs/MODEL-PROVIDERS.md:519: 
  docs/MODEL-PROVIDERS.md:520: 1. `zgate.json` 里 child 的 `exe`/`cwd` 相对路径以 `gateways/zgate` 为基准，
  docs/MODEL-PROVIDERS.md:521:    写成 `../third-party/...` 会解析成 `gateways/third-party/...`，报
  docs/MODEL-PROVIDERS.md:522:    `fork/exec ...: The directory name is invalid`。必须是 `../../third-party/...`。
  ...
  docs/MODEL-PROVIDERS.md:634: | 有档位但**不发**（装饰项） | `Kimi-K3`、`Conatus`、`Claude-Haiku-5.5`、`Muse-Spark1.3`、`GPT-6-Luna` | 5 个：七牛是 Anthropic 桥、后两个是 messages/responses 协议，都只能 `map="{}"` |
  docs/MODEL-PROVIDERS.md:635: | 只有开关且开关生效 | `Iceman`、`MiMo-2.6-Flash`、`MiMo-2.6-Pro` | 上游目录没有档位声明（`cn:mimo-v2.6-pro` 的 `supported_efforts` 为空） |
  docs/MODEL-PROVIDERS.md:636: 
  ...
  docs/MODEL-PROVIDERS.md:669: | 中文任务 | `qwen3.8-flash` |
  docs/MODEL-PROVIDERS.md:670: | 后台批量 | `hy3`、`longcat-2.0`，夜里用 `longcat-2.5-preview-free` |
  docs/MODEL-PROVIDERS.md:671: | 别用于交互 | `longcat-2.0`、`longcat-2.5-preview-free`、`qwen3.7-plus` |
```
### docs/MODEL-QUICK-REF.md
```text
  ...
  docs/MODEL-QUICK-REF.md:36: | mimo-v2.5 | 0.14 / 0.28 | $60 | **214M** | 2.1–3.3s | 同上，稍快一点 |
  docs/MODEL-QUICK-REF.md:37: | hy3 | 0.14 / 0.58 | $60 | 103M | 3–7.3s | 慢；后台任务 |
  docs/MODEL-QUICK-REF.md:38: 
  ...
  docs/MODEL-QUICK-REF.md:86: - **中文任务** → `qwen3.8-flash`
  docs/MODEL-QUICK-REF.md:87: - **后台批量** → `hy3`、`longcat-2.0`，夜里用 `longcat-2.5-preview-free`
  docs/MODEL-QUICK-REF.md:88: - **别用于交互** → `longcat-2.0`、`longcat-2.5-preview-free`、`qwen3.7-plus`
```
### docs/PITFALLS.md
```text
  ...
  docs/PITFALLS.md:109: 
  docs/PITFALLS.md:110: `optionSpecs.reasoningLevel.map` 也是同一个语义：**最后一条命中的规则**的 map 生效。
  docs/PITFALLS.md:111: 
  ...
  docs/PITFALLS.md:199: 
  docs/PITFALLS.md:200: - 脚本从**环境变量**读凭据（`WB_GATEWAY_KEY` / `WB_GATEWAY_BASE` /
  docs/PITFALLS.md:201:   `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` / `ZCODE_BUILTIN` / `OPENCODE_SESSION`），
  ...
  docs/PITFALLS.md:262: 
  docs/PITFALLS.md:263: **解法**：本仓用 `gateways/zgate` 做本地入口 —— 四个 chat provider 指向
  docs/PITFALLS.md:264: `http://127.0.0.1:7871/v1`，路由按 model 前缀把 `cn:` / `global:` 转到 WorkBuddy 网关，
  ...
  docs/PITFALLS.md:277: 
  docs/PITFALLS.md:278: ## 14. `gateways/upstream/workbuddy/` 是上游独立 clone，改动只在本地
  docs/PITFALLS.md:279: 
  ...
  docs/PITFALLS.md:282: 
  docs/PITFALLS.md:283: **机制**：主仓 `.gitignore` 用 `/gateways/upstream/workbuddy/` **整目录**排除 —— 里面是
  docs/PITFALLS.md:284: `auths/` 账号凭据、`config.json`（api_key）、`data/` 运行时状态与 `wb2api.exe`。
  docs/PITFALLS.md:285: 更新方式是 `git -C gateways/upstream/workbuddy pull --ff-only`，不是本仓管理。
  docs/PITFALLS.md:286: 
  ...
  docs/PITFALLS.md:291: 
  docs/PITFALLS.md:292: **现象**：网关首次启动时把自动生成的 `api_key` 明文打进 stdout；守护器把 stdout
  docs/PITFALLS.md:293: 落到 `logs/gateway.stdout.log`，等于凭据明文落盘。示例配置里的 `api_key` 是
  docs/PITFALLS.md:294: `test_key`，而 README 的部署步骤要求 `cp` 这份文件。
  ...
  docs/PITFALLS.md:348: 
  docs/PITFALLS.md:349: ## 20. 裸 `go build` 会把无窗 zgate 覆盖成控制台程序 【通用】
  docs/PITFALLS.md:350: 
  docs/PITFALLS.md:351: - **现象**：开机自启时弹出一个 cmd 控制台窗口，标题是快捷方式名
  docs/PITFALLS.md:352:   （「ModelBus zgate」）；关掉那个窗口等于杀掉网关，模型全挂。
  docs/PITFALLS.md:353:   有时窗口是「可见的」而不是最小化 —— 快捷方式里 `WindowStyle = 7`
  docs/PITFALLS.md:354:   只对**有窗口**的程序生效，对控制台子系统程序不等于隐藏。
  docs/PITFALLS.md:355: - **根因**：Windows PE 头里的 `Subsystem` 字段决定程序启动时要不要分配控制台。
  ...
  docs/PITFALLS.md:357:   - `3` = `CONSOLE` → 一启动就分配一个真控制台窗口
  docs/PITFALLS.md:358:   `-H windowsgui` 是**链接期** flag，只在那一次编译里生效。事后从源码看不出来，
  docs/PITFALLS.md:359:   只能读产物的 PE 头。
  docs/PITFALLS.md:360: - **回退是怎么发生的**：`go build` 在**单包**模式下会把可执行文件写到当前目录，
  docs/PITFALLS.md:361:   所以在 `gateways/zgate/` 里跑一次裸 `go build .`，就把之前用
  docs/PITFALLS.md:362:   `-ldflags "-H windowsgui"` 编好的无窗版**原地覆盖**成控制台版。
  docs/PITFALLS.md:363:   （`go build ./...` 是多包模式，Go 只编译不落盘，**不会**覆盖 —— 实测确认。）
  docs/PITFALLS.md:364:   产物在 `.gitignore` 里（`/gateways/zgate/*.exe`），所以 `git checkout` 救不回来。
  docs/PITFALLS.md:365: - **为什么难发现**：覆盖发生在**编译期**，弹窗发生在**下次开机**，
  docs/PITFALLS.md:366:   中间隔着一次重启；日志、git 历史、进程列表都看不出因果。
  docs/PITFALLS.md:367: - **解法**：编译入口收口到 `gateways/zgate/build.py`（带 flag + 强制校验 PE 子系统）；
  docs/PITFALLS.md:368:   检查用 `go vet ./...`，别在 `gateways/zgate/` 里裸跑 `go build`。
  docs/PITFALLS.md:369: - **验证**：`python gateways/zgate/build.py --check` 打印
  docs/PITFALLS.md:370:   `Subsystem = 2 → WINDOWS_GUI（无窗）`；`--cross-check` 会在临时目录交叉编译一份
  docs/PITFALLS.md:371:   windows/amd64 再校验，CI 用这条（Linux 上也能真跑起来）。
  docs/PITFALLS.md:372: - **2026-11-09 补充（Win11 终端接管）**：计划任务 / 快捷方式拉起**控制台子系统**程序时，
  docs/PITFALLS.md:373:   Windows 11 的默认终端会让 `WindowsTerminal.exe`（父进程是 `svchost.exe` 的 Task Scheduler）
  docs/PITFALLS.md:374:   接管它的 console 并显示成可见窗口，标题就是 exe 路径 —— 该 `wt` 进程的 `MainWindowHandle`
  docs/PITFALLS.md:375:   非 0，而 zgate 自身 `MainWindowHandle` 是 0，很容易误判成"窗口是 zgate 弹的"。
  docs/PITFALLS.md:376:   可靠的判断方式是对着 `wt` / `OpenConsole` 进程数做前后对照，而不是看标题。
  ...
  docs/PITFALLS.md:378:   `CreateNoWindow`（`ProcessStartInfo` + `UseShellExecute=$false`）包一层，
  docs/PITFALLS.md:379:   别让 Task Scheduler 直接 exec 控制台程序。现行自启见 `docs/MAINTENANCE.md` §8.1。
  docs/PITFALLS.md:380: 
  ...
  docs/PITFALLS.md:382: 
  docs/PITFALLS.md:383: - **现象**：机器人调用 `opencode.ai` 偶发 502，单次回复 22–32s；zgate 日志里
  docs/PITFALLS.md:384:   `Post "https://opencode.ai/zen/go/v1/chat/completions": net/http: TLS handshake timeout`。
  docs/PITFALLS.md:385: - **根因**：本机到 `opencode.ai` 走 fake-IP 透明代理，链路握手会抖（同一节点实测成功
  docs/PITFALLS.md:386:   0.32s，坏窗口 0.6–7.7s，再往上就不返回了）。transport 的 `TLSHandshakeTimeout`
  docs/PITFALLS.md:387:   是 15s，且 `http.Client` 没有整体 `Timeout` —— 一次坏叫要等满 15s 才回落，
  docs/PITFALLS.md:388:   叠上 WorkBuddy 免费池的 429/503 再排队，回复就拖到 20 秒以上。
  docs/PITFALLS.md:389: - **解法**：`TLSHandshakeTimeout` 收到 8s。**不要**顺手给 `http.Client` 设 `Timeout`：
  docs/PITFALLS.md:390:   它覆盖整个响应体，流式（SSE）会被从中间截断，非流式的长推理也会被误杀。
  docs/PITFALLS.md:391: - **验证**：`grep TLSHandshakeTimeout gateways/zgate/main.go` 应为 8s；
  docs/PITFALLS.md:392:   坏窗口内单次失败的上限约为 8s，而不是 15s。
  docs/PITFALLS.md:393: 
  docs/PITFALLS.md:394: ## 22. 派生数据落盘又回读 → 上游改价永久不生效 【通用】
  docs/PITFALLS.md:395: 
  ...
  docs/PITFALLS.md:443:      （`qwen-max` 才有）；`Model not exist.` 是唯一的判据。
  docs/PITFALLS.md:444:   2. `zgate` 的协议桥把地址拼成 `TrimRight(base,"/") + "/messages"`，
  docs/PITFALLS.md:445:      **不会**自己补 `/v1`。基址写成 `.../apps/anthropic` 就打到
  ...
  docs/PITFALLS.md:520: 
  docs/PITFALLS.md:521: ## 28. zgate 停掉后忘了拉起来 = 全站模型不可用；启动必须带 `serve` 【通用】
  docs/PITFALLS.md:522: 
  docs/PITFALLS.md:523: - **现象**：为了让新二进制生效 `taskkill` 掉 zgate，之后用
  docs/PITFALLS.md:524:   `start "" zgate.exe` 启动，进程立刻消失，`/health` 不通，ZCode 里所有模型
  docs/PITFALLS.md:525:   一起报错。直接前台跑，报 `panic: slice bounds out of range [2:1]`
  docs/PITFALLS.md:526:   （`main.loadConfig` 里的 `os.Args[2:]`）。
  docs/PITFALLS.md:527: - **根因**：zgate 没有默认子命令，`usage()` 要求显式 `serve`；`os.Args[2:]`
  docs/PITFALLS.md:528:   在只有 1 个参数时越界。另外 `zgate.exe` 是 GUI 子系统，用 `start` 时的参数
  docs/PITFALLS.md:529:   传递方式容易被 shell 吞掉。
  docs/PITFALLS.md:530: - **解法**：停旧进程 → `python gateways/zgate/build.py` 重新构建（会校验 PE
  docs/PITFALLS.md:531:   子系统是 WINDOWS_GUI）→ 用显式参数列表启动：
  ...
  docs/PITFALLS.md:533:   ```powershell
  docs/PITFALLS.md:534:   Start-Process -FilePath '<工作区>\ModelBus\gateways\zgate\zgate.exe' `
  docs/PITFALLS.md:535:     -ArgumentList 'serve' `
  docs/PITFALLS.md:536:     -WorkingDirectory '<工作区>\ModelBus\gateways\zgate' -WindowStyle Hidden
  docs/PITFALLS.md:537:   ```
  ...
  docs/PITFALLS.md:540:   `curl http://127.0.0.1:7871/health` 返回 `"ok":true`。
  docs/PITFALLS.md:541: - **教训**：**这是单点故障**。重启网关属于「会切断用户所有模型」的操作，
  docs/PITFALLS.md:542:   停机窗口要压到最短，重建失败就立刻回退旧二进制，不能停着慢慢查。
  docs/PITFALLS.md:543: 
  ...
  docs/PITFALLS.md:607:   `unsupported_country_region_territory`，链上明明排了「同上游、经机场」的第二跳，
  docs/PITFALLS.md:608:   zgate 却把 403 原样返回给客户端；`beam-free` 拿 `RegionError` 时同理。
  docs/PITFALLS.md:609: - **根因**：两处判定都只顾了「跳坏了」的情况 ——
  ...
  docs/PITFALLS.md:628: - **现象**：2026-10-31 01:14 起浏览器里调 `Beam` 连续 502（它只有一跳机场兜底），
  docs/PITFALLS.md:629:   zgate 日志 `Post "https://opencode.ai/zen/go/v1/chat/completions": EOF`。
  docs/PITFALLS.md:630:   同期 `robots.txt`（GET）一直 200，`/proxies/<组>/delay` 也全绿。
  ...
  docs/PITFALLS.md:641:      已经吐了半截 chunk 再重试会重复输出。
  docs/PITFALLS.md:642:   3. 只对 `EOF / TLS handshake timeout / connection reset / i/o timeout /
  docs/PITFALLS.md:643:      broken pipe / connection refused` 这类「请求大概率没被受理」的错误重试；
  ...
  docs/PITFALLS.md:656:   而体检是脚本**自己**用 `urllib` 直接打 `https://opencode.ai/zen/go/v1`，
  docs/PITFALLS.md:657:   根本不经过 zgate，自然拿不到那第二条出口 → 直连 403 → `stale_reason` 判「跑不通即清」。
  docs/PITFALLS.md:658:   换句话说：**出口策略只修在路由器一侧，任何自建请求的脚本都得各修一遍**。
  docs/PITFALLS.md:659: - **解法**：
  docs/PITFALLS.md:660:   1. 探测遇到地区标记（与 zgate `regionBlocked` 同一套字符串：`unsupported_country_region_territory` /
  docs/PITFALLS.md:661:      `RegionError` / `not available in your country` / `region, or territory not supported`）时，
  ...
  docs/PITFALLS.md:673:   - 端到端：`curl 127.0.0.1:7871/v1/chat/completions -d '{"model":"Beam",...}'` 返回 200，
  docs/PITFALLS.md:674:     zgate 日志 `(1/2)` 直连 403 → `(2/2)` 机场 200。
  docs/PITFALLS.md:675:   - 反证：直连复测仍是 403，说明不是网络抖动而是出口问题。
  ...
  docs/PITFALLS.md:702:   零命中 —— 结果文件从来没被生成过。
  docs/PITFALLS.md:703: - **三个坑叠在一起，只修一个都不生效**：
  docs/PITFALLS.md:704:   1. **没人跑**：每日同步从第四步直接跳到 `model_alias.py`，没有探活这一步，
  ...
  docs/PITFALLS.md:732: 
  docs/PITFALLS.md:733: ## 39. DSH 的 edit 工具会剥掉 UTF-8 BOM：改了带 BOM 的 .ps1 就变乱码 【通用】
  docs/PITFALLS.md:734: 
  ...
  docs/PITFALLS.md:738:   `Parser::ParseFile` 报一串 `Unexpected token '涓诲姏'` / `The string is missing
  docs/PITFALLS.md:739:   the terminator`。计划任务里跑会直接把脚本跑挂。
  docs/PITFALLS.md:740: - **解法**：每次用 edit 类工具改带 BOM 的文件，改完补一行：
```
### docs/QINIU.md
```text
  ...
  docs/QINIU.md:2: 
  docs/QINIU.md:3: > **一句话**：七牛云的 AI 推理网关只提供 Anthropic Messages 端点，经 `zgate` 的
  docs/QINIU.md:4: > `QN` 渠道 + 协议桥接入；目前收了 2 个**限时免费到 2026-11-30** 的模型
```
### docs/QODER.md
```text
  ...
  docs/QODER.md:29: 上游项目：[shuishuipingan/qoder2api-hub](https://github.com/shuishuipingan/qoder2api-hub)
  docs/QODER.md:30: （MIT，Python 3.9+，零第三方依赖）。本机 clone 在 `gateways/upstream/qoder/`，整目录被
  docs/QODER.md:31: `.gitignore` 排除（与 `gateways/upstream/workbuddy/` 同一模式）。
  docs/QODER.md:32: 
  ...
  docs/QODER.md:40: | 看板 | `http://127.0.0.1:8790/` |
  docs/QODER.md:41: | 面板密码 | 存在 `gateways/upstream/qoder/accounts/settings.json`（PBKDF2 摘要） |
  docs/QODER.md:42: | API Key | 存在同一份 `settings.json`；合并模式下由 7871 路由从 `providers/qoder/.env.local` 的 `QD_API_KEY` 读 |
  docs/QODER.md:43: | 账号 | `gateways/upstream/qoder/accounts/*.json`（含 token，绝不入库） |
  docs/QODER.md:44: | 用量 | `gateways/upstream/qoder/usage/` |
  docs/QODER.md:45: | 日志 | `gateways/upstream/qoder/qoder-proxy.log` / `qoder-proxy.err.log` |
  docs/QODER.md:46: | 启动 | `gateways/upstream/qoder/start-qoder-proxy.bat`（detached，关窗口不退出） |
  docs/QODER.md:47: | 停止 | `gateways/upstream/qoder/stop-qoder-proxy.bat`（按 PID，只停 `qoder_proxy.py`） |
  docs/QODER.md:48: | 健康 | `GET http://127.0.0.1:8790/ping`、`GET /health` |
  ...
  docs/QODER.md:50: API Key 与面板密码已持久化到 `accounts/settings.json`，所以 `.bat` 不需要
  docs/QODER.md:51: 额外参数即可用同一把 Key 重启。`providers/qoder/.env.local` 只给同步/探测脚本读，
  docs/QODER.md:52: 也在 `.gitignore` 里。
  docs/QODER.md:53: 
  docs/QODER.md:54: Qoder 现在由 `gateways/zgate` 以 `always` 策略托管（见 [MAINTENANCE.md](MAINTENANCE.md) §8.5）：它是常驻进程，
  docs/QODER.md:55: 不随 ZCode 起停。这样 09:00 / 21:00 的签到在 ZCode 没开时也会跑；如果以后
  docs/QODER.md:56: 要改成按需回收，把 `zgate.json` 的 `children.qoder.policy` 改成 `ondemand` 即可（会漏签到窗口）。
  docs/QODER.md:57: 
  ...
  docs/QODER.md:69: - 签到排程默认 **09:00 / 21:00**，Token 保活 **22:00**，状态在
  docs/QODER.md:70:   `gateways/upstream/qoder/accounts/scheduler/state.json`。
  docs/QODER.md:71: - 签到所需的 UMID 组件已用 `python _install_umid.py` 提取到
  docs/QODER.md:72:   `gateways/upstream/qoder/umid/`（`runtime-info.exe` + `sgsdk.dll`）。2026-10-23 16:56
  docs/QODER.md:73:   的启动巡检已成功领取 **+100 Credits**，余额 399。
  ...
  docs/QODER.md:166:   覆盖脚本结果；机制见 [PITFALLS.md](PITFALLS.md) §8）。
  docs/QODER.md:167: - ZCode 约 1 秒热加载 `provider_config.json`，写完用 `ListModels` 或模型选择器
  docs/QODER.md:168:   确认即可，不需要重启。
  docs/QODER.md:169: 
  ...
  docs/QODER.md:172: ```bash
  docs/QODER.md:173: git -C gateways/upstream/qoder pull --ff-only
  docs/QODER.md:174: # 然后 stop-qoder-proxy.bat → start-qoder-proxy.bat
  ...
  docs/QODER.md:192:   常驻、router 随 ZCode 起停（见 [MAINTENANCE.md](MAINTENANCE.md) §8.1）。
  docs/QODER.md:193: - 本仓不把 `gateways/upstream/qoder/`、`providers/qoder/.env.local`、`providers/qoder/qoder_probe.json`、
  docs/QODER.md:194:   `accounts/` 下的任何文件入库。
```
### docs/QWEN.md
```text
  ...
  docs/QWEN.md:2: 
  docs/QWEN.md:3: > **一句话**：千问平台是**只提供 Anthropic Messages 协议**的直连上游，经 `zgate`
  docs/QWEN.md:4: > 协议桥接入免费组；免费额度是「每模型 1M tokens、2026-12-15 到期、用完即停」的试用池，
  ...
  docs/QWEN.md:17: | 网关 | `https://maas.qianwenaiapi.com/apps/anthropic`（**只有 Messages**） |
  docs/QWEN.md:18: | zgate 渠道 | `QW`（远程，无本地进程） |
  docs/QWEN.md:19: | 协议 | `anthropic-messages` → 由 zgate 协议桥把 chat 请求转成 Messages |
  docs/QWEN.md:20: | 凭据 | `QWEN_API_KEY`（`providers/qwen/.env.local`，gitignored） |
  ...
  docs/QWEN.md:70: 
  docs/QWEN.md:71: 注意：控制器比服务端宽 —— 控制台**列出**的模型不等于 API **能调**（§4.4 的三个反例）。
  docs/QWEN.md:72: 
  ...
  docs/QWEN.md:184: 
  docs/QWEN.md:185: - `zgate` 把 **400 带 `Model not exist` / `model_unavailable` / `Arrearage` /
  docs/QWEN.md:186:   `AllocationQuota` / `FreeTierOnly`** 和 **402** 判为「这跳作废」，立刻换下一跳；
  ...
  docs/QWEN.md:188:   `/health` 的 `cooling` 字段是当前冷却中的跳数。
  docs/QWEN.md:189: - 冷却只在内存里：**重启 zgate 会清零**，重启后第一轮请求会重新撞一遍死跳。
  docs/QWEN.md:190: - 冷却表与额度窗口无联动 —— 30 分钟后会再试一次，如果还是没额度就再冷却 30 分钟。
  ...
  docs/QWEN.md:239: |---|---|
  docs/QWEN.md:240: | `gateways/zgate/zgate.json` | `upstreams.QW` + `qwenEnvFile` |
  docs/QWEN.md:241: | `internal/config/config.go` | `QwenEnvFile` 字段与默认值、`Upstreams["QW"]` 兜底 |
  ...
  docs/QWEN.md:284: 
  docs/QWEN.md:285: `gateways/zgate` 的桥用**非流式**请求上游，再把整段结果合成 chat SSE。所以：
  docs/QWEN.md:286: 
  ...
  docs/QWEN.md:342: `providers/qwen/.env.local` 是唯一持久落点，`.gitignore` 已排除；
  docs/QWEN.md:343: `zgate` 只报「key 是否存在」，不返回值。轮换 key 后重启 zgate 即可。
  docs/QWEN.md:344: 
```
### docs/README.md
```text
  ...
  docs/README.md:26: | [DOC-RULES.md](DOC-RULES.md) | **文档规则正本**：文件命名（全大写连字符）、分类定位、单一正本映射表、链接纪律、变更触发矩阵、体量预算 |
  docs/README.md:27: | [ARCHITECTURE.md](ARCHITECTURE.md) | **运行架构整合方案（已落地 2026-10-23）**：四个常驻进程 293 MB 的实测拆解、`zgate` 单入口 + 按需子进程方案、`gateways/` 与 `providers/` 两轴目录重构、分阶段验收与回退 |
  docs/README.md:28: | [MAINTENANCE.md](MAINTENANCE.md) | 日常维护：刷价格表、探测限速、快照保留、`--apply` 备份与回退、热重载注意事项 |
```
### docs/SECRETS.md
```text
  ...
  docs/SECRETS.md:19: - **`providers/workbuddy/cache/` 与 `providers/workbuddy/logs/` 是活数据缓存**（含账号池探测结果），随机器走，不随仓库走；
  docs/SECRETS.md:20: - **`gateways/upstream/qoder/accounts/` 是 Qoder 的 OAuth token 与面板/Key 设置**，随机器走，不随仓库走。
  docs/SECRETS.md:21: 
  ...
  docs/SECRETS.md:30: | **OpenCode-Go API key**（`oc_sk_…`） | ZCode 的 `provider_config.json` 里的 `apiKey` 字段；也可从 OpenCode 控制台重新签发 | 5 个探测脚本从环境变量 **`OPENCODE_GO_KEY`** 读；**未设置时明确报错退出**，不会带着空 key 去请求 | **不入库**。轮换后重新 `export` |
  docs/SECRETS.md:31: | **WorkBuddy 网关 key** | 本机 `wb2api` 网关自己的 `api_key`（网关面板 / 配置里） | 2 个 WorkBuddy 脚本从环境变量 **`WB_GATEWAY_KEY`** 读 | **不入库**。网关换账号池时一并轮换 |
  docs/SECRETS.md:32: | **统一路由的上游 key** | 不新增凭据文件：OpenCode key 从 `provider_config.json` / `OPENCODE_GO_KEY` 读，WorkBuddy key 从 `gateways/upstream/workbuddy/config.json` / `WB_GATEWAY_KEY` 读 | `gateways/zgate` 启动时读取；只监听 `127.0.0.1`；`/health` 只返回 key 是否存在，不返回值 | **不入库**。轮换上游 key 后重启路由 |
  docs/SECRETS.md:33: | **网关账号池凭据**（`auths/`，4 个号） | 本机 `gateways/upstream/workbuddy/auths/`（上游 clone 的运行目录）；`config.json` 里还有网关自己的 `api_key` | 整个 `gateways/upstream/workbuddy/` 被 `.gitignore` 排除；仓库里只出现 `WB_GATEWAY_KEY` 这个变量名 | **不入库**。换账号池时整目录一起换 |
  docs/SECRETS.md:34: | **Qoder API key**（`qd-…`） | qoder2api-hub 的 `gateways/upstream/qoder/accounts/settings.json`；本地脚本与 7871 路由从 `providers/qoder/.env.local` 的 `QD_API_KEY` 读 | `providers/qoder/qoder_zcode_sync.py` / `qoder_probe_zcode.py` 只从环境变量或本地 `.env.local` 读；合并模式**不**把 key 写进 provider_config（separate 模式才写） | **不入库**。轮换后同步改 `settings.json` 与 `.env.local` |
  docs/SECRETS.md:35: | **Qoder 面板密码** | `gateways/upstream/qoder/accounts/settings.json` 的 PBKDF2 摘要；初始值来自 `providers/qoder/.env.local` 的 `QD_PANEL_PASSWORD` | 本仓不出现值；`.env.local` 与整个 clone 都 gitignore | **不入库**。看板「设置」可改 |
  docs/SECRETS.md:36: | **Qoder 账号凭据**（OAuth device token / refresh token） | `gateways/upstream/qoder/accounts/<uid>.json` | 整个 `gateways/upstream/qoder/` 被 `.gitignore` 排除 | **不入库**。换账号时整目录操作 |
  docs/SECRETS.md:37: | **千问平台 API key**（`sk-ws-…`） | 控制台 `platform.qianwenai.com/home/api-keys`；本机写在 `providers/qwen/.env.local`（`.gitignore` 排除） | 脚本与 `zgate` 只从环境变量或该文件读；`/health` 只报 key 是否存在 | **不入库**。轮换后改 `.env.local` 并重启 zgate |
  docs/SECRETS.md:38: | **其它供应商的凭据**（你自己接的） | 该服务商自己的控制台 / 账号设置 | **一律走环境变量**，不落进源码、文档、缓存、日志。命名建议 `<供应商>_KEY` / `<供应商>_BASE`，与 §3.5 的表同格式 | **不入库**。加变量时同步补 §3.5 的表 |
  docs/SECRETS.md:39: | **ZCode provider 配置**（含各 provider 的 `apiKey`） | 本机 `~/.zcode/v2/provider_config.json` | 不在本仓；`--apply` 产生的 `provider_config.json.bak-*` 备份同样含 key，已被 `.gitignore` 排除 | **不入库**。回退步骤见 [MAINTENANCE.md](MAINTENANCE.md) §4 |
  ...
  docs/SECRETS.md:73: 
  docs/SECRETS.md:74: - **环境变量**：**`WB_GATEWAY_KEY`**。
  docs/SECRETS.md:75: - **谁在读**：`providers/workbuddy/workbuddy_probe_zcode.py`、`providers/workbuddy/workbuddy_zcode_sync.py`
  ...
  docs/SECRETS.md:81: ```sh
  docs/SECRETS.md:82: export WB_GATEWAY_KEY='<网关 api_key>'
  docs/SECRETS.md:83: ```
  ...
  docs/SECRETS.md:86: 
  docs/SECRETS.md:87: - **环境变量**：**`WB_GATEWAY_BASE`**，默认 `http://127.0.0.1:7863`。
  docs/SECRETS.md:88: - **谁在读**：`providers/workbuddy/workbuddy_probe_zcode.py`、`providers/workbuddy/workbuddy_zcode_sync.py`。
  ...
  docs/SECRETS.md:108: |---|---|---|---|
  docs/SECRETS.md:109: | **`OPENCODE_GO_KEY`** | `providers/opencode-go/probe/` 下 5 个脚本 + `gateways/zgate`（缺省回退到 `provider_config.json`） | 无 | 明确报错退出（不静默）；路由对应上游 502 |
  docs/SECRETS.md:110: | **`WB_GATEWAY_KEY`** | `providers/workbuddy/` 下 2 个现役脚本 + 1 个归档脚本 + `gateways/zgate`（缺省回退到网关 `config.json`） | 无（空串） | 不本地报错，表现为网关 **401**；路由对应上游 502 |
  docs/SECRETS.md:111: | **`WB_GATEWAY_BASE`** | 同上 + `gateways/zgate` | `http://127.0.0.1:7863` | 用默认值 |
  docs/SECRETS.md:112: | **`ZGATE_LISTEN`** / **`UNIFIED_ROUTER_PORT`**（旧） | `gateways/zgate` | `127.0.0.1:7871` | 用默认值；改了要同步改四组的 `baseUrl` |
  docs/SECRETS.md:113: | **`ZCODE_PERSONAL_PROVIDER_CONFIG_FILE`** | `providers/workbuddy/workbuddy_zcode_sync.py` | `~/.zcode/v2/provider_config.json` | 用默认值 |
  ...
  docs/SECRETS.md:119: | **`QD_API_KEY`** | `providers/qoder/qoder_zcode_sync.py`、`providers/qoder/qoder_probe_zcode.py`（缺省回退 `providers/qoder/.env.local`） | 无 | 明确报错退出（不静默） |
  docs/SECRETS.md:120: | **`QD_GATEWAY_BASE`** | 同上 | `http://127.0.0.1:8790/v1` | 用默认值 |
  docs/SECRETS.md:121: | `QD_PANEL_PASSWORD` | 首次启动 qoder2api-hub 时用；之后以 `accounts/settings.json` 的摘要为准 | 无 | 用已持久化的面板密码 |
  docs/SECRETS.md:122: | **`QWEN_API_KEY`** | `providers/qwen/qwen_zcode_sync.py`、`gateways/zgate`（缺省回退 `providers/qwen/.env.local`） | 无 | 脚本明确报错退出；路由的千问渠道 502 |
  docs/SECRETS.md:123: | **`QWEN_BASE`** | `providers/qwen/qwen_zcode_sync.py` | `https://maas.qianwenaiapi.com/apps/anthropic/v1` | 用默认值（**必须带 `/v1`**：桥会直接拼 `/messages`） |
  ...
  docs/SECRETS.md:126: 
  docs/SECRETS.md:127: - **环境变量**：`QD_API_KEY`（必填）、`QD_GATEWAY_BASE`（默认 `http://127.0.0.1:8790/v1`）。
  docs/SECRETS.md:128: - **谁在读**：`providers/qoder/qoder_zcode_sync.py`、`providers/qoder/qoder_probe_zcode.py`、
  docs/SECRETS.md:129:   `gateways/zgate`（7871 用它给 Qoder 上游鉴权）。
  docs/SECRETS.md:130: - **本机明文落点**：`providers/qoder/.env.local`（`QD_API_KEY` / `QD_PANEL_PASSWORD`），
  docs/SECRETS.md:131:   已被 `.gitignore` 排除；整个 `gateways/upstream/qoder/` clone 也被排除。
  docs/SECRETS.md:132: - **网关侧持久化**：API Key 与面板密码的摘要在
  docs/SECRETS.md:133:   `gateways/upstream/qoder/accounts/settings.json`；OAuth 账号在 `accounts/<uid>.json`。
  docs/SECRETS.md:134: - **合并模式**：key 只在 `.env.local` / 路由里；`--separate` 才写进
  ...
  docs/SECRETS.md:150: | `providers/opencode-go/probe/results/<日期>/` | 探测原始结果 | 体积大、可重跑再生 |
  docs/SECRETS.md:151: | `gateways/upstream/qoder/accounts/` | Qoder OAuth token、面板/Key 设置、签到状态 | 含 token；整个 clone 被 `.gitignore` 排除 |
  docs/SECRETS.md:152: | `providers/qoder/qoder_probe.json` | Qoder 模型探测结果 | 活数据，可重跑再生 |
  ...
  docs/SECRETS.md:156: `.gitignore` 里对应的排除项：`/providers/workbuddy/cache/*.json`、`/providers/workbuddy/logs/`、
  docs/SECRETS.md:157: `/providers/workbuddy/cache/*.log`、`/providers/opencode-go/probe/results/`、`/gateways/upstream/qoder/`、
  docs/SECRETS.md:158: `/providers/qoder/qoder_probe.json`、`*.env.local`、`*.bak-*`。
  ...
  docs/SECRETS.md:168: # 1) 确认没有把凭据文件带进去
  docs/SECRETS.md:169: git ls-files | grep -E 'provider_config\.json|\.bak-|providers/workbuddy/cache/|gateways/upstream/qoder/|providers/qoder/qoder_probe\.json|\.env$|\.key$'
  docs/SECRETS.md:170: 
  docs/SECRETS.md:171: # 2) 确认忽略规则生效
  docs/SECRETS.md:172: git status --ignored --short | grep -E '^!!' | head -20
  ...
  docs/SECRETS.md:183: - [ ] `providers/workbuddy/cache/`、`providers/workbuddy/logs/`、`providers/opencode-go/probe/results/` 不在库里；
  docs/SECRETS.md:184: - [ ] `gateways/upstream/qoder/`、`providers/qoder/.env.local`、`providers/qoder/qoder_probe.json` 不在库里；
  docs/SECRETS.md:185: - [ ] `evidence/` 下的文件不含 `apiKey` / `oc_sk_…`；
  ...
  docs/SECRETS.md:274: 
  docs/SECRETS.md:275: **完整路径一律不放行。** 这条只对文档类文件生效
  docs/SECRETS.md:276: （`CHANGELOG.md` / `PROGRESS.md` / `SECURITY.md` / `CONTRIBUTING.md` / `docs/` /
```
### docs/TOOLS.md
```text
  ...
  docs/TOOLS.md:17: |---|---|---|
  docs/TOOLS.md:18: | Python | 3.x，**只用标准库**（无第三方依赖） | 除 `tools/make_social_preview.py`（门面资源重生成，需 numpy + Pillow）和 `tools/dsh_sync.py`（读 DSH profile，需 PyYAML）外的所有 `.py` 脚本 |
  docs/TOOLS.md:19: | Node.js | 18+ | 跑 `.js` 脚本（探测、统一路由、思考字段映射） |
  ...
  docs/TOOLS.md:28: | `providers/opencode-go/ops/opencode-header-proxy.js` | 给不支持自定义头的客户端（ChatBox / Open WebUI 等）补 `x-opencode-session` | 常驻 HTTP 代理，默认 `127.0.0.1:8787` | ✅ 长期 |
  docs/TOOLS.md:29: | `gateways/zgate/` | **统一入口（Go）**：监听 `127.0.0.1:7871`，按 `model-alias-map.json` 分流；无 map 时回退旧前缀（`cn:`/`global:`/`qoder:`）；messages/responses 模型内置协议桥；同时按策略拉起/回收两个上游子进程（WB `ondemand`、Qoder `ondemand`）。子命令 `serve` / `status` / `reload` / `install` / `uninstall` / `version`；子进程默认全部 `ondemand`，签到/保活用 `windows` 定时窗口兜底；改策略后 `zgate reload` 热加载。策略与配置见 [MAINTENANCE.md](MAINTENANCE.md) §8 | 日志 `%LOCALAPPDATA%\ZCodeGateway\zgate.log`（5 MB 轮转）；子进程输出同目录 `workbuddy.*` / `qoder.*` | ✅ 长期 |
  docs/TOOLS.md:30: | `gateways/zgate/build.py` | **zgate 构建入口**：带 `-H windowsgui` 编译（GUI 子系统 → 登录自启零窗口），并**强制校验产物的 PE `Subsystem` 必须为 2**；`--check` 只校验现有产物，`--cross-check` 交叉编译一份 windows/amd64 到临时目录再校验（CI 用，Linux 上也生效） | `gateways/zgate/zgate.exe`（`.gitignore` 排除）；临时目录里的交叉编译产物 | ✅ 长期 |
  docs/TOOLS.md:31: | `gateways/zgate/smoke_test.py` | 冒烟测试：四条通道 + 两种桥 + 流式各打一发微小请求，断言 200 / `chat.completion` / `[DONE]` | 只打印 PASS/FAIL；`ZGATE_BASE` 可改目标 | ✅ 长期（每次改路由后跑） |
  docs/TOOLS.md:32: | `tools/model_alias.py` | **最终写入者**：把当前配置里的模型归一成纯型号名，同型号跨渠道合并成 `chain`（WB 固定链首，其余按价格 / 前缀 / 渠道稳定排序），按人工有序名单分**三组**（主力 `MAIN_ORDER` / 免费按 0 价 / 省钱 `LOW_ORDER` 严格白名单），组内顺序也按名单下标，生成 alias map；**价格每轮从源重算、不继承旧值**（死跳直接剔除）；`--probe-file` 只保留 ok（或曾 ok 的瞬时限流，超过 `--probe-max-age-hours` 默认 72h 视为未知）；`--check` 只做漂移检测（有差异退出码 1）；`--arena-main` 读榜单候选扩充主力，`--no-arena` 回到纯人工。使用默认 ZCode 配置路径时，`--apply` 会在写完后调用 `tools/dsh_sync.py --apply` 投影到本机 DeepSeekRuntime（DSH 未安装则跳过；`--config` 指向沙盒时默认不投影；`--no-dsh` 关闭） | `provider_config.json.bak-alias-<时间戳>`；`~/.zcode/v2/model-alias-map.json`；DSH patch / 凭据备份（见下行） | ✅ 长期 |
  docs/TOOLS.md:33: | `tools/arena_leaderboard.py` | **主力扩充取数**：拉 ArenaGalleri 榜单接口，按 DeepSeek 基准（分数 ≥95%、积分 ≤0.11、非临时名次、≥50 局、不含 0 积分）从**已配置模型**里筛候选；候选集合或规则变化才触发重写。`--refresh` 联网重拉、`--write` 落候选、`--apply` 接着调 `model_alias.py`、`--status` 看已保存候选 | `~/.zcode/v2/arena-leaderboard.json`（榜单缓存）、`~/.zcode/v2/arena-main.json`（主力候选） | ✅ 长期 |
  docs/TOOLS.md:34: | `tools/sync_report.py` | **同步报告**：对比上一轮快照（`~/.zcode/v2/model-sync-state.json`），写出本次新增 / 移除 / 分组变化 / 链路变化；`--write` 落 `docs/reports/MODEL-SYNC-<时间>.md` 并更新索引，`--push` 再 `git add/commit/push`。自动化最后一步跑它 | 报告 `docs/reports/*.md`、索引 `docs/reports/README.md`、快照 `model-sync-state.json` | ✅ 长期 |
  docs/TOOLS.md:35: | `tools/dsh_sync.py` | **DeepSeekRuntime 投影**：读 ZCode 最终 `provider_config.json`，重写 `~/.dsh/profiles/<profile>/cordis.patch.yml` 的 `llm-pi-ai` 三组路由，保留其他 patch 条目和非 `zcode-*` provider；`reasoningLevel.map="{}"` 的模型不写 `reasoningEfforts`（避免 DSH 发送上游会拒的 `reasoning_effort`）；`--apply` 备份并写 patch + DSH 凭据引用，`--check` 有漂移退出 1。通常由 `model_alias.py --apply` 自动调用 | DSH profile patch；`~/.dsh/.credentials.yaml` 的 `ZCODE_GATEWAY_KEY` 引用；`*.bak-dshsync-<时间戳>` | ✅ 长期 |
  docs/TOOLS.md:36: | `tools/model_probe.py` | 用 **ZCode 真实 body**（`zcode_effective_body.js` + provider id）探测三组模型；经 7871，含桥接模型；结果带 `ever_ok` | `~/.zcode/v2/model_probe.json`（活数据） | ✅ 长期 |
  docs/TOOLS.md:37: | `gateways/legacy-router/protocol_bridge.js` | chat ↔ Anthropic Messages / OpenAI Responses 转换（旧 Node 实现，已由 zgate 内置桥取代） | 由 `unified-router.js` require | ⚠️ 回退用（保留一个版本） |
  docs/TOOLS.md:38: | `providers/workbuddy/workbuddy_fetch_pricing.py` | 拉网关目录接口 → 归一化 → 写价格表（打印倍率变化 / 新增 / 下架摘要）；条数骤降时逐个探活，只删确认下架的 | `providers/workbuddy/cache/wb_pricing.json`（写前自动备份） | ✅ 长期 |
  ...
  docs/TOOLS.md:41: | `providers/workbuddy/zcode_effective_body.js` | 复刻 ZCode 引擎的规则解析顺序，算某 modelId **真实会发的请求体** | stdout JSON | ✅ 长期（`probe_zcode.py` 依赖它，必须同目录） |
  docs/TOOLS.md:42: | `gateways/legacy-router/unified-router.js` | **旧 Node 路由**（回退用）：与 zgate 行为对齐；P3 验收通过后删除 | 日志 `router.stdout.log` / `router.stderr.log` | ⚠️ 回退用（保留一个版本） |
  docs/TOOLS.md:43: | `gateways/upstream/workbuddy/` | 上游 WorkBuddy2API Panel 的**独立 clone** + 运行时（`config.json` / `auths/` / `data/` / `wb2api.exe`）；整目录被 `.gitignore` 排除 | 网关自身的 `data/` 与日志 | ✅ 长期（更新：`git -C gateways/upstream/workbuddy pull --ff-only`） |
  docs/TOOLS.md:44: | `gateways/upstream/qoder/` | 上游 qoder2api-hub 的**独立 clone** + 运行时（`accounts/` / `usage/` / `umid/`）；整目录被 `.gitignore` 排除。默认 `127.0.0.1:8790`，`start-qoder-proxy.bat` / `stop-qoder-proxy.bat` 管理 | 网关自身的 `accounts/scheduler/state.json`、`qoder-proxy.log` / `.err.log` | ✅ 长期（更新：`git -C gateways/upstream/qoder pull --ff-only`） |
  docs/TOOLS.md:45: | `providers/qoder/qoder_zcode_sync.py` | **默认合并**：拉 qoder2api-hub `/v1/models` → 排除 `Auto`/`Fast` 别名 → 按 `price_factor` 把 `qoder:` 前缀模型并入三个 chat 组（主力 / 免费 / 省钱）；`--separate` 才写独立的 `qoder` provider；`--probe-file` 只保留探测 `ok`（或曾 ok 的瞬时限流），默认 `--max-price 0.8`。每天 12:00 定时任务里与 `qoder_probe_zcode.py` 成对执行（见 [MAINTENANCE.md](MAINTENANCE.md) §6） | 备份 `provider_config.json.bak-qoder-merge-<时间戳>`（separate 模式 `.bak-qoder-<时间戳>`）；dry run 打印落组 | ✅ 长期 |
  ...
  docs/TOOLS.md:62: | `~/.zcode/v2/arena-main.json` | 主力候选（基准分 / 窗口规则 / 每个候选的 channel、upstream、分数、积分） | 由 `tools/arena_leaderboard.py` 生成，被 `model_alias.py` 读取 | ⚠️ 活数据 |
  docs/TOOLS.md:63: | `~/.zcode/v2/model-alias-map.json` | 显示名 → 上游模型/base/protocol 的映射 | 由 `tools/model_alias.py` 生成，路由按 mtime 热加载 | ⚠️ 活数据（不含凭据） |
  docs/TOOLS.md:64: | `evidence/wb_panel_models.json` | 网关模型目录原始快照 | 只读证据 | — |
  ...
  docs/TOOLS.md:79: |---|---|---|
  docs/TOOLS.md:80: | 统一模式（默认） | 不带 `--separate` | WorkBuddy 模型并进 OpenCode 的三组，三组的 `baseUrl` 指向统一入口 `gateways/zgate`（`127.0.0.1:7871`） |
  docs/TOOLS.md:81: | 分离模式 | `--separate` | 重建四个独立的 `workbuddy-*` provider（免代 / 低代 / 高代 / 备用），`baseUrl` 直指网关 |
  ...
  docs/TOOLS.md:83: 统一入口按 alias map 分流：`W/…` → WorkBuddy 网关（`127.0.0.1:7863`），
  docs/TOOLS.md:84: 其余 → OpenCode-Go。它由 `gateways/zgate` 常驻提供（登录自启，见
  docs/TOOLS.md:85: [MAINTENANCE.md](MAINTENANCE.md) §8），健康检查 `GET http://127.0.0.1:7871/health`。
  ...
  docs/TOOLS.md:87: 模型怎么分档、哪些模型进哪一组，见 [MODEL-PROVIDERS.md](MODEL-PROVIDERS.md) §4.0、§4.2；
  docs/TOOLS.md:88: 守护器与开机自启，见 [MAINTENANCE.md](MAINTENANCE.md) §8。
  docs/TOOLS.md:89: 
```
### docs/TROUBLESHOOTING.md
```text
  ...
  docs/TROUBLESHOOTING.md:47: |---|---|
  docs/TROUBLESHOOTING.md:48: | ZCode 还没热重载（约 1 秒轮询） | 等 1~2 秒；仍不刷新就**重启客户端** |
  docs/TROUBLESHOOTING.md:49: | **ZCode 的 provider 设置界面在你写完之后又保存了一次**，整份写回覆盖了 | 写配置期间**不要在界面里改**；重新跑一次脚本 |
  ...
  docs/TROUBLESHOOTING.md:150: | `no_healthy_account` | **【实例 B】** | **探测间隔太短，把账号池打爆了** —— 用 `--sleep 20` 重跑（脚本支持断点续跑） |
  docs/TROUBLESHOOTING.md:151: | 429 / `no_healthy_account` 伴随**网关进程消失** | **【实例 B】** | 网关被打崩了，重启 `wb2api` 后再跑；**先确认 `/status` 可达** |
  docs/TROUBLESHOOTING.md:152: | `400 model_unavailable` + `upstream: 6004 model rate limit` | **【实例 B】** | 该模型的**全部账号**在冷却（模型级限流，不是账号池被打爆）。带 `fallbacks` 的显示名会自动改走备用区域（如 `global:` → `cn:`）；没有 fallback 的模型只能等，`gateway_hint` 里有最早解封时间 |
  docs/TROUBLESHOOTING.md:153: 
  ...
  docs/TROUBLESHOOTING.md:169: ```bash
  docs/TROUBLESHOOTING.md:170: # 1) 看当前价格表里各模型的生效倍率
  docs/TROUBLESHOOTING.md:171: python -c "import json; d=json.load(open('providers/workbuddy/cache/wb_pricing.json',encoding='utf-8')); [print('%-32s list=%-6s eff=%s' % (m['id'], m.get('list_rate'), m.get('eff_rate'))) for m in sorted(d, key=lambda x: x.get('eff_rate') if x.get('eff_rate') is not None else 999)]"
  ...
  docs/TROUBLESHOOTING.md:173: # 2) 对比网关当前返回的倍率
  docs/TROUBLESHOOTING.md:174: curl -s http://127.0.0.1:7863/panel/api/models -H "Authorization: Bearer $WB_GATEWAY_KEY" | python -m json.tool | head -40
  docs/TROUBLESHOOTING.md:175: ```
  ...
  docs/TROUBLESHOOTING.md:182: | 限时免费到期（网关日志：`free tier ended, now 0.227 credits/1k`） | 统一模式重跑 `workbuddy_zcode_sync.py --apply`；分离模式重排四档 |
  docs/TROUBLESHOOTING.md:183: | 网关未重启时 `/panel/api/models` 只返回 34 个 global 模型 | 重启网关再取 |
  docs/TROUBLESHOOTING.md:184: 
  ...
  docs/TROUBLESHOOTING.md:271: curl -si -X POST http://127.0.0.1:7863/v1/chat/completions \
  docs/TROUBLESHOOTING.md:272:   -H "Authorization: Bearer $WB_GATEWAY_KEY" -H "Content-Type: application/json" \
  docs/TROUBLESHOOTING.md:273:   -d '{"model":"<model-id>","messages":[{"role":"user","content":"hi"}],"max_tokens":16}' | head -20
  ...
  docs/TROUBLESHOOTING.md:324: 
  docs/TROUBLESHOOTING.md:325: <a id="gateway-lifecycle"></a>
  docs/TROUBLESHOOTING.md:326: 
  ...
  docs/TROUBLESHOOTING.md:329: **现象**：WorkBuddy 模型连不上 `127.0.0.1:7863`，或四组模型都连不上 `127.0.0.1:7871`；
  docs/TROUBLESHOOTING.md:330: 开机后 zgate 没生效；或者 Qoder 上游没在跑。
  docs/TROUBLESHOOTING.md:331: 
  ...
  docs/TROUBLESHOOTING.md:334: ```bash
  docs/TROUBLESHOOTING.md:335: # 1) 一次看全：服务是否在跑 / 子进程状态 / 端口 / 凭据有无
  docs/TROUBLESHOOTING.md:336: gateways/zgate/zgate.exe status
  docs/TROUBLESHOOTING.md:337: 
  docs/TROUBLESHOOTING.md:338: # 2) 看 zgate 日志（每个请求一行、子进程起停、错误；UTF-8）
  docs/TROUBLESHOOTING.md:339: python -c "import os; p=os.path.join(os.environ['LOCALAPPDATA'],'ZCodeGateway','zgate.log'); print(open(p,encoding='utf-8').read()[-3000:])"
  docs/TROUBLESHOOTING.md:340: 
  docs/TROUBLESHOOTING.md:341: # 3) 看开机自启在不在
  docs/TROUBLESHOOTING.md:342: ls "$APPDATA/Microsoft/Windows/Start Menu/Programs/Startup/" | grep -i zcode
  docs/TROUBLESHOOTING.md:343: ```
  ...
  docs/TROUBLESHOOTING.md:348: |---|---|
  docs/TROUBLESHOOTING.md:349: | zgate 没在跑（没装自启 / 被杀） | `gateways/zgate/zgate.exe serve` 前台起一次看报错；再 `zgate.exe install` 重建自启 |
  docs/TROUBLESHOOTING.md:350: | 7871 被别的进程占着 | `zgate.exe serve` 会明确报「监听失败」；用 `netstat -ano \| findstr 7871` 找出占用者 |
  docs/TROUBLESHOOTING.md:351: | 配置路径不对（`gateways/zgate/zgate.json`） | `zgate.exe status` 第一段会打印实际读到的配置、alias map 与日志路径 |
  docs/TROUBLESHOOTING.md:352: | WorkBuddy 冷启动失败 | 看 `%LOCALAPPDATA%\ZCodeGateway\workbuddy.stderr.log`；确认 `gateways/upstream/workbuddy/wb2api.exe` 与 `config.json` 存在（clone 整目录被 `.gitignore` 排除，**克隆后不会自带**，重建见 [MAINTENANCE.md](MAINTENANCE.md) §8.4） |
  docs/TROUBLESHOOTING.md:353: | Qoder 冷启动失败 | 看 `%LOCALAPPDATA%\ZCodeGateway\qoder.stderr.log`；确认 `python` 在 PATH、`gateways/upstream/qoder/` 完整 |
  docs/TROUBLESHOOTING.md:354: | 端口被占但健康检查不通 | zgate 会拒绝重复启动并报「端口被占用且健康检查不通」；先清掉占用进程 |
  docs/TROUBLESHOOTING.md:355: | 子进程老是退出 | 默认 `ondemand` 模式下 WB 空闲 15 分钟会被回收，这是正常行为；不是「挂了」 |
  docs/TROUBLESHOOTING.md:356: | `status` 的 Provider 段显示 key 缺失 | 四组没指向 7871，或 provider 里没有 apiKey：重跑 `python tools/model_alias.py --slot auto --apply`，或检查 `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` |
  docs/TROUBLESHOOTING.md:357: | 想彻底回到手动 | `zgate.exe uninstall` 移除自启；网关仍可用 `gateways/upstream/workbuddy/run.bat`、Qoder 用 `start-qoder-proxy.bat` 单独起 |
  docs/TROUBLESHOOTING.md:358: 
  docs/TROUBLESHOOTING.md:359: > zgate 常驻（约 19 MB），不跟随 ZCode 起停：它自己按策略管两个子进程
  docs/TROUBLESHOOTING.md:360: > （WB `ondemand`、Qoder `always`）。ZCode 最小化到托盘不影响任何进程，
  ...
  docs/TROUBLESHOOTING.md:375: 
  docs/TROUBLESHOOTING.md:376: # 2) 看服务与子进程状态
  docs/TROUBLESHOOTING.md:377: gateways/zgate/zgate.exe status
  docs/TROUBLESHOOTING.md:378: 
  docs/TROUBLESHOOTING.md:379: # 3) 看日志
  docs/TROUBLESHOOTING.md:380: python -c "import os; p=os.path.join(os.environ['LOCALAPPDATA'],'ZCodeGateway','zgate.log'); print(open(p,encoding='utf-8',errors='replace').read()[-3000:])"
  docs/TROUBLESHOOTING.md:381: ```
  ...
  docs/TROUBLESHOOTING.md:386: |---|---|
  docs/TROUBLESHOOTING.md:387: | 入口没起 | `gateways/zgate/zgate.exe serve` 前台启动排错，或 `zgate.exe install` 重建自启 |
  docs/TROUBLESHOOTING.md:388: | 7871 被别的进程占用 | `Get-NetTCPConnection -LocalPort 7871`；换 `ZGATE_LISTEN` 后同步改四组的 `baseUrl` |
  docs/TROUBLESHOOTING.md:389: | 缺 OpenCode key | 设置 `OPENCODE_GO_KEY`，或检查 `provider_config.json` 里 OpenCode provider 的 `access.apiKey` |
  docs/TROUBLESHOOTING.md:390: | 缺 WorkBuddy key | 设置 `WB_GATEWAY_KEY`，或检查 `gateways/upstream/workbuddy/config.json` 的 `api_key` |
  docs/TROUBLESHOOTING.md:391: | 只有 WorkBuddy 模型 502 | 网关没起 / 没就绪；看 `gateway.stderr.log` |
  docs/TROUBLESHOOTING.md:392: | 对话 / 响应正常，chat 全挂 | 就是路由问题；这两组不经过路由，所以能正常工作 |
  ...
  docs/TROUBLESHOOTING.md:429: | `cn:hy4-preview-f` / `global:hy4-preview-f` 没被收录 | **已修**：`rate_of` 原先只看原始 `credits`（免费条目为空串）→ 判成 `None` → 按「无公布倍率」排除 | 现改为优先用归一化的 `eff_rate` / `list_rate`，两个免费 `-f` 已进免代档（见 [MAINTENANCE.md](MAINTENANCE.md) §7 待办 7） |
  docs/TROUBLESHOOTING.md:430: | `cn:deepseek-v4.1-flash` 503 `no_healthy_account` | 账号池里唯一那个 CN 账号上，该模型被 **6004 模型频率限制**锁住 | 查 `curl -sS http://127.0.0.1:7863/status` 的 `model_locks`（含 `unlock_at`），到点自愈；`global:` 同款通常正常 |
  docs/TROUBLESHOOTING.md:431: 
  ...
  docs/TROUBLESHOOTING.md:439: 
  docs/TROUBLESHOOTING.md:440: 先分三层确认：服务活着、账号可用、模型写进 ZCode。
  docs/TROUBLESHOOTING.md:441: 
  ...
  docs/TROUBLESHOOTING.md:450: | ZCode 里没有 `qoder:` 模型 | `ListModels`；看五个 chat 组里是否有 `qoder:` 前缀的 model id + model rule；`curl http://127.0.0.1:7871/health` 的 `qoder.key`；8790 `/v1/models` 是否可达 | 同步没写，或被 ZCode 界面整份写回覆盖。重跑 `qoder_zcode_sync.py --apply`，不要与界面同时保存 |
  docs/TROUBLESHOOTING.md:451: | 请求 401 | `providers/qoder/.env.local` 的 `QD_API_KEY` 与 `gateways/upstream/qoder/accounts/settings.json` 是否一致；`--separate` 模式再看 provider_config 里的 `qoder` apiKey | 合并模式 key 只在 `.env.local` / 7871 路由；三处不一致时轮换后一起改，再重启 hub 与路由 |
  docs/TROUBLESHOOTING.md:452: | 7871 `/health` 里 `qoder.key=false` 或 `qoder:` 请求 502 `Qoder key not configured` | 路由启动时没读到 `QD_API_KEY` | 确认 `providers/qoder/.env.local` 存在且可读，然后重启路由（zgate 会自动拉起） |
  docs/TROUBLESHOOTING.md:453: | 502 / `10605` / `isQueued` | `/health` 的 `risk.queue`；`providers/qoder/qoder_probe.json` 的状态 | 上游排队，不是本地故障。免费 `Qwen3.8-Flash` 最容易中，`DeepSeek-Flash` 也会（64s 后 200，或 90s+ 后 502）。`--probe-file` 只看 `ever_ok`：曾 200 的模型遇排队仍保留，只有从未成功过的才会被排除 |
  ...
  docs/TROUBLESHOOTING.md:475: 
  docs/TROUBLESHOOTING.md:476: ## 16. 开机弹 cmd 控制台窗口（zgate 不是无窗版）【实例 B】
  docs/TROUBLESHOOTING.md:477: 
  docs/TROUBLESHOOTING.md:478: **现象**：登录后弹出一个 cmd 控制台窗口，标题是快捷方式名「ModelBus zgate」；
  docs/TROUBLESHOOTING.md:479: 关掉它网关就死，四个 chat 组全 502。
  ...
  docs/TROUBLESHOOTING.md:484: # 1) 直接读 PE 头，看 Subsystem 是 2（GUI 无窗）还是 3（CONSOLE 控制台）
  docs/TROUBLESHOOTING.md:485: python gateways/zgate/build.py --check
  docs/TROUBLESHOOTING.md:486: 
  docs/TROUBLESHOOTING.md:487: # 2) 看这个窗口是不是 zgate 带来的
  docs/TROUBLESHOOTING.md:488: Get-CimInstance Win32_Process -Filter "Name='zgate.exe'" | Select ProcessId,ParentProcessId,CommandLine
  docs/TROUBLESHOOTING.md:489: 
  docs/TROUBLESHOOTING.md:490: # 3) 看是不是编译期被覆盖过（看 exe 修改时间 vs 提交时间）
  docs/TROUBLESHOOTING.md:491: ls -la gateways/zgate/zgate.exe
  docs/TROUBLESHOOTING.md:492: ```
  ...
  docs/TROUBLESHOOTING.md:497: |---|---|
  docs/TROUBLESHOOTING.md:498: | 产物是控制台程序（`Subsystem = 3`） | 在 `gateways/zgate/` 里裸跑过 `go build .`（单包模式会原地覆盖产物）。用 `python gateways/zgate/build.py` 重编，它带 `-H windowsgui` 并强制校验 PE 子系统 |
  docs/TROUBLESHOOTING.md:499: | 产物是控制台程序，但 exe 正被占用改不动 | zgate 在运行时 Windows 会锁住文件。先停掉（zgate 没有 `stop` 子命令）：`Stop-Process -Id <pid> -Force`；再重编、再起 |
  docs/TROUBLESHOOTING.md:500: | 快捷方式 `WindowStyle = 7` 没用 | 「最小化」只对有窗口的程序有效，对控制台子系统程序**不等于隐藏**。而且实测那个窗口既没最小化、也是可见的 —— 唯一解法是让产物本身是 GUI 子系统 |
  docs/TROUBLESHOOTING.md:501: | 想确认没有别的控制台窗口 | `Get-Process conhost | Where-Object { $_.MainWindowTitle }`；无输出即没有 |
  docs/TROUBLESHOOTING.md:502: | 窗口没了但服务也没了 | zgate 被 agent 会话结束时连带清掉了（进程树回收）。要让 Task Scheduler 当父进程才活得下来：`schtasks /run /tn "ModelBus-zgate-hidden"`，或等看门狗（PT1M）自动拉回；会话里直接 `Start-Process zgate.exe` 会被回收 |
  docs/TROUBLESHOOTING.md:503: 
  ...
  docs/TROUBLESHOOTING.md:506: 
  docs/TROUBLESHOOTING.md:507: ### 16.1 终端里起的 zgate 随窗口关闭而死
  docs/TROUBLESHOOTING.md:508: 
  docs/TROUBLESHOOTING.md:509: **现象**：在 cmd / Windows Terminal 里敲 `zgate serve`（或双击 exe），网关跑起来；一关那个窗口，四个 chat 组立刻全 502，`/health` 拒连。
  docs/TROUBLESHOOTING.md:510: 
  docs/TROUBLESHOOTING.md:511: **原因**：`zgate serve` 是前台进程，控制台窗口关闭会给窗口内所有进程发 `CTRL_CLOSE_EVENT`；子进程（wb2api 等）挂在 zgate 的 Job Object 上一起走。这不是 bug，是前台进程的正常语义 —— 要让网关活过终端，就得让终端不是它的父。
  docs/TROUBLESHOOTING.md:512: 
  ...
  docs/TROUBLESHOOTING.md:515: ```cmd
  docs/TROUBLESHOOTING.md:516: :: 后台起，立刻返回；关掉这个窗口不影响网关
  docs/TROUBLESHOOTING.md:517: zgate.exe serve -tray
  docs/TROUBLESHOOTING.md:518: ```
  docs/TROUBLESHOOTING.md:519: 
  docs/TROUBLESHOOTING.md:520: - `serve -tray` 用 `DETACHED_PROCESS` 拉一个**无父进程**的副本：副本没有控制台，收不到关窗事件；拉起方退出后副本照常服务。
  docs/TROUBLESHOOTING.md:521: - 拉起方通过环境变量把自身 PID 传给副本，副本每 2 秒查一次：拉起它的进程消失就自己退出，不留孤儿占端口。日志里是 `拉起方 <pid> 已退出，后台副本随之停止`。
  docs/TROUBLESHOOTING.md:522: - 前台 `zgate serve` 现在打完启动横幅就 `FreeConsole` 解放控制台，避免留下半死的 `conhost`；输出仍写日志文件，重定向（`zgate status > out.txt`）不受影响。
  docs/TROUBLESHOOTING.md:523: - 登录自启（`zgate install`）生成的快捷方式已改成 `serve -tray`。
  docs/TROUBLESHOOTING.md:524: 
  ...
  docs/TROUBLESHOOTING.md:527: ```cmd
  docs/TROUBLESHOOTING.md:528: zgate.exe serve -tray
  docs/TROUBLESHOOTING.md:529: :: 应有一行「已在后台启动: <exe> (pid N, ready=true)；停止: Stop-Process -Id N」
  docs/TROUBLESHOOTING.md:530: curl http://127.0.0.1:7871/health
  ...
  docs/TROUBLESHOOTING.md:533: 
  docs/TROUBLESHOOTING.md:534: **注意**：`DETACHED_PROCESS` 只表示「不共享控制台」，不保证**调用方整棵进程树被回收**时仍存活（`cmd /c`、`Start-Process` 结束后会连带带走，已实测）。要彻底解耦，用计划任务启动 —— 自启走的就是这条路。
  docs/TROUBLESHOOTING.md:535: 
  ...
  docs/TROUBLESHOOTING.md:542: 
  docs/TROUBLESHOOTING.md:543: 1. **先确认服务活着**（实例 B：`curl http://127.0.0.1:7863/status`；
  docs/TROUBLESHOOTING.md:544:    实例 A：`curl https://opencode.ai/zen/go/v1/models`；
```
### docs/UPSTREAM.md
```text
  ...
  docs/UPSTREAM.md:13: | 快照日期 | **2026-10-20**（star 数、最近推送时间都是这一天的快照，会变） |
  docs/UPSTREAM.md:14: | 检索方式 | GitHub REST API `search/repositories`（`multi-provider ai gateway`、`llm proxy provider manager`、`claude code router`、`openai compatible proxy coding agent`、`zcode`）+ `repos/{owner}/{repo}` 元数据 |
  docs/UPSTREAM.md:15: | 取源码方式 | `git ls-remote` 取 HEAD SHA；`codeload` tarball 与 `raw.githubusercontent.com` 取文件。**没有整仓 clone 大仓库**（ZCodium 的 tarball 有 84 MiB，用完即删） |
  ...
  docs/UPSTREAM.md:168: 
  docs/UPSTREAM.md:169: **为什么没有 vendor 它的代码**：它是一整个常驻代理服务（2549 行 `zen-proxy.mjs`），
  docs/UPSTREAM.md:170: 本仓要的是「写配置」不是「再插一个代理」；而且它针对**免费档**，
  ...
  docs/UPSTREAM.md:205: 把请求里的 `thinking` 字段解析成一个 `ReasoningPolicy(mode=auto|on|off, effort, budget_tokens)`，
  docs/UPSTREAM.md:206: 再由各适配器决定怎么落回去。另外提供「no-thinking gateway IDs」这种**用模型名表达开关**的技巧。
  docs/UPSTREAM.md:207: 
  ...
  docs/UPSTREAM.md:221: **为什么没有 vendor 它的代码**：它是 Python，但**依赖 FastAPI + python-dotenv**，
  docs/UPSTREAM.md:222: 而本仓的纪律是**只用标准库**；且它是一整套网关服务，本仓不需要。抄它的
  docs/UPSTREAM.md:223: 「档位/降级/限流三元组」这个**模型**即可。
  ...
  docs/UPSTREAM.md:293: 它是「一个本地控制面管所有 agent」的代表作。跟我们相关的是它的**能力目录**：
  docs/UPSTREAM.md:294: `packages/core/src/gateway/model-catalog.ts` 里的 `readCatalogCapability()` 与
  docs/UPSTREAM.md:295: `modelCatalogReasoningEffortConfig()` —— 从上游目录的 metadata 里读出
  ...
  docs/UPSTREAM.md:383: | AnyBridge | 技术栈对不上（Rust + Tauri + 内嵌 `cursor-core`），且它是**图形化配置管理器**，本仓是脚本工具。有用的只有一张协议映射表和两个写入策略 |
  docs/UPSTREAM.md:384: | zen-proxy | 是常驻代理服务（2549 行），本仓要的是「写配置」；且它针对免费档，本仓走付费 Go 套餐，会话头规则**未经本仓实测** |
  docs/UPSTREAM.md:385: | my-free-code | 依赖 FastAPI + python-dotenv，本仓**只用标准库**；且它是网关服务 |
  docs/UPSTREAM.md:386: | claude-code-router | tarball 20 MiB 的单体仓；本仓只用到「能力目录」这个思路 |
```
### docs/VERSIONING.md
```text
  ...
  docs/VERSIONING.md:40: |---|---|---|
  docs/VERSIONING.md:41: | 修一个「本该生效却没生效」的 bug | ❌ `+0.0.1` | 行为回到了它本来该有的样子，不是新行为 |
  docs/VERSIONING.md:42: | 删掉某项能力 / 某个入口 / 某个 provider 分组 | ✅ `+0.1.0` | 能力清单变了，使用者可感知的减法也是更新 |
  ...
  docs/VERSIONING.md:76: | 日期 | **2026-11-06** |
  docs/VERSIONING.md:77: | 性质 | WB 链首硬规则、dsh_sync 429 快速失败、go-sync 三道护栏、模型同步改计划任务驱动、effort 自动写档位 |
  docs/VERSIONING.md:78: 
```
### docs/archive/OPENCODE-GO-ANALYSIS.md
```text
  ...
  docs/archive/OPENCODE-GO-ANALYSIS.md:85: | **longcat-2.0** | 0.30 | 1.20 | $60 | chat | 首字很慢（17s+） | 不推荐交互 |
  docs/archive/OPENCODE-GO-ANALYSIS.md:86: | **longcat-2.5-preview-free** | 0 | 0 | 无限 | chat | 极慢（TTFT 11–24s） | 后台批处理 |
  docs/archive/OPENCODE-GO-ANALYSIS.md:87: | **qwen3.7-plus** | 0.40 | 1.60 | $60 | messages | 首字 17s，话极多 | 一次生成大段内容 |
  ...
  docs/archive/OPENCODE-GO-ANALYSIS.md:127: - `yamls/proxy-groups.yaml` 是官方支持的自定义策略组扩展点（clash_modify.sh 会合并）。
  docs/archive/OPENCODE-GO-ANALYSIS.md:128: - `provider_temp_clash=DustinWin_RS_Full.yaml` 是死设置，当前模式不生效。
  docs/archive/OPENCODE-GO-ANALYSIS.md:129: 
  ...
  docs/archive/OPENCODE-GO-ANALYSIS.md:178:    - 更致命的是记忆里那条：订阅一旦自带顶层 `rule-providers:`，和 `clash_modify.sh`
  docs/archive/OPENCODE-GO-ANALYSIS.md:179:      注入的会撞键，mihomo 直接拒载。现在这套是验证过不会撞的。
  docs/archive/OPENCODE-GO-ANALYSIS.md:180: 
  ...
  docs/archive/OPENCODE-GO-ANALYSIS.md:182:    ```sh
  docs/archive/OPENCODE-GO-ANALYSIS.md:183:    /etc/ShellCrash/task/task.sh hotupdate      # 热更新订阅，不重启
  docs/archive/OPENCODE-GO-ANALYSIS.md:184:    /etc/ShellCrash/task/task.sh update_config  # 更新并重启
  docs/archive/OPENCODE-GO-ANALYSIS.md:185:    ```
  ...
  docs/archive/OPENCODE-GO-ANALYSIS.md:209: - **hy3**（7s+）、**mimo-v2.5**（~39 tok/s）、**mimo-v2.6-flash**（3–6s）、
  docs/archive/OPENCODE-GO-ANALYSIS.md:210:   **longcat-2.0**（17s+）。适合不赶时间的批处理/后台任务。
  docs/archive/OPENCODE-GO-ANALYSIS.md:211: 
  ...
  docs/archive/OPENCODE-GO-ANALYSIS.md:271: - [x] 新增 `ai-api-check.sh` 自检 + `opencode.key`
  docs/archive/OPENCODE-GO-ANALYSIS.md:272: - [x] 重启 ShellCrash 并验证三协议
  docs/archive/OPENCODE-GO-ANALYSIS.md:273: - [x] 19/19 模型验证通过
  docs/archive/OPENCODE-GO-ANALYSIS.md:274: - [ ] 用户重启 ZCode 使新模型列表生效
  docs/archive/OPENCODE-GO-ANALYSIS.md:275: 
```
### docs/release-notes/0.1.0.md
```text
  ...
  docs/release-notes/0.1.0.md:25: - 新增 维护流程 —— 价格表怎么刷（含当前没有生成脚本这个缺口）、探测多久跑一次、结果快照留多久、写配置前怎么备份与回退。
  docs/release-notes/0.1.0.md:26: - 新增 第三方声明 —— WorkBuddy2API Panel（MIT）、OpenCode Go（商业服务）、ZCode（闭源客户端）的来源、许可与使用理由。
  docs/release-notes/0.1.0.md:27: - 调整 仓库 —— 从原工作目录里拆成独立仓库，脚本按「长期运维 / 一次性探测 / 归档」分目录，行为零变更。
  ...
  docs/release-notes/0.1.0.md:33: > 脚本会改你自己的 ZCode 配置文件，写前自动备份到同目录的 .bak-* 文件。
  docs/release-notes/0.1.0.md:34: > 模型价格、额度、倍率与可用性以服务商当时的说明为准；文档里的数字是快照，会过时。
  docs/release-notes/0.1.0.md:35: 
```
### docs/release-notes/0.2.0.md
```text
  ...
  docs/release-notes/0.2.0.md:18: 
  docs/release-notes/0.2.0.md:19: - 修复 每日自动收录 —— 重建为每天 12:00；取网关 key 的来源改为 `gateway/config.json`；目标会话解绑，每次运行新建独立会话。
  docs/release-notes/0.2.0.md:20: - 调整 守护器 —— 主进程改用进程句柄判活；启动时对账清理遗留网关；停止时按端口反查并校验进程名；新增 15 分钟心跳。
  docs/release-notes/0.2.0.md:21: 
  ...
  docs/release-notes/0.2.0.md:28: > 脚本会改你自己的 ZCode 配置文件，写前自动备份到同目录的 .bak-* 文件。
  docs/release-notes/0.2.0.md:29: > 模型价格、额度、倍率与可用性以服务商当时的说明为准；文档里的数字是快照，会过时。
  docs/release-notes/0.2.0.md:30: 
```
### docs/release-notes/0.3.0.md
```text
  ...
  docs/release-notes/0.3.0.md:1: **单进程入口：路由、协议桥与两个本地网关的起停都交给 `gateways/zgate`，目录重新分层。**
  docs/release-notes/0.3.0.md:2: 
  ...
  docs/release-notes/0.3.0.md:8: 
  docs/release-notes/0.3.0.md:9: - 新增 `gateways/zgate` —— 一个 Go 二进制监听 `127.0.0.1:7871`，四组模型照旧填空，`provider_config.json` 不用改。
  docs/release-notes/0.3.0.md:10: - 变更 分流方式 —— 按 `model-alias-map.json` 把显示名还原到上游；文件改了自动热加载，不用重启。
  docs/release-notes/0.3.0.md:11: - 新增 子进程托管 —— 两个网关都**随用随拉**：首个请求时拉起，空闲 5 分钟回收，平时一个都不占。
  ...
  docs/release-notes/0.3.0.md:13: - 调整 内存占用 —— 从 4 个进程 293 MB 降到 3 个进程约 99 MB；只留入口时约 19 MB。
  docs/release-notes/0.3.0.md:14: - 调整 无窗自启 —— zgate 按 GUI 子系统构建：登录自启零窗口、无乱码，日志只落文件；终端里 `status` 照常输出。
  docs/release-notes/0.3.0.md:15: - 移除 旧的 Node 路由与 PowerShell 守护器（旧路由留在 `gateways/legacy-router/` 一个版本，可回退）。
  docs/release-notes/0.3.0.md:16: 
  ...
  docs/release-notes/0.3.0.md:18: 
  docs/release-notes/0.3.0.md:19: - 变更 按两轴分层 —— 会被启动的东西进 `gateways/`，手动执行的采集/探测脚本进 `providers/`，跨供应商工具留在 `tools/`。
  docs/release-notes/0.3.0.md:20: - 变更 上游位置 —— `gateways/upstream/workbuddy`、`gateways/upstream/qoder`（仍是独立 clone，整目录不入库）。
  docs/release-notes/0.3.0.md:21: - 调整 文档与模板里的全部路径；新增 [docs/ARCHITECTURE.md](https://github.com/MVennn/ZcodeAIModels/blob/main/docs/ARCHITECTURE.md) 记录这次改造。
  ...
  docs/release-notes/0.3.0.md:24: 
  docs/release-notes/0.3.0.md:25: - 新增 冒烟测试 `gateways/zgate/smoke_test.py` —— 四条通道 + 两种桥 + 流式各打一发，返回 PASS/FAIL。
  docs/release-notes/0.3.0.md:26: - 新增 `zgate reload` —— 改策略 / 空闲阈值 / 签到窗口不用重启（key 与上游 base 也一起热加载）。
  docs/release-notes/0.3.0.md:27: - 调整 CI —— 增加 Go 格式、构建与单元测试。
  ...
  docs/release-notes/0.3.0.md:45: > 脚本会改你自己的 ZCode 配置文件，写前自动备份到同目录的 .bak-* 文件。
  docs/release-notes/0.3.0.md:46: > 升级后如果入口没起，运行 `gateways/zgate/zgate.exe status` 看状态，或 `zgate.exe install` 重建登录自启。
  docs/release-notes/0.3.0.md:47: > 模型价格、额度、倍率与可用性以服务商当时的说明为准；文档里的数字是快照，会过时。
  docs/release-notes/0.3.0.md:48: 
```
### docs/release-notes/0.4.0.md
```text
  ...
  docs/release-notes/0.4.0.md:1: **zgate 的构建只剩一条命令，编译完当场校验产物是不是无窗版。**
  docs/release-notes/0.4.0.md:2: 
  ...
  docs/release-notes/0.4.0.md:8: 
  docs/release-notes/0.4.0.md:9: - 新增 构建脚本 `gateways/zgate/build.py` —— 一条命令完成构建与校验；产物不是无窗版就直接报错退出，不会流到开机自启。
  docs/release-notes/0.4.0.md:10: - 新增 产物校验 —— `--check` 随时确认当前 `zgate.exe` 是不是无窗版；`--cross-check` 在临时目录另编一份再验，CI 与 Linux 上都能跑。
  docs/release-notes/0.4.0.md:11: - 调整 构建方式 —— `docs/MAINTENANCE.md` 的构建命令正本改为 `python gateways/zgate/build.py`；原有的 `go build` 命令仍然可用。
  docs/release-notes/0.4.0.md:12: 
  ...
  docs/release-notes/0.4.0.md:14: 
  docs/release-notes/0.4.0.md:15: - 修复 无窗构建被顶掉 —— 在 `gateways/zgate/` 里误跑单包 `go build .` 会把无窗版覆盖成控制台版、开机弹 cmd 窗口；现在构建走 `build.py`，产物当场校验。
  docs/release-notes/0.4.0.md:16: - 修复 误判归因 —— 「`go build ./...` 会覆盖产物」的说法不准确：多包模式只编译不落盘，真正会覆盖的是单包 `go build .`；文档已订正。
  ...
  docs/release-notes/0.4.0.md:27: > 脚本会改你自己的 ZCode 配置文件，写前自动备份到同目录的 .bak-* 文件。
  docs/release-notes/0.4.0.md:28: > 模型价格、额度、倍率与可用性以服务商当时的说明为准；文档里的数字是快照，会过时。
  docs/release-notes/0.4.0.md:29: 
```
### docs/release-notes/0.5.0.md
```text
  ...
  docs/release-notes/0.5.0.md:1: **zgate 支持每跳自己的出口（分步代理链），地区受限的 403 自动换机场兜底跳；传输层瞬时失败重试同一跳。**
  docs/release-notes/0.5.0.md:2: 
  ...
  docs/release-notes/0.5.0.md:6: 
  docs/release-notes/0.5.0.md:7: **zgate 路由与链路**
  docs/release-notes/0.5.0.md:8: 
  ...
  docs/release-notes/0.5.0.md:23: > 脚本会改你自己的 ZCode 配置文件，写前自动备份到同目录的 .bak-* 文件。
  docs/release-notes/0.5.0.md:24: > 模型价格、额度、倍率与可用性以服务商当时的说明为准；文档里的数字是快照，会过时。
  docs/release-notes/0.5.0.md:25: 
```
### docs/release-notes/0.6.0.md
```text
  ...
  docs/release-notes/0.6.0.md:1: **WB 永远链首与模型同步护栏落地，dsh_sync 429 快速失败，模型同步改由 Windows 计划任务驱动。**
  docs/release-notes/0.6.0.md:2: 
  ...
  docs/release-notes/0.6.0.md:8: 
  docs/release-notes/0.6.0.md:9: - 调整 tools/model_alias.py —— 排序键第一维改 WB_FIRST_CHANNELS，WB 永远第一消费来源、不看价格；DEMOTE_HOPS 常量与排序分支整段删除，限流改由 zgate 逐跳回落。
  docs/release-notes/0.6.0.md:10: - 调整 tools/model_alias.py —— 省钱组按厂商自动补位，新厂商 / 新一代 <=0.11 自动收录；Qoder 倍率落 providers/qoder/cache/qd_prices.json 快照，8790 停着时不再丢定价。
  docs/release-notes/0.6.0.md:11: - 修复 gateways/zgate/internal/router/router.go —— 客户端取消后不再重试同一跳，取消的请求不再多打一次上游。
  docs/release-notes/0.6.0.md:12: - 修复 providers/workbuddy/workbuddy_fetch_pricing.py —— 价格表骤降时逐个探活，只删确认下架的型号。
  ...
  docs/release-notes/0.6.0.md:15: 
  docs/release-notes/0.6.0.md:16: - 调整 tools/dsh_sync.py —— 注入 429 快速失败 retryPolicy，防止每日同步冲掉手改。
  docs/release-notes/0.6.0.md:17: - 新增 providers/opencode-go/ops/go_model_sync.py —— 三道护栏（清单残缺保护、目录差额提示、api 形状防御）；新增候选只认实时 /models，不再把过期文档表的型号当新模型。
  docs/release-notes/0.6.0.md:18: - 调整 sync-models.ps1、sync-models.vbs —— 模型同步改由 Windows 计划任务驱动；去掉逐个模型的探测请求，改纯上游清单驱动。
  docs/release-notes/0.6.0.md:19: - 新增 providers/qoder/qoder_zcode_sync.py、providers/workbuddy/workbuddy_zcode_sync.py —— 按上游声明自动写思考档位，18 个模型里 10 个可真实调档。
  ...
  docs/release-notes/0.6.0.md:24: - 新增 tests/test_model_alias_hop_order.py —— 钉住 WB 打头、QW 与机场孪生跳在链尾、DEMOTE_HOPS 属性不存在，全量 44 用例通过。
  docs/release-notes/0.6.0.md:25: - 新增 tests/test_dsh_sync_retry_policy.py、tests/test_go_sync_list_only.py —— 钉住 429 快速失败与纯清单驱动契约。
  docs/release-notes/0.6.0.md:26: 
  ...
  docs/release-notes/0.6.0.md:29: > 脚本会改你自己的 ZCode 配置文件，写前自动备份到同目录的 .bak-* 文件。
  docs/release-notes/0.6.0.md:30: > 模型价格、额度、倍率与可用性以服务商当时的说明为准；文档里的数字是快照，会过时。
  docs/release-notes/0.6.0.md:31: 
```
### docs/release-notes/README.md
```text
  ...
  docs/release-notes/README.md:49: 
  docs/release-notes/README.md:50: > 脚本会改你自己的 ZCode 配置文件（写前自动备份）。模型价格与额度以服务商当时的说明为准。
  docs/release-notes/README.md:51: ```
  ...
  docs/release-notes/README.md:154: > 脚本会改你自己的 ZCode 配置文件，写前自动备份到同目录的 .bak-* 文件。
  docs/release-notes/README.md:155: > 模型价格、额度、倍率与可用性以服务商当时的说明为准；文档里的数字是快照，会过时。
  docs/release-notes/README.md:156: ```
```
### memories/MEMORY.md
```text
  ...
  memories/MEMORY.md:15: - [zcode-ui-ordering-preferences](zcode-ui-ordering-preferences.md) — 用户对模型/策略组列表的命名与排序偏好：自建标签用两字中文、不加 emoji、常用的排最前、模型按厂商分组
  memories/MEMORY.md:16: - [zgate-windowless-build](zgate-windowless-build.md) — zgate 必须按 GUI 子系统编译（PE `Subsystem`=2）；构建入口只有 `gateways/zgate/build.py`，别裸跑单包 `go build .`（会覆盖成控制台版）；agent 会话里起 zgate 只有 explorer 拉起能活
  memories/MEMORY.md:17: 
```
### memories/README.md
```text
  ...
  memories/README.md:3: > **一句话**：这里放**只靠读代码和文档读不出来的事实** —— 踩过的坑、根因、实测结论；
  memories/README.md:4: > 它是 dsh-mnemon 中「项目记忆：ModelBus」Document 的**随 git 版本化快照**，可 diff、可回溯。
  memories/README.md:5: 
  ...
  memories/README.md:7: 
  memories/README.md:8: - 长期记忆正本在 `~/.mnemon`（dsh-mnemon Documents，一篇一仓、按项目归篇）；全局共享教训归 `_shared` 篇。
  memories/README.md:9: - 路由表与按需加载口径见 `~/.dsh/skills/on-demand/DOCUMENTS-ROUTING.md`；热条目只留「结论 + 指针」。
  memories/README.md:10: - 记忆与代码/实测冲突时**以代码为准**，并回写记忆；改完跑 `node ~/.dsh/tools/check-memory-hygiene.mjs`。
  memories/README.md:11: 
```
### memories/answer-first-preference.md
```text
  ...
  memories/answer-first-preference.md:11: 
  memories/answer-first-preference.md:12: **Why**：用户要的是结论本身；长时间后台探测/反复验证会让他干等，而问题往往他自己已经解决。
  memories/answer-first-preference.md:13: 
```
### memories/beam-free-thinking-param-fix.md
```text
  ...
  memories/beam-free-thinking-param-fix.md:26: 
  memories/beam-free-thinking-param-fix.md:27: **当前状态（2026-10-19 22:32 已应用）**：`provider_config.json` 的 beam-free 条目已有 `optionSpecs.reasoningLevel.map = "{}"`，备份 `provider_config.json.bak-beamfix-20261019143257`。用户随后重启了 ZCode。若以后配置被重置，重跑 `node ~/.zcode/v2/apply-beam-fix.js --apply`（脚本幂等，已应用会直接退出）。
  memories/beam-free-thinking-param-fix.md:28: 
  memories/beam-free-thinking-param-fix.md:29: **配置热加载**：引擎的 `NodePersonalProviderConfigRepository`（`resources/glm/zcode.cjs` 的 `ohe` 类）对 `provider_config.json` 默认每 1000ms 轮询一次，外部修改会被加载；本次运行中直接改文件也未被应用覆盖。仍在 UI 改 provider 设置时避免同时外部写入（atomic update + 锁），改前照例备份。
  memories/beam-free-thinking-param-fix.md:30: 
```
### memories/opencode-go-zcode-models.md
```text
  ...
  memories/opencode-go-zcode-models.md:14: 
  memories/opencode-go-zcode-models.md:15: **价格带（≤ V4.1 Flash 或略高）**：beam-free、longcat-2.5-preview-free、minimax-m3.1-flash-free 三个 free 模型官方定价表里 Input/Output/Cached Read 全是 `Free`、月额度列写 **`Unlimited`**、"Estimated requests" 表里 5 小时/周/月三档也是 `Unlimited`（Go 与 Go Plus 都是）；但脚注逐个写 **"Free for a limited time"**——即无限的是配额不是永久供应，官方说"model list 可能随时变""usage limits may change"，没有公布截止日。官方 Tip：**"If you reach the usage limit, you can continue using the free models"**——付费额度全用光后还能靠 free 模型续命，free 组是兜底不是补充。**2026-10-20 00:53 复核官方页面**：M3.1 Flash Free 仍是 Free/Free/Free + 月额度 `Unlimited`，Estimated requests 5h/周/月三档全 `Unlimited`（Go 与 Go Plus 一致）→ 官方口径下"额度无限"，但脚注仍是 "Free for a limited time"（无截止日）。models 页明写它**零保留、不用于训练**；官方弃用表里**没有**它 = 未公布退役日。Console 通用页另有更多 free 模型（glm-5.3-flash-free、deepseek-v4.1-flash-free、exo-free、mimo-v2.5/v2.6-flash-free、nemotron 3 ultra/3.5 系列、big-pickle、ll-alpha-free、jev-1.13-free），但 Go 套餐表只承认 3 个 free。地区限制名单（安哥拉/白俄/柬埔寨/**中国含港澳**/古巴/伊朗/伊拉克/老挝/利比亚/尼日利亚/朝鲜/俄罗斯/叙利亚/土库曼/乌兹别克/委内瑞拉+乌克兰三州）**只挂在 Beam Free 头上**，M3.1 Flash Free 和 LongCat 2.5 Preview Free 无地区排除；但整个 Go 服务"主要面向国际用户"，直连中国出口会 403 `unsupported_country_region_territory`（见 [[shellcrash-ai-routing-fix]]）。free 模型没有公布 RPM/并发数，只有"traffic is monitored for abuse"的口径。官方价表解析入口 `https://opencode.ai/v2/docs/console/go/`（HTML），请求估算表在同页 "Estimated requests" 段。MiMo 系列 $0.14/$0.28；GLM-5.3-Flash $0.15/$0.50；Qwen3.8 Flash $0.15/$0.47；Space Bunny $0.15/$0.60；Hy3 $0.14/$0.58；DeepSeek V4.1 Flash $0.15–0.30/$0.60–1.20；MiniMax M3、LongCat-2.0 $0.30/$1.20；GPT-6-Luna $0.10/$0.50；Claude Haiku 5.5 $0.10/$0.50；GPT-5.6-Luna $0.20/$1.20；Qwen3.7 Plus $0.40/$1.60。
  memories/opencode-go-zcode-models.md:16: 
  ...
  memories/opencode-go-zcode-models.md:36: 
  memories/opencode-go-zcode-models.md:37: baseUrl 均为 `https://opencode.ai/zen/go/v1`（三种路径都实测可用）。`opencode-go-chat` 这个 providerId 必须保留（当前会话的默认模型挂在它下面）。改配置前先备份为 `provider_config.json.bak-YYYYMMDD-HHMMSS`。引擎对 `provider_config.json` 默认每 1s 轮询热加载（`NodePersonalProviderConfigRepository`，`pollingIntervalMs` 默认 1000），外部编辑通常无需重启；若模型选择器没刷新再重启 ZCode。避免在 UI 改 provider 设置的同时外部写文件（原子写竞态）。19/19 模型按各自协议实测 HTTP 200。ZCode 是 opencode 官方 listed validated client。
  memories/opencode-go-zcode-models.md:38: 
  ...
  memories/opencode-go-zcode-models.md:69: - 收藏门限：输出单价 ≤ $1.60（现有配置里最贵的 qwen3.7-plus）；主力组人工精选不自动进；价格查不到的模型只列候选。
  memories/opencode-go-zcode-models.md:70: - **定时任务能不能指定模型**：`automations` 表有 `model/provider/mode/thought_level/model_selection` 字段，但 **CronCreate 工具入参没有 model**，会自动继承"创建时那个会话"的模型；**CronUpdate 明确不能改 model/provider/mode/thought_level**，只能改标题/提示词/时间。实测本次继承到 `opencode-go-chat-free/minimax-m3.1-flash-free`（免费模型，正好零成本）。另外同一会话内**第二次 CronCreate 会被拒**（"session that already belongs to a scheduled task"），需先用 CronUpdate 改现有任务。
  memories/opencode-go-zcode-models.md:71: - **Agent 固定模型**（原生支持）：agent 目录 = 用户级 `~/.zcode/agents/` + 项目级 `<工作区>\.zcode\agents\`；frontmatter 支持 `model:`（如 `model: opencode-go-chat/deepseek-v4.1-flash`）、`thoughtLevel`、`tools`。这是"按用途分模型"零延迟的官方做法。
```
### memories/workbuddy-proxy-zcode.md
```text
  ...
  memories/workbuddy-proxy-zcode.md:25: - **积分倍率 = 上游 `credits` 字段**（`x0.11` 这种，`/panel/api/models` 返回）；
  memories/workbuddy-proxy-zcode.md:26:   `promo_credits` 是生效价（限时免费/夜间折扣），`promo_label` 说明。**牌价 = 生效价 = 0**
  memories/workbuddy-proxy-zcode.md:27:   的才是真免费。cn:hy3（限时免费）、cn:step-5-preview（独家限免）、
  ...
  memories/workbuddy-proxy-zcode.md:39:   `no_healthy_account` 冷却，连网关进程都一度消失。探测间隔必须 ≥20 秒。
  memories/workbuddy-proxy-zcode.md:40: - `/panel/api/models` 在网关**刚重启时**只返回 34 个 global 模型，重启完成后才返回全部 56 个
  memories/workbuddy-proxy-zcode.md:41:   （cn 22 + global 34）→ 脚本要能容忍列表缺失，或先确认网关已热身完。
  ...
  memories/workbuddy-proxy-zcode.md:57:   那边 minimax-m3 拒 `thinking:{type:"enabled"}`，这边 CodeBuddy 上游接受）。
  memories/workbuddy-proxy-zcode.md:58: - ZCode 热加载 `provider_config.json`（~1s 轮询）——改完无需重启，用 `ListModels` 工具
  memories/workbuddy-proxy-zcode.md:59:   即可确认新 provider 是否已生效。
  memories/workbuddy-proxy-zcode.md:60: 
```
### memories/zcode-open-source-upstream.md
```text
  ...
  memories/zcode-open-source-upstream.md:26: - 合并语义 `overlayValue(base,next) = next===undefined ? base : next`（后者胜、undefined 不清空、null 清空、数组整体替换）
  memories/zcode-open-source-upstream.md:27: - `apiTypeMatch` **缺省时对所有 api type 生效**（provider-site 里有 4 条这样）
  memories/zcode-open-source-upstream.md:28: - `map` 表达式的作用域只有 `reasoningLevel` 与 `maxOutputTokens` 两个自由变量
  ...
  memories/zcode-open-source-upstream.md:37:    "看起来没改"其实每个字节都不同。要拿原始 blob 就用
  memories/zcode-open-source-upstream.md:38:    `https://codeload.github.com/<owner>/<repo>/tar.gz/<sha>`（服务端无转换），
  memories/zcode-open-source-upstream.md:39:    或 `git -c core.autocrlf=false archive`。CRLF 的上游 shell 脚本拷到路由器会直接报错。
  memories/zcode-open-source-upstream.md:40: 3. `mihomo` 的许可是 **MIT**（`Copyright 2023 KT`），不是 GPL-3.0；
  memories/zcode-open-source-upstream.md:41:    `jucase/ShellCrash` **不存在**，真实上游是 `juewuy/ShellCrash`；
  memories/zcode-open-source-upstream.md:42:    `ACL4SSR` 是 **CC BY-SA 4.0**（→ GPL-3.0 单向兼容，但 share-alike 独立生效）。
  memories/zcode-open-source-upstream.md:43: 
```
### memories/zgate-windowless-build.md
```text
  ...
  memories/zgate-windowless-build.md:1: # zgate 无窗产物的构建与守护
  memories/zgate-windowless-build.md:2: 
  memories/zgate-windowless-build.md:3: > **一句话**：zgate 必须按 GUI 子系统编译（`-H windowsgui`），构建入口只有
  memories/zgate-windowless-build.md:4: > `gateways/zgate/build.py`；别在 `gateways/zgate/` 里裸跑单包 `go build .` ——
  memories/zgate-windowless-build.md:5: > 它会把无窗版原地覆盖成控制台版，开机弹 cmd 窗口。
  ...
  memories/zgate-windowless-build.md:11: | 无窗与否取决于 PE 头的 `Subsystem` | `2` = WINDOWS_GUI（无窗，设计要求）；`3` = CONSOLE（一启动就分配控制台窗口） |
  memories/zgate-windowless-build.md:12: | `-H windowsgui` 只在链接期生效 | 事后无法从源码判断，只能读产物 PE 头 → 所以编译后必须当场校验 |
  memories/zgate-windowless-build.md:13: | 回退真凶是**单包** `go build .` | 实测：`go build ./...`（多包）只编译不落盘、**不会**覆盖；`go build .`（单包）会原地覆盖 |
  memories/zgate-windowless-build.md:14: | 产物在 `.gitignore` 里 | `/gateways/zgate/*.exe` → 被覆盖后 **`git checkout` 救不回来**，只能带 flag 重编 |
  memories/zgate-windowless-build.md:15: | 快捷方式 `WindowStyle = 7` 不管用 | 「最小化」只对有窗口的程序有效，对控制台子系统程序**不等于隐藏** |
  memories/zgate-windowless-build.md:16: | 唯一构建入口 | `python gateways/zgate/build.py`（带 flag + 强制校验）；`--check` 只校验；`--cross-check` 交叉编译校验（Linux CI 上也生效，因为 `-H` 是 windows 链接器 flag） |
  memories/zgate-windowless-build.md:17: 
  memories/zgate-windowless-build.md:18: ## agent 会话里起 zgate：只有 explorer 拉起能活
  memories/zgate-windowless-build.md:19: 
  memories/zgate-windowless-build.md:20: Windows **Job Object 会在 agent 会话结束时回收整棵进程树**。
  memories/zgate-windowless-build.md:21: 实测 `nohup` / `setsid` / `Start-Process` 起的 zgate 都会随会话消失；
  memories/zgate-windowless-build.md:22: 日志里表现为 `已启动` 之后**连「已退出」都没有**（被强杀，不是自己退的）。
  ...
  memories/zgate-windowless-build.md:24: 活下来的办法：**用 explorer 拉起启动文件夹快捷方式**，父进程是 `explorer.exe`，
  memories/zgate-windowless-build.md:25: 与登录自启同一条路径：
  memories/zgate-windowless-build.md:26: 
  memories/zgate-windowless-build.md:27: ```
  memories/zgate-windowless-build.md:28: Start-Process explorer.exe -ArgumentList '"<启动文件夹>\ModelBus zgate.lnk"'
  memories/zgate-windowless-build.md:29: ```
  memories/zgate-windowless-build.md:30: 
  memories/zgate-windowless-build.md:31: 长期驻留靠**登录自启快捷方式**（`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\`），
  memories/zgate-windowless-build.md:32: 不要靠 agent 起的进程。
  memories/zgate-windowless-build.md:33: 
  memories/zgate-windowless-build.md:34: ## 自启三层与被 dsh 重启连带杀死（2026-11-06 实测）
  memories/zgate-windowless-build.md:35: 
  ...
  memories/zgate-windowless-build.md:37: |---|---|
  memories/zgate-windowless-build.md:38: | 自启是**三层**，不是一层 | ① 启动文件夹 `ModelBus zgate.lnk`（Target=zgate.exe，Args=serve）；② 计划任务 `ModelBus-zgate`（LogonTrigger + PT30S）；③ 看门狗 `ModelBus-zgate-watchdog`（每 5 分钟，2026-11-06 已改 **PT1M**，动作 wscript → ensure-zgate.ps1） |
  memories/zgate-windowless-build.md:39: | 自启只在**登录那一刻**触发一次 | 它不是守护进程。登录之后任何一次「会话内 Start-Process / start-zgate.bat / swap-zgate.ps1」起的 zgate 都会顶替它，父链落到 dsh 的 Job Object 里 |
  memories/zgate-windowless-build.md:40: | dsh 重启为什么连坐 | dsh 退出时 TerminateJobObject 终止整棵子进程树；实测 13:27 被杀的那台，是 11:49 在会话里手工起的，不是 lnk 起的 |
  memories/zgate-windowless-build.md:41: | 自愈实测 | 13:30:46 看门狗拉起（13:30:49 日志「已启动」）；手动 Stop-Process 后 25s 由看门狗拉回。新 zgate 父进程是 Task Scheduler 下的 powershell，随后成孤儿，与 dsh 无关 |
  memories/zgate-windowless-build.md:42: | 结论 | 只要 zgate 由**登录自启 / 计划任务 / 看门狗**产生，重启 dsh 杀不到它；由会话产生就会陪葬 |
  memories/zgate-windowless-build.md:43: | 禁 | 会话里禁止 `Start-Process zgate.exe`、`start-zgate.bat`、`swap-zgate.ps1`。需要它起来用 `schtasks /run /tn ModelBus-zgate`（父链走 Task Scheduler）或等看门狗 |
  memories/zgate-windowless-build.md:44: | 秒级守护（尽力而为） | `%LOCALAPPDATA%\ZCodeGateway\zgate-daemon.ps1` + HKCU Run 键 `ModelBus-zgate-daemon`，登录时由 explorer 拉起、10s 轮询；实测该脚本从无控制台上下文（WMI Create / EncodedCommand）启动会秒退，只有交互式登录态能常驻，故看门狗仍是兜底。**2026-11-09 已移除**（HKCU Run 值删除 + 进程杀掉），见下节 |
  memories/zgate-windowless-build.md:45: 
  memories/zgate-windowless-build.md:46: ## 2026-11-09 自启收敛：弹窗来源与现行结构
  memories/zgate-windowless-build.md:47: 
  ...
  memories/zgate-windowless-build.md:53: |---|---|---|
  memories/zgate-windowless-build.md:54: | Windows Terminal（标题 `…\gateways\zgate\zgate.exe`，07:10:39，父 svchost=Task Scheduler） | 计划任务 `\ModelBus-zgate` 直接拉起 `zgate.exe serve`；Win11 默认终端接管其 console → 可见窗口 | 网关本体**有用**；弹窗 = 控制台版产物 + 终端接管 |
  memories/zgate-windowless-build.md:55: | 第二个实例 | HKCU Run `ZcodeAIModels-zgate-daemon`（07:11:16，父 explorer）+ 启动文件夹 `ModelBus zgate.lnk` 与计划任务重复，抢 7871 失败退出（`zgate.log` 记 `bind: Only one usage of each socket address`） | 冗余，已删 |
  memories/zgate-windowless-build.md:56: 
  memories/zgate-windowless-build.md:57: **根因**：`gateways/zgate/zgate.exe` 被裸 `go build .` 覆盖成控制台版（`build.py --check` 报 `Subsystem = 3`；
  memories/zgate-windowless-build.md:58: 10469888B / 11-06 22:55，与 `zgate-0.3.0-cand.exe` 同尺寸）。`-WindowStyle Hidden` 与 lnk 的 `WindowStyle=7`
  memories/zgate-windowless-build.md:59: 对控制台子系统程序都**不等于隐藏**，Win11 的 Windows Terminal 接管后照样可见。
  ...
  memories/zgate-windowless-build.md:64: |---|---|---|
  memories/zgate-windowless-build.md:65: | 登录自启 | 计划任务 `\ModelBus-zgate-hidden`（AtLogOn, Interactive, Limited）→ `wscript //B //Nologo launch-zgate.vbs` → `start-zgate-nw.ps1` → `CreateNoWindow` 起 `zgate.exe serve` | 否 |
  memories/zgate-windowless-build.md:66: | 兜底 | `\ModelBus-zgate-watchdog`（PT1M）→ `ensure-zgate.vbs` → 同一个 `start-zgate-nw.ps1` | 否 |
  memories/zgate-windowless-build.md:67: | 产物 | `python gateways/zgate/build.py`（强制 `Subsystem = 2`） | 否 |
  memories/zgate-windowless-build.md:68: 
  memories/zgate-windowless-build.md:69: `start-zgate-nw.ps1` 先 `Test-Up(127.0.0.1:7871, 1200ms)`：已起就写 `port already up, skip` 退出；
  memories/zgate-windowless-build.md:70: 否则 `ProcessStartInfo`(UseShellExecute=$false, CreateNoWindow=$true) 拉起并轮询 12×500ms。
  memories/zgate-windowless-build.md:71: **脚本跑完即退，不留常驻 powershell** —— 即「执行完自动杀死自己」。
  memories/zgate-windowless-build.md:72: 
  memories/zgate-windowless-build.md:73: 已删除：启动文件夹 `ModelBus zgate.lnk`、HKCU Run `ZcodeAIModels-zgate-daemon`（进程 9804 一并杀掉）、
  memories/zgate-windowless-build.md:74: 计划任务 `\ModelBus-zgate`（UAC 提权 `schtasks /Delete /F`，exit=0）。保留 `CSPPassword.ahk.lnk`
  memories/zgate-windowless-build.md:75: （itzmx 加密包自动填密码，AHK v2 无控制台）。备份/回滚：`%LOCALAPPDATA%\ZCodeGateway\autostart-backup-20261109\restore-autostart.ps1`。
  memories/zgate-windowless-build.md:76: 
  memories/zgate-windowless-build.md:77: **验证**：`wscript //B //Nologo launch-zgate.vbs` → `zgate-launch.log` 记 `port already up, skip`，
  memories/zgate-windowless-build.md:78: WindowsTerminal/OpenConsole 计数不增；`CreateNoWindow` 起 `ping -n 8` 对照实验 wt 计数 before=2 after=2。
  memories/zgate-windowless-build.md:79: 首次真实开机验证在下次登录：当前可见的 wt pid 10264 属运行中的 5388，重启后不再出现（**别关它，关了等于杀网关**）。
  memories/zgate-windowless-build.md:80: 
  ...
  memories/zgate-windowless-build.md:84: # 产物是不是无窗版
  memories/zgate-windowless-build.md:85: python gateways/zgate/build.py --check
  memories/zgate-windowless-build.md:86: 
  memories/zgate-windowless-build.md:87: # 服务在不在
  memories/zgate-windowless-build.md:88: curl -s http://127.0.0.1:7871/health
  memories/zgate-windowless-build.md:89: gateways/zgate/zgate.exe status
  memories/zgate-windowless-build.md:90: 
```

## 7. Windows 计划任务 / 服务 / Run 键 / 启动文件夹（只读取证）

命令：```text
CMD: chcp 65001>nul & schtasks /query /fo list /v
```
exitCode=0；stdout 3785 字符；原始输出 7765 行，命中 7 行，上下文 65 行
说明：上面是原始输出中与 zgate/wb2api/mihomo/gateway/ModelBus 相关的上下文片段（带原始行号）；全文共 7765 行
真实输出（stdout）：
```text
...
291: Repeat: Stop If Still Running:        Disabled
292: 
293: HostName:                             MVENN-PC
294: TaskName:                             \ModelBus 模型同步
295: Next Run Time:                        2026/11/10 12:00:00
296: Status:                               Ready
297: Logon Mode:                           Interactive only
298: Last Run Time:                        2026/11/9 12:00:01
299: Last Result:                          0
300: Author:                               MVENN-PC\SansK
301: Task To Run:                          wscript.exe //nologo F:\Project\ModelBus\sync-models.vbs
302: Start In:                             N/A
303: Comment:                              N/A
304: Scheduled Task State:                 Enabled
305: Idle Time:                            Disabled
306: Power Management:                     Stop On Battery Mode, No Start On Batteries
307: Run As User:                          SansK
308: Delete Task If Not Rescheduled:       Disabled
309: Stop Task If Runs X Hours and X Mins: 72:00:00
310: Schedule:                             Scheduling data is not available in this format.
311: Schedule Type:                        Daily 
...
320: Repeat: Stop If Still Running:        Disabled
321: 
322: HostName:                             MVENN-PC
323: TaskName:                             \ModelBus-zgate-hidden
324: Next Run Time:                        N/A
325: Status:                               Ready
326: Logon Mode:                           Interactive only
327: Last Run Time:                        2026/11/9 14:51:13
328: Last Result:                          0
329: Author:                               N/A
330: Task To Run:                          wscript.exe //B //Nologo "C:\Users\<用户名>\AppData\Local\ZCodeGateway\launch-zgate.vbs"
331: Start In:                             N/A
332: Comment:                              Launch zgate at logon with no console window (CREATE_NO_WINDOW via launch-zgate.vbs). Replaces ModelBus-zgate.
333: Scheduled Task State:                 Enabled
334: Idle Time:                            Disabled
335: Power Management:                     
336: Run As User:                          SansK
337: Delete Task If Not Rescheduled:       Disabled
338: Stop Task If Runs X Hours and X Mins: Disabled
339: Schedule:                             Scheduling data is not available in this format.
340: Schedule Type:                        At logon time
341: Start Time:                           N/A
342: Start Date:                           N/A
...
349: Repeat: Stop If Still Running:        N/A
350: 
351: HostName:                             MVENN-PC
352: TaskName:                             \ModelBus-zgate-watchdog
353: Next Run Time:                        2026/11/9 15:43:00
354: Status:                               Ready
355: Logon Mode:                           Interactive only
356: Last Run Time:                        2026/11/9 15:42:01
357: Last Result:                          0
358: Author:                               MVENN-PC\SansK
359: Task To Run:                          wscript.exe //B //Nologo C:\Users\<用户名>\AppData\Local\ZCodeGateway\ensure-zgate.vbs
360: Start In:                             N/A
361: Comment:                              N/A
362: Scheduled Task State:                 Enabled
363: Idle Time:                            Disabled
364: Power Management:                     Stop On Battery Mode, No Start On Batteries
365: Run As User:                          SansK
366: Delete Task If Not Rescheduled:       Disabled
367: Stop Task If Runs X Hours and X Mins: 72:00:00
368: Schedule:                             Scheduling data is not available in this format.
369: Schedule Type:                        One Time Only, Minute 
```

说明：`schtasks` 上面给出的是全量原始输出里与 `zgate|wb2api|mihomo|gateway|ModelBus` 相关的上下文片段（原始行号保留）；若片段为「无」表示全量输出中无相关项。`schtasks` 全部任务数由 `Get-ScheduledTask` 单独给出。

命令：```text
PowerShell -NoProfile -EncodedCommand <base64> -- script: $pat='zgate|wb2api|mihomo|gateway|ModelBus'; $all=@(Get-ScheduledTask -ErrorAction SilentlyContinue); $rel=@($all | Where-Object { $_.TaskName -match $pat -or $_.TaskPath -match $pat -or (($_.Actions | ForEach-Object { $_.Execute + ' ' + $_.Arguments }) -join ' ') -match $pat } | Select-Object TaskN
```
exitCode=0；stdout 668 字符
真实输出（stdout）：
```text
ALL_TASK_COUNT=196
[
    {
        "TaskName":  "ModelBus 模型同步",
        "TaskPath":  "\\",
        "State":  3,
        "Actions":  "wscript.exe //nologo F:\\Project\\ModelBus\\sync-models.vbs"
    },
    {
        "TaskName":  "ModelBus-zgate-hidden",
        "TaskPath":  "\\",
        "State":  3,
        "Actions":  "wscript.exe //B //Nologo \"C:\\Users\\SansK\\AppData\\Local\\ZCodeGateway\\launch-zgate.vbs\""
    },
    {
        "TaskName":  "ModelBus-zgate-watchdog",
        "TaskPath":  "\\",
        "State":  3,
        "Actions":  "wscript.exe //B //Nologo C:\\Users\\SansK\\AppData\\Local\\ZCodeGateway\\ensure-zgate.vbs"
    }
]

```
stderr：
```text
#< CLIXML
<Objs Version="1.1.0.1" xmlns="http://schemas.microsoft.com/powershell/2004/04"><Obj S="progress" RefId="0"><TN RefId="0"><T>System.Management.Automation.PSCustomObject</T><T>System.Object</T></TN><MS><I64 N="SourceId">1</I64><PR N="Record"><AV>正在准备首次使用模块。</AV><AI>0</AI><Nil /><PI>-1</PI><PC>-1</PC><T>Completed</T><SR>-1</SR><SD> </SD></PR></MS></Obj><Obj S="progress" RefId="1"><TNRef RefId="0" /><MS><I64 N="SourceId">2</I64><PR N="Record"><AV>Get-ScheduledTask -ErrorAction SilentlyContinue); $rel=@($all | Where-Object { $_.TaskName -match $pat -or $_.TaskPath -match $pat -or (($_.Actions | ForEach-Object { $_.Execute + ' ' + $_.Arguments }) -join ' ') -match $pat } | Select-Object TaskName,TaskPath,State,@{n='Actions';e={(($_.Actions | ForEach-Object { $_.Execute + ' ' + $_.Arguments }) -join '; ')}}); 'ALL_TASK_COUNT=' + $all.Count; if($rel.Count){$rel | ConvertTo-Json -Depth 5}else{'无'}</AV><AI>560143528</AI><Nil /><PI>-1</PI><PC>100</PC><T>Completed</T><SR>0</SR><SD>已完成 1/1</SD></PR></MS></Obj><Obj S="progress" RefId="2"><TNRef RefId="0" /><MS><I64 N="SourceId">1</I64><PR N="Record"><AV>正在准备首次使用模块。</AV><AI>0</AI><Nil /><PI>-1</PI><PC>-1</PC><T>Completed</T><SR>-1</SR
```

命令：```text
CMD: chcp 65001>nul & sc query state= all
```
exitCode=0；stdout 231 字符；原始输出 2935 行，命中 1 行，上下文 6 行
说明：上面是原始输出中与 zgate/wb2api/mihomo/gateway 相关的上下文片段；全文共 2935 行
真实输出（stdout）：
```text
...
56: 
57: SERVICE_NAME: ALG
58: DISPLAY_NAME: Application Layer Gateway Service
59:         TYPE               : 10  WIN32_OWN_PROCESS  
60:         STATE              : 1  STOPPED 
61:         WIN32_EXIT_CODE    : 1077  (0x435)
```

命令：```text
PowerShell -NoProfile -EncodedCommand <base64> -- script: $pat='zgate|wb2api|mihomo|gateway|ModelBus'; $s=@(Get-Service -ErrorAction SilentlyContinue | Where-Object { $_.Name -match $pat -or $_.DisplayName -match $pat }); if($s.Count){$s | Select-Object Name,DisplayName,Status,StartType | Format-Table -AutoSize | Out-String -Width 400}else{'无'}
```
exitCode=0；stdout 182 字符
真实输出（stdout）：
```text

Name DisplayName                        Status StartType
---- -----------                        ------ ---------
ALG  Application Layer Gateway Service Stopped    Manual




```
stderr：
```text
#< CLIXML
<Objs Version="1.1.0.1" xmlns="http://schemas.microsoft.com/powershell/2004/04"><Obj S="progress" RefId="0"><TN RefId="0"><T>System.Management.Automation.PSCustomObject</T><T>System.Object</T></TN><MS><I64 N="SourceId">1</I64><PR N="Record"><AV>正在准备首次使用模块。</AV><AI>0</AI><Nil /><PI>-1</PI><PC>-1</PC><T>Completed</T><SR>-1</SR><SD> </SD></PR></MS></Obj><Obj S="progress" RefId="1"><TNRef RefId="0" /><MS><I64 N="SourceId">1</I64><PR N="Record"><AV>正在准备首次使用模块。</AV><AI>0</AI><Nil /><PI>-1</PI><PC>-1</PC><T>Completed</T><SR>-1</SR><SD> </SD></PR></MS></Obj></Objs>
```

命令：```text
PowerShell -NoProfile -EncodedCommand <base64> -- script: $pat='zgate|wb2api|mihomo|gateway|ModelBus'; $keys=@('HKCU:\Software\Microsoft\Windows\CurrentVersion\Run','HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run','HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run'); $found=@(); foreach($k in $keys){ if(Test-Path $k){ $props=Get-ItemProp
```
exitCode=0；stdout 189 字符
真实输出（stdout）：
```text
SCANNED_KEYS=HKCU:\Software\Microsoft\Windows\CurrentVersion\Run | HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run | HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run
无

```
stderr：
```text
#< CLIXML
<Objs Version="1.1.0.1" xmlns="http://schemas.microsoft.com/powershell/2004/04"><Obj S="progress" RefId="0"><TN RefId="0"><T>System.Management.Automation.PSCustomObject</T><T>System.Object</T></TN><MS><I64 N="SourceId">1</I64><PR N="Record"><AV>正在准备首次使用模块。</AV><AI>0</AI><Nil /><PI>-1</PI><PC>-1</PC><T>Completed</T><SR>-1</SR><SD> </SD></PR></MS></Obj></Objs>
```

命令：```text
PowerShell -NoProfile -EncodedCommand <base64> -- script: $p=[Environment]::GetFolderPath('Startup'); 'STARTUP=' + $p; $i=Get-ChildItem -LiteralPath $p -Force -ErrorAction SilentlyContinue; if($i){$i | Select-Object Name,FullName,Length,LastWriteTime | Format-List | Out-String -Width 500}else{'无文件'}
```
exitCode=0；stdout 500 字符
真实输出（stdout）：
```text
STARTUP=C:\Users\<用户名>\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup


Name          : CSPPassword.ahk.lnk
FullName      : C:\Users\<用户名>\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\CSPPassword.ahk.lnk
Length        : 685
LastWriteTime : 2026/8/31 13:02:02

Name          : desktop.ini
FullName      : C:\Users\<用户名>\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\desktop.ini
Length        : 174
LastWriteTime : 2026/3/14 12:25:56





```
stderr：
```text
#< CLIXML
<Objs Version="1.1.0.1" xmlns="http://schemas.microsoft.com/powershell/2004/04"><Obj S="progress" RefId="0"><TN RefId="0"><T>System.Management.Automation.PSCustomObject</T><T>System.Object</T></TN><MS><I64 N="SourceId">1</I64><PR N="Record"><AV>正在准备首次使用模块。</AV><AI>0</AI><Nil /><PI>-1</PI><PC>-1</PC><T>Completed</T><SR>-1</SR><SD> </SD></PR></MS></Obj><Obj S="progress" RefId="1"><TNRef RefId="0" /><MS><I64 N="SourceId">1</I64><PR N="Record"><AV>正在准备首次使用模块。</AV><AI>0</AI><Nil /><PI>-1</PI><PC>-1</PC><T>Completed</T><SR>-1</SR><SD> </SD></PR></MS></Obj></Objs>
```

取证结论：与 `zgate / wb2api / mihomo / gateway` 相关的 Windows 服务与计划任务以 `Get-Service` / `Get-ScheduledTask` 真实输出为准；`main.go install()` 走的是「启动」文件夹快捷方式（`WScript.Shell`）而非 `schtasks / sc create / NSSM`，因此必须同时看启动文件夹 `Get-ChildItem` 输出。`sync-models.vbs:3-5` 自述「计划任务的动作指向本文件（wscript.exe）」指向的是**模型同步**任务，不是 zgate 守护。

## 8. 当前运行实况（只读，未重启）

`Get-CimInstance Win32_Process` 全量 JSON 与相关进程表：
命令：```text
PowerShell -NoProfile -EncodedCommand <base64> -- script: $pat='zgate|wb2api|mihomo|qoder|cli-proxy|python|node|cmd.exe|powershell|conhost|dsh|explorer|wscript'; Get-CimInstance Win32_Process | Where-Object { $_.Name -match $pat } | Select-Object Name,ProcessId,ParentProcessId,CreationDate,ExecutablePath,CommandLine | Format-Table -AutoSize | Out-String -W
```
exitCode=0；stdout 29492 字符
真实输出（stdout）：
```text

Name           ProcessId ParentProcessId CreationDate       ExecutablePath                                                                                                                  CommandLine                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     
----           --------- --------------- ------------       --------------                                                                                                                  -----------                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     
explorer.exe        8292            8180 2026/11/9 14:51:13 C:\WINDOWS\Explorer.EXE                                                                                                         C:\WINDOWS\Explorer.EXE                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         
conhost.exe        15984           15976 2026/11/9 14:51:23 C:\WINDOWS\system32\conhost.exe                                                                                                 \??\C:\WINDOWS\system32\conhost.exe 0x4                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         
zgate.exe           5508           15976 2026/11/9 14:51:32 F:\Project\ModelBus\gateways\zgate\zgate.exe                                                                                    "F:\Project\ModelBus\gateways\zgate\zgate.exe" serve                                                                                                                                                                                                                                                                                                                                                                                                                                                                            
node.exe            5408           18548 2026/11/9 14:51:46 C:\Program Files\nodejs\node.exe                                                                                                "C:\Program Files\nodejs\node.exe" C:\Users\<用户名>\.dsh\profiles\desktop\node_modules\billion-context\dist\index.js start --host 127.0.0.1 --port 18787                                                                                                                                                                                                                                                                                                                                                                          
cncmd.exe           2744           17372 2026/11/9 14:51:56 C:\Program Files\AMD\CNext\CNext\cncmd.exe                                                                                      "C:\Program Files\AMD\CNext\CNext\cncmd.exe" watch 17372                                                                                                                                                                                                                                                                                                                                                                                                                                                                        
cmd.exe            19504           14460 2026/11/9 14:51:57 C:\WINDOWS\system32\cmd.exe                                                                                                     "C:\WINDOWS\system32\cmd.exe" /C "C:\Program Files\AMD\CNext\CNext\AMDRSServ.exe"                                                                                                                                                                                                                                                                                                                                                                                                                                               
conhost.exe        19528           19504 2026/11/9 14:51:57 C:\WINDOWS\system32\conhost.exe                                                                                                 \??\C:\WINDOWS\system32\conhost.exe 0x4                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         
wb2api.exe         22408            5508 2026/11/9 14:53:09 F:\Project\ModelBus\gateways\upstream\workbuddy\wb2api.exe                                                                      F:\Project\ModelBus\gateways\upstream\workbuddy\wb2api.exe -config F:\Project\ModelBus\gateways\upstream\workbuddy\config.json                                                                                                                                                                                                                                                                                                                                                                                                  
conhost.exe        22252           22408 2026/11/9 14:53:10 C:\WINDOWS\system32\conhost.exe                                                                                                 \??\C:\WINDOWS\system32\conhost.exe 0x4                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         
conhost.exe        11092           27388 2026/11/9 15:21:06 C:\WINDOWS\system32\conhost.exe                                                                                                 \??\C:\WINDOWS\system32\conhost.exe 0x4                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         
conhost.exe        26532           28404 2026/11/9 15:21:09 C:\WINDOWS\system32\conhost.exe                                                                                                 \??\C:\WINDOWS\system32\conhost.exe 0x4                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         
explorer.exe       30684            1996 2026/11/9 15:34:27 C:\WINDOWS\explorer.exe                                                                                                         C:\WINDOWS\explorer.exe /factory,{75dff2b7-6936-4c06-a8bb-676a7b00b24b} -Embedding                                                                                                                                                                                                                                                                                                                                                                                                                                              
cmd.exe            11680           32228 2026/11/9 15:42:56 C:\WINDOWS\system32\cmd.exe                                                                                                     cmd.exe /c "codegraph status"                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   
conhost.exe         2556           11680 2026/11/9 15:42:56 C:\WINDOWS\system32\conhost.exe                                                                                                 \??\C:\WINDOWS\system32\conhost.exe 0x4                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         
powershell.exe     31532           32228 2026/11/9 15:42:56 C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe                                                                       C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -EncodedCommand JABFAHIAcgBvAHIAQQBjAHQAaQBvAG4AUAByAGUAZgBlAHIAZQBuAGMAZQA9ACcAQwBvAG4AdABpAG4AdQBlACcAOwAgAFsAQwBvAG4AcwBvAGwAZQBdADoAOgBPAHUAdABwAHUAdABFAG4AYwBvAGQAaQBuAGcAPQBbAFMAeQBzAHQAZQBtAC4AVABlAHgAdAAuAEUAbgBjAG8AZABpAG4AZwBdADoAOgBVAFQARgA4ADsAIAAkAE8AdQB0AHAAdQB0AEUAbgBjAG8AZABpAG4AZwA9AFsAUwB5AHMAdABlAG0ALgBUAGUAeAB0AC4ARQBuAGMAbwBkAGkAbgBnAF0AOgA6AFUAVABGADgAOwAgACQAcgBvAG8AdAA9ACcARgA6AFwAUAByAG8A...
node.exe           27336           11680 2026/11/9 15:42:56 C:\Program Files\nodejs\node.exe                                                                                                "node"   "C:\Users\<用户名>\AppData\Roaming\npm\\node_modules\@colbymchenry\codegraph\npm-shim.js" status                                                                                                                                                                                                                                                                                                                                                                                                                          
conhost.exe        23380           31532 2026/11/9 15:42:56 C:\WINDOWS\system32\conhost.exe                                                                                                 \??\C:\WINDOWS\system32\conhost.exe 0x4                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         
powershell.exe     26976           32228 2026/11/9 15:42:56 C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe                                                                       C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -EncodedCommand JABFAHIAcgBvAHIAQQBjAHQAaQBvAG4AUAByAGUAZgBlAHIAZQBuAGMAZQA9ACcAQwBvAG4AdABpAG4AdQBlACcAOwAgAFsAQwBvAG4AcwBvAGwAZQBdADoAOgBPAHUAdABwAHUAdABFAG4AYwBvAGQAaQBuAGcAPQBbAFMAeQBzAHQAZQBtAC4AVABlAHgAdAAuAEUAbgBjAG8AZABpAG4AZwBdADoAOgBVAFQARgA4ADsAIAAkAE8AdQB0AHAAdQB0AEUAbgBjAG8AZABpAG4AZwA9AFsAUwB5AHMAdABlAG0ALgBUAGUAeAB0AC4ARQBuAGMAbwBkAGkAbgBnAF0AOgA6AFUAVABGADgAOwA
```
stderr：
```text
#< CLIXML
<Objs Version="1.1.0.1" xmlns="http://schemas.microsoft.com/powershell/2004/04"><Obj S="progress" RefId="0"><TN RefId="0"><T>System.Management.Automation.PSCustomObject</T><T>System.Object</T></TN><MS><I64 N="SourceId">1</I64><PR N="Record"><AV>正在准备首次使用模块。</AV><AI>0</AI><Nil /><PI>-1</PI><PC>-1</PC><T>Completed</T><SR>-1</SR><SD> </SD></PR></MS></Obj><Obj S="progress" RefId="1"><TNRef RefId="0" /><MS><I64 N="SourceId">2</I64><PR N="Record"><AV>正在准备首次使用模块。</AV><AI>0</AI><Nil /><PI>-1</PI><PC>-1</PC><T>Completed</T><SR>-1</SR><SD> </SD></PR></MS></Obj></Objs>
```

`Get-CimInstance Win32_Process` 全量 JSON（用于派生父进程链，原样保留）：
```text
[{"Name":"System Idle Process","ProcessId":0,"ParentProcessId":0,"CommandLine":null,"CreationDate":"\/Date(1794207063205)\/","ExecutablePath":null},{"Name":"System","ProcessId":4,"ParentProcessId":0,"CommandLine":null,"CreationDate":"\/Date(1794207063205)\/","ExecutablePath":null},{"Name":"Registry","ProcessId":272,"ParentProcessId":4,"CommandLine":null,"CreationDate":"\/Date(1794207060546)\/","ExecutablePath":null},{"Name":"smss.exe","ProcessId":976,"ParentProcessId":4,"CommandLine":null,"CreationDate":"\/Date(1794207063220)\/","ExecutablePath":null},{"Name":"csrss.exe","ProcessId":1424,"ParentProcessId":1360,"CommandLine":null,"CreationDate":"\/Date(1794207068654)\/","ExecutablePath":null},{"Name":"wininit.exe","ProcessId":1688,"ParentProcessId":1360,"CommandLine":null,"CreationDate":"\/Date(1794207070464)\/","ExecutablePath":null},{"Name":"csrss.exe","ProcessId":1696,"ParentProcessId":1680,"CommandLine":null,"CreationDate":"\/Date(1794207070467)\/","ExecutablePath":null},{"Name":"winlogon.exe","ProcessId":1788,"ParentProcessId":1680,"CommandLine":null,"CreationDate":"\/Date(1794207070592)\/","ExecutablePath":null},{"Name":"services.exe","ProcessId":1808,"ParentProcessId":1688,"CommandLine":null,"CreationDate":"\/Date(1794207070608)\/","ExecutablePath":null},{"Name":"lsass.exe","ProcessId":1840,"ParentProcessId":1688,"CommandLine":null,"CreationDate":"\/Date(1794207070645)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":1996,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207070833)\/","ExecutablePath":null},{"Name":"fontdrvhost.exe","ProcessId":2028,"ParentProcessId":1788,"CommandLine":null,"CreationDate":"\/Date(1794207070848)\/","ExecutablePath":null},{"Name":"fontdrvhost.exe","ProcessId":2036,"ParentProcessId":1688,"CommandLine":null,"CreationDate":"\/Date(1794207070848)\/","ExecutablePath":null},{"Name":"WUDFHost.exe","ProcessId":2044,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207070851)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":1336,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207070938)\/","ExecutablePath":null},{"Name":"WUDFHost.exe","ProcessId":2080,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207070945)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":2152,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207070967)\/","ExecutablePath":null},{"Name":"dwm.exe","ProcessId":2276,"ParentProcessId":1788,"CommandLine":null,"CreationDate":"\/Date(1794207071043)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":2456,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207071123)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":2464,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207071124)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":2472,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207071124)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":2480,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207071125)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":2676,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207071149)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":2688,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207071150)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":2712,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207071154)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":2724,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207071154)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":2732,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207071154)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":2828,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207071162)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":2956,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207071176)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":2964,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207071176)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":2340,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207071188)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":3400,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207071250)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":3408,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207071250)\/","ExecutablePath":null},{"Name":"HipsDaemon.exe","ProcessId":3484,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207071274)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":3616,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207071313)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":3768,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207071376)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":3824,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207071472)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":4084,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207072244)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":3472,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207072397)\/","ExecutablePath":null},{"Name":"amdfendrsr.exe","ProcessId":3932,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073188)\/","ExecutablePath":null},{"Name":"atiesrxx.exe","ProcessId":3528,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073188)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":3496,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073188)\/","ExecutablePath":null},{"Name":"atieclxx.exe","ProcessId":3168,"ParentProcessId":3528,"CommandLine":null,"CreationDate":"\/Date(1794207073215)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":3248,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073230)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":4104,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073230)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":4192,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073247)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":4228,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073256)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":4276,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073285)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":4400,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073312)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":4404,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073312)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":4500,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073336)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":4556,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073353)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":4636,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073367)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":4752,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073378)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":4880,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073400)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":4936,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073410)\/","ExecutablePath":null},{"Name":"spoolsv.exe","ProcessId":5036,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073431)\/","ExecutablePath":null},{"Name":"sihost.exe","ProcessId":5056,"ParentProcessId":2956,"CommandLine":"sihost.exe","CreationDate":"\/Date(1794207073433)\/","ExecutablePath":"C:\\WINDOWS\\system32\\sihost.exe"},{"Name":"svchost.exe","ProcessId":5092,"ParentProcessId":1808,"CommandLine":"C:\\WINDOWS\\system32\\svchost.exe -k BthAppGroup -p -s BluetoothUserService","CreationDate":"\/Date(1794207073438)\/","ExecutablePath":"C:\\WINDOWS\\system32\\svchost.exe"},{"Name":"svchost.exe","ProcessId":5112,"ParentProcessId":1808,"CommandLine":"C:\\WINDOWS\\system32\\svchost.exe -k PenService -s PenService","CreationDate":"\/Date(1794207073439)\/","ExecutablePath":"C:\\WINDOWS\\system32\\svchost.exe"},{"Name":"svchost.exe","ProcessId":4176,"ParentProcessId":1808,"CommandLine":"C:\\WINDOWS\\system32\\svchost.exe -k UnistackSvcGroup -s CDPUserSvc","CreationDate":"\/Date(1794207073439)\/","ExecutablePath":"C:\\WINDOWS\\system32\\svchost.exe"},{"Name":"svchost.exe","ProcessId":5172,"ParentProcessId":1808,"CommandLine":"C:\\WINDOWS\\system32\\svchost.exe -k LocalSystemNetworkRestricted -p -s webthreatdefusersvc","CreationDate":"\/Date(1794207073449)\/","ExecutablePath":"C:\\WINDOWS\\system32\\svchost.exe"},{"Name":"svchost.exe","ProcessId":5336,"ParentProcessId":1808,"CommandLine":"C:\\WINDOWS\\system32\\svchost.exe -k UnistackSvcGroup -s WpnUserService","CreationDate":"\/Date(1794207073461)\/","ExecutablePath":"C:\\WINDOWS\\system32\\svchost.exe"},{"Name":"svchost.exe","ProcessId":5384,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073467)\/","ExecutablePath":null},{"Name":"taskhostw.exe","ProcessId":5424,"ParentProcessId":2676,"CommandLine":"taskhostw.exe {222A245B-E637-4AE9-A93F-A59CA119A75E}","CreationDate":"\/Date(1794207073473)\/","ExecutablePath":"C:\\WINDOWS\\system32\\taskhostw.exe"},{"Name":"ARPProtection.exe","ProcessId":5580,"ParentProcessId":2676,"CommandLine":null,"CreationDate":"\/Date(1794207073485)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":5728,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073489)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":5764,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073490)\/","ExecutablePath":null},{"Name":"AIService.exe","ProcessId":5824,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073492)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":5856,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073495)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":5872,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073496)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":5896,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073496)\/","ExecutablePath":null},{"Name":"micont_service.exe","ProcessId":5912,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073497)\/","ExecutablePath":null},{"Name":"AmdPpkgSvc.exe","ProcessId":5920,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073498)\/","ExecutablePath":null},{"Name":"MiPlayCastService.exe","ProcessId":5928,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073498)\/","ExecutablePath":null},{"Name":"XiaomiService.exe","ProcessId":5940,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073499)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":5948,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073499)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":5956,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073499)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":5964,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073499)\/","ExecutablePath":null},{"Name":"MiRemoteDeskService.exe","ProcessId":5980,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073500)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":5988,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073501)\/","ExecutablePath":null},{"Name":"MAFSvr.exe","ProcessId":6072,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073506)\/","ExecutablePath":null},{"Name":"DistributedService.exe","ProcessId":6088,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073507)\/","ExecutablePath":null},{"Name":"dist_service.exe","ProcessId":6108,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073507)\/","ExecutablePath":null},{"Name":"qcmtusvc.exe","ProcessId":5484,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073508)\/","ExecutablePath":null},{"Name":"handoff_svc.exe","ProcessId":5448,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073509)\/","ExecutablePath":null},{"Name":"MiDeviceService.exe","ProcessId":5656,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073510)\/","ExecutablePath":null},{"Name":"MsMpEng.exe","ProcessId":6148,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073510)\/","ExecutablePath":null},{"Name":"wallpaperservice32.exe","ProcessId":6156,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073510)\/","ExecutablePath":null},{"Name":"MpDefenderCoreService.exe","ProcessId":6172,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073510)\/","ExecutablePath":null},{"Name":"MiService.exe","ProcessId":6184,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073511)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":6216,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073514)\/","ExecutablePath":null},{"Name":"XiaomiHost.exe","ProcessId":6680,"ParentProcessId":5940,"CommandLine":null,"CreationDate":"\/Date(1794207073555)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":6964,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073583)\/","ExecutablePath":null},{"Name":"svchost.exe","ProcessId":6972,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073584)\/","ExecutablePath":null},{"Name":"AIBroker.exe","ProcessId":6980,"ParentProcessId":5824,"CommandLine":null,"CreationDate":"\/Date(1794207073584)\/","ExecutablePath":null},{"Name":"ctfmon.exe","ProcessId":7656,"ParentProcessId":2340,"CommandLine":null,"CreationDate":"\/Date(1794207073688)\/","ExecutablePath":null},{"Name":"TabTip.exe","ProcessId":7736,"ParentProcessId":2340,"CommandLine":null,"CreationDate":"\/Date(1794207073706)\/","ExecutablePath":null},{"Name":"wlanext.exe","ProcessId":7952,"ParentProcessId":4880,"CommandLine":null,"CreationDate":"\/Date(1794207073763)\/","ExecutablePath":null},{"Name":"explorer.exe","ProcessId":8292,"ParentProcessId":8180,"CommandLine":"C:\\WINDOWS\\Explorer.EXE","CreationDate":"\/Date(1794207073981)\/","ExecutablePath":"C:\\WINDOWS\\Explorer.EXE"},{"Name":"svchost.exe","ProcessId":8452,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207073992)\/","ExecutablePath":null},{"Name":"ShellHost.exe","ProcessId":8828,"ParentProcessId":5056,"CommandLine":"\"C:\\Windows\\System32\\ShellHost.exe\"","CreationDate":"\/Date(1794207074109)\/","ExecutablePath":"C:\\Windows\\System32\\ShellHost.exe"},{"Name":"svchost.exe","ProcessId":9040,"ParentProcessId":1808,"CommandLine":null,"CreationDate":"\/Date(1794207074154)\/","ExecutablePath":null},{"Name":"CrossDeviceResume.exe","ProcessId":9240,"ParentProcessId":5056,"CommandLine":"\"C:\\WINDOWS\\SystemApps\\MicrosoftWindows.Client.CBS_cw5n1h2txyewy\\CrossDeviceResume.exe\" /tileid MicrosoftWindows.Cli
```

父进程链（从全量 JSON 按 ParentProcessId 向上回溯，真实派生）：
```text
SEED zgate.exe#5508
  zgate.exe#5508(PPID=15976, Created=/Date(1794207092528)/, Cmd="F:\Project\ModelBus\gateways\zgate\zgate.exe" serve)

SEED wb2api.exe#22408
  wb2api.exe#22408(PPID=5508, Created=/Date(1794207189891)/, Cmd=F:\Project\ModelBus\gateways\upstream\workbuddy\wb2api.exe -config F:\Project\ModelBus\gateways\upstream\workbuddy\config.json)
  <- zgate.exe#5508(PPID=15976, Created=/Date(1794207092528)/, Cmd="F:\Project\ModelBus\gateways\zgate\zgate.exe" serve)

SEED CefViewWing.exe#5600
  CefViewWing.exe#5600(PPID=23868, Created=/Date(1794208869802)/, Cmd="D:/Program Files/Netease/MuMu/nx_main/CefView/CefViewWing.exe" --type=gpu-process --disable-gpu-sandbox --no-sandbox --disable-breakpad --disable-gpu-rasterization --use-angle=d3d11 --locales-dir-path="D:/Program Files/)
  <- MuMuNxMain.exe#23868(PPID=26884, Created=/Date(1794208866822)/, Cmd="D:\Program Files\Netease\MuMu\nx_main\MuMuNxMain.exe" )

SEED CefViewWing.exe#28368
  CefViewWing.exe#28368(PPID=23868, Created=/Date(1794208870027)/, Cmd="D:/Program Files/Netease/MuMu/nx_main/CefView/CefViewWing.exe" --type=utility --utility-sub-type=network.mojom.NetworkService --lang=en-US --service-sandbox-type=none --no-sandbox --use-angle=d3d11 --use-gl=angle --loca)
  <- MuMuNxMain.exe#23868(PPID=26884, Created=/Date(1794208866822)/, Cmd="D:\Program Files\Netease\MuMu\nx_main\MuMuNxMain.exe" )

SEED CefViewWing.exe#11060
  CefViewWing.exe#11060(PPID=24724, Created=/Date(1794208877811)/, Cmd="D:/Program Files/Netease/MuMu/nx_device/12.0/shell/CefView/CefViewWing.exe" --type=gpu-process --disable-gpu-sandbox --no-sandbox --disable-breakpad --disable-gpu-rasterization --use-angle=d3d11 --locales-dir-path="D:/P)
  <- MuMuNxDevice.exe#24724(PPID=23868, Created=/Date(1794208867702)/, Cmd="D:\Program Files\Netease\MuMu\\nx_device\12.0\shell\MuMuNxDevice.exe" -v 1 --vm MuMuPlayer-12.0-1)
  <- MuMuNxMain.exe#23868(PPID=26884, Created=/Date(1794208866822)/, Cmd="D:\Program Files\Netease\MuMu\nx_main\MuMuNxMain.exe" )

SEED CefViewWing.exe#5620
  CefViewWing.exe#5620(PPID=24724, Created=/Date(1794208878124)/, Cmd="D:/Program Files/Netease/MuMu/nx_device/12.0/shell/CefView/CefViewWing.exe" --type=utility --utility-sub-type=network.mojom.NetworkService --lang=en-US --service-sandbox-type=none --no-sandbox --use-angle=d3d11 --use-gl)
  <- MuMuNxDevice.exe#24724(PPID=23868, Created=/Date(1794208867702)/, Cmd="D:\Program Files\Netease\MuMu\\nx_device\12.0\shell\MuMuNxDevice.exe" -v 1 --vm MuMuPlayer-12.0-1)
  <- MuMuNxMain.exe#23868(PPID=26884, Created=/Date(1794208866822)/, Cmd="D:\Program Files\Netease\MuMu\nx_main\MuMuNxMain.exe" )
```

7871 / 7863 / 7890 / 7896 监听端口 OwningProcess：
命令：```text
PowerShell -NoProfile -EncodedCommand <base64> -- script: Get-NetTCPConnection -LocalPort 7871,7863,7890,7896 -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,State,OwningProcess | Sort-Object LocalPort,State | Format-Table -AutoSize | Out-String -Width 300
```
exitCode=1；stdout 408 字符
真实输出（stdout）：
```text

LocalAddress LocalPort State       OwningProcess
------------ --------- -----       -------------
::                7863                     22408
127.0.0.1         7863 Closed              22408
127.0.0.1         7863 Established         22408
127.0.0.1         7863 FinWait1            22408
127.0.0.1         7871                      5508
127.0.0.1         7871 Established          5508




```
stderr：
```text
#< CLIXML
<Objs Version="1.1.0.1" xmlns="http://schemas.microsoft.com/powershell/2004/04"><Obj S="progress" RefId="0"><TN RefId="0"><T>System.Management.Automation.PSCustomObject</T><T>System.Object</T></TN><MS><I64 N="SourceId">1</I64><PR N="Record"><AV>正在准备首次使用模块。</AV><AI>0</AI><Nil /><PI>-1</PI><PC>-1</PC><T>Completed</T><SR>-1</SR><SD> </SD></PR></MS></Obj><Obj S="progress" RefId="1"><TNRef RefId="0" /><MS><I64 N="SourceId">2</I64><PR N="Record"><AV>正在准备首次使用模块。</AV><AI>0</AI><Nil /><PI>-1</PI><PC>-1</PC><T>Completed</T><SR>-1</SR><SD> </SD></PR></MS></Obj><Obj S="progress" RefId="2"><TNRef RefId="0" /><MS><I64 N="SourceId">3</I64><PR N="Record"><AV>Get-NetTCPConnection -LocalPort 7871,7863,7890,7896 -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,State,OwningProcess | Sort-Object LocalPort,State | Format-Table -AutoSize | Out-String -Width 300</AV><AI>944346068</AI><Nil /><PI>-1</PI><PC>100</PC><T>Completed</T><SR>0</SR><SD>已完成 1/1</SD></PR></MS></Obj></Objs>
```
executor error：Command failed: C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -EncodedCommand JABFAHIAcgBvAHIAQQBjAHQAaQBvAG4AUAByAGUAZgBlAHIAZQBuAGMAZQA9ACcAQwBvAG4AdABpAG4AdQBlACcAOwAgAFsAQwBvAG4AcwBvAGwAZQBdADoAOgBPAHUAdABwAHUAdABFAG4AYwBvAGQAaQBuAGcAPQBbAFMAeQBzAHQAZQBtAC4AVABlAHgAdAAuAEUAbgBjAG8AZABpAG4AZwBdADoAOgBVAFQARgA4ADsAIAAkAE8AdQB0AHAAdQB0AEUAbgBjAG8AZABpAG4AZwA9AFsAUwB5AHMAdABlAG0ALgBUAGUAeAB0AC4ARQBuAGMAbwBkAGkAbgBnAF0AOgA6AFUAVABGADgAOwAgAEcAZQB0AC0ATgBlAHQAVABDAFAAQwBvAG4AbgBlAGMAdABpAG8AbgAgAC0ATABvAGMAYQBsAFAAbwByAHQAIAA3ADgANwAxACwANwA4ADYAMwAsADcAOAA5ADAALAA3ADgAOQA2ACAALQBFAHIAcgBvAHIAQQBjAHQAaQBvAG4AIABTAGkAbABlAG4AdABsAHkAQwBvAG4AdABpAG4AdQBlACAAfAAgAFMAZQBsAGUAYwB0AC0ATwBiAGoAZQBjAHQAIABMAG8AYwBhAGwAQQBkAGQAcgBlAHMAcwAsAEwAbwBjAGEAbABQAG8AcgB0ACwAUwB0AGEAdABlACwATwB3AG4AaQBuAGcAUAByAG8AYwBlAHMAcwAgAHwAIABTAG8AcgB0AC0ATwBiAGoAZQBjAHQAIABMAG8AYwBhAGwAUABvAHIAdAAsAFMAdABhAHQAZQAgAHwAIABGAG8AcgBtAGEAdAAtAFQAYQBiAGwAZQAgAC0AQQB1AHQAbwBTAGkAegBlACAAfAAgAE8AdQB0AC0AUwB0AHIAaQBuAGcAIAAtAFcAaQBkAHQAaAAgADMAMAAwAA==
#< CLIXML
<Objs Version="1.1.0.1" xmlns="http://schemas.microsoft.com/powershell/2004/04"><Obj S="progress" RefId="0"><TN RefId="0"><T>System.Management.Automation.PSCustomObject</T><T>System.Object</T></TN><MS><I64 N="SourceId">1</I64><PR N="Record"><AV>正在准备首次使用模块。</AV><AI>0</AI><Nil /><PI>-1</PI><PC>-1</PC><T>Completed</T><SR>-1</SR><SD> </SD></PR></MS></Obj><Obj S="progress" RefId="1"><TNRef RefId="0" /><MS><I64 N="SourceId">2</I64><PR N="Record"><AV>正在准备首次使用模块。</AV><AI>0</AI><Nil /><PI>-1</PI><PC>-1</PC><T>Completed</T><SR>-1</SR><SD> </SD></PR></MS></Obj><Obj S="progress" RefId="2"><TNRef RefId="0" /><MS><I64 N="SourceId">3</I64><PR N="Record"><AV>Get-NetTCPConnection -LocalPort 7871,7863,7890,7896 -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,State,OwningProcess | Sort-Object LocalPort,State | Format-Table -AutoSize | Out-String -Width 300</AV><AI>944346068</AI><Nil /><PI>-1</PI><PC>100</PC><T>Completed</T><SR>0</SR><SD>已完成 1/1</SD></PR></MS></Obj></Objs>

命令：```text
PowerShell -NoProfile -EncodedCommand <base64> -- script: Get-NetTCPConnection -LocalPort 7871,7863,7890,7896 -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,RemoteAddress,RemotePort,State,OwningProcess,CreationTime | ConvertTo-Json -Depth 3
```
exitCode=1；stdout 1555 字符
真实输出（stdout）：
```text
[
    {
        "LocalAddress":  "::",
        "LocalPort":  7863,
        "RemoteAddress":  "::",
        "RemotePort":  0,
        "State":  null,
        "OwningProcess":  22408,
        "CreationTime":  "\/Date(1794207190000)\/"
    },
    {
        "LocalAddress":  "127.0.0.1",
        "LocalPort":  7871,
        "RemoteAddress":  "127.0.0.1",
        "RemotePort":  14074,
        "State":  5,
        "OwningProcess":  5508,
        "CreationTime":  "\/Date(1794209715000)\/"
    },
    {
        "LocalAddress":  "127.0.0.1",
        "LocalPort":  7871,
        "RemoteAddress":  "0.0.0.0",
        "RemotePort":  0,
        "State":  null,
        "OwningProcess":  5508,
        "CreationTime":  "\/Date(1794207092000)\/"
    },
    {
        "LocalAddress":  "127.0.0.1",
        "LocalPort":  7863,
        "RemoteAddress":  "127.0.0.1",
        "RemotePort":  10501,
        "State":  5,
        "OwningProcess":  22408,
        "CreationTime":  "\/Date(1794208820000)\/"
    },
    {
        "LocalAddress":  "127.0.0.1",
        "LocalPort":  7863,
        "RemoteAddress":  "127.0.0.1",
        "RemotePort":  3844,
        "State":  6,
        "OwningProcess":  22408,
        "CreationTime":  "\/Date(1794210048000)\/"
    },
    {
        "LocalAddress":  "127.0.0.1",
        "LocalPort":  7863,
        "RemoteAddress":  "127.0.0.1",
        "RemotePort":  3165,
        "State":  1,
        "OwningProcess":  22408,
        "CreationTime":  "\/Date(1794207190000)\/"
    }
]

```
stderr：
```text
#< CLIXML
<Objs Version="1.1.0.1" xmlns="http://schemas.microsoft.com/powershell/2004/04"><Obj S="progress" RefId="0"><TN RefId="0"><T>System.Management.Automation.PSCustomObject</T><T>System.Object</T></TN><MS><I64 N="SourceId">1</I64><PR N="Record"><AV>正在准备首次使用模块。</AV><AI>0</AI><Nil /><PI>-1</PI><PC>-1</PC><T>Completed</T><SR>-1</SR><SD> </SD></PR></MS></Obj><Obj S="progress" RefId="1"><TNRef RefId="0" /><MS><I64 N="SourceId">2</I64><PR N="Record"><AV>正在准备首次使用模块。</AV><AI>0</AI><Nil /><PI>-1</PI><PC>-1</PC><T>Completed</T><SR>-1</SR><SD> </SD></PR></MS></Obj><Obj S="progress" RefId="2"><TNRef RefId="0" /><MS><I64 N="SourceId">3</I64><PR N="Record"><AV>Get-NetTCPConnection -LocalPort 7871,7863,7890,7896 -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,RemoteAddress,RemotePort,State,OwningProcess,CreationTime | ConvertTo-Json -Depth 3</AV><AI>1375053031</AI><Nil /><PI>-1</PI><PC>100</PC><T>Completed</T><SR>0</SR><SD>已完成 1/1</SD></PR></MS></Obj></Objs>
```
executor error：Command failed: C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -EncodedCommand JABFAHIAcgBvAHIAQQBjAHQAaQBvAG4AUAByAGUAZgBlAHIAZQBuAGMAZQA9ACcAQwBvAG4AdABpAG4AdQBlACcAOwAgAFsAQwBvAG4AcwBvAGwAZQBdADoAOgBPAHUAdABwAHUAdABFAG4AYwBvAGQAaQBuAGcAPQBbAFMAeQBzAHQAZQBtAC4AVABlAHgAdAAuAEUAbgBjAG8AZABpAG4AZwBdADoAOgBVAFQARgA4ADsAIAAkAE8AdQB0AHAAdQB0AEUAbgBjAG8AZABpAG4AZwA9AFsAUwB5AHMAdABlAG0ALgBUAGUAeAB0AC4ARQBuAGMAbwBkAGkAbgBnAF0AOgA6AFUAVABGADgAOwAgAEcAZQB0AC0ATgBlAHQAVABDAFAAQwBvAG4AbgBlAGMAdABpAG8AbgAgAC0ATABvAGMAYQBsAFAAbwByAHQAIAA3ADgANwAxACwANwA4ADYAMwAsADcAOAA5ADAALAA3ADgAOQA2ACAALQBFAHIAcgBvAHIAQQBjAHQAaQBvAG4AIABTAGkAbABlAG4AdABsAHkAQwBvAG4AdABpAG4AdQBlACAAfAAgAFMAZQBsAGUAYwB0AC0ATwBiAGoAZQBjAHQAIABMAG8AYwBhAGwAQQBkAGQAcgBlAHMAcwAsAEwAbwBjAGEAbABQAG8AcgB0ACwAUgBlAG0AbwB0AGUAQQBkAGQAcgBlAHMAcwAsAFIAZQBtAG8AdABlAFAAbwByAHQALABTAHQAYQB0AGUALABPAHcAbgBpAG4AZwBQAHIAbwBjAGUAcwBzACwAQwByAGUAYQB0AGkAbwBuAFQAaQBtAGUAIAB8ACAAQwBvAG4AdgBlAHIAdABUAG8ALQBKAHMAbwBuACAALQBEAGUAcAB0AGgAIAAzAA==
#< CLIXML
<Objs Version="1.1.0.1" xmlns="http://schemas.microsoft.com/powershell/2004/04"><Obj S="progress" RefId="0"><TN RefId="0"><T>System.Management.Automation.PSCustomObject</T><T>System.Object</T></TN><MS><I64 N="SourceId">1</I64><PR N="Record"><AV>正在准备首次使用模块。</AV><AI>0</AI><Nil /><PI>-1</PI><PC>-1</PC><T>Completed</T><SR>-1</SR><SD> </SD></PR></MS></Obj><Obj S="progress" RefId="1"><TNRef RefId="0" /><MS><I64 N="SourceId">2</I64><PR N="Record"><AV>正在准备首次使用模块。</AV><AI>0</AI><Nil /><PI>-1</PI><PC>-1</PC><T>Completed</T><SR>-1</SR><SD> </SD></PR></MS></Obj><Obj S="progress" RefId="2"><TNRef RefId="0" /><MS><I64 N="SourceId">3</I64><PR N="Record"><AV>Get-NetTCPConnection -LocalPort 7871,7863,7890,7896 -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,RemoteAddress,RemotePort,State,OwningProcess,CreationTime | ConvertTo-Json -Depth 3</AV><AI>1375053031</AI><Nil /><PI>-1</PI><PC>100</PC><T>Completed</T><SR>0</SR><SD>已完成 1/1</SD></PR></MS></Obj></Objs>

说明：`Get-NetTCPConnection -LocalPort 7871,7863,7890,7896` 只返回本机仍在监听/连接的行；若某端口无输出即当前无 OwningProcess。

## 9. 结论汇总（对应用户两个诉求）

1. **「关闭 CMD 杀死网关」**：源码已部分缓解但没根除。`build.py:11-13` 指出裸 `go build ./...` 会覆盖 GUI 子系统产物导致登录自启弹 CMD 窗口、关窗即杀；`console_windows.go:37-42` + `main.go:185` 在启动横幅后 `FreeConsole()` 释放父控制台；`detach()`（`main.go:429-451`）用 `DETACHED_PROCESS | CREATE_NO_WINDOW | HideWindow` 起 `serve -tray` 副本。但 `main.go:440` 自己写明 DETACHED_PROCESS 不保证父进程树被回收时仍存活，`superviseLauncher`（:232）会在父终端消失时让副本自行退出；且 `install()` 用的是「启动」文件夹快捷方式，不是服务/计划任务。
2. **「DSH 关闭网关跟着消失」**：当前运行实况（§8）决定根因是父进程链还是 Job Object。`winproc.go:3-5` 明确 zgate 用 `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` 把子进程绑在自己的 Job 上：zgate 一退，wb2api/qoder/cliproxyapi 全被带走；这与 DSH 是否存活是两层关系。
3. **「改完代码自动生效」**：**当前完全不具备**。`config.go` 无 watch、`supervisor.go:473-475` 明确 exe/端口是启动期固定、`router.go:984` 明确监听地址/新子进程/alias 路径需重启；`/admin/reload` 只是手动 HTTP 触发的部分配置重读；无 `fsnotify`、无二进制哈希检测、无 `syscall.Exec` 自替换、无 `net.FileListener/ExtraFiles` 无缝继承 listener。`gateways/zgate/.restart.log` 与 `zgate.exe.prev / .bak-*` 只证明历史上做过人工受控替换。
4. **守护自愈**：`supervisor` 只对**被它管理的子进程**（workbuddy/qoder/cliproxyapi）做 5s 轮询 + always 策略自愈；**zgate 自身**没有外部守护者，没有服务恢复策略，没有计划任务拉起。
5. **热重载**：已有 `/admin/reload` + alias 每请求 ModTime 惰性重载，可作为「配置/路由热更」基座；但它不覆盖二进制替换，且 `/admin/reload` 无鉴权（仅监听 `127.0.0.1:7871`）。

## 方案建议

1. **服务化（解决 DSH/CMD 退出后不死，代价中等）**：把 zgate 注册为 Windows 服务（`sc create` / NSSM / WinSW），或至少把 `install()` 从「启动」快捷方式升级为带恢复策略的登录计划任务；服务控制管理器负责启动、崩溃重启、与会话/控制台解耦。代价：需要改 `main.go` 增加 service 入口或包一层 shim，处理 Session 0 下 `%LOCALAPPDATA%`、相对路径、子进程 Job Object 与「服务停止时优雅关 listener + Shutdown」；凭据仍只走环境变量；`build.py` 必须继续保证 `-H windowsgui` 不被 `go build ./...` 覆盖。
2. **守护自愈 + 受控热替换（解决「改完代码自动生效」，代价较高）**：在现有 `supervisor` 之上加一个独立 watchdog（同样服务化），用 `zgate.exe` 的 SHA-256 / LastWriteTime 检测产物变化，走「构建到临时文件 → 校验 PE Subsystem=2 → 备份旧 exe → 原子替换 → 向旧进程发 SIGTERM/graceful `Shutdown` → 等端口释放 → 起新进程 → `/health` 通过才提交，否则回滚到 `.prev`」。代价：现有 `net.Listen` + `srv.Shutdown` 之间没有 listener 继承，切换期有秒级连接拒绝；需补 `net.FileListener/ExtraFiles` 或前置反向代理才能无缝；且要处理 `winproc` 的 `KILL_ON_JOB_CLOSE` 让子进程随旧 zgate 一起退出、由新 zgate 重新拉起。
3. **热重载（低代价、范围有限，建议先做）**：保留并收口 `/admin/reload` 与 `alias.Map.Reload()`，把「策略/上游 base/key/alias 内容」的变更做成文件 watch（fsnotify 或 1–2s ModTime 轮询）自动触发，配合 `sync-models.ps1` 写完配置后主动 POST `/admin/reload`；同时给 `/admin/reload` 加本机 token。代价最小，但**明确不能解决 Go 代码改动**——代码改动仍必须走方案 2 的受控进程替换；把「热重载配置」和「热替换二进制」分开表述，避免再次出现「PROGRESS 自认生产实例未重启（仍是旧二进制）」的错配。

## 未决疑问 / 取证限制

- `codegraph status` 真实根显示 `Added: 8 files / Modified: 26 files`，索引陈旧；本报告已对 `main.go` / `router.go` 直读磁盘，但**未执行 `codegraph sync`**（只读约束），其他文件的 CodeGraph 行号可能落后，源码结论以磁盘逐行摘录为准。
- `schtasks /query /fo list /v` 与 `sc query state= all` 原始输出很长，本报告只保留与 `zgate/wb2api/mihomo/gateway/ModelBus` 相关的上下文片段并标注原始总行数；`Get-ScheduledTask` / `Get-Service` 的过滤输出是判定「是否已注册」的主证据。
- `F:\Project\ModelBus\third-party\cliproxyapi\config.yaml` 含 `access.api-keys` 真值，按约束未展开；`config.example.yaml` 的 `config reload` 注释属于 CLIProxyAPI 自身能力，不是 zgate 的热重载。
- 进程/端口是某一时刻的快照，未做任何重启或停止；「生产实例未重启（仍是旧二进制）」需结合 `binary hashes and timestamps` 的 SHA-256 与 `zgate.exe` 运行进程 CommandLine/CreationDate 一起判断。
- `main.go:42 const taskName = "ModelBus-zgate"` 与 `install()` 的 Startup 快捷方式是否已被用户实际执行过，只能由 §7 启动文件夹 / 计划任务输出与 §8 父进程链断定；本报告没有替用户执行 `install` / `uninstall`。

## 10. 补证：失败命令原文、复测与敏感值扫描

### 10.1 三条 git 命令原 `cmd /c` 包装返回 128（原始 stderr 不改色）

原报告 §0 中 `git rev-parse --show-toplevel` 命令块原文（节选）：
```text
未找到该命令块
```

提取到的原始 stderr：
```text
未找到 stderr 块（原命令块可能无 stderr 段）
```

改用 `git.exe` argv 直连（绕开 `cmd /c` 引号包装）后真实输出：

命令：git.exe -C F:\Project\ModelBus rev-parse --show-toplevel
exitCode=0
stdout：
```text
F:/Project/ModelBus

```

命令：git.exe -C F:\Project\ModelBus rev-parse --abbrev-ref HEAD
exitCode=0
stdout：
```text
main

```

命令：git.exe -C F:\Project\ModelBus status --short
exitCode=0
stdout：
```text
 M PROGRESS.md
 M docs/ARCHITECTURE.md
 M docs/MAINTENANCE.md
 M docs/MODEL-PROVIDERS.md
 M docs/PITFALLS.md
 M docs/TROUBLESHOOTING.md
 M gateways/zgate/internal/config/config.go
 M gateways/zgate/internal/keys/keys.go
 M gateways/zgate/internal/router/router.go
 M gateways/zgate/internal/winproc/console_other.go
 M gateways/zgate/internal/winproc/console_windows.go
 M gateways/zgate/internal/winproc/winproc_other.go
 M gateways/zgate/internal/winproc/winproc_windows.go
 M gateways/zgate/main.go
 M gateways/zgate/zgate.json
 M memories/zgate-windowless-build.md
 M providers/qoder/cache/qd_prices.json
 M tools/model_alias.py
?? evidence/agent-cliproxyapi.md
?? evidence/agent-gateway-lifecycle.md
?? evidence/agent-sort-rule.md
?? evidence/go-model-sync-20261106-120006.md
?? evidence/go-model-sync-20261106-232822.md
?? evidence/go-model-sync-20261109-120007.md
?? gateways/zgate/.restart.log
?? gateways/zgate/zgate.exe.prev
?? third-party/cliproxyapi/

```

结论不变：真实项目根 `F:/Project/ModelBus`、分支 `main`、工作树修改清单与 §0 一致。

### 10.2 两条端口命令返回 1 的原始 stderr 与逐端口复测

原报告 §8 中 `Get-NetTCPConnection -LocalPort 7871,7863,7890,7896` 命令块原文（节选）：
```text
-- script: Get-NetTCPConnection -LocalPort 7871,7863,7890,7896 -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,State,OwningProcess | Sort-Object LocalPort,State | Format-Table -AutoSize | Out-String -Width 300
```
exitCode=1；stdout 408 字符
真实输出（stdout）：
```text

LocalAddress LocalPort State       OwningProcess
------------ --------- -----       -------------
::                7863                     22408
127.0.0.1         7863 Closed              22408
127.0.0.1         7863 Established         22408
127.0.0.1         7863 FinWait1            22408
127.0.0.1         7871                      5508
127.0.0.1         7871 Established          5508




```
stderr：
```text
#< CLIXML
<Objs Version="1.1.0.1" xmlns="http://schemas.microsoft.com/powershell/2004/04"><Obj S="progress" RefId="0"><TN RefId="0"><T>System.Management.Automation.PSCustomObject</T><T>System.Object</T></TN><MS><I64 N="SourceId">1</I64><PR N="Record"><AV>正在准备首次使用模块。</AV><AI>0</AI><Nil /><PI>-1</PI><PC>-1</PC><T>Completed</T><SR>-1</SR><SD> </SD></PR></MS></Obj><Obj S="progress" RefId="1"><TNRef RefId="0" /><MS><I64 N="SourceId">2</I64><PR N="Record"><AV>正在准备首次使用模块。</AV><AI>0</AI><Nil /><PI>-1</PI><PC>-1</PC><T>Completed</T><SR>-1</SR><SD> </SD></PR></MS></Obj><Obj S="progress" RefId="2"><TNRef RefId="0" /><MS><I64 N="SourceId">3</I64><PR N="Record"><AV>Get-NetTCPConnection -LocalPort 7871,7863,7890,7896 -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,State,OwningProcess | Sort-Object LocalPort,State | Format-Table -AutoSize | Out-String -Width 300</AV><AI>944346068</AI><Nil /><PI>-1</PI><PC>100</PC><T>Completed</T><SR>0</SR><SD>已完成 1/1</SD></PR></MS></O
```

提取到的原始 stderr：
```text
#< CLIXML
<Objs Version="1.1.0.1" xmlns="http://schemas.microsoft.com/powershell/2004/04"><Obj S="progress" RefId="0"><TN RefId="0"><T>System.Management.Automation.PSCustomObject</T><T>System.Object</T></TN><MS><I64 N="SourceId">1</I64><PR N="Record"><AV>正在准备首次使用模块。</AV><AI>0</AI><Nil /><PI>-1</PI><PC>-1</PC><T>Completed</T><SR>-1</SR><SD> </SD></PR></MS></Obj><Obj S="progress" RefId="1"><TNRef RefId="0" /><MS><I64 N="SourceId">2</I64><PR N="Record"><AV>正在准备首次使用模块。</AV><AI>0</AI><Nil /><PI>-1</PI><PC>-1</PC><T>Completed</T><SR>-1</SR><SD> </SD></PR></MS></Obj><Obj S="progress" RefId="2"><TNRef RefId="0" /><MS><I64 N="SourceId">3</I64><PR N="Record"><AV>Get-NetTCPConnection -LocalPort 7871,7863,7890,7896 -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,State,OwningProcess | Sort-Object LocalPort,State | Format-Table -AutoSize | Out-String -Width 300</AV><AI>944346068</AI><Nil /><PI>-1</PI><PC>100</PC><T>Completed</T><SR>0</SR><SD>已完成 1/1</SD></PR></MS></Obj></Objs>
```

逐端口 `-ErrorAction SilentlyContinue` 复测（每个端口明确写 `无连接记录` 或 OwningProcess 表）：

命令：PowerShell -NoProfile -EncodedCommand <base64> -- script: $ports=7871,7863,7890,7896; foreach($p in $ports){ 'PORT=' + $p; $c=@(Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue); if($c.Count){ $c | Select-Object LocalAddress,LocalPort,State,OwningProcess | Sort-Object State | Format-Table -AutoSize | Out-String -Width 240 } else { '无连接记录' }
exitCode=0
stdout：
```text
PORT=7871

LocalAddress LocalPort State       OwningProcess
------------ --------- -----       -------------
127.0.0.1         7871                      5508
127.0.0.1         7871 Established          5508
127.0.0.1         7871 Established          5508



PORT=7863

LocalAddress LocalPort State       OwningProcess
------------ --------- -----       -------------
::                7863                     22408
127.0.0.1         7863 Established         22408
127.0.0.1         7863 Established         22408
127.0.0.1         7863 Established         22408



PORT=7890
无连接记录
PORT=7896
无连接记录

```
stderr：
```text
#< CLIXML
<Objs Version="1.1.0.1" xmlns="http://schemas.microsoft.com/powershell/2004/04"><Obj S="progress" RefId="0"><TN RefId="0"><T>System.Management.Automation.PSCustomObject</T><T>System.Object</T></TN><MS><I64 N="SourceId">1</I64><PR N="Record"><AV>正在准备首次使用模块。</AV><AI>0</AI><Nil /><PI>-1</PI><PC>-1</PC><T>Completed</T><SR>-1</SR><SD> </SD></PR></MS></Obj><Obj S="progress" RefId="1"><TNRef RefId="0" /><MS><I64 N="SourceId">2</I64><PR N="Record"><AV>正在准备首次使用模块。</AV><AI>0</AI><Nil /><PI>-1</PI><PC>-1</PC><T>Completed</T><SR>-1</SR><SD> </SD></PR></MS></Obj><Obj S="progress" RefId="2"><TNRef RefId="0" /><MS><I64 N="SourceId">3</I64><PR N="Record"><AV>Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue); if($c.Count){ $c | Select-Object LocalAddress,LocalPort,State,OwningProcess | Sort-Object State | Format-Table -AutoSize | Out-String -Width 240 } else { '无连接记录' } }</AV><AI>1834908386</AI><Nil /><PI>-1</PI><PC>100</PC><T>Completed</T><SR>0</SR><SD>已完成 1/1</SD></PR></MS></Obj><Obj S="progress" RefId="3"><TNRef RefId="0" /><MS><I64 N="SourceId">4</I64><PR N="Record"><AV>Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue); if($c.Count){ $c | Select-Object
```

仅 LISTEN 状态复测：

命令：PowerShell -NoProfile -EncodedCommand <base64> -- script: $ports=7871,7863,7890,7896; $c=@(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -in $ports }); if($c.Count){ $c | Select-Object LocalAddress,LocalPort,State,OwningProcess | Sort-Object LocalPort | Format-Table -AutoSize | Out-String -Width 240 } else {
exitCode=0
stdout：
```text
NO_LISTEN_ROWS

```
stderr：
```text
#< CLIXML
<Objs Version="1.1.0.1" xmlns="http://schemas.microsoft.com/powershell/2004/04"><Obj S="progress" RefId="0"><TN RefId="0"><T>System.Management.Automation.PSCustomObject</T><T>System.Object</T></TN><MS><I64 N="SourceId">1</I64><PR N="Record"><AV>正在准备首次使用模块。</AV><AI>0</AI><Nil /><PI>-1</PI><PC>-1</PC><T>Completed</T><SR>-1</SR><SD> </SD></PR></MS></Obj><Obj S="progress" RefId="1"><TNRef RefId="0" /><MS><I64 N="SourceId">2</I64><PR N="Record"><AV>正在准备首次使用模块。</AV><AI>0</AI><Nil /><PI>-1</PI><PC>-1</PC><T>Completed</T><SR>-1</SR><SD> </SD></PR></MS></Obj><Obj S="progress" RefId="2"><TNRef RefId="0" /><MS><I64 N="SourceId">3</I64><PR N="Record"><AV>Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -in $ports }); if($c.Count){ $c | Select-Object LocalAddress,LocalPort,State,OwningProcess | Sort-Object LocalPort | Format-Table -AutoSize | Out-String -Width 240 } else { 'NO_LISTEN_ROWS' }</AV><AI>1016276938</AI><Nil /><PI>-1</PI><PC>100</PC><T>Completed</T><SR>0</SR><SD>已完成 1/1</SD></PR></MS></Obj></Objs>
```

`netstat -ano -p tcp` 过滤这四个端口的真实输出：

命令：CMD: netstat -ano -p tcp | findstr /r /c:":7871 " /c:":7863 " /c:":7890 " /c:":7896 "
exitCode=1
stdout：
```text
(空)
```
stderr：
```text
FINDSTR: �޷��� /c:":7863
FINDSTR: �޷��� /c:":7890
FINDSTR: �޷��� /c:":7896

```
executor error：Command failed: cmd.exe /c netstat -ano -p tcp | findstr /r /c:":7871 " /c:":7863 " /c:":7890 " /c:":7896 "
FINDSTR: �޷��� /c:":7863
FINDSTR: �޷��� /c:":7890
FINDSTR: �޷��� /c:":7896


结论：`Get-NetTCPConnection` 原批量命令的 exitCode 1 与原始 stderr 一起保留；逐端口复测给出 7871 / 7863 / 7890 / 7896 的明确「无连接记录」或 `OwningProcess` 行。

### 10.3 敏感值扫描

- 全报告按 `api-key|token|secret|password|authorization|credential|header-value-env` 赋值模式扫描：命中 0 处，其中需脱敏 0 处；疑似凭据前缀（AQ./sk-/oc_sk- 等）兜底替换 0 处。
- `third-party/cliproxyapi/config.yaml` 正文未展开；任何疑似真值已统一写成 `<REDACTED>`。
- 本补证未读取环境变量值，未打印任何 key / token。


