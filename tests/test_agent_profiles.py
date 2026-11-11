#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""agent_profiles.py 行为回归：真源校验 / 投影过滤 / 分桶稳定 / CLI 退出码。"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import agent_profiles as ap  # noqa: E402


def doc(models):
    return {"schema": ap.SCHEMA, "models": models}


def m(display, conf="high", source="upstream-api", tool=True, image=True, rv=None, **kw):
    base = {
        "display": display, "channel": "OC", "context_window": 1000000,
        "max_output_tokens": 128000, "supports_tool_call": tool,
        "supports_image": image, "reasoning_values": rv if rv is not None else ["low", "high"],
        "source": source, "confidence": conf,
    }
    base.update(kw)
    return base


class TestValidate(unittest.TestCase):
    def test_real_catalog_passes(self):
        self.assertEqual(ap.validate(ap.load_catalog()), [])

    def test_schema_mismatch_reported(self):
        d = doc([m("A")]); d["schema"] = "wrong/v9"
        self.assertTrue(any("schema" in p for p in ap.validate(d)))

    def test_duplicate_display_reported(self):
        self.assertTrue(any("重复" in p for p in ap.validate(doc([m("A"), m("A")]))))

    def test_none_source_must_not_invent_values(self):
        self.assertTrue(any("编了值" in p for p in ap.validate(doc([m("A", source="none"), m("B")]))))

    def test_bad_confidence_reported(self):
        self.assertTrue(any("confidence 非法" in p for p in ap.validate(doc([m("A", conf="guess"), m("B")]))))


class TestProject(unittest.TestCase):
    def test_session_is_full_catalog(self):
        d = doc([m("A"), m("B", conf="low")])
        self.assertEqual([x["id"] for x in ap.project("session", d)["models"]], ["A", "B"])

    def test_subagent_requires_tool_call_and_medium(self):
        d = doc([m("A"), m("B", tool=False), m("C", conf="low")])
        self.assertEqual([x["id"] for x in ap.project("subagent", d)["models"]], ["A"])

    def test_service_plugin_only_high_with_tool(self):
        d = doc([m("A", conf="high"), m("B", conf="medium"), m("C", conf="high", tool=False)])
        self.assertEqual([x["id"] for x in ap.project("service-plugin", d)["models"]], ["A"])

    def test_unknown_profile_raises(self):
        with self.assertRaises(ap.AgentProfileError):
            ap.project("nope", doc([m("A")]))

    def test_projection_declares_single_gateway(self):
        out = ap.project("session", doc([m("A")]))
        self.assertEqual(out["gateway"], "http://127.0.0.1:7871/v1")
        self.assertEqual(out["source"], "catalog/model_caps.json")


class TestBucket(unittest.TestCase):
    def test_header_variants_and_stability(self):
        self.assertEqual(ap.agent_bucket({"X-Agent-Id": "sub-1"}), "sub-1")
        self.assertEqual(ap.agent_bucket({"x-agent-id": "sub-1"}), "sub-1")
        self.assertEqual(ap.agent_bucket({"X-Dsh-Preset": "p"}), "p")
        self.assertEqual(ap.agent_bucket({}), "default")
        self.assertEqual(ap.agent_bucket({"X-Agent-Id": "  a  "}), "a")


class TestCli(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-B", str(ROOT / "tools" / "agent_profiles.py"), *args],
            cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")

    def test_check_exit0(self):
        r = self.run_cli("--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("[OK]", r.stdout)

    def test_list_lists_all_profiles(self):
        r = self.run_cli("--list")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for pid in ap.AGENT_PROFILES:
            self.assertIn("[" + pid + "]", r.stdout)

    def test_json_machine_readable(self):
        r = self.run_cli("--json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(len(payload["profiles"]), len(ap.AGENT_PROFILES))


if __name__ == "__main__":
    unittest.main()
