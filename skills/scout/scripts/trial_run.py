#!/usr/bin/env python3
"""Fetch, screen and trial-run a candidate skill with and without it.

Subcommands:
  fetch <link>         Shallow-fetch a GitHub link into a temp dir (no hooks,
                       no LFS, no submodules, symlinks as plain files). Prints
                       dir, skill_dir and commit.
  check <skill-dir>    List hooks, MCP servers, agents and commands the
                       candidate ships, and whether this platform can trial.
  run <skill-dir>      Read the task from stdin, run it once with the candidate
                       and once without, in headless Claude Code. Prints a
                       JSON report.
  cleanup <dir>        Remove a temp dir that fetch created.

Each run gets the user's personal skills (~/.claude/skills) as a baseline
plugin, so the comparison matches their real setup. The candidate is copied in
as a second plugin for the "with" run only. Candidate hooks never run: hook
files are not copied, `hooks` and `allowed-tools` are stripped from copied
SKILL.md frontmatter, and the runs set disableAllHooks. Bash runs in the
sandbox with no unsandboxed fallback, no network beyond the sandbox's rules,
and no read access to the home directory. All temp dirs are removed when the
run ends.

Set SCOUT_CLAUDE_BIN to use a different claude command (tests use a fake).
"""

import argparse
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading

from skillmd import find_skills, read_frontmatter, safe_name, strip_keys

TMP_PREFIX = "scout-"
TRIAL_TOOLS = "Read,Glob,Grep,Edit,Write,Bash,Skill"
TRIAL_SETTINGS = {
    "disableAllHooks": True,
    "sandbox": {
        "enabled": True,
        "failIfUnavailable": True,
        "allowUnsandboxedCommands": False,
        "filesystem": {"denyRead": ["~"]},
    },
}
STRIPPED_KEYS = ("hooks", "allowed-tools")
NETWORK_RE = re.compile(r"\b(curl|wget|nc|ssh|scp|rsync|ftp|telnet)\b|https?://", re.I)
NETWORK_DENIED_RE = re.compile(r"(network|connect|resolve host|dns|socket).{0,80}(denied|blocked|not permitted|refused)"
                               r"|(denied|blocked|not permitted).{0,80}(network|connect|host)", re.I)
MAX_FILE_CHARS = 20000
GITHUB_RE = re.compile(
    r"^https?://(?:www\.)?github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:\.git)?"
    r"(?:/(?:tree|blob)/(?P<rest>.+?))?/?$")
GIT_ENV = {"GIT_TERMINAL_PROMPT": "0", "GIT_LFS_SKIP_SMUDGE": "1", "GIT_CONFIG_NOSYSTEM": "1"}
GIT_SAFE = ["-c", "core.hooksPath=/dev/null", "-c", "core.symlinks=false", "-c", "protocol.file.allow=never"]


# ---------- fetch / cleanup ----------

def parse_github(link):
    """Return (clone url, [(ref, sub-path), ...]) candidates for a GitHub link.

    Branch names can contain slashes, so every split of tree/<rest> is a
    candidate; fetch tries them in order.
    """
    m = GITHUB_RE.match(link.strip().split("#", 1)[0].split("?", 1)[0])
    if not m:
        raise ValueError(f"not a GitHub repo link: {link}")
    url = f"https://github.com/{m.group('owner')}/{m.group('repo')}.git"
    rest = m.group("rest")
    if not rest:
        return url, [(None, "")]
    parts = rest.strip("/").split("/")
    splits = []
    for i in range(1, len(parts) + 1):
        sub = "/".join(parts[i:])
        if sub.endswith("SKILL.md"):
            sub = os.path.dirname(sub)
        splits.append(("/".join(parts[:i]), sub))
    return url, splits


def _git(args, cwd=None):
    env = {**os.environ, **GIT_ENV}
    return subprocess.run(["git"] + GIT_SAFE + args, cwd=cwd, env=env, check=True,
                          capture_output=True, text=True, timeout=120)


