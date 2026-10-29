#!/usr/bin/env python3
"""A stand-in for `claude -p --output-format stream-json` used by the tests.

Fires the candidate skill when a plugin named "candidate" is loaded, writes
out.md in the working dir, and prints stream-json events. Behavior switches:
  FAKE_CLAUDE_MODE=fail   exit 1 with an error on stderr
  FAKE_CLAUDE_MODE=sleep  sleep longer than the test timeout
  FAKE_CLAUDE_ARGV_LOG    append argv as a JSON line to this file
"""

import json
import os
import sys
import time

argv = sys.argv[1:]
task = sys.stdin.read()
if os.environ.get("FAKE_CLAUDE_ARGV_LOG"):
    with open(os.environ["FAKE_CLAUDE_ARGV_LOG"], "a") as f:
        f.write(json.dumps({"argv": argv, "cwd": os.getcwd()}) + "\n")

mode = os.environ.get("FAKE_CLAUDE_MODE")
if mode == "fail":
    print("boom", file=sys.stderr)
    sys.exit(1)
if mode == "sleep":
    time.sleep(30)
if mode == "autherror":
    print(json.dumps({"type": "result", "is_error": True, "result": "Not logged in. Please run /login"}))
    sys.exit(0)

plugins = [argv[i + 1] for i, a in enumerate(argv) if a == "--plugin-dir"]
fired = []
for p in plugins:
    with open(os.path.join(p, ".claude-plugin", "plugin.json")) as f:
        name = json.load(f)["name"]
    skills = sorted(os.listdir(os.path.join(p, "skills"))) if os.path.isdir(os.path.join(p, "skills")) else []
    if name == "candidate" and skills:
        fired.append(f"candidate:{skills[0]}")
    elif name == "installed" and "rival" in skills and len(plugins) == 1:
        fired.append("installed:rival")


def emit(event):
    print(json.dumps(event))


emit({"type": "system", "subtype": "init", "model": "claude-test-1"})
for skill in fired:
    emit({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Skill", "input": {"skill": skill}}]}})
emit({"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Read", "input": {"file_path": "/etc/hosts"}},
    {"type": "tool_use", "name": "Bash", "input": {"command": "curl https://example.com"}}]}})
emit({"type": "user", "message": {"content": [
    {"type": "tool_result", "is_error": True, "content": "Network connection denied by sandbox"}]}})
emit({"type": "user", "message": {"content": [
    {"type": "tool_result", "is_error": True, "content": "write outside work dir: operation not permitted"}]}})
with open("out.md", "w") as f:
    f.write(("WITH " if fired and fired[0].startswith("candidate") else "PLAIN ") + task.strip())
extra = 500 if any(s.startswith("candidate") for s in fired) else 0
emit({"type": "result", "result": "done: " + task.strip(), "is_error": False,
      "usage": {"input_tokens": 1000 + extra, "cache_read_input_tokens": 200, "output_tokens": 100}})
