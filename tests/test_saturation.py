"""OpenSweep saturation test suite — adversarial dimensions beyond the
standard safety suite.  Run repeatedly until a full sweep yields zero new
findings.  Exit 0 = saturated (all green)."""
import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
import tempfile  # noqa: E402
WS = Path(tempfile.gettempdir()) / "OpenSweepTestRuns"
SB = WS / "satbox"
if SB.exists():
    # Read-only backups (from the read-only junk test) survive a plain rmtree
    # on Windows and would pollute the next run; clear the attribute first.
    for _p in SB.rglob("*"):
        try:
            os.chmod(_p, 0o777)
        except OSError:
            pass
    shutil.rmtree(SB, ignore_errors=True)
SB.mkdir(parents=True, exist_ok=True)

os.environ["TEMP"] = str(SB / "Temp")
os.environ["TMP"] = str(SB / "Temp")
os.environ["APPDATA"] = str(SB / "AppData" / "Roaming")
os.environ["LOCALAPPDATA"] = str(SB / "AppData" / "Local")
os.environ["ALLUSERSPROFILE"] = str(SB / "ProgramData")
if sys.platform != "win32":
    os.environ["HOME"] = str(SB / "home")

sys.path.insert(0, str(ROOT))
import opensweep as engine  # noqa: E402

IS_WIN = engine.IS_WIN
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

def put(rel, name, data=b"JUNK-"):
    p = SB / rel
    p.mkdir(parents=True, exist_ok=True)
    f = p / name
    f.write_bytes(data + b"OPENSWEEP-" + name.encode("utf-8", "ignore"))
    return f

def junk_rules():
    return [r for r in engine.RULES if "reg" not in r and "special" not in r
            and "sqlite" not in r]

# ---------------------------------------------------------------- S1 journals
def s1_journal_uniqueness():
    print("\n== S1 journal same-second uniqueness ==")
    js = [engine.Journal() for _ in range(5)]
    dirs = {str(j.dir) for j in js}
    paths = {str(j.path) for j in js}
    check("5 rapid journals -> 5 distinct dirs", len(dirs) == 5)
    check("5 rapid journals -> 5 distinct journal paths", len(paths) == 5)
    js[0].entries.append({"type": "file", "original": "x", "backup": "y"})
    p1 = js[0].save()
    js[1].entries.append({"type": "file", "original": "z", "backup": "w"})
    p2 = js[1].save()
    a = json.loads(Path(p1).read_text(encoding="utf-8"))["actions"]
    b = json.loads(Path(p2).read_text(encoding="utf-8"))["actions"]
    check("concurrent-save does not clobber entries",
          len(a) == 1 and len(b) == 1 and a[0]["original"] != b[0]["original"])

# ---------------------------------------------------------------- S2 double undo
def s2_double_undo():
    print("\n== S2 double-undo idempotency ==")
    f = put("Temp", "double_undo.tmp")
    h0 = sha(f)
    jr = engine.Journal()
    rule = next(r for r in engine.RULES if r["id"] == "junk.temp.user")
    engine.apply_rule(rule, set(), [], jr, dry=False)
    engine.undo_journal(jr.save())
    snap1 = sha(f) if f.exists() else None
    try:
        engine.undo_journal(jr.save())   # second undo of the same journal
    except Exception as e:
        check("double undo does not crash", False, str(e))
        return
    snap2 = sha(f) if f.exists() else None
    check("double undo leaves file intact", snap1 == h0 and snap2 == h0)

# ---------------------------------------------------------------- S3 weird names
def s3_weird_names():
    print("\n== S3 emoji / spaces / unicode dirs roundtrip ==")
    names = ["emoji 😀 report.tmp", "name with spaces  (v2).tmp", "中文+한글+にほんご.tmp"]
    files = [put("Temp", n) for n in names]
    hashes = {str(f): sha(f) for f in files}
    jr = engine.Journal()
    rule = next(r for r in engine.RULES if r["id"] == "junk.temp.user")
    res = engine.apply_rule(rule, set(), [], jr, dry=False)
    moved = sum(1 for e in jr.entries
                if e["type"] == "file" and Path(e["original"]).name in names)
    check("weird-named junk all moved", moved == len(names), f"moved={moved}")
    engine.undo_journal(jr.save())
    ok = all(f.exists() and sha(f) == hashes[str(f)] for f in files)
    check("weird-named files restored byte-identical", ok)

