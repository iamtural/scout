import json
import os
import tempfile
import unittest

from helpers import write
import history_search

# Synthetic transcript lines only. Never copy real history into this public repo.
LINES = [
    {"type": "user", "isSidechain": False, "timestamp": "2026-10-01T10:00:00Z",
     "message": {"content": "write the release notes for version 2.3 from the changelog and merged pull requests"}},
    {"type": "user", "isSidechain": False, "timestamp": "2026-10-02T10:00:00Z",
     "message": {"content": "what should I cook for dinner tonight with pasta and tomatoes"}},
    {"type": "user", "isSidechain": True, "timestamp": "2026-10-03T10:00:00Z",
     "message": {"content": "release notes changelog pull requests version from a subagent"}},
    {"type": "user", "isSidechain": False, "timestamp": "2026-10-04T10:00:00Z",
     "message": {"content": "<command-name>/release-notes</command-name> changelog version"}},
    {"type": "user", "isSidechain": False, "timestamp": "2026-10-05T10:00:00Z",
     "message": {"content": [{"type": "text", "text": "release notes changelog version"}]}},
    {"type": "user", "isSidechain": False, "timestamp": "2026-10-06T10:00:00Z",
     "message": {"content": "scout https://github.com/example/release-notes-skill for release notes changelog"}},
    {"type": "assistant", "message": {"content": "release notes changelog version pull requests"}},
    {"type": "user", "isSidechain": False, "isCompactSummary": True, "timestamp": "2026-10-08T10:00:00Z",
     "message": {"content": "This session is being continued. release notes changelog version pull requests /home/x"}},
    {"type": "user", "isSidechain": False, "isMeta": True, "timestamp": "2026-10-09T10:00:00Z",
     "message": {"content": "Base directory for this skill: release notes changelog version pull requests"}},
]


class HistorySearchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        path = os.path.join(self.root, "proj-a", "s1.jsonl")
        write(path, "\n".join(json.dumps(l) for l in LINES) + "\n{not json\n")
        # Exact duplicate in another project.
        write(os.path.join(self.root, "proj-b", "s2.jsonl"), json.dumps(LINES[0]) + "\n")

    def tearDown(self):
        self.tmp.cleanup()

    def run_search(self, **kw):
        return history_search.search(
            "Writes release notes from a changelog and merged pull requests", self.root, **kw)

    def test_finds_relevant_prompts_once(self):
        out = self.run_search()
        texts = [m["text"] for m in out["matches"]]
        self.assertEqual(len(texts), 2)
        self.assertEqual(sum("release notes for version 2.3" in t for t in texts), 1)
        # List-shaped content (text blocks, e.g. with an image) still counts as a prompt.
        self.assertIn("release notes changelog version", texts)

    def test_skips_noise_and_never_returns_project_paths(self):
        out = self.run_search()
        blob = json.dumps(out)
        for bad in ("subagent", "<command-name>", "dinner", "scout https", "proj-a",
                    "being continued", "Base directory", "/home/x"):
            self.assertNotIn(bad, blob)
        self.assertEqual(set(out["matches"][0]), {"preview", "text", "timestamp"})

    def test_excludes_candidate_url(self):
        write(os.path.join(self.root, "proj-c", "s3.jsonl"), json.dumps(
            {"type": "user", "isSidechain": False, "timestamp": "2026-10-07T10:00:00Z",
             "message": {"content": "is github.com/example/release-notes-skill good for release notes changelog?"}}) + "\n")
        out = self.run_search(exclude=["github.com/example/release-notes-skill"])
        self.assertTrue(all("example/release-notes-skill" not in m["text"] for m in out["matches"]))

    def test_no_match_is_empty_not_error(self):
        out = history_search.search("Generates quantum chemistry orbital diagrams", self.root)
        self.assertEqual(out["matches"], [])

    def test_limit(self):
        for i in range(6):
            write(os.path.join(self.root, f"p{i}", "s.jsonl"), json.dumps(
                {"type": "user", "isSidechain": False, "timestamp": f"2026-09-0{i + 1}T00:00:00Z",
                 "message": {"content": f"draft release notes {i} from the changelog for this version"}}) + "\n")
        self.assertEqual(len(self.run_search(limit=3)["matches"]), 3)

    def test_skill_dir_reads_description_from_file(self):
        import subprocess, sys
        from helpers import SCRIPTS, make_skill
        cand = os.path.join(self.root, "cand-skill")
        make_skill(cand, "notes", "Writes release notes from a changelog. $(touch pwned)")
        out = subprocess.run([sys.executable, os.path.join(SCRIPTS, "history_search.py"),
                              "--skill-dir", cand, "--root", self.root], capture_output=True, text=True, cwd=self.root)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertTrue(json.loads(out.stdout)["matches"])
        self.assertFalse(os.path.exists(os.path.join(self.root, "pwned")))

    def test_missing_root(self):
        out = history_search.search("anything at all here", os.path.join(self.root, "nope"))
        self.assertEqual(out, {"matches": [], "searched": 0})


if __name__ == "__main__":
    unittest.main()
