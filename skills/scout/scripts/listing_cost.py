#!/usr/bin/env python3
"""Estimate what a candidate skill costs in the skill listing budget.

Claude Code lists every skill's name and description in context, within a
budget of roughly 1% of the context window. Past that, descriptions get
dropped (least-used first, which Scout cannot see). This reports the
candidate's added characters and, if the total passes the budget, which
installed skills would fall past it in a plain alphabetical estimate.

Usage:
  listing_cost.py <candidate-dir> [--installed-root DIR] [--budget-chars N]
"""

import argparse
import json
import os

from skillmd import find_skills

# ~1% of a 200K-token context is ~2,000 tokens, roughly 8,000 characters.
DEFAULT_BUDGET_CHARS = 8000


def entry_chars(name, description):
    return len(name) + len(description) + 4


def listing_cost(candidate_dir, installed_root, budget):
    candidates = list(find_skills(candidate_dir))
    cand_names = {n for n, _, _ in candidates}
    installed = sorted((n, d) for n, _, d in find_skills(installed_root) if n not in cand_names)

    before = sum(entry_chars(n, d) for n, d in installed)
    added = sum(entry_chars(n, d) for n, _, d in candidates)
    after = before + added

    pushed_out = []
    if after > budget:
        running = added
        for name, desc in installed:
            running += entry_chars(name, desc)
            if running > budget:
                pushed_out.append(name)

    return {
        "candidate_skills": sorted(cand_names),
        "installed_count": len(installed),
        "chars_before": before,
        "chars_added": added,
        "chars_after": after,
        "budget_chars": budget,
        "over_budget": after > budget,
        "pushed_out_estimate": pushed_out,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("candidate_dir")
    ap.add_argument("--installed-root", default=os.path.expanduser("~/.claude/skills"))
    ap.add_argument("--budget-chars", type=int, default=DEFAULT_BUDGET_CHARS)
    args = ap.parse_args()
    print(json.dumps(listing_cost(args.candidate_dir, args.installed_root, args.budget_chars), indent=2))


if __name__ == "__main__":
    main()
