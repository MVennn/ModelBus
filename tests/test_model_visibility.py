#!/usr/bin/env python3
"""隐藏名单（tools/model_visibility.py）与投影过滤（tools/dsh_sync.py）回归。"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import dsh_sync  # noqa: E402
import model_alias  # noqa: E402
import model_visibility as V  # noqa: E402

CFG = {
    "config": {
        "providerOrder": ["opencode-go-chat", "opencode-go-chat-free"],
        "providerConfigRules": {"providerRules": [
            {"providerId": "opencode-go-chat", "providerName": "主力",
             "config": {"modelOrder": ["DeepSeek-4.1-Flash-OC", "DeepSeek-4.1-Flash"]}},
            {"providerId": "opencode-go-chat-free", "providerName": "免费",
             "config": {"modelOrder": ["Beam"]}},
        ]},
    }
}


class HiddenStateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def _write(self, doc: dict) -> Path:
        path = self.root / "model-hidden.json"
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return path

    def test_missing_file_is_empty_state(self):
        state = V.load_state(self.root / "nope.json")
        self.assertEqual(state["models"], {})
        self.assertEqual(state["providers"], {})

    def test_corrupt_file_degrades_to_empty(self):
        path = self.root / "bad.json"
        path.write_text("{not json", encoding="utf-8")
        self.assertEqual(V.load_state(path)["models"], {})

    def test_roundtrip_keeps_reason_and_channel(self):
        path = self.root / "model-hidden.json"
        state = V.load_state(path)
        state["models"]["Beam"] = {"reason": "OC 暂停", "at": "t", "channel": "OC"}
        V.save_state(state, path)
        again = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(again["models"]["Beam"]["channel"], "OC")
        self.assertEqual(again["version"], 1)

    def test_provider_groups_reads_source_config(self):
        cfg = self.root / "provider_config.json"
        cfg.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
        groups = V.provider_groups(cfg)
        self.assertEqual(groups["opencode-go-chat"]["models"],
                         ["DeepSeek-4.1-Flash-OC", "DeepSeek-4.1-Flash"])


class ProjectionFilterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.providers = [
            {"providerId": "opencode-go-chat", "providerName": "主力",
             "modelIds": ["DeepSeek-4.1-Flash-OC", "DeepSeek-4.1-Flash"], "baseUrl": "u", "apiKey": "k"},
            {"providerId": "opencode-go-chat-free", "providerName": "免费",
             "modelIds": ["Beam"], "baseUrl": "u", "apiKey": "k"},
        ]

    def test_model_hidden_from_projection_only(self):
        kept = dsh_sync._apply_hidden(self.providers, set(), {"DeepSeek-4.1-Flash-OC"})
        self.assertEqual([p["providerId"] for p in kept],
                         ["opencode-go-chat", "opencode-go-chat-free"])
        self.assertEqual(kept[0]["modelIds"], ["DeepSeek-4.1-Flash"])
        # 源对象没有被就地修改（隐藏不是删除）
        self.assertEqual(len(self.providers[0]["modelIds"]), 2)

    def test_group_with_every_model_hidden_disappears(self):
        kept = dsh_sync._apply_hidden(self.providers, set(), {"Beam"})
        self.assertEqual([p["providerId"] for p in kept], ["opencode-go-chat"])

    def test_provider_level_hide(self):
        kept = dsh_sync._apply_hidden(self.providers, {"opencode-go-chat"}, set())
        self.assertEqual([p["providerId"] for p in kept], ["opencode-go-chat-free"])

    def test_hiding_everything_raises(self):
        with self.assertRaises(dsh_sync.DshSyncError):
            dsh_sync._apply_hidden(self.providers, {"opencode-go-chat", "opencode-go-chat-free"}, set())

    def test_efforts_lost_skips_hidden_models(self):
        rules = {("opencode-go-chat", "Beam"): {
            "optionSpecs": {"reasoningLevel": {"values": ["off", "high"]}},
        }}
        self.assertEqual(len(dsh_sync._efforts_lost(rules, {})), 1)
        self.assertEqual(dsh_sync._efforts_lost(rules, {}, {"Beam"}), [])


class SharedHiddenSetsTest(unittest.TestCase):
    """隐藏名单解析只有一份：model_alias.hidden_sets()，dsh_sync 也走它。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.path = self.root / "model-hidden.json"

    def test_reads_models_and_providers(self):
        self.path.write_text(json.dumps({
            "version": 1,
            "providers": {"opencode-go-chat-free": True},
            "models": {"Beam": {"reason": "OC 暂停", "channel": "OC"}},
        }, ensure_ascii=False), encoding="utf-8")
        providers, models = model_alias.hidden_sets(self.path)
        self.assertEqual(providers, {"opencode-go-chat-free"})
        self.assertEqual(models, {"Beam"})

    def test_false_means_visible_again(self):
        self.path.write_text(json.dumps({"models": {"Beam": False, "Iceman": {}}}), encoding="utf-8")
        _, models = model_alias.hidden_sets(self.path)
        self.assertEqual(models, {"Iceman"})

    def test_missing_and_corrupt_degrade_to_empty(self):
        self.assertEqual(model_alias.hidden_sets(self.root / "nope.json"), (set(), set()))
        bad = self.root / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        self.assertEqual(model_alias.hidden_sets(bad), (set(), set()))

    def test_dsh_sync_delegates_to_the_same_reader(self):
        self.path.write_text(json.dumps({"models": {"Beam": {}}}), encoding="utf-8")
        with mock.patch.object(dsh_sync, "HIDDEN_FILE", self.path):
            self.assertEqual(dsh_sync._hidden_sets(), (set(), {"Beam"}))


