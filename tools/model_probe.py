#!/usr/bin/env python3
"""Probe the unified four-group model list with the exact body ZCode sends.

Every model is sent through the unified router (127.0.0.1:7871) using its
display id (`WB:...` / `OC:...` / `QD:...`). The effective body is computed by
`providers/workbuddy/effective_body.js` with the model's provider id, so
provider-specific `optionSpecs.reasoningLevel.map` overrides (e.g. the empty
map for minimax-m3 / beam-free / bridged models) are applied.

Status vocabulary (same as the Qoder probe):

    ok / fallback / queued / rate_limited / blocked / unavailable / timeout / error

`ever_ok` is preserved across runs. `tools/model_alias.py --probe-file` keeps a
previously working model through a transient queue/timeout/blocked/error and
removes only a model the upstream explicitly says is gone (`unavailable`, 404).

Each record also carries `resp_model` / `quota_model` / `credit` taken from the
upstream reply: one display id can hide different real models (hy4-free vs hy4 vs
hy4-preview), and the WB channel marks its quota pool there. Fields the upstream
did not send are written as null and never retried — a reader must tolerate both
a missing key (results written by an older probe) and a null value.

Usage
-----
    python tools/model_probe.py
    python tools/model_probe.py --only "OC:MM3:X0.22" --timeout 120
    python tools/model_probe.py --group 高耗 --sleep 2
    python tools/model_alias.py --probe-file ~/.zcode/v2/model_probe.json --apply
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
EFFECTIVE = REPO / "providers" / "workbuddy" / "effective_body.js"
DEFAULT_OUT = Path.home() / ".zcode" / "v2" / "model_probe.json"
ALIAS = Path.home() / ".zcode" / "v2" / "model-alias-map.json"
PROVIDERS = ("opencode-go-chat", "opencode-go-chat-free",
             "opencode-go-chat-fast", "opencode-go-chat-slow")


def config_path(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    env = os.environ.get("ZCODE_PERSONAL_PROVIDER_CONFIG_FILE")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".zcode" / "v2" / "provider_config.json"


def provider_rules(cfg: dict) -> list[dict]:
    rules = cfg["config"]["providerConfigRules"]
    return rules if isinstance(rules, list) else rules.get("providerRules", [])


def load_alias() -> dict:
    try:
        return json.loads(ALIAS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def models_of(cfg: dict, group: str | None, alias: dict) -> list[tuple[str, str, str]]:
    """Return (display id, provider id, original id); probe results key on original."""
    models = alias.get("models") or {}
    legacy = alias.get("legacy") or {}
    out: list[tuple[str, str, str]] = []
    for rule in provider_rules(cfg):
        provider_id = str(rule.get("providerId") or "")
        if provider_id not in PROVIDERS:
            continue
        name = str(rule.get("providerName") or "")
        if group and group not in (provider_id, name):
            continue
        for model in (rule.get("config") or {}).get("personalModelIds") or []:
            display = str(model)
            entry = models.get(display) or models.get(legacy.get(display, ""), {})
            original = str((entry or {}).get("original") or display)
            out.append((display, provider_id, original))
    return out


def effective_body(model: str, provider_id: str, max_tokens: int) -> dict:
    try:
        result = subprocess.run(
            [
                "node", str(EFFECTIVE),
                "--provider-id", provider_id,
                "--api-type", "openai-chat-completions",
                "--base-url", "http://127.0.0.1:7871/v1",
                "--max-output-tokens", str(max_tokens),
                model,
            ],
            capture_output=True, text=True, timeout=60, check=True,
        )
        parsed = json.loads(result.stdout)
        return (parsed.get(model) or {}).get("body") or {}
    except Exception as exc:
        print(f"warning: effective body failed for {model}: {exc}", file=sys.stderr)
        return {}


def build_body(model: str, extra: dict, max_tokens: int) -> dict:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "ok"},
        ],
        "max_completion_tokens": max_tokens,
        "stream": False,
    }
    body.update(extra)
    return body


def post(model: str, body: dict, timeout: int) -> tuple[int | None, str, str]:
    request = urllib.request.Request(
        "http://127.0.0.1:7871/v1/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", "replace"), ""
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace"), ""
    except Exception as exc:
        return None, "", str(exc)


def classify(http: int | None, detail: str, error: str) -> str:
    text = (detail + " " + error).lower()
    if http is None:
        return "timeout" if "timed out" in text or "timeout" in text else "error"
    if http == 200:
        return "ok"
    if "10605" in text or "isqueued" in text or ("queue" in text and http in (403, 502)):
        return "queued"
    if "no_healthy_account" in text or "no healthy account" in text:
        # WorkBuddy pool-level cooldown: the model is fine, every account is
        # temporarily cooled. Treat it like a rate limit, not a dead model.
        return "rate_limited"
    if http == 429 or "rate limit" in text or "6004" in text:
        return "rate_limited"
    # HTTP 状态码先于文本判定：opencode 把地区/权限拒绝包在
    # "Endpoint is unavailable." 这类话术里（经 zgate 桥接后 body 只剩
    # "bridge upstream error: Upstream request failed: Endpoint is unavailable."），
    # 按文本匹配 "unavailable" 会把「这条出口进不去」误判成「型号下架」，
    # 再被 model_alias --probe-file 摘掉。2026-11-10 12:02 Claude-Haiku-5.5
    # 就是这样从配置里消失的。
    if http == 403 or "not allowed" in text or "permission" in text or "user type" in text:
        return "blocked"
    # 只有「上游明确说没有这个型号」才算下架。404 是权威信号；文本只在
    # 明确点名型号不存在时才算，避免把 endpoint / region 的话术算进来。
    if http == 404 or "model not found" in text or "no such model" in text or "unknown model" in text:
        return "unavailable"
    return "error"


def pick(obj: object, *names: str):
    """Return the first present, non-null value; 0 and "" are real answers here."""
    if not isinstance(obj, dict):
        return None
    for name in names:
        value = obj.get(name)
        if value is not None:
            return value
    return None


def identity(detail: str) -> dict:
    """Pull resp_model / quota_model / credit out of the raw reply body.

    Scanned at top level plus the `usage` / `metadata` sub-objects, because a
    chat-completions reply puts them on top while the WB gateway nests them.
    Unparsable bodies (error pages, empty timeouts) just yield an all-null record.
    """
    out = {"resp_model": None, "quota_model": None, "credit": None}
    try:
        payload = json.loads(detail) if detail else None
    except Exception:
        payload = None
    if not isinstance(payload, dict):
        return out
    scopes = [payload]
    for holder in ("usage", "metadata"):
        nested = payload.get(holder)
        if isinstance(nested, dict):
            scopes.append(nested)
    for scope in scopes:
        out["resp_model"] = out["resp_model"] or pick(scope, "model")
        out["quota_model"] = out["quota_model"] or pick(scope.get("quota"), "model")
        out["credit"] = out["credit"] if out["credit"] is not None else pick(scope, "credit", "credits")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--group", help="只探测某组（provider id 或显示名：主力/免费/低耗/高耗）")
    parser.add_argument("--only", help="只探测这些模型（逗号分隔，精确匹配）")
    # 默认值给 256：32 在「先思考再出字」的模型（Gemini / Doubao 档）上会被思考预算
    # 吃光，上游回 400 max output tokens were exhausted，探活把它记成死型号，
    # 再被 --probe-file 从配置里摘掉（2026-11-11 Gemini-AIS 消失的同一路径）。
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--timeout", type=int, default=75)
    parser.add_argument("--sleep", type=float, default=1.5)
    args = parser.parse_args()

    cfg = json.loads(config_path(args.config).read_text(encoding="utf-8"))
    models = models_of(cfg, args.group, load_alias())
    if args.only:
        wanted = {part.strip() for part in args.only.split(",") if part.strip()}
        models = [item for item in models if item[0] in wanted or item[2] in wanted]
    if not models:
        raise SystemExit("没有要探测的模型")

    out_path = Path(args.out).expanduser()
    results: dict[str, dict] = {}
    if out_path.exists():
        try:
            results = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception:
            results = {}

    for index, (model, provider_id, original) in enumerate(models):
        print(f"[{index + 1}/{len(models)}] {model} ({provider_id}) ...", flush=True)
        extra = effective_body(model, provider_id, args.max_tokens)
        started = time.time()
        http, detail, error = post(model, build_body(model, extra, args.max_tokens), args.timeout)
        status = classify(http, detail, error)
        ident = identity(detail)
        key = original or model
        previous = results.get(key) or {}
        results[key] = {
            "display": model,
            "status": status,
            "http": http,
            "ms": int((time.time() - started) * 1000),
            "detail": (detail or error)[:300],
            "resp_model": ident["resp_model"],
            "quota_model": ident["quota_model"],
            "credit": ident["credit"],
            "provider": provider_id,
            "body_keys": sorted(extra.keys()),
            "ever_ok": bool(previous.get("ever_ok")) or previous.get("status") == "ok" or status == "ok",
            "ok_at": time.strftime("%Y-%m-%d %H:%M:%S") if status == "ok" else previous.get("ok_at"),
            # model_alias._fresh_probe 按 checked_at 判新鲜度。之前只写 ok_at，
            # 非 ok 的记录没有时间戳 → 整份结果一律被当「未知」，下架的型号
            # 永远删不掉（2026-11-06 第一次接通探活时踩到）。
            "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        # 只在真实型号和显示名不一致时才多打一段，免得噪音盖住状态
        shown = ""
        if ident["resp_model"] and ident["resp_model"] != model:
            shown = f" resp_model={ident['resp_model']}"
        print(f"  {status:<12} http={http} {results[key]['detail'][:120]}{shown}", flush=True)
        if index + 1 < len(models) and args.sleep > 0:
            time.sleep(args.sleep)

    print(f"\n结果写入 {out_path}")
    for model, provider_id, original in models:
        item = results.get(original or model, {})
        print(f"  {model:<38} {item.get('status','?'):<12} http={item.get('http')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
