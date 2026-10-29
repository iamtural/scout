#!/usr/bin/env python3
"""Write and update private trial receipts on this machine.

Receipts live in ~/.scout/receipts/ (or $SCOUT_HOME/receipts/). Every value is
validated against a fixed shape, so task text cannot end up in a receipt.
This script has no network code; receipts are never sent anywhere.

Usage:
  receipt.py write --source URL --commit SHA --model ID --category CAT \
      --origin history|drafted --winner with|without|tie --extra-tokens N
  receipt.py overrule <receipt-file> --winner with|without|tie
"""

import argparse
import datetime
import json
import os
import re
import sys

CATEGORIES = ("writing", "code", "research", "review", "data", "design", "ops", "other")
WINNERS = ("with", "without", "tie")
ORIGINS = ("history", "drafted")


def receipts_dir():
    home = os.environ.get("SCOUT_HOME") or os.path.expanduser("~/.scout")
    return os.path.join(home, "receipts")


def _check(value, pattern, field):
    if not re.fullmatch(pattern, value):
        raise ValueError(f"invalid {field}: {value!r}")
    return value


def validate(source, commit, model, category, origin, winner, extra_tokens):
    _check(source, r"https://(www\.)?github\.com/[\w.-]{1,100}/[\w.-]{1,100}(/(tree|blob)/[\w./-]{1,200})?/?", "source")
    _check(commit, r"[0-9a-f]{7,40}|unknown", "commit")
    _check(model, r"[A-Za-z0-9._\-\[\]]{1,64}", "model")
    for value, allowed, field in ((category, CATEGORIES, "category"), (origin, ORIGINS, "origin"),
                                  (winner, WINNERS, "winner")):
        if value not in allowed:
            raise ValueError(f"invalid {field}: {value!r} (allowed: {', '.join(allowed)})")
    if not isinstance(extra_tokens, int):
        raise ValueError("extra_tokens must be an integer")


def write(source, commit, model, category, origin, winner, extra_tokens):
    validate(source, commit, model, category, origin, winner, extra_tokens)
    now = datetime.datetime.now(datetime.timezone.utc)
    slug = re.sub(r"[^a-z0-9-]+", "-", source.rstrip("/").rsplit("/", 1)[-1].lower()).strip("-")[:40] or "skill"
    record = {
        "scout_receipt": 1,
        "created": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": source,
        "commit": commit,
        "model": model,
        "task_category": category,
        "task_origin": origin,
        "judge_winner": winner,
        "user_winner": None,
        "winner": winner,
        "extra_tokens": extra_tokens,
    }
    os.makedirs(receipts_dir(), exist_ok=True)
    path = os.path.join(receipts_dir(), f"{now.strftime('%Y%m%dT%H%M%S%fZ')}-{slug}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    return path


def overrule(path, winner):
    if winner not in WINNERS:
        raise ValueError(f"invalid winner: {winner!r}")
    real = os.path.realpath(path)
    if os.path.dirname(real) != os.path.realpath(receipts_dir()):
        raise ValueError("receipt must live in the receipts directory")
    with open(real, encoding="utf-8") as f:
        record = json.load(f)
    record["user_winner"] = winner
    record["winner"] = winner
    with open(real, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    return record


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write")
    w.add_argument("--source", required=True)
    w.add_argument("--commit", default="unknown")
    w.add_argument("--model", required=True)
    w.add_argument("--category", required=True)
    w.add_argument("--origin", required=True)
    w.add_argument("--winner", required=True)
    w.add_argument("--extra-tokens", type=int, required=True)
    o = sub.add_parser("overrule")
    o.add_argument("file")
    o.add_argument("--winner", required=True)
    args = ap.parse_args()
    try:
        if args.cmd == "write":
            print(write(args.source, args.commit, args.model, args.category, args.origin,
                        args.winner, args.extra_tokens))
        else:
            print(json.dumps(overrule(args.file, args.winner), indent=2))
    except (ValueError, OSError) as e:
        print(f"receipt: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
