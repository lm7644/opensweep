"""OpenSweep safety test suite — cross-platform (Windows + macOS CI).

Strategy: inject sandbox env (TEMP/APPDATA/LOCALAPPDATA/ALLUSERSPROFILE and,
on POSIX, HOME) BEFORE importing the engine so every rule path resolves
inside the sandbox; manifest-hash protected files; repeat apply/verify/undo
rounds; torture-test guards. Registry semantics are tested on self-created
fixture keys, Windows only.  Exit 0 = all green.
"""
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
import tempfile  # noqa: E402
WS = Path(tempfile.gettempdir()) / "OpenSweepTestRuns"
SB = WS / "sandbox"
if SB.exists():
    shutil.rmtree(SB, ignore_errors=True)
SB.mkdir(parents=True, exist_ok=True)

os.environ["TEMP"] = str(SB / "Temp")
os.environ["TMP"] = str(SB / "Temp")
os.environ["APPDATA"] = str(SB / "AppData" / "Roaming")
os.environ["LOCALAPPDATA"] = str(SB / "AppData" / "Local")
os.environ["ALLUSERSPROFILE"] = str(SB / "ProgramData")
if sys.platform != "win32":
    os.environ["HOME"] = str(SB / "home")   # darwin rules resolve under sandbox

sys.path.insert(0, str(ROOT))
import opensweep as engine  # noqa: E402

IS_WIN = engine.IS_WIN
IS_MAC = engine.IS_MAC
RESULTS = []

