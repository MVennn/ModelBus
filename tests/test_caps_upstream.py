#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_caps_upstream.py —— 上游真值采集与覆盖的单元测试。

跑法（仓根）：
    python -B -m unittest discover -s tests -q

覆盖点：
1. 别名对号：WB 的 cn: 前缀两种写法都能命中；
2. 主用跳优先、跨跳不一致进 conflicts，但取值必须是主用跳的；
3. 主用跳没有的字段可由后续跳补位，并注明来源；
4. 主用渠道不提供元数据时，cross 记下同名模型，但绝不写进 fields；
5. --check 与现网比对只报上游有的字段，快照为 null 的字段不算差异；
6. model_caps.apply_upstream 只覆盖快照有值的字段，provenance 标 upstream:<渠道>:<id>；
7. apply_records(only_sources=[...]) 只落上游真值，规则推断值不写。
"""

import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import caps_upstream as cu  # noqa: E402
import model_caps as mc  # noqa: E402


def alias(display, hops):
    return {"models": {display: {"base_model": hops[0][1], "chain": [
        {"channel": channel, "base": base, "base_model": base} for channel, base in hops
    ]}}}


def sources(wb=None, oc=None, qn=None):
    def table(items):
        return {key: dict(value) for key, value in (items or {}).items()}

    return {
        "wb": {"url": "wb", "count": len(table(wb)), "models": table(wb)},
        "oc": {"url": "oc", "count": len(table(oc)), "models": table(oc)},
        "qn": {"url": "qn", "count": len(table(qn)), "models": table(qn)},
    }


class HopCandidatesTest(unittest.TestCase):
    def test_cn_prefix_added(self):
        self.assertEqual(
            cu.hop_candidates({"base": "cn:hy3", "base_model": "hy3"}),
            ["cn:hy3", "hy3"],
        )

    def test_plain_id_gets_cn_variant(self):
        self.assertIn("cn:deepseek-v4.1-flash", cu.hop_candidates({"base": "deepseek-v4.1-flash"}))


class CollectTest(unittest.TestCase):
    def test_primary_hop_wins_and_conflict_recorded(self):
        table = sources(
            wb={"cn:m": {"context_window": 1000000, "max_output_tokens": 128000,
                         "supports_tool_call": True, "supports_image": True}},
            oc={"m": {"context_window": 1048576, "max_output_tokens": 131072,
                      "supports_tool_call": True, "supports_image": True}},
        )
        models = cu.collect(alias("M", [("WB", "m"), ("OC", "m")]), table)
        entry = models[0]
        self.assertEqual(entry["context_window"], 1000000)
        self.assertEqual(entry["field_sources"]["context_window"], "WB:cn:m")
        fields = {item["field"] for item in entry["conflicts"]}
        self.assertEqual(fields, {"context_window", "max_output_tokens"})

    def test_following_hop_fills_missing_field(self):
        table = sources(
            wb={"cn:m": {"context_window": 1000000, "max_output_tokens": None,
                         "supports_tool_call": True, "supports_image": True}},
            oc={"m": {"context_window": 1000000, "max_output_tokens": 131072,
                      "supports_tool_call": True, "supports_image": True}},
        )
        entry = cu.collect(alias("M", [("WB", "m"), ("OC", "m")]), table)[0]
        self.assertEqual(entry["max_output_tokens"], 131072)
        self.assertEqual(entry["field_sources"]["max_output_tokens"], "OC:m")

    def test_unknown_channel_only_cross_reference(self):
        table = sources(oc={"qwen3.8-max": {"context_window": 1000000, "max_output_tokens": 131072,
                                            "supports_tool_call": True, "supports_image": True}})
        entry = cu.collect(alias("Qwen-3.8-Max", [("QD", "Qwen3.8-Max")]), table)[0]
        self.assertIsNone(entry["context_window"])
        self.assertEqual(entry["field_sources"]["context_window"], None)
        self.assertTrue(entry["cross"])
        self.assertEqual(entry["cross"][0]["source"], "OC:qwen3.8-max")


class CheckTest(unittest.TestCase):
    def test_only_upstream_fields_count(self):
        snapshot = {"models": [
            {"display": "A", "context_window": 262144, "max_output_tokens": None,
             "supports_tool_call": None, "supports_image": None,
             "field_sources": {"context_window": "OC:a"}},
        ]}
        current = {"A": {"context_window": 1000000, "max_output_tokens": 128000,
                         "supports_tool_call": True, "supports_image": False}}
        diffs = cu.check(snapshot, current)
        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0][1], "context_window")
        self.assertEqual(diffs[0][3], 262144)


class ApplyUpstreamTest(unittest.TestCase):
    def record(self):
        return {
            "display": "X",
            "context_window": 1000000,
            "max_output_tokens": 128000,
            "supports_tool_call": None,
            "supports_image": None,
            "reasoning_values": ["low", "high"],
            "source": "builtin-wildcard",
            "confidence": "low",
            "notes": "",
            "provenance": {"field_sources": {}},
        }

    def test_overlay_writes_value_and_provenance(self):
        records = [self.record()]
        snapshot = {"models": [{
            "display": "X", "context_window": 262144, "max_output_tokens": None,
            "supports_tool_call": True, "supports_image": False,
            "field_sources": {"context_window": "OC:x", "supports_tool_call": "OC:x",
                              "supports_image": "OC:x"},
        }]}
        out, replaced = mc.apply_upstream(records, snapshot)
        self.assertEqual(out[0]["context_window"], 262144)
        self.assertEqual(out[0]["max_output_tokens"], 128000)  # 快照 null 不动
        self.assertEqual(out[0]["provenance"]["field_sources"]["context_window"], "upstream:OC:x")
        self.assertEqual(out[0]["source"], "upstream-api")
        self.assertTrue(replaced)

    def test_only_sources_filters_rule_inference(self):
        records = [self.record()]
        records[0]["provenance"]["field_sources"] = {
            "context_window": "upstream:OC:x",
            "max_output_tokens": "builtin-family",
            "supports_tool_call": "builtin-family",
            "supports_image": "builtin-family",
        }
        records[0]["context_window"] = 262144
        records[0]["max_output_tokens"] = 131072
        work = tempfile.mkdtemp(prefix="caps_upstream_apply_")
        target = os.path.join(work, "candidate.json")
        with open(target, "w", encoding="utf-8") as handle:
            handle.write('{"config": {"modelConfigRules": {"providerModelRules": '
                         '[{"modelId": "X", "config": {}}]}}}')
        try:
            changed = mc.apply_records(records, target, only_sources=["upstream:"])
            fields = {item[1] for item in changed}
            self.assertIn("properties.contextWindow", fields)
            self.assertNotIn("optionSpecs.maxOutputTokens.max", fields)
            self.assertNotIn("properties.supportsToolCall", fields)
        finally:
            shutil.rmtree(work, ignore_errors=True)


class EvidenceOverlayTest(unittest.TestCase):
    """接口取不到时的取证覆盖层（catalog/upstream_caps_evidence.json）。"""

    def model(self, **over):
        item = {
            "display": "Gemini-AIS",
            "channel": "GM",
            "base": "ais-gemini-3.8-flash",
            "context_window": None,
            "max_output_tokens": None,
            "supports_tool_call": None,
            "supports_image": None,
            "field_sources": {field: None for field in cu.CAPABILITY_FIELDS},
            "conflicts": [],
            "cross": [],
            "notes": "",
        }
        item.update(over)
        return item

    def overlay(self, **over):
        item = {
            "display": "Gemini-AIS",
            "channel": "GM",
            "context_window": 1000000,
            "max_output_tokens": 65536,
            "supports_tool_call": True,
            "supports_image": True,
            "field_sources": {
                "context_window": "evidence:GM-selfreport",
                "max_output_tokens": "evidence:GM-selfreport",
                "supports_tool_call": "evidence:vendor-doc",
                "supports_image": "evidence:vendor-doc",
            },
            "notes": "取证说明",
        }
        item.update(over)
        return item

    def test_fills_only_missing_fields(self):
        model = self.model(context_window=None, max_output_tokens=131072,
                           field_sources={"context_window": None,
                                          "max_output_tokens": "WB:cn:gemini-ais"})
        merged = cu.merge_evidence([model], {"models": [self.overlay()]})[0]
        self.assertEqual(merged["context_window"], 1000000)
        self.assertEqual(merged["field_sources"]["context_window"], "evidence:GM-selfreport")
        # 接口已经给出的值不被文档覆盖，差异只记 conflicts
        self.assertEqual(merged["max_output_tokens"], 131072)
        self.assertEqual(merged["field_sources"]["max_output_tokens"], "WB:cn:gemini-ais")
        self.assertEqual(merged["conflicts"][0]["field"], "max_output_tokens")

    def test_null_evidence_never_fills(self):
        merged = cu.merge_evidence([self.model()], {"models": [self.overlay(supports_image=None)]})[0]
        self.assertIsNone(merged["supports_image"])
        self.assertIsNone(merged["field_sources"]["supports_image"])

    def test_notes_and_conflicts_are_merged(self):
        model = self.model(notes="HJ 无 API 元数据")
        merged = cu.merge_evidence(
            [model],
            {"models": [self.overlay(conflicts=[{"field": "context_window", "values": {}, "picked": "x"}])]},
        )[0]
        self.assertIn("HJ 无 API 元数据", merged["notes"])
        self.assertIn("取证说明", merged["notes"])
        self.assertEqual(merged["conflicts"][0]["picked"], "x")

    def test_missing_display_is_ignored(self):
        models = [self.model(display="Other")]
        merged = cu.merge_evidence(models, {"models": [self.overlay()]})
        self.assertIsNone(merged[0]["context_window"])


if __name__ == "__main__":

    unittest.main()
