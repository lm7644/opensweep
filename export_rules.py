"""One-shot migration: dump opensweep.RULES to rules.json with paths rewritten
to %VAR% form for portability.  Run before the inline rule block is removed."""
import json, os, sys, pathlib

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import opensweep as o  # noqa: E402  (import is safe; main is guarded)

LOCAL = str(o.LOCAL)
APPDATA = str(o.APPDATA)
TEMPD = os.environ.get("TEMP", "")
ALLU = os.environ.get("ALLUSERSPROFILE", "")
WIN = os.environ.get("SystemRoot", r"C:\Windows")

def deabs(s):
    # longest/most-specific prefixes first (TEMP sits under LOCALAPPDATA)
    for old, new in ((TEMPD, "%TEMP%"), (ALLU, "%ALLUSERSPROFILE%"),
                     (LOCAL, "%LOCALAPPDATA%"), (APPDATA, "%APPDATA%"), (WIN, "%SystemRoot%")):
        if old and old.lower() in s.lower():
            i = s.lower().index(old.lower())
            s = s[:i] + new + s[i + len(old):]
    return s

out = []
for r in o.RULES:
    r = json.loads(json.dumps(r))
    for spec in r.get("files", []):
        spec["path"] = deabs(spec["path"])
    for spec in r.get("sqlite", []):
        spec["glob"] = deabs(spec["glob"])
    out.append(r)

dst = HERE / "rules.json"
dst.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
print(f"exported {len(out)} rules -> {dst}")
