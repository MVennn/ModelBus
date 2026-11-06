#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把竞技榜成绩折算成「智力 / 价格 / 性价比」三个分数，供生成器选型参考。

用法：
    python tools/model_score.py                 # 打印排行（dry run）
    python tools/model_score.py --write         # 写 ~/.zcode/v2/model-scores.json
    python tools/model_score.py --write --quiet # 自动化里用

=== 为什么要它 ===

`docs/BENCHMARKS.md` §5.4 早就定义了三档计算口径，但 `model_alias.py` 里**零引用**：
选型只看人工白名单 + 价格阈值，性能维度从来没进过自动化。结果是「便宜但笨」的
型号只要价格够低就能留在省钱组，而竞技榜上明显更强的型号进不来。

=== 口径（与 BENCHMARKS §5.4 一致，两榜不混算）===

* **智力指数 intel** = score ÷ 基准分 × 100。
  基准优先取「锚定型号」在表里的实测分；表里没有该型号时退回 ArenaGalleri 的
  baseline 字段。**不写死 342.40** —— 那是 AA 基准的旧值，本文件用的是竞技榜基线。
* **价格指数 price_idx** = price ÷ 基准价 × 100。基准价取锚定型号的价格（默认 0.11，
  与 arena 候选文件的 `rule.max_price` 同源），即「和参考型号同样贵 = 100」。
* **性价比 value** = intel ÷ price_idx；免费模型不算性价比（记 null）。

竞技榜原始分（1000 上下）与 AA 总分（342.40）是两套量纲，且覆盖的型号集几乎不重叠，
所以本文件只给「竞技榜内可比」的相对分数，并通过 `basis` 字段写明基准，不冒充 AA 指数。

输出结构（`~/.zcode/v2/model-scores.json`）：

    {
      "version": 1,
      "checked_at": "2026-11-06 22:40:00",
      "basis": {"model": "deepseek-v4.1-flash", "score": 1094, "price": 0.11,
                "source": "arena-main.json"},
      "models": {
        "OC|mimo-v2.6-flash": {"intel": 99.8, "price_idx": 54.5, "value": 1.83,
                              "score": 1092, "price": 0.06, "games": 71,
                              "rank": 65, "provisional": false}
      }
    }

键是 `CHANNEL|upstream`，与生成器的跳（hop）一一对应，不按显示名 —— 显示名会随分组
改、按名字对会在改名当天全部失配。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ARENA = Path.home() / ".zcode" / "v2" / "arena-main.json"
DEFAULT_OUT = Path.home() / ".zcode" / "v2" / "model-scores.json"
BASELINE_MODEL = "deepseek-v4.1-flash"
DEFAULT_BASELINE_PRICE = 0.11


def arena_path(explicit: str | None) -> Path:
    return Path(explicit).expanduser() if explicit else DEFAULT_ARENA


def out_path(explicit: str | None) -> Path:
    return Path(explicit).expanduser() if explicit else DEFAULT_OUT


def load_rows(path: Path) -> dict:
    """读 arena-main.json。候选 + 「接近但未入选」都算 —— 分数对选型有用，
    不因为它没进主力就被丢掉（那批是生成器最需要拿来比的）。"""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except Exception as exc:  # noqa: BLE001
        print(f"warning: 读不了 {path}（{exc}）", file=sys.stderr)
        return {}


def baseline_of(data: dict) -> tuple[str, float, float]:
    """(基准型号, 基准分, 基准价)。基准分优先用表里同名型号的实测分。"""
    base = data.get("baseline") or {}
    model = str(base.get("model") or BASELINE_MODEL)
    price = float((data.get("rule") or {}).get("max_price") or DEFAULT_BASELINE_PRICE)
    score = float(base.get("score") or 0)
    for row in data.get("near") or []:
        if str(row.get("model") or "") == model and row.get("score"):
            score = float(row["score"])
            break
    return model, score, price


def score_rows(data: dict) -> dict:
    base_model, base_score, base_price = baseline_of(data)
    if base_score <= 0 or base_price <= 0:
        return {"basis": {}, "models": {}}

    rows: dict[str, dict] = {}
    for row in list(data.get("candidates") or []) + list(data.get("near") or []):
        channel = str(row.get("channel") or "")
        upstream = str(row.get("upstream") or row.get("model") or "")
        score = float(row.get("score") or 0)
        price = float(row.get("price") or 0)
        if not channel or not upstream or score <= 0:
            continue
        intel = round(score / base_score * 100, 1)
        if price > 0:
            price_idx = round(price / base_price * 100, 1)
            value = round(intel / price_idx, 2) if price_idx else None
        else:
            price_idx = 0.0
            value = None  # 免费模型不算性价比，与 BENCHMARKS §5.4 一致
        key = f"{channel}|{upstream}"
        # 同一跳出现多次（候选 + 近似）时留分高的那条
        if key in rows and rows[key]["score"] >= score:
            continue
        rows[key] = {
            "intel": intel,
            "price_idx": price_idx,
            "value": value,
            "score": score,
            "price": price,
            "games": int(row.get("games") or 0),
            "rank": int(row.get("rank") or 0),
            "provisional": bool(row.get("provisional")),
        }
    basis = {
        "model": base_model,
        "score": base_score,
        "price": base_price,
        "source": "arena-main.json",
    }
    return {"basis": basis, "models": rows}


def render(payload: dict) -> None:
    basis = payload.get("basis") or {}
    rows = payload.get("models") or {}
    if not rows:
        print("没有可用分数（arena-main.json 为空或基准分缺失）")
        return
    print(f"基准：{basis['model']} 分数 {basis['score']:g} / 价格 {basis['price']:g}")
    print(f"{'通道|上游':38} {'智力':>6} {'价格':>7} {'性价比':>7} {'分数':>6} {'局数':>5}")
    for key, row in sorted(rows.items(), key=lambda kv: -kv[1]["intel"]):
        value = "-" if row["value"] is None else f"{row['value']:.2f}"
        print(f"{key:38} {row['intel']:6.1f} {row['price_idx']:7.1f} {value:>7} "
              f"{row['score']:6.0f} {row['games']:5d}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--arena-main", help="arena-main.json 路径")
    parser.add_argument("--out", help="输出路径（默认 ~/.zcode/v2/model-scores.json）")
    parser.add_argument("--write", action="store_true", help="写分数文件")
    parser.add_argument("--quiet", action="store_true", help="不打印排行（自动化用）")
    args = parser.parse_args()

    data = load_rows(arena_path(args.arena_main))
    scored = score_rows(data)
    if not scored["models"]:
        print("没有可用分数：先跑 tools/arena_leaderboard.py --refresh --force --write")
        return 1

    payload = {
        "version": 1,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "basis": scored["basis"],
        "models": scored["models"],
    }
    if not args.quiet:
        render(payload)
    if not args.write:
        print("dry run；加 --write 落盘")
        return 0

    path = out_path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)  # 原子替换：生成器随时可能在读
    print(f"已写入 {path}（{len(payload['models'])} 条）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
