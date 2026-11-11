#!/usr/bin/env python3
"""探活摘除策略回归：一次探测失败不等于型号下架。

两个真实事故同时锁在这里：

1. 2026-11-10 12:00 zgate 部署重启打断在途探测，beam-free / conatus-free 记成
   error、claude-haiku-5-5 的 403 被写成 unavailable，ever_ok=true 的型号被删。
2. 2026-11-11 每日同步：Gemini-AIS 一次 45s 超时（ever_ok 为空）被摘出
   provider_config，DSH 侧 zcode-main 的清单是这份配置投影出来的，缺型号不降级
   而是硬失败（pi-ai: provider "zcode-main" has no configured model
   "Gemini-AIS"），用户整场会话卡在报错上。

判据：除「上游明确说没有这个型号」(unavailable 且非 403) 之外，任何状态都不得
删模型；主力组成员连 unavailable 之外的一切非 ok 都只报不删。

跑法：`python -m unittest discover -s tests -v`
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
sys.modules.setdefault("model_alias", ma)
spec.loader.exec_module(ma)


def row(name: str, upstream: str = "ais-gemini-3.8-flash", *,
        channel: str = "GM", legacy: list[str] | None = None) -> dict:
    return {
        "new_id": name,
        "raw": f"gem:{upstream}" if channel == "GM" else upstream,
        "abbr": name,
        "name": name,
        "protocol": "chat",
        "price": 0.11,
        "chain": [{"channel": channel, "upstream": upstream,
                   "original": upstream, "protocol": "chat", "price": 0.11}],
        "legacy_ids": legacy or [upstream],
    }


def grouped(**groups: list[dict]) -> dict[str, list[dict]]:
    out = {"main": [], "free": [], "low": []}
    out.update(groups)
    return out


class ProbeFilterTest(unittest.TestCase):
    def _run(self, g, probe, existing=None, legacy=None):
        skipped: list[str] = []
        kept, suspect = ma.apply_probe_filter(
            g, probe, existing or {}, legacy or {}, skipped)
        return g, kept, suspect, skipped

    def test_timeout_without_ever_ok_keeps_main_model(self):
        """事故 2 的最小复现：主力组 timeout + ever_ok 缺省 → 必须保留。"""
        g = grouped(main=[row("Gemini-AIS")])
        probe = {"gem:ais-gemini-3.8-flash": {"status": "timeout", "http": None, "ms": 45007}}
        out, kept, suspect, skipped = self._run(g, probe)
        self.assertEqual([r["new_id"] for r in out["main"]], ["Gemini-AIS"])
        self.assertIn("Gemini-AIS", " ".join(suspect), "主力组必须留下待核实记录")
        self.assertEqual(skipped, [])

    def test_timeout_without_ever_ok_still_drops_non_main(self):
        """非主力组维持原语义：超时且从未 ok，说明它本来就没成功过。"""
        g = grouped(low=[row("MiMo-2.6-Pro", "mimo-v2.6-pro", channel="OC")])
        probe = {"mimo-v2.6-pro": {"status": "timeout"}}
        out, kept, suspect, skipped = self._run(g, probe)
        self.assertEqual(out["low"], [])
        self.assertEqual(len(skipped), 1)

    def test_error_keeps_model_without_ever_ok(self):
        """事故 1：网络层失败连 HTTP 码都没有，连非主力组也不能删。"""
        g = grouped(free=[row("Beam", "beam-free", channel="OC")])
        probe = {"beam-free": {"status": "error", "ever_ok": False}}
        out, _, _, skipped = self._run(g, probe)
        self.assertEqual([r["new_id"] for r in out["free"]], ["Beam"])
        self.assertEqual(skipped, [])

    def test_403_unavailable_is_blocked_not_removed(self):
        """事故 1：403 被写成 unavailable 时按地区拒绝处理，不判死。"""
        # blocked 是瞬时限流集合的一员，历史账本不会写 ever_ok，这里复刻原样。
        g = grouped(free=[row("Conatus", "qn:qiniu/conatus-free", channel="QN")])
        probe = {"qn:qiniu/conatus-free": {"status": "unavailable", "http": 403}}
        out, _, suspect, skipped = self._run(g, probe)
        self.assertEqual([r["new_id"] for r in out["free"]], [], "无 ever_ok 的 blocked 照旧摘除")
        self.assertEqual(len(skipped), 1, "403 只能改判 blocked 后再判，不能直接按 unavailable 判死")
        self.assertEqual(out["free"], [], "没有 ever_ok 的 blocked 仍按原语义摘除")

        g2 = grouped(free=[row("Conatus", "qn:qiniu/conatus-free", channel="QN")])
        probe2 = {"qn:qiniu/conatus-free": {"status": "blocked", "http": 403, "ever_ok": True}}
        out2, _, _, _ = self._run(g2, probe2)
        self.assertEqual([r["new_id"] for r in out2["free"]], ["Conatus"])

    def test_upstream_says_gone_removes_non_main(self):
        """真下架（unavailable 且不是 403）仍然照删 —— 策略不能被改成「永不删」。"""
        g = grouped(free=[row("Kimi", "qn:moonshotai/kimi-k3-free", channel="QN")])
        probe = {"qn:moonshotai/kimi-k3-free": {"status": "unavailable", "http": 404}}
        out, _, _, skipped = self._run(g, probe)
        self.assertEqual(out["free"], [])
        self.assertEqual(len(skipped), 1)

    def test_upstream_says_gone_keeps_main_and_flags(self):
        """主力组连 404 也只报不删：选择器里正被点名的模型不能由脚本默默抽走。"""
        g = grouped(main=[row("Gemini-AIS")])
        probe = {"gem:ais-gemini-3.8-flash": {"status": "unavailable", "http": 404}}
        out, _, suspect, _ = self._run(g, probe)
        self.assertEqual([r["new_id"] for r in out["main"]], ["Gemini-AIS"])
        self.assertEqual(len(suspect), 1)

    def test_transient_with_ever_ok_always_kept(self):
        """曾经成功过的型号，遇到瞬时限流/排队一律保留。"""
        g = grouped(low=[row("Qwen", "qoder:Qwen3.8-Flash", channel="QD")])
        probe = {"qoder:Qwen3.8-Flash": {"status": "rate_limited", "ever_ok": True}}
        out, _, _, _ = self._run(g, probe)
        self.assertEqual([r["new_id"] for r in out["low"]], ["Qwen"])

    def test_missing_probe_entry_keeps_existing_model(self):
        """本轮新补进配置、还没来得及探的型号，按上一版配置保留。"""
        r = row("Gemini-AIS")
        g = grouped(main=[r])
        out, kept, _, skipped = self._run(g, {}, existing={"Gemini-AIS": r})
        self.assertEqual(len(out["main"]), 1)
        self.assertEqual(len(kept), 1)

    def test_probe_matches_legacy_id(self):
        """探测账本用的是 original（gem:ais-…），用 legacy 反查必须也能命中。"""
        g = grouped(main=[row("Gemini-AIS")])
        probe = {"gem:ais-gemini-3.7-flash": {"status": "ok"}}
        out, _, suspect, _ = self._run(
            g, probe, legacy={"gem:ais-gemini-3.7-flash": "Gemini-AIS"})
        self.assertEqual(len(out["main"]), 1)
        self.assertEqual(suspect, [])


class ChainCapTest(unittest.TestCase):
    def test_ais_chain_capped_at_three(self):
        """用户 2026-11-11 口径「能 3.8 就 3.8」：AIS 链最多 3 跳。"""
        self.assertEqual(ma.CHAIN_CAP.get("Gemini-AIS"), 3)

    def test_all_ais_hops_have_price(self):
        """GM 只认显式价，漏收录的跳会被 family_entries 静默丢掉。"""
        for upstream in ("ais-gemini-3.8-flash", "ais-gemini-3.7-flash",
                         "ais-gemini-3.6-flash", "ais-gemini-3.5-flash",
                         "ais-gemini-3.5-flash-lite", "ais-gemini-3.1-flash-lite",
                         "ais-gemini-3-flash-preview"):
            self.assertIsNotNone(ma.GM_PRICES.get(upstream), upstream)


if __name__ == "__main__":
    unittest.main()
