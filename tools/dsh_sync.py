#!/usr/bin/env python3
"""Project the host's final model groups into DeepSeekRuntime's llm-pi-ai profile.

The daily model sync writes the compatibility projection ``~/.zcode/v2/provider_config.json`` through
``tools/model_alias.py``. This tool reads that final state and rewrites only
the ``llm-pi-ai`` entry in ``~/.dsh/profiles/<profile>/cordis.patch.yml``:

* every provider in the active source becomes a DSH route (``opencode-go-chat`` -> ``zcode-main``,
  ``...-free`` -> ``zcode-free``, ``...-fast`` -> ``zcode-saver``);
* providers / models named in ``~/.zcode/v2/model-hidden.json`` are left out of the
  projection only. ``tools/model_visibility.py`` maintains that list; the source
  config keeps every definition, so showing them again is one command (hide != delete);
* model order, context window, output cap, image input and reasoning levels are
  copied from the resolved host metadata (``effective_body.js``);
* Models whose effective ``reasoningLevel.map`` is ``{}`` deliberately
  get no ``reasoningEfforts``, because DSH would otherwise send a
  ``reasoning_effort`` that these upstreams reject;
* all other patch entries and non-``zcode-*`` DSH providers are preserved;
* every ``zcode-*`` route carries the module-level ``RETRY_POLICY`` (429
  fast-fail: one short retry for SERVER/TIMEOUT/TRANSPORT/EMPTY_RESPONSE only),
  so the daily 12:00 sync regenerates it instead of wiping a hand edit.

The patch never contains a key. The gateway key is written to DSH's managed
credential store under ``ZCODE_GATEWAY_KEY`` (read from the active source's provider config).

Usage
-----
    python tools/dsh_sync.py            # dry run, print the projected routes
    python tools/dsh_sync.py --apply    # backup + write patch and credential ref
    python tools/dsh_sync.py --check    # exit 1 when DSH is out of date
    python tools/dsh_sync.py --export-inventory ~/.dsh/profiles/desktop/modelbus-inventory.json
    python tools/dsh_sync.py --source dsh               # DSH 清单 + catalog 能力真值
    python tools/dsh_sync.py --source dsh --apply       # 按 DSH 真源写 patch
    # --source compat（默认）与改造前逐字节一致；--source dsh 不读 ~/.zcode/v2/。

The tool only touches files under ``$DSH_HOME`` (default ``~/.dsh``); it does
not modify the repository or the compatibility projection's config. DSH hot-reloads the profile patch,
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
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import model_alias  # noqa: E402  （隐藏名单解析的唯一实现，见 hidden_sets）
REPO = HERE.parent
EFFECTIVE_SCRIPT = REPO / "providers" / "workbuddy" / "effective_body.js"
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
# 默认推理档的选择顺序（低→高）；off 不作为默认档。
_LEVEL_ESCALATION = ["minimal", "low", "medium", "high", "xhigh", "max"]
# 上一轮投影到 DSH 的型号清单（只用来报「这次少了谁」，不是配置来源）
DSH_LEDGER = DSH_HOME / "profiles" / DSH_PROFILE / "zcode-model-ledger.json"
# DSH 原生真源：DSH 侧清单 + catalog 能力真值（--source dsh，默认仍走 compat）
CATALOG = REPO / "catalog" / "model_caps.json"
DSH_INVENTORY = DSH_HOME / "profiles" / DSH_PROFILE / "modelbus-inventory.json"
INVENTORY_SCHEMA = "modelbus-inventory/v1"
# alias map：model_alias.py 写盘时给每条写入 displayName（可撞、去后缀的显示名）。
# dsh_sync 读它把显示名投影成 DSH models[].name，让界面显示名与内部调用 id 分离。
# 与 model_alias.alias_path 同口径：UNIFIED_MODEL_MAP env 可覆盖。
ALIAS_MAP = Path(
    os.environ.get("UNIFIED_MODEL_MAP", str(Path.home() / ".zcode" / "v2" / "model-alias-map.json"))
)
# 源头 map 里出现 reasoning_effort，才代表上游真吃 OpenAI 风格档位字段
_USES_EFFORT_FIELD = re.compile(r"reasoning_effort")
# 手配档位白名单：这些模型的推理档位由 patch 人工维护，不随宿主 catalog 覆盖。
# 当前为空（Gemini-4-Hydrogen 已随 odyfree 线路移除）。
HANDSET_EFFORTS: set = set()
# provider 级默认档目标（2026-11-19 用户定）：组内共同档低于它时抬到这一档，
# 缺这一档的模型用 wire 别名补齐；不再按「并列取低、省思考开销」的旧口径。
DEFAULT_EFFORT_TARGET = "high"
KNOWN_PROVIDER_IDS = {
    "opencode-go-chat": "zcode-main",
    "opencode-go-chat-free": "zcode-free",
    "opencode-go-chat-fast": "zcode-saver",
}
# 隐藏名单（本机状态，不进仓库）：tools/model_visibility.py 维护。
# 只影响 DSH 投影，provider_config.json / alias map 里的定义一条不删 ——
# 隐藏不是删除，恢复就是把名字从名单里拿掉再投一次影。
# 2026-11-17 起用于「OC 暂停续费时整条线先藏起来」。
HIDDEN_FILE = Path(
    os.environ.get("MODEL_HIDDEN_FILE", str(Path.home() / ".zcode" / "v2" / "model-hidden.json"))
)

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

# PyYAML 默认按 YAML 1.1 布尔表解析：裸 off/on/yes/no 都会读成布尔。DSH 客户端用
# js-yaml（YAML 1.2）整体重写 profile patch 时会把 'off' 的引号去掉，这里再读一次就
# 成了 {False: False}，safe_dump 回写成 false: false —— llm-pi-ai 的 zod 只认
# false 或 7 个档位名，整份 providers 配置随之失效，设置页报
# reasoningEfforts expected false | {...} but got {"false":false,...} 并拒绝保存，
# 连新建供应商都点不下去（2026-11-19 实况）。这里把布尔表裁到 1.2 口径，
# 与 js-yaml 对齐，只认 true/false 两种拼写。
_BOOL_YAML12 = re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$")
_BlockLoader.yaml_implicit_resolvers = {
    key: [(tag, rx) for tag, rx in resolvers if tag != "tag:yaml.org,2002:bool"]
    for key, resolvers in _BlockLoader.yaml_implicit_resolvers.items()
}
_BlockLoader.add_implicit_resolver("tag:yaml.org,2002:bool", _BOOL_YAML12, list("tTfF"))


def _load_yaml(text: str) -> Any:
    return yaml.load(text, Loader=_BlockLoader)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DshSyncError(f"找不到 ZCode 配置：{path}") from exc
    except json.JSONDecodeError as exc:
        raise DshSyncError(f"ZCode 配置不是合法 JSON：{path}（{exc}）") from exc


def _display_names_from_alias_map(path: Path) -> dict[str, str]:
    """读 alias map 的 {唯一代号 new_id: 显示名 displayName}，供 DSH models[].name 投影。

    model_alias.py 写盘时给每条写入 displayName（去后缀、可撞的族名），键是唯一代号。
    读不到 / 字段缺失时降级空字典，绝不阻断投影：name 缺省时 DSH fallback 到 id，
    界面行为与改造前一致。
    """
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    out: dict[str, str] = {}
    models = doc.get("models") if isinstance(doc, dict) else None
    for model_id, row in (models or {}).items():
        if not isinstance(row, dict):
            continue
        name = row.get("displayName")
        if isinstance(name, str) and name:
            out[str(model_id)] = name
    return out


def _previous_model_ids(provider_id: str) -> list[str]:
    """上一次投影到 DSH 的该 provider 型号清单（用于报「这次少了谁」）。"""
    path = DSH_LEDGER
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    entry = (data.get("providers") or {}).get(provider_id) or {}
    return [str(mid) for mid in entry.get("modelIds") or []]


def _remember_model_ids(snapshot: list[dict[str, Any]]) -> None:
    """把本次投影结果记下来，供下一轮算差值。"""
    payload = {"providers": {p["providerId"]: {"modelIds": p["modelIds"]} for p in snapshot}}
    try:
        DSH_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        DSH_LEDGER.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"WARN: 投影账本写入失败：{exc}", file=sys.stderr)


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
        # 2026-11-11：上一版投影出去、这一版配置里已经消失的型号必须显式报出来。
        # 用户侧看到的是模型选择器里少了一条，或者（更糟）DSH 会话直接硬失败
        # 「provider "zcode-main" has no configured model "<某型号>"」——
        # 清单是这份配置投影的，缺型号不会降级。静默少一条是这个故障最难查的地方，
        # 所以投影到 DSH 的这条路径上必须留一行字。
        dropped = [mid for mid in _previous_model_ids(provider_id) if mid not in ids]
        if dropped:
            print(
                f"WARN: {provider_id} 投影到 DSH 时移除了 {len(dropped)} 个上次还在的型号："
                + "、".join(dropped),
                file=sys.stderr,
            )
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


def _hidden_sets() -> tuple[set[str], set[str]]:
    """读隐藏名单 -> (providerIds, 型号 ids)。

    解析只留一份实现：tools/model_alias.py 的 hidden_sets()。ZCode 兼容投影与
    DSH 投影读同一份名单，两边不会因为解析差异对不上。缺失 / 损坏 / 不是对象
    一律退化为空集合：隐藏是可选层，绝不能因为它读不出来就把整条投影打断。
    """
    return model_alias.hidden_sets(HIDDEN_FILE)


def _apply_hidden(
    providers: list[dict[str, Any]], hidden_providers: set[str], hidden_models: set[str]
) -> list[dict[str, Any]]:
    """按名单过滤「投影用」的 provider / 型号；源配置原样保留。"""
    if not hidden_providers and not hidden_models:
        return providers
    kept: list[dict[str, Any]] = []
    dropped = 0
    for provider in providers:
        pid = provider["providerId"]
        if pid in hidden_providers:
            print(f"隐藏：整组 {pid}（{provider['providerName']}，{len(provider['modelIds'])} 个型号）")
            continue
        ids = [mid for mid in provider["modelIds"] if mid not in hidden_models]
        dropped += len(provider["modelIds"]) - len(ids)
        if not ids:
            print(f"隐藏：{pid} 的型号全部在名单里，跳过该组")
            continue
        kept.append({**provider, "modelIds": ids})
    if dropped:
        # 路径只在 _main 里报一次：_apply_hidden 被测试直接调用时，不该把本机
        # 真实名单路径混进 fixture 测试的输出里（看起来像测试被污染）。
        print(f"隐藏：{dropped} 个型号不投影")
    if not kept:
        raise DshSyncError(
            f"隐藏名单把全部 provider 都藏起来了，DSH 会没有任何 zcode-* 路由：{HIDDEN_FILE}"
        )
    return kept


def _effective_metadata(model_ids: list[str]) -> dict[str, Any]:
    """Read the resolved model metadata; fall back to provider_config on failure."""
    if not model_ids:
        return {}
    node = shutil.which("node")
    if not node or not EFFECTIVE_SCRIPT.exists():
        print("WARN: 找不到 node 或 effective_body.js，改用 provider_config 元数据", file=sys.stderr)
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
        print(f"WARN: effective_body.js 执行失败，改用 provider_config 元数据：{exc}", file=sys.stderr)
        return {}
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip().splitlines()[-1:] or ["unknown error"]
        print(f"WARN: effective_body.js 退出码 {proc.returncode}，改用 provider_config 元数据：{detail[0]}", file=sys.stderr)
        return {}
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        print(f"WARN: effective_body.js 输出不是 JSON，改用 provider_config 元数据：{exc}", file=sys.stderr)
        return {}
    return data if isinstance(data, dict) else {}


def _efforts_outside(values: list[Any]) -> list[str]:
    """档位里 DSH 表达不了的部分。

    DSH 的 reasoningEfforts 是 dict（键 = 发给客户端的档位名），重复键会在落盘时
    互相覆盖，所以源头出现重复档位（disabled 与 off 都是「关」）时只保留一个。
    """
    clean = [str(v) for v in values if isinstance(v, str)]
    return [v for v in dict.fromkeys(clean) if v not in DSH_LEVELS and v != "disabled"]


def _efforts_lost(
    rules: dict[tuple[str, str], dict[str, Any]],
    routes: dict[str, Any],
    hidden_models: set[str] | frozenset[str] = frozenset(),
    hidden_providers: set[str] | frozenset[str] = frozenset(),
) -> list[str]:
    """源头有档位、投影后却没有的模型 —— 每日同步的回归守门。

    当前真源（compat=兼容投影配置 / dsh=catalog 能力真值）是档位的唯一正本；DSH 侧只是投影。投影把一条非空档位写成空，用户
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
        # 被隐藏的型号本来就不该出现在投影里，不能算漂移 —— 否则 --check 永远
        # 报 1、每日同步白跑一轮 --apply，还天天打一行 WARN。
        if model_id in hidden_models or provider_id in hidden_providers:
            continue
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
    """Map the host's effective reasoning rule to llm-pi-ai's schema."""
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


