#!/usr/bin/env python3
"""dsh_sync 的推理档位必须「源头有档位就写出来、手写档位不被冲掉」。

回归背景（2026-11-10）：
1. `_reasoning()` 见到源头 `map:"{}"` 直接返回 {}，Beam / Conatus / Claude-Haiku-5.5 /
   Muse-Spark1.3 / GPT-6-Luna 的档位就此消失 —— 模型选择器里这些模型没有推理等级。
2. `_merge_patch()` 整段重建 `zcode-*` 路由，人工补进 patch 的 reasoningEfforts
   会被每天 12:00 的定时同步冲掉。
3. `compat.thinkingFormat: deepseek` 原来只要源头有 disabled 就加，thinking_budget
   协议和「只有开关」的模型套上它，档位看着有、实际不生效。

跑法：python -B -m unittest discover -s tests -p "test_dsh_sync_efforts.py" -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import dsh_sync as S  # noqa: E402
import dsh_sync as K  # noqa: E402,F401


class ReasoningMappingTest(unittest.TestCase):
    def test_empty_map_drops_levels(self):
        self.assertEqual(S._reasoning(["off", "high"], "{}"), {})

    def test_effort_levels_are_emitted(self):
        out = S._reasoning(["low", "high", "max"], '{"reasoning_effort": reasoningLevel}')
        self.assertEqual(out["reasoningEfforts"], {"low": "low", "high": "high", "max": "max"})
        self.assertEqual(out["compat"], {"thinkingFormat": "deepseek"})

    def test_disabled_becomes_off(self):
        out = S._reasoning(
            ["disabled", "low", "high"], '{"reasoning_effort": reasoningLevel}'
        )
        self.assertEqual(out["reasoningEfforts"]["off"], "disabled")
        self.assertEqual(out["reasoningEfforts"]["high"], "high")

    def test_disabled_only_still_gives_a_level(self):
        out = S._reasoning(["disabled"], '{"reasoning_effort": reasoningLevel}')
        self.assertEqual(out["reasoningEfforts"], {"off": "disabled", "high": "high"})

    def test_unknown_levels_are_filtered(self):
        out = S._reasoning(["enabled", "HIGH", "high"], '{"reasoning_effort": reasoningLevel}')
        self.assertEqual(out["reasoningEfforts"], {"high": "high"})

    def test_thinking_format_needs_real_effort_protocol(self):
        # thinking_budget 协议不吃 deepseek 格式
        gem = S._reasoning(
            ["disabled", "low", "high"],
            '{extra_body: {google: {thinking_config: {thinking_budget: 0}}}}',
        )
        self.assertNotIn("compat", gem)
        self.assertEqual(gem["reasoningEfforts"]["off"], "disabled")

    def test_no_disabled_has_no_off_key(self):
        # 上游不给关闭档时不造 "off"，但 reasoning_effort 协议仍要声明 thinkingFormat
        out = S._reasoning(["low", "high"], '{"reasoning_effort": reasoningLevel}')
        self.assertNotIn("off", out["reasoningEfforts"])
        self.assertEqual(out["compat"], {"thinkingFormat": "deepseek"})


class SharedDefaultEffortTest(unittest.TestCase):
    """provider 级默认档只取组内共同支持的最高档，无共同档则不设。"""

    def test_shared_high_is_set(self):
        models = [
            {"reasoningEfforts": {"off": "disabled", "high": "high"}},
            {"reasoningEfforts": {"low": "low", "high": "high", "max": "max"}},
        ]
        self.assertEqual(S._shared_default_effort(models), "high")

    def test_highest_common_level_wins(self):
        models = [
            {"reasoningEfforts": {"low": "low", "medium": "medium", "high": "high"}},
            {"reasoningEfforts": {"medium": "medium", "high": "high", "max": "max"}},
        ]
        self.assertEqual(S._shared_default_effort(models), "high")

    def test_no_common_level_returns_none(self):
        # 一组只有 high、一组只有 medium：一刀切会让后者 dispatch 抛错
        models = [
            {"reasoningEfforts": {"high": "high"}},
            {"reasoningEfforts": {"low": "low", "medium": "medium"}},
        ]
        self.assertIsNone(S._shared_default_effort(models))

    def test_non_reasoning_model_disables_default(self):
        models = [
            {"reasoningEfforts": {"high": "high"}},
            {"reasoning": False},
        ]
        self.assertIsNone(S._shared_default_effort(models))

    def test_empty_group_returns_none(self):
        self.assertIsNone(S._shared_default_effort([]))


class ScatteredDefaultEffortTest(unittest.TestCase):
    """档位分散组：选覆盖面最广的档 + 给缺失模型注入 wire 别名。"""

    def test_scattered_group_picks_low_and_injects_alias(self):
        models = [
            {"id": "HY4", "reasoningEfforts": {"high": "high"}},
            {"id": "Qwen", "reasoningEfforts": {"low": "low", "medium": "medium", "xhigh": "xhigh"}},
            {"id": "GLM", "reasoningEfforts": {"low": "low", "high": "high", "max": "max"}},
        ]
        best = S._apply_default_effort(models)
        self.assertEqual(best, "low")
        # 只有 high 的 HY4 被注入 low->high 别名；原生支持 low 的不动
        self.assertEqual(models[0]["reasoningEfforts"]["low"], "high")
        # Qwen 原生支持 low，未被注入任何新档位键
        self.assertEqual(set(models[1]["reasoningEfforts"].keys()), {"low", "medium", "xhigh"})
        self.assertEqual(models[2]["reasoningEfforts"]["low"], "low")

    def test_consistent_group_no_alias_injected(self):
        models = [
            {"id": "a", "reasoningEfforts": {"high": "high"}},
            {"id": "b", "reasoningEfforts": {"off": "disabled", "high": "high", "max": "max"}},
        ]
        import copy
        before = copy.deepcopy(models)
        best = S._apply_default_effort(models)
        self.assertEqual(best, "high")
        self.assertEqual(models, before)  # 天然一致组不注入任何别名

    def test_alias_uses_highest_supported_wire(self):
        # 缺失默认档的模型有多个档时，别名应指向它最高的那一档的 wire 值
        models = [
            {"id": "x", "reasoningEfforts": {"low": "low", "medium": "M-WIRE", "xhigh": "X-WIRE"}},
            {"id": "y", "reasoningEfforts": {"high": "high"}},  # 只有 high
        ]
        best = S._apply_default_effort(models)
        # low 覆盖 1、high 覆盖 1、medium 覆盖 1... 并列取靠前 low
        self.assertEqual(best, "low")
        # y 只有 high，注入 low->high
        self.assertEqual(models[1]["reasoningEfforts"]["low"], "high")


OLD_PATCH = """- id: llm-pi-ai
  config:
    providers:
      zcode-free:
        displayName: 免费
        api: openai-completions
        models:
          - id: Beam
            input: [text]
            reasoningEfforts:
              low: low
              high: high
          - id: Fresh
            input: [text]
      custom-keep:
        displayName: 手工 provider
        models:
          - id: CUSTOM
