#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_model_caps.py —— tools/model_caps.py 的单元测试。

跑法（仓根）：
    python -B -m unittest discover -s tests -q

覆盖点：
1. 正则匹配语义（整串全匹配、忽略大小写、带转义点 glm-5\\.3 / deepseek-v4\\.1-flash）；
2. 多跳矛盾时取主 channel，其余跳记 conflicts；
3. 全无命中返回 None（source=none，能力字段一律 null）；
4. --check 在夹具上有差异 exit 1、无差异 exit 0；
5. --apply 只写副本，~/.zcode 真身被拒；
6. catalog 条目字段齐全。
"""

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import model_caps as mc  # noqa: E402


def site_rule(model_match, api_type_match, base_url_match, ctx=None, max_tokens=None,
              image=None, tool=None, reasoning=None, map_template=None):
    """拼一条 providerSiteRules 条目。"""
    props = {}
    if ctx is not None:
        props["contextWindow"] = ctx
    if tool is not None:
        props["supportsToolCall"] = tool
    if image is not None:
        props["inputFormat"] = {"supportsImage": image}
    specs = {}
    if max_tokens is not None:
        specs["maxOutputTokens"] = {"max": max_tokens}
    if reasoning is not None:
        specs["reasoningLevel"] = {"values": reasoning}
        if map_template is not None:
            specs["reasoningLevel"]["map"] = map_template
    config = {}
    if props:
        config["properties"] = props
    if specs:
        config["optionSpecs"] = specs
    return {
        "modelMatch": model_match,
        "apiTypeMatch": api_type_match,
        "baseUrlMatch": base_url_match,
        "config": config,
    }


def builtin_of(site_rules, model_rules=None, template_rules=None):
    return {
        "config": {
            "providerConfigRules": {"templateRules": template_rules or []},
            "modelConfigRules": {
                "providerSiteRules": site_rules,
                "modelRules": model_rules or [],
                "modelApiRules": [],
                "builtinProviderModelRules": [],
                "templateModelRules": [],
            },
        }
    }


def alias_of(models):
    return {"version": 1, "models": models}


def entry_of(base_model, channel, base, protocol, chain=()):
    return {
        "base_model": base_model,
        "channel": channel,
        "base": base,
        "protocol": protocol,
        "chain": list(chain),
    }


OPENCODE = "https://opencode.ai/zen/go/v1"
OPENCODE_RULE = "https://opencode\\.ai/zen/go/v1/?"


class MatchRuleTest(unittest.TestCase):
    """复刻 ZCode 的 matchesRule：正则 + 整串全匹配。"""

    def test_escaped_dot_matches_only_literal_dot(self):
        self.assertTrue(mc.match_rule("glm-5\\.3", "glm-5.3"))
        # 转义点必须只匹配字面点
        self.assertFalse(mc.match_rule("glm-5\\.3", "glm-5x3"))
        # 整串全匹配：前缀相同但更长不算命中
        self.assertFalse(mc.match_rule("glm-5\\.3", "glm-5.3-flash"))
        self.assertTrue(mc.match_rule("glm-5\\.3-flash", "glm-5.3-flash"))

    def test_deepseek_escaped_dot(self):
        pattern = "deepseek-v4\\.1-flash"
        self.assertTrue(mc.match_rule(pattern, "deepseek-v4.1-flash"))
        self.assertFalse(mc.match_rule(pattern, "deepseek-v4x1-flash"))
        self.assertFalse(mc.match_rule(pattern, "deepseek-v4.1-flash-vision"))

    def test_ignore_case_only_for_model_id(self):
        self.assertTrue(mc.match_rule("GLM-5\\.3-Flash", "glm-5.3-flash", ignore_case=True))
        self.assertFalse(mc.match_rule("openai-chat-completions", "OpenAI-Chat-Completions"))
        self.assertFalse(mc.match_rule(".*", None))
        self.assertFalse(mc.match_rule("(unclosed", "anything"))

    def test_wildcard_detection(self):
        self.assertTrue(mc.is_wildcard(".*"))
        self.assertTrue(mc.is_wildcard("(?:.*)"))
        self.assertFalse(mc.is_wildcard(".*glm-5.*"))

    def test_normalize_base(self):
        self.assertEqual(mc.normalize_base(OPENCODE + "/"), OPENCODE)
        self.assertEqual(mc.normalize_base("https://API.Opencode.AI/zen/go/v1/"),
                         "https://api.opencode.ai/zen/go/v1")
        self.assertIsNone(mc.normalize_base("not a url"))

    def test_protocol_mapping(self):
        self.assertEqual(mc.api_type_of("chat"), "openai-chat-completions")
        self.assertEqual(mc.api_type_of("messages"), "anthropic-messages")
        self.assertEqual(mc.api_type_of("responses"), "openai-responses")


class ResolveSiteTest(unittest.TestCase):
    """site 规则要求 modelMatch + apiTypeMatch + baseUrlMatch 三件同时命中。"""

    def test_base_mismatch_does_not_hit(self):
        rules = [site_rule("glm-5\\.3-flash", "openai-chat-completions", OPENCODE_RULE,
                           ctx=1000000, max_tokens=131072, image=True)]
        # 现网过去就是拿 127.0.0.1 的 base 去匹配，永远打不中
        miss = mc.resolve_site(rules, "glm-5.3-flash", "openai-chat-completions",
                               "http://127.0.0.1:8790/v1")
        self.assertEqual(miss["hits"], [])
        self.assertEqual(miss["fields"], {})
        hit = mc.resolve_site(rules, "glm-5.3-flash", "openai-chat-completions", OPENCODE)
        self.assertEqual([item["index"] for item in hit["hits"]], [0])
        self.assertEqual(hit["fields"]["context_window"]["value"], 1000000)

    def test_api_type_mismatch_does_not_hit(self):
        rules = [site_rule("qwen3\\.8-flash", "anthropic-messages", OPENCODE_RULE, ctx=1000000)]
        miss = mc.resolve_site(rules, "Qwen3.8-Flash", "openai-chat-completions", OPENCODE)
        self.assertEqual(miss["hits"], [])
        hit = mc.resolve_site(rules, "Qwen3.8-Flash", "anthropic-messages", OPENCODE)
        self.assertEqual(len(hit["hits"]), 1)

    def test_later_rule_overlays_earlier(self):
        rules = [
            site_rule("glm-5\\.3-flash", ".*", ".*", ctx=200000, max_tokens=64000),
            site_rule("glm-5\\.3-flash", "openai-chat-completions", OPENCODE_RULE, ctx=1000000),
        ]
        resolved = mc.resolve_site(rules, "glm-5.3-flash", "openai-chat-completions", OPENCODE)
        self.assertEqual(resolved["fields"]["context_window"]["value"], 1000000)
        self.assertEqual(resolved["fields"]["max_output_tokens"]["value"], 64000)


class MultiHopTest(unittest.TestCase):
    """多跳命中取主 channel，其余跳只记 conflicts。"""

    def setUp(self):
        self.builtin = builtin_of([
            site_rule("deepseek-v4\\.1-flash", "openai-chat-completions",
                      "https://opencode\\.ai/zen/go/v1/?",
                      ctx=1000000, max_tokens=384000, image=True),
        ])

    def test_main_channel_wins(self):
        # 主跳是本地 WB（打不中），第二跳是 OC（打中）
        entry = entry_of("deepseek-v4.1-flash", "WB", "http://127.0.0.1:7863/v1", "chat", chain=[
            {"channel": "OC", "base": OPENCODE, "protocol": "chat",
             "base_model": "deepseek-v4.1-flash"},
        ])
        record = mc.resolve_model("DeepSeek-4.1-Flash", entry, self.builtin, None)
        self.assertEqual(record["source"], "site-rule")
        self.assertEqual(record["channel"], "OC")
        self.assertEqual(record["context_window"], 1000000)
        self.assertEqual(record["max_output_tokens"], 384000)

    def test_conflict_between_hops_is_recorded(self):
        builtin = builtin_of([
            site_rule("deepseek-v4\\.1-flash", "openai-chat-completions", ".*",
                      ctx=1000000, max_tokens=384000),
            site_rule("deepseek-v4\\.1-flash", "anthropic-messages",
                      "https://maas\\.qianwenaiapi\\.com/apps/anthropic/v1",
                      ctx=256000, max_tokens=64000),
        ])
        entry = entry_of("deepseek-v4.1-flash", "OC", OPENCODE, "chat", chain=[
            {"channel": "QW", "base": "https://maas.qianwenaiapi.com/apps/anthropic/v1",
             "protocol": "messages", "base_model": "deepseek-v4.1-flash"},
        ])
        record = mc.resolve_model("DeepSeek-4.1-Flash", entry, builtin, None)
        # 主 channel 优先
        self.assertEqual(record["context_window"], 1000000)
        self.assertEqual(record["max_output_tokens"], 384000)
        fields = {item["field"] for item in record["conflicts"]}
        self.assertIn("context_window", fields)
        self.assertIn("max_output_tokens", fields)
        self.assertIn("多跳冲突", record["notes"])


class NoEvidenceTest(unittest.TestCase):
    """全无命中：source=none，能力字段一律 null，绝不编数字。"""

    def test_no_hit_returns_none(self):
        builtin = builtin_of(
            [site_rule("glm-5\\.3-flash", "openai-chat-completions", OPENCODE_RULE,
                       ctx=1000000, max_tokens=131072)],
            model_rules=[{"modelMatch": ".*", "config": {"properties": {"contextWindow": 1000000,
                                                                       "supportsToolCall": True,
                                                                       "inputFormat": {"supportsImage": False}},
                                                          "optionSpecs": {"maxOutputTokens": {"max": 128000}}}}],
        )
        entry = entry_of("mystery-model-x", "XX", "https://example.invalid/v1", "chat")
        record = mc.resolve_model("Mystery-X", entry, builtin, None)
        self.assertEqual(record["source"], "none")
        self.assertIsNone(record["context_window"])
        self.assertIsNone(record["max_output_tokens"])
        self.assertIsNone(record["supports_tool_call"])
        self.assertIsNone(record["supports_image"])
        self.assertEqual(record["confidence"], "none")
        self.assertIn("无法取证", record["notes"])

    def test_wildcard_only_is_not_evidence(self):
        # 只有通配 .* 命中 → 不能拿 1000000/128000 当证据
        builtin = builtin_of([], model_rules=[{
            "modelMatch": ".*",
            "config": {"properties": {"contextWindow": 1000000},
                       "optionSpecs": {"maxOutputTokens": {"max": 128000}}},
        }])
        entry = entry_of("mystery-model-y", "XX", "https://example.invalid/v1", "chat")
        record = mc.resolve_model("Mystery-Y", entry, builtin, None)
        self.assertEqual(record["source"], "none")
        self.assertIsNone(record["context_window"])

    def test_family_rule_gives_medium_confidence(self):
        builtin = builtin_of([], model_rules=[{
            "modelMatch": ".*mimo-v2\\.6-(?:pro|flash).*",
            "config": {"properties": {"contextWindow": 1000000,
                                      "inputFormat": {"supportsImage": True}},
                       "optionSpecs": {"maxOutputTokens": {"max": 131072}}},
        }])
        entry = entry_of("mimo-v2.6-flash", "OC", OPENCODE, "chat")
        record = mc.resolve_model("MiMo-2.6-Flash", entry, builtin, None)
        self.assertEqual(record["source"], "builtin-family")
        self.assertEqual(record["confidence"], "medium")
        self.assertEqual(record["max_output_tokens"], 131072)


class CliCheckTest(unittest.TestCase):
    """--check 在夹具上：有差异 exit 1，无差异 exit 0。"""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="model_caps_test_")
        self.builtin_path = os.path.join(self.dir, "builtin.json")
        self.alias_path = os.path.join(self.dir, "alias.json")
        self.current_path = os.path.join(self.dir, "current.json")
        builtin = builtin_of([
            site_rule("glm-5\\.3-flash", "openai-chat-completions", OPENCODE_RULE,
                      ctx=1000000, max_tokens=131072, image=True, tool=True,
                      reasoning=["low", "high", "max"]),
        ])
        with open(self.builtin_path, "w", encoding="utf-8") as handle:
            json.dump(builtin, handle, ensure_ascii=False)
        alias = alias_of({
            "GLM-5.3-Flash": entry_of("glm-5.3-flash", "OC", OPENCODE, "chat"),
        })
        with open(self.alias_path, "w", encoding="utf-8") as handle:
            json.dump(alias, handle, ensure_ascii=False)
        self.resolved = {
            "context_window": 1000000,
            "max_output_tokens": 131072,
            "supports_tool_call": True,
            "supports_image": True,
            "reasoning_values": ["low", "high", "max"],
        }

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def write_current(self, config, max_tokens):
        payload = {
            "config": {
                "modelConfigRules": {
                    "providerModelRules": [{
                        "modelId": "GLM-5.3-Flash",
                        "providerId": "opencode-go-chat",
                        "config": config,
                    }],
                },
            },
        }
        with open(self.current_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)

    def run_cli(self, *extra):
        argv = [
            "--alias-map", self.alias_path,
            "--builtin", self.builtin_path,
            "--current", self.current_path,
        ] + list(extra)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = mc.main(argv)
        return code, buffer.getvalue()

    def test_check_exits_1_when_current_differs(self):
        # 现网缺 properties，且 max 是通配的 128000 → 必须有差异
        self.write_current({"enabled": True,
                            "optionSpecs": {"maxOutputTokens": {"max": 128000}}}, 128000)
        code, output = self.run_cli("--check")
        self.assertEqual(code, 1)
        self.assertIn("max_output_tokens", output)
        self.assertIn("supports_image", output)

    def test_check_exits_0_when_matching(self):
        self.write_current({
            "enabled": True,
            "properties": {
                "contextWindow": 1000000,
                "supportsToolCall": True,
                "inputFormat": {"supportsImage": True},
            },
            "optionSpecs": {
                "maxOutputTokens": {"max": 131072},
                "reasoningLevel": {"values": ["low", "high", "max"]},
            },
        }, 131072)
        code, output = self.run_cli("--check")
        self.assertEqual(code, 0)
        self.assertIn("0 条差异", output)

    def test_catalog_then_json_roundtrip(self):
        self.write_current({"enabled": True}, None)
        catalog_path = os.path.join(self.dir, "catalog.json")
        code, _ = self.run_cli("--catalog", catalog_path)
        self.assertEqual(code, 0)
        with open(catalog_path, encoding="utf-8") as handle:
            document = json.load(handle)
        self.assertEqual(document["schema"], "model_caps/v1")
        entry = document["models"][0]
        for key in mc.CANONICAL_FIELDS:
            self.assertIn(key, entry)
        self.assertIn("provenance", entry)
        self.assertEqual(entry["context_window"], 1000000)
        self.assertEqual(entry["source"], "site-rule")
        self.assertEqual(entry["confidence"], "high")

    def test_apply_writes_copy_only(self):
        self.write_current({"enabled": True}, None)
        code, _ = self.run_cli("--apply", "--target", self.current_path)
        self.assertEqual(code, 0)
        with open(self.current_path, encoding="utf-8") as handle:
            data = json.load(handle)
        config = data["config"]["modelConfigRules"]["providerModelRules"][0]["config"]
        self.assertEqual(config["properties"]["contextWindow"], 1000000)
        self.assertEqual(config["properties"]["inputFormat"]["supportsImage"], True)
        self.assertEqual(config["optionSpecs"]["maxOutputTokens"]["max"], 131072)
        # 再跑一次应当零改动（幂等）
        code, output = self.run_cli("--apply", "--target", self.current_path)
        self.assertEqual(code, 0)
        self.assertIn("0 处改动", output)

    def test_apply_refuses_real_config_path(self):
        self.write_current({"enabled": True}, None)
        real = os.path.join(os.path.expanduser("~"), ".zcode", "v2", "provider_config.json")
        with self.assertRaises(SystemExit):
            mc.guard_target(real)


class DefaultsTest(unittest.TestCase):
    def test_capability_field_order(self):
        self.assertEqual(mc.CAPABILITY_FIELDS,
                         ("context_window", "max_output_tokens",
                          "supports_tool_call", "supports_image"))

    def test_confidence_table(self):
        self.assertEqual(mc.SOURCE_CONFIDENCE["site-rule"], "high")
        self.assertEqual(mc.SOURCE_CONFIDENCE["builtin-family"], "medium")
        self.assertEqual(mc.SOURCE_CONFIDENCE["builtin-exact"], "low")
        self.assertEqual(mc.SOURCE_CONFIDENCE["current"], "low")
        self.assertEqual(mc.SOURCE_CONFIDENCE["none"], "none")


if __name__ == "__main__":
    unittest.main()
