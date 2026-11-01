#!/usr/bin/env python3
"""OpenSweep - a clean-room, zero-dependency, zero-network privacy trace
cleaner for Windows.

Inspired by the *functionality* of commercial system cleaners; contains no
code, assets, or rule text from any commercial product. Cleaning-rule
locations (Windows MRU registry keys, browser cache paths) are public
forensic facts. Ships with safer defaults than the original: every mutation
is journaled and reversible via `undo`, browsers must be closed before
their profile data is touched, and saved passwords are never touched.

Usage:
  python -I opensweep.py scan   [--category CAT] [--rule ID] [--json]
  python -I opensweep.py rules
  python -I opensweep.py apply  [--category CAT] [--rule ID] [--all]
                                [--yes] [--keep-cookies "a.com,b.org"]
  python -I opensweep.py harden [--yes] [--json]   # Windows privacy settings
  python -I opensweep.py tools  [--winget]         # companion-tool layer
  python -I opensweep.py undo   <journal.json>

Architecture (v2.0 "compose & borrow"):
  - cleaning rules live in external declarative rules.json (CleanerML idea,
    own schema/content)
  - Windows privacy-settings hardening in harden.json (Sophia/privacy.sexy
    idea, own content)
  - `tools` surfaces companion programs instead of reimplementing them
"""
import argparse
import ctypes
import datetime
import fnmatch
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
if IS_WIN:
    import winreg
else:  # registry layer is Windows-only; macOS uses the file/sqlite ruleset
    winreg = None

TOOL = "OpenSweep v3.0-oss"
UNDO_ROOT = Path(os.environ.get("TEMP", r"C:\Temp")) / "OpenSweepUndo"

# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def log(msg):
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        # GBK console: never die on vendor names with ™/é etc.
        print(msg.encode(sys.stdout.encoding or "gbk", "replace").decode(sys.stdout.encoding or "gbk"),
              flush=True)

def human(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return f"{n:,.0f} {u}" if u == "B" else f"{n:,.1f} {u}"
        n /= 1024

def running_exes():
    """Lowercased set of running program base names (no .exe / path)."""
    try:
        if IS_WIN:
            out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"],
                                 capture_output=True, text=True, timeout=20).stdout.lower()
            names = set()
            for line in out.splitlines():
                if line.startswith('"'):
                    names.add(line.split('","')[0].strip('"').removesuffix(".exe"))
            return names
        # POSIX: comm may carry a full path; keep the basename
        out = subprocess.run(["ps", "-axo", "comm="] if IS_MAC else ["ps", "-eo", "comm="],
                             capture_output=True, text=True, timeout=20).stdout.lower()
        return {os.path.basename(line.strip().removesuffix(".exe"))
                for line in out.splitlines() if line.strip()}
    except Exception:
        return set()

if IS_WIN:
    HKEYS = {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE}
    HKEY_NAMES = {v: k for k, v in HKEYS.items()}
else:
    HKEYS, HKEY_NAMES = {}, {}

def open_key(hive, subkey, writable=False):
    return winreg.OpenKey(hive, subkey, 0,
                          winreg.KEY_ALL_ACCESS if writable else winreg.KEY_READ)

def reg_tree_values(root):
    """Yield (full_subkey_path, value_name) for every value under root."""
    hive, subkey = root
    stack = [subkey]
    while stack:
        cur = stack.pop()
        try:
            with open_key(hive, cur) as k:
                i = 0
                while True:
                    try:
                        name, _, _ = winreg.EnumValue(k, i)
                        yield (cur, name)
                        i += 1
                    except OSError:
                        break
        except OSError:
            continue
        try:
            with open_key(hive, cur) as k:
                i = 0
                while True:
                    try:
                        child = winreg.EnumKey(k, i)
                        stack.append(cur + "\\" + child)
                        i += 1
                    except OSError:
                        break
        except OSError:
            continue

def reg_count_values(root):
    return sum(1 for _ in reg_tree_values(root))

def reg_delete_tree(hive, subkey):
    try:
        with open_key(hive, subkey, writable=True) as k:
            while True:
                try:
                    child = winreg.EnumKey(k, 0)
                except OSError:
                    break
                reg_delete_tree(hive, subkey + "\\" + child)
            winreg.DeleteKey(k, "")
        return True
    except OSError:
        return False

def reg_delete_values(hive, subkey, names=None):
    """Delete all (or named) values of one key. Returns count deleted."""
    n = 0
    try:
        with open_key(hive, subkey, writable=True) as k:
            existing = []
            i = 0
            while True:
                try:
                    existing.append(winreg.EnumValue(k, i)[0])
                    i += 1
                except OSError:
                    break
            for name in existing:
                if names is None or name in names:
                    try:
                        winreg.DeleteValue(k, name)
                        n += 1
                    except OSError:
                        pass
    except OSError:
        pass
    return n

