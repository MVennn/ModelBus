#!/usr/bin/env python3
"""退役型号过滤回归（2026-11-16 审计）。

WorkBuddy 的 retired.json 是「目录删了但接口还能调」型号的唯一退役出口。
本测试锁三道防线，防止像 2026-11-16 那样漏掉命名空间变体：

1. model_probe.retired_keys / is_retired 按裸名归一化 —— 名单写 cn:hy3，
   探测缓存里的 global:hy3 / 裸 hy3 也要能剔掉（实测曾漏 4 条）。
2. 名单缺失 / 损坏时 is_retired 一律返回 False —— 只做减法，不能因坏文件
   清空整份缓存。
3. model_alias.wb_prices 对 price cache 里的退役行做二次过滤 —— 白名单
   补建候选时不会复活已下线型号。

跑法：`python -m unittest discover -s tests -v`
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


mp = _load("model_probe_rt", "tools/model_probe.py")
ma = _load("model_alias_rt", "tools/model_alias.py")


class RetiredProbeFilterTest(unittest.TestCase):
    def test_normalized_keys_cover_namespaces(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "retired.json"
            f.write_text(json.dumps({"retired": {"cn:hy3": "下线", "cn:hy4free": "限免结束"}}), encoding="utf-8")
            keys = mp.retired_keys(f)
            self.assertIn("cn:hy3", keys)
            self.assertIn("hy3", keys)
            for variant in ("cn:hy3", "global:hy3", "hy3", "WB:HY3"):
                self.assertTrue(mp.is_retired(variant, keys), variant)
            self.assertTrue(mp.is_retired("global:hy4free", keys))
            self.assertFalse(mp.is_retired("cn:hy4flash-free", keys))  # 在架限免档

    def test_missing_or_broken_file_is_noop(self) -> None:
        self.assertEqual(mp.retired_keys(Path("/no/such/retired.json")), set())
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "broken.json"
            f.write_text("{bad json", encoding="utf-8")
            self.assertEqual(mp.retired_keys(f), set())
        self.assertFalse(mp.is_retired("cn:hy3", set()))


class WbPricesRetiredTest(unittest.TestCase):
    def test_price_cache_retired_rows_filtered(self) -> None:
        orig_path = ma.WB_PRICING
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / "workbuddy" / "cache").mkdir(parents=True)
            price = base / "workbuddy" / "cache" / "wb_pricing.json"
            price.write_text(json.dumps([
                {"id": "cn:hy3", "credits": "x0.00", "list_rate": 0},
                {"id": "cn:hy4flash-free", "credits": "x0.00", "list_rate": 0},
            ]), encoding="utf-8")
            # retired.json 在 cache 的上一层（parent.parent），保留原路径写法
            retired = base / "workbuddy" / "retired.json"
            retired.write_text(json.dumps({"retired": {"cn:hy3": "下线"}}), encoding="utf-8")
            ma.WB_PRICING = price
            try:
                out = ma.wb_prices()
                self.assertNotIn("cn:hy3", out)
                self.assertIn("cn:hy4flash-free", out)
            finally:
                ma.WB_PRICING = orig_path


if __name__ == "__main__":
    unittest.main()
