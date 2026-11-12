"""ModelBus 控制台 · HTTP 层。

> 一句话：绑 127.0.0.1 的独立只读服务，静态页 + /api/* 数据面 + 唯一 reload 动作，网关响应一字不改。

用法：
  python tools/console/server.py --port 7872
  python tools/console/server.py --check
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import actions  # noqa: E402
import sources  # noqa: E402

STATIC = HERE / "static"
ROUTES = {
    "/api/overview": (sources.overview, 5000),
    "/api/gateway": (sources.gateway, 5000),
    "/api/models": (sources.aliases, 30000),
    "/api/probe": (sources.probe, 30000),
    "/api/prices": (sources.prices, 60000),
    "/api/scores": (sources.scores, 60000),
    "/api/quota": (sources.quota, 60000),
    "/api/arena": (sources.arena, 300000),
    "/api/traffic": (sources.traffic, 15000),
    "/api/accounts": (sources.accounts, 60000),
    "/api/logs": (sources.logs, 5000),
    "/api/config": (sources.config, 60000),
    "/api/ops": (sources.ops, 30000),
}
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
    "/favicon.svg": ("favicon.svg", "image/svg+xml"),
    "/vendor/tabler.min.css": ("vendor/tabler.min.css", "text/css; charset=utf-8"),
}
STATUS = {"SOURCE_MISSING": 404, "PARSE_ERROR": 500, "UPSTREAM_DOWN": 502,
          "BAD_REQUEST": 400, "JOB_BUSY": 409}
PORT = 7872


def ok_envelope(data, ttl_ms):
    return {"ok": True, "generated_at": sources._now(), "ttl_ms": ttl_ms, "data": data}


def err_envelope(code, message):
    return {"ok": False, "generated_at": sources._now(), "ttl_ms": 0,
            "data": None, "error": {"code": code, "message": message}}


class Handler(BaseHTTPRequestHandler):
    server_version = "ModelBusConsole/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("[console] %s - %s\n" % (self.address_string(), fmt % args))

    def _host_ok(self):
        raw = (self.headers.get("Host") or "").split(",")[0].strip().lower()
        allowed = {f"127.0.0.1:{PORT}", f"localhost:{PORT}", f"[::1]:{PORT}",
                   "127.0.0.1", "localhost", "[::1]"}
        return raw in allowed

    def _origin_ok(self):
        origin = self.headers.get("Origin")
        if not origin:
            return False  # 写操作必须带同源 Origin，挡住无来源的简单跨站 POST
        host = urlparse(origin).netloc.lower()
        return host in {f"127.0.0.1:{PORT}", f"localhost:{PORT}", f"[::1]:{PORT}"}

    def _send(self, status, payload, ctype="application/json; charset=utf-8", extra=None):
        body = b"" if getattr(self, "_head", False) else json.dumps(
            payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if not getattr(self, "_head", False):
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def _serve_static(self, path):
        item = STATIC_FILES.get(path)
        if item is None:
            return self._send(404, err_envelope("BAD_REQUEST", "unknown static path"))
        name, ctype = item
        fp = STATIC / name
        if not fp.is_file():
            return self._send(404, err_envelope("SOURCE_MISSING", f"static/{name}"))
        raw = fp.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if not getattr(self, "_head", False):
            try:
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def do_HEAD(self):
        self._head = True
        return self.do_GET()

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, err_envelope("BAD_REQUEST", "host not allowed"))
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path == "/healthz":
            return self._send(200, ok_envelope({"service": "console", "port": PORT,
                                                "gateway": sources.GATEWAY}, 0))
        if path == "/api/actions/jobs":
            return self._send(200, ok_envelope(actions.jobs(), 0))
        if path == "/api/logs/stream":
            if getattr(self, "_head", False):
                return self._send(200, {}, ctype="text/event-stream; charset=utf-8")
            return self._stream_logs()
        if path in STATIC_FILES:
            return self._serve_static(path)
        route = ROUTES.get(path)
        if route is None:
            return self._send(404, err_envelope("BAD_REQUEST", f"unknown route {path}"))
        fn, ttl = route
        try:
            return self._send(200, ok_envelope(fn(), ttl))
        except sources.SourceError as exc:
            return self._send(STATUS.get(exc.code, 500), err_envelope(exc.code, exc.message))
        except Exception as exc:  # 页面必须拿到结构化错误，不能是裸 500
            return self._send(500, err_envelope("PARSE_ERROR", f"{type(exc).__name__}: {exc}"))

    def _stream_logs(self):
        zl = sources.ZGATE_DIR / "zgate.log"
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            for _ in range(30):  # 上限 60 s，页面自行重连
                try:
                    lines = sources.tail_lines(zl, 20, 128 << 10)
                except sources.SourceError:
                    lines = []
                chunk = json.dumps({"lines": [sources._clip(x, 240) for x in lines],
                                    "at": sources._now()}, ensure_ascii=False)
                self.wfile.write(("data: " + chunk + "\n\n").encode("utf-8"))
                self.wfile.flush()
                time.sleep(2)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def do_POST(self):
        if not self._host_ok() or not self._origin_ok():
            return self._send(403, err_envelope("BAD_REQUEST", "origin not allowed"))
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path != "/api/actions/reload":
            return self._send(404, err_envelope("BAD_REQUEST", f"unknown action {path}"))
        try:
            return self._send(200, ok_envelope(actions.reload_gateway(), 0))
        except sources.SourceError as exc:
            return self._send(STATUS.get(exc.code, 500), err_envelope(exc.code, exc.message))
        except Exception as exc:  # 页面必须拿到结构化错误，不能是裸 500
            return self._send(500, err_envelope("PARSE_ERROR", f"{type(exc).__name__}: {exc}"))


def run_check():
    global PORT
    failures = 0
    hand_bytes = 0
    vendor_bytes = 0
    for filename in {item[0] for item in STATIC_FILES.values()}:
        fp = STATIC / filename
        if not fp.is_file():
            print(f"[check] FAIL missing static/{filename}")
            failures += 1
            continue
        size = fp.stat().st_size
        if filename.startswith("vendor/"):
            vendor_bytes += size
        else:
            hand_bytes += size
    print(f"[check] handwritten static bytes = {hand_bytes} (budget 200 KB)")
    print(f"[check] vendor static bytes = {vendor_bytes} (Tabler 1.7.4, offline)")
    if hand_bytes > 200 * 1024:
        print("[check] FAIL handwritten static over budget")
        failures += 1
    if vendor_bytes == 0:
        print("[check] FAIL vendor CSS missing")
        failures += 1
    for path, (fn, _) in ROUTES.items():
        try:
            fn()
            print(f"[check] OK   {path}")
        except sources.SourceError as exc:
            if exc.code == "UPSTREAM_DOWN":
                print(f"[check] WARN {path}: {exc.message}")
            else:
                print(f"[check] FAIL {path}: {exc.code}: {exc.message}")
                failures += 1
        except Exception as exc:
            print(f"[check] FAIL {path}: {type(exc).__name__}: {exc}")
            failures += 1
    try:
        sources._get("/health")
        print("[check] OK   gateway /health")
    except sources.SourceError as exc:
        print(f"[check] WARN gateway /health: {exc.message}")
    print(f"[check] result = {'PASS' if failures == 0 else 'FAIL'} ({failures} failure(s))")
    return 0 if failures == 0 else 1


def main():
    global PORT
    ap = argparse.ArgumentParser(description="ModelBus 控制台")
    ap.add_argument("--port", type=int, default=7872)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--check", action="store_true", help="自检数据源与静态体量，不监听端口")
    args = ap.parse_args()
    PORT = args.port
    if args.check:
        return run_check()
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print("only loopback bind is allowed", file=sys.stderr)
        return 2
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    srv.daemon_threads = True
    print(f"[console] http://{args.host}:{args.port}  gateway={sources.GATEWAY}", flush=True)
    try:
        srv.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
