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
    """档位分散组：默认抬到 high + 给缺 high 的模型注入 wire 别名。"""

    def test_scattered_group_defaults_to_high_and_injects_alias(self):
        models = [
            {"id": "HY4", "reasoningEfforts": {"high": "high"}},
            {"id": "Qwen", "reasoningEfforts": {"low": "low", "medium": "medium", "xhigh": "xhigh"}},
            {"id": "GLM", "reasoningEfforts": {"low": "low", "high": "high", "max": "max"}},
        ]
        best = S._apply_default_effort(models)
        self.assertEqual(best, "high")
        # 原生支持 high 的模型不动
        self.assertEqual(models[0]["reasoningEfforts"], {"high": "high"})
        # Qwen 没有 high 档，注入 high->xhigh（它支持的最高档 wire）
        self.assertEqual(models[1]["reasoningEfforts"]["high"], "xhigh")
        self.assertEqual(set(models[2]["reasoningEfforts"].keys()), {"low", "high", "max"})

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
        # 默认档抬到 high；x 没有 high，注入 high->X-WIRE（它最高的档）
        self.assertEqual(best, "high")
        self.assertEqual(models[0]["reasoningEfforts"]["high"], "X-WIRE")
        self.assertEqual(models[1]["reasoningEfforts"], {"high": "high"})


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

    def test_handset_efforts_beat_source(self):
        # 手配白名单模型即使源头算出 off/high，也以 patch 里手配的五档为准
        S.HANDSET_EFFORTS.add("HandsetSample")
        old = OLD_PATCH.replace(
            "          - id: Fresh\n            input: [text]",
            "          - id: Fresh\n            input: [text]\n"
            "          - id: HandsetSample\n            input: [text]\n"
            "            reasoningEfforts: {'off': 'off', low: low, medium: medium, high: high, xhigh: xhigh}",
        )
        try:
            text, changed, _ = S._merge_patch(
                old,
                {"zcode-free": _route([
                    {"id": "HandsetSample", "input": ["text"],
                     "reasoningEfforts": {"off": "disabled", "high": "high"},
                     "name": "HandsetSample"},
                ])},
            )
            by_id = {m["id"]: m for m in yaml.safe_load(text)[0]["config"]["providers"]["zcode-free"]["models"]}
            self.assertTrue(changed)
            self.assertEqual(
                by_id["HandsetSample"]["reasoningEfforts"],
                {"off": "off", "low": "low", "medium": "medium", "high": "high", "xhigh": "xhigh"},
            )
        finally:
            S.HANDSET_EFFORTS.discard("HandsetSample")

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


class DisplayNameProjectionTest(unittest.TestCase):
    """显示名/代号分离：id 是唯一代号，name 是可撞的显示名，投影进 patch。"""

    def _provider(self, model_ids: list[str]) -> dict:
        return {
            "providerId": "opencode-go-chat",
            "providerName": "主力",
            "modelIds": model_ids,
            "baseUrl": "http://127.0.0.1:7871/v1",
        }

    def test_display_name_projected_into_model(self) -> None:
        # alias map 说 HY4-Flash-Free 的显示名是 HY4-Flash（去后缀、可撞）
        display = {"HY4-Flash-Free": "HY4-Flash", "HY4-Flash": "HY4-Flash"}
        _, route = S._build_route(
            self._provider(["HY4-Flash-Free", "HY4-Flash"]), {}, {}, display)
        by_id = {m["id"]: m for m in route["models"]}
        # 两条代号不同、显示名撞成同一个 —— 正是「重命名撞了无所谓」。
        self.assertEqual(by_id["HY4-Flash-Free"]["name"], "HY4-Flash")
        self.assertEqual(by_id["HY4-Flash"]["name"], "HY4-Flash")
        self.assertNotEqual(by_id["HY4-Flash-Free"]["id"], by_id["HY4-Flash"]["id"])

    def test_no_display_name_falls_back_to_id(self) -> None:
        # alias map 没这条时 name 缺省，DSH fallback 到 id（改造前行为不变）
        _, route = S._build_route(self._provider(["Plain"]), {}, {}, {})
        self.assertNotIn("name", route["models"][0])
        self.assertEqual(route["models"][0]["id"], "Plain")

    def test_display_names_from_alias_map_reads_and_degrades(self) -> None:
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "model-alias-map.json"
            p.write_text(json.dumps({
                "models": {
                    "HY4-Flash-Free": {"displayName": "HY4-Flash", "abbr": "HY4-Flash"},
                    "NoName": {"abbr": "NoName"},
                    "BadRow": "not-a-dict",
                }
            }), encoding="utf-8")
            self.assertEqual(
                S._display_names_from_alias_map(p), {"HY4-Flash-Free": "HY4-Flash"})
        # 文件不存在时降级空，不抛错
        self.assertEqual(S._display_names_from_alias_map(Path(d) / "missing.json"), {})