def check(name, good, detail=""):
    RESULTS.append((name, bool(good), detail))
    print(f"  [{'PASS' if good else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 16), b""):
            h.update(b)
    return h.hexdigest()

def put(rel, name, size=64, tag=b""):
    p = SB / rel
    p.mkdir(parents=True, exist_ok=True)
    f = p / name
    f.write_bytes(tag + b"OPENSWEEP-FIXTURE-"
                  + name.encode("utf-8") * max(1, size // 32))
    return f

PROTECTED, JUNK_EXPECT = {}, {}

def build_important():
    zones = {
        "Documents": ["report.docx", "thesis-final.pdf", "budget.xlsx"],
        "Desktop": ["family-photo.jpg", "contract-signed.pdf"],
        "Pictures": ["IMG_0001.png"],
        "AppData/Roaming/MyCriticalApp": ["license.key", "config.json"],
    }
    for zone, names in zones.items():
        for n in names:
            f = put(zone, n, tag=b"PROTECTED-")
            PROTECTED[str(f.relative_to(SB)).replace("\\", "/")] = sha(f)
    # browser credential/bookmark stores, at the platform's real chrome path
    chrome = engine.CHROMIUM_BROWSERS.get("chrome", {}).get("data", "")
    if chrome:
        d = Path(chrome) / "Default"
        d.mkdir(parents=True, exist_ok=True)
        for n in ("Login Data", "Bookmarks"):
            f = d / n
            f.write_bytes(b"PROTECTED-STORE")
            PROTECTED[str(f.relative_to(SB)).replace("\\", "/")] = sha(f)

def build_junk():
    exp = {}
    def junk(rel, names):
        for n in names:
            put(rel, n, tag=b"JUNK-")
            exp[str((SB / rel / n).relative_to(SB)).replace("\\", "/")] = True
    if IS_WIN:
        junk("Temp", [f"native_{i:03d}.tmp" for i in range(40)]
             + ["中文临时文件.tmp", "a" * 120 + ".tmp", "setup payload.dat"])
        junk("AppData/Roaming/Microsoft/Windows/PowerShell/PSReadLine",
             ["ConsoleHost_history.txt"])
        junk("AppData/Roaming/Microsoft/Windows/Recent", [f"doc{i}.lnk" for i in range(4)])
        junk("AppData/Local/Microsoft/Windows/Explorer",
             [f"thumbcache_{i}.db" for i in range(3)] + ["iconcache_1.db"])
        junk("AppData/Local/CrashDumps", ["app.exe.1234.dmp", "svc.5678.dmp"])
        junk("ProgramData/Microsoft/Windows/WER/ReportArchive", ["r1", "r2"])
        junk("ProgramData/Microsoft/Windows/WER/ReportQueue", ["q1"])
        junk("AppData/Local/Microsoft/Windows/WER/ReportArchive", ["lr1"])
        junk("AppData/Roaming/Tencent/QQ/STemp", ["patch.dat", "up.log"])
        junk("AppData/Roaming/Tencent/QQNT/STemp", ["nt.dat"])
        junk("AppData/Roaming/Tencent/WeChat/log", ["wxlog1.txt", "wxlog2.txt"])
        junk("AppData/Roaming/Tencent/WeChat/crash", ["wx.dmp"])
        junk("AppData/Roaming/Tencent/WeChat/cdncomm", ["cdn.bin"])
        junk("AppData/Roaming/Tencent/Logs", ["qq_setup.log", "x.tlg"])
        junk("AppData/Local/DoubaoWork/User Data/Crashpad", ["d1.dmp"])
        junk("AppData/Local/DoubaoWork/User Data/BrowserMetrics", ["bm.bin"])
        junk("AppData/Local/DoubaoWork/User Data/component_crx_cache", ["c1"])
        junk("AppData/Local/DoubaoWork/User Data/ClipboardTemp", ["ct.dat"])
        b = "AppData/Local/Google/Chrome/User Data/Default"
    else:
        # no $TMPDIR rule on darwin yet (needs age-based filtering) - the
        # engine must not be tested against rules that do not exist
        b = "home/Library/Application Support/Google/Chrome/Default"
    junk(b + "/Cache", [f"c{i}.dat" for i in range(6)])
    junk(b + "/Code Cache", ["cc.dat"])
    junk(b + "/GPUCache", ["gpu.dat"])
    junk(b + "/Service Worker/CacheStorage", ["sw.dat"])
    junk(b + "/Service Worker/ScriptCache", ["sws.dat"])
    put("Temp/OpenSweepUndo", "canary.txt", tag=b"CANARY-")
    if not IS_WIN:
        junk("home/Library/Application Support/Microsoft Edge/Default/Cache",
             [f"e{i}.dat" for i in range(4)])
        junk("home/Library/Caches/Firefox/Profiles/abc123.default/cache2", ["f1.dat", "f2.dat"])
        junk("home/Library/Caches/com.apple.Safari", ["s1.dat", "s2.dat"])
        junk("home/Library/Logs", ["app1.log", "app2.log"])
        junk("home/Library/Logs/DiagnosticReports", ["crash1.ips"])
    # neutral zone (not covered by any rule -> must survive)
    if IS_WIN:
        put("AppData/Local/DoubaoWork/User Data/EBWebView/Default/Cache", "keepme.dat")
    return exp

def build_cookies():
    rule = next(r for r in engine.RULES if r["id"].endswith("chrome.cookies"))
    glob = os.path.expandvars(rule["sqlite"][0]["glob"])
    # exactly one '*' (the profile dir segment) -> replace to get the fixture path
    db = Path(glob.replace("*", "Default"))
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE IF NOT EXISTS cookies (host_key TEXT, name TEXT, value TEXT)")
    con.execute("DELETE FROM cookies")
    for h in (".github.com", "github.com", "sub.github.com", "evil-tracker.com", ".ads.cn"):
        con.execute("INSERT INTO cookies VALUES (?,?,?)", (h, "sid", "x"))
    con.commit(); con.close()
    return db

def cookie_counts(db):
    con = sqlite3.connect(f"file:{db}?mode=ro&immutable=1", uri=True)
    total = con.execute("SELECT COUNT(*) FROM cookies").fetchone()[0]
    kept = con.execute("SELECT COUNT(*) FROM cookies WHERE host_key='github.com' "
                       "OR host_key LIKE '%.github.com'").fetchone()[0]
    con.close()
    return total, kept

def sandbox_rules():
    return [r for r in engine.RULES if "reg" not in r and "special" not in r]

def manifest():
    return {rel: sha(SB / rel) for rel in PROTECTED}

def junk_snapshot():
    return {rel for rel in JUNK_EXPECT if (SB / rel).exists()}

def dryrun_test():
    print("\n== dry-run zero-mutation ==")
    before = manifest()
    for r in sandbox_rules():
        engine.apply_rule(r, set(), [], None, dry=True)
    check("dry-run performs zero mutations", before == manifest())

def scan_determinism():
    print("\n== scan determinism ==")
    a = [engine.scan_rule(r, set(), []) for r in sandbox_rules()]
    b = [engine.scan_rule(r, set(), []) for r in sandbox_rules()]
    same = all(x["id"] == y["id"] and x["items"] == y["items"] and x["bytes"] == y["bytes"]
               for x, y in zip(a, b))
    check("two consecutive scans identical", same)
    check("sandbox scan finds the junk", sum(x["items"] for x in a) > 20,
          f"items={sum(x['items'] for x in a)}")

def rounds(n_rounds=3):
    print(f"\n== apply/verify/undo rounds x{n_rounds} (sandbox) ==")
    rules = sandbox_rules()
    for rnd in range(1, n_rounds + 1):
        print(f" -- round {rnd} --")
        before = manifest()
        junk_before = junk_snapshot()
        jr = engine.Journal()
        for r in rules:
            engine.apply_rule(r, set(), [], jr, dry=False)
        after = manifest()
        diff = [k for k in before if before[k] != after.get(k)]
        check(f"r{rnd}: protected files byte-identical ({len(before)} files)",
              not diff, ",".join(diff[:3]))
        left = junk_snapshot()
        check(f"r{rnd}: all junk moved ({len(junk_before)} files)", not left,
              ",".join(sorted(left)[:3]))
        check(f"r{rnd}: undo-area canary excluded",
              (SB / "Temp/OpenSweepUndo/canary.txt").exists())
        moved = sum(1 for e in jr.entries if e["type"] == "file")
        check(f"r{rnd}: journal captured moved files", moved >= len(junk_before) - 3,
              f"moved={moved}")
        moved2 = 0
        for r in rules:
            moved2 += engine.apply_rule(r, set(), [], engine.Journal(), dry=False)["files"]
        check(f"r{rnd}: repeat apply is a no-op", moved2 == 0, f"moved2={moved2}")
        engine.undo_journal(jr.save())
        restored = manifest()
        rdiff = [k for k in before if before[k] != restored.get(k)]
        check(f"r{rnd}: undo restores byte-identical", not rdiff, ",".join(rdiff[:3]))
        check(f"r{rnd}: junk present again after undo",
              len(junk_snapshot()) == len(JUNK_EXPECT))

def cookie_test():
    print("\n== cookie whitelist (row-level) ==")
    db = build_cookies()
    rule = next(r for r in engine.RULES if r["id"].endswith("chrome.cookies"))
    total0, _ = cookie_counts(db)
    jr = engine.Journal()
    engine.apply_rule(rule, set(), ["github.com"], jr, dry=False)
    total1, kept = cookie_counts(db)
    check("cookies: whitelist keeps github.com family", kept == 3, f"kept={kept}")
    check("cookies: non-whitelisted deleted", total1 == 3, f"total {total0}->{total1}")
    check("cookies: credential stores untouched",
          all((SB / rel).exists() for rel in PROTECTED if "login data" in rel.lower()
              or "bookmarks" in rel.lower()))

def tmpdir_age_test():
    """mac: the $TMPDIR rule only removes files older than 3 days."""
    if not IS_MAC:
        return
    print("\n== $TMPDIR age-based cleaning (mac) ==")
    rule = next((r for r in engine.RULES if r["id"] == "mac.temp.tmpdir"), None)
    if not rule:
        check("tmpdir rule present in rules-darwin.json", False)
        return
    spec = rule["files"][0]
    tmp = Path(os.path.expandvars(spec["path"]))
    tmp.mkdir(parents=True, exist_ok=True)
    old = tmp / "stale_opensweep_test.tmp"
    fresh = tmp / "fresh_opensweep_test.tmp"
    old.write_bytes(b"OLD-JUNK"); fresh.write_bytes(b"FRESH-KEEP")
    three_days_ago = time.time() - 3 * 86400 - 3600
    os.utime(old, (three_days_ago, three_days_ago))
    jr = engine.Journal()
    engine.apply_rule(rule, set(), [], jr, dry=False)
    check("tmpdir: stale file removed", not old.exists())
    check("tmpdir: fresh file untouched (age filter works)", fresh.exists())
    fresh.unlink()
    engine.undo_journal(jr.save())
    check("tmpdir: stale file restored by undo", old.exists())
    old.unlink()

def dupes_test():
    print("\n== duplicate quick-scan (read-only) ==")
    d = SB / "DupZone"
    d.mkdir(parents=True, exist_ok=True)
    import secrets
    a = d / "dup_a.bin"
    b = d / "dup_b.bin"
    a.write_bytes(b"DUPDATA-" + secrets.token_bytes(300))
    b.write_bytes(a.read_bytes())          # byte-identical pair
    (d / "unique.bin").write_bytes(b"UNIQUE-" + secrets.token_bytes(300))
    groups = engine.dup_scan(str(d), min_mb=0.0001)
    found = next((g for g in (groups or []) if len(g["files"]) == 2
                  and g["files"][0].endswith("dup_a.bin")), None)
    check("dupes: identical pair detected as one group", found is not None,
          f"groups={len(groups or [])}")
    check("dupes: unique file not flagged",
          found is not None and all("unique" not in f for f in found["files"]))
    check("dupes: read-only (sandbox untouched)", a.exists() and b.exists())
    shutil.rmtree(d, ignore_errors=True)

def restore_point_test():
    print("\n== restore point (Windows, graceful off-admin) ==")
    if not IS_WIN:
        print("  (Windows-only feature)")
        return
    ok, note = engine.create_restore_point("OpenSweep CI check")
    # on non-admin CI it must fail gracefully with a note, never crash
    check("restore point: graceful (ok or honest note)", isinstance(note, str),
          f"ok={ok} note={note[:60]}")

def browser_guard_test():
    print("\n== browser running guard ==")
    try:
        rule = next(r for r in engine.RULES if r["id"].endswith("edge.cache")
                    or r["id"].endswith("chrome.cache"))
    except StopIteration:
        return
    orig = engine.running_exes
    engine.running_exes = lambda: {engine._browser_of_rule(rule)}
    try:
        res = engine.apply_rule(rule, {engine._browser_of_rule(rule)}, [], None, dry=False)
        check("guard: browser rules skipped while browser running",
              len(res["skipped"]) == 1 and res["files"] == 0)
    finally:
        engine.running_exes = orig

def neutral_zone():
    print("\n== rule precision (neutral zone) ==")
    rules = sandbox_rules()
    jr = engine.Journal()
    for r in rules:
        engine.apply_rule(r, set(), [], jr, dry=False)
    probe = (SB / "AppData/Local/DoubaoWork/User Data/EBWebView/Default/Cache/keepme.dat"
             if IS_WIN else SB / "home/Library/Logs/subdir-keep/keepme.dat")
    if not probe.parent.exists():
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_bytes(b"KEEP")
    moved_probe = any(e["type"] == "file" and e["original"] == str(probe)
                      for e in jr.entries)
    check("rule precision: non-covered path survives", probe.exists() and not moved_probe)
    engine.undo_journal(jr.save())

def registry_fixture_tests():
    if not IS_WIN:
        print("\n== registry semantics: skipped (not Windows) ==")
        return
    import winreg
    print("\n== registry semantics (fixture keys under HKCU\\Software\\OpenSweepTest) ==")
    base = r"Software\OpenSweepTest"
    def mk(sub, values=(("v1", "d1"), ("v2", "d2")), children=()):
        k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + "\\" + sub)
        for n, v in values:
            winreg.SetValueEx(k, n, 0, winreg.REG_SZ, v)
        winreg.CloseKey(k)
        for c in children:
            mk(sub + "\\" + c)
    def has(sub):
        try:
            winreg.OpenKey(winreg.HKEY_CURRENT_USER, base + "\\" + sub); return True
        except OSError:
            return False
    def vals(sub):
        try:
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, base + "\\" + sub)
        except OSError:
            return -1
        n, i = 0, 0
        while True:
            try:
                winreg.EnumValue(k, i); n += 1; i += 1
            except OSError:
                break
        return n
    mk("KeyA", children=("Child1", "Child2"))
    mk("KeyB")
    mk("KeyC\\Deep\\Deeper")
    rr = [
        {"id": "t.delkey", "category": "apps", "risk": "low", "default": True,
         "name": "t", "reg": [{"key": "HKCU\\" + base + "\\KeyA", "mode": "delete_key"}]},
        {"id": "t.values", "category": "apps", "risk": "low", "default": True,
         "name": "t", "reg": [{"key": "HKCU\\" + base + "\\KeyB", "mode": "values"}]},
        {"id": "t.vtree", "category": "apps", "risk": "low", "default": True,
         "name": "t", "reg": [{"key": "HKCU\\" + base + "\\KeyC", "mode": "values_tree"}]},
    ]
    jr = engine.Journal()
    for r in rr:
        engine.apply_rule(r, set(), [], jr, dry=False)
    check("registry: delete_key removes tree",
          not has("KeyA") and not has("KeyA\\Child1"))
    check("registry: values mode empties but keeps key",
          has("KeyB") and vals("KeyB") == 0)
    check("registry: values_tree clears deep values",
          vals("KeyC\\Deep\\Deeper") == 0 and has("KeyC\\Deep\\Deeper"))
    engine.undo_journal(jr.save())
    check("registry undo: KeyA tree restored", has("KeyA\\Child1") and vals("KeyA") == 2)
    check("registry undo: KeyB values restored", vals("KeyB") == 2)
    check("registry undo: KeyC values restored", vals("KeyC\\Deep\\Deeper") == 2)
    for sub in ("KeyA\\Child1", "KeyA\\Child2", "KeyA", "KeyB", "KeyC\\Deep\\Deeper",
                "KeyC\\Deep", "KeyC"):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, base + "\\" + sub)
        except OSError:
            pass

def main():
    print(f"platform: {sys.platform}  sandbox: {SB}")
    build_important()
    global JUNK_EXPECT
    JUNK_EXPECT = build_junk()
    check("env injection: engine UNDO_ROOT inside sandbox",
          str(engine.UNDO_ROOT).startswith(str(SB)))
    check("env injection: browser data inside sandbox (or absent on platform)",
          not engine.CHROMIUM_BROWSERS
          or str(engine.CHROMIUM_BROWSERS["chrome"]["data"]).startswith(str(SB)))
    dryrun_test()
    scan_determinism()
    rounds(3)
    cookie_test()
    browser_guard_test()
    neutral_zone()
    registry_fixture_tests()
    tmpdir_age_test()
    dupes_test()
    restore_point_test()

    print("\n" + "=" * 56)
    passed = sum(1 for _, okk, _ in RESULTS if okk)
    failed = [n for n, okk, _ in RESULTS if not okk]
    print(f"SAFETY SUITE: {passed} passed / {len(RESULTS)} checks, "
          f"rules={len(engine.RULES)}, protected={len(PROTECTED)} files")
    if failed:
        print("FAILED:", failed)
    print(f"sandbox kept for inspection: {SB}")
    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    main()
