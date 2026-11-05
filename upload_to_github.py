"""OpenSweep one-shot GitHub uploader (pure REST, no git binary needed).

Pipeline: verify token -> create repo -> upload every file as blobs ->
tree -> commit -> refs/heads/main -> sanitize -> watch the CI matrix.

Usage:
  python upload_to_github.py [<TOKEN>] [--name opensweep] [--private]
  (preferred: set GH_TOKEN in the environment and pass no token argument -
   a token in argv is visible to other local processes via the process list)

Token guidance (see RELEASE_CHECKLIST.md):
  fine-grained PAT: Contents RW + Administration RW (+ Actions R)
  classic PAT:      repo + workflow
Revoke the token after the run.
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

API = "https://api.github.com"
CURL = shutil.which("curl") or "curl.exe"   # POSIX: curl; Windows: System32 curl.exe
ROOT = Path(__file__).resolve().parent
REPO_DESC = ("Clean-room privacy trace cleaner for Windows & macOS. "
             "Zero dependencies, zero network, everything reversible.")
EXCLUDE_PARTS = {".git", "__pycache__", "sandbox", "satbox"}
EXCLUDE_SUFFIX = {".pyc", ".log"}

def api(method, path, token, payload=None, raw=False, _retry=0):
    """GitHub API call via curl.exe (Schannel/Windows trust store - robust
    behind local proxies that break Python's OpenSSL chain validation)."""
    cmd = [CURL, "-sS", "-X", method, API + path,
           "-H", f"Authorization: Bearer {token}",
           "-H", "Accept: application/vnd.github+json",
           "-H", "User-Agent: opensweep-uploader",
           "--ssl-no-revoke", "--connect-timeout", "20",
           "--max-time", "120", "--retry", "2", "--retry-delay", "3",
           "-w", "\n%{http_code}"]
    stdin_data = None
    if payload is not None:
        cmd += ["-d", "@-"]
        stdin_data = json.dumps(payload)
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", input=stdin_data)
    out = r.stdout.rsplit("\n", 1)
    body_text = out[0] if len(out) == 2 else ""
    try:
        code = int(out[-1].strip())
    except ValueError:
        code = 0
    if code == 0:
        if _retry < 3:
            time.sleep(3 * (_retry + 1))
            return api(method, path, token, payload, raw, _retry + 1)
        raise RuntimeError(f"curl transport failed: {r.stderr.strip()[:200]}")
    if 500 <= code < 600 and _retry < 3:
        time.sleep(3 * (_retry + 1))
        return api(method, path, token, payload, raw, _retry + 1)
    body = body_text if raw else (json.loads(body_text) if body_text.strip() else {})
    return code, body

def collect_files(skip_workflows=False):
    out = []
    for f in sorted(ROOT.rglob("*")):
        parts = set(f.parts)
        if not f.is_file():
            continue
        if parts & EXCLUDE_PARTS or f.suffix in EXCLUDE_SUFFIX:
            continue
        if skip_workflows and ".github" in f.relative_to(ROOT).parts:
            continue
        out.append(f)
    return out

def main():
    args = sys.argv[1:]
    token = os.environ.get("GH_TOKEN", "")
    if args and not args[0].startswith("-"):
        token = args[0]
        args = args[1:]
    if not token:
        print(__doc__)
        sys.exit(1)
    name = "opensweep"
    private = False
    if "--name" in args:
        name = args[args.index("--name") + 1]
    private = "--private" in args
    skip_wf = "--skip-workflows" in args

    # 1. token identity
    code, me = api("GET", "/user", token)
    if code != 200:
        print(f"token rejected ({code}): {me.get('message')}")
        sys.exit(1)
    login = me["login"]
    print(f"[1/6] token OK, user = {login}")

    # 2. repo (skip creation if already exists -> update mode)
    full = f"{login}/{name}"
    code, existing = api("GET", f"/repos/{full}", token)
    if code == 200:
        print(f"[2/6] repo {full} already exists -> updating it")
    elif code == 404:
        code, repo = api("POST", "/user/repos", token, payload={
            "name": name, "description": REPO_DESC,
            "private": private, "auto_init": False,
            "has_issues": True, "has_wiki": False})
        if code not in (201, 202):
            print(f"repo creation failed ({code}): {repo.get('message')} "
                  f"{repo.get('errors', '')}")
            sys.exit(1)
        print(f"[2/6] repo created: {repo['html_url']}")
    else:
        print(f"repo check failed ({code})"); sys.exit(1)

    # 3. seed the empty repo via the contents API (the only reliable write on
    #    a zero-commit repo), then use its commit as the base tree
    files = collect_files(skip_workflows=skip_wf)
    code, ref = api("GET", f"/repos/{full}/git/refs/heads/main", token)
    if code != 200:
        readme = next((f for f in files if f.name == "README.md"), None)
        if readme is None:
            print("seed failed: no README"); sys.exit(1)
        code, seed = api("PUT", f"/repos/{full}/contents/README.md", token, payload={
            "message": "seed: README",
            "content": base64.b64encode(readme.read_bytes()).decode()})
        if code not in (201, 200):
            print(f"seed failed ({code}): {seed.get('message')}"); sys.exit(1)
        print("[3/6] seeded empty repo with README (initial commit)")
        code, ref = api("GET", f"/repos/{full}/git/refs/heads/main", token)
    head_sha = ref["object"]["sha"]
    code, head_c = api("GET", f"/repos/{full}/git/commits/{head_sha}", token)
    base_tree = head_c["tree"]["sha"]

    # 3b. blobs
    print(f"[3/6] uploading {len(files)} files as blobs ...")
    tree = []
    for f in files:
        rel = f.relative_to(ROOT).as_posix()
        data = f.read_bytes()
        code, blob = api("POST", f"/repos/{full}/git/blobs", token, payload={
            "content": base64.b64encode(data).decode(), "encoding": "base64"})
        if code != 201:
            print(f"  blob failed: {rel} ({code}) {blob.get('message', '')}")
            sys.exit(1)
        tree.append({"path": rel, "mode": "100644", "type": "blob",
                     "sha": blob["sha"]})
        print(f"  + {rel} ({len(data):,} B)")
        time.sleep(0.3)

    # 4. tree (on top of the seed tree) + commit + fast-forward ref
    code, tree_res = api("POST", f"/repos/{full}/git/trees", token, payload={
        "tree": tree, "base_tree": base_tree})
    if code != 201:
        print(f"tree failed ({code})"); sys.exit(1)
    msg = ("OpenSweep v3.0.0 - clean-room privacy trace cleaner\n\n"
           "Windows + macOS. Zero dependencies, zero network, fully reversible.\n"
           "Includes: 45+11 declarative rules, 15-item Windows hardening,\n"
           "ledger web UI, desktop GUI, CLI, sandboxed safety suite (37/37),\n"
           "saturation suite (33/33), CI matrix (windows/macos x py3.10/3.12).")
    code, commit = api("POST", f"/repos/{full}/git/commits", token, payload={
        "message": msg, "tree": tree_res["sha"], "parents": [head_sha]})
    if code != 201:
        print(f"commit failed ({code})"); sys.exit(1)
    code, _ = api("PATCH", f"/repos/{full}/git/refs/heads/main", token, payload={
        "sha": commit["sha"]})
    if code != 200:
        print(f"ref update failed ({code})"); sys.exit(1)
    print(f"[4/6] pushed: https://github.com/{full} (commit {commit['sha'][:8]})")
    print("[5/6] token used only in-memory; nothing written to disk. "
          "Revoke it now if you wish (CI does not need it).")
    if skip_wf:
        print("[6/6] workflows skipped (token lacks workflow scope) - no CI to watch.")
        print("      Add CI via web UI: Add file -> Create file -> path "
              ".github/workflows/ci.yml (content in ci.yml locally), or re-run "
              "with a token that has the workflow scope.")
        print(f"DONE: https://github.com/{full}")
        return

    # 6. watch CI
    print("[6/6] watching Actions (this can take a few minutes) ...")
    deadline = time.time() + 20 * 60
    run_id, run_status = None, "queued"
    while time.time() < deadline:
        code, runs = api("GET", f"/repos/{full}/actions/runs?per_page=5", token)
        for run in runs.get("workflow_runs", []):
            if run["head_sha"] == commit["sha"]:
                run_id, run_status = run["id"], run["status"]
                break
        if run_id and run_status == "completed":
            break
        print(f"  ... {run_status or 'waiting for run to appear'}")
        time.sleep(20)
    if not run_id:
        print("  (no CI run seen before timeout - check the Actions tab manually)")
        print(f"DONE: https://github.com/{full}")
        return
    code, jobs = api("GET", f"/repos/{full}/actions/runs/{run_id}/jobs", token)
    print(f"\nCI run {run_id} conclusion:")
    allpass = True
    for j in jobs.get("jobs", []):
        concl = j.get("conclusion") or j.get("status")
        allpass &= (concl == "success")
        print(f'  [{concl:>9}] {j["name"]}')
    print("\nFINAL:", "ALL GREEN - release v3.0.0 when ready" if allpass
          else "SOME JOBS FAILED - see the Actions tab for logs")
    print(f"repo: https://github.com/{full}")

if __name__ == "__main__":
    main()
