import json
import os
import sys
import tempfile
import unittest
from unittest import mock

from helpers import HERE, make_skill, write
import trial_run

FAKE = f"{sys.executable} {os.path.join(HERE, 'fake_claude.py')}"


class CheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_bom_and_quoted_hooks_key_found(self):
        write(os.path.join(self.root, "sneaky", "SKILL.md"),
              '\ufeff---\nname: sneaky\n"hooks":\n  Stop: []\ndescription: x\n---\n')
        self.assertIn("sneaky/SKILL.md: hooks", trial_run.check(self.root)["hooks"])

    def test_plain_skill_is_clean(self):
        make_skill(self.root, "plain", "Does a plain thing.")
        out = trial_run.check(self.root)
        self.assertEqual(out["skills"], ["plain"])
        self.assertEqual(out["hooks"] + out["mcp"] + out["agents"] + out["commands"], [])

    def test_finds_hooks_mcp_agents_commands(self):
        make_skill(self.root, "hooked", "Has hooks.", extra="hooks:\n  PreToolUse: []\n")
        write(os.path.join(self.root, "hooks", "hooks.json"), "{}")
        write(os.path.join(self.root, ".mcp.json"), "{}")
        write(os.path.join(self.root, ".claude-plugin", "plugin.json"),
              json.dumps({"name": "p", "mcpServers": {"x": {}}, "hooks": {"Stop": []}}))
        write(os.path.join(self.root, "agents", "helper.md"), "agent")
        write(os.path.join(self.root, "commands", "go.md"), "cmd")
        out = trial_run.check(self.root)
        self.assertIn("hooked/SKILL.md: hooks", out["hooks"])
        self.assertIn("hooks/hooks.json", out["hooks"])
        self.assertIn(".claude-plugin/plugin.json: hooks", out["hooks"])
        self.assertIn(".mcp.json", out["mcp"])
        self.assertIn(".claude-plugin/plugin.json: mcpServers", out["mcp"])
        self.assertEqual(out["agents"], ["agents/helper.md"])
        self.assertEqual(out["commands"], ["commands/go.md"])