def reg_delete_values_tree(root):
    """Delete every value in a key tree, keep the keys."""
    hive, subkey = root
    n = 0
    for cur, name in list(reg_tree_values(root)):
        n += reg_delete_values(hive, cur, {name})
    return n

def reg_export(full_key, out_file):
    try:
        subprocess.run(["reg", "export", full_key, str(out_file), "/y"],
                       capture_output=True, timeout=30, check=True)
        return True
    except Exception:
        return False

def glob_resolve(pattern):
    """Expand a path pattern possibly containing wildcards to existing paths."""
    p = Path(os.path.expandvars(pattern))
    if not any(ch in p.as_posix() for ch in "*?"):
        return [p] if p.exists() else []
    parts = p.parts
    # find first wildcard segment
    fixed = Path(parts[0])
    i = 1
    while i < len(parts) and not any(ch in parts[i] for ch in "*?"):
        fixed /= parts[i]
        i += 1
    # os.sep: backslash on Windows (pathlib accepts it), forward slash on POSIX
    rest = os.sep.join(parts[i:]) or "*"
    try:
        return [x for x in fixed.glob(rest)]
    except Exception:
        return []

UNDO_PREFIX = str(UNDO_ROOT).lower() + os.sep

# credential/bookmark stores are invisible to EVERY rule, wherever they sit
# (live drill found a browser profile copy inside %TEMP% — these must never
# be cleaned, not even into the undo area)
PROTECTED_NAMES = {"login data", "login data-journal", "bookmarks", "bookmarks.bak"}

def iter_file_candidates(spec):
    """Yield candidate files for a files-spec. Handles file-type bases (the
    path itself IS the target), never returns anything inside the undo area
    (self-contamination guard), and never returns credential/bookmark stores."""
    for base in glob_resolve(spec["path"]):
        pats = [p.strip() for p in spec["patterns"].split(";") if p.strip()]
        if base.is_file():
            if (base.name.lower() not in PROTECTED_NAMES
                    and any(fnmatch.fnmatch(base.name.lower(), p.lower()) for p in pats)):
                yield base
            continue
        for pat in pats:
            try:
                it = base.rglob(pat) if spec.get("recurse") else base.glob(pat)
                for f in it:
                    if str(f).lower().startswith(UNDO_PREFIX):
                        continue
                    if f.is_file() and f.name.lower() in PROTECTED_NAMES:
                        continue
                    yield f
            except OSError:
                continue

def cookie_domain_clause(col, domain):
    dom = re.sub(r"[^a-z0-9.-]", "", domain.lower())
    if not dom:
        return None
    return f"({col} = '{dom}' OR {col} LIKE '%.{dom}')"

def table_where(t, keep_cookies):
    """Build the WHERE clause for one sqlite table action."""
    where = t.get("where", "")
    if where == "KEEP":
        col = t.get("col", "host_key")
        clauses = [c for c in (cookie_domain_clause(col, d) for d in keep_cookies) if c]
        return ("NOT (" + " OR ".join(clauses) + ")") if clauses else ""
    return where

# --------------------------------------------------------------------------
# rule source data (external declarative files; public forensic locations)
# --------------------------------------------------------------------------

LOCAL = os.environ.get("LOCALAPPDATA", "")
APPDATA = os.environ.get("APPDATA", "")
HOME = os.path.expanduser("~")

if IS_WIN:
    CHROMIUM_BROWSERS = {
        "edge":   {"data": rf"{LOCAL}\Microsoft\Edge\User Data", "proc": "msedge"},
        "chrome": {"data": rf"{LOCAL}\Google\Chrome\User Data",  "proc": "chrome"},
    }
elif IS_MAC:
    CHROMIUM_BROWSERS = {
        "edge":   {"data": rf"{HOME}/Library/Application Support/Microsoft Edge", "proc": "msedge"},
        "chrome": {"data": rf"{HOME}/Library/Application Support/Google/Chrome",  "proc": "chrome"},
    }
else:
    CHROMIUM_BROWSERS = {}

SCRIPT_DIR = Path(__file__).resolve().parent

