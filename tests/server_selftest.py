"""OpenSweep web UI selftest (portable): kill orphans of THIS tool, boot the
server on a random port, verify token gating + endpoints, always terminate.
Run:  python tests/server_selftest.py
"""
import json, secrets, subprocess, sys, time, urllib.request
from pathlib import Path

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent

# kill orphans of THIS tool only (by command-line signature)
kill_ps = ("Get-CimInstance Win32_Process -Filter \"Name='python.exe' or Name='pythonw.exe'\" | "
           "Where-Object {$_.CommandLine -match 'server\\.py'} | "
           "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }")
if sys.platform == "win32":
    subprocess.run(["powershell", "-NoProfile", "-Command", kill_ps],
                   capture_output=True, text=True, timeout=30)
else:
    subprocess.run(["pkill", "-f", "server.py"], capture_output=True, timeout=10)

PORT = 8791 + (int(secrets.token_hex(1), 16) % 200)
proc = subprocess.Popen([sys.executable, str(ROOT / "server.py"), str(PORT)],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                        encoding="utf-8", errors="replace")
ok = fail = 0

def report(good, label, code=""):
    global ok, fail
    ok, fail = ok + bool(good), fail + (not good)
    print(f"[{'PASS' if good else 'FAIL'}] {label}" + (f" -> {code}" if code else ""))

try:
    url = None
    for _ in range(40):
        line = proc.stdout.readline()
        if "http://127.0.0.1" in line:
            url = line.split("->")[1].strip()
            break
        time.sleep(0.2)
    if not url:
        print("FAIL: server did not print URL")
        sys.exit(1)
    base = url.split("?")[0].rstrip("/")
    token = url.split("?t=")[-1].strip()
    print(f"[selftest] {base}  token=...{token[-6:]}")

    def get(path, expect=200):
        req = urllib.request.Request(base + path, headers={"X-Token": token})
        try:
            r = urllib.request.urlopen(req, timeout=180)
            return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    try:
        urllib.request.urlopen(base + "/api/health", timeout=30)
        report(False, "no-token rejected")
    except urllib.error.HTTPError as e:
        report(e.code == 403, "no-token rejected", e.code)

    for p in ("/", "/styles.css", "/app.js"):
        code, _ = get(p)
        report(code == 200, f"GET {p}", code)

    code, b = get("/api/health")
    report(code == 200 and b"harden" in b, "GET /api/health", code)
    code, _ = get("/api/journals"); report(code == 200, "GET /api/journals", code)
    code, _ = get("/api/rules");    report(code == 200, "GET /api/rules", code)
    code, _ = get("/api/tools");    report(code == 200, "GET /api/tools", code)

    code, b = get("/api/scan")
    n = len(json.loads(b)["results"])
    report(code == 200 and n >= 1, f"GET /api/scan (rules={n})", code)

    print(f"[selftest] PASS {ok} / FAIL {fail}")
    sys.exit(1 if fail else 0)
finally:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except Exception:
        proc.kill()
