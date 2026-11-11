#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""model_caps.py —— 20 个模型的「能力字段真值」解析器 + CLI

本仓以 DSH 为主宿主 + 各类 agent：本工具解析兼容投影 provider_config.json 的
能力字段并产出 catalog/ 真源；DSH 侧由 tools/dsh_sync.py 写 cordis.patch.yml。
third-party/zcode/ 正本与 ~/.zcode/v2/ 契约路径原样保留。

问题背景
--------
兼容投影 provider_config.json 的模型能力（上下文窗口 / 最大输出 / 是否支持图片 / 是否支持工具调用 /
推理档位）由几种规则共同决定：

* providerSiteRules：modelMatch + apiTypeMatch + baseUrlMatch 三元组，
  面向**上游模型 id** 与**上游 base**（例如 deepseek-v4.1-flash 配
  https://opencode.ai/zen/go/v1 ）。这是唯一带专属数字的一层。
* modelRules / modelApiRules：只按模型 id（大小写不敏感）或 id+apiType 匹配，
  属于「族级」规则，覆盖同族模型但不区分渠道。
* builtinProviderModelRules / templateModelRules：按 providerId+modelId /
  templateId+modelId 精确匹配，通常只带 enabled。

运行时真正生效的匹配语义取自已入仓的正本 third-party/zcode/model-config.ts：

* matchesRule（同文件 544-546 行）= 正则加前后锚点做**整串全匹配**
  （^ 加 (?:pattern) 加 $）；模型 id 一路带忽略大小写标志 i，
  apiType / baseUrl 不带。
* resolve()（同文件 387-423 行）= 按规则表顺序**逐条 overlay**，后命中的
  字段覆盖先命中的字段；未出现的字段（undefined）继承，显式 null 才是清空。
* normalizeBaseURLForRuleMatch（同文件 548-559 行）= 解析 URL、去掉末尾斜杠、
  保留 query/hash；解析失败则不参与 site 规则匹配。

因此本工具对每一跳都按上述语义重放匹配，得到「该跳在该 base 上会拿到什么」。

三层证据链（置信度递减）
------------------------
1. site-rule / high：alias-map 的 base_model + 该跳 base + 该跳 protocol 映射出的
   apiType，命中 providerSiteRules。
2. builtin-family / medium、builtin-exact / low：site 规则全不命中时才看 builtin 的
   modelRules / modelApiRules / builtinProviderModelRules / templateModelRules。
   **只命中通配 .* 不算证据**（否则 20 条全被 1000000/128000 污染，正是本次要修的 bug）。
3. current / low：现网 provider_config.json 里已有的值，只作兜底。
4. none：以上都没有 —— 输出 null，绝不编数字。

多跳优先级：先主 channel 那一跳（模型顶层 channel/base/protocol），再按 chain 顺序；
第一跳拿到值即胜出，其余命中记进 conflicts 供人工复核。

用法
----
    python -B tools/model_caps.py                    # 表格
    python -B tools/model_caps.py --check            # 对比现网，有差异 exit 1
    python -B tools/model_caps.py --json             # 机器可读
    python -B tools/model_caps.py --catalog catalog/model_caps.json
    python -B tools/model_caps.py --apply --target .work/provider_config.copy.json

约束：--apply 只写 --target 指定的副本；目标落在 ~/.zcode 下一律拒绝
（真身不碰、进程不重启）。读 provider_config.json 时只取
config.modelConfigRules 段，凭据（apiKey 等）不读、不落盘、不打印。
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from urllib.parse import urlsplit

# ---------------------------------------------------------------- 常量

PROTOCOL_TO_API_TYPE = {
    "chat": "openai-chat-completions",
    "messages": "anthropic-messages",
    "responses": "openai-responses",
}

#: 参与「真值」判定的能力字段，顺序即表格列顺序。
CAPABILITY_FIELDS = (
    "context_window",
    "max_output_tokens",
    "supports_tool_call",
    "supports_image",
)

#: 推理档位相关字段。
REASONING_FIELDS = ("reasoning_values", "reasoning_map")

#: 只有这种「匹配任何串」的 pattern 算通配兜底，不作为证据。
_WILDCARD_PATTERNS = (".*", "(?:.*)")

SOURCE_CONFIDENCE = {
    "site-rule": "high",
    "builtin-family": "medium",
    "builtin-exact": "low",
    "current": "low",
    "none": "none",
}

DEFAULT_ALIAS_MAP = "~/.zcode/v2/model-alias-map.json"
DEFAULT_BUILTIN = "third-party/zcode/zcode-builtin.json"
DEFAULT_CURRENT = "~/.zcode/v2/provider_config.json"


# ---------------------------------------------------------------- 基础工具


def _expand(path):
    """展开 ~ 与相对路径（相对当前工作目录）。"""
    return os.path.abspath(os.path.expanduser(path))


