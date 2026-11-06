#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""同步报告：对比上一次快照，写出本次模型清单的变化，并可选提交推送。

用法：
    python tools/sync_report.py                      # 只打印摘要（dry run）
    python tools/sync_report.py --write              # 写报告 + 更新索引 + 存快照
    python tools/sync_report.py --write --push       # 再 git add/commit/push

状态文件默认 `~/.zcode/v2/model-sync-state.json`，记录上一轮的
「显示名 → 分组 / 最低价 / 链路」。第一次运行没有状态时写一份基线报告。

自动化里放在最后一步（model_alias.py --apply 之后）：
    python tools/sync_report.py --write --push
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT_DIR = ROOT / "docs" / "reports"
INDEX_NAME = "README.md"
REPO_URL = "https://github.com/MVennn/ModelBus/blob/main/docs/reports"

# 两个可选输入由 model_alias.py 那一侧写。本脚本是自动化的最后一步，
# 少一个文件只该少一段正文，不能把整轮同步判成失败。
SCORES_FILE = Path.home() / ".zcode" / "v2" / "model-scores.json"
QUOTA_FILE = Path.home() / ".zcode" / "v2" / "quota-windows.json"

# 阈值与 model_alias.py 的 SCORE_MIN_INTEL / SCORE_MIN_VALUE 同口径：
# 报告和生成器必须挑中同一批「不划算」的模型，否则两边给出相反结论。
SCORE_MIN_INTEL = 85.0
SCORE_MIN_VALUE = 1.0
DRIFT_MAX_ROWS = 10
QUOTA_WARN_DAYS = 30