class YamlBoolDialectTest(unittest.TestCase):
    """YAML 1.1 布尔表会把客户端写的裸 off 读成布尔，回写即成 false: false。

    2026-11-19 实况：客户端（js-yaml，YAML 1.2）整体重写 patch 时去掉 'off' 的引号，
    PyYAML 读成 {False: False}，safe_dump 回写 false: false，llm-pi-ai 校验整份配置失败，
    设置页连新建供应商都存不进去。
    """

    def test_unquoted_off_is_still_a_string(self):
        doc = S._load_yaml("reasoningEfforts:\n  off: off\n  low: low\n")
        self.assertEqual(doc["reasoningEfforts"], {"off": "off", "low": "low"})

    def test_true_false_stay_booleans(self):
        self.assertEqual(S._load_yaml("a: true\nb: false\n"), {"a": True, "b": False})

    def test_roundtrip_requotes_off(self):
        item = S._load_yaml(
            "reasoningEfforts: {off: off, low: low, xhigh: xhigh}\n")
        dumped = yaml.safe_dump(item, allow_unicode=True, sort_keys=False)
        self.assertIn("'off': 'off'", dumped)
        self.assertNotIn("false:", dumped)


class EffortSchemaGuardTest(unittest.TestCase):
    def test_invalid_handwritten_efforts_are_not_kept(self):
        routes = {"zcode-main": {"models": [{"id": "HandsetSample", "input": ["text"]}]}}
        old = {"zcode-main": {"models": [
            {"id": "HandsetSample",
             "reasoningEfforts": {"false": False, "low": "low"}},
        ]}}
        S.HANDSET_EFFORTS.add("HandsetSample")
        try:
            out = S._keep_efforts(routes, old)
        finally:
            S.HANDSET_EFFORTS.discard("HandsetSample")
        self.assertNotIn("reasoningEfforts", out["zcode-main"]["models"][0])

    def test_valid_handwritten_efforts_are_still_kept(self):
        routes = {"zcode-main": {"models": [{"id": "HandsetSample", "input": ["text"]}]}}
        old = {"zcode-main": {"models": [
            {"id": "HandsetSample",
             "reasoningEfforts": {"off": "off", "low": "low", "xhigh": "xhigh"}},
        ]}}
        S.HANDSET_EFFORTS.add("HandsetSample")
        try:
            out = S._keep_efforts(routes, old)
        finally:
            S.HANDSET_EFFORTS.discard("HandsetSample")
        self.assertEqual(
            out["zcode-main"]["models"][0]["reasoningEfforts"],
            {"off": "off", "low": "low", "xhigh": "xhigh"})

    def test_boolean_value_inside_map_is_rejected(self):
        self.assertFalse(S._efforts_schema_ok({"off": False}))
        self.assertFalse(S._efforts_schema_ok({"false": False}))
        self.assertTrue(S._efforts_schema_ok(False))
        self.assertTrue(S._efforts_schema_ok({"off": "disabled"}))


if __name__ == "__main__":
    unittest.main()

