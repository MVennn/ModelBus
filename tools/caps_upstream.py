#!/usr/bin/env python3
"""上游能力真值采集器（catalog/upstream_caps.json）

本仓以 DSH 为主宿主；采集结果写 catalog/ 供各类 agent 只读，不写回任何现网配置。。

model_caps.py 的解析链是「别名 → 兼容投影内置规则 → 现网 providerModelRules」，
它能证明某个字段「规则里没写」，但证明不了「这个模型真实上限是多少」。真值只在
各家上游的模型接口里：

  WB  http://127.0.0.1:7863/panel/api/models    context_length / max_output_tokens /
                                                supports_tool_call / supports_images
  OC  https://opencode.ai/zen/go/v1/models      limit.context / limit.output /
                                                capabilities.tools / modalities.input
  QN  https://api.qnaigc.com/v1/models          context_length / max_tokens

本工具按别名链路的每一跳去对应上游对号，取第一跳（主用跳）的值，跨跳不一致就记
conflicts 但不擅自取舍；取不到的字段留 null，绝不推算。产出是证据快照：可以提交、
可以离线复算，门禁不依赖网络。

用法：
  python -B tools/caps_upstream.py --fetch      # 联网采集并写 catalog/upstream_caps.json
  python -B tools/caps_upstream.py              # 读快照打印表格（不联网）
  python -B tools/caps_upstream.py --check      # 与现网 provider_config 比对，有差异 exit 1
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ALIAS_MAP = os.path.expanduser("~/.zcode/v2/model-alias-map.json")
DEFAULT_WB_CONFIG = os.path.join(REPO, "gateways", "upstream", "workbuddy", "config.json")
DEFAULT_SNAPSHOT = os.path.join(REPO, "catalog", "upstream_caps.json")
DEFAULT_CURRENT = os.path.expanduser("~/.zcode/v2/provider_config.json")
DEFAULT_EVIDENCE = os.path.join(REPO, "catalog", "upstream_caps_evidence.json")

OC_BASE = "https://opencode.ai/zen/go/v1"
QN_BASE = "https://api.qnaigc.com/v1"

CAPABILITY_FIELDS = ("context_window", "max_output_tokens", "supports_tool_call", "supports_image")


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) caps-upstream/1"


def http_json(url, headers=None, timeout=25):
    request = urllib.request.Request(url)
    # 部分上游（OC）对默认的 Python-urllib UA 直接回 403，这里固定带浏览器 UA。
    request.add_header("User-Agent", UA)
    request.add_header("Accept", "application/json")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


# ---------------------------------------------------------------- 上游采集


def fetch_wb():
    """WorkBuddy 面板接口：唯一同时给出 ctx / max / tool / img 的来源。"""
    config = load_json(DEFAULT_WB_CONFIG)
    host = str(config.get("listen") or ":7863").lstrip(":")
    url = "http://127.0.0.1:%s/panel/api/models" % host
    payload = http_json(url, {"Authorization": "Bearer %s" % config.get("api_key", "")})
    table = {}
    for model in payload.get("models") or []:
        ctx = model.get("context_length") or model.get("max_allowed_size")
        table[str(model.get("id"))] = {
            "context_window": int(ctx) if ctx else None,
            "max_output_tokens": int(model["max_output_tokens"])
            if model.get("max_output_tokens")
            else None,
            "supports_tool_call": model.get("supports_tool_call"),
            "supports_image": model.get("supports_images"),
            "reasoning_values": model.get("supported_efforts"),
        }
    return {"url": url, "count": len(table), "models": table}


def fetch_oc():
    payload = http_json(OC_BASE + "/models")
    table = {}
    for model in payload.get("data") or []:
        limit = model.get("limit") or {}
        inputs = (model.get("modalities") or {}).get("input") or []
        tools = (model.get("capabilities") or {}).get("tools") or {}
        efforts = (model.get("capabilities") or {}).get("reasoning") or {}
        ctx = limit.get("context")
        out = limit.get("output")
        table[str(model.get("id"))] = {
            "context_window": int(ctx) if ctx else None,
            "max_output_tokens": int(out) if out else None,
            "supports_tool_call": tools.get("supported"),
            # 明确列出输入模态才能断言 false；缺字段才是 None。
            "supports_image": (
                any(str(item).startswith("image") for item in inputs) if inputs else None
            ),
            "reasoning_values": efforts.get("effort"),
        }
    return {"url": OC_BASE + "/models", "count": len(table), "models": table}


def fetch_qn():
    payload = http_json(QN_BASE + "/models")
    table = {}
    for model in payload.get("data") or []:
        ctx = model.get("context_length")
        out = model.get("max_tokens")
        table[str(model.get("id"))] = {
            "context_window": int(ctx) if ctx else None,
            "max_output_tokens": int(out) if out else None,
            "supports_tool_call": None,
            "supports_image": None,
            "reasoning_values": None,
        }
    return {"url": QN_BASE + "/models", "count": len(table), "models": table}


# ---------------------------------------------------------------- 别名对号

# 渠道 → 上游表；不在表里的渠道（QD / GM / HJ / QW）目前不提供能力元数据。
CHANNEL_SOURCE = {"WB": "wb", "OC": "oc", "QN": "qn"}

UNKNOWN_CHANNELS = {
    "QD": "Qoder 端点（127.0.0.1:8790）未暴露 context/limit 元数据",
    "GM": "GM 端点 /v1/models 只返回 id/object/owned_by，无能力字段",
    "HJ": "HJ 端点 /v1/models 需鉴权且未见能力字段",
    "QW": "QW 端点走 anthropic 协议，未暴露模型元数据",
}


def hop_candidates(hop):
    base = str(hop.get("base_model") or hop.get("base") or "")
    out = []
    for value in (hop.get("base"), base):
        if value:
            out.append(str(value))
            if ":" in str(value):
                out.append(str(value).split(":", 1)[1])
    # WB 面板把模型登记成 cn:xxx，别名里写 xxx，两种都要试。
    for value in list(out):
        if ":" not in value:
            out.append("cn:" + value)
    ordered = []
    for value in out:
        if value not in ordered:
            ordered.append(value)
    return ordered


def lookup(table, hop):
    for candidate in hop_candidates(hop):
        if candidate in table:
            return candidate, table[candidate]
    # 大小写不敏感兜底：QD 写 Qwen3.8-Max、OC 写 qwen3.8-max，同款模型不同拼法。
    lowered = {str(key).lower(): key for key in table}
    for candidate in hop_candidates(hop):
        hit = lowered.get(candidate.lower())
        if hit is not None:
            return hit, table[hit]
    return None, None


def collect(alias_map, sources):
    models = []
    for display, entry in (alias_map.get("models") or {}).items():
        hops = entry.get("chain") or []
        fields = {field: None for field in CAPABILITY_FIELDS}
        field_sources = {field: None for field in CAPABILITY_FIELDS}
        conflicts = []
        seen = {}
        notes = []
        for index, hop in enumerate(hops):
            channel = str(hop.get("channel") or "")
            source_key = CHANNEL_SOURCE.get(channel)
            if not source_key:
                if index == 0 and channel in UNKNOWN_CHANNELS:
                    notes.append(UNKNOWN_CHANNELS[channel])
                continue
            match_id, record = lookup(sources[source_key]["models"], hop)
            if not record:
                if index == 0:
                    notes.append("%s 上游未列出 %s" % (channel, hop.get("base") or hop.get("base_model")))
                continue
            for field in CAPABILITY_FIELDS:
                value = record.get(field)
                if value is None:
                    continue
                seen.setdefault(field, {})
                seen[field].setdefault(repr(value), (value, channel, match_id, index))
                if fields[field] is None and index == 0:
                    fields[field] = value
                    field_sources[field] = "%s:%s" % (channel, match_id)
        for field, values in seen.items():
            distinct = {repr(item[0]) for item in values.values()}
            if len(distinct) > 1:
                conflicts.append(
                    {
                        "field": field,
                        "values": {item[1] + "/" + item[2]: item[0] for item in values.values()},
                        "picked": field_sources.get(field),
                    }
                )
        # 主用跳没有的字段，用其它跳的同名字段补位并注明来源
        for field in CAPABILITY_FIELDS:
            if fields[field] is not None:
                continue
            for value, channel, match_id, _index in list(seen.get(field, {}).values()):
                fields[field] = value
                field_sources[field] = "%s:%s" % (channel, match_id)
                notes.append("%s 取自非主用跳 %s" % (field, channel))
                break
        # 主用渠道不提供元数据时，去其它已采集上游找同名模型，只作交叉参考（不填 fields）
        cross = []
        if fields["context_window"] is None:
            for hop in hops[:1]:
                for source_key, source in sources.items():
                    match_id, record = lookup(source.get("models") or {}, hop)
                    if record:
                        cross.append(
                            {
                                "source": "%s:%s" % (source_key.upper(), match_id),
                                "channel": hop.get("channel"),
                                **{field: record.get(field) for field in CAPABILITY_FIELDS},
                            }
                        )
                        break
        models.append(
            {
                "display": display,
                "channel": (hops[0].get("channel") if hops else None),
                "base": (hops[0].get("base_model") or hops[0].get("base")) if hops else None,
                **fields,
                "field_sources": field_sources,
                "conflicts": conflicts,
                "cross": cross,
                "notes": "；".join(notes),
            }
        )
    return models


# ---------------------------------------------------------------- 输出


def merge_evidence(models, evidence):
    """把「接口取不到、靠取证补」的结论合进快照（catalog/upstream_caps_evidence.json）。

    规则：只在接口没给值（None）时采用取证值，并标 field_sources=evidence:<出处>；
    接口有值且与取证值不同则记 conflicts、保留接口值 —— 接口实测永远优先于文档。
    """
    if not evidence:
        return models
    by_display = {item.get("display"): item for item in models}
    for item in evidence.get("models") or []:
        target = by_display.get(item.get("display"))
        if target is None:
            continue
        sources = target.setdefault("field_sources", {})
        for field in CAPABILITY_FIELDS:
            value = item.get(field)
            if value is None:
                continue
            current = target.get(field)
            if current is None:
                target[field] = value
                sources[field] = (item.get("field_sources") or {}).get(field) or "evidence:%s" % (item.get("channel") or "-")
            elif current != value:
                target.setdefault("conflicts", []).append(
                    {
                        "field": field,
                        "values": {"evidence": value, "upstream": current},
                        "picked": sources.get(field),
                    }
                )
        for conflict in item.get("conflicts") or []:
            target.setdefault("conflicts", []).append(conflict)
        note = (item.get("notes") or "").strip()
        if note:
            existing = (target.get("notes") or "").strip()
            target["notes"] = (existing + "；" + note).strip("；") if existing else note
    return models


def build_snapshot(alias_map, fetch=True, evidence=None):
    sources = {}
    if fetch:
        for key, loader in (("wb", fetch_wb), ("oc", fetch_oc), ("qn", fetch_qn)):
            try:
                sources[key] = loader()
            except Exception as exc:  # 单个上游失败不影响其它来源
                sources[key] = {"url": None, "count": 0, "models": {}, "error": str(exc)}
    return {
        "schema": "caps_upstream/v1",
        "generated_by": "tools/caps_upstream.py",
        "generated_at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "note": "上游接口原样采集的能力字段；接口取不到的渠道按 catalog/upstream_caps_evidence.json 的取证结论补齐（field_sources 以 evidence: 开头）；null = 没有来源，禁止推算补值。",
        "sources": {
            key: {
                "url": value.get("url"),
                "count": value.get("count", 0),
                "error": value.get("error"),
            }
            for key, value in sources.items()
        },
        "models": merge_evidence(collect(alias_map, sources), evidence) if fetch else [],
    }


def merge_into_snapshot(alias_map, existing, fetch=True):
    fresh = build_snapshot(alias_map, fetch=fetch)
    if not fresh["models"]:
        return existing
    return fresh


def render(snapshot):
    lines = [
        "%-20s %-4s %-10s %-8s %-6s %-6s %s"
        % ("display", "ch", "ctx", "max_out", "tool", "img", "来源"),
    ]
    for item in snapshot.get("models") or []:
        lines.append(
            "%-20s %-4s %-10s %-8s %-6s %-6s %s"
            % (
                item["display"],
                item.get("channel") or "-",
                item.get("context_window") if item.get("context_window") is not None else "-",
                item.get("max_output_tokens") if item.get("max_output_tokens") is not None else "-",
                item.get("supports_tool_call") if item.get("supports_tool_call") is not None else "-",
                item.get("supports_image") if item.get("supports_image") is not None else "-",
                ",".join(
                    sorted({value for value in (item.get("field_sources") or {}).values() if value})
                )
                or "none",
            )
        )
    return "\n".join(lines)


def current_rules(path):
    if not os.path.exists(path):
        return {}
    data = load_json(path)
    rules = ((data.get("config") or {}).get("modelConfigRules") or {}).get("providerModelRules") or []
    table = {}
    for rule in rules:
        config = rule.get("config") or {}
        props = config.get("properties") or {}
        table[str(rule.get("modelId"))] = {
            "context_window": props.get("contextWindow"),
            "max_output_tokens": (config.get("optionSpecs") or {}).get("maxOutputTokens", {}).get("max"),
            "supports_tool_call": props.get("supportsToolCall"),
            "supports_image": (props.get("inputFormat") or {}).get("supportsImage"),
        }
    return table


def check(snapshot, current):
    diffs = []
    for item in snapshot.get("models") or []:
        have = current.get(item["display"])
        if not have:
            continue
        for field in CAPABILITY_FIELDS:
            value = item.get(field)
            if value is None:
                continue
            if have.get(field) != value:
                diffs.append((item["display"], field, have.get(field), value, item["field_sources"].get(field)))
    return diffs


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass
    parser = argparse.ArgumentParser(prog="caps_upstream.py", description="采集上游能力真值快照")
    parser.add_argument("--alias-map", default=DEFAULT_ALIAS_MAP)
    parser.add_argument("--snapshot", default=DEFAULT_SNAPSHOT)
    parser.add_argument("--current", default=DEFAULT_CURRENT, help="现网 provider_config.json（只读）")
    parser.add_argument("--evidence", default=DEFAULT_EVIDENCE, help="接口取不到字段时的取证结论文件")
    parser.add_argument("--fetch", action="store_true", help="联网采集并重写快照")
    parser.add_argument("--check", action="store_true", help="与现网比对，有差异 exit 1")
    parser.add_argument("--json", action="store_true", help="输出快照 JSON")
    args = parser.parse_args(argv)

    alias_map = load_json(os.path.expanduser(args.alias_map))
    path = os.path.expanduser(args.snapshot)

    if args.fetch:
        evidence_path = os.path.expanduser(args.evidence)
        evidence = load_json(evidence_path) if os.path.exists(evidence_path) else None
        snapshot = build_snapshot(alias_map, fetch=True, evidence=evidence)
        parent = os.path.dirname(path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")
        print("已写出 %s（%d 条）" % (args.snapshot, len(snapshot["models"])), file=sys.stderr)
    else:
        snapshot = load_json(path)

    if args.json:
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        return 0

    print(render(snapshot))
    if args.check:
        diffs = check(snapshot, current_rules(os.path.expanduser(args.current)))
        print()
        if not diffs:
            print("现网与上游真值一致。")
            return 0
        print("现网与上游真值差异 %d 处：" % len(diffs))
        for display, field, have, want, source in diffs:
            print("  %-22s %-20s %-10s → %-10s %s" % (display, field, have, want, source))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