def _load_rules():
    """Load cleaning rules from the platform's declarative rules file
    (CleanerML-inspired idea; own schema and content)."""
    fname = "rules-windows.json" if IS_WIN else "rules-darwin.json"
    f = SCRIPT_DIR / fname
    if not f.exists():
        print(f"[opensweep] no rules file for this platform ({fname}); "
              "only generic features available", flush=True)
        return []
    data = json.loads(f.read_text(encoding="utf-8-sig"))
    for r in data:
        if not r.get("id") or not r.get("category"):
            raise ValueError(f"bad rule entry: {r!r}")
    return data

RULES = _load_rules()

# --------------------------------------------------------------------------
# scanning
# --------------------------------------------------------------------------

def sqlite_targets(spec):
    return glob_resolve(spec["glob"])

def sqlite_count(db, tables, keep_cookies=None):
    total = 0
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro&immutable=1", uri=True, timeout=2)
        for t in tables:
            try:
                where = table_where(t, keep_cookies or [])
                sql = f'SELECT COUNT(*) FROM "{t["table"]}"'
                if where:
                    sql += f" WHERE {where}"
                total += con.execute(sql).fetchone()[0]
            except sqlite3.Error:
                pass
        con.close()
    except sqlite3.Error:
        pass
    return total

def scan_rule(rule, browsers_running, keep_cookies):
    """Return dict findings summary (read-only)."""
    res = {"id": rule["id"], "name": rule["name"], "category": rule["category"],
           "risk": rule["risk"], "items": 0, "bytes": 0, "notes": []}

    running = browsers_running
    if rule.get("browser"):
        bid = rule["browser"]
        proc = CHROMIUM_BROWSERS.get(bid, {}).get("proc", bid)
        if proc in running:
            res["notes"].append(f"{proc}.exe running - deep scan skipped")
            if rule.get("needs_close"):
                res["notes"].append("must close browser before cleaning")

    for spec in rule.get("files", []):
        seen = set()
        for f in iter_file_candidates(spec):
            if f in seen or not f.is_file():
                continue
            seen.add(f)
            try:
                res["bytes"] += f.stat().st_size
                res["items"] += 1
            except OSError:
                pass

    for spec in rule.get("sqlite", []):
        skip_db = bool(rule.get("needs_close")) and _browser_of_rule(rule) in browsers_running
        for db in sqlite_targets(spec):
            if skip_db:
                if "row counts n/a while browser running" not in res["notes"]:
                    res["notes"].append("row counts n/a while browser running")
                continue
            n = sqlite_count(db, spec["tables"], keep_cookies)
            res["items"] += n
            try:
                res["bytes"] += Path(db).stat().st_size
            except OSError:
                pass

    for spec in rule.get("reg", []):
        hive, subkey = parse_key(spec["key"])
        if not subkey:
            continue
        root = (hive, subkey)
        if spec["mode"] in ("delete_key",):
            res["items"] += reg_count_values(root)  # values about to vanish
        elif spec["mode"] in ("values", "values_tree"):
            res["items"] += reg_count_values(root)

    for sp in rule.get("special", []):
        res["notes"].append(sp)
    return res

def _browser_of_rule(rule):
    return CHROMIUM_BROWSERS.get(rule.get("browser", ""), {}).get("proc", rule.get("browser", ""))

def parse_key(k):
    k = k.strip()
    hive_name, _, rest = k.partition("\\")
    hive = HKEYS.get(hive_name.upper())
    return (hive, rest.strip("\\")) if hive else (None, None)

# --------------------------------------------------------------------------
# apply (with journal)
# --------------------------------------------------------------------------

class Journal:
    def __init__(self):
        UNDO_ROOT.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        d = UNDO_ROOT / ts
        i = 2
        while d.exists():  # same-second collisions get unique suffixes
            d = UNDO_ROOT / f"{ts}-{i}"
            i += 1
        d.mkdir(parents=True, exist_ok=True)
        self.dir = d
        self.entries = []
        self.path = UNDO_ROOT / f"{d.name}.json"

    def save(self):
        self.path.write_text(json.dumps({"tool": TOOL, "created": self.dir.name,
                                         "actions": self.entries}, indent=1), encoding="utf-8")
        return self.path

