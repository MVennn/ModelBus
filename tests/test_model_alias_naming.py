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


class DisplayNameSeparationTest(unittest.TestCase):
    """显示名（abbr，可撞/去后缀）与代号（new_id，唯一）分离的数据源锁。"""

    @staticmethod
    def _hop(channel: str, upstream: str, price: float) -> dict:
        return {
            "raw": upstream, "original": upstream, "channel": channel,
            "upstream": upstream, "base_model": upstream, "protocol": "chat",
            "price": price, "fallbacks": [], "chain": [], "legacy_ids": [upstream],
        }

    def test_abbr_is_display_name_source_and_can_collide(self) -> None:
        # 同一型号付费档 + 免费档：family_entries 给两条独立 entry，
        # 它们的 abbr（=写盘 displayName）相同、name（→new_id 代号）不同。
        items = [
            self._hop("WB", "hy4flash", 0.03),
            self._hop("OC", "hy4-flash-free", 0.00),
        ]
        entries = ma.family_entries(items, {}, {}, "auto")
        hy4 = [e for e in entries if e.get("abbr") == "HY4-Flash"]
        self.assertEqual(len(hy4), 2, "付费档与免费档应各成一条")
        self.assertEqual({e["abbr"] for e in hy4}, {"HY4-Flash"},
                         "两条显示名来源相同 —— 重命名可撞")
        self.assertEqual(len({e["name"] for e in hy4}), 2,
                         "代号（name→new_id）必须唯一，一条带 -Free")
        self.assertTrue(any(e["name"].endswith("-Free") for e in hy4))

    def test_writer_projects_abbr_as_display_name(self) -> None:
        # 写盘约定：alias map 每条的 displayName 取 abbr（去后缀族名）。
        src = (HERE.parent / "tools" / "model_alias.py").read_text(encoding="utf-8")
        self.assertIn('"displayName": row["abbr"]', src,
                      "写盘必须把 abbr 投影成 displayName，供 dsh_sync 读成 DSH name")


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
        # 主力组 = DeepSeek 三跳 + Gemini 4 Hydrogen（2026-11-17 接入）。
        # Gemini 走 gem: 显式前缀（渠道 GM 不在 cn:/qoder: 这些天然前缀里），
        # 2026-11-17 GM 从 catiecli 换到 123（odyfree）原生支持工具版，旧 catiecli id 已撤。
        self.assertIn("chat:cn:deepseek-v4.1-flash", ma.MAIN_ORDER)
        self.assertIn("chat:gem:gemini-4-hydrogen-原生1M支持工具", ma.MAIN_ORDER)
        self.assertEqual([m for m in ma.MAIN_ORDER if "gem:" in m],
                         ["chat:gem:gemini-4-hydrogen-原生1M支持工具"])


if __name__ == "__main__":
    unittest.main()
