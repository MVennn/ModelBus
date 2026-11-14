"""ModelBus 控制台 · 唯一写面。

> 一句话：只允许把 POST /admin/reload 转发给网关，其他动作一律不落地。

不重启进程、不写配置、不碰凭据；每次动作留一条内存态记录供页面回看。
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import sources

_STATE = {"running": False, "history": []}
_LOCK = threading.Lock()
_HISTORY_MAX = 20


def jobs():
    with _LOCK:
        return {"running": _STATE["running"],
                "history": list(reversed(_STATE["history"][-_HISTORY_MAX:])),
                "allowed": ["reload"]}


def reload_gateway():
    """转发网关热重载；网关自身负责重新读配置，控制台不碰文件。"""
    with _LOCK:
        if _STATE["running"]:
            raise sources.SourceError("JOB_BUSY", "reload already running")
        _STATE["running"] = True
    entry = {"action": "reload", "at": datetime.now().astimezone().isoformat(timespec="seconds")}
    try:
        # 网关管理面要求 X-Zgate-Admin（挡住浏览器跨站表单）；配了 adminToken
        # 的话再从环境变量带口令，控制台不把口令写进代码。
        headers = {"Content-Type": "application/json",
                   "Accept": "application/json",
                   "X-Zgate-Admin": "1"}
        token = os.environ.get("ZGATE_ADMIN_TOKEN", "").strip()
        if token:
            headers["X-Zgate-Token"] = token
        req = Request(sources.GATEWAY + "/admin/reload", data=b"{}", method="POST",
                      headers=headers)
        with urlopen(req, timeout=10) as resp:
            raw = resp.read(65536).decode("utf-8", "replace")
            entry["status"] = resp.status
            try:
                entry["response"] = sources.scrub(json.loads(raw))
            except json.JSONDecodeError:
                entry["response"] = sources._clip(raw, 300)
        entry["ok"] = 200 <= entry["status"] < 300
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        entry["ok"] = False
        entry["status"] = getattr(exc, "code", 0)
        entry["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        with _LOCK:
            _STATE["running"] = False
            _STATE["history"].append(entry)
            del _STATE["history"][:-_HISTORY_MAX]
    return entry