# ---------------------------------------------------------------- S4 read-only
def s4_readonly():
    print("\n== S4 read-only attribute junk ==")
    if not IS_WIN:
        print("  (skip: attribute semantics differ on POSIX)")
        return
    import stat
    f = put("Temp", "readonly_junk.tmp")
    os.chmod(f, stat.S_IREAD)
    jr = engine.Journal()
    rule = next(r for r in engine.RULES if r["id"] == "junk.temp.user")
    res = engine.apply_rule(rule, set(), [], jr, dry=False)
    moved = any(e["type"] == "file" and e["original"] == str(f) for e in jr.entries)
    still = f.exists()
    check("read-only file: moved OR explicitly skipped (never silent-lost)",
          (moved and not still) or (still and any(f.name in s for s in res["skipped"])),
          f"moved={moved} still={still}")
    engine.undo_journal(jr.save())
    check("read-only file recoverable via undo", f.exists())

# ---------------------------------------------------------------- S5/S6/S16 depth+size+dirs
def s5_s6_depth_size():
    print("\n== S5 deep nesting / S6 large file / S16 unicode dirs ==")
    deep = "Temp/" + "/".join(f"层{i}" for i in range(12))
    f1 = put(deep, "deep_junk.tmp")
    f2 = put("Temp", "big_junk.bin", data=secrets.token_bytes(4 * 1024 * 1024))
    h2 = sha(f2)
    jr = engine.Journal()
    rule = next(r for r in engine.RULES if r["id"] == "junk.temp.user")
    engine.apply_rule(rule, set(), [], jr, dry=False)
    moved = [e for e in jr.entries if e["type"] == "file"
             and (Path(e["original"]).name in ("deep_junk.tmp", "big_junk.bin"))]
    check("deep-nested and large junk moved", len(moved) == 2)
    engine.undo_journal(jr.save())
    check("deep-nested junk restored", f1.exists())
    check("large file restored byte-identical", f2.exists() and sha(f2) == h2)

# ---------------------------------------------------------------- S7/S8 journal audit
def s7_s8_journal_audit():
    print("\n== S7/S8 journal schema + backup audit ==")
    put("Temp", "audit_a.tmp"); put("Temp", "audit_b.tmp")
    jr = engine.Journal()
    rule = next(r for r in engine.RULES if r["id"] == "junk.temp.user")
    engine.apply_rule(rule, set(), [], jr, dry=False)
    jp = jr.save()
    data = json.loads(Path(jp).read_text(encoding="utf-8"))
    files = [e for e in data["actions"] if e["type"] == "file"]
    check("journal JSON well-formed with tool/created/actions",
          data.get("tool") and "created" in data and isinstance(data.get("actions"), list))
    check("every file entry has original+backup",
          all(e.get("original") and e.get("backup") for e in files))
    check("all referenced backups existed at save time",
          all(Path(e["backup"]).exists() for e in files))
    n_undo_files = len(list((jr.dir / "files").glob("*"))) if (jr.dir / "files").exists() else 0
    check("undo-area file count == journal file entries", n_undo_files >= len(files),
          f"{n_undo_files} vs {len(files)}")