"""


def _route(models: list[dict]) -> dict:
    return {
        "displayName": "免费",
        "api": "openai-completions",
        "models": models,
    }


class MergeKeepsEffortsTest(unittest.TestCase):
    def _merge(self, models: list[dict]) -> tuple[dict, bool]:
        text, changed, item = S._merge_patch(OLD_PATCH, {"zcode-free": _route(models)})
        return yaml.safe_load(text)[0], changed

    def test_handwritten_efforts_survive_regeneration(self):
        item, changed = self._merge([{"id": "Beam", "input": ["text"]}])
        self.assertTrue(changed)
        beam = item["config"]["providers"]["zcode-free"]["models"][0]
        self.assertEqual(beam["reasoningEfforts"], {"low": "low", "high": "high"})

    def test_source_efforts_win_over_stale_handwritten(self):
        item, _ = self._merge(
            [
                {
                    "id": "Beam",
                    "input": ["text"],
                    "reasoningEfforts": {"max": "max"},
                }
            ]
        )
        beam = item["config"]["providers"]["zcode-free"]["models"][0]
        self.assertEqual(beam["reasoningEfforts"], {"max": "max"})

    def test_new_model_without_history_stays_without_efforts(self):
        item, _ = self._merge([{"id": "Brand-New", "input": ["text"]}])
        model = item["config"]["providers"]["zcode-free"]["models"][0]
        self.assertNotIn("reasoningEfforts", model)

    def test_non_zcode_provider_still_preserved(self):
        item, _ = self._merge([{"id": "Beam", "input": ["text"]}])
        providers = item["config"]["providers"]
        self.assertEqual(providers["custom-keep"]["models"][0]["id"], "CUSTOM")


class EffortDriftGateTest(unittest.TestCase):
    """源头有档位、投影后为空 —— 每日同步必须能提前发现，而不是等用户发现。"""

    def test_source_levels_without_projection_is_drift(self):
        rules = {("zcode-main", "BudgetModel"): {"optionSpecs": {"reasoningLevel": {
            "values": ["disabled", "low", "high"],
            "map": "{}",
        }}}}
        routes = {"zcode-main": {"models": [{"id": "BudgetModel"}]}}
        self.assertEqual(len(K._efforts_lost(rules, routes)), 1)

    def test_projected_levels_are_fine(self):
        rules = {("zcode-main", "BudgetModel"): {"optionSpecs": {"reasoningLevel": {
            "values": ["disabled", "low"],
        }}}}
        routes = {"zcode-main": {"models": [
            {"id": "BudgetModel", "reasoningEfforts": {"off": "disabled", "low": "low"}}
        ]}}
        self.assertEqual(K._efforts_lost(rules, routes), [])

    def test_model_without_source_levels_is_not_drift(self):
        rules = {("zcode-main", "Plain"): {"optionSpecs": {}}}
        routes = {"zcode-main": {"models": [{"id": "Plain"}]}}
        self.assertEqual(K._efforts_lost(rules, routes), [])

    def test_levels_outside_dsh_are_reported(self):
        # 源头写着上游特有的档位名，DSH 侧表达不了就必须报出来，而不是静默丢弃
        self.assertEqual(K._efforts_outside(["disabled", "turbo"]), ["turbo"])
        self.assertEqual(K._efforts_outside(["off", "high"]), [])


if __name__ == "__main__":
    unittest.main()
