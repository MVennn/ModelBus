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

def _gemini_entries() -> list[dict]:
    """乱序喂 7 个 GM 跳：必须收敛成一条 Gemini-AIS 链。"""
    items = [
        _hop("GM", upstream, ma.GM_PRICES[upstream], base_model=upstream)
        for upstream in reversed(GEMINI_HOPS)
    ]
    return ma.family_entries(items, {}, {}, "auto")


def _entry_by_abbr(abbr: str) -> dict:
    entries = _gemini_entries()
    hits = [e for e in entries if e["abbr"] == abbr]
    if len(hits) != 1:
        raise AssertionError(f"{abbr} 应正好一条条目，实际 {len(hits)} 条")
    return hits[0]


class GeminiHopOrderTest(unittest.TestCase):
    def test_ais_chain_is_three_gm_hops_in_version_order(self) -> None:
        entry = _entry_by_abbr("Gemini-AIS")
        chain = entry["chain"]
        # CHAIN_CAP：AIS 按次计费，链上只留 3.8 / 3.7 / 3.6（见 ROUTING-POLICY §8.3）。
        self.assertEqual(len(chain), 3, "Gemini-AIS 只保留前 3 跳")
        self.assertEqual(
            [h["upstream"] for h in chain],
            GEMINI_HOPS[:3],
            "链序必须严格是 3.8 → 3.7 → 3.6",
        )
        self.assertEqual({h["channel"] for h in chain}, {"GM"}, "AIS 链里不该再出现别的渠道")
        self.assertEqual(
            entry.get("dropped_hops"),
            GEMINI_HOPS[3:],
            "被 CHAIN_CAP 裁掉的四跳要留痕，方便查「为什么没走 3.5」",
        )
        self.assertEqual(
            {i.split(":", 1)[-1] for i in entry.get("legacy_ids") or []},
            set(GEMINI_HOPS),
            "裁掉的跳仍要留在 legacy_ids：老会话点名 ais-gemini-3.5-flash 不能 404",
        )

    def test_hajimi_family_stays_retired(self) -> None:
        """哈基米 3.8 族 2026-11-11 下线：价目表空、名单/优先级/别名都不许再提它。

        渠道本身（HJ_BASE / CHANNEL_BASE / hjm: 前缀）保留，用于把存量配置里的
        hjm: 条目按缺价安全剔除；被删的是模型：没有价，任何 id 都进不了模型表。
        """
        self.assertEqual(ma.HJ_PRICES, {}, "HJ 价目表必须为空，否则整族会被重新收录")
        self.assertFalse(
            [e for e in ma.MAIN_ORDER if "hjm:" in e],
            "主力名单不该再点名哈基米跳",
        )
        self.assertFalse(
            [u for u in ma.HOP_PRIORITY if u.startswith("[")],
            "HOP_PRIORITY 只服务 GM 的 ais-* 跳，不该留售卖站前缀的键",
        )
        self.assertNotIn("Gemini-3.8-Flash", set(ma.ABBR.values()))

    def test_hop_priority_covers_every_ais_hop(self) -> None:
        # 漏一个就回落到默认 99，会被 3.5 之类的字符串序顶到前面。
        self.assertEqual(
            {upstream for upstream in ma.HOP_PRIORITY if upstream.startswith("ais-gemini")},
            set(GEMINI_HOPS),
        )
        ordered = sorted(ma.HOP_PRIORITY, key=lambda u: ma.HOP_PRIORITY[u])
        self.assertEqual(
            [u for u in ordered if u.startswith("ais-gemini")],
            GEMINI_HOPS,
            "AIS 这条链的跳序",
        )
        self.assertGreater(
            ma.HOP_PRIORITY_DEFAULT,
            max(ma.HOP_PRIORITY.values()),
            "默认值必须大于所有显式优先级，其它渠道的顺序才不会被改",
        )

    def test_non_gemini_hops_keep_default_priority(self) -> None:
        main, oc = _chains(0.11)
        for chain in (main, oc):
            order = [ma.HOP_PRIORITY.get(h["upstream"], ma.HOP_PRIORITY_DEFAULT) for h in chain]
            self.assertEqual(set(order), {ma.HOP_PRIORITY_DEFAULT}, "非 GM 跳一律取默认优先级")

    @unittest.skipUnless(ALIAS_MAP.exists(), "本机没有 alias map，跳过磁盘守卫")
    def test_on_disk_alias_map_keeps_gemini_ais_three_hops(self) -> None:
        data = json.loads(ALIAS_MAP.read_text(encoding="utf-8"))
        models = data.get("models") or {}
        ais = models.get("Gemini-AIS") or {}
        self.assertEqual(
            [h.get("channel") for h in ais.get("chain") or []],
            ["GM"] * 3,
            "磁盘上 Gemini-AIS 是 3 跳纯 GM（CHAIN_CAP）",
        )
        self.assertNotIn(
            "Gemini-3.8-Flash", models,
            "已下线的哈基米 3.8 族不该还留在磁盘 alias map 里",
        )


if __name__ == "__main__":
    unittest.main()