def fetch(link):
    url, splits = parse_github(link)
    tmp = tempfile.mkdtemp(prefix=TMP_PREFIX + "fetch-")
    repo = os.path.join(tmp, "repo")
    try:
        _git(["init", "--quiet", repo])
        _git(["config", "core.symlinks", "false"], cwd=repo)
        _git(["remote", "add", "origin", url], cwd=repo)
        last_err, sub = None, ""
        for ref, sub in splits:
            try:
                _git(["fetch", "--quiet", "--depth", "1", "--no-recurse-submodules", "origin", ref or "HEAD"],
                     cwd=repo)
                break
            except subprocess.CalledProcessError as e:
                last_err = e
        else:
            raise RuntimeError(f"fetch failed: {(last_err.stderr or '').strip()}")
        _git(["checkout", "--quiet", "FETCH_HEAD"], cwd=repo)
        commit = _git(["rev-parse", "HEAD"], cwd=repo).stdout.strip()
        skill_dir = os.path.realpath(os.path.join(repo, sub))
        if not (skill_dir == os.path.realpath(repo) or skill_dir.startswith(os.path.realpath(repo) + os.sep)):
            raise RuntimeError("path escapes the repo")
        if not os.path.isdir(skill_dir):
            raise RuntimeError(f"path not found in repo: {sub}")
    except (subprocess.SubprocessError, OSError, RuntimeError) as e:
        shutil.rmtree(tmp, ignore_errors=True)
        detail = (getattr(e, "stderr", "") or str(e)).strip()
        raise RuntimeError(detail if detail.startswith(("fetch failed", "path")) else f"clone failed: {detail}")
    return {"dir": tmp, "skill_dir": skill_dir, "commit": commit}


def cleanup(path):
    real = os.path.realpath(path)
    if not (os.path.dirname(real) == os.path.realpath(tempfile.gettempdir())
            and os.path.basename(real).startswith(TMP_PREFIX)):
        raise ValueError(f"refusing to remove a dir scout did not create: {path}")
    shutil.rmtree(real, ignore_errors=True)


# ---------- check ----------

def check(skill_dir):
    found = {"hooks": [], "mcp": [], "agents": [], "commands": [], "symlinks": []}
    skills = []
    for dirpath, dirnames, filenames in os.walk(skill_dir):
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules")]
        rel = os.path.relpath(dirpath, skill_dir)
        base = os.path.basename(dirpath)
        found["symlinks"] += [os.path.join(rel, n) for n in dirnames + filenames
                              if os.path.islink(os.path.join(dirpath, n))]
        if base == "hooks" and "hooks.json" in filenames:
            found["hooks"].append(os.path.join(rel, "hooks.json"))
        if base == "agents":
            found["agents"] += [os.path.join(rel, f) for f in filenames if f.endswith(".md")]
        if base == "commands":
            found["commands"] += [os.path.join(rel, f) for f in filenames if f.endswith(".md")]
        if ".mcp.json" in filenames:
            found["mcp"].append(os.path.join(rel, ".mcp.json"))
        if "plugin.json" in filenames:
            try:
                with open(os.path.join(dirpath, "plugin.json"), encoding="utf-8-sig") as f:
                    manifest = json.load(f)
            except (OSError, ValueError):
                manifest = {}
            if isinstance(manifest, dict) and manifest.get("hooks"):
                found["hooks"].append(os.path.join(rel, "plugin.json: hooks"))
            if isinstance(manifest, dict) and manifest.get("mcpServers"):
                found["mcp"].append(os.path.join(rel, "plugin.json: mcpServers"))
        if "SKILL.md" in filenames:
            fm = read_frontmatter(os.path.join(dirpath, "SKILL.md"))
            skills.append(fm.get("name") or base)
            if "hooks" in fm:
                found["hooks"].append(os.path.join(rel, "SKILL.md: hooks"))
    for key in found:
        found[key] = sorted({os.path.normpath(p) for p in found[key]})
    return {"platform_ok": not sys.platform.startswith("win"), "skills": sorted(skills), **found}


# ---------- run ----------

def claude_cmd():
    return shlex.split(os.environ.get("SCOUT_CLAUDE_BIN", "claude"))


_trusted_ignore = shutil.ignore_patterns(".git", "node_modules", "hooks", ".mcp.json")