def load_json(path):
    """读 JSON。

    仓里的 zcode-builtin.json 含裸 0xad 字节，严格 utf-8 解码可能失败，因此先按
    utf-8 严格读，失败再退回 errors=replace（替换字符只可能落在字符串值里，
    不影响结构）。
    """
    with io.open(path, "rb") as handle:
        raw = handle.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    if text[:1] == "\ufeff":
        text = text[1:]
    return json.loads(text)


def _write_text(path, text):
    """按 UTF-8 写文件，强制 LF（避免 Windows 下 CRLF 混进产物）。"""
    with io.open(path, "wb") as handle:
        handle.write(text.encode("utf-8"))


def _dump_json(data, indent=2):
    return json.dumps(data, ensure_ascii=False, indent=indent, sort_keys=False) + chr(10)


def is_wildcard(pattern):
    """.* / (?:.*) 视为通配兜底。"""
    if pattern is None:
        return False
    return pattern.strip() in _WILDCARD_PATTERNS


def match_rule(pattern, value, ignore_case=False):
    """复刻 matchesRule：正则 + 整串全匹配，可选忽略大小写。

    空值、非字符串、非法正则一律不命中（兼容投影引擎里非法正则会抛，这里退化为不命中）。
    """
    if pattern is None or not isinstance(value, str) or not value:
        return False
    flags = re.IGNORECASE if ignore_case else 0
    try:
        return re.fullmatch(pattern, value, flags) is not None
    except re.error:
        return False