def _shared_default_effort(models: list[dict[str, Any]]) -> str | None:
    """组内所有模型共同支持的最高推理档，作为 provider 级默认档。

    llm-pi-ai 的 profile.reasoning 既是 UI 选择器的 defaultEffort 来源，也是
    请求未声明档位时的 dispatch 兜底档。因此只能取“整组都支持”的档：
    若并存只支持 high 与只支持 medium 的模型，一刀切会让后者在 dispatch
    阶段抛 UNSUPPORTED_REASONING_EFFORT，这时宁可不设（UI 退回 provider default）。
    """
    shared: set[str] | None = None
    for model in models:
        efforts = model.get("reasoningEfforts")
        if not isinstance(efforts, dict):
            return None
        levels = {k for k in efforts if k in _LEVEL_ESCALATION}
        shared = levels if shared is None else shared & levels
        if not shared:
            return None
    if not shared:
        return None
    for level in reversed(_LEVEL_ESCALATION):
        if level in shared:
            return level
    return None


def _apply_default_effort(models: list[dict[str, Any]]) -> str | None:
    """为整组挑一个 provider 级默认档，必要时给个别模型注入 wire 别名。

    llm-pi-ai 的 profile.reasoning 同时驱动两处：
      * UI 选择器的 defaultEffort —— describableReasoningLevel 对模型不支持的
        档静默降级，于是显示 "Default" 伪档；
      * 请求兜底档 —— resolveReasoningLevel 对不支持的档直接抛
        UNSUPPORTED_REASONING_EFFORT。
    所以整组必须有一个「每个模型都支持」的默认档。策略（2026-11-19 用户定）：
    默认一律抬到 DEFAULT_EFFORT_TARGET（high）——
      * 共同档已达目标：直接用共同最高档，不注入任何别名；
      * 目标档至少一个模型支持：用目标档，给缺该档的模型注入一条 wire 别名
        （档名 -> 该模型真实支持的最高档 wire 值），让 UI 与请求都走同一个档名，
        实际发给上游的仍是模型支持的 wire 值；
      * 目标档没有模型支持：退回共同档，再退回覆盖面最广的档。
    """
    shared = _shared_default_effort(models)
    reasoning_models = [m for m in models if isinstance(m.get("reasoningEfforts"), dict)]
    if not reasoning_models:
        return shared

    target = DEFAULT_EFFORT_TARGET
    target_rank = _LEVEL_ESCALATION.index(target) if target in _LEVEL_ESCALATION else None

    # 1. 共同档已经不低于目标：直接用共同最高档，不注入任何别名。
    if shared is not None and (
        target_rank is None or _LEVEL_ESCALATION.index(shared) >= target_rank
    ):
        return shared

    # 2. 挑默认档：目标档优先，没人支持时退回共同档 / 覆盖面最广的档。
    if target_rank is not None and any(target in m["reasoningEfforts"] for m in reasoning_models):
        best = target
    elif shared is not None:
        best = shared
    else:
        counts = {lv: 0 for lv in _LEVEL_ESCALATION}
        for m in reasoning_models:
            for lv in _LEVEL_ESCALATION:
                if lv in m["reasoningEfforts"]:
                    counts[lv] += 1
        best = max(_LEVEL_ESCALATION, key=lambda lv: (counts[lv], -_LEVEL_ESCALATION.index(lv)))
        if counts[best] == 0:
            return None

    # 3. 给不支持 best 的模型补别名：best -> 它真实支持的最高档 wire 值。
    for m in models:
        efforts = m.get("reasoningEfforts")
        if not isinstance(efforts, dict) or best in efforts:
            continue
        wire = None
        for lv in reversed(_LEVEL_ESCALATION):
            if lv in efforts and isinstance(efforts[lv], str):
                wire = efforts[lv]
                break
        if wire is not None:
            efforts[best] = wire
    return best