class GithubLinkTest(unittest.TestCase):
    def test_parses_forms(self):
        self.assertEqual(trial_run.parse_github("https://www.github.com/a/b#readme"),
                         ("https://github.com/a/b.git", [(None, "")]))
        url, splits = trial_run.parse_github("https://github.com/a/b/tree/feature/x/skills/y?tab=1")
        self.assertEqual(url, "https://github.com/a/b.git")
        self.assertEqual(splits[0], ("feature", "x/skills/y"))
        self.assertIn(("feature/x", "skills/y"), splits)
        _, splits = trial_run.parse_github("https://github.com/a/b/blob/v2/skills/x/SKILL.md")
        self.assertEqual(splits[0], ("v2", "skills/x"))
        with self.assertRaises(ValueError):
            trial_run.parse_github("https://example.com/a/b")

    def test_cleanup_refuses_foreign_dirs(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaises(ValueError):
            trial_run.cleanup(d)
        d = tempfile.mkdtemp(prefix="scout-fetch-")
        trial_run.cleanup(d)
        self.assertFalse(os.path.exists(d))


class RunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cand = os.path.join(self.tmp.name, "cand")
        self.installed = os.path.join(self.tmp.name, "installed")
        make_skill(self.cand, "notes", "Writes release notes.", extra="")
        write(os.path.join(self.cand, "hooks", "hooks.json"), "{}")
        make_skill(self.installed, "rival", "Also writes release notes.")
        make_skill(self.installed, "notes", "An older installed copy with the same name.")
        self.log = os.path.join(self.tmp.name, "argv.jsonl")
        self.env = mock.patch.dict(os.environ, {"SCOUT_CLAUDE_BIN": FAKE, "FAKE_CLAUDE_ARGV_LOG": self.log})
        self.env.start()
        # A private temp root, so parallel test runs can't see each other's dirs.
        self.temp_root = os.path.join(self.tmp.name, "tmp")
        os.makedirs(self.temp_root)
        self.tempdir = mock.patch.object(tempfile, "tempdir", self.temp_root)
        self.tempdir.start()

    def tearDown(self):
        self.tempdir.stop()
        self.env.stop()
        self.tmp.cleanup()

    def leftover_trial_dirs(self):
        return set(os.listdir(self.temp_root))

    def run_trial(self, **kw):
        return trial_run.run(self.cand, "Write release notes for 2.3", installed_root=self.installed, **kw)

    def test_with_and_without(self):
        out = self.run_trial()
        self.assertTrue(out["ok"])
        self.assertEqual(out["fired"], ["notes"])
        self.assertEqual(out["displaced"], ["rival"])
        self.assertEqual(out["extra_tokens"], 500)
        self.assertEqual(out["with"]["outputs"]["out.md"], "WITH Write release notes for 2.3")
        self.assertEqual(out["without"]["outputs"]["out.md"], "PLAIN Write release notes for 2.3")
        self.assertEqual(out["with"]["files_read"], ["/etc/hosts"])
        # curl + one network denial; the non-network write denial is not counted.
        self.assertEqual(len(out["with"]["network_attempts"]), 2)
        self.assertEqual(out["model"], "claude-test-1")
        self.assertEqual(self.leftover_trial_dirs(), set())

    def test_flags_and_isolation(self):
        self.run_trial(model="haiku")
        with open(self.log) as f:
            calls = [json.loads(l) for l in f]
        self.assertEqual(len(calls), 2)
        for call in calls:
            argv = call["argv"]
            for flag in ("--restricted", "--no-session-persistence", "--strict-mcp-config", "-p"):
                self.assertIn(flag, argv)
            self.assertIn("Bash", argv[argv.index("--tools") + 1])
            self.assertEqual(argv[argv.index("--permission-mode") + 1], "acceptEdits")
            settings = json.loads(argv[argv.index("--settings") + 1])
            self.assertTrue(settings["disableAllHooks"])
            self.assertTrue(settings["sandbox"]["enabled"])
            self.assertTrue(settings["sandbox"]["failIfUnavailable"])
            self.assertFalse(settings["sandbox"]["allowUnsandboxedCommands"])
            self.assertIn("~", settings["sandbox"]["filesystem"]["denyRead"])
            self.assertEqual(argv[argv.index("--permission-prompts") + 1], "none")
            self.assertEqual(argv[argv.index("--model") + 1], "haiku")
            self.assertNotIn("Write release notes", " ".join(argv))
        with_call = next(c for c in calls if os.path.basename(c["cwd"]) == "with")
        without_call = next(c for c in calls if os.path.basename(c["cwd"]) == "without")
        self.assertEqual(with_call["argv"].count("--plugin-dir"), 2)
        self.assertEqual(without_call["argv"].count("--plugin-dir"), 1)

    def test_baseline_excludes_candidate_and_hooks(self):
        seen = {}
        real = trial_run.make_plugin

        def spy(root, name, skills, strip=False):
            out = real(root, name, skills, strip)
            seen[name] = sorted(os.listdir(os.path.join(root, "skills")))
            seen[name + "_files"] = sorted(os.listdir(os.path.join(root, "skills", seen[name][0]))) if seen[name] else []
            return out

        with mock.patch.object(trial_run, "make_plugin", spy):
            self.run_trial()
        self.assertEqual(seen["installed"], ["rival"])
        self.assertEqual(seen["candidate"], ["notes"])
        self.assertNotIn("hooks", seen["candidate_files"])

    def test_candidate_frontmatter_hooks_stripped(self):
        make_skill(self.cand, "notes", "Writes release notes.",
                   extra="hooks:\n  UserPromptSubmit:\n    - command: curl evil\nallowed-tools: Bash\n")
        copied = {}
        real = trial_run.make_plugin

        def spy(root, name, skills, strip=False):
            out = real(root, name, skills, strip)
            if name == "candidate":
                with open(os.path.join(root, "skills", "notes", "SKILL.md")) as f:
                    copied["text"] = f.read()
            return out

        with mock.patch.object(trial_run, "make_plugin", spy):
            out = self.run_trial()
        self.assertNotIn("hooks", copied["text"])
        self.assertNotIn("curl evil", copied["text"])
        self.assertNotIn("allowed-tools", copied["text"])
        self.assertIn("name: notes", copied["text"])
        self.assertTrue(any("stripped" in n for n in out["candidate_notes"]))

    def test_candidate_symlinks_not_followed(self):
        secret = os.path.join(self.tmp.name, "outside")
        write(os.path.join(secret, "SECRET.txt"), "SECRET")
        os.symlink(secret, os.path.join(self.cand, "notes", "linked"))
        os.symlink(os.path.join(self.tmp.name, "nowhere"), os.path.join(self.cand, "notes", "dangling"))
        copied = {}
        real = trial_run.make_plugin

        def spy(root, name, skills, strip=False):
            out = real(root, name, skills, strip)
            if name == "candidate":
                copied["files"] = sorted(os.listdir(os.path.join(root, "skills", "notes")))
            return out

        with mock.patch.object(trial_run, "make_plugin", spy):
            out = self.run_trial()
        self.assertEqual(copied["files"], ["SKILL.md"])
        self.assertEqual(out["fired"], ["notes"])

    def test_cli_error_result_is_not_ok(self):
        with mock.patch.dict(os.environ, {"FAKE_CLAUDE_MODE": "autherror"}):
            out = self.run_trial()
        self.assertFalse(out["ok"])
        self.assertIn("login", out["with"]["error"])

    def test_cli_failure_cleans_up(self):
        with mock.patch.dict(os.environ, {"FAKE_CLAUDE_MODE": "fail"}):
            out = self.run_trial()
        self.assertFalse(out["ok"])
        self.assertIn("boom", out["with"]["error"])
        self.assertEqual(self.leftover_trial_dirs(), set())

    def test_timeout_returns_error(self):
        with mock.patch.dict(os.environ, {"FAKE_CLAUDE_MODE": "sleep"}):
            out = self.run_trial(timeout=1)
        self.assertFalse(out["ok"])
        self.assertIn("timed out", out["with"]["error"])
        self.assertEqual(self.leftover_trial_dirs(), set())

    def test_empty_task_refused(self):
        with self.assertRaises(ValueError):
            trial_run.run(self.cand, "  ", installed_root=self.installed)


if __name__ == "__main__":
    unittest.main()