def apply_rule(rule, browsers_running, keep_cookies, journal, dry=False):
    res = {"id": rule["id"], "deleted_values": 0, "deleted_keys": 0, "files": 0,
           "rows": 0, "bytes": 0, "skipped": [], "notes": []}

    if rule.get("browser"):
        proc = _browser_of_rule(rule)
        if rule.get("needs_close") and proc in browsers_running:
            res["skipped"].append(f"{proc}.exe running")
            return res

    for spec in rule.get("files", []):
        if not dry:
            (journal.dir / "files").mkdir(parents=True, exist_ok=True)
        for f in iter_file_candidates(spec):
            if not f.is_file():
                continue
            try:
                size = f.stat().st_size
                if dry:
                    res["files"] += 1
                    res["bytes"] += size
                    continue
                dest = journal.dir / "files" / f.name
                i = 1
                while dest.exists():
                    dest = journal.dir / "files" / f"{f.stem}_{i}{f.suffix}"
                    i += 1
                try:
                    shutil.move(str(f), str(dest))
                except OSError:
                    # long/odd names: mangle the BACKUP name (journal still
                    # records the exact original path, so undo is unaffected)
                    h = hashlib.sha256(str(f).encode("utf-8")).hexdigest()[:8]
                    budget = max(20, 235 - len(str(journal.dir / "files")))
                    dest = journal.dir / "files" / (h + f.suffix)[:budget]
                    shutil.move(str(f), str(dest))
                journal.entries.append({"type": "file", "original": str(f),
                                        "backup": str(dest)})
                res["files"] += 1
                res["bytes"] += size
            except OSError as e:
                res["skipped"].append(f"{f.name}: {e.strerror or e}")

    for spec in rule.get("sqlite", []):
        for db in sqlite_targets(spec):
            if not Path(db).exists():
                continue
            if dry:
                # read-only estimate; never open the live DB for writing
                res["rows"] += sqlite_count(db, spec["tables"], keep_cookies)
                try:
                    res["bytes"] += Path(db).stat().st_size
                except OSError:
                    pass
                continue
            try:
                db = str(db)
                bak = journal.dir / "db" / Path(db).name
                bak.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(db, bak)
                for ext in ("-wal",):   # -shm is transient; never copy it
                    if Path(db + ext).exists():
                        shutil.copy2(db + ext, str(bak) + ext)
                con = sqlite3.connect(db, timeout=5)
                for t in spec["tables"]:
                    sql = f'DELETE FROM "{t["table"]}"'
                    where = table_where(t, keep_cookies)
                    if where:
                        sql += f" WHERE {where}"
                    try:
                        cur = con.execute(sql)
                        res["rows"] += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
                    except sqlite3.Error as e:
                        res["skipped"].append(f"{Path(db).name}:{t['table']}: {e}")
                con.commit()
                con.close()
                journal.entries.append({"type": "db", "original": db,
                                        "backup": str(bak)})
            except (sqlite3.Error, OSError) as e:
                res["skipped"].append(f"{Path(db).name}: {e}")

    for spec in rule.get("reg", []):
        hive, subkey = parse_key(spec["key"])
        if not hive or not subkey:
            continue
        if dry:
            res["deleted_values"] += reg_count_values((hive, subkey))
            continue
        full = f"{HKEY_NAMES[hive]}\\{subkey}"
        bak = journal.dir / "reg" / (subkey.replace("\\", "_") + ".reg")
        bak.parent.mkdir(parents=True, exist_ok=True)
        reg_export(full, bak)
        mode = spec["mode"]
        if mode == "delete_key":
            n = reg_count_values((hive, subkey))
            if reg_delete_tree(hive, subkey):
                res["deleted_keys"] += 1
                res["deleted_values"] += n
                journal.entries.append({"type": "regkey", "key": full,
                                        "backup": str(bak) if bak.exists() else None})
        elif mode == "values":
            n = reg_delete_values(hive, subkey, set(spec.get("values", [])) or None)
            res["deleted_values"] += n
            if n:
                journal.entries.append({"type": "regkey", "key": full,
                                        "backup": str(bak) if bak.exists() else None})
        elif mode == "values_tree":
            n = reg_delete_values_tree((hive, subkey))
            res["deleted_values"] += n
            if n:
                journal.entries.append({"type": "regkey", "key": full,
                                        "backup": str(bak) if bak.exists() else None})

    for sp in rule.get("special", []):
        if dry:
            res["notes"].append(f"would run: {sp}")
            continue
        if sp == "flushdns":
            if IS_WIN:
                subprocess.run(["ipconfig", "/flushdns"], capture_output=True)
            elif IS_MAC:
                subprocess.run(["dscacheutil", "-flushcache"], capture_output=True)
                subprocess.run(["killall", "-INFO", "mDNSResponder"], capture_output=True)
            res["notes"].append("DNS cache flushed (no undo needed)")
        elif sp == "recyclebin":
            if not IS_WIN:
                res["notes"].append("recyclebin special is Windows-only; skipped")
                continue
            subprocess.run(["powershell", "-NoProfile", "-Command",
                            "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"],
                           capture_output=True)
            res["notes"].append("recycle bin emptied (NOT undoable)")
    return res