def _untrusted_ignore(dirpath, names):
    """Like _trusted_ignore, and also drop symlinks so nothing outside the repo is copied."""
    return set(_trusted_ignore(dirpath, names)) | {n for n in names if os.path.islink(os.path.join(dirpath, n))}


def make_plugin(root, name, skills, strip=False):
    """Build a session plugin holding copies of the given (name, dir) skills.

    Only the skill folders are copied; hook dirs and MCP config never come
    along. With strip=True (the untrusted candidate), symlinks are dropped and
    `hooks` and `allowed-tools` are removed from each copied SKILL.md. Returns a list of problems (copy failures, stripped keys).
    """
    os.makedirs(os.path.join(root, ".claude-plugin"))
    with open(os.path.join(root, ".claude-plugin", "plugin.json"), "w") as f:
        json.dump({"name": name}, f)
    notes = []
    for skill_name, src in skills:
        dest = os.path.join(root, "skills", safe_name(skill_name))
        if os.path.exists(dest):
            notes.append(f"duplicate skill name skipped: {skill_name}")
            continue
        try:
            shutil.copytree(src, dest, symlinks=False, ignore_dangling_symlinks=True,
                            ignore=_untrusted_ignore if strip else _trusted_ignore)
        except (OSError, shutil.Error) as e:
            notes.append(f"copy problem in {skill_name}: {str(e)[:200]}")
        if strip and os.path.exists(os.path.join(dest, "SKILL.md")):
            removed = strip_keys(os.path.join(dest, "SKILL.md"), STRIPPED_KEYS)
            if removed:
                notes.append(f"stripped from {skill_name}: {', '.join(removed)}")
    return notes


def snapshot(root):
    state = {}
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            try:
                st = os.lstat(p)
            except OSError:
                continue
            state[os.path.relpath(p, root)] = (st.st_size, st.st_mtime_ns)
    return state


def strip_ns(skill):
    return skill.split(":", 1)[-1] if skill else skill


def empty_report():
    return {"final_text": "", "model": None, "skills_fired": [], "files_read": [], "network_attempts": [],
            "tokens_in": 0, "tokens_cached": 0, "tokens_out": 0, "is_error": False}


def parse_stream(text):
    out = empty_report()
    for line in text.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        kind = event.get("type")
        content = (event.get("message") or {}).get("content")
        if kind == "system" and event.get("subtype") == "init":
            out["model"] = event.get("model")
        elif kind == "assistant" and isinstance(content, list):
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                name, inp = block.get("name"), block.get("input") or {}
                if name == "Skill":
                    skill = inp.get("skill") or inp.get("command") or inp.get("name")
                    if skill:
                        out["skills_fired"].append(strip_ns(str(skill)))
                elif name == "Read" and inp.get("file_path"):
                    out["files_read"].append(str(inp["file_path"]))
                elif name == "Bash" and NETWORK_RE.search(str(inp.get("command", ""))):
                    out["network_attempts"].append(str(inp.get("command"))[:200])
        elif kind == "user" and isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result" and block.get("is_error"):
                    body = json.dumps(block.get("content"))
                    if NETWORK_DENIED_RE.search(body):
                        out["network_attempts"].append("denied: " + body[:200])
        elif kind == "result":
            out["final_text"] = str(event.get("result") or "")
            out["is_error"] = bool(event.get("is_error"))
            usage = event.get("usage") or {}

            def num(key):
                try:
                    return int(usage.get(key) or 0)
                except (TypeError, ValueError):
                    return 0
            out["tokens_in"] = num("input_tokens") + num("cache_creation_input_tokens")
            out["tokens_cached"] = num("cache_read_input_tokens")
            out["tokens_out"] = num("output_tokens")
    return out


