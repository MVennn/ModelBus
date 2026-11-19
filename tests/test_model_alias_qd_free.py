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
        # 渠道级隐藏开关：OC 被 hide 时，alias chain 里的 OC 跳会被移除，
        # 依赖「OC 付费兜底跳存在」的断言必须先让路（否则与本轮新语义冲突）。
        hidden_path = Path(os.path.expanduser("~/.zcode/v2/model-hidden.json"))
        try:
            hidden = json.loads(hidden_path.read_text(encoding="utf-8"))
            chans = hidden.get("channels") if isinstance(hidden, dict) else {}
            self.hidden_channels = {str(k).upper() for k, v in (chans or {}).items()
                                    if v is not False}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            self.hidden_channels = set()

    def test_qw_leads_and_qd_follows(self) -> None:
        """链首必须是 QW（千问官方预付额度），QD 只能跟在后面。

        2026-11-19 实测：QD 只在 08:58-09:15 / 20:58-21:15 / 21:58-22:15 三个窗口内
        真能回包，窗口外排队 90s 起（403/10605 isQueued），等它期间网关已经给客户端
        交了 200 空正文，QW 兜底轮不到。QW 是每模型 1M tokens 试用池（边际单价 0）
        且秒回，所以见 QW_FIRST_MODELS。
        """
        entry = self.models.get("Qwen-3.8-Flash")
        if entry is None:
            self.skipTest("当前配置没有 Qwen-3.8-Flash")
        chain = entry.get("chain") or []
        self.assertTrue(chain, "Qwen-3.8-Flash 链为空")
        head = chain[0]
        self.assertEqual(head.get("channel"), "QW", f"链首不是 QW：{head}")
        self.assertEqual(head.get("protocol"), "messages", f"QW 跳必须是 messages：{head}")
        self.assertEqual(head.get("price"), 0.0, f"QW 跳在预付额度内应记 0 价：{head}")
        self.assertTrue(
            any(hop.get("channel") == "QD" for hop in chain),
            f"QW 之后没有 QD 兜底跳：{chain}",
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