def undo_journal(jpath):
    data = json.loads(Path(jpath).read_text(encoding="utf-8"))
    ok, fail = 0, 0
    for e in reversed(data["actions"]):
        try:
            t = e["type"]
            if t == "file":
                orig = Path(e["original"])
                orig.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(e["backup"], str(orig))
            elif t == "db":
                shutil.copy2(e["backup"], e["original"])
                for ext in ("-wal",):
                    b = Path(e["backup"] + ext)
                    if b.exists():
                        shutil.copy2(b, e["original"] + ext)
                shm = Path(e["original"] + "-shm")
                try:
                    if shm.exists():
                        shm.unlink()   # stale wal-index must be rebuilt, never restored
                except OSError:
                    # a live holder (e.g. an open browser) pins the shm; the
                    # db+wal restore already succeeded — advise closing it
                    e["note"] = ("db+wal restored, but the -shm file is held by "
                                 "another process; close that program so SQLite "
                                 "can rebuild the index")
            elif t == "regkey":
                if e.get("backup") and Path(e["backup"]).exists():
                    subprocess.run(["reg", "import", e["backup"]],
                                   capture_output=True, timeout=30)
            elif t == "regvalue":
                hive, subkey = parse_key(e["key"])
                k = winreg.CreateKey(hive, subkey)  # key exists post-apply; be safe
                with k:
                    if e.get("old_type") is None:
                        try:
                            winreg.DeleteValue(k, e["value"])
                        except OSError:
                            pass
                    else:
                        winreg.SetValueEx(k, e["value"], 0, e["old_type"], e["old_data"])
            ok += 1
        except Exception as ex:
            fail += 1
            log(f"  undo failed for {e.get('original', e.get('key'))}: {ex}")
    log(f"undo complete: {ok} restored, {fail} failed")

# --------------------------------------------------------------------------
# privacy hardening (Windows settings; registry locations are public facts)
# --------------------------------------------------------------------------

def _load_harden():
    if not IS_WIN:
        return []  # Windows privacy-setting hardening; N/A elsewhere
    f = SCRIPT_DIR / "harden.json"
    data = json.loads(f.read_text(encoding="utf-8-sig"))
    for h in data:
        if not h.get("id") or not h.get("set"):
            raise ValueError(f"bad harden entry: {h!r}")
    return data

REG_TYPES = {"REG_DWORD": winreg.REG_DWORD, "REG_SZ": winreg.REG_SZ} if IS_WIN else {}

def is_admin():
    if IS_WIN:
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    return hasattr(os, "geteuid") and os.geteuid() == 0

def _read_value(hive, subkey, name):
    try:
        with open_key(hive, subkey) as k:
            data, typ = winreg.QueryValueEx(k, name)
            return typ, data
    except OSError:
        return None, None

def harden_report():
    """Read-only status of every harden item (never mutates)."""
    isadm = is_admin()
    rows = []
    for h in _load_harden():
        items, exposed = [], False
        for spec in h["set"]:
            hive, subkey = parse_key(spec["key"])
            typ, data = _read_value(hive, subkey, spec["value"])
            ok = typ is not None and data == spec["data"]
            exposed |= not ok
            items.append({"key": spec["key"], "value": spec["value"],
                          "current": data if typ is not None else "(absent)",
                          "target": spec["data"], "ok": ok})
        blocked = h.get("admin", False) and not isadm
        status = "hardened" if not exposed else ("admin-required" if blocked else "exposed")
        rows.append({"id": h["id"], "name": h["name"], "risk": h.get("risk", "low"),
                     "admin": h.get("admin", False), "status": status, "items": items})
    return rows

def harden_apply(journal, dry=False):
    """Apply hardened values. Journaled + reversible (regvalue entries)."""
    isadm = is_admin()
    results = []
    for h in _load_harden():
        res = {"id": h["id"], "changed": 0, "skipped": []}
        if h.get("admin", False) and not isadm:
            res["skipped"].append("needs administrator")
            results.append(res)
            continue
        for spec in h["set"]:
            hive, subkey = parse_key(spec["key"])
            typ, data = _read_value(hive, subkey, spec["value"])
            if typ is not None and data == spec["data"]:
                continue
            if dry:
                res["changed"] += 1
                continue
            full = f"{HKEY_NAMES[hive]}\\{subkey}"
            bak = journal.dir / "reg" / (subkey.replace("\\", "_") + ".reg")
            bak.parent.mkdir(parents=True, exist_ok=True)
            reg_export(full, bak)
            try:
                # CreateKey creates the key (and intermediates) if missing
                k = winreg.CreateKey(hive, subkey)
                try:
                    winreg.SetValueEx(k, spec["value"], 0,
                                      REG_TYPES.get(spec["type"], winreg.REG_DWORD),
                                      spec["data"])
                finally:
                    k.Close()
            except OSError as e:
                res["skipped"].append(f"{spec['value']}: {e}")
                continue
            journal.entries.append({"type": "regvalue", "key": full,
                                    "value": spec["value"], "old_type": typ,
                                    "old_data": data,
                                    "backup": str(bak) if bak.exists() else None})
            res["changed"] += 1
        results.append(res)
    return results

