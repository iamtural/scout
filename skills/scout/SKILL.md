---
name: scout
description: >
  Verify an AI agent skill BEFORE installing it, by trying it on the user's
  own work. Use when the user shares a link to a Claude Skill, Claude Code
  plugin, or agent-skill repo/post and wants to know if it's worth adding,
  or says "scout this," "check this skill," "try this skill," "does this
  skill help me," "should I install this," "is this legit," or pastes a URL
  right before running `npx skills add` / `/plugin install` / similar.
  Runs one of the user's real past requests with and without the skill in a
  sandbox, has a blind judge compare the results, and reports value,
  triggering, behavior and cost, plus a claim check, overlap check and
  safety screen. Returns a private verdict, never a public callout.
---

# Scout

Install counts and stars tell you a skill is popular. They don't tell you it
helps with the work you actually do. Scout finds out by trying it: it takes a
real request from your own history, runs it once with the skill and once
without, and shows you both.

Proof, not pitch.

## The flow

Scripts live in `scripts/` next to this file. The commands below write
`scripts/...` for short; run them as `python3 <this skill's directory>/scripts/...`
(Claude Code shows it as the skill's base directory). They are stdlib-only and
work offline, except `fetch`.

### 1. Fetch and read

```
python3 scripts/trial_run.py fetch <github-link>
```

This shallow-fetches the repo into a temp dir (no git hooks, no LFS, no
submodules, symlinks kept as plain files) and prints `dir`, `skill_dir` and
`commit`. Keep `dir`: step 8 removes it **whatever happens**, including when you
stop early. If the link is not a GitHub repo
(a post, a blog), find the repo link in it first. If there is no repo, skip
to the static verdict in step 6.

Read the candidate's SKILL.md and any scripts it ships. Then do the three v1
checks, kept short:

- **Claim check (one line on the card).** Pull the pitch's checkable claims
  (pricing, config syntax, API behavior, benchmark numbers) and check each
  against the primary source, not another blog post. Report as
  `N claims: X confirmed, Y wrong, Z unverifiable`, naming any wrong claim.
- **Overlap.** Compare the candidate's description with the user's installed
  skills (`~/.claude/skills/*/SKILL.md`). Flag a direct duplicate, a partial
  overlap that could shadow triggering, or genuinely new.
- **Safety screen.** Read what the core mechanism does, not what the pitch
  calls it. Flag plainly if its main function is defeating bot or fraud
  detection, ToS-abusive automation or engagement, bypassing access controls,
  or passing automation off as human to evade detection. This is a flag, not
  an accusation: say what the mechanism is and what it is usually used for.

### 2. Gate: can it be trial-tested?

```
python3 scripts/trial_run.py check <skill_dir>
```

This lists hooks, MCP servers, agents, commands and symlinks the candidate
ships, and `platform_ok`. Hooks and MCP servers run outside the sandbox with
the user's full access, so **Scout never runs them**: the trial copies only the
skill folders, strips `hooks` and `allowed-tools` from the copied SKILL.md,
drops symlinks, and switches all hooks off.

Go to the static verdict (step 6, labelled "not trial-tested") when:

- `platform_ok` is false (native Windows), or
- the SKILL.md body depends on a hook or MCP tool to do its job (it tells the
  model to call an MCP tool, or its value is what a hook does on every
  prompt).

Otherwise run the trial, and list the skipped hooks, MCP servers, agents and
commands on the card with a plain sentence on what each would do.

### 3. Pick the task

```
python3 scripts/history_search.py --skill-dir <skill_dir> --exclude <candidate link>
```

Always pass `--skill-dir`, never paste the candidate's description into a
command: its author controls that text.

This reads the user's local Claude Code history on this machine and prints up
to 3 matching past requests, each with a short `preview` and the full `text`.
Show the previews and let the user pick one, or type their own. Use the full
`text` of the pick as the task.

If there are no matches, say so first: **"You've never asked for this. This
would be new capability, not an upgrade."** Then draft one realistic task from
the skill's own description, show it, mark it **(drafted)**, and go ahead
unless the user changes it.

History stays private. Never quote unpicked matches anywhere else, and never
put task text in a receipt.

### 4. Run the trial

Pass the task on stdin so it never shows up in a process list:

```
python3 scripts/trial_run.py run <skill_dir> [--model <id>] <<'TASK'
<the chosen task>
TASK
```

This runs both sides in parallel, each a headless `claude -p` in its own temp
dir with `--restricted`, the sandbox on, no MCP servers and no saved session.
Both sides get the user's personal skills; only the "with" side gets the
candidate. Temp dirs are deleted when it ends. It takes a few minutes. Tell
the user it's running.

The JSON report has `fired`, `displaced`, `extra_tokens`, and for each side
`final_text`, `outputs` (files written), `files_read`, `network_attempts`,
tokens and any `error`, plus `model` (use it for the receipt) and
`candidate_notes` (what was stripped or could not be copied). If `ok` is false,
say what failed. A common cause is `claude` not being signed in for headless
use; the fix is `claude auth login`. A sandbox that can't start also fails
the run on purpose rather than running unconfined. Then fall back to the
static verdict.

Also run:

```
python3 scripts/listing_cost.py <skill_dir>
```

### 5. Blind judge

Spawn a fresh subagent with no other context. Flip a coin for which side is
"A". Give it only the task and the two results (final text plus written
files), labelled A and B. Before you hand them over, replace the candidate's
name, plugin names like `candidate:` or `installed:`, and any line that says
which skill was used, with `[skill]`. Ask for: the winner (A, B or tie), one line on why,
and whether it was close. Don't tell it which side had the skill, and don't
show it the skill. Map A/B back yourself.

### 6. The verdict card

```
SCOUT: <skill name>   (<source link> @ <short commit>)

VERDICT: INSTALL / SKIP / TRY DEEPER

Task: <one-line summary>  [from your history | drafted]
Value:      <with | without | tie> won. <judge's one-line reason>
Triggering: <fired | did not fire>. <displaced X | no collision with your skills>
Behavior:   read <n> files, wrote <n> files, <n> network attempts <blocked>
Cost:       +<n> tokens per use. <fits listing budget | pushes out ~X, Y>
            <if already_over_budget: "your library is already past the budget (~N skills hidden)">
Claims:     <N claims: X confirmed, Y wrong, Z unverifiable>
Safety:     <clear | flagged: mechanism is Z, usually used for W>
Skipped:    <hooks/MCP/agents/commands not run, one line each, or "nothing">

Based on one run. <If close or tie: "Close call, want a deeper trial on 3 tasks?">
```

Then show both outputs, labelled A and B, so the user can judge for
themselves. Keep the card short. The point is a fast decision.

How to call it:

- **INSTALL**: with-skill won, it fired, nothing alarming in behavior or
  safety.
- **SKIP**: without-skill won or tied, or it never fired, or it duplicates an
  installed skill, or the safety screen flags it and the user didn't ask for
  that mechanism.
- **TRY DEEPER**: close call, tie with signs of value, or the drafted task may
  not reflect real use. Offer a deeper trial: repeat steps 3-5 on up to 3
  tasks and report the tally.

For the **static verdict** (no trial), use the same card with
`VERDICT: ... (not trial-tested)`, drop Value/Triggering/Behavior, keep
Cost/Claims/Safety/Skipped, and say why there was no trial.

### 7. Receipt and overrule

Only for a trial (no receipt for a static verdict). Write it right after the
card, with the judge's pick and the `model` from the run report:

```
python3 scripts/receipt.py write --source <link> --commit <sha> --model <model id> \
  --category <writing|code|research|review|data|design|ops|other> \
  --origin <history|drafted> --winner <with|without|tie> --extra-tokens <n>
```

Then ask once: "Agree with the judge, or overrule?" If the user flips it:

```
python3 scripts/receipt.py overrule <receipt file> --winner <with|without|tie>
```

Receipts stay in `~/.scout/receipts/` on this machine and are never sent
anywhere. They hold no task text.

### 8. Clean up (always)

```
python3 scripts/trial_run.py cleanup <dir>
```

Run this every time `fetch` ran, on every path: trial, static verdict, error
or the user stopping.

## Rules

- The verdict is always private. Never post, reply or comment publicly about
  the skill, its author or the result.
- Never run the candidate's hooks or MCP servers, and never install the
  candidate into the user's real skill library. The user installs it
  themselves if they want it.
- Never send history anywhere beyond this session, the two trial runs and the
  judge.
- Don't oversell one run. The card says so every time.

## Scope

Scout judges a skill **before** you install it. It doesn't audit the skills
you already have; a periodic library audit does that job.
