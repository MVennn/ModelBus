#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""agent_profiles.py — DSH 主宿主下各类 agent 的只读模型投影。

一句话：以 catalog/model_caps.json 为唯一能力真源，为 DSH 会话 / 子代理 /
headless / 服务插件等各类 agent 生成只读模型投影，不写任何现网配置。

设计边界（docs/DSH-FIRST.md §3 / §5 / §6）：
  * DSH 负责 agent 运行时，ModelBus 负责模型供给与路由策略；
  * 本模块只读 catalog/ 与（可选）alias map，绝不写回真源；
  * 写仍单写者：cordis.patch.yml 只由 tools/dsh_sync.py 写，
    兼容投影 provider_config.json 只由 providers/*_sync.py 写；
  * 契约层一个字不动：~/.zcode/v2/provider_config.json、
    ZCODE_PERSONAL_PROVIDER_CONFIG_FILE / ZCODE_BUILTIN / ZCODE_GATEWAY_KEY、
    zcode-main|zcode-free|zcode-saver route id、schema 键、NOTICE 商标段照旧。

用法：
    python -B tools/agent_profiles.py --list      # 列 agent 类型与模型子集
    python -B tools/agent_profiles.py --check     # 校验 catalog 与 profile，漂移 exit 1
    python -B tools/agent_profiles.py --json      # 机器可读投影
    python -B tools/agent_profiles.py --alias-map <path> --check   # 连别名表一起对

退出码：0 通过 / 1 有漂移 / 2 输入或环境错误。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
CATALOG = REPO / "catalog" / "model_caps.json"
SCHEMA = "model_caps/v1"
VALID_CONFIDENCE = {"high", "medium", "low"}
CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}
CAPABILITY_FIELDS = ("context_window", "max_output_tokens", "supports_tool_call", "supports_image")
GATEWAY = "http://127.0.0.1:7871/v1"

# DSH 主宿主下的 agent 类型。include 规则只是「按能力/置信度取只读子集」——
# 所有 agent 共用同一份 catalog 真源与同一个 gateways/zgate 单一入口，
# 不给每个 agent 造一套独立配置。
AGENT_PROFILES: dict[str, dict[str, Any]] = {
    "session": {
        "label": "DSH 主会话（GUI 交互）",
        "note": "全量模型；交互场景可用图像与工具调用，允许低置信度条目并由 --check 标注来源。",
        "min_confidence": "low",
        "require": (),
        "text_only": False,
        "header": "X-Agent-Id: session",
    },
    "subagent": {
        "label": "子代理 / 委派任务",
        "note": "必须支持工具调用；能力字段收敛到 medium 以上，避免低置信度数值拖累判活。",
        "min_confidence": "medium",
        "require": ("supports_tool_call",),
        "text_only": False,
        "header": "X-Agent-Id: <preset-id>",
    },
    "headless": {
        "label": "无头任务（每日同步 / CI / 定时）",
        "note": "只要文本与稳定推理档位；supports_image 为空不成为排除理由。",
        "min_confidence": "low",
        "require": (),
        "text_only": True,
        "header": "X-Agent-Id: headless",
    },
    "service-plugin": {
        "label": "服务插件（网关内驻留）",
        "note": "只取 high 置信度且带工具调用的模型，避免插件侧能力漂移。",
        "min_confidence": "high",
        "require": ("supports_tool_call",),
        "text_only": False,
        "header": "X-Agent-Id: <plugin-id>",
    },
}


class AgentProfileError(RuntimeError):
    """输入或环境错误（退出码 2）。"""


def load_catalog(path: Path = CATALOG) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AgentProfileError("找不到能力真源：%s" % path) from exc
    except json.JSONDecodeError as exc:
        raise AgentProfileError("能力真源不是合法 JSON：%s（%s）" % (path, exc)) from exc
    if not isinstance(doc, dict) or not isinstance(doc.get("models"), list):
        raise AgentProfileError("能力真源缺 models 数组：%s" % path)
    return doc


def project(profile_id: str, doc: dict[str, Any]) -> dict[str, Any]:
    """按 agent profile 从 catalog 取只读子集；纯函数，不写文件。"""
    prof = AGENT_PROFILES.get(profile_id)
    if prof is None:
        raise AgentProfileError(
            "未知 agent 类型：%s（可用：%s）" % (profile_id, ", ".join(AGENT_PROFILES)))
    threshold = CONFIDENCE_ORDER[prof["min_confidence"]]
    require = tuple(prof.get("require") or ())
    picked: list[dict[str, Any]] = []
    skipped: list[str] = []
    for item in doc.get("models") or []:
        if not isinstance(item, dict) or not str(item.get("display") or ""):
            continue
        conf = item.get("confidence")
        if conf not in CONFIDENCE_ORDER or CONFIDENCE_ORDER[conf] < threshold:
            skipped.append(str(item["display"]) + "(confidence=" + str(conf) + ")")
            continue
        if any(item.get(field) is not True for field in require):
            skipped.append(str(item["display"]) + "(缺 " + "/".join(require) + ")")
            continue
        picked.append({
            "id": item["display"],
            "channel": item.get("channel"),
            "contextWindow": item.get("context_window"),
            "maxTokens": item.get("max_output_tokens"),
            "input": ["text", "image"] if item.get("supports_image") else ["text"],
            "reasoningValues": item.get("reasoning_values") or [],
            "source": item.get("source"),
            "confidence": conf,
        })
    return {
        "profile": profile_id,
        "label": prof["label"],
        "note": prof["note"],
        "header": prof["header"],
        "textOnly": bool(prof.get("text_only")),
        "source": "catalog/model_caps.json",
        "gateway": GATEWAY,
        "models": picked,
        "skipped": skipped,
    }


def validate(doc: dict[str, Any]) -> list[str]:
    """返回漂移明细；空列表代表 --check 通过。"""
    problems: list[str] = []
    if doc.get("schema") != SCHEMA:
        problems.append("schema 不是 %s（当前 %r）" % (SCHEMA, doc.get("schema")))
    seen: set[str] = set()
    for i, item in enumerate(doc.get("models") or []):
        tag = "#%d %s" % (i + 1, (item.get("display") or "<空>") if isinstance(item, dict) else "<非对象>")
        if not isinstance(item, dict):
            problems.append(tag + " 不是对象")
            continue
        display = str(item.get("display") or "")
        if not display:
            problems.append(tag + " 缺 display")
        elif display in seen:
            problems.append(tag + " display 重复")
        else:
            seen.add(display)
        source = item.get("source")
        conf = item.get("confidence")
        if conf not in VALID_CONFIDENCE:
            problems.append(tag + " confidence 非法：%r" % conf)
        if source == "none":
            for field in CAPABILITY_FIELDS:
                if item.get(field) is not None:
                    problems.append(tag + " source=none 但 %s 编了值 %r" % (field, item.get(field)))
        rv = item.get("reasoning_values")
        if rv is not None and (not isinstance(rv, list) or any(not isinstance(v, str) for v in rv)):
            problems.append(tag + " reasoning_values 不是字符串数组")
    for pid in AGENT_PROFILES:
        if not project(pid, doc)["models"]:
            problems.append("agent profile %s 命中 0 个模型（include 规则过严）" % pid)
    return problems


def agent_bucket(headers: Mapping[str, str]) -> str:
    """按 X-Agent-Id（或 DSH preset id）返回稳定分桶键。

    接口占位：Go 侧 gateways/zgate 的 per-agent 预算 / 冷却分桶属于后续演进，
    本轮不实现、不改 Go 代码、不重启长驻网关（仓规 §6）。这里只保证同一
    agent 身份稳定落到同一桶，供路由策略层预留接缝；缺省身份落 default 桶。
    """
    for key in ("X-Agent-Id", "x-agent-id", "X-Dsh-Preset", "x-dsh-preset"):
        value = headers.get(key)
        if value and str(value).strip():
            return str(value).strip()
    return "default"


def alias_alignment(doc: dict[str, Any], alias_path: Path) -> list[str]:
    """（可选）catalog 与 alias map 的型号对齐报告；不写任何文件。"""
    try:
        alias = json.loads(alias_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AgentProfileError("alias map 读不了：%s（%s）" % (alias_path, exc)) from exc
    models = alias.get("models") if isinstance(alias, dict) else None
    if not isinstance(models, dict):
        raise AgentProfileError("alias map 缺 models 对象：%s" % alias_path)
    caps = {str(item.get("display")) for item in doc.get("models") or [] if isinstance(item, dict)}
    alias_ids = {str(key) for key in models}
    out: list[str] = []
    only_alias = sorted(alias_ids - caps)
    only_caps = sorted(caps - alias_ids)
    if only_alias:
        out.append("alias map 有 %d 个型号不在 catalog：%s" % (len(only_alias), "、".join(only_alias[:8])))
    if only_caps:
        out.append("catalog 有 %d 个型号不在 alias map：%s" % (len(only_caps), "、".join(only_caps[:8])))
    return out


def render_list(projections: list[dict[str, Any]]) -> str:
    lines = ["DSH 主宿主 · agent 只读投影（真源 catalog/model_caps.json，入口 127.0.0.1:7871）", ""]
    for p in projections:
        lines.append("[%s] %s" % (p["profile"], p["label"]))
        lines.append("  " + p["note"])
        lines.append("  分桶头 %s ｜ 命中 %d 个模型 ｜ 跳过 %d 个" % (p["header"], len(p["models"]), len(p["skipped"])))
        lines.append("  " + "、".join(m["id"] for m in p["models"]))
        lines.append("")
    lines.append("红线：所有 agent 共用一份 catalog 真源与单一网关入口；写仍单写者，本工具不写任何现网配置。")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DSH 主宿主下各类 agent 的只读模型投影")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--list", action="store_true", help="列 agent 类型与模型子集")
    mode.add_argument("--check", action="store_true", help="校验 catalog 与 profile，漂移 exit 1")
    mode.add_argument("--json", action="store_true", help="输出机器可读投影")
    parser.add_argument("--profile", help="只投影指定 agent 类型")
    parser.add_argument("--catalog", type=Path, default=CATALOG, help="能力真源（默认 catalog/model_caps.json）")
    parser.add_argument("--alias-map", type=Path, help="（可选）连带校验 alias map 对齐")
    args = parser.parse_args(argv)

    doc = load_catalog(args.catalog)
    ids = [args.profile] if args.profile else list(AGENT_PROFILES)
    projections = [project(pid, doc) for pid in ids]

    if args.check:
        problems = validate(doc)
        if args.alias_map:
            problems += alias_alignment(doc, args.alias_map)
        if problems:
            print("[FAIL] %d 个问题：" % len(problems))
            for p in problems:
                print("   ", p)
            return 1
        print("[OK] catalog %d 条 / %d 个 agent profile 全部通过%s" % (
            len(doc.get("models") or []), len(ids), "（含 alias map 对齐）" if args.alias_map else ""))
        return 0
    if args.json:
        print(json.dumps({"source": str(args.catalog), "profiles": projections}, ensure_ascii=False, indent=2))
        return 0
    print(render_list(projections))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AgentProfileError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        raise SystemExit(2)
