"""ModelBus 控制台 · 只读数据层。

> 一句话：把磁盘快照、网关 /health 与日志尾部收敛成脱敏的结构化视图，全程不写文件、不启停任何长驻进程。

纪律：零第三方依赖（Python 3.12 标准库）；大日志一律 tail 流式，禁止整文件读入；
凭据文件只报存在性 / 体积 / 是否配置，值一律不出进程。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
HOME = Path.home()
ZV2 = HOME / ".zcode" / "v2"
LOCALAPP = Path(os.environ.get("LOCALAPPDATA", str(HOME / "AppData" / "Local")))
ZGATE_DIR = LOCALAPP / "ZCodeGateway"
GATEWAY = os.environ.get("MODELBUS_GATEWAY", "http://127.0.0.1:7871").rstrip("/")
REQUEST_LOGS = ROOT / "gateways" / "upstream" / "workbuddy" / "data" / "request-logs"

# 只认「凭据语境」的字段名，不认裸 token：request-logs 里 total_tokens /
# prompt_tokens / completion_tokens / cache_hit_tokens 是业务计量，抹掉会让流量页丢数。
SECRET_NAME = re.compile(
    r"(?i)(access[_-]?token|refresh[_-]?token|id[_-]?token|auth[_-]?token|"
    r"secret|cookie|passwd|password|credential|authorization|api[_-]?key|private|sk-|bearer)"
)
SECRET_VALUE = re.compile(r"(?i)(sk-[A-Za-z0-9_-]{6,}|Bearer\s+[A-Za-z0-9._-]{12,})")
MASK = "<redacted>"


class SourceError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


_CACHE: dict[str, tuple[float, object]] = {}
_CACHE_LOCK = threading.Lock()


def cached(key: str, ttl_ms: int, fn):
    """TTL 缓存：一次刷新里多页取同一源只付一次磁盘 / 网络成本。"""
    now = time.monotonic()
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit is not None and now - hit[0] < ttl_ms / 1000.0:
            return hit[1]
    value = fn()
    with _CACHE_LOCK:
        _CACHE[key] = (time.monotonic(), value)
    return value


def _safe(fn, default):
    try:
        return fn()
    except (SourceError, OSError, ValueError):
        return default


def _load_json(path: Path):
    if not path.is_file():
        raise SourceError("SOURCE_MISSING", f"source missing: {path.name}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceError("PARSE_ERROR", f"{path.name}: {type(exc).__name__}: {exc}") from exc


def _tail_bytes(path: Path, max_bytes: int = 1 << 20) -> str:
    """从尾部读，避免 18 MB stdout 日志 / 6 MB jsonl 整文件进内存。"""
    with path.open("rb") as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        span = min(size, max_bytes)
        fh.seek(size - span)
        raw = fh.read(span)
    if span < size:
        nl = raw.find(b"\n")
        if nl >= 0:
            raw = raw[nl + 1:]
    return raw.decode("utf-8", errors="replace")


def tail_lines(path: Path, limit: int = 200, max_bytes: int = 1 << 20) -> list[str]:
    if not path.is_file():
        raise SourceError("SOURCE_MISSING", f"source missing: {path.name}")
    return [ln for ln in _tail_bytes(path, max_bytes).splitlines() if ln.strip()][-limit:]


def tail_jsonl(path: Path, limit: int = 500, max_bytes: int = 4 << 20) -> list[dict]:
    out = []
    for ln in tail_lines(path, limit, max_bytes):
        try:
            obj = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def scrub(obj):
    """兜底：嵌套结构里命中凭据字段名的键，值直接换成掩码。"""
    if isinstance(obj, dict):
        return {k: (MASK if SECRET_NAME.search(str(k)) else scrub(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub(v) for v in obj]
    if isinstance(obj, str):
        return SECRET_VALUE.sub(MASK, obj)
    return obj


def _clip(value, width: int = 200) -> str:
    return SECRET_VALUE.sub(MASK, str(value or ""))[:width]


def _mask_id(value) -> str:
    s = str(value or "")
    if not s:
        return ""
    if len(s) <= 8:
        return s[:2] + "…"
    return s[:4] + "…" + s[-2:]


def _meta(path: Path) -> dict:
    try:
        st = path.stat()
        return {
            "name": path.name,
            "bytes": st.st_size,
            "mtime": datetime.fromtimestamp(st.st_mtime).astimezone().isoformat(timespec="seconds"),
        }
    except OSError:
        return {"name": path.name, "bytes": 0, "mtime": None}


def _get(path: str, timeout: float = 2.5):
    req = Request(GATEWAY + path, headers={"Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read(4 << 20)
            return json.loads(raw.decode("utf-8", "replace")), resp.headers.get("Content-Type", "")
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise SourceError("UPSTREAM_DOWN", f"gateway {path}: {type(exc).__name__}: {exc}") from exc


# ---- 采集器 ----------------------------------------------------------------

def gateway():
    def fn():
        data, ctype = _get("/health")
        models, ctype_models = _get("/v1/models")
        return {
            "health": scrub(data),
            "health_bytes": len(json.dumps(data, ensure_ascii=False).encode("utf-8")),
            "health_content_type": ctype,
            "models": models,
            "models_content_type": ctype_models,
            "gateway": GATEWAY,
            "polling_hint_ms": 5000,  # /health 每次触发 aliases.Reload()，别高频轮询
        }
    return cached("gateway", 5000, fn)


def aliases():
    def fn():
        path = ZV2 / "model-alias-map.json"
        raw = _load_json(path)
        models = raw.get("models", {}) if isinstance(raw, dict) else {}
        rows = []
        for name, spec in models.items():
            if isinstance(spec, dict):
                rows.append({"name": name, **scrub(spec)})
            else:
                rows.append({"name": name, "value": scrub(spec)})
        return {
            "meta": _meta(path),
            "version": raw.get("version"),
            "generated_at": raw.get("generated_at"),
            "slot": raw.get("slot"),
            "count": len(models),
            "legacy_count": len(raw.get("legacy", {}) or {}),
            "rows": rows,
        }
    return cached("aliases", 30000, fn)


def probe():
    def fn():
        path = ZV2 / "model_probe.json"
        raw = _load_json(path)
        rows, ok = [], 0
        for name, spec in (raw.items() if isinstance(raw, dict) else []):
            if not isinstance(spec, dict):
                continue
            status = str(spec.get("status") or "")
            if status.lower() in ("ok", "healthy", "200", "true"):
                ok += 1
            rows.append({
                "name": name,
                "status": status,
                "http": spec.get("http"),
                "ms": spec.get("ms"),
                "provider": spec.get("provider"),
                "detail": _clip(spec.get("detail")),
                "ever_ok": spec.get("ever_ok"),
                "ok_at": spec.get("ok_at"),
                "credit": spec.get("credit"),
            })
        return {"meta": _meta(path), "total": len(rows), "ok": ok, "rows": rows}
    return cached("probe", 30000, fn)


def scores():
    def fn():
        path = ZV2 / "model-scores.json"
        raw = _load_json(path)
        rows = []
        for name, spec in (raw.get("models", {}) or {}).items():
            if isinstance(spec, dict):
                rows.append({"name": name, **scrub(spec)})
        return {"meta": _meta(path), "checked_at": raw.get("checked_at"),
                "basis": scrub(raw.get("basis")), "count": len(rows), "rows": rows}
    return cached("scores", 60000, fn)


def quota():
    def fn():
        path = ZV2 / "quota-windows.json"
        raw = _load_json(path)
        return {"meta": _meta(path), "generated_at": raw.get("generated_at"),
                "windows": scrub(raw.get("windows", []))}
    return cached("quota", 60000, fn)


def prices():
    def fn():
        wb_path = ROOT / "providers" / "workbuddy" / "cache" / "wb_pricing.json"
        qd_path = ROOT / "providers" / "qoder" / "cache" / "qd_prices.json"
        wb = _load_json(wb_path)
        qd = _load_json(qd_path)
        wb_rows = [scrub(x) for x in wb if isinstance(x, dict)] if isinstance(wb, list) else []
        qd_rows = [{"name": k, **scrub(v)} for k, v in qd.items() if isinstance(v, dict)]
        return {"sources": [_meta(wb_path), _meta(qd_path)],
                "workbuddy_count": len(wb_rows), "qoder_count": len(qd_rows),
                "workbuddy": wb_rows, "qoder": qd_rows}
    return cached("prices", 60000, fn)


def arena():
    def fn():
        path = ZV2 / "arena-leaderboard.json"
        raw = _load_json(path)
        rows = raw.get("rows", []) if isinstance(raw, dict) else []
        return {"meta": _meta(path), "updatedAt": raw.get("updatedAt"),
                "totals": scrub(raw.get("totals")), "standings": scrub(raw.get("standings")),
                "total_rows": len(rows), "rows": [scrub(x) for x in rows[:20]],
                "note": "只展开前 20 行，避免整份榜单进响应"}
    return cached("arena", 300000, fn)


def traffic():
    def fn():
        files = sorted(REQUEST_LOGS.glob("requests-*.jsonl"),
                       key=lambda p: p.stat().st_mtime, reverse=True) if REQUEST_LOGS.is_dir() else []
        if not files:
            raise SourceError("SOURCE_MISSING", "request-logs/requests-*.jsonl")
        rows = tail_jsonl(files[0], limit=800, max_bytes=4 << 20)
        count = len(rows)
        okc = sum(1 for r in rows if r.get("ok") is True)
        durs = [r["duration_ms"] for r in rows if isinstance(r.get("duration_ms"), (int, float))]
        toks = sum(r.get("total_tokens") or 0 for r in rows
                   if isinstance(r.get("total_tokens"), (int, float)))
        by_model, by_status, hours = {}, {}, {}
        for r in rows:
            m, s = str(r.get("model") or "-"), str(r.get("status") or "-")
            by_model[m] = by_model.get(m, 0) + 1
            by_status[s] = by_status.get(s, 0) + 1
            h = str(r.get("time") or "")[:13]
            if h:
                hours[h] = hours.get(h, 0) + 1
        return {
            "file": files[0].name, "meta": _meta(files[0]), "count": count,
            "ok": okc, "ok_rate": round(okc / count, 4) if count else 0,
            "avg_ms": round(sum(durs) / len(durs), 1) if durs else 0,
            "tokens": toks,
            "by_model": sorted(by_model.items(), key=lambda x: -x[1])[:12],
            "by_status": sorted(by_status.items(), key=lambda x: -x[1])[:12],
            "hours": sorted(hours.items()),
            "files": [{"name": p.name, "bytes": p.stat().st_size} for p in files[:10]],
            "note": "tail 800 行流式采样，非全量统计",
        }
    return cached("traffic", 15000, fn)


def accounts():
    def fn():
        auth_dir = ROOT / "gateways" / "upstream" / "workbuddy" / "auths"
        rows = []
        for p in sorted(auth_dir.glob("*.json")) if auth_dir.is_dir() else []:
            try:
                raw = _load_json(p)
            except SourceError:
                continue
            acc, au = raw.get("account") or {}, raw.get("auth") or {}
            rows.append({
                "id": _mask_id(p.stem),
                "nickname": acc.get("nickname"),
                "uid": _mask_id(acc.get("uid")),
                "credential_present": bool(au.get("accessToken") or au.get("refreshToken")),
                "expires_at": au.get("expiresAt"),
                "bytes": p.stat().st_size,
            })
        qdir = ROOT / "gateways" / "upstream" / "qoder" / "accounts"
        qrows = [{"id": _mask_id(p.stem), "bytes": p.stat().st_size}
                 for p in (sorted(qdir.glob("*.json")) if qdir.is_dir() else [])][:20]
        pc = ZV2 / "provider_config.json"
        pc_view = {"present": pc.is_file(), "values": "never exported"}
        if pc.is_file():
            pc_view.update(_meta(pc))
        return {
            "workbuddy": {"count": len(rows), "rows": rows},
            "qoder": {"count": len(qrows), "rows": qrows,
                      "note": "只列文件名与体积，内容含凭据字段一律不解析"},
            "provider_config": pc_view,
            "credentials": {"present": (ZV2 / "credentials.json").is_file(),
                            "values": "never exported"},
        }
    return cached("accounts", 60000, fn)


def logs():
    def fn():
        zl = ZGATE_DIR / "zgate.log"
        lines = tail_lines(zl, 160) if zl.is_file() else []
        files = []
        if ZGATE_DIR.is_dir():
            for p in sorted(ZGATE_DIR.glob("*.log"), key=lambda x: x.stat().st_size, reverse=True)[:10]:
                files.append(_meta(p))
        return {
            "gateway_tail": [_clip(x, 240) for x in lines], "tail_limit": 160,
            "files": files,
            "note": "仅 zgate.log 出行内容；其余日志只报体积，避免请求体泄漏",
        }
    return cached("logs", 5000, fn)


def config():
    def fn():
        env_names = ("MODELBUS_GATEWAY", "WB_GATEWAY_KEY", "WB_GATEWAY_BASE",
                     "ZCODE_PERSONAL_PROVIDER_CONFIG_FILE", "ZCODE_BUILTIN",
                     ADMIN_TOKEN_ENV)
        env = [{"name": n, "configured": bool(os.environ.get(n))} for n in env_names]
        targets = [("provider_config.json", ZV2 / "provider_config.json"),
                   ("credentials.json", ZV2 / "credentials.json"),
                   ("model-sync-state.json", ZV2 / "model-sync-state.json"),
                   ("setting.json", ZV2 / "setting.json")]
        files = []
        for label, p in targets:
            entry = {"label": label, "present": p.is_file(), "values": "never exported"}
            if p.is_file():
                entry.update(_meta(p))
            files.append(entry)
        return {
            "gateway": GATEWAY, "bind": "127.0.0.1", "env": env, "files": files,
            "write_actions": ["reload"],
            "admin": {"header": "X-Zgate-Admin: 1",
                      "token_env": ADMIN_TOKEN_ENV,
                      "token_configured": admin_token_configured(),
                      "endpoints": ["/admin/routes", "/admin/stats", "/metrics"]},
            "note": "配置只报存在性 / 体积，键与值一律不出进程",
        }
    return cached("config", 60000, fn)


def ops():
    def fn():
        gw = ROOT / "gateways"
        baks = [p for p in (gw.rglob("*.bak-*") if gw.is_dir() else []) if p.is_file()]
        bak_bytes = sum(p.stat().st_size for p in baks)
        jls = list(REQUEST_LOGS.glob("*.jsonl")) if REQUEST_LOGS.is_dir() else []
        jl_bytes = sum(p.stat().st_size for p in jls)
        work = ROOT / ".work"
        work_bytes = sum(p.stat().st_size for p in work.rglob("*") if p.is_file()) if work.is_dir() else 0
        literal = ROOT / "%SystemDrive%"
        lit_bytes = sum(p.stat().st_size for p in literal.rglob("*") if p.is_file()) if literal.is_dir() else 0
        cfg_baks = list(ZV2.glob("provider_config.json.bak-*")) if ZV2.is_dir() else []
        cfg_bytes = sum(p.stat().st_size for p in cfg_baks)
        candidates = [
            {"key": "zgate_exe_backups", "path": "gateways/**/*.bak-*", "count": len(baks),
             "bytes": bak_bytes, "review": "旧版二进制，人工确认后删"},
            {"key": "request_logs", "path": "gateways/upstream/workbuddy/data/request-logs/*.jsonl",
             "count": len(jls), "bytes": jl_bytes, "review": "无轮转上限，建议按日保留 N 天"},
            {"key": "work_dir", "path": ".work/", "count": None, "bytes": work_bytes,
             "review": "会话中间产物"},
            {"key": "provider_config_backups", "path": "~/.zcode/v2/provider_config.json.bak-*",
             "count": len(cfg_baks), "bytes": cfg_bytes, "review": "本机备份，不入库"},
            {"key": "literal_systemdrive_dir", "path": "%SystemDrive%/", "count": None,
             "bytes": lit_bytes, "review": "字面量目录，硬编码路径产物"},
        ]
        try:
            du = shutil.disk_usage(ROOT)
            disk = {"total": du.total, "used": du.used, "free": du.free}
        except OSError:
            disk = {}
        return {
            "candidates": candidates,
            "reclaimable_bytes": bak_bytes + work_bytes + lit_bytes + cfg_bytes,
            "disk": disk,
            "policy": "后台只读展示，不自动删除任何文件",
        }
    return cached("ops", 30000, fn)


# ---- 网关管理面（三个只读端点）--------------------------------------------
# 7871 上这三个端点由 gateways/zgate/internal/router/admin.go 提供：
#   /admin/routes → 整张路由表（每跳渠道 / 协议 / 价格 / 当前状态）
#   /admin/stats  → 请求量 / 错误 / inflight / 字节 / p50 p90 p99 / 状态码分布 / 慢请求
#   /metrics      → Prometheus 0.0.4 文本
# /admin/* 走 adminGuard：回环来源 + X-Zgate-Admin 头 +（配了口令时的）X-Zgate-Token。
# 控制台自己也在回环上跑，头统一在 _admin_headers() 里补；口令只从环境变量读，
# 不进源码、不进响应、不进日志。
#
# 降级口径：这三个源可能比控制台新或旧 —— 旧版 zgate.exe 对 /admin/* 直接 404。
# 控制台不因此 500：统一返回 {available: false, error: {...}}，页面显示
# 「网关未提供该端点」，其余页照常可用。
ADMIN_TOKEN_ENV = "ZGATE_ADMIN_TOKEN"
METRICS_MAX_BYTES = 64 << 10  # /metrics 原样返回但限长，几十 KB 全塞页面没有意义


def admin_token_configured() -> bool:
    """只报「配没配」，值永不出进程。"""
    return bool(os.environ.get(ADMIN_TOKEN_ENV, "").strip())


def _admin_headers(accept: str = "application/json") -> dict:
    headers = {"Accept": accept, "X-Zgate-Admin": "1"}
    token = os.environ.get(ADMIN_TOKEN_ENV, "").strip()
    if token:
        headers["X-Zgate-Token"] = token
    return headers


def _admin_raw(path: str, accept: str = "application/json", timeout: float = 2.5,
               limit: int = 4 << 20):
    req = Request(GATEWAY + path, headers=_admin_headers(accept))
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.headers.get("Content-Type", ""), resp.read(limit)
    except HTTPError as exc:
        # 404 / 405 = 这版网关还没有该端点（旧二进制），和「网关挂了」要分开报。
        code = "NOT_SUPPORTED" if exc.code in (404, 405) else "UPSTREAM_DOWN"
        raise SourceError(code, f"gateway {path}: HTTP {exc.code}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise SourceError("UPSTREAM_DOWN",
                          f"gateway {path}: {type(exc).__name__}: {exc}") from exc


def _admin_json(path: str, timeout: float = 2.5):
    _, _, raw = _admin_raw(path, timeout=timeout)
    try:
        return json.loads(raw.decode("utf-8", "replace"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceError("PARSE_ERROR",
                          f"gateway {path}: {type(exc).__name__}: {exc}") from exc


def _degraded(run):
    """管理面失败降级：available=False + 结构化原因，页面照常渲染。"""
    try:
        payload = run()
        if not isinstance(payload, dict):
            raise SourceError("PARSE_ERROR", "unexpected payload shape")
        return {"available": True, **payload}
    except SourceError as exc:
        return {"available": False, "error": {"code": exc.code, "message": exc.message}}
    except Exception as exc:  # 兜底：任何形状意外都不许把页面打成裸 500
        return {"available": False,
                "error": {"code": "PARSE_ERROR", "message": f"{type(exc).__name__}: {exc}"}}


def _num_or_none(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _routes_view(raw):
    """把 /admin/routes 摊成「模型行 + 渠道分组」两张视图。

    渠道分组按跳拆：一条链跨渠道时，每个渠道都要能看到「哪些模型从我这走、
    协议是什么、价格多少、这跳现在 ready 还是冷却」—— 这正是排查
    「为什么这次没走首选」时要看的那张表。
    """
    models = raw.get("models") if isinstance(raw, dict) else None
    models = models if isinstance(models, list) else []
    rows, channel_map = [], {}
    hop_total = hop_ready = 0
    for item in models:
        if not isinstance(item, dict):
            continue
        name = _clip(item.get("model"), 120)
        proto = _clip(item.get("protocol") or "chat", 24)
        hops = [h for h in (item.get("hops") or []) if isinstance(h, dict)]
        hop_rows = []
        for idx, hop in enumerate(hops):
            state = _clip(hop.get("state") or "unknown", 48)
            row = {
                "channel": _clip(hop.get("channel") or "-", 40),
                "upstream": _clip(hop.get("upstream"), 120),
                "base": _clip(hop.get("base"), 160),
                "protocol": _clip(hop.get("protocol") or proto, 24),
                "price": _num_or_none(hop.get("price")),
                "proxy": _clip(hop.get("proxy"), 60),
                "state": state,
                "primary": idx == 0,
            }
            hop_rows.append(row)
            hop_total += 1
            if state == "ready":
                hop_ready += 1
            group = channel_map.setdefault(
                row["channel"], {"channel": row["channel"], "rows": [], "models": []})
            group["rows"].append({"model": name, "hop": idx + 1, **row})
            if name not in group["models"]:
                group["models"].append(name)
        states = [h["state"] for h in hop_rows]
        rows.append({
            "model": name,
            "group": _clip(item.get("group"), 40),
            "protocol": proto,
            "price": _num_or_none(item.get("price")),
            "state": states[0] if states else "unknown",
            "hop_count": len(hop_rows),
            "ready_hops": sum(1 for s in states if s == "ready"),
            "channels": [h["channel"] for h in hop_rows],
            "fallbacks": [_clip(x, 80) for x in (item.get("fallbacks") or [])
                          if isinstance(x, str)],
            "legacy_ids": [_clip(x, 80) for x in (item.get("legacy_ids") or [])
                           if isinstance(x, str)],
            "hops": hop_rows,
        })
    channels = []
    for key in sorted(channel_map):
        group = channel_map[key]
        states = [r["state"] for r in group["rows"]]
        channels.append({
            "channel": group["channel"],
            "hops": len(states),
            "ready": sum(1 for s in states if s == "ready"),
            "degraded": sum(1 for s in states if s != "ready"),
            "model_count": len(group["models"]),
            "models": group["models"],
            "rows": group["rows"],
        })
    return {
        "revision": raw.get("revision") if isinstance(raw, dict) else None,
        "total": len(rows),
        "hop_total": hop_total,
        "hop_ready": hop_ready,
        "channels": channels,
        "models": rows,
    }


def _stats_view(raw):
    """把 /admin/stats 收敛成页面要的那几个数（缺字段一律归零，不编造）。"""
    stats = raw.get("stats") if isinstance(raw, dict) else {}
    stats = stats if isinstance(stats, dict) else {}
    lat = stats.get("latency_ms") if isinstance(stats.get("latency_ms"), dict) else {}
    cls = stats.get("status_class") if isinstance(stats.get("status_class"), dict) else {}
    slow_raw = [s for s in (stats.get("slow") or []) if isinstance(s, dict)]
    requests = _num_or_none(stats.get("requests")) or 0
    errors = _num_or_none(stats.get("errors")) or 0
    slow = [{
        "at": _clip(s.get("at"), 24),
        "id": _clip(s.get("id"), 40),
        "path": _clip(s.get("path"), 80),
        "model": _clip(s.get("model"), 80),
        "status": _num_or_none(s.get("status")) or 0,
        "ms": _num_or_none(s.get("ms")) or 0,
    } for s in slow_raw[-10:]]
    slow.reverse()  # 网关按发生顺序追加，页面要最新的在最上面
    return {
        "version": _clip(raw.get("version"), 60),
        "draining": bool(raw.get("draining")),
        "uptime_s": _num_or_none(stats.get("uptime_s")) or 0,
        "requests": requests,
        "errors": errors,
        "inflight": _num_or_none(stats.get("inflight")) or 0,
        "bytes_in": _num_or_none(stats.get("bytes_in")) or 0,
        "bytes_out": _num_or_none(stats.get("bytes_out")) or 0,
        "rps": round(float(_num_or_none(stats.get("rps")) or 0), 3),
        "error_rate": round(errors / requests, 4) if requests else 0.0,
        "latency_ms": {k: (_num_or_none(lat.get(k)) or 0) for k in ("p50", "p90", "p99")},
        "status_class": {k: (_num_or_none(cls.get(k)) or 0)
                         for k in ("1xx", "2xx", "3xx", "4xx", "5xx")},
        "slow": slow,
        "slow_total": len(slow_raw),
        "alias": scrub(raw.get("alias") or {}),
        "cooling": _num_or_none(raw.get("cooling")) or 0,
        "children": scrub(raw.get("children") or {}),
    }


def admin_routes():
    def fn():
        return _degraded(lambda: _routes_view(_admin_json("/admin/routes")))
    return cached("admin_routes", 5000, fn)


def admin_stats():
    def fn():
        return _degraded(lambda: _stats_view(_admin_json("/admin/stats")))
    return cached("admin_stats", 5000, fn)


def admin_metrics():
    def fn():
        def run():
            status, ctype, raw = _admin_raw("/metrics", accept="text/plain")
            text = raw.decode("utf-8", "replace")
            truncated = len(raw) >= METRICS_MAX_BYTES
            if truncated:
                text = text[:METRICS_MAX_BYTES]
            return {
                "status": status,
                "content_type": _clip(ctype, 80),
                "bytes": len(raw),
                "returned_bytes": len(text.encode("utf-8")),
                "limit_bytes": METRICS_MAX_BYTES,
                "truncated": truncated,
                "lines": text.count("\n") + 1 if text else 0,
                "families": sum(1 for ln in text.splitlines() if ln.startswith("# TYPE ")),
                "text": text,
            }
        return _degraded(run)
    return cached("admin_metrics", 10000, fn)


SEGMENTS = ("workbuddy", "qoder", "qwen", "qiniu", "gemini", "hajimi", "opencode")


def overview():
    def fn():
        gw = _safe(gateway, {"health": {}, "health_bytes": 0})
        h = gw.get("health") or {}
        pr = _safe(probe, {"total": 0, "ok": 0})
        tr = _safe(traffic, {"file": None, "count": 0, "ok_rate": 0, "avg_ms": 0, "tokens": 0})
        op = _safe(ops, {"reclaimable_bytes": 0, "candidates": []})
        segments = {}
        for key in SEGMENTS:
            seg = h.get(key)
            if isinstance(seg, dict):
                segments[key] = {"state": seg.get("state"), "key": seg.get("key"),
                                 "child": seg.get("child"), "base": seg.get("base")}
        hops = h.get("hops") or {}
        hop_ok = sum(1 for v in hops.values() if isinstance(v, dict) and v.get("ok"))
        return {
            "ok": h.get("ok"), "uptime_s": h.get("uptime_s"),
            "alias_models": (h.get("alias") or {}).get("models"),
            "segments": segments, "cooling": h.get("cooling"), "guard": h.get("guard"),
            "children": scrub(h.get("children") or {}),
            "hops": {"total": len(hops), "ok": hop_ok},
            "probe": {"total": pr.get("total", 0), "ok": pr.get("ok", 0)},
            "traffic": {"file": tr.get("file"), "requests": tr.get("count", 0),
                        "ok_rate": tr.get("ok_rate", 0), "avg_ms": tr.get("avg_ms", 0),
                        "tokens": tr.get("tokens", 0)},
            "ops": {"reclaimable_bytes": op.get("reclaimable_bytes", 0),
                    "top": op.get("candidates", [])[:3]},
            "health_bytes": gw.get("health_bytes", 0),
            "generated_at": _now(),
        }
    return cached("overview", 5000, fn)
