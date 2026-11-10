#!/usr/bin/env python3
"""模型清单的价格必须每次从源重算，不能继承上一版 alias map。

回归背景（2026-10-28）：`expand_hops()` 曾把 alias map 里 chain 的 price
原样带回，`family_entries()` 又优先用 `item["price"]`，于是上游改价永远不生效。
WorkBuddy 的 Step-5-Pre 限免在 10-25 结束后实际已按 x0.33 计费，配置里却一直
挂在「免费 @0.00」，直到有人手点模型才发现。

跑法：`python -m unittest discover -s tests -v`
"""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import model_alias as M  # noqa: E402


def wb_record(list_rate: float, eff_rate: float | None = None) -> dict:
    return {
        "list": list_rate,
        "eff": list_rate if eff_rate is None else eff_rate,
        "label": "",
    }


def chain_item(*hops: tuple[str, str, float]) -> dict:
    """构造一条已存在的 alias 链路（带旧价格）。"""
    base = {"WB": M.WB_BASE, "OC": M.OC_BASE, "QD": M.QD_BASE}
    upstream = hops[0][1]
    return {
        "channel": hops[0][0],
        "upstream": upstream,
        "base_model": upstream.split(":", 1)[-1],
        "original": upstream,
        "protocol": "chat",
        "fallbacks": [],
        "legacy_ids": [upstream],
        "chain": [
            {
                "channel": channel,
                "upstream": up,
                "base": base[channel],
                "price": old_price,
                "original": up,
                "base_model": up.split(":", 1)[-1],
            }
            for channel, up, old_price in hops
        ],
    }


class PriceIsDerivedTest(unittest.TestCase):
    def test_chain_price_is_not_inherited(self):
        """存着 0.0，源里是 0.33 —— 结果必须是 0.33。"""
        item = chain_item(("WB", "cn:step-5-preview", 0.0))
        hops = M.expand_hops(item)
        self.assertTrue(all(h["price"] is None for h in hops))

        entries = M.family_entries(hops, {"cn:step-5-preview": wb_record(0.33)}, {}, "auto")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["price"], 0.33)
        self.assertEqual(entries[0]["chain"][0]["price"], 0.33)

    def test_price_drop_is_picked_up(self):
        """涨价要跟上，降价也要跟上（MiMo-2.6-Pro 0.18 -> 0.13）。"""
        item = chain_item(
            ("WB", "cn:mimo-v2.6-pro", 0.18),
            ("OC", "mimo-v2.6-pro", 0.18),
        )
        entries = M.family_entries(
            M.expand_hops(item), {"cn:mimo-v2.6-pro": wb_record(0.13)}, {}, "auto",
        )
        self.assertEqual(entries[0]["price"], 0.13)
        # OC 直连跳链尾会自动补「同上游、经机场」的孪生跳（2026-10-30 起，
        # with_airport_fallback），孪生跳带 proxy、直连跳不带。
        self.assertEqual([h["upstream"] for h in entries[0]["chain"]],
                         ["cn:mimo-v2.6-pro", "mimo-v2.6-pro", "mimo-v2.6-pro"])
        self.assertEqual(entries[0]["chain"][1].get("proxy", ""), "")
        self.assertEqual(entries[0]["chain"][2].get("proxy"), M.AIRPORT_PROXY)

    def test_dead_hop_is_dropped(self):
        """源里已经没有这个上游（下架/账号封禁）→ 该跳消失，不靠旧价赖着。"""
        item = chain_item(
            ("WB", "cn:step-5-preview", 0.0),
            ("OC", "step-5-preview", 0.0),
        )
        entries = M.family_entries(
            M.expand_hops(item), {"cn:step-5-preview": wb_record(0.33)}, {}, "auto"
        )
        self.assertEqual(len(entries), 1)
        self.assertEqual([h["upstream"] for h in entries[0]["chain"]],
                         ["cn:step-5-preview"])

    def test_fully_dead_chain_is_skipped(self):
        item = chain_item(("WB", "cn:gone-model", 0.0))
        self.assertEqual(M.family_entries(M.expand_hops(item), {}, {}, "auto"), [])

    def test_free_promo_expiry_drops_unlisted_model(self):
        """限免到期：价格从 0 变 0.33，又不在 MAIN_IDS / LOW_PICKS 里 -> 不收录。"""
        item = chain_item(("WB", "cn:step-5-preview", 0.0))
        entries = M.family_entries(
            M.expand_hops(item), {"cn:step-5-preview": wb_record(0.33)}, {}, "auto"
        )
        self.assertEqual(M.entry_group(entries[0], {}), ("drop", ""))

    def test_group_rules(self):
        """主力看名单（豁免价格），省钱要同时命中名单与 0.11 上限，其余不收录。"""
        def entry_for(upstream: str, price: float) -> dict:
            item = chain_item(("WB", upstream, 0.0))
            built = M.family_entries(
                M.expand_hops(item), {upstream: wb_record(price)}, {}, "auto"
            )[0]
            return dict(built, price=price)

        # 主力看名单：名单里的型号即使 0.43 也进主力（豁免价格上限）。
        # 11-10 主力收敛后名单只剩 DeepSeek 三跳 + gem:ais-gemini-3.8-flash，
        # 这里用三跳里的 cn:deepseek-v4.1-flash 做样本。
        self.assertEqual(M.entry_group(entry_for("cn:deepseek-v4.1-flash", 0.43), {}), ("main", "manual"))
        # 名单里的便宜模型 -> 省钱
        self.assertEqual(M.entry_group(entry_for("cn:glm-5.3-flash", 0.08), {}), ("low", ""))
        # 不在名单的贵模型 -> 不收录
        self.assertEqual(M.entry_group(entry_for("cn:glm-5.3", 0.69), {}), ("drop", ""))
        # 免费模型永远进免费组，不受名单影响
        self.assertEqual(M.entry_group(entry_for("cn:some-free", 0.0), {}), ("free", ""))


