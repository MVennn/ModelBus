#!/usr/bin/env python3
"""ZCode 受限 CEL 守门：reasoningLevel.map 在写盘/--check 前必须能编译。

回归背景（2026-11-13）：
ZCode 3.18.x 用 packages/model-option-map 的受限 CEL 编译器解析每条 map。
本机 catalog/model_caps.json 长期带旧 JS 方言（裸键 {k:v}、===、!==），
同步链每天 12:00 把它复制进 ~/.zcode/v2/provider_config.json → Zod 校验
整份失败「以内存空配置降级」→ providerCount=0 → ZCode agent 不启动 →
设置页用量统计抛 no_active_workspace，用户只看到「无法读取用量统计」。
守门必须早于写盘，且不能挂到被测纯函数上（旧夹具要继续全绿）。

跑法：python -B -m unittest discover -s tests -p "test_cel_map_guard.py" -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import model_alias as A  # noqa: E402


LEGAL = [
    '{"reasoning_effort": reasoningLevel}',
    'reasoningLevel == "disabled" ? {} : {"reasoning_effort": reasoningLevel}',
    '{"reasoning_effort": reasoningLevel == "disabled" ? "none" : reasoningLevel, '
    '"enable_thinking": reasoningLevel != "disabled"}',
    "{'reasoning_effort': reasoningLevel}",
    '{"extra_body": {"google": {"thinking_config": {"thinking_budget": '
    'reasoningLevel == "disabled" ? 0 : reasoningLevel == "low" ? 1024 : 4096}}}}',
    '{}',
]

ILLEGAL = [
    '{reasoning_effort: reasoningLevel}',                        # 裸键
    '{"reasoning_effort": reasoningLevel === "disabled" ? "none" : reasoningLevel}',  # ===
    '{"enable_thinking": reasoningLevel !== "disabled"}',        # !==
    '{"a": foo()}',                                              # 函数调用
    '{"a": reasoningLevel.x}',                                   # 成员访问
    'foo',                                                        # 未知标识符
    '{"a": 1} + {"b": 2}',                                       # 顶层不是对象
    '{"a": 1, "a": 2}',                                          # 重复键
    '{"a": 1',                                                    # 缺 }
    '{"a": 1} trailing',                                          # 尾部多余
]


class CelMapErrorTest(unittest.TestCase):
    def test_legal_expressions_compile(self):
        for expr in LEGAL:
            with self.subTest(expr=expr):
                self.assertIsNone(A._cel_map_error(expr), expr)

    def test_illegal_expressions_are_rejected(self):
        for expr in ILLEGAL:
            with self.subTest(expr=expr):
                self.assertIsNotNone(A._cel_map_error(expr), expr)

    def test_empty_source_is_rejected_but_blank_map_is_skipped_by_guard(self):
        self.assertIsNotNone(A._cel_map_error(""))
        self.assertIsNotNone(A._cel_map_error("   "))
        # _cel_bad_maps 跳过空串与装饰档位 "{}"；_cel_map_error 自身仍接受 "{}"。
        rules = [_rule("m", "")]
        self.assertEqual(A._cel_bad_maps(rules), [])
        rules = [_rule("m", "{}")]
        self.assertEqual(A._cel_bad_maps(rules), [])
        self.assertIsNone(A._cel_map_error("{}"))

    def test_condition_is_right_associative(self):
        expr = 'reasoningLevel == "a" ? {"a": 1} : reasoningLevel == "b" ? {"b": 2} : {"c": 3}'
        self.assertIsNone(A._cel_map_error(expr))

    def test_variable_name_is_honored(self):
        expr = '{"max_tokens": maxOutputTokens}'
        self.assertIsNone(A._cel_map_error(expr, "maxOutputTokens"))
        self.assertIsNotNone(A._cel_map_error(expr))

    def test_equals_vs_triple_equals_offset_matches_upstream(self):
        # 用日志里那条原始 map：tokenizer 先撞到 "===" 的第三个 "="，offset 36。
        err = A._cel_map_error(
            '{reasoning_effort: reasoningLevel === "disabled" ? "none" : reasoningLevel, '
            'enable_thinking: reasoningLevel !== "disabled"}')
        self.assertIn('unsupported token "="', err)
        self.assertIn('at offset 36', err)  # 与 ZCode 日志里的报错一致


def _rule(model_id: str, map_expr: str | None) -> dict:
    rl = {"values": ["low", "high"]}
    if map_expr is not None:
        rl["map"] = map_expr
    return {
        "modelId": model_id,
        "providerId": "opencode-go-chat",
        "config": {"enabled": True, "optionSpecs": {"reasoningLevel": rl}},
    }


class CelBadMapsTest(unittest.TestCase):
    def test_clean_rules_pass(self):
        rules = [_rule("a", '{"reasoning_effort": reasoningLevel}'),
                 _rule("b", "{}"), _rule("c", None), _rule("d", "")]
        self.assertEqual(A._cel_bad_maps(rules), [])

    def test_old_dialect_is_reported_with_model_id(self):
        rules = [_rule("ok", '{"a": 1}'),
                 _rule("bad-1", '{reasoning_effort: reasoningLevel}'),
                 _rule("bad-2", '{"a": reasoningLevel !== "disabled"}')]
        bad = A._cel_bad_maps(rules)
        self.assertEqual([mid for mid, _ in bad], ["bad-1", "bad-2"])
        self.assertIn("object keys must be string literals", bad[0][1])
        self.assertIn('unsupported token "="', bad[1][1])

    def test_dict_shaped_rules_are_supported(self):
        wrapped = {"providerModelRules": {"a": _rule("a", "{bad: 1}")}}
        bad = A._cel_bad_maps(wrapped)
        self.assertEqual(len(bad), 1)
        self.assertIn("object keys must be string literals", bad[0][1])

    def test_non_dict_reasoning_level_is_ignored(self):
        rules = [{"modelId": "x", "config": {"optionSpecs": {"reasoningLevel": "junk"}}}]
        self.assertEqual(A._cel_bad_maps(rules), [])


class GuardHookOrderTest(unittest.TestCase):
    """守门必须真挂在 main 的 --check 与 --apply 写盘前，且早于备份。"""

    def setUp(self):
        self.src = (REPO / "tools" / "model_alias.py").read_text(encoding="utf-8")

    def test_check_branch_includes_bad_cel_in_return_code(self):
        self.assertIn("bad_cel = _cel_bad_maps(model_rules(cfg))", self.src)
        self.assertIn("return 1 if (any(drift.values()) or lost_efforts or bad_cel) else 0",
                      self.src)

    def test_apply_guard_sits_between_assignment_and_backup(self):
        assign = self.src.index(
            'cfg["config"]["modelConfigRules"]["providerModelRules"] = new_model_rules')
        # 从 assign 之后开始找：文件里还有别的 tmp.write_text / shutil.copy2。
        guard = self.src.index("bad_cel = _cel_bad_maps(new_model_rules)", assign)
        backup = self.src.index("shutil.copy2(path, backup)", guard)
        write = self.src.index("tmp.write_text(", guard)
        self.assertLess(assign, guard)
        self.assertLess(guard, backup)
        self.assertLess(guard, write)
        # 守门失败必须 return 1，不能继续写盘。
        segment = self.src[guard:backup]
        self.assertIn("return 1", segment)

    def test_pure_helpers_are_not_hooked(self):
        # 旧夹具（_effort_is_live / _inherit_efforts）不调用守门，保持行为等价。
        start = self.src.index("def _effort_is_live(")
        end = self.src.index("def _same_family(")
        self.assertNotIn("_cel_map_error", self.src[start:end])


if __name__ == "__main__":
    unittest.main()
