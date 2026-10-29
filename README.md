# Scout

**Verify an AI agent skill before you install it.**

The skill marketplace exploded in 2026. Every week brings a new repo with a slick README and a stats-heavy post. Most are fine. Some quietly duplicate a skill you already have. Some make claims in the pitch that are just wrong. A few are built for something you would not want to run once you look past the pitch.

Scout does the check in one pass so the decision takes seconds, not twenty minutes.

```
scout https://github.com/someone/some-skill
```

It does three things:

1. **Fact-checks the pitch.** Every checkable claim (pricing, config syntax, benchmark numbers) is checked against the primary source and marked confirmed, wrong, or unverifiable.
2. **Checks overlap.** It compares the candidate against the skills you already have installed, since descriptions drive triggering.
3. **Screens the mechanism.** It flags tools whose core purpose is detection evasion, ToS-circumventing automation or fake engagement. These are flagged plainly, without assuming bad intent.

```
SCOUT — some-skill
Source: https://github.com/someone/some-skill

VERDICT: INSTALL WITH CAUTION

Claims checked: 3
  ✓ CONFIRMED — "40% cheaper per token" (source: platform.claude.com/docs/pricing)
  ✗ WRONG — config field is `effort` → actually `effortLevel` (source: code.claude.com/docs/settings)
  ? UNVERIFIABLE — "63% vs 69% on agentic coding" (no benchmark cited)

Overlap: partial overlap with your installed `ce-debug`
Safety: clear

Bottom line: real tool, sloppy pitch. The config example would silently
no-op if copy-pasted. Worth installing — don't trust the exact JSON block.
```

The verdict is always private to you. Scout never posts publicly about a skill or its author.

## Install

**Claude Code / any [Agent Skills](https://agentskills.io) host:**

```
npx skills add iamtural/scout -g
```

**Manual:** copy `skills/scout/` into your harness's skills directory (for example `~/.claude/skills/`).

## License

MIT
