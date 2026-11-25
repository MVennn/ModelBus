#!/usr/bin/env python3
"""check-zgate-policy.py — zgate 启动自检的离线复刻（channelPolicy x 别名链）。

为什么要有这道门禁：gateways/zgate/main.go:155 的 ValidatePolicies 会在
「某个渠道只服务单跳模型、却配了多跳字段」时拒绝启动。2026-11-17 15:45 就是这样
全站 503 了 25 分钟 —— 某渠道只剩单跳模型，配置里却还留着
softCooldownSeconds / rateLimitBackoffMs / maxParallel 三个永远读不到的字段；错误只走
stderr，watchdog 只记了 up=False (timed out)，日志里只剩三条 [policy] WARN。

这份脚本与 internal/router/policy.go 的判据逐条对齐，把同样的判定从「启动时」前移到
「提交前」。判据变了要同时改这里和 policy.go（check-project.py 会比对字段清单）。

用法:
  python tools/check-zgate-policy.py           # 人类可读
  python tools/check-zgate-policy.py --quiet   # 只输出问题
退出码: 0 = 无 Fatal / 无引用错误；1 = 有 Fatal 或引用错误
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZGATE_JSON = os.path.join(ROOT, "gateways", "zgate", "zgate.json")

# 只在多跳链上才有意义的字段（policy.go:131 policyRaceFields 的镜像）。
RACE_FIELDS = [
    ("hedgeAfterMs", lambda v: v > 0),
    ("firstBlockMs", lambda v: v > 0),
    ("maxParallel", lambda v: v > 0),
    ("silenceCooldownSeconds", lambda v: v > 0),
    ("softCooldownSeconds", lambda v: v > 0),
    ("rateLimitBackoffMs", lambda v: v != 0),
]

# config.go:104 ChannelPolicy 认识的键（拼错的键会被 encoding/json 静默丢掉）。
KNOWN_POLICY_KEYS = {
    "softCooldownSeconds",
    "silenceCooldownSeconds",
    "rateLimitBackoffMs",
    "firstBlockMs",
    "hedgeAfterMs",
    "maxParallel",
    "authFailCooldownHours",
    "busyCooldownSeconds",
    "headerTimeoutSec",
    "timeoutCooldownSeconds",
    "retry500Once",
}


POLICY_GO = os.path.join(ROOT, "gateways", "zgate", "internal", "router", "policy.go")


def drift_problems() -> list[str]:
    """policyRaceFields 的字段集合必须与 RACE_FIELDS 一致。

    两边判据漂移的后果很具体：Go 侧加了字段而这里没跟，门禁就会漏掉新的 Fatal
    组合；反过来这里多认了字段，会把合法配置误判成 Fatal。所以宁可让门禁报错，
    也别让两份判据悄悄分开走。
    """
    if not os.path.exists(POLICY_GO):
        return ["找不到 policy.go，判据漂移检查没法做: " + POLICY_GO]
    with open(POLICY_GO, encoding="utf-8") as f:
        src = f.read()
    m = re.search(r"func policyRaceFields\(.*?\n}\n", src, re.S)
    if not m:
        return ["policy.go 里找不到 policyRaceFields（函数改名了？），判据漂移检查没法做"]
    names = set(re.findall(r'fmt\.Sprintf\("([a-zA-Z]+)=', m.group(0)))
    mine = {n for n, _ in RACE_FIELDS}
    if names != mine:
        return [
            "判据漂移：policy.go 的 policyRaceFields 有 [%s]，本脚本有 [%s] —— 两边必须同时改"
            % (",".join(sorted(names)), ",".join(sorted(mine)))
        ]
    return []


def race_fields(policy: dict) -> list[str]:
    out = []
    for name, nonzero in RACE_FIELDS:
        v = policy.get(name)
        if isinstance(v, (int, float)) and nonzero(v):
            out.append(name + "=" + str(v))
    return out


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def resolve_alias_path(cfg: dict) -> str:
    raw = cfg.get("aliasMap") or "~/.zcode/v2/model-alias-map.json"
    return os.path.expanduser(raw)


def chains_of(am: dict) -> dict[str, list[str]]:
    """复刻 alias.Map.Chains()：无 chain 的模型是 [channel]，有 chain 就逐跳取 channel。"""
    out = {}
    for name, target in (am.get("models") or {}).items():
        hops = target.get("chain") or []
        if hops:
            out[name] = [h.get("channel") or "" for h in hops]
        else:
            ch = target.get("channel") or ""
            out[name] = [ch] if ch else []
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    problems: list[str] = []
    warns: list[str] = []
    notes: list[str] = []

    cfg = load_json(ZGATE_JSON)
    policy_map = cfg.get("channelPolicy") or {}
    upstreams = cfg.get("upstreams") or {}

    # 别名表是运行时状态（~/.zcode/v2/model-alias-map.json），不进仓库：CI 的干净检出
    # 里必然没有它。缺表时只跳过「单跳/多跳」这一半判定，其余三项（渠道引用、策略键
    # 拼写、判据漂移）照跑 —— 2026-11-17 第一版把它当 FAIL，直接让 CI 红了。
    alias_path = resolve_alias_path(cfg)
    if not os.path.exists(alias_path):
        notes.append("别名表不存在（" + alias_path + "），跳过单跳/多跳判定（CI 干净检出属常态）")
        chains = {}
    else:
        try:
            chains = chains_of(load_json(alias_path))
        except (OSError, ValueError) as e:
            problems.append("别名表解析失败: " + alias_path + " " + repr(e))
            chains = {}

    # --- 1) 复刻 ValidatePolicies ---
    single: dict[str, list[str]] = {}
    multi: set[str] = set()
    for name, chs in chains.items():
        if not chs:
            continue
        if len(chs) == 1:
            single.setdefault(chs[0], []).append(name)
        else:
            for ch in chs:
                multi.add(ch)

    for ch in sorted(policy_map):
        fields = race_fields(policy_map[ch])
        if not fields:
            continue
        names = sorted(single.get(ch, []))
        if not names:
            continue
        shown = names[:6] + (["等 %d 个" % len(names)] if len(names) > 6 else [])
        line = "channel=%s 字段=[%s] 影响模型=[%s]" % (ch, ",".join(fields), ",".join(shown))
        if ch in multi:
            warns.append("策略在单跳模型上不生效 " + line)
        else:
            problems.append(
                "FATAL 策略完全无效（渠道只服务单跳模型，多跳字段永远读不到）"
                + line
                + " -> 删掉这些字段，否则 zgate 拒绝启动（2026-11-17 全站 503 的原因）"
            )

    # --- 1.5) 判据漂移（本脚本 vs policy.go）---
    problems.extend(drift_problems())

    # --- 2) channelPolicy / upstreams 互相引用 ---
    for ch in sorted(policy_map):
        if ch not in upstreams:
            problems.append("channelPolicy 有 %s，但 upstreams 里没有这个渠道（字段永远读不到）" % ch)
    for ch in sorted(upstreams):
        if not (upstreams[ch] or {}).get("base"):
            problems.append("upstreams.%s 没有 base（该渠道的跳会拿空地址去请求）" % ch)

    # --- 3) 策略键拼写（encoding/json 不报未知键）---
    for ch in sorted(policy_map):
        unknown = sorted(set(policy_map[ch]) - KNOWN_POLICY_KEYS)
        if unknown:
            problems.append(
                "channelPolicy.%s 有未知键 %s（ChannelPolicy 不认，静默失效）" % (ch, ",".join(unknown))
            )

    # --- 4) 别名链每一跳都要有落点 ---
    bad_hops = []
    for name in sorted(chains):
        for ch in chains[name]:
            if not ch:
                bad_hops.append(name + ": 有跳没写 channel")
            elif ch not in upstreams:
                bad_hops.append(name + ": 跳到 " + ch + "，upstreams 里没有这个渠道")
    if bad_hops:
        problems.extend("别名链落点错误 " + x for x in bad_hops[:10])
        if len(bad_hops) > 10:
            problems.append("别名链落点错误 另有 %d 条未列" % (len(bad_hops) - 10))

    notes.append("模型 %d 条 / 渠道 %d 个 / channelPolicy %d 段"
                 % (len(chains), len(upstreams), len(policy_map)))
    if not chains:
        notes.append("本次未做单跳/多跳判定：Fatal 结论只能在本机（有别名表）得出")

    if not a.quiet:
        for n in notes:
            print("[INFO] " + n)
        for w in warns:
            print("[WARN] " + w)
    for p in problems:
        print("[FAIL] " + p)

    if problems:
        print("[FAIL] check-zgate-policy: %d 项（Fatal 会让 zgate 拒绝启动）" % len(problems))
        return 1
    if not a.quiet:
        print("[OK] check-zgate-policy: 无 Fatal / 无引用错误（WARN %d 条不拦）" % len(warns))
    return 0


if __name__ == "__main__":
    sys.exit(main())
