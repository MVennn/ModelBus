#!/usr/bin/env python3
"""check-project.py — 本地 pre-commit 与 CI 共用的项目级闸门。

真值唯一来源：gateways/zgate/zgate.json（children / ports / upstreams）。

用法:
  python tools/check-project.py              # 全跑（语义 + 换行/BOM + PS1 语法）
  python tools/check-project.py --semantic   # 只跑门面语义
  python tools/check-project.py --lineendings
  python tools/check-project.py --ps1

补的是旧门禁中间的空白：zgate.json 真值、新脚本 LF/BOM、PS1 语法
过去没有统一判据；.github/workflows/ci.yml 只在 push/PR 触发，
tools/check-docs.py 只查链接/锚点/引言/孤儿，不比对 zgate.json。
本脚本把「门面口径是否跟着配置走」「新脚本 LF/BOM」「PS1 语法」收成
同一条命令；.githooks/pre-commit 依次调用 check-secrets.py、gofmt、
check-docs.py、check-project.py 四道门禁，CI 也调同一条命令，避免每轮靠人肉收尾复现。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys

# Windows 控制台默认 GBK，中文门禁输出会变乱码；CI/Git Bash 已是 UTF-8。
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZGATE_JSON = os.path.join(ROOT, "gateways", "zgate", "zgate.json")
LIFECYCLE = os.path.join(ROOT, "tools", "zgate-lifecycle")
GATEWAY_ROUTER = "gateways/zgate/internal/router/router.go"
GATEWAY_ALIAS = "gateways/zgate/internal/alias/alias.go"


def read_bytes(rel: str) -> bytes:
    with open(os.path.join(ROOT, rel), "rb") as f:
        return f.read()


def read_text(rel: str) -> str:
    return read_bytes(rel).decode("utf-8", errors="replace")


# ---------- 1) 语义：门面口径必须跟着 zgate.json ----------
FACADES = ["README.md", "docs/README.md", "docs/ARCHITECTURE.md", "docs/TOOLS.md"]
STALE = [
    (r"托管两个本地网关", "旧口径：托管两个本地网关"),
    (r"两个上游进程", "旧口径：两个上游进程"),
    (r"两个子进程", "旧口径：两个子进程"),
    (r"两个本地网关", "旧口径：两个本地网关"),
    (r"三组\s*provider", "旧口径：三组 provider"),
    (r"三个\s*provider", "旧口径：三个 provider"),
    (r"3\s*个\s*provider", "旧口径：3 个 provider"),
    (r"四个常驻进程", "旧口径：四个常驻进程"),
    (r"293\s*MB", "旧口径：293 MB"),
]

# 现行正本：退役的 JS 协议桥不得再被门面写成现行实现；Go 正本必须带流式实现。
STALE_CANONICAL = [
    (r"`tools/protocol_bridge\.js`（375 行）", "把退役 JS 协议桥当现行正本"),
]


def check_canonical(results: list) -> None:
    bridge_rel = "gateways/zgate/internal/bridge/bridge.go"
    if not os.path.isfile(os.path.join(ROOT, bridge_rel)):
        results.append(("FAIL", bridge_rel + " 缺失（协议桥现行正本）"))
        return
    if os.path.isfile(os.path.join(ROOT, "tools", "protocol_bridge.js")):
        results.append(("FAIL", "tools/protocol_bridge.js 仍在位（已退役，正本应为 bridge.go）"))
    if "func forwardStream(" not in read_text(bridge_rel):
        results.append(("FAIL", bridge_rel + " 缺 func forwardStream(...)：门面写「已支持流式」将失去实现依据"))
    for rel in FACADES:
        try:
            t = read_text(rel)
        except OSError:
            continue
        for pat, why in STALE_CANONICAL:
            m = re.search(pat, t, re.I)
            if m:
                results.append(("FAIL", rel + ": " + why + " -> " + repr(m.group(0))))
    results.append(("OK", "正本指针: bridge.go 在位且含 forwardStream，门面无退役 JS 正本口径"))


def check_gateway(results: list) -> None:
    # 评估 m00494 暴露的三处回归：聚合 catalog、六段 /health、QN Bearer。
    # 门面文档写「已落地」之前源码实现必须真的在位；pre-commit 与 CI 共用这道闸。
    before = len(results)
    try:
        router = read_text(GATEWAY_ROUTER)
        alias = read_text(GATEWAY_ALIAS)
    except OSError as e:
        results.append(('FAIL', '网关源码缺失: ' + repr(e)))
        return
    checks = [
        ('func (s *Server) models(', 'GET /v1/models 聚合 catalog handler'),
        ('upstreamView("CP")', '/health 第六段 cliproxyapi'),
        ('case "WB", "QD", "QW", "QN", "CP":', 'QN 原生 chat 跳的 Bearer 覆盖'),
    ]
    for needle, why in checks:
        if needle not in router:
            results.append(('FAIL', 'router.go: 缺 ' + why + ' -> ' + repr(needle)))
    for seg in ('opencode', 'workbuddy', 'qoder', 'qwen', 'qiniu', 'cliproxyapi'):
        if ('"' + seg + '":') not in router:
            results.append(('FAIL', 'router.go: /health payload 缺 ' + seg + ' 段'))
    if 'func (m *Map) Catalog(' not in alias:
        results.append(('FAIL', 'alias.go: 缺 func (m *Map) Catalog(...)：聚合视图退回 OC 透传'))
    if len(results) == before:
        results.append(('OK', '网关实现: /v1/models 聚合 + /health 六段 + QN Bearer 在位'))


def check_semantic(results: list) -> None:
    with open(ZGATE_JSON, encoding="utf-8") as f:
        cfg = json.load(f)
    children = cfg.get("children", {}) or {}
    ports = sorted({str(v.get("port")) for v in children.values() if v.get("port")})
    n_up = len(cfg.get("upstreams", []) or {})
    results.append(("OK", "zgate.json 真值: children=" + str(len(children)) +
                    " ports=" + ",".join(ports) + " upstreams=" + str(n_up)))
    for rel in FACADES:
        try:
            t = read_text(rel)
        except OSError:
            results.append(("FAIL", rel + ": 门面文件缺失"))
            continue
        for pat, why in STALE:
            m = re.search(pat, t, re.I)
            if m:
                results.append(("FAIL", rel + ": 命中 " + why + " -> 字面量 " + repr(m.group(0))))
    try:
        if "8317" not in read_text("README.md"):
            results.append(("FAIL", "README.md: 缺 8317（zgate.json 第三个 child cliproxyapi 的端口）"))
    except OSError:
        results.append(("FAIL", "README.md: 门面文件缺失"))
    try:
        mt = read_text("docs/MAINTENANCE.md")
    except OSError:
        mt = ""
    for task in ("ModelBus-zgate-hidden", "ModelBus-zgate-watchdog"):
        if task not in mt:
            results.append(("FAIL", "docs/MAINTENANCE.md: 缺现行计划任务名 " + task))
    indexed = False
    for rel in ("docs/README.md", "docs/MAINTENANCE.md"):
        try:
            if "zgate-lifecycle" in read_text(rel):
                indexed = True
        except OSError:
            pass
    if not indexed:
        results.append(("FAIL", "tools/zgate-lifecycle/ 未被 docs/README.md 或 docs/MAINTENANCE.md 索引（孤儿）"))
    check_canonical(results)
    check_gateway(results)
    check_sync_policy(results)


def check_sync_policy(results: list) -> None:
    # 守两条「最性价比 / 零新增推理请求」口径，防止自动化退回旧行为：
    #   ① 每日同步默认只写报告、不 push（sync-models.ps1 只有 -Push 才推送，vbs 入口不带 -Push）；
    #   ② PITFALLS §35 现行口径：go_model_sync.py 不再发探测请求。
    before = len(results)
    try:
        ps1 = read_text("sync-models.ps1")
        vbs = read_text("sync-models.vbs")
        pitfalls = read_text("docs/PITFALLS.md")
    except OSError as e:
        results.append(("FAIL", "同步策略文件读取失败: " + repr(e)))
        return
    if "[switch]$Push" not in ps1 or "[switch]$NoPush" in ps1:
        results.append(("FAIL", "sync-models.ps1: 推送开关应为显式 -Push（默认不 push）"))
    m = re.search(r"if \(\$Push\) \{(.+?)\}", ps1, re.S)
    if not m:
        results.append(("FAIL", "sync-models.ps1: 缺 if ($Push) 分支"))
    else:
        if "--push" not in m.group(1):
            results.append(("FAIL", "sync-models.ps1: if ($Push) 分支内没有 --push"))
        else_m = re.search(r"else \{(.+?)\}", ps1[m.end():], re.S)
        if not else_m or "--push" in else_m.group(1):
            results.append(("FAIL", "sync-models.ps1: 默认分支（else）仍在 push 或缺失"))
    if re.search(r"-Push\b", vbs):
        results.append(("FAIL", "sync-models.vbs: 计划任务入口带了 -Push，会天天自动 push"))
    if "不再发探测请求" not in pitfalls:
        results.append(("FAIL", "docs/PITFALLS.md: §35 缺「不再发探测请求」现行口径注记"))
    if len(results) == before:
        results.append(("OK", "同步策略: 默认不 push（-Push 才推）+ §35 现行不发探测口径在位"))


# ---------- 2) 新脚本换行/BOM（不翻历史文件的旧债，只管生命周期正本 + 钩子 + 自身） ----------
def check_lineendings(results: list) -> None:
    specs = []
    for p in sorted(glob.glob(os.path.join(LIFECYCLE, "*.ps1"))):
        specs.append((p, True, "PS1 必须 UTF-8 BOM + LF"))
    for ext in ("cmd", "bat", "vbs"):
        for p in sorted(glob.glob(os.path.join(LIFECYCLE, "*." + ext))):
            specs.append((p, False, ext.upper() + " 无 BOM + LF"))
    hook = os.path.join(ROOT, ".githooks", "pre-commit")
    if os.path.isfile(hook):
        specs.append((hook, False, "pre-commit(sh) 无 BOM + LF"))
    specs.append((os.path.abspath(__file__), False, "check-project.py 无 BOM + LF"))
    if len(specs) <= 2:
        results.append(("FAIL", "tools/zgate-lifecycle/ 下没有脚本正本"))
        return
    bad = 0
    for p, want_bom, label in specs:
        with open(p, "rb") as f:
            b = f.read()
        bom = b.startswith(b"\xef\xbb\xbf")
        cr = b.count(b"\r")
        rel = os.path.relpath(p, ROOT).replace("\\", "/")
        if bom != want_bom:
            results.append(("FAIL", rel + ": BOM=" + str(bom) + " 期望 " + str(want_bom) + "（" + label + "）"))
            bad += 1
        elif cr:
            results.append(("FAIL", rel + ": 含 " + str(cr) + " 个 CR（" + label + "）"))
            bad += 1
    if not bad:
        results.append(("OK", "换行/BOM: " + str(len(specs)) + " 个脚本全部符合（PS1 BOM+LF / CMD·VBS·sh 无 BOM+LF）"))


# ---------- 3) PS1 语法（仅 Windows 有 powershell/pwsh 时跑；CI ubuntu 自动 SKIP） ----------
def check_ps1(results: list) -> None:
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        results.append(("SKIP", "PS1 语法: 本机无 powershell/pwsh（CI ubuntu 跳过）"))
        return
    files = sorted(glob.glob(os.path.join(LIFECYCLE, "*.ps1")))
    if not files:
        results.append(("SKIP", "PS1 语法: 无 .ps1 正本"))
        return
    before = len(results)
    for p in files:
        rel = os.path.relpath(p, ROOT).replace("\\", "/")
        ps = ("$e=$null; [System.Management.Automation.Language.Parser]::ParseFile("
              "'" + p + "',[ref]$null,[ref]$e) > $null; "
              "if($e){ $e | ForEach-Object { Write-Output $_.Message }; exit 1 }")
        r = subprocess.run([exe, "-NoProfile", "-NonInteractive", "-Command", ps],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            results.append(("FAIL", rel + ": PS1 语法 " + r.stdout.strip() + " " + r.stderr.strip()))
    if len(results) == before:
        results.append(("OK", "PS1 语法: " + str(len(files)) + " 个脚本 Parser 通过（" + exe + "）"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--semantic", action="store_true")
    ap.add_argument("--lineendings", action="store_true")
    ap.add_argument("--ps1", action="store_true")
    a = ap.parse_args()
    all_ = not (a.semantic or a.lineendings or a.ps1)
    results = []
    if all_ or a.semantic:
        check_semantic(results)
    if all_ or a.lineendings:
        check_lineendings(results)
    if all_ or a.ps1:
        check_ps1(results)
    for st, msg in results:
        print("[" + st + "] " + msg)
    fails = [m for st, m in results if st == "FAIL"]
    if fails:
        print("[FAIL] check-project: " + str(len(fails)) + " 项失败")
        return 1
    print("[OK] check-project: " + str(len(results)) + " 项通过（语义 / 换行BOM / PS1）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
