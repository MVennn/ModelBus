#!/usr/bin/env python3
"""Go 同步只认上游清单：不发探测请求，协议从 /models 的 api 字段取。

回归背景：体检过去靠 `probe_detail()` 对每个已配置模型发一次真实请求来决定去留。
但探测结果被出口影响——同一个模型中国 IP 直连 403、换机场出口 200，机场节点
自己会漂。于是 `Beam`(beam-free) 在 2026-11-02 / 11-03 / 11-04 各走了一轮
「误删 → 下一轮又加回」。

现在的契约（用户口径：opencode 删掉了才算删，没删就是没删）：
  * `stale_reason()` 只认两件事：官方弃用日已过、实时清单与 Go 文档表里都没有了；
  * 协议来自 `/models` 每条记录的 `api` 字段（协议名 -> 接入参数），
    没有任何受支持协议的直接跳过，而不是靠试出来。

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


class StaleReasonTest(unittest.TestCase):
    """去留判定：纯清单，不碰网络。"""

    def test_listed_in_live_is_kept(self):
        self.assertIsNone(G.stale_reason("beam-free", {}, {"beam-free"}, set()))

    def test_listed_only_in_go_docs_is_kept(self):
        """文档还挂着但实时清单暂时没有 —— 也算上游还有，保留。"""
        self.assertIsNone(G.stale_reason("beam-free", {}, set(), {"beam-free"}))

    def test_gone_from_every_list_is_removed(self):
        why = G.stale_reason("beam-free", {}, set(), set())
        self.assertIsNotNone(why)
        self.assertIn("都没有了", why)

    def test_deprecated_date_wins_over_listing(self):
        """弃用日已过就删，哪怕还挂在清单里。"""
        why = G.stale_reason("mimo-v2.5", {"mimo-v2.5": "2026-10-01"},
                             {"mimo-v2.5"}, {"mimo-v2.5"})
        self.assertIsNotNone(why)
        self.assertIn("弃用日", why)

    def test_signature_takes_no_probe_state(self):
        """签名里不能再有 status / kind / raw —— 那是探测时代的入参。"""
        import inspect
        params = list(inspect.signature(G.stale_reason).parameters)
        self.assertEqual(params, ["model", "deprecated_dates", "live", "hint"])


class DeclaredProtocolsTest(unittest.TestCase):
    """协议从 /models 的 api 字段解析。"""

    def test_maps_short_names_to_paths(self):
        models = [
            {"id": "a", "api": {"chat-completions": {}, "messages": {}}},
            {"id": "b", "api": {"messages": {}}},
            {"id": "c", "api": {"responses": {}}},
        ]
        protos, unsupported = G.declared_protocols(models)
        self.assertEqual(protos["a"], ["chat/completions", "messages"])
        self.assertEqual(protos["b"], ["messages"])
        self.assertEqual(protos["c"], ["responses"])
        self.assertEqual(unsupported, {})

    def test_order_follows_PROTOCOLS(self):
        """多协议时要按 PROTOCOLS 的固定顺序，避免同一模型每天换协议。"""
        protos, _ = G.declared_protocols(
            [{"id": "x", "api": {"messages": {}, "chat-completions": {}}}]
        )
        self.assertEqual(protos["x"], list(G.PROTOCOLS[:2]))

    def test_only_unsupported_protocol_is_recorded(self):
        """gemini-4-argon 只提供 generate-content，本客户端用不了，必须单独记下。"""
        protos, unsupported = G.declared_protocols(
            [{"id": "gemini-4-argon", "api": {"generate-content": {}}}]
        )
        self.assertNotIn("gemini-4-argon", protos)
        self.assertEqual(unsupported["gemini-4-argon"], ["generate-content"])

    def test_no_api_field_is_neither_listed_nor_unsupported(self):
        """缺 api 字段的模型交给上层兜底，不要误判成不支持。"""
        protos, unsupported = G.declared_protocols([{"id": "y"}])
        self.assertEqual(protos, {})
        self.assertEqual(unsupported, {})


class NoProbeLeftTest(unittest.TestCase):
    """探测层必须已经从模块里消失。"""

    def test_probe_helpers_are_gone(self):
        for name in ("probe_once", "probe_detail", "probe_protocols", "probe_headers",
                     "probe_body", "region_blocked", "upstream_message",
                     "AIRPORT_PROXY", "AIRPORT_MODELS"):
            self.assertFalse(hasattr(G, name), "%s 应该已被删除" % name)


if __name__ == "__main__":
    unittest.main()
