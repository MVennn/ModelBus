#!/usr/bin/env python3
"""显示名与渠道前缀的回归（2026-11-06）。

背景：用户口径「没有相同/可合并的模型就不要尾缀」。旧 ABBR 把 hy4std 叫成
HY4-Std、把任何 flash 收成 -Fs、把任何 preview 收成 -Pre，于是同一个上游模型
在不同渠道下被读成两个型号，选择器里出现 HY4-Std / HY4-Pre 这种纯人造后缀。

三条硬约束：
1. 回包 model 就是 hy4，显示名也必须是 HY4 —— 不许再出现 -Std；
2. abbreviate 的兜底不许再造 -Fs / -Pre 这类缩写后缀；
3. 白名单里写显式渠道（chat:oc:qwen3.8-max）必须真的解析成 OC 渠道，
   且 upstream 不带 "oc:" 前缀（否则会被当成另一个型号名去查价）。
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
spec = importlib.util.spec_from_file_location("model_alias", HERE.parent / "tools" / "model_alias.py")
assert spec and spec.loader
ma = importlib.util.module_from_spec(spec)
sys.modules["model_alias"] = ma
spec.loader.exec_module(ma)


class AbbrTest(unittest.TestCase):
    def test_hy4std_has_no_std_suffix(self) -> None:
        # 上游回包 model 是 hy4，加 -Std 等于让用户以为这是另一个型号。
        self.assertEqual(ma.abbreviate("hy4std"), "HY4")

    def test_preview_family_shares_one_name(self) -> None:
        for upstream in ("hy4-preview", "hy4-preview-f", "hy4-preview-ctrl", "hy4-preview-exp1"):
            self.assertEqual(ma.abbreviate(upstream), "HY4-Preview", upstream)

    def test_no_invented_suffixes(self) -> None:
        # 兜底不许再缩成 -Fs / -Pre：那会造出用户看不出原型的名字。
        cases = ["qwen3.8-flash", "glm-5.3-flash", "mimo-v2.6-flash", "step-5-preview", "kimi-k2.8-preview"]
        for upstream in cases:
            name = ma.abbreviate(upstream)
            self.assertFalse(name.endswith("-Fs"), upstream)
            self.assertFalse(name.endswith("-Pre"), upstream)

    def test_vendor_names_stay_readable(self) -> None:
        self.assertEqual(ma.abbreviate("kimi-k2.8-preview"), "Kimi-K2.8-Preview")
        self.assertEqual(ma.abbreviate("step-5-preview"), "Step-5-Preview")
        self.assertEqual(ma.abbreviate("qwen3.8-max"), "Qwen-3.8-Max")


class ExplicitOcPrefixTest(unittest.TestCase):
    def test_oc_prefix_parses(self) -> None:
        item = ma.classify("oc:qwen3.8-max", "chat", {}, {})
        self.assertIsNotNone(item)
        self.assertEqual(item["channel"], "OC")
        self.assertEqual(item["upstream"], "qwen3.8-max")

    def test_oc_prefix_item_is_built_by_whitelist(self) -> None:
        items = ma.whitelist_items(["chat:oc:qwen3.8-max"])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["channel"], "OC")
        self.assertEqual(items[0]["upstream"], "qwen3.8-max")
        self.assertTrue(items[0].get("explicit_channel"))

    def test_main_order_names_the_gem_hop_explicitly(self) -> None:
        # 主力组当前是 DeepSeek 三跳 + Gemini 单跳。Gemini 那条走 gem: 显式前缀
        # （渠道 GM 不在 cn:/qoder: 这些天然前缀里），缺价时只留 WARN 不中断。
        self.assertIn("chat:cn:deepseek-v4.1-flash", ma.MAIN_ORDER)
        self.assertIn("chat:gem:ais-gemini-3.8-flash", ma.MAIN_ORDER)


if __name__ == "__main__":
    unittest.main()