def _positive_int(value: Any) -> int | None:
    return value if isinstance(value, int) and value > 0 else None


def _build_route(provider: dict[str, Any], effective: dict[str, Any], rules: dict[tuple[str, str], dict[str, Any]], display_names: dict[str, str] | None = None) -> tuple[str, dict[str, Any]]:
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
        # 显示名（可撞、去后缀）投影：id 仍是唯一代号，name 只影响界面显示。
        # alias map 没这条 displayName 时不写 name，DSH fallback 到 id（行为不变）。
        _display = (display_names or {}).get(model_id)
        if _display:
            model["name"] = _display
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
    # provider 级默认档 → llm-pi-ai 的 reasoningInfo() 生成 defaultEffort，
    # UI 模型选择器据此显示真实档名而不是 "Default" 伪档。
    default_effort = _apply_default_effort(models)
    if default_effort is not None:
        route["reasoning"] = default_effort
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


def _efforts_schema_ok(efforts: Any) -> bool:
    """llm-pi-ai 的 reasoningEfforts 只吃 false 或档位名到字符串的映射。

    档位名限定 DSH_LEVELS 七档；任何别的东西（典型：PyYAML 把裸 off 读成布尔后
    回写的 false: false 键值）都会让宿主前端拒绝保存整份 providers 配置，
    所以这种值一概不沿用。
    """
    if efforts is False:
        return True
    if not isinstance(efforts, dict):
        return False
    return all(
        isinstance(level, str) and level in DSH_LEVELS and isinstance(wire, str)
        for level, wire in efforts.items()
    )


