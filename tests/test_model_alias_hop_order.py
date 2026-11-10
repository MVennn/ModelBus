#!/usr/bin/env python3
"""链序回归：WB（WorkBuddy）永远是第一消费来源。

三条硬约束，任一被打破就该红：
1. 真实 family_entries() 里 WB 跳排链首，哪怕它比 OC 贵；
2. QW 尾跳（一年期预付）永远在链尾，机场孪生跳紧随其后；
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


def _chain(wb_price: float) -> list[dict]:
    items = [
        _hop("OC", "deepseek-v4.1-flash", 0.11),
        _hop("WB", "cn:deepseek-v4.1-flash", wb_price),
        _hop("OC", "deepseek-v4.1-flash", 0.11, proxy=ma.AIRPORT_PROXY),
        _hop("QW", "deepseek-v4.1-flash", 0.00, protocol="messages"),
    ]
    entries = ma.family_entries(items, {}, {}, "auto")
    deepseek = [e for e in entries if e["base_model"] == "deepseek-v4.1-flash"]
    if len(deepseek) != 1:
        raise AssertionError(f"deepseek-v4.1-flash 应只有一条链，实际 {len(deepseek)}")
    return deepseek[0]["chain"]


class HopOrderTest(unittest.TestCase):
    def test_wb_leads_at_equal_price(self):
        chain = _chain(0.11)
        self.assertEqual(chain[0]["channel"], "WB", "WB 必须在链首")
        self.assertEqual(
            [(h["channel"], h["upstream"]) for h in chain][:3],
            [
                ("WB", "cn:deepseek-v4.1-flash"),
                ("OC", "deepseek-v4.1-flash"),
                ("OC", "deepseek-v4.1-flash"),
            ],
        )

    def test_wb_leads_even_when_more_expensive(self):
        # 贵 3 倍也必须打头：WB 是额度优先消费对象，不是价格最优对象。
        chain = _chain(0.33)
        self.assertEqual(chain[0]["channel"], "WB", "价格不能让 WB 让位")

    def test_qw_tail_and_airport_twin_stay_last(self):
        chain = _chain(0.11)
        self.assertEqual(chain[-1]["channel"], "QW", "QW 尾跳不能被挤掉")
        airport = [i for i, h in enumerate(chain) if str(h.get("proxy") or "") == ma.AIRPORT_PROXY]
        self.assertEqual(len(airport), 1, "机场孪生跳必须且只能有一条")
        self.assertEqual(airport[0], len(chain) - 2, "机场孪生跳紧邻 QW 之前")

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


# GM（catiecli 中转）7 个 Gemini Flash 档：同渠道、同价（GM_PRICES 全是 0.11），
# 跳序只能由 HOP_PRIORITY 决定。顺序 = 新一代优先，尾跳是 3-preview。
GEMINI_HOPS = [
    "ais-gemini-3.8-flash",
    "ais-gemini-3.7-flash",
    "ais-gemini-3.6-flash",
    "ais-gemini-3.5-flash",
    "ais-gemini-3.5-flash-lite",
    "ais-gemini-3.1-flash-lite",
    "ais-gemini-3-flash-preview",
]


def _gemini_chain() -> list[dict]:
    """乱序喂 7 个同价 GM 跳，链序必须由 HOP_PRIORITY 纠正回 3.8 → 3-preview。"""
    items = [
        _hop("GM", upstream, ma.GM_PRICES[upstream], base_model=upstream)
        for upstream in reversed(GEMINI_HOPS)
    ]
    entries = ma.family_entries(items, {}, {}, "auto")
    gem = [e for e in entries if e["abbr"] == "Gemini-AIS"]
    if len(gem) != 1:
        raise AssertionError(f"7 个 GM 跳应并成一条 Gemini-AIS，实际 {len(gem)} 条")
    return gem[0]["chain"]


class GeminiHopOrderTest(unittest.TestCase):
    def test_gemini_chain_is_seven_hops_in_version_order(self) -> None:
        chain = _gemini_chain()
        self.assertEqual(len(chain), 7, "Gemini-AIS 必须是 7 跳")
        self.assertEqual(
            [h["upstream"] for h in chain],
            GEMINI_HOPS,
            "链序必须严格是 3.8 → 3.7 → 3.6 → 3.5 → 3.5-lite → 3.1-lite → 3-preview",
        )
        self.assertEqual({h["channel"] for h in chain}, {"GM"})
        self.assertEqual({h["price"] for h in chain}, {0.11})

    def test_hop_priority_covers_every_gemini_hop(self) -> None:
        # 漏一个就回落到默认 99，会被 3.5 之类的字符串序顶到前面。
        self.assertEqual(
            {upstream for upstream in ma.HOP_PRIORITY if upstream.startswith("ais-gemini")},
            set(GEMINI_HOPS),
        )
        self.assertEqual(
            sorted(ma.HOP_PRIORITY, key=lambda u: ma.HOP_PRIORITY[u]),
            GEMINI_HOPS,
        )
        self.assertGreater(
            ma.HOP_PRIORITY_DEFAULT,
            max(ma.HOP_PRIORITY.values()),
            "默认值必须大于所有显式优先级，其它渠道的顺序才不会被改",
        )

    def test_non_gemini_hops_keep_default_priority(self) -> None:
        chain = _chain(0.11)
        order = [ma.HOP_PRIORITY.get(h["upstream"], ma.HOP_PRIORITY_DEFAULT) for h in chain]
        self.assertEqual(set(order), {ma.HOP_PRIORITY_DEFAULT}, "非 GM 跳一律取默认优先级")


if __name__ == "__main__":
    unittest.main()
