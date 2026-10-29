---
name: scout
description: >
  Verify an AI agent skill BEFORE installing it. Use when the user shares a
  link to a Claude Skill, Claude Code plugin, or agent-skill repo/post and
  wants to know if it's worth adding — or says "scout this," "check this
  skill," "should I install this," "verify this skill," "is this legit," or
  pastes a URL right before running `npx skills add` / `/plugin install` /
  similar. Fact-checks the pitch's checkable claims against primary-source
  docs, checks overlap against the user's already-installed skills, and
  screens for tools whose core mechanism is detection evasion, ToS
  circumvention, or fake engagement. Returns a private verdict — never a
  public callout of the source.
---

# Skill Scout

Before you add one more thing to your skill library, find out if it's real,
if it's redundant, and if it's safe — in the time it takes to read the
verdict, not the time it takes to manually check three things yourself.

## Why this exists

Skill marketplaces exploded in 2026. Every week there's a new repo with a
compelling pitch, a slick README, and a stats-heavy X post announcing it.
Most of them are fine. Some silently duplicate something you already have.
Some make a claim in the pitch that's just wrong — a benchmark number with no
source, a config example with the wrong field name, a "this ends soon" price
deadline that turns out to check out (or doesn't). And a few are built for
something you wouldn't actually want to run, once you look past the pitch.

Checking all of this by hand — pulling the repo, reading the actual docs it
claims to be based on, comparing against what you've already got — takes
real time. Nobody does it consistently. So people either install everything
(bloat, silent trigger conflicts) or install nothing new (missing the
genuinely good stuff). Skill Scout does the check in one pass so the
decision takes seconds, not twenty minutes.

## What it checks

Give Skill Scout a URL — a GitHub repo, an X/Twitter post, a blog post
pitching a skill or plugin. It runs three passes and returns one verdict.

### 1. Claim verification

Extract every checkable claim from the pitch: pricing, specific config
syntax, API/library behavior, benchmark numbers, "as used internally at
X" attributions, deadline/pricing-window claims. For each one:

- Find the actual primary source the claim is about (official docs, the
  platform's own pricing page, the actual settings schema) — not a second
  blog post repeating the same claim.
- Mark each claim **CONFIRMED** (with the source), **WRONG** (with what's
  actually true), or **UNVERIFIABLE** (no primary source exists to check
  against — common for unsourced benchmark numbers; say so plainly rather
  than either trusting or rejecting it).
- A wrong claim in the pitch doesn't automatically sink the tool — a
  copy-paste config error in a README is different from a fabricated
  benchmark used to sell the tool. Note the distinction in the verdict.

### 2. Overlap check

Read the user's currently installed skills (their descriptions — that's
what drives triggering, so that's what matters for overlap). Compare against
what the candidate skill actually does, not just its name. Flag:

- **Direct duplicate** — an installed skill already does this
- **Partial overlap** — meaningfully different but triggers on similar
  phrasing, risking one silently shadowing the other
- **Genuinely new** — no overlap, fills a real gap

If the user's current skill list isn't already available in context, ask for
it (or, in Claude Code specifically, list `~/.claude/skills/*/SKILL.md`
description fields directly).

### 3. Safety screen

Read what the tool's core mechanism actually does — not what the pitch calls
it. Flag clearly, in plain language, if the tool's primary function is:

- Defeating bot/fraud detection, browser fingerprinting evasion, or
  "passes every anti-bot test" style claims
- Automating engagement, follows, or interactions on a platform in a way
  that platform's terms of service would consider abuse
- Scraping or reproducing content in a way that bypasses a platform's own
  access controls
- Anything else designed to make automated behavior indistinguishable from
  a human specifically to evade detection

This is a **flag, not an accusation.** Many of these mechanisms have
legitimate, defensive, or research uses. Say plainly what the mechanism is
and what it's typically used for, and let the user decide — do not silently
skip the flag because the tool *could* be used innocently.

## Output — the verdict

Always private to the user. Never post, reply, or comment publicly about
the source, its creator, or the verdict — this is the user's decision tool,
not a public review.

```
SKILL SCOUT — [tool name]
Source: [URL]

VERDICT: INSTALL / SKIP / INSTALL WITH CAUTION

Claims checked: [N]
  ✓ CONFIRMED — [claim] (source: [link])
  ✗ WRONG — [claim] → actually [correct fact] (source: [link])
  ? UNVERIFIABLE — [claim] (no primary source found)

Overlap: [none / partial overlap with X / duplicates Y]

Safety: [clear / flagged — mechanism is Z, typically used for W]

Bottom line: [1-2 sentences — the actual recommendation and the single
biggest reason for it]
```

Keep it short. The whole point is a fast, trustworthy decision — not a
report nobody reads.

## Scope (v1)

Skill Scout evaluates a skill **before** you install it, from a link. It
does not audit skills you already have installed — for that, run a periodic
audit against your full library instead (see the Skill Audit Prompt pattern:
inventory, per-skill check, conflicts table, rewrite recommendations). The
two are complementary: Scout gates new arrivals, an audit periodically
cleans the shelf.
