#!/usr/bin/env python3
"""Go 体检遇到「地区受限 403」必须换机场复测，不能直接判模型死亡。

回归背景（2026-11-02、2026-11-03 两次复现）：`go_model_sync.py` 的体检自己发
HTTPS 请求、不经过 zgate，于是路由器的「机场孪生跳」帮不到它 —— `Beam` /
`GPT-6-Luna` / `Muse-Spark1.3` 直连 403 后被判「上游不可用」删掉，客户端里直接消失。
修法：`probe_detail()` 认出地区标记后用 `AIRPORT_PROXY` 复测一次，只有机场也不通
才把失败交给 `stale_reason`。机制见 docs/PITFALLS.md §35。

跑法：`python -m unittest discover -s tests -v`
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

SPEC = importlib.util.spec_from_file_location(
    "go_model_sync", REPO / "providers" / "opencode-go" / "ops" / "go_model_sync.py"
)
G = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(G)  # type: ignore[union-attr]

REGION_403 = (
    403,
    '{"type":"error","error":{"type":"RegionError","message":"This model is not available in your country"}}',
)
OK_200 = (200, '{"id":"msg_1","content":[{"type":"text","text":"hi"}]}')
PLAIN_403 = (403, '{"error":{"message":"forbidden"}}')


class RegionBlockedTest(unittest.TestCase):
    def test_markers_match_zgate(self):
        for body in (
            '{"error":{"code":"unsupported_country_region_territory"}}',
            '{"type":"error","error":{"type":"RegionError"}}',
            '{"message":"This model is not available in your country"}',
            '{"message":"Country, region, or territory not supported"}',
        ):
            self.assertTrue(G.region_blocked(403, body), body)

    def test_plain_403_and_other_status_are_not_region(self):
        self.assertFalse(G.region_blocked(403, '{"error":"forbidden"}'))
        self.assertFalse(G.region_blocked(400, '{"error":"bad request"}'))
        self.assertFalse(G.region_blocked(500, "unsupported_country_region_territory"))


class ProbeAirportFallbackTest(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.saved = (G.probe_once, G.AIRPORT_PROXY, set(G.AIRPORT_MODELS))
        G.AIRPORT_PROXY = "http://10.0.0.1:7896"
        G.AIRPORT_MODELS = set()

    def tearDown(self):
        G.probe_once, G.AIRPORT_PROXY, airport = self.saved
        G.AIRPORT_MODELS = airport

    def fake(self, direct, via_airport):
        def probe_once(model, protocol, thinking=True, proxy=None):
            self.calls.append(proxy)
            return via_airport if proxy else direct
        G.probe_once = probe_once

    def test_region_403_retries_through_airport(self):
        self.fake(REGION_403, OK_200)
        st, kind, _ = G.probe_detail("beam-free", "messages", thinking=False)
        self.assertEqual((st, kind), (200, "ok"))
        self.assertEqual(self.calls, [None, "http://10.0.0.1:7896"])
        self.assertIn("beam-free", G.AIRPORT_MODELS)

    def test_airport_failure_keeps_model_dead(self):
        self.fake(REGION_403, REGION_403)
        st, kind, _ = G.probe_detail("beam-free", "messages", thinking=False)
        self.assertEqual(kind, "error")
        self.assertNotIn("beam-free", G.AIRPORT_MODELS)

    def test_non_region_error_never_touches_airport(self):
        self.fake(PLAIN_403, OK_200)
        st, kind, _ = G.probe_detail("some-model", "chat/completions", thinking=False)
        self.assertEqual(kind, "error")
        self.assertEqual(self.calls, [None])

    def test_direct_success_never_touches_airport(self):
        self.fake(OK_200, OK_200)
        st, kind, _ = G.probe_detail("m", "chat/completions", thinking=False)
        self.assertEqual((st, kind), (200, "ok"))
        self.assertEqual(self.calls, [None])

    def test_region_blocked_still_listed_is_kept(self):
        """地区受限是出口属性，不是模型状态。

        只要模型还在上游清单里就必须保留：同一个模型从中国 IP 直连 403、
        换机场出口 200，机场节点自己会漂，用单次探测决定去留会造成 churn。
        2026-11-02 / 11-03 / 11-04 各有一次「误删 → 下一轮又加回」。
        """
        why = G.stale_reason(
            "beam-free", REGION_403[0], "error", REGION_403[1], {}, {"beam-free"}, {}
        )
        self.assertIsNone(why, "还在实时清单里的地区受限模型不该被判死")

    def test_region_blocked_in_doc_list_only_is_kept(self):
        """只在文档模型清单里出现，同样算「上游还有」，保留。"""
        why = G.stale_reason(
            "beam-free", REGION_403[0], "error", REGION_403[1], {}, set(), {"beam-free"}
        )
        self.assertIsNone(why)

    def test_region_blocked_gone_from_catalog_is_removed(self):
        """两边清单都没有了才算真删，理由要写明地区受限且已不在清单。"""
        why = G.stale_reason(
            "beam-free", REGION_403[0], "error", REGION_403[1], {}, set(), set()
        )
        self.assertIsNotNone(why)
        self.assertIn("地区受限", why)
        self.assertIn("已不在上游清单", why)


if __name__ == "__main__":
    unittest.main()
