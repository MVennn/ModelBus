#!/usr/bin/env python3
"""Project ZCode's final model groups into DeepSeekRuntime's llm-pi-ai profile.

The daily model sync writes ``~/.zcode/v2/provider_config.json`` through
``tools/model_alias.py``. This tool reads that final state and rewrites only
the ``llm-pi-ai`` entry in ``~/.dsh/profiles/<profile>/cordis.patch.yml``:

* every ZCode provider becomes a DSH route (``opencode-go-chat`` -> ``zcode-main``,
  ``...-free`` -> ``zcode-free``, ``...-fast`` -> ``zcode-saver``);
* model order, context window, output cap, image input and reasoning levels are
  copied from the resolved ZCode metadata (``zcode_effective_body.js``);
* ZCode models whose effective ``reasoningLevel.map`` is ``{}`` deliberately
  get no ``reasoningEfforts``, because DSH would otherwise send a
  ``reasoning_effort`` that these upstreams reject;
* all other patch entries and non-``zcode-*`` DSH providers are preserved;
* every ``zcode-*`` route carries the module-level ``RETRY_POLICY`` (429
  fast-fail: one short retry for SERVER/TIMEOUT/TRANSPORT/EMPTY_RESPONSE only),
  so the daily 12:00 sync regenerates it instead of wiping a hand edit.

The patch never contains a key. The gateway key is written to DSH's managed
credential store under ``ZCODE_GATEWAY_KEY`` (read from ZCode's provider config).

Usage
-----
    python tools/dsh_sync.py            # dry run, print the projected routes
    python tools/dsh_sync.py --apply    # backup + write patch and credential ref
    python tools/dsh_sync.py --check    # exit 1 when DSH is out of date

The tool only touches files under ``$DSH_HOME`` (default ``~/.dsh``); it does
not modify the repository or ZCode's config. DSH hot-reloads the profile patch,
so no restart is needed after a write.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - dependency error path
    sys.exit("dsh_sync.py 需要 PyYAML：python -m pip install pyyaml")

# The daily automation captures stdout; force UTF-8 even when Windows would
# otherwise use the console code page for a redirected pipe.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure") and (_stream.encoding or "").lower() not in {"utf-8", "utf8"}:
        _stream.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
EFFECTIVE_SCRIPT = REPO / "providers" / "workbuddy" / "zcode_effective_body.js"
ZCODE_CONFIG = Path(
    os.environ.get(
        "ZCODE_PERSONAL_PROVIDER_CONFIG_FILE",
        str(Path.home() / ".zcode" / "v2" / "provider_config.json"),
    )
)
DSH_HOME = Path(os.environ.get("DSH_HOME", str(Path.home() / ".dsh")))
DSH_PROFILE = os.environ.get("DSH_PROFILE", "desktop")
API_KEY_ENV = "ZCODE_GATEWAY_KEY"
DEFAULT_BASE = "http://127.0.0.1:7871/v1"
DSH_LEVELS = {"off", "minimal", "low", "medium", "high", "xhigh", "max"}
# 源头 map 里出现 reasoning_effort，才代表上游真吃 OpenAI 风格档位字段
_USES_EFFORT_FIELD = re.compile(r"reasoning_effort")
KNOWN_PROVIDER_IDS = {
    "opencode-go-chat": "zcode-main",
    "opencode-go-chat-free": "zcode-free",
    "opencode-go-chat-fast": "zcode-saver",
}

# 429 快速失败：默认 llm-retry 会给 RATE_LIMIT 重试 5 次、退避上限 10s，
# 上游额度类 6004 在重置墙钟之前一直失败，重试只会把一次失败放大成 5/5。
# 其余错误（502/超时/传输抖动/空响应）保留一次短重试。
RETRY_POLICY: dict[str, Any] = {
    "mode": "normal",
    "maxRetries": 1,
    "retryableCodes": ["EMPTY_RESPONSE", "SERVER", "TIMEOUT", "TRANSPORT"],
    "backoff": {
        "initialDelayMs": 500,
        "maxDelayMs": 3000,
        "jitterRatio": 0.1,
    },
}


class DshSyncError(RuntimeError):
    """A configuration or filesystem problem the caller should report."""


class _BlockLoader(yaml.SafeLoader):
    """SafeLoader that tolerates Cordis ``!!js`` values inside the block."""


def _construct_js(loader: yaml.Loader, node: yaml.Node) -> Any:
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_mapping(node)


for _tag in ("!js", "tag:yaml.org,2002:js"):
    _BlockLoader.add_constructor(_tag, _construct_js)


def _load_yaml(text: str) -> Any:
    return yaml.load(text, Loader=_BlockLoader)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DshSyncError(f"找不到 ZCode 配置：{path}") from exc
    except json.JSONDecodeError as exc:
        raise DshSyncError(f"ZCode 配置不是合法 JSON：{path}（{exc}）") from exc


def _zcode_providers(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        config = cfg["config"]
        rules = {
            r["providerId"]: r
            for r in config["providerConfigRules"]["providerRules"]
        }
        order = config.get("providerOrder") or list(rules)
    except (KeyError, TypeError) as exc:
        raise DshSyncError("ZCode 配置缺少 config.providerConfigRules.providerRules") from exc

    providers: list[dict[str, Any]] = []
    for provider_id in order:
        rule = rules.get(provider_id)
        if not rule:
            raise DshSyncError(f"providerOrder 里的 {provider_id} 没有对应 providerRule")
        pcfg = rule.get("config") or {}
        ids = pcfg.get("modelOrder") or pcfg.get("personalModelIds") or []
        ids = [str(mid) for mid in ids if str(mid).strip()]
        if not ids:
            continue
        providers.append(
            {
                "providerId": provider_id,
                "providerName": rule.get("providerName") or provider_id,
                "modelIds": ids,
                "baseUrl": (pcfg.get("api") or {}).get("baseUrl") or DEFAULT_BASE,
                "apiKey": (pcfg.get("access") or {}).get("apiKey") or "",
            }
        )
    if not providers:
        raise DshSyncError("ZCode 配置里没有任何含模型的 provider")
    return providers


def _effective_metadata(model_ids: list[str]) -> dict[str, Any]:
    """Read the resolved model metadata; fall back to provider_config on failure."""
    if not model_ids:
        return {}
    node = shutil.which("node")
    if not node or not EFFECTIVE_SCRIPT.exists():
        print("WARN: 找不到 node 或 zcode_effective_body.js，改用 provider_config 元数据", file=sys.stderr)
        return {}
    try:
        proc = subprocess.run(
            [node, str(EFFECTIVE_SCRIPT), *model_ids],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"WARN: zcode_effective_body.js 执行失败，改用 provider_config 元数据：{exc}", file=sys.stderr)
        return {}
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip().splitlines()[-1:] or ["unknown error"]
        print(f"WARN: zcode_effective_body.js 退出码 {proc.returncode}，改用 provider_config 元数据：{detail[0]}", file=sys.stderr)
        return {}
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        print(f"WARN: zcode_effective_body.js 输出不是 JSON，改用 provider_config 元数据：{exc}", file=sys.stderr)
        return {}
    return data if isinstance(data, dict) else {}


def _efforts_outside(values: list[Any]) -> list[str]:
    """档位里 DSH 表达不了的部分。

    DSH 的 reasoningEfforts 是 dict（键 = 发给客户端的档位名），重复键会在落盘时
    互相覆盖，所以源头出现重复档位（disabled 与 off 都是「关」）时只保留一个。
    """
    clean = [str(v) for v in values if isinstance(v, str)]
    return [v for v in dict.fromkeys(clean) if v not in DSH_LEVELS and v != "disabled"]


def _efforts_lost(rules: dict[tuple[str, str], dict[str, Any]], routes: dict[str, Any]) -> list[str]:
    """源头有档位、投影后却没有的模型 —— 每日同步的回归守门。

    ZCode 配置是档位的唯一正本；DSH 侧只是投影。投影把一条非空档位写成空，用户
    看到的是「模型选择器里的推理等级突然消失」，而且没有任何报错。所以这里把两边
    对一遍，漂移就返回明细，由 --check 判失败、由 --apply 打 WARN。

    只报「源头非空、投影为空」：反过来（源头退化但 DSH 还留着）由
    ``_keep_efforts`` 兜着，属于正常保留，不算漂移。
    """
    projected: dict[str, list[Any]] = {}
    for route in routes.values():
        for model in route.get("models") or []:
            if isinstance(model, dict):
                projected[str(model.get("id"))] = model.get("reasoningEfforts") or []
    lost: list[str] = []
    for (provider_id, model_id), rule in rules.items():
        source = ((rule.get("optionSpecs") or {}).get("reasoningLevel") or {})
        values = [str(v) for v in (source.get("values") or []) if isinstance(v, str)]
        if not values:
            continue
        if not projected.get(str(model_id)):
            lost.append(f"{provider_id}/{model_id}（源头 {len(values)} 档 → 投影无档位）")
    return lost


def _model_rules(cfg: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    try:
        rules = cfg["config"]["modelConfigRules"]["providerModelRules"]
    except (KeyError, TypeError):
        return {}
    return {
        (str(r.get("providerId")), str(r.get("modelId"))): r.get("config") or {}
        for r in rules
        if isinstance(r, dict)
    }


def _fallback_meta(rule: dict[str, Any]) -> dict[str, Any]:
    props = rule.get("properties") or {}
    opts = rule.get("optionSpecs") or {}
    inp = props.get("inputFormat") or {}
    max_out = (opts.get("maxOutputTokens") or {}).get("max")
    rl = opts.get("reasoningLevel") or {}
    return {
        "contextWindow": props.get("contextWindow"),
        "maxTokens": max_out,
        "supportsImage": bool(inp.get("supportsImage")),
        "reasoningValues": rl.get("values") or [],
        "reasoningMap": rl.get("map"),
    }


def _metadata_for(model_id: str, effective: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    eff = effective.get(model_id) or {}
    econf = eff.get("config") or {}
    props = econf.get("properties") or {}
    opts = econf.get("optionSpecs") or {}
    inp = props.get("inputFormat") or {}
    e_rl = opts.get("reasoningLevel") or {}
    values = e_rl.get("values")
    map_expr = e_rl.get("map")
    if values is None:
        values = fallback.get("reasoningValues") or []
    if map_expr is None:
        map_expr = fallback.get("reasoningMap")
    return {
        "contextWindow": props.get("contextWindow") if props.get("contextWindow") is not None else fallback.get("contextWindow"),
        "maxTokens": (opts.get("maxOutputTokens") or {}).get("max") if (opts.get("maxOutputTokens") or {}).get("max") is not None else fallback.get("maxTokens"),
        "supportsImage": bool(inp.get("supportsImage")) if props.get("inputFormat") is not None else bool(fallback.get("supportsImage")),
        "reasoningValues": values or [],
        "reasoningMap": map_expr,
    }


def _reasoning(values: list[Any], map_expr: Any) -> dict[str, Any]:
    """Map ZCode's effective reasoning rule to llm-pi-ai's schema."""
    if map_expr is not None and str(map_expr).strip() == "{}":
        return {}
    clean = [str(v) for v in values if isinstance(v, str)]
    levels = [v for v in clean if v in DSH_LEVELS and v != "off"]
    if "disabled" in clean:
        efforts: dict[str, str] = {"off": "disabled"}
        for level in levels:
            efforts[level] = level
        if not any(key != "off" for key in efforts):
            efforts["high"] = "high"
        out: dict[str, Any] = {"reasoningEfforts": efforts}
        # thinkingFormat 只在源头真的用 reasoning_effort 协议时才声明。
        # Gemini 系（thinking_budget / reasoningLevel）和「只有开关」的模型套上
        # deepseek 格式会发出上游不认的字段，档位看着有、实际不生效。
        if _USES_EFFORT_FIELD.search(str(map_expr or "")):
            out["compat"] = {"thinkingFormat": "deepseek"}
        return out
    efforts = {level: level for level in levels}
    if not efforts:
        return {}
    out: dict[str, Any] = {"reasoningEfforts": efforts}
    if _USES_EFFORT_FIELD.search(str(map_expr or "")):
        out["compat"] = {"thinkingFormat": "deepseek"}
    return out


def _positive_int(value: Any) -> int | None:
    return value if isinstance(value, int) and value > 0 else None


def _build_route(provider: dict[str, Any], effective: dict[str, Any], rules: dict[tuple[str, str], dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    provider_id = provider["providerId"]
    dsh_id = KNOWN_PROVIDER_IDS.get(provider_id)
    if not dsh_id:
        slug = re.sub(r"[^a-z0-9]+", "-", provider_id.lower()).strip("-")
        dsh_id = "zcode-" + (slug or "group")
    models: list[dict[str, Any]] = []
    for model_id in provider["modelIds"]:
        meta = _metadata_for(
            model_id,
            effective,
            _fallback_meta(rules.get((provider_id, model_id), {})),
        )
        model: dict[str, Any] = {"id": model_id}
        ctx = _positive_int(meta.get("contextWindow"))
        max_out = _positive_int(meta.get("maxTokens"))
        if ctx:
            model["contextWindow"] = ctx
        if max_out:
            model["maxTokens"] = max_out
        model["input"] = ["text", "image"] if meta.get("supportsImage") else ["text"]
        model.update(_reasoning(meta.get("reasoningValues") or [], meta.get("reasoningMap")))
        models.append(model)
    route = {
        "displayName": provider["providerName"],
        # 每条 zcode-* route 独立拷贝，避免改一条污染常量或其它 route。
        "retryPolicy": copy.deepcopy(RETRY_POLICY),
        "api": "openai-completions",
        "baseURL": provider["baseUrl"] or DEFAULT_BASE,
        "apiKeyEnv": API_KEY_ENV,
        "models": models,
    }
    return dsh_id, route


class _PatchDoc:
    """Text-level access to the one top-level ``llm-pi-ai`` patch entry."""

    def __init__(self, text: str):
        self.text = text
        self.start: int | None = None
        self.end: int | None = None
        match = re.search(r"(?m)^-\s*id:\s*['\"]?llm-pi-ai['\"]?\s*(?:#.*)?$", text)
        if match:
            self.start = match.start()
            tail = text[match.end() :]
            nxt = re.search(r"(?m)^-\s", tail)
            self.end = match.end() + nxt.start() if nxt else len(text)

    @property
    def exists(self) -> bool:
        return self.start is not None

    def item(self) -> dict[str, Any]:
        if not self.exists:
            return {}
        block = self.text[self.start : self.end]
        try:
            parsed = _load_yaml(block)
        except yaml.YAMLError as exc:
            raise DshSyncError(f"现有 llm-pi-ai 段不是合法 YAML：{exc}") from exc
        if not isinstance(parsed, list) or not parsed or not isinstance(parsed[0], dict):
            raise DshSyncError("现有 llm-pi-ai 段不是预期的单条 patch 条目")
        return parsed[0]

    def replace(self, item: dict[str, Any]) -> str:
        block = yaml.safe_dump(
            [item],
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            width=120,
        ).rstrip() + "\n"
        if not self.exists:
            return self.text.rstrip() + "\n\n" + block
        before = self.text[: self.start].rstrip()
        after = self.text[self.end :].lstrip("\n")
        return (before + "\n\n" if before else "") + block + ("\n" + after if after else "")


def _keep_efforts(routes: dict[str, Any], old_providers: dict[str, Any]) -> dict[str, Any]:
    """把现有 patch 里手写/人工调过的 reasoningEfforts 保留到新生成的路由上。

    ZCode 源头的 optionSpecs 缺失或退化（map="{}"、只留开关）时，生成器只能写出
    空档位；这些档位一旦被 --apply 抹掉，模型选择器里的推理等级就消失。规则：
      - 新路由没算出 reasoningEfforts → 沿用旧的；
      - 新路由算出了 → 以新路由为准（源头改档位时能被正确更新）。
    """
    kept: dict[str, Any] = {}
    for provider_key, new_route in routes.items():
        old_route = old_providers.get(provider_key) or {}
        if not isinstance(new_route, dict) or not isinstance(old_route, dict):
            continue
        old_models = {
            m.get("id"): m
            for m in (old_route.get("models") or [])
            if isinstance(m, dict) and m.get("id")
        }
        for model in new_route.get("models") or []:
            if not isinstance(model, dict) or model.get("reasoningEfforts"):
                continue
            old_model = old_models.get(model.get("id"))
            if not old_model or not old_model.get("reasoningEfforts"):
                continue
            model["reasoningEfforts"] = old_model["reasoningEfforts"]
            if old_model.get("compat"):
                model["compat"] = old_model["compat"]
            kept[model.get("id")] = model["reasoningEfforts"]
    if kept:
        print("保留已有推理档位：" + ", ".join(sorted(str(k) for k in kept)))
    return routes


def _merge_patch(text: str, routes: dict[str, Any]) -> tuple[str, bool, dict[str, Any]]:
    doc = _PatchDoc(text)
    old_item = doc.item()
    old_config = old_item.get("config") or {}
    old_providers = old_config.get("providers") or {}
    routes = _keep_efforts(routes, old_providers)
    preserved = {
        key: value
        for key, value in old_providers.items()
        if not str(key).startswith("zcode-")
    }
    merged_providers = {**routes, **preserved}
    new_item = dict(old_item) if old_item else {"id": "llm-pi-ai"}
    new_item["id"] = "llm-pi-ai"
    new_config = dict(old_config)
    new_config["providers"] = merged_providers
    new_item["config"] = new_config
    if old_item == new_item:
        return text, False, new_item
    return doc.replace(new_item), True, new_item


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp-dshsync")
    tmp.write_text(text, encoding="utf-8")
    last: Exception | None = None
    for attempt in range(3):
        try:
            os.replace(tmp, path)
            return
        except PermissionError as exc:
            last = exc
            if attempt < 2:
                time.sleep(0.5)
    tmp.unlink(missing_ok=True)
    assert last is not None
    raise DshSyncError(f"写入被拒绝：{path}（{last}）")


def _backup(path: Path) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(path.name + ".bak-dshsync-" + stamp)
    counter = 2
    while backup.exists():
        backup = path.with_name(path.name + f".bak-dshsync-{stamp}-{counter}")
        counter += 1
    shutil.copy2(path, backup)
    return backup


def _quote_scalar(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def _update_credentials_text(text: str, key: str) -> str:
    """Surgically set refs.ZCODE_GATEWAY_KEY, preserving annotations elsewhere."""
    refs = re.search(r"(?m)^refs:\s*(?:#.*)?$", text)
    if refs:
        tail = text[refs.end() :]
        nxt = re.search(r"(?m)^\S", tail)
        block_end = refs.end() + nxt.start() if nxt else len(text)
        block = text[refs.end() : block_end]
        line = re.search(r"(?m)^(\s+)ZCODE_GATEWAY_KEY:\s*.*$", block)
        if line:
            new_block = block[: line.start()] + line.group(1) + "ZCODE_GATEWAY_KEY: " + _quote_scalar(key) + block[line.end() :]
        else:
            new_block = "\n  ZCODE_GATEWAY_KEY: " + _quote_scalar(key) + block
        return text[: refs.end()] + new_block + text[block_end:]
    return text.rstrip() + "\n\nrefs:\n  ZCODE_GATEWAY_KEY: " + _quote_scalar(key) + "\n"


def _credentials_state(path: Path, patch_key: str | None, apply: bool) -> tuple[bool, Path | None]:
    if not path.exists():
        raise DshSyncError(f"找不到 DSH 凭据文件：{path}")
    text = path.read_text(encoding="utf-8")
    try:
        parsed = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise DshSyncError(f"DSH 凭据文件不是合法 YAML：{exc}") from exc
    refs = parsed.get("refs") if isinstance(parsed, dict) else None
    current = refs.get(API_KEY_ENV) if isinstance(refs, dict) else None
    if not patch_key:
        raise DshSyncError("ZCode provider 配置里没有 gateway apiKey，无法写 DSH 凭据引用")
    if current == patch_key:
        return False, None
    if not apply:
        return True, None
    backup = _backup(path)
    _atomic_write(path, _update_credentials_text(text, patch_key))
    return True, backup


def _route_summary(routes: dict[str, Any]) -> str:
    return "；".join(
        f"{route['displayName']} {len(route['models'])}"
        for route in routes.values()
    )


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="同步 ZCode 最终模型到 DeepSeekRuntime llm-pi-ai")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="备份并写入 DSH patch 与凭据引用")
    mode.add_argument("--check", action="store_true", help="只检测漂移；有漂移退出码 1")
    parser.add_argument("--dsh-home", type=Path, default=DSH_HOME, help="DSH_HOME（默认 ~/.dsh）")
    parser.add_argument("--profile", default=DSH_PROFILE, help="DSH profile（默认 desktop）")
    parser.add_argument("--config", type=Path, default=ZCODE_CONFIG, help="ZCode provider_config.json")
    args = parser.parse_args(argv)

    patch_path = args.dsh_home / "profiles" / args.profile / "cordis.patch.yml"
    if not patch_path.exists():
        raise DshSyncError(f"找不到 DSH profile patch：{patch_path}")

    cfg = _read_json(args.config)
    providers = _zcode_providers(cfg)
    model_ids = list(dict.fromkeys(mid for p in providers for mid in p["modelIds"]))
    effective = _effective_metadata(model_ids)
    rules = _model_rules(cfg)
    routes: dict[str, Any] = {}
    for provider in providers:
        dsh_id, route = _build_route(provider, effective, rules)
        if dsh_id in routes:
            raise DshSyncError(f"DSH provider id 冲突：{dsh_id}")
        routes[dsh_id] = route

    old_text = patch_path.read_text(encoding="utf-8")
    new_text, changed, item = _merge_patch(old_text, routes)
    patch_key = providers[0]["apiKey"]
    key_changed, cred_backup = _credentials_state(
        args.dsh_home / ".credentials.yaml", patch_key, args.apply
    )

    print(f"ZCode      : {len(providers)} 个 provider / {sum(len(p['modelIds']) for p in providers)} 个模型")
    print(f"DSH 路由   : {_route_summary(routes)}")
    print(f"patch      : {patch_path}")
    print(f"模型表     : {'有变化' if changed else '无变化'}；凭据引用：{'有变化' if key_changed else '无变化'}")

    lost = _efforts_lost(rules, routes)
    if lost:
        print(f"推理档位 : {len(lost)} 个模型投影后为空", file=sys.stderr)
        for line in lost:
            print(f"  - {line}", file=sys.stderr)

    if args.check:
        return 1 if (changed or key_changed or lost) else 0
    if not args.apply:
        # 把投影后的 providers 打出来，定时任务的日志里能直接看到 429 策略。
        print("retryPolicy（模块级常量）: " + json.dumps(RETRY_POLICY, ensure_ascii=False))
        print("--- 投影后的 providers（dry-run，不写入）---")
        print(
            yaml.safe_dump(
                (item.get("config") or {}).get("providers") or {},
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
                width=120,
            ).rstrip()
        )
        print("--- end ---")
        print("dry-run：加 --apply 才会写入")
        return 0

    if changed:
        backup = _backup(patch_path)
        _atomic_write(patch_path, new_text)
        print(f"已写入 patch（备份：{backup.name}）")
    if cred_backup is not None:
        print(f"已更新凭据引用（备份：{cred_backup.name}）")
    if not changed and not key_changed:
        print("DeepSeekHarness 同步：无变化")
    elif lost:
        print("WARN: 上面列出的模型在源头有档位、投影后为空，检查 _reasoning 与 map 表达式")
    else:
        print(f"DeepSeekHarness 同步：{len(routes)} 个 provider / {sum(len(r['models']) for r in routes.values())} 个模型")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(_main())
    except DshSyncError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
