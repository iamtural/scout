# Scout

**Try an AI agent skill on your own work before you install it.**

Install counts and stars tell you a skill is popular. They don't tell you it
helps with what you actually do. Most skill pages are a pitch. Scout gets you
proof.

```
scout https://github.com/someone/some-skill
```

Scout takes a real request from your own Claude Code history, runs it once
with the skill and once without in a sandbox, and has a blind judge compare
the results. You see both and can overrule the judge. Then you get one card
(an example):

```
SCOUT: release-notes   (github.com/someone/release-notes @ 3f2a91c)

VERDICT: INSTALL

Task: draft release notes for v2.3 from the changelog   [from your history]
Value:      with won. Grouped changes by user impact; without listed commits.
Triggering: fired. No collision with your skills.
Behavior:   read 4 files, wrote 1 file, 0 network attempts
Cost:       +1,850 tokens per use. Fits your listing budget.
Claims:     3 claims: 2 confirmed, 1 unverifiable
Safety:     clear
Skipped:    nothing

Based on one run.
```

If nothing in your history matches, Scout says so: *you've never asked for
this, so it would be new capability, not an upgrade.* Then it drafts a task
and labels it drafted.

## What it checks

| Line | How |
|---|---|
| **Value** | Your task, run with and without the skill. A blind judge picks the better result. |
| **Triggering** | Whether the skill actually fired, and whether it pushed aside a skill you already have. |
| **Behavior** | Files read and written, and network attempts, during the run. |
| **Cost** | Extra tokens per use, and whether its description pushes others out of the skill listing budget. |
| **Claims** | The pitch's checkable claims, checked against primary sources. |
| **Safety** | Flags tools built for detection evasion, ToS-abusive automation or fake engagement. |

## Safety and privacy

- **Hooks and MCP servers never run.** They run outside the sandbox with your
  full access, so Scout lists them instead. A skill whose value depends on
  them gets a static read labelled "not trial-tested".
- **Each trial run is locked down:** headless Claude Code with
  `--restricted`, the sandbox on, no MCP servers, no saved session, in a
  throwaway folder that's deleted afterward. The candidate never touches your
  real skill library.
- **Your history stays on your machine.** It's searched locally. Only the one
  task you pick goes into the trial.
- **Receipts are private.** Each trial writes a small record to
  `~/.scout/receipts/`: skill, commit, model, task category, winner and token
  cost. There's no task text, and it's never sent anywhere.
- **The verdict is private.** Scout never posts about a skill or its author.

## Requirements

- macOS or Linux (the sandbox isn't available on native Windows; there Scout
  gives the static read)
- Claude Code CLI, signed in for headless use (`claude auth login`)
- `python3` (no packages needed)

## Install

```
npx skills add iamtural/scout -g
```

**Manual:** copy `skills/scout/` into your skills directory (for example
`~/.claude/skills/`).

Scout also loads in Codex and other [Agent Skills](https://agentskills.io)
hosts. The claim, overlap and safety checks work there today; trial runs use
Claude Code for now.

## Development

```
python3 -m unittest discover tests
```

Tests use a fake `claude` (`tests/fake_claude.py`) and synthetic history, so
they run offline with no model calls.

## License

MIT
