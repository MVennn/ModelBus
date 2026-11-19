#!/usr/bin/env python3
"""漂移复查幂等性回归（tools/model_alias.py projected_for_drift）。

背景（2026-11-19 实测）：OC 渠道被列入隐藏名单后，--apply 写 alias 条目会把 OC 跳
摘掉，而 --check 拿未裁剪的重算结果去比，于是每天必报「链路漂移」、每日任务长期
exit 1。这里锁住「比漂移前先按写入端同一套规则裁剪」。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import model_alias as M  # noqa: E402


def hop(channel: str, upstream: str, price: float) -> dict:
    return {"channel": channel, "upstream": upstream, "price": price}


def row(new_id: str, chain: list[dict], price: float, group: str = "省钱") -> dict:
    return {
        "new_id": new_id,
        "chain": chain,
        "price": price,
        "group": group,
        "upstream": chain[0]["upstream"],
        "channel": chain[0]["channel"],
    }


class ProjectedForDriftTest(unittest.TestCase):
    def test_hidden_channel_hop_is_stripped_before_compare(self):
        # 重算结果：WB -> QD -> OC(隐藏)
        grouped = {"low": [row("GLM-5.3-Flash", [
            hop("WB", "cn:glm-5.3-flash", 0.08),
            hop("QD", "GLM-5.3-Flash", 0.09),
            hop("OC", "glm-5.3-flash", 0.1),
        ], 0.08)]}
        # 磁盘上写的就是裁掉 OC 之后的两跳
        existing = {"GLM-5.3-Flash": {
            "group": "省钱",
            "price": 0.08,
            "chain": [
                hop("WB", "cn:glm-5.3-flash", 0.08),
                hop("QD", "GLM-5.3-Flash", 0.09),
            ],
        }}
        raw = M.drift_report(grouped, existing)
        self.assertTrue(raw["chain_changed"], "未裁剪时应复现旧 bug，否则这条测试失去意义")

        drift = M.drift_report(M.projected_for_drift(grouped, {"OC"}), existing)
        self.assertFalse(any(drift.values()), drift)

    def test_pure_hidden_channel_row_disappears_from_drift(self):
        # 整条只有一个隐藏渠道的跳：写入端整条不写，比漂移时也该当成不存在
        grouped = {"low": [
            row("GLM-5.3-Flash", [hop("WB", "cn:glm-5.3-flash", 0.08)], 0.08),
            row("Claude-Haiku-5.5", [hop("OC", "claude-haiku-5.5", 0.2)], 0.2),
        ]}
        existing = {"GLM-5.3-Flash": {
            "group": "省钱", "price": 0.08,
            "chain": [hop("WB", "cn:glm-5.3-flash", 0.08)],
        }}
        projected = M.projected_for_drift(grouped, {"OC"})
        self.assertEqual([r["new_id"] for r in projected["low"]], ["GLM-5.3-Flash"])

        drift = M.drift_report(M.projected_for_drift(grouped, {"OC"}), existing)
        self.assertFalse(any(drift.values()), drift)

    def test_no_hidden_channel_is_identity(self):
        grouped = {"low": [row("GLM-5.3-Flash", [hop("OC", "glm-5.3-flash", 0.1)], 0.1)]}
        self.assertIs(M.projected_for_drift(grouped, set()), grouped)

    def test_price_follows_first_remaining_hop(self):
        # 头字段换成过滤后第一跳：WB 被隐藏后 price 应取 QD 那条
        grouped = {"low": [row("X", [
            hop("WB", "cn:x", 0.01),
            hop("QD", "X", 0.5),
        ], 0.01)]}
        projected = M.projected_for_drift(grouped, {"WB"})["low"][0]
        self.assertEqual(projected["price"], 0.5)
        self.assertEqual([h["channel"] for h in projected["chain"]], ["QD"])


if __name__ == "__main__":
    unittest.main()