class ChannelHideSwitchTest(unittest.TestCase):
    """渠道级真开关：隐藏渠道跳从 chain 移除，纯该渠道型号整条消失，show 可逆。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.path = self.root / "h.json"

    def _write(self, doc):
        self.path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    def test_hidden_channels_reads_and_normalizes_case(self):
        self._write({"channels": {"OC": {"reason": "暂停"}, "wb": False}})
        self.assertEqual(model_alias.hidden_channels(self.path), {"OC"})

    def test_missing_corrupt_and_false_degrade_to_empty(self):
        self.assertEqual(model_alias.hidden_channels(self.root / "nope.json"), set())
        bad = self.root / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        self.assertEqual(model_alias.hidden_channels(bad), set())
        self._write({"channels": {"OC": False}})
        self.assertEqual(model_alias.hidden_channels(self.path), set())

    def test_chain_filters_hidden_channel_hops(self):
        row = {"chain": [
            {"channel": "WB", "upstream": "w1"},
            {"channel": "OC", "upstream": "o1"},
            {"channel": "OC", "upstream": "o2", "proxy": "px"},
        ]}
        got = model_alias.chain_without_hidden_channels(row, {"OC"})
        self.assertEqual(got, [{"channel": "WB", "upstream": "w1"}])
        self.assertEqual(len(row["chain"]), 3)  # 入参不改

    def test_pure_hidden_channel_chain_becomes_empty(self):
        row = {"chain": [{"channel": "OC", "upstream": "o1"}]}
        self.assertEqual(model_alias.chain_without_hidden_channels(row, {"OC"}), [])

    def test_legacy_single_upstream_entry_gets_one_hop(self):
        row = {"upstream": "o1", "channel": "OC", "base_model": "x"}
        got = model_alias.chain_without_hidden_channels(row, set())
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["channel"], "OC")
        self.assertEqual(model_alias.chain_without_hidden_channels(row, {"OC"}), [])

    def test_no_hidden_channel_preserves_chain(self):
        row = {"chain": [{"channel": "OC", "upstream": "o1"}]}
        self.assertEqual(model_alias.chain_without_hidden_channels(row, set()),
                         [{"channel": "OC", "upstream": "o1"}])

    def test_classify_prefers_full_chain_for_show_restore(self):
        # 隐藏期间 alias 里 chain 被截断，full_chain 留完整快照；show 重建时
        # classify 必须优先读 full_chain，否则被藏的跳永久丢失（实测过的回归）。
        alias_models = {"HY4-Flash-Free": {
            "channel": "WB", "upstream": "cn:hy4flash-free",
            "base_model": "hy4flash-free", "protocol": "chat",
            "chain": [{"channel": "WB", "upstream": "cn:hy4flash-free"}],
            "full_chain": [
                {"channel": "WB", "upstream": "cn:hy4flash-free"},
                {"channel": "OC", "upstream": "hy4-flash-free"},
            ],
        }}
        got = model_alias.classify("HY4-Flash-Free", "chat", alias_models, {})
        self.assertEqual([h["channel"] for h in got["chain"]], ["WB", "OC"])

    def test_classify_without_full_chain_uses_chain(self):
        alias_models = {"X": {"channel": "WB", "upstream": "cn:x",
                              "chain": [{"channel": "WB", "upstream": "cn:x"}]}}
        got = model_alias.classify("X", "chat", alias_models, {})
        self.assertEqual([h["channel"] for h in got["chain"]], ["WB"])

    def test_show_all_clears_channels(self):
        state = V.load_state(self.path)
        state["channels"]["OC"] = {"reason": "test"}
        V.save_state(state, self.path)
        with mock.patch.object(V, "HIDDEN_FILE", self.path), \
             mock.patch.object(V, "_sync", return_value=0):
            V.cmd_show(argparse.Namespace(all=True, channel=None, model=None,
                                          provider=None, dry_run=False, no_sync=False))
        self.assertEqual(V.load_state(self.path)["channels"], {})


if __name__ == "__main__":
    unittest.main()