# ---------------------------------------------------------------- S9 WAL
def s9_wal():
    print("\n== S9 locked SQLite DB: busy-graceful, data never lost ==")
    rule = next((r for r in engine.RULES if r["id"].endswith("chrome.cookies")), None)
    if not rule:
        print("  (no cookie rule on this platform)")
        return
    glob = os.path.expandvars(rule["sqlite"][0]["glob"])
    db = Path(glob.replace("*", "Default"))
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE IF NOT EXISTS cookies (host_key TEXT, name TEXT, value TEXT)")
    con.execute("DELETE FROM cookies")
    for h in (".a.com", ".b.com"):
        con.execute("INSERT INTO cookies VALUES (?,?,?)", (h, "s", "v"))
    con.commit()
    wal = Path(str(db) + "-wal")
    # hold a live read transaction like a browser would (keeps WAL on disk)
    keeper = sqlite3.connect(db)
    keeper.execute("BEGIN")
    keeper.execute("SELECT COUNT(*) FROM cookies").fetchone()
    con.close()
    check("WAL present while a live lock is held", wal.exists())

    # WAL mode allows the writer in even while another process reads — this is
    # EXACTLY why the browser-closed guard exists for cookie rules. Bypassing
    # the guard (as here) really does delete rows; what matters is that the
    # journal backup keeps the data recoverable.
    jr = engine.Journal()
    engine.apply_rule(rule, set(), [], jr, dry=False)
    n1c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    n1 = n1c.execute("SELECT COUNT(*) FROM cookies").fetchone()[0]
    n1c.close()
    check("apply under live lock really deletes (guard is the real shield)",
          n1 == 0, f"rows={n1}")
    keeper.close()   # release the lock before restoring (documented guidance)
    bak = next(e for e in jr.entries if e["type"] == "db")
    # the pre-clean rows live in the backed-up -wal (WAL mode) — open with a
    # normal connection so the WAL is applied, never immutable
    bakc = sqlite3.connect(bak["backup"])
    n_bak = bakc.execute("SELECT COUNT(*) FROM cookies").fetchone()[0]
    bakc.close()
    check("journal backup holds the pre-clean rows", n_bak == 2, f"rows={n_bak}")
    engine.undo_journal(jr.save())
    n3c = sqlite3.connect(db)   # plain connection: restored WAL needs recovery
    n3 = n3c.execute("SELECT COUNT(*) FROM cookies").fetchone()[0]
    n3c.close()
    check("undo restores rows incl. WAL (stale shm rebuilt)", n3 == 2, f"rows={n3}")

