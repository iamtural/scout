#!/usr/bin/env python3
"""Find past requests in local Claude Code history that match a skill.

Reads ~/.claude/projects/*/*.jsonl on this machine only. Prints the best
2-3 matching prompts as JSON: a short preview to show the user, the full text
to use as the trial task, and a timestamp. No project paths. Nothing is
written to disk and nothing is sent anywhere.

Usage:
  history_search.py --skill-dir <candidate skill dir> [--exclude <link>]...
  history_search.py --description "text" [--root DIR] [--limit 3]

Prefer --skill-dir: it reads the description from the candidate's SKILL.md
itself, so untrusted text never goes on a command line.
"""

import argparse
import glob
import json
import os
import re
import sys

from skillmd import find_skills

STOPWORDS = set("""
a an and are as at be but by can do does for from has have how i if in into is
it its just me my not of on or our so that the their them then there these this
to up use used uses using was we what when where which while who why will with
you your any all also more most other some such than too very via should would
could skill skills claude user users want wants help helps make makes
""".split())

TAG_PREFIXES = ("<command-", "<local-command", "<system-reminder", "<task-notification",
                "<user-prompt-submit-hook", "<bash-", "<pasted_content", "Caveat:")
MIN_CHARS = 25
MAX_CHARS = 4000
PREVIEW_CHARS = 160


def words(text):
    return {w for w in re.findall(r"[a-z][a-z0-9-]{2,}", text.lower()) if w not in STOPWORDS}


def prompt_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content
                         if isinstance(b, dict) and b.get("type") == "text")
    return ""


def iter_prompts(root):
    for path in glob.glob(os.path.join(root, "*", "*.jsonl")):
        try:
            f = open(path, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with f:
            for line in f:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if (not isinstance(event, dict) or event.get("type") != "user" or event.get("isSidechain")
                        or event.get("isCompactSummary") or event.get("isMeta")):
                    continue
                text = prompt_text((event.get("message") or {}).get("content")).strip()
                if len(text) < MIN_CHARS or text.startswith(TAG_PREFIXES):
                    continue
                yield text, event.get("timestamp", "")


def search(description, root, limit=3, exclude=()):
    keys = words(description)
    excluded = [e.lower() for e in exclude if e]
    seen, scored = set(), []
    for text, ts in iter_prompts(root):
        norm = " ".join(text.lower().split())
        if norm in seen:
            continue
        seen.add(norm)
        if re.match(r"^/?scout\b", norm) or any(e in norm for e in excluded):
            continue
        overlap = len(keys & words(text))
        if overlap >= 2:
            # Prefer dense matches over long prompts that mention everything.
            scored.append((overlap / (1 + len(norm) / 2000), ts, text))
    scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
    matches = [{"preview": " ".join(t.split())[:PREVIEW_CHARS], "text": t[:MAX_CHARS], "timestamp": ts}
               for _, ts, t in scored[:limit]]
    return {"matches": matches, "searched": len(seen)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--skill-dir")
    src.add_argument("--description")
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--root", default=os.path.expanduser("~/.claude/projects"))
    ap.add_argument("--limit", type=int, default=3)
    args = ap.parse_args()
    description = args.description
    if args.skill_dir:
        skills = list(find_skills(args.skill_dir))
        if not skills:
            print(f"history_search: no SKILL.md under {args.skill_dir}", file=sys.stderr)
            sys.exit(2)
        description = " ".join(f"{n} {d}" for n, _, d in skills)
    print(json.dumps(search(description, args.root, args.limit, args.exclude), indent=2))


if __name__ == "__main__":
    main()
