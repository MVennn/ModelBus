#!/usr/bin/env python3
"""链序回归：WB（WorkBuddy）永远是第一消费来源。

三条硬约束，任一被打破就该红：
1. 真实 family_entries() 里 WB 跳排链首，哪怕它比 OC 贵；
2. QW 尾跳（一年期预付）永远在母条目链尾；OC 跳自 2026-11-14 起按渠道拆成
   独立条目 DeepSeek-4.1-Flash-OC（用户口径：OC 额度到期前先烧），机场孪生跳
   跟在 OC 直连后面、排该条目链尾；
3. 生成器里不存在任何「临时降级」开关 —— 2026-11-05 的 DEMOTE_HOPS 曾把
   WB 降到 OC 之后，整条会话静默跑在 opencode 上计费，不能再有第二次。
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


def _hop(channel: str, upstream: str, price: float, protocol: str = "chat",
         proxy: str | None = None, base_model: str = "deepseek-v4.1-flash") -> dict:
    h = {
        "raw": upstream,
        "original": upstream,
        "channel": channel,
        "upstream": upstream,
        "base_model": base_model,
        "protocol": protocol,
        "price": price,
        "fallbacks": [],
        "chain": [],
        "legacy_ids": [upstream],
    }
    if proxy:
        h["proxy"] = proxy
    return h


def _chains(wb_price: float) -> tuple[list[dict], list[dict]]:
    """返回 (母条目链, OC 拆分条目链)。SPLIT_CHANNEL_DISPLAY 把 OC 跳单列成一条。"""
    items = [
        _hop("OC", "deepseek-v4.1-flash", 0.11),
        _hop("WB", "cn:deepseek-v4.1-flash", wb_price),
        _hop("OC", "deepseek-v4.1-flash", 0.11, proxy=ma.AIRPORT_PROXY),
        _hop("QW", "deepseek-v4.1-flash", 0.00, protocol="messages"),
    ]
    entries = ma.family_entries(items, {}, {}, "auto")
    main = [e for e in entries if e["name"] == "DeepSeek-4.1-Flash"]
    oc = [e for e in entries if e["name"] == "DeepSeek-4.1-Flash-OC"]
    if len(main) != 1 or len(oc) != 1:
        raise AssertionError(
            f"应各有一条链：DeepSeek-4.1-Flash={len(main)}、"
            f"DeepSeek-4.1-Flash-OC={len(oc)}（共 {len(entries)} 条）")
    return main[0]["chain"], oc[0]["chain"]


class HopOrderTest(unittest.TestCase):
    def test_wb_leads_at_equal_price(self):
        main, oc = _chains(0.11)
        self.assertEqual(main[0]["channel"], "WB", "WB 必须在母条目链首")
        self.assertEqual(
            [(h["channel"], h["upstream"]) for h in main],
            [
                ("WB", "cn:deepseek-v4.1-flash"),
                ("QW", "deepseek-v4.1-flash"),
            ],
        )
        # OC 拆条：直连在前、机场孪生在后，链上不再有 WB / QW 跳。
        self.assertEqual([h["channel"] for h in oc], ["OC", "OC"])
        self.assertEqual(str(oc[0].get("proxy") or ""), "", "OC 直连跳排链首")

    def test_wb_leads_even_when_more_expensive(self):
        # 贵 3 倍也必须打头：WB 是额度优先消费对象，不是价格最优对象。
        main, _ = _chains(0.33)
        self.assertEqual(main[0]["channel"], "WB", "价格不能让 WB 让位")

    def test_qw_tail_and_airport_twin_stay_last(self):
        main, oc = _chains(0.11)
        self.assertEqual(main[-1]["channel"], "QW", "QW 尾跳不能被挤掉")
        airport = [i for i, h in enumerate(oc) if str(h.get("proxy") or "") == ma.AIRPORT_PROXY]
        self.assertEqual(len(airport), 1, "机场孪生跳必须且只能有一条")
        self.assertEqual(airport[0], len(oc) - 1, "机场孪生跳排在 OC 条目链尾")

    def test_no_demote_switch_left(self):
        self.assertFalse(
            hasattr(ma, "DEMOTE_HOPS"),
            "降级开关必须不存在；上游限流交给 zgate 逐跳回落",
        )
        self.assertEqual(ma.WB_FIRST_CHANNELS, {"WB"})

    @unittest.skipUnless(ALIAS_MAP.exists(), "本机没有 alias map，跳过磁盘守卫")
    def test_on_disk_alias_map_puts_wb_first(self):
        data = json.loads(ALIAS_MAP.read_text(encoding="utf-8"))
        offenders = []
        for name, model in (data.get("models") or {}).items():
            chain = model.get("chain") or []
            wb = [i for i, h in enumerate(chain) if h.get("channel") == "WB"]
            if wb and wb[0] != 0:
                offenders.append(f"{name}: WB 在第 {wb[0]} 位（链 {[h.get('channel') for h in chain]}）")
        self.assertEqual(offenders, [], "磁盘 alias map 里 WB 跳不在链首：" + "; ".join(offenders))


if __name__ == "__main__":
    unittest.main()