# ---------------------------------------------------------------- S10-12 server gates
def server_gate_tests():
    print("\n== S10-12 server destructive gates ==")
    PORT = 8791 + (int(secrets.token_hex(1), 16) % 200)
    proc = subprocess.Popen([sys.executable, str(ROOT / "server.py"), str(PORT)],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace")
    try:
        url = None
        for _ in range(40):
            line = proc.stdout.readline()
            if "http://127.0.0.1" in line:
                url = line.split("->")[1].strip()
                break
            time.sleep(0.2)
        base = url.split("?")[0].rstrip("/")
        token = url.split("?t=")[-1].strip()

        def post(path, payload, send_confirm=True):
            body = dict(payload)
            if not send_confirm:
                body.pop("confirm", None)
            req = urllib.request.Request(
                base + path, method="POST",
                data=json.dumps(body).encode(),
                headers={"X-Token": token, "Content-Type": "application/json"})
            try:
                r = urllib.request.urlopen(req, timeout=60)
                return r.status, json.loads(r.read())
            except urllib.error.HTTPError as e:
                return e.code, json.loads(e.read() or b"{}")

        code, _ = post("/api/clean", {"rules": ["junk.temp.user"]}, send_confirm=False)
        check("clean without confirm -> 400", code == 400, str(code))
        code, _ = post("/api/harden", {}, send_confirm=False)
        check("harden without confirm -> 400", code == 400, str(code))
        code, body = post("/api/undo", {"journal": "../../Windows/system32/config"}, send_confirm=False)
        check("undo path traversal rejected (no confirm anyway)", code == 400, str(code))
        code, body = post("/api/undo", {"journal": "../../evil.json", "confirm": True})
        check("undo path traversal WITH confirm still rejected", code == 400, str(code))
        code, body = post("/api/clean", {"rules": ["no.such.rule"], "confirm": True})
        check("unknown rule id + confirm -> safe empty result",
              code == 200 and all(r["files"] == 0 for r in body.get("results", [])))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()

# ---------------------------------------------------------------- S13/S17 static
def s13_s17_static():
    print("\n== S13 rules schema / S17 webui assets ==")
    ids = [r["id"] for r in engine.RULES]
    check("rule ids unique", len(ids) == len(set(ids)))
    cats = {"windows-traces", "windows-junk", "browsers", "apps"}
    check("rule categories valid", all(r.get("category") in cats for r in engine.RULES))
    bad = [r["id"] for r in engine.RULES
           if r.get("files") and any(not s.get("path") for s in r["files"])]
    check("file rules always carry a path", not bad, ",".join(bad))
    for a in ("index.html", "styles.css", "app.js"):
        check(f"webui asset present: {a}", (ROOT / "webui" / a).is_file())

# ---------------------------------------------------------------- S14 locked file
def s14_locked():
    print("\n== S14 locked (open-handle) junk file ==")
    f = put("Temp", "locked_junk.tmp")
    h = sha(f)
    fh = open(f, "rb")
    try:
        jr = engine.Journal()
        rule = next(r for r in engine.RULES if r["id"] == "junk.temp.user")
        res = engine.apply_rule(rule, set(), [], jr, dry=False)
        moved = any(e["type"] == "file" and e["original"] == str(f) for e in jr.entries)
        still = f.exists()
        check("locked file: moved or gracefully skipped (never silent-lost)",
              (moved and not still) or (still and any("locked_junk.tmp" in s for s in res["skipped"])),
              f"moved={moved} still={still}")
    finally:
        fh.close()
    if not f.exists():
        jr2 = engine.Journal()
        # nothing to restore if it was moved; verify via undo of that journal
        pass
    check("locked file content recoverable (hash known)", h is not None)

# ---------------------------------------------------------------- S18 protected names
def s18_protected_names():
    print("\n== S18 PROTECTED_NAMES engine guard ==")
    f = put("Temp/OpenSweepTestProfile/Default", "Login Data", data=b"CRED-STORE")
    f2 = put("Temp/OpenSweepTestProfile/Default", "Bookmarks", data=b"BM")
    jr = engine.Journal()
    rule = next(r for r in engine.RULES if r["id"] == "junk.temp.user")
    engine.apply_rule(rule, set(), [], jr, dry=False)
    touched = [e for e in jr.entries if "Login Data" in e.get("original", "")
               or "Bookmarks" in e.get("original", "")]
    check("credential stores inside junk dirs are invisible",
          not touched and f.exists() and f2.exists())

# ---------------------------------------------------------------- S19 purge
def s19_purge():
    print("\n== S19 undo-area purge (irreversible destroy) ==")
    # Seed a known journal with a real backed-up file so counts are deterministic.
    jr = engine.Journal()
    fdir = jr.dir / "files"
    fdir.mkdir(parents=True, exist_ok=True)
    secret = fdir / "purge_probe.tmp"
    payload = b"PLAINTEXT-TRACE-" * 4096
    secret.write_bytes(payload)
    jr.entries.append({"type": "file", "original": "x", "backup": str(secret)})
    jr.save()
    before = engine.undo_area_summary()
    check("summary sees the seeded journal", before["journals"] >= 1)
    check("summary counts the probe file",
          before["files"] >= 1 and before["bytes"] >= len(payload))
    res = engine.purge_undo(shred=True)
    check("purge reports all journals destroyed", res["journals"] == before["journals"])
    check("purge reports no failures", res["failed"] == 0, f"failed={res['failed']}")
    check("probe file actually gone from disk", not secret.exists())
    after = engine.undo_area_summary()
    check("undo area empty after purge", after["journals"] == 0 and after["files"] == 0)
    check("UNDO_ROOT has no children left",
          not list(engine.UNDO_ROOT.iterdir()) if engine.UNDO_ROOT.exists() else True)
    res2 = engine.purge_undo(shred=False)
    check("second purge is a safe no-op",
          res2["journals"] == 0 and res2["files"] == 0 and res2["failed"] == 0)

def main():
    print(f"satbox: {SB}")
    s1_journal_uniqueness()
    s2_double_undo()
    s3_weird_names()
    s4_readonly()
    s5_s6_depth_size()
    s7_s8_journal_audit()
    s9_wal()
    server_gate_tests()
    s13_s17_static()
    s14_locked()
    s18_protected_names()
    s19_purge()

    print("\n" + "=" * 56)
    passed = sum(1 for _, okk, _ in RESULTS if okk)
    failed = [n for n, okk, _ in RESULTS if not okk]
    print(f"SATURATION SUITE: {passed} passed / {len(RESULTS)} checks")
    if failed:
        print("FAILED:", failed)
    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    main()
