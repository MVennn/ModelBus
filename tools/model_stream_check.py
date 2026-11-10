#!/usr/bin/env python3
"""model_stream_check.py — 模型流式 / 思考 / 输出 / TPS 自动准入探针。

一句话：把 DSH profile 的 llm-pi-ai 模型表当成唯一契约，模型进表即自动纳入，
新增模型无需人工维护清单，也无需逐个手测。

契约推导（与 dsh-claude-style 去 Default 伪档位补丁一致）：
  * expectedEffort = reasoningEfforts 按宿主 THINKING_LEVELS 升序的末位；
  * 实际发送的 reasoning_effort = 该档的 wire 值；
  * reasoning_deepseek（compat.thinkingFormat=deepseek）必须吐思考；
  * reasoning_plain 必须流式，思考不强制；
  * no_reasoning 必须流式，不判思考 / 不发 effort。

判定口径（按串行对照实测修正，避免假阴性）：
  * 长提示 + max_tokens 768，保证有足量正文可判分块；
  * 默认并发 2；429 / 5xx / 超时 / 网络错误自动退避重试；
  * 分块判据只在正文 >= 24 字时生效（超短答案 1-2 块属正常）；
  * tps = 端到端观测字符速率（正文字符 / 总耗时），不用首末块间隔；
  * 首选档思考占满预算时，保持同一官方档位把预算提到 2048 补测正文，不误判为故障。

豁免与自动恢复：
  tools/model_stream_exemptions.json 记录上游真故障模型。探针仍会实测它们：
  满足 recoverWhen 就标 RECOVERED（提示可删条目），否则标 EXEMPT（不计 FAIL）。
  上游修好后自动暴露，无需人工改清单。

用法：
  python tools/model_stream_check.py                  # 全量矩阵
  python tools/model_stream_check.py --changed        # 只测新增 / 档位变更 / 上次非 PASS 待复查
  python tools/model_stream_check.py --model Iceman   # 单测
  python tools/model_stream_check.py --deep           # 额外找隐藏思考能力
  python tools/model_stream_check.py --soft           # 有 FAIL 也返回 0（定时任务）
  python tools/model_stream_check.py --no-heal        # 跳过插件补丁自愈

退出码：0 = 无 FAIL；1 = 存在 FAIL；2 = 配置 / 依赖错误。
报告：.work/model-stream/report-<UTC>.json 与 latest.json（真实项目内）。
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    sys.exit("model_stream_check.py 需要 PyYAML：python -m pip install pyyaml")

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure") and (_s.encoding or "").lower() not in {"utf-8", "utf8"}:
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DSH_HOME = Path(os.environ.get("DSH_HOME", str(Path.home() / ".dsh")))
PROFILE = os.environ.get("DSH_PROFILE", "desktop")
PATCH = DSH_HOME / "profiles" / PROFILE / "cordis.patch.yml"
PATCH_SCRIPT = DSH_HOME / "tools" / "patch-claude-style-effort.mjs"
EXEMPTIONS = ROOT / "tools" / "model_stream_exemptions.json"
REPORT_DIR = ROOT / ".work" / "model-stream"
LATEST = REPORT_DIR / "latest.json"
DEFAULT_BASE = os.environ.get("MODEL_GATEWAY_BASE", "http://127.0.0.1:7871/v1")

# 与宿主 dsh-llm-pi-ai 的 THINKING_LEVELS 完全一致；补丁取 efforts 末位即此序末位。
LEVEL_ORDER = ["off", "minimal", "low", "medium", "high", "xhigh", "max"]
PROMPT = "请写一段约 100 字的短文，介绍春天的景象，要求连续叙述、不要分点、不要标题。"
MAX_TOKENS = 768
RECOVER_TOKENS = 2048     # 思考占满预算时的同档位补测预算（Iceman high-2048 实测 fin=stop）

# 阈值（软/硬分离；上游额度与网络抖动归 SKIP，不算 FAIL）
MIN_CHUNKS = 4
MIN_CONTENT = 24          # 正文不足此长度不做分块判定，避免超短答案误伤
CHUNKY_RATIO = 0.6
CHUNKY_FLOOR = 48
SLOW_TPS = 1.0            # 端到端观测字符速率下限，低于此标 WARN 而非 FAIL
# 上次这些状态次日必须重测：瞬态 SKIP / 真故障 FAIL / 边缘 WARN / 豁免 EXEMPT 待复通。
# PASS 与 RECOVERED 不重复打，避免每天对全量模型白发一轮推理请求。
RETRY_STATES = {"SKIP", "FAIL", "WARN", "EXEMPT"}
TIMEOUT_DEFAULT = 45
CONCURRENCY_DEFAULT = 2   # 并发 6 实测会把网关打出假阴性，降到 2
RETRIES = 2
RETRY_BACKOFF_S = 1.2


class _Loader(yaml.SafeLoader):
    pass


def _construct_js(loader: yaml.Loader, node: yaml.Node) -> Any:
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_mapping(node)


for _tag in ("!js", "tag:yaml.org,2002:js"):
    _Loader.add_constructor(_tag, _construct_js)


def _rank(level: str) -> int:
    return LEVEL_ORDER.index(level) if level in LEVEL_ORDER else len(LEVEL_ORDER)


def _effort_map(raw: Any) -> dict[str, str]:
    """YAML 1.1 会把裸 off/on/yes/no 读成 bool；档位键一律归一化成字符串。
    cordis.patch.yml 经不同生成器重写后可能丢引号，宿主（YAML 1.2）读到的仍是 off，
    这里必须对齐，否则 ",".join(keys) 会炸且 off 档被当成非法级别。
    """
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in raw.items():
        key = ("off" if not k else "on") if isinstance(k, bool) else str(k)
        out[key] = "" if v is None else str(v)
    return out


def load_contract() -> list[dict[str, Any]]:
    """把 patch 里的每个模型翻译成一条可机器判定的期望契约。"""
    if not PATCH.exists():
        raise RuntimeError("找不到 DSH profile patch：" + str(PATCH))
    doc = yaml.load(PATCH.read_text(encoding="utf-8"), Loader=_Loader)
    out: list[dict[str, Any]] = []
    for item in doc or []:
        if not isinstance(item, dict) or item.get("id") != "llm-pi-ai":
            continue
        providers = (item.get("config") or {}).get("providers") or {}
        for pid, pconf in providers.items():
            if not str(pid).startswith("zcode-"):
                continue
            base = pconf.get("baseURL") or DEFAULT_BASE
            for m in pconf.get("models") or []:
                efforts = _effort_map(m.get("reasoningEfforts"))
                keys = sorted(efforts.keys(), key=_rank)
                last = keys[-1] if keys else None
                wire = efforts[last] if last else None
                compat = m.get("compat") or {}
                deepseek = compat.get("thinkingFormat") == "deepseek"
                if efforts and deepseek:
                    kind = "reasoning_deepseek"
                elif efforts:
                    kind = "reasoning_plain"
                else:
                    kind = "no_reasoning"
                out.append(
                    {
                        "id": m["id"],
                        "provider": pid,
                        "base": base,
                        "kind": kind,
                        "efforts": efforts,
                        "expectedEffort": last,
                        "wireEffort": wire,
                        "expectThinking": kind == "reasoning_deepseek",
                        "fingerprint": "|".join([m["id"], ",".join(keys), kind, str(wire)]),
                    }
                )
    return out


def load_exemptions() -> dict[str, dict[str, str]]:
    if not EXEMPTIONS.exists():
        return {}
    try:
        doc = json.loads(EXEMPTIONS.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        print("[WARN] 豁免清单读取失败，按空处理：" + str(exc))
        return {}
    if doc.get("schema") != 1:
        print("[WARN] 豁免清单 schema 不是 1，按空处理")
        return {}
    return {x["id"]: x for x in doc.get("exemptions", []) if isinstance(x, dict) and x.get("id")}


def still_broken(ex: dict[str, str], r: dict[str, Any]) -> bool:
    """recoverWhen 用白名单键解释，不引入任意表达式求值。"""
    rule = ex.get("recoverWhen", "contentChars>0")
    if rule == "http!=403":
        return r["http"] == 403
    if rule == "chunks>=4":
        return r["chunks"] < 4
    return r["contentChars"] == 0


def _opener():
    # 显式绕过系统代理：127.0.0.1 网关必须直连，不能经过 mihomo / 透明代理。
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _delta_fields(delta: dict[str, Any]) -> tuple[str, str]:
    content = delta.get("content") or ""
    if not isinstance(content, str):
        content = ""
    reasoning = ""
    for key in ("reasoning_content", "reasoning", "thinking", "reasoningContent", "thinking_content"):
        v = delta.get(key)
        if isinstance(v, str):
            reasoning += v
    return content, reasoning


def _encrypted_reasoning(delta: dict[str, Any]) -> int:
    """格式 B：上游只给 reasoning_details[type=reasoning.encrypted] 的 opaque replay blob。
    宿主 pi-ai 把它当 replay 元数据丢弃、思考块留空，GUI 完全看不到思考；
    这里单独计数，让准入报告能区分「上游加密分流」与「模型真故障」。
    """
    details = delta.get("reasoning_details")
    if not isinstance(details, list):
        return 0
    n = 0
    for d in details:
        if isinstance(d, dict) and str(d.get("type", "")).startswith("reasoning.encrypted"):
            n += 1
    return n


def _request(m: dict[str, Any], timeout: int, effort: str | None, max_tokens: int) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": m["id"],
        "messages": [{"role": "user", "content": PROMPT}],
        "stream": True,
        "max_tokens": max_tokens,
    }
    if effort is not None:
        body["reasoning_effort"] = effort
    req = urllib.request.Request(
        m["base"].rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        method="POST",
    )
    t0 = time.monotonic()
    chunks = 0
    reasoning_chars = 0
    content_chars = 0
    max_delta = 0
    first_ms: float | None = None
    http = 0
    err = ""
    finish = ""
    completion_tokens: int | None = None
    encrypted_reasoning = 0
    try:
        with _opener().open(req, timeout=timeout) as resp:
            http = resp.status
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line or not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    obj = json.loads(payload)
                except (ValueError, TypeError):
                    continue
                usage = obj.get("usage") or {}
                if isinstance(usage, dict) and isinstance(usage.get("completion_tokens"), (int, float)):
                    completion_tokens = usage["completion_tokens"]
                choices = obj.get("choices") or []
                if not choices:
                    continue
                ch = choices[0] or {}
                if ch.get("finish_reason"):
                    finish = str(ch["finish_reason"])
                delta = ch.get("delta") or ch.get("message") or {}
                if not isinstance(delta, dict):
                    continue
                c, rr = _delta_fields(delta)
                # 加密 thinking 只落在 reasoning_details，_delta_fields 读不到；
                # 单独累计，不把它算进 chunks（它是 finish 前的 replay 元数据块）。
                encrypted_reasoning += _encrypted_reasoning(delta)
                n = len(c) + len(rr)
                if n == 0:
                    continue
                now = time.monotonic()
                if first_ms is None:
                    first_ms = (now - t0) * 1000
                chunks += 1
                max_delta = max(max_delta, n)
                content_chars += len(c)
                reasoning_chars += len(rr)
    except urllib.error.HTTPError as exc:
        http = exc.code
        err = "HTTP " + str(exc.code)
    except Exception as exc:  # noqa: BLE001 - 网络抖动统一归 SKIP / 重试
        err = type(exc).__name__ + ": " + str(exc)[:120]
    total_ms = (time.monotonic() - t0) * 1000
    gen_s = total_ms / 1000.0
    cps = round(content_chars / gen_s, 2) if gen_s > 0 else 0.0
    tok_tps = (round(completion_tokens / gen_s, 2)
               if completion_tokens and gen_s > 0 else None)
    return {
        "http": http, "err": err, "chunks": chunks,
        "reasoningChars": reasoning_chars, "contentChars": content_chars,
        "maxDelta": max_delta, "firstMs": round(first_ms or 0, 1),
        "totalMs": round(total_ms, 1), "tps": cps, "tokTps": tok_tps,
        "finishReason": finish, "completionTokens": completion_tokens,
        "encryptedReasoning": encrypted_reasoning, "effort": effort,
    }


def _retryable(r: dict[str, Any]) -> bool:
    return r["http"] == 429 or r["http"] >= 500 or (r["http"] == 0 and bool(r["err"]))


def probe(m: dict[str, Any], timeout: int, force_effort: str | None = None,
          max_tokens: int = MAX_TOKENS, retries: int = RETRIES) -> dict[str, Any]:
    effort = force_effort if force_effort is not None else m["wireEffort"]
    r: dict[str, Any] = {}
    for attempt in range(retries + 1):
        r = _request(m, timeout, effort, max_tokens)
        if not _retryable(r):
            break
        if attempt < retries:
            time.sleep(RETRY_BACKOFF_S * (attempt + 1))
    r["attempts"] = attempt + 1
    # 思考占满预算：保持同一官方档位，只把预算提到 RECOVER_TOKENS 补测正文。
    # 不退回「省略 effort」或 off 档：前者正是 Default 伪档位 bug 的根源，
    # 后者 wire=disabled 会被上游 422 拒绝（2026-11-09 实测）。
    if (force_effort is None and r["http"] == 200
            and r["contentChars"] == 0 and r["reasoningChars"] > 0):
        budget = max(max_tokens, RECOVER_TOKENS)
        r2 = _request(m, timeout, effort, budget)
        r["recoverProbe"] = {
            "effort": effort, "maxTokens": budget,
            "http": r2["http"], "chunks": r2["chunks"],
            "reasoningChars": r2["reasoningChars"],
            "contentChars": r2["contentChars"], "maxDelta": r2["maxDelta"],
            "firstMs": r2["firstMs"], "totalMs": r2["totalMs"], "tps": r2["tps"],
            "finishReason": r2["finishReason"], "err": r2["err"],
            "primary": {"maxTokens": max_tokens, "chunks": r["chunks"],
                        "reasoningChars": r["reasoningChars"],
                        "finishReason": r.get("finishReason", "")},
        }
        if r2["http"] == 200 and r2["contentChars"] > 0:
            for k in ("chunks", "reasoningChars", "contentChars", "maxDelta",
                      "firstMs", "totalMs", "tps", "finishReason", "completionTokens"):
                r[k] = r2[k]
    return r


def judge(m: dict[str, Any], r: dict[str, Any],
          exempt: dict[str, dict[str, str]]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    ex = exempt.get(m["id"])
    if ex:
        if still_broken(ex, r):
            return "EXEMPT", ["上游真故障（豁免中）：" + ex["reason"]]
        return "RECOVERED", ["上游已恢复，可删除豁免条目：" + m["id"]]
    http = r["http"]
    if http == 429 or http >= 500 or (http == 0 and r["err"]):
        return "SKIP", [r["err"] or ("HTTP " + str(http))]
    if http != 200:
        return "FAIL", ["HTTP " + str(http) + " " + r["err"]]
    if r["contentChars"] == 0 and r["reasoningChars"] == 0:
        return "FAIL", ["无正文输出（上游空 completion）"]
    if r["contentChars"] == 0:
        reasons.append("思考占满预算且同档位大预算补测未拿到正文")
    elif r["contentChars"] >= MIN_CONTENT:
        limit = max(CHUNKY_FLOOR, r["contentChars"] * CHUNKY_RATIO)
        if r["chunks"] < MIN_CHUNKS or r["maxDelta"] > limit:
            reasons.append("大块聚合 chunks=%d maxDelta=%d limit=%.0f" % (
                r["chunks"], r["maxDelta"], limit))
    if r.get("finishReason") == "max_tokens" and r["chunks"] < MIN_CHUNKS:
        if not any("大块聚合" in x for x in reasons):
            reasons.append("上游 max_tokens 截断且仅 %d 块" % r["chunks"])
    if m["expectThinking"] and r["reasoningChars"] == 0:
        if r.get("encryptedReasoning", 0) > 0:
            reasons.append("上游加密思考分流（reasoning.encrypted，零明文 thinking delta；"
                           "宿主按 replay 元数据丢弃，GUI 看不到思考）")
        else:
            reasons.append("声明 deepseek 思考但 reasoningChars=0")
    if 0 < r["tps"] < SLOW_TPS:
        reasons.append("端到端字符速率偏低 %.2f cps" % r["tps"])
    rp = r.get("recoverProbe")
    if rp:
        note = ("同档位 %d 预算补测出正文（首选 %d 思考占满）" % (
                    rp["maxTokens"], rp["primary"]["maxTokens"])
                if r["contentChars"] > 0 else
                "同档位 %d 预算补测仍未拿到正文" % rp["maxTokens"])
        if r["contentChars"] > 0 and not reasons:
            return "PASS", [note]
        reasons.append(note)
    return ("WARN", reasons) if reasons else ("PASS", [])


def deep_explore(m: dict[str, Any], timeout: int, main: dict[str, Any],
                 retries: int) -> str | None:
    """no_reasoning 模型：额外试一次开思考，找出「上游能思考但档位漏声明」。"""
    if m["kind"] != "no_reasoning":
        return None
    r = probe(m, timeout, force_effort="high", retries=retries)
    if r["http"] == 200 and r["reasoningChars"] > 0 and main["reasoningChars"] == 0:
        return "上游可吐思考但 DSH 未声明档位（需在 effective 规则补 optionSpecs.reasoningLevel）"
    return None


def ensure_patch() -> str:
    """顺带自愈插件补丁：每次跑探针就检查一次，插件升级后也不会退回 Default 伪档位。"""
    if not PATCH_SCRIPT.exists():
        return "absent"
    try:
        chk = subprocess.run(
            ["node", str(PATCH_SCRIPT), "--check"],
            capture_output=True, text=True, timeout=40,
        )
        txt = chk.stdout + chk.stderr
        if "WOULD_PATCH" in txt or chk.returncode != 0:
            app = subprocess.run(
                ["node", str(PATCH_SCRIPT)],
                capture_output=True, text=True, timeout=90,
            )
            out = app.stdout + app.stderr
            return "reapplied" if ("PATCHED" in out and app.returncode == 0) else "apply-failed"
        return "ok"
    except Exception as exc:  # noqa: BLE001
        return "skipped:" + type(exc).__name__


def select_models(args, all_models):
    if args.model:
        wanted = set(args.model)
        picked = [m for m in all_models if m["id"] in wanted]
        missing = wanted - {m["id"] for m in picked}
        if missing:
            print("[WARN] 模型不在 patch 里：" + ", ".join(sorted(missing)))
        return picked
    if args.changed:
        if not LATEST.exists():
            print("[INFO] 无基线报告，--changed 退化为全量")
            return all_models
        try:
            prev = json.loads(LATEST.read_text(encoding="utf-8"))
            old = {x.get("fingerprint") for x in prev.get("contract", prev.get("models", []))}
            # 上次瞬态失败 / 边缘 / 豁免的模型次日必须复测；EXEMPT 借此自动复通，
            # PASS / RECOVERED 不再重复打，避免每天全量白发推理请求。
            stale = {x.get("id") for x in prev.get("models", [])
                     if isinstance(x, dict) and x.get("state") in RETRY_STATES}
        except Exception:
            old = set()
            stale = set()
        picked = [m for m in all_models if m["fingerprint"] not in old or m["id"] in stale]
        if not picked:
            print("[INFO] 无新增 / 档位变更 / 待复查模型，跳过探针")
        return picked
    return all_models


def merge_results(prev: dict[str, Any] | None, new: list[dict[str, Any]],
                  contract_ids: set[str], changed: bool) -> list[dict[str, Any]]:
    """增量测试（--changed / --model）也把 latest.json 保持为全量视图：
    避免手动单测把基线覆盖成 1 条，破坏次日 --changed 的待复查集合。
    """
    if not changed or not prev:
        return new
    by_id: dict[str, dict[str, Any]] = {}
    for x in prev.get("models", []):
        if isinstance(x, dict) and x.get("id") in contract_ids:
            by_id[x["id"]] = x
    for x in new:
        by_id[x["id"]] = x
    return [by_id[k] for k in sorted(by_id)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="模型流式 / 思考 / 输出 / TPS 自动准入探针")
    ap.add_argument("--model", action="append", help="只测指定模型（可重复）")
    ap.add_argument("--changed", action="store_true",
                    help="只测新增 / 档位变更 / 上次非 PASS 待复查的模型")
    ap.add_argument("--deep", action="store_true", help="额外探测未声明档位的隐藏思考能力")
    ap.add_argument("--soft", action="store_true", help="有 FAIL 也返回 0（定时任务不阻断）")
    ap.add_argument("--no-heal", action="store_true", help="跳过插件补丁自愈")
    ap.add_argument("--concurrency", type=int, default=CONCURRENCY_DEFAULT)
    ap.add_argument("--timeout", type=int, default=TIMEOUT_DEFAULT)
    ap.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
    ap.add_argument("--retries", type=int, default=RETRIES)
    args = ap.parse_args(argv)

    try:
        all_models = load_contract()
    except Exception as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 2
    if not all_models:
        print("ERROR: patch 里没有 zcode-* 模型", file=sys.stderr)
        return 2
    exempt = load_exemptions()
    heal = "disabled" if args.no_heal else ensure_patch()
    models = select_models(args, all_models)
    if not models:
        print("补丁自愈：%s；契约模型 %d 个；本次待测 0 个" % (heal, len(all_models)))
        return 0

    print("补丁自愈：%s；契约模型 %d 个；本次待测 %d 个；网关 %s" % (
        heal, len(all_models), len(models), DEFAULT_BASE))
    print("-" * 112)
    print("%-22s %-19s %-9s %6s %7s %8s %4s %7s %8s %9s  %s" % (
        "MODEL", "KIND", "STATE", "CHUNK", "THINK", "CONTENT", "ENC", "MAXD", "CPS",
        "FIRST_MS", "NOTE"))
    print("-" * 112)

    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        fut = {pool.submit(probe, m, args.timeout, None, args.max_tokens, args.retries): m
               for m in models}
        for f in concurrent.futures.as_completed(fut):
            m = fut[f]
            try:
                r = f.result()
            except Exception as exc:  # noqa: BLE001
                r = {"http": 0, "err": type(exc).__name__, "chunks": 0, "reasoningChars": 0,
                     "contentChars": 0, "maxDelta": 0, "firstMs": 0, "totalMs": 0, "tps": 0,
                     "tokTps": None, "finishReason": "", "encryptedReasoning": 0,
                     "effort": None}
            state, reasons = judge(m, r, exempt)
            if args.deep:
                hint = deep_explore(m, args.timeout, r, args.retries)
                if hint:
                    reasons.append(hint)
                    if state == "PASS":
                        state = "WARN"
            row = {**m, **r, "state": state, "reasons": reasons}
            results.append(row)
            print("%-22s %-19s %-9s %6d %7d %8d %4d %7d %8.2f %9.1f  %s" % (
                m["id"], m["kind"], state, r["chunks"], r["reasoningChars"],
                r["contentChars"], r.get("encryptedReasoning", 0), r["maxDelta"], r["tps"],
                r["firstMs"], "; ".join(reasons)[:66]))
    results.sort(key=lambda x: (x["provider"], x["id"]))

    states = ("PASS", "WARN", "FAIL", "SKIP", "EXEMPT", "RECOVERED")
    tested_counts = {s: sum(1 for x in results if x["state"] == s) for s in states}
    print("-" * 112)
    print("本次：PASS %d / WARN %d / FAIL %d / SKIP %d / EXEMPT %d / RECOVERED %d" % tuple(
        tested_counts[s] for s in states))
    print("口径：CPS = 端到端观测字符速率（正文字符 / 总耗时，TPS 代理）；"
          "大块聚合 = 正文>=%d 且 (chunks<%d 或 maxDelta>max(%d, 正文*%.1f))；"
          "SKIP = 429/5xx/超时（重试 %d 次后仍失败）" % (
              MIN_CONTENT, MIN_CHUNKS, CHUNKY_FLOOR, CHUNKY_RATIO, args.retries))
    print("豁免：仍实测，满足 recoverWhen 自动标 RECOVERED；清单 " + str(EXEMPTIONS))
    print("补测：首选预算下思考占满时，保持同一官方档位提至 %d 重测（不退回省略 effort）" % RECOVER_TOKENS)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prev: dict[str, Any] | None = None
    if LATEST.exists():
        try:
            prev = json.loads(LATEST.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            prev = None
    contract_ids = {m["id"] for m in all_models}
    # --changed 与 --model 都是增量测试：结果合并回全量视图，latest.json 恒定契约条数。
    merged = merge_results(prev, results, contract_ids, args.changed or bool(args.model))
    summary = {s: sum(1 for x in merged if x.get("state") == s) for s in states}
    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "profile": PROFILE, "gateway": DEFAULT_BASE, "patchHeal": heal,
        "thresholds": {"minChunks": MIN_CHUNKS, "minContent": MIN_CONTENT,
                       "chunkyRatio": CHUNKY_RATIO, "chunkyFloor": CHUNKY_FLOOR,
                       "slowCps": SLOW_TPS, "maxTokens": args.max_tokens,
                       "recoverTokens": RECOVER_TOKENS, "retries": args.retries},
        "contractCount": len(all_models), "tested": len(results),
        "contract": [{"id": m["id"], "fingerprint": m["fingerprint"]} for m in all_models],
        "summary": summary, "testedSummary": tested_counts,
        "models": merged,
    }
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    (REPORT_DIR / ("report-" + stamp + ".json")).write_text(payload, encoding="utf-8")
    LATEST.write_text(payload, encoding="utf-8")
    print("报告：" + str(LATEST) + "（全量视图 " + str(len(merged)) + " 条）")

    if tested_counts["FAIL"] and not args.soft:
        print("失败模型：" + ", ".join(x["id"] for x in results if x["state"] == "FAIL"))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