def run_one(work, plugins, task, model, timeout, result):
    report = empty_report()
    try:
        cmd = claude_cmd() + [
            "-p", "--output-format", "stream-json", "--verbose",
            "--no-session-persistence", "--restricted",
            "--tools", TRIAL_TOOLS, "--permission-mode", "acceptEdits", "--permission-prompts", "none",
            "--strict-mcp-config", "--settings", json.dumps(TRIAL_SETTINGS),
        ]
        for p in plugins:
            cmd += ["--plugin-dir", p, "--add-dir", p]
        if model:
            cmd += ["--model", model]
        before = snapshot(work)
        proc = subprocess.Popen(cmd, cwd=work, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                                start_new_session=True)
        try:
            stdout, stderr = proc.communicate(task, timeout=timeout)
            report = parse_stream(stdout)
            report["exit_code"] = proc.returncode
            if proc.returncode or report["is_error"] or not report["final_text"]:
                report["error"] = (report["final_text"] or (stderr or "").strip()[-500:]
                                   or f"exit {proc.returncode}")[:500]
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                proc.kill()
            proc.communicate()
            report.update(exit_code=None, error=f"timed out after {timeout}s")
        after = snapshot(work)
        written = sorted(p for p, sig in after.items() if before.get(p) != sig)
        report["files_written"] = written
        report["outputs"] = {}
        for rel in written[:10]:
            path = os.path.join(work, rel)
            if os.path.islink(path):
                continue
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    report["outputs"][rel] = f.read(MAX_FILE_CHARS)
            except OSError:
                pass
    except Exception as e:  # a crashed thread must still leave a report
        report.setdefault("files_written", [])
        report.setdefault("outputs", {})
        report.update(exit_code=None, error=f"runner error: {type(e).__name__}: {e}"[:500])
    result.update(report)


def run(skill_dir, task, model=None, timeout=600, installed_root=None):
    if not task.strip():
        raise ValueError("empty task on stdin")
    candidates = [(n, d) for n, d, _ in find_skills(skill_dir)]
    if not candidates:
        raise ValueError(f"no SKILL.md found under {skill_dir}")
    cand_names = {n for n, _ in candidates}
    installed_root = installed_root or os.path.expanduser("~/.claude/skills")
    installed = ([(n, d) for n, d, _ in find_skills(installed_root, followlinks=True)
                  if n not in cand_names and n != "scout"] if os.path.isdir(installed_root) else [])

    tmp = tempfile.mkdtemp(prefix=TMP_PREFIX + "trial-")
    try:
        baseline, candidate = os.path.join(tmp, "baseline"), os.path.join(tmp, "candidate")
        make_plugin(baseline, "installed", installed)
        notes = make_plugin(candidate, "candidate", candidates, strip=True)
        work_with, work_without = os.path.join(tmp, "with"), os.path.join(tmp, "without")
        os.makedirs(work_with)
        os.makedirs(work_without)
        with_res, without_res = {}, {}
        threads = [
            threading.Thread(target=run_one, args=(work_with, [baseline, candidate], task, model, timeout, with_res)),
            threading.Thread(target=run_one, args=(work_without, [baseline], task, model, timeout, without_res)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    fired = sorted(cand_names & set(with_res["skills_fired"]))
    displaced = sorted(set(without_res["skills_fired"]) - set(with_res["skills_fired"]) - cand_names)
    total = lambda r: r["tokens_in"] + r["tokens_cached"] + r["tokens_out"]
    return {
        "candidate_skills": sorted(cand_names),
        "baseline_skill_count": len(installed),
        "model": with_res.get("model") or without_res.get("model") or model,
        "fired": fired,
        "displaced": displaced,
        "displacement_scope": "personal skills only",
        "extra_tokens": total(with_res) - total(without_res),
        "candidate_notes": notes,
        "with": with_res,
        "without": without_res,
        "ok": not with_res.get("error") and not without_res.get("error"),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch").add_argument("link")
    sub.add_parser("check").add_argument("skill_dir")
    sub.add_parser("cleanup").add_argument("dir")
    r = sub.add_parser("run")
    r.add_argument("skill_dir")
    r.add_argument("--model")
    r.add_argument("--timeout", type=int, default=600)
    r.add_argument("--installed-root")
    args = ap.parse_args()
    try:
        if args.cmd == "fetch":
            out = fetch(args.link)
        elif args.cmd == "check":
            out = check(args.skill_dir)
        elif args.cmd == "cleanup":
            cleanup(args.dir)
            out = {"removed": args.dir}
        else:
            out = run(args.skill_dir, sys.stdin.read(), args.model, args.timeout, args.installed_root)
    except (ValueError, RuntimeError, OSError) as e:
        print(f"trial_run: {e}", file=sys.stderr)
        sys.exit(2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
