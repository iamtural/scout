"""Read name and description from a SKILL.md frontmatter block (stdlib only)."""

import os
import re

FOLDED = ("", ">", "|", ">-", "|-", ">+", "|+")


def _split(path):
    """Return (frontmatter lines, end index, all lines) or None."""
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        return None
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i], i, lines
    return None


def _key(line):
    """Return the top-level key on this line, or None."""
    if not line or line[0] in " \t#" or ":" not in line:
        return None
    return line.partition(":")[0].strip().strip("\"'")


def read_frontmatter(path):
    """Return the frontmatter of a SKILL.md as a dict of top-level string values.

    Handles plain, quoted, multi-line plain and folded (`>` / `|`) values,
    quoted keys, and a UTF-8 BOM. Returns {} when there is no frontmatter.
    """
    split = _split(path)
    if not split:
        return {}
    body = split[0]
    fields = {}
    i = 0
    while i < len(body):
        key = _key(body[i])
        if key is None:
            i += 1
            continue
        value = body[i].partition(":")[2].strip()
        i += 1
        block = []
        while i < len(body) and (not body[i].strip() or body[i][0] in " \t"):
            block.append(body[i].strip())
            i += 1
        if value in FOLDED:
            joiner = "\n" if value.startswith("|") else " "
            value = joiner.join(b for b in block if b).strip()
        else:
            value = " ".join([value] + [b for b in block if b]).strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
        fields[key] = value
    return fields


def strip_keys(path, keys):
    """Remove top-level frontmatter keys (and their indented blocks) in place.

    Returns the keys that were found and removed.
    """
    split = _split(path)
    if not split:
        return []
    body, end, lines = split
    kept, removed, skipping = [], [], False
    for line in body:
        key = _key(line)
        if key is not None:
            skipping = key in keys
            if skipping:
                removed.append(key)
        elif skipping and (not line.strip() or line[0] in " \t-"):
            continue
        if not skipping:
            kept.append(line)
    if removed:
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(["---"] + kept + lines[end:]) + "\n")
    return removed


def find_skills(root, followlinks=False):
    """Yield (name, skill_dir, description) for every SKILL.md under root.

    Follow symlinks only for trusted trees (the user's own library). Visited
    real paths are tracked so link loops can't run forever.
    """
    seen = set()
    for dirpath, dirnames, filenames in os.walk(root, followlinks=followlinks):
        real = os.path.realpath(dirpath)
        if real in seen:
            dirnames[:] = []
            continue
        seen.add(real)
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "node_modules"]
        if "SKILL.md" in filenames:
            fm = read_frontmatter(os.path.join(dirpath, "SKILL.md"))
            name = fm.get("name") or os.path.basename(dirpath)
            yield name, dirpath, fm.get("description", "")
            dirnames[:] = []


def safe_name(name):
    return re.sub(r"[^\w.-]", "-", name) or "skill"
