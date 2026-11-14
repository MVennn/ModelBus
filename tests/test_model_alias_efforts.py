#!/usr/bin/env python3
"""model_alias 重建规则时，已落盘的推理档位不能被上游的沉默抹掉。

回归背景（2026-11-10）：
1. `main()` 重建 `providerModelRules` 时只按 `old_rules.get(raw/original/upstream)`
   继承，而上游对 mimo-v2.6-pro / iceman / gemini 系不声明 supported_efforts ——
   这类模型一旦改名或换链，新规则就继承不到档位，档位静默消失。
2. 子型号（mimo-v2.6-pro / mimo-v2.6-flash）共用同一套上游枚举，档位可以互借：
   一条被写空时，用同 base_model 兄弟条目已落盘的值补回来。
3. `--check` 必须能提前发现这种漂移（`drifted_efforts`），否则每天 12:00 的
   定时同步会悄悄把档位抹平，用户只看到「推理等级不见了」。

跑法：python -B -m unittest discover -s tests -p "test_model_alias_efforts.py" -v
"""
from __future__ import annotations

import copy
import sys
import unittest
import unittest.mock
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import model_alias as A  # noqa: E402


def _rule(model_id: str, values, map_expr=None) -> dict:
    rl = {"values": values}
    if map_expr is not None:
        rl["map"] = map_expr
    return {
        "modelId": model_id,
        "providerId": "opencode-go-chat-fast",
        "config": {"enabled": True, "optionSpecs": {"reasoningLevel": rl}},
    }


def _cfg(*rules: dict) -> dict:
    return {"config": {"modelConfigRules": {"providerModelRules": list(rules)}}}


def _entry(name: str, upstream: str, base_model: str, channel: str = "WB",
           protocol: str = "chat") -> dict:
    return {
        "name": name,
        "abbr": name,
        "raw": name,
        "original": upstream,
        "upstream": upstream,
        "base_model": base_model,
        "channel": channel,
        "protocol": protocol,
        "chain": [{"upstream": upstream, "channel": channel}],
    }


class InheritEffortsTest(unittest.TestCase):
    def test_existing_levels_are_kept_verbatim(self):
        cfg = _cfg(_rule("MiMo-2.6-Pro", ["disabled", "high"]))
        entries = [_entry("MiMo-2.6-Pro", "cn:mimo-v2.6-pro", "mimo-v2.6-pro")]
        old = {str(r["modelId"]): r["config"] for r in cfg["config"]["modelConfigRules"]["providerModelRules"]}
        picked = A.pick_rule_config(entries, cfg, old)
        got = picked["MiMo-2.6-Pro"]["optionSpecs"]["reasoningLevel"]["values"]
        self.assertEqual(got, ["disabled", "high"])

    def test_sibling_hit_recovers_a_wiped_model(self):
        # Pro 被某个上游的沉默写空，Flash 还留着完整档位 -> 用同 base_model 兄弟补回
        cfg = _cfg(
            _rule("MiMo-2.6-Pro", []),
            _rule("MiMo-2.6-Flash", ["disabled", "minimal", "high"]),
        )
        entries = [
            _entry("MiMo-2.6-Pro", "cn:mimo-v2.6-pro", "mimo-v2.6-pro"),
            _entry("MiMo-2.6-Flash", "cn:mimo-v2.6-flash", "mimo-v2.6-flash"),
        ]
        old = {str(r["modelId"]): r["config"] for r in cfg["config"]["modelConfigRules"]["providerModelRules"]}
        picked = A.pick_rule_config(entries, cfg, old)
        got = picked["MiMo-2.6-Pro"]["optionSpecs"]["reasoningLevel"]["values"]
        self.assertEqual(got, ["disabled", "minimal", "high"])

    def test_no_source_means_no_invented_levels(self):
        cfg = _cfg(_rule("Other", ["high"]))
        entries = [_entry("Brand-New", "cn:brand-new", "brand-new")]
        old = {str(r["modelId"]): r["config"] for r in cfg["config"]["modelConfigRules"]["providerModelRules"]}
        picked = A.pick_rule_config(entries, cfg, old)
        self.assertNotIn("reasoningLevel", picked["Brand-New"].get("optionSpecs") or {})

    def test_decorative_channel_drops_unusable_levels(self):
        # gem 前缀（Gemini-AIS / GM）不在档位渠道表里、map 又是空的：不回写档位，
        # 免得 GUI 摆一个永远发不出去的下拉
        cfg = _cfg(_rule("Gemini-AIS", ["disabled", "low"]))
        entries = [_entry("Gemini-AIS", "ais-gemini-3.8-flash", "ais-gemini-3.8-flash",
                          channel="GM", protocol="messages")]
        old = {str(r["modelId"]): r["config"] for r in cfg["config"]["modelConfigRules"]["providerModelRules"]}
        picked = A.pick_rule_config(entries, cfg, old)
        self.assertNotIn("reasoningLevel", picked["Gemini-AIS"].get("optionSpecs") or {})

    def test_all_blank_global_is_self_healing(self):
        # 整份配置一条档位都没有（历史事故现场）：不能被当成「装饰渠道」清空
        cfg = _cfg(_rule("Gemini-AIS", []), _rule("Other", []))
        self.assertTrue(A._blank_effort_global(cfg))
        cfg2 = _cfg(_rule("Gemini-AIS", []), _rule("Other", ["high"]))
        self.assertFalse(A._blank_effort_global(cfg2))