def config_path(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    env = os.environ.get("ZCODE_PERSONAL_PROVIDER_CONFIG_FILE")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".zcode" / "v2" / "provider_config.json"


def alias_path(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    env = os.environ.get("UNIFIED_MODEL_MAP")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".zcode" / "v2" / "model-alias-map.json"


def state_path(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    return Path.home() / ".zcode" / "v2" / "model-sync-state.json"


def load_groups(cfg_path: Path) -> dict[str, str]:
    """显示名 → 组名（主力 / 免费 / 低耗 / 高耗）。"""
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    rules = (((cfg.get("config") or {}).get("providerConfigRules") or {}).get("providerRules") or [])
    for rule in rules:
        name = str(rule.get("providerName") or "")
        for model in (rule.get("config") or {}).get("personalModelIds") or []:
            out[str(model)] = name
    return out


def snapshot(alias_file: Path, cfg_path: Path) -> dict:
    data = json.loads(alias_file.read_text(encoding="utf-8"))
    groups = load_groups(cfg_path)
    models: dict[str, dict] = {}
    for name, entry in (data.get("models") or {}).items():
        chain = entry.get("chain") or []
        if chain:
            hops = [f"{h.get('channel')}:{h.get('upstream')}@{h.get('price')}" for h in chain]
        else:
            hops = [f"{entry.get('channel')}:{entry.get('upstream')}@{entry.get('price')}"]
        models[name] = {
            "group": groups.get(name, entry.get("group") or ""),
            "price": entry.get("price"),
            "chain": hops,
        }
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "alias_generated_at": data.get("generated_at"),
        "models": models,
    }


def diff(previous: dict, current: dict) -> dict:
    old = previous.get("models") or {}
    new = current.get("models") or {}
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    group_changed = []
    chain_changed = []
    for name in sorted(set(new) & set(old)):
        if new[name].get("group") != old[name].get("group"):
            group_changed.append((name, old[name].get("group"), new[name].get("group")))
        if new[name].get("chain") != old[name].get("chain"):
            chain_changed.append((name, old[name].get("chain"), new[name].get("chain")))
    return {
        "added": added,
        "removed": removed,
        "group_changed": group_changed,
        "chain_changed": chain_changed,
    }


# 分组名与 model_alias.PROVIDER_NAMES 保持一致（主力/免费/省钱）。
# 2026-11-06 之前这里是主力/免费/低耗/高耗四个组名，后两个在生成器里根本不存在，导致 10 条省钱组模型在概览里凭空消失、合计 9≠19。
GROUP_NAMES = ("主力", "免费", "省钱")


def load_optional(path: Path) -> dict | None:
    """读可选输入；文件缺失、内容坏掉都返回 None，由调用方整段跳过。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _num(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt(value: float | None, digits: int = 2) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def _days(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def name_index(models: dict) -> dict[str, str]:
    """scores 的键是 `CHANNEL|upstream`，这里反查回显示名；查不到就照原键打印。"""
    out: dict[str, str] = {}
    for display, entry in models.items():
        for hop in entry.get("chain") or []:
            pair = str(hop).rsplit("@", 1)[0]
            if ":" in pair:
                channel, _, upstream = pair.partition(":")
                # 分隔符两种写法都认：scores 用 CHANNEL|upstream，链路串用 CHANNEL:upstream
                out.setdefault(f"{channel}|{upstream}", display)
                out.setdefault(pair, display)
    return out


def score_entries(scores: dict) -> dict:
    """两种落盘形状都认：直接平铺，或包在 models 下（现网 model-scores.json 是后者）。

    上游换个包装就整段空白，比多写四行判空更糟。
    """
    nested = scores.get("models")
    if isinstance(nested, dict) and nested:
        return nested
    return scores


def render_score_drift(models: dict, scores: dict | None) -> list[str] | None:
    """性价比漂移：只列 intel 偏低或 value 偏低的那一侧，其余不占版面。

    免费条目 value 为 null，没有性价比可谈，直接跳过而不是当成 0 ——
    否则整段免费模型会刷屏，把真正变差的付费条目挤掉。
    """
    if scores is None:
        return None
    names = name_index(models)
    rows: list[tuple[float, float, str, float | None, float | None, str]] = []
    for key, item in score_entries(scores).items():
        if not isinstance(item, dict) or item.get("value") is None:
            continue
        intel = _num(item.get("intel"))
        value = _num(item.get("value"))
        low_intel = intel is not None and intel < SCORE_MIN_INTEL
        low_value = value is not None and value < SCORE_MIN_VALUE
        if not (low_intel or low_value):
            continue
        rows.append((
            value if value is not None else float("inf"),
            intel if intel is not None else float("inf"),
            names.get(str(key), str(key)), intel, value,
            str(item.get("basis") or "-"),
        ))
    if not rows:
        return ["（无）"]
    rows.sort(key=lambda row: (row[0], row[1]))
    body = ["| 显示名 | intel | value | basis |", "|---|---|---|---|"]
    for _, _, name, intel, value, basis in rows[:DRIFT_MAX_ROWS]:
        # 反查不到显示名时打印的是 CHANNEL|upstream，竖线必须转义否则整行表格错列
        cell = name.replace("|", "\\|")
        body.append(f"| `{cell}` | {_fmt(intel, 1)} | {_fmt(value)} | {basis} |")
    if len(rows) > DRIFT_MAX_ROWS:
        body += ["", f"…另 {len(rows) - DRIFT_MAX_ROWS} 条"]
    # 条目自己不带 basis 时把整份分数的标定基准挂到表下，免得每一行都是 "-"
    anchor = scores.get("basis")
    if isinstance(anchor, dict):
        parts = [str(anchor[key]) for key in ("source", "model") if anchor.get(key)]
        if parts:
            body += ["", f"基准：{' / '.join(parts)}"]
    return body


def render_quota_windows(quota: dict | None) -> list[str] | None:
    """额度窗口：只列 30 天内到期和已经过期的，远期窗口不占版面。

    days_left 由写入方算好，这里不重新计时 —— 报告是快照，
    重算会让同一份报告在不同时间重跑出不同内容。
    """
    if quota is None:
        return None
    windows = quota.get("windows")
    if not isinstance(windows, list):
        return ["（无）"]
    rows = []
    for item in windows:
        if not isinstance(item, dict):
            continue
        days = _num(item.get("days_left"))
        if days is not None:
            rows.append((days, item))
    rows.sort(key=lambda row: row[0])
    body: list[str] = []
    for days, item in rows:
        channel = str(item.get("channel") or "-")
        until = str(item.get("until") or "-")
        note = str(item.get("note") or "").strip()
        if days < 0:
            line = f"- ❌ **{channel}** 已于 {until} 过期（超期 {_days(-days)} 天）"
        elif days <= QUOTA_WARN_DAYS:
            line = f"- ⚠️ **{channel}** 剩 {_days(days)} 天（{until}）"
        else:
            continue
        body.append(line + (f" —— {note}" if note else ""))
    return body or ["（无）"]


def render_report(current: dict, changes: dict, baseline: bool,
                  scores: dict | None = None, quota: dict | None = None) -> str:
    models = current["models"]
    groups = GROUP_NAMES
    counts = {g: sum(1 for m in models.values() if m.get("group") == g) for g in groups}
    stamp = current["generated_at"]
    added = 0 if baseline else len(changes["added"])
    removed = 0 if baseline else len(changes["removed"])

    lines = [
        f"# 模型同步报告 {stamp[:16]}",
        "",
        f"> **一句话**：本次自动化后的模型清单 —— 共 {len(models)} 个，"
        f"新增 {added}、移除 {removed}、"
        f"分组变化 {len(changes['group_changed'])}、链路变化 {len(changes['chain_changed'])}"
        + ("（首次运行，作为基线）" if baseline else "") + "。",
        "",
        "## 概览",
        "",
        "| 组 | 数量 |",
        "|---|---|",
    ]
    for group in groups:
        lines.append(f"| {group} | {counts[group]} |")
    other = sum(1 for m in models.values() if m.get("group") not in groups)
    if other:
        # 兜底：生成器加了新分组却没人改这份清单时，宁可显式暴露也不静默吞掉
        lines.append(f"| 其他（未在 GROUP_NAMES 登记） | {other} |")
    total = sum(counts.values()) + other
    lines += ["", f"合计 {total} / 清单 {len(models)}"
              + ("" if total == len(models) else " ⚠️ 对不上，检查 GROUP_NAMES"), ""]
    lines += [f"生成时间：{stamp}；alias map：{current.get('alias_generated_at') or '-'}", ""]

    if baseline:
        lines += ["## 基线", "", "首次生成，没有上一轮快照可比；当前清单见文末。", ""]
    else:
        lines += ["## 新增", ""]
        if changes["added"]:
            lines += ["| 名称 | 组 | 最低价 |", "|---|---|---|"]
            for name in changes["added"]:
                entry = models[name]
                lines.append(f"| `{name}` | {entry.get('group')} | {entry.get('price')} |")
        else:
            lines.append("（无）")
        lines += ["", "## 移除", ""]
        lines += [f"- `{name}`" for name in changes["removed"]] or ["（无）"]
        lines += ["", "## 分组变化", ""]
        if changes["group_changed"]:
            lines += ["| 名称 | 原分组 | 新分组 |", "|---|---|---|"]
            for name, before, after in changes["group_changed"]:
                lines.append(f"| `{name}` | {before} | {after} |")
        else:
            lines.append("（无）")
        lines += ["", "## 链路变化", ""]
        if changes["chain_changed"]:
            for name, before, after in changes["chain_changed"]:
                lines.append(f"- `{name}`")
                lines.append(f"  - 原：{' → '.join(before or ['-'])}")
                lines.append(f"  - 新：{' → '.join(after or ['-'])}")
        else:
            lines.append("（无）")
        lines.append("")

    lines += ["## 当前清单", "", "| 名称 | 组 | 最低价 | 链路（按尝试顺序） |", "|---|---|---|---|"]
    for name in sorted(models):
        entry = models[name]
        chain = " → ".join(entry.get("chain") or [])
        lines.append(f"| `{name}` | {entry.get('group')} | {entry.get('price')} | {chain} |")
    lines.append("")

    # 可选段放在正文末尾：文件不在时整段消失，上面的分组统计与概览不受影响
    drift = render_score_drift(models, scores)
    if drift is not None:
        lines += ["### 性价比漂移", ""] + drift + [""]
    windows = render_quota_windows(quota)
    if windows is not None:
        lines += ["### 额度窗口", ""] + windows + [""]
    return "\n".join(lines)


def update_index(report_name: str, current: dict, changes: dict, baseline: bool) -> None:
    index = REPORT_DIR / INDEX_NAME
    if index.exists():
        text = index.read_text(encoding="utf-8")
    else:
        text = (
            "# 模型同步报告索引\n\n"
            "> **一句话**：每次自动化结束后的模型清单快照与变化记录，最新的在最上面。\n\n"
            "| 时间 | 报告 | 总数 | 新增 | 移除 |\n|---|---|---|---|---|\n"
        )
    row = (
        f"| {current['generated_at'][:16]} | [{report_name}]({report_name}) | "
        f"{len(current['models'])} | {0 if baseline else len(changes['added'])} | "
        f"{0 if baseline else len(changes['removed'])} |\n"
    )
    header, _, rest = text.partition("|---|---|---|---|---|\n")
    if not rest:
        text = text.rstrip() + "\n" + row
    else:
        text = header + "|---|---|---|---|---|\n" + row + rest
    index.write_text(text, encoding="utf-8")


def git_push(report_name: str, out_dir: Path = REPORT_DIR) -> int:
    def run(args: list[str]) -> int:
        proc = subprocess.run(args, cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True)
        if proc.returncode != 0:
            print(proc.stdout.strip())
            print(proc.stderr.strip(), file=sys.stderr)
        return proc.returncode

    # 推送前门禁：自动同步历史上把本机绝对路径写进 evidence/ 分片并直接 push，
    # CI 的「敏感信息扫描」连续三次因此红。这里在 add/commit/push 之前堵住。
    gate = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "check-secrets.py")],
        cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True)
    if gate.returncode != 0:
        print(gate.stdout.strip())
        print(gate.stderr.strip(), file=sys.stderr)
        print("敏感信息门禁未通过，已终止自动提交与推送", file=sys.stderr)
        return gate.returncode

    # Commit the directory the report was actually written to: with
    # --out-dir the fixed "docs/reports" add staged nothing and git reported
    # "nothing to commit" as success.
    try:
        rel_dir = out_dir.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        print(f"报告目录 {out_dir} 不在仓库内，无法自动提交", file=sys.stderr)
        return 1
    if run(["git", "add", rel_dir]) != 0:
        return 1
    if run(["git", "commit", "-m", f"docs(reports): 模型同步报告 {report_name}"]) != 0:
        # Nothing to commit is not a failure for the automation.
        status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, text=True, capture_output=True)
        if status.stdout.strip():
            return 1
        print("没有需要提交的变更")
        return 0
    return run(["git", "push", "origin", "HEAD"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help="写报告、更新索引并保存快照")
    parser.add_argument("--push", action="store_true", help="写完以后 git add/commit/push（需要 --write）")
    parser.add_argument("--config", help="provider_config.json 路径")
    parser.add_argument("--alias-map", help="model-alias-map.json 路径")
    parser.add_argument("--state", help="上一轮快照路径（默认 ~/.zcode/v2/model-sync-state.json）")
    parser.add_argument("--out-dir", help="报告目录（默认 docs/reports）")
    args = parser.parse_args()

    current = snapshot(alias_path(args.alias_map), config_path(args.config))
    spath = state_path(args.state)
    baseline = not spath.exists()
    previous = {} if baseline else json.loads(spath.read_text(encoding="utf-8"))
    changes = diff(previous, current)

    print(f"模型 {len(current['models'])} 个"
          "（" + " / ".join(
              f"{g} {sum(1 for m in current['models'].values() if m['group'] == g)}"
              for g in GROUP_NAMES
          ) + "）")
    if baseline:
        print("首次运行：本次作为基线，没有可比的变化")
    else:
        print(f"新增 {len(changes['added'])}：{', '.join(changes['added']) or '无'}")
        print(f"移除 {len(changes['removed'])}：{', '.join(changes['removed']) or '无'}")
        for name, before, after in changes["group_changed"]:
            print(f"分组变化：{name} {before} → {after}")
        print(f"链路变化 {len(changes['chain_changed'])}：{', '.join(n for n, _, _ in changes['chain_changed']) or '无'}")

    if not args.write:
        print("dry run；加 --write 生成报告并保存快照")
        return 0

    out_dir = Path(args.out_dir).expanduser() if args.out_dir else REPORT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"MODEL-SYNC-{datetime.now().strftime('%Y%m%d-%H%M')}.md"
    scores = load_optional(SCORES_FILE)
    quota = load_optional(QUOTA_FILE)
    (out_dir / name).write_text(
        render_report(current, changes, baseline, scores, quota), encoding="utf-8")
    if out_dir == REPORT_DIR:
        update_index(name, current, changes, baseline)
    spath.parent.mkdir(parents=True, exist_ok=True)
    spath.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已写入 {out_dir / name}")

    if args.push:
        code = git_push(name, out_dir)
        print("已推送" if code == 0 else "推送失败（见上面的 git 输出）")
        return code
    return 0


if __name__ == "__main__":
    sys.exit(main())