class AutoLowTest(unittest.TestCase):
    """省钱组的自动补位（2026-11-02）：新厂商 / 新一代进组，同代兄弟与老型号不进。

    规则见 `pick_auto_low`：价格 ≤ LOW_MAX，且该厂商还没有代表、或版本号高于现有代表。
    """

    def _entry(self, upstream: str, price: float) -> dict:
        item = chain_item(("WB", upstream, 0.0))
        built = M.family_entries(
            M.expand_hops(item), {upstream: wb_record(price)}, {}, "auto"
        )[0]
        return dict(built, price=price)

    def test_new_vendor_is_picked(self):
        """名单里没有的厂商（MUSE），价格在省钱档 -> 自动进省钱组。"""
        entry = self._entry("cn:muse-spark-1.3-contributor", 0.04)
        picked = M.pick_auto_low([entry], {})
        self.assertIn(id(entry), picked)
        self.assertEqual(M.entry_group(entry, {}, picked), ("low", "auto"))

    def test_only_newest_per_vendor(self):
        """同一家两个版本：只收版本高的那个。"""
        old = self._entry("cn:muse-spark-1.2-contributor", 0.04)
        new = self._entry("cn:muse-spark-1.3-contributor", 0.04)
        picked = M.pick_auto_low([old, new], {})
        self.assertIn(id(new), picked)
        self.assertNotIn(id(old), picked)

    def test_same_generation_sibling_is_not_picked(self):
        """腾讯已有 HY3-X（3 代），同代的 HY3 不该因为便宜就混进组。"""
        incumbent = self._entry("cn:hy3-x", 0.05)
        sibling = self._entry("cn:hy3", 0.11)
        picked = M.pick_auto_low([incumbent, sibling], {})
        self.assertNotIn(id(sibling), picked)
        self.assertEqual(M.entry_group(sibling, {}, picked), ("drop", ""))

    def test_newer_generation_is_picked(self):
        """这家出了新一代（HY4 > HY3-X 的 3 代）-> 收录。"""
        incumbent = self._entry("cn:hy3-x", 0.05)
        newer = self._entry("cn:hy4-preview-f", 0.05)
        picked = M.pick_auto_low([incumbent, newer], {})
        self.assertIn(id(newer), picked)

    def test_over_budget_is_never_picked(self):
        """超过省钱档（0.22）的模型，哪怕厂商没代表也不自动收录。"""
        entry = self._entry("cn:longcat-2.0", 0.22)
        self.assertEqual(M.pick_auto_low([entry], {}), set())


class DriftCheckTest(unittest.TestCase):
    def _grouped(self, price: float) -> dict:
        entry = M.family_entries(
            M.expand_hops(chain_item(("WB", "cn:step-5-preview", 0.0))),
            {"cn:step-5-preview": wb_record(price)}, {}, "auto",
        )[0]
        entry = dict(entry)
        entry["new_id"] = "Step-5-Pre"
        entry["price"] = price
        return {"high": [entry]}

    def test_price_drift_is_reported(self):
        existing = {
            "Step-5-Pre": {
                "group": "免费",
                "price": 0.0,
                "chain": [{"channel": "WB", "upstream": "cn:step-5-preview", "price": 0.0}],
            }
        }
        drift = M.drift_report(self._grouped(0.33), existing)
        self.assertEqual(drift["price_changed"], [("Step-5-Pre", 0.0, 0.33)])
        self.assertEqual(drift["group_changed"], [("Step-5-Pre", "免费", "高耗")])

    def test_no_drift_after_apply(self):
        existing = {
            "Step-5-Pre": {
                "group": "高耗",
                "price": 0.33,
                "chain": [{"channel": "WB", "upstream": "cn:step-5-preview", "price": 0.33}],
            }
        }
        drift = M.drift_report(self._grouped(0.33), existing)
        self.assertFalse(any(drift.values()), drift)


class ProbeFreshnessTest(unittest.TestCase):
    def test_stale_probe_entries_are_dropped(self):
        fresh_at = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
        stale_at = (datetime.now() - timedelta(days=8)).strftime("%Y-%m-%dT%H:%M:%S")
        probe = {
            "cn:fresh": {"status": "ok", "checked_at": fresh_at},
            "cn:stale": {"status": "unavailable", "checked_at": stale_at},
            "cn:no-stamp": {"status": "ok"},
        }
        fresh, stale = M._fresh_probe(probe, 72)
        self.assertEqual(sorted(fresh), ["cn:fresh"])
        self.assertEqual(sorted(stale), ["cn:no-stamp", "cn:stale"])

    def test_ttl_zero_disables_filtering(self):
        probe = {"cn:old": {"status": "ok", "checked_at": "2020-01-01T00:00:00"}}
        fresh, stale = M._fresh_probe(probe, 0)
        self.assertEqual(fresh, probe)
        self.assertEqual(stale, [])


if __name__ == "__main__":
    unittest.main()
