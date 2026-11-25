#!/usr/bin/env python3
"""effort_probe.py — 逐模型 x 逐档全矩阵实测探针（首轮审计用）。

复用 tools/model_stream_check.py 的契约加载与 _request()，对每个模型的每个
官方档位（wire 映射后的真实 effort 值）发一次流式请求，记录 HTTP / 思考 /
正文 / 状态。**关键**：urllib 的 timeout 只是 socket 读超时，深度思考流式
持续吐 token 时不会触发整体超时，所以这里用守护线程 + join 做整体硬超时。

输出 .work/effort-matrix/report-<stamp>.json 与 latest.json。不改网关/配置。

用法：
    python tools/effort_probe.py --concurrency 2 --hard-timeout 30
    python tools/effort_probe.py --model "HY4-Flash-Free" --hard-timeout 20
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import model_stream_check as msc

REPORT_DIR = Path(__file__).resolve().parent.parent / ".work" / "effort-matrix"
LATEST = REPORT_DIR / "latest.json"


def _request_hard(m: dict, timeout: int, wire: str | None, max_tokens: int,
                  hard_timeout: int) -> dict:
    """在守护线程里跑 _request，join(hard_timeout) 做整体硬超时。"""
    box: dict = {}

    def run() -> None:
        try:
            box["r"] = msc._request(m, timeout, wire, max_tokens)
        except Exception as exc:  # noqa: BLE001
            box["r"] = {"http": 0, "err": type(exc).__name__ + ": " + str(exc)[:120],
                        "chunks": 0, "reasoningChars": 0, "contentChars": 0,
                        "encryptedReasoning": 0, "maxDelta": 0, "finishReason": "",
                        "firstMs": 0, "totalMs": 0, "tps": 0.0, "effort": wire}

    th = threading.Thread(target=run, daemon=True)
    th.start()
    th.join(hard_timeout)
    if th.is_alive():
        return {"http": 0, "err": "HARD_TIMEOUT_%ss" % hard_timeout, "chunks": 0,
                "reasoningChars": 0, "contentChars": 0, "encryptedReasoning": 0,
                "maxDelta": 0, "finishReason": "", "firstMs": 0,
                "totalMs": hard_timeout * 1000, "tps": 0.0, "effort": wire}
    return box.get("r", {"http": 0, "err": "NO_RESULT", "chunks": 0,
                         "reasoningChars": 0, "contentChars": 0, "encryptedReasoning": 0,
                         "maxDelta": 0, "finishReason": "", "firstMs": 0,
                         "totalMs": 0, "tps": 0.0, "effort": wire})


def probe_cell(m: dict, label: str, wire: str | None, timeout: int,
               max_tokens: int, retries: int, hard_timeout: int) -> dict:
    """测一个 (模型, 档位) 单元。"""
    fake = {**m, "wireEffort": wire}
    r = _request_hard(fake, timeout, wire, max_tokens, hard_timeout)
    for attempt in range(retries):
        if msc._retryable(r):
            import time
            time.sleep(msc.RETRY_BACKOFF_S * (attempt + 1))
            r = _request_hard(fake, timeout, wire, max_tokens, hard_timeout)
        else:
            break
    if r["err"].startswith("HARD_TIMEOUT"):
        state = "TIMEOUT"
    elif r["http"] != 200:
        state = "SKIP" if (r["http"] == 429 or r["http"] >= 500) else "FAIL"
    elif r["reasoningChars"] == 0 and r["contentChars"] == 0:
        state = "EMPTY"
    elif r["reasoningChars"] > 0:
        state = "THINKING"
    else:
        state = "CONTENT_ONLY"
    return {
        "label": label, "wire": wire, "state": state,
        "http": r["http"], "chunks": r["chunks"],
        "reasoningChars": r["reasoningChars"], "contentChars": r["contentChars"],
        "encryptedReasoning": r.get("encryptedReasoning", 0),
        "maxDelta": r["maxDelta"], "finishReason": r.get("finishReason", ""),
        "tps": r["tps"], "firstMs": r["firstMs"], "totalMs": r["totalMs"],
        "err": r.get("err", ""), "effort": wire,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", action="append", help="只测指定模型（可重复）")
    ap.add_argument("--concurrency", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=msc.TIMEOUT_DEFAULT)
    ap.add_argument("--hard-timeout", type=int, default=35,
                    help="每个单元整体硬超时秒数（默认 35，覆盖流式慢速）")
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--retries", type=int, default=0)
    args = ap.parse_args()

    models = msc.load_contract()
    if args.model:
        wanted = set(args.model)
        models = [m for m in models if m["id"] in wanted]
        missing = wanted - {m["id"] for m in models}
        if missing:
            print("[WARN] 模型不在契约里：" + ", ".join(sorted(missing)), flush=True)
    if not models:
        print("ERROR: 无待测模型", flush=True)
        return 2

    cells = []
    for m in models:
        for label in sorted(m["efforts"].keys(), key=msc._rank):
            cells.append((m, label, m["efforts"][label]))
    print("全矩阵：%d 模型 x 合计 %d 单元；并发 %d；硬超时 %ss；网关 %s" % (
        len(models), len(cells), args.concurrency, args.hard_timeout, msc.DEFAULT_BASE), flush=True)
    print("-" * 112, flush=True)
    print("%-22s %-8s %-10s %-12s %5s %6s %7s %8s  %s" % (
        "MODEL", "LABEL", "WIRE", "STATE", "HTTP", "CHUNK", "THINK", "CONTENT", "ERR"), flush=True)
    print("-" * 112, flush=True)

    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        fut = {pool.submit(probe_cell, m, label, wire, args.timeout,
                           args.max_tokens, args.retries, args.hard_timeout): (m, label, wire)
               for m, label, wire in cells}
        for f in concurrent.futures.as_completed(fut):
            m, label, wire = fut[f]
            try:
                row = f.result()
            except Exception as exc:
                row = {"label": label, "wire": wire, "state": "ERROR", "http": 0,
                       "chunks": 0, "reasoningChars": 0, "contentChars": 0,
                       "encryptedReasoning": 0, "maxDelta": 0, "finishReason": "",
                       "tps": 0.0, "firstMs": 0, "totalMs": 0,
                       "err": type(exc).__name__ + ": " + str(exc)[:80], "effort": wire}
            row["model"] = m["id"]
            row["kind"] = m["kind"]
            results.append(row)
            print("%-22s %-8s %-10s %-12s %5d %6d %7d %8d  %s" % (
                m["id"], label, str(wire), row["state"], row["http"] or 0,
                row["chunks"], row["reasoningChars"], row["contentChars"],
                row["err"][:36]), flush=True)

    results.sort(key=lambda x: (x["model"], msc._rank(x["label"])))
    summary: dict[str, dict[str, int]] = {}
    for r in results:
        s = summary.setdefault(r["model"], {})
        s[r["state"]] = s.get(r["state"], 0) + 1
    print("-" * 112, flush=True)
    for model in sorted(summary):
        print("%-22s %s" % (model, dict(summary[model])), flush=True)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "gateway": msc.DEFAULT_BASE,
        "maxTokens": args.max_tokens, "timeout": args.timeout,
        "hardTimeout": args.hard_timeout, "retries": args.retries,
        "concurrency": args.concurrency, "cellCount": len(cells),
        "summary": summary, "cells": results,
    }
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    rp = REPORT_DIR / ("report-" + stamp + ".json")
    rp.write_text(payload, encoding="utf-8")
    LATEST.write_text(payload, encoding="utf-8")
    print("报告：" + str(rp), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
