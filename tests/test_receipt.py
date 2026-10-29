import json
import os
import tempfile
import unittest
from unittest import mock

import helpers  # noqa: F401  (puts the scripts dir on sys.path)
import receipt

GOOD = dict(source="https://github.com/example/some-skill", commit="abc1234", model="claude-sonnet-5-5",
            category="writing", origin="history", winner="with", extra_tokens=1200)


class ReceiptTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {"SCOUT_HOME": self.tmp.name})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_writes_only_allowed_fields(self):
        path = receipt.write(**GOOD)
        self.assertTrue(path.startswith(os.path.join(self.tmp.name, "receipts")))
        with open(path) as f:
            record = json.load(f)
        self.assertEqual(set(record), {"scout_receipt", "created", "source", "commit", "model", "task_category",
                                       "task_origin", "judge_winner", "user_winner", "winner", "extra_tokens"})
        self.assertEqual(record["judge_winner"], "with")
        self.assertIsNone(record["user_winner"])

    def test_rejects_free_text(self):
        bad_values = [
            {"category": "release notes for the Q3 customer quote"},
            {"source": "my secret task text"},
            {"source": "https://example.com/my%20secret%20task"},
            {"commit": "not a sha"},
            {"model": "claude with spaces"},
            {"winner": "A"},
            {"origin": "typed"},
            {"extra_tokens": "12"},
        ]
        for bad in bad_values:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                receipt.write(**{**GOOD, **bad})
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "receipts")))

    def test_overrule_keeps_judge_pick(self):
        path = receipt.write(**GOOD)
        record = receipt.overrule(path, "without")
        self.assertEqual(record["judge_winner"], "with")
        self.assertEqual(record["user_winner"], "without")
        self.assertEqual(record["winner"], "without")

    def test_overrule_refuses_outside_files(self):
        outside = os.path.join(self.tmp.name, "elsewhere.json")
        with open(outside, "w") as f:
            json.dump({}, f)
        with self.assertRaises(ValueError):
            receipt.overrule(outside, "tie")


if __name__ == "__main__":
    unittest.main()
