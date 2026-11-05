#!/usr/bin/env python3
"""OpenSweep local UI server.

Binds 127.0.0.1 only (zero external network), token-gated (each start prints
a one-time URL), every destructive API requires confirm:true in the payload.
Static UI is served from ./webui.  Ctrl+C stops.
"""
import json
import secrets
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parent))
import opensweep as engine  # noqa: E402

HERE = Path(__file__).resolve().parent
UI = HERE / "webui"
TOKEN = secrets.token_urlsafe(16)
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8791


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            # 扫描要跑一两分钟，用户中途关页面/刷新是常态：不要为此打一屏 traceback
            pass

    def _check(self):
        q = parse_qs(urlparse(self.path).query)
        if q.get("t", [""])[0] == TOKEN or self.headers.get("X-Token") == TOKEN:
            return True
        self._json({"error": "bad token"}, 403)
        return False

    def do_GET(self):
        u = urlparse(self.path)
        if u.path.startswith("/api/"):
            if not self._check():
                return
            name = u.path[5:]
            try:
                if name == "rules":
                    self._json({"rules": engine.RULES})
                elif name == "scan":
                    running = engine.running_exes()
                    out = [engine.scan_rule(r, running, []) for r in engine.RULES]
                    self._json({"results": out})
                elif name == "harden":
                    self._json({"rows": engine.harden_report()})
                elif name == "startup":
                    self._json({"items": engine.startup_report()})
                elif name == "apps":
                    self._json({"apps": engine.installed_apps()})
                elif name == "updates":
                    self._json({"lines": engine.winget_upgrades()})
                elif name == "tools":
                    self._json({"rows": engine.tools_report()})
                elif name == "journals":
                    files = (sorted(engine.UNDO_ROOT.glob("*.json"))
                             if engine.UNDO_ROOT.exists() else [])
                    self._json({"journals": [{"name": f.name,
                                              "mtime": f.stat().st_mtime,
                                              "size": f.stat().st_size}
                                             for f in files]})
                elif name == "health":
                    rows = engine.harden_report()
                    nh = sum(1 for r in rows if r["status"] == "hardened")
                    ne = sum(1 for r in rows if r["status"] == "exposed")
                    na = sum(1 for r in rows if r["status"] == "admin-required")
                    n = (len(list(engine.UNDO_ROOT.glob("*.json")))
                         if engine.UNDO_ROOT.exists() else 0)
                    self._json({"harden": {"hardened": nh, "exposed": ne, "admin": na},
                                "journals": n, "rules": len(engine.RULES),
                                "admin": engine.is_admin(),
                                "platform": sys.platform})
                elif name == "dupes":
                    q = parse_qs(u.query)
                    d = q.get("dir", [""])[0]
                    mb = float(q.get("min", ["10"])[0] or 10)
                    groups = engine.dup_scan(d, mb)
                    if groups is None:
                        self._json({"error": "directory not found"}, 400)
                        return
                    self._json({"groups": groups[:200]})
                else:
                    self._json({"error": "unknown endpoint"}, 404)
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return
        # static UI is public: it ships no data, every byte of data comes from
        # the token-gated /api/ endpoints below. (Requiring a token here made
        # the browser's own subresource requests (styles.css / app.js) 403.)
        rel = "index.html" if u.path in ("/", "/index.html") else u.path.lstrip("/")
        fp = (UI / rel).resolve()
        if UI.resolve() not in fp.parents or not fp.is_file():
            self.send_response(404)
            self.end_headers()
            return
        ctype = {"html": "text/html", "css": "text/css", "js": "text/javascript",
                 "svg": "image/svg+xml"}.get(fp.suffix.lstrip("."), "application/octet-stream")
        data = fp.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        u = urlparse(self.path)
        if not u.path.startswith("/api/"):
            self._json({"error": "not found"}, 404)
            return
        if not self._check():
            return
        try:
            ln = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(ln) or b"{}")
        except Exception:
            payload = {}
        name = u.path[5:]
        try:
            if name == "clean":
                if not payload.get("confirm"):
                    self._json({"error": "confirm required"}, 400)
                    return
                ids = payload.get("rules") or []
                keep = [d.strip().lower() for d in payload.get("keep", []) if d.strip()]
                running = engine.running_exes()
                jr = engine.Journal()
                rp_note = None
                if payload.get("restore_point"):
                    rp_ok, rp_note = engine.create_restore_point("OpenSweep pre-clean")
                out = []
                for rid in ids:
                    rule = next((r for r in engine.RULES if r["id"] == rid), None)
                    if rule:
                        out.append(engine.apply_rule(rule, running, keep, jr, dry=False))
                self._json({"results": out, "journal": jr.save().name,
                            "restore_point": rp_note})
            elif name == "harden":
                if not payload.get("confirm"):
                    self._json({"error": "confirm required"}, 400)
                    return
                jr = engine.Journal()
                out = engine.harden_apply(jr, dry=False)
                self._json({"results": out, "journal": jr.save().name})
            elif name == "undo":
                if not payload.get("confirm"):
                    self._json({"error": "confirm required"}, 400)
                    return
                fp = (engine.UNDO_ROOT / (payload.get("journal") or "")).resolve()
                if engine.UNDO_ROOT not in fp.parents or fp.suffix != ".json":
                    self._json({"error": "bad journal"}, 400)
                    return
                engine.undo_journal(str(fp))
                self._json({"ok": True})
            else:
                self._json({"error": "unknown"}, 404)
        except Exception as e:
            self._json({"error": str(e)}, 500)


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"OpenSweep UI  ->  http://127.0.0.1:{PORT}/?t={TOKEN}")
    print("(token gates every call; share nothing. Ctrl+C to stop.)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