def _keep_efforts(routes: dict[str, Any], old_providers: dict[str, Any]) -> dict[str, Any]:
    """把现有 patch 里手写/人工调过的 reasoningEfforts 保留到新生成的路由上。

    真源的 optionSpecs 缺失或退化（map="{}"、只留开关）时，生成器只能写出
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
            if not isinstance(model, dict):
                continue
            mid = model.get("id")
            # 源头算出档位且不在手配白名单 → 以源头为准；白名单模型始终沿用 patch 手配档位
            if model.get("reasoningEfforts") and mid not in HANDSET_EFFORTS:
                continue
            old_model = old_models.get(mid)
            if not old_model or not old_model.get("reasoningEfforts"):
                continue
            if not _efforts_schema_ok(old_model["reasoningEfforts"]):
                print(
                    f"警告：{mid} 的 reasoningEfforts 不符合 llm-pi-ai schema"
                    f"（{old_model['reasoningEfforts']!r}），不沿用、按源头重算"
                )
                continue
            model["reasoningEfforts"] = old_model["reasoningEfforts"]
            if old_model.get("compat"):
                model["compat"] = old_model["compat"]
            kept[mid] = model["reasoningEfforts"]
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



# --- DSH 原生真源（--source dsh）-------------------------------------------
# 默认 --source compat 与改造前逐字节一致：仍读兼容投影最终态。
# --source dsh 把分组/型号/顺序真源迁到 DSH 侧清单，能力真值来自 catalog，
# 各类 agent（会话 / 子代理 / headless / 服务插件）不再依赖 ZCode 客户端配置。

def _catalog_capabilities() -> dict[str, dict[str, Any]]:
    """catalog/model_caps.json -> {display: 归一化能力字段}。

    catalog 是各类 agent 共用的唯一能力真源；这里只做字段改名，绝不拿它的
    键集合去裁现网型号全集（少一条就会让 DSH 会话硬失败）。
    """
    try:
        doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in doc.get("models") or []:
        if not isinstance(row, dict) or not row.get("display"):
            continue
        caps: dict[str, Any] = {}
        if row.get("context_window") is not None:
            caps["contextWindow"] = row["context_window"]
        if row.get("max_output_tokens") is not None:
            caps["maxTokens"] = row["max_output_tokens"]
        if row.get("supports_image") is not None:
            caps["supportsImage"] = bool(row["supports_image"])
        if row.get("reasoning_values") is not None:
            caps["reasoningValues"] = row["reasoning_values"]
        if row.get("reasoning_map") is not None:
            caps["reasoningMap"] = row["reasoning_map"]
        out[str(row["display"])] = caps
    return out


def _read_inventory(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DshSyncError(f"找不到 DSH 清单：{path}（先用 --export-inventory 导出）") from exc
    except json.JSONDecodeError as exc:
        raise DshSyncError(f"DSH 清单不是合法 JSON：{path}（{exc}）") from exc
    if not isinstance(doc, dict) or doc.get("schema") != INVENTORY_SCHEMA:
        raise DshSyncError(f"DSH 清单 schema 不是 {INVENTORY_SCHEMA}：{path}")
    return doc


def _dsh_providers(inv: dict[str, Any]) -> list[dict[str, Any]]:
    """DSH 侧清单 -> providers。型号全集 / 顺序 / baseUrl 全来自 DSH 真源。"""
    rows = inv.get("providers")
    if not isinstance(rows, list) or not rows:
        raise DshSyncError("DSH 清单里没有 providers")
    providers: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("providerId"):
            raise DshSyncError("DSH 清单 providers 条目缺少 providerId")
        ids = [str(m) for m in row.get("modelIds") or [] if str(m).strip()]
        if not ids:
            continue
        providers.append(
            {
                "providerId": str(row["providerId"]),
                "providerName": row.get("providerName") or str(row["providerId"]),
                "modelIds": ids,
                "baseUrl": row.get("baseUrl") or DEFAULT_BASE,
                "apiKey": "",
            }
        )
    if not providers:
        raise DshSyncError("DSH 清单里没有任何含模型的 provider")
    return providers


def _inventory_rules(inv: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for key, value in (inv.get("modelRules") or {}).items():
        pid, sep, mid = str(key).partition("::")
        if sep and isinstance(value, dict):
            out[(pid, mid)] = value
    return out


def _inventory_effective(inv: dict[str, Any]) -> dict[str, Any]:
    """清单能力快照；声明了 catalog 真源时，只覆盖 catalog 命中的型号。"""
    effective = {
        str(k): v for k, v in (inv.get("effective") or {}).items() if isinstance(v, dict)
    }
    if inv.get("capabilities_source") != "catalog/model_caps.json":
        return effective
    for model_id, cap in _catalog_capabilities().items():
        if model_id not in effective:
            continue
        cfg = dict(effective[model_id].get("config") or {})
        props = dict(cfg.get("properties") or {})
        opts = dict(cfg.get("optionSpecs") or {})
        inp = dict(props.get("inputFormat") or {})
        rl = dict(opts.get("reasoningLevel") or {})
        if "contextWindow" in cap:
            props["contextWindow"] = cap["contextWindow"]
        if "maxTokens" in cap:
            opts["maxOutputTokens"] = dict(opts.get("maxOutputTokens") or {})
            opts["maxOutputTokens"]["max"] = cap["maxTokens"]
        if "supportsImage" in cap:
            inp["supportsImage"] = cap["supportsImage"]
            props["inputFormat"] = inp
        if "reasoningValues" in cap:
            rl["values"] = cap["reasoningValues"]
        if "reasoningMap" in cap:
            rl["map"] = cap["reasoningMap"]
        opts["reasoningLevel"] = rl
        cfg["properties"] = props
        cfg["optionSpecs"] = opts
        effective[model_id] = {**effective[model_id], "config": cfg}
    return effective


def _existing_credential(path: Path) -> str | None:
    """DSH 凭据库里已有的网关 key；dsh 源不读 ZCode 配置也能续用。"""
    try:
        parsed = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (FileNotFoundError, yaml.YAMLError):
        return None
    refs = parsed.get("refs") if isinstance(parsed, dict) else None
    value = refs.get(API_KEY_ENV) if isinstance(refs, dict) else None
    return str(value) if value else None


def _export_inventory(
    cfg: dict[str, Any], path: Path, catalog_caps: bool = True
) -> dict[str, Any]:
    """把 compat 最终态导出成 DSH 侧清单：型号全集不缩水，能力真值取 catalog。"""
    providers = _zcode_providers(cfg)
    ids = list(dict.fromkeys(mid for p in providers for mid in p["modelIds"]))
    inv: dict[str, Any] = {
        "schema": INVENTORY_SCHEMA,
        "generated_by": "tools/dsh_sync.py --export-inventory",
        "source": "dsh",
        "providers": [
            {k: p[k] for k in ("providerId", "providerName", "modelIds", "baseUrl")}
            for p in providers
        ],
        "modelRules": {
            f"{pid}::{mid}": rule for (pid, mid), rule in _model_rules(cfg).items()
        },
        "effective": _effective_metadata(ids),
    }
    if catalog_caps:
        inv["capabilities_source"] = "catalog/model_caps.json"
        inv["effective"] = _inventory_effective(inv)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(inv, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return inv


def _load_source(
    source: str, config_path: Path, inventory_path: Path
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[tuple[str, str], dict[str, Any]]]:
    """compat = 改造前的唯一路径；dsh = DSH 清单 + catalog 能力真值。"""
    if source == "compat":
        cfg = _read_json(config_path)
        providers = _zcode_providers(cfg)
        ids = list(dict.fromkeys(mid for p in providers for mid in p["modelIds"]))
        return providers, _effective_metadata(ids), _model_rules(cfg)
    if source == "dsh":
        inv = _read_inventory(inventory_path)
        return _dsh_providers(inv), _inventory_effective(inv), _inventory_rules(inv)
    raise DshSyncError(f"未知 --source：{source}")


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="同步宿主模型分组到 DeepSeekRuntime llm-pi-ai（默认 compat 行为不变）")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="备份并写入 DSH patch 与凭据引用")
    mode.add_argument("--check", action="store_true", help="只检测漂移；有漂移退出码 1")
    parser.add_argument("--dsh-home", type=Path, default=DSH_HOME, help="DSH_HOME（默认 ~/.dsh）")
    parser.add_argument("--profile", default=DSH_PROFILE, help="DSH profile（默认 desktop）")
    parser.add_argument("--config", type=Path, default=ZCODE_CONFIG, help="compat 源：provider_config.json")
    parser.add_argument("--source", choices=("compat", "dsh"), default="compat",
                        help="真源：compat=兼容投影最终态（默认，行为不变）；dsh=DSH 清单 + catalog 能力真值")
    parser.add_argument("--inventory", type=Path, default=DSH_INVENTORY,
                        help="DSH 侧 modelbus-inventory.json（--source dsh）")
    parser.add_argument("--export-inventory", type=Path, default=None,
                        help="从 compat 最终态导出 DSH 清单后退出（不写 patch / 凭据）")
    parser.add_argument("--no-catalog-caps", action="store_true",
                        help="导出时不把 catalog 能力真值烘进清单（行为等价对照用）")
    args = parser.parse_args(argv)

    if args.export_inventory is not None:
        cfg = _read_json(args.config)
        inv = _export_inventory(cfg, args.export_inventory,
                                catalog_caps=not args.no_catalog_caps)
        rows = inv.get("providers") or []
        model_count = sum(len(p.get("modelIds") or []) for p in rows)
        print(f"已导出 DSH 清单：{args.export_inventory}")
        print(f"provider {len(rows)} 个 / 型号 {model_count} 个")
        return 0

    patch_path = args.dsh_home / "profiles" / args.profile / "cordis.patch.yml"
    if not patch_path.exists():
        raise DshSyncError(f"找不到 DSH profile patch：{patch_path}")

    providers, effective, rules = _load_source(args.source, args.config, args.inventory)
    # 源真值先记下来：下面过滤只影响投影，日志里两者要分开报，否则「源里只有 11 个」会误导。
    source_counts = (len(providers), sum(len(p["modelIds"]) for p in providers))
    # 隐藏名单在两条真源之后统一过滤：源配置 / inventory 都是全集，
    # 「藏起来」只发生在投影这一步（隐藏不是删除）。
    hidden_providers, hidden_models = _hidden_sets()
    if hidden_providers or hidden_models:
        print(
            f"隐藏名单：{HIDDEN_FILE}（provider {len(hidden_providers)} 个 / 型号 "
            f"{len(hidden_models)} 个；恢复用 python tools/model_visibility.py show）"
        )
    providers = _apply_hidden(providers, hidden_providers, hidden_models)
    # 显示名只在 compat 源投影（dsh 源按设计不读 ~/.zcode/v2/）；
    # alias map 缺失 / 无 displayName 时降级空，投影行为与改造前一致。
    display_names = _display_names_from_alias_map(ALIAS_MAP) if args.source == "compat" else {}
    routes: dict[str, Any] = {}
    for provider in providers:
        dsh_id, route = _build_route(provider, effective, rules, display_names)
        if dsh_id in routes:
            raise DshSyncError(f"DSH provider id 冲突：{dsh_id}")
        routes[dsh_id] = route

    old_text = patch_path.read_text(encoding="utf-8")
    new_text, changed, item = _merge_patch(old_text, routes)
    patch_key = (
        providers[0]["apiKey"]
        if args.source == "compat"
        else (os.environ.get(API_KEY_ENV)
              or _existing_credential(args.dsh_home / ".credentials.yaml") or "")
    )
    # --source dsh 不带 apiKey（凭据走 env / DSH 凭据库）；check / dry-run 不该
    # 因凭据库缺 key 直接 exit 2。compat 默认路径行为逐字不变。
    if args.source == "dsh" and not patch_key and not args.apply:
        key_changed, cred_backup = False, None
    else:
        key_changed, cred_backup = _credentials_state(
            args.dsh_home / ".credentials.yaml", patch_key, args.apply
        )

    projected = (len(providers), sum(len(p["modelIds"]) for p in providers))
    hidden_note = "" if projected == source_counts else f"（投影 {projected[0]} 个 / {projected[1]} 个）"
    print(f"Host/Compat: {source_counts[0]} 个 provider / {source_counts[1]} 个模型{hidden_note}")
    print(f"DSH 路由   : {_route_summary(routes)}")
    print(f"patch      : {patch_path}")
    print(f"模型表     : {'有变化' if changed else '无变化'}；凭据引用：{'有变化' if key_changed else '无变化'}")

    if args.apply:
        # 只有真正写进去才更新账本；dry-run/--check 不能把「计划」记成「已投影」。
        _remember_model_ids(providers)

    lost = _efforts_lost(rules, routes, hidden_models, hidden_providers)
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