def normalize_base(value):
    """复刻 normalizeBaseURLForRuleMatch：去末尾斜杠、保留 query/hash、主机小写。"""
    if not value:
        return None
    try:
        parts = urlsplit(value)
    except ValueError:
        return None
    if not parts.scheme or not parts.netloc:
        return None
    base = "%s://%s%s" % (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"))
    if parts.query:
        base += "?" + parts.query
    if parts.fragment:
        base += "#" + parts.fragment
    return base


def api_type_of(protocol):
    """协议 → apiType；未知协议原样返回（好让 .* 之类的 apiTypeMatch 仍能命中）。"""
    if protocol is None:
        return None
    return PROTOCOL_TO_API_TYPE.get(protocol, protocol)


# ---------------------------------------------------------------- 规则取值


def extract_config(cfg):
    """把一条规则的 config 摊平成「字段 → 值」。

    只有**出现过的键**才会被返回，对应兼容投影 overlay 的「未出现即继承」。
    显式 null 会以 None 返回，表示清空。
    """
    out = {}
    if not isinstance(cfg, dict):
        return out
    props = cfg.get("properties") or {}
    if "contextWindow" in props:
        out["context_window"] = props["contextWindow"]
    if "supportsToolCall" in props:
        out["supports_tool_call"] = props["supportsToolCall"]
    input_format = props.get("inputFormat") or {}
    if "supportsImage" in input_format:
        out["supports_image"] = input_format["supportsImage"]
    specs = cfg.get("optionSpecs") or {}
    max_tokens = specs.get("maxOutputTokens") or {}
    if "max" in max_tokens:
        out["max_output_tokens"] = max_tokens["max"]
    reasoning = specs.get("reasoningLevel") or {}
    if "values" in reasoning:
        out["reasoning_values"] = reasoning["values"]
    if "map" in reasoning:
        out["reasoning_map"] = reasoning["map"]
    return out


def _overlay(acc, add, source, wildcard=False):
    """按兼容投影语义 overlay：后到覆盖先到，逐字段记录来源。

    wildcard=True 表示该字段来自通配规则（modelMatch 为 .*），只能算「兜底默认值」，
    不能当模型专属证据 —— 上层据此把这类字段剔掉。
    """
    for key, value in add.items():
        acc[key] = {"value": value, "source": source, "wildcard": wildcard}


def _values(acc):
    return {key: item["value"] for key, item in acc.items()}


# ---------------------------------------------------------------- 第一层：site 规则


def resolve_site(rules, base_model, api_type, base):
    """在 providerSiteRules 里重放匹配并 overlay。

    返回 {"hits": [...], "fields": {...}, "base": 归一化后的 base}。
    hits 里每条都带规则下标与三元组原文，便于证据溯源。
    """
    normalized = normalize_base(base)
    hits = []
    acc = {}
    if normalized is None:
        return {"hits": [], "fields": {}, "base": None}
    for index, rule in enumerate(rules or []):
        pattern = rule.get("modelMatch")
        if not match_rule(pattern, base_model, ignore_case=True):
            continue
        api_match = rule.get("apiTypeMatch")
        if api_match is not None and not match_rule(api_match, api_type):
            continue
        base_match = rule.get("baseUrlMatch")
        # site 规则的 schema 要求 baseUrlMatch 必填；缺失即不可能命中。
        if base_match is None or not match_rule(base_match, normalized):
            continue
        extracted = extract_config(rule.get("config"))
        source = "providerSiteRules[%d]" % index
        _overlay(acc, extracted, source)
        hits.append(
            {
                "index": index,
                "modelMatch": pattern,
                "apiTypeMatch": api_match,
                "baseUrlMatch": base_match,
                "carries_values": bool(extracted),
            }
        )
    return {"hits": hits, "fields": acc, "base": normalized}


def _has_values(acc):
    """是否有任何能力字段拿到非 None 的值（reasoning 不计）。"""
    for key in CAPABILITY_FIELDS:
        item = acc.get(key)
        if item is not None and item["value"] is not None:
            return True
    return False


# ---------------------------------------------------------------- 第二层：builtin 其它规则


def resolve_builtin_other(rulesets, base_model, display, provider_id, api_types):
    """site 规则全不命中时，看 builtin 的其余四张表。

    返回 {"hits": [...], "fields": {...}}；hits 里带 wildcard 标记，
    调用方据此判定「只有通配兜底」。
    """
    acc = {}
    hits = []

    def consider(tier, index, rule, need_api=False):
        pattern = rule.get("modelMatch")
        if not match_rule(pattern, base_model, True):
            return
        if need_api:
            api_match = rule.get("apiTypeMatch")
            if api_match is not None and not any(
                match_rule(api_match, api) for api in api_types if api
            ):
                return
        extracted = extract_config(rule.get("config"))
        wildcard = is_wildcard(pattern)
        suffix = "(wildcard)" if wildcard else ""
        _overlay(acc, extracted, "%s[%d]%s" % (tier, index, suffix), wildcard=wildcard)
        hits.append(
            {
                "tier": tier,
                "index": index,
                "modelMatch": pattern,
                "apiTypeMatch": rule.get("apiTypeMatch"),
                "wildcard": wildcard,
                "carries_values": bool(extracted),
            }
        )

    for index, rule in enumerate(rulesets.get("modelRules") or []):
        consider("modelRules", index, rule)
    for index, rule in enumerate(rulesets.get("modelApiRules") or []):
        consider("modelApiRules", index, rule, need_api=True)

    # 精确层：providerId + modelId（现网 modelId 就是显示别名）
    for index, rule in enumerate(rulesets.get("builtinProviderModelRules") or []):
        if rule.get("providerId") != provider_id:
            continue
        if rule.get("modelId") not in (display, base_model):
            continue
        extracted = extract_config(rule.get("config"))
        if not extracted:
            continue
        _overlay(
            acc, extracted, "builtinProviderModelRules[%d]" % index, wildcard=False
        )
        hits.append(
            {
                "tier": "builtinProviderModelRules",
                "index": index,
                "modelMatch": rule.get("modelId"),
                "apiTypeMatch": None,
                "wildcard": False,
                "carries_values": True,
            }
        )
    # templateModelRules 需要 templateId，alias-map 无法推出，跳过而不是瞎猜。
    return {"hits": hits, "fields": acc}


def builtin_rulesets(builtin):
    """把 builtin 文件里的 config.modelConfigRules 取出来。"""
    config = builtin.get("config") or {}
    return config.get("modelConfigRules") or {}


# ---------------------------------------------------------------- 模板线索（只给建议）


def template_hint(builtin, base_model):
    """找出把该上游 id 收进 builtinModelIds 的 templateRule。

    templateRule 给出该模型**官方口径**的 (apiType, baseUrl)。据此再去 site 规则
    匹配，往往就能拿到专属数字 —— 但这条链路依赖「模板 = 该模型挂在哪」，属于
    间接推断，所以只写进 notes 当建议值，不参与真值判定。
    """
    config = builtin.get("config") or {}
    template_rules = (config.get("providerConfigRules") or {}).get("templateRules") or []
    site_rules = builtin_rulesets(builtin).get("providerSiteRules") or []
    target = (base_model or "").lower()
    if not target:
        return None
    for rule in template_rules:
        cfg = rule.get("config") or {}
        ids = [str(item).lower() for item in (cfg.get("builtinModelIds") or [])]
        if target not in ids:
            continue
        api = cfg.get("api") or {}
        api_type = api.get("type")
        base = api.get("baseUrl")
        resolved = resolve_site(site_rules, base_model, api_type, base)
        if not _has_values(resolved["fields"]):
            continue
        values = _values(resolved["fields"])
        return {
            "template_id": rule.get("templateId"),
            "api_type": api_type,
            "base": base,
            "site_rule_index": resolved["hits"][-1]["index"] if resolved["hits"] else None,
            "context_window": values.get("context_window"),
            "max_output_tokens": values.get("max_output_tokens"),
            "supports_image": values.get("supports_image"),
            "reasoning_values": values.get("reasoning_values"),
        }
    return None


# ---------------------------------------------------------------- 单模型解析


def order_hops(entry):
    """主 channel 那一跳排最前，其余按 chain 顺序去重。"""
    main = {
        "channel": entry.get("channel"),
        "base": entry.get("base"),
        "protocol": entry.get("protocol"),
        "base_model": entry.get("base_model"),
        "upstream": entry.get("upstream"),
    }
    ordered = []
    seen = set()

    def push(hop):
        key = (hop.get("base"), hop.get("protocol"), hop.get("base_model"), hop.get("channel"))
        if key in seen:
            return
        seen.add(key)
        ordered.append(hop)

    push(main)
    for hop in entry.get("chain") or []:
        push(hop)
    return ordered


def current_values(rule):
    """从现网 providerModelRules 的一条规则里取现值。"""
    if not rule:
        return {}
    return extract_config(rule.get("config"))


def resolve_model(display, entry, builtin, current_rule):
    """解析一个模型，返回完整记录（含逐字段来源与冲突）。"""
    rulesets = builtin_rulesets(builtin)
    site_rules = rulesets.get("providerSiteRules") or []
    hops = order_hops(entry)
    base_model = entry.get("base_model")

    hop_reports = []
    for priority, hop in enumerate(hops):
        api_type = api_type_of(hop.get("protocol"))
        resolved = resolve_site(site_rules, hop.get("base_model") or base_model, api_type, hop.get("base"))
        hop_reports.append(
            {
                "priority": priority,
                "main": priority == 0,
                "channel": hop.get("channel"),
                "base": hop.get("base"),
                "protocol": hop.get("protocol"),
                "api_type": api_type,
                "base_normalized": resolved["base"],
                "site_hits": resolved["hits"],
                "fields": resolved["fields"],
            }
        )

    winner = None
    for report in hop_reports:
        if _has_values(report["fields"]):
            winner = report
            break

    # 多跳冲突：凡是拿到值的跳都参与比对
    conflicts = []
    valued = [report for report in hop_reports if _has_values(report["fields"])]
    for field in CAPABILITY_FIELDS:
        seen = []
        for report in valued:
            item = report["fields"].get(field)
            if item is None or item["value"] is None:
                continue
            seen.append(
                {"hop": report["priority"], "channel": report["channel"], "value": item["value"]}
            )
        distinct = {json.dumps(item["value"], sort_keys=True) for item in seen}
        if len(distinct) > 1:
            conflicts.append({"field": field, "candidates": seen})

    fields = {}
    source = "none"
    notes = []
    evidence_hits = []

    if winner is not None:
        fields = dict(winner["fields"])
        source = "site-rule"
        evidence_hits = winner["site_hits"]
        notes.append(
            "命中 providerSiteRules[%s]（%s）于第 %d 跳 %s %s"
            % (
                ",".join(str(hit["index"]) for hit in winner["site_hits"]),
                " + ".join(
                    "%s | %s | %s" % (hit["modelMatch"], hit["apiTypeMatch"], hit["baseUrlMatch"])
                    for hit in winner["site_hits"]
                ),
                winner["priority"],
                winner["channel"],
                winner["base"],
            )
        )
        if conflicts:
            notes.append(
                "多跳冲突已按主 channel 优先："
                + "；".join(
                    "%s %s" % (item["field"], [cand["value"] for cand in item["candidates"]])
                    for item in conflicts
                )
            )
    else:
        other = resolve_builtin_other(
            rulesets,
            base_model,
            display,
            current_rule.get("providerId") if current_rule else None,
            [api_type_of(hop.get("protocol")) for hop in hops],
        )
        meaningful = [hit for hit in other["hits"] if hit["carries_values"] and not hit["wildcard"]]
        wildcards = [hit for hit in other["hits"] if hit["wildcard"]]
        if meaningful:
            # 逐字段剔除通配来源：通配只提供默认值，不是该模型的证据。
            fields = {}
            dropped = []
            for key, item in other["fields"].items():
                if item.get("wildcard"):
                    dropped.append(key)
                    continue
                fields[key] = item
            if dropped:
                notes.append(
                    "以下字段只由通配 .* 提供，已剔除（不作证据）：" + ",".join(sorted(dropped))
                )
            tiers = {hit["tier"] for hit in meaningful}
            exact = tiers <= {"builtinProviderModelRules", "templateModelRules"}
            source = "builtin-exact" if exact else "builtin-family"
            evidence_hits = meaningful
            notes.append(
                "providerSiteRules 无命中；取自 %s（%s），族级规则，置信度低一档"
                % (
                    ",".join("%s[%d]" % (hit["tier"], hit["index"]) for hit in meaningful),
                    ",".join(str(hit["modelMatch"]) for hit in meaningful),
                )
            )
            if wildcards:
                notes.append("部分字段来自内置通配 .*，无模型专属证据")
        elif wildcards:
            notes.append(
                "providerSiteRules 无命中，内置规则只有通配 .* 命中（ctx 1000000 / max 128000 / "
                "tool true / img false），不算证据"
            )

    # 兜底：现网现值
    current = current_values(current_rule)
    if source == "none":
        if any(current.get(key) is not None for key in CAPABILITY_FIELDS):
            fields = {}
            for key, value in current.items():
                fields[key] = {"value": value, "source": "current"}
            source = "current"
            notes.append("无上游证据，沿用现网 provider_config 现值")
        else:
            notes.append("无法取证：上游规则与内置规则都没有该模型的专属条目，现网也缺 properties")

    # 逐字段补：缺的字段用现值兜底（不让组合字段半截为 null）
    for key in CAPABILITY_FIELDS + REASONING_FIELDS:
        item = fields.get(key)
        if (item is None or item["value"] is None) and current.get(key) is not None:
            fields[key] = {"value": current[key], "source": "current"}

    hint = template_hint(builtin, base_model)
    if hint and source != "site-rule":
        notes.append(
            "建议参考：templateRules[%s] 收录该 id（%s @ %s），据此可命中 providerSiteRules[%s]"
            " → ctx %s / max %s / img %s"
            % (
                hint["template_id"],
                hint["api_type"],
                hint["base"],
                hint["site_rule_index"],
                hint["context_window"],
                hint["max_output_tokens"],
                hint["supports_image"],
            )
        )

    values = {
        key: (fields.get(key) or {}).get("value") for key in CAPABILITY_FIELDS + REASONING_FIELDS
    }
    if source == "none":
        # 约定：source=none 的能力字段一律 null，绝不编数字。
        for key in CAPABILITY_FIELDS:
            values[key] = None
        # 推理档位不是「编出来的数字」：现网里显式配过的档位照抄，标 current。
        for key in REASONING_FIELDS:
            if values.get(key) is None and current.get(key) is not None:
                values[key] = current[key]
                fields[key] = {"value": current[key], "source": "current"}

    first = hop_reports[0] if hop_reports else {}
    # api_type/channel 取「真正给出真值的那一跳」；没有命中时退回主 hop。
    anchor = winner if winner is not None else first
    return {
        "display": display,
        "base_model": base_model,
        "channel": anchor.get("channel"),
        "api_type": anchor.get("api_type"),
        "context_window": values["context_window"],
        "max_output_tokens": values["max_output_tokens"],
        "supports_tool_call": values["supports_tool_call"],
        "supports_image": values["supports_image"],
        "reasoning_values": values["reasoning_values"],
        "reasoning_map": values["reasoning_map"],
        "source": source,
        "confidence": SOURCE_CONFIDENCE[source],
        "notes": "；".join(notes),
        # ---- 以下是溯源用的附加信息（不影响上面 12 个正字段）----
        "field_sources": {
            key: (fields.get(key) or {}).get("source")
            for key in CAPABILITY_FIELDS + REASONING_FIELDS
        },
        "conflicts": conflicts,
        "hops": [
            {
                "priority": report["priority"],
                "main": report["main"],
                "channel": report["channel"],
                "base": report["base"],
                "protocol": report["protocol"],
                "api_type": report["api_type"],
                "site_hit_indexes": [hit["index"] for hit in report["site_hits"]],
                "evidence": evidence_hits if report is winner else [],
            }
            for report in hop_reports
        ],
        "current": current,
    }


CANONICAL_FIELDS = (
    "display",
    "base_model",
    "channel",
    "api_type",
    "context_window",
    "max_output_tokens",
    "supports_tool_call",
    "supports_image",
    "reasoning_values",
    "reasoning_map",
    "source",
    "confidence",
    "notes",
)

PROVENANCE_FIELDS = ("field_sources", "conflicts", "hops", "current")


def catalog_entries(records):
    """把内部记录收敛成 catalog 条目：13 个正字段 + 一段溯源。"""
    entries = []
    for record in records:
        entry = {key: record.get(key) for key in CANONICAL_FIELDS}
        entry["provenance"] = {key: record.get(key) for key in PROVENANCE_FIELDS}
        entries.append(entry)
    return entries


def build_records(alias_map, builtin, provider_config):
    """按 alias-map 顺序产出全部模型记录。"""
    models = alias_map.get("models") or {}
    rules = (
        ((provider_config.get("config") or {}).get("modelConfigRules") or {}).get(
            "providerModelRules"
        )
        or []
    )
    by_model = {}
    for rule in rules:
        by_model.setdefault(rule.get("modelId"), rule)
    records = []
    for display, entry in models.items():
        records.append(resolve_model(display, entry, builtin, by_model.get(display)))
    return records


# ---------------------------------------------------------------- --check


def apply_upstream(records, snapshot):
    """用上游接口真值覆盖解析结果（tools/caps_upstream.py 的快照）。

    解析链只能回答「规则里写了什么」，答不了「这个模型真实上限是多少」。上游模型
    接口给的是后者，所以字段只要有值就以它为准，并把 provenance 标成
    upstream:<渠道>:<上游模型 id>；快照里为 null 的字段保持解析值不动。
    """
    by_display = {}
    for item in snapshot.get("models") or []:
        if item.get("display"):
            by_display[str(item["display"])] = item
    replaced = []
    touched = set()
    for record in records:
        item = by_display.get(record["display"])
        if not item:
            continue
        provenance = record.setdefault("provenance", {})
        field_sources = provenance.setdefault("field_sources", {})
        for field in CAPABILITY_FIELDS:
            value = item.get(field)
            if value is None:
                continue
            source = "upstream:%s" % ((item.get("field_sources") or {}).get(field) or "-")
            if record.get(field) != value:
                replaced.append((record["display"], field, record.get(field), value))
                record[field] = value
                touched.add(record["display"])
            field_sources[field] = source
        note_parts = [
            "上游接口真值 %s" % source_value
            for source_value in sorted(
                {value for value in (item.get("field_sources") or {}).values() if value}
            )
        ]
        if note_parts:
            note = note_parts[0]
            record["notes"] = ("%s；%s" % (record.get("notes") or "", note)).strip("；")
        if record["display"] in touched:
            record["source"] = "upstream-api"
            record["confidence"] = "high"
    return records, replaced


def diff_records(records, provider_config):
    """逐字段对比解析值与现网值。

    返回 [{"display","provider","field","current","resolved","source"}]。
    现网缺字段（None）而解析值有 → 也算差异（当前正是「缺 properties」的形态）。
    """
    rules = (
        ((provider_config.get("config") or {}).get("modelConfigRules") or {}).get(
            "providerModelRules"
        )
        or []
    )
    by_model = {}
    for rule in rules:
        by_model.setdefault(rule.get("modelId"), []).append(rule)
    diffs = []
    for record in records:
        entries = by_model.get(record["display"]) or []
        if not entries:
            continue
        provider_id = entries[0].get("providerId")
        current = record.get("current") or {}
        for field in CAPABILITY_FIELDS + ("reasoning_values",):
            resolved = record.get(field)
            if resolved is None:
                continue
            have = current.get(field)
            if have == resolved:
                continue
            # 单字段来源优先：整条 record 的 source 会被「只有一个字段来自上游」
            # 抬成 upstream-api，直接拿它标注每个字段会误导排查。
            field_sources = (record.get("provenance") or {}).get("field_sources") or {}
            diffs.append(
                {
                    "display": record["display"],
                    "provider": provider_id,
                    "field": field,
                    "current": have,
                    "resolved": resolved,
                    "source": field_sources.get(field) or record["source"],
                }
            )
    return diffs


# ---------------------------------------------------------------- --apply


def real_config_paths():
    """现网真身与其目录 —— --apply 一律不许碰。"""
    home = os.path.expanduser("~")
    directory = os.path.abspath(os.path.join(home, ".zcode", "v2"))
    return os.path.join(directory, "provider_config.json"), directory


def guard_target(target):
    """目标必须在 ~/.zcode/v2 之外。"""
    absolute = os.path.normcase(os.path.abspath(target))
    real_file, real_dir = real_config_paths()
    real_file = os.path.normcase(real_file)
    real_dir = os.path.normcase(real_dir)
    if absolute == real_file or absolute == real_dir or absolute.startswith(real_dir + os.sep):
        raise SystemExit(
            "拒绝写入 %s：--apply 只允许写副本，~/.zcode 下的真身不动（进程也不重启）。" % target
        )
    return absolute


def apply_records(records, target, only_sources=None):
    """把解析值写进 target 副本，返回改动列表。

    only_sources 给定时只写 provenance.field_sources 以这些前缀开头的字段 ——
    用来实现「只落上游接口真值，不落规则推断值」：族级/站点级推断能说明「可能」，
    但写进配置就成了既成事实。
    """

    def trusted(record, field):
        if not only_sources:
            return True
        source = str(((record.get("provenance") or {}).get("field_sources") or {}).get(field) or "")
        return any(source.startswith(prefix) for prefix in only_sources)
    guard_target(target)
    if not os.path.exists(target):
        raise SystemExit("目标不存在：%s（--apply 只改已存在的副本，不新建）" % target)
    data = load_json(target)
    rules = (
        ((data.get("config") or {}).get("modelConfigRules") or {}).get("providerModelRules") or []
    )
    by_display = {}
    for rule in rules:
        by_display.setdefault(rule.get("modelId"), []).append(rule)
    changed = []
    for record in records:
        entries = by_display.get(record["display"]) or []
        if not entries:
            continue
        for rule in entries:
            config = rule.setdefault("config", {})
            # 一律「按需建容器」：真值为 None 的字段绝不写，也绝不留下空的
            # properties {} / inputFormat {}（否则副本会出现无意义的空壳差异）。
            props = config.get("properties")
            specs = config.get("optionSpecs")

            def need_props():
                nonlocal props
                if props is None:
                    props = config["properties"] = {}
                return props

            def need_specs():
                nonlocal specs
                if specs is None:
                    specs = config["optionSpecs"] = {}
                return specs

            context_window = record.get("context_window")
            if context_window is not None and trusted(record, "context_window"):
                if need_props().get("contextWindow") != context_window:
                    props["contextWindow"] = context_window
                    changed.append(
                        (record["display"], "properties.contextWindow", context_window)
                    )
            tool_call = record.get("supports_tool_call")
            if tool_call is not None and trusted(record, "supports_tool_call"):
                if need_props().get("supportsToolCall") != tool_call:
                    props["supportsToolCall"] = tool_call
                    changed.append(
                        (record["display"], "properties.supportsToolCall", tool_call)
                    )
            image = record.get("supports_image")
            if image is not None and trusted(record, "supports_image"):
                input_format = need_props().get("inputFormat")
                if input_format is None:
                    input_format = props["inputFormat"] = {}
                if input_format.get("supportsImage") != image:
                    input_format["supportsImage"] = image
                    changed.append(
                        (record["display"], "properties.inputFormat.supportsImage", image)
                    )
            max_tokens = record.get("max_output_tokens")
            if max_tokens is not None and trusted(record, "max_output_tokens"):
                limit = need_specs().get("maxOutputTokens")
                if limit is None:
                    limit = specs["maxOutputTokens"] = {}
                if limit.get("max") != max_tokens:
                    limit["max"] = max_tokens
                    changed.append(
                        (record["display"], "optionSpecs.maxOutputTokens.max", max_tokens)
                    )
            values = record.get("reasoning_values")
            if values and trusted(record, "reasoning_values"):
                reasoning = need_specs().get("reasoningLevel")
                if reasoning is None:
                    reasoning = specs["reasoningLevel"] = {}
                if reasoning.get("values") != values:
                    reasoning["values"] = values
                    changed.append(
                        (record["display"], "optionSpecs.reasoningLevel.values", values)
                    )
                # map 只在现网缺失时补写：内置规则里的 map 模板方言与现网不同
                # （{"k": v} vs {k: v}），直接覆盖会改变请求参数的拼装方式。
                mapping = record.get("reasoning_map")
                if mapping and not reasoning.get("map"):
                    reasoning["map"] = mapping
                    changed.append(
                        (record["display"], "optionSpecs.reasoningLevel.map(补写)", mapping)
                    )
    _write_text(target, _dump_json(data))
    return changed


# ---------------------------------------------------------------- 表格


def _fmt(value):
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return str(len(value))
    return str(value)


def render_table(records):
    """默认输出：主表 + 「无法取证」段 + 「仅有现值」段。"""
    headers = (
        "display",
        "base_model",
        "apiType",
        "ctx",
        "max",
        "img",
        "tool",
        "reasoningCount",
        "source",
        "confidence",
    )
    rows = []
    for record in records:
        rows.append(
            (
                record["display"],
                record["base_model"] or "-",
                record["api_type"] or "-",
                _fmt(record["context_window"]),
                _fmt(record["max_output_tokens"]),
                _fmt(record["supports_image"]),
                _fmt(record["supports_tool_call"]),
                _fmt(record["reasoning_values"]),
                record["source"],
                record["confidence"],
            )
        )
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def line(cells):
        return "  ".join(cell.ljust(widths[index]) for index, cell in enumerate(cells)).rstrip()

    out = [line(headers), line(tuple("-" * width for width in widths))]
    for row in rows:
        out.append(line(row))

    missing = [record for record in records if record["source"] == "none"]
    out.append("")
    out.append("== 无法取证（source=none，值一律 null，不编数字）==")
    if not missing:
        out.append("（无）")
    else:
        for record in missing:
            out.append("- %s（%s / %s）" % (record["display"], record["base_model"], record["channel"]))
            out.append("    原因：%s" % record["notes"])
            out.append("    建议：保留现值 / 打问号 / 人工补 —— 现值见 --json 的 current 字段")

    weak = [record for record in records if record["source"] == "current"]
    if weak:
        out.append("")
        out.append("== 仅有现网现值（source=current，无上游证据）==")
        for record in weak:
            out.append("- %s：%s" % (record["display"], record["notes"]))
    return chr(10).join(out)


def _fmt_full(value):
    """差异表用：列表原样展开，不折叠成数量。"""
    if value is None:
        return "-"
    if isinstance(value, list):
        return "[" + ",".join(str(item) for item in value) + "]"
    return _fmt(value)


def render_diffs(diffs):
    """--check 的差异表（逐字段，带来源）。"""
    if not diffs:
        return "现网 provider_config 与解析真值一致：0 条差异。"
    header = ("display", "provider", "field", "current", "resolved", "source")
    rows = [
        (
            item["display"],
            item["provider"] or "-",
            item["field"],
            _fmt_full(item["current"]),
            _fmt_full(item["resolved"]),
            item["source"],
        )
        for item in diffs
    ]
    widths = [len(cell) for cell in header]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(str(cell)))

    def line(cells):
        return "  ".join(str(cell).ljust(widths[index]) for index, cell in enumerate(cells)).rstrip()

    lines = ["差异 %d 条（current = 现网 provider_config，resolved = 解析真值）：" % len(diffs)]
    lines.append(line(header))
    lines.append(line(tuple("-" * width for width in widths)))
    for row in rows:
        lines.append(line(row))
    return chr(10).join(lines)