class NonChatEffortTest(unittest.TestCase):
    """messages 协议的模型照样能有档位 —— 原先这里无条件写 map="{}"。"""

    def _cfg_with(self, values, map_expr):
        return {"optionSpecs": {"reasoningLevel": {"values": values, "map": map_expr}}}

    def test_messages_protocol_keeps_reasoning_effort_map(self):
        cfg = self._cfg_with(
            ["disabled", "low", "high"],
            '{"reasoning_effort": reasoningLevel == "disabled" ? "none" : reasoningLevel}',
        )
        entry = {"channel": "OC", "protocol": "messages"}
        A._enforce_non_chat_effort(cfg, entry)
        self.assertEqual(cfg["optionSpecs"]["reasoningLevel"]["values"], ["disabled", "low", "high"])
        self.assertIn("reasoning_effort", cfg["optionSpecs"]["reasoningLevel"]["map"])

    def test_messages_protocol_keeps_budget_map_on_decorative_channel(self):
        # 哈基米/AIS 这类渠道：只要 map 是能求值的表达式，档位就真能生效
        cfg = self._cfg_with(
            ["disabled", "low", "medium", "high"],
            '{"extra_body": {"google": {"thinking_config": {"thinking_budget": 4096}}}}',
        )
        entry = {"channel": "GM", "protocol": "chat"}
        A._enforce_non_chat_effort(cfg, entry)
        self.assertEqual(cfg["optionSpecs"]["reasoningLevel"]["values"],
                         ["disabled", "low", "medium", "high"])

    def test_dead_effort_is_blanked(self):
        # 既不在能力表、又没有表达式 = 空头下拉，必须去掉
        cfg = self._cfg_with(["low", "high"], "{}")
        A._enforce_non_chat_effort(cfg, {"channel": "GM", "protocol": "chat"})
        self.assertEqual(cfg["optionSpecs"]["reasoningLevel"], {"map": "{}"})

    def test_effort_is_live_needs_a_real_expression(self):
        self.assertTrue(A._effort_is_live({"channel": "WB"}, {"values": ["low"]}))
        self.assertFalse(A._effort_is_live({"channel": "GM"}, {"values": ["low"], "map": "{}"}))
        self.assertFalse(A._effort_is_live({"channel": "GM"}, {"values": ["low"]}))
        self.assertTrue(A._effort_is_live({"channel": "GM"}, {"values": ["low"], "map": '{"a": 1}'}))


class DriftGateTest(unittest.TestCase):
    def test_values_helper_tolerates_junk(self):
        self.assertEqual(A._effort_values(None), [])
        self.assertEqual(A._effort_values({"optionSpecs": {"reasoningLevel": {"values": "high"}}}), [])
        self.assertEqual(
            A._effort_values({"optionSpecs": {"reasoningLevel": {"values": ["low", 3]}}}),
            ["low", "3"],
        )



class DriftGateSnapshotTest(unittest.TestCase):
    """守门自己不能是哑的：快照必须与重算所用对象分属不同内存。

    2026-11-10 实测事故：drifted_efforts 在 work 深拷贝上取 old_rules，再把同一批
    config 交给 pick_rule_config 原地补写，before 与 after 是同一个 dict，比出来
    永远相等 —— 拿一份档位被清空的配置去跑 --check 也 exit 0。
    """

    def _gate(self, cfg):
        # 只验判定本身：真实价格源/清单会联网，用桩替掉。条目直接从 model_rules
        # 派生，保证「重算」这一侧拿到的是同一批模型（否则全被算成无条目=无档位）。
        def fake_entries(*args, **kwargs):
            return [{"name": r["modelId"], "raw": r["modelId"], "channel": "WB"}
                    for r in A.model_rules(cfg)]
        with unittest.mock.patch.object(A, "inventory", return_value=[]), \
                unittest.mock.patch.object(A, "family_entries", side_effect=fake_entries), \
                unittest.mock.patch.object(A, "pool_entries", return_value=[]):
            return A.drifted_efforts(cfg)

    def test_empty_efforts_are_reported_not_silently_passed(self):
        cfg = _cfg(_rule("Beam", []), _rule("HY3", ["low", "high"]))
        self.assertEqual(self._gate(cfg), ["Beam（无档位，且本轮同步补不回来）"])

    def test_empty_allowlist_lets_known_models_through(self):
        cfg = _cfg(_rule("Beam", []))
        with unittest.mock.patch.object(A, "EMPTY_ALLOWED", {"Beam"}):
            self.assertEqual(self._gate(cfg), [])

    def test_nothing_reported_when_all_have_levels(self):
        cfg = _cfg(_rule("HY3", ["low", "high"]), _rule("Beam", ["low", "high"]))
        self.assertEqual(self._gate(cfg), [])

    def test_snapshot_is_independent_of_recomputed_configs(self):
        # 直接盯住内存别名这个根因：pick_rule_config 就地改写时，快照不受影响。
        cfg = _cfg(_rule("Beam", ["low", "high"]))
        work = copy.deepcopy(cfg)
        landed = {str(r["modelId"]): A._effort_values(r.get("config"))
                  for r in A.model_rules(work)}
        old_rules = {str(r["modelId"]): copy.deepcopy(r.get("config") or {})
                     for r in A.model_rules(work)}
        A._inherit_efforts(old_rules["Beam"], {"name": "Beam", "channel": "GM"},
                           old_rules, [], False)
        self.assertEqual(landed["Beam"], ["low", "high"])


if __name__ == "__main__":
    unittest.main()
