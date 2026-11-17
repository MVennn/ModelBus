#!/usr/bin/env python3
"""模型隐藏名单：把模型 / provider 从宿主投影里藏起来，源配置一条都不删。

隐藏不是删除。名单只影响投影（tools/dsh_sync.py 写 DSH 的 cordis.patch.yml），
~/.zcode/v2/provider_config.json 里的 provider、personalModelIds / modelOrder、
alias map 全部原样保留。恢复就是把名字从名单里拿掉再投影一次 —— 没有一条
配置需要重建。

正本文件：~/.zcode/v2/model-hidden.json（本机状态，不进仓库，可用环境变量
MODEL_HIDDEN_FILE 覆盖）：

    {
      "version": 1,
      "updatedAt": "2026-11-17T23:58:00+08:00",
      "providers": {"opencode-go-chat-fast": {"reason": "...", "at": "..."}},
      "models": {"DeepSeek-4.1-Flash-OC": {"reason": "...", "at": "...", "channel": "OC"}}
    }

用法：

    python tools/model_visibility.py list
    python tools/model_visibility.py hide --channel OC --reason "OC 暂停续费"
    python tools/model_visibility.py hide --model DeepSeek-4.1-Flash-OC Beam
    python tools/model_visibility.py hide --provider opencode-go-chat-free
    python tools/model_visibility.py show --channel OC
    python tools/model_visibility.py show --all

改完名单默认立刻重投影（dsh_sync.py --apply，DSH 热加载 profile patch）；
--no-sync 只改名单，--dry-run 连名单都不写。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure") and (_stream.encoding or "").lower() not in {"utf-8", "utf8"}:
        _stream.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
HIDDEN_FILE = Path(
    os.environ.get("MODEL_HIDDEN_FILE", str(Path.home() / ".zcode" / "v2" / "model-hidden.json"))
)
ALIAS_MAP = Path(
    os.environ.get("UNIFIED_MODEL_MAP", str(Path.home() / ".zcode" / "v2" / "model-alias-map.json"))
)
ZCODE_CONFIG = Path(
    os.environ.get(
        "ZCODE_PERSONAL_PROVIDER_CONFIG_FILE",
        str(Path.home() / ".zcode" / "v2" / "provider_config.json"),
    )
)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z") or time.strftime("%Y-%m-%dT%H:%M:%S")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return doc if isinstance(doc, dict) else {}


def load_state(path: Path | None = None) -> dict[str, Any]:
    """读名单；缺失或损坏时返回空名单（投影照常，不阻断）。"""
    path = path or HIDDEN_FILE
    doc = _read_json(path)
    providers = doc.get("providers") if isinstance(doc.get("providers"), dict) else {}
    models = doc.get("models") if isinstance(doc.get("models"), dict) else {}
    return {
        "version": 1,
        "updatedAt": str(doc.get("updatedAt") or ""),
        "providers": {str(k): v for k, v in providers.items()},
        "models": {str(k): v for k, v in models.items()},
    }


def save_state(state: dict[str, Any], path: Path | None = None) -> Path:
    path = path or HIDDEN_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    state["version"] = 1
    state["updatedAt"] = _now()
    text = json.dumps(state, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    if path.exists():
        backup = path.with_name(path.name + ".bak")
        try:
            backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        except OSError:
            pass
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
    return path


def model_channels(path: Path | None = None) -> dict[str, str]:
    """alias map -> {型号: 主渠道}。只读显示字段，不参与投影决策。"""
    doc = _read_json(path or ALIAS_MAP)
    out: dict[str, str] = {}
    for model_id, row in (doc.get("models") or {}).items():
        if isinstance(row, dict) and row.get("channel"):
            out[str(model_id)] = str(row["channel"])
    return out


def provider_groups(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """provider_config -> {providerId: {name, models}}（源真值，不受名单影响）。"""
    doc = _read_json(path or ZCODE_CONFIG)
    try:
        cfg = doc["config"]
        rules = {r["providerId"]: r for r in cfg["providerConfigRules"]["providerRules"]}
        order = cfg.get("providerOrder") or list(rules)
    except (KeyError, TypeError):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for pid in order:
        rule = rules.get(pid) or {}
        pcfg = rule.get("config") or {}
        ids = pcfg.get("modelOrder") or pcfg.get("personalModelIds") or []
        out[str(pid)] = {
            "name": str(rule.get("providerName") or pid),
            "models": [str(m) for m in ids],
        }
    return out


def _entry(reason: str, channel: str | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {"reason": reason or "", "at": _now()}
    if channel:
        row["channel"] = channel
    return row


def _resolve_by_channel(channels: list[str]) -> list[str]:
    wanted = {c.upper() for c in channels}
    chans = model_channels()
    return sorted(mid for mid, ch in chans.items() if ch.upper() in wanted)


def _visible_summary(state: dict[str, Any]) -> list[str]:
    groups = provider_groups()
    hidden_models = set(state["models"])
    hidden_providers = set(state["providers"])
    lines: list[str] = []
    for pid, row in groups.items():
        if pid in hidden_providers:
            lines.append(f"  {row['name']}({pid}) 整组隐藏（源 {len(row['models'])} 个）")
            continue
        visible = [m for m in row["models"] if m not in hidden_models]
        hidden = [m for m in row["models"] if m in hidden_models]
        head = f"  {row['name']}({pid}) 可见 {len(visible)}/{len(row['models'])}"
        lines.append(head + (f"｜隐藏：{'、'.join(hidden)}" if hidden else ""))
    return lines


def cmd_list(args: argparse.Namespace) -> int:
    state = load_state()
    chans = model_channels()
    if args.json:
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    print(f"隐藏名单：{HIDDEN_FILE}")
    if not state["models"] and not state["providers"]:
        print("名单为空：所有模型都在投影里。")
        return 0
    if state["models"]:
        print(f"已隐藏型号 {len(state['models'])} 个：")
        for mid in sorted(state["models"]):
            row = state["models"][mid] if isinstance(state["models"][mid], dict) else {}
            ch = row.get("channel") or chans.get(mid) or "-"
            print(f"  {mid}  [{ch}]  {row.get('reason') or ''}  {row.get('at') or ''}".rstrip())
    if state["providers"]:
        print(f"已隐藏 provider {len(state['providers'])} 个：")
        for pid in sorted(state["providers"]):
            row = state["providers"][pid] if isinstance(state["providers"][pid], dict) else {}
            print(f"  {pid}  {row.get('reason') or ''}  {row.get('at') or ''}".rstrip())
    print("投影现状（源配置里的分组 / 隐藏后仍可见）：")
    for line in _visible_summary(state):
        print(line)
    print("恢复：python tools/model_visibility.py show --all")
    return 0


def cmd_hide(args: argparse.Namespace) -> int:
    state = load_state()
    chans = model_channels()
    models: dict[str, str | None] = {}
    if args.channel:
        picked = _resolve_by_channel(args.channel)
        if not picked:
            print(f"ERROR: alias map 里没有主渠道为 {args.channel} 的型号", file=sys.stderr)
            return 2
        for mid in picked:
            models[mid] = chans.get(mid)
    for mid in args.model or []:
        models[str(mid)] = chans.get(str(mid))
    providers = [str(p) for p in (args.provider or [])]
    if not models and not providers:
        print("ERROR: 至少给 --model / --provider / --channel 之一", file=sys.stderr)
        return 2
    # 名字打错时会「静默生效」：名单写了、投影没变，用户以为藏好了。所以对不上就喊一声。
    groups = provider_groups()
    if groups:
        known = {mid for row in groups.values() for mid in row["models"]} | set(chans)
        for mid in sorted(m for m in models if m not in known):
            print(f"WARN: alias map / provider_config 里都查不到型号 {mid}，仍写进名单", file=sys.stderr)
        for pid in sorted(p for p in providers if p not in groups):
            print(f"WARN: 没有 providerId {pid}，仍写进名单", file=sys.stderr)
    for mid, ch in models.items():
        state["models"][mid] = _entry(args.reason, ch)
    for pid in providers:
        state["providers"][pid] = _entry(args.reason)
    print(f"本次隐藏：型号 {len(models)} 个 / provider {len(providers)} 个"
          + (f"（理由：{args.reason}）" if args.reason else ""))
    if models:
        print("  型号：" + "、".join(sorted(models)))
    if providers:
        print("  provider：" + "、".join(sorted(providers)))
    if args.dry_run:
        print("dry-run：名单未写入")
        return 0
    path = save_state(state)
    print(f"已写入名单：{path}")
    return _sync(args)


def cmd_show(args: argparse.Namespace) -> int:
    state = load_state()
    chans = model_channels()
    removed_models: list[str] = []
    removed_providers: list[str] = []
    if args.all:
        removed_models = sorted(state["models"])
        removed_providers = sorted(state["providers"])
        state["models"].clear()
        state["providers"].clear()
    else:
        matchers = set()
        if args.channel:
            wanted = {c.upper() for c in args.channel}
            for mid, row in state["models"].items():
                row_ch = row.get("channel") if isinstance(row, dict) else None
                if str(row_ch or chans.get(mid) or "").upper() in wanted:
                    matchers.add(mid)
        matchers.update(str(m) for m in (args.model or []))
        for mid in sorted(matchers):
            if mid in state["models"]:
                state["models"].pop(mid)
                removed_models.append(mid)
        for pid in [str(p) for p in (args.provider or [])]:
            if pid in state["providers"]:
                state["providers"].pop(pid)
                removed_providers.append(pid)
        if not matchers and not (args.provider or []):
            print("ERROR: 至少给 --model / --provider / --channel 或 --all", file=sys.stderr)
            return 2
    print(f"本次恢复：型号 {len(removed_models)} 个 / provider {len(removed_providers)} 个")
    if removed_models:
        print("  型号：" + "、".join(removed_models))
    if removed_providers:
        print("  provider：" + "、".join(removed_providers))
    if not removed_models and not removed_providers:
        print("名单里没有这些条目，无需改动")
        return 0
    if args.dry_run:
        print("dry-run：名单未写入")
        return 0
    path = save_state(state)
    print(f"已写入名单：{path}")
    return _sync(args)


def _sync(args: argparse.Namespace) -> int:
    if getattr(args, "no_sync", False):
        print("--no-sync：名单已改，投影未动；需要时手动跑 python tools/dsh_sync.py --apply")
        return 0
    script = HERE / "dsh_sync.py"
    print(f"重投影：{script} --apply")
    code = subprocess.call([sys.executable, str(script), "--apply"], cwd=str(REPO))
    if code != 0:
        print(f"WARN: dsh_sync.py 退出码 {code}，投影未完成", file=sys.stderr)
    return 0 if code == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="模型隐藏名单：藏起型号 / provider，源配置一条不删（恢复只需 show）"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="看当前隐藏了什么、投影里还剩什么")
    p_list.add_argument("--json", action="store_true", help="输出名单原始 JSON")
    p_list.set_defaults(func=cmd_list)

    def add_write_flags(p: argparse.ArgumentParser) -> None:
        p.add_argument("--model", nargs="+", metavar="ID", help="型号 id（可多个）")
        p.add_argument("--provider", nargs="+", metavar="ID", help="providerId（整组，可多个）")
        p.add_argument("--channel", nargs="+", metavar="CH", help="按 alias map 主渠道选型号：OC / WB / GM / QD ...")
        p.add_argument("--reason", default="", help="写进名单的理由（以后看得懂）")
        p.add_argument("--no-sync", action="store_true", help="只改名单，不重投影")
        p.add_argument("--dry-run", action="store_true", help="只打印，不写名单")

    p_hide = sub.add_parser("hide", help="隐藏型号 / provider（不删除）")
    add_write_flags(p_hide)
    p_hide.set_defaults(func=cmd_hide)

    p_show = sub.add_parser("show", help="恢复隐藏的型号 / provider")
    add_write_flags(p_show)
    p_show.add_argument("--all", action="store_true", help="清空整份名单")
    p_show.set_defaults(func=cmd_show)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