# --------------------------------------------------------------------------
# composition layer (detect companion tools instead of reimplementing them)
# --------------------------------------------------------------------------

COMPANIONS = [
    ("winget",    ["%ProgramFiles%\\WindowsApps\\Microsoft.DesktopAppInstaller_8wekyb3d8bbwe\\winget.exe"],
     "software updates (official)", "winget upgrade"),
    ("Autoruns",  ["%ProgramFiles%\\Sysinternals\\Autoruns64.exe", "%ProgramFiles%\\Sysinternals\\Autoruns.exe"],
     "startup points enumeration", "run GUI"),
    ("BCU",       ["%ProgramFiles%\\Bulk Crap Uninstaller\\BCUninstaller.exe",
                   "%LocalAppData%\\Programs\\Bulk Crap Uninstaller\\BCUninstaller.exe"],
     "bulk uninstall + leftovers", "run GUI"),
    ("dupeGuru",  ["%ProgramFiles%\\dupeguru\\dupeguru.exe", "%LocalAppData%\\Programs\\dupeguru\\dupeguru.exe"],
     "duplicate file finder", "run GUI"),
    ("Eraser",    ["%ProgramFiles%\\Eraser\\Eraser.exe"],
     "file shredding / wiping", "run GUI"),
    ("BleachBit", ["%ProgramFiles%\\BleachBit\\bleachbit.exe", "%LocalAppData%\\Programs\\BleachBit\\bleachbit.exe"],
     "peer cleaner (GPL)", "bleachbit.exe --preview"),
    ("UniGetUI",  ["%LocalAppData%\\Programs\\UniGetUI\\UniGetUI.exe"],
     "package manager GUI", "run GUI"),
]

def tools_report():
    rows = []
    for name, paths, purpose, cmd in COMPANIONS:
        found = ""
        for p in paths:
            p2 = os.path.expandvars(p)
            if Path(p2).exists():
                found = p2
                break
        if not found and name == "winget":
            found = shutil.which("winget") or ""
        rows.append({"tool": name, "present": bool(found), "path": found,
                     "purpose": purpose, "usage": cmd})
    return rows

# --------------------------------------------------------------------------
# read-only inventories (composition parity with CCleaner's other tabs;
# every function here is strictly read-only)
# --------------------------------------------------------------------------

