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

    def test_free_1017_splits_without_polluting_main(self):
        # 免费版 V4.1-Flash-1017（oc:deepseek-v4.1-flash-free）必须与付费主力
        # DeepSeek-4.1-Flash 分成两条：否则 MERGE_FREE_GB 把 price=0 的跳并进主力，
        # 主力价格 0.11 会被改成 0、链路被改写到免费端点（--check 漂移）。
        items = [
            _hop("WB", "cn:deepseek-v4.1-flash", 0.11),
            _hop("OC", "deepseek-v4.1-flash", 0.11, base_model="deepseek-v4.1-flash"),
            _hop("OC", "deepseek-v4.1-flash-free", 0.00, base_model="deepseek-v4.1-flash-free"),
        ]
        entries = ma.family_entries(items, {}, {}, "auto")
        main = [e for e in entries if e["name"] == "DeepSeek-4.1-Flash"]
        free = [e for e in entries if e["name"] == "DeepSeek-4.1-Flash-Free"]
        self.assertEqual(len(main), 1, f"主力应恰好一条，实际 {len(main)}")
        self.assertEqual(len(free), 1, f"免费档应自成一族恰好一条，实际 {len(free)}")
        self.assertEqual(main[0]["price"], 0.11, "主力价格不能被免费档拉到 0")
        self.assertEqual(free[0]["price"], 0.0, "免费档价格必须是 0")
        self.assertNotIn(
            "deepseek-v4.1-flash-free",
            [h["upstream"] for h in main[0]["chain"]],
            "免费 upstream 不能混进主力链",
        )
        # 免费档走本地 Bun 代理 8789（ZEN_FREE_UPSTREAMS 覆盖）。
        self.assertTrue(
            all(h["base"] == ma.ZEN_FREE_BASE for h in free[0]["chain"]),
            "免费档链路 base 必须全部指向 8789 代理",
        )

    def test_zen_free_hops_get_no_airport_twin(self):
        # Zen TUI 免费档的 base 是本机 8789，机场 twin 会让机场去连它自己的
        # 127.0.0.1:8789 → 必 502（big-pickle 就是这样整条链断掉的）。
        # 两道防线都要在：新增时不加（with_airport_fallback），存量 alias map
        # 里已有的 twin 也要滤掉（expand_hops），否则坏跳递归保留、永远摘不掉。
        for upstream in ("big-pickle", "mimo-v2.6-flash-free", "glm-5.3-flash-free"):
            # 防线一：新增
            hops = [_hop("OC", upstream, 0.00)]
            out = ma.with_airport_fallback(hops)
            self.assertEqual(len(out), 1,
                f"{upstream} 不应被加机场 twin，实际 {len(out)} 跳")
            # 防线二：存量 twin 被 expand_hops 滤掉
            stale = {
                "channel": "OC", "upstream": upstream, "protocol": "chat",
                "base_model": upstream, "original": f"oc:{upstream}",
                "chain": [
                    {"channel": "OC", "upstream": upstream, "protocol": "chat",
                     "base_model": upstream},
                    {"channel": "OC", "upstream": upstream, "protocol": "chat",
                     "base_model": upstream, "proxy": ma.AIRPORT_PROXY},
                ],
            }
            expanded = ma.expand_hops(stale)
            self.assertEqual(len(expanded), 1,
                f"{upstream} 存量 twin 应被滤掉，实际 {len(expanded)} 跳")
            self.assertEqual(str(expanded[0].get("proxy") or ""), "",
                f"{upstream} 不应残留 proxy")
        # 普通 OC 型号（非 ZEN_FREE）的机场 twin 是地区受限兜底，不能一起砍掉。
        normal = ma.with_airport_fallback([_hop("OC", "gpt-6-luna", 0.09)])
        self.assertEqual(len(normal), 2, "普通 OC 型号仍要有机场 twin")
        self.assertEqual(str(normal[1].get("proxy") or ""), ma.AIRPORT_PROXY)
        normal_stale = {
            "channel": "OC", "upstream": "gpt-6-luna", "protocol": "chat",
            "base_model": "gpt-6-luna", "original": "oc:gpt-6-luna",
            "chain": [
                {"channel": "OC", "upstream": "gpt-6-luna", "protocol": "chat"},
                {"channel": "OC", "upstream": "gpt-6-luna", "protocol": "chat",
                 "proxy": ma.AIRPORT_PROXY},
            ],
        }
        self.assertEqual(len(ma.expand_hops(normal_stale)), 2,
            "普通 OC 型号的存量 twin 必须保留")

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
