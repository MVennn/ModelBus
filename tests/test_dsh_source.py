#!/usr/bin/env python3
"""--source compat/dsh 行为等价与 DSH 原生真源回归。"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import dsh_sync  # noqa: E402

FIXTURE_CFG = {
    "config": {
        "providerConfigRules": {"providerRules": [
            {"providerId": "opencode-go-chat", "providerName": "主力",
             "config": {"modelOrder": ["DeepSeek-4.1-Flash", "HY3"],
                        "api": {"baseUrl": "http://127.0.0.1:7871/v1"},
                        "access": {"apiKey": "fixture-key"}}},
            {"providerId": "opencode-go-chat-free", "providerName": "免费",
             "config": {"modelOrder": ["Beam"], "api": {}, "access": {"apiKey": "fixture-key"}}},
        ]},
        "providerOrder": ["opencode-go-chat", "opencode-go-chat-free"],
        "modelConfigRules": {"providerModelRules": [
            {"providerId": "opencode-go-chat", "modelId": "DeepSeek-4.1-Flash",
             "config": {"properties": {"contextWindow": 128000},
                        "optionSpecs": {"maxOutputTokens": {"max": 8192},
                                        "reasoningLevel": {"values": ["off", "high"], "map": "{}"}}}},
        ]},
    }
}

EFFECTIVE = {
    "DeepSeek-4.1-Flash": {"config": {"properties": {"contextWindow": 128000,
                                                     "inputFormat": {"supportsImage": False}},
                                      "optionSpecs": {"maxOutputTokens": {"max": 8192},
                                                      "reasoningLevel": {"values": ["off", "high"], "map": "{}"}}}},
    "HY3": {"config": {"properties": {"contextWindow": 64000}, "optionSpecs": {}}},
    "Beam": {"config": {"properties": {"contextWindow": 32000}, "optionSpecs": {}}},
}


class DshCheckWithoutCredentialTest(unittest.TestCase):
    """C3 回归：--source dsh --check 不因凭据库缺 key 触发 exit 2。"""

    def test_dsh_check_without_credential_returns_drift_only(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            prof = home / "profiles" / "desktop"
            prof.mkdir(parents=True)
            (prof / "cordis.patch.yml").write_text(
                "dsh:\n  preset: desktop\n- id: llm-pi-ai\n  config:\n    providers: {}\n",
                encoding="utf-8",
            )
            (home / ".credentials.yaml").write_text("refs: {}\n", encoding="utf-8")
            inv = home / "modelbus-inventory.json"
            dsh_sync._export_inventory(FIXTURE_CFG, inv, catalog_caps=False)
            rc = dsh_sync._main([
                "--source", "dsh", "--check",
                "--dsh-home", str(home), "--inventory", str(inv),
            ])
            self.assertIn(rc, (0, 1))
            self.assertNotEqual(rc, 2)

class DshSourceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.cfg = self.root / "provider_config.json"
        self.cfg.write_text(json.dumps(FIXTURE_CFG, ensure_ascii=False), encoding="utf-8")
        self.inv = self.root / "modelbus-inventory.json"
        self.env_patch = mock.patch.dict(os.environ, {}, clear=False)
        self.env_patch.start()
        self.eff_patch = mock.patch.object(dsh_sync, "_effective_metadata", return_value=EFFECTIVE)
        self.ledger_patch = mock.patch.object(
            dsh_sync, "DSH_LEDGER", self.root / "zcode-model-ledger.json")
        self.eff_patch.start()
        self.ledger_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.addCleanup(self.eff_patch.stop)
        self.addCleanup(self.ledger_patch.stop)
        self.addCleanup(self.tmp.cleanup)

    def _routes(self, providers, effective, rules):
        out = {}
        for p in providers:
            dsh_id, route = dsh_sync._build_route(p, effective, rules)
            out[dsh_id] = route
        return out

    def test_compat_default_unchanged(self):
        providers, eff, rules = dsh_sync._load_source("compat", self.cfg, self.inv)
        self.assertEqual([p["providerId"] for p in providers],
                         ["opencode-go-chat", "opencode-go-chat-free"])
        self.assertEqual(providers[0]["apiKey"], "fixture-key")
        self.assertEqual(eff, EFFECTIVE)
        self.assertEqual(sorted(self._routes(providers, eff, rules)),
                         ["zcode-free", "zcode-main"])

    @staticmethod
    def _without_key(providers):
        return [{k: v for k, v in p.items() if k != "apiKey"} for p in providers]

    def test_export_then_dsh_matches_compat(self):
        compat = dsh_sync._load_source("compat", self.cfg, self.inv)
        dsh_sync._export_inventory(FIXTURE_CFG, self.inv, catalog_caps=False)
        dsh_src = dsh_sync._load_source("dsh", self.cfg, self.inv)
        self.assertEqual(self._without_key(compat[0]), self._without_key(dsh_src[0]))
        self.assertEqual(compat[1], dsh_src[1])
        self.assertEqual(compat[2], dsh_src[2])
        self.assertEqual(self._routes(*compat), self._routes(*dsh_src))
        self.assertEqual(compat[0][0]["apiKey"], "fixture-key")
        self.assertEqual(dsh_src[0][0]["apiKey"], "")

    def test_merge_patch_byte_equivalent(self):
        compat = dsh_sync._load_source("compat", self.cfg, self.inv)
        dsh_sync._export_inventory(FIXTURE_CFG, self.inv, catalog_caps=False)
        dsh_src = dsh_sync._load_source("dsh", self.cfg, self.inv)
        base = "- id: llm-pi-ai\n  config:\n    providers: {}\n"
        self.assertEqual(dsh_sync._merge_patch(base, self._routes(*compat))[0],
                         dsh_sync._merge_patch(base, self._routes(*dsh_src))[0])

    def test_dsh_source_does_not_read_zcode_config(self):
        dsh_sync._export_inventory(FIXTURE_CFG, self.inv, catalog_caps=False)
        missing = self.root / "does-not-exist.json"
        providers, _eff, _rules = dsh_sync._load_source("dsh", missing, self.inv)
        self.assertEqual(sum(len(p["modelIds"]) for p in providers), 3)

    def test_dsh_keeps_full_model_set_with_catalog_caps(self):
        dsh_sync._export_inventory(FIXTURE_CFG, self.inv, catalog_caps=True)
        inv = json.loads(self.inv.read_text(encoding="utf-8"))
        self.assertEqual(inv["schema"], "modelbus-inventory/v1")
        self.assertEqual(inv["capabilities_source"], "catalog/model_caps.json")
        providers, eff, rules = dsh_sync._load_source("dsh", self.cfg, self.inv)
        routes = self._routes(providers, eff, rules)
        ids = [m["id"] for r in routes.values() for m in r["models"]]
        self.assertEqual(sorted(ids), ["Beam", "DeepSeek-4.1-Flash", "HY3"])
        self.assertIn("contextWindow", routes["zcode-main"]["models"][0])

    def test_export_writes_no_credential(self):
        dsh_sync._export_inventory(FIXTURE_CFG, self.inv, catalog_caps=False)
        self.assertNotIn("fixture-key", self.inv.read_text(encoding="utf-8"))

    def test_unknown_source_raises(self):
        with self.assertRaises(dsh_sync.DshSyncError):
            dsh_sync._load_source("bogus", self.cfg, self.inv)

    def test_inventory_schema_guard(self):
        bad = self.root / "bad.json"
        bad.write_text(json.dumps({"schema": "other/v1"}), encoding="utf-8")
        with self.assertRaises(dsh_sync.DshSyncError):
            dsh_sync._load_source("dsh", self.cfg, bad)

    def test_missing_inventory_is_actionable_error(self):
        with self.assertRaises(dsh_sync.DshSyncError) as ctx:
            dsh_sync._load_source("dsh", self.cfg, self.root / "nope.json")
        self.assertIn("--export-inventory", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