def startup_report():
    """Autostart inventory (read-only). Borrowed *idea* from Autoruns; deep
    control still belongs to Autoruns (win) / launchctl (mac)."""
    items = []
    if IS_WIN:
        run_keys = [
            ("HKCU", winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
            ("HKLM", winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
            ("HKLM", winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"),
        ]
        for hive_name, hive, sub in run_keys:
            try:
                with open_key(hive, sub) as k:
                    i = 0
                    while True:
                        try:
                            name, val, _ = winreg.EnumValue(k, i)
                            items.append({"kind": "Run", "where": hive_name,
                                          "name": name, "cmd": str(val)[:150]})
                            i += 1
                        except OSError:
                            break
            except OSError:
                pass
        for env in ("APPDATA", "ALLUSERSPROFILE"):
            base = (Path(os.path.expandvars(f"%{env}%"))
                    / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup")
            try:
                for f in base.iterdir():
                    if f.is_file():
                        items.append({"kind": "Folder", "where": "Startup",
                                      "name": f.name, "cmd": str(f)[:150]})
            except OSError:
                pass
        # auto-start services (read-only; capped)
        try:
            with open_key(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services") as rk:
                names = []
                i = 0
                while True:
                    try:
                        names.append(winreg.EnumKey(rk, i)); i += 1
                    except OSError:
                        break
                for sub in names:
                    if len([x for x in items if x["kind"] == "Service"]) >= 200:
                        break
                    try:
                        with open_key(winreg.HKEY_LOCAL_MACHINE,
                                      rf"SYSTEM\CurrentControlSet\Services\{sub}") as k:
                            start = winreg.QueryValueEx(k, "Start")[0]
                            if start != 2:
                                continue
                            try:
                                img = str(winreg.QueryValueEx(k, "ImagePath")[0])
                            except OSError:
                                continue
                            if ".exe" not in img.lower():
                                continue
                            items.append({"kind": "Service", "where": "HKLM",
                                          "name": sub, "cmd": img[:150]})
                    except OSError:
                        continue
        except OSError:
            pass
    elif IS_MAC:
        # LaunchAgents / LaunchDaemons plists (read-only inventory)
        plist_dirs = [
            ("User", Path(HOME) / "Library" / "LaunchAgents"),
            ("Local", Path("/Library/LaunchAgents")),
            ("System", Path("/Library/LaunchDaemons")),
        ]
        for where, d in plist_dirs:
            try:
                for f in sorted(d.glob("*.plist")):
                    items.append({"kind": "Launch", "where": where,
                                  "name": f.name, "cmd": str(f)[:150]})
            except OSError:
                pass
    return items

def installed_apps():
    """Installed-app inventory. Windows: ARP (three registry views)."""
    apps, seen = [], set()
    if not IS_WIN:
        return apps   # macOS equivalent lives in /Applications - not in scope v3
    views = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hive, base in views:
        try:
            with open_key(hive, base) as rk:
                i = 0
                while True:
                    try:
                        sub = winreg.EnumKey(rk, i); i += 1
                    except OSError:
                        break
                    try:
                        with open_key(hive, base + "\\" + sub) as k:
                            def gv(n):
                                try:
                                    v, _ = winreg.QueryValueEx(k, n)
                                    return str(v)
                                except OSError:
                                    return ""
                            name = gv("DisplayName")
                            if not name or "KB" in name[:4]:
                                continue
                            key = (name.lower(), gv("DisplayVersion"))
                            if key in seen:
                                continue
                            seen.add(key)
                            apps.append({"name": name[:60],
                                         "version": gv("DisplayVersion")[:20],
                                         "publisher": gv("Publisher")[:34],
                                         "uninstall": gv("UninstallString")[:110]})
                    except OSError:
                        continue
        except OSError:
            pass
    apps.sort(key=lambda a: a["name"].lower())
    return apps

def winget_upgrades():
    """Pending upgrades via winget (read-only listing). Returns raw lines."""
    try:
        r = subprocess.run(["winget", "upgrade", "--include-unknown"],
                           capture_output=True, text=True, timeout=180)
    except FileNotFoundError:
        return ["(winget not found)"]
    except Exception as e:
        return [f"(winget error: {e})"]
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    return lines if lines else ["(no pending upgrades or empty output)"]

# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(prog="opensweep", description=TOOL)
    sub = ap.add_subparsers(dest="cmd")
    for name in ("scan", "apply", "rules"):
        s = sub.add_parser(name)
        s.add_argument("--category", choices=["windows-traces", "windows-junk", "browsers", "apps"])
        s.add_argument("--rule", action="append", default=[], help="rule id (repeatable)")
        if name != "rules":
            s.add_argument("--json", action="store_true")
        if name == "apply":
            s.add_argument("--all", action="store_true", help="include non-default (risky) rules")
            s.add_argument("--yes", action="store_true", help="actually mutate (default: dry-run)")
            s.add_argument("--keep-cookies", default="",
                           help="comma-separated domains to keep cookies for")
    u = sub.add_parser("undo")
    u.add_argument("journal")
    hd = sub.add_parser("harden", help="Windows privacy settings (report by default)")
    hd.add_argument("--yes", action="store_true", help="apply hardened values")
    hd.add_argument("--json", action="store_true")
    tl = sub.add_parser("tools", help="detect companion tools (composition layer)")
    tl.add_argument("--winget", action="store_true", help="also list pending winget upgrades")
    sub.add_parser("startup", help="autostart inventory (read-only; manage with Autoruns)")
    sub.add_parser("apps", help="installed apps inventory (read-only; uninstall via BCU/Settings)")
    sub.add_parser("updates", help="pending updates via winget (read-only listing)")
    args = ap.parse_args()

    if args.cmd == "undo":
        undo_journal(args.journal)
        return
    if args.cmd is None:
        ap.print_help()
        return
    if args.cmd == "harden":
        if args.yes:
            journal = Journal()
            log(f"hardening; journal -> {journal.path}")
            for r in harden_apply(journal, dry=False):
                log(f'  [{r["id"]}] changed={r["changed"]} '
                    f'skipped={"; ".join(r["skipped"]) or "0"}')
            jp = journal.save()
            log(f'\ndone. undo anytime:  python -I opensweep.py undo "{jp}"')
        else:
            rows = harden_report()
            if args.json:
                print(json.dumps(rows, indent=1))
            else:
                log(f"{TOOL} - harden (read-only report; add --yes to apply)")
                for r in rows:
                    cur = "; ".join(f"{i['value']}={i['current']}" for i in r["items"][:2])
                    log(f'  [{r["status"]:>14}] {r["id"]:<28} {r["name"]}  ({cur})')
                n_exp = sum(1 for r in rows if r["status"] == "exposed")
                n_adm = sum(1 for r in rows if r["status"] == "admin-required")
                log(f"\n  {n_exp} exposed, {n_adm} need administrator, "
                    f"{len(rows) - n_exp - n_adm} already hardened")
        return
    if args.cmd == "tools":
        rows = tools_report()
        log(f"{TOOL} - companion tools (composition layer)")
        for r in rows:
            log(f'  [{"x" if r["present"] else " "}] {r["tool"]:<10} {r["purpose"]:<30} {r["usage"]}')
        log("\n  division of labor: cleaning=OpenSweep (this tool); settings=Sophia/privacy.sexy;")
        log("  startup=Autoruns; uninstall=BCU; duplicates=dupeGuru; shred=Eraser; updates=winget/UniGetUI")
        if args.winget:
            subprocess.run(["winget", "upgrade"])
        return
    if args.cmd == "startup":
        items = startup_report()
        log(f"{TOOL} - autostart inventory (read-only; deep control -> Autoruns)")
        for it in items:
            log(f'  [{it["kind"]:<7}] {it["name"]:<34} {it["cmd"][:86]}')
        log(f"\n  {len(items)} entries")
        return
    if args.cmd == "apps":
        apps = installed_apps()
        log(f"{TOOL} - installed apps inventory (read-only; uninstall -> BCU/Settings)")
        for a in apps:
            log(f'  {a["name"]:<42} {a["version"]:<16} {a["publisher"]}')
        log(f"\n  {len(apps)} apps")
        return
    if args.cmd == "updates":
        log(f"{TOOL} - pending updates via winget (read-only listing)")
        for line in winget_upgrades():
            log("  " + line[:130])
        return

    sel = [r for r in RULES
           if (not args.category or r["category"] == args.category)
           and (not args.rule or r["id"] in args.rule)]
    if args.cmd == "rules":
        for r in sel:
            log(f'[{r["category"]:>14}] {"*" if r["default"] else " "} {r["id"]:<28} '
                f'{r["risk"]:<6} {r["name"]}')
        log("\n(* = default-on for apply without --all)")
        return

    running = running_exes()
    keep = [d.strip().lower() for d in getattr(args, "keep_cookies", "").split(",") if d.strip()]

    if args.cmd == "scan":
        out = [scan_rule(r, running, keep) for r in sel]
        total_items = sum(o["items"] for o in out)
        total_bytes = sum(o["bytes"] for o in out)
        if args.json:
            print(json.dumps(out, indent=1))
        else:
            log(f"{TOOL} - scan (read-only)  running-guard: "
                f"{','.join(sorted(running & {'msedge','chrome','firefox'})) or 'none'}")
            for o in out:
                notes = ("; ".join(o["notes"])) if o["notes"] else ""
                log(f'  {o["id"]:<28} {o["items"]:>7,} items  {human(o["bytes"]):>10}  {notes}')
            log(f"\n  TOTAL: {total_items:,} items, {human(total_bytes)}")
            log("  scan is read-only; to clean: apply --category ... --yes")
        return

    # apply
    sel2 = sel if args.rule else [r for r in sel if args.all or r["default"]]
    if not args.yes:
        log("DRY-RUN (no changes; add --yes to actually clean):\n")
        journal = None
        results = [apply_rule(r, running, keep, None, dry=True) for r in sel2]
        for r in results:
            log(f'  [{r["id"]}] files={r["files"]} regvals={r["deleted_values"]} '
                f'rows={r["rows"]} skipped={len(r["skipped"])} {"; ".join(r["notes"])}')
        log("\nre-run with --yes to execute (files are moved to the undo folder, "
            "registry keys exported first).")
        return

    journal = Journal()
    log(f"applying {len(sel2)} rules; journal -> {journal.path}")
    for r in sel2:
        res = apply_rule(r, running, keep, journal, dry=False)
        log(f'  [{r["id"]}] files={res["files"]} regvals={res["deleted_values"]} '
            f'rows={res["rows"]} skipped={len(res["skipped"])} '
            f'{"; ".join(res["skipped"][:2])}')
    jp = journal.save()
    log(f"\ndone. undo anytime:  python -I opensweep.py undo \"{jp}\"")

if __name__ == "__main__":
    main()
