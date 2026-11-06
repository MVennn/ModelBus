#!/usr/bin/env python3
"""Qoder 侧免费型号进链的回归（2026-11-06）。

背景：Qoder 的 Qwen3.8-Flash（catalog key qfmodel）price_factor 0.0、is_free=true，
而 model_alias 的条目只来自 provider_config 的 personalModelIds。白名单补建原本
只按「裸型号名」去重，Qwen3.8-Flash 已被 OC 的 messages 条目占位，于是 QD 那条
免费跳被静默吞掉 —— 名单写了等于没写。

时效：Qoder 的免费窗口在 2026-11-06 23:59 前后关闭（price_factor 0.0 → 0.04，
usage.billable false → true），但仍比 OC 的 0.09 便宜，所以链首继续是 QD。

两条硬约束：
1. 白名单里显式写了渠道前缀（chat:qoder:…）的条目必须带 explicit_channel，
   否则 main() 的裸名去重会把新渠道的跳当重复丢掉；
2. QD(0.0) 与 OC 的 messages 跳必须并成同一条链（MERGE_ACROSS_PROTOCOL +
   MERGE_FREE_GB），Qwen-3.8-Flash 只有一个显示名，链首是 QD。
"""
from __future__ import annotations

import importlib.util
import json
import os
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

ALIAS_MAP = Path(os.path.expanduser("~/.zcode/v2/model-alias-map.json"))


class WhitelistExplicitChannelTest(unittest.TestCase):
    def test_explicit_channel_prefix_is_marked(self) -> None:
        items = ma.whitelist_items(["chat:qoder:Qwen3.8-Flash"])
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["channel"], "QD")
        self.assertEqual(item["upstream"], "Qwen3.8-Flash")
        self.assertTrue(item.get("explicit_channel"))

    def test_bare_name_is_not_marked(self) -> None:
        # 没写渠道前缀时 classify 只能猜（Qwen3.8-Max 会被猜成 OC），
        # 这种条目必须继续走裸名去重，否则会与已在 QD 下的同一条重复。
        items = ma.whitelist_items(["chat:Qwen3.8-Max"])
        self.assertEqual(len(items), 1)
        self.assertFalse(items[0].get("explicit_channel"))

    def test_cn_prefix_is_marked(self) -> None:
        items = ma.whitelist_items(["chat:cn:hy4std"])
        self.assertEqual(items[0]["channel"], "WB")
        self.assertTrue(items[0].get("explicit_channel"))


class QwenFlashChainTest(unittest.TestCase):
    """状态回归：跑过 --apply 的机器上，Qwen-3.8-Flash 必须有一条带 QD 首跳的链。"""

    def setUp(self) -> None:
        if not ALIAS_MAP.exists():
            self.skipTest("没有 model-alias-map.json")
        data = json.loads(ALIAS_MAP.read_text(encoding="utf-8"))
        self.models = data.get("models") or {}

    def test_qd_hop_leads_the_chain(self) -> None:
        """QD 必须是这条链最便宜的一跳。

        2026-11-06 23:44 上游还是 price_factor 0.0（真免费），23:59 已改成 0.04、
        usage.billable 也从 false 变 true —— 免费窗口关掉了。所以这里不再写死 0.0，
        只断言「比 OC 兜底便宜、排链首」；哪天上游涨价超过 OC，这条会红，提示复核。
        """
        entry = self.models.get("Qwen-3.8-Flash")
        if entry is None:
            self.skipTest("当前配置没有 Qwen-3.8-Flash")
        chain = entry.get("chain") or []
        self.assertTrue(chain, "Qwen-3.8-Flash 链为空")
        head = chain[0]
        self.assertEqual(head.get("channel"), "QD", f"链首不是 QD：{head}")
        head_price = head.get("price")
        self.assertIsNotNone(head_price, "QD 跳没有价格，会被静默剔除")
        others = [h.get("price") for h in chain[1:] if h.get("price") is not None]
        self.assertTrue(others, f"链里没有 OC 付费兜底跳：{chain}")
        self.assertLessEqual(head_price, min(others), f"QD 不再是最便宜的一跳：{head_price} vs {others}")
        # 同一条链里必须还留着 OC 的付费跳做兜底（跨协议合并）。
        self.assertTrue(
            any(hop.get("channel") == "OC" for hop in chain),
            f"链里没有 OC 兜底跳：{chain}",
        )

    def test_no_duplicate_display_name(self) -> None:
        # 合并后不允许再出现 Qwen-3.8-Flash-Msg / -Resp 这类同型号分身。
        for name in self.models:
            self.assertFalse(
                name.startswith("Qwen-3.8-Flash-"),
                f"出现了同型号分身：{name}",
            )


if __name__ == "__main__":
    unittest.main()