# ---------------------------------------------------------------- CLI


def build_parser():
    parser = argparse.ArgumentParser(
        prog="model_caps.py",
        description="解析并核对兼容投影模型能力字段真值（ctx / max / img / tool / reasoning）",
    )
    parser.add_argument("--alias-map", default=DEFAULT_ALIAS_MAP, help="model-alias-map.json 路径")
    parser.add_argument("--builtin", default=DEFAULT_BUILTIN, help="zcode-builtin.json 路径")
    parser.add_argument(
        "--current",
        default=DEFAULT_CURRENT,
        help="现网 provider_config.json 路径（只读 modelConfigRules 段）",
    )
    parser.add_argument("--check", action="store_true", help="对比现网，有差异 exit 1")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    parser.add_argument(
        "--catalog", metavar="PATH", help="把机器可读结果写到指定文件（catalog/model_caps.json）"
    )
    parser.add_argument(
        "--upstream",
        metavar="PATH",
        help="上游真值快照（catalog/upstream_caps.json）；命中字段压过规则解析值",
    )
    parser.add_argument(
        "--apply-source",
        metavar="PREFIX",
        help="只写入 provenance 以该前缀开头的字段（如 upstream:），规则推断值不落盘",
    )
    parser.add_argument("--apply", action="store_true", help="把真值写进 --target 指定的副本")
    parser.add_argument("--target", metavar="PATH", help="--apply 的目标副本（~/.zcode 下会被拒绝）")
    return parser


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass
    parser = build_parser()
    args = parser.parse_args(argv)
    alias_map = load_json(_expand(args.alias_map))
    builtin = load_json(_expand(args.builtin))
    current_path = _expand(args.current)
    provider_config = load_json(current_path) if os.path.exists(current_path) else {}

    records = build_records(alias_map, builtin, provider_config)
    if args.upstream:
        records, replaced = apply_upstream(records, load_json(_expand(args.upstream)))
        print("上游真值覆盖 %d 处" % len(replaced), file=sys.stderr)
        for display, field, before, after in replaced:
            print(
                "  %-22s %-20s %s → %s" % (display, field, _fmt_full(before), _fmt_full(after)),
                file=sys.stderr,
            )

    if args.apply:
        if not args.target:
            print("--apply 需要 --target <副本路径>", file=sys.stderr)
            return 2
        only = [args.apply_source] if args.apply_source else None
        changed = apply_records(records, args.target, only_sources=only)
        print("已写入 %s：%d 处改动" % (args.target, len(changed)))
        for display, field, value in changed:
            print("  %-22s %-38s %s" % (display, field, _fmt_full(value)))
        if not changed:
            print("（无改动）")
        return 0

    entries = catalog_entries(records)
    document = {
        "schema": "model_caps/v1",
        "generated_by": "tools/model_caps.py",
        "note": "单一真源：display 对齐现网 providerModelRules 的 modelId；source/confidence 标明证据强度，source=none 时能力字段一律 null。",
        "models": entries,
    }

    if args.catalog:
        path = _expand(args.catalog)
        parent = os.path.dirname(path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        _write_text(path, _dump_json(document))
        print("已写出 %s（%d 条）" % (path, len(entries)), file=sys.stderr)

    if args.check:
        diffs = diff_records(records, provider_config)
        print(render_diffs(diffs))
        return 1 if diffs else 0

    if args.json:
        print(_dump_json(document))
        return 0

    print(render_table(records))
    return 0


if __name__ == "__main__":
    sys.exit(main())
